# claw-ea MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python MCP server that archives medical messages into Obsidian notes, Apple Calendar, and Apple Reminders.

**Architecture:** External MCP server using FastMCP decorator API. Tools are side-effect-only (file I/O, system API calls). All "understanding" (classification, image comprehension) is done by the calling agent's LLM. Config loaded eagerly at startup.

**Tech Stack:** Python 3.11+, uv, mcp SDK (FastMCP), pyobjc-framework-EventKit, pyobjc-framework-Vision, pyyaml, pytest

---

## File Structure

```
claw-ea/
├── pyproject.toml                  # Package config, dependencies, pytest markers
├── src/claw_ea/
│   ├── __init__.py                 # Package marker
│   ├── __main__.py                 # Entry point: python -m claw_ea
│   ├── server.py                   # FastMCP instance + tool registration
│   ├── config.py                   # Config dataclass + load/save
│   ├── eventkit_utils.py           # Shared EKEventStore client
│   └── tools/
│       ├── __init__.py
│       ├── attachment.py           # save_attachment
│       ├── obsidian.py             # create_obsidian_note
│       ├── calendar.py             # create_calendar_event
│       ├── reminder.py             # create_reminder
│       ├── ocr.py                  # ocr_image
│       └── setup.py                # detect_obsidian_vault, list_apple_calendars, save_config
├── tests/
│   ├── conftest.py                 # Shared fixtures
│   ├── test_config.py
│   ├── test_attachment.py
│   ├── test_obsidian.py
│   ├── test_calendar.py
│   ├── test_reminder.py
│   ├── test_ocr.py
│   ├── test_setup.py
│   └── test_integration.py
├── CLAUDE.md
└── TODOS.md
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/claw_ea/__init__.py`
- Create: `src/claw_ea/__main__.py`
- Create: `src/claw_ea/tools/__init__.py`
- Create: `tests/__init__.py` (empty, not needed but clarifies intent)
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "claw-ea"
version = "0.1.0"
description = "MCP server for medical office automation — Obsidian, Apple Calendar, Reminders"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0",
    "pyyaml>=6.0",
    "pyobjc-framework-EventKit>=10.0",
    "pyobjc-framework-Vision>=10.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/claw_ea"]

[tool.pytest.ini_options]
markers = ["macos: tests requiring macOS APIs (EventKit, Vision)"]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create package structure**

```python
# src/claw_ea/__init__.py
"""claw-ea: MCP server for medical office automation."""

# src/claw_ea/tools/__init__.py
"""MCP tool modules."""
```

- [ ] **Step 3: Create __main__.py**

```python
# src/claw_ea/__main__.py
"""Entry point: python -m claw_ea"""
from claw_ea.server import main

main()
```

- [ ] **Step 4: Create tests/conftest.py with shared fixtures**

```python
# tests/conftest.py
import pytest
from pathlib import Path
from claw_ea.config import Config


@pytest.fixture
def tmp_vault(tmp_path):
    """Create a temporary Obsidian vault with required structure."""
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Inbox" / "OpenClaw").mkdir(parents=True)
    return vault


@pytest.fixture
def tmp_attachments(tmp_path):
    """Create a temporary attachments directory."""
    att = tmp_path / "attachments"
    att.mkdir()
    return att


@pytest.fixture
def mock_config(tmp_vault, tmp_attachments):
    """Return a Config pointing at temporary directories."""
    return Config(
        user_name="张医生",
        user_aliases=["张三", "Dr. Zhang"],
        vault_path=tmp_vault,
        notes_folder="Inbox/OpenClaw",
        attachments_path=tmp_attachments,
        organize_by_date=True,
        calendar_name="工作",
        reminder_list="OpenClaw",
        surgery_time_slots={1: "09:00", 2: "13:00", 3: "17:00", 4: "20:00"},
        surgery_user_roles=["主刀", "带组", "一助"],
    )
```

- [ ] **Step 5: Install dependencies and verify**

Run: `uv sync --dev`
Expected: Dependencies installed successfully.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/ tests/conftest.py
git commit -m "feat: project scaffold with pyproject.toml, package structure, test fixtures"
```

---

## Task 2: Config Module

**Files:**
- Create: `src/claw_ea/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for config loading**

```python
# tests/test_config.py
import pytest
import yaml
from pathlib import Path
from claw_ea.config import load_config, Config, ConfigError


def test_load_valid_config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "user": {"name": "张医生", "aliases": ["张三"]},
        "obsidian": {"vault_path": str(tmp_path), "notes_folder": "Inbox/OpenClaw"},
        "attachments": {"base_path": str(tmp_path / "att"), "organize_by_date": True},
        "apple": {"calendar_name": "工作", "reminder_list": "OpenClaw"},
        "categories": {
            "surgery": {
                "schedule_time_slots": {1: "09:00", 2: "13:00"},
                "user_roles": ["主刀", "带组"],
            }
        },
    }))
    config = load_config(config_file)
    assert config.user_name == "张医生"
    assert config.vault_path == tmp_path
    assert isinstance(config, Config)


def test_load_missing_config(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nonexistent.yaml")


def test_load_invalid_yaml(tmp_path):
    bad = tmp_path / "config.yaml"
    bad.write_text("not: valid: yaml: {{")
    with pytest.raises(ConfigError):
        load_config(bad)


def test_load_missing_required_field(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"user": {"name": "张医生"}}))
    with pytest.raises(ConfigError, match="obsidian"):
        load_config(config_file)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'claw_ea.config'`

- [ ] **Step 3: Implement config.py**

