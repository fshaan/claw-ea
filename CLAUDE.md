# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

claw-ea is a Python MCP (Model Context Protocol) server that helps medical professionals automatically archive messages from social media channels (Feishu, WeCom, Telegram, etc.) into Obsidian notes, Apple Calendar, and Apple Reminders. It runs as an external MCP server connected to OpenClaw via MCPorter, but is designed to work with any MCP client (Claude Desktop, Cursor, etc.).

## Architecture

### Agent vs Tool Boundary (Critical Design Principle)

The MCP server only provides **side-effect tools** — tools that write files, call system APIs, or read system state. All "understanding" tasks (message classification, image comprehension, approval dialog formatting) are handled by the calling agent's LLM, NOT by our tools.

### MCP Tools (8 total)

**Core workflow** (called by agent after it classifies the message):
- `ocr_image` — Local OCR only (macOS Vision framework). Agent's multimodal LLM handles image understanding directly; this tool is the fallback when the LLM lacks vision.
- `save_attachment` — Saves file to date-organized attachment directory. Dedup: skips if identical file exists.
- `create_obsidian_note` — Creates Markdown note with YAML frontmatter in Obsidian vault. Dedup via content hash (first 8 chars in filename); returns existing path if duplicate.
- `create_calendar_event` — Creates event in Apple Calendar via pyobjc EventKit. Returns event ID.
- `create_reminder` — Creates reminder in Apple Reminders via pyobjc EventKit. Returns reminder ID.

**Configuration** (used during setup wizard, orchestrated by agent):
- `detect_obsidian_vault` — Scans common paths for Obsidian vaults.
- `list_apple_calendars` — Lists available calendars and reminder lists.
- `save_config` — Validates and writes config.yaml.

### Approval Flow

Obsidian notes and attachments are written automatically (low risk). Calendar events and reminders require user confirmation first — the agent shows a summary and waits for approval before calling `create_calendar_event` / `create_reminder`.

### Data Flow

```
User message → [OpenClaw Agent / any MCP client]
                    │
                    ├─ Agent LLM reads text / sees images directly
                    │  (falls back to ocr_image if LLM lacks vision)
                    │
                    ├─ Agent classifies message, fills structured JSON
                    │
                    ├─ Calls save_attachment (auto)
                    ├─ Calls create_obsidian_note (auto)
                    │
                    ├─ Agent formats approval summary, sends to user
                    │  User confirms → Agent calls:
                    │     ├─ create_calendar_event
                    │     └─ create_reminder
```

## Project Structure

```
claw-ea/
├── pyproject.toml
├── src/claw_ea/
│   ├── server.py           # MCP server entry point
│   ├── config.py           # Config loading/saving/validation
│   ├── eventkit_utils.py   # Shared EKEventStore init + permissions
│   └── tools/
│       ├── ocr.py          # ocr_image (macOS Vision framework)
│       ├── attachment.py   # save_attachment
│       ├── obsidian.py     # create_obsidian_note (with content-hash dedup)
│       ├── calendar.py     # create_calendar_event (uses eventkit_utils)
│       ├── reminder.py     # create_reminder (uses eventkit_utils)
│       └── setup.py        # detect_obsidian_vault, list_apple_calendars, save_config
├── tests/
└── TODOS.md
```

## Tech Stack

- **Python 3.11+** with **uv** for package management
- **mcp** Python SDK for MCP server
- **pyobjc-framework-EventKit** for Apple Calendar/Reminders (NOT AppleScript — chosen to avoid string escaping issues with Chinese text and to get event IDs back)
- **pyobjc-framework-Vision** for local OCR
- **pyyaml** for config
- **pytest** for tests

## Commands

```bash
uv sync                          # Install dependencies
uv run python -m claw_ea.server  # Run MCP server
uv run pytest                    # Run all tests
uv run pytest -m "not macos"     # Run tests without macOS API calls
uv run pytest -m macos           # Run only real macOS API tests
uv run pytest tests/test_obsidian.py -k "test_dedup"  # Single test
```

## Key Design Decisions

1. **No classify_message tool** — Classification is the agent's job. Tool descriptions include the expected JSON schema so the agent knows what to pass.
2. **No prepare_schedule_items tool** — Formatting approval summaries is text generation, which the agent handles.
3. **No setup_wizard tool** — Setup is three atomic tools (detect, list, save) orchestrated by the agent.
4. **pyobjc over AppleScript** — Chinese medical terms contain special characters that break AppleScript string escaping. pyobjc EventKit returns proper event IDs and error info.
5. **Content-hash dedup** — Notes use `{date}-{category}-{hash[:8]}.md` naming. Duplicate messages produce the same hash and are skipped.
6. **macOS-only, no premature abstraction** — No platform interface layer. Each tool is one module. Cross-platform support deferred until needed.
7. **Two-tier testing** — Mock tests run everywhere; `@pytest.mark.macos` tests hit real EventKit/Vision APIs.

