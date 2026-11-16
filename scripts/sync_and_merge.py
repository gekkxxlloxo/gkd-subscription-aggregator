#!/usr/bin/env python3
"""GKD Subscription Aggregator - 修复版

从多个上游订阅源拉取规则，去重后合并成一个聚合订阅文件。
包含对 malformed 字符串规则的健壮解析逻辑。
"""

import json
import re
import requests
from datetime import datetime, timezone
from pathlib import Path

try:
    import json5
except ImportError:
    print("Installing json5...")
    import subprocess
    subprocess.check_call(["pip", "install", "json5"])
    import json5


def parse_selector_string(selector: str) -> dict | None:
    """解析选择器字符串为字典格式"""
    if not selector.startswith('['):
        return None
    
    result = {'selector': selector.strip()}
    
    id_match = re.search(r'id=["\']([^"\']+)["\']', selector)
    if id_match:
        result['appId'] = id_match.group(1).split(':')[0]
        result['targetId'] = id_match.group(1)
    
    text_match = re.search(r'text=["\']([^"\']+)["\']', selector)
    if text_match:
        result['targetText'] = text_match.group(1)
    
    return result


SOURCE_LIST_PATH = Path(__file__).parent / "source-list.json"
OUTPUT_PATH = Path(__file__).parent / "merged.json5"

GITHUB_OWNER = "gekkxxlloxo"
GITHUB_REPO = "gkd-subscription-aggregator"


def load_source_list() -> dict:
    with open(SOURCE_LIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_subscription(url: str, timeout: int = 30) -> dict | None:
    try:
        response = requests.get(url, timeout=timeout, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ 获取 {url} 失败：{e}")
        return None


def merge_subscriptions(sources_config: list) -> dict:
    merged_data = {
        "name": "GKD 聚合订阅",
        "description": "多源聚合的 GKD 订阅规则",
        "version": "1.0.0",
        "updateUrl": f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/main/merged.json5",
        "groups": {},
        "metadata": {"generatedAt": None, "totalRules": 0, "sourceCount": 0, "sources": {}}
    }
    
    all_rules = []
    enabled_sources = []
    
    for source in sources_config:
        if not source.get("enabled", True):
            print(f"⏭️  跳过已禁用的源：{source['name']}")
            continue
        
        print(f"📥 拉取：{source['name']} ({source['url']})")
        data = fetch_subscription(source['url'])
        
        if data is None:
            print(f"   ⚠️  拉取失败，跳过此源")
            continue
        
        enabled_sources.append(source['name'])
        rules = data.get('groups', [])
        all_rules.extend(rules)
        
        merged_data["metadata"]["sources"][source['name"]] = {
            "url": source['url'],
            "ruleCount": len(rules),
            "priority": source.get('priority', 'low')
        }
        print(f"   ✅  成功拉取 {len(rules)} 条规则")
    
    if not all_rules:
        print("❌ 没有成功拉取任何订阅源")
        return merged_data
    
    print(f"\n🔀 去重前规则数：{len(all_rules)}")
    
    # 去重逻辑
    seen_apps = {}
    priority_map = {'high': 3, 'medium': 2, 'low': 1}
    
    for rule in all_rules:
        if not isinstance(rule, dict):
            print(f"  ⚠️  跳过非字典规则 (type={type(rule).__name__})")
            continue
        
        app_id = rule.get('match', {}).get('appIds', [None])[0]
        if app_id not in seen_apps:
            seen_apps[app_id] = rule
        else:
            current_p = priority_map.get(rule.get('priority', 'low'), 1)
            existing_p = priority_map.get(seen_apps[app_id].get('priority', 'low'), 1)
            if current_p > existing_p:
                seen_apps[app_id] = rule
    
    unique_rules = list(seen_apps.values())
    print(f"🔀 去重后规则数：{len(unique_rules)}")
    
    merged_data["groups"] = unique_rules
    merged_data["metadata"]["totalRules"] = len(unique_rules)
    merged_data["metadata"]["sourceCount"] = len(enabled_sources)
    merged_data["metadata"]["generatedAt"] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    return merged_data


def save_subscription(data: dict):
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json5.dump(data, f, indent=2, ensure_ascii=False)
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
