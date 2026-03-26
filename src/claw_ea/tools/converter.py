"""convert_to_markdown MCP tool — convert files to Markdown via configurable converter chains."""

from pathlib import Path

from claw_ea.config import Config
from claw_ea.converters import dispatch


def convert_to_markdown_impl(file_path: str, hint: str, config: Config) -> dict:
    """Core logic for convert_to_markdown."""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        result = dispatch(path, config, hint=hint)
    except (ValueError, RuntimeError) as e:
        return {"error": str(e)}

    return {
        "md_path": result.temp_path,
        "converter_used": result.converter_used,
        "fallback_used": result.fallback_used,
    }


def register(mcp_instance, config: Config):
    """Register convert_to_markdown tool with the MCP server."""

    @mcp_instance.tool()
    async def convert_to_markdown(file_path: str, hint: str = "") -> dict:
        """Convert a file to Markdown and save as a temp file.

        IMPORTANT: MUST be called for ALL files (including text) before creating Obsidian notes.
        For PPT files: agent should read the converted markdown, summarize it, then pass the
        summary to create_obsidian_note via content_data (do NOT use raw_body_path for PPT).

        Supports: PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), CSV, HTML, images, plaintext.
        Automatically detects file type and selects the best converter.
        Result is written to a temp file (not returned as string) to avoid
        large text consuming agent context tokens.

        Args:
            file_path: Path to the file to convert.
            hint: Optional type hint to select a specialized converter chain.
                  For example, "academic" for academic PDF papers (uses MinerU).
                  Omit to use the default chain for the file extension.

        Returns:
            md_path: Path to the converted Markdown temp file.
                     Pass this to create_obsidian_note's raw_body_path parameter.
            converter_used: Name of the converter that produced the result.
            fallback_used: Whether a fallback converter was used.
        """
        return convert_to_markdown_impl(file_path, hint, config)
