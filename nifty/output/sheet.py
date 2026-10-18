"""
nifty.output.sheet
===========

The delivered artifact: one self-contained HTML file covering every session.

The sheet is data-driven. The template holds the panes, the table, the toolbars and
the styling; everything that varies arrives as one JSON payload spliced into it:

    meta        the recipe and the tape: instrument, sessions, timeframes, averages,
                precision, the run rule and the direction rule
    days[]      per session: its metadata, its per-timeframe frames, its stats

A frame carries only what the browser cannot reconstruct -- the OHLC bars plus the
tape columns -- because the sheet derives every average, every analytics value and the
green-arrow flag itself, and the audit checks that its numbers equal the pipeline's.
That keeps the payload small and makes the in-page recomputation a second, independent
implementation of the same rules.

`sheet_name` and `page_title` are rendered from the two templates in the recipe, so
changing what the delivered file is called is a config edit rather than a code edit.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import meta
from ..core.clock import tf_label, tf_short, tf_slug
from ..core.keys import CE_OI_CHANGE, PE_OI_CHANGE
from ..recipe.config import Config
from ..core.model import Day

# What one bar carries into the browser. The two dashboard columns travel with the tape
# columns because the sheet's own rule engine reads them: it recomputes the arrows from
# these fields, so a condition the payload did not carry could not be checked in the page.
BAR_FIELDS = ("time", "open", "high", "low", "close", "atm", "ticks",
              CE_OI_CHANGE, PE_OI_CHANGE)


def frame(cfg: Config, seconds: int, bars: list[dict], stats: dict) -> dict:
    """One (session, timeframe) as the sheet receives it."""
    payload_bars = [{key: bar[key] for key in BAR_FIELDS} for bar in bars]
    return {
        "seconds": seconds,
        "label": tf_label(seconds),
        "short": tf_short(seconds),
        "slug": tf_slug(seconds),
        **meta.indicator_periods(cfg),
        "pctDecimals": cfg.pct_decimals,
        # a frame carries the periods and the sentences; the column names travel once, in
        # the payload's own meta block, because they are the table's headings there
        **meta.side_blocks(cfg, with_columns=False),
        **meta.arrow_blocks(cfg),
        "barFields": list(BAR_FIELDS),
        "bars": payload_bars,
        "stats": stats,
    }


def payload_meta(cfg: Config, days: tuple[Day, ...]) -> dict:
    """The recipe as the sheet reads it back, key order included."""
    dates = [day.date for day in days]
    first = days[0]
    return {
        "instrument": cfg.instrument,
        "dates": dates,
        "days": len(days),
        "firstDateIST": dates[0],
        "lastDateIST": dates[-1],
        "sources": [day.source for day in days],
        "timeframes": list(cfg.timeframes),
        **meta.indicator_periods(cfg),
        **meta.side_blocks(cfg),
        **meta.arrow_blocks(cfg),
        "runRule": cfg.run_rule,
        "pctDecimals": cfg.pct_decimals,
        # how many candles a chart opens on. A window is a view, not a truncation: the
        # table, the flags and both exports still cover every candle of the session.
        "windowBars": cfg.sheet.window_bars,
        # two audited marker rules run over every timeframe: the green arrow and the red one
        # that mirrors it. Their conditions and thresholds travel with the payload, so what
        # the arrows were drawn from is inspectable rather than implied -- and because the
        # red rule is derived from the green one, the payload is also where its numbers can
        # be read back and checked against the green rule's own.
        "signalLogic": True,
        # the active day drives the masthead / KPI cards; the sheet reads them per day,
        # and these mirror the first day so a static reader still sees a session
        "dateIST": first.session["dateIST"],
        "sessionStartIST": first.session["sessionStartIST"],
        "sessionEndIST": first.session["sessionEndIST"],
        "ticks": first.session["ticks"],
        "coveragePct": first.session["coveragePct"],
        "source": first.session["source"],
    }


def payload(cfg: Config, days: tuple[Day, ...]) -> dict:
    """The whole inlined payload."""
    return {"meta": payload_meta(cfg, days), "days": [day.to_payload() for day in days]}


def date_range(dates: list[str]) -> tuple[str, str]:
    """(slug, label) for a run of sessions: 'a_to_b' / 'a -> b', or the single date."""
    if len(dates) > 1:
        return f"{dates[0]}_to_{dates[-1]}", f"{dates[0]} \u2192 {dates[-1]}"
    return dates[0], dates[0]


def naming_tokens(cfg: Config, dates: list[str]) -> dict[str, str]:
    """Everything a sheet name or title template may interpolate."""
    slug, label = date_range(dates)
    return {
        "instrument": cfg.instrument,
        "range_slug": slug,
        "range_label": label,
        "first_date": dates[0],
        "last_date": dates[-1],
        "sma_slash": cfg.sma_slash,
        "sessions": str(len(dates)),
    }


def sheet_name(cfg: Config, dates: list[str]) -> str:
    return cfg.sheet.name_template.format(**naming_tokens(cfg, dates))


def sheet_glob(cfg: Config) -> str:
    """The name template with its tokens blanked -- what a superseded sheet matches."""
    return re.sub(r"\{[^}]*\}", "*", cfg.sheet.name_template)


def page_title(cfg: Config, dates: list[str]) -> str:
    return cfg.sheet.title_template.format(**naming_tokens(cfg, dates))


def render(template_text: str, chart_lib_text: str, data_json: str, title: str) -> str:
    """Splice the library, the payload and the title into the template."""
    return (template_text
            .replace("/*__CHART_LIB__*/", chart_lib_text)
            .replace("__DATA_JSON__", data_json)
            .replace("__PAGE_TITLE__", title))


def write_sheet(cfg: Config, days: tuple[Day, ...]) -> Path:
    """Render the sheet for every session and return the file that was written."""
    dates = [day.date for day in days]
    data_json = json.dumps(payload(cfg, days), separators=(",", ":")).replace("<", "\\u003c")
    html = render(cfg.paths.template.read_text(encoding="utf-8"),
                  cfg.paths.chart_lib.read_text(encoding="utf-8"),
                  data_json,
                  page_title(cfg, dates))
    out_path = cfg.paths.output_dir / sheet_name(cfg, dates)
    out_path.write_text(html, encoding="utf-8")
    return out_path
