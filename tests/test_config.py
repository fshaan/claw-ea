import pytest
import yaml
from pathlib import Path
from claw_ea.config import load_config, Config, ConfigError


def test_load_valid_config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({
        "user": {"name": "张医生", "aliases": ["张三"]},
        "obsidian": {"vault_path": str(tmp_path), "notes_folder": "Inbox/OpenClaw"},
        "attachments": {"base_path": str(tmp_path / "att"), "organize_by_date": True},
        "apple": {"calendar_name": "工作", "reminder_list": "OpenClaw"},
        "categories": {
            "surgery": {
                "schedule_time_slots": {1: "09:00", 2: "13:00"},
                "user_roles": ["主刀", "带组"],
            }
        },
    }))
    config = load_config(config_file)
    assert config.user_name == "张医生"
    assert config.vault_path == tmp_path
    assert isinstance(config, Config)


def test_load_missing_config(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nonexistent.yaml")


def test_load_invalid_yaml(tmp_path):
    bad = tmp_path / "config.yaml"
    bad.write_text("not: valid: yaml: {{")
    with pytest.raises(ConfigError):
        load_config(bad)


def test_load_missing_required_field(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"user": {"name": "张医生"}}))
    with pytest.raises(ConfigError, match="obsidian"):
        load_config(config_file)
