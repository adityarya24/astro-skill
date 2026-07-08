"""Serialize access to the process-global Swiss Ephemeris state.

``pyswisseph`` keeps state at the process level — the sidereal/ayanamsa mode set
by ``swe.set_sid_mode``, the ephemeris path, and internal caches. It is **not**
thread-safe. The astro MCP server runs each tool in a worker thread
(``asyncio.to_thread``), so two concurrent ``calculate_kundali`` /
``calculate_panchang`` calls could interleave ``set_sid_mode`` and ``calc_ut``
and corrupt each other's results.

Every computation that touches ``swisseph`` must run under ``SWE_LOCK``. Use the
``serialized`` decorator on the top-level calculation entry points; the calls are
fast (a few milliseconds), so coarse serialization is correct and cheap.
"""
from __future__ import annotations

import functools
import threading
from typing import Callable, TypeVar

SWE_LOCK = threading.RLock()

_T = TypeVar("_T")


def serialized(fn: Callable[..., _T]) -> Callable[..., _T]:
    """Run ``fn`` while holding the global Swiss Ephemeris lock."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs) -> _T:
        with SWE_LOCK:
            return fn(*args, **kwargs)

    return wrapper
