from mcp.server.fastmcp import FastMCP
from claw_ea.config import load_config, ConfigError

mcp = FastMCP("claw-ea", json_response=True)


def main():
    """Entry point for the MCP server."""
    try:
        config = load_config()
    except ConfigError as e:
        import sys
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Register Slice 1 tools (attachment + obsidian)
    from claw_ea.tools.attachment import register as reg_attachment
    from claw_ea.tools.obsidian import register as reg_obsidian

    reg_attachment(mcp, config)
    reg_obsidian(mcp, config)

    mcp.run(transport="stdio")
