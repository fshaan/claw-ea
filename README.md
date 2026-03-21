# claw-ea

医生太忙了，没时间整理信息。

每天飞书群里的手术排班表、企微里的会议通知、Telegram 收到的文件——看一眼就过去了，回头想找的时候已经埋在几百条消息里。重要的手术安排可能忘掉，会议时间记不清，收到的文件不知道存到了哪里。

claw-ea 解决的就是这个问题：**把消息转发给 AI 助手，剩下的全自动完成。**

## 它做什么

把你从社交渠道（飞书、企业微信、Telegram）收到的工作消息转发给 OpenClaw，claw-ea 会自动：

- **归档附件** —— 文件按日期保存到指定文件夹，重复文件自动跳过
- **创建 Obsidian 笔记** —— 结构化的 Markdown 笔记，带 YAML frontmatter 和附件链接，按类别分类（手术、会议、任务、文档）
- **同步日历** —— 手术安排和会议通知自动写入 Apple Calendar（需你确认后才写入）
- **创建提醒** —— 待办任务和会议议程中你负责的环节自动创建 Apple Reminders
- **读懂图片** —— 手术排班表截图、会议通知截图通过 OCR 提取文字（中英文），交给 AI 理解

你要做的只有一步：**转发消息**。零操作，零学习成本。

## 使用场景

**手术排班表**：转发排班表截图 → AI 识别所有手术 → 你主刀/带组的手术自动创建日历事件（按台次估算时间：第一台 9:00，第二台 13:00...） → Obsidian 记录完整排班信息

**会议通知**：转发会议通知 → 自动创建日历事件 → 如果有议程且你要发言/主持，额外创建提醒任务

**会议纪要**：转发纪要文件 → 提取 action items → 你负责的任务自动创建提醒 → 下次会议时间写入日历

**日常文件**：转发 PDF、Word → 文件自动归档到按日期组织的附件文件夹 → Obsidian 笔记关联附件链接

**所有日历和提醒事项的写入都需要你确认后才执行。** Obsidian 笔记和文件归档是自动完成的（低风险，随时可编辑）。

## 技术方案

claw-ea 是一个 Python MCP (Model Context Protocol) Server，通过 OpenClaw 原生插件接入。核心设计原则：

- **Tool 只做副作用操作**（写文件、调 API、读系统状态），所有"理解"（消息分类、图片理解、审核摘要格式化）由 AI agent 的 LLM 完成
- **MCP 开放标准**——同一个 server 可被 OpenClaw、Claude Desktop、Cursor 等任何 MCP 客户端调用
- **全部本地处理**——医疗信息敏感，不上传任何第三方服务
- **pyobjc EventKit**（而非 AppleScript）——避免中文字符转义问题，获取完整事件 ID 和错误信息

8 个 MCP Tool：`save_attachment`、`create_obsidian_note`、`create_calendar_event`、`create_reminder`、`ocr_image`、`detect_obsidian_vault`、`list_apple_calendars`、`save_config`

## Quick start

```bash
git clone https://github.com/fshaan/claw-ea.git
cd claw-ea && uv sync
```

## Connect to OpenClaw

claw-ea 通过原生插件接入 OpenClaw。仓库中的 `openclaw-plugin/` 目录包含了 TypeScript 桥接层，负责将 Python MCP Server 注册为 OpenClaw 的 tool。

### Automated installation (for AI agents)

将以下指令复制粘贴给你的 OpenClaw agent，它会自动完成安装和配置：

