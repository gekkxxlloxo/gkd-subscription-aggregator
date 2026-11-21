# AGENTS.md - 给接手 AI 的工作说明书

本文件面向 AI 助手，不是给终端用户看的。用户说明见 README.md。
接手任何修改前，先完整读一遍本文件，尤其是"铁律"和"踩过的坑"两节。

## 1. 项目是什么

一个 GitHub 仓库，定时把多个 GKD 订阅源聚合成一个文件，供 GKD 客户端订阅。

- 仓库: `gekkxxlloxo/gkd-subscription-aggregator` (分支 main)
- 订阅链接: `https://raw.githubusercontent.com/gekkxxlloxo/gkd-subscription-aggregator/main/merged.json5`
- 工作流: `.github/workflows/sync.yml`，每天 UTC 00:00 (北京时间 08:00) 自动跑，也支持手动 `workflow_dispatch`
- 当前规模: 14 个源，约 1128 个 app (以远程 merged.json5 的 metadata 为准)

数据流:

```
scripts/source-list.json  ──> scripts/sync_and_merge.py  ──> merged.json5
scripts/custom-rules.json5 ──> (同上，按 app id + group key 并入)
                                      │
                              GitHub Actions 校验并提交
                                      │
                                  用户更新订阅
```

## 2. 文件地图

| 文件 | 作用 | 能否直接改 |
|---|---|---|
| `scripts/source-list.json` | **脚本实际读取**的源清单 | 可以，改完必须同步根目录那份 |
| `source-list.json` | 根目录镜像，给人看/给其他工具用；脚本不读 | 可以，必须与 scripts 版逐字一致 |
| `scripts/custom-rules.json5` | 常驻自定义规则，每次同步自动并入产物 | 可以，这是做定制规则的唯一入口 |
| `scripts/sync_and_merge.py` | 核心聚合逻辑: 拉取、镜像回退、去重、合并、写产物 | 谨慎改，改完必须本地跑一遍 |
| `scripts/char_check.py` | 字符/路径检查，拦截 AI 写错横杠和隐藏字符 | 一般不用改 |
| `ruff.toml` | Python lint 配置，只开 E + F | 一般不用改 |
| `.github/workflows/sync.yml` | CI: 同步、质检、校验产物、自动提交 | 谨慎改 |
| `merged.json5` | 自动生成产物，**必须提交到仓库** | 永远不要手工编辑 |

## 3. 铁律 (违反会出事故)

1. **改订阅源必须同时改两份清单**。脚本只读 `scripts/source-list.json`，根目录那份是摆设，但两份内容必须一致，否则下一个人会被误导。这是本项目踩过的最大的坑。
2. **不要手工编辑 `merged.json5`**。它由 CI 生成并提交。本地"改一下产物"在下次同步时会被覆盖，而且大文件通过 API 单文件上传容易失败。
3. **不要把 `merged.json5` 加进 .gitignore**。早期误忽略过，结果 CI 跑通但用户订阅不到任何更新。
4. **不要扫描 `merged.json5` 做字符检查**。里面的智能引号来自上游源，不是我们写的代码，扫描必定误报并把 CI 卡死。char_check.py 已将其列入 EXCLUDE_FILES，不要删掉这条。
5. **只做检测，不做自动修复**。当前 CI 发现问题就让步骤失败，不会自动改代码。修完必须手动推送再触发。
6. **自定义规则的 group key 一律 >= 9000**，避免与上游规则的 key 撞车被覆盖。
7. **写完任何代码，本地先跑三条检查再推**，见第 7 节。

## 4. 订阅源配置

`scripts/source-list.json` 每个源字段:

- `name`: 显示名，也就是去重日志里的来源名
- `url`: 主地址
- `mirror_urls`: 主地址失败时依次尝试 (jsDelivr / npmmirror / gitmirror 等)
- `type`: 只有 npm 托管的源写 `"npm"`，脚本会从 tarball 里取 `dist/gkd.json5`；其余不写
- `priority`: `high` (3) / `medium` (2) / `low` (1)；同一 appId 保留优先级高的源
- `enabled`: false 即跳过
- `description`: 说明

