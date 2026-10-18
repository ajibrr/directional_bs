"""
build_charts.py  --  entry point
================================
Pipeline: 1-second NIFTY ticks  ->  multi-timeframe OHLC bars  ->  SMA(2/9/44)
          ->  SMA 2/9/44 analytics  ->  one tabbed HTML sheet covering every day.

The pipeline itself lives in the `nifty` package; this file is only what you run.

    python build_charts.py

Input
    input data/NIFTY_<date>_PRICE_1SEC.jsonl   -- one file per session, discovered
        {"timestamp": "2026-10-15 09:15:00", "timestamp_epoch": 1792035900,
         "nifty": 22671.3, "atm": 22650}

    or, when a session ships no tape, its dashboard -- whose own `nifty_seconds` series
    carries the same per-second triple:

    input data/NIFTY_<date>_DASHBOARD.json
        {"nifty_seconds": [{"timestamp": "2026-10-15 09:15:00",
                            "timestamp_epoch": 1792035900, "nifty": 22671.3,
                            "atm": 22650}, ...]}

    Every session in that directory is picked up and given the SAME configuration: the
    same timeframes, the same averages and the same analytics rows. Adding a new day
    is a matter of dropping another file in -- nothing else changes. A dashboard that
    sits beside a tape is not a second session: the tape is the fuller record (it runs
    to the last second of the closing minute) and it wins.

Defaults
    12 s, 36 s, 1 min, 3 min, 5 min bar widths; SMA 2, 9 and 44 plotted on the price
    chart; all three additionally driving the analytics indicator (per-candle
    percentage change and the length of the current run of consecutive moves); one
    row pairing SMA 2 with SMA 9 -- the direction streak, counting consecutive
    candles where SMA 2 sits above SMA 9 while SMA 9 rises (ABOVE), or below it while
    SMA 9 falls (BELOW); and two more rows for the strict SMA 2 vs SMA 9 crossing:
    the crossing direction itself (ABOVE / BELOW on the crossing candle, empty
    otherwise) and the signed SMA 9 vs SMA 44 distance (%) that candle carried.

    Every one of those is a recipe value rather than a constant; see `--print-config`.

The crossing rows are descriptive: they name the candle on which SMA 2 swapped sides of
SMA 9 and report how far apart SMA 9 and SMA 44 were at that moment.

One rule reads those rows and nothing else -- the green arrow, declared in the recipe's
`[signal]` block. It is a six-condition AND: on the candle, the crossing direction, the
distance it carried and the above/below relationship; on the candle before it, the slow
average's change and the two consecutive-count runs. It draws an up arrow below the bar
on the price pane of every timeframe and ships the same flag as `1` / `0` in the
`green_arrow` column, so the drawn arrow and the exported number are one value. It marks
a candle that has already closed and states no verdict.

Every threshold is named after the row it reads -- `cross_direction`,
`distance_pct_at_cross_min` / `distance_pct_at_cross_max`, `relation`,
`chg_pct_min`, `streak_minus_min` / `streak_minus_max`, `streak_plus_min` -- and that one
name is what the recipe, the resolved config, the payload and the sheet's own code use.

Outputs
    Every index owns one tree, named by its recipe's `paths.output_dir`:

    output/nifty/data/<date>/nifty_<tf>.json   structured bar objects + analytics
    output/nifty/data/<date>/nifty_<tf>.csv    flat spreadsheet-friendly export
    output/nifty/data/session_summary.json     every day + per-timeframe statistics
    output/nifty/NIFTY_<first>_to_<last>_SMA_sheet.html
                                        self-contained sheet: a day tab strip over the
                                        timeframe tabs

    and the same shape again under output/sensex/ for `--config config/sensex.json`.
"""

from __future__ import annotations

from nifty.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
