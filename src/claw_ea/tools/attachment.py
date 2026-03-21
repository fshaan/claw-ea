import base64
from datetime import date
from pathlib import Path

from claw_ea.config import Config


def save_attachment_impl(
    file_content: str, filename: str, subfolder: str, config: Config
) -> dict:
    """Core logic for save_attachment. Separate from MCP registration for testability."""
    try:
        data = base64.b64decode(file_content, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 content: {e}") from e

    target_dir = config.attachments_path
    if config.organize_by_date:
        today = date.today()
        target_dir = target_dir / f"{today.year}" / f"{today.month:02d}" / f"{today.day:02d}"
    if subfolder:
        target_dir = target_dir / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename: strip path separators and parent references
    safe_name = Path(filename).name  # removes any directory components
    if not safe_name or safe_name in (".", ".."):
        raise ValueError(f"Invalid filename: {filename}")
    target_file = target_dir / safe_name

    # Verify resolved path stays within attachments directory
    if not target_file.resolve().is_relative_to(config.attachments_path.resolve()):
        raise ValueError(f"Path traversal detected in filename: {filename}")

    if target_file.exists() and target_file.read_bytes() == data:
        return {"saved_path": str(target_file), "already_existed": True}

    if target_file.exists():
        stem = target_file.stem
        suffix = target_file.suffix
        counter = 1
        while target_file.exists():
            target_file = target_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    target_file.write_bytes(data)
    return {"saved_path": str(target_file), "already_existed": False}


def register(mcp_instance, config: Config):
    """Register save_attachment tool with the MCP server."""

    @mcp_instance.tool()
    async def save_attachment(
        file_content: str, filename: str, subfolder: str = ""
    ) -> dict:
        """Save a file to the attachments directory, organized by date.

        Args:
            file_content: Base64-encoded file content
            filename: Original filename (e.g. "手术通知_张三.pdf")
            subfolder: Optional subdirectory within the date folder

        Returns:
            saved_path: Absolute path where the file was saved
            already_existed: True if an identical file was already present
        """
        return save_attachment_impl(file_content, filename, subfolder, config)
