#!/usr/bin/env python3
"""字符检查工具 - 专门检测 AI 生成代码中的字符错误

主要检测：
1. 文件路径中横杠（-）被错误替换为下划线（_）
2. Unicode 不可见字符（零宽字符、Bidi 控制符等）
3. 智能引号、破折号等中文标点混入代码
4. 路径分隔符混用（\\ 与 /）

用法：
    python scripts/char_check.py [路径]
    默认检查当前目录（排除 .git 和 venv）
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote


# 需要检测的 Unicode 特殊字符
SPECIAL_CHARS = {
    '\u200b': '零宽空格 (Zero-Width Space)',
    '\u200c': '零宽非连接符 (Zero-Width Non-Joiner)',
    '\u200d': '零宽连接符 (Zero-Width Joiner)',
    '\u200e': '从左到右标记 (Left-to-Right Mark)',
    '\u200f': '从右到左标记 (Right-to-Left Mark)',
    '\u2013': '短破折号 (U+2013)',
    '\u2014': '长破折号 (Em Dash)',
    '\u2018': '左单引号 (U+2018)',
    '\u2019': '右单引号 (U+2019)',
    '\u201c': '左双引号 (U+201C)',
    '\u201d': '右双引号 (U+201D)',
    '\u2026': '省略号 (Ellipsis)',
    '\u2028': '行分隔符 (Line Separator)',
    '\u2029': '段落分隔符 (Paragraph Separator)',
    '\u202f': '窄空格 (Narrow No-Break Space)',
    '\u2060': '零宽不换行空格 (Zero-Width No-Break Space)',
    '\ufeff': '零宽不换行空格 (BOM/Zero-Width No-Break Space)',
    '\uff0d': '全角横杠 (Fullwidth Hyphen)',
    '\uff3b': '全角左方括号 (Fullwidth Left Square Bracket)',
    '\uff3d': '全角右方括号 (Fullwidth Right Square Bracket)',
    '\uff3f': '全角左括号 (Fullwidth Left Parenthesis)',
}

# 代码中常见的智能引号正则
SMART_QUOTE_PATTERN = re.compile(r'[\u2018\u2019\u201c\u201d]')
DASH_PATTERN = re.compile(r'[\u2013\u2014]')
PATH_MIX_PATTERN = re.compile(r'[^/\\]:\\[^\\]|[^/\\]:/[^/]')


def check_path_hyphens(file_path: Path) -> list:
    """检测文件路径中横杠（-）是否被错误替换为下划线（_）"""
    issues = []
    relative_path = file_path.relative_to(Path.cwd())
    
    # 检查路径各部分是否应该包含横杠
    parts = relative_path.parts
    for i, part in enumerate(parts):
        # 常见的项目结构模式，可能需要横杠
        hyphen_patterns = [
            r'source-list',
            r'sync-and-merge',
            r'gkd-subscription',
            r'ad-filter',
            r'char-check',
        ]
        
        for pattern in hyphen_patterns:
            # 将模式中的 - 替换为 _ 后匹配
            underscore_pattern = pattern.replace('-', '_')
            if underscore_pattern in part.lower():
                issues.append(
                    f"路径部分 '{part}' 可能应该是 '{part.replace('_', '-')}' "
                    f"(包含横杠的 '{pattern}')"
                )
    
    return issues


def check_unicode_issues(content: str, file_path: Path) -> list:
    """检测文件内容中的 Unicode 特殊字符"""
    issues = []
    lines = content.split('\n')
    
    # 智能引号和破折号的 Unicode 码点集合（用于去重）
    smart_quote_chars = set('\u2018\u2019\u201c\u201d\u2013\u2014')
    
    for line_num, line in enumerate(lines, 1):
        if line.strip().startswith('#'):
            continue
        
        reported_positions = set()  # 记录已报告的位置，避免重复
        
        # 检测特殊 Unicode 字符
        for char, name in SPECIAL_CHARS.items():
            pos = 0
            while True:
                pos = line.find(char, pos)
                if pos == -1:
                    break
                
                # 跳过智能引号和破折号（单独处理）
                if char in smart_quote_chars:
                    pos += 1
                    continue
                
                col = pos + 1
                key = (line_num, col)
                if key not in reported_positions:
                    reported_positions.add(key)
                    issues.append(
                        f"行 {line_num}, 列 {col}: 发现特殊字符 {name} (U+{ord(char):04X})"
                    )
                pos += 1
        
        # 检测智能引号（在代码中不应该出现）
        for match in SMART_QUOTE_PATTERN.finditer(line):
            col = match.start() + 1
            key = (line_num, col)
            if key not in reported_positions:
                reported_positions.add(key)
                issues.append(
                    f"行 {line_num}, 列 {col}: 发现智能引号 (应使用直引号')"
                )
        
        # 检测破折号
        for match in DASH_PATTERN.finditer(line):
            col = match.start() + 1
            key = (line_num, col)
            if key not in reported_positions:
                reported_positions.add(key)
                issues.append(
                    f"行 {line_num}, 列 {col}: 发现破折号 (应使用 -- 或 -)"
                )
    
    return issues


def check_path_separators(content: str, file_path: Path) -> list:
    r"""检测路径分隔符混用

    主要检测：
    1. Windows 绝对路径中的反斜杠（如 C:\Users\...）
    2. 路径分隔符混用（同一字符串中既有 / 又有 \\）
    """
    issues = []
    
    if file_path.suffix not in ['.py', '.js', '.json', '.yaml', '.yml', '.toml']:
        return []
    
    # 跳过检查脚本自身（避免误报 Unicode 转义序列）
    if file_path.name == 'char_check.py':
        return []
    
    lines = content.split('\n')
    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        
        # 跳过注释行
        if stripped.startswith('#') or stripped.startswith('//'):
            continue
        
        # 检测 Windows 绝对路径：C:\ 或 D:\ 等
        if re.search(r'[A-Z]:\\[a-zA-Z]', stripped, re.IGNORECASE):
            issues.append(
                f"行 {line_num}: 发现 Windows 绝对路径 (建议使用正斜杠 / 或 Path)"
            )
            continue
        
        # 检测相对路径中的反斜杠（在引号内，且不是转义序列）
        quoted_paths = re.findall(r'["\']([^"\']*\\[^"\']*)["\']', stripped)
        for qp in quoted_paths:
            # 排除 Unicode 转义序列（如 \u200b, \x41）和常见转义（\n, \t, \r）
            if re.search(r'\\[uxX]', qp):
                continue
            if re.match(r'^[^\\]*\\[nrt]', qp):
                continue
            issues.append(
                f"行 {line_num}: 发现反斜杠路径 '{qp}' (建议使用正斜杠 / 或 Path)"
            )
    
    return issues


def check_file_content(file_path: Path) -> list:
    """检查单个文件的内容"""
    issues = []
    
    try:
        # 跳过二进制文件
        if file_path.suffix in ['.pyc', '.so', '.dll', '.exe', '.bin', '.png', '.jpg', '.jpeg', '.gif', '.ico']:
            return []
        
        # 读取文件内容
        try:
            content = file_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                content = file_path.read_text(encoding='gbk')
            except:
                return []  # 二进制文件，跳过
        
        # 检查 Unicode 问题
        issues.extend(check_unicode_issues(content, file_path))
        
        # 检查路径分隔符问题
        issues.extend(check_path_separators(content, file_path))
        
    except Exception as e:
        issues.append(f"读取文件失败: {e}")
    
    return issues


def check_project_paths() -> list:
    """检查项目路径结构"""
    issues = []
    project_root = Path.cwd()
    
    # 检查常见的项目路径
    common_paths = [
        'source-list.json',
        'sync_and_merge.py',
        'gkd-subscription-aggregator',
        'char-check.py',
    ]
    
    for path in common_paths:
        full_path = project_root / path
        if full_path.exists():
            # 检查是否应该包含横杠
            if 'source-list' in path:
                issues.append(
                    f"文件 '{path}' 可能应该是 'source-list.json' (包含横杠)"
                )
            elif 'sync_and_merge' in path:
                issues.append(
                    f"文件 '{path}' 可能应该是 'sync-and-merge.py' (包含横杠)"
                )
    
    return issues


def main():
    print("=" * 70)
    print("🔍 字符检查工具 - AI 生成代码字符错误检测")
    print("=" * 70)
    print()
    
    target_dir = Path.cwd()
    if len(sys.argv) > 1:
        target_dir = Path(sys.argv[1]).resolve()
    
    print(f"检查目录: {target_dir}")
    print()
    
    all_issues = []
    files_checked = 0
    
    # 检查项目路径
    print("📁 检查项目路径结构...")
    path_issues = check_project_paths()
    if path_issues:
        all_issues.extend(path_issues)
        for issue in path_issues:
            print(f"  ⚠️  {issue}")
    print()
    
    # 检查文件内容
    print("📄 检查文件内容...")
    exclude_dirs = {'.git', 'venv', '.venv', '__pycache__', 'node_modules', '.tox', '.mypy_cache'}
    
    for root, dirs, files in os.walk(target_dir):
        # 排除指定目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            file_path = Path(root) / file
            
            # 跳过大文件和二进制文件
            if file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB
                continue
            
            if file_path.suffix in ['.pyc', '.so', '.dll', '.exe', '.bin']:
                continue
            
            files_checked += 1
            issues = check_file_content(file_path)
            if issues:
                all_issues.extend(issues)
                print(f"  ⚠️  {file_path.relative_to(target_dir)}:")
                for issue in issues:
                    print(f"      {issue}")
    
    print()
    print("=" * 70)
    print(f"✅ 检查完成！共检查 {files_checked} 个文件")
    print(f"📊 发现问题: {len(all_issues)} 个")
    
    if all_issues:
        print()
        print("🔴 详细问题列表:")
        for i, issue in enumerate(all_issues, 1):
            print(f"  {i}. {issue}")
        print()
        print("💡 建议:")
        print("  - 路径中的横杠应使用 '-' 而不是 '_'")
        print("  - 代码中应使用直引号 ' 和 \" 而不是智能引号")
        print("  - 路径分隔符应使用正斜杠 / 而不是反斜杠 \")
        print("  - 避免使用不可见 Unicode 字符")
    else:
        print()
        print("🎉 未发现字符错误！代码质量良好。")
    
    print("=" * 70)
    
    # 返回退出码
    return 1 if all_issues else 0


if __name__ == '__main__':
    sys.exit(main())
