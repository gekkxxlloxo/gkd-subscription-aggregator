# GKD Subscription Aggregator

> 🚀 自动聚合多个 GKD 订阅源，智能去重，一键订阅

## 🌟 功能特点

- ✅ **自动聚合**: 从多个上游订阅源拉取规则
- ✅ **智能去重**: 按 `app_id` 去重，保留优先级高的规则
- ✅ **定时更新**: 每天北京时间 08:00 自动同步
- ✅ **手动触发**: 支持随时手动更新
- ✅ **优先级管理**: high > medium > low

## 📦 订阅源列表（6 个启用）

| 名称 | 优先级 | 覆盖应用 | 描述 |
|------|--------|----------|------|
| AIsouler | high | 1200+ | 国产应用深度优化 |
| GKD_THS | high | 2000+ | 多维护者联合更新 |
| MengNianXiaoYao | medium | 1500+ | 游戏党专属 |
| GanLin | medium | 300+ | 视频平台优化 |
| Adpro-Team | medium | 800+ | 国际应用优化 |
| AoGuai | low | 500+ | 轻量省电 |

## 🚀 快速开始

### 1. 直接使用（推荐）

直接订阅生成的聚合链接：

```
https://raw.githubusercontent.com/gekkxxlloxo/gkd-subscription-aggregator/main/merged.json5
```

### 2. 自行部署

克隆项目后运行脚本：

```bash
git clone https://github.com/gekkxxlloxo/gkd-subscription-aggregator.git
cd gkd-subscription-aggregator
pip install requests json5
python scripts/sync_and_merge.py
```

## 📄 文件说明

- `.github/workflows/sync.yml` - GitHub Actions 工作流配置
- `scripts/sync_and_merge.py` - 核心聚合脚本
- `source-list.json` - 订阅源配置文件
- `merged.json5` - 聚合输出文件
- `README.md` - 项目说明
- `DEPLOYMENT.md` - 详细部署指南

## ⚙️ 配置说明

编辑 `source-list.json` 可以：
- 添加/删除订阅源
- 调整优先级（high/medium/low）
- 启用/禁用特定源

## 🔧 高级用法

### 修改更新频率

编辑 `.github/workflows/sync.yml` 中的 cron 表达式：

```yaml
schedule:
  - cron: '0 */6 * * *'  # 每 6 小时
```

### 自定义去重策略

在 `source-list.json` 的 `settings.deduplication` 中调整：

```json
{
  "deduplication": {
    "method": "by_app_id",  // 或 "by_rule_id"
    "keep_highest_priority": true
  }
}
```

## 📊 工作流状态

查看 [Actions](https://github.com/gekkxxlloxo/gkd-subscription-aggregator/actions) 页面了解更新状态。

## 📝 许可证

MIT License
