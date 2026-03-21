# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1.0] - 2026-03-21

### Added
- **8 MCP tools** for medical office automation — connect via OpenClaw native plugin or any MCP client
- Forward a message and its attachments are saved automatically, organized by date
- Obsidian notes created with structured frontmatter — surgery, meeting, and general categories with content-hash dedup (no duplicate notes from repeated forwards)
- Apple Calendar events created from surgery schedules and meeting notices (via pyobjc EventKit)
- Apple Reminders created for tasks and agenda items (supports due date and priority)
- Local OCR for image-based messages — extracts Chinese and English text via macOS Vision
- Interactive setup wizard: auto-detects your Obsidian vault, lists your calendars, saves config
- Path traversal prevention on all file operations
- Graceful fallback on non-macOS — file and Obsidian tools work everywhere, calendar/reminder tools require macOS
- `save_attachment` now accepts local file paths (`file_path`) — no more base64 encoding for files already on disk
- OpenClaw plugin wrapper included in repo (`openclaw-plugin/`) — `cp -r` to install
- Agent prompt configuration guide for OpenClaw (AGENTS.md + TOOLS.md templates)
- 38 tests covering all tools with two-tier strategy (mock tests on any platform + real API tests on macOS)
