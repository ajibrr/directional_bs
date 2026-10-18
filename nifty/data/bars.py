"""
nifty.data.bars
==========

The session in, price bars out.

    input data/NIFTY_<date>_PRICE_1SEC.jsonl        either one per session ...
        {"timestamp": "2026-10-15 09:15:00", "timestamp_epoch": 1792035900,
         "nifty": 22671.3, "atm": 22650}

    input data/NIFTY_<date>_DASHBOARD.json          ... or the dashboard alone, whose
        {"nifty_seconds": [{"timestamp": "2026-10-15 09:15:00",     `nifty_seconds`
                            "timestamp_epoch": 1792035900,          carries the same
                            "nifty": 22671.3, "atm": 22650}, ...]}  per-second series

    discover_sources -> [session file, ...]  (one per session; the tape wins when both exist)
    load_ticks       -> [{'epoch', 'nifty', 'atm'}, ...]  (chronological)
    bucket_ohlc      -> [{'time', 'open', 'high', 'low', 'close', 'atm', 'ticks'}, ...]

A session is the tape, or -- when it ships no tape -- its dashboard's own per-second
series: the same `timestamp_epoch` / `nifty` / `atm` triple, one row per second, so one
reader covers both and a `ticks` count means the same thing either way. The two are
paired by filename, and the tape is preferred whenever it is there: it runs to the last
second of the closing minute, while the dashboard's series stops when the feed stops.

A bucket's open is the first tick seen, its close the last, high/low the extremes,
`ticks` how many samples landed in it and `atm` the strike the tape spent most of the
bucket at (ties broken by first appearance). Everything is rounded to the shipped
price precision here and nowhere else, so one bar object is the whole truth about a
candle.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ..core.clock import bucket_key
from ..core.errors import DataError
from ..core.numeric import r2
from .flow import DASHBOARD_SUFFIX, dashboard_glob, tape_path

# the two feeds this tool reads, and the field each names its index level with. The
# internal tick/bar field stays `nifty` for both -- one schema downstream, not two.
SECONDS_KEYS = ("nifty_seconds", "sensex_seconds")
PRICE_KEYS = ("nifty", "sensex")


def discover_sources(sources_dir: Path, glob: str) -> list[Path]:
    """Every session in `sources_dir`, one file each, earliest session first.

    The tapes matching `glob` are the sessions; a dashboard whose tape is absent is a
    session too, read from its own per-second series. A dashboard that does sit beside a
    tape is not listed twice -- the tape is the fuller record, so it wins -- which is why
    a folder holding both kinds builds the same session it always did.

    Sorting is by the date embedded in the filename, so the sheet's day tabs read
    chronologically no matter what order the filesystem hands the files back.
    """
    if not sources_dir.is_dir():
        raise DataError(f"no such input directory: {sources_dir}")
    tapes = sorted(sources_dir.glob(glob))
    files = list(tapes)
    dashboards = dashboard_glob(glob)
    if dashboards:
        known = {p.name for p in tapes}
        files += sorted(d for d in sources_dir.glob(dashboards)
                        if tape_path(d).name not in known)
    if not files:
        wanted = f"{glob} (or {dashboards})" if dashboards else glob
        raise DataError(f"no {wanted} files found in {sources_dir}")
    return sorted(files, key=lambda p: p.name)


def price_of(record: dict) -> float:
    """The index level in one row, whichever name the feed gave it.

    A NIFTY feed keys its price `nifty`, a SENSEX feed `sensex`; both are the index level
    the bars are made of, so the reader accepts either rather than each index needing its
    own copy of the pipeline. The value is stored internally under the one name every
    later step spells -- `nifty` -- because that is the column the schema already gives.
    """
    for key in PRICE_KEYS:
        if key in record:
            return float(record[key])
    raise KeyError(f"none of {PRICE_KEYS} is present")


def load_ticks(path: Path) -> list[dict]:
    """One session file as a chronological list of ticks.

    A dashboard is read from its own per-second series (`nifty_seconds` for NIFTY,
    `sensex_seconds` for SENSEX) instead of from lines: one row per second carrying the
    same three fields, so nothing downstream can tell which file or which index the
    session came from.
    """
    if path.name.endswith(DASHBOARD_SUFFIX):
        return _dashboard_ticks(path)
    ticks: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise DataError(f"{path}:{lineno} invalid JSON: {exc}") from exc
            try:
                ticks.append({"epoch": int(rec["timestamp_epoch"]),
                              "nifty": price_of(rec),
                              "atm": int(rec["atm"])})
            except (KeyError, TypeError, ValueError) as exc:
                raise DataError(f"{path}:{lineno} missing/unusable field: {exc}") from exc
    ticks.sort(key=lambda t: t["epoch"])
    return ticks


def _dashboard_ticks(path: Path) -> list[dict]:
    """A dashboard's own per-second series, as the ticks a tape would have given.

    The series key names the index (`nifty_seconds` / `sensex_seconds`), so the reader
    takes whichever the file carries and the row's price through `price_of`. The series
    is stamped in IST wall clock like the tape's lines and carries the same
    `timestamp_epoch`, so it is read as the epoch directly rather than through the clock
    labels. A repeated second keeps both rows, exactly as the tape's reader keeps both
    lines: deduplicating here would quietly hide a feed that sent one twice.
    """
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError(f"{path} could not be read: {exc}") from exc
    series_key, rows = None, None
    if isinstance(doc, dict):
        for candidate in SECONDS_KEYS:
            if isinstance(doc.get(candidate), list):
                series_key, rows = candidate, doc[candidate]
                break
    if series_key is None:
        raise DataError(f"{path} has no {SECONDS_KEYS[0]!r} / {SECONDS_KEYS[1]!r} list")
    ticks: list[dict] = []
    for lineno, rec in enumerate(rows, 1):
        try:
            ticks.append({"epoch": int(rec["timestamp_epoch"]),
                          "nifty": price_of(rec),
                          "atm": int(rec["atm"])})
        except (KeyError, TypeError, ValueError) as exc:
            raise DataError(f"{path}: {series_key} row {lineno} missing/unusable field: "
                            f"{exc}") from exc
    if not ticks:
        raise DataError(f"{path} has an empty {series_key!r} list")
    ticks.sort(key=lambda t: t["epoch"])
    return ticks


def bucket_ohlc(ticks: list[dict], seconds: int) -> list[dict]:
    """Aggregate ticks into OHLC bars aligned to wall-clock IST boundaries."""
    bars: list[dict] = []
    current_key: int | None = None
    buf: list[dict] = []

    def flush(key: int, rows: list[dict]) -> dict:
        prices = [r["nifty"] for r in rows]
        atm_counts = Counter(r["atm"] for r in rows)
        # the most frequent strike; a tie goes to whichever appeared first
        top = max(atm_counts.items(),
                  key=lambda kv: (kv[1], [r["atm"] for r in rows].index(kv[0])))
        return {"time": key, "open": r2(prices[0]), "high": r2(max(prices)),
                "low": r2(min(prices)), "close": r2(prices[-1]),
                "atm": int(top[0]), "ticks": len(rows)}

    for tick in ticks:
        key = bucket_key(tick["epoch"], seconds)
        if key != current_key:
            if buf:
                bars.append(flush(current_key, buf))
            current_key, buf = key, []
        buf.append(tick)
    if buf:
        bars.append(flush(current_key, buf))
    return bars
