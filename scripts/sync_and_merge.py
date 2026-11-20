#!/usr/bin/env python3
"""GKD Subscription Aggregator - 修复版

从多个上游订阅源拉取规则，去重后合并成一个聚合订阅文件。

修复要点（相对初版）：
1. 引号错位导致的 SyntaxError（[source['name"] -> [source['name']）。
2. 上游返回的是 JSON5（含单引号 / 无引号键名），必须用 json5 解析，
   不能用 response.json()。
3. GKD 订阅的真实结构是顶层 {"apps": [...], "globalGroups": [...]}，
   规则在 apps[].groups[].rules[] 里，不存在顶层 groups 数组。
   初版按 data['groups'] 取值，永远拿到 0 条规则。
4. 去重键用 app 的 id 字段（apps[].id），不是 match.appIds。
5. 输出路径与订阅链接一致，产物写回仓库根目录 merged.json5。
6. 产物内容无变化时保留原文件，避免每次定时运行都产生仅时间戳不同的空提交。
"""

import json
import sys
import tarfile
import io
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    import json5
except ImportError:
    print("Installing json5...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "json5"])
    import json5


SOURCE_LIST_PATH = Path(__file__).parent / "source-list.json"
CUSTOM_RULES_PATH = Path(__file__).parent / "custom-rules.json5"
OUTPUT_PATH = Path(__file__).parent.parent / "merged.json5"

GITHUB_OWNER = "gekkxxlloxo"
GITHUB_REPO = "gkd-subscription-aggregator"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def load_source_list() -> dict:
    with open(SOURCE_LIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_custom_rules() -> dict:
    """读取常驻自定义规则（本地文件，非远程订阅，不会被 CI 覆盖）。

    文件不存在或解析失败时返回空结构，保证合并流程不中断。
    """
    if not CUSTOM_RULES_PATH.exists():
        print("ℹ️  未找到 custom-rules.json5，跳过自定义规则")
        return {"apps": [], "globalGroups": []}
    try:
        data = json5.loads(CUSTOM_RULES_PATH.read_text(encoding="utf-8"))
        apps = data.get("apps") or []
        global_groups = data.get("globalGroups") or []
        if not isinstance(apps, list):
            apps = []
        if not isinstance(global_groups, list):
            global_groups = []
        print(f"📝 加载自定义规则：{len(apps)} 个应用 / {len(global_groups)} 个全局组")
        return {"apps": apps, "globalGroups": global_groups}
    except Exception as e:
        print(f"⚠️  自定义规则解析失败，跳过：{type(e).__name__}: {e}")
        return {"apps": [], "globalGroups": []}


def apply_custom_rules(merged_apps: dict, merged_groups: dict,
                       custom: dict, priority_map: dict) -> tuple[int, int]:
    """把自定义规则并入已合并的 app / globalGroups。

    - app 按 id 匹配：已存在则按 group.key 合并，key 冲突时自定义覆盖上游
      （用于修正上游那条点不到节点的开屏规则）；不存在则新增。
    - globalGroups 按 key 合并，key 相同自定义覆盖。
    返回 (新增或覆盖的 app 数, 新增或覆盖的 group 数)。
    """
    custom_priority = 4  # 高于 high(3)，保证自定义覆盖同名 app
    added_apps = 0
    merged_group_count = 0

    for app in custom.get("apps", []):
        if not isinstance(app, dict):
            continue
        app_id = app.get("id")
        if not app_id:
            continue
        custom_groups = app.get("groups") or []
        if not isinstance(custom_groups, list):
            custom_groups = []

        existing = merged_apps.get(app_id)
        if existing is None:
            merged_apps[app_id] = {
                "app": app,
                "priority": custom_priority,
                "source": "custom-rules.json5",
            }
            added_apps += 1
            merged_group_count += len(custom_groups)
            continue

        # 已有该 app：按 group.key 合并，自定义覆盖同名 key
        base_app = existing["app"]
        base_groups = base_app.get("groups")
        if not isinstance(base_groups, list):
            base_groups = []
        key_to_index = {}
        for idx, g in enumerate(base_groups):
            if isinstance(g, dict) and g.get("key") is not None:
                key_to_index[g.get("key")] = idx

        for cg in custom_groups:
            if not isinstance(cg, dict):
                continue
            ck = cg.get("key")
            if ck is not None and ck in key_to_index:
                base_groups[key_to_index[ck]] = cg  # 自定义覆盖
            else:
                base_groups.append(cg)
            merged_group_count += 1
        base_app["groups"] = base_groups

    for g in custom.get("globalGroups", []):
        if not isinstance(g, dict):
            continue
        key = g.get("key")
        gkey = f"global:{key}"
        merged_groups[gkey] = {
            "group": g,
            "priority": custom_priority,
            "source": "custom-rules.json5",
        }
        merged_group_count += 1

    return added_apps, merged_group_count


def _http_get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _fetch_with_fallback(url: str, mirror_urls: list, timeout: int = 45,
                         retries: int = 2) -> bytes | None:
    """先试主 URL，失败再依次尝试镜像。

    raw.githubusercontent.com 在部分网络下会 TLS 中断或被限流，
    镜像（jsDelivr / npm registry）可显著提高成功率。
    """
    candidates = [url] + list(mirror_urls or [])
    for raw_url in candidates:
        for attempt in range(1, retries + 1):
            try:
                return _http_get(raw_url, timeout=timeout)
            except Exception as e:
                print(f"   ↻ 尝试 {attempt}/{retries} 失败："
                      f"{raw_url} -> {type(e).__name__}")
                if attempt < retries:
                    time.sleep(2 * attempt)
    return None


def fetch_subscription(url: str, mirror_urls: list | None = None,
                       timeout: int = 45) -> dict | None:
    """拉取并解析一个订阅源。上游多为 JSON5，必须用 json5 解析。"""
    raw = _fetch_with_fallback(url, mirror_urls or [], timeout=timeout)
    if raw is None:
        print(f"❌ 所有地址均获取失败：{url}")
        return None

    try:
        return json5.loads(raw.decode("utf-8"))
    except Exception as e:
        print(f"❌ 解析 {url} 失败：{type(e).__name__}: {e}")
        return None


def fetch_npm_package(url: str, mirror_urls: list | None = None,
                      timeout: int = 60) -> dict | None:
    """npm 托管的源需要从 tarball 里取 dist/gkd.json5。"""
    raw = _fetch_with_fallback(url, mirror_urls or [], timeout=timeout)
    if raw is None:
        print(f"❌ 所有地址均获取失败：{url}")
        return None

    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
            for member in tf.getmembers():
                if member.name.endswith("dist/gkd.json5"):
                    data = tf.extractfile(member).read().decode("utf-8")
                    return json5.loads(data)
    except Exception as e:
        print(f"❌ 解析 npm tarball {url} 失败：{type(e).__name__}: {e}")
        return None

    print(f"❌ npm 包内未找到 dist/gkd.json5：{url}")
    return None


def normalize(data: dict) -> tuple[list, list]:
    """把不同源的订阅结构归一化为 (apps, globalGroups)。

    GKD 订阅的标准结构：
        {"apps": [{"id": "...", "name": "...", "groups": [...]}],
         "globalGroups": [...]}
    """
    if not isinstance(data, dict):
        return [], []

    apps = data.get("apps") or []
    global_groups = data.get("globalGroups") or []

    if not isinstance(apps, list):
        apps = []
    if not isinstance(global_groups, list):
        global_groups = []

    return apps, global_groups


def merge_subscriptions(sources_config: list) -> dict:
    merged = {
        "id": 0,
        "name": "GKD 聚合订阅",
        "version": 202,
        "author": "gekkxxlloxo",
        "supportUri": f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/issues",
        "checkUpdateUrl": (
            f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}"
            "/main/merged.json5"
        ),
        "categories": [],
        "globalGroups": [],
        "apps": [],
    }

    priority_map = {"high": 3, "medium": 2, "low": 1}
    merged_apps: dict[str, dict] = {}
    merged_groups: dict[str, dict] = {}
    enabled_sources: list[str] = []
    source_stats: dict[str, dict] = {}

    for source in sources_config:
        if not source.get("enabled", True):
            print(f"⏭️  跳过已禁用的源：{source['name']}")
            continue

        name = source["name"]
        url = source["url"]
        print(f"📥 拉取：{name} ({url})")

        if source.get("type") == "npm":
            data = fetch_npm_package(url, source.get("mirror_urls") or [])
        else:
            data = fetch_subscription(url, source.get("mirror_urls") or [])

        if data is None:
            print("   ⚠️  拉取失败，跳过此源")
            continue

        apps, global_groups = normalize(data)
        if not apps and not global_groups:
            print("   ⚠️  源内无 apps / globalGroups，跳过此源")
            continue

        enabled_sources.append(name)

        # 去重应用：同一 appId 保留优先级更高的源
        for app in apps:
            if not isinstance(app, dict):
                continue
            app_id = app.get("id")
            if not app_id:
                continue
            p = priority_map.get(source.get("priority", "low"), 1)
            existing = merged_apps.get(app_id)
            if existing is None:
                merged_apps[app_id] = {
                    "app": app,
                    "priority": p,
                    "source": name,
                }
            elif p > existing["priority"]:
                merged_apps[app_id] = {
                    "app": app,
                    "priority": p,
                    "source": name,
                }

        # 全局规则组：按 key 去重
        for g in global_groups:
            if not isinstance(g, dict):
                continue
            key = g.get("key")
            gkey = f"global:{key}"
            p = priority_map.get(source.get("priority", "low"), 1)
            existing = merged_groups.get(gkey)
            if existing is None:
                merged_groups[gkey] = {"group": g, "priority": p, "source": name}
            elif p > existing["priority"]:
                merged_groups[gkey] = {"group": g, "priority": p, "source": name}

        source_stats[name] = {
            "url": url,
            "appCount": len(apps),
            "globalGroupCount": len(global_groups),
            "priority": source.get("priority", "low"),
        }
        print(f"   ✅ {len(apps)} 个应用 / {len(global_groups)} 个全局组")

    # 并入常驻自定义规则（本地文件，每次同步都会带上，不会被覆盖）
    custom = load_custom_rules()
    added_apps, merged_group_count = apply_custom_rules(
        merged_apps, merged_groups, custom, priority_map
    )
    if added_apps or merged_group_count:
        print(f"   ✅ 自定义规则已并入：{added_apps} 个新应用 / "
              f"{merged_group_count} 个规则组")

    if not merged_apps and not merged_groups:
        print("❌ 没有成功拉取任何订阅源")
        merged["metadata"] = {
            "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "totalApps": 0,
            "totalGlobalGroups": 0,
            "sourceCount": 0,
            "sources": {},
            "note": "所有源均拉取失败",
        }
        return merged

    merged["apps"] = [v["app"] for v in merged_apps.values()]
    merged["globalGroups"] = [v["group"] for v in merged_groups.values()]

    # 分类：按应用名首字归类，方便在 GKD 内检索
    categories = {}
    for app in merged["apps"]:
        nm = app.get("name") or app.get("id") or "其他"
        first = nm[0].upper() if nm else "#"
        if not first.isascii() or not first.isalnum():
            first = "#"
        categories.setdefault(first, {"key": len(categories), "name": first, "enable": False})
    merged["categories"] = list(categories.values())

    merged["metadata"] = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "totalApps": len(merged["apps"]),
        "totalGlobalGroups": len(merged["globalGroups"]),
        "sourceCount": len(enabled_sources),
        "sources": source_stats,
        "note": "此文件由 GitHub Actions 自动更新，请勿手动编辑",
    }

    print(f"\n🔀 去重后：{len(merged['apps'])} 个应用，"
          f"{len(merged['globalGroups'])} 个全局组")
    return merged


