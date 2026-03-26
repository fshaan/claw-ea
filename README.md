# claw-ea

[English](README.en.md)

医生没时间整理信息。

飞书群里的手术排班、企微发来的开会通知、Telegram 收到的文件——扫一眼就被几百条消息淹没。重要手术忘了、开会时间记错、文件找不到了。

claw-ea 解决这个问题：**把消息转发给 AI 助手，剩下的全自动。**

## 环境要求

> **当前版本（v0.1.3.1）仅支持 macOS，面向中文医疗场景。**

| 条件 | 说明 |
|------|------|
| **操作系统** | macOS 13+（Ventura 及以上）— Apple 日历/提醒事项通过 pyobjc EventKit 调用，OCR 通过 macOS Vision 框架 |
| **Python** | 3.11+，使用 [uv](https://docs.astral.sh/uv/) 包管理器 |
| **Obsidian** | 任意版本 — 笔记以标准 Markdown 文件写入 |
| **MCP 客户端** | [OpenClaw](https://openclaw.com)（原生插件）或任何支持 MCP 协议的客户端（Claude Desktop、Cursor 等） |
| **转换工具** | [docling](https://github.com/DS4SD/docling)（必装，主力转换器）+ [markitdown](https://github.com/microsoft/markitdown)（推荐，回退方案） |

暂不支持 Windows、Linux 和非中文环境。跨平台支持等有实际需求后再做。

## 功能

把飞书/企微/Telegram 的工作消息转发给 OpenClaw，claw-ea 自动完成：

- **归档附件** — 按日期保存文件，自动跳过重复
- **创建 Obsidian 笔记** — 带 YAML frontmatter 的结构化 Markdown 笔记，按类别（会议、任务、文件等）分类
- **同步日历** — 手术排班和会议通知写入 Apple 日历，事件自带 15 分钟提前提醒（写入前需你确认）
- **创建提醒** — 待办事项和你的议程任务加入 Apple 提醒事项
- **转为 Markdown** — PDF、Word、Excel、PPT、图片、纯文本文件全部转为可搜索的 Markdown 后归档（6 个转换器后端，自动回退）
- **识别图片** — 手术排班截图、开会通知图片通过 OCR 识别（中英文），AI 理解内容

你只做一件事：**转发消息。** 零操作，零学习成本。

## 使用场景

**手术排班**：转发排班截图 → AI 识别所有台次 → 你参与的手术自动创建日历事件（含 15 分钟提前提醒，按台次估算时间：第 1 台 09:00，第 2 台 13:00…）

**开会通知**：转发会议通知 → 自动创建日历事件 → 如果议程中你是主持/汇报人，还会创建提醒任务

**会议纪要**：转发纪要文档 → 提取待办事项 → 你的任务创建为提醒 → 下次开会时间加入日历

**日常文件**：转发 PDF、Word → 文件转为 Markdown → 内容嵌入可搜索的 Obsidian 笔记（原始文件作为附件备份）

**所有日历事件和提醒写入前都需要你确认。** Obsidian 笔记和附件归档自动完成（低风险，随时可编辑）。

## 架构

claw-ea 是一个 Python MCP（Model Context Protocol）服务器，通过原生插件连接 OpenClaw。核心设计：

- **工具只做副作用操作**（写文件、调 API、读系统状态）— 所有"理解"（消息分类、图片理解、审批摘要格式化）由 AI agent 的 LLM 完成
- **MCP 开放标准** — 同一个服务器兼容 OpenClaw、Claude Desktop、Cursor 等任何 MCP 客户端
- **全部本地处理** — 医疗信息敏感，不上传任何第三方服务
- **pyobjc EventKit**（非 AppleScript）— 避免中文特殊字符的转义问题，返回事件 ID 和错误信息

9 个 MCP 工具：`save_attachment`、`convert_to_markdown`、`create_obsidian_note`、`create_calendar_event`、`create_reminder`、`ocr_image`、`detect_obsidian_vault`、`list_apple_calendars`、`save_config`

## 快速开始

```bash
git clone https://github.com/fshaan/claw-ea.git
cd claw-ea && uv sync
```

## 连接 OpenClaw

claw-ea 以原生插件方式连接 OpenClaw。仓库中的 `openclaw-plugin/` 目录包含 TypeScript 桥接层，将 Python MCP 服务器注册为 OpenClaw 工具。

### 自动安装（给 AI agent 用）

把以下指令粘贴给你的 OpenClaw agent，它会自动完成安装：

<!-- AGENT INSTALL INSTRUCTIONS — paste this block to your OpenClaw agent -->
```
我需要你安装 claw-ea 插件，步骤如下：

1. 克隆仓库并安装 Python 依赖：
   cd ~/Workspace/Claude && git clone https://github.com/fshaan/claw-ea.git claw_EA
   cd claw_EA && uv sync

2. 复制 OpenClaw 插件（仓库中已包含）：
   cp -r openclaw-plugin ~/.openclaw/extensions/claw-ea
   cd ~/.openclaw/extensions/claw-ea && npm install

3. 在 ~/.openclaw/openclaw.json 中注册插件：
   - "plugins.allow" 数组中加入 "claw-ea"
   - "plugins.entries" 中加入：
   "claw-ea": {
     "enabled": true,
     "config": {
       "pythonPath": "<HOME>/Workspace/Claude/claw_EA/.venv/bin/python",
       "projectDir": "<HOME>/Workspace/Claude/claw_EA"
     }
   }
   - "plugins.installs" 中加入：
   "claw-ea": {
     "source": "path",
     "installPath": "<HOME>/.openclaw/extensions/claw-ea",
     "version": "0.1.3.1"
   }
   将 <HOME> 替换为实际的 home 目录路径。

4. 创建配置 — 运行: mkdir -p ~/.claw-ea
   然后创建 ~/.claw-ea/config.yaml，填入用户名、Obsidian vault 路径、
   日历名称和提醒列表。使用 detect_obsidian_vault 和
   list_apple_calendars 工具发现可用选项。

5. 配置 agent 行为 — 参考 openclaw-plugin/PROMPT_TEMPLATE.md，
   将对应内容添加到 ~/.openclaw/workspace/AGENTS.md（触发规则）
   和 ~/.openclaw/workspace/TOOLS.md（工具参考）。

6. 重启 OpenClaw: openclaw restart
```
<!-- END AGENT INSTALL INSTRUCTIONS -->

### 手动安装

1. 克隆并安装：
   ```bash
   cd ~/Workspace/Claude
   git clone https://github.com/fshaan/claw-ea.git claw_EA
   cd claw_EA && uv sync
   ```

2. 安装 OpenClaw 插件：
   ```bash
   cp -r openclaw-plugin ~/.openclaw/extensions/claw-ea
   cd ~/.openclaw/extensions/claw-ea && npm install
   ```

3. 在 `~/.openclaw/openclaw.json` 中注册插件：
   - `plugins.allow` 中加入 `"claw-ea"`
   - `plugins.entries` 中加入 `pythonPath` 和 `projectDir` 配置
   - `plugins.installs` 中加入 `source: "path"` 条目

4. 创建 `~/.claw-ea/config.yaml`（见下方[配置](#配置)）

5. 配置 agent 行为 — 参考 `openclaw-plugin/PROMPT_TEMPLATE.md`，添加到 `~/.openclaw/workspace/AGENTS.md` 和 `TOOLS.md`

6. 重启：`openclaw restart`

### MCPorter（可选 — 用于 CLI 调试）

MCPorter 是独立的 CLI 调试工具，可以直接调用 MCP 工具，但不会将工具注册到 OpenClaw agent。

```bash
# 在 ~/.mcporter/mcporter.json 中添加：
# "claw-ea": { "command": ".../.venv/bin/python", "args": ["-m", "claw_ea.server"], "cwd": "..." }

mcporter call claw-ea.detect_obsidian_vault
```

### 其他 MCP 客户端

支持 Claude Desktop、Cursor 或任何兼容 stdio 传输的 MCP 客户端：

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

创建 `~/.claw-ea/config.yaml`：

```yaml
user:
  name: 张医生              # 用于在排班表和议程中匹配你的名字
  aliases: [张三, Dr. Zhang] # 英文名、简称等

obsidian:
  vault_path: ~/Obsidian/my-vault
  notes_folder: Inbox/OpenClaw    # 相对于 vault 根目录

attachments:
  base_path: ~/Obsidian/my-vault/attachments/OpenClaw
  organize_by_date: true

apple:
  calendar_name: 工作              # 必须已存在于日历 App 中
  reminder_list: OpenClaw          # 必须已存在于提醒事项 App 中

categories:
  surgery:
    schedule_time_slots:
      1: "09:00"    # 第 1 台
      2: "13:00"    # 第 2 台
      3: "17:00"    # 第 3 台
      4: "20:00"    # 第 4 台（急诊/加台）
    user_roles: [主刀, 带组, 一助]
```

安装后可以用 `detect_obsidian_vault` 和 `list_apple_calendars` 工具发现可用的 vault 路径和日历名称。

## 开发

```bash
uv sync --dev
uv run pytest                    # 全部测试
uv run pytest -m "not macos"     # 跳过 macOS API 测试
```

架构详情和设计决策见 [CLAUDE.md](CLAUDE.md)。

## 贡献者

本项目由人类开发者和 AI 协作设计和构建：

- **f.sh** — 产品设想、领域专业知识（医疗工作流）、设计决策、代码审查
- **Claude (Anthropic)** — 架构设计、代码实现、测试、文档

## 许可证

[MIT](LICENSE)
