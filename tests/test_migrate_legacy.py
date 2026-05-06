"""Tests for scripts/migrate_legacy_inbox.py — legacy note detection logic."""

import pytest
import yaml
from pathlib import Path

# Import from the migration script
import importlib.util
import sys

spec = importlib.util.spec_from_file_location(
    "migrate_legacy", "scripts/migrate_legacy_inbox.py"
)
migrate = importlib.util.module_from_spec(spec)
sys.modules["migrate_legacy"] = migrate
spec.loader.exec_module(migrate)


class TestStripMarkdown:
    def test_strips_headings(self):
        # # markers removed, but heading text stays (it's real content)
        result = migrate.strip_markdown("# Title\n\ncontent")
        assert "content" in result
        assert not result.startswith("#")

    def test_strips_wikilinks(self):
        result = migrate.strip_markdown("See [[note name]] for details")
        assert "See" in result
        assert "for details" in result
        assert "[[note name]]" not in result
        result2 = migrate.strip_markdown("[[a]] and [[b]]")
        assert "and" in result2
        assert "[[" not in result2

    def test_strips_comments(self):
        assert migrate.strip_markdown("text <!-- hidden --> more") == "text  more"
        assert migrate.strip_markdown("<!--\nmultiline\ncomment\n-->ok") == "ok"

    def test_strips_blockquotes(self):
        assert migrate.strip_markdown("> quoted text") == "quoted text"

    def test_strips_bold_italic(self):
        result = migrate.strip_markdown("**bold** and *italic*")
        assert "bold" not in result
        assert "italic" not in result

    def test_returns_stripped_empty_for_template_only(self):
        """Template-rendered body with no real content → effectively empty."""
        body = "## 备注\n（待补充）\n"
        result = migrate.strip_markdown(body)
        assert len(result) < 50


class TestIsLegacy:
    def test_empty_body_no_attachments(self):
        assert migrate.is_legacy({}, "\n") == (True, "empty_body (0 chars)")

    def test_short_body_no_attachments(self):
        assert migrate.is_legacy({}, "ok") == (True, "empty_body (2 chars)")

    def test_full_body_not_legacy(self):
        fm = {}
        body = "This is a full note with substantial content " * 5
        assert migrate.is_legacy(fm, body) == (False, "")

    def test_empty_body_with_attachments_not_legacy(self):
        """Even if body is empty, attachments mean the file has value."""
        fm = {"attachments": ["手术通知.pdf"]}
        assert migrate.is_legacy(fm, "") == (False, "")

    def test_template_only_body_is_legacy(self):
        """Template placeholder body with no real content."""
        body = "## 备注\n（待补充）\n"
        is_legacy, reason = migrate.is_legacy({}, body)
        assert is_legacy is True
        assert "empty_body" in reason

    def test_boundary_49_chars(self):
        body = "x" * 49
        assert migrate.is_legacy({}, body) == (True, f"empty_body ({49} chars)")

    def test_boundary_50_chars(self):
        body = "x" * 50
        assert migrate.is_legacy({}, body) == (False, "")

    def test_whitespace_only_is_empty(self):
        assert migrate.is_legacy({}, "   \n  \t  \n") == (True, "empty_body (0 chars)")


class TestParseNote:
    def test_parses_frontmatter_and_body(self):
        content = "---\ntype: document\ncategory: meeting\n---\n# Title\n\nBody text"
        fm, fm_raw, body = migrate.parse_note(content)
        assert fm["type"] == "document"
        assert fm["category"] == "meeting"
        assert "# Title" in body
        assert "Body text" in body

    def test_no_frontmatter(self):
        content = "# Just a heading\n\nContent"
        fm, fm_raw, body = migrate.parse_note(content)
        assert fm == {}
        assert body == content


class TestEndToEndDryRun:
    """Integration test: create a fake inbox, run migration dry-run, verify results."""

    def test_dry_run_migrates_legacy_notes(self, tmp_path, monkeypatch):
        # Create fake vault structure
        vault = tmp_path / "vault"
        inbox = vault / "Inbox" / "OpenClaw"
        inbox.mkdir(parents=True)

        # Create a legacy note (near-empty body, no attachments)
        legacy = inbox / "2026-01-01-meeting-abc12345.md"
        legacy.write_text(
            "---\ntype: meeting_minutes\ncategory: meeting\ntitle: Test\n---\n"
            "## 备注\n（待补充）\n",
            encoding="utf-8",
        )

        # Create a good note (has real content)
        good = inbox / "2026-01-02-document-def67890.md"
        good.write_text(
            "---\ntype: document\ncategory: document\ntitle: Real Doc\nattachments: [file.pdf]\n---\n"
            + "substantial content " * 20,
            encoding="utf-8",
        )

        # Run migration on each file
        legacy_dir = inbox / "_legacy"

        # Legacy file should be detected
        status1 = migrate.migrate_file(legacy, legacy_dir, apply=False)
        assert status1.startswith("migrate (dry-run)")

        # Good file should be skipped
        status2 = migrate.migrate_file(good, legacy_dir, apply=False)
        assert status2 == "skip"

    def test_apply_migrates_file(self, tmp_path):
        vault = tmp_path / "vault"
        inbox = vault / "Inbox" / "OpenClaw"
        inbox.mkdir(parents=True)

        note = inbox / "2026-01-01-meeting-abc12345.md"
        note.write_text(
            "---\ntype: meeting_minutes\ncategory: meeting\ntitle: Test\n---\n"
            "## 备注\n（待补充）\n",
            encoding="utf-8",
        )

        legacy_dir = inbox / "_legacy"
        status = migrate.migrate_file(note, legacy_dir, apply=True)
        assert status.startswith("migrated")

        # File should have moved
        assert not note.exists()
        moved = legacy_dir / "2026-01-01-meeting-abc12345.md"
        assert moved.exists()

        # Frontmatter should have legacy fields
        content = moved.read_text(encoding="utf-8")
        fm, _, _ = migrate.parse_note(content)
        assert fm["legacy"] is True
        assert "empty_body" in fm["legacy_reason"]
