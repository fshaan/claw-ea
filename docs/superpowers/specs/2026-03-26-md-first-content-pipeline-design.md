# Design: Markdown-First Content Pipeline (md-first)

Brainstormed: 2026-03-25 (office-hours)
Eng Review: 2026-03-26
Status: APPROVED

## Problem

claw-ea saves non-text files (images, Word, Excel, PDF) as raw attachments in Obsidian. Note content is a wikilink reference only — file contents are unsearchable, unlinkable, and require the original app to view.

**Goal:** Convert all archived files to Markdown before saving to Obsidian, making everything searchable and linkable.

## Constraints

- Self-use branch (`feat/md-first`), no backward compatibility needed
- macOS only
- All conversion runs locally (docling, markitdown, LM Studio, Vision OCR)
- Follows existing agent/tool boundary: conversion is a side-effect → tool responsibility

## Architecture

```
file → extension detection → converter routing → conversion → is_usable() → pass/fallback → temp file → return path
```

### File Changes

| File | Change |
|------|--------|
| `src/claw_ea/converters.py` | **New.** dispatch + 5 converter functions + is_usable + temp file mgmt |
| `src/claw_ea/tools/converter.py` | **New.** `convert_to_markdown` MCP tool |
| `src/claw_ea/tools/obsidian.py` | **Modified.** Add `raw_body_path` parameter |
| `src/claw_ea/config.py` | **Modified.** Parse optional `converters` config section |
| `src/claw_ea/server.py` | **Modified.** Register new tool |
| `openclaw-plugin/src/tools.ts` | **Modified.** Add TypeScript tool definition |

## Data Structure

```python
@dataclass
class ConversionResult:
    temp_path: str          # converted md temp file path
    source_path: str        # original file path
    converter_used: str     # which converter was used
    fallback_used: bool     # whether fallback was triggered
```

No quality_score or quality_issues — these are internal to dispatch only, not exposed to the agent.

## Converters (5 functions)

Each converter: `(file_path: Path) -> str` (returns markdown string), plus `_is_available() -> bool`.

### convert_docling (default)

- Subprocess call to `docling` CLI, wrapped in `asyncio.to_thread()`
- Process cleanup: `Popen` + `os.killpg()` for full process tree kill on timeout
- Executable: `shutil.which()` first, then `config.converters.paths.docling`
- Formats: `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`, images

### convert_markitdown

- Subprocess call to `markitdown` CLI, reads stdout
- Formats: `.docx`, `.xlsx`, `.pptx`, `.pdf`, `.html`, `.csv`

### convert_mineru

- Subprocess call to `magic-pdf`
- Formats: `.pdf` (specialty: academic papers, complex formulas)

### convert_lmstudio

- HTTP POST to LM Studio API (OpenAI-compatible)
- Image → base64 → vision message to glm-OCR model
- Timeout: 120s default
- Formats: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.webp`

### convert_vision_ocr (image last-resort)

- Reuses `ocr.py._run_ocr()` (macOS Vision framework)
- Available only on macOS with Vision framework
- Returns plain text markdown

## Routing & Dispatch

```python
DEFAULT_ROUTING = {
    ".pdf":  {"default": ["docling"]},
    ".docx": {"default": ["docling", "markitdown"]},
    ".pptx": {"default": ["docling", "markitdown"]},
    ".xlsx": {"default": ["docling", "markitdown"]},
    ".jpg":  {"default": ["lmstudio", "docling", "vision_ocr"]},
    ".png":  {"default": ["lmstudio", "docling", "vision_ocr"]},
    # other image formats same as above
}

def dispatch(file_path: Path, config: Config, hint: str = "") -> ConversionResult:
    """
    1. Look up converter chain by extension + hint
       routing[ext].get(hint, routing[ext]["default"])
    2. Filter out converters where is_available() == False
    3. Try each converter:
       a. call convert_xxx(file_path) → markdown string
       b. call is_usable(markdown) → bool
       c. pass → write temp file → return ConversionResult
       d. fail → try next
    4. All fail → return longest result + warning
    """
```

Routing is dict-only format (every extension has a `"default"` key). Config overrides DEFAULT_ROUTING when present.

## Quality Check

```python
def is_usable(markdown: str) -> bool:
    """
    v1 checks:
    - Non-empty, non-whitespace-only
    - Valid character ratio >= 80% (excluding Cc/Cs/Co unicode categories, \n not counted)

    Returns bool. No scoring — v1 is a binary decision (empty/garbled vs usable).
    """
```

## MCP Tool: convert_to_markdown

```python
@mcp_instance.tool()
async def convert_to_markdown(file_path: str, hint: str = "") -> dict:
    """Convert file to Markdown, save as temp file.

    Returns:
        md_path: temp file path (pass to create_obsidian_note raw_body_path)
        converter_used: which converter was used
        fallback_used: whether fallback was triggered
    """
