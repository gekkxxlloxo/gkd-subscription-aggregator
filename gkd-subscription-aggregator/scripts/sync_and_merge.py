#!/usr/bin/env python3
"""
GKD 订阅聚合脚本
- 从多个上游源拉取订阅规则
- 自动去重和合并
- 生成最终的订阅文件
"""

import json
import re
import requests
from requests.exceptions import SSLError
import time
from datetime import datetime, timezone
from pathlib import Path
import json5
from urllib3.exceptions import SSLError as Urllib3SSLError


def parse_selector_string(selector_str: str) -> dict | None:
    """
    将 GKD 选择器字符串转换为字典格式
    
    支持两种格式：
    1. 单个选择器：[id="com.example:id/button"]
    2. 多个选择器：[text="点击"] + [id="com.example:id/close"]
    
    返回：dict 或 None（如果解析失败）
    """
    if not selector_str or not isinstance(selector_str, str):
        return None
    
    # 移除空格
    selector_str = selector_str.strip()
    
    # 匹配 [key=value] 格式，支持多个选择器用 + 连接
    pattern = r'\[([^\]=]+)=([^\]]+)\]'
    matches = re.findall(pattern, selector_str)
    
    if not matches:
        return None
    
    # 转换为字典
    result = {}
    for key, value in matches:
        # 去除值两边的引号（如果有）
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        result[key.strip()] = value
    
    return result if result else None


