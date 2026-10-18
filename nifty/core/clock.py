"""
nifty.core.clock
===========

Two halves of the same idea -- time.

IST display: the tape's epochs are UTC; every label the sheet shows is IST
(UTC+05:30). The offset is applied by addition, never by a local timezone, so the
output does not depend on the machine's locale or zone.

Timeframe arithmetic: which bucket a tick belongs to, and how a bar width is
written, parsed and named. The widths the pipeline uses are whole seconds, and the
IST offset divides exactly by every one of them, so flooring the raw epoch aligns
buckets to the IST clock rather than to a UTC boundary.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

IST_OFFSET_SECONDS = 19800          # UTC+05:30, display only

_UNIT_SECONDS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hour": 3600, "hours": 3600,
}
_WIDTH = re.compile(r"^(\d+(?:\.\d+)?)\s*([a-z]*)$")


# --------------------------------------------------------------------------------------
# IST display
# --------------------------------------------------------------------------------------

def ist_datetime(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch + IST_OFFSET_SECONDS, tz=timezone.utc)


def ist_label(epoch: int, with_seconds: bool = False) -> str:
    return ist_datetime(epoch).strftime("%H:%M:%S" if with_seconds else "%H:%M")


def ist_full(epoch: int) -> str:
    return ist_datetime(epoch).strftime("%Y-%m-%d %H:%M:%S")


def ist_date(epoch: int) -> str:
    return ist_datetime(epoch).strftime("%Y-%m-%d")


def clock_seconds(text: str) -> int:
    """'HH:MM:SS' (or 'HH:MM') as seconds after midnight, for comparing two clock times."""
    parts = [int(part) for part in text.split(":")]
    hours, minutes, seconds = (parts + [0, 0])[:3]
    return hours * 3600 + minutes * 60 + seconds


def ist_clock(epoch: int) -> int:
    """The IST wall-clock time of an epoch, in seconds after IST midnight.

    The trade clock in `nifty/trade/backtest.py` reads this: a bar's `time` is an epoch, and a
    rule like "no entry after 15:10" is a comparison of wall-clock times, not of epochs.
    """
    return (epoch + IST_OFFSET_SECONDS) % 86400


# --------------------------------------------------------------------------------------
# Timeframes
# --------------------------------------------------------------------------------------

def tf_label(seconds: int) -> str:
    """The tab's long name: '12 sec', '5 min'."""
    return f"{seconds} sec" if seconds < 60 else f"{seconds // 60} min"


def tf_short(seconds: int) -> str:
    """The tab's short name: '12s', '5m'."""
    return f"{seconds}s" if seconds < 60 else f"{seconds // 60}m"


def tf_slug(seconds: int) -> str:
    """The name an export file is given: '12sec', '5min'."""
    return f"{seconds}sec" if seconds < 60 else f"{seconds // 60}min"


def parse_timeframe(value: object) -> int:
    """One bar width, as a recipe may write it: 12, '12s', '1m', '5 minutes', '0.5m'.

    Raises ValueError with the offending text, so the config layer can report which
    key it came from.
    """
    if isinstance(value, bool):
        raise ValueError(f"{value!r} is not a bar width")
    if isinstance(value, int):
        seconds = value
    elif isinstance(value, float):
        seconds = int(round(value))
    else:
        match = _WIDTH.match(str(value).strip().lower())
        if not match:
            raise ValueError(f"{value!r} is not a bar width -- try 12, '12s' or '1m'")
        amount, unit = float(match.group(1)), match.group(2) or "s"
        if unit not in _UNIT_SECONDS:
            raise ValueError(f"unknown unit {unit!r} in {value!r}")
        seconds = int(round(amount * _UNIT_SECONDS[unit]))
    if seconds <= 0:
        raise ValueError(f"a bar width must be positive, got {value!r}")
    return seconds


def parse_timeframes(values: object) -> tuple[int, ...]:
    """A whole list of bar widths, kept in the order given and checked for collisions."""
    if isinstance(values, (int, float, str)):
        values = [values]
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"expected a list of bar widths, got {values!r}")
    widths = tuple(parse_timeframe(v) for v in values)
    if not widths:
        raise ValueError("at least one timeframe is required")
    if len(set(widths)) != len(widths):
        raise ValueError(f"duplicate bar widths in {list(widths)}")
    return widths


def bucket_key(epoch: int, seconds: int) -> int:
    """The wall-clock IST boundary a tick belongs to."""
    return epoch - (epoch % seconds)
