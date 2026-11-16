#!/usr/bin/env python3
"""
GKD 订阅源自动更新脚本
每天定时拉取活跃订阅源并合并发布
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests
import json5

# 活跃订阅源列表
ACTIVE_SUBSCRIPTIONS = [
    {
        "name": "奥怪订阅",
        "owner": "aoguai",
        "repo": "subscription",
        "branch": "custom",
        "file": "dist/aoguai_gkd.json5",
        "mirror_url": "https://gitmirror.com/aoguai/subscription/raw/custom/dist/aoguai_gkd.json5",
        "license": "MIT",
        "status": "active"
    },
    {
        "name": "甘霖订阅",
        "owner": "ganlinte",
        "repo": "GKD-subscription",
        "branch": "main",
        "file": "dist/ganlin_gkd.json5",
        "mirror_url": "https://cdn.jsdelivr.net/gh/ganlinte/GKD-subscription@main/dist/ganlin_gkd.json5",
        "license": "MIT",
        "status": "active"
    },
    {
        "name": "梦念逍遥订阅",
        "owner": "MengNianxiaoyao",
        "repo": "gkd-subscription",
        "branch": "main",
        "file": "gkd.json5",
        "mirror_url": "https://registry.npmmirror.com/gkd-subscription/latest/files/dist/gkd.json5",
        "license": "MIT",
        "status": "active"
    },
    {
        "name": "Lin-arm 订阅",
        "owner": "Lin-arm",
        "repo": "GKD-subscription",
        "branch": "master",
        "file": "dist/Lin-arm_gkd.json5",
        "mirror_url": "https://cdn.jsdelivr.net/gh/Lin-arm/GKD-subscription@master/dist/Lin-arm_gkd.json5",
        "license": "MIT",
        "status": "active"
    },
    {
        "name": "Mrlc 订阅",
        "owner": "mrlctate",
        "repo": "GKD-subscription",
        "branch": "main",
        "file": "gkd.json5",
        "mirror_url": "https://cdn.jsdelivr.net/gh/mrlctate/GKD-subscription@main/gkd.json5",
        "license": "MIT",
        "status": "active"
    },
    {
        "name": "LenorEric 订阅",
        "owner": "LenorEric",
        "repo": "GKD-subscription",
        "branch": "master",
        "file": "dist/gkd.json5",
        "mirror_url": "https://cdn.jsdelivr.net/gh/LenorEric/GKD-subscription@master/dist/gkd.json5",
        "license": "MIT",
        "status": "active"
    }
]

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "GKD-Subscription-Updater"
}


def fetch_content(url: str, use_mirror: bool = True) -> dict | None:
    """
    获取订阅源内容
    优先使用原始链接，失败则使用镜像链接
    """
    urls = [
        f"https://raw.githubusercontent.com/{ACTIVE_SUBSCRIPTIONS[url.split('/')[1]]['owner']}/{ACTIVE_SUBSCRIPTIONS[url.split('/')[1]]['repo']}/{ACTIVE_SUBSCRIPTIONS[url.split('/')[1]]['branch']}/{ACTIVE_SUBSCRIPTIONS[url.split('/')[1]]['file']}",
        url
    ]
    
    for u in urls:
        try:
            response = requests.get(u, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                return json5.loads(response.text)
        except Exception as e:
            print(f"❌ Failed to fetch {u}: {e}")
            continue
    
    return None


def merge_subscriptions(all_rules: list, sub: dict) -> None:
    """合并订阅源规则到总列表"""
    if not sub:
        print(f"⚠️  Skipping {all_rules['name']}: no content fetched")
        return
    
    # 提取 appRules 和 globalRules
    app_rules = sub.get('appRules', [])
    global_rules = sub.get('globalRules', [])
    
    # 添加来源标识
    for rule in app_rules + global_rules:
        rule.setdefault('source', all_rules['name'])
        rule.setdefault('license', all_rules.get('license', 'Unknown'))
    
    all_rules['appRules'].extend(app_rules)
    all_rules['globalRules'].extend(global_rules)
    
    print(f"✅ Merged {len(app_rules)} app rules + {len(global_rules)} global rules from {all_rules['name']}")


def generate_import_config(all_rules: dict) -> dict:
    """生成导入配置文件"""
    return {
        "version": 1,
        "subscriptions": [
            {
                "name": sub['name'],
                "url": sub['mirror_url'],
                "license": sub.get('license', 'Unknown'),
                "status": sub['status'],
                "lastUpdated": datetime.utcnow().isoformat()
            }
            for sub in ACTIVE_SUBSCRIPTIONS
        ],
        "mergedRules": {
            "appRulesCount": len(all_rules['appRules']),
            "globalRulesCount": len(all_rules['globalRules']),
            "lastMerged": datetime.utcnow().isoformat(),
            "sources": len(ACTIVE_SUBSCRIPTIONS)
        }
    }


def main():
    print("🚀 Starting GKD subscriptions update...")
    print(f"📋 Total active sources: {len(ACTIVE_SUBSCRIPTIONS)}")
    
    all_rules = {
        "appRules": [],
        "globalRules": [],
        "versionName": "1.0.0",
        "versionCode": 1,
        "id": "cn.gekkxxlloxo.gkd-aggregated",
        "lastUpdated": datetime.utcnow().isoformat()
    }
    
    # 拉取并合并所有订阅源
    for sub in ACTIVE_SUBSCRIPTIONS:
        print(f"\n📥 Fetching {sub['name']}...")
        content = fetch_content(sub['mirror_url'])
        merge_subscriptions(all_rules, content)
    
    # 保存合并后的规则
    dist_dir = Path(__file__).parent.parent / "dist"
    dist_dir.mkdir(exist_ok=True)
    
    merged_file = dist_dir / "gkd-aggregated.json5"
    with open(merged_file, 'w', encoding='utf-8') as f:
        f.write(json5.dumps(all_rules, indent=2, ensure_ascii=False))
    print(f"\n💾 Saved merged rules to {merged_file}")
    
    # 生成导入配置文件
    import_config = generate_import_config(all_rules)
    config_file = dist_dir / "import-config.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(import_config, f, indent=2, ensure_ascii=False)
    print(f"💾 Saved import config to {config_file}")
    
    print("\n✅ Update complete!")


if __name__ == "__main__":
    main()
