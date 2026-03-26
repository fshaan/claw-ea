"""Markdown-first content pipeline: converter dispatch, routing, and quality check."""

import base64
import json
import logging
import os
import shutil
import signal
import subprocess
import tempfile
import unicodedata
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from claw_ea.tools.ocr import _run_ocr, VISION_AVAILABLE
except ImportError:
    VISION_AVAILABLE = False

    def _run_ocr(image_data: bytes) -> str:
        raise RuntimeError("Vision framework not available")


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
            process_group=0,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_group(proc.pid)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            raise TimeoutError(f"docling timed out after {timeout}s on {file_path}")

        if proc.returncode != 0:
            stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            raise RuntimeError(f"docling failed (exit {proc.returncode}): {stderr[:500]}")

        stem = file_path.stem
        md_path = Path(out_dir) / f"{stem}.md"
        if not md_path.exists():
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
        process_group=0,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_group(proc.pid)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        raise TimeoutError(f"markitdown timed out after {timeout}s on {file_path}")

    if proc.returncode != 0:
        raise RuntimeError(f"markitdown failed (exit {proc.returncode}): {stderr.decode('utf-8', errors='replace')[:500]}")

    return stdout.decode("utf-8")


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
    mime_type = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
        "bmp": "image/bmp", "tiff": "image/tiff", "webp": "image/webp",
    }.get(suffix, "image/png")

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
            process_group=0,
        )
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_group(proc.pid)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            raise TimeoutError(f"magic-pdf timed out after {timeout}s on {file_path}")

        if proc.returncode != 0:
            stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            raise RuntimeError(f"magic-pdf failed (exit {proc.returncode}): {stderr[:500]}")

        stem = file_path.stem
        md_path = Path(out_dir) / stem / "auto" / f"{stem}.md"
        if not md_path.exists():
            md_files = list(Path(out_dir).rglob("*.md"))
            if not md_files:
                raise RuntimeError(f"magic-pdf produced no .md output for {file_path}")
            md_path = md_files[0]

        return md_path.read_text(encoding="utf-8")


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


# --- dispatch and routing ---

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp", ".gif"}

DEFAULT_ROUTING: dict[str, dict[str, list[str]]] = {
    ".pdf":  {"default": ["docling"]},
    ".docx": {"default": ["docling", "markitdown"]},
    ".pptx": {"default": ["docling", "markitdown"]},
    ".xlsx": {"default": ["docling", "markitdown"]},
    ".csv":  {"default": ["markitdown"]},
    ".html": {"default": ["docling", "markitdown"]},
}
for _ext in _IMAGE_EXTENSIONS:
    DEFAULT_ROUTING[_ext] = {"default": ["lmstudio", "docling", "vision_ocr"]}


def _get_available_check(name: str, config) -> bool:
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


def _run_converter(name: str, file_path: Path, config, timeout: int = 60) -> str:
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


def _write_temp(content: str) -> str:
    """Write content to a temp file. Returns path string."""
    temp_dir = Path(tempfile.gettempdir())
    temp_path = temp_dir / f"claw-ea-{uuid.uuid4().hex[:12]}.md"
    temp_path.write_text(content, encoding="utf-8")
    return str(temp_path)


def dispatch(file_path: Path, config, hint: str = "") -> ConversionResult:
    """Route file to converter chain, try each with fallback.

    1. Look up chain by extension + hint
    2. Filter out unavailable converters
    3. Try each: convert → is_usable → return or fallback
    4. All fail → return longest result + warning
    """
    ext = file_path.suffix.lower()

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

    available = [name for name in chain if _get_available_check(name, config)]
    if not available:
        raise RuntimeError(f"No converters available for {ext} (chain: {chain})")

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
            fallback_used = True
            tried_one = True
            continue

        tried_one = True
        if is_usable(md):
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

    logger.warning("All converters failed for %s, returning best effort (%s)", file_path, best_converter)
    temp_path = _write_temp(best_result) if best_result else _write_temp(f"[Conversion failed for {file_path.name}]")
    return ConversionResult(
        temp_path=temp_path,
        source_path=str(file_path),
        converter_used=best_converter,
        fallback_used=True,
    )


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
