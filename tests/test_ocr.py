import base64
import pytest
from unittest.mock import MagicMock, patch
from claw_ea.tools.ocr import ocr_image_impl


def test_ocr_invalid_base64():
    with pytest.raises(ValueError, match="base64"):
        ocr_image_impl("not-valid!!!", "test.png")


def test_ocr_returns_text(tmp_path):
    """Test with mocked Vision framework."""
    # Create a small valid PNG (1x1 pixel)
    import struct, zlib

    def make_png():
        header = b'\x89PNG\r\n\x1a\n'
        ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data)
        ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
        raw = zlib.compress(b'\x00\x00\x00\x00')
        idat_crc = zlib.crc32(b'IDAT' + raw)
        idat = struct.pack('>I', len(raw)) + b'IDAT' + raw + struct.pack('>I', idat_crc)
        iend_crc = zlib.crc32(b'IEND')
        iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
        return header + ihdr + idat + iend

    img_b64 = base64.b64encode(make_png()).decode()

    with patch("claw_ea.tools.ocr.VISION_AVAILABLE", True), \
         patch("claw_ea.tools.ocr._run_ocr") as mock_ocr:
        mock_ocr.return_value = "手术排班表 2026年3月22日"
        result = ocr_image_impl(img_b64, "排班表.png")
        assert result["extracted_text"] == "手术排班表 2026年3月22日"
