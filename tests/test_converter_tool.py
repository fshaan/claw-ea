import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from claw_ea.converters import ConversionResult
from claw_ea.tools.converter import convert_to_markdown_impl


class TestConvertToMarkdownTool:
    @patch("claw_ea.tools.converter.dispatch")
    def test_success(self, mock_dispatch, tmp_path, mock_config):
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake pdf")

        temp_md = tmp_path / "output.md"
        temp_md.write_text("# Converted content")

        mock_dispatch.return_value = ConversionResult(
            temp_path=str(temp_md),
            source_path=str(input_file),
            converter_used="docling",
            fallback_used=False,
        )

        result = convert_to_markdown_impl(str(input_file), "", mock_config)
        assert result["md_path"] == str(temp_md)
        assert result["converter_used"] == "docling"
        assert result["fallback_used"] is False

    def test_file_not_found(self, mock_config):
        result = convert_to_markdown_impl("/nonexistent/file.pdf", "", mock_config)
        assert "error" in result

    @patch("claw_ea.tools.converter.dispatch")
    def test_dispatch_error(self, mock_dispatch, tmp_path, mock_config):
        input_file = tmp_path / "test.pdf"
        input_file.write_text("fake pdf")
        mock_dispatch.side_effect = ValueError("Unsupported file extension: .pdf")

        result = convert_to_markdown_impl(str(input_file), "", mock_config)
        assert "error" in result
