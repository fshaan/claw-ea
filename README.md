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

Add to your OpenClaw config (`~/.openclaw/config.json5`):

```json5
{
  plugins: {
    entries: {
      "mcporter": {
        config: {
          servers: {
            "claw-ea": {
              command: "uv",
              args: ["run", "python", "-m", "claw_ea"],
              env: { "CLAW_EA_CONFIG": "~/.claw-ea/config.yaml" }
            }
          }
        }
      }
    }
  }
}
```

Also works with Claude Desktop, Cursor, or any MCP client.

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
