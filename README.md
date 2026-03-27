# claw-ea

[English](README.en.md)

医生没时间整理信息。

企业微信群里的手术排班、微信发来的开会通知、各类收到的文件——看一眼就被后面的消息顶掉了。等到要用的时候翻半天聊天记录，或者干脆忘了。

我写 claw-ea 就是解决自己这个问题：**把工作消息转发给 AI 助手，它帮你归档、建日历、设提醒。**

## 环境要求

> **当前版本（v0.1.4.0）只跑在 macOS 上，给中文医疗场景用的。**

| 条件 | 说明 |
|------|------|
| **系统** | macOS 13+（Ventura 及以上）— 日历和提醒事项走 pyobjc EventKit，OCR 走 macOS Vision |
| **Python** | 3.11+，用 [uv](https://docs.astral.sh/uv/) 管理依赖 |
| **Obsidian** | 任意版本，笔记就是标准 Markdown 文件 |
| **MCP 客户端** | [OpenClaw](https://openclaw.com)（原生插件）或其他 MCP 客户端（Claude Desktop、Cursor 等都行） |
| **转换工具** | [docling](https://github.com/DS4SD/docling)（必装）+ [markitdown](https://github.com/microsoft/markitdown)（建议装，做回退） |

Windows、Linux 暂时没做。等真有人需要再说。

## 干什么用的

把工作消息转发给 OpenClaw，claw-ea 在后台干活：

- **存附件** — 文件按日期归到 Obsidian 附件目录，重复的跳过
- **建笔记** — 在 Obsidian 里生成带 frontmatter 的结构化笔记，会议、任务、文件各有分类
- **排日历** — 手术和会议写进 Apple 日历，带 15 分钟提前提醒（写之前让你确认）
- **设提醒** — 待办和你负责的议程条目加到提醒事项里
- **转 Markdown** — PDF、Word、Excel、PPT、图片、纯文本，先转成 Markdown 再存，Obsidian 里全文可搜。6 个转换器，一个不行自动换下一个
- **认图** — 排班截图、通知图片走 OCR（中英文），AI 直接读内容

你要做的就是转发。

## 场景

**手术排班**：转发排班截图 → AI 读出所有台次 → 你上的台自动建日历（按台次估时间，第一台 09:00，第二台 13:00…带 15 分钟提前提醒）

**开会通知**：转发通知 → 建日历事件 → 议程里你要汇报的，再加一条提醒

**会议纪要**：转发纪要 → 提出待办 → 分给你的建提醒 → 下次会议时间加进日历

**收到文件**：转发 PDF、Word → 转成 Markdown 嵌进 Obsidian 笔记 → 原文件留着当附件

日历和提醒写入前都要你点确认。笔记和附件直接存，低风险，随时能改。

## 技术方案

claw-ea 是个 Python MCP 服务器，挂在 OpenClaw 上当原生插件跑。几个设计选择：

- **工具只管写入**（存文件、调系统 API、读状态）— 消息分类、图片理解、摘要排版这些活交给 LLM
- **走 MCP 协议** — OpenClaw、Claude Desktop、Cursor，哪个客户端都能接
- **数据不出本机** — 医疗信息敏感，不往任何第三方传
- **用 pyobjc EventKit 而不是 AppleScript** — 中文手术名里各种特殊字符，AppleScript 转义容易炸，EventKit 直接拿到事件 ID 和报错

11 个 MCP 工具：`save_attachment`、`convert_to_markdown`、`create_obsidian_note`、`create_calendar_event`、`delete_calendar_event`、`create_reminder`、`delete_reminder`、`ocr_image`、`detect_obsidian_vault`、`list_apple_calendars`、`save_config`

## 快速开始

```bash
git clone https://github.com/fshaan/claw-ea.git
cd claw-ea && uv sync
```

## 接入 OpenClaw

claw-ea 作为原生插件接入 OpenClaw，`openclaw-plugin/` 目录里是 TypeScript 桥接层，把 Python MCP 服务器的工具注册到 OpenClaw。

### 让 AI 帮你装

把下面这段话粘贴给你的 OpenClaw agent，它自己就装好了：

<!-- AGENT INSTALL INSTRUCTIONS -->
```
帮我安装 claw-ea 插件：

1. 拉代码装依赖：
   cd ~/Workspace/Claude && git clone https://github.com/fshaan/claw-ea.git claw_EA
   cd claw_EA && uv sync

2. 装 OpenClaw 插件（仓库里带着的）：
   cp -r openclaw-plugin ~/.openclaw/extensions/claw-ea
   cd ~/.openclaw/extensions/claw-ea && npm install

3. 注册到 ~/.openclaw/openclaw.json：
   - "plugins.allow" 加 "claw-ea"
   - "plugins.entries" 加：
   "claw-ea": {
     "enabled": true,
     "config": {
       "pythonPath": "<HOME>/Workspace/Claude/claw_EA/.venv/bin/python",
       "projectDir": "<HOME>/Workspace/Claude/claw_EA"
     }
   }
   - "plugins.installs" 加：
   "claw-ea": {
     "source": "path",
     "installPath": "<HOME>/.openclaw/extensions/claw-ea",
     "version": "0.1.4.0"
   }
   <HOME> 换成实际路径。

4. 建配置目录 mkdir -p ~/.claw-ea，
   然后创建 ~/.claw-ea/config.yaml，填用户名、vault 路径、日历名、提醒列表。
   用 detect_obsidian_vault 和 list_apple_calendars 工具查可用选项。

5. ⛔ 配 agent 行为（必做，不可跳过）：
   读取项目目录下的 openclaw-plugin/PROMPT_TEMPLATE.md，
   将其中的 AGENTS.md 片段完整写入 ~/.openclaw/workspace/AGENTS.md，
   将 TOOLS.md 片段完整写入 ~/.openclaw/workspace/TOOLS.md。
   如果已有 claw-ea 段落则替换，没有则追加。
   这一步定义了消息分类规则和工具调用顺序，跳过会导致工作流错误。

6. 重启 OpenClaw: openclaw restart
```
<!-- END AGENT INSTALL INSTRUCTIONS -->

### 手动装

1. 拉代码：
   ```bash
   cd ~/Workspace/Claude
   git clone https://github.com/fshaan/claw-ea.git claw_EA
   cd claw_EA && uv sync
   ```

2. 装插件：
   ```bash
   cp -r openclaw-plugin ~/.openclaw/extensions/claw-ea
   cd ~/.openclaw/extensions/claw-ea && npm install
   ```

3. 在 `~/.openclaw/openclaw.json` 里注册（`plugins.allow`、`plugins.entries`、`plugins.installs` 三处）

4. 写配置文件 `~/.claw-ea/config.yaml`（见[配置](#配置)）

5. **⛔ 配 agent 行为（必做）** — 读取 `openclaw-plugin/PROMPT_TEMPLATE.md`，将其中两个片段分别写入 `~/.openclaw/workspace/AGENTS.md` 和 `TOOLS.md`（已有则替换，没有则追加）。跳过这步会导致分类规则缺失

6. `openclaw restart`

### MCPorter（调试用）

MCPorter 是个独立的命令行调试工具，能直接调 MCP 工具，但不会注册到 OpenClaw agent 里。

```bash
# ~/.mcporter/mcporter.json 里加：
# "claw-ea": { "command": ".../.venv/bin/python", "args": ["-m", "claw_ea.server"], "cwd": "..." }

mcporter call claw-ea.detect_obsidian_vault
```

### 其他 MCP 客户端

Claude Desktop、Cursor 或任何走 stdio 的 MCP 客户端都能用：

```json
{
  "mcpServers": {
    "claw-ea": {
      "command": "/path/to/claw_EA/.venv/bin/python",
      "args": ["-m", "claw_ea.server"],
      "cwd": "/path/to/claw_EA"
    }
  }
}
```

## 配置

建 `~/.claw-ea/config.yaml`：

```yaml
user:
  name: 张医生              # 排班表和议程里匹配你名字用的
  aliases: [张三, Dr. Zhang] # 英文名、简称

obsidian:
  vault_path: ~/Obsidian/my-vault
  notes_folder: Inbox/OpenClaw    # vault 下的相对路径

attachments:
  base_path: ~/Obsidian/my-vault/attachments/OpenClaw
  organize_by_date: true

apple:
  calendar_name: 工作              # 日历 App 里必须已有这个日历
  reminder_list: OpenClaw          # 提醒事项 App 里必须已有这个列表

categories:
  surgery:
    schedule_time_slots:
      1: "09:00"    # 第 1 台
      2: "13:00"    # 第 2 台
      3: "17:00"    # 第 3 台
      4: "20:00"    # 第 4 台（急诊/加台）
    user_roles: [主刀, 带组, 一助]
```

装好之后可以用 `detect_obsidian_vault` 和 `list_apple_calendars` 工具查看本机有哪些 vault 和日历。

## 开发

```bash
uv sync --dev
uv run pytest                    # 跑全部测试
uv run pytest -m "not macos"     # 不跑 macOS API 的测试
```

架构和设计决策见 [CLAUDE.md](CLAUDE.md)。

## 关于

这个项目是我和 AI 一起做的：

- **f.sh** — 想法、医疗工作流的领域知识、设计决策、code review
- **Claude (Anthropic)** — 架构、写代码、测试、文档

## 许可证

[MIT](LICENSE)
