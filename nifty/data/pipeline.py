"""
nifty.data.pipeline
==============

The build itself, from recipe to delivered artifacts.

    build(cfg)
      |
      +-- discover_sources          every session the recipe names: a tape, or a
      |                             dashboard whose tape is absent
      |
      +-- build_day, per session
      |     load_ticks -> bucket_ohlc -> run every analysis step -> stats
      |     -> <paths.output_dir>/data/<date>/nifty_<tf>.csv, .json -> the sheet's frame
      |     load_flow, when the session's dashboard ships beside the tape (always, when
      |     the dashboard is the session's only file)
      |
      +-- write_session_summary     one summary of every session and timeframe
      +-- sheet.write_sheet         the self-contained HTML
      +-- prune_stale, drop_other_sheets

Every session is built from the same recipe -- the same timeframes, averages,
precision and rules -- so sessions differ only by their tape, which is the point of
the day tabs. A session may ship its tape, or only the dashboard that carries the same
per-second series (and the minute flow beside it); either way it is one row per second
in, one set of artifacts out.

Adding an analysis means adding a step to `nifty.data.analysis`; it appears in the CSV, the
JSON exports and the sheet payload without a line changing here.
"""

from __future__ import annotations

from pathlib import Path

from . import analysis
from ..output import exports, sheet
from ..signals import stats
from .bars import bucket_ohlc, discover_sources, load_ticks
from ..core.clock import ist_date
from ..recipe.config import Config
from ..core.errors import DataError
from .flow import attach_flow, load_flow
from ..core.model import Build, Day
from ..output.sheet import sheet_glob


def build_day(cfg: Config, src: Path, ticks: list[dict]) -> Day:
    """One session file and its ticks -> its bars, exports, sheet frame and summary."""
    date = ist_date(ticks[0]["epoch"])
    day_dir = cfg.paths.data_dir / date
    day_dir.mkdir(parents=True, exist_ok=True)

    session = stats.session_meta(cfg, src, ticks, date)
    # the dashboard beside the tape, when the session ships one: the sheet's flow chart
    # reads it, and a session without one simply carries no rows
    flow = load_flow(src)
    frames: dict[str, dict] = {}
    summary: dict[str, dict] = {}
    signals: list[dict] = []

    for seconds in cfg.timeframes:
        slug = cfg.timeframe_slug(seconds)
        bars = bucket_ohlc(ticks, seconds)
        # the dashboard row of the minute each candle opens in joins the tape columns
        # before the steps run, so the flow condition reads the same bars everything else
        # does -- and a session with no dashboard carries None here, not a zero
        attach_flow(bars, flow)
        analysis.run_steps(bars, cfg)
        tf_stats = stats.timeframe_stats(seconds, bars, cfg)

        exports.write_csv(day_dir / f"nifty_{slug}.csv", bars, cfg)
        exports.write_bars_json(day_dir / f"nifty_{slug}.json", cfg, seconds, bars, session)
        frames[str(seconds)] = sheet.frame(cfg, seconds, bars, tf_stats)
        summary[str(seconds)] = tf_stats
        signals.extend(exports.arrow_signals(cfg, seconds, bars))

    return Day(date=date, source=cfg.source_path(src), session=session,
               frames=frames, summary=summary, signals=tuple(signals),
               flow=tuple(flow))


def write_session_summary(cfg: Config, days: tuple[Day, ...]) -> Path:
    """Every session and every timeframe in one file, keyed by session date."""
    path = cfg.paths.data_dir / "session_summary.json"
    exports.write_json(path, {
        "days": {day.date: {"session": day.session, "timeframes": day.summary}
                 for day in days},
    })
    return path


def write_arrow_signals(cfg: Config, days: tuple[Day, ...]) -> Path:
    """Every arrow of every session and timeframe, in time order, numbered from 1."""
    path = cfg.paths.data_dir / "arrow_signal.json"
    records = sorted((r for day in days for r in day.signals),
                     key=lambda r: (r["date"], r["epoch"], r["timeframeSeconds"]))
    exports.write_json(path, [{"srNo": number, **record}
                              for number, record in enumerate(records, start=1)])
    return path


def prune_stale(cfg: Config, days: tuple[Day, ...]) -> tuple[Path, ...]:
    """Remove session folders this run did not write, so an incremental build leaves no ghosts.

    A session folder for a date no longer configured would otherwise look like a
    seventh session's exports.
    """
    removed: list[Path] = []
    keep = {day.date for day in days}
    if cfg.paths.data_dir.is_dir():
        for stale in sorted(p for p in cfg.paths.data_dir.iterdir() if p.is_dir()):
            if stale.name in keep:
                continue
            for child in sorted(stale.iterdir()):
                child.unlink()
                removed.append(child)
            stale.rmdir()
            removed.append(stale)
    return tuple(removed)


def drop_other_sheets(cfg: Config, keep: Path) -> tuple[Path, ...]:
    """Remove sheets a previous run left under a different name."""
    removed: list[Path] = []
    for old in sorted(cfg.paths.output_dir.glob(sheet_glob(cfg))):
        if old != keep:
            old.unlink()
            removed.append(old)
    return tuple(removed)


def build(cfg: Config) -> Build:
    """Run the whole pipeline for one recipe."""
    cfg.check_inputs()
    cfg.paths.output_dir.mkdir(parents=True, exist_ok=True)
    cfg.paths.data_dir.mkdir(parents=True, exist_ok=True)

    sources = discover_sources(cfg.paths.sources_dir, cfg.paths.sources_glob)

    # one session per trading day: the exports are keyed by date, so two files carrying the
    # same day would write the same folder twice and leave the sheet with the day twice over.
    # Read every session first and refuse the collision before anything is written.
    loaded: list[tuple[Path, list[dict]]] = []
    by_date: dict[str, Path] = {}
    for src in sources:
        ticks = load_ticks(src)
        if not ticks:
            raise DataError(f"{src} contained no ticks")
        date = ist_date(ticks[0]["epoch"])
        if date in by_date:
            raise DataError(
                f"two session files carry the {date} session: {by_date[date].name} and "
                f"{src.name} -- the exports are keyed by date, so keep one file per "
                f"trading day (rename or remove the duplicate)")
        by_date[date] = src
        loaded.append((src, ticks))

    days = tuple(build_day(cfg, src, ticks) for src, ticks in loaded)

    pruned = prune_stale(cfg, days)
    summary_json = write_session_summary(cfg, days)
    write_arrow_signals(cfg, days)
    sheet_path = sheet.write_sheet(cfg, days)
    dropped = drop_other_sheets(cfg, sheet_path)

    return Build(days=days, sheet=sheet_path, summary_json=summary_json,
                 data_dir=cfg.paths.data_dir, pruned=pruned, dropped=dropped)
