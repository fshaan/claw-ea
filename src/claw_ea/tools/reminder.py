"""create_reminder MCP tool."""
from datetime import datetime

from claw_ea.config import Config

try:
    from EventKit import EKReminder
    from Foundation import NSDate, NSCalendar, NSDateComponents
    EVENTKIT_AVAILABLE = True
except ImportError:
    EVENTKIT_AVAILABLE = False


async def create_reminder_impl(
    title: str, due_date: str | None = None,
    priority: int | None = None, notes: str | None = None,
    *, ek_client, list_name: str,
) -> dict:
    """Core logic for create_reminder."""
    await ek_client.ensure_reminder_access()

    rem_list = ek_client.find_reminder_list(list_name)
    if rem_list is None:
        available = ek_client.list_reminder_lists()
        raise ValueError(
            f"Reminder list '{list_name}' not found. "
            f"Available: {', '.join(available) if available else 'none'}"
        )

    reminder = EKReminder.reminderWithEventStore_(ek_client.store)
    reminder.setTitle_(title)
    reminder.setCalendar_(rem_list)

    if due_date:
        dt = datetime.fromisoformat(due_date)
        cal = NSCalendar.currentCalendar()
        components = NSDateComponents.alloc().init()
        components.setYear_(dt.year)
        components.setMonth_(dt.month)
        components.setDay_(dt.day)
        components.setHour_(dt.hour)
        components.setMinute_(dt.minute)
        reminder.setDueDateComponents_(components)

    if priority is not None:
        reminder.setPriority_(priority)
    if notes:
        reminder.setNotes_(notes)

    success, error = ek_client.store.saveReminder_commit_error_(reminder, True, None)
    if not success:
        raise RuntimeError(f"Failed to save reminder: {error}")

    return {
        "reminder_id": reminder.calendarItemIdentifier(),
        "list": list_name,
    }


def register(mcp_instance, config: Config, ek_client):
    """Register create_reminder tool."""

    @mcp_instance.tool()
    async def create_reminder(
        title: str, due_date: str = "", priority: int = 0, notes: str = "",
    ) -> dict:
        """Create a reminder in Apple Reminders.

        Args:
            title: Reminder title (e.g. "[主持] 新技术培训 - 科室周会 10:00")
            due_date: ISO-8601 datetime for due date. Empty for undated reminder.
            priority: 1-9 (1=highest). 0 or empty for default.
            notes: Additional notes

        Returns:
            reminder_id: Apple Reminders identifier
            list: Reminder list name used
        """
        return await create_reminder_impl(
            title, due_date or None, priority or None, notes or None,
            ek_client=ek_client, list_name=config.reminder_list,
        )
