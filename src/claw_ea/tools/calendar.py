"""create_calendar_event MCP tool."""
from datetime import datetime, timedelta

from claw_ea.config import Config

try:
    from EventKit import EKEvent, EKSpanThisEvent
    from Foundation import NSDate
    EVENTKIT_AVAILABLE = True
except ImportError:
    EVENTKIT_AVAILABLE = False


def _parse_datetime(iso_str: str) -> "NSDate":
    """Parse ISO-8601 string to NSDate."""
    dt = datetime.fromisoformat(iso_str)
    timestamp = dt.timestamp()
    return NSDate.dateWithTimeIntervalSince1970_(timestamp)


async def create_calendar_event_impl(
    title: str, start_time: str, end_time: str | None = None,
    location: str | None = None, notes: str | None = None,
    *, ek_client, calendar_name: str,
) -> dict:
    """Core logic for create_calendar_event."""
    await ek_client.ensure_calendar_access()

    calendar = ek_client.find_calendar(calendar_name)
    if calendar is None:
        available = ek_client.list_calendars()
        raise ValueError(
            f"Calendar '{calendar_name}' not found. "
            f"Available: {', '.join(available) if available else 'none'}"
        )

    event = EKEvent.eventWithEventStore_(ek_client.store)
    event.setTitle_(title)
    event.setCalendar_(calendar)
    event.setStartDate_(_parse_datetime(start_time))

    if end_time:
        event.setEndDate_(_parse_datetime(end_time))
    else:
        # Default: 1 hour
        start_dt = datetime.fromisoformat(start_time)
        end_dt = start_dt + timedelta(hours=1)
        event.setEndDate_(_parse_datetime(end_dt.isoformat()))

    if location:
        event.setLocation_(location)
    if notes:
        event.setNotes_(notes)

    success, error = ek_client.store.saveEvent_span_error_(event, EKSpanThisEvent, None)
    if not success:
        raise RuntimeError(f"Failed to save event: {error}")

    return {
        "event_id": event.eventIdentifier(),
        "calendar": calendar_name,
    }


def register(mcp_instance, config: Config, ek_client):
    """Register create_calendar_event tool."""

    @mcp_instance.tool()
    async def create_calendar_event(
        title: str, start_time: str, end_time: str = "",
        location: str = "", notes: str = "",
    ) -> dict:
        """Create an event in Apple Calendar.

        Args:
            title: Event title (e.g. "[主刀] 腹腔镜胆囊切除术 - 张三")
            start_time: ISO-8601 datetime (e.g. "2026-03-22T09:00:00")
            end_time: ISO-8601 datetime. Defaults to start_time + 1 hour.
            location: Event location (e.g. "3号手术室")
            notes: Additional notes

        Returns:
            event_id: Apple Calendar event identifier
            calendar: Calendar name used

        Note: Do NOT use for surgery schedules — use create_reminder instead.
        """
        return await create_calendar_event_impl(
            title, start_time, end_time or None, location or None, notes or None,
            ek_client=ek_client, calendar_name=config.calendar_name,
        )
