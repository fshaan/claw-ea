import json
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest
from claw_ea.converters import is_usable
from claw_ea.converters import (
    docling_is_available, convert_docling,
    markitdown_is_available, convert_markitdown,
)
from claw_ea.converters import (
    lmstudio_is_available, convert_lmstudio,
    vision_ocr_is_available, convert_vision_ocr,
)
from claw_ea.converters import mineru_is_available, convert_mineru


class TestIsUsable:
    def test_empty_string(self):
        assert is_usable("") is False

    def test_whitespace_only(self):
        assert is_usable("   \n\t  \n") is False

    def test_normal_markdown(self):
        assert is_usable("# Hello\n\nThis is a test document.") is True

    def test_chinese_text(self):
        assert is_usable("# 手术通知\n\n患者张三，腹腔镜胆囊切除术") is True

    def test_garbled_mostly_control_chars(self):
        garbled = "\x00\x01\x02\x03\x04" * 10 + "hello"
        assert is_usable(garbled) is False

    def test_just_above_threshold(self):
        valid = "a" * 80
        invalid = "\x00" * 20
        assert is_usable(valid + invalid) is True

    def test_just_below_threshold(self):
        valid = "a" * 79
        invalid = "\x00" * 21
        assert is_usable(valid + invalid) is False

    def test_newlines_not_counted(self):
        assert is_usable("hello\n\n\n\n\nworld") is True


class TestDocling:
    @patch("shutil.which", return_value="/usr/local/bin/docling")
    def test_is_available_when_on_path(self, mock_which):
        assert docling_is_available({}) is True

    @patch("shutil.which", return_value=None)
    def test_is_available_with_config_path(self, mock_which):
        assert docling_is_available({"docling": "/custom/bin/docling"}) is True

    @patch("shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        assert docling_is_available({}) is False

    @patch("subprocess.Popen")
    @patch("shutil.which", return_value="/usr/local/bin/docling")
    def test_convert_success(self, mock_which, mock_popen, tmp_path):
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake pdf")

        process = MagicMock()
        process.wait.return_value = 0
        process.returncode = 0
        process.pid = 12345
        mock_popen.return_value = process

        def simulate_output(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            for i, arg in enumerate(cmd):
                if arg == "--output":
                    out_dir = Path(cmd[i + 1])
                    out_dir.mkdir(parents=True, exist_ok=True)
                    (out_dir / "test.md").write_text("# Converted\n\nHello world")
                    break
            return process

        mock_popen.side_effect = simulate_output
        result = convert_docling(input_file, {}, timeout=60)
        assert "# Converted" in result
        assert "Hello world" in result

    @patch("subprocess.Popen")
    @patch("shutil.which", return_value="/usr/local/bin/docling")
    def test_convert_timeout(self, mock_which, mock_popen, tmp_path):
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake pdf")

        process = MagicMock()
        process.wait.side_effect = subprocess.TimeoutExpired(cmd="docling", timeout=60)
        process.pid = 12345
        mock_popen.return_value = process

        with pytest.raises(TimeoutError):
            convert_docling(input_file, {}, timeout=60)


class TestMarkitdown:
    @patch("shutil.which", return_value="/usr/local/bin/markitdown")
    def test_is_available_when_on_path(self, mock_which):
        assert markitdown_is_available({}) is True

    @patch("shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        assert markitdown_is_available({}) is False

    @patch("subprocess.Popen")
    @patch("shutil.which", return_value="/usr/local/bin/markitdown")
    def test_convert_success(self, mock_which, mock_popen, tmp_path):
        input_file = tmp_path / "test.docx"
        input_file.write_text("fake docx")

        process = MagicMock()
        process.communicate.return_value = (b"# Converted from docx\n\nContent here", b"")
        process.returncode = 0
        process.pid = 12345
        mock_popen.return_value = process

        result = convert_markitdown(input_file, {}, timeout=60)
        assert "# Converted from docx" in result


class TestLmstudio:
    def test_is_available_with_endpoint(self):
        assert lmstudio_is_available("http://localhost:1234/v1") is True

    def test_not_available_empty_endpoint(self):
        assert lmstudio_is_available("") is False

    @patch("urllib.request.urlopen")
    def test_convert_success(self, mock_urlopen, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        response_data = {
            "choices": [{"message": {"content": "# OCR Result\n\n手术通知：张三"}}]
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(response_data).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = convert_lmstudio(
            img, endpoint="http://localhost:1234/v1",
            api_key="test", model="glm-ocr", timeout=120
        )
        assert "手术通知" in result

    @patch("urllib.request.urlopen")
    def test_convert_connection_error(self, mock_urlopen, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")

        mock_urlopen.side_effect = ConnectionError("refused")
        with pytest.raises(RuntimeError, match="LM Studio"):
            convert_lmstudio(
                img, endpoint="http://localhost:1234/v1",
                api_key="test", model="glm-ocr", timeout=120
            )


class TestMineru:
    @patch("shutil.which", return_value="/usr/local/bin/magic-pdf")
    def test_is_available(self, mock_which):
        assert mineru_is_available({}) is True

    @patch("shutil.which", return_value=None)
    def test_not_available(self, mock_which):
        assert mineru_is_available({}) is False

    @patch("subprocess.Popen")
    @patch("shutil.which", return_value="/usr/local/bin/magic-pdf")
    def test_convert_success(self, mock_which, mock_popen, tmp_path):
        input_file = tmp_path / "paper.pdf"
        input_file.write_text("fake pdf")

        process = MagicMock()
        process.wait.return_value = 0
        process.returncode = 0
        process.pid = 12345
        mock_popen.return_value = process

        def simulate_output(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            for i, arg in enumerate(cmd):
                if arg == "-o":
                    out_dir = Path(cmd[i + 1])
                    md_dir = out_dir / "paper" / "auto"
                    md_dir.mkdir(parents=True, exist_ok=True)
                    (md_dir / "paper.md").write_text("# Academic Paper\n\n$E=mc^2$")
                    break
            return process

        mock_popen.side_effect = simulate_output
        result = convert_mineru(input_file, {}, timeout=120)
        assert "Academic Paper" in result


class TestVisionOcr:
    @patch("claw_ea.converters.VISION_AVAILABLE", True)
    def test_is_available_on_macos(self):
        assert vision_ocr_is_available() is True

    @patch("claw_ea.converters.VISION_AVAILABLE", False)
    def test_not_available_without_vision(self):
        assert vision_ocr_is_available() is False

    @patch("claw_ea.converters.VISION_AVAILABLE", True)
    @patch("claw_ea.converters._run_ocr_from_file")
    def test_convert_success(self, mock_ocr, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        mock_ocr.return_value = "手术通知内容"

        result = convert_vision_ocr(img)
        assert "手术通知内容" in result
        mock_ocr.assert_called_once_with(img)
