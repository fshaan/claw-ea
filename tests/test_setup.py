import pytest
import yaml
from pathlib import Path
from claw_ea.tools.setup import (
    detect_obsidian_vault_impl,
    save_config_impl,
)


def test_detect_vault_finds_existing(tmp_path):
    """Detects a vault when .obsidian directory exists."""
    vault = tmp_path / "MyVault"
    (vault / ".obsidian").mkdir(parents=True)
    results = detect_obsidian_vault_impl(search_paths=[tmp_path])
    assert str(vault) in results


def test_detect_vault_empty_when_none(tmp_path):
    results = detect_obsidian_vault_impl(search_paths=[tmp_path])
    assert results == []


def test_save_config_creates_file(tmp_path):
    config_path = tmp_path / "config.yaml"
    data = {
        "user": {"name": "张医生", "aliases": []},
        "obsidian": {"vault_path": "/tmp/vault", "notes_folder": "Inbox"},
        "attachments": {"base_path": "/tmp/att", "organize_by_date": True},
        "apple": {"calendar_name": "工作", "reminder_list": "OpenClaw"},
    }
    result = save_config_impl(data, config_path)
    assert result["saved"] is True
    assert config_path.exists()
    saved = yaml.safe_load(config_path.read_text())
    assert saved["user"]["name"] == "张医生"


def test_save_config_validates_required_fields(tmp_path):
    config_path = tmp_path / "config.yaml"
    with pytest.raises(ValueError, match="user.name"):
        save_config_impl({"user": {}}, config_path)
