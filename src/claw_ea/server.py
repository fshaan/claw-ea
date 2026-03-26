from mcp.server.fastmcp import FastMCP
from claw_ea.config import load_config, ConfigError

mcp = FastMCP("claw-ea", json_response=True)


def main():
    try:
        config = load_config()
    except ConfigError as e:
        import sys
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    ek_client = None
    try:
        from claw_ea.eventkit_utils import EventKitClient
        ek_client = EventKitClient()
    except (ImportError, RuntimeError):
        import sys
        print("WARNING: EventKit not available. Calendar/Reminder tools disabled.", file=sys.stderr)

    from claw_ea.tools.attachment import register as reg_attachment
    from claw_ea.tools.obsidian import register as reg_obsidian
    from claw_ea.tools.ocr import register as reg_ocr
    from claw_ea.tools.converter import register as reg_converter
    from claw_ea.tools.setup import register as reg_setup

    reg_attachment(mcp, config)
    reg_obsidian(mcp, config)
    reg_ocr(mcp)
    reg_converter(mcp, config)
    reg_setup(mcp, ek_client)

    if ek_client:
        from claw_ea.tools.calendar import register as reg_calendar
        from claw_ea.tools.reminder import register as reg_reminder
        reg_calendar(mcp, config, ek_client)
        reg_reminder(mcp, config, ek_client)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
