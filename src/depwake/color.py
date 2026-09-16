"""Terminal colors without dependencies. Respects NO_COLOR and pipes.

Rule: color only when the user sees it (TTY) unless forced. CI logs and
redirects stay clean — a green test suite must never print escapes.
"""

from __future__ import annotations

import os
import sys

CODES = {
    "red": "\033[31m",
    "yellow": "\033[33m",
    "green": "\033[32m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}

RISK_COLORS = {"major": "red", "minor": "yellow", "patch": "green",
               "same": "green", "unknown": "dim"}


def enabled(mode: str = "auto") -> bool:
    """mode: auto | always | never."""
    if mode == "always":
        return True
    if mode == "never":
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    try:
        return sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def paint(text: str, color: str, on: bool) -> str:
    if not on or color not in CODES:
        return text
    return f"{CODES[color]}{text}{CODES['reset']}"
