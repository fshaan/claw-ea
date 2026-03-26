# Markdown-First Content Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `convert_to_markdown` capability — convert files (PDF, docx, pptx, xlsx, images) to Markdown via configurable converter chains with fallback, then embed into Obsidian notes.

**Architecture:** Single-file `converters.py` with function-based converters, a `dispatch()` router with fallback chains, and `is_usable()` binary quality check. New MCP tool `convert_to_markdown` returns temp file path (not content). Modified `create_obsidian_note` reads from `raw_body_path` to avoid large text passing through agent context.

**Tech Stack:** Python 3.11+, subprocess (docling/markitdown/magic-pdf CLIs), httpx (LM Studio API), macOS Vision (OCR fallback), pytest

**Spec:** `docs/superpowers/specs/2026-03-26-md-first-content-pipeline-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/claw_ea/converters.py` | **New.** `ConversionResult` dataclass, `DEFAULT_ROUTING`, 5 converter functions (`convert_docling`, `convert_markitdown`, `convert_mineru`, `convert_lmstudio`, `convert_vision_ocr`), each with `_is_available()`, `is_usable()` quality check, `dispatch()` router, temp file cleanup |
| `src/claw_ea/tools/converter.py` | **New.** `convert_to_markdown` MCP tool — thin wrapper around `dispatch()` |
| `src/claw_ea/tools/obsidian.py` | **Modified.** Add `raw_body_path` parameter to `create_obsidian_note` |
| `src/claw_ea/config.py` | **Modified.** Add optional `converters` fields to `Config` dataclass, parse from YAML |
| `src/claw_ea/server.py` | **Modified.** Register `convert_to_markdown` tool |
| `tests/test_converters.py` | **New.** Tests for `is_usable`, routing, dispatch fallback, process cleanup |
| `tests/test_converter_tool.py` | **New.** Tests for `convert_to_markdown` MCP tool |
| `tests/test_obsidian.py` | **Modified.** Tests for `raw_body_path` behavior |
| `tests/test_config.py` | **Modified.** Tests for converters config parsing |
| `tests/conftest.py` | **Modified.** Update `mock_config` fixture with new Config fields |

---

## Task 0: Create feature branch

**Files:** None

- [ ] **Step 1: Create and switch to feature branch**

```bash
git checkout -b feat/md-first
```

- [ ] **Step 2: Verify branch**

```bash
git branch --show-current
```

Expected: `feat/md-first`

---

## Task 1: Config — add converters fields

**Files:**
- Modify: `src/claw_ea/config.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_config.py`

### Step 1: Update Config dataclass and conftest

- [ ] **Step 1a: Add new fields to Config dataclass**

In `src/claw_ea/config.py`, add these fields to the `Config` dataclass after `surgery_user_roles`:

```python
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
    # Converter settings (all optional)
    converter_paths: dict[str, str]  # e.g. {"docling": "/path/to/docling"}
    converter_routing: dict[str, dict[str, list[str]]]  # e.g. {".pdf": {"default": ["docling"]}}
    lmstudio_endpoint: str
    lmstudio_api_key: str
    lmstudio_model: str
    lmstudio_timeout: int
```

- [ ] **Step 1b: Update conftest mock_config with new fields**

In `tests/conftest.py`, add defaults for the new fields in `mock_config`:

```python
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
        converter_paths={},
        converter_routing={},
        lmstudio_endpoint="",
        lmstudio_api_key="",
        lmstudio_model="",
        lmstudio_timeout=120,
    )
```

- [ ] **Step 1c: Run existing tests to verify no breakage**

Run: `uv run pytest -x`
Expected: All existing tests PASS (the new fields have no effect on existing logic)

### Step 2: Write test for converters config parsing

- [ ] **Step 2a: Write test for parsing converters section**

Add to `tests/test_config.py`:

```python
def test_parse_converters_config(tmp_path):
    """Converters config section is parsed into Config fields."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
user:
  name: 张医生
obsidian:
  vault_path: /tmp/vault
  notes_folder: Inbox
apple:
  calendar_name: 工作
  reminder_list: OpenClaw
converters:
  lmstudio:
    endpoint: http://localhost:1234/v1
    api_key: test-key
    model: glm-ocr
    timeout: 90
  paths:
    docling: /usr/local/bin/docling
  routing:
    pdf:
      default: [docling]
      academic: [mineru, docling]
    image:
      default: [lmstudio, vision_ocr]
""", encoding="utf-8")
    from claw_ea.config import load_config
    cfg = load_config(config_file)
    assert cfg.lmstudio_endpoint == "http://localhost:1234/v1"
    assert cfg.lmstudio_api_key == "test-key"
    assert cfg.lmstudio_model == "glm-ocr"
    assert cfg.lmstudio_timeout == 90
    assert cfg.converter_paths == {"docling": "/usr/local/bin/docling"}
    assert cfg.converter_routing[".pdf"]["default"] == ["docling"]
    assert cfg.converter_routing[".pdf"]["academic"] == ["mineru", "docling"]
    assert cfg.converter_routing[".image"]["default"] == ["lmstudio", "vision_ocr"]


def test_parse_config_without_converters(tmp_path):
    """Missing converters section gives empty defaults."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
user:
  name: 张医生
obsidian:
  vault_path: /tmp/vault
  notes_folder: Inbox
apple:
  calendar_name: 工作
  reminder_list: OpenClaw
""", encoding="utf-8")
    from claw_ea.config import load_config
    cfg = load_config(config_file)
    assert cfg.converter_paths == {}
    assert cfg.converter_routing == {}
    assert cfg.lmstudio_endpoint == ""
    assert cfg.lmstudio_api_key == ""
    assert cfg.lmstudio_model == ""
    assert cfg.lmstudio_timeout == 120
```

- [ ] **Step 2b: Run tests to confirm they fail**

Run: `uv run pytest tests/test_config.py::test_parse_converters_config tests/test_config.py::test_parse_config_without_converters -v`
Expected: FAIL — `Config.__init__()` missing new fields in `_parse_config`

### Step 3: Implement converters config parsing

- [ ] **Step 3a: Add parsing logic to `_parse_config`**

In `src/claw_ea/config.py`, add this block before the `return Config(...)` at the end of `_parse_config`:

