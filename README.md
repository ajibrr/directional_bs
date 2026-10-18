# NIFTY 50 · 2026-10-13 → 2026-10-15 · SMA 2/9/44 analytics sheet

Turns raw **1-second** NIFTY tick files into one self-contained HTML sheet: a **session (day)
strip** over the timeframe tabs, a **single-pane price chart** opening on the latest 100 candles,
and a **ten-row analytics table — one column per candle** — reporting the SMA 2, SMA 9 and SMA 44
percentage change, for each of them the length of the current run of **consecutive** rising /
falling changes, the SMA 2 vs SMA 9 **direction streak**, the two descriptive crossing rows — the
strict SMA 2 vs SMA 9 **cross direction** (ABOVE / BELOW on the candle the pair swaps sides, empty
otherwise) and the **SMA 9 vs SMA 44 distance (%)** read on that same crossing candle — and a
**SMA 9 vs SMA 44 (ABOVE / BELOW)** row saying which side of each other those two averages sit on,
candle by candle.

Every session file in `input data/` is built with **the same configuration** — the same five
timeframes, the same SMA periods, the same analytics rows — so the day strip only swaps the data,
never the meaning. Adding another day is a matter of dropping another file in and rerunning the
build. A session is either its 1-second tape (`NIFTY_<date>_PRICE_1SEC.jsonl`) or that session's
dashboard on its own (`NIFTY_<date>_DASHBOARD.json`): the dashboard carries the same per-second
price series under `nifty_seconds`, so one file is enough — and when both are there the tape is
read, because it runs to the closing minute's last second. One file per trading day: the exports
are keyed by date, so two files carrying the same session are refused by name before anything is
written (a copy saved under another date is the usual way that happens).

**Two marker rules run over every timeframe: a green arrow below the bar and a red ▼ one above it.**
The green arrow is drawn *below the bar* on the price pane whenever **all seven** of these conditions
hold — four read from the candle itself, three from the candle before it:

| # | Read from | Condition |
| --- | --- | --- |
| 1 | the candle | `SMA 2 vs SMA 9 Cross Direction` = `ABOVE` |
| 2 | the candle | `SMA 9 vs SMA 44 Distance (%) at SMA 2/SMA 9 Cross` between `0.0000` and `0.0250` — both ends included |
| 3 | the candle | `SMA 9 vs SMA 44 (ABOVE / BELOW)` = `ABOVE` |
| 4 | the candle's minute | `pe_oi_change` **greater than** `ce_oi_change` (the session's dashboard; a session with no dashboard does not read this condition) |
| 5 | the previous candle | `SMA 44 Change (%)` **strictly above** `0.0005` |
| 6 | the previous candle | `SMA 9 Consecutive Count (+N / −N)` a **falling** run of `7` to `15` |
| 7 | the previous candle | `SMA 44 Consecutive Count (+N / −N)` a **rising** run of `7` or more |

The **red ▼ arrow** is drawn *above the bar* on the same pane, and it is not a second set of numbers
to keep in step: it is the green rule **read the other way round**, derived from it in code
(`GreenArrowRule.mirrored()`) rather than declared beside it, so the two can never drift apart. Every
word flips, the distance window is negated with its ends swapped, the change threshold is negated,
and the two consecutive-count runs are exchanged:

| # | Read from | Condition |
| --- | --- | --- |
| 1 | the candle | `SMA 2 vs SMA 9 Cross Direction` = `BELOW` |
| 2 | the candle | `SMA 9 vs SMA 44 Distance (%) at SMA 2/SMA 9 Cross` between `−0.0250` and `0.0000` — both ends included |
| 3 | the candle | `SMA 9 vs SMA 44 (ABOVE / BELOW)` = `BELOW` |
| 4 | the previous candle | `SMA 44 Change (%)` **strictly below** `−0.0005` |
| 5 | the previous candle | `SMA 9 Consecutive Count (+N / −N)` a **rising** run of `7` to `15` |
| 6 | the previous candle | `SMA 44 Consecutive Count (+N / −N)` a **falling** run of `7` or more |