```

Returns file path, not markdown string. Large documents (100-page PDFs) would waste agent tokens.

## create_obsidian_note Changes

New optional parameter:

```python
async def create_obsidian_note(
    category, title, content_data,
    attachment_paths=None,
    raw_body_path: str = "",  # NEW: read content from this file path
)
```

When `raw_body_path` is set:
- Read markdown from file
- Still generate YAML frontmatter
- Use file content as note body (instead of template rendering)
- Append original file wikilink at end (`## 原始文件\n- [[filename]]`)
- **Delete temp file after reading**

Image notes: text only, no embedded image (decision: start minimal, add `![[image]]` later if needed).

## ocr_image vs convert_to_markdown

- **`ocr_image`**: agent needs to read image text for classification (lightweight, no archiving)
- **`convert_to_markdown`**: archiving file content to Obsidian note (includes routing, fallback, temp file)

Image archiving calls `convert_to_markdown` only (internal OCR fallback chain). `ocr_image` is for non-archival "read this image" scenarios.

## Agent Workflow Change

```
Before: message → save_attachment → create_obsidian_note
After:  message → save_attachment → convert_to_markdown → create_obsidian_note
                                         ↓                       ↓
                                    returns md_path        raw_body_path=md_path
                                    (content stays          reads file, deletes temp
                                     out of agent)
```

## Config Format

```yaml
# ~/.claw-ea/config.yaml (converters section is optional)
converters:
  lmstudio:
    endpoint: http://localhost:1234/v1
    api_key: "your-token-here"       # supports ${ENV_VAR}
    model: "glm-ocr"
    timeout: 120

  paths:
    docling: /Users/f.sh/Library/Python/3.9/bin/docling
    # markitdown, magic-pdf: omit to use shutil.which()

  routing:
    pdf:
      default: [docling]
      academic: [mineru, docling]
    docx:
      default: [docling, markitdown]
    xlsx:
      default: [docling, markitdown]
    pptx:
      default: [docling, markitdown]
    image:
      default: [lmstudio, docling, vision_ocr]
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Converter not installed | `is_available()` → False, skip to next |
| Conversion timeout | `Popen` + `os.killpg()` kills process group, try next. Default 60s, lmstudio 120s |
| Empty/garbled output | `is_usable()` → False, trigger fallback |
| All converters fail | Return longest result + warning |
| LM Studio down | HTTP connection fail → `is_available()` = False, fallback |
| Unsupported format | Return error, agent uses plain save_attachment |
| Temp file leak | `create_obsidian_note` deletes after read; server startup cleans `/tmp/claw-ea-*` older than 1 hour |

## Testing Strategy

- **Mock tests**: All subprocess/HTTP mocked — routing, is_usable, fallback chain, process cleanup
- **Integration tests (`@pytest.mark.converter`)**: Real small files with docling/markitdown CLI
- **is_usable tests**: Pre-built good/bad/empty/garbled markdown samples
- **Temp file tests**: Verify read-then-delete and startup cleanup

## Success Criteria

1. PDF/docx/xlsx/pptx/image → markdown → Obsidian note works
2. docling as default converter functions correctly
3. Config-driven routing with dict format
4. `is_usable()` detects empty/garbled content, triggers fallback
5. Fallback chains work (docling fail → markitdown; image 3-level chain)
6. Existing 8 MCP tools unchanged (`raw_body_path` is optional)
7. Test coverage for routing/fallback/is_usable/temp file cleanup
8. Subprocess timeout kills full process tree (no zombies)
9. Cross-venv CLI tools findable via config paths

## Implementation Order

1. Create `feat/md-first` branch
2. `converters.py` — dispatch + convert_docling + is_usable + temp file + process cleanup
3. `tools/converter.py` — convert_to_markdown MCP tool + server.py registration
4. `tools/obsidian.py` — add raw_body_path support + temp file deletion
5. `config.py` — parse converters config (optional section, fallback to DEFAULT_ROUTING)
6. Add convert_markitdown / convert_lmstudio / convert_vision_ocr
7. Add convert_mineru (after MinerU installation)
8. `openclaw-plugin/src/tools.ts` — TypeScript definition for convert_to_markdown
9. Tests — mock (routing, fallback, is_usable, process cleanup, temp files) + integration
10. Update OpenClaw agent config — AGENTS.md / TOOLS.md

## Key Decisions (from Eng Review)

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Single file converters.py, not package | 4 functions don't need ABC + 7 files |
| 2 | Vision OCR as image fallback chain end | Reuse ocr.py._run_ocr, DRY |
| 3 | File passing (raw_body_path) not string | Large docs would truncate/waste agent tokens |
| 4 | Dict-only routing format | Eliminate list/dict dual-format parsing |
| 5 | Subprocess first, no Python API deps | Avoid torch etc, get it working first |
| 6 | is_usable() bool, not quality scoring | v1 is binary; scoring framework is overdesign |
| 7 | Don't expose quality_score to agent | Agent can't act on scores, wastes tokens |
| 8 | Popen + os.killpg() for timeout | Full process tree cleanup |
| 9 | Config paths section | Cross-venv shutil.which() failures |
| 10 | Temp file: read-then-delete + startup cleanup | Prevent leaks on agent interruption |
| 11 | Image notes: text only, no embedded image | Start minimal (user decision: add later if needed) |
