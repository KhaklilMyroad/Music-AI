"""Printing that cannot crash. A Windows console or a pipe often cannot encode Hebrew or accented names (a folder
called after its owner, a stem called "תופים"); Python then raises on print. Commands call safe_output() first."""
from __future__ import annotations

import sys


def safe_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None and hasattr(stream, "reconfigure"):
                # a pipe (how an assistant runs commands) gets UTF-8; a console keeps its own encoding, and what it
                # cannot show becomes "?" instead of an exception
                if stream.isatty():
                    stream.reconfigure(errors="replace")
                else:
                    stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
