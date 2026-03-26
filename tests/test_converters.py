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
from claw_ea.converters import convert_passthrough
from claw_ea.converters import dispatch, DEFAULT_ROUTING, ConversionResult
from claw_ea.config import Config


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
        process.communicate.return_value = (None, b"")
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
        process.communicate.side_effect = subprocess.TimeoutExpired(cmd="docling", timeout=60)
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
        process.communicate.return_value = (None, b"")
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


class TestDispatch:
    def _make_config(self, tmp_path, routing=None, paths=None, **lms_kwargs):
        """Helper to build a Config with converter fields."""
        vault = tmp_path / "vault"
        vault.mkdir(exist_ok=True)
        (vault / "Inbox/OpenClaw").mkdir(parents=True, exist_ok=True)
        att = tmp_path / "attachments"
        att.mkdir(exist_ok=True)
        return Config(
            user_name="张医生", user_aliases=[], vault_path=vault,
            notes_folder="Inbox/OpenClaw", attachments_path=att,
            organize_by_date=True, calendar_name="工作", reminder_list="OpenClaw",
            surgery_time_slots={}, surgery_user_roles=[],
            converter_paths=paths or {},
            converter_routing=routing or {},
            lmstudio_endpoint=lms_kwargs.get("endpoint", ""),
            lmstudio_api_key=lms_kwargs.get("api_key", ""),
            lmstudio_model=lms_kwargs.get("model", ""),
            lmstudio_timeout=lms_kwargs.get("timeout", 120),
        )

    @patch("claw_ea.converters.docling_is_available", return_value=True)
    @patch("claw_ea.converters.convert_docling", return_value="# Good markdown\n\nContent here")
    def test_happy_path_pdf(self, mock_convert, mock_avail, tmp_path):
        cfg = self._make_config(tmp_path)
        f = tmp_path / "test.pdf"
        f.write_text("fake")
        result = dispatch(f, cfg)
        assert result.converter_used == "docling"
        assert result.fallback_used is False
        assert Path(result.temp_path).exists()
        assert "Good markdown" in Path(result.temp_path).read_text()

    @patch("claw_ea.converters.docling_is_available", return_value=True)
    @patch("claw_ea.converters.convert_docling", return_value="")
    @patch("claw_ea.converters.markitdown_is_available", return_value=True)
    @patch("claw_ea.converters.convert_markitdown", return_value="# Fallback content")
    def test_fallback_on_empty(self, mock_mk, mock_mk_avail, mock_dl, mock_dl_avail, tmp_path):
        cfg = self._make_config(tmp_path)
        f = tmp_path / "test.docx"
        f.write_text("fake")
        result = dispatch(f, cfg)
        assert result.converter_used == "markitdown"
        assert result.fallback_used is True

    @patch("claw_ea.converters.docling_is_available", return_value=False)
    @patch("claw_ea.converters.markitdown_is_available", return_value=True)
    @patch("claw_ea.converters.convert_markitdown", return_value="# Content")
    def test_skip_unavailable(self, mock_mk, mock_mk_avail, mock_dl_avail, tmp_path):
        cfg = self._make_config(tmp_path)
        f = tmp_path / "test.docx"
        f.write_text("fake")
        result = dispatch(f, cfg)
        assert result.converter_used == "markitdown"
        # Skipping unavailable is not "fallback" — fallback means tried and rejected
        assert result.fallback_used is False

    @patch("claw_ea.converters.docling_is_available", return_value=True)
    @patch("claw_ea.converters.convert_docling", side_effect=RuntimeError("crash"))
    @patch("claw_ea.converters.markitdown_is_available", return_value=True)
    @patch("claw_ea.converters.convert_markitdown", return_value="# Recovered")
    def test_fallback_on_exception(self, mock_mk, mock_mk_avail, mock_dl, mock_dl_avail, tmp_path):
        cfg = self._make_config(tmp_path)
        f = tmp_path / "test.pptx"
        f.write_text("fake")
        result = dispatch(f, cfg)
        assert result.converter_used == "markitdown"
        assert result.fallback_used is True

    def test_dispatch_txt_passthrough(self, tmp_path):
        cfg = self._make_config(tmp_path)
        f = tmp_path / "readme.txt"
        f.write_text("Plain text content here.", encoding="utf-8")
        result = dispatch(f, cfg)
        assert result.converter_used == "passthrough"
        assert result.fallback_used is False
        assert Path(result.temp_path).read_text(encoding="utf-8") == "Plain text content here."

    def test_unsupported_extension(self, tmp_path):
        cfg = self._make_config(tmp_path)
        f = tmp_path / "test.xyz"
        f.write_text("fake")
        with pytest.raises(ValueError, match="Unsupported"):
            dispatch(f, cfg)

    @patch("claw_ea.converters.docling_is_available", return_value=True)
    @patch("claw_ea.converters.convert_docling", return_value="# Custom route")
    def test_hint_selects_sub_route(self, mock_convert, mock_avail, tmp_path):
        cfg = self._make_config(tmp_path, routing={
            ".pdf": {"default": ["markitdown"], "academic": ["docling"]},
        })
        f = tmp_path / "paper.pdf"
        f.write_text("fake")
        result = dispatch(f, cfg, hint="academic")
        assert result.converter_used == "docling"

    @patch("claw_ea.converters.docling_is_available", return_value=True)
    @patch("claw_ea.converters.convert_docling", return_value="# Default route content")
    @patch("claw_ea.converters.markitdown_is_available", return_value=True)
    @patch("claw_ea.converters.convert_markitdown", return_value="# Markitdown content")
    def test_partial_config_routing_falls_back_to_default(self, mock_mk, mock_mk_avail, mock_dl, mock_dl_avail, tmp_path):
        """Config routing only covers .pdf — .docx should fall back to DEFAULT_ROUTING."""
        cfg = self._make_config(tmp_path, routing={
            ".pdf": {"default": ["markitdown"]},  # only pdf configured
        })
        f = tmp_path / "test.docx"
        f.write_text("fake")
        result = dispatch(f, cfg)
        # .docx not in config routing, should fall back to DEFAULT_ROUTING: ["docling", "markitdown"]
        assert result.converter_used == "docling"

    @patch("claw_ea.converters.docling_is_available", return_value=True)
    @patch("claw_ea.converters.convert_docling", return_value="")
    @patch("claw_ea.converters.markitdown_is_available", return_value=True)
    @patch("claw_ea.converters.convert_markitdown", return_value="\x00\x01\x02")
    def test_all_fail_returns_longest(self, mock_mk, mock_mk_avail, mock_dl, mock_dl_avail, tmp_path):
        cfg = self._make_config(tmp_path)
        f = tmp_path / "test.docx"
        f.write_text("fake")
        result = dispatch(f, cfg)
        assert result.converter_used == "markitdown"
        assert result.fallback_used is True


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


