"""Markdown cell / inline-fragment cleaning helpers.

The OpenCode docs mix plain markdown, MDX, HTML fragments (`<br />`,
`<small>`) and emphasis markers. Parsers want the *value*, while the
promo parser additionally wants the *crossed-out* value. We therefore keep
both a "clean" and a "raw" view of every cell.
"""

from __future__ import annotations

import re

_HTML_TAG = re.compile(r"<[^>]+>")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_STRIKE = re.compile(r"~~(.+?)~~")


def strip_html(text: str) -> str:
    """Drop HTML fragments and collapse the whitespace they introduce."""
    return re.sub(r"\s+", " ", _HTML_TAG.sub(" ", text)).strip()


def clean(text: str) -> str:
    """Reduce a markdown cell to its human-readable value.

    Strikethrough content is *kept* here because it often carries the only
    occurrence of a value in prose; callers that need to distinguish it
    (limits, requests) parse the raw cell instead.
    """
    text = strip_html(text)
    text = _LINK.sub(r"\1", text)
    text = _INLINE_CODE.sub(r"\1", text)
    text = _BOLD.sub(r"\1", text)
    text = _STRIKE.sub(r"\1", text)
    text = _ITALIC.sub(r"\1", text)
    return text.strip()


def clean_keep_emphasis(text: str) -> str:
    """Like :func:`clean` but keeps `**bold**` / `~~struck~~` markers."""
    return strip_html(text).strip()


def parse_number(text: str) -> float | None:
    """Parse a currency or plain number cell; ``-`` and blanks give None."""
    text = strip_html(text)
    text = _STRIKE.sub("", text)
    text = _BOLD.sub(r"\1", text)
    text = text.replace(",", "").replace("$", "").strip()
    if text in ("", "-", "—", "n/a", "N/A"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(text: str) -> int | None:
    value = parse_number(text)
    return None if value is None else int(value)