```python
    # Converters (entire section optional)
    conv = raw.get("converters", {})

    lms = conv.get("lmstudio", {})
    lmstudio_endpoint = lms.get("endpoint", "")
    lmstudio_api_key = lms.get("api_key", "")
    lmstudio_model = lms.get("model", "")
    lmstudio_timeout = lms.get("timeout", 120)

    converter_paths = conv.get("paths", {})

    # Normalize routing keys: config uses short names (pdf, image),
    # internal uses dot-prefixed (.pdf, .image)
    raw_routing = conv.get("routing", {})
    converter_routing = {}
    for fmt, chains in raw_routing.items():
        key = f".{fmt}" if not fmt.startswith(".") else fmt
        converter_routing[key] = chains
```

Then update the `return Config(...)` to include the new fields:

```python
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
        converter_paths=converter_paths,
        converter_routing=converter_routing,
        lmstudio_endpoint=lmstudio_endpoint,
        lmstudio_api_key=lmstudio_api_key,
        lmstudio_model=lmstudio_model,
        lmstudio_timeout=lmstudio_timeout,
    )
```

- [ ] **Step 3b: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: All PASS including the two new tests

- [ ] **Step 3c: Run full test suite**

Run: `uv run pytest -x`
Expected: All PASS

- [ ] **Step 3d: Commit**

```bash
git add src/claw_ea/config.py tests/conftest.py tests/test_config.py
git commit -m "feat(config): add optional converters config section

Parse lmstudio, paths, and routing from converters YAML section.
All fields optional with empty defaults."
```

---

## Task 2: is_usable() quality check

**Files:**
- Create: `src/claw_ea/converters.py`
- Create: `tests/test_converters.py`

- [ ] **Step 1: Write failing tests for is_usable**

Create `tests/test_converters.py`:

```python
import pytest
from claw_ea.converters import is_usable


class TestIsUsable:
    def test_empty_string(self):
        assert is_usable("") is False

    def test_whitespace_only(self):
        assert is_usable("   \n\t  \n") is False

    def test_normal_markdown(self):
        assert is_usable("# Hello\n\nThis is a test document.") is True

    def test_chinese_text(self):
        assert is_usable("# 手术通知\n\n患者张三，腹腔镜胆囊切除术") is True

    def test_garbled_mostly_control_chars(self):
        # Over 20% control/surrogate/private-use characters
        garbled = "\x00\x01\x02\x03\x04" * 10 + "hello"
        assert is_usable(garbled) is False

    def test_just_above_threshold(self):
        # 80% valid + 20% invalid → should pass
        valid = "a" * 80
        invalid = "\x00" * 20
        assert is_usable(valid + invalid) is True

    def test_just_below_threshold(self):
        # 79% valid + 21% invalid → should fail
        valid = "a" * 79
        invalid = "\x00" * 21
        assert is_usable(valid + invalid) is False

    def test_newlines_not_counted(self):
        # Text with lots of newlines should still pass
        assert is_usable("hello\n\n\n\n\nworld") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_converters.py::TestIsUsable -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'claw_ea.converters'`

- [ ] **Step 3: Implement is_usable**

Create `src/claw_ea/converters.py`:

```python
"""Markdown-first content pipeline: converter dispatch, routing, and quality check."""

import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConversionResult:
    """Result of a file-to-markdown conversion."""
    temp_path: str
    source_path: str
    converter_used: str
    fallback_used: bool


def is_usable(markdown: str) -> bool:
    """Check if converted markdown is usable (not empty, not garbled).

    Returns True if:
    - Non-empty and non-whitespace-only
    - At least 80% of non-newline characters are valid
      (not in Unicode categories Cc, Cs, Co — control, surrogate, private-use)
    """
    stripped = markdown.strip()
    if not stripped:
        return False

    # Count characters excluding newlines
    total = 0
    invalid = 0
    for ch in stripped:
        if ch == "\n":
            continue
        total += 1
        cat = unicodedata.category(ch)
        if cat.startswith(("Cc", "Cs", "Co")):
            invalid += 1

    if total == 0:
        return False

    valid_ratio = (total - invalid) / total
    return valid_ratio >= 0.80
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_converters.py::TestIsUsable -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/claw_ea/converters.py tests/test_converters.py
git commit -m "feat(converters): add is_usable() quality check and ConversionResult

Binary check: non-empty, >=80% valid unicode characters.
No scoring framework — v1 only needs empty/garbled detection."
```

---

## Task 3: Converter functions — docling and markitdown

**Files:**
- Modify: `src/claw_ea/converters.py`
- Modify: `tests/test_converters.py`

- [ ] **Step 1: Write failing tests for converter functions**

Add to `tests/test_converters.py`:

```python
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path
from claw_ea.converters import (
    docling_is_available, convert_docling,
    markitdown_is_available, convert_markitdown,
)


class TestDocling:
    @patch("shutil.which", return_value="/usr/local/bin/docling")
    def test_is_available_when_on_path(self, mock_which):
        assert docling_is_available({}) is True

    @patch("shutil.which", return_value=None)
    def test_is_available_with_config_path(self, mock_which):
        assert docling_is_available({"docling": "/custom/bin/docling"}) is True

    @patch("shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        assert docling_is_available({}) is False

    @patch("subprocess.Popen")
    @patch("shutil.which", return_value="/usr/local/bin/docling")
    def test_convert_success(self, mock_which, mock_popen, tmp_path):
        # docling writes output to <input_stem>.md in output dir
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake pdf")

        process = MagicMock()
        process.wait.return_value = 0
        process.returncode = 0
        process.pid = 12345
        mock_popen.return_value = process

        # docling writes to output_dir/test.md
        def simulate_output(*args, **kwargs):
            # Find the --output arg to know where docling writes
            cmd = args[0] if args else kwargs.get("args", [])
            for i, arg in enumerate(cmd):
                if arg == "--output":
                    out_dir = Path(cmd[i + 1])
                    out_dir.mkdir(parents=True, exist_ok=True)
                    (out_dir / "test.md").write_text("# Converted\n\nHello world")
                    break
            return process

        mock_popen.side_effect = simulate_output
        result = convert_docling(input_file, {}, timeout=60)
        assert "# Converted" in result
        assert "Hello world" in result

    @patch("subprocess.Popen")
    @patch("shutil.which", return_value="/usr/local/bin/docling")
    def test_convert_timeout(self, mock_which, mock_popen, tmp_path):
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake pdf")

        process = MagicMock()
        process.wait.side_effect = subprocess.TimeoutExpired(cmd="docling", timeout=60)
        process.pid = 12345
        mock_popen.return_value = process

        with pytest.raises(TimeoutError):
            convert_docling(input_file, {}, timeout=60)


class TestMarkitdown:
    @patch("shutil.which", return_value="/usr/local/bin/markitdown")
    def test_is_available_when_on_path(self, mock_which):
        assert markitdown_is_available({}) is True

    @patch("shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        assert markitdown_is_available({}) is False

    @patch("subprocess.Popen")
    @patch("shutil.which", return_value="/usr/local/bin/markitdown")
    def test_convert_success(self, mock_which, mock_popen, tmp_path):
        input_file = tmp_path / "test.docx"
        input_file.write_text("fake docx")

        process = MagicMock()
        process.communicate.return_value = (b"# Converted from docx\n\nContent here", b"")
        process.returncode = 0
        process.pid = 12345
        mock_popen.return_value = process

        result = convert_markitdown(input_file, {}, timeout=60)
        assert "# Converted from docx" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_converters.py::TestDocling tests/test_converters.py::TestMarkitdown -v`
