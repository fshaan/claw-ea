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
