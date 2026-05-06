#!/usr/bin/env python3
"""One-shot migration: tag near-empty legacy notes and move them to _legacy/.

Scans the Obsidian inbox folder (from ~/.claw-ea/config.yaml) for .md files.
A note is considered "legacy" (v1 LLM-extraction failure) when:
  1. Body (excluding frontmatter, after stripping markdown syntax) < 50 chars
  2. No attachments (attachments field missing or empty in frontmatter)

Action (--apply):
  - Adds frontmatter fields: legacy: true, legacy_reason: empty_body
  - Moves file to <notes_folder>/_legacy/

Dry-run by default; pass --apply to execute.

Usage:
  uv run python scripts/migrate_legacy_inbox.py          # dry-run
  uv run python scripts/migrate_legacy_inbox.py --apply  # execute
  uv run python scripts/migrate_legacy_inbox.py --help

Per Q7 resolution (docs/design/2026-04-30-capture-first-redesign.md).
"""

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

LEGACY_BODY_MIN_CHARS = 50

# Markdown patterns to strip before measuring body length
_MD_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_MD_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_MD_WIKILINK = re.compile(r"\[\[.*?\]\]")
_MD_BLOCKQUOTE = re.compile(r"^>\s?", re.MULTILINE)
_MD_LINK = re.compile(r"\[.*?\]\(.*?\)")
_MD_BOLD_ITALIC = re.compile(r"\*{1,3}[^*]+\*{1,3}")


def load_config() -> dict[str, Any]:
    config_path = Path.home() / ".claw-ea" / "config.yaml"
    if not config_path.exists():
        print(f"Error: config not found at {config_path}", file=sys.stderr)
        sys.exit(1)
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def parse_note(content: str) -> tuple[dict[str, Any], str, str]:
    """Parse a .md file into (frontmatter_dict, frontmatter_raw, body)."""
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, "", content
    fm_raw = parts[1]
    body = parts[2]
    try:
        fm = yaml.safe_load(fm_raw) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, fm_raw, body


def strip_markdown(text: str) -> str:
    """Strip markdown syntax to measure 'real' content length."""
    t = _MD_COMMENT.sub("", text)
    t = _MD_HEADING.sub("", t)
    t = _MD_WIKILINK.sub("", t)
    t = _MD_BLOCKQUOTE.sub("", t)
    t = _MD_LINK.sub("", t)
    t = _MD_BOLD_ITALIC.sub("", t)
    t = t.replace("---", "").replace("`", "")
    return t.strip()


def has_attachments(fm: dict[str, Any]) -> bool:
    val = fm.get("attachments")
    return isinstance(val, list) and len(val) > 0


def is_legacy(fm: dict[str, Any], body: str) -> tuple[bool, str]:
    """Check if a note meets legacy criteria. Returns (is_legacy, reason)."""
    cleaned = strip_markdown(body)
    if len(cleaned) >= LEGACY_BODY_MIN_CHARS:
        return False, ""
    if has_attachments(fm):
        return False, ""
    if cleaned:
        return True, f"empty_body ({len(cleaned)} chars)"
    return True, "empty_body (0 chars)"


def migrate_file(
    file_path: Path,
    legacy_dir: Path,
    *,
    apply: bool = False,
) -> str:
    """Process one .md file. Returns status: 'skip', 'migrate', or 'error'."""
    content = file_path.read_text(encoding="utf-8")
    fm, fm_raw, body = parse_note(content)

    legacy, reason = is_legacy(fm, body)
    if not legacy:
        return "skip"

    if not apply:
        return f"migrate (dry-run): {reason}"

    # Add legacy fields to frontmatter
    fm["legacy"] = True
    fm["legacy_reason"] = reason
    new_fm = yaml.dump(fm, default_flow_style=False, allow_unicode=True)
    new_content = f"---\n{new_fm}---\n{body}"

    legacy_dir.mkdir(parents=True, exist_ok=True)
    dest = legacy_dir / file_path.name

    # If dest exists, add suffix to avoid overwrite
    if dest.exists():
        stem = file_path.stem
        dest = legacy_dir / f"{stem}_dup{file_path.suffix}"

    try:
        file_path.write_text(new_content, encoding="utf-8")
        shutil.move(str(file_path), str(dest))
    except OSError as e:
        return f"error: {e}"

    return f"migrated -> {dest.relative_to(legacy_dir.parent)}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tag and move legacy (near-empty) notes from inbox to _legacy/.",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Execute migration (default: dry-run only)",
    )
    args = parser.parse_args()

    config = load_config()
    vault_path = Path(config["obsidian"]["vault_path"]).expanduser()
    notes_folder = config["obsidian"]["notes_folder"]
    inbox_dir = vault_path / notes_folder

    if not inbox_dir.is_dir():
        print(f"Error: inbox directory not found: {inbox_dir}", file=sys.stderr)
        sys.exit(1)

    legacy_dir = inbox_dir / "_legacy"
    md_files = sorted(inbox_dir.glob("*.md"))

    if not md_files:
        print(f"No .md files found in {inbox_dir}")
        return

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== {mode}: scanning {inbox_dir} ===")
    print(f"  {len(md_files)} .md files found\n")

    results: dict[str, list[str]] = {"skip": [], "migrate": [], "error": []}

    for f in md_files:
        status = migrate_file(f, legacy_dir, apply=args.apply)
        if status.startswith("migrate") or status.startswith("migrated"):
            results["migrate"].append(f"{f.name} — {status}")
        elif status.startswith("error"):
            results["error"].append(f"{f.name} — {status}")
        else:
            results["skip"].append(f.name)

    # Report
    skipped = len(results["skip"])
    migrated = len(results["migrate"])
    errors = len(results["error"])

    print(f"Results: {skipped} skipped, {migrated} legacy, {errors} errors\n")

    if results["migrate"]:
        print("Legacy notes:")
        for entry in results["migrate"]:
            print(f"  {entry}")
        print()

    if results["error"]:
        print("Errors:")
        for entry in results["error"]:
            print(f"  {entry}")
        print()

    if not args.apply and migrated > 0:
        print(f"Dry-run complete. {migrated} file(s) would be migrated.")
        print("Run with --apply to execute.")


if __name__ == "__main__":
    main()
