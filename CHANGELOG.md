# Changelog

All notable changes to this project will be documented in this file.

## [0.1.2.0] - 2026-03-26

### Added
- **Markdown-first content pipeline** — new `convert_to_markdown` MCP tool converts files to Markdown before archiving to Obsidian, making all content searchable and linkable
- **5 converter backends** with configurable fallback chains: docling (default), markitdown, MinerU (academic PDFs), LM Studio (vision OCR), macOS Vision OCR (last-resort)
- **`dispatch()` routing engine** — routes files by extension, supports hint-based sub-routing (e.g. `academic` for research PDFs), automatically falls back through the converter chain
- **`is_usable()` quality check** — binary check for empty/garbled output (≥80% valid Unicode), triggers fallback when a converter produces unusable results
- **`raw_body_path` parameter** for `create_obsidian_note` — reads converted Markdown from file instead of passing through agent context, avoiding token waste on large documents
- **Configurable converter paths** — `converters.paths` in config.yaml for cross-venv CLI discovery when `shutil.which()` fails
- **Process group cleanup** — `subprocess.Popen(process_group=0)` + `os.killpg()` ensures converter subprocesses are fully killed on timeout (no zombie processes)
- **Temp file lifecycle management** — converter output written to `/tmp/claw-ea-*.md`, deleted after note creation, stale files cleaned on server startup
- **OpenClaw plugin updated** with `claw_convert_to_markdown` tool definition and `raw_body_path` parameter on `claw_create_note`
- 83 tests (up from 38) — full coverage of routing, fallback chains, quality checks, temp file cleanup, and integration tests with real CLIs

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