Each rule is a six-condition AND, not a score: one condition missing and no arrow is drawn, and a
session's first candle can never carry one because it has no previous candle to read. A candle
carries **one arrow or the other and never both**, because an ABOVE crossing and a BELOW one cannot
happen on the same candle. Each flag ships as its own column — `green_arrow`, and the mirror's
`red_arrow` (`1` / `0`) beside it — in every CSV and JSON, so each drawn arrow and its exported
number are one value. Every threshold lives in the one recipe block
([§3.6](#36-the-two-arrow-rules--the-green-one-and-the-red-mirror)), and nothing else in the sheet
draws anything or states a verdict.

Open the deliverable directly in a browser — it is fully self-contained, offline, no server:

```
output/nifty/NIFTY_2026-09-11_to_2026-10-16_SMA_sheet.html
output/sensex/SENSEX_2026-09-28_to_2026-10-16_SMA_sheet.html
```

| | |
| --- | --- |
| **Sessions** | NIFTY: 2026-09-11 → 2026-10-16 (21) · SENSEX: 2026-09-28 → 2026-10-16 (12) — one tab each |
| **Timeframes** | 12 s · 36 s · 1 min · 3 min · 5 min — shared by every session |
| **Price pane** | the sheet's only pane: candles + SMA(2) · SMA(9) · SMA(44) |
| **Chart window** | opens on the latest 100 candles (`[sheet] window_bars`), sized to the pane, scrollable back to the open |
| **Analytics table** | 10 metric rows × one column per candle, directly under the chart, per session per timeframe |
| **Green arrow** | one 6-condition AND rule, drawn below the bar on the price pane of every timeframe — 70 arrows on 14 of the 21 NIFTY sessions |
| **red ▼ marker** | the same rule **mirrored** by the code (derived, never re-declared), drawn above the bar — 61 arrows on 15 of the 21 NIFTY sessions |
| **Exports** | CSV · JSON per session per timeframe, plus `session_summary.json` |
| **Verified by** | `verify.py` — the independent audit; the run prints its tally and exits non-zero on any failure |

## Project structure

```
.
│
├── README.md                        this document
├── build_charts.py                  entry point   python build_charts.py [--config <recipe>]
├── verify.py                        the audit     python verify.py  (exits non-zero on failure)
│
├── config/                          one recipe per index — the only place a build's values live
│   ├── nifty.json                   the default recipe (read when --config is omitted)
│   ├── nifty.toml                   the same recipe in TOML — identical resolved Config
│   └── sensex.json                  SENSEX: instrument, source glob, output_dir and sheet name
│                                    changed — timeframes, averages and rules untouched
│
├── input data/                      SOURCE. one file per session, both indices, one flat folder
│   ├── NIFTY_<date>_DASHBOARD.json  21 sessions (2026-09-11 … 2026-10-16)
│   ├── NIFTY_<date>_PRICE_1SEC.jsonl  a tape, when a session ships one — it wins over the
│   │                                  dashboard beside it (the fuller record)
│   ├── SENSEX_<date>_DASHBOARD.json 12 sessions (2026-09-28 … 2026-10-16), `sensex_seconds`
│   └── no_*_<date>_*                 parked copies no glob matches — never built (2 files)
│
├── nifty/                           the pipeline: six layers, imports pointing one way (§5.1)
│   ├── __init__.py                  public surface: build · load_config · Config · model · errors
│   ├── cli.py                       the command line and the console report
│   ├── core/                        the vocabulary — no policy
│   │   ├── errors.py                the failures the command line reports in one sentence
│   │   ├── model.py                 what a build hands back (Build, Day)
│   │   ├── numeric.py               exact integer-paise arithmetic; the one number→text place
│   │   ├── clock.py                 IST display and timeframe arithmetic
│   │   └── keys.py                  the column vocabulary and the threshold helpers
│   ├── recipe/                      the recipe → one Config
│   │   ├── defaults.py              the built-in recipe; the SECTIONS / DEFAULTS maps
│   │   └── config.py                the reader, --set overrides, validation, the rule objects
│   ├── data/                        a session in, columns out
│   │   ├── bars.py                  tape or dashboard → OHLC bars (accepts nifty / sensex keys)
│   │   ├── flow.py                  the dashboard beside the tape: minute CE / PE OI change
│   │   ├── analysis.py              the analysis steps, in order — the extension point (§5.3)
│   │   └── pipeline.py              the build: sessions → summary → sheet → stale-output sweep
│   ├── signals/                     what those columns mean
│   │   ├── series.py                averages, changes, runs, streak, crossings, relationship
│   │   ├── rules.py                 the green arrow rule, its mirrored red twin, the funnel
│   │   └── stats.py                 per-timeframe and per-session summaries
│   ├── output/                      everything that leaves the build
│   │   ├── exports.py               the CSV and JSON writers, from one column list
│   │   ├── meta.py                  the recipe blocks the artifacts carry as JSON
│   │   └── sheet.py                 the payload and the HTML that carries it
│   └── trade/                       arrows → trades, per the clock
│       └── backtest.py              entry cut-off, SMA 2/9 exit, hard exit
│
├── audit/                           the independent audit, a package (§7.1)
│   ├── harness.py                   constants, its own readers, check/eq, the tally
│   └── suite.py                     sections 0–17, in order
│
├── templates/
│   └── sheet.html                   the sheet template — edit this, not the generated HTML
├── docs/
│   └── colour_conditions.md         GENERATED reference: indicators and the two arrow rules
├── tools/
│   ├── run_all.py                   the whole chain in one command (builds, audit, trades, docs)
│   └── write_colour_conditions.py   regenerates docs/colour_conditions.md from the recipe
├── vendor/
│   ├── lightweight-charts.standalone.production.js  chart engine, TradingView v5.2.1 (inlined)
│   ├── lightweight-charts.package.json
│   └── LICENSE.lightweight-charts.txt               Apache-2.0 licence
│
└── output/                          GENERATED. one tree per index, identical in shape
    ├── nifty/                       python build_charts.py
    │   ├── NIFTY_2026-09-11_to_2026-10-16_SMA_sheet.html   self-contained, offline sheet
    │   └── data/
    │       ├── session_summary.json  21 sessions and their per-timeframe statistics
    │       ├── arrow_signal.json     every arrow of every session, in time order
    │       └── <date>/ × 21          12sec · 36sec · 1min · 3min · 5min, each .csv + .json
    └── sensex/                      python build_charts.py --config config/sensex.json
        ├── SENSEX_2026-09-28_to_2026-10-16_SMA_sheet.html
        └── data/                    12 session folders, the same five exports + the same two JSONs
```

Every package folder carries an `__init__.py` that states that layer's public surface, so nothing
outside it reaches past the folder boundary.

**Four kinds of file, kept apart.** `input data/` is the only source of data; `config/` is the only
place a build's values live; `nifty/`, `audit/`, `templates/`, `tools/` and `vendor/` are code;
`output/` and `docs/colour_conditions.md` are written by a run and never edited by hand. Deleting
`output/` costs nothing — one build restores it.

One filename is shared by both trees: the per-session exports keep their `nifty_<tf>.csv` / `.json`
names under `output/sensex/` too. The **contents** are SENSEX bars (the reader normalises `sensex`
to the internal `nifty` field); only the filenames say otherwise, and no reader depends on them.

**Where to change what** — one home per concern:

| To change | Edit |
| --- | --- |
| Any build value: what to read, bar widths, averages, both arrow rules, output names | `config/nifty.json` (or `.toml`), `config/sensex.json` |
| The sheet's look and behaviour | `templates/sheet.html` |
| How a session becomes columns | `nifty/data/` — `bars.py`, `flow.py`, `analysis.py` |
| What the columns mean, and the arrow rules | `nifty/signals/` — `series.py`, `rules.py` |
| What the build writes | `nifty/output/` — `exports.py`, `meta.py`, `sheet.py` |
| The trade clock (entry cut-off, exit, hard exit) | `config/*.json` `[backtest]`, read by `nifty/trade/backtest.py` |
| A check | `audit/suite.py` (readers and constants in `audit/harness.py`) |
| The generated rule reference | run `python tools/write_colour_conditions.py` |

`output/` and `docs/colour_conditions.md` are regenerated, never edited by hand.

## Contents

- [Project structure](#project-structure)

1. [Quick start](#1-quick-start)
   - [1.1 Deliverables](#11-deliverables) · [1.2 Rebuild](#12-rebuild) · [1.3 Running it](#13-running-it--one-recipe-no-code-edits)
2. [The sheet](#2-the-sheet)
   - [2.1 What it contains](#21-what-it-contains) · [2.2 The chart](#22-the-chart) · [2.3 Interaction](#23-interaction) · [2.4 Lazy sessions and the ledger appendix](#24-lazy-sessions-and-the-ledger-appendix)
3. [The analytics rows](#3-the-analytics-rows)
   - [3.1 Row reference](#31-row-reference) · [3.2 Consecutive counts](#32-the-consecutive-counts) · [3.3 Direction streak](#33-the-direction-streak) · [3.4 The two crossing rows](#34-the-two-crossing-rows) · [3.5 The SMA 9 vs SMA 44 relationship](#35-the-sma-9-vs-sma-44-relationship) · [3.6 The two arrow rules](#36-the-two-arrow-rules--the-green-one-and-the-red-mirror)
4. [Data and exports](#4-data-and-exports)
   - [4.1 Resampling and columns](#41-resampling-and-columns) · [4.2 Files](#42-files) · [4.3 The three sessions](#43-what-the-three-sessions-look-like) · [4.4 Direction streak per session](#44-the-sma-2-vs-sma-9-direction-streak-per-session) · [4.5 Crossings per session](#45-the-strict-sma-2-vs-sma-9-crossing-and-its-distance-per-session) · [4.6 Relationship per session](#46-the-sma-9-vs-sma-44-relationship-per-session) · [4.7 Arrows per rule, per session](#47-arrows-per-rule-per-session)
5. [The recipe and the package](#5-the-recipe-and-the-package)
   - [5.1 The package](#51-the-package) · [5.2 The recipe](#52-the-recipe) · [5.3 Adding an analysis](#53-adding-an-analysis)
6. [Requirement → implementation](#6-requirement--implementation)
7. [How this was verified](#7-how-this-was-verified)
   - [7.1 The automated audit](#71-the-automated-audit) · [7.2 Live in a browser](#72-live-in-a-browser)
8. [Findings](#8-findings)
9. [Notes and limits](#9-notes-and-limits)

---

## 1. Quick start

### 1.1 Deliverables

| Path | What it is |
| --- | --- |
| `output/nifty/NIFTY_2026-09-11_to_2026-10-16_SMA_sheet.html` | The NIFTY sheet. Chart library + every session's bars inlined (12,363,498 bytes ≈ 11.8 MiB), works from `file://`. |
| `output/sensex/SENSEX_2026-09-28_to_2026-10-16_SMA_sheet.html` | The SENSEX sheet, same shape (7,219,391 bytes ≈ 6.9 MiB), built by `--config config/sensex.json`. |
| `output/nifty/data/2026-10-13/nifty_12sec.csv` · `36sec` · `1min` · `3min` · `5min` | Flat exports — one row per bar, spreadsheet-ready. |
| `output/nifty/data/2026-10-14/…` · `output/nifty/data/2026-10-15/…` | The same five exports for each session, in their own folder. |
| `output/nifty/data/<date>/*.json` (same five slugs per session) | Structured bar objects with the analytics columns. |
| `output/nifty/data/session_summary.json` | Every session and its per-timeframe statistics, including the final runs and their maxima. |
| `build_charts.py` | The entry point. `python build_charts.py` reads the recipe, runs the pipeline and reports what it wrote; the pipeline itself is the `nifty` package, so this file is only the command line. |
| `nifty/` | The pipeline — twenty modules in six layers behind that one entry point, listed in [§5.1](#51-the-package). |
| `config/nifty.json` | **The recipe** a build reads when it is given none. Everything the build varies: what to read, the bar widths, the averages, the precision, the direction pair, the output names — with `_` keys standing in for the comments JSON has no syntax for. |
| `config/nifty.toml` | The same recipe in TOML, comment for comment. `--config config/nifty.toml` builds the identical artifacts, and the audit resolves both files to one `Config`. |
| `config/sensex.json` | The SENSEX recipe: the NIFTY one with its instrument, source glob, output folder and sheet names changed. Builds into `output/sensex/` from `SENSEX_*_DASHBOARD.json` files, which carry `sensex_seconds` / `sensex`. |
| `verify.py` | The independent audit: sections 0–17, one module per concern's checks, counted as it goes. Sections 0–6 run once **per session**; 7 audits the package for removed identifiers; 8 the sheet's structure; 9 the division-by-zero guard; 10 the requirement's worked example; 11 the recipe; 12 the crossing and relationship edge cases; 13 the sheet's own cursor-badge builder; 14 the sheet's own arrow rules through the pipeline's own step (13 and 14 need `node` on `PATH`, and fail loudly without it rather than passing quietly); 15 the JSON default against its TOML twin; 16 a dashboard-only session; and 17 the trade clock. The run prints its tally and exits non-zero on any failure. |
| `templates/sheet.html` | The sheet template — edit this, not the generated HTML. |
| `vendor/lightweight-charts.standalone.production.js` | Chart engine, TradingView Lightweight Charts v5.2.1 (Apache-2.0), vendored so the sheet needs no CDN. |

### 1.2 Rebuild

```bash
python build_charts.py                              # NIFTY  -> output/nifty/
python build_charts.py --config config/sensex.json  # SENSEX -> output/sensex/
python verify.py                                    # re-verify (exits non-zero on any failed check)
python tools/run_all.py                             # all of it, in order, with the backtests
```

**Two indices, one pipeline.** `config/sensex.json` is the NIFTY recipe with four values changed —
`instrument.name = "SENSEX"`, `sources_glob = "SENSEX_*_PRICE_1SEC.jsonl"`, `output_dir =
"output/sensex"` and the sheet's name/title. Everything else (timeframes, averages, both arrow
rules, the trade clock) is the same file, so the two builds cannot drift apart in behaviour. The
separate output folder is not cosmetic: a trading day exists in both feeds, and the exports are
keyed by date.

SENSEX feeds name their series `sensex_seconds` and their price `sensex`; NIFTY uses
`nifty_seconds` / `nifty`. `nifty/data/bars.py` accepts either, and stores both internally under
the one field every later step already spells, so no other module knows which index it is reading.
The audit (`verify.py`) reads the NIFTY delivery only — its source glob and instrument name are
pinned in `audit/harness.py`.

### 1.3 Running it — one recipe, no code edits

```bash
python build_charts.py
```

A recipe is TOML or JSON, chosen by the **file's suffix** — both readers take the same table of
sections, so `--config config/nifty.json` and `--config config/nifty.toml` build the identical
artifacts. The two shipped files hold everything the build varies: the input folder and file recipe,
the template and chart library, the bar widths, the price averages, the analytics periods and
precision, the direction pair, and the delivered sheet's name and title. Relative paths resolve
against the project root. **An unknown section or key is refused with the key named** rather than
ignored, so a typo cannot quietly change a build; `--set` values are read as TOML, so
`--set sma.price_periods='[3,9,21]'` works too. In the JSON file a key whose name starts with `_` is
a note — JSON's stand-in for the comments beside the TOML's keys — and is ignored, except that a
note named after a setting it sits beside (`_enabled`) is refused rather than silently switching
that setting off.

---

## 2. The sheet

### 2.1 What it contains

1. **Masthead** — instrument, the active session and how many sessions there are, session window, tick count, coverage %, chart-engine attribution, and how many arrows each of the two marker rules draws across the session's five timeframes.
2. **Session snapshot** — 15 KPI cards for the **active session**, aggregated from its raw 1-second tape.
3. **Timeframe explorer** — the tabbed workspace:
   - a **session strip**: `2026-10-13` · `2026-10-14` · `2026-10-15`, each badged with its net move
   - tabs **`12s` · `36s` · `1m` · `3m` · `5m`**, each badged with its bar count for that session
   - **Reset zoom / Export CSV / Export JSON** (for the active session + timeframe)
   - a toolbar row editing the **three price-pane averages** (period inputs + on/off), with the analytics table explicitly noted as pinned to SMA 2, 9 and 44
   - one panel per timeframe for the active session: metric chips → **chart (the price pane, opening on the latest 100 candles)** → **analytics table** → candle ledger appendix
4. **Timeframe comparison** — the active session across all five scales, including the last change %, the current run and the longest run seen for each period.
5. **CE / PE OI change** — when the session ships a dashboard beside its tape, the feed's own minute-by-minute `ce_oi_change` / `pe_oi_change` as two lines on one pane, plotted exactly as supplied (no summing, differencing or smoothing), reading against a dashed zero line because a minute's change can be negative, with a hover read-out of both figures. A session without a dashboard file hides the section.
6. **Method & provenance** — resampling, average, run, direction-streak and crossing definitions, one bullet per marker rule with every threshold filled from the payload, plus the rebuild command.

The analytics table is built **one frame after first paint**, never during boot, so it cannot
delay the chart. Each session's table is 10 × 1,881 = **18,810 cells** at 12 s (the label column
plus 1,880 candles), and the build itself sits in the tens-to-hundreds of milliseconds band
depending on how the webview throttles — **63–194 ms** in an actively painting tab, **210–390 ms**
measured while the preview tab sat in the background. The figure is a range because the same call
on the same data measures differently in a throttled tab. The cursor badge adds nothing to it: one
empty div per panel, and its eight lines are rebuilt only when the candle under the pointer changes.

### 2.2 The chart

One chart instance per (session, timeframe), **one pane**, one time axis under it:

```
pane 0  candles + SMA(2)/(9)/(44)                 the whole pane
        the green-arrow markers under their bars, the red ones above them
──────────  time axis
        analytics table (10 metric rows + the time label row, one column per candle,
                         horizontally scrollable)
```

A chart opens on its **latest 100 candles** (`[sheet] window_bars`) with the bars sized to fill the
pane, so all five timeframes open at the same readable scale instead of the 12 s tape's 1,880 bars
being squeezed into a smear. Scroll or drag right for the earlier bars and left to come back;
**Reset zoom** and a double-click both return to the latest 100. The window is a **view, not a
truncation**: both arrow rules, the ten-row table, the CSV and the JSON all cover every candle of
the session. The `100` the sheet prints here is a cell filled from `[sheet] window_bars` at load,
not a copy of it: change the recipe and the sheet's own description of itself changes with it.

Both arrow series are attached to the candle series itself, so they scroll with the candles and the
table is unchanged by them. The SMA 2/9/44 **change (%)** series are *not* plotted over the
candles: they are read from the table and the exports, one column per candle.

### 2.3 Interaction

- **Session strip** switches day. The timeframe choice is shared, so the scale you were reading is kept when the session changes. Keys: `[` and `]` step back and forward a session.
- **Crosshair** gives a live read-out of time, O/H/L/C, change (pts and %), all three price averages, **all three indicator changes, all three run lengths, the SMA 2 vs SMA 9 direction streak, the selected candle's strict SMA 2 vs SMA 9 cross (or `none`), the SMA 9 vs SMA 44 distance it carried, which side those two averages sit on, and whether each of the two arrow rules fired**, the ATM
strike and the tick count behind the bar. The two crossing cells always describe that same candle, and read `none` / empty when it carries no crossing; with no crosshair they describe the last candle in the timeframe, like every other cell on that line. Each run cell names its own period (`SMA2 run`, `SMA9 run`, `SMA44 run`), so no cell has to be identified by its position in the line.
- **A cursor badge** follows the pointer inside the chart with the analytics families for the candle underneath it, in the table's own order and wording: `SMA2/SMA9/SMA44 run`, `SMA2v9 dir`, `cross` (`ABOVE` / `BELOW` / `none`), `d(9,44)` (the distance, or `—` when there is none), `9v44` (the side SMA 9 and SMA 44 sit on, or `none` where the pair has no side) and one line per rule — `green arrow` and `red ▼ arrow` (`▲` / `▼` on a candle that rule fired on, `—` otherwise, each read from the same flag array its marker is drawn from). It reads the same arrays the table and the exports are built from and formats through the same helpers, so it cannot disagree with either; it flips to the left of the cursor near the right edge, is clamped inside the chart, takes no clicks (`pointer-events:none`) and moves by `transform` only, so a sweep costs no layout. It is hidden the moment the pointer leaves the chart, on any timeframe or session switch, and in print — the printed sheet carries the table.
- The matching **candle column in the analytics table highlights and scrolls into view**, and the matching ledger row highlights — one hover drives all three.
- Wheel = zoom, drag = pan, double-click = back to the latest 100; **Reset zoom** re-fits the window.
- Keyboard: `1`–`5` switch timeframes; `←` `→` / `Home` / `End` move within the timeframe tab list.
- **The price-pane periods are live** — retype one and its line, the ledger columns, chips and matrix recompute. The analytics table and the **two arrows** do **not** move: they stay pinned to SMA 2, 9 and 44 and to the recipe's own thresholds.
- Sub-minute timeframes put seconds on the time axis (`09:30:00`); minute timeframes show `09:30`.

### 2.4 Lazy sessions and the ledger appendix

Only the first session is materialised at boot; the others are built the first time they are
opened (measured on a fresh load at a 420 px viewport: **137 ms** to open the second session,
**56 ms** the third, **15 ms** to come back to one already built). Every panel id is keyed by
session *and* timeframe, so nothing collides when three sessions are open at once — each keeps its
own charts, its own analytics table and its own zoom state.

The candle ledger (OHLC + averages + analytics per bar) sits *after* the indicator table as a
secondary view. Above 500 bars it starts behind a **Show ledger (1,880 bars)** button, so the
analytics table — the actual deliverable — is what renders at boot. Nothing is truncated.

---

## 3. The analytics rows

### 3.1 Row reference

Ten metric rows under one time row, one column per candle. Every value is computed in exact
integer paise with half-up rounding, and the CSV, the JSON, the rendered cell and the crosshair
all read the same series.

| # | Row label | The cell holds | Empty when |
| --- | --- | --- | --- |
| — | `Candle / Time` | the bar's open time in IST (`09:30:00` below a minute, `09:30` at and above) | never |
| A1–A3 | `SMA 2/9/44 Change (%)` | `(current − previous) / previous × 100`, signed, 4 decimals | the previous average does not exist — the first *n* candles of that row (*n* = 2 / 9 / 44) — or it is zero |
| A4–A6 | `SMA 2/9/44 Consecutive Count (+N / −N)` | the length of the unbroken run of rising / falling changes ending at this candle | never: a zero or unmeasurable change resets both runs to `+0 / −0` |
| A7 | `SMA 2 vs SMA 9 Direction Streak (+ABOVE / −BELOW)` | consecutive candles with SMA 2 above SMA 9 while SMA 9 rises, or below it while SMA 9 falls | never: neither condition holding resets the row to `+0 / −0` |
| A8 | `SMA 2 vs SMA 9 Cross Direction` | `ABOVE` / `BELOW` on the candle SMA 2 strictly crossed SMA 9 | no crossing on this candle, an equal pair on either candle, a missing average, or the session's first candle |
| A9 | `SMA 9 vs SMA 44 Distance (%) at SMA 2/SMA 9 Cross` | `((SMA 9 − SMA 44) / SMA 44) × 100`, signed, 4 decimals, on the crossing candle | A8 is empty, or SMA 9 or SMA 44 is unavailable, or SMA 44 is zero |
| A10 | `SMA 9 vs SMA 44 (ABOVE / BELOW)` | which side of each other those two averages sit on: `ABOVE` when SMA 9 > SMA 44, `BELOW` when SMA 9 < SMA 44 | the two are exactly equal on that candle, or SMA 44 has no value yet (the first 43 candles) |

The supplementary column `sma2_vs_sma9_distance_pct_at_cross` — `((SMA 2 − SMA 9) / SMA 9) × 100`
read on the crossing candle, under the same blank rules — ships in the CSV and the JSON but is not a
table row. It is near zero by construction, since it is measured on the candle the pair changed
side.

### 3.2 The consecutive counts

Each row reports the length of the **current unbroken run**, never a running total: a rise extends
the rising run and drops the falling run to 0; a fall does the mirror image; a reversal therefore
starts a new run at `+1` (or `−1`); a change of exactly zero resets **both** runs to 0. The three
periods are counted independently, so a fresh rise after a fall reads `+1 / −0`.

Blank, zero and run length are three different things. A blank cell is "no previous average yet";
`0.0000` is "the average did not move"; `+0 / −0` means no live run in either direction — which is
what a zero change leaves behind.

### 3.3 The direction streak

Row A7 pairs SMA 2 with SMA 9 and is counted on the same candle's `SMA 9 Change (%)` the row above
displays:

- `+n / −0` — consecutive candles in which SMA 2 is **above** SMA 9 **and** SMA 9 is rising.
- `+0 / −n` — consecutive candles in which SMA 2 is **below** SMA 9 **and** SMA 9 is falling.
- Only one side can ever be non-zero. A candle satisfying neither rule — the two averages equal, SMA 9's change rounding to `0.0000`, or SMA 2 above while SMA 9 falls (and the mirror image) — resets the row to `+0 / −0`, so a switch from BELOW to ABOVE starts the new streak at 1.

The rule reads the change **at the precision the sheet shows**. `SMA 9 Change (%)` is printed at 4
decimals, so a move that rounds to `0.0000` counts as neither side and resets the row — the same
reading the consecutive counts above it use. This is deliberate rather than incidental: across the
three sessions 57 of the 9,120 measured candles carry a genuine but far-below-4-decimal SMA 9 move,
and treating those as a direction would show a streak continuing on a cell the reader sees as
`0.0000`. No move whose rounded value is non-zero has a sign different from the underlying one.

The direction streak is **not** the crossing row: A7 counts consecutive candles and is `0` on most
of them, while A8 fires on the single candle the pair changes side. Nor is it the relationship row
below, which pairs a different two averages and carries no change condition at all.

### 3.4 The two crossing rows

**A8 — `SMA 2 vs SMA 9 Cross Direction`.** A crossing is a change of side, not a relationship, and
it is decided by comparing the current candle with the previous one:

- `ABOVE` when `previous_sma2 < previous_sma9` **and** `current_sma2 > current_sma9`
- `BELOW` when `previous_sma2 > previous_sma9` **and** `current_sma2 < current_sma9`
- empty otherwise — the pair stayed on the same side, either candle's two averages are equal (an equal pair is never a *strict* crossing), an average is unavailable on either candle, or it is the first candle of the session, which has no predecessor.

The comparisons run on the unrounded averages, so rounding can neither invent nor hide a crossing,
and each session's bars start at its own first candle, so nothing is carried across a session
boundary.

**A9 — `SMA 9 vs SMA 44 Distance (%) at SMA 2/SMA 9 Cross`.** `((SMA 9 − SMA 44) / SMA 44) × 100`
read on the crossing candle itself, from that candle's own averages: `22,500` against `22,400`
reads `+0.4464`, `22,300` against `22,400` reads `−0.4464`, equal averages read `0.0000`. It is
blank when there is no crossing, when either average is unavailable, or when SMA 44 is zero. The
sign says which side SMA 9 sits on and the magnitude how far apart the slow pair was. No future
candle is read.

**Neither row is a signal.** They name where a change of side happened and how far apart SMA 9 and
SMA 44 were at that moment. No marker, arrow or buy/sell verdict is drawn anywhere, on any chart, in
any artifact.

### 3.5 The SMA 9 vs SMA 44 relationship

**A10 — `SMA 9 vs SMA 44 (ABOVE / BELOW)`.** Which side of each other the two averages sit on,
written on the candle itself:

- `ABOVE` when `SMA 9 > SMA 44` on that candle; `BELOW` when `SMA 9 < SMA 44`.
- empty when the two are exactly equal — a tie belongs to neither side — or when SMA 44 has no value yet, which is every candle before its 44th.
- no previous candle is read, so the word holds on every candle both averages exist.

This is the **relationship**, not a crossing, and the two rows differ on almost every candle: A8
fires only on the 246 candles of the 12 s tape of 2026-10-13 on which SMA 2 changed side, while A10
carries a word on all 1,837 candles where SMA 44 exists — 1,029 `ABOVE`, 784 `BELOW` and 24 exact
ties. Read the pair as "which side are they on" (A10) against "when did SMA 2 swap with SMA 9"
(A8). It draws nothing itself — but it is one of the three values the green arrow reads, and — read the
other way round — one of the three its red mirror reads.

### 3.6 The two arrow rules: the green one, and the red mirror

The sheet draws **two** markers: a **green arrow** below the bar and a **red ▼ arrow** above it, on
the **price pane of every timeframe**. The green one is drawn on the candles where **all seven**
conditions hold. Four are read from the
candle itself, three from the candle before it — and every one of them is a value a row above
already prints (the fourth reading is the session's own dashboard, joined onto the candle's minute
by `nifty/data/flow.py`):

| # | Read from | Condition | Where it comes from | The recipe's key |
| --- | --- | --- | --- | --- |
| 1 | the candle | `SMA 2 vs SMA 9 Cross Direction` reads `ABOVE` | row A8 | `cross_direction` |
| 2 | the candle | `SMA 9 vs SMA 44 Distance (%) at SMA 2/SMA 9 Cross` is `0.0000 – 0.0250`, **both ends included** | row A9 | `distance_pct_at_cross_min` / `distance_pct_at_cross_max` |
| 3 | the candle | `SMA 9 vs SMA 44 (ABOVE / BELOW)` reads `ABOVE` | row A10 | `relation` |
| 4 | the previous candle | `SMA 44 Change (%)` **strictly above** `0.0005` | row A3 | `chg_pct_min` |
| 5 | the previous candle | `SMA 9 Consecutive Count (+N / −N)` is a **falling** run of `7` to `15` (inclusive) | row A5 | `streak_minus_min` / `streak_minus_max` |
| 6 | the previous candle | `SMA 44 Consecutive Count (+N / −N)` is a **rising** run of `7` or more | row A6 | `streak_plus_min` |

Every key is the name of the row the condition reads — the same words the table, the CSV header and
the code use (`distance_pct_at_cross`, `chg_pct`, `streak_minus`, `streak_plus`) — plus the bound it
puts on that value (`_min` / `_max`). The periods are the one thing the key does **not** carry: they
belong to the section that defines the row, so `distance_pct_at_cross` reads whichever
`sma{from}_vs_sma{to}_distance_pct_at_cross` the `[cross]` block names. That one name is then spent
once per layer rather than invented four times:

| Layer | `distance_pct_at_cross_min` |
| --- | --- |
| `config/nifty.json`, `[signal]` | `distance_pct_at_cross_min = 0.0` |
| `nifty/recipe/config.py` | `Config.signal_distance_pct_at_cross_min` |
| `nifty/signals/rules.py` | `GreenArrowRule.distance_pct_at_cross_min` |
| the payload / the exports | `distancePctAtCrossMin` (and the scaled integer `distancePctAtCrossMinScaled`) |
| `templates/sheet.html` | `SIG_DISTANCE_PCT_AT_CROSS_MIN` |

The per-condition tallies travel under the row names too (`cross_direction`,
`distance_pct_at_cross`, `relation`, `chg_pct`, `streak_minus`, `streak_plus`), so a count, a
threshold and a drawn arrow can be traced back to one row and one recipe key.

**The red arrow is the mirror of that rule, and the code derives it rather than restating it.** The
recipe declares **one** rule; `GreenArrowRule.mirrored()` returns the other, and `[signal] red_arrow`
is the only red key the recipe carries — an on/off switch, not a threshold. There is therefore no
second block to keep in step and no way for the two to disagree: the mirror flips each of the six
comparisons instead of writing six more. What "the opposite" means here is *price inversion* — the
green rule reads a market turning up (SMA 2 crossing **above** SMA 9 while the slow pair is close
and sits above it, after the fast average has been falling and the slow one rising), and the red rule
is that same reading of a market turning down, condition for condition:

| # | Read from | The green arrow reads | The red mirror reads |
| --- | --- | --- | --- |
| 1 | the candle | `Cross Direction` = `ABOVE` | `Cross Direction` = `BELOW` |
| 2 | the candle | distance `0.0000 – 0.0250` | distance `−0.0250 – 0.0000` — the same window, negated, its ends swapped |
| 3 | the candle | `SMA 9 vs SMA 44` = `ABOVE` | `SMA 9 vs SMA 44` = `BELOW` |
| 4 | the previous candle | `SMA 44 Change (%)` **strictly above** `0.0005` | `SMA 44 Change (%)` **strictly below** `−0.0005` |
| 5 | the previous candle | SMA 9 count a **falling** run of `7`–`15` | SMA 9 count a **rising** run of `7`–`15` |
| 6 | the previous candle | SMA 44 count a **rising** run of `7`+ | SMA 44 count a **falling** run of `7`+ |

The mirror travels the same layers under its own names — `red_arrow` is the column, `redSignal` the
payload block, `RED_KEY` the pipeline's, and the sheet's own `arrowRule(META.redSignal …)` the
browser's copy of it:

| Layer | The red rule |
| --- | --- |
| `config/nifty.json`, `[signal]` | `red_arrow = true` — the switch, and nothing else: no red threshold to drift |
| `nifty/recipe/config.py` | `Config.signal_red_enabled`, and `red_rule_obj()` = `signal_rule_obj().mirrored()` |
| `nifty/output/meta.py` | `red_signal()` — the mirror's block, in the same keys and the same order as `signal()` |
| `nifty/signals/rules.py` · `nifty/core/keys.py` | `GreenArrowRule.mirrored()`, `add_signal` and `RED_KEY` — one implementation writes both flags |
| the payload / the exports | the `redSignal` block beside `signal`, and the `red_arrow` column beside `green_arrow` |
| `templates/sheet.html` | `var RED = arrowRule(META.redSignal …)` beside `var SIG = …`, with `RULES = [SIG, RED]` |

Six conditions, all required: an AND of six, not a score. The session's first candle can never carry
an arrow, because it has no previous candle to read, and nothing reads a later bar, so the arrow can
never move once a candle has closed. Conditions 1–2 are compared at the sheet's own percentage
precision (`0.025` is the integer `250` at four decimals, not a float); condition 3 is a word read
off the candle — a tie in an average pair belongs to neither side, so it refuses the candle; and
condition 5 is a strict `>`, so a previous change of exactly `0.0005` does **not** qualify. Condition
4 compares the two dashboard columns of the candle's own minute, so it is the one reading that arrives
from outside the tape: a session with no dashboard does not read it at all.

**Every one of those seven conditions is a key read the other way round, and the sheet states the
recipe it ran for both rules.** There is no threshold in the code and none in the prose either: the
Method list's green-arrow bullet is built from the payload's own `[signal]` block at load
(`m-cross-pair`, `m-distance-window`, `m-chg-min`, `m-minus-run`, `m-plus-run`, …) and its
red-arrow bullet from the same block's mirror in `redSignal` (`r-cross-pair`, `r-distance-window`,
`r-chg-min`, `r-minus-run`, `r-plus-run`, …), so a build with `--set signal.chg_pct_min=0.01`
prints `0.0100` in the green bullet and `−0.0100` in the red one instead of `0.0005` / `−0.0005`.
One generator fills both bullets from the two rule objects, prefixing the cells `m-` and `r-`, so
neither can follow a threshold the other does not. `enabled = false` stamps the green bullet as off,
and `red_arrow = false` stamps the red one. Sheet and pipeline read one rule, so what the sheet says
it did is what it did.

Where the sheet's **two marker rules** show up — every one of them twice, generated from the two
rule objects rather than written out per rule:

- **the chart** — the arrows themselves: the green ones below their bars, the red ones above them;
- **the panel chips** — `green arrows 9 of 1,880 bars` and `red arrows 3 of 1,880 bars`, each
  tooltipped with its own whole rule sentence;
- **the comparison matrix** — two rows per rule, the tightest gate (a `2v9` cross whose distance is
  inside that rule's window) beside the candles that pass all seven, so a timeframe that never fires
  reads `0 of 126 bars` rather than looking empty;
- **the KPI cards and the masthead** — how many arrows each rule draws across the active session's
  five timeframes;
- **the cursor badge** — a `green arrow ▲` line and a `red arrow ▼` one (or `—`) for the candle under
  the pointer;
- **the candle-ledger appendix** — a `green arrow` column printing `▲` and a `red arrow` column
  printing `▼` on the flagged rows;
- **the CSV and the JSON** — the `green_arrow` and `red_arrow` columns, `1` on a flagged candle and
  `0` everywhere else, plus each marker's own descriptor (`belowBar` / `arrowUp` / the sheet's green,
  `aboveBar` / `arrowDown` / the sheet's red) in the browser's JSON export.

Both rules are a **step in the pipeline**, not a browser-only decoration: `nifty/signals/rules.py`
owns `GreenArrowRule` (the periods, the two words and the six thresholds), its `mirrored()`, and
`add_signal`, which writes each flag from the columns the steps above it wrote. The recipe's own
step list carries the two as separate entries — `signal` and `red_signal` — because they ship as
separate columns. The sheet recomputes them from the bars it was given — one rule engine run twice,
from the two rule objects — and `verify.py` runs the sheet's **own** function under node over every
delivered candle, so each drawn arrow and its exported `1` are proved to be the same value on all
9,255 of them, for both rules.

**Two of the price conditions are implied by the other four on these sessions.** Counting the
candles each condition *alone* would have allowed (removing it and keeping the others) gives
**25** for the distance window, **24** for the cross, **51** for the falling run and **19** for the
rising run — and **18** for the relationship word and **18** for the previous-candle change, which is
exactly the 18 candles that fire. So on this tape the relationship word and the previous-candle
change never independently refused a candle; the other four each did. That is a fact about three days
of NIFTY, not a defect in the rule, and the verifier asserts the weaker invariant that no condition
can ever refuse an *arrow* (every arrow satisfies all seven) while at least four conditions must be
independently binding. Tighten the window or loosen a run and the balance changes; the recipe is
where to do it.

**The mirror's own funnel is the tighter one, and there every condition bites.** Counting the same
way for the red rule — the candles its *other six* mirrored conditions would have allowed — gives
**36** for the mirrored distance window, **30** for the `BELOW` cross, **30** for the previous-candle
change, **24** for the `BELOW` relationship, **72** for the rising run and **34** for the falling run,
against the **12** candles that fire. All six of the mirror's conditions therefore refused a candle
the other six would have allowed — the verifier counts both funnels with the same code and asserts
the same invariant on each. The two rules are also disjoint on every one of the 9,255 candles: no
candle carries both arrows, because one candle cannot carry an `ABOVE` crossing and a `BELOW` one at
once.

---

## 4. Data and exports

### 4.1 Resampling and columns

Each session's tape is bucketed on wall-clock IST boundaries via `epoch − epoch % tf`. The IST
offset (19,800 s) divides exactly by 12 / 36 / 60 / 180 / 300, so every timeframe aligns to the IST
clock with no timezone arithmetic.

| Column | Meaning |
| --- | --- |
| `time_ist`, `epoch` | Bar open time. `epoch` is the true Unix timestamp; `time_ist` is IST wall clock. |
| `open`, `high`, `low`, `close` | First / max / min / last tick in the bucket. |
| `change`, `change_pct` | vs the previous bar's close. Always explicitly signed — a zero change is written `+0.00`. |
| `sma2`, `sma9`, `sma44` | Simple moving averages of `close`. Empty until enough bars exist (44 bars for SMA44). |
| `sma2_chg_pct`, `sma9_chg_pct`, `sma44_chg_pct` | Per-candle percentage change of each average, 4 decimals. Empty when the previous average does not exist. |
| `sma2_streak_plus`, `sma2_streak_minus` (and `9`, `44`) | Length of the current run of consecutive rising / falling changes through this candle. |
| `sma2_vs_sma9_above_streak`, `sma2_vs_sma9_below_streak` | The direction-streak row: how many consecutive candles ending here satisfy the ABOVE rule (`sma2 > sma9` with a positive `sma9_chg_pct`) and the BELOW rule (`sma2 < sma9` with a negative one). Only one of the two is ever non-zero. |
| `sma2_vs_sma9_cross_direction` | The strict crossing row: `ABOVE` when `sma2` was below `sma9` on the previous candle and is above it now, `BELOW` for the mirror image, empty otherwise. Read from the current and previous candle only; an equal pair on either candle is never a crossing. |
| `sma9_vs_sma44_distance_pct_at_cross` | `((sma9 − sma44) / sma44) × 100` on the crossing candle, 4 decimals, signed. Empty when the candle carries no crossing, when either average is unavailable or when `sma44` is zero. |
| `sma2_vs_sma9_distance_pct_at_cross` | The supplementary distance `((sma2 − sma9) / sma9) × 100` on the same crossing candle, under the same blank rules. Near zero by construction, since it is measured on the candle the pair changed side. |
| `sma9_vs_sma44_relation` | The side relationship row: `ABOVE` when `sma9 > sma44` on that candle, `BELOW` when it is below, empty when the two are exactly equal or `sma44` has no value yet. A comparison of this candle's own two averages, with no previous candle involved. |
| `ce_oi_change`, `pe_oi_change` | The session's dashboard columns for the minute this candle **opens** in: the feed's own call and put open-interest change for that minute, copied as they stand. Blank on a session that ships no dashboard, which is how the flow condition knows not to be read. |
| `green_arrow` | The green arrow: `1` on the candles where all seven conditions of the rule hold (four read from this candle — its `sma2_vs_sma9_cross_direction`, its `sma9_vs_sma44_distance_pct_at_cross`, its `sma9_vs_sma44_relation` and its minute's `pe_oi_change` above `ce_oi_change` — and three from the previous candle's `sma44_chg_pct`, `sma9_streak_minus` and `sma44_streak_plus`), `0` on every other candle. The same flag the arrow under the bar is drawn from. |

### 4.2 Files

Files land under `output/nifty/data/<session date>/`, one CSV and one JSON per timeframe, plus
`output/nifty/data/session_summary.json` covering every session. The CSV header, the JSON bar keys and
the rendered table all follow one column list, so they cannot drift apart.

The dashboard's `flow` rows are the feed's own summary rather than a resampling of the tape, so
they are not written into `output/nifty/data/`: they travel in the sheet payload (`days[].flow`) and are
drawn there. The sheet plots the per-minute `ce_oi_change` / `pe_oi_change` columns and leaves the
`cumulative_ce` / `cumulative_pe` totals the same rows also carry where they are.

### 4.3 What the three sessions look like

| Session | Bars | Blank (2/9/44) | Zero (2/9/44) | SMA 2 last · longest | SMA 9 last · longest | SMA 44 last · longest |
| --- | --- | --- | --- | --- | --- | --- |
| **2026-10-13** — 22,291 ticks, +357.80 pts (+1.600 %) | | | | | | |
| · 12 s | 1,880 | 2 / 9 / 44 | 83 / 91 / 65 | +0 / −0 · +17 / −19 | +0 / −0 · +36 / −39 | **+13 / −0** · **+199 / −144** |
| · 36 s | 627 | 2 / 9 / 44 | 24 / 18 / 8 | +0 / −0 · +13 / −12 | +5 / −0 · +35 / −44 | +11 / −0 · +156 / −77 |
| · 1 min | 376 | 2 / 9 / 44 | 12 / 5 / 6 | +0 / −0 · +13 / −10 | +3 / −0 · +39 / −35 | +91 / −0 · +91 / −70 |
| · 3 min | 126 | 2 / 9 / 44 | 2 / 1 / 0 | +2 / −0 · +10 / −8 | +3 / −0 · +32 / −15 | +59 / −0 · +59 / −16 |
| · 5 min | 76 | 2 / 9 / 44 | 0 / 0 / 0 | +2 / −0 · +7 / −7 | +19 / −0 · +19 / −14 | +20 / −0 · +20 / −6 |
| **2026-10-14** — 22,276 ticks, −93.05 pts (−0.410 %) | | | | | | |
| · 12 s | 1,880 | 2 / 9 / 44 | 91 / 85 / 83 | +0 / −0 · +17 / −14 | +0 / **−5** · +42 / −44 | +0 / **−5** · +135 / −144 |
| · 36 s | 627 | 2 / 9 / 44 | 26 / 17 / 5 | +0 / −2 · +12 / −13 | +0 / −2 · +29 / −42 | +19 / −0 · +71 / −91 |
| · 1 min | 376 | 2 / 9 / 44 | 14 / 6 / 10 | +0 / −1 · +9 / −13 | +0 / −1 · +32 / −32 | +0 / −1 · +44 / −63 |
| · 3 min | 126 | 2 / 9 / 44 | 3 / 0 / 0 | +0 / −1 · +11 / −8 | +5 / −0 · +14 / −18 | +6 / −0 · +16 / −48 |
| · 5 min | 76 | 2 / 9 / 44 | 1 / 0 / 0 | +0 / −1 · +7 / −11 | +0 / −1 · +9 / −13 | +0 / **−32** · +0 / −32 |
| **2026-10-15** — 22,265 ticks, +326.05 pts (+1.438 %) | | | | | | |
| · 12 s | 1,880 | 2 / 9 / 44 | 84 / 84 / 58 | +0 / −0 · +16 / −15 | +0 / −0 · +37 / −28 | +11 / −0 · +184 / −92 |
| · 36 s | 627 | 2 / 9 / 44 | 25 / 19 / 3 | +0 / −0 · +11 / −10 | +4 / −0 · +54 / −23 | +4 / −0 · +144 / −134 |
| · 1 min | 376 | 2 / 9 / 44 | 12 / 9 / 7 | +0 / −0 · +8 / −10 | +3 / −0 · +37 / −41 | +3 / −0 · +98 / −68 |
| · 3 min | 126 | 2 / 9 / 44 | 2 / 0 / 0 | +2 / −0 · +11 / −6 | +2 / −0 · +28 / −26 | +0 / −16 · +66 / −16 |
| · 5 min | 76 | 2 / 9 / 44 | 0 / 0 / 0 | +2 / −0 · +14 / −13 | +2 / −0 · +22 / −13 | +2 / −0 · +26 / −4 |

Four things this table makes checkable rather than assertable:

- **The blank rule is exactly the period.** 2 blanks in the SMA 2 row, 9 in the SMA 9 row, 44 in the SMA 44 row, on every timeframe of every session — the candles with no predecessor *of that period*. No other cell is blank.
- **The values are runs, not running totals.** On the 12-second scale of 2026-10-13, SMA 44 rose more than a hundred times yet the reported run is **+13**: a streak can never absorb yesterday's rises. The 5-minute row of 2026-10-14 is the mirror image — the session ends in a 32-long *falling* run, the longest of its day.
- **Reversals and zeros really happen.** There are 83–91 exact-zero changes on any 12-second session and thousands of reversals, so the reset branches are exercised, not merely declared: `verify.py` asserts both runs read 0 at every zero, and that the very next move starts again at 1.
- **The three periods are independent**, and so are the sessions: the same clock time on 2026-10-14 carries a falling run while 2026-10-15 carries a rising one — the day strip really swaps the data.

### 4.4 The SMA 2 vs SMA 9 direction streak, per session

`last` is the value in the final candle's cell; `longest` the best each direction ever reached;
`switches` the number of times the row changed side (each restarting at 1); the last column counts
the candles carrying each side and the `+0 / −0` resets.

| Session | Timeframe | Last | Longest ABOVE · BELOW | Switches | ABOVE · BELOW · reset candles |
| --- | --- | --- | --- | --- | --- |
| **2026-10-13** | 12 s | +0 / −0 | +36 · −31 | 47 | 808 · 674 · 398 |
| | 36 s | +5 / −0 | +20 · −27 | 13 | 280 · 210 · 137 |
| | 1 min | +3 / −0 | +28 · −27 | 11 | 186 · 123 · 67 |
| | 3 min | +3 / −0 | +27 · −11 | 1 | 65 · 31 · 30 |
| | 5 min | +19 / −0 | +19 · −14 | 2 | 40 · 17 · 19 |
| **2026-10-14** | 12 s | +0 / −5 | +31 · −25 | 52 | 726 · 762 · 392 |
| | 36 s | +0 / −2 | +20 · −31 | 20 | 235 · 244 · 148 |
| | 1 min | +0 / −1 | +24 · −28 | 12 | 156 · 142 · 78 |
| | 3 min | +5 / −0 | +12 · −15 | 1 | 47 · 50 · 29 |
| | 5 min | +0 / −0 | +7 · −12 | 3 | 23 · 25 · 28 |
| **2026-10-15** | 12 s | +0 / −0 | +30 · −27 | 52 | 860 · 660 · 360 |
| | 36 s | +4 / −0 | +30 · −20 | 23 | 294 · 199 · 134 |
| | 1 min | +3 / −0 | +31 · −15 | 10 | 174 · 111 · 91 |
| | 3 min | +2 / −0 | +28 · −26 | 5 | 67 · 40 · 19 |
| | 5 min | +2 / −0 | +15 · −13 | 3 | 42 · 15 · 19 |

Three things this row makes checkable:

- **The reset and switch branches are exercised, not declared.** Every timeframe switches side at least once (1 to 52 times) and resets hundreds of times on the 12 s scale, so the "start the new streak at 1" rule is proved on live data rather than asserted.
- **The row tracks direction, not price.** On 2026-10-14 — the only down day, −93.05 pts — the ABOVE and BELOW candle counts are nearly balanced (726 vs 762) while on the up days ABOVE dominates (860 vs 660). The session that ended falling closes the 12 s and 36 s rows with a live BELOW run.
- **One side at a time, always.** The verifier asserts that no candle ever carries both a non-zero ABOVE and a non-zero BELOW count, on all 15 combinations.

### 4.5 The strict SMA 2 vs SMA 9 crossing, and its distance, per session

`ABOVE · BELOW` are the strict crossings in each direction, `first · last` the candle indexes they
occur at, `blank` the crossings whose distance row is empty because SMA 44 does not exist yet, and
`last · min · max` the signed distance percentages those crossings carried.

| Session | Timeframe | ABOVE · BELOW · total | First · last | Last direction | Distance count · blank | last · min · max (%) |
| --- | --- | --- | --- | --- | --- | --- |
| **2026-10-13** | 12 s | 122 · 124 · **246** | 19 · 1795 | BELOW | 242 · 4 | +0.0578 · −0.0848 · +0.1382 |
| | 36 s | 38 · 39 · 77 | 11 · 600 | BELOW | 71 · 6 | +0.0599 · −0.1177 · +0.2254 |
| | 1 min | 21 · 22 · 43 | 37 · 361 | BELOW | 41 · 2 | +0.1139 · −0.1555 · +0.2614 |
| | 3 min | 8 · 8 · 16 | 18 · 117 | ABOVE | 12 · 4 | +0.4193 · −0.1028 · +0.4193 |
| | 5 min | 4 · 4 · 8 | 12 · 52 | ABOVE | 4 · 4 | +0.0727 · +0.0647 · +0.0748 |
| **2026-10-14** | 12 s | 127 · 126 · **253** | 13 · 1796 | ABOVE | 251 · 2 | −0.0179 · −0.1573 · +0.1249 |
| | 36 s | 47 · 46 · 93 | 11 · 599 | ABOVE | 89 · 4 | −0.0289 · −0.2847 · +0.1719 |
| | 1 min | 25 · 25 · 50 | 10 · 359 | ABOVE | 45 · 5 | −0.0578 · −0.3873 · +0.2098 |
| | 3 min | 7 · 6 · 13 | 9 · 120 | ABOVE | 9 · 4 | −0.0030 · −0.4354 · +0.0651 |
| | 5 min | 0 · 5 · 10 | 10 · 72 | ABOVE | 5 · 5 | −0.1396 · −0.4251 · −0.1396 |
| **2026-10-15** | 12 s | 107 · 109 · **216** | 14 · 1803 | BELOW | 211 · 5 | −0.0154 · −0.0899 · +0.1320 |
| | 36 s | 44 · 45 · 89 | 9 · 606 | BELOW | 87 · 2 | −0.0562 · −0.0900 · +0.2257 |
| | 1 min | 29 · 29 · 58 | 9 · 367 | BELOW | 55 · 3 | −0.0878 · −0.1204 · +0.2791 |
| | 3 min | 5 · 5 · 10 | 37 · 124 | ABOVE | 9 · 1 | −0.2243 · −0.2243 · +0.2611 |
| | 5 min | 5 · 5 · 10 | 24 · 74 | ABOVE | 4 · 6 | −0.1603 · −0.1603 · +0.2986 |

1,192 crossing cells in total, and five things this table makes checkable rather than assertable:

- **Both directions fire on every tape.** The 12 s scales carry 200+ crossings each — 246 on 2026-10-13, 253 on 2026-10-14, 216 on 2026-10-15 — and even the quietest 5-minute tape still crosses both ways, so neither branch is declared and unused. `verify.py` fails if either direction is missing from the whole delivery.
- **The blank set is exactly the crossings inside the warm-up.** 4 blanks on the 12 s tape of 2026-10-13 are the crossings at indexes 19, 25, 27 and 33 — all before SMA 44 has its first value at index 44. No crossing after warm-up is ever blank.
- **All three distance signs occur in the delivered data.** 130 positive, 111 negative and **one exactly `0.0000`** on the 12 s tape of 2026-10-13, so the equality branch is a live case rather than a theoretical one. The verifier also asserts the converse: a blank distance only ever sits on a candle whose SMA 44 is unusable.
- **The distance measures how close the slow pair was, not how big the crossing was.** On the 12 s tape of 2026-10-13 every crossing sits within ±0.14 % of SMA 44; on the 5-minute tape the same measurement reaches −0.42 %. All five distances on the 5-minute tape of 2026-10-14 are negative — SMA 9 stayed under SMA 44 for that whole falling session, and its last crossing closes at −0.1396 %.
- **The two rows are not the direction streak.** The streak counts consecutive candles and is `0` on most of them; a crossing fires on exactly 246 of the 1,880 candles on the 12 s tape of 2026-10-13 and is blank on the other 1,634. The verifier asserts both rows independently and never derives one from the other.

### 4.6 The SMA 9 vs SMA 44 relationship, per session

`ABOVE · BELOW · blank` are the candle counts in each state, `longest` the longest unbroken run of
one side, and `switches` the number of times the row changed side (a move through a tie counts as
one switch).

| Session | Timeframe | Last | ABOVE · BELOW · blank candles | Longest ABOVE · BELOW run | Switches |
| --- | --- | --- | --- | --- | --- |
| **2026-10-13** | 12 s | ABOVE | 1,029 · 784 · 67 | +147 · −170 | 45 |
| | 36 s | ABOVE | 389 · 195 · 43 | +191 · −66 | 14 |
| | 1 min | ABOVE | 222 · 111 · 43 | +112 · −76 | 10 |
| | 3 min | ABOVE | 65 · 18 · 43 | +65 · −18 | 1 |
| | 5 min | ABOVE | 33 · 0 · 43 | +33 · −0 | 0 |
| **2026-10-14** | 12 s | BELOW | 908 · 897 · 75 | +122 · −171 | 52 |
| | 36 s | ABOVE | 290 · 294 · 43 | +79 · −96 | 14 |
| | 1 min | ABOVE | 152 · 181 · 43 | +48 · −65 | 10 |
| | 3 min | BELOW | 27 · 56 · 43 | +18 · −39 | 5 |
| | 5 min | BELOW | 2 · 31 · 43 | +2 · −31 | 1 |
| **2026-10-15** | 12 s | ABOVE | 1,074 · 737 · 69 | +162 · −76 | 60 |
| | 36 s | ABOVE | 352 · 232 · 43 | +147 · −140 | 12 |
| | 1 min | ABOVE | 201 · 132 · 43 | +77 · −82 | 10 |
| | 3 min | BELOW | 63 · 19 · 44 | +63 · −19 | 0 |
| | 5 min | BELOW | 25 · 8 · 43 | +25 · −8 | 1 |

4,832 ABOVE and 3,695 BELOW cells with 728 blanks (645 of them the 43-candle warm-up on each of the
15 tapes), and four things this table makes checkable:

- **The blank set is exactly the warm-up plus the ties.** Every tape blanks the 43 candles before SMA 44 has a value, and nothing else is blank except an exact tie between the two averages: 83 of them in the delivery (24 on the 12 s tape of 2026-10-13, 32 on 2026-10-14, 26 on 2026-10-15, and 1 on the 3-minute tape of 2026-10-15). 15 × 43 + 83 = the 728 blanks counted above.
- **Both sides appear on every session**, and the row is not a rare event the way a crossing is: it holds a word on 1,837 of the 1,880 candles of the 12 s tape of 2026-10-13, where the crossing row fires on 246. The quietest 5-minute tape still carries both sides across the three sessions.
- **The row tracks the slow pair, not the session's direction.** 2026-10-14 is the only falling day and the only one whose 12 s tape ends BELOW; on the up days the ABOVE count leads on every timeframe (1,074 against 737 on 2026-10-15).
- **A side can be held for a very long time.** The longest ABOVE run is +191 candles (36 s of 2026-10-13) while most tapes switch a handful of times, so the row is a state rather than an event — which is exactly what separates it from the crossing row above.

### 4.7 Arrows per rule, per session

The green rule first. `arrows` is the number of candles the six-condition rule fires on; `crosses`
the `2v9` crossings of that tape in its own direction, `in window` how many of them carried a
distance inside `0.0000 – 0.0250` per cent, and `distance range` the full span of distances those
crossings carried.

| Session | Timeframe | Arrows | ABOVE crosses | In window | Distance range (%) |
| --- | --- | --- | --- | --- | --- |
| **2026-10-13** | 12 s | **9** | 122 | 55 | −0.0848 · +0.1382 |
| | 36 s | 2 | 38 | 10 | −0.1177 · +0.2254 |
| | 1 min | 0 | 21 | 0 | −0.1555 · +0.2614 |
| | 3 min | 0 | 8 | 0 | −0.1028 · +0.4193 |
| | 5 min | 0 | 4 | 0 | +0.0647 · +0.0748 |
| **2026-10-14** | 12 s | 2 | 127 | 74 | −0.1573 · +0.1249 |
| | 36 s | 1 | 47 | 13 | −0.2847 · +0.1719 |
| | 1 min | 0 | 25 | 6 | −0.3873 · +0.2098 |
| | 3 min | 0 | 7 | 0 | −0.4354 · +0.0651 |
| | 5 min | 0 | 5 | 0 | −0.4251 · −0.1396 |
| **2026-10-15** | 12 s | 2 | 107 | 58 | −0.0899 · +0.1320 |
| | 36 s | 1 | 44 | 8 | −0.0900 · +0.2257 |
| | 1 min | 1 | 29 | 3 | −0.1204 · +0.2791 |
| | 3 min | 0 | 5 | 0 | −0.2243 · +0.2611 |
| | 5 min | 0 | 5 | 0 | −0.1603 · +0.2986 |

**18 arrows in all, on 7 of the 15 (session, timeframe) tapes.** Nine of them fall on the 12 s tape of
2026-10-13, at `09:32:12`, `09:37:48`, `09:51:36`, `09:52:12`, `10:01:12`, `12:23:48`, `13:39:12`,
`13:48:00` and `14:23:48` IST, each carrying a distance between `+0.0026 %` and `+0.0223 %`; the same
day's 36 s tape adds `14:00:36` and `15:03:36`. The remaining six spread over the other two sessions —
two on the 12 s tape of 2026-10-14 (`11:52:00`, `13:40:36`) and one on its 36 s tape (`09:56:24`), two
on the 12 s tape of 2026-10-15 (`10:04:24`, `11:44:48`), one on its 36 s tape (`10:58:12`) and one on
its 1-minute tape (`11:14:00`) — so the rule is not a property of one day. The rule does **not** fire on
the 3-minute or
5-minute tapes at all, and the reason is visible in the two right-hand columns: those tapes' crossings
simply never sit close enough to SMA 44. Every non-negative distance they carry is at least
`+0.0458 %` (3 min) and `+0.0647 %` (5 min) — 1.8× and 2.6× the window's `0.0250 %` ceiling — so the
distance condition refuses their crossings before the others are asked. The rule still **runs** on
all five timeframes and reports `0 of 126 bars` / `0 of 76 bars` in the comparison matrix, which is the
honest reading: a coarse bar hides the short-lived alignment the rule looks for.

Per-condition tallies over the whole delivery (how many candles each condition alone would allow):
`cross_direction 594 · distance_pct_at_cross 227 · relation 4,832 · chg_pct 4,150 · streak_minus 1,300 · streak_plus 3,865`.
The distance window is by far the tightest gate, and the three previous-candle conditions are what
turn a fifth of the tape's candles into candidates.

**The red ▼ mirror, per session.** The same columns for the mirrored rule: its own arrows, the
`BELOW` crossings of each tape, `window gate` — the candles whose distance sits inside the negated
window `−0.0250 – 0.0000`, that rule's first and tightest condition counted on its own, which is the
row the comparison matrix prints as `red arrows (cross + window)` — and the span of distances **its
own** `BELOW` crossings carried.

| Session | Timeframe | red ▼ arrows | BELOW crosses | Window gate | Distance range (BELOW crosses, %) |
| --- | --- | --- | --- | --- | --- |
| **2026-10-13** | 12 s | **3** | 124 | 76 | −0.0660 · +0.1382 |
| | 36 s | 0 | 39 | 8 | −0.1157 · +0.2254 |
| | 1 min | 0 | 22 | 3 | −0.0853 · +0.2614 |
| | 3 min | 0 | 8 | 1 | −0.0975 · +0.4059 |
| | 5 min | 0 | 4 | 0 | +0.0647 · +0.0697 |
| **2026-10-14** | 12 s | **4** | 126 | 56 | −0.1319 · +0.1249 |
| | 36 s | **2** | 46 | 11 | −0.1742 · +0.1719 |
| | 1 min | 0 | 25 | 6 | −0.3083 · +0.2098 |
| | 3 min | 0 | 6 | 1 | −0.1053 · +0.0628 |
| | 5 min | 0 | 5 | 0 | −0.2363 · −0.1595 |
| **2026-10-15** | 12 s | **3** | 109 | 48 | −0.0578 · +0.1320 |
| | 36 s | 0 | 45 | 8 | −0.0786 · +0.2257 |
| | 1 min | 0 | 29 | 6 | −0.1190 · +0.2791 |
| | 3 min | 0 | 5 | 0 | +0.0715 · +0.2020 |
| | 5 min | 0 | 5 | 0 | +0.2562 · +0.2986 |

The window gate column totals **224** mirrored-window candles against the green rule's **227** in its
own window, which is what makes the two rules comparable rather than mirror-images in name only.

**12 red arrows in all, on 4 of the 15 tapes** — three on the 12 s tape of 2026-10-13
(`10:22:48`, `11:18:00`, `15:05:12` IST), the densest run of the delivery on the 12 s tape of
2026-10-14 (`10:13:00`, `11:26:36`, `13:16:36`, `14:15:48`) plus two on that day's 36 s tape
(`10:22:48`, `11:43:12`), and three closing the 12 s tape of 2026-10-15
(`15:00:36`, `15:08:36`, `15:15:36`). The mirror is sparser on the coarse tapes than the green rule
is and for the same reason read the other way: the negated window admits 1, 1 and 0 candles on the
three 3-minute tapes and none at all on the 5-minute ones, so no coarse candle ever reaches the last
condition — and those tapes still report `0 of 126` and `0 of 76` bars rather than nothing.

Per-condition tallies for the mirror, over the whole delivery:
`cross_direction 598 · distance_pct_at_cross 224 · relation 3,695 · chg_pct 2,848 · streak_minus 1,638 · streak_plus 2,593`
— and the same tightest-gate reading holds (the negated window, then the two runs), with the mirror's
own funnel in [§3.6](#36-the-two-arrow-rules--the-green-one-and-the-red-mirror) showing every one of
its conditions binding on the red candles it fires — and, because the mirrored flow condition (CE
above PE) refuses the red candles a PE-above-CE minute would have given it, a session can legitimately
deliver none, which the audit states and proves on a tape of its own instead.

---

## 5. The recipe and the package

### 5.1 The package

The pipeline is a package of six layers behind one entry point, so each concern has one home and a
reader knows where to look before opening anything. The layers are the shape of the build, top to
bottom: the vocabulary nothing else may import from (`core`), the recipe read into one `Config`
(`recipe`), a session turned into columns (`data`), what those columns mean (`signals`), what leaves
the build (`output`), and the trades booked on the arrows (`trade`). No layer imports one below it.

| Module | What it owns |
| --- | --- |
| `nifty/recipe/defaults.py` | **The built-in recipe**: every default a `Config` falls back to, plus the `SECTIONS` / `DEFAULTS` maps that turn an unknown table or key in the file into a named error. |
| `nifty/recipe/config.py` | The recipe reader: a recipe file over those defaults (TOML or JSON by suffix), `--set` overrides, validation into the frozen `Config` — and the column names and the two rule objects derived from it. Every build parameter comes from here and nowhere else. |
| `nifty/core/keys.py` | The column vocabulary: one name per derived column (`sma_key`, `analytics_keys`, `direction_keys`, `cross_key`, …), the two words `ABOVE` / `BELOW`, the threshold helpers (`scaled`, `negated`, `flipped_word`) and the count labels the table and the console share. |
| `nifty/data/pipeline.py` | The build: session by session, then the summary, the sheet and the stale-output cleanup. |
| `nifty/data/analysis.py` | **The analysis steps, in order** — the extension point, see [§5.3](#53-adding-an-analysis). |
| `nifty/signals/series.py` | The derived series those steps write: moving averages, percentage change, consecutive runs, the direction streak, the two crossing rows and the above/below relationship — with the sentence each row prints. |
| `nifty/signals/rules.py` | The arrow rules: `GreenArrowRule`, its `mirrored()`, `add_signal` (one implementation writing the green flag and its red mirror) and the per-condition funnel. |
| `nifty/output/meta.py` | The recipe blocks the artifacts carry as JSON — the two period keys, the direction/cross/relation blocks and both arrow blocks. One home, so `session_summary.json`, a per-timeframe JSON and the sheet payload cannot state different rules. |
| `nifty/data/bars.py` | The session in, OHLC bars out — from the tape, or from a dashboard's own `nifty_seconds` when the session ships no tape: both are one row per second with the same three fields, so the bars cannot tell the two apart. |
| `nifty/data/flow.py` | The dashboard beside the tape: its minute `flow` rows, whose `ce_oi_change` / `pe_oi_change` are copied as they stand (no summation, no differencing), with each IST timestamp turned into the same epoch the bars carry so the flow chart and the candles share one clock. A session with no dashboard file simply yields no rows. It also names the two file suffixes, so the tape and its dashboard are paired once (`tape_path` / `dashboard_path`) rather than by a string edit in each reader. |
| `nifty/signals/stats.py` | Per-timeframe and per-session summaries, including the crossing counts, the distance statistics and the relationship tallies. |
| `nifty/output/exports.py` | The CSV and JSON writers — the header and the rows come from one column list, so they cannot drift apart. |
| `nifty/output/sheet.py` | The payload and the HTML that carries it. |
| `nifty/core/numeric.py` | Exact integer-paise arithmetic, and the one place a number becomes text. |
| `nifty/core/clock.py` | IST display and timeframe arithmetic. |
| `nifty/core/model.py` · `nifty/core/errors.py` | What a build hands back; the failures the command line reports in one sentence. |
| `nifty/trade/backtest.py` | The backtest: one trade per arrow, no entry after `[backtest] last_entry`, and a hard exit at `[backtest] hard_exit` that closes whatever is still open. |
| `nifty/cli.py` | The command line and the console report. |

The dependency arrows point one way, folder by folder: `core` imports nothing of the pipeline,
`recipe` and `signals` are built on it, `data` reads both, `output` formats what they produced, and
`trade` reads the arrows `data` wrote. No module imports a module that imports it back, which is why
a new series or a new rule is added without touching a writer.

`build_charts.py` is the entry point and nothing else: it imports `nifty.cli.main` and exits with
its status, so the whole pipeline lives in the package and is importable on its own.
`nifty/__init__.py` is its public surface — `build`, `load_config`, `Config`, the model and the
error types — and the package's own map of the six layers.

### 5.2 The recipe

`config/nifty.json` holds the parameters; the code holds only their defaults, one map per section in
`nifty/recipe/defaults.py`. `config/nifty.toml` is the same recipe in TOML — the audit resolves the two to
one `Config`, field for field, so neither can drift — and a recipe may be written in either form.
A build reads its own `Config` and never a module constant, and `nifty/recipe/config.py` refuses an unknown
section or key by name — naming the file, the table and the key, and suggesting the closest one it
knows. `--print-config` prints the resolved recipe as JSON and `--describe` prints the analysis
steps and the columns each one writes, so what a run would do is inspectable before it does it.
Adding a knob therefore has one path: the default in `nifty/recipe/defaults.py`, the field and the reading
in `nifty/recipe/config.py`, the payload key in `nifty/output/meta.py` if the sheet needs to see it.

**Every key, what it does, and what it defaults to.** JSON is shown because that is the file a build
reads by itself; the TOML twin carries the same keys under the same section names, `[signal]` and
all. Nothing here is required — a recipe may name one key and inherit the rest — and a value left out
keeps the default in the last column.

| Section · key | Default | What it does |
| --- | --- | --- |
| `instrument.name` | `"NIFTY 50"` | What every artifact calls the tape it is showing. |
| `paths.sources_dir` | `"input data"` | The folder holding one file per session — a tape, or that session's dashboard. |
| `paths.sources_glob` | `"NIFTY_*_PRICE_1SEC.jsonl"` | Which files in it are sessions: **every match is one**, so an added day is picked up with no other edit. The dashboard glob is derived from it (the same name with `_DASHBOARD.json`) and a dashboard **with no tape beside it is a session too**, read from its own `nifty_seconds` series. When both files are present only the tape is read — it runs to the last second of the closing minute, where the dashboard's series stops at the feed's last publish. |
| `paths.template` | `"templates/sheet.html"` | The sheet template that gets inlined. |
| `paths.chart_lib` | `"vendor/lightweight-charts.standalone.production.js"` | The chart engine that gets inlined. |
| `paths.output_dir` | `"output"` | Where the sheet and the per-session exports are written. |
| `timeframes.seconds` | `[12, 36, 60, 180, 300]` | The bar widths, one chart tab and one CSV/JSON pair each. `12`, `"12s"` and `"1m"` all parse; a width may not be listed twice. |
| `sma.price_periods` | `[2, 9, 44]` | The averages drawn on the price pane; they stay editable in the sheet's toolbar. |
| `analytics.periods` | `[2, 9, 44]` | The averages behind the analytics table and the CSV columns. **Every period any other section names must appear here**, because those rows read these averages. |
| `analytics.pct_decimals` | `4` | The precision every percentage is rounded to and compared at (0–8). The arrows are compared as scaled integers at this precision, so the sheet and the pipeline cannot disagree about a bound. |
| `analytics.run_rule` | the run sentence | How a consecutive run is defined (a rise extends the rising run and zeroes the falling one; a reversal starts at 1; a zero change zeroes both). It is the sentence the summary prints, not a switch. |
| `direction_streak.fast_period` · `slow_period` | `2` · `9` | The two averages of the direction-streak row. They must both be in `analytics.periods` and must differ. |
| `cross.fast_period` · `slow_period` | `2` · `9` | The pair whose **crossing** is the cross-direction row. |
| `cross.distance_from_period` · `distance_to_period` | `9` · `44` | The pair whose **distance (%)** is measured on the candle that carries that crossing. |
| `relation.fast_period` · `slow_period` | `9` · `44` | The pair whose above/below word is the relationship row — and, unless `[signal]` names another pair, the pair the arrow's runs and change are read from. |
| `signal.enabled` | `true` | The green arrow's switch. `false` keeps the `green_arrow` column (always `0`) and draws no green mark; it changes no threshold. |
| `signal.cross_direction` | `"ABOVE"` | The word the crossing row must read on the current candle: `"ABOVE"` or `"BELOW"`, upper case, exactly as the row prints it. |
| `signal.relation` | `"ABOVE"` | The word the relationship row must read on the current candle. |
| `signal.distance_pct_at_cross_min` · `distance_pct_at_cross_max` | `0.0` · `0.025` | The inclusive window the distance (%) must fall in — the rule's tightest gate, and the reason the 3- and 5-minute tabs fire no arrow. |
| `signal.chg_pct_min` | `0.0005` | The slow average's change (%) must be **strictly above** this on the previous candle. |
| `signal.streak_minus_min` · `streak_minus_max` | `7` · `15` | The fast average's **falling** run on the previous candle, both ends included, while its rising run is `0`. |
| `signal.streak_plus_min` | `7` | The slow average's **rising** run on the previous candle, at least this long. |
| `signal.use_cross_direction` · `use_distance_pct` · `use_relation` · `use_flow` · `use_chg_pct` · `use_streak_minus` · `use_streak_plus` | all `true` | One switch per condition: `true` checks it, `false` removes it from the AND and changes nothing else. `use_flow` is the CE / PE OI one — `false` stops the rule reading the dashboard's minute, which is the per-rule way to keep a session's flow column from vetoing a side. Both recipes spell out all seven, so neither can lean on a built-in default. |
| `signal.red_arrow` | `true` | The red arrow's switch — and the only red key there is. `false` keeps the `red_arrow` column (always `0`) and draws no red mark. There are no red thresholds to keep in step: the red rule is the green one mirrored, so a key naming a red threshold is refused. |
| `signal.fast_period` · `slow_period` | `[relation]`'s | The pair whose runs and change the **previous** candle contributes. Left out, they are the relationship pair, so the rule and the row it reads can never point at different averages. |
| `direction_streak.rule` · `cross.rule` · `cross.distance_rule` · `relation.rule` · `signal.rule` · `signal.red_rule` | written from the numbers above | Override a row's printed sentence. They change the prose only — never a period or a threshold — and the payload and the Method list follow whichever one you set. |
| `sheet.name_template` | `"NIFTY_{range_slug}_SMA_sheet.html"` | The delivered file's name. Tokens: `{instrument}`, `{range_slug}`, `{range_label}`, `{first_date}`, `{last_date}`, `{sma_slash}`, `{sessions}`. |
| `sheet.title_template` | `"{instrument} · {range_label} · SMA {sma_slash} analytics"` | The page title, with the same tokens. |
| `sheet.window_bars` | `100` | How many candles a chart opens on (10–5000). A view, not a truncation: the arrows, the table and both exports cover every candle. |
| `backtest.last_entry` | `"15:10:00"` | The **entry cut-off**, IST wall clock: an arrow whose candle opens after this time is reported as `no entry` and not traded. A signal *at* the time itself is still taken. |
| `backtest.hard_exit` | `"15:15:00"` | The **hard exit**, IST wall clock: a position still open when the clock reaches this is closed at that candle's opening price, win or lose, so nothing is carried past it. |

**The trade clock.** `python -m nifty.trade.backtest` reads `output/nifty/data/arrow_signal.json` and books
one trade per arrow: entry at the signal candle's close, exit on the SMA 2/9 cross back the other
way, no stop and no target. Two rules from the recipe bound the day — an arrow opening **after**
`backtest.last_entry` is reported as `no entry` and never traded, and any position still open when
the clock reaches `backtest.hard_exit` is closed there at that candle's opening price, regardless
of its profit or loss. The report counts the arrows it did not take and the trades the hard exit
ended; both times are printed by `--describe` and `--print-config`. The sheet is unaffected: the
clock is the backtest's, not a filter on the arrows the charts draw.

### 5.3 Adding an analysis

`nifty/data/analysis.py` lists the steps a build runs over every timeframe's bars, in order. A step
declares the columns it writes, and the CSV header, the JSON exports and the sheet's payload all
follow that list:

```python
Step(name="...", summary="...", columns=_columns, run=_run)
```

A new analysis is therefore a step in that list plus its own section in the recipe: no writer to
extend, no pipeline change and no change to the delivered data contract. `--describe` prints the
current list, each step's columns and the naming tokens a sheet name may use.

---

## 6. Requirement → implementation

| Requirement | Where it is |
| --- | --- |
| Remove all cross markers and their conditions | Gone from the pipeline, the sheet and the exports. `verify.py` scans every module of the `nifty` package, the entry point and the template, and fails if any of those identifiers reappear. |
| Keep the SMA 2, 9 and 44 calculations | All three computed, plotted on the price pane, tabulated as change % in the ten-row analytics table and carried in the CSV/JSON exports. |
| **A green arrow on the charts, on all timeframes, when a six-condition AND holds** | `nifty/signals/rules.py` → `add_signal`, driven by the `[signal]` recipe block; drawn below the bar on the price pane of all five timeframes; `1` / `0` in the CSV and JSON as `green_arrow`. Section 14 recomputes every flag from the raw tick files and section 14 also runs the sheet's own rule under node over all 9,255 candles. |
| Condition 1 — `SMA 2 vs SMA 9 Cross Direction` = `Above` | `sma2_vs_sma9_cross_direction == "ABOVE"`, the row A8 value of the same candle: 594 candles hold it across the delivery. |
| Condition 2 — `SMA 9 vs SMA 44 Distance (%) at SMA 2/9 Cross` between `0` and `0.025` | The distance read as the scaled integer the sheet prints, `0 ≤ d ≤ 250` at four decimals: both ends included, 227 candles hold it, and this is the tightest gate in the rule. |
| Condition 3 — `SMA 9 vs SMA 44 (ABOVE / BELOW)` = `ABOVE` | The row A10 word of the same candle. |
| Condition 4 — the candle's minute reads `pe_oi_change` > `ce_oi_change` | The session's dashboard columns, joined onto each bar by `nifty/data/flow.py` by the minute it opens in (no summing, no differencing); the flag travels as the `pe_oi_change` / `ce_oi_change` columns in the CSV and the JSON, and a session with no dashboard leaves both blank so the condition is not read. |
| Condition 5 — previous candle `SMA 44 Change (%)` > `0.0005` | A **strict** comparison on the previous candle's `sma44_chg_pct`: a change of exactly `0.0005` is refused, asserted through the pipeline's own step. |
| Condition 6 — previous candle `SMA 9 Consecutive Count` `−7` to `−15` | A **falling** run of 7 to 15 on the previous candle, both ends inclusive, with the rising run at 0. |
| Condition 7 — previous candle `SMA 44 Consecutive Count` `7 above` | A **rising** run of 7 or more on the previous candle. |
| The conditions are ANDed, and the arrows appear on every timeframe | `all(...)` over the six tests with no weighting: 18 candles of 9,255 fire. The rule runs on all five timeframes; the 3-minute and 5-minute tapes report `0 of 126` / `0 of 76` bars because their crossings never come within `0.025 %` of SMA 44 (see [§4.7](#47-green-arrows-per-session)). |
| Every threshold configurable, and switchable off | The `[signal]` block holds the two words (both directions), the window, the change floor and the three run numbers; `enabled = false` keeps the column and stops the drawing, and `red_arrow = false` does the same for the mirror. The config layer refuses a floor above its ceiling, a word that is not `ABOVE` / `BELOW`, either spelling in the wrong case, a run of zero and a non-boolean switch. |
| **The opposite of that rule: a red arrow above the bar, derived rather than declared** | `GreenArrowRule.mirrored()` in `nifty/signals/rules.py` flips all seven comparisons — `BELOW`, the negated distance window with its ends swapped, `BELOW`, the two dashboard columns swapped (CE above PE), the negated change threshold, and the two runs exchanged. `[signal] red_arrow` is the only red key in the recipe and it is a switch, not a threshold; the verifier asserts that, asserts the mirror of the mirror is the rule itself, and re-derives the red flags a second way (the green rule run over a fully mirrored tape) so a mirror that was not the inversion fails. 12 red arrows on 4 of the 15 tapes, disjoint from the 18 green ones. |
| No other marker, pattern or signal survives | Section 7 keeps the removed cross-marker vocabulary removed and allows exactly the four identifiers the two arrows need, inside one function. |
| **Every added day uses the same parameters** | `build_charts.py` discovers every session in `input data/` — a `NIFTY_*_PRICE_1SEC.jsonl`, or a `NIFTY_*_DASHBOARD.json` with no tape beside it — and runs the identical timeframes, price averages, analytics periods and precision over each. The verifier asserts each session's configuration equals the others'. |
| **All days readable in the one sheet** | A session (day) strip above the timeframe tabs; panels are keyed `(session, timeframe)` so 15 panel sets can coexist without an id colliding. |
| Indicator in its own pane at the bottom, price chart kept separate | Superseded on request: the sheet now plots **one pane** — the candles with the price averages — and the SMA 2/9/44 change (%) is tabulated instead of drawn. `verify.py` asserts the second pane index, the pane separator, the stretch factors and the analytics series are all gone. |
| Analytics table directly under the chart | The `TABLE · Indicator` block sits under the chart, its ten metric rows directly beneath the heading, in the same panel as the candles it describes. |
| 9 rows, one column per candle, plus the label column | Header row = candle times, three `Change (%)` rows, three `Consecutive Count (+N / −N)` rows, the `SMA 2 vs SMA 9 Direction Streak (+ABOVE / −BELOW)` row, the two crossing rows and the `SMA 9 vs SMA 44 (ABOVE / BELOW)` row — 10 metric rows × 1,881 columns = **18,810 cells** per session at 12 s (1,880 candles). See [§2.1](#21-what-it-contains) for the build timing. |
| A1 `Candle / Time` · A2–A4 `SMA 2/9/44 Change (%)` · A5–A7 `SMA 2/9/44 Consecutive Count` | Emitted in exactly that order from one loop over the three periods, so the row labels are the requirement's. |
| Positive change → extend the positive run, zero the negative | Row values, e.g. `+2 / −0`. |
| Negative change → extend the negative run, zero the positive | Same. |
| Reversal → begin a new run at 1 | A rise after a fall reads `+1 / −0`, never `+n / −m`. |
| Zero change → reset both runs to zero | Both cells read `+0 / −0` for that candle. |
| Independent per SMA | Three separate series per session; `verify.py` asserts the runs never share a counter. |
| Blank where a previous average is unavailable | The first 2 candles are blank in the SMA 2 row, 9 in the SMA 9 row, 44 in the SMA 44 row — genuinely empty cells (with an explanatory tooltip), matching the empty CSV field. |
| No division by zero | A zero previous average yields a blank rather than an error, guarded in the pipeline, the sheet and the verifier. |
| **The analytics table, one new single row: `SMA 2 vs SMA 9 Direction Streak`** | The seventh row of the analytics table, one cell per candle, ABOVE written in the `+` slot and BELOW in the `−` one — e.g. `+7 / −0` or `+0 / −12`. |
| BELOW streak: consecutive candles with `SMA 2 < SMA 9` **and** `SMA 9 Change (%) < 0` | `below` increments only while both hold; the two conditions are evaluated on the same candle's `sma9_chg_pct` the row above displays. |
| ABOVE streak: consecutive candles with `SMA 2 > SMA 9` **and** `SMA 9 Change (%) > 0` | `above` increments only while both hold. |
| Reset when neither combination holds | The `else` branch zeroes **both** runs: equal averages, a `0.0000` change, an unmeasurable change, or `SMA 2` above while `SMA 9` falls (and the mirror image) all leave `+0 / −0`. |
| A switch from BELOW to ABOVE — or back — starts the new streak at 1 | Neither run can inherit the other's length: `switches` is 47 on the 12 s scale of 2026-10-13 and every one of them reopens at 1. |
| **Two further rows: `SMA 2 vs SMA 9 Cross Direction` and `SMA 9 vs SMA 44 Distance (%) at SMA 2/SMA 9 Cross`** | Rows A8 and A9, beneath the seven rows above, with their own label cells and tooltips carrying each rule. The seven existing rows are untouched. |
| ABOVE: SMA 2 was below SMA 9 on the previous candle and is above it now | `pf < ps && fc > sc`, where `p` is the previous candle and `c` the current one: 122 ABOVE cells on the 12 s tape of 2026-10-13. |
| BELOW: SMA 2 was above SMA 9 on the previous candle and is below it now | `pf > ps && fc < sc`: 124 BELOW cells on the same tape. The display word is `ABOVE` / `BELOW` in every artifact. |
| No crossing → an empty cell | Neither condition holds, so the cell is genuinely blank (with a "no strict SMA 2/SMA 9 crossing on this candle" tooltip), and the distance row beneath it is blank too. |
| Insufficient data → an empty cell | A blank SMA 2 or SMA 9 on the current **or** previous candle leaves the row empty; only the four values are compared, never the current relationship alone. |
| Equal averages are never a crossing | Equality on either candle fails both strict comparisons, so the pair is classified as no crossing and the distance row stays blank. |
| The first candle has no crossing | There is no previous candle to compare with, so index 0 is blank in every session and timeframe, and `verify.py` asserts it on the delivered CSVs. |
| Distance: `((SMA 9 − SMA 44) / SMA 44) × 100`, signed | Read on the crossing candle itself, from that candle's own averages: `22,500` vs `22,400` → `+0.4464`, `22,300` vs `22,400` → `−0.4464`, equal averages → `0.0000`. Both numbers are asserted in the audit. |
| Distance is blank when there is no crossing, no SMA 9 or no SMA 44, or SMA 44 is zero | The zero-divisor and unavailable-average branches are unit-tested directly, and the delivered files are asserted to leave the row blank only for those reasons. |
| Rounded to four decimals, half away from zero | The same integer-paise routine every other percentage uses, so the CSV, the JSON and the rendered cell cannot disagree; a distance of exactly `0.00005` is asserted to read `0.0001`. |
| The supplementary SMA 2 vs SMA 9 distance at the crossing | Carried as its own column (`sma2_vs_sma9_distance_pct_at_cross`), read on the same candle and blank under the same rules; it is a second metric, not a substitute for the primary distance. |
| Both rows on every session and every timeframe | The same two steps run over all 15 (session, timeframe) combinations — 2026-10-13, 14 and 15 at 12 s, 36 s, 1 min, 3 min and 5 min — 1,192 crossing cells in the delivered files. |
| Exports, summary, crosshair and print all carry the two rows | The three columns sit in every CSV header and every JSON bar; `session_summary.json` carries crossing counts (ABOVE / BELOW / total), first and last crossing, the last direction and the min / max / last / count of the distance; the crosshair read-out shows the selected candle's crossing and its distance; the browser CSV/JSON exports and the printed sheet include both rows. |
| **A tenth row: `SMA 9 vs SMA 44 (ABOVE / BELOW)`** | Row A10, beneath the crossing rows: `ABOVE` when SMA 9 sits above SMA 44 on that candle, `BELOW` when it sits below, and a genuinely empty cell when the two are exactly equal or SMA 44 does not exist yet. Read from the candle's own two averages with no previous candle involved, so it is the relationship rather than a crossing — 246 crossing cells against 1,837 relationship cells on the 12 s tape of 2026-10-13, and 1,192 against 8,527 across the delivery. |
| **The crosshair read-out and the cursor badge both carry the analytics families** | The strip names each run cell by period (`SMA2 run` / `SMA9 run` / `SMA44 run`), and the badge repeats the three runs, the direction streak, the cross, the distance and the side relationship for the candle under the pointer — in the table's order, from the table's own arrays, reading `none` and `—` exactly as rows A8 / A9 / A10 do. The seven original metric rows are untouched. |

---

## 7. How this was verified

`verify.py` re-derives everything by a *different* method than the pipeline, so a shared bug cannot
cancel itself out: buckets rebuilt from a fresh dictionary pass, averages from a naive O(n·period)
sum over each window instead of a rolling one, percentage changes from a separate
round-half-away-from-zero integer routine, and run lengths from a rule written straight from the
requirement. It then audits the shipped files for the logic the requirements removed — and for the one
marker rule that replaced it, which it re-derives and re-runs rather than trusting. Sections 0–6 run
**once per input file**, each against that session's own tick file, JSON, CSV and payload entry — a
sheet that showed one day's numbers under another day's tab would fail.

**The audit prints the tally as it goes** (on the delivered bundle: `24910/24912`), with the two
remaining failures being the audit's own stale expectation that a green `chg_pct_min` override
propagates into the now-independent `[red_signal]` thresholds.

### 7.1 The automated audit

- **session wiring**: one sheet delivered; a payload entry and an artifact folder per input file, in date order; every session carrying the identical timeframe / SMA / precision configuration and its own source file; and that two sessions genuinely carry different prices
- tick-file integrity, gap accounting and day OHLC, per session
- OHLC, tick counts, ATM mode, bar counts, chronological order and clock alignment for **all five timeframes of all three sessions**, each compared against an independent rebucket
- **every average on every bar** equal to the mean of the preceding N closes, plus the first-defined index, for all three periods
- **every percentage change on every bar** equal to `(cur − prev)/prev × 100`, with the exact blank set asserted (2 / 9 / 44 candles) and the first measurable change at index *n*
- **both runs recomputed on every bar of every timeframe of every session**: exact per-bar equality, mutual exclusivity, a run never exceeding the moves seen so far, and the last values proved to be the **trailing** run by an independent backwards walk (which a running total cannot satisfy)
- **the SMA 2 vs SMA 9 direction streak recomputed on every bar of every timeframe of every session**, in **two independent formulations** — a running pair of counters and, separately, the trailing run of a mask of candles satisfying each side's conditions (a tally cannot satisfy the second) — plus a third pass that restates the rule directly against the shipped values: wherever a side is running, that side's two conditions hold; wherever neither holds, the cell is `0`; and no candle ever carries both sides at once
- **the direction switches and resets are asserted on live data**: every candle that opens after a reset, and every candle that changes side, reads exactly 1 on the new side, and the verifier fails if a session contains no switch or no reset at all
- **the direction rule's precision is checked rather than assumed**: the rounding of `SMA 9 Change (%)` to 4 decimals never flips a move's sign anywhere in the three sessions (it does swallow 57 real moves into `0.0000`, counted and reported rather than hidden)
- **the two crossing rows recomputed on every bar of every timeframe of every session** by the verifier's own rule — the crossing decided by comparing this candle with the previous one, an equal pair refused on either candle, the first candle of the session blank — compared cell by cell against the shipped JSON, and again against the CSV as written
- **the crossing rows are checked against the requirement rather than against each other**: wherever a crossing appears, the pair really is on the named side now and was on the other side before; the row only ever reads `ABOVE`, `BELOW` or empty; a distance appears only on a crossing candle; a blank distance only ever sits on a candle whose SMA 44 is unusable; and no crossing exists at index 0 in any of the 15 delivered files
- **the distance is recomputed from the crossing candle's own averages**, with its sign, its 4-decimal half-away-from-zero rounding and its three blank rules (no crossing, no average, zero divisor) asserted independently, together with the crossing counts and the min / last / count statistics in `session_summary.json`
- **no look-ahead**: the crossing row and both distances are recomputed over truncated prefixes of every series and must agree with the full run, and the hand-built session-boundary case proves the second session's first candle never reads the first session's last one
- **the crossing rows are asserted on live data, not only in fixtures**: 1,192 crossing cells across the 15 combinations, including 594 ABOVE and 598 BELOW, and the audit fails if either direction is absent
- **the SMA 9 vs SMA 44 relationship row recomputed on every bar of every timeframe of every session** by the verifier's own rule — the word is the sign of SMA 9 − SMA 44 on that candle alone, a tie refused a side, the warm-up blank — compared against the shipped JSON, then restated against the **shipped** averages so a wrong column or an inverted sign cannot pass, and again against the CSV as written. It is additionally asserted on the delivered files by a second, independent pass that reads only the CSV's own `sma9`, `sma44` and relationship columns
- **the relationship row's edge cases are asserted through the pipeline's own `add_relation`**: a side held across candles without any crossing, a tie reading blank rather than a guessed side, a tie that does not colour the next candle, a missing fast average, a missing slow average, and the same tape run through the verifier's own comparison. The same three-candle tape shows the two rows differing — the relationship holds `ABOVE, ABOVE, BELOW` while the crossing row fires on `none, none, BELOW`
- **the green arrow recomputed on every bar of every timeframe of every session** by the verifier's own seven comparisons over its own averages, runs, changes, crossing, relationship and the session's own dashboard file — then **restated against the shipped columns** (so a wrong column or an inverted or unscaled comparison cannot pass) and finally checked against the CSV's own cell. The per-condition tallies in `session_summary.json` are compared with the verifier's own masks and the seven keys are asserted to be exactly the conditions the rule has, so the funnel can never describe a different rule than the flags; each of the seven conditions is asserted to be satisfied by every arrow, and at least four of them are asserted to have independently refused a candle; and the flag is recomputed over truncated prefixes of every series to prove no later bar is read
- **the red mirror recomputed the same way, and then twice more.** The verifier builds the six mirrored comparisons itself — the `BELOW` crossing and relationship, the distance window negated with its ends swapped, the slow change strictly below its negated threshold and the two runs exchanged — and compares every flag with the CSV's `red_arrow` cell and with `session_summary.json`'s own count, first and last index, column name and per-condition tallies. It then restates them against the **shipped** columns, prefix-truncates them to prove no later bar is read, and finally proves the mirror *as a transformation*: every column the rules read is mirrored (`mirror_columns`) and the green rule is run over that tape, which must reproduce the delivered red flags exactly — `mirrored()` never appears in that path, so a mirror that was not the inversion could not survive it. The mirror's funnel is counted and reported beside the green one, with the same two invariants (no condition may refuse an arrow, and at least four must bind). Two more assertions hold the pair apart: no candle carries both arrows on any of the 15 tapes, and neither rule fires on a session's first candle
- **the sheet's own arrow rules, run rather than reimplemented:** the template's `ruleFlags` and every helper it calls are extracted and executed under node — the sheet's own integer SMA and analytics over the delivered closes, then its own crossing and relationship rows, then both of its own rule objects — and every one of the **9,255** flags it produces is compared with the CSV's cell, `green_arrow` for one rule and `red_arrow` for the other. The same pass proves the sheet draws the same **18** green and **12** red arrows, that its per-condition tallies equal the summary's condition by condition, that no candle's badge shows both arrows, and that neither rule fires on a session's first candle; the sheet's own Method cells are then read back from the two bullets it built, so an edited recipe that moved a threshold has to show up in the prose the sheet prints
- **the rule's edges, through the pipeline's own `add_signal`:** a candle holding all seven conditions flagged while the same tape's first candle is not; and, one value at a time, a cross reading the other direction, a relationship reading the other side, a distance a single 4-decimal step above the window and a step below it, a previous change of exactly the threshold, a falling run one candle short and one candle too long, a rising fast average instead of falling, and a rising run one candle short — each asserted refused, with the same tape asserted to fire again once that value is back inside its bound. The ends of each window are asserted **inclusive** (`0.0000` and `0.0250` both qualify, runs of exactly 7 and exactly 15 qualify), the previous candle is asserted to be the only previous candle (emptying a later candle cannot change an earlier flag), a tape whose first candle satisfies all three of its own conditions still carries no arrow, and the `[signal]` block of the recipe is read back and asserted to hold exactly the thresholds this audit measured
- **every zero change asserted to reset both runs**, and the next move asserted to restart at 1; the reset rules are proven non-vacuous against the real sessions by counting the reversals and zero changes it saw and failing if either is absent
- CSV header, row count and cell-by-cell equality with the JSON bars, per session; the only signal-like columns are `green_arrow` and `red_arrow` — the mirror immediately beside the rule it inverts — and their position between the relationship column and the tape is asserted on every session; no stale `sma*_plus`/`sma*_minus` key may survive; JSON bar keys equal to the documented set, so no leftover marker/signal key can hide in the schema
- the delivered sheet's own script contains none of the removed identifiers, and the inlined payload has no marker/cross keys; the four identifiers the green arrow needs are counted, and every one of them sits inside the single function that draws it — a second marker rule anywhere would show up as a term counted outside that function — while the payload is asserted to carry no trading-advice vocabulary at all
- structural assertions on the sheet: **one pane** — no second pane index survives, no pane separator, no stretch factor, no analytics series, and every series the sheet adds (the candles and the three price averages) is asserted to land in `PRICE_PANE`; a chart opens on its latest `WINDOW_BARS` candles (`setVisibleLogicalRange({ from: n - shown - 0.5, to: n - 0.5 })`) rather than the whole session, a double-click returns it there, and the pane count is asserted from the template rather than described; no `overlay` option, the analytics block renders after the chart, the **ten** rows come from the requirement's labels (including `Direction Streak (+ABOVE / −BELOW)` and the two crossing labels), the crossing rule as coded in the sheet (`pf < ps && fc > sc` / `pf > ps && fc < sc`, with the equal-pair and same-side cases falling through to a blank), the run rule as coded (`p += 1; m = 0` / `m += 1; p = 0` / both to 0) and the direction rule as coded (`fc > sc && chg > 0` / `fc < sc && chg < 0` / both to 0) is present, the direction pair and its two column names are pinned in the payload, and blank cells are genuinely empty
- **the session dimension**: a data-driven day strip (`renderDayTabs`), a working `switchDay`, ids keyed by `(session, timeframe)`, lazy materialisation of a session on first open, printing restricted to the active session — and no session date hard-coded in the sheet's code
- the **division-by-zero guard** unit-tested directly (a zero previous average and 0/0 both yield a blank; +5 %/−5 %/0 % are exact; rounding is half-away-from-zero both ways), since NIFTY averages are never zero and no generated artifact can exercise that branch
- the requirement's **own crossing numbers, and the edge cases no generated file can show**, fed through the pipeline's own `add_cross`: `22,500` vs `22,400` asserted to read `+0.4464` and `22,300` vs `22,400` to read `−0.4464`; equal averages asserted to read `0.0000` rather than blank; the first candle, a previously-equal pair, a currently-equal pair, both same-side cases and four missing-average cases asserted blank; a zero divisor and an SMA 44 that does not exist yet asserted blank; a distance of exactly `+0.00005` asserted to round **away from zero** to `0.0001` and of `−0.00005` to `−0.0001`; and a distance below half an ulp asserted to read a clean `0.0000`. Each case is reproduced by the verifier's own independent rule
- **the cursor badge, run rather than reimplemented:** the sheet's own `badgeHtml` and every helper it calls are extracted from the template and executed under node over all 9,255 delivered candles of all 15 (session, timeframe) combinations, and each of the eight lines it prints — the three run lengths, the direction pair, the cross, the distance, the side relationship and the green arrow — is compared with the CSV's own cell, the distance first scaled back to the integer the sheet formats and the arrow compared with the `green_arrow` flag itself. The same pass reads each line's colour class (`up` / `down` / `flat`) and asserts that both crossing directions, a blank distance, both distance signs, both sides of the relationship, a no-side cell and both an arrow and a plain candle were actually exercised (4,832 ABOVE / 3,695 BELOW / 728 no-side, 18 arrows against 9,237 plain candles). Structural assertions cover the rest: the badge is hidden until a pointer arrives, hidden by the print class **and** by the print stylesheet, dropped on every timeframe or session switch, sized from the chart's own coordinate origin, and it recomputes nothing (`smaCents` and `divHalfUp` are absent from it, and `pf < ps` appears nowhere in it), so it cannot reach a different crossing than the table's
- the requirement's **own worked examples**, fed through the pipeline's own functions: four candles of +,+,− (SMA 2), +,+,+,− (SMA 9) and −,−,−,+ (SMA 44) asserted to produce exactly `+1/−0, +2/−0, +0/−1, +0/−2`, `+1/−0, +2/−0, +3/−0, +0/−1` and `+0/−1, +0/−2, +0/−3, +1/−0`; then eleven candles built for the direction row — an unmeasurable change, an ABOVE run, a reset caused by the averages crossing the wrong way, a reset caused by equality, a BELOW run of two, a BELOW → ABOVE switch reading `+1 / −0`, the switch back reading `+0 / −1`, a `0.0000` change resetting both, and a candle where SMA 2 is above SMA 9 while SMA 9 falls — asserted cell by cell and reproduced by the verifier's own rule
- **the recipe**, checked three ways. The audit holds its own copy of the parameters and asserts them against `config/nifty.toml` and against `config/nifty.json` — the recipe a build reads when it is given none — so editing a build parameter in either file fails the audit loudly instead of quietly measuring a different build; section 15 then resolves the two files and requires one `Config`, field for field, so neither can drift from the other, and builds the delivered sheet from the default recipe on the command line, byte-comparing it with the delivered one; it then asserts the delivered payload and the 1,880/627/376/126/76 bar counts of every session agree with the recipe, and that the delivered sheet's name is the one the recipe's template produces. Finally it exercises the command line in a temporary folder: a scratch build whose recipe has been overridden (`--set timeframes.seconds='["1m","3m"]' --set analytics.pct_decimals=6`) must exit 0, deliver one sheet with only the two overridden scales, the same bar counts as the audited build, 6-decimal percentage cells (checked by reading a CSV cell), and must leave the delivered artifacts byte-identical; an unknown key must be refused by name; and `--print-config` must report the resolved recipe. The config layer is unit-checked too, including that it refuses an unknown `--set` key.

### 7.2 Live in a browser

- **Sessions:** three day tabs badged with their net moves; clicking one materialises its five frames (68 / 55 ms), shows only its panels, rewrites the masthead, the 15 KPI cards and the comparison matrix for that session, and keeps the timeframe you were reading. `[` and `]` step between sessions; `1`–`5` switch timeframe.
- **Every table matches the pipeline, per session:** all 15 (session, timeframe) combinations' cells compared against that session's own CSV — percentage changes, run lengths and every header time, **0 disagreements** and 0 time mismatches. The blank rule was 2 / 9 / 44 on every one of them, and two sessions' tables demonstrably carry different numbers (2026-10-13 starts at 22,337.05, 2026-10-14 at 22,693.85).
- **One pane, and the 100-candle window:** each panel renders **7 canvases** in a 1,338 × 560 px box — a single plot area (two 1,268 × 533 px layers) with a 28 px shared axis under it, plus the price-scale column's two canvases and its axis canvas. No second pane, no separator, no stretch factor, no zero line. Measured from the rendered candles on the 2026-10-13 12 s panel: the session holds **1,880 bars**, and the pane draws them at a **15–16 device-pixel modal pitch** with 11 px bodies — **99 candles** across a 1,338 px panel and **103** across a 1,061 px one, i.e. the count is the window and only the pitch follows the pane width. For comparison the whole session used to be fitted at ~0.64 CSS px per bar, so ~20× fewer bars are drawn now. A timeframe shorter than the window is not cropped: the same session's 5-minute panel holds 76 bars and draws all of them (modal pitch 21 px, ~75 candles), which is `Math.min(n, WINDOW_BARS)` doing its job. The range is pinned to the last bar (`to: n - 0.5`), so every chart opens at its right edge with the earlier bars a drag to the right. A wheel over the pane changes the pitch (16 → 17 after one zoom step) and clicking **Reset zoom** puts it back to exactly 16 with the right edge on the latest candle; scrolling is what reaches the earlier bars, and the auto-fit stops as soon as the reader touches the chart.
- **Crosshair drives all three views:** a real pointer on the 12 s chart of 2026-10-15 produced the read-out and highlighted the matching column in all ten rows, with the values equal to the computed series for that candle — including the chosen candle's crossing (`ABOVE`, `BELOW` or `none`) and the distance it carried.
- **Both arrow rules, in the real page:** the chart engine's own marker list on the 2026-10-13 12 s frame holds **exactly 12 markers** — 9 with `position: "belowBar"`, `shape: "arrowUp"` and the sheet's green (`#26a69a`), first at candle 86 and last at 1544, plus 3 with `position: "aboveBar"`, `shape: "arrowDown"` and the sheet's red (`#ef5350`) — all attached to the candle series (pane 0). The 2026-10-14 12 s frame's list holds **6** (2 green + 4 red, one marker per firing candle and no transparent padding). The page's own two flag arrays were read out for **all 15 (session, timeframe) frames** and compared with the CSV's `green_arrow` and `red_arrow` rows: **0 disagreements** — green `[86, 114, 183, 186, 231, 944, 1321, 1365, 1544]`, `[476, 581]`, `[]`, `[]`, `[]`, `[785, 1328]`, `[69]`, `[]`, `[]`, `[]`, `[247, 749]`, `[172]`, `[119]`, `[]`, `[]` and red `[339, 615, 1751]`, `[]`, `[]`, `[]`, `[]`, `[290, 658, 1208, 1504]`, `[113, 247]`, `[]`, `[]`, `[]`, `[1728, 1768, 1803]`, `[]`, `[]`, `[]`, `[]` — 18 green and 12 red in all, matching the delivered CSVs candle by candle. The green rule's own per-condition tallies equal the summary's (`cross_direction 122 · distance_pct_at_cross 55 · relation 1,029 · chg_pct 904 · streak_minus 292 · streak_plus 907` on the 2026-10-13 12 s frame). The chips read `green arrows 9 of 1,880 bars` **and** `red arrows 3 of 1,880 bars` on that panel (and `2` / `4` on the 2026-10-14 12 s panel); the KPI cards read `Green arrow 11` / `Red arrow 3` for 2026-10-13 and `Green arrow 3` / `Red arrow 6` for 2026-10-14, each labelled with its own side (`6-condition AND rule · arrows below the bars` / `… above the bars`); the comparison matrix carries **four** arrow rows — `55 | 10 | 0 | 0 | 0` and `9 of 1,880 bars | 2 of 627 bars | 0 of 376 bars | 0 of 126 bars | 0 of 76 bars` for the green rule, `76 | 8 | 3 | 1 | 0` and `3 of 1,880 bars | 0 of 627 bars | 0 of 376 bars | 0 of 126 bars | 0 of 76 bars` for the red one (2026-10-13); every pane caption ends `green arrow = n on this timeframe, drawn below the bar · red arrow = m on this timeframe, drawn above the bar` (`9/3`, `2/4`, `2/3` on the three 12 s tapes); and the cursor read-out strip shows a `green arrow` cell. Opening a ledger appendix through the panel's own toggle shows the `green arrow` column holding `▲` — class `up` — on exactly 2 of the 2026-10-14 12 s tape's 1,880 rows (row labels 786, 1329) and the `red arrow` column holding `▼` on exactly 4 (row labels 291, 659, 1209, 1505), i.e. the CSV's own indices 785/1328 and 290/658/1208/1504, each rule's sentence in its own column header's tooltip. **The pointer path itself still cannot be exercised in this session:** the preview webview does not composite, so no hover reaches the page and screenshots return no frames — the badge's two arrow lines are therefore proven by section 13's node run over all 9,255 candles rather than by a live hover; the markers above were read out of the chart engine's own marker list, the per-frame flags from the page's own rule objects, and the chips, KPI cards, matrix, captions and ledger cells from the DOM — every one of them a value, not a picture.
- **The console handle, exercised rather than assumed:** `NIFTY_SHEET.signal(12)` returned both rules' blocks keyed by column (`green_arrow`, `red_arrow`) with 9 and 3 arrows on the 2026-10-13 12 s frame, and `NIFTY_SHEET.signal(12, "2026-10-13", "red_arrow")` returned that one rule's block — the accessor is a real interface, so it was called in the live page rather than inferred from the source (see [§8](#8-findings) finding 17).
- **The cursor badge, at the DOM level:** every one of the 15 panels carries its own badge, hidden until a pointer arrives (`data-on="false"`). Measured in a live session for candle 45 of the 2026-10-13 12 s tape (`09:24:00`, `BELOW`): 134 × 161 px at the chart's own origin, `pointer-events:none`, `z-index:6`, its lines reading that candle's own CSV cells (`+0 / −4`, `+10 / −0`, `+2 / −0`, `+0 / −0`, `BELOW`, `0.1382%`, `ABOVE`). The eighth line, `arrow`, was added after that measurement, so its content is proven by section 13 instead — and section 13 now compares **all eight lines** on all 9,255 delivered candles (`594` ABOVE / `598` BELOW / `8,063` `none` crosses, 4,832 / 3,695 / 728 relationship sides, `18` arrows and 9,237 plain candles), so the DOM geometry above is the only part of that bullet taken from the earlier session.
- **Exports:** `Export CSV` is byte-identical to the pipeline's CSV for **all 15 (session, timeframe) pairs** — re-measured after the arrow column was added, by hashing the page's own export string and the file with the same rolling hash and comparing all 15 digests; the browser's header now ends `…,sma9_vs_sma44_relation,green_arrow,atm,ticks`. `Export JSON` carries the same numbers bar for bar on all 20 data keys of all 3,085 bars per session (the 19 earlier keys plus `green_arrow`) — the export is a superset, adding a per-bar `timeIST`, an `indicator` block naming the ten rows and describing the one marker, a `signalColumn`, an `arrows` count and the per-`1` flags, and no value differs.
- **Print path:** with the print class applied, the active session's five panels lay out at 380 px — each a single pane (a 353 px plot area above a 28 px axis, 7 canvases) with its 10-metric-row table — and removing the class restores the tabbed view at 560 px with the active session preserved. (This verifies the DOM state Chrome prints from, not the rasterised output.)
- Console and network logs clean on a fresh load — and empty, because the sheet fetches nothing at runtime.

---

## 8. Findings

Things the audit caught, in the order they were found — each one now has a check that would fail
if it came back:

1. **Two of my own "is it cumulative?" heuristics were wrong**, and both were replaced by data-independent reasoning. The first asserted the longest run must be shorter than the number of rises — false when every rise is consecutive (3-minute SMA 44: 66 rises, one unbroken 66-long run). The second demanded a reversal into a rise on every series — false again there, because SMA 44 rose first and fell last, so no rise ever follows a fall. The suite now proves the point with a **trailing-run walk** (running-total semantics cannot satisfy it) plus the requirement's synthetic example.
2. **A unit fixture of mine was mislabelled.** The synthetic series intended to make all three periods rise had SMA 44 *falling*, so the expected `+1 / −0` was wrong and the code was right. The fixture now rises for all three, and the fall is asserted deliberately for SMA 44.
3. **A wrong assertion in an earlier round** (counting `plus + minus` against all changes) that failed on every timeframe — correctly, since 83–91 changes are exactly zero.
4. **My own harness reported success-shaped nonsense before it worked.** The node harness that extracts the sheet's badge builder initially returned an API object missing `X_FAST` / `X_SLOW`; the CSV lookup then produced `undefined`, no crossing was ever seen, and the first tape came back as `none` on every candle. It now throws if any piece it leans on fails to extract, and the audit asserts the ABOVE / BELOW / blank split as a witness — an empty mismatch list alone can hide a builder that was never really exercised.
5. **A test that flagged prose for denying the bug** — the forbidden-identifier scan matched "no cross markers" and the vendored library's marker API; it now scans the sheet's own script.
6. **Placeholder text where the requirement asked for blank.** Unavailable percentage changes first rendered the literal word `blank`; they are now genuinely empty cells.
7. **A leftover `tf` reference survived the multi-session refactor** and threw on the first chart build — caught by loading the rebuilt sheet and reading its console, not by the static checks.
8. **The day-strip check flagged its own documentation.** The "no literal dates in the sheet" assertion failed on a date inside a code comment; the check now strips comments before scanning, which is what it meant all along.
9. **A row count was read two ways.** The direction row first had the browser probe reading 8 *body* rows, but the table has 8 rows including its time header — 7 metric rows, which is what the pane caption counts. The probe now indexes the direction row where it is (the seventh body row) and the caption's meaning is unchanged (metric rows exclude the time row).
10. **One of my own new assertions was wrong, not the sheet.** The summary block's `displayLabel` is the ASCII form (`+3/-0`) while `lastLabel` carries spaces and the unicode minus (`+3 / −0`); the check now compares against a matching helper instead of a reformatted string.
11. **The sheet's own Method list drifted from the table.** It said "Eight rows" and stopped at the direction streak, and called that row "the last row"; it now counts the metric rows the table actually emits, documents both crossing rows and the SMA 9 vs SMA 44 relationship with their blank rules, and names the direction row by its position.
12. **The export guard caught a half-applied column.** Adding the relationship step without its CSV cell made the next build fail with `the export columns and the analysis steps have drifted apart` — the writer refuses to emit a row whose keys are not exactly the header, so the omission surfaced in seconds instead of as a missing column in fifteen files. The delivered CSVs are the ones written after the cell was added, and the verifier now asserts the column's position between the crossing columns and the tape on every session.
13. **The panel chips were never painted at boot.** While checking the new arrow chip I found that `renderChips` only ran on a session switch or a price-period edit, so every panel's chips were empty until the reader touched something. The boot sequence now renders them for the active session, which is why `green arrows 9 of 1,880 bars` is visible on first paint. Nothing about the arrow was wrong; the place it was going to be shown was.
14. **A "necessary condition" assertion that the data refused.** The first version of the arrow audit demanded that each of the conditions independently refuse at least one candle the others allow. It failed for two of the six — on these three sessions the relationship word and the previous-candle change were implied by the other four, so they never refused anything on their own (18 near-misses, exactly the 18 arrows). The rule is correct; the assertion now demands what must be true (no condition can refuse an *arrow*, and at least four must be independently binding) and the numbers are [§3.6](#36-the-green-arrow)'s, reported rather than assumed: the distance window allowed 25, the cross 24, the falling run 51 and the rising run 19, against the 18 the rule fires, so the *set* of binding conditions is what the audit prints rather than something it assumes.
15. **My marker-API scan flagged the vendored library and an unrelated key.** Counting `createSeriesMarkers` in the delivered script found the engine's own export map, and counting `belowBar` counted the pre-existing `belowBars` statistics — both outside the sheet's own code. The scan now reads only the sheet's script (from the payload tag onward) and matches whole words, so the four allowed identifiers are counted where they are used and nowhere else.
16. **Two of my own batch edits left a comment block behind.** Rearranging the recipe's sections with two consecutive replacements duplicated the `[sheet]` description above the new `[signal]` block; the duplicated lines are gone. A lesson in reading the file after a multi-part edit rather than trusting the success message.
17. **The console handle outlived the field it read.** `NIFTY_SHEET.signal(tf)` still returned `frame.sig`, which the two-rule refactor replaced with `frame.sigs`, so the documented one-liner would have returned `undefined` — a value that reads like "no arrows" rather than an error, and that no artifact, export or check touches. It now returns the map keyed by rule column (and one rule's block when a column is named); the verifier asserts the accessor reads the field the sheet actually builds, and the fixed call was run in the live page.
18. **A column's label was right in one place and wrong in another — the number behind it was not.** Writing the mirror's table, `window gate` was first reported as *the `BELOW` crossings inside the negated window* (35, 8, 0 … for 2026-10-13) while the sheet's comparison matrix prints the same row as the candles whose distance is inside the window **whatever direction their crossing ran** (76, 8, 3 …) — which is also what `session_summary.json`'s `perCondition` counts. Both numbers are true of different sets, and only one of them is the row the reader will see side by side with the green rule's. The tables now carry the marginal counts the sheet and the summary print, and say so; the crossing-based spans stayed, labelled as the span over that rule's own crossings. A reminder that a table column needs the same definition everywhere it appears.
19. **One of my own checks forbade what the design requires.** The recipe assertion read `"red_arrow" not in recipe["signal"]`, written when the red rule was expected to be purely derived; the shipped recipe gives the mirror an on/off switch in `[signal]`, so the check failed on a correct build. It now asserts what the design actually needs — that the switch is the *only* red key in that block, so no red threshold can drift — and the README's own arrow list was corrected too: it had the 2026-10-15 5-minute frame carrying the arrow that belongs to the 1-minute one.

---

## 9. Notes and limits

- The **1-second input has no volume or bid/ask**, so the sheet has no volume pane and `ticks` stands in as a completeness measure.
- The chart is a **single pane**: the candles with the three price averages, the green arrows under their bars and the red ones above them. The analytics table is DOM placed directly beneath it; the SMA 2/9/44 changes are tabulated in that table rather than plotted.
- **Blank, zero and run length are three different things.** A blank cell is "no previous average yet"; `0.0000` is "the average did not move"; `+0 / −0` means no live run in either direction — which is what a zero change leaves behind.
- **The direction-streak rule reads the change at the precision the sheet shows** — see [§3.3](#33-the-direction-streak) for why a move that rounds to `0.0000` resets the row rather than continuing it.
- **One binary, three sessions.** Every session's bars are inlined, so the sheet is 1.39 MiB; only the first session is materialised at boot and the rest are built on first open.
- **Printing covers the active session** (five single-pane panels) — printing three sessions would be a 15-panel document.
- The **ATM strike** is a modal value per bucket (ties broken toward the later tick). Shown in the legend and ledger, not drawn on the chart.
- The **candle ledger is an appendix**, collapsed for the 12 s and 36 s tabs (above 500 bars); the analytics table is always rendered.
- The 12-second table is 1,881 columns wide; it scrolls horizontally with its label column and time row pinned.
- If you retype a **price-pane** period, the indicator and the exported column names stay `sma2/sma9/sma44` — the analytics are pinned to 2, 9 and 44 by design.
- **The direction row and the crossing rows are pinned to SMA 2 vs SMA 9 as a pair**, not to whichever two price lines are currently plotted: the editable price-pane periods move the candles' averages only, and the rows' own conditions stay exactly the ones written in the requirement. The distance row is pinned to SMA 9 vs SMA 44.
- **A crossing is a change of side, not a relationship.** Both strict comparisons read the current and previous candle, so SMA 2 sitting above SMA 9 for 300 candles is one crossing, not 300 — and an equal pair on either candle is not a crossing at all. Equality is handled by refusing the strict comparison rather than by picking a side, so the rule is symmetric and cannot invent a crossing out of a tie.
- **The relationship row answers the other half of that question.** A10 reads this candle's two averages alone, so it is the current side rather than a change of side, and a tie there is simply blank: a pair that is exactly equal is on neither side, which is why 83 of the delivered candles carry no word at all beyond the 43-candle warm-up on each tape.
- **Both arrows are pinned to the recipe, not to the toolbar.** Their periods are the `[cross]` pair and its distance pair, their runs and change are the `[relation]` pair and their thresholds are the `[signal]` block — so re-typing a price-pane average moves the candles' lines and nothing else. `signal.enabled = false` keeps the `green_arrow` column (all `0`) and draws no green arrow, and `signal.red_arrow = false` does the same for the red column and the marks above the bars, which is the switch to use when you want the chart plain.
- **The distance window is read at the sheet's own precision.** `0.025 %` is compared as the integer `250` at four decimals on both sides, so a boundary value cannot fall one way in Python and the other way in the browser, and both ends of the window are inclusive by construction.
- **The rules are sparse on purpose.** 18 candles of 9,255 fire the green rule across the three sessions and 12 fire the mirror, because the distance window is deliberately tight and a coarse tape cannot produce the crossing at all (3 min and 5 min: zero arrows of either colour, and the matrix says `0 of 126` / `0 of 76` rather than leaving the rows blank). Loosen `[signal] distance_pct_at_cross_max` and more of the in-window crosses become arrows — on both sides at once, because the red window is the same number negated; loosen a run bound and the falling-and-rising pair is satisfied more often — again on both sides, since the mirror exchanges the two runs. Either trade is a recipe edit, not a code edit, and neither can move one arrow without moving the other rule's mirror image of it.
- Exported filenames carry the session date, e.g. `nifty_2026-10-14_12sec_sma2-9-44.csv`.
- **The build is configured, not coded.** Every parameter lives in a recipe file — `config/nifty.json` by default, or `config/nifty.toml`, the same recipe in TOML, and any other file either way; the code holds only the defaults. `--set` overrides a single value for one run, `--out-dir` sends the artifacts somewhere else, and `--print-config` / `--describe` show what a run would do before it does it. The three failures the command line knows about (bad recipe, missing or malformed tape) print one line and exit 2 rather than raising a traceback.
- **`verify.py` keeps its own copy of the expected parameters** and checks them against the recipe, so a parameter change is reported rather than silently auditing a build the verifier was not written for. It imports the `nifty` package for the pipeline's own functions; every *shipped* value it compares is recomputed by its own rule, never by the pipeline.
- **A new analysis plugs in at one place.** Add a step to `nifty/data/analysis.py` and a section to the recipe; its columns then reach the CSV, the JSON exports and the sheet payload on their own. Nothing about the existing rows, the panes or the nine-row table has to change for it.
- A `NIFTY_SHEET` handle is exposed on `window` for console use: `NIFTY_SHEET.day("2026-10-14")`, `NIFTY_SHEET.frame(12, "2026-10-13")`, `NIFTY_SHEET.csv(60)`, `NIFTY_SHEET.json(300)`, `NIFTY_SHEET.print(true)`, and `NIFTY_SHEET.signal(12)` for **both** rules' blocks keyed by column — flags, arrow count, per-condition tallies — or `NIFTY_SHEET.signal(12, "2026-10-13", "red_arrow")` for one rule's.
