from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when config is missing, invalid, or incomplete."""


@dataclass
class Config:
    user_name: str
    user_aliases: list[str]
    vault_path: Path
    notes_folder: str
    attachments_path: Path
    organize_by_date: bool
    calendar_name: str
    reminder_list: str
    surgery_time_slots: dict[int, str]
    surgery_user_roles: list[str]
    # Converter settings (all optional)
    converter_paths: dict[str, str]  # e.g. {"docling": "/path/to/docling"}
    converter_routing: dict[str, dict[str, list[str]]]  # e.g. {".pdf": {"default": ["docling"]}}
    lmstudio_endpoint: str
    lmstudio_api_key: str
    lmstudio_model: str
    lmstudio_timeout: int


def load_config(path: Path | None = None) -> Config:
    """Load config from YAML file. Raises ConfigError if missing or invalid."""
    if path is None:
        path = Path.home() / ".claw-ea" / "config.yaml"

    if not path.exists():
        raise ConfigError(
            f"Config file not found: {path}\n"
            "Run the setup wizard to create one."
        )

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError(f"Config must be a YAML mapping, got {type(raw).__name__}")

    return _parse_config(raw, path)


def _parse_config(raw: dict[str, Any], path: Path) -> Config:
    """Parse raw YAML dict into Config dataclass."""
    def require(section: str, key: str) -> Any:
        if section not in raw:
            raise ConfigError(f"Missing required section '{section}' in {path}")
        if key not in raw[section]:
            raise ConfigError(f"Missing required key '{section}.{key}' in {path}")
        return raw[section][key]

    user_name = require("user", "name")
    user_aliases = raw.get("user", {}).get("aliases", [])

    vault_path = Path(require("obsidian", "vault_path")).expanduser()
    notes_folder = require("obsidian", "notes_folder")

    att = raw.get("attachments", {})
    # Accept both "base_path" (documented) and "folder" (common alias)
    att_path_str = att.get("base_path") or att.get("folder") or str(vault_path / "attachments")
    attachments_path = Path(att_path_str).expanduser()
    organize_by_date = att.get("organize_by_date", True)

    calendar_name = require("apple", "calendar_name")
    reminder_list = require("apple", "reminder_list")

    cats = raw.get("categories", {}).get("surgery", {})
    surgery_time_slots = {int(k): v for k, v in cats.get("schedule_time_slots", {1: "09:00", 2: "13:00", 3: "17:00", 4: "20:00"}).items()}
    surgery_user_roles = cats.get("user_roles", ["主刀", "带组", "一助"])

    # Converters (entire section optional)
    conv = raw.get("converters", {})

    lms = conv.get("lmstudio", {})
    lmstudio_endpoint = lms.get("endpoint", "")
    lmstudio_api_key = lms.get("api_key", "")
    lmstudio_model = lms.get("model", "")
    lmstudio_timeout = lms.get("timeout", 120)

    converter_paths = conv.get("paths", {})

    # Normalize routing keys: config uses short names (pdf, image),
    # internal uses dot-prefixed (.pdf, .image)
    raw_routing = conv.get("routing", {})
    converter_routing = {}
    for fmt, chains in raw_routing.items():
        key = f".{fmt}" if not fmt.startswith(".") else fmt
        converter_routing[key] = chains

    return Config(
        user_name=user_name,
        user_aliases=user_aliases,
        vault_path=vault_path,
        notes_folder=notes_folder,
        attachments_path=attachments_path,
        organize_by_date=organize_by_date,
        calendar_name=calendar_name,
        reminder_list=reminder_list,
        surgery_time_slots=surgery_time_slots,
        surgery_user_roles=surgery_user_roles,
        converter_paths=converter_paths,
        converter_routing=converter_routing,
        lmstudio_endpoint=lmstudio_endpoint,
        lmstudio_api_key=lmstudio_api_key,
        lmstudio_model=lmstudio_model,
        lmstudio_timeout=lmstudio_timeout,
    )