新增源的姿势: 先 curl 实测 url 能返回 JSON5，再追加到两份清单，本地跑一次同步确认 app 数增加，然后推送并触发 CI。不要凭记忆拼 GitHub 仓库名，横杠/下划线混淆是本项目的高发错误。

## 5. 定制规则 SOP (用户发来 GKD 快照时)

用户会发来一个 zip，里面是 GKD 抓包快照: 一张截图 + 一个 `时间戳.json` 节点树。

### 5.1 解析节点树

节点树顶层字段: `appId`、`activityId`、`screenWidth`、`screenHeight`、`nodes[]`。
每个节点的 `attr` 常用字段: `name`、`text`、`desc`、`id`、`vid`、`clickable`、`visibleToUser`、`left/top/right/bottom`、`width/height`。

用 json (不是 json5) 读取快照 JSON。先确认 appId 和 activityId，再看屏幕分辨率。

### 5.2 定位要点的节点

核心原则: **点 `clickable=true` 的那个节点，不要点它的文字子节点**。本项目两次踩到同一个坑:

- 酷狗开屏: `text=跳过` 的节点 clickable=false，父容器 clickable=true
- YouTube Morphe: `text=跳过开头` 的节点 clickable=false，外层 `desc=跳过` 的容器 clickable=true

定位方法:

1. 如果截图就是原始分辨率，直接用像素坐标和节点的 bounds 对照；如果截过图，按比例换算。
2. 用户画了红圈时，可以用 PIL 找红色像素的质心: `r>150 and g<90 and b<90 and r-g>80`，再换算到快照坐标。
3. 找到候选后，**必须验证唯一性**: 统计全树满足条件 (例如 `desc=关闭 and clickable=true`) 的节点数，必须只有一个；同时检查有没有值相近的不同节点 (例如 `关闭侧边栏`) 会误匹配。
4. 打印候选节点的完整属性和整棵子树，确认层级关系再写选择器。

### 5.3 写入规则

编辑 `scripts/custom-rules.json5`:

```json5
{
  apps: [{
    id: '包名',              // 来自快照 appId；上游没有这个 app 就新增整个条目
    name: '应用名',
    groups: [{
      key: 9004,             // 递增，绝不 <= 8999
      name: '规则说明',
      activityIds: ['快照里的 activityId'],
      rules: [{
        matches: '[desc="跳过"][clickable=true]',
        action: 'clickCenter',
      }],
    }],
  }],
  globalGroups: [],
}
```

`sync_and_merge.py` 的 `apply_custom_rules()` 按 app id 匹配，已存在时按 group.key 合并，key 相同则自定义覆盖上游；app 不存在则新增。所以既能补新 app，也能修上游那条点不到节点的规则。

### 5.4 验证与上线

1. 单元验证合并结果:
   ```bash
   python - <<'PY'
   import sys, json5
   sys.path.insert(0, 'scripts')
   import sync_and_merge as s
   apps, groups = {}, {}
   print(s.apply_custom_rules(apps, groups, s.load_custom_rules(), {}))
   # 检查目标 app 的 groups 里出现了新 key
   PY
   ```
2. 本地跑三条检查 (第 7 节)。
3. 推送 `scripts/custom-rules.json5` 到 GitHub (第 6 节)，触发 CI。
4. 等 CI success 后，**必须拉远程 merged.json5 核对**新 key 真的在线，不能只看 CI 绿。
5. 告诉用户"更新订阅后生效"。真机点不到就让他再抓一份当时的快照迭代。

## 6. GitHub 操作 SOP (不要每次临时拼命令)

本机网络 TLS 不稳定，所有 curl 都要带 `--retry 5 --retry-all-errors`。

### 6.1 取 token

```bash
CRED=$(printf "protocol=https\nhost=github.com\n\n" | git credential fill 2>/dev/null)
TOKEN=$(printf "%s" "$CRED" | sed -n 's/^password=//p')
```

凭据弹窗出现时选账号 `gekkxxlloxo`。曾经选完后报失败，原因是 TLS 中断，不是账号错。

### 6.2 更新单个文件 (无需本地 git push)

