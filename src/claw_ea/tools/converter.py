"""convert_to_markdown MCP tool — convert files to Markdown via configurable converter chains."""

from pathlib import Path

from claw_ea.config import Config
from claw_ea.converters import dispatch


def convert_to_markdown_impl(file_path: str, config: Config) -> dict:
    """Core logic for convert_to_markdown."""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        result = dispatch(path, config)
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
    async def convert_to_markdown(file_path: str) -> dict:
        """Convert a file to Markdown and save as a temp file.

        File-type routing (the agent decides which path to take):
        - Images / PDF: prefer reading them DIRECTLY with the agent's own multimodal
          vision — summarize the core content and write it into the note, with the
          original file kept as an embedded attachment (![[file]]). Only call this
          tool for images/PDF as a fallback when the agent lacks vision.
        - Office docs (.docx, .pptx, .xlsx): call this tool — MinerU is the default
          converter for offline, local conversion (docling fallback).
        - .csv / .html: call this tool — these route to markitdown / docling
          (MinerU does not handle them), so converter_used won't be "mineru".
        - Other file types: the agent picks the best extraction approach, but the
          original file must still be archived via save_attachment.
        For PPT files: read the converted markdown, summarize it, then pass the
        summary to create_obsidian_note via content_data (do NOT use raw_body_path for PPT).

        Supports: PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), CSV, HTML, images, plaintext.
        Automatically detects file type and selects the best converter chain.
        Result is written to a temp file (not returned as string) to avoid
        large text consuming agent context tokens.

        Args:
            file_path: Path to the file to convert.

        Returns:
            md_path: Path to the converted Markdown temp file.
                     Pass this to create_obsidian_note's raw_body_path parameter.
            converter_used: Name of the converter that produced the result.
            fallback_used: Whether a fallback converter was used.
        """
        return convert_to_markdown_impl(file_path, config)