```python
# src/claw_ea/config.py
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when config is missing, invalid, or incomplete."""


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


def load_config(path: Path | None = None) -> Config:
    """Load config from YAML file. Raises ConfigError if missing or invalid."""
    if path is None:
        path = Path.home() / ".claw-ea" / "config.yaml"

    if not path.exists():
        raise ConfigError(
            f"Config file not found: {path}\n"
            "Run the setup wizard to create one."
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError(f"Config must be a YAML mapping, got {type(raw).__name__}")

    return _parse_config(raw, path)


def _parse_config(raw: dict[str, Any], path: Path) -> Config:
    """Parse raw YAML dict into Config dataclass."""
    def require(section: str, key: str) -> Any:
        if section not in raw:
            raise ConfigError(f"Missing required section '{section}' in {path}")
        if key not in raw[section]:
            raise ConfigError(f"Missing required key '{section}.{key}' in {path}")
        return raw[section][key]

    user_name = require("user", "name")
    user_aliases = raw.get("user", {}).get("aliases", [])

    vault_path = Path(require("obsidian", "vault_path")).expanduser()
    notes_folder = require("obsidian", "notes_folder")

    att = raw.get("attachments", {})
    attachments_path = Path(att.get("base_path", str(vault_path / "attachments"))).expanduser()
    organize_by_date = att.get("organize_by_date", True)

    calendar_name = require("apple", "calendar_name")
    reminder_list = require("apple", "reminder_list")

    cats = raw.get("categories", {}).get("surgery", {})
    surgery_time_slots = {int(k): v for k, v in cats.get("schedule_time_slots", {1: "09:00", 2: "13:00", 3: "17:00", 4: "20:00"}).items()}
    surgery_user_roles = cats.get("user_roles", ["主刀", "带组", "一助"])

    return Config(
        user_name=user_name,
        user_aliases=user_aliases,
        vault_path=vault_path,
        notes_folder=notes_folder,
        attachments_path=attachments_path,
        organize_by_date=organize_by_date,
        calendar_name=calendar_name,
        reminder_list=reminder_list,
        surgery_time_slots=surgery_time_slots,
        surgery_user_roles=surgery_user_roles,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/claw_ea/config.py tests/test_config.py
git commit -m "feat: config module with dataclass, YAML loading, validation"
```

---

## Task 3: MCP Server Entry Point

**Files:**
- Create: `src/claw_ea/server.py`

- [ ] **Step 1: Implement server.py with FastMCP**

```python
# src/claw_ea/server.py
from mcp.server.fastmcp import FastMCP
from claw_ea.config import load_config, ConfigError

mcp = FastMCP("claw-ea", json_response=True)


def main():
    """Entry point for the MCP server."""
    try:
        config = load_config()
    except ConfigError as e:
        import sys
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Register Slice 1 tools (attachment + obsidian)
    # Each tool module exports register(mcp_instance, config) which uses
    # @mcp_instance.tool() inside a closure to capture config.
    from claw_ea.tools.attachment import register as reg_attachment
    from claw_ea.tools.obsidian import register as reg_obsidian

    reg_attachment(mcp, config)
    reg_obsidian(mcp, config)

    # Later slices will add: calendar, reminder, ocr, setup

    mcp.run(transport="stdio")
```

Each tool module exports a `register(mcp_instance, config)` function. Inside `register()`, the `@mcp_instance.tool()` decorator is used within a closure that captures `config`. This avoids global state while working with FastMCP's decorator API.

- [ ] **Step 2: Verify server starts (will fail without tools, but import should work)**

Run: `uv run python -c "from claw_ea.server import mcp; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/claw_ea/server.py src/claw_ea/__main__.py
git commit -m "feat: MCP server entry point with FastMCP and config loading"
```

---

## Task 4: save_attachment Tool

**Files:**
- Create: `src/claw_ea/tools/attachment.py`
- Create: `tests/test_attachment.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_attachment.py
import base64
import pytest
from pathlib import Path
from claw_ea.tools.attachment import save_attachment_impl


def test_save_basic_file(mock_config):
    content = base64.b64encode(b"hello world").decode()
    result = save_attachment_impl(content, "test.txt", "", mock_config)
    assert result["already_existed"] is False
    saved = Path(result["saved_path"])
    assert saved.exists()
    assert saved.read_bytes() == b"hello world"


def test_save_creates_date_subdirectory(mock_config):
    content = base64.b64encode(b"data").decode()
    result = save_attachment_impl(content, "file.pdf", "", mock_config)
    # Path should contain date components: YYYY/MM/DD
    parts = Path(result["saved_path"]).relative_to(mock_config.attachments_path).parts
    assert len(parts) == 4  # YYYY/MM/DD/filename


def test_save_duplicate_skips(mock_config):
    content = base64.b64encode(b"same content").decode()
    r1 = save_attachment_impl(content, "dup.txt", "", mock_config)
    r2 = save_attachment_impl(content, "dup.txt", "", mock_config)
    assert r1["saved_path"] == r2["saved_path"]
    assert r2["already_existed"] is True


def test_save_same_name_different_content(mock_config):
    c1 = base64.b64encode(b"content A").decode()
    c2 = base64.b64encode(b"content B").decode()
    r1 = save_attachment_impl(c1, "file.txt", "", mock_config)
    r2 = save_attachment_impl(c2, "file.txt", "", mock_config)
    assert r1["saved_path"] != r2["saved_path"]
    assert "file_1.txt" in r2["saved_path"]


def test_save_chinese_filename(mock_config):
    content = base64.b64encode(b"data").decode()
    result = save_attachment_impl(content, "手术通知_张三.pdf", "", mock_config)
    assert "手术通知_张三.pdf" in result["saved_path"]


def test_save_invalid_base64(mock_config):
    with pytest.raises(ValueError, match="base64"):
        save_attachment_impl("not-valid-base64!!!", "file.txt", "", mock_config)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_attachment.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement attachment.py**

```python
# src/claw_ea/tools/attachment.py
import base64
from datetime import date
from pathlib import Path

from claw_ea.config import Config


