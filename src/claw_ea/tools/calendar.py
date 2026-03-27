"""create_calendar_event MCP tool."""
from datetime import datetime, timedelta

from claw_ea.config import Config

try:
    from EventKit import EKAlarm, EKEvent, EKSpanThisEvent
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

    # Default: 15-minute reminder before event
    alarm = EKAlarm.alarmWithRelativeOffset_(-15 * 60)
    event.addAlarm_(alarm)

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


async def delete_calendar_event_impl(event_id: str, *, ek_client) -> dict:
    """Core logic for delete_calendar_event."""
    if not event_id or not event_id.strip():
        raise ValueError("event_id must be a non-empty string")

    await ek_client.ensure_calendar_access()

    event = ek_client.store.eventWithIdentifier_(event_id)
    if event is None:
        raise ValueError(f"Event '{event_id}' not found")

    title = event.title()
    success, error = ek_client.store.removeEvent_span_commit_error_(
        event, EKSpanThisEvent, True, None
    )
    if not success:
        raise RuntimeError(f"Failed to delete event: {error}")

    return {"deleted": True, "event_id": event_id, "title": title}


def register(mcp_instance, config: Config, ek_client):
    """Register calendar tools."""

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

        For surgery schedules: this is the primary action (no note, no reminder).
        """
        return await create_calendar_event_impl(
            title, start_time, end_time or None, location or None, notes or None,
            ek_client=ek_client, calendar_name=config.calendar_name,
        )

    @mcp_instance.tool()
    async def delete_calendar_event(event_id: str) -> dict:
        """Delete an event from Apple Calendar.

        Args:
            event_id: The event identifier returned by create_calendar_event.

        Returns:
            deleted: True if successful
            event_id: The deleted event's identifier
            title: The deleted event's title (for confirmation)

        Agent should confirm with user before calling this tool.
        """
        return await delete_calendar_event_impl(
            event_id, ek_client=ek_client,
        )
