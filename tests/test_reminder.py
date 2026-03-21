import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from claw_ea.tools.reminder import create_reminder_impl


@pytest.fixture
def mock_ek_client():
    client = MagicMock()
    client.ensure_reminder_access = AsyncMock()
    mock_list = MagicMock()
    mock_list.title.return_value = "OpenClaw"
    client.find_reminder_list.return_value = mock_list
    client.store = MagicMock()
    client.store.saveReminder_commit_error_.return_value = (True, None)
    return client


@pytest.mark.asyncio
async def test_create_reminder_basic(mock_ek_client):
    with patch("claw_ea.tools.reminder.EKReminder") as MockReminder:
        mock_rem = MagicMock()
        mock_rem.calendarItemIdentifier.return_value = "rem-id-456"
        MockReminder.reminderWithEventStore_.return_value = mock_rem

        result = await create_reminder_impl(
            title="术前准备：张三 腹腔镜胆囊切除术",
            due_date="2026-03-22T08:00:00",
            priority=None, notes="提前1小时提醒",
            ek_client=mock_ek_client, list_name="OpenClaw",
        )
        assert result["reminder_id"] == "rem-id-456"


@pytest.mark.asyncio
async def test_create_reminder_no_due_date(mock_ek_client):
    with patch("claw_ea.tools.reminder.EKReminder") as MockReminder:
        mock_rem = MagicMock()
        mock_rem.calendarItemIdentifier.return_value = "rem-id-789"
        MockReminder.reminderWithEventStore_.return_value = mock_rem

        result = await create_reminder_impl(
            title="跟进检查结果",
            due_date=None, priority=None, notes=None,
            ek_client=mock_ek_client, list_name="OpenClaw",
        )
        assert result["reminder_id"] == "rem-id-789"


@pytest.mark.asyncio
async def test_create_reminder_list_not_found(mock_ek_client):
    mock_ek_client.find_reminder_list.return_value = None
    with pytest.raises(ValueError, match="not found"):
        await create_reminder_impl(
            title="test", due_date=None, priority=None, notes=None,
            ek_client=mock_ek_client, list_name="不存在",
        )
