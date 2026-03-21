import pytest
from unittest.mock import MagicMock, patch


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
