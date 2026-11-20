# GKD Subscription Aggregator

> 自动聚合多个 GKD 订阅源，智能去重，一键订阅

## 功能特点

- **自动聚合**: 从 11 个上游订阅源拉取规则
- **智能去重**: 按 `appId` 去重，同一应用保留优先级最高源的规则
- **常驻自定义规则**: 用户发的 GKD 快照可转成规则，每次同步自动并入，不会被上游覆盖
- **定时更新**: 每天北京时间 08:00 自动同步
- **手动触发**: 支持通过 GitHub Actions 随时手动更新
- **镜像回退**: 主源失败时自动切换 jsDelivr / npmmirror / gitmirror
- **AI 代码质检**: 字符与路径检查 + Ruff lint，拦截横杠写成下划线等生成错误

## 订阅地址

```
https://raw.githubusercontent.com/gekkxxlloxo/gkd-subscription-aggregator/main/merged.json5
```

在 GKD 客户端里导入这个链接即可。当前聚合结果约 1098 个应用，以产物内 `metadata` 为准。

## 订阅源列表（11 个启用）

| 名称 | 优先级 | 说明 |
|------|--------|------|
| Lin-arm | high | 持续维护中，规则稳定 |
| AIsouler | high | 国产应用深度优化 |
| Adpro-Team | high | 规则丰富、更新频繁 |
| gkd-kit-official | high | GKD 官方订阅 |
| 九千院 | medium | 规则量大 |
| GanLin | medium | 视频平台优化 |
| MengNianXiaoYao | medium | 游戏党专属 |
| DreamXiaoYao (npm) | medium | npm 托管，速度快 |
| oklazeno | low | 轻量订阅 |
| aoguai | low | 含较多自动化规则 |
| AIsouler-Lite | low | AIsouler 精简版 |

## 自行部署

```bash
git clone https://github.com/gekkxxlloxo/gkd-subscription-aggregator.git
cd gkd-subscription-aggregator
pip install json5 ruff
python scripts/sync_and_merge.py
python scripts/char_check.py
python -m ruff check scripts/
```

产物输出到仓库根目录 `merged.json5`，与上面的订阅链接对应。

## 文件说明

| 文件 | 作用 |
|------|------|
| `.github/workflows/sync.yml` | GitHub Actions 工作流：同步、质检、校验、自动提交 |
| `scripts/sync_and_merge.py` | 核心聚合脚本 |
| `scripts/source-list.json` | 订阅源配置（脚本实际读取此文件） |
| `source-list.json` | 上面那份的镜像，改动时需同步 |
| `scripts/custom-rules.json5` | 常驻自定义规则入口 |
| `scripts/char_check.py` | 字符与路径检查 |
| `ruff.toml` | Python lint 配置 |
| `merged.json5` | 自动生成的聚合产物，需提交到仓库，勿手工编辑 |
| `AGENTS.md` | 给接手 AI 的工作说明书 |

## 配置说明

编辑 `scripts/source-list.json` 可以：

- 添加或删除订阅源
- 调整优先级（`high` / `medium` / `low`）
- 启用或禁用特定源
- 配置镜像地址（`mirror_urls`）

注意根目录 `source-list.json` 只是给人看的镜像，脚本不读它，但改动后两份必须保持一致。

## 自定义规则

`scripts/custom-rules.json5` 里的规则每次同步都会自动并入 `merged.json5`，按应用 id 和规则组 key 合并，不会被上游覆盖。规则组 key 使用 9000 以上避免冲突。

目前内置的定制规则：

- 酷狗音乐开屏广告「跳过」按钮（key 9001）
- 酷狗音乐首页信息流广告关闭按钮（key 9002）
- YouTube Morphe 跳过开头按钮（key 9003）

## 给 AI 的说明

如果你是要接手维护这个项目的 AI，请先完整阅读 [AGENTS.md](AGENTS.md)。里面有文件职责、修改流程、GitHub 操作命令、快照转规则的步骤，以及历史上踩过的坑。换了模型也不用重新摸索。

## 工作流状态

查看 [Actions](https://github.com/gekkxxlloxo/gkd-subscription-aggregator/actions) 页面了解更新状态。

## 许可证

MIT License
