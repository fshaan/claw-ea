"""Shared EventKit client for Calendar and Reminders tools."""
import asyncio

try:
    from EventKit import (
        EKEventStore,
        EKEntityTypeEvent,
        EKEntityTypeReminder,
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

    async def ensure_calendar_access(self, allow_prompt: bool = False) -> None:
        """Ensure calendar access. Raises PermissionError if unavailable."""
        await self._ensure_access(EKEntityTypeEvent, "Calendar", "Calendars", allow_prompt)

    async def ensure_reminder_access(self, allow_prompt: bool = False) -> None:
        """Ensure reminder access. Raises PermissionError if unavailable."""
        await self._ensure_access(EKEntityTypeReminder, "Reminders", "Reminders", allow_prompt)

    async def _ensure_access(
        self, entity_type: int, label: str, pane: str, allow_prompt: bool
    ) -> None:
        """Status-gated access check.

        Default (allow_prompt=False) never triggers a TCC prompt: if the status is
        notDetermined we raise instead of requesting, so a headless/cron invocation
        cannot poison the TCC cache with a denial. Only the dedicated GUI grant
        entrypoint (claw_ea.grant) passes allow_prompt=True.
        """
        # EKAuthorizationStatus: 0 notDetermined, 1 restricted, 2 denied,
        # 3 fullAccess/authorized, 4 writeOnly.
        status = EKEventStore.authorizationStatusForEntityType_(entity_type)
        if status in (3, 4):
            return
        if status == 0:
            if not allow_prompt:
                raise PermissionError(
                    f"{label} access not yet authorized. Run the one-time GUI grant "
                    f"in a graphical login session: `python -m claw_ea.grant`. "
                    f"Refusing to request headless to avoid poisoning the TCC cache."
                )
            granted, error = await self._request_access(entity_type)
            if not granted:
                raise PermissionError(f"{label} access denied during prompt: {error}")
            return
        raise PermissionError(
            f"{label} access is denied (status={status}). Enable it in "
            f"System Settings > Privacy & Security > {pane}, then re-run the grant."
        )

    async def _request_access(self, entity_type: int):
        """Bridge ObjC completion handler to asyncio (macOS 14+ full-access API)."""
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        def callback(granted, error):
            loop.call_soon_threadsafe(future.set_result, (granted, error))

        if entity_type == EKEntityTypeEvent:
            self.store.requestFullAccessToEventsWithCompletion_(callback)
        else:
            self.store.requestFullAccessToRemindersWithCompletion_(callback)
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
