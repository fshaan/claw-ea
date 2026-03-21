import base64
import pytest
from pathlib import Path
from claw_ea.tools.attachment import save_attachment_impl


# --- base64 mode (existing tests, updated call signature) ---

def test_save_basic_file(mock_config):
    content = base64.b64encode(b"hello world").decode()
    result = save_attachment_impl(mock_config, file_content=content, filename="test.txt")
    assert result["already_existed"] is False
    saved = Path(result["saved_path"])
    assert saved.exists()
    assert saved.read_bytes() == b"hello world"


def test_save_creates_date_subdirectory(mock_config):
    content = base64.b64encode(b"data").decode()
    result = save_attachment_impl(mock_config, file_content=content, filename="file.pdf")
    parts = Path(result["saved_path"]).relative_to(mock_config.attachments_path).parts
    assert len(parts) == 4  # YYYY/MM/DD/filename


def test_save_duplicate_skips(mock_config):
    content = base64.b64encode(b"same content").decode()
    r1 = save_attachment_impl(mock_config, file_content=content, filename="dup.txt")
    r2 = save_attachment_impl(mock_config, file_content=content, filename="dup.txt")
    assert r1["saved_path"] == r2["saved_path"]
    assert r2["already_existed"] is True


def test_save_same_name_different_content(mock_config):
    c1 = base64.b64encode(b"content A").decode()
    c2 = base64.b64encode(b"content B").decode()
    r1 = save_attachment_impl(mock_config, file_content=c1, filename="file.txt")
    r2 = save_attachment_impl(mock_config, file_content=c2, filename="file.txt")
    assert r1["saved_path"] != r2["saved_path"]
    assert "file_1.txt" in r2["saved_path"]


def test_save_chinese_filename(mock_config):
    content = base64.b64encode(b"data").decode()
    result = save_attachment_impl(mock_config, file_content=content, filename="手术通知_张三.pdf")
    assert "手术通知_张三.pdf" in result["saved_path"]


def test_save_invalid_base64(mock_config):
    with pytest.raises(ValueError, match="base64"):
        save_attachment_impl(mock_config, file_content="not-valid-base64!!!", filename="file.txt")


# --- file_path mode (new tests) ---

def test_save_from_file_path(mock_config, tmp_path):
    source = tmp_path / "source" / "report.pdf"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"PDF content here")

    result = save_attachment_impl(mock_config, file_path=str(source))
    assert result["already_existed"] is False
    saved = Path(result["saved_path"])
    assert saved.exists()
    assert saved.read_bytes() == b"PDF content here"
    assert "report.pdf" in result["saved_path"]


def test_file_path_derives_filename(mock_config, tmp_path):
    source = tmp_path / "source" / "手术排班表.xlsx"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"excel data")

    result = save_attachment_impl(mock_config, file_path=str(source))
    assert "手术排班表.xlsx" in result["saved_path"]


def test_file_path_with_explicit_filename(mock_config, tmp_path):
    source = tmp_path / "source" / "temp_download_12345"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"data")

    result = save_attachment_impl(mock_config, file_path=str(source), filename="会议纪要.docx")
    assert "会议纪要.docx" in result["saved_path"]


def test_file_path_not_found(mock_config):
    with pytest.raises(ValueError, match="not found"):
        save_attachment_impl(mock_config, file_path="/nonexistent/path/file.txt")


def test_file_path_and_content_exclusive(mock_config, tmp_path):
    source = tmp_path / "source" / "file.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"data")
    content = base64.b64encode(b"data").decode()

    with pytest.raises(ValueError, match="mutually exclusive"):
        save_attachment_impl(mock_config, file_content=content, filename="file.txt", file_path=str(source))


def test_neither_provided(mock_config):
    with pytest.raises(ValueError, match="Either"):
        save_attachment_impl(mock_config)


def test_file_path_dedup(mock_config, tmp_path):
    source = tmp_path / "source" / "same.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"identical content")

    r1 = save_attachment_impl(mock_config, file_path=str(source))
    r2 = save_attachment_impl(mock_config, file_path=str(source))
    assert r1["saved_path"] == r2["saved_path"]
    assert r2["already_existed"] is True