class TestPassthrough:
    def test_convert_passthrough_reads_content(self, tmp_path):
        f = tmp_path / "notes.txt"
        f.write_text("Hello, 世界！\n第二行", encoding="utf-8")
        result = convert_passthrough(f)
        assert result == "Hello, 世界！\n第二行"

    def test_passthrough_is_always_available(self):
        from claw_ea.converters import _get_available_check
        # passthrough should always be available regardless of config
        cfg = MagicMock()
        assert _get_available_check("passthrough", cfg) is True

    def test_passthrough_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = convert_passthrough(f)
        assert result == ""
        assert is_usable(result) is False

    def test_passthrough_non_utf8(self, tmp_path):
        f = tmp_path / "binary.txt"
        f.write_bytes(b"\x80\x81\x82\x83\xff\xfe")
        with pytest.raises(UnicodeDecodeError):
            convert_passthrough(f)


@pytest.mark.converter
class TestMarkitdownIntegration:
    """Integration tests that call real markitdown CLI."""

    def test_convert_csv(self, tmp_path):
        """Test markitdown with a CSV file."""
        if not markitdown_is_available({}):
            pytest.skip("markitdown not installed")

        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name,age\n张三,45\n李四,32", encoding="utf-8")

        result = convert_markitdown(csv_file, {}, timeout=30)
        assert "张三" in result
        assert "45" in result
