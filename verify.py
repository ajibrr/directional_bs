#!/usr/bin/env python3
"""
verify.py  --  independent audit of the multi-session SMA 2 / 9 / 44 analytics sheet
======================================================================================

Nothing here computes a shipped value from the pipeline. Every quantity is recomputed
from each session's own file with its own code path -- an explicit min/max scan, a naive
sum, a fresh bucketing loop -- then compared against the artifacts. The shipped files are
also audited for the logic the requirements removed.

    python verify.py            # the whole audit, exit 0 only when every check passes
    python -m audit.suite       # the same run, from inside the package

Where things live:

    audit/harness.py   the constants, the independent readers, the loaded artifacts and
                       the `check` / `eq` helpers that count
    audit/suite.py     the sections, in order
    verify.py          this file: the command

Sections:

     0  sessions   one sheet, a payload entry and an artifact folder per input file;
                   one session per trading day; identical configuration across them
     1  session    tick file integrity, gap accounting, day OHLC
     2  bars       IST bucketing, OHLC extremes, tick attribution, chronological order
     3  sma        every plotted average, every bar, exact to the paisa
     4  analytics  percentage change (formula, blank rule, no division by zero)
     5  runs       consecutive rising / falling runs, resets, independence
     5b direction  the SMA 2 vs SMA 9 direction streak
     5c crossings  the strict crossing and the distance (%) it carried, no look-ahead
     5e arrows     both marker rules bar by bar, the mirror recomputed two ways
     6  outputs    CSV column set and every cell, JSON schema, session summary
     7  removal    no marker / pattern / signal logic survives in any shipped file
     8  sheet      single-pane wiring, the ten-row table, pinned analytics, direction row
     9  guard      the zero-previous division guard no artifact can exhibit
    10  example    the requirement's worked examples, through the pipeline's own functions
    11  recipe     the TOML recipe, the command line's --set, and a refused typo
    12  crossings  worked examples and the edges a generated file cannot show
    13  badge      the sheet's own badge builder, run under node
    14  rules      both arrow rules through the sheet's own engine and the pipeline's step
    15  json       the default JSON recipe and its TOML twin resolve to one Config
    16  source     a session may ship only its dashboard
    17  clock      the entry cut-off and the hard exit, and the trades they bound

Run:  python build_charts.py && python verify.py
"""

from __future__ import annotations

import audit.suite  # noqa: F401  -- importing the suite runs it and exits 1 on a failure