<!-- AGENT INSTALL INSTRUCTIONS — paste this block to your OpenClaw agent -->
```
I need you to install the claw-ea plugin. Here are the steps:

1. Clone the repo and install Python dependencies:
   cd ~/Workspace/Claude && git clone https://github.com/fshaan/claw-ea.git claw_EA
   cd claw_EA && uv sync

2. Copy the OpenClaw plugin wrapper (already included in the repo):
   cp -r openclaw-plugin ~/.openclaw/extensions/claw-ea
   cd ~/.openclaw/extensions/claw-ea && npm install

3. Add to ~/.openclaw/openclaw.json — in "plugins.allow" array, add "claw-ea".
   In "plugins.entries", add:
   "claw-ea": {
     "enabled": true,
     "config": {
       "pythonPath": "<HOME>/Workspace/Claude/claw_EA/.venv/bin/python",
       "projectDir": "<HOME>/Workspace/Claude/claw_EA"
     }
   }
   In "plugins.installs", add:
   "claw-ea": {
     "source": "path",
     "installPath": "<HOME>/.openclaw/extensions/claw-ea",
     "version": "0.1.0"
   }
   Replace <HOME> with the actual home directory path.

4. Create config — run: mkdir -p ~/.claw-ea
   Then create ~/.claw-ea/config.yaml with user name, Obsidian vault path,
   calendar name, and reminder list. Use the detect_obsidian_vault and
   list_apple_calendars tools to discover available options.

5. Restart OpenClaw: openclaw restart
```
<!-- END AGENT INSTALL INSTRUCTIONS -->

### Manual installation

1. Clone and install:
   ```bash
   cd ~/Workspace/Claude
   git clone https://github.com/fshaan/claw-ea.git claw_EA
   cd claw_EA && uv sync
   ```

2. Install the OpenClaw plugin wrapper:
   ```bash
   cp -r openclaw-plugin ~/.openclaw/extensions/claw-ea
   cd ~/.openclaw/extensions/claw-ea && npm install
   ```

3. Register the plugin in `~/.openclaw/openclaw.json`:
   - Add `"claw-ea"` to `plugins.allow`
   - Add entry to `plugins.entries` with `pythonPath` and `projectDir`
   - Add entry to `plugins.installs` with `source: "path"`

4. Create `~/.claw-ea/config.yaml` (see [Config](#config) below)

5. Restart: `openclaw restart`

### MCPorter (optional — for CLI testing)

MCPorter 是独立的命令行调试工具，可以直接调用 MCP tool，但不会将 tool 注册到 OpenClaw agent。

```bash
# ~/.mcporter/mcporter.json 中添加:
# "claw-ea": { "command": ".../.venv/bin/python", "args": ["-m", "claw_ea.server"], "cwd": "..." }

mcporter call claw-ea.detect_obsidian_vault
```

### Other MCP clients

兼容 Claude Desktop、Cursor 等任何支持 stdio transport 的 MCP 客户端：

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

## Config

Create `~/.claw-ea/config.yaml`:

```yaml
user:
  name: 你的姓名          # 用于在会议议程和手术排班中匹配你的名字
  aliases: [别名1, 别名2]  # 英文名、简称等

obsidian:
  vault_path: ~/Obsidian/my-vault
  notes_folder: Inbox/OpenClaw    # 相对于 vault 的路径

attachments:
  base_path: ~/Obsidian/my-vault/attachments/OpenClaw
  organize_by_date: true

apple:
  calendar_name: 工作              # 必须已存在于 Calendar.app
  reminder_list: OpenClaw          # 必须已存在于 Reminders.app

categories:
  surgery:
    schedule_time_slots:
      1: "09:00"    # 第1台
      2: "13:00"    # 第2台
      3: "17:00"    # 第3台
      4: "20:00"    # 第4台（急诊/加台）
    user_roles: [主刀, 带组, 一助]
```

Tip: 安装后用 `detect_obsidian_vault` 和 `list_apple_calendars` tool 可以自动发现可用的 vault 路径和日历名称。

## Requirements

- Python 3.11+
- macOS (Apple Calendar/Reminders 和 Vision OCR 需要 macOS；文件和 Obsidian 相关功能跨平台可用)

## Development

```bash
uv sync --dev
uv run pytest                    # All tests
uv run pytest -m "not macos"     # Skip macOS API tests
```

See [CLAUDE.md](CLAUDE.md) for architecture details and design decisions.

## Contributors

This project was designed and built collaboratively by a human developer and AI:

- **f.sh** — Product vision, domain expertise (medical workflows), design decisions, code review
- **Claude (Anthropic)** — Architecture design, implementation, testing, documentation

## License

MIT License
