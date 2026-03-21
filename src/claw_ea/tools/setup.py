"""Configuration tools: detect_obsidian_vault, list_apple_calendars, save_config."""
from pathlib import Path
from typing import Any

import yaml


def detect_obsidian_vault_impl(search_paths: list[Path] | None = None) -> list[str]:
    """Scan for Obsidian vaults by looking for .obsidian directories."""
    if search_paths is None:
        home = Path.home()
        search_paths = [
            home / "Documents",
            home / "Obsidian",
            home,
        ]

    vaults = []
    for base in search_paths:
        if not base.exists():
            continue
        # Check direct children only (not deep recursive)
        try:
            for child in base.iterdir():
                if child.is_dir() and (child / ".obsidian").exists():
                    vaults.append(str(child))
        except PermissionError:
            continue
    return vaults


def save_config_impl(config_data: dict[str, Any], config_path: Path) -> dict:
    """Validate and save config to YAML file."""
    # Validate required fields
    required = [
        ("user", "name"),
        ("obsidian", "vault_path"),
        ("obsidian", "notes_folder"),
        ("apple", "calendar_name"),
        ("apple", "reminder_list"),
    ]
    for section, key in required:
        if section not in config_data or key not in config_data[section]:
            raise ValueError(f"Missing required field: {section}.{key}")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.dump(config_data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    return {"saved": True, "path": str(config_path)}


def register(mcp_instance, ek_client=None):
    """Register configuration tools."""

    @mcp_instance.tool()
    async def detect_obsidian_vault() -> list[str]:
        """Scan common locations for Obsidian vaults.

        Returns a list of absolute paths to directories containing .obsidian/.
        """
        return detect_obsidian_vault_impl()

    @mcp_instance.tool()
    async def list_apple_calendars() -> dict:
        """List available Apple Calendar calendars and Reminder lists.

        Returns:
            calendars: List of calendar names
            reminder_lists: List of reminder list names
        """
        if ek_client is None:
            return {"calendars": [], "reminder_lists": [], "error": "EventKit not available"}
        await ek_client.ensure_calendar_access()
        await ek_client.ensure_reminder_access()
        return {
            "calendars": ek_client.list_calendars(),
            "reminder_lists": ek_client.list_reminder_lists(),
        }

    @mcp_instance.tool()
    async def save_config(config_data: dict) -> dict:
        """Validate and save configuration to ~/.claw-ea/config.yaml.

        Args:
            config_data: Configuration dictionary with sections: user, obsidian, attachments, apple

        Returns:
            saved: True if saved successfully
            path: Absolute path to the saved config file
        """
        config_path = Path.home() / ".claw-ea" / "config.yaml"
        return save_config_impl(config_data, config_path)
