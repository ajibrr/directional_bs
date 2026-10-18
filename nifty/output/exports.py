"""
nifty.output.exports
=============

The flat artifacts written per session and timeframe.

    nifty_<slug>.csv    one row per candle, spreadsheet-friendly
    nifty_<slug>.json   the bar objects themselves, indented
    session_summary.json  every session, every timeframe, every run

The CSV header and the CSV rows are both built from `csv_columns(cfg)` and
`row_cells(...)`, and the writer refuses to emit a row whose keys are not exactly the
header -- so a column can never be added to one and forgotten in the other. The order
comes from the analysis steps (`nifty.data.analysis`), which is why adding a step extends
the export without touching this module.

Formatting is delegated to `nifty.core.numeric`, so the CSV and the JSON can never disagree
about how many decimals a value carries.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ..data import analysis
from . import meta
from ..core.clock import ist_date, ist_full, ist_label, tf_label
from ..recipe.config import Config
from ..core.keys import CE_OI_CHANGE, FLOW_KEYS, PE_OI_CHANGE, analytics_keys, sma_key
from ..core.errors import PipelineError
from ..core.numeric import PRICE_DECIMALS, fmt_pct, fmt_price, fmt_signed, r2

BASE_COLUMNS = ("time_ist", "epoch", "open", "high", "low", "close", "change", "change_pct")
TAPE_COLUMNS = ("atm", "ticks")
# the session's dashboard columns, joined onto each candle's own minute. They are an input
# like the tape's, not a derived series, so they sit beside it at the end of the row; a
# session with no dashboard writes them empty rather than inventing a value
FLOW_COLUMNS = tuple(FLOW_KEYS)


def csv_columns(cfg: Config) -> tuple[str, ...]:
    """The CSV header: the candle, then one block per analysis step, then the tape and
    the dashboard columns."""
    return BASE_COLUMNS + analysis.column_names(cfg) + TAPE_COLUMNS + FLOW_COLUMNS


def row_cells(bar: dict, prev_close: float | None, cfg: Config) -> dict:
    """One candle as column -> text/value, in header order."""
    chg = None if prev_close is None else r2(bar["close"] - prev_close)
    chg_pct = (None if prev_close in (None, 0)
               else round((bar["close"] - prev_close) / prev_close * 100.0, 3))
    cells: dict[str, object] = {
        "time_ist": ist_full(bar["time"]),
        "epoch": bar["time"],
        "open": fmt_price(bar["open"]),
        "high": fmt_price(bar["high"]),
        "low": fmt_price(bar["low"]),
        "close": fmt_price(bar["close"]),
        "change": fmt_signed(chg, PRICE_DECIMALS),
        "change_pct": fmt_signed(chg_pct, 3),
    }
    for period in cfg.price_periods:
        cells[sma_key(period)] = fmt_price(bar[sma_key(period)])
    for period in cfg.analytics_periods:
        chg_key, up_key, down_key = analytics_keys(period)
        cells[chg_key] = fmt_pct(bar[chg_key], cfg.pct_decimals)
        cells[up_key] = bar[up_key]
        cells[down_key] = bar[down_key]
    cells[cfg.direction_above_column] = bar[cfg.direction_above_column]
    cells[cfg.direction_below_column] = bar[cfg.direction_below_column]
    # the crossing is written in the CSV's own vocabulary -- 'above' / 'below' / empty
    cells[cfg.cross_direction_column] = bar[cfg.cross_direction_column] or ""
    cells[cfg.cross_distance_column] = fmt_pct(bar[cfg.cross_distance_column], cfg.pct_decimals)
    cells[cfg.cross_pair_distance_column] = fmt_pct(bar[cfg.cross_pair_distance_column],
                                                    cfg.pct_decimals)
    # the side relationship is written in the same vocabulary as the crossing: the word
    # itself, or an empty field where the two averages are equal or unavailable
    cells[cfg.relation_column] = bar[cfg.relation_column] or ""
    # the arrows are flags rather than measurements: 1 where the rule fired, 0 on every
    # other candle, so the CSV, the JSON and each drawn arrow are the same number. The red
    # one is the green rule's mirror and ships beside it.
    cells[cfg.signal_column] = bar[cfg.signal_column]
    cells[cfg.red_column] = bar[cfg.red_column]
    cells["atm"] = bar["atm"]
    cells["ticks"] = bar["ticks"]
    # the dashboard's minute pair, as the two integers the flow condition compares -- blank
    # on a session that ships no dashboard
    cells[CE_OI_CHANGE] = "" if bar.get(CE_OI_CHANGE) is None else bar[CE_OI_CHANGE]
    cells[PE_OI_CHANGE] = "" if bar.get(PE_OI_CHANGE) is None else bar[PE_OI_CHANGE]
    if tuple(cells) != csv_columns(cfg):
        raise PipelineError("the export columns and the analysis steps have drifted apart")
    return cells


def write_csv(path: Path, bars: list[dict], cfg: Config) -> None:
    """The flat export. lineterminator='\\n' so it is byte-identical to the sheet's export."""
    columns = csv_columns(cfg)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(columns)
        prev_close = None
        for bar in bars:
            cells = row_cells(bar, prev_close, cfg)
            writer.writerow([cells[column] for column in columns])
            prev_close = bar["close"]


def arrow_signals(cfg: Config, seconds: int, bars: list[dict]) -> list[dict]:
    """One record per arrow fired on this timeframe's bars, green and red alike.

    The record is read straight from the bar's own flags, so the file lists exactly the
    arrows the sheet draws and the CSV counts.
    """
    records: list[dict] = []
    for index, bar in enumerate(bars):
        for arrow, flag in (("green", cfg.signal_column), ("red", cfg.red_column)):
            if not bar[flag]:
                continue
            records.append({
                "date": ist_date(bar["time"]),
                "time": ist_label(bar["time"], with_seconds=True),
                "timeframe": tf_label(seconds),
                "timeframeSeconds": seconds,
                "arrow": arrow,
                "epoch": bar["time"],
                "barIndex": index,
                "close": bar["close"],
            })
    return records


def write_json(path: Path, payload: object) -> None:
    """Indented UTF-8 JSON -- the shape of every .json this pipeline writes."""
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_bars_json(path: Path, cfg: Config, seconds: int, bars: list[dict],
                    session: dict) -> None:
    """One timeframe's bars plus the metadata a consumer needs to read them."""
    write_json(path, {
        "meta": {"timeframeSeconds": seconds, "label": tf_label(seconds),
                 **meta.indicator_periods(cfg),
                 # a bars file carries no crossing block: the crossing row is a whole-series
                 # row the session summary describes, and this file is one timeframe's bars
                 "directionStreak": meta.direction(cfg),
                 "relation": meta.relation(cfg),
                 **meta.arrow_blocks(cfg),
                 # two audited marker rules, one the exact mirror of the other
                 "signalLogic": True,
                 "pctDecimals": cfg.pct_decimals,
                 "bars": len(bars), "session": session},
        "bars": bars,
    })