REST API 的 contents PUT 必须带当前文件的 sha，先 GET 再 PUT:

```bash
curl --retry 5 --retry-all-errors -sSL -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/gekkxxlloxo/gkd-subscription-aggregator/contents/scripts/custom-rules.json5"
# 从响应取 sha，然后把新内容 base64 -w0，PUT 回去，body:
# {"message": "提交说明", "content": "<base64>", "sha": "<上一步的 sha>"}
```

### 6.3 触发工作流并等结果

```bash
curl --retry 6 --retry-all-errors -sSL -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" -d '{"ref":"main"}' \
  "https://api.github.com/repos/gekkxxlloxo/gkd-subscription-aggregator/actions/workflows/sync.yml/dispatches"
# 成功是 HTTP 204，没有 body
```

然后轮询 `GET /actions/runs?per_page=3`，按 `run_number` 找到本次运行，等 `status=completed` 且 `conclusion=success`。

最后核对产物，URL 加时间戳绕开缓存:

```bash
curl --retry 5 --retry-all-errors -sSL \
  "https://raw.githubusercontent.com/gekkxxlloxo/gkd-subscription-aggregator/main/merged.json5?t=$(date +%s)"
```

用 json5 解析，确认目标 app 和 group key 存在。

## 7. 每次改动后的本地检查 (三条都要过)

```bash
cd <仓库根目录>
python scripts/char_check.py          # 期望 exit 0，问题数 0
python -m ruff check scripts/         # 期望全部 passed
python scripts/sync_and_merge.py      # 期望能拉到源并生成 merged.json5
```

第三条会改写本地 merged.json5。这是正常的，但**不要把这个本地产物当作交付物上传**，交给 CI 生成提交。

## 8. 踩过的坑 (真实事故，不要重蹈)

| 症状 | 根因 | 修法 |
|---|---|---|
| 连续十几次报文件找不到 | 把 `source-list.json` 写成 `source_list.json`，横杠变下划线 | char_check.py 的 `check_project_paths()` 会比对磁盘真实文件名精准拦截 |
| 解析订阅源一直拿到 0 条规则 | 上游返回 JSON5 (单引号/无引号键)，用了 `response.json()` | 必须用 `json5.loads()` |
| 规则永远取不到 | 按 `data['groups']` 取，但订阅顶层是 `apps` / `globalGroups` | 规则在 `apps[].groups[].rules[]` |
| 脚本 SyntaxError | 引号错位 `source['name"]` | Ruff 的 E 规则可拦截 |
| 去重键取错 | 用 `match.appIds` 而不是 `apps[].id` | 用 app 的 `id` 字段 |
| CI 被质检步骤卡死 (exit 1) | char_check.py 扫了 `merged.json5` 里的上游智能引号 | 只扫源码白名单，排除产物 |
| Ruff 退出码 2 | `target-version` 放进了 `[lint]` 段 | 必须放 ruff.toml 顶层 |
| Ruff 报 48 项风格噪音 | 开了全套规则 | 只开 `E` + `F`，忽略 `E501` / `F541` |
| 临时目录 `.probe` 被扫出字符错误 | 检查范围没收紧 | 开始检查前删掉临时目录，或确认不在白名单后缀内 |
| CI 跑通但订阅没更新 | `merged.json5` 被 .gitignore 忽略 | 产物必须提交进仓库 |
| 点按钮没反应 | 点了 text 节点，而它 clickable=false | 找外层 clickable=true 的容器，验证唯一性 |
| 推送报 SIGTERM / 执行失败 | TLS 中断 | 加 `--retry`，不要误判成凭据或权限问题 |

## 9. 重要认知

- 这个项目将来大概率还会由别的 AI 接手。换模型解决不了字符错误，因为那是概率生成的固有特性。真正的防线是 char_check.py + Ruff + CI 校验这套确定性工具，以及本文件里的固定流程。
- CI 只检测不修复。看到失败要看具体是哪一步，不要笼统判断成"工作流坏了"。
- 用户发快照让我们做规则，是验证可行的流程；但**逻辑正确不等于真机生效**，最终以用户更新订阅后的实测为准。