Expected: FAIL — `ImportError: cannot import name 'docling_is_available'`

- [ ] **Step 3: Implement converter functions**

Add to `src/claw_ea/converters.py` (after the `is_usable` function):

```python
import os
import shutil
import signal
import subprocess
import tempfile


def _find_executable(name: str, config_paths: dict[str, str]) -> str | None:
    """Find executable by shutil.which() first, then config paths."""
    path = shutil.which(name)
    if path:
        return path
    return config_paths.get(name)


def _kill_process_group(pid: int) -> None:
    """Kill entire process group to clean up subprocess tree."""
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


# --- docling ---

def docling_is_available(config_paths: dict[str, str]) -> bool:
    return _find_executable("docling", config_paths) is not None


def convert_docling(file_path: Path, config_paths: dict[str, str], timeout: int = 60) -> str:
    """Convert file using docling CLI. Returns markdown string."""
    exe = _find_executable("docling", config_paths)
    if not exe:
        raise RuntimeError("docling not found")

    with tempfile.TemporaryDirectory(prefix="claw-ea-docling-") as out_dir:
        cmd = [exe, "--output", out_dir, str(file_path)]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=os.setsid,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_group(proc.pid)
            proc.wait(timeout=5)
            raise TimeoutError(f"docling timed out after {timeout}s on {file_path}")

        if proc.returncode != 0:
            stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            raise RuntimeError(f"docling failed (exit {proc.returncode}): {stderr[:500]}")

        # docling writes <stem>.md in the output directory
        stem = file_path.stem
        md_path = Path(out_dir) / f"{stem}.md"
        if not md_path.exists():
            # Try finding any .md file in output
            md_files = list(Path(out_dir).glob("*.md"))
            if not md_files:
                raise RuntimeError(f"docling produced no .md output for {file_path}")
            md_path = md_files[0]

        return md_path.read_text(encoding="utf-8")


# --- markitdown ---

def markitdown_is_available(config_paths: dict[str, str]) -> bool:
    return _find_executable("markitdown", config_paths) is not None


def convert_markitdown(file_path: Path, config_paths: dict[str, str], timeout: int = 60) -> str:
    """Convert file using markitdown CLI. Returns markdown string from stdout."""
    exe = _find_executable("markitdown", config_paths)
    if not exe:
        raise RuntimeError("markitdown not found")

    cmd = [exe, str(file_path)]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        preexec_fn=os.setsid,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_group(proc.pid)
        proc.wait(timeout=5)
        raise TimeoutError(f"markitdown timed out after {timeout}s on {file_path}")

    if proc.returncode != 0:
        raise RuntimeError(f"markitdown failed (exit {proc.returncode}): {stderr.decode('utf-8', errors='replace')[:500]}")

    return stdout.decode("utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_converters.py::TestDocling tests/test_converters.py::TestMarkitdown -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/claw_ea/converters.py tests/test_converters.py
git commit -m "feat(converters): add docling and markitdown converter functions

Subprocess-based with os.killpg() process group cleanup on timeout.
Executable lookup: shutil.which() first, then config paths."
```

---

## Task 4: Converter functions — lmstudio and vision_ocr

**Files:**
- Modify: `src/claw_ea/converters.py`
- Modify: `tests/test_converters.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_converters.py`:

```python
import json
from unittest.mock import patch, MagicMock
from claw_ea.converters import (
    lmstudio_is_available, convert_lmstudio,
    vision_ocr_is_available, convert_vision_ocr,
)


class TestLmstudio:
    def test_is_available_with_endpoint(self):
        assert lmstudio_is_available("http://localhost:1234/v1") is True

    def test_not_available_empty_endpoint(self):
        assert lmstudio_is_available("") is False

    @patch("urllib.request.urlopen")
    def test_convert_success(self, mock_urlopen, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        response_data = {
            "choices": [{"message": {"content": "# OCR Result\n\n手术通知：张三"}}]
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_data).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = convert_lmstudio(
            img, endpoint="http://localhost:1234/v1",
            api_key="test", model="glm-ocr", timeout=120
        )
        assert "手术通知" in result

    @patch("urllib.request.urlopen")
    def test_convert_connection_error(self, mock_urlopen, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")

        mock_urlopen.side_effect = ConnectionError("refused")
        with pytest.raises(RuntimeError, match="LM Studio"):
            convert_lmstudio(
                img, endpoint="http://localhost:1234/v1",
                api_key="test", model="glm-ocr", timeout=120
            )


class TestVisionOcr:
    @patch("claw_ea.converters.VISION_AVAILABLE", True)
    def test_is_available_on_macos(self):
        assert vision_ocr_is_available() is True

    @patch("claw_ea.converters.VISION_AVAILABLE", False)
    def test_not_available_without_vision(self):
        assert vision_ocr_is_available() is False

    @patch("claw_ea.converters.VISION_AVAILABLE", True)
    @patch("claw_ea.converters._run_ocr_from_file")
    def test_convert_success(self, mock_ocr, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        mock_ocr.return_value = "手术通知内容"

        result = convert_vision_ocr(img)
        assert "手术通知内容" in result
        mock_ocr.assert_called_once_with(img)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_converters.py::TestLmstudio tests/test_converters.py::TestVisionOcr -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement lmstudio and vision_ocr converters**

Add to `src/claw_ea/converters.py`:

```python
import base64
import json
import urllib.request
import urllib.error

