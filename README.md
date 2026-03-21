# claw-ea

MCP server for medical office automation. Forward messages from social media channels (Feishu, WeCom, Telegram) to your AI agent, and claw-ea automatically archives them into Obsidian notes, Apple Calendar events, and Apple Reminders.

## What it does

- **Attachments** — saves files organized by date, skips duplicates
- **Obsidian notes** — creates structured notes with YAML frontmatter and wikilinks to attachments
- **Apple Calendar** — creates events from surgery schedules and meeting notices
- **Apple Reminders** — creates tasks from action items and agenda assignments
- **OCR** — extracts text from images (Chinese + English) via macOS Vision framework
- **Setup wizard** — auto-detects your Obsidian vault, lists calendars, saves config

## Quick start

```bash
# Install
uv sync

# Configure
# Create ~/.claw-ea/config.yaml (see CLAUDE.md for format)

# Run
uv run python -m claw_ea
```

## Connect to OpenClaw

claw-ea runs as a native OpenClaw plugin. It needs a TypeScript wrapper that bridges the Python MCP server into OpenClaw's plugin system.

### Automated installation (for AI agents)

Copy the following instructions to your OpenClaw agent — it can execute the setup automatically:

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

4. Create `~/.claw-ea/config.yaml` (see [Config format](#config) below)

5. Restart: `openclaw restart`

### MCPorter (optional — for CLI testing)

If you have MCPorter installed, you can also test tools from the command line:

```bash
# Add to ~/.mcporter/mcporter.json:
# "claw-ea": {
#   "command": "/path/to/claw_EA/.venv/bin/python",
#   "args": ["-m", "claw_ea.server"],
#   "cwd": "/path/to/claw_EA"
# }

mcporter call claw-ea.detect_obsidian_vault
mcporter call claw-ea.save_attachment file_content="aGVsbG8=" filename="test.txt"
```

MCPorter is a standalone CLI tool — it does NOT connect tools to OpenClaw's agent. Use the native plugin (above) for that.

### Other MCP clients

Works with Claude Desktop, Cursor, or any MCP client that supports stdio transport:

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
  name: 你的姓名          # Used for matching in meeting agendas and surgery schedules
  aliases: [别名1, 别名2]  # English name, abbreviations, etc.

obsidian:
  vault_path: ~/Obsidian/my-vault
  notes_folder: Inbox/OpenClaw    # Relative to vault

attachments:
  base_path: ~/Obsidian/my-vault/attachments/OpenClaw
  organize_by_date: true

apple:
  calendar_name: 工作              # Must exist in Calendar.app
  reminder_list: OpenClaw          # Must exist in Reminders.app

categories:
  surgery:
    schedule_time_slots:
      1: "09:00"    # 1st case
      2: "13:00"    # 2nd case
      3: "17:00"    # 3rd case
      4: "20:00"    # 4th case (emergency)
    user_roles: [主刀, 带组, 一助]
```

Tip: Use the `detect_obsidian_vault` and `list_apple_calendars` tools to discover available paths and calendar names.

## Requirements

- Python 3.11+
- macOS (for Apple Calendar/Reminders and Vision OCR — file and Obsidian tools work on any platform)

## Development

```bash
uv sync --dev
uv run pytest                    # All tests
uv run pytest -m "not macos"     # Skip macOS API tests
```

See [CLAUDE.md](CLAUDE.md) for architecture details and design decisions.
