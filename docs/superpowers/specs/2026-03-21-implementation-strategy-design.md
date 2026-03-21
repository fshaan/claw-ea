# Implementation Strategy for claw-ea MCP Server

## Summary

This spec defines the implementation strategy for claw-ea, a Python MCP server that archives medical professionals' messages into Obsidian notes, Apple Calendar, and Apple Reminders. The architecture, tool set, and tech stack were locked in prior design reviews (`/office-hours` + `/plan-eng-review`). This document covers **how** to build it: SDK patterns, implementation order, module structure, and testing approach.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| MCP SDK style | Decorator (`@server.tool()`) | Simpler, Flask-like, community standard |
| Implementation order | Vertical slices | Forces early resolution of cross-cutting concerns |
| Config loading | Eager on startup, fail-fast | No silent misconfiguration; tools assume config is valid |
| Testing timing | Synchronous with implementation | Each tool gets tests before moving to the next slice |
| Apple API | pyobjc EventKit | Returns event IDs, handles Chinese characters safely |

## Vertical Slices

```
Slice 1: Project scaffold + file operations
  pyproject.toml → config.py → server.py → save_attachment → create_obsidian_note → tests

Slice 2: Apple Calendar/Reminders integration
  eventkit_utils.py → create_calendar_event → create_reminder → tests

Slice 3: Local OCR
  ocr_image (macOS Vision framework) → tests

Slice 4: Configuration tools
  detect_obsidian_vault → list_apple_calendars → save_config → tests

Slice 5: End-to-end integration tests
```

Each slice produces a working, tested increment. Slice 1 runs on any platform; Slices 2-3 require macOS.

## Module Design

### server.py — MCP Server Entry Point

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from claw_ea.config import load_config

server = Server("claw-ea")

def main():
    import asyncio

    async def run():
        config = load_config()          # Fail-fast if missing
        register_tools(server, config)  # Each tool module exports register()
        async with stdio_server() as (read, write):
            await server.run(read, write)

    asyncio.run(run())
```

Key: `config` is explicitly passed to each tool module via `register(server, config)`. No global state.

### config.py — Configuration

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    user_name: str
    user_aliases: list[str]
    vault_path: Path
    notes_folder: str
    attachments_path: Path
    organize_by_date: bool
    calendar_name: str
    reminder_list: str
    surgery_time_slots: dict[int, str]
    surgery_user_roles: list[str]

class ConfigError(Exception): ...

def load_config(path: Path | None = None) -> Config:
    """Load from ~/.claw-ea/config.yaml. Raises ConfigError if missing or invalid."""
```

Uses `dataclass` for type safety and IDE completion. Validation happens once at load time.

### Tool Module Pattern

Every tool module follows this pattern:

```python
# tools/attachment.py
from mcp.server import Server
from claw_ea.config import Config

def register(server: Server, config: Config):
    @server.tool()
    async def save_attachment(file_content: str, filename: str, subfolder: str = "") -> dict:
        """Save a file to the attachments directory organized by date."""
        ...
```

### save_attachment

- Input: `file_content` (base64), `filename`, `subfolder` (optional)
- Output: `{"saved_path": str, "already_existed": bool}`
- Logic: base64 decode → construct dated path → skip if identical file exists → write
- Filename collision: append `_1`, `_2` suffix if same name but different content

### create_obsidian_note

- Input: `category`, `title`, `content_data` (JSON dict), `attachment_paths` (list)
- Output: `{"note_path": str, "already_existed": bool}`
- Dedup: SHA256 of sorted `content_data` JSON, first 8 chars in filename
- Filename pattern: `{date}-{category}-{hash[:8]}.md`
- Templates: hardcoded Python dicts per category (surgery, meeting, meeting_minutes, task, document, general)
- Each template defines which frontmatter fields to include and the Markdown body structure

### eventkit_utils.py — Shared EventKit Client

