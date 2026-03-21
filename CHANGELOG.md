# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0.0] - 2026-03-21

### Added
- MCP server with FastMCP, stdio transport, eager config loading
- `save_attachment` tool — date-organized file storage with dedup and collision handling
- `create_obsidian_note` tool — Markdown notes with YAML frontmatter, content-hash dedup, Obsidian wikilink syntax
- `create_calendar_event` tool — Apple Calendar integration via pyobjc EventKit, default 1-hour duration
- `create_reminder` tool — Apple Reminders integration via pyobjc EventKit, due date and priority support
- `ocr_image` tool — local OCR via macOS Vision framework (Chinese + English)
- `detect_obsidian_vault` tool — scans common paths for Obsidian vaults
- `list_apple_calendars` tool — lists system calendars and reminder lists
- `save_config` tool — validates and writes config.yaml
- Shared `EventKitClient` with async permission request bridging
- Config module with dataclass validation, YAML loading, fail-fast on startup
- Path traversal prevention in attachment and note tools
- Graceful degradation on non-macOS (calendar/reminder tools disabled with warning)
- 31 unit and integration tests with two-tier strategy (mock + macOS-real)
- CLAUDE.md with architecture guide and design decisions
