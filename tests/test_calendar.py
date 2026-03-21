import pytest
from unittest.mock import MagicMock, patch, AsyncMock


def test_eventkit_client_init():
    """EventKitClient initializes without error (mocked)."""
    with patch("claw_ea.eventkit_utils.EKEventStore") as MockStore:
        MockStore.alloc.return_value.init.return_value = MagicMock()
        from claw_ea.eventkit_utils import EventKitClient
        client = EventKitClient()
        assert client.store is not None


def test_find_calendar_returns_none_when_missing():
    """find_calendar returns None for nonexistent calendar name."""
    with patch("claw_ea.eventkit_utils.EKEventStore") as MockStore:
        mock_store = MagicMock()
        mock_store.calendarsForEntityType_.return_value = []
        MockStore.alloc.return_value.init.return_value = mock_store
        from claw_ea.eventkit_utils import EventKitClient
        client = EventKitClient()
        assert client.find_calendar("nonexistent") is None


from claw_ea.tools.calendar import create_calendar_event_impl


@pytest.fixture
def mock_ek_client():
    client = MagicMock()
    client.ensure_calendar_access = AsyncMock()
    mock_cal = MagicMock()
    mock_cal.title.return_value = "工作"
    client.find_calendar.return_value = mock_cal
    client.store = MagicMock()
    client.store.saveEvent_span_error_.return_value = (True, None)
    return client


@pytest.mark.asyncio
async def test_create_event_basic(mock_ek_client):
    with patch("claw_ea.tools.calendar.EKEvent") as MockEvent:
        mock_event = MagicMock()
        mock_event.eventIdentifier.return_value = "test-id-123"
        MockEvent.eventWithEventStore_.return_value = mock_event

        result = await create_calendar_event_impl(
            title="[主刀] 腹腔镜胆囊切除术 - 张三",
            start_time="2026-03-22T09:00:00",
            end_time=None, location="3号手术室", notes="第一台",
            ek_client=mock_ek_client, calendar_name="工作",
        )
        assert result["event_id"] == "test-id-123"
        assert result["calendar"] == "工作"


@pytest.mark.asyncio
async def test_create_event_calendar_not_found(mock_ek_client):
    mock_ek_client.find_calendar.return_value = None
    with pytest.raises(ValueError, match="Calendar.*not found"):
        await create_calendar_event_impl(
            title="test", start_time="2026-03-22T09:00:00",
            ek_client=mock_ek_client, calendar_name="不存在",
        )
