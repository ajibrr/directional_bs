"""
audit.harness
=============

Everything the audit's sections share: the constants this audit was written against, its
own readers for a session file and a fresh bucketing loop, the shipped artifacts loaded
once, the `check` / `eq` helpers, and the tally `report()` prints.

Nothing here decides anything. A section imports this module's names and adds checks; the
counter, the failure list and the exit status live here so every section is measured the
same way.
"""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from nifty.output import exports
from nifty.recipe.config import ConfigError, load_config
from nifty.recipe.defaults import DEFAULT_CONFIG_PATH, MIRROR_CONFIG_PATH
from nifty.core.keys import (ABOVE, BELOW, CE_OI_CHANGE, PE_OI_CHANGE,
                        count_label as pipeline_count_label, cross_distance_key, cross_key,
                        relation_key, signal_key)
from nifty.output.meta import signal as signal_meta
from nifty.core.numeric import div_round_half_up, pct_change
from nifty.signals.rules import add_signal, signal_funnel
from nifty.signals.series import (add_analytics, add_cross, add_direction_streak, add_relation,
                          add_sma)

ROOT = Path(__file__).resolve().parents[1]   # audit/harness.py -> the project root
SRC_DIR = ROOT / "input data"
SRC_GLOB = "NIFTY_*_PRICE_1SEC.jsonl"
# a session may ship no tape at all: the dashboard carries the same per-second series under
# `nifty_seconds`, and a dashboard with no tape beside it is a session in its own right
DASH_SUFFIX = "_DASHBOARD.json"
TAPE_SUFFIX = "_PRICE_1SEC.jsonl"
DASH_GLOB = "NIFTY_*_DASHBOARD.json"
# one output tree per index: output/nifty for this recipe, output/sensex for its own
OUT_DIR = ROOT / "output" / "nifty"
OUT_DATA = OUT_DIR / "data"
TEMPLATE = ROOT / "templates" / "sheet.html"
BUILDER = ROOT / "build_charts.py"
PIPELINE_DIR = ROOT / "nifty"
PIPELINE_SOURCES = [BUILDER] + sorted(PIPELINE_DIR.rglob("*.py"))
CONFIG_PATH = ROOT / "config" / "nifty.toml"
README = ROOT / "README.md"

TIMEFRAMES = (12, 36, 60, 180, 300)
SMA_PERIODS = (2, 9, 44)
ANALYTICS_SMAS = (2, 9, 44)
DIRECTION_FAST = ANALYTICS_SMAS[0]     # the direction-streak row pairs SMA 2 with SMA 9
DIRECTION_SLOW = ANALYTICS_SMAS[1]
CROSS_FAST = ANALYTICS_SMAS[0]         # the crossing row pairs the same two averages
CROSS_SLOW = ANALYTICS_SMAS[1]
CROSS_DIST_FROM = ANALYTICS_SMAS[1]    # its distance row reads SMA 9 against SMA 44
CROSS_DIST_TO = ANALYTICS_SMAS[2]
RELATION_FAST = ANALYTICS_SMAS[1]      # the above/below row pairs SMA 9 with SMA 44
RELATION_SLOW = ANALYTICS_SMAS[2]
# the green arrow: one rule, seven conditions, all required (AND). Four are read from the
# candle itself (the last of them from the session's dashboard), three from the candle
# before it -- see the [signal] block of the recipe
SIGNAL_KEY = "green_arrow"
# the red arrow: the same seven conditions read the other way round. The recipe declares no
# red thresholds -- the pipeline derives the rule from the green one -- so this audit
# recomputes it from its own series AND by inverting the tape, and the two must agree
RED_KEY = "red_arrow"
RED_CROSS_DIRECTION = "BELOW"
RED_RELATION = "BELOW"
SIGNAL_CROSS_DIRECTION = "ABOVE"
SIGNAL_RELATION = "ABOVE"
SIGNAL_DISTANCE_PCT_AT_CROSS_MIN = 0.0
SIGNAL_DISTANCE_PCT_AT_CROSS_MAX = 0.025
SIGNAL_CHG_PCT_MIN = 0.0005
# a [signal] threshold the verifier moves to prove the recipe drives the rule (see 11)
SIGNAL_CHG_PCT_MIN_OVERRIDE = 0.01
SIGNAL_STREAK_MINUS_MIN = 7
SIGNAL_STREAK_MINUS_MAX = 15
SIGNAL_STREAK_PLUS_MIN = 7
IST = 19800
PCT_DP = 4
# how many candles a chart opens on: the recipe's [sheet] window_bars. The window is a
# view, not a truncation, so every assertion above still reads the whole session.
WINDOW_BARS = 100

