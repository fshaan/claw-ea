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
    assert "type: document" in content       # §4: surgery → document
    assert "category: surgery" in content    # claw-ea subtype preserved
    assert "source: claw-ea" in content      # §4: source marker
    assert "status: inbox" in content        # §4: lifecycle
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
    assert "type: meeting_minutes" in content  # §4: meeting → meeting_minutes
    assert "category: meeting" in content


def test_note_with_attachment_links(mock_config):
    data = {"title": "文件归档", "summary": "收到文件"}
    paths = ["/path/to/手术通知.pdf", "/path/to/会议纪要.docx"]
    result = create_obsidian_note_impl("document", data["title"], data, paths, mock_config)
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    # PDF embeds (rendered inline); docx links (Obsidian can't render it inline)
    assert "![[手术通知.pdf]]" in content
    assert "[[会议纪要.docx]]" in content
    assert "![[会议纪要.docx]]" not in content


def test_image_attachment_uses_embed_syntax(mock_config):
    """图片附件用 ![[file]] 嵌入,在笔记中直接渲染展示。"""
    data = {"title": "现场照片", "summary": "AI 视觉归纳的核心内容"}
    paths = ["/path/to/术野照片.png"]
    result = create_obsidian_note_impl("document", data["title"], data, paths, mock_config)
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    assert "![[术野照片.png]]" in content


def test_office_attachment_uses_link_syntax(mock_config):
    """非图片/PDF 附件(docx/xlsx)用 [[file]] 链接,不嵌入。"""
    data = {"title": "报表归档", "summary": "转换后正文已入正文区"}
    paths = ["/path/to/季度报表.xlsx"]
    result = create_obsidian_note_impl("document", data["title"], data, paths, mock_config)
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    assert "[[季度报表.xlsx]]" in content
    assert "![[季度报表.xlsx]]" not in content


def test_verbatim_header_image_attachment_embeds(mock_config, tmp_path):
    """raw_body_path 路径下,原始文件块中的图片也用 ![[file]] 嵌入展示。"""
    md_file = tmp_path / "out.md"
    md_file.write_text("正文内容", encoding="utf-8")
    result = create_obsidian_note_impl(
        "document", "图文笔记", {"title": "图文笔记"},
        ["/path/to/扫描件.png", "/path/to/附表.docx"],
        mock_config,
        raw_body_path=str(md_file),
        converter_used="mineru",
    )
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    assert "![[扫描件.png]]" in content        # 图片嵌入
    assert "[[附表.docx]]" in content           # docx 链接
    assert "![[附表.docx]]" not in content      # docx 不嵌入


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
    parts = content.split("---")
    assert len(parts) >= 3
    fm = yaml.safe_load(parts[1])
    assert fm["source"] == "claw-ea"
    assert fm["type"] == "document"       # general → document (fallback)
    assert fm["category"] == "general"
    assert fm["status"] == "inbox"
    assert "ingested_at" in fm
    assert fm["processed_by_ai"] is False


def test_note_path_in_configured_folder(mock_config):
    data = {"title": "test", "summary": "hello"}
    result = create_obsidian_note_impl("general", "test", data, [], mock_config)
    note = Path(result["note_path"])
    assert str(mock_config.vault_path / mock_config.notes_folder) in str(note.parent)


def test_raw_body_path_creates_note_with_file_content(mock_config, tmp_path):
    """raw_body_path reads content from file and uses it as note body."""
    md_file = tmp_path / "converted.md"
    md_file.write_text("# Converted Content\n\nThis is the converted markdown.", encoding="utf-8")

    data = {"title": "test doc", "summary": "converted"}
    result = create_obsidian_note_impl(
        "document", "test doc", data, ["/path/to/original.pdf"], mock_config,
        raw_body_path=str(md_file),
        converter_used="mineru",
    )
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    # Verbatim header
    assert "> **原始文件**" in content
    assert "> **转换工具**：mineru" in content
    assert "> **转换时间**" in content
    # Original content preserved
    assert "# Converted Content" in content
    assert "This is the converted markdown." in content
    # Frontmatter
    assert "type: document" in content
    assert "source: claw-ea" in content


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


# --- PR-3 new tests ---

def test_verbatim_mode_with_converter_header(mock_config, tmp_path):
    """raw_body_path + converter_used → verbatim body with header block (§5.2)."""
    md_file = tmp_path / "output.md"
    md_file.write_text("# Full Paper\n\n## Abstract\n\nSignificant findings.", encoding="utf-8")

    result = create_obsidian_note_impl(
        "document", "Paper", {"title": "Paper"}, [],
        mock_config,
        raw_body_path=str(md_file),
        converter_used="mineru",
    )
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    # Header block
    assert "> **转换工具**：mineru" in content
    assert "> **转换时间**" in content
    assert "---" in content
    # Original content verbatim
    assert "# Full Paper" in content
    assert "Significant findings" in content
    # No template rendering
    assert "## 备注" not in content