## Config File (~/.claw-ea/config.yaml)

```yaml
user:
  name: 张医生            # Used for matching in meeting agendas and surgery schedules
  aliases: [张三, Dr. Zhang]

obsidian:
  vault_path: ~/Documents/ObsidianVault
  notes_folder: Inbox/OpenClaw

attachments:
  base_path: ~/Documents/ObsidianVault/attachments
  organize_by_date: true

apple:
  calendar_name: 工作
  reminder_list: OpenClaw

categories:
  surgery:
    schedule_time_slots: {1: "09:00", 2: "13:00", 3: "17:00", 4: "20:00"}
    user_roles: [主刀, 带组, 一助]
```

## Domain-Specific Logic

- **Surgery schedules**: When a surgery schedule mentions the user (by name/alias in a role like 主刀/带组/一助), create calendar events with estimated times based on case order (configurable per-slot).
- **Meeting agendas**: When a meeting has an agenda listing the user as presenter/chair/discussant, create reminder tasks for their specific agenda items.
- **Meeting minutes**: Extract action items and follow-up schedules; only create reminders for items assigned to the user.

## OpenClaw Integration

claw-ea connects to OpenClaw as a **native plugin** (NOT via MCPorter).

**How it works:**
- `openclaw-plugin/` in this repo contains a TypeScript wrapper (`index.ts` + `mcp-bridge.ts` + `tools.ts`)
- The wrapper spawns `python -m claw_ea.server` as a subprocess and bridges MCP JSON-RPC over stdin/stdout
- Each Python MCP tool is registered as an OpenClaw tool via `api.registerTool()`
- The plugin auto-loads on every OpenClaw restart — no manual action needed

**Key lesson:** MCPorter (`~/.mcporter/mcporter.json`) is a standalone CLI tool for testing MCP servers. It does NOT integrate with OpenClaw's agent. Only native plugins (`~/.openclaw/extensions/`) register tools that the agent can use.

**Adding a new tool:**
1. Implement the tool in `src/claw_ea/tools/` (Python)
2. Register it in `server.py`
3. Add a corresponding tool definition in `openclaw-plugin/src/tools.ts` (TypeScript)
4. Restart OpenClaw

**server.py requires `if __name__ == "__main__": main()`** — without this guard, `python -m claw_ea.server` imports the module but never starts the server. Both MCPorter and the OpenClaw plugin wrapper call `python -m claw_ea.server`.

### Agent Prompt Configuration

After installing the plugin, you need to tell the OpenClaw agent **when and how** to use claw-ea tools. OpenClaw assembles its system prompt from workspace files at `~/.openclaw/workspace/`. Two files need changes:

**`AGENTS.md`** — add a behavior rule section:

```markdown
## Social media message auto-processing (claw-ea)

**Trigger**: When the user forwards work messages from Feishu/WeCom/Telegram
(surgery notices, meeting schedules, files, screenshots), automatically use
claw-ea tools. No trigger word needed — decide based on message content.

**Flow**:
1. Read the message — classify as surgery/meeting/meeting_minutes/task/document/general
2. If image: read it directly (or call claw_ocr_image if you can't see images)
3. If attachment: call claw_save_attachment
4. Create note: call claw_create_note with category, title, structured data, attachment paths
5. If schedule/task: show summary for user confirmation, then call
   claw_create_calendar_event / claw_create_reminder

**Multi-message**: Consecutive messages about the same event → merge before processing.
Different events → process separately.

**Don't trigger**: For chat, Q&A, commands, or anything unrelated to work message archiving.
```

**`TOOLS.md`** — add a claw-ea section with:
- Tool table (8 tools, which are auto vs need-confirmation)
- Message category → action mapping table
- User name matching list (name + aliases from config)
- Surgery case time slots
- Approval summary format template

See the installed `~/.openclaw/workspace/TOOLS.md` for a complete example.

## Design Documents

- Design doc: `~/.gstack/projects/claw-ea/f.sh-unknown-design-20260321-114310.md`
- Test plan: `~/.gstack/projects/claw-ea/f.sh-unknown-test-plan-20260321-131135.md`
