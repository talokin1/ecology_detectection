"""Exclusive advisory lock on an open file, on Linux/macOS (fcntl.flock) and Windows (msvcrt.locking).

Used by the pipeline loader and daemon so two runs never overlap. The lock is released when the file
is closed or the process exits. ``lock(fh, blocking=False)`` raises ``BlockingIOError`` if another
process holds it, on every platform.

SI-assisted (Claude, Anthropic); pending team review (see docs/08-si-usage-log.md).
"""

from __future__ import annotations

import os
import time
from typing import IO

if os.name == "nt":
    import msvcrt

    def lock(fh: IO, blocking: bool = True, poll_seconds: float = 1.0) -> None:
        """Lock the first byte of ``fh`` (Windows locks byte ranges; past EOF is allowed)."""
        fh.seek(0)
        while True:
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError as exc:  # held by another process
                if not blocking:
                    raise BlockingIOError(f"lock held by another process: {fh.name}") from exc
                time.sleep(poll_seconds)

else:
    import fcntl

    def lock(fh: IO, blocking: bool = True, poll_seconds: float = 1.0) -> None:  # noqa: ARG001
        """``flock`` the whole file (``poll_seconds`` is unused: flock blocks natively)."""
        fcntl.flock(fh, fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB)
