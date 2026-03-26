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
    assert "[[手术通知.pdf]]" in content
    assert "[[会议纪要.docx]]" in content


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
    assert fm["category"] == "general"


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
