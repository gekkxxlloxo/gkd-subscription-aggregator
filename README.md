# 🎯 GKD Active Subscriptions

GKD 活跃订阅源自动整合仓库，每日自动更新，汇集所有仍在维护的活跃订阅源。

## 📦 项目简介

本项目自动聚合**仍在活跃维护**的 GKD 订阅源，提供：

- ✅ **自动更新**：GitHub Actions 每天定时拉取最新规则
- ✅ **完整整合**：包含所有活跃订阅源
- ✅ **一键导入**：提供标准导入配置文件
- ✅ **国内加速**：所有链接均提供镜像加速方案

## 🚀 快速开始

### 方式一：下载导入配置文件（推荐）

点击以下链接下载导入配置文件，然后在 GKD 应用中选择"从文件导入"：

📥 [下载导入配置](import-config.json)

### 方式二：应用内逐个添加

在 GKD 应用的"订阅"设置中，逐个添加以下订阅源：

| 订阅源 | 订阅链接（镜像加速） |
|--------|---------------------|
| 🎯 奥怪订阅 | [链接](https://gitmirror.com/aoguai/subscription/raw/custom/dist/aoguai_gkd.json5) |
| 💎 甘霖订阅 | [链接](https://cdn.jsdelivr.net/gh/ganlinte/GKD-subscription@main/dist/ganlin_gkd.json5) |
| 📱 梦念逍遥订阅 | [链接](https://registry.npmmirror.com/gkd-subscription/latest/files/dist/gkd.json5) |
| 🔧 Lin-arm 订阅 | [链接](https://cdn.jsdelivr.net/gh/Lin-arm/GKD-subscription@master/dist/Lin-arm_gkd.json5) |
| 🛠️ Mrlc 订阅 | [链接](https://cdn.jsdelivr.net/gh/mrlctate/GKD-subscription@main/gkd.json5) |
| ⚡ LenorEric 订阅 | [链接](https://cdn.jsdelivr.net/gh/LenorEric/GKD-subscription@master/dist/gkd.json5) |

### 方式三：访问网页版

查看实时更新的整合页面（如果已部署到 GitHub Pages）：

🌐 [访问整合页面](https://gekkxxlloxo.github.io/gkd-active-subscriptions/)

## 📊 当前包含的订阅源

| 名称 | 仓库 | 状态 | 规则数 | 许可证 |
|------|------|------|--------|--------|
| 奥怪订阅 | [aoguai/subscription](https://github.com/aoguai/subscription) | 🟢 活跃 | ~5000+ | MIT |
| 甘霖订阅 | [ganlinte/GKD-subscription](https://github.com/ganlinte/GKD-subscription) | 🟢 活跃 | ~3000+ | MIT |
| 梦念逍遥订阅 | [MengNianxiaoyao/gkd-subscription](https://github.com/MengNianxiaoyao/gkd-subscription) | 🟢 活跃 | 870 | MIT |
| Lin-arm 订阅 | [Lin-arm/GKD-subscription](https://github.com/Lin-arm/GKD-subscription) | 🟢 活跃 | ~2000+ | MIT |
| Mrlc 订阅 | [mrlctate/GKD-subscription](https://github.com/mrlctate/GKD-subscription) | 🟢 活跃 | ~500+ | MIT |
| LenorEric 订阅 | [LenorEric/GKD-subscription](https://github.com/LenorEric/GKD-subscription) | 🟢 活跃 | ~300+ | MIT |

## 🔧 技术实现

### 自动更新流程

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Actions                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  每天 00:00 UTC 自动触发                               │  │
│  └──────────────────────┬────────────────────────────────┘  │
│                         ▼                                     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Python 脚本拉取 6 个活跃订阅源                          │  │
│  │  • aoguai/subscription                                 │  │
│  │  • ganlinte/GKD-subscription                           │  │
│  │  • MengNianxiaoyao/gkd-subscription                    │  │
│  │  • Lin-arm/GKD-subscription                            │  │
│  │  • mrlctate/GKD-subscription                           │  │
│  │  • LenorEric/GKD-subscription                          │  │
│  └──────────────────────┬────────────────────────────────┘  │
│                         ▼                                     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  合并所有规则到 gkd-aggregated.json5                   │  │
│  │  生成导入配置文件 import-config.json                   │  │
│  └──────────────────────┬────────────────────────────────┘  │
│                         ▼                                     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  发布到 dist/ 目录                                     │  │
│  │  部署到 GitHub Pages                                   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 目录结构

```
.
├── .github/
│   └── workflows/
│       └── update-subscriptions.yml  # GitHub Actions 工作流
├── scripts/
│   └── fetch_and_merge.py            # 订阅源拉取和合并脚本
├── dist/                              # 发布目录（GitHub Pages）
│   ├── gkd-aggregated.json5          # 合并后的规则文件
│   ├── import-config.json            # 导入配置文件
│   └── index.html                    # 网页版导入页面
├── README.md
└── ...
```

### 手动触发更新

如果需要立即更新，可以在 GitHub 仓库页面手动触发工作流：

1. 进入仓库的 "Actions" 标签页
2. 选择 "Update GKD Subscriptions" 工作流
3. 点击 "Run workflow" 按钮

## 📝 导入方法

### GKD 应用内导入

1. 打开 GKD 应用
2. 进入"设置" → "订阅"
3. 点击"添加订阅"
4. 选择"从文件导入"
5. 选择 `import-config.json` 文件

### 或者逐个添加

在"订阅"页面点击"添加订阅"，逐个输入上述订阅源链接。

## 🔄 更新频率

- **自动更新**：每天 UTC 时间 00:00（北京时间 08:00）
- **手动更新**：可在 GitHub Actions 页面手动触发

## 📄 许可证

本项目整合的内容遵循各订阅源原有的许可证协议。

---

**维护者**: [gekkxxlloxo](https://github.com/gekkxxlloxo)

**相关项目**: [GKD](https://github.com/hid4/gkd)