def save_attachment_impl(
    file_content: str, filename: str, subfolder: str, config: Config
) -> dict:
    """Core logic for save_attachment. Separate from MCP registration for testability."""
    try:
        data = base64.b64decode(file_content, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 content: {e}") from e

    # Build target directory
    target_dir = config.attachments_path
    if config.organize_by_date:
        today = date.today()
        target_dir = target_dir / f"{today.year}" / f"{today.month:02d}" / f"{today.day:02d}"
    if subfolder:
        target_dir = target_dir / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    target_file = target_dir / filename

    # Dedup: same name + same content → skip
    if target_file.exists() and target_file.read_bytes() == data:
        return {"saved_path": str(target_file), "already_existed": True}

    # Collision: same name + different content → add suffix
    if target_file.exists():
        stem = target_file.stem
        suffix = target_file.suffix
        counter = 1
        while target_file.exists():
            target_file = target_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    target_file.write_bytes(data)
    return {"saved_path": str(target_file), "already_existed": False}


def register(mcp_instance, config: Config):
    """Register save_attachment tool with the MCP server."""

    @mcp_instance.tool()
    async def save_attachment(
        file_content: str, filename: str, subfolder: str = ""
    ) -> dict:
        """Save a file to the attachments directory, organized by date.

        Args:
            file_content: Base64-encoded file content
            filename: Original filename (e.g. "手术通知_张三.pdf")
            subfolder: Optional subdirectory within the date folder

        Returns:
            saved_path: Absolute path where the file was saved
            already_existed: True if an identical file was already present
        """
        return save_attachment_impl(file_content, filename, subfolder, config)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_attachment.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/claw_ea/tools/attachment.py tests/test_attachment.py
git commit -m "feat: save_attachment tool with date organization, dedup, collision handling"
```

---

## Task 5: create_obsidian_note Tool

**Files:**
- Create: `src/claw_ea/tools/obsidian.py`
- Create: `tests/test_obsidian.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_obsidian.py
import pytest
import json
from pathlib import Path
from claw_ea.tools.obsidian import create_obsidian_note_impl


def test_create_surgery_note(mock_config):
    data = {
        "title": "手术安排：张三 - 腹腔镜胆囊切除术",
        "patient": "张三",
        "procedure": "腹腔镜胆囊切除术",
        "datetime": "2026-03-22T09:00",
        "surgeon": "李医生",
        "location": "3号手术室",
        "summary": "明天第一台手术",
    }
    result = create_obsidian_note_impl("surgery", data["title"], data, [], mock_config)
    assert result["already_existed"] is False
    note = Path(result["note_path"])
    assert note.exists()
    content = note.read_text(encoding="utf-8")
    assert "category: surgery" in content
    assert "张三" in content
    assert "腹腔镜胆囊切除术" in content


def test_create_meeting_note(mock_config):
    data = {
        "title": "科室周会",
        "datetime": "2026-03-22T14:00",
        "location": "会议室A",
        "summary": "每周例会",
    }
    result = create_obsidian_note_impl("meeting", data["title"], data, [], mock_config)
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    assert "category: meeting" in content


def test_note_with_attachment_links(mock_config):
    data = {"title": "文件归档", "summary": "收到文件"}
    paths = ["/path/to/手术通知.pdf", "/path/to/会议纪要.docx"]
    result = create_obsidian_note_impl("document", data["title"], data, paths, mock_config)
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    assert "[[手术通知.pdf]]" in content or "手术通知.pdf" in content


def test_dedup_same_content(mock_config):
    data = {"title": "test", "key": "value"}
    r1 = create_obsidian_note_impl("general", "test", data, [], mock_config)
    r2 = create_obsidian_note_impl("general", "test", data, [], mock_config)
    assert r1["note_path"] == r2["note_path"]
    assert r2["already_existed"] is True


def test_different_content_different_hash(mock_config):
    d1 = {"title": "test", "key": "value1"}
    d2 = {"title": "test", "key": "value2"}
    r1 = create_obsidian_note_impl("general", "test1", d1, [], mock_config)
    r2 = create_obsidian_note_impl("general", "test2", d2, [], mock_config)
    assert r1["note_path"] != r2["note_path"]


def test_frontmatter_is_valid_yaml(mock_config):
    import yaml
    data = {"title": "test", "summary": "hello"}
    result = create_obsidian_note_impl("general", "test", data, [], mock_config)
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    # Extract frontmatter between --- markers
    parts = content.split("---")
    assert len(parts) >= 3
    fm = yaml.safe_load(parts[1])
    assert fm["category"] == "general"


def test_note_path_in_configured_folder(mock_config):
    data = {"title": "test", "summary": "hello"}
    result = create_obsidian_note_impl("general", "test", data, [], mock_config)
    note = Path(result["note_path"])
    assert str(mock_config.vault_path / mock_config.notes_folder) in str(note.parent)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_obsidian.py -v`
Expected: FAIL

- [ ] **Step 3: Implement obsidian.py**

```python
# src/claw_ea/tools/obsidian.py
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from claw_ea.config import Config


def _content_hash(content_data: dict) -> str:
    """SHA256 of sorted JSON, first 8 hex chars."""
    canonical = json.dumps(content_data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]


def _render_frontmatter(category: str, content_data: dict) -> str:
    """Generate YAML frontmatter for the note."""
    fm: dict[str, Any] = {
        "date": date.today().isoformat(),
        "category": category,
    }
    # Add category-specific fields
    for key in ("patient", "procedure", "surgeon", "datetime", "location",
                "meeting_title", "meeting_date", "attendees", "priority"):
        if key in content_data:
            fm[key] = content_data[key]

    fm["tags"] = [category]
    return yaml.dump(fm, default_flow_style=False, allow_unicode=True)


def _render_body(category: str, title: str, content_data: dict, attachment_paths: list[str]) -> str:
    """Generate Markdown body for the note."""
    lines = [f"# {title}", ""]

    # Summary section
    if "summary" in content_data:
        lines.extend(["## 摘要", f"> {content_data['summary']}", ""])

    # Key fields as bullet list
    field_labels = {
        "patient": "患者", "procedure": "术式", "surgeon": "主刀",
        "datetime": "时间", "location": "地点",
    }
    detail_lines = []
    for key, label in field_labels.items():
        if key in content_data:
            detail_lines.append(f"- **{label}**：{content_data[key]}")
    if detail_lines:
        lines.extend(["## 详细信息"] + detail_lines + [""])

    # Attachments
    if attachment_paths:
        lines.append("## 附件")
        for p in attachment_paths:
            filename = Path(p).name
            lines.append(f"- [[{filename}]]")
        lines.append("")

    # Notes placeholder
    lines.extend(["## 备注", "（待补充）", ""])
    return "\n".join(lines)


def create_obsidian_note_impl(
    category: str, title: str, content_data: dict,
    attachment_paths: list[str], config: Config,
) -> dict:
    """Core logic for create_obsidian_note."""
    chash = _content_hash(content_data)
    today = date.today().isoformat()
    filename = f"{today}-{category}-{chash}.md"

    notes_dir = config.vault_path / config.notes_folder
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_path = notes_dir / filename

    if note_path.exists():
        return {"note_path": str(note_path), "already_existed": True}

    frontmatter = _render_frontmatter(category, content_data)
    body = _render_body(category, title, content_data, attachment_paths)
    content = f"---\n{frontmatter}---\n\n{body}"

    note_path.write_text(content, encoding="utf-8")
    return {"note_path": str(note_path), "already_existed": False}


def register(mcp_instance, config: Config):
    """Register create_obsidian_note tool with the MCP server."""

    @mcp_instance.tool()
    async def create_obsidian_note(
        category: str, title: str, content_data: dict, attachment_paths: list[str] | None = None,
    ) -> dict:
        """Create an Obsidian note with YAML frontmatter. Deduplicates by content hash.

        Args:
            category: One of: surgery, meeting, meeting_minutes, task, document, general
            title: Note title (e.g. "手术安排：张三 - 腹腔镜胆囊切除术")
            content_data: Structured data extracted from the message. Keys vary by category.
                Common keys: title, datetime, location, summary.
                Surgery: patient, procedure, surgeon.
                Meeting: attendees, meeting_title.
            attachment_paths: Absolute paths to saved attachment files (from save_attachment)

        Returns:
            note_path: Absolute path to the created note
            already_existed: True if a note with identical content already exists
        """
        return create_obsidian_note_impl(
            category, title, content_data, attachment_paths or [], config
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_obsidian.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/claw_ea/tools/obsidian.py tests/test_obsidian.py
git commit -m "feat: create_obsidian_note tool with frontmatter, content-hash dedup, templates"
```

---

## Task 6: Wire Up Server + Slice 1 Integration Test

**Files:**
- Modify: `src/claw_ea/server.py`
- Create: `tests/test_integration.py`

- [ ] **Step 1: Update server.py to register Slice 1 tools**

Update the `main()` function in `server.py` to import and register attachment and obsidian tools:

```python
# In server.py main(), replace the tool import section:
    from claw_ea.tools.attachment import register as register_attachment
    from claw_ea.tools.obsidian import register as register_obsidian

    register_attachment(mcp, _config)
    register_obsidian(mcp, _config)
```

- [ ] **Step 2: Write integration test**

```python
# tests/test_integration.py
import base64
from pathlib import Path
from claw_ea.tools.attachment import save_attachment_impl
from claw_ea.tools.obsidian import create_obsidian_note_impl


def test_end_to_end_attachment_then_note(mock_config):
    """Save an attachment, then create a note linking to it."""
    # Save attachment
    content = base64.b64encode(b"PDF content here").decode()
    att_result = save_attachment_impl(content, "手术通知.pdf", "", mock_config)
    assert att_result["already_existed"] is False

    # Create note linking to attachment
    note_data = {
        "title": "手术安排：张三",
        "patient": "张三",
        "procedure": "腹腔镜胆囊切除术",
        "datetime": "2026-03-22T09:00",
        "summary": "明天第一台手术",
    }
    note_result = create_obsidian_note_impl(
        "surgery", note_data["title"], note_data,
        [att_result["saved_path"]], mock_config,
    )
    assert note_result["already_existed"] is False

    # Verify note contains attachment link
    note_content = Path(note_result["note_path"]).read_text(encoding="utf-8")
    assert "手术通知.pdf" in note_content
    assert "张三" in note_content
```

- [ ] **Step 3: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass (config + attachment + obsidian + integration)

- [ ] **Step 4: Commit**

```bash
git add src/claw_ea/server.py tests/test_integration.py
git commit -m "feat: wire up server with Slice 1 tools, add integration test"
```

---

## Task 7: EventKit Utils (Shared Client)

**Files:**
- Create: `src/claw_ea/eventkit_utils.py`
- Create: `tests/test_calendar.py` (mock tests only in this task)

- [ ] **Step 1: Write failing mock test for EventKitClient**

```python
# tests/test_calendar.py
import pytest
from unittest.mock import MagicMock, patch


def test_eventkit_client_init():
    """EventKitClient initializes without error (mocked)."""
    with patch("claw_ea.eventkit_utils.EKEventStore") as MockStore:
        MockStore.alloc.return_value.init.return_value = MagicMock()
        from claw_ea.eventkit_utils import EventKitClient
        client = EventKitClient()
        assert client.store is not None


def test_find_calendar_returns_none_when_missing():
    """find_calendar returns None for nonexistent calendar name."""
    with patch("claw_ea.eventkit_utils.EKEventStore") as MockStore:
        mock_store = MagicMock()
        mock_store.calendarsForEntityType_.return_value = []
        MockStore.alloc.return_value.init.return_value = mock_store
        from claw_ea.eventkit_utils import EventKitClient
        client = EventKitClient()
        assert client.find_calendar("nonexistent") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_calendar.py -v`
Expected: FAIL

- [ ] **Step 3: Implement eventkit_utils.py**

```python
# src/claw_ea/eventkit_utils.py
"""Shared EventKit client for Calendar and Reminders tools."""
import asyncio
from functools import partial

try:
    from EventKit import (
        EKEventStore,
        EKEntityTypeEvent,
        EKEntityTypeReminder,
        EKAuthorizationStatusAuthorized,
    )
    EVENTKIT_AVAILABLE = True
except ImportError:
    EVENTKIT_AVAILABLE = False


class EventKitClient:
    def __init__(self):
        if not EVENTKIT_AVAILABLE:
            raise RuntimeError(
                "pyobjc-framework-EventKit not available. "
                "This tool requires macOS."
            )
        self.store = EKEventStore.alloc().init()

    async def ensure_calendar_access(self) -> None:
        """Request calendar access. Raises PermissionError if denied."""
        granted = await self._request_access(EKEntityTypeEvent)
        if not granted:
            raise PermissionError(
                "Calendar access denied. Grant access in "
                "System Preferences > Privacy & Security > Calendars."
            )

    async def ensure_reminder_access(self) -> None:
        """Request reminder access. Raises PermissionError if denied."""
        granted = await self._request_access(EKEntityTypeReminder)
        if not granted:
            raise PermissionError(
                "Reminders access denied. Grant access in "
                "System Preferences > Privacy & Security > Reminders."
            )

    async def _request_access(self, entity_type: int) -> bool:
        """Bridge ObjC completion handler to asyncio."""
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        def callback(granted, error):
            loop.call_soon_threadsafe(future.set_result, granted)

        self.store.requestAccessToEntityType_completion_(entity_type, callback)
        return await future

    def find_calendar(self, name: str):
        """Find a calendar by name. Returns EKCalendar or None."""
        calendars = self.store.calendarsForEntityType_(EKEntityTypeEvent)
        for cal in calendars:
            if cal.title() == name:
                return cal
        return None

    def find_reminder_list(self, name: str):
        """Find a reminder list by name. Returns EKCalendar or None."""
        calendars = self.store.calendarsForEntityType_(EKEntityTypeReminder)
        for cal in calendars:
            if cal.title() == name:
                return cal
        return None

    def list_calendars(self) -> list[str]:
        """List all calendar names."""
        return [c.title() for c in self.store.calendarsForEntityType_(EKEntityTypeEvent)]

    def list_reminder_lists(self) -> list[str]:
        """List all reminder list names."""
        return [c.title() for c in self.store.calendarsForEntityType_(EKEntityTypeReminder)]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_calendar.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/claw_ea/eventkit_utils.py tests/test_calendar.py
git commit -m "feat: EventKitClient with async permission requests, calendar/reminder lookup"
```

---

## Task 8: create_calendar_event Tool

**Files:**
- Create: `src/claw_ea/tools/calendar.py`
- Modify: `tests/test_calendar.py` (add tool tests)

- [ ] **Step 1: Add failing tests for create_calendar_event**

Append to `tests/test_calendar.py`:

```python
from unittest.mock import MagicMock, patch, AsyncMock
from claw_ea.tools.calendar import create_calendar_event_impl


@pytest.fixture
def mock_ek_client():
    client = MagicMock()
    client.ensure_calendar_access = AsyncMock()
    mock_cal = MagicMock()
    mock_cal.title.return_value = "工作"
    client.find_calendar.return_value = mock_cal
    client.store = MagicMock()
    client.store.saveEvent_span_error_.return_value = (True, None)
    return client


@pytest.mark.asyncio
async def test_create_event_basic(mock_ek_client):
    with patch("claw_ea.tools.calendar.EKEvent") as MockEvent:
        mock_event = MagicMock()
        mock_event.eventIdentifier.return_value = "test-id-123"
        MockEvent.eventWithEventStore_.return_value = mock_event

        result = await create_calendar_event_impl(
            title="[主刀] 腹腔镜胆囊切除术 - 张三",
            start_time="2026-03-22T09:00:00",
            end_time=None, location="3号手术室", notes="第一台",
            ek_client=mock_ek_client, calendar_name="工作",
        )
        assert result["event_id"] == "test-id-123"
        assert result["calendar"] == "工作"


@pytest.mark.asyncio
async def test_create_event_calendar_not_found(mock_ek_client):
    mock_ek_client.find_calendar.return_value = None
    with pytest.raises(ValueError, match="Calendar.*not found"):
        await create_calendar_event_impl(
            title="test", start_time="2026-03-22T09:00:00",
            ek_client=mock_ek_client, calendar_name="不存在",
        )
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_calendar.py::test_create_event_basic -v`
Expected: FAIL

- [ ] **Step 3: Implement calendar.py**

```python
# src/claw_ea/tools/calendar.py
"""create_calendar_event MCP tool."""
from datetime import datetime, timedelta

from claw_ea.config import Config

try:
    from EventKit import EKEvent, EKSpanThisEvent
    from Foundation import NSDate
    EVENTKIT_AVAILABLE = True
except ImportError:
    EVENTKIT_AVAILABLE = False


def _parse_datetime(iso_str: str) -> "NSDate":
    """Parse ISO-8601 string to NSDate."""
    dt = datetime.fromisoformat(iso_str)
    timestamp = dt.timestamp()
    return NSDate.dateWithTimeIntervalSince1970_(timestamp)


async def create_calendar_event_impl(
    title: str, start_time: str, end_time: str | None = None,
    location: str | None = None, notes: str | None = None,
    *, ek_client, calendar_name: str,
) -> dict:
    """Core logic for create_calendar_event."""
    await ek_client.ensure_calendar_access()

    calendar = ek_client.find_calendar(calendar_name)
    if calendar is None:
        available = ek_client.list_calendars()
        raise ValueError(
            f"Calendar '{calendar_name}' not found. "
            f"Available: {', '.join(available) if available else 'none'}"
        )

    event = EKEvent.eventWithEventStore_(ek_client.store)
    event.setTitle_(title)
    event.setCalendar_(calendar)
    event.setStartDate_(_parse_datetime(start_time))

    if end_time:
        event.setEndDate_(_parse_datetime(end_time))
    else:
        # Default: 1 hour
        start_dt = datetime.fromisoformat(start_time)
        end_dt = start_dt + timedelta(hours=1)
        event.setEndDate_(_parse_datetime(end_dt.isoformat()))

    if location:
        event.setLocation_(location)
    if notes:
        event.setNotes_(notes)

    success, error = ek_client.store.saveEvent_span_error_(event, EKSpanThisEvent, None)
    if not success:
        raise RuntimeError(f"Failed to save event: {error}")

    return {
        "event_id": event.eventIdentifier(),
        "calendar": calendar_name,
    }


def register(mcp_instance, config: Config, ek_client):
    """Register create_calendar_event tool."""

    @mcp_instance.tool()
    async def create_calendar_event(
        title: str, start_time: str, end_time: str = "",
        location: str = "", notes: str = "",
    ) -> dict:
        """Create an event in Apple Calendar.

        Args:
            title: Event title (e.g. "[主刀] 腹腔镜胆囊切除术 - 张三")
            start_time: ISO-8601 datetime (e.g. "2026-03-22T09:00:00")
            end_time: ISO-8601 datetime. Defaults to start_time + 1 hour.
            location: Event location (e.g. "3号手术室")
            notes: Additional notes

        Returns:
            event_id: Apple Calendar event identifier
            calendar: Calendar name used
        """
        return await create_calendar_event_impl(
            title, start_time, end_time or None, location or None, notes or None,
            ek_client=ek_client, calendar_name=config.calendar_name,
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_calendar.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/claw_ea/tools/calendar.py tests/test_calendar.py
git commit -m "feat: create_calendar_event tool with EventKit, default duration, error handling"
```

---

## Task 9: create_reminder Tool

**Files:**
- Create: `src/claw_ea/tools/reminder.py`
- Create: `tests/test_reminder.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_reminder.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from claw_ea.tools.reminder import create_reminder_impl


@pytest.fixture
def mock_ek_client():
    client = MagicMock()
    client.ensure_reminder_access = AsyncMock()
    mock_list = MagicMock()
    mock_list.title.return_value = "OpenClaw"
    client.find_reminder_list.return_value = mock_list
    client.store = MagicMock()
    client.store.saveReminder_commit_error_.return_value = (True, None)
    return client


@pytest.mark.asyncio
async def test_create_reminder_basic(mock_ek_client):
    with patch("claw_ea.tools.reminder.EKReminder") as MockReminder:
        mock_rem = MagicMock()
        mock_rem.calendarItemIdentifier.return_value = "rem-id-456"
        MockReminder.reminderWithEventStore_.return_value = mock_rem

        result = await create_reminder_impl(
            title="术前准备：张三 腹腔镜胆囊切除术",
            due_date="2026-03-22T08:00:00",
            priority=None, notes="提前1小时提醒",
            ek_client=mock_ek_client, list_name="OpenClaw",
        )
        assert result["reminder_id"] == "rem-id-456"


@pytest.mark.asyncio
async def test_create_reminder_no_due_date(mock_ek_client):
    with patch("claw_ea.tools.reminder.EKReminder") as MockReminder:
        mock_rem = MagicMock()
        mock_rem.calendarItemIdentifier.return_value = "rem-id-789"
        MockReminder.reminderWithEventStore_.return_value = mock_rem

        result = await create_reminder_impl(
            title="跟进检查结果",
            due_date=None, priority=None, notes=None,
            ek_client=mock_ek_client, list_name="OpenClaw",
        )
        assert result["reminder_id"] == "rem-id-789"


@pytest.mark.asyncio
async def test_create_reminder_list_not_found(mock_ek_client):
    mock_ek_client.find_reminder_list.return_value = None
    with pytest.raises(ValueError, match="not found"):
        await create_reminder_impl(
            title="test", due_date=None, priority=None, notes=None,
            ek_client=mock_ek_client, list_name="不存在",
        )
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_reminder.py -v`
Expected: FAIL

- [ ] **Step 3: Implement reminder.py**

```python
# src/claw_ea/tools/reminder.py
"""create_reminder MCP tool."""
from datetime import datetime

from claw_ea.config import Config

try:
    from EventKit import EKReminder
    from Foundation import NSDate, NSCalendar, NSDateComponents
    EVENTKIT_AVAILABLE = True
except ImportError:
    EVENTKIT_AVAILABLE = False


async def create_reminder_impl(
    title: str, due_date: str | None = None,
    priority: int | None = None, notes: str | None = None,
    *, ek_client, list_name: str,
) -> dict:
    """Core logic for create_reminder."""
    await ek_client.ensure_reminder_access()

    rem_list = ek_client.find_reminder_list(list_name)
    if rem_list is None:
        available = ek_client.list_reminder_lists()
        raise ValueError(
            f"Reminder list '{list_name}' not found. "
            f"Available: {', '.join(available) if available else 'none'}"
        )

    reminder = EKReminder.reminderWithEventStore_(ek_client.store)
    reminder.setTitle_(title)
    reminder.setCalendar_(rem_list)

    if due_date:
        dt = datetime.fromisoformat(due_date)
        cal = NSCalendar.currentCalendar()
        components = NSDateComponents.alloc().init()
        components.setYear_(dt.year)
        components.setMonth_(dt.month)
        components.setDay_(dt.day)
        components.setHour_(dt.hour)
        components.setMinute_(dt.minute)
        reminder.setDueDateComponents_(components)

    if priority is not None:
        reminder.setPriority_(priority)
    if notes:
        reminder.setNotes_(notes)

    success, error = ek_client.store.saveReminder_commit_error_(reminder, True, None)
    if not success:
        raise RuntimeError(f"Failed to save reminder: {error}")

    return {
        "reminder_id": reminder.calendarItemIdentifier(),
        "list": list_name,
    }


def register(mcp_instance, config: Config, ek_client):
    """Register create_reminder tool."""

    @mcp_instance.tool()
    async def create_reminder(
        title: str, due_date: str = "", priority: int = 0, notes: str = "",
    ) -> dict:
        """Create a reminder in Apple Reminders.

        Args:
            title: Reminder title (e.g. "[主持] 新技术培训 - 科室周会 10:00")
            due_date: ISO-8601 datetime for due date. Empty for undated reminder.
            priority: 1-9 (1=highest). 0 or empty for default.
            notes: Additional notes

        Returns:
            reminder_id: Apple Reminders identifier
            list: Reminder list name used
        """
        return await create_reminder_impl(
            title, due_date or None, priority or None, notes or None,
            ek_client=ek_client, list_name=config.reminder_list,
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_reminder.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/claw_ea/tools/reminder.py tests/test_reminder.py
git commit -m "feat: create_reminder tool with EventKit, due date, priority support"
```

---

## Task 10: ocr_image Tool

**Files:**
- Create: `src/claw_ea/tools/ocr.py`
- Create: `tests/test_ocr.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_ocr.py
import base64
import pytest
from unittest.mock import MagicMock, patch
from claw_ea.tools.ocr import ocr_image_impl


def test_ocr_invalid_base64():
    with pytest.raises(ValueError, match="base64"):
        ocr_image_impl("not-valid!!!", "test.png")


def test_ocr_returns_text(tmp_path):
    """Test with mocked Vision framework."""
    # Create a small valid PNG (1x1 pixel)
    import struct, zlib
    def make_png():
        header = b'\x89PNG\r\n\x1a\n'
        ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data)
        ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
        raw = zlib.compress(b'\x00\x00\x00\x00')
        idat_crc = zlib.crc32(b'IDAT' + raw)
        idat = struct.pack('>I', len(raw)) + b'IDAT' + raw + struct.pack('>I', idat_crc)
        iend_crc = zlib.crc32(b'IEND')
        iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
        return header + ihdr + idat + iend

    img_b64 = base64.b64encode(make_png()).decode()

    with patch("claw_ea.tools.ocr.VISION_AVAILABLE", True), \
         patch("claw_ea.tools.ocr._run_ocr") as mock_ocr:
        mock_ocr.return_value = "手术排班表 2026年3月22日"
        result = ocr_image_impl(img_b64, "排班表.png")
        assert result["extracted_text"] == "手术排班表 2026年3月22日"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ocr.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ocr.py**

```python
# src/claw_ea/tools/ocr.py
"""ocr_image MCP tool — local OCR via macOS Vision framework."""
import base64

try:
    from Vision import VNRecognizeTextRequest, VNImageRequestHandler
    from Foundation import NSData
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False


def _run_ocr(image_data: bytes) -> str:
    """Run OCR using macOS Vision framework. Returns extracted text."""
    ns_data = NSData.dataWithBytes_length_(image_data, len(image_data))
    handler = VNImageRequestHandler.alloc().initWithData_options_(ns_data, None)

    request = VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLanguages_(["zh-Hans", "en"])
    request.setRecognitionLevel_(1)  # VNRequestTextRecognitionLevelAccurate

    success, error = handler.performRequests_error_([request], None)
    if not success:
        raise RuntimeError(f"Vision OCR failed: {error}")

    results = request.results()
    lines = []
    for observation in results:
        candidate = observation.topCandidates_(1)
        if candidate:
            lines.append(candidate[0].string())

    return "\n".join(lines)


def ocr_image_impl(image_content: str, filename: str) -> dict:
    """Core logic for ocr_image."""
    try:
        image_data = base64.b64decode(image_content, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 image content: {e}") from e

    if not VISION_AVAILABLE:
        raise RuntimeError(
            "macOS Vision framework not available. "
            "ocr_image requires macOS with pyobjc-framework-Vision."
        )

    text = _run_ocr(image_data)
    return {
        "extracted_text": text,
        "language": "zh-Hans+en",
    }


def register(mcp_instance):
    """Register ocr_image tool."""

    @mcp_instance.tool()
    async def ocr_image(image_content: str, filename: str) -> dict:
        """Extract text from an image using local OCR (macOS Vision framework).

        Use this tool only when the agent's LLM does not support vision/multimodal input.
        If the LLM can see images directly, prefer that over this tool.

        Args:
            image_content: Base64-encoded image data (PNG, JPEG, etc.)
            filename: Original filename for reference

        Returns:
            extracted_text: OCR-extracted text content
            language: Recognition languages used
        """
        return ocr_image_impl(image_content, filename)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_ocr.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/claw_ea/tools/ocr.py tests/test_ocr.py
git commit -m "feat: ocr_image tool with macOS Vision framework, Chinese+English support"
```

---

## Task 11: Configuration Tools

**Files:**
- Create: `src/claw_ea/tools/setup.py`
- Create: `tests/test_setup.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_setup.py
import pytest
import yaml
from pathlib import Path
from claw_ea.tools.setup import (
    detect_obsidian_vault_impl,
    save_config_impl,
)


def test_detect_vault_finds_existing(tmp_path):
    """Detects a vault when .obsidian directory exists."""
    vault = tmp_path / "MyVault"
    (vault / ".obsidian").mkdir(parents=True)
    results = detect_obsidian_vault_impl(search_paths=[tmp_path])
    assert str(vault) in results


def test_detect_vault_empty_when_none(tmp_path):
    results = detect_obsidian_vault_impl(search_paths=[tmp_path])
    assert results == []


def test_save_config_creates_file(tmp_path):
    config_path = tmp_path / "config.yaml"
    data = {
        "user": {"name": "张医生", "aliases": []},
        "obsidian": {"vault_path": "/tmp/vault", "notes_folder": "Inbox"},
        "attachments": {"base_path": "/tmp/att", "organize_by_date": True},
        "apple": {"calendar_name": "工作", "reminder_list": "OpenClaw"},
    }
    result = save_config_impl(data, config_path)
    assert result["saved"] is True
    assert config_path.exists()
    saved = yaml.safe_load(config_path.read_text())
    assert saved["user"]["name"] == "张医生"


def test_save_config_validates_required_fields(tmp_path):
    config_path = tmp_path / "config.yaml"
    with pytest.raises(ValueError, match="user.name"):
        save_config_impl({"user": {}}, config_path)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_setup.py -v`
Expected: FAIL

- [ ] **Step 3: Implement setup.py**

```python
# src/claw_ea/tools/setup.py
"""Configuration tools: detect_obsidian_vault, list_apple_calendars, save_config."""
from pathlib import Path
from typing import Any

import yaml


def detect_obsidian_vault_impl(search_paths: list[Path] | None = None) -> list[str]:
    """Scan for Obsidian vaults by looking for .obsidian directories."""
    if search_paths is None:
        home = Path.home()
        search_paths = [
            home / "Documents",
            home / "Obsidian",
            home,
        ]

    vaults = []
    for base in search_paths:
        if not base.exists():
            continue
        # Check direct children only (not deep recursive)
        try:
            for child in base.iterdir():
                if child.is_dir() and (child / ".obsidian").exists():
                    vaults.append(str(child))
        except PermissionError:
            continue
    return vaults


def save_config_impl(config_data: dict[str, Any], config_path: Path) -> dict:
    """Validate and save config to YAML file."""
    # Validate required fields
    required = [
        ("user", "name"),
        ("obsidian", "vault_path"),
        ("obsidian", "notes_folder"),
        ("apple", "calendar_name"),
        ("apple", "reminder_list"),
    ]
    for section, key in required:
        if section not in config_data or key not in config_data[section]:
            raise ValueError(f"Missing required field: {section}.{key}")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.dump(config_data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    return {"saved": True, "path": str(config_path)}


def register(mcp_instance, ek_client=None):
    """Register configuration tools."""

    @mcp_instance.tool()
    async def detect_obsidian_vault() -> list[str]:
        """Scan common locations for Obsidian vaults.

        Returns a list of absolute paths to directories containing .obsidian/.
        """
        return detect_obsidian_vault_impl()

    @mcp_instance.tool()
    async def list_apple_calendars() -> dict:
        """List available Apple Calendar calendars and Reminder lists.

        Returns:
            calendars: List of calendar names
            reminder_lists: List of reminder list names
        """
        if ek_client is None:
            return {"calendars": [], "reminder_lists": [], "error": "EventKit not available"}
        await ek_client.ensure_calendar_access()
        await ek_client.ensure_reminder_access()
        return {
            "calendars": ek_client.list_calendars(),
            "reminder_lists": ek_client.list_reminder_lists(),
        }

    @mcp_instance.tool()
    async def save_config(config_data: dict) -> dict:
        """Validate and save configuration to ~/.claw-ea/config.yaml.

        Args:
            config_data: Configuration dictionary with sections: user, obsidian, attachments, apple

        Returns:
            saved: True if saved successfully
            path: Absolute path to the saved config file
        """
        config_path = Path.home() / ".claw-ea" / "config.yaml"
        return save_config_impl(config_data, config_path)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_setup.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/claw_ea/tools/setup.py tests/test_setup.py
git commit -m "feat: config tools — detect_obsidian_vault, list_apple_calendars, save_config"
```

---

## Task 12: Final Server Wiring + Full Test Suite

**Files:**
- Modify: `src/claw_ea/server.py` (register all tools)
- Modify: `tests/test_integration.py` (add full suite)

- [ ] **Step 1: Update server.py to register all tools**

```python
# src/claw_ea/server.py — complete version
from mcp.server.fastmcp import FastMCP
from claw_ea.config import load_config, ConfigError

mcp = FastMCP("claw-ea", json_response=True)


def main():
    try:
        config = load_config()
    except ConfigError as e:
        import sys
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize EventKit client (may fail on non-macOS)
    ek_client = None
    try:
        from claw_ea.eventkit_utils import EventKitClient
        ek_client = EventKitClient()
    except (ImportError, RuntimeError):
        import sys
        print("WARNING: EventKit not available. Calendar/Reminder tools disabled.", file=sys.stderr)

    # Register all tools
    from claw_ea.tools.attachment import register as reg_attachment
    from claw_ea.tools.obsidian import register as reg_obsidian
    from claw_ea.tools.ocr import register as reg_ocr
    from claw_ea.tools.setup import register as reg_setup

    reg_attachment(mcp, config)
    reg_obsidian(mcp, config)
    reg_ocr(mcp)
    reg_setup(mcp, ek_client)

    if ek_client:
        from claw_ea.tools.calendar import register as reg_calendar
        from claw_ea.tools.reminder import register as reg_reminder
        reg_calendar(mcp, config, ek_client)
        reg_reminder(mcp, config, ek_client)

    mcp.run(transport="stdio")
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 3: Run non-macOS tests only (simulates CI)**

Run: `uv run pytest -m "not macos" -v`
Expected: All non-macOS tests pass

- [ ] **Step 4: Commit**

```bash
git add src/claw_ea/server.py
git commit -m "feat: wire all tools into server, graceful degradation for non-macOS"
```

- [ ] **Step 5: Verify CLAUDE.md is tracked and commit any updates**

CLAUDE.md already exists in the repo (created during project init). If any updates were made during implementation, commit them:

```bash
git diff CLAUDE.md  # Check for changes
git add CLAUDE.md   # Stage if changed
git status          # Verify state before committing
# Only commit if there are staged changes:
git commit -m "docs: update CLAUDE.md with implementation details" || echo "Nothing to commit"
```
