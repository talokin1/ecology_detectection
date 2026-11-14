"""The pipeline lock works on Linux/macOS and Windows: a second holder is refused, then let in."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from file_lock import lock  # noqa: E402


def test_second_holder_is_refused_until_release(tmp_path):
    path = tmp_path / "run.lock"
    first = path.open("a")
    lock(first, blocking=False)
    second = path.open("a")
    with pytest.raises(BlockingIOError):
        lock(second, blocking=False)
    first.close()  # releases the lock
    lock(second, blocking=False)
    second.close()
