import pytest
from pathlib import Path
from claw_ea.config import Config


@pytest.fixture
def tmp_vault(tmp_path):
    """Create a temporary Obsidian vault with required structure."""
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Inbox" / "OpenClaw").mkdir(parents=True)
    return vault


@pytest.fixture
def tmp_attachments(tmp_path):
    """Create a temporary attachments directory."""
    att = tmp_path / "attachments"
    att.mkdir()
    return att


@pytest.fixture
def mock_config(tmp_vault, tmp_attachments):
    """Return a Config pointing at temporary directories."""
    return Config(
        user_name="张医生",
        user_aliases=["张三", "Dr. Zhang"],
        vault_path=tmp_vault,
        notes_folder="Inbox/OpenClaw",
        attachments_path=tmp_attachments,
        organize_by_date=True,
        calendar_name="工作",
        reminder_list="OpenClaw",
        surgery_time_slots={1: "09:00", 2: "13:00", 3: "17:00", 4: "20:00"},
        surgery_user_roles=["主刀", "带组", "一助"],
        converter_paths={},
        converter_routing={},
        lmstudio_endpoint="",
        lmstudio_api_key="",
        lmstudio_model="",
        lmstudio_timeout=120,
    )
