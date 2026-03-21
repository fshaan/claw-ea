import base64
import hashlib
import shutil
from datetime import date
from pathlib import Path

from claw_ea.config import Config


def _file_hash(path: Path) -> str:
    """SHA256 hash of file, read in chunks to handle large files."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def save_attachment_impl(
    config: Config,
    file_content: str | None = None,
    filename: str | None = None,
    subfolder: str = "",
    file_path: str | None = None,
) -> dict:
    """Core logic for save_attachment.

    Two modes:
    - file_content (base64): decode and write. filename required.
    - file_path (local path): copy file directly. filename derived from path if not provided.
    """
    # --- Mutual exclusion ---
    if file_content and file_path:
        raise ValueError("file_content and file_path are mutually exclusive — provide one, not both")
    if not file_content and not file_path:
        raise ValueError("Either file_content or file_path must be provided")

    # --- Resolve source ---
    source_path: Path | None = None

    if file_path:
        source_path = Path(file_path).resolve()
        if not source_path.is_file():
            raise ValueError(f"Source file not found: {file_path}")
        if filename is None:
            filename = source_path.name
    else:
        # base64 mode — filename is required
        if not filename:
            raise ValueError("filename is required when using file_content (base64) mode")
        try:
            data = base64.b64decode(file_content, validate=True)
        except Exception as e:
            raise ValueError(f"Invalid base64 content: {e}") from e

    # --- Build target path ---
    target_dir = config.attachments_path
    if config.organize_by_date:
        today = date.today()
        target_dir = target_dir / f"{today.year}" / f"{today.month:02d}" / f"{today.day:02d}"
    if subfolder:
        target_dir = target_dir / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = Path(filename).name
    if not safe_name or safe_name in (".", ".."):
        raise ValueError(f"Invalid filename: {filename}")
    target_file = target_dir / safe_name

    # Verify resolved path stays within attachments directory
    if not target_file.resolve().is_relative_to(config.attachments_path.resolve()):
        raise ValueError(f"Path traversal detected in filename: {filename}")

    # --- Dedup check ---
    if target_file.exists():
        if source_path:
            # file_path mode: compare size first (fast), then hash
            if (target_file.stat().st_size == source_path.stat().st_size
                    and _file_hash(target_file) == _file_hash(source_path)):
                return {"saved_path": str(target_file), "already_existed": True}
        else:
            # base64 mode: compare bytes directly (already in memory)
            if target_file.read_bytes() == data:
                return {"saved_path": str(target_file), "already_existed": True}

    # --- Collision handling ---
    if target_file.exists():
        stem = target_file.stem
        suffix = target_file.suffix
        counter = 1
        while target_file.exists():
            target_file = target_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    # --- Write/copy ---
    if source_path:
        shutil.copy2(source_path, target_file)
    else:
        target_file.write_bytes(data)

    return {"saved_path": str(target_file), "already_existed": False}


def register(mcp_instance, config: Config):
    """Register save_attachment tool with the MCP server."""

    @mcp_instance.tool()
    async def save_attachment(
        file_content: str = "", filename: str = "",
        subfolder: str = "", file_path: str = "",
    ) -> dict:
        """Save a file to the attachments directory, organized by date.

        Two modes (mutually exclusive):
        - file_content: Base64-encoded file content (filename required)
        - file_path: Local file path to copy directly (filename optional, derived from path)

        Args:
            file_content: Base64-encoded file content
            file_path: Local file path (e.g. "/tmp/openclaw/media/手术通知.pdf")
            filename: Original filename. Required for file_content, optional for file_path.
            subfolder: Optional subdirectory within the date folder

        Returns:
            saved_path: Absolute path where the file was saved
            already_existed: True if an identical file was already present
        """
        return save_attachment_impl(
            config,
            file_content=file_content or None,
            filename=filename or None,
            subfolder=subfolder,
            file_path=file_path or None,
        )