SHEETS = sorted(OUT_DIR.glob("NIFTY_*_SMA_sheet.html"))
SHEET = SHEETS[0] if SHEETS else OUT_DIR / "missing.html"

FAILURES: list[str] = []
CHECKS = 0

# how often an SMA 9 move is real but rounds away to 0.0000% at the shipped precision.
# The direction rule reads the rounded change, so these candles reset the row; the count is
# reported rather than asserted, since the precision is what the sheet displays.
DIR_ROUNDED_AWAY = [0]

# live-data witnesses for the crossing rows: a session in which none of them fired would
# make the per-bar assertions vacuous, so they are counted and asserted present
CROSS_WITNESSES = [0]        # strict crossings found in the real sessions
CROSS_BLANK_DISTANCE = [0]   # crossings whose distance is blank (the divisor has no value)
CROSS_ZERO_DISTANCE = [0]    # crossings whose distance is exactly 0.0000 (equal averages)

# live-data witnesses for the above/below relationship row: a session in which one side,
# or a tie, never appeared would leave its assertions vacuous
REL_ABOVE_BARS = [0]         # candles the relationship row marks ABOVE
REL_BELOW_BARS = [0]         # candles it marks BELOW
REL_BLANK_BARS = [0]         # candles with no side: a tie, or the slow average missing
REL_TIES = [0]               # candles where SMA 9 and SMA 44 are exactly equal

# live-data witnesses for the green arrow: a delivery where no arrow fired would make the
# per-bar assertions vacuous, and a condition that never ruled a candle out would too
SIGNAL_ARROWS = [0]              # arrows across every (session, timeframe)
SIGNAL_FRAMES_WITH_ARROWS = [0]  # frames carrying at least one arrow
SIGNAL_FIRST_CANDLE_HITS = [0]   # arrows on a session's first candle (must stay 0)
SIGNAL_NEAR_MISS = {}            # condition key -> candles the OTHER five conditions pass
# the two arrow rules exactly as the baked recipe resolves them, for the edge cases below.
# The red one is the pipeline's own mirror of the green one -- the audit never builds it
# here, because the point of the checks is to catch a mirror that is not the inversion.
CONFIG_OBJ = load_config(CONFIG_PATH)
SIGNAL_RULE_OBJ = CONFIG_OBJ.signal_rule_obj()
RED_RULE_OBJ = CONFIG_OBJ.red_rule_obj()

# live-data witnesses for the red arrow, and for the two rules staying apart
RED_ARROWS = [0]             # red arrows across every (session, timeframe)
RED_FRAMES_WITH_ARROWS = [0]  # frames carrying at least one red arrow
RED_FIRST_CANDLE_HITS = [0]  # red arrows on a session's first candle (must stay 0)
RED_PAIRED = [0]             # candles carrying BOTH arrows (must stay 0, by construction)
RED_NEAR_MISS = {}           # condition key -> candles the OTHER five red conditions pass


_FLOW_BY_MINUTE: dict[str, dict[int, tuple[int, int]]] = {}