def save_subscription(data: dict):
    """写出产物。

    若产物内容（除 generatedAt 外）与现有文件一致，则保留旧文件不动，
    避免每次定时运行都产生一次仅时间戳不同的无意义提交。
    """
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = json5.dumps(data, indent=2, ensure_ascii=False)

    if OUTPUT_PATH.exists():
        try:
            old = json5.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        except Exception:
            old = None
        if isinstance(old, dict):
            old_cmp = {k: v for k, v in old.items() if k != "metadata"}
            new_cmp = {k: v for k, v in data.items() if k != "metadata"}
            old_meta = {k: v for k, v in (old.get("metadata") or {}).items()
                        if k != "generatedAt"}
            new_meta = {k: v for k, v in (data.get("metadata") or {}).items()
                        if k != "generatedAt"}
            if old_cmp == new_cmp and old_meta == new_meta:
                print("\n💾 内容无变化，保留原文件（generatedAt 不更新）")
                print(f"   {OUTPUT_PATH}")
                return

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(payload)
    print(f"\n💾 已保存到：{OUTPUT_PATH}")


def main():
    print("🚀 GKD Subscription Aggregator")
    print("=" * 50)

    config = load_source_list()
    sources = config.get("sources", [])
    print(f"📋 配置了 {len(sources)} 个订阅源\n")

    merged_data = merge_subscriptions(sources)
    save_subscription(merged_data)

    print(f"\n📌 订阅链接:")
    print(f"   https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/main/merged.json5")
    print(f"\n✨ 完成！")


if __name__ == "__main__":
    main()
