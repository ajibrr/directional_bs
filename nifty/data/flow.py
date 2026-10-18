"""
nifty.data.flow
==========

The dashboard's minute-by-minute options flow, and the one place a session's two file
suffixes are named.

    input data/NIFTY_<date>_DASHBOARD.json
        {"flow": [{"time": "09:15:00", "timestamp": "2026-10-16 09:15:00",
                   "nifty": 23065.1, "ce_oi_change": 0, "pe_oi_change": 0,
                   "cumulative_ce": 0, "cumulative_pe": 0}, ...],
         "nifty_seconds": [{"timestamp": "2026-10-16 09:15:00",
                            "timestamp_epoch": 1792122300, "nifty": 23065.1,
                            "atm": 23050}, ...]}

The per-minute change is the column the sheet draws; the cumulative totals the same
rows also carry are left where they are.

    load_flow   -> [{'time': epoch, 'ceOIChange': int, 'peOIChange': int}, ...]
    attach_flow -> the same two columns on every bar, keyed by the minute it opens in

The dashboard is the feed's own summary of one session: a row per minute carrying both
the minute's call and put open-interest change and the running totals accumulated so
far. The chart draws the two per-minute change columns, read as they stand -- nothing
here sums, differences or smooths anything, so the chart plots exactly the numbers the
feed published. A change may be negative, so the chart reads against its zero line.

The tape has no such column, so this is the second input a session may bring -- and a
session without one simply carries no flow rows, which the sheet shows by hiding the
chart rather than drawing an empty one.

The same file also carries the session's per-second price series (`nifty_seconds`), which
`nifty.data.bars` reads as the tape when a session ships no `.jsonl` beside it. This module owns
the suffix constants both readers share: `tape_path()` and `dashboard_path()` are the two
halves of one pairing, so a session is named once and the same name finds either file.

Timestamps arrive as IST wall clock and are converted to the same UTC epoch the bars
carry, so the flow chart and the price charts read one time axis. A repeated minute
keeps its last row: the chart needs strictly increasing times.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..core.clock import IST_OFFSET_SECONDS
from ..core.errors import DataError
from ..core.keys import CE_OI_CHANGE, PE_OI_CHANGE

DASHBOARD_SUFFIX = "_DASHBOARD.json"
TAPE_SUFFIX = "_PRICE_1SEC.jsonl"


def dashboard_glob(tape_glob: str) -> str | None:
    """The dashboard pattern that goes with a tape pattern: the same name, other suffix.

    One recipe key names the sessions, so the dashboard pattern is derived rather than
    configured twice -- and a glob that does not name tapes has no dashboard twin, which
    is why this returns None instead of guessing one.
    """
    if not tape_glob.endswith(TAPE_SUFFIX):
        return None
    return tape_glob[:-len(TAPE_SUFFIX)] + DASHBOARD_SUFFIX


def tape_path(src: Path) -> Path:
    """The tape that belongs beside a session's dashboard (the tape itself if already one)."""
    if src.name.endswith(DASHBOARD_SUFFIX):
        return src.with_name(src.name[:-len(DASHBOARD_SUFFIX)] + TAPE_SUFFIX)
    return src


def dashboard_path(src: Path) -> Path:
    """The dashboard that belongs beside a session's tape (the dashboard itself if already one)."""
    if src.name.endswith(DASHBOARD_SUFFIX):
        return src
    if src.name.endswith(TAPE_SUFFIX):
        return src.with_name(src.name[:-len(TAPE_SUFFIX)] + DASHBOARD_SUFFIX)
    return src.with_name(src.name + DASHBOARD_SUFFIX)


def ist_epoch(text: str) -> int:
    """A dashboard timestamp ('2026-10-16 09:15:00', IST) as a UTC epoch."""
    stamp = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    ist = stamp.replace(tzinfo=timezone(timedelta(seconds=IST_OFFSET_SECONDS)))
    return int(ist.timestamp())


def load_flow(src: Path) -> list[dict]:
    """One session's dashboard as chart points, chronological, one per minute."""
    path = dashboard_path(src)
    if not path.is_file():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"{path} could not be read: {exc}") from exc
    rows = doc.get("flow") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        raise DataError(f"{path} has no 'flow' list")

    points: dict[int, dict] = {}
    for lineno, row in enumerate(rows, 1):
        try:
            epoch = ist_epoch(row["timestamp"])
            # the feed's own per-minute columns, copied as-is: the sheet plots them
            points[epoch] = {"time": epoch,
                             "ceOIChange": int(row["ce_oi_change"]),
                             "peOIChange": int(row["pe_oi_change"])}
        except (KeyError, TypeError, ValueError) as exc:
            raise DataError(f"{path}: flow row {lineno} missing/unusable field: {exc}") from exc
    return [points[epoch] for epoch in sorted(points)]


def attach_flow(bars: list[dict], flow: list[dict]) -> None:
    """Give every bar the dashboard row of the minute it opens in, in place.

    The dashboard publishes one row per minute; a timeframe publishes one bar per 12
    seconds and up, so a bar reads the minute its own **open** falls in (`time - time %
    60`) and every bar of that minute reads the same row -- no averaging, no summing, no
    interpolation between two minutes. A bar whose minute has no row keeps None, and a
    session with no dashboard at all keeps None on every bar, which is what the arrow
    rules read as "this session does not read the flow condition" rather than as a zero.
    """
    by_minute = {row["time"] // 60: row for row in flow}
    for bar in bars:
        row = by_minute.get(bar["time"] // 60)
        bar[CE_OI_CHANGE] = None if row is None else row["ceOIChange"]
        bar[PE_OI_CHANGE] = None if row is None else row["peOIChange"]
