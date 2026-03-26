# Changelog

All notable changes to this project will be documented in this file.

## [0.1.3.0] - 2026-03-26

### Added
- **Plaintext passthrough converter** — `.txt`, `.md`, `.rst`, `.log` files now go through the `convert_to_markdown` pipeline for uniform handling
- **Behavioral constraints in tool descriptions** — critical workflow rules (must convert before note creation, surgery → reminder only, PPT → summarize) embedded directly in MCP tool descriptions, auto-enforced by any MCP client
- **OpenClaw prompt template** (`openclaw-plugin/PROMPT_TEMPLATE.md`) — ready-to-use AGENTS.md + TOOLS.md snippets with recommended converter tool installation guide

### Fixed
- **Pipe deadlock in docling/mineru** — subprocess stdout changed from PIPE to DEVNULL with `communicate()`, preventing deadlock on large outputs
- **Tab characters misclassified as garbled** — `is_usable()` now skips `\t` and `\r` alongside `\n`
- **Dead code removed** — unused `tried_one` variable in `dispatch()`
- 88 tests (up from 83)

## [0.1.2.0] - 2026-03-26

### Added
- **Markdown-first content pipeline** — forwarded PDF, Word, Excel, PowerPoint, and image files are now converted to Markdown before archiving, making all content searchable and linkable in Obsidian
- **5 converter backends** with automatic fallback: docling (default), markitdown, MinerU (academic PDFs with LaTeX), LM Studio (vision OCR), macOS Vision OCR (last-resort)
- **Smart routing** — files are matched to the best converter by extension; use `hint="academic"` for research PDFs to prioritize MinerU; if a converter fails or produces garbled output, the next one in chain is tried automatically
- **File-passing mode** — converted Markdown stays out of agent context (passed as file path, not string), keeping token usage low even for 100-page PDFs
- **Configurable converter paths** — `converters.paths` in config.yaml for when CLI tools are in a different virtualenv
- **Robust subprocess management** — process group cleanup on timeout (no zombie processes), temp files cleaned on server startup
- **OpenClaw plugin updated** with `convert_to_markdown` tool and `raw_body_path` parameter
- 83 tests (up from 38) covering routing, fallback chains, quality checks, and integration with real CLIs

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
