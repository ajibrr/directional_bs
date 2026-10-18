"""
nifty.core.model
===========

What a build hands back. The pipeline builds these; the sheet writer and the command
line read them.

    Day     one session: its date, its source file, its metadata, its dashboard flow
            rows (when the session brings a dashboard), and for every timeframe the
            frame the sheet receives and the stats the exports record
    Build   the finished run: the days, the sheet that was written, the data folder,
            and whatever stale files the run cleaned up

`Day.to_payload()` is the exact shape the sheet's `days[]` array carries, key order
included, so the payload is described in one place rather than assembled twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Day:
    """One session, fully built."""

    date: str                        # IST session date, 'YYYY-MM-DD'
    source: str                      # the input file, relative to the project root
    session: dict                    # session metadata (see nifty.signals.stats.session_meta)
    frames: dict[str, dict]          # timeframe seconds -> the sheet's frame
    summary: dict[str, dict]         # timeframe seconds -> the stats block
    signals: tuple[dict, ...] = ()   # one record per arrow fired, all timeframes
    flow: tuple[dict, ...] = ()      # the dashboard's minute rows (see nifty.data.flow)

    def to_payload(self) -> dict:
        return {"date": self.date,
                "session": self.session,
                "timeframes": self.frames,
                "summary": self.summary,
                "flow": list(self.flow),
                "source": self.source}


@dataclass(frozen=True)
class Build:
    """A finished build."""

    days: tuple[Day, ...]
    sheet: Path                      # the delivered self-contained HTML
    summary_json: Path               # <paths.output_dir>/data/session_summary.json
    data_dir: Path                   # <paths.output_dir>/data
    pruned: tuple[Path, ...] = ()                     # stale session folders removed
    dropped: tuple[Path, ...] = ()                    # superseded sheets removed

    @property
    def dates(self) -> list[str]:
        return [day.date for day in self.days]
