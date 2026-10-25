"""Console output helpers.

Progress markers such as "✓" or "✗" cannot be encoded by legacy Windows code
pages (cp1252 and friends). Writing them raises UnicodeEncodeError, which
aborted the clone stage and marked otherwise successful runs as failed.
"""

import sys
from typing import Any


def configure_console() -> None:
    """Make stdout/stderr tolerant of characters the console encoding cannot represent."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except Exception:
            # pytest replaces stdout with a stream that refuses reconfiguration,
            # and some hosts expose a stream without the method at all.
            continue


def safe_print(*args: Any, **kwargs: Any) -> None:
    """Print without ever raising on an encoding mismatch."""

    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        stream = kwargs.get("file") or sys.stdout
        encoding = getattr(stream, "encoding", None) or "ascii"
        fallback = [
            str(a).encode(encoding, errors="replace").decode(encoding, errors="replace")
            for a in args
        ]
        try:
            print(*fallback, **kwargs)
        except Exception:
            pass
