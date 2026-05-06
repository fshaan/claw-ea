import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from claw_ea.config import Config

# §4.1 claw-ea category → qp type 映射表
_TYPE_FROM_CATEGORY: dict[str, str] = {
    "meeting": "meeting_minutes",
    "surgery": "document",
    "task": "document",
    "document": "document",
    "raw_thought": "idea",
    "review": "review",
}


def _compute_dedup_hash(raw_body_path: str, attachment_paths: list[str]) -> str:
    """SHA256 of raw body content + sorted attachment paths, first 8 hex chars."""
    if raw_body_path:
        body_bytes = Path(raw_body_path).read_bytes()
        body_hash = hashlib.sha256(body_bytes).hexdigest()
    else:
        body_hash = ""
    att_hashes = sorted(
        hashlib.sha256(p.encode("utf-8")).hexdigest() for p in attachment_paths
    )
    combined = f"{body_hash}{''.join(att_hashes)}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:8]


def _compute_legacy_hash(content_data: dict) -> str:
    """SHA256 of sorted content_data JSON, first 8 hex chars.
    Used only when raw_body_path is empty (backward compat)."""
    canonical = json.dumps(content_data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]


def _render_frontmatter(
    category: str,
    title: str,
    content_data: dict,
    *,
    type: str = "",
    source_channel: str = "",
    source_message_id: str = "",
    message_ts: str = "",
    project: str = "",
    related_event_id: str = "",
    related_reminder_id: str = "",
    attachment_paths: list[str] | None = None,
    idea_stage: str = "",
    idea_topics: list[str] | None = None,
    tags: list[str] | None = None,
) -> str:
    """Generate YAML frontmatter per §4 Capture-First v2 schema."""
    qp_type = type or _TYPE_FROM_CATEGORY.get(category, "document")
    ingested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    fm: dict[str, Any] = {
        "source": "claw-ea",
        "type": qp_type,
        "category": category,
        "title": title,
        "status": "inbox",
        "ingested_at": ingested_at,
        "processed_by_ai": False,
    }

    if source_channel:
        fm["source_channel"] = source_channel
    if source_message_id:
        fm["source_message_id"] = source_message_id
    if message_ts:
        fm["message_ts"] = message_ts
    if project:
        fm["project"] = project
    if related_event_id:
        fm["related_event_id"] = related_event_id
    if related_reminder_id:
        fm["related_reminder_id"] = related_reminder_id

    # Legacy content_data fields preserved for backward compat
    for key in ("patient", "procedure", "surgeon", "datetime", "location",
                "meeting_title", "meeting_date", "attendees", "priority"):
        if key in content_data:
            fm[key] = content_data[key]

    if idea_stage or qp_type == "idea":
        fm["idea_stage"] = idea_stage or "raw"
    if idea_topics:
        fm["idea_topics"] = idea_topics

    fm["tags"] = tags or [category]

    if attachment_paths:
        fm["attachments"] = [Path(p).name for p in attachment_paths]

    return yaml.dump(fm, default_flow_style=False, allow_unicode=True)


