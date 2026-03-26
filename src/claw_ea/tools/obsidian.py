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
    for key in ("patient", "procedure", "surgeon", "datetime", "location",
                "meeting_title", "meeting_date", "attendees", "priority"):
        if key in content_data:
            fm[key] = content_data[key]

    fm["tags"] = [category]
    return yaml.dump(fm, default_flow_style=False, allow_unicode=True)


def _render_body(category: str, title: str, content_data: dict, attachment_paths: list[str]) -> str:
    """Generate Markdown body for the note."""
    lines = [f"# {title}", ""]

    if "summary" in content_data:
        lines.extend(["## 摘要", f"> {content_data['summary']}", ""])

    field_labels = {
        "patient": "患者", "procedure": "术式", "surgeon": "主刀",
        "datetime": "时间", "location": "地点",
        "meeting_title": "会议主题", "attendees": "参会人员",
        "meeting_date": "会议日期", "priority": "优先级",
    }
    detail_lines = []
    for key, label in field_labels.items():
        if key in content_data:
            detail_lines.append(f"- **{label}**：{content_data[key]}")
    if detail_lines:
        lines.extend(["## 详细信息"] + detail_lines + [""])

    if attachment_paths:
        lines.append("## 附件")
        for p in attachment_paths:
            filename = Path(p).name
            lines.append(f"- [[{filename}]]")
        lines.append("")

    lines.extend(["## 备注", "（待补充）", ""])
    return "\n".join(lines)


def create_obsidian_note_impl(
    category: str, title: str, content_data: dict,
    attachment_paths: list[str], config: Config,
    raw_body_path: str = "",
) -> dict:
    """Core logic for create_obsidian_note."""
    # Handle raw_body_path: validate file exists
    if raw_body_path:
        raw_file = Path(raw_body_path)
        if not raw_file.exists():
            return {"error": f"raw_body_path file not found: {raw_body_path}"}

    # Sanitize category to prevent path traversal
    safe_category = "".join(c for c in category if c.isalnum() or c in "-_")
    if not safe_category:
        safe_category = "general"

    chash = _content_hash(content_data)
    # Mix in raw_body content hash so different conversions aren't deduped
    if raw_body_path:
        raw_file = Path(raw_body_path)
        if raw_file.exists():
            body_hash = hashlib.sha256(raw_file.read_bytes()).hexdigest()[:8]
            chash = hashlib.sha256(f"{chash}{body_hash}".encode()).hexdigest()[:8]
    today = date.today().isoformat()
    filename = f"{today}-{safe_category}-{chash}.md"

    notes_dir = config.vault_path / config.notes_folder
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_path = notes_dir / filename

    if note_path.exists():
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
