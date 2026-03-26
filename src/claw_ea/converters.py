"""Markdown-first content pipeline: converter dispatch, routing, and quality check."""

import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConversionResult:
    """Result of a file-to-markdown conversion."""
    temp_path: str
    source_path: str
    converter_used: str
    fallback_used: bool


def is_usable(markdown: str) -> bool:
    """Check if converted markdown is usable (not empty, not garbled).

    Returns True if:
    - Non-empty and non-whitespace-only
    - At least 80% of non-newline characters are valid
      (not in Unicode categories Cc, Cs, Co — control, surrogate, private-use)
    """
    stripped = markdown.strip()
    if not stripped:
        return False

    total = 0
    invalid = 0
    for ch in stripped:
        if ch == "\n":
            continue
        total += 1
        cat = unicodedata.category(ch)
        if cat.startswith(("Cc", "Cs", "Co")):
            invalid += 1

    if total == 0:
        return False

    valid_ratio = (total - invalid) / total
    return valid_ratio >= 0.80