def load_source_list(config_path: str) -> dict:
    """加载订阅源列表配置"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json5.load(f)


def fetch_subscription(url: str, timeout: int = 30, max_retries: int = 3) -> dict | None:
    """从指定 URL 获取订阅规则（带重试和 SSL 错误处理）"""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }, allow_redirects=True)
            response.raise_for_status()
            # JSON5 文件需要使用 json5 库解析（支持单引号和注释）
            return json5.loads(response.text)
        except (Urllib3SSLError, SSLError) as e:
            last_error = e
            if attempt < max_retries - 1:
                print(f"⚠️  SSL 错误，{url} 重试 {attempt + 1}/{max_retries}...")
                time.sleep(2)
                continue
            else:
                print(f"❌ {url}: 获取失败（SSL 错误，已重试 {max_retries} 次）")
                return None
        except Exception as e:
            print(f"❌ 获取 {url} 失败：{e}")
            return None
    
    return None


def deduplicate_rules(rules: list, sources: list) -> list:
    """
    去重规则
    策略：按 app_id 去重，保留优先级高的来源
    """
    seen_apps = {}
    priority_map = {'high': 3, 'medium': 2, 'low': 1}
    
    for rule in rules:
        # 支持多种 app_id 获取方式
        app_id = rule.get('appId') or rule.get('match', {}).get('appIds', [None])[0]
        if not app_id:
            # 没有 app_id 的规则直接保留
            seen_apps[f"global_{id(rule)}"] = rule
            continue
        
        if app_id not in seen_apps:
            seen_apps[app_id] = rule
        else:
            # 比较优先级
            current_priority = priority_map.get(rule.get('priority', 'low'), 1)
            existing_priority = priority_map.get(seen_apps[app_id].get('priority', 'low'), 1)
            
            if current_priority > existing_priority:
                seen_apps[app_id] = rule
    
    return list(seen_apps.values())


def merge_subscriptions(sources_data: list) -> dict:
    """合并多个订阅源"""
    merged = {
        "name": "GKD 聚合订阅",
        "updateUrl": None,
        "importUrl": None,
        "groups": []
    }
    
    all_rules = []
    
    for source in sources_data:
        if not source.get('enabled', True):
            print(f"⏭️  跳过未启用的源：{source['name']}")
            continue
        
        print(f"📥 获取 {source['name']} 的订阅...")
        rules = fetch_subscription(source['url'])
        
        if rules:
            # 为规则添加来源信息（支持两种数据结构：groups 和 apps）
            rule_count = 0
            
            # 处理 groups 结构（传统格式）
            for group in rules.get('groups', []):
                rules_list = group.get('rules', [])
                for idx, rule in enumerate(rules_list):
                    # 处理 JSON 字符串规则（包括单个字符的字符串元素）
                    if isinstance(rule, str):
                        # 尝试直接解析为 JSON
                        try:
                            rule = json5.loads(rule)
                        except:
                            # 尝试拼接所有后续字符串元素
                            chunks = []
                            for i in range(idx, len(rules_list)):
                                item = rules_list[i]
                                if isinstance(item, str):
                                    chunks.append(item)
                                else:
                                    break  # 遇到非字符串元素就停止收集
                            
                            if len(chunks) > 1:
                                joined = ''.join(chunks)
                                # 先尝试作为 JSON 解析
                                try:
                                    rule = json5.loads(joined)
                                    print(f"  ✓  {source['name']}: 已拼接 {len(chunks)} 个字符的规则字符串")
                                except:
                                    # 再尝试作为选择器字符串解析
                                    parsed = parse_selector_string(joined)
                                    if parsed:
                                        rule = parsed
                                        print(f"  ✓  {source['name']}: 已拼接 {len(chunks)} 个字符的选择器字符串")
                                    else:
                                        print(f"  ⚠️  {source['name']}: 跳过无法解析的规则字符串")
                                        continue
                            else:
                                print(f"  ⚠️  {source['name']}: 跳过无法解析的规则字符串")
                                continue
                    if not isinstance(rule, dict):
                        print(f"  ⚠️  {source['name']}: 跳过非字典规则 (type={type(rule).__name__})")
                        continue
                    rule['source'] = source['name']
                    rule['priority'] = source.get('priority', 'low')
                    all_rules.append(rule)
                    rule_count += 1
            
            # 处理 apps 结构（现代格式）
            for app in rules.get('apps', []):
                # 每个 app 可能有 groups 数组（每个 group 包含 rules）
                for group in app.get('groups', []):
                    rules_list = group.get('rules', [])
                    for idx, rule in enumerate(rules_list):
                        # 处理 JSON 字符串规则（包括单个字符的字符串元素）
                        if isinstance(rule, str):
                            # 尝试直接解析为 JSON
                            try:
                                rule = json5.loads(rule)
                            except:
                                # 尝试拼接所有后续字符串元素（Adpro-Team 源的特殊情况）
                                chunks = []
                                for i in range(idx, len(rules_list)):
                                    item = rules_list[i]
                                    if isinstance(item, str):
                                        chunks.append(item)
                                    else:
                                        break  # 遇到非字符串元素就停止收集
                                
                                if len(chunks) > 1:
                                    joined = ''.join(chunks)
                                    # 先尝试作为 JSON 解析
                                    try:
                                        rule = json5.loads(joined)
                                        print(f"  ✓  {source['name']}: 已拼接 {len(chunks)} 个字符的规则字符串")
                                    except:
                                        # 再尝试作为选择器字符串解析
                                        parsed = parse_selector_string(joined)
                                        if parsed:
                                            rule = parsed
                                            print(f"  ✓  {source['name']}: 已拼接 {len(chunks)} 个字符的选择器字符串")
                                        else:
                                            print(f"  ⚠️  {source['name']}: 跳过无法解析的规则字符串")
                                            continue
                                else:
                                    # 只有一个字符串或没有字符串可拼接，直接跳过
                                    print(f"  ⚠️  {source['name']}: 跳过无法解析的规则字符串")
                                    continue
                        if not isinstance(rule, dict):
                            print(f"  ⚠️  {source['name']}: 跳过非字典规则 (type={type(rule).__name__})")
                            continue
                        rule['source'] = source['name']
                        rule['priority'] = source.get('priority', 'low')
                        rule['appId'] = app.get('id')
                        all_rules.append(rule)
                        rule_count += 1
                
                # 某些 app 可能直接有 rules 数组（兼容性处理）
                if 'groups' not in app and app.get('rules'):
                    rules_list = app.get('rules', [])
                    for idx, rule in enumerate(rules_list):
                        # 处理 JSON 字符串规则（包括单个字符的字符串元素）
                        if isinstance(rule, str):
                            try:
                                rule = json5.loads(rule)
                            except:
                                # 尝试拼接连续的字符串元素（Adpro-Team 源的特殊情况）
                                # 查找从当前位置开始的连续字符串
                                chunks = []
                                for i in range(idx, len(rules_list)):
                                    item = rules_list[i]
                                    if isinstance(item, str):
                                        chunks.append(item)
                                    # 跳过非字符串元素（如整数），继续收集字符串
                                if len(chunks) > 1:
                                    joined = ''.join(chunks)
                                    try:
                                        rule = json5.loads(joined)
                                        print(f"  ✓  {source['name']}: 已拼接 {len(chunks)} 个字符的规则字符串")
                                    except:
                                        print(f"  ⚠️  {source['name']}: 跳过无法解析的规则字符串")
                                        continue
                                else:
                                    print(f"  ⚠️  {source['name']}: 跳过无法解析的规则字符串")
                                    continue
                        if not isinstance(rule, dict):
                            print(f"  ⚠️  {source['name']}: 跳过非字典规则 (type={type(rule).__name__})")
                            continue
                        rule['source'] = source['name']
                        rule['priority'] = source.get('priority', 'low')
                        rule['appId'] = app.get('id')
                        all_rules.append(rule)
                        rule_count += 1
            
            # 处理 globalGroups
            for group in rules.get('globalGroups', []):
                rules_list = group.get('rules', [])
                for idx, rule in enumerate(rules_list):
                    # 处理 JSON 字符串规则（包括单个字符的字符串元素）
                    if isinstance(rule, str):
                        try:
                            rule = json5.loads(rule)
                        except:
                            # 尝试拼接所有后续字符串元素
                            chunks = []
                            for i in range(idx, len(rules_list)):
                                item = rules_list[i]
                                if isinstance(item, str):
                                    chunks.append(item)
                                else:
                                    break
                            
                            if len(chunks) > 1:
                                joined = ''.join(chunks)
                                # 先尝试作为 JSON 解析
                                try:
                                    rule = json5.loads(joined)
                                    print(f"  ✓  {source['name']}: 已拼接 {len(chunks)} 个字符的规则字符串")
                                except:
                                    # 再尝试作为选择器字符串解析
                                    parsed = parse_selector_string(joined)
                                    if parsed:
                                        rule = parsed
                                        print(f"  ✓  {source['name']}: 已拼接 {len(chunks)} 个字符的选择器字符串")
                                    else:
                                        print(f"  ⚠️  {source['name']}: 跳过无法解析的规则字符串")
                                        continue
                            else:
                                print(f"  ⚠️  {source['name']}: 跳过无法解析的规则字符串")
                                continue
                    if not isinstance(rule, dict):
                        print(f"  ⚠️  {source['name']}: 跳过非字典规则 (type={type(rule).__name__})")
                        continue
                    rule['source'] = source['name']
                    rule['priority'] = source.get('priority', 'low')
                    rule['isGlobal'] = True
                    all_rules.append(rule)
                    rule_count += 1
            
            print(f"✅ {source['name']}: 获取成功，规则数：{rule_count}")
        else:
            print(f"❌ {source['name']}: 获取失败")
    
    # 去重
    print(f"\n🔄 去重规则...")
    unique_rules = deduplicate_rules(all_rules, sources_data)
    print(f"📊 去重后规则数：{len(unique_rules)}")
    
    # 重新分组（按来源分组）
    groups_by_source = {}
    for rule in unique_rules:
        source = rule.get('source', 'Unknown')
        if source not in groups_by_source:
            groups_by_source[source] = {
                "name": f"{source} 规则",
                "enabled": True,
                "rules": []
            }
        groups_by_source[source]['rules'].append(rule)
    
    merged['groups'] = list(groups_by_source.values())
    
    return merged


def save_subscription(data: dict, output_path: str):
    """保存订阅文件"""
    # 添加元数据
    data['metadata'] = {
        'generatedAt': datetime.now(timezone.utc).isoformat(),
        'totalRules': sum(len(g['rules']) for g in data.get('groups', [])),
        'sourceCount': len(data['groups'])
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json5.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 已保存至：{output_path}")


def update_source_list(config_path: str, success_count: int, error_count: int):
    """更新源列表的最后更新时间"""
    config = load_source_list(config_path)
    config['last_updated'] = datetime.now(timezone.utc).isoformat()
    config['stats'] = {
        'successful_sources': success_count,
        'failed_sources': error_count
    }
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 GKD 订阅聚合脚本")
    print("=" * 60)
    
    # 获取项目根目录
    root_dir = Path(__file__).parent.parent
    config_path = root_dir / 'source-list.json'
    output_path = root_dir / 'merged.json5'
    
    # 加载配置
    config = load_source_list(config_path)
    sources = config.get('sources', [])
    enabled_sources = [s for s in sources if s.get('enabled', True)]
    
    print(f"📋 配置了 {len(sources)} 个订阅源，其中 {len(enabled_sources)} 个启用\n")
    
    # 合并订阅
    merged = merge_subscriptions(enabled_sources)
    
    # 保存结果
    save_subscription(merged, output_path)
    
    # 更新配置
    success_count = sum(1 for s in enabled_sources if any(g['name'].startswith(s['name']) for g in merged['groups']))
    error_count = len(enabled_sources) - success_count
    update_source_list(config_path, success_count, error_count)
    
    print("\n" + "=" * 60)
    print(f"✅ 聚合完成！共 {len(enabled_sources)} 个源，{merged['metadata']['totalRules']} 条规则")
    print("=" * 60)
    
    # 输出订阅链接（用户需要手动替换占位符）
    print("\n📌 订阅链接（请替换为您的仓库 URL）:")
    print(f"   https://raw.githubusercontent.com/YOUR_USERNAME/gkd-subscription-aggregator/main/merged.json5")
    print("\n⚠️  提示：请在 GitHub 仓库中更新 merged.json5 的 updateUrl 和 importUrl 字段")


if __name__ == '__main__':
    main()