```python
class EventKitClient:
    def __init__(self):
        self.store = EKEventStore.alloc().init()

    async def ensure_calendar_access(self) -> None:
        """Request calendar permission. Raises PermissionError if denied."""

    async def ensure_reminder_access(self) -> None:
        """Request reminder permission. Raises PermissionError if denied."""

    def find_calendar(self, name: str) -> EKCalendar | None: ...
    def find_reminder_list(self, name: str) -> EKCalendar | None: ...
```

Created once at server startup, shared between calendar.py and reminder.py.

EventKit permission requests use ObjC completion handlers — wrap with `asyncio.Future` or `run_in_executor` to bridge into async Python.

### create_calendar_event

- Input: `title`, `start_time` (ISO-8601), `end_time` (optional), `location` (optional), `notes` (optional)
- Output: `{"event_id": str, "calendar": str}`
- Default duration: 1 hour if no end_time provided

### create_reminder

- Input: `title`, `due_date` (optional, ISO-8601), `priority` (optional: 1-9), `notes` (optional)
- Output: `{"reminder_id": str, "list": str}`

### ocr_image

- Input: `image_content` (base64), `filename`
- Output: `{"extracted_text": str, "language": str}`
- Uses macOS Vision framework (`VNRecognizeTextRequest`) with `["zh-Hans", "en"]`
- Pure text extraction — no classification, no structured data parsing

### Configuration Tools (tools/setup.py)

Three atomic tools in one module:

- `detect_obsidian_vault()` → scans `~/` for dirs containing `.obsidian/`
- `list_apple_calendars()` → returns `{"calendars": [...], "reminder_lists": [...]}`
- `save_config(config_data: dict)` → validates and writes `~/.claw-ea/config.yaml`

## Testing Architecture

```
tests/
├── conftest.py          # Shared fixtures
├── test_config.py       # Config load/save/validation
├── test_attachment.py   # File saving, dedup, Chinese filenames
├── test_obsidian.py     # Note creation, frontmatter, content-hash dedup
├── test_calendar.py     # Mock tests + @pytest.mark.macos real API tests
├── test_reminder.py     # Mock tests + @pytest.mark.macos real API tests
├── test_ocr.py          # Mock tests + @pytest.mark.macos real Vision tests
├── test_setup.py        # Config tools
└── test_integration.py  # MCP server startup, end-to-end tool calls
```

### Key Fixtures (conftest.py)

```python
@pytest.fixture
def tmp_vault(tmp_path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Inbox" / "OpenClaw").mkdir(parents=True)
    return vault

@pytest.fixture
def mock_config(tmp_vault, tmp_path):
    return Config(
        user_name="张医生",
        user_aliases=["张三", "Dr. Zhang"],
        vault_path=tmp_vault,
        notes_folder="Inbox/OpenClaw",
        attachments_path=tmp_path / "attachments",
        organize_by_date=True,
        calendar_name="工作",
        reminder_list="OpenClaw",
        surgery_time_slots={1: "09:00", 2: "13:00", 3: "17:00", 4: "20:00"},
        surgery_user_roles=["主刀", "带组", "一助"],
    )
```

### Two-Tier Testing Strategy

- **Mock tests** (all platforms): Test business logic — parameter assembly, error handling, dedup, filename generation. EventKit and Vision calls are mocked.
- **macOS tests** (`@pytest.mark.macos`): Hit real APIs. Create real calendar events (in a test calendar), run real OCR. Skipped in CI.

## Error Handling Pattern

All tools return structured errors via MCP's error mechanism:

- `ConfigError` — config missing or invalid → tool returns error suggesting setup wizard
- `PermissionError` — macOS permission denied → clear message about System Preferences
- `FileNotFoundError` — vault/attachment path gone → clear error with the path that's missing
- `ValueError` — invalid input (bad base64, bad date format) → clear message about what's wrong

No silent failures. Every error path returns a message the agent can relay to the user.

## NOT in Scope

- Cross-platform support (Linux/Windows)
- Custom Jinja2 note templates (deferred to TODOS.md)
- Handoff report generation (deferred to TODOS.md)
- Google Calendar integration
- Multi-user support