def _render_verbatim_header(converter_used: str, attachment_paths: list[str]) -> str:
    """Render converter metadata header block (§5.2 template)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    lines = []
    if attachment_paths:
        lines.append("> **原始文件**：")
        for p in attachment_paths:
            lines.append(f"> - [[{Path(p).name}]]")
    if converter_used:
        lines.append(f"> **转换工具**：{converter_used}")
    lines.append(f"> **转换时间**：{now}")
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def _render_idea_body(original_text: str) -> str:
    """Render dual-section idea body (§5.3 template)."""
    lines = [
        "## 原始想法（用户原文，AI 不得修改）",
        "",
        f"> {original_text}",
        "",
        "---",
        "",
        "## AI 调研补充",
        "> 生成时间：（待异步调研）",
        "> 信息来源：web_search + 本地知识库",
        "> ⚠️ 仅供参考，可能含错误",
        "",
        "### 相关概念",
        "（待补充）",
        "",
        "### 已有研究",
        "（待补充）",
        "",
        "### 可能延伸方向",
        "（待补充）",
        "",
    ]
    return "\n".join(lines)


def _render_body(category: str, title: str, content_data: dict, attachment_paths: list[str]) -> str:
    """Generate Markdown body from template (backward compat — used when raw_body_path is empty)."""
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
    *,
    type: str = "",
    source_channel: str = "",
    source_message_id: str = "",
    message_ts: str = "",
    project: str = "",
    related_event_id: str = "",
    related_reminder_id: str = "",
    converter_used: str = "",
    idea_stage: str = "",
    idea_topics: list[str] | None = None,
) -> dict:
    """Core logic for create_obsidian_note."""
    if raw_body_path:
        raw_file = Path(raw_body_path)
        if not raw_file.exists():
            return {"error": f"raw_body_path file not found: {raw_body_path}"}

    safe_category = "".join(c for c in category if c.isalnum() or c in "-_")
    if not safe_category:
        safe_category = "general"

    qp_type = type or _TYPE_FROM_CATEGORY.get(category, "document")

    if raw_body_path:
        chash = _compute_dedup_hash(raw_body_path, attachment_paths)
    else:
        chash = _compute_legacy_hash(content_data)

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

    frontmatter = _render_frontmatter(
        category, title, content_data,
        type=type,
        source_channel=source_channel,
        source_message_id=source_message_id,
        message_ts=message_ts,
        project=project,
        related_event_id=related_event_id,
        related_reminder_id=related_reminder_id,
        attachment_paths=attachment_paths,
        idea_stage=idea_stage,
        idea_topics=idea_topics,
    )

    if raw_body_path:
        raw_file = Path(raw_body_path)
        body_content = raw_file.read_text(encoding="utf-8")

        if qp_type == "idea":
            body = _render_idea_body(body_content.strip())
        else:
            header = _render_verbatim_header(converter_used, attachment_paths)
            body = f"{header}{body_content}"

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
        type: str = "",
        source_channel: str = "",
        source_message_id: str = "",
        message_ts: str = "",
        project: str = "",
        related_event_id: str = "",
        related_reminder_id: str = "",
        converter_used: str = "",
        idea_stage: str = "",
        idea_topics: list[str] | None = None,
    ) -> dict:
        """Create an Obsidian note with Capture-First v2 frontmatter and dedup.

        IMPORTANT: raw_body_path MUST be the md_path from convert_to_markdown
        for all file-based messages. Never skip the conversion step.
        Do NOT create notes for surgery category — use create_calendar_event only.

        Args:
            category: claw-ea business subtype. One of: surgery, meeting, task, document,
                      raw_thought, review.
            title: Note title (auto-generated from message first line, max 30 chars).
            content_data: Legacy structured data for frontmatter enrichment
                          (patient, procedure, surgeon, etc.). Prefer passing
                          individual keyword args in v2.
            attachment_paths: Absolute paths to saved attachment files.
            raw_body_path: Path to converted Markdown file. Its content becomes
                           the note body (verbatim). Always use this for file-based
                           messages. The temp file is deleted after reading.
            type: qp namespace type. Derived from category if omitted.
                  One of: meeting_minutes, document, idea, review, writing.
            source_channel: feishu, wecom, telegram, or tui.
            source_message_id: Channel-native message ID for dedup and traceability.
            message_ts: Original message timestamp (ISO 8601).
            project: Obsidian wikilink to project, e.g. "[[项目名]]".
            related_event_id: Apple Calendar event ID for back-reference.
            related_reminder_id: Apple Reminder ID for back-reference.
            converter_used: Name of converter that produced raw_body_path content.
            idea_stage: Only for type=idea. One of: raw, enriched, framed.
            idea_topics: Only for type=idea. Research dimensions for retrieval.

        Returns:
            note_path: Absolute path to the created note.
            already_existed: True if a note with identical content already exists.
        """
        return create_obsidian_note_impl(
            category, title, content_data, attachment_paths or [], config,
            raw_body_path=raw_body_path,
            type=type,
            source_channel=source_channel,
            source_message_id=source_message_id,
            message_ts=message_ts,
            project=project,
            related_event_id=related_event_id,
            related_reminder_id=related_reminder_id,
            converter_used=converter_used,
            idea_stage=idea_stage,
            idea_topics=idea_topics,
        )
