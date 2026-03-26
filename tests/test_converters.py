import pytest
from claw_ea.converters import is_usable


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