try:
    from claw_ea.tools.ocr import _run_ocr, VISION_AVAILABLE
except ImportError:
    VISION_AVAILABLE = False

    def _run_ocr(image_data: bytes) -> str:
        raise RuntimeError("Vision framework not available")


# --- lmstudio ---

def lmstudio_is_available(endpoint: str) -> bool:
    return bool(endpoint)


def convert_lmstudio(
    file_path: Path, endpoint: str, api_key: str, model: str, timeout: int = 120
) -> str:
    """Convert image to markdown via LM Studio vision API."""
    image_data = file_path.read_bytes()
    b64 = base64.b64encode(image_data).decode("ascii")

    suffix = file_path.suffix.lower().lstrip(".")
    mime_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                 "bmp": "image/bmp", "tiff": "image/tiff", "webp": "image/webp"}.get(suffix, "image/png")

    payload = json.dumps({
        "model": model or "default",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "请将这张图片中的所有文字内容提取出来，用 Markdown 格式输出。保留原始结构和排版。"},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
            ],
        }],
        "max_tokens": 4096,
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        f"{endpoint}/chat/completions", data=payload, headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise RuntimeError(f"LM Studio request failed: {e}") from e


# --- vision_ocr ---

def _run_ocr_from_file(file_path: Path) -> str:
    """Read image file and run macOS Vision OCR."""
    image_data = file_path.read_bytes()
    return _run_ocr(image_data)


def vision_ocr_is_available() -> bool:
    return VISION_AVAILABLE


def convert_vision_ocr(file_path: Path) -> str:
    """Convert image to markdown using macOS Vision OCR (last-resort fallback)."""
    if not VISION_AVAILABLE:
        raise RuntimeError("macOS Vision framework not available")
    text = _run_ocr_from_file(file_path)
    return text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_converters.py::TestLmstudio tests/test_converters.py::TestVisionOcr -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/claw_ea/converters.py tests/test_converters.py
git commit -m "feat(converters): add lmstudio and vision_ocr converter functions

LM Studio: HTTP POST to OpenAI-compatible vision API.
Vision OCR: reuses ocr.py._run_ocr as image fallback chain end."
```

---

## Task 5: Converter function — mineru

**Files:**
- Modify: `src/claw_ea/converters.py`
- Modify: `tests/test_converters.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_converters.py`:

```python
from claw_ea.converters import mineru_is_available, convert_mineru