def test_idea_dual_section_structure(mock_config, tmp_path):
    """type=idea + raw_body_path → dual-section body (§5.3)."""
    idea_text = "今天看到一篇关于 X 的论文，觉得 Y 方向有意思"
    md_file = tmp_path / "idea.md"
    md_file.write_text(idea_text, encoding="utf-8")

    result = create_obsidian_note_impl(
        "raw_thought", "研究方向", {"title": "研究方向"}, [],
        mock_config,
        raw_body_path=str(md_file),
        type="idea",
        idea_stage="raw",
        idea_topics=["agent-design", "obsidian"],
    )
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    # Dual sections
    assert "## 原始想法（用户原文，AI 不得修改）" in content
    assert f"> {idea_text}" in content
    assert "## AI 调研补充" in content
    # Frontmatter
    assert "type: idea" in content
    assert "category: raw_thought" in content
    assert "idea_stage: raw" in content
    assert "agent-design" in content
    assert "obsidian" in content


def test_dedup_by_raw_body(mock_config, tmp_path):
    """Same raw body + same attachments → same hash → dedup."""
    md1 = tmp_path / "output1.md"
    md1.write_text("# Same content", encoding="utf-8")
    md2 = tmp_path / "output2.md"
    md2.write_text("# Same content", encoding="utf-8")  # identical content, different path

    r1 = create_obsidian_note_impl(
        "document", "test", {"title": "test"}, ["/p/a.pdf"], mock_config,
        raw_body_path=str(md1),
    )
    r2 = create_obsidian_note_impl(
        "document", "test", {"title": "test"}, ["/p/a.pdf"], mock_config,
        raw_body_path=str(md2),
    )
    assert r1["note_path"] == r2["note_path"]
    assert r2["already_existed"] is True


def test_dedup_different_raw_body_different_hash(mock_config, tmp_path):
    """Different raw body → different hash → new note."""
    md1 = tmp_path / "output1.md"
    md1.write_text("# Content A", encoding="utf-8")
    md2 = tmp_path / "output2.md"
    md2.write_text("# Content B", encoding="utf-8")

    r1 = create_obsidian_note_impl(
        "document", "test", {"title": "test"}, [], mock_config,
        raw_body_path=str(md1),
    )
    r2 = create_obsidian_note_impl(
        "document", "test", {"title": "test"}, [], mock_config,
        raw_body_path=str(md2),
    )
    assert r1["note_path"] != r2["note_path"]


def test_idea_type_auto_derived_from_raw_thought(mock_config, tmp_path):
    """When type is omitted, raw_thought → type=idea per §4.1 mapping."""
    md_file = tmp_path / "idea.md"
    md_file.write_text("some thought", encoding="utf-8")

    result = create_obsidian_note_impl(
        "raw_thought", "idea title", {"title": "idea title"}, [],
        mock_config,
        raw_body_path=str(md_file),
    )
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    assert "type: idea" in content
    assert "## 原始想法" in content


def test_meeting_type_auto_derived_from_meeting(mock_config):
    """When type is omitted, meeting → type=meeting_minutes per §4.1 mapping."""
    result = create_obsidian_note_impl(
        "meeting", "test meeting", {"title": "test"}, [], mock_config,
    )
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    assert "type: meeting_minutes" in content


def test_frontmatter_includes_optional_fields(mock_config, tmp_path):
    """All optional §4 fields render correctly when provided."""
    md_file = tmp_path / "test.md"
    md_file.write_text("# test content", encoding="utf-8")

    result = create_obsidian_note_impl(
        "document", "Test Note", {"title": "test"}, ["/p/doc.pdf"],
        mock_config,
        raw_body_path=str(md_file),
        type="document",
        source_channel="feishu",
        source_message_id="msg-12345",
        message_ts="2026-05-06T10:30:00",
        project="[[Research]]",
        related_event_id="E:abc123",
        related_reminder_id="R:def456",
        converter_used="mineru",
    )
    content = Path(result["note_path"]).read_text(encoding="utf-8")
    assert "source_channel: feishu" in content
    assert "source_message_id: msg-12345" in content
    assert "message_ts: '2026-05-06T10:30:00'" in content
    assert "project: '[[Research]]'" in content
    assert "related_event_id: E:abc123" in content
    assert "related_reminder_id: R:def456" in content
