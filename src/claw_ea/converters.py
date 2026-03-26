"""Markdown-first content pipeline: converter dispatch, routing, and quality check."""

import os
import shutil
import signal
import subprocess
import tempfile
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
            preexec_fn=os.setsid,
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
