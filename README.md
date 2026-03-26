# claw-ea

Doctors are too busy to organize information.

Surgery schedules in Feishu group chats, meeting notices on WeCom, files received via Telegram — glanced at once and buried under hundreds of messages. Important surgeries get forgotten, meeting times slip, files disappear.

claw-ea fixes this: **forward the message to your AI assistant, everything else happens automatically.**

## What it does

Forward work messages from social channels (Feishu, WeCom, Telegram) to OpenClaw, and claw-ea will:

- **Archive attachments** — files saved by date, duplicates skipped automatically
- **Create Obsidian notes** — structured Markdown with YAML frontmatter and attachment links, categorized (surgery, meeting, task, document)
- **Sync calendar** — surgery schedules and meeting notices written to Apple Calendar (requires your confirmation before writing)
- **Create reminders** — action items and your agenda assignments added to Apple Reminders
- **Convert to Markdown** — PDF, Word, Excel, PowerPoint, images, and plaintext files all converted to searchable Markdown before archiving (6 converter backends with automatic fallback)
- **Read images** — surgery schedule screenshots and meeting notice images processed via OCR (Chinese + English), understood by AI

You do one thing: **forward the message**. Zero operation, zero learning curve.

## Use cases

**Surgery schedule**: Forward a schedule screenshot → AI identifies all cases → your lead surgeon / team lead cases automatically create calendar events (estimated by case order: 1st case 9:00, 2nd case 13:00...) → Obsidian records the full schedule

**Meeting notice**: Forward a meeting notice → calendar event created → if the agenda lists you as presenter/chair, a reminder task is also created

**Meeting minutes**: Forward minutes document → action items extracted → your assigned tasks become reminders → next meeting time added to calendar

**Daily files**: Forward PDF, Word → file converted to Markdown → content embedded in searchable Obsidian note (original file archived as backup)

**All calendar events and reminders require your confirmation before writing.** Obsidian notes and file archiving happen automatically (low risk, editable anytime).

## Architecture

claw-ea is a Python MCP (Model Context Protocol) Server connected to OpenClaw as a native plugin. Core design principles:

- **Tools only perform side effects** (write files, call APIs, read system state) — all "understanding" (message classification, image comprehension, approval summary formatting) is handled by the AI agent's LLM
- **MCP open standard** — the same server works with OpenClaw, Claude Desktop, Cursor, or any MCP client
- **Fully local processing** — medical information is sensitive, nothing is uploaded to third-party services
- **pyobjc EventKit** (not AppleScript) — avoids Chinese character escaping issues, returns proper event IDs and error info

9 MCP Tools: `save_attachment`, `convert_to_markdown`, `create_obsidian_note`, `create_calendar_event`, `create_reminder`, `ocr_image`, `detect_obsidian_vault`, `list_apple_calendars`, `save_config`

## Quick start

```bash
git clone https://github.com/fshaan/claw-ea.git
cd claw-ea && uv sync
```

## Connect to OpenClaw

claw-ea connects to OpenClaw as a native plugin. The `openclaw-plugin/` directory in this repo contains the TypeScript bridge layer that registers the Python MCP Server as OpenClaw tools.

### Automated installation (for AI agents)

Copy and paste the following instructions to your OpenClaw agent — it will complete setup automatically:

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
     "version": "0.1.3.0"
   }
   Replace <HOME> with the actual home directory path.

4. Create config — run: mkdir -p ~/.claw-ea
   Then create ~/.claw-ea/config.yaml with user name, Obsidian vault path,
   calendar name, and reminder list. Use the detect_obsidian_vault and
   list_apple_calendars tools to discover available options.

5. Configure agent behavior — add a "claw-ea" section to
   ~/.openclaw/workspace/AGENTS.md (trigger rules: when to use claw-ea tools)
   and ~/.openclaw/workspace/TOOLS.md (tool reference: categories, user name
   matching, approval flow). See CLAUDE.md "Agent Prompt Configuration" for
   the full template.

6. Restart OpenClaw: openclaw restart
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

5. Configure agent behavior — add claw-ea sections to `~/.openclaw/workspace/AGENTS.md` and `TOOLS.md` (see [CLAUDE.md](CLAUDE.md#agent-prompt-configuration) for templates)

6. Restart: `openclaw restart`

### MCPorter (optional — for CLI testing)

MCPorter is a standalone CLI debugging tool. It can call MCP tools directly but does NOT register them with the OpenClaw agent.

```bash
# Add to ~/.mcporter/mcporter.json:
# "claw-ea": { "command": ".../.venv/bin/python", "args": ["-m", "claw_ea.server"], "cwd": "..." }

mcporter call claw-ea.detect_obsidian_vault
```

### Other MCP clients

Works with Claude Desktop, Cursor, or any MCP client supporting stdio transport:

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
  name: Your Name           # Used for matching in meeting agendas and surgery schedules
  aliases: [Alias1, Alias2] # English name, abbreviations, etc.

obsidian:
  vault_path: ~/Obsidian/my-vault
  notes_folder: Inbox/OpenClaw    # Relative to vault root

attachments:
  base_path: ~/Obsidian/my-vault/attachments/OpenClaw
  organize_by_date: true

apple:
  calendar_name: Work              # Must already exist in Calendar.app
  reminder_list: OpenClaw          # Must already exist in Reminders.app

categories:
  surgery:
    schedule_time_slots:
      1: "09:00"    # 1st case
      2: "13:00"    # 2nd case
      3: "17:00"    # 3rd case
      4: "20:00"    # 4th case (emergency/add-on)
    user_roles: [主刀, 带组, 一助]  # Lead surgeon, team lead, first assistant
```

Tip: After installation, use the `detect_obsidian_vault` and `list_apple_calendars` tools to discover available vault paths and calendar names.

## Requirements

- Python 3.11+
- macOS (Apple Calendar/Reminders and Vision OCR require macOS — file and Obsidian tools work on any platform)

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

[MIT](LICENSE)
