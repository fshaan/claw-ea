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


def test_attachments_folder_alias(tmp_path):
    """Config with 'folder' instead of 'base_path' should work."""
    config_file = tmp_path / "config.yaml"
    att_dir = tmp_path / "99_Attachments"
    config_file.write_text(yaml.dump({
        "user": {"name": "张医生", "aliases": []},
        "obsidian": {"vault_path": str(tmp_path), "notes_folder": "Inbox"},
        "attachments": {"folder": str(att_dir)},
        "apple": {"calendar_name": "日历", "reminder_list": "任务箱"},
    }))
    config = load_config(config_file)
    assert config.attachments_path == att_dir


def test_parse_converters_config(tmp_path):
    """Converters config section is parsed into Config fields."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
user:
  name: 张医生
obsidian:
  vault_path: /tmp/vault
  notes_folder: Inbox
apple:
  calendar_name: 工作
  reminder_list: OpenClaw
converters:
  lmstudio:
    endpoint: http://localhost:1234/v1
    api_key: test-key
    model: glm-ocr
    timeout: 90
  paths:
    docling: /usr/local/bin/docling
  routing:
    pdf:
      default: [docling]
      academic: [mineru, docling]
    image:
      default: [lmstudio, vision_ocr]
""", encoding="utf-8")
    from claw_ea.config import load_config
    cfg = load_config(config_file)
    assert cfg.lmstudio_endpoint == "http://localhost:1234/v1"
    assert cfg.lmstudio_api_key == "test-key"
    assert cfg.lmstudio_model == "glm-ocr"
    assert cfg.lmstudio_timeout == 90
    assert cfg.converter_paths == {"docling": "/usr/local/bin/docling"}
    assert cfg.converter_routing[".pdf"]["default"] == ["docling"]
    assert cfg.converter_routing[".pdf"]["academic"] == ["mineru", "docling"]
    assert cfg.converter_routing[".image"]["default"] == ["lmstudio", "vision_ocr"]


def test_parse_config_without_converters(tmp_path):
    """Missing converters section gives empty defaults."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
user:
  name: 张医生
obsidian:
  vault_path: /tmp/vault
  notes_folder: Inbox
apple:
  calendar_name: 工作
  reminder_list: OpenClaw
""", encoding="utf-8")
    from claw_ea.config import load_config
    cfg = load_config(config_file)
    assert cfg.converter_paths == {}
    assert cfg.converter_routing == {}
    assert cfg.lmstudio_endpoint == ""
    assert cfg.lmstudio_api_key == ""
    assert cfg.lmstudio_model == ""
    assert cfg.lmstudio_timeout == 120