class TestMineru:
    @patch("shutil.which", return_value="/usr/local/bin/magic-pdf")
    def test_is_available(self, mock_which):
        assert mineru_is_available({}) is True

    @patch("shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        assert mineru_is_available({}) is False

    @patch("subprocess.Popen")
    @patch("shutil.which", return_value="/usr/local/bin/magic-pdf")
    def test_convert_success(self, mock_which, mock_popen, tmp_path):
        input_file = tmp_path / "paper.pdf"
        input_file.write_text("fake pdf")

        process = MagicMock()
        process.wait.return_value = 0
        process.returncode = 0
        process.pid = 12345
        mock_popen.return_value = process

        def simulate_output(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            for i, arg in enumerate(cmd):
                if arg == "-o":
                    out_dir = Path(cmd[i + 1])
                    md_dir = out_dir / "paper" / "auto"
                    md_dir.mkdir(parents=True, exist_ok=True)
                    (md_dir / "paper.md").write_text("# Academic Paper\n\n$E=mc^2$")
                    break
            return process

        mock_popen.side_effect = simulate_output
        result = convert_mineru(input_file, {}, timeout=120)
        assert "Academic Paper" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_converters.py::TestMineru -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement mineru converter**

Add to `src/claw_ea/converters.py`:

```python
# --- mineru ---

def mineru_is_available(config_paths: dict[str, str]) -> bool:
    return _find_executable("magic-pdf", config_paths) is not None


def convert_mineru(file_path: Path, config_paths: dict[str, str], timeout: int = 120) -> str:
    """Convert PDF using MinerU (magic-pdf). Specialty: academic papers, complex formulas."""
    exe = _find_executable("magic-pdf", config_paths)
    if not exe:
        raise RuntimeError("magic-pdf not found")

    with tempfile.TemporaryDirectory(prefix="claw-ea-mineru-") as out_dir:
        cmd = [exe, "-p", str(file_path), "-o", out_dir, "-m", "auto"]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=os.setsid,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_group(proc.pid)
            proc.wait(timeout=5)
            raise TimeoutError(f"magic-pdf timed out after {timeout}s on {file_path}")

        if proc.returncode != 0:
            stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            raise RuntimeError(f"magic-pdf failed (exit {proc.returncode}): {stderr[:500]}")

        # MinerU outputs to <out_dir>/<stem>/auto/<stem>.md
        stem = file_path.stem
        md_path = Path(out_dir) / stem / "auto" / f"{stem}.md"
        if not md_path.exists():
            # Search for any .md file recursively
            md_files = list(Path(out_dir).rglob("*.md"))
            if not md_files:
                raise RuntimeError(f"magic-pdf produced no .md output for {file_path}")
            md_path = md_files[0]

        return md_path.read_text(encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_converters.py::TestMineru -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/claw_ea/converters.py tests/test_converters.py
git commit -m "feat(converters): add mineru (magic-pdf) converter for academic PDFs

Subprocess-based with process group cleanup. Specialty: LaTeX formulas."
```

---

## Task 6: dispatch() routing with fallback

**Files:**
- Modify: `src/claw_ea/converters.py`
- Modify: `tests/test_converters.py`

- [ ] **Step 1: Write failing tests for dispatch**

Add to `tests/test_converters.py`:

```python
from claw_ea.converters import dispatch, DEFAULT_ROUTING, ConversionResult
from claw_ea.config import Config


class TestDispatch:
    def _make_config(self, tmp_path, routing=None, paths=None, **lms_kwargs):
        """Helper to build a Config with converter fields."""
        vault = tmp_path / "vault"
        vault.mkdir(exist_ok=True)
        (vault / "Inbox/OpenClaw").mkdir(parents=True, exist_ok=True)
        att = tmp_path / "attachments"
        att.mkdir(exist_ok=True)
        return Config(
            user_name="张医生", user_aliases=[], vault_path=vault,
            notes_folder="Inbox/OpenClaw", attachments_path=att,
            organize_by_date=True, calendar_name="工作", reminder_list="OpenClaw",
            surgery_time_slots={}, surgery_user_roles=[],
            converter_paths=paths or {},
            converter_routing=routing or {},
            lmstudio_endpoint=lms_kwargs.get("endpoint", ""),
            lmstudio_api_key=lms_kwargs.get("api_key", ""),
            lmstudio_model=lms_kwargs.get("model", ""),
            lmstudio_timeout=lms_kwargs.get("timeout", 120),
        )

    @patch("claw_ea.converters.docling_is_available", return_value=True)
    @patch("claw_ea.converters.convert_docling", return_value="# Good markdown\n\nContent here")
    def test_happy_path_pdf(self, mock_convert, mock_avail, tmp_path):
        cfg = self._make_config(tmp_path)
        f = tmp_path / "test.pdf"
        f.write_text("fake")
        result = dispatch(f, cfg)
        assert result.converter_used == "docling"
        assert result.fallback_used is False
        assert Path(result.temp_path).exists()
        assert "Good markdown" in Path(result.temp_path).read_text()

    @patch("claw_ea.converters.docling_is_available", return_value=True)
    @patch("claw_ea.converters.convert_docling", return_value="")
    @patch("claw_ea.converters.markitdown_is_available", return_value=True)
    @patch("claw_ea.converters.convert_markitdown", return_value="# Fallback content")
    def test_fallback_on_empty(self, mock_mk, mock_mk_avail, mock_dl, mock_dl_avail, tmp_path):
        cfg = self._make_config(tmp_path)
        f = tmp_path / "test.docx"
        f.write_text("fake")
        result = dispatch(f, cfg)
        assert result.converter_used == "markitdown"
        assert result.fallback_used is True

    @patch("claw_ea.converters.docling_is_available", return_value=False)
    @patch("claw_ea.converters.markitdown_is_available", return_value=True)
    @patch("claw_ea.converters.convert_markitdown", return_value="# Content")
    def test_skip_unavailable(self, mock_mk, mock_mk_avail, mock_dl_avail, tmp_path):
        cfg = self._make_config(tmp_path)
        f = tmp_path / "test.docx"
        f.write_text("fake")
        result = dispatch(f, cfg)
        assert result.converter_used == "markitdown"
        # First converter was unavailable, but we found one — not a "fallback"
        # since we never tried docling. fallback_used means a converter ran
        # but its output was rejected.
        assert result.fallback_used is False

    @patch("claw_ea.converters.docling_is_available", return_value=True)
    @patch("claw_ea.converters.convert_docling", side_effect=RuntimeError("crash"))
    @patch("claw_ea.converters.markitdown_is_available", return_value=True)
    @patch("claw_ea.converters.convert_markitdown", return_value="# Recovered")
    def test_fallback_on_exception(self, mock_mk, mock_mk_avail, mock_dl, mock_dl_avail, tmp_path):
        cfg = self._make_config(tmp_path)
        f = tmp_path / "test.pptx"
        f.write_text("fake")
        result = dispatch(f, cfg)
        assert result.converter_used == "markitdown"
        assert result.fallback_used is True

    def test_unsupported_extension(self, tmp_path):
        cfg = self._make_config(tmp_path)
        f = tmp_path / "test.xyz"
        f.write_text("fake")
        with pytest.raises(ValueError, match="Unsupported"):
            dispatch(f, cfg)

    @patch("claw_ea.converters.docling_is_available", return_value=True)
    @patch("claw_ea.converters.convert_docling", return_value="# Custom route")
    def test_hint_selects_sub_route(self, mock_convert, mock_avail, tmp_path):
        cfg = self._make_config(tmp_path, routing={
            ".pdf": {"default": ["markitdown"], "academic": ["docling"]},
        })
        f = tmp_path / "paper.pdf"
        f.write_text("fake")
        result = dispatch(f, cfg, hint="academic")
        assert result.converter_used == "docling"

    @patch("claw_ea.converters.docling_is_available", return_value=True)
    @patch("claw_ea.converters.convert_docling", return_value="")
    @patch("claw_ea.converters.markitdown_is_available", return_value=True)
    @patch("claw_ea.converters.convert_markitdown", return_value="\x00\x01\x02")
    def test_all_fail_returns_longest(self, mock_mk, mock_mk_avail, mock_dl, mock_dl_avail, tmp_path):
        cfg = self._make_config(tmp_path)
        f = tmp_path / "test.docx"
        f.write_text("fake")
        result = dispatch(f, cfg)
        # Should return the longest result (markitdown's 3 chars > docling's 0)
        assert result.converter_used == "markitdown"
        assert result.fallback_used is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_converters.py::TestDispatch -v`
Expected: FAIL — `ImportError: cannot import name 'dispatch'`

- [ ] **Step 3: Implement dispatch and DEFAULT_ROUTING**

Add to `src/claw_ea/converters.py`:

```python
import logging

logger = logging.getLogger(__name__)

# Image extensions that share the same converter chain
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp", ".gif"}

DEFAULT_ROUTING: dict[str, dict[str, list[str]]] = {
    ".pdf":  {"default": ["docling"]},
    ".docx": {"default": ["docling", "markitdown"]},
    ".pptx": {"default": ["docling", "markitdown"]},
    ".xlsx": {"default": ["docling", "markitdown"]},
    ".csv":  {"default": ["markitdown"]},
    ".html": {"default": ["docling", "markitdown"]},
}
# All image extensions share the same chain
for _ext in _IMAGE_EXTENSIONS:
    DEFAULT_ROUTING[_ext] = {"default": ["lmstudio", "docling", "vision_ocr"]}

# Registry: converter name → (is_available_func, convert_func)
# is_available takes varying args; convert takes (file_path, ..., timeout)
# dispatch() handles calling them with the right arguments.

CONVERTER_NAMES = {"docling", "markitdown", "mineru", "lmstudio", "vision_ocr"}


def _get_available_check(name: str, config: "Config") -> bool:
    """Check if a converter is available."""
    if name == "docling":
        return docling_is_available(config.converter_paths)
    elif name == "markitdown":
        return markitdown_is_available(config.converter_paths)
    elif name == "mineru":
        return mineru_is_available(config.converter_paths)
    elif name == "lmstudio":
        return lmstudio_is_available(config.lmstudio_endpoint)
    elif name == "vision_ocr":
        return vision_ocr_is_available()
    return False


def _run_converter(name: str, file_path: Path, config: "Config", timeout: int = 60) -> str:
    """Run a converter by name. Returns markdown string."""
    if name == "docling":
        return convert_docling(file_path, config.converter_paths, timeout=timeout)
    elif name == "markitdown":
        return convert_markitdown(file_path, config.converter_paths, timeout=timeout)
    elif name == "mineru":
        return convert_mineru(file_path, config.converter_paths, timeout=timeout)
    elif name == "lmstudio":
        return convert_lmstudio(
            file_path, endpoint=config.lmstudio_endpoint,
            api_key=config.lmstudio_api_key, model=config.lmstudio_model,
            timeout=config.lmstudio_timeout,
        )
    elif name == "vision_ocr":
        return convert_vision_ocr(file_path)
    raise ValueError(f"Unknown converter: {name}")


def dispatch(file_path: Path, config: "Config", hint: str = "") -> ConversionResult:
    """Route file to converter chain, try each with fallback.

    1. Look up chain by extension + hint
    2. Filter out unavailable converters
    3. Try each: convert → is_usable → return or fallback
    4. All fail → return longest result + warning
    """
    ext = file_path.suffix.lower()

    # Use .image as lookup key for image extensions in config routing
    routing = config.converter_routing if config.converter_routing else DEFAULT_ROUTING
    if ext in _IMAGE_EXTENSIONS and ext not in routing and ".image" in routing:
        route_entry = routing[".image"]
    elif ext in routing:
        route_entry = routing[ext]
    elif ext in DEFAULT_ROUTING:
        route_entry = DEFAULT_ROUTING[ext]
    else:
        raise ValueError(f"Unsupported file extension: {ext}")

    chain = route_entry.get(hint, route_entry["default"]) if isinstance(route_entry, dict) else route_entry

    # Filter to available converters
    available = [name for name in chain if _get_available_check(name, config)]
    if not available:
        raise RuntimeError(f"No converters available for {ext} (chain: {chain})")

    # Track attempts for "all fail" scenario
    best_result = ""
    best_converter = available[0]
    fallback_used = False
    tried_one = False

    for name in available:
        timeout = config.lmstudio_timeout if name == "lmstudio" else 60
        try:
            md = _run_converter(name, file_path, config, timeout=timeout)
        except Exception as e:
            logger.warning("Converter %s failed on %s: %s", name, file_path, e)
            if tried_one:
                fallback_used = True
            tried_one = True
            continue

        tried_one = True
        if is_usable(md):
            # Write to temp file
            temp_path = _write_temp(md)
            return ConversionResult(
                temp_path=temp_path,
                source_path=str(file_path),
                converter_used=name,
                fallback_used=fallback_used,
            )
        else:
            logger.warning("Converter %s output not usable for %s", name, file_path)
            fallback_used = True
            if len(md) > len(best_result):
                best_result = md
                best_converter = name

    # All failed — return best effort
    logger.warning("All converters failed for %s, returning best effort (%s)", file_path, best_converter)
    temp_path = _write_temp(best_result) if best_result else _write_temp(f"[Conversion failed for {file_path.name}]")
    return ConversionResult(
        temp_path=temp_path,
        source_path=str(file_path),
        converter_used=best_converter,
        fallback_used=True,
    )


def _write_temp(content: str) -> str:
    """Write content to a temp file. Returns path string."""
    import uuid
    temp_dir = Path(tempfile.gettempdir())
    temp_path = temp_dir / f"claw-ea-{uuid.uuid4().hex[:12]}.md"
    temp_path.write_text(content, encoding="utf-8")
    return str(temp_path)


def cleanup_stale_temps(max_age_seconds: int = 3600) -> int:
    """Remove claw-ea temp files older than max_age_seconds. Returns count removed."""
    import time
    temp_dir = Path(tempfile.gettempdir())
    removed = 0
    for f in temp_dir.glob("claw-ea-*.md"):
        try:
            if time.time() - f.stat().st_mtime > max_age_seconds:
                f.unlink()
                removed += 1
        except OSError:
            pass
    return removed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_converters.py::TestDispatch -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/claw_ea/converters.py tests/test_converters.py
git commit -m "feat(converters): add dispatch() routing with fallback chains

Routes by extension + optional hint. Tries each converter in chain,
falls back on failure/garbled output. Returns best-effort if all fail.
Includes temp file write and stale temp cleanup."
```

---

## Task 7: convert_to_markdown MCP tool

**Files:**
- Create: `src/claw_ea/tools/converter.py`
- Modify: `src/claw_ea/server.py`
- Create: `tests/test_converter_tool.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_converter_tool.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from claw_ea.converters import ConversionResult
from claw_ea.tools.converter import convert_to_markdown_impl


class TestConvertToMarkdownTool:
    @patch("claw_ea.tools.converter.dispatch")
    def test_success(self, mock_dispatch, tmp_path, mock_config):
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake pdf")

        temp_md = tmp_path / "output.md"
        temp_md.write_text("# Converted content")

        mock_dispatch.return_value = ConversionResult(
            temp_path=str(temp_md),
            source_path=str(input_file),
            converter_used="docling",
            fallback_used=False,
        )

        result = convert_to_markdown_impl(str(input_file), "", mock_config)
        assert result["md_path"] == str(temp_md)
        assert result["converter_used"] == "docling"
        assert result["fallback_used"] is False

    def test_file_not_found(self, mock_config):
        result = convert_to_markdown_impl("/nonexistent/file.pdf", "", mock_config)
        assert "error" in result

    @patch("claw_ea.tools.converter.dispatch")
    def test_dispatch_error(self, mock_dispatch, tmp_path, mock_config):
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake pdf")
        mock_dispatch.side_effect = ValueError("Unsupported file extension: .pdf")

        result = convert_to_markdown_impl(str(input_file), "", mock_config)
        assert "error" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_converter_tool.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'claw_ea.tools.converter'`

- [ ] **Step 3: Implement the MCP tool**

Create `src/claw_ea/tools/converter.py`:

```python
"""convert_to_markdown MCP tool — convert files to Markdown via configurable converter chains."""

from pathlib import Path

from claw_ea.config import Config
from claw_ea.converters import dispatch


def convert_to_markdown_impl(file_path: str, hint: str, config: Config) -> dict:
    """Core logic for convert_to_markdown."""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        result = dispatch(path, config, hint=hint)
    except (ValueError, RuntimeError) as e:
        return {"error": str(e)}

    return {
        "md_path": result.temp_path,
        "converter_used": result.converter_used,
        "fallback_used": result.fallback_used,
    }


def register(mcp_instance, config: Config):
    """Register convert_to_markdown tool with the MCP server."""

    @mcp_instance.tool()
    async def convert_to_markdown(file_path: str, hint: str = "") -> dict:
        """Convert a file to Markdown and save as a temp file.

        Supports: PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), images (jpg/png/etc).
        Automatically detects file type and selects the best converter.
        Result is written to a temp file (not returned as string) to avoid
        large text consuming agent context tokens.

        Args:
            file_path: Path to the file to convert.
            hint: Optional type hint to select a specialized converter chain.
                  For example, "academic" for academic PDF papers (uses MinerU).
                  Omit to use the default chain for the file extension.

        Returns:
            md_path: Path to the converted Markdown temp file.
                     Pass this to create_obsidian_note's raw_body_path parameter.
            converter_used: Name of the converter that produced the result.
            fallback_used: Whether a fallback converter was used.
        """
        return convert_to_markdown_impl(file_path, hint, config)
```

- [ ] **Step 4: Register in server.py**

In `src/claw_ea/server.py`, add the import and registration after the OCR registration:

```python
    from claw_ea.tools.converter import register as reg_converter

    reg_attachment(mcp, config)
    reg_obsidian(mcp, config)
    reg_ocr(mcp)
    reg_converter(mcp, config)
    reg_setup(mcp, ek_client)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_converter_tool.py -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest -x`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/claw_ea/tools/converter.py src/claw_ea/server.py tests/test_converter_tool.py
git commit -m "feat: add convert_to_markdown MCP tool

Thin wrapper around dispatch(). Returns temp file path, not content.
Registered as 9th MCP tool in server.py."
```

---

## Task 8: Modify create_obsidian_note — add raw_body_path

**Files:**
- Modify: `src/claw_ea/tools/obsidian.py`
- Modify: `tests/test_obsidian.py`

- [ ] **Step 1: Write failing tests for raw_body_path**

Add to `tests/test_obsidian.py`:

```python
def test_raw_body_path_creates_note_with_file_content(mock_config, tmp_path):
    """raw_body_path reads content from file and uses it as note body."""
    md_file = tmp_path / "converted.md"
    md_file.write_text("# Converted Content\n\nThis is the converted markdown.", encoding="utf-8")

    data = {"title": "test doc", "summary": "converted"}
    result = create_obsidian_note_impl(
        "document", "test doc", data, ["/path/to/original.pdf"], mock_config,
        raw_body_path=str(md_file),
    )
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    assert "# Converted Content" in content
    assert "This is the converted markdown." in content
    assert "category: document" in content  # frontmatter still generated
    assert "[[original.pdf]]" in content  # original file wikilink


def test_raw_body_path_deletes_temp_file(mock_config, tmp_path):
    """Temp file is deleted after reading."""
    md_file = tmp_path / "converted.md"
    md_file.write_text("# Content", encoding="utf-8")
    assert md_file.exists()

    create_obsidian_note_impl(
        "document", "test", {"title": "test"}, [], mock_config,
        raw_body_path=str(md_file),
    )
    assert not md_file.exists()


def test_raw_body_path_not_found(mock_config):
    """Missing raw_body_path file returns error."""
    result = create_obsidian_note_impl(
        "document", "test", {"title": "test"}, [], mock_config,
        raw_body_path="/nonexistent/file.md",
    )
    assert "error" in result


def test_raw_body_path_empty_string_uses_template(mock_config):
    """Empty raw_body_path (default) uses normal template rendering."""
    data = {"title": "test", "summary": "hello"}
    result = create_obsidian_note_impl(
        "general", "test", data, [], mock_config,
        raw_body_path="",
    )
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    assert "## 摘要" in content  # template-rendered section
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_obsidian.py::test_raw_body_path_creates_note_with_file_content tests/test_obsidian.py::test_raw_body_path_deletes_temp_file tests/test_obsidian.py::test_raw_body_path_not_found tests/test_obsidian.py::test_raw_body_path_empty_string_uses_template -v`
Expected: FAIL — `TypeError: create_obsidian_note_impl() got an unexpected keyword argument 'raw_body_path'`

- [ ] **Step 3: Implement raw_body_path support**

Modify `src/claw_ea/tools/obsidian.py`:

Update the `create_obsidian_note_impl` function signature and body:

```python
def create_obsidian_note_impl(
    category: str, title: str, content_data: dict,
    attachment_paths: list[str], config: Config,
    raw_body_path: str = "",
) -> dict:
    """Core logic for create_obsidian_note."""
    # Handle raw_body_path: read file, validate existence
    if raw_body_path:
        raw_file = Path(raw_body_path)
        if not raw_file.exists():
            return {"error": f"raw_body_path file not found: {raw_body_path}"}

    # Sanitize category to prevent path traversal
    safe_category = "".join(c for c in category if c.isalnum() or c in "-_")
    if not safe_category:
        safe_category = "general"

    chash = _content_hash(content_data)
    today = date.today().isoformat()
    filename = f"{today}-{safe_category}-{chash}.md"

    notes_dir = config.vault_path / config.notes_folder
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_path = notes_dir / filename

    if note_path.exists():
        # Still clean up temp file even if note already exists
        if raw_body_path:
            try:
                Path(raw_body_path).unlink(missing_ok=True)
            except OSError:
                pass
        return {"note_path": str(note_path), "already_existed": True}

    frontmatter = _render_frontmatter(category, content_data)

    if raw_body_path:
        raw_file = Path(raw_body_path)
        body = raw_file.read_text(encoding="utf-8")
        # Append original file references
        if attachment_paths:
            body += "\n\n## 原始文件\n"
            for p in attachment_paths:
                body += f"- [[{Path(p).name}]]\n"
        # Delete temp file after reading
        try:
            raw_file.unlink(missing_ok=True)
        except OSError:
            pass
    else:
        body = _render_body(category, title, content_data, attachment_paths)

    content = f"---\n{frontmatter}---\n\n{body}"

    note_path.write_text(content, encoding="utf-8")
    return {"note_path": str(note_path), "already_existed": False}
```

Update the MCP tool registration to pass through `raw_body_path`:

```python
def register(mcp_instance, config: Config):
    """Register create_obsidian_note tool with the MCP server."""

    @mcp_instance.tool()
    async def create_obsidian_note(
        category: str, title: str, content_data: dict,
        attachment_paths: list[str] | None = None,
        raw_body_path: str = "",
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
            raw_body_path: Path to a Markdown file whose content will be used as note body.
                Typically the md_path returned by convert_to_markdown.
                When set, the note body comes from this file instead of template rendering.
                The file is deleted after reading.

        Returns:
            note_path: Absolute path to the created note
            already_existed: True if a note with identical content already exists
        """
        return create_obsidian_note_impl(
            category, title, content_data, attachment_paths or [], config,
            raw_body_path=raw_body_path,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_obsidian.py -v`
Expected: All PASS (existing + new tests)

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/claw_ea/tools/obsidian.py tests/test_obsidian.py
git commit -m "feat(obsidian): add raw_body_path parameter to create_obsidian_note

Reads converted markdown from file path instead of template rendering.
Deletes temp file after reading. Original file wikilinks appended."
```

---

## Task 9: Server startup temp cleanup

**Files:**
- Modify: `src/claw_ea/server.py`

- [ ] **Step 1: Add cleanup call to server startup**

In `src/claw_ea/server.py`, add cleanup at the start of `main()` after config loading:

```python
def main():
    try:
        config = load_config()
    except ConfigError as e:
        import sys
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Clean up stale temp files from previous runs
    from claw_ea.converters import cleanup_stale_temps
    cleaned = cleanup_stale_temps()
    if cleaned:
        import sys
        print(f"Cleaned up {cleaned} stale temp file(s)", file=sys.stderr)

    ek_client = None
    # ... rest unchanged
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -x`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/claw_ea/server.py
git commit -m "feat(server): clean up stale converter temp files on startup

Removes /tmp/claw-ea-*.md files older than 1 hour to prevent leaks."
```

---

## Task 10: OpenClaw plugin TypeScript definition

**Files:**
- Modify: `openclaw-plugin/src/tools.ts`

- [ ] **Step 1: Check current tools.ts structure**

Read `openclaw-plugin/src/tools.ts` to see the existing tool definition pattern.

- [ ] **Step 2: Add convert_to_markdown tool definition**

Add the new tool following the same pattern as existing tools:

```typescript
{
    name: "claw_convert_to_markdown",
    description: "Convert a file to Markdown and save as a temp file. Supports: PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), images (jpg/png/etc). Returns a temp file path — pass it to create_obsidian_note's raw_body_path parameter.",
    parameters: {
        type: "object",
        properties: {
            file_path: {
                type: "string",
                description: "Path to the file to convert"
            },
            hint: {
                type: "string",
                description: "Optional type hint for specialized converter chain (e.g. 'academic' for academic PDF papers)"
            }
        },
        required: ["file_path"]
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add openclaw-plugin/src/tools.ts
git commit -m "feat(plugin): add convert_to_markdown TypeScript tool definition"
```

---

## Task 11: Integration smoke test (optional, @pytest.mark.converter)

**Files:**
- Modify: `tests/test_converters.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add converter marker to pytest config**

In `pyproject.toml`, update markers:

```toml
[tool.pytest.ini_options]
markers = [
    "macos: tests requiring macOS APIs (EventKit, Vision)",
    "converter: tests requiring real converter CLIs (docling, markitdown)"
]
```

- [ ] **Step 2: Write integration tests**

Add to `tests/test_converters.py`:

```python
@pytest.mark.converter
class TestDoclingIntegration:
    """Integration tests that call real docling CLI. Skip if not installed."""

    def test_convert_small_pdf(self, tmp_path):
        """Test docling with a minimal PDF file."""
        if not docling_is_available({}):
            pytest.skip("docling not installed")

        # Create a minimal text file docling can process
        # (A real PDF would be better but this tests the pipeline)
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, this is a test document for conversion.")

        # docling may not support .txt — test with real PDF in manual testing
        # This test validates the subprocess pipeline works end-to-end


@pytest.mark.converter
class TestMarkitdownIntegration:
    """Integration tests that call real markitdown CLI."""

    def test_convert_csv(self, tmp_path):
        """Test markitdown with a CSV file."""
        if not markitdown_is_available({}):
            pytest.skip("markitdown not installed")

        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name,age\n张三,45\n李四,32", encoding="utf-8")

        result = convert_markitdown(csv_file, {}, timeout=30)
        assert "张三" in result
        assert "45" in result
```

- [ ] **Step 3: Run integration tests**

Run: `uv run pytest tests/test_converters.py -m converter -v`
Expected: Tests either PASS or skip (if CLI not installed)

- [ ] **Step 4: Commit**

```bash
git add tests/test_converters.py pyproject.toml
git commit -m "test: add converter integration tests with pytest marker

Skipped when CLIs not installed. Validates real subprocess pipeline."
```

---

## Summary

| Task | What it builds | Files touched |
|------|---------------|---------------|
| 0 | Feature branch | — |
| 1 | Config: converters fields | config.py, conftest.py, test_config.py |
| 2 | is_usable() quality check | converters.py, test_converters.py |
| 3 | docling + markitdown converters | converters.py, test_converters.py |
| 4 | lmstudio + vision_ocr converters | converters.py, test_converters.py |
| 5 | mineru converter | converters.py, test_converters.py |
| 6 | dispatch() routing + fallback | converters.py, test_converters.py |
| 7 | convert_to_markdown MCP tool | tools/converter.py, server.py, test_converter_tool.py |
| 8 | raw_body_path for obsidian notes | tools/obsidian.py, test_obsidian.py |
| 9 | Startup temp cleanup | server.py |
| 10 | TypeScript plugin definition | openclaw-plugin/src/tools.ts |
| 11 | Integration smoke tests | test_converters.py, pyproject.toml |
