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


from claw_ea.tools.calendar import create_calendar_event_impl, delete_calendar_event_impl


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
    with patch("claw_ea.tools.calendar.EKEvent") as MockEvent, \
         patch("claw_ea.tools.calendar.EKAlarm") as MockAlarm:
        mock_event = MagicMock()
        mock_event.eventIdentifier.return_value = "test-id-123"
        MockEvent.eventWithEventStore_.return_value = mock_event
        mock_alarm = MagicMock()
        MockAlarm.alarmWithRelativeOffset_.return_value = mock_alarm

        result = await create_calendar_event_impl(
            title="[主刀] 腹腔镜胆囊切除术 - 张三",
            start_time="2026-03-22T09:00:00",
            end_time=None, location="3号手术室", notes="第一台",
            ek_client=mock_ek_client, calendar_name="工作",
        )
        assert result["event_id"] == "test-id-123"
        assert result["calendar"] == "工作"
        # Verify 15-minute alarm was added
        MockAlarm.alarmWithRelativeOffset_.assert_called_once_with(-900)
        mock_event.addAlarm_.assert_called_once_with(mock_alarm)


@pytest.mark.asyncio
async def test_create_event_calendar_not_found(mock_ek_client):
    mock_ek_client.find_calendar.return_value = None
    with pytest.raises(ValueError, match="Calendar.*not found"):
        await create_calendar_event_impl(
            title="test", start_time="2026-03-22T09:00:00",
            ek_client=mock_ek_client, calendar_name="不存在",
        )


@pytest.mark.asyncio
async def test_delete_event_basic(mock_ek_client):
    mock_event = MagicMock()
    mock_event.title.return_value = "[主刀] 腹腔镜胆囊切除术"
    mock_ek_client.store.eventWithIdentifier_.return_value = mock_event
    mock_ek_client.store.removeEvent_span_commit_error_.return_value = (True, None)

    result = await delete_calendar_event_impl(
        "test-id-123", ek_client=mock_ek_client,
    )
    assert result["deleted"] is True
    assert result["event_id"] == "test-id-123"
    assert result["title"] == "[主刀] 腹腔镜胆囊切除术"


@pytest.mark.asyncio
async def test_delete_event_empty_id(mock_ek_client):
    with pytest.raises(ValueError, match="non-empty"):
        await delete_calendar_event_impl("", ek_client=mock_ek_client)


@pytest.mark.asyncio
async def test_delete_event_not_found(mock_ek_client):
    mock_ek_client.store.eventWithIdentifier_.return_value = None
    with pytest.raises(ValueError, match="not found"):
        await delete_calendar_event_impl(
            "nonexistent-id", ek_client=mock_ek_client,
        )


@pytest.mark.asyncio
async def test_delete_event_remove_fails(mock_ek_client):
    mock_event = MagicMock()
    mock_event.title.return_value = "test"
    mock_ek_client.store.eventWithIdentifier_.return_value = mock_event
    mock_ek_client.store.removeEvent_span_commit_error_.return_value = (False, "locked")
    with pytest.raises(RuntimeError, match="Failed to delete event"):
        await delete_calendar_event_impl(
            "test-id", ek_client=mock_ek_client,
        )