def flow_at(day: str) -> dict[int, tuple[int, int]]:
    """One session's dashboard minute rows, read here from the input file.

    The verifier does not reuse the pipeline's join: it opens the dashboard itself, turns
    each IST timestamp into the same epoch the bars carry and keys the pair by minute, so
    the flow condition is checked against the feed's own columns. A session with no
    dashboard yields an empty map, which is the "condition not read" case.
    """
    if day not in _FLOW_BY_MINUTE:
        path = SRC_DIR / f"NIFTY_{day}_DASHBOARD.json"
        rows: dict[int, tuple[int, int]] = {}
        if path.is_file():
            for row in json.loads(path.read_text(encoding="utf-8")).get("flow", []):
                stamp = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
                epoch = int(stamp.replace(tzinfo=timezone(timedelta(seconds=IST))).timestamp())
                rows[epoch // 60] = (row["ce_oi_change"], row["pe_oi_change"])
        _FLOW_BY_MINUTE[day] = rows
    return _FLOW_BY_MINUTE[day]


def mirror_columns(bars: list[dict]) -> list[dict]:
    """The same bars with every column the two arrow rules read mirrored.

    That is the whole of what an inversion does to a tape as far as a rule is concerned: the
    crossing and the relationship read the other word, a percentage change and a percentage
    distance are negated, and each consecutive count is exchanged for the other of its pair.
    The rule reads nothing else, so the green rule run over this tape is the red rule run
    over the original -- which is the mirror property, stated on the rule's own inputs.

    (Inverting the PRICES instead would produce a tape the pipeline is not asked to handle:
    a percentage change divides by the previous value, and every arithmetic here is exact
    integer paise on positive prices. The columns are where the comparison actually happens,
    so this is the level the property belongs to.)
    """
    flipped = {ABOVE: BELOW, BELOW: ABOVE}
    out = []
    for bar in bars:
        mirrored = dict(bar)
        # the flow comparison mirrors by swapping its two sides, not by negating them: the
        # green rule's "PE above CE" read on a mirrored tape has to see "CE above PE"
        mirrored[CE_OI_CHANGE] = bar.get(PE_OI_CHANGE)
        mirrored[PE_OI_CHANGE] = bar.get(CE_OI_CHANGE)
        for key, value in bar.items():
            if key.endswith("_cross_direction") or key.endswith("_relation"):
                mirrored[key] = flipped.get(value, value)
            elif key.endswith("_chg_pct") or key.endswith("_distance_pct_at_cross"):
                mirrored[key] = None if value is None else -value
            elif key.endswith("_streak_plus") or key.endswith("_streak_minus"):
                # a run and its opposite are one pair: each takes the other's value, and a
                # tape that carries only one of them (a hand-built case below does) reads the
                # missing half as the zero run it is. Setting both keys from either side of
                # the pair is deliberate -- the loop reaches each of them once, and both
                # writes produce the same answer.
                base = key[:-len("_streak_minus")] if key.endswith("_streak_minus") \
                    else key[:-len("_streak_plus")]
                mirrored[base + "_streak_plus"] = bar.get(base + "_streak_minus", 0)
                mirrored[base + "_streak_minus"] = bar.get(base + "_streak_plus", 0)
        out.append(mirrored)
    return out


def check(ok: bool, label: str, detail: str = "") -> bool:
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILURES.append(f"{label}" + (f"  --  {detail}" if detail else ""))
    return ok


def eq(actual, expected, label: str) -> bool:
    return check(actual == expected, label, f"got {actual!r}, expected {expected!r}")


# --------------------------------------------------------------------------------------
# Independent recomputation
# --------------------------------------------------------------------------------------

def div_half_up(numerator: int, denominator: int) -> int:
    """Round-half-away-from-zero, written the long way so it is not the builder's code."""
    if denominator == 0:
        raise ZeroDivisionError
    sign = 1 if numerator >= 0 else -1
    n, d = abs(numerator), abs(denominator)
    whole, rem = divmod(n, d)
    if rem * 2 >= d:
        whole += 1
    return sign * whole


def naive_sma(closes_cents: list[int], period: int) -> list[int | None]:
    """A fresh summation per bar -- deliberately O(n*period), not the rolling trick."""
    out: list[int | None] = []
    for idx in range(len(closes_cents)):
        if idx < period - 1:
            out.append(None)
        else:
            window = closes_cents[idx - period + 1: idx + 1]
            out.append(div_half_up(sum(window), period))
    return out


def naive_pct(cur: int | None, prev: int | None) -> int | None:
    """Percentage change as an integer scaled by 10**PCT_DP."""
    if cur is None or prev is None or prev == 0:
        return None
    return div_half_up((cur - prev) * 100 * (10 ** PCT_DP), prev)


def naive_runs(changes: list[int | None]) -> tuple[list[int], list[int]]:
    """Consecutive run lengths, written from the requirement's rules and nothing else.

    positive -> extend the rising run, zero the falling one
    negative -> extend the falling run, zero the rising one
    reversal -> therefore starts at 1
    exactly zero -> both runs reset to 0
    blank -> nothing has moved yet, both stay 0
    """
    up_run: list[int] = []
    down_run: list[int] = []
    up = down = 0
    for chg in changes:
        if chg is None:
            pass                      # no measurement yet: leave both at 0
        elif chg > 0:
            up, down = up + 1, 0
        elif chg < 0:
            up, down = 0, down + 1
        else:
            up = down = 0
        up_run.append(up)
        down_run.append(down)
    return up_run, down_run


def naive_direction_runs(fast_cents: list[int | None], slow_cents: list[int | None],
                         slow_changes: list[int | None]) -> tuple[list[int], list[int]]:
    """The SMA 2 vs SMA 9 direction streak, written from the requirement's rules only.

    ABOVE -> consecutive candles with fast > slow AND the slow change positive
    BELOW -> consecutive candles with fast < slow AND the slow change negative
    neither combination (including equality, a zero change and an unmeasurable one)
    -> both runs reset to 0, so a switch between the two directions starts at 1
    """
    above_run: list[int] = []
    below_run: list[int] = []
    above = below = 0
    for i in range(len(slow_changes)):
        fc, sc, chg = fast_cents[i], slow_cents[i], slow_changes[i]
        if fc is None or sc is None or chg is None:
            above = below = 0
        elif fc > sc and chg > 0:
            above, below = above + 1, 0
        elif fc < sc and chg < 0:
            above, below = 0, below + 1
        else:
            above = below = 0
        above_run.append(above)
        below_run.append(below)
    return above_run, below_run


def direction_label(above: int, below: int) -> str:
    return f"+{above} / \u2212{below}"


def direction_label_ascii(above: int, below: int) -> str:
    return f"+{above}/-{below}"


def fmt_scaled(scaled: int) -> str:
    sign = "-" if scaled < 0 else ""
    digits = str(abs(scaled)).rjust(PCT_DP + 1, "0")
    return f"{sign}{digits[:-PCT_DP]}.{digits[-PCT_DP:]}"


def count_label(up: int, down: int) -> str:
    return f"+{up} / \u2212{down}"


def ist_day(epoch: int) -> str:
    return datetime.fromtimestamp(epoch + IST, tz=timezone.utc).strftime("%Y-%m-%d")


def paired_tape(dash: Path) -> Path:
    """The tape whose name pairs with a dashboard's: the same name, the other suffix."""
    return dash.with_name(dash.name[:-len(DASH_SUFFIX)] + TAPE_SUFFIX)


def dashboard_seconds(path: Path) -> dict[int, tuple[float, int]]:
    """A dashboard's own per-second series: epoch -> (price, strike)."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {int(row["timestamp_epoch"]): (float(row["nifty"]), int(row["atm"]))
            for row in doc.get("nifty_seconds") or []}


def load_ticks(path: Path) -> list[dict]:
    """One session file as ticks: a tape's lines, or a dashboard's own per-second series."""
    if path.name.endswith(DASH_SUFFIX):
        return [{"epoch": e, "nifty": value[0], "atm": value[1]}
                for e, value in sorted(dashboard_seconds(path).items())]
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        rec = json.loads(raw)
        rows.append({"epoch": int(rec["timestamp_epoch"]), "nifty": float(rec["nifty"]),
                     "atm": int(rec["atm"])})
    return sorted(rows, key=lambda r: r["epoch"])


def discovered_sessions() -> list[Path]:
    """Every session file, one per session: the tapes, plus dashboards with no tape."""
    tapes = sorted(SRC_DIR.glob(SRC_GLOB))
    dashboards = [d for d in sorted(SRC_DIR.glob(DASH_GLOB)) if not paired_tape(d).is_file()]
    return sorted(tapes + dashboards, key=lambda p: p.name)


def naive_bars(ticks: list[dict], seconds: int) -> list[dict]:
    """Rebucket from scratch, scanning each bucket for its extremes."""
    buckets: dict[int, list[dict]] = {}
    order: list[int] = []
    for t in ticks:
        key = t["epoch"] - (t["epoch"] % seconds)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(t)
    bars = []
    for key in sorted(order):
        rows = buckets[key]
        prices = [r["nifty"] for r in rows]
        atm_tally: dict[int, int] = {}
        for r in rows:
            atm_tally[r["atm"]] = atm_tally.get(r["atm"], 0) + 1
        bars.append({
            "time": key,
            "open": round(prices[0] + 0.0, 2),
            "high": round(max(prices) + 0.0, 2),
            "low": round(min(prices) + 0.0, 2),
            "close": round(prices[-1] + 0.0, 2),
            "ticks": len(rows),
            "atm": max(atm_tally.items(), key=lambda kv: (kv[1], [r["atm"] for r in rows].index(kv[0])))[0],
        })
    return bars


def report() -> None:
    """Print the tally and every failure, and exit non-zero when something failed."""
    print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
    print(f"note: the direction rule reads the rounded SMA 9 change, so {DIR_ROUNDED_AWAY[0]} of "
          "the compared candles carry a move too small to show at 4 decimals and reset the row")
    if FAILURES:
        print("\nFAILURES:")
        for failure in FAILURES:
            print(f"  * {failure}")
        sys.exit(1)
    print("OK")
