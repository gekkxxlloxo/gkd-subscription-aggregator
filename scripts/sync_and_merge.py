#!/usr/bin/env python3
"""GKD Subscription Aggregator

从多个上游订阅源拉取规则，去重后合并成一个聚合订阅文件。
"""

import json
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


# Configuration
SOURCE_LIST_PATH = Path(__file__).parent / "source-list.json"
OUTPUT_PATH = Path(__file__).parent / "merged.json5"


# GitHub repository info
GITHUB_OWNER = "gekkxxlloxo"
GITHUB_REPO = "gkd-subscription-aggregator"


def load_source_list() -> dict:
    """加载订阅源配置文件"""
    with open(SOURCE_LIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_subscription(url: str, timeout: int = 30) -> dict | None:
    """从指定 URL 获取订阅规则"""
    try:
        response = requests.get(url, timeout=timeout, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ 获取 {url} 失败：{e}")
        return None


def deduplicate_rules(rules: list, sources: list) -> list:
    """按 app_id 去重，保留优先级高的规则"""
    seen_apps = {}
    priority_map = {'high': 3, 'medium': 2, 'low': 1}
    
    for rule in rules:
        app_id = rule.get('match', {}).get('appIds', [None])[0]
        if app_id not in seen_apps:
            seen_apps[app_id] = rule
        else:
            current_priority = priority_map.get(rule.get('priority', 'low'), 1)
            existing_priority = priority_map.get(seen_apps[app_id].get('priority', 'low'), 1)
            if current_priority > existing_priority:
                seen_apps[app_id] = rule
    
    return list(seen_apps.values())


def merge_subscriptions(sources_config: list) -> dict:
    """合并所有启用的订阅源"""
    merged_data = {
        "name": "GKD 聚合订阅",
        "description": "多源聚合的 GKD 订阅规则，自动去重和更新",
        "version": "1.0.0",
        "updateUrl": f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/main/merged.json5",
        "importUrl": None,
        "groups": {},
        "metadata": {
            "generatedAt": None,
            "totalRules": 0,
            "sourceCount": 0,
            "sources": {}
        }
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
        
        merged_data["metadata"]["sources"][source['name']] = {
            "url": source['url'],
            "ruleCount": len(rules),
            "priority": source.get('priority', 'low')
        }
        
        print(f"   ✅  成功拉取 {len(rules)} 条规则")
    
    if not all_rules:
        print("❌ 没有成功拉取任何订阅源")
        return merged_data
    
    # 去重
    print(f"\n🔀 去重前规则数：{len(all_rules)}")
    unique_rules = deduplicate_rules(all_rules, sources_config)
    print(f"🔀 去重后规则数：{len(unique_rules)}")
    
    # 按来源分组
    merged_data["groups"] = unique_rules
    merged_data["metadata"]["totalRules"] = len(unique_rules)
    merged_data["metadata"]["sourceCount"] = len(enabled_sources)
    merged_data["metadata"]["generatedAt"] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    return merged_data


def save_subscription(data: dict):
    """保存聚合后的订阅文件"""
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json5.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n💾 已保存到：{OUTPUT_PATH}")


def main():
    print("🚀 GKD Subscription Aggregator")
    print("=" * 50)
    
    # 加载配置
    config = load_source_list()
    sources = config.get("sources", [])
    
    print(f"📋 配置了 {len(sources)} 个订阅源\n")
    
    # 合并订阅
    merged_data = merge_subscriptions(sources)
    
    # 保存结果
    save_subscription(merged_data)
    
    # 输出订阅链接
    print(f"\n📌 订阅链接:")
    print(f"   https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/main/merged.json5")
    print(f"\n✨ 完成！")


if __name__ == "__main__":
    main()
