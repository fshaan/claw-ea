import base64
from pathlib import Path
from claw_ea.tools.attachment import save_attachment_impl
from claw_ea.tools.obsidian import create_obsidian_note_impl


def test_end_to_end_attachment_then_note(mock_config):
    """Save an attachment, then create a note linking to it."""
    # Save attachment
    content = base64.b64encode(b"PDF content here").decode()
    att_result = save_attachment_impl(mock_config, file_content=content, filename="手术通知.pdf")
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
