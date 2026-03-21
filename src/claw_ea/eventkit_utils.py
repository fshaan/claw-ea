"""Shared EventKit client for Calendar and Reminders tools."""
import asyncio

try:
    from EventKit import (
        EKEventStore,
        EKEntityTypeEvent,
        EKEntityTypeReminder,
        EKAuthorizationStatusAuthorized,
    )
    EVENTKIT_AVAILABLE = True
except ImportError:
    EVENTKIT_AVAILABLE = False


class EventKitClient:
    def __init__(self):
        if not EVENTKIT_AVAILABLE:
            raise RuntimeError(
                "pyobjc-framework-EventKit not available. "
                "This tool requires macOS."
            )
        self.store = EKEventStore.alloc().init()

    async def ensure_calendar_access(self) -> None:
        """Request calendar access. Raises PermissionError if denied."""
        granted = await self._request_access(EKEntityTypeEvent)
        if not granted:
            raise PermissionError(
                "Calendar access denied. Grant access in "
                "System Preferences > Privacy & Security > Calendars."
            )

    async def ensure_reminder_access(self) -> None:
        """Request reminder access. Raises PermissionError if denied."""
        granted = await self._request_access(EKEntityTypeReminder)
        if not granted:
            raise PermissionError(
                "Reminders access denied. Grant access in "
                "System Preferences > Privacy & Security > Reminders."
            )

    async def _request_access(self, entity_type: int) -> bool:
        """Bridge ObjC completion handler to asyncio."""
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        def callback(granted, error):
            loop.call_soon_threadsafe(future.set_result, granted)

        self.store.requestAccessToEntityType_completion_(entity_type, callback)
        return await future

    def find_calendar(self, name: str):
        """Find a calendar by name. Returns EKCalendar or None."""
        calendars = self.store.calendarsForEntityType_(EKEntityTypeEvent)
        for cal in calendars:
            if cal.title() == name:
                return cal
        return None

    def find_reminder_list(self, name: str):
        """Find a reminder list by name. Returns EKCalendar or None."""
        calendars = self.store.calendarsForEntityType_(EKEntityTypeReminder)
        for cal in calendars:
            if cal.title() == name:
                return cal
        return None

    def list_calendars(self) -> list[str]:
        """List all calendar names."""
        return [c.title() for c in self.store.calendarsForEntityType_(EKEntityTypeEvent)]

    def list_reminder_lists(self) -> list[str]:
        """List all reminder list names."""
        return [c.title() for c in self.store.calendarsForEntityType_(EKEntityTypeReminder)]
