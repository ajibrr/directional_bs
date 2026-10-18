"""
nifty.signals.series
============

The derived series: what a step adds to a bar. Each function attaches its values to the
bar dicts in place, under a key from `nifty.core.keys` derived from the period it was asked
for, so a bar is both the input and the output of an analysis step:

    add_sma               sma<period>                                    float | None
    add_analytics         sma<period>_chg_pct                            float | None
                          sma<period>_streak_plus                        int
                          sma<period>_streak_minus                       int
    add_direction_streak  sma<fast>_vs_sma<slow>_above_streak            int
                          sma<fast>_vs_sma<slow>_below_streak            int
    add_cross             sma<fast>_vs_sma<slow>_cross_direction         str | None
                          sma<from>_vs_sma<to>_distance_pct_at_cross     float | None
                          sma<fast>_vs_sma<slow>_distance_pct_at_cross   float | None
    add_relation          sma<fast>_vs_sma<slow>_relation                str | None

All of them are descriptive: the rows say where two averages swapped sides, which side
they sit on, how long a run is, and how far apart they were when they crossed. None of
them decides anything -- the one rule that does decide lives in `nifty.signals.rules`, reads the
columns these functions write, and is declared by the recipe rather than by the data.

Each `*_rule` function here is the sentence that describes its row. They are written
from the periods they were configured with, so a changed pair changes the prose with it,
and a recipe may override the sentence without touching the row.

`bar_color` is the smallest of these: the candle's own body, compared in exact integer
paise, which is what the green / red / doji counts are read from.
"""

from __future__ import annotations

from ..core.keys import (analytics_keys, cross_distance_key, cross_key, direction_keys,
                   relation_key, sma_key)
from ..core.numeric import PCT_DECIMALS, cents_to_price, pct_change, to_cents


# --------------------------------------------------------------------------------------
# The candle's own body
# --------------------------------------------------------------------------------------

def bar_color(bar: dict) -> str:
    """'green' / 'red' / 'doji' for one candle, compared in exact integer paise.

    Green closes above its open, red below it, and a candle that closes exactly where it
    opened is a doji -- a tie, which belongs to neither colour rather than to both. The
    body is read from the bar's own open and close, which every bar carries, so this adds
    no series and needs no step of its own: the summary's green / red / doji counts are
    read from here, and from nowhere else.
    """
    opened, closed = to_cents(bar["open"]), to_cents(bar["close"])
    if closed > opened:
        return "green"
    return "red" if closed < opened else "doji"


# --------------------------------------------------------------------------------------
# Moving averages
# --------------------------------------------------------------------------------------

def add_sma(bars: list[dict], period: int) -> None:
    """Attach the simple moving average of the bar close to each bar, in place.

    The mean is a rolling sum of integer paise, so the value is exactly reproducible;
    the first period-1 bars have no average and are left None.
    """
    key = sma_key(period)
    cents = [to_cents(b["close"]) for b in bars]
    total = 0
    for idx, bar in enumerate(bars):
        total += cents[idx]
        if idx >= period:
            total -= cents[idx - period]
        bar[key] = cents_to_price(total, period) if idx >= period - 1 else None


# --------------------------------------------------------------------------------------
# Percentage change and consecutive runs
# --------------------------------------------------------------------------------------

def add_analytics(bars: list[dict], period: int, decimals: int = PCT_DECIMALS) -> None:
    """Attach the per-candle percentage change and the current run of consecutive moves.

    sma<p>_chg_pct        percentage change vs the previous candle's average, or None
                          when that average does not exist yet
    sma<p>_streak_plus    length of the current unbroken run of rising changes, 0 if the
    sma<p>_streak_minus   last measurable change was not rising (and vice versa)

    Run rules, per period and independent of the other periods:
      * a positive change extends the rising run and drops the falling run to 0
      * a negative change extends the falling run and drops the rising run to 0
      * a reversal therefore starts a new run at 1
      * a change of exactly zero resets BOTH runs to 0

    A blank change (no previous average yet) leaves both runs at 0 -- nothing has moved
    yet, so there is no streak to report.
    """
    chg_key, up_key, down_key = analytics_keys(period)
    cents = [None if b[sma_key(period)] is None else to_cents(b[sma_key(period)]) for b in bars]
    up = down = 0
    for idx, bar in enumerate(bars):
        prev = cents[idx - 1] if idx > 0 else None
        cur = cents[idx]
        chg = pct_change(cur, prev, decimals) if (cur is not None and prev is not None) else None
        bar[chg_key] = chg
        if chg is not None:
            if chg > 0:
                up, down = up + 1, 0
            elif chg < 0:
                up, down = 0, down + 1
            else:
                up = down = 0
        bar[up_key] = up
        bar[down_key] = down


# --------------------------------------------------------------------------------------
# The direction streak (one pair of averages)
# --------------------------------------------------------------------------------------

def direction_rule(fast: int, slow: int) -> str:
    """The sentence the sheet prints for the direction row."""
    return (f"ABOVE: SMA {fast} > SMA {slow} and the SMA {slow} change (%) is positive; "
            f"BELOW: SMA {fast} < SMA {slow} and the SMA {slow} change (%) is negative; "
            "neither combination resets the streak to 0, so a switch from BELOW to ABOVE "
            "(or back) starts the new streak at 1")


def add_direction_streak(bars: list[dict], fast: int = 2, slow: int = 9) -> None:
    """Attach the SMA fast vs SMA slow direction streak to each bar, in place.

    ABOVE     -- consecutive candles where SMA fast > SMA slow and SMA slow is rising
    BELOW     -- consecutive candles where SMA fast < SMA slow and SMA slow is falling
    neither   -- both runs drop to 0, so a switch from BELOW to ABOVE (or back) starts
                 the new run at 1 and a candle that fits no rule resets the row

    The change is read from the bar's own sma<slow>_chg_pct, i.e. the rounded
    value the sheet prints in its 'SMA n Change (%)' row, not the raw paise delta, so
    the row and the counts above it always agree. This step therefore expects
    `add_analytics(bars, slow)` to have run first.
    """
    above_key, below_key = direction_keys(fast, slow)
    fast_cents = [None if b[sma_key(fast)] is None else to_cents(b[sma_key(fast)]) for b in bars]
    slow_cents = [None if b[sma_key(slow)] is None else to_cents(b[sma_key(slow)]) for b in bars]
    above = below = 0
    for idx, bar in enumerate(bars):
        chg = bar[f"sma{slow}_chg_pct"]
        fc, sc = fast_cents[idx], slow_cents[idx]
        if fc is None or sc is None or chg is None:
            above = below = 0            # no comparison available yet: nothing to count
        elif fc > sc and chg > 0:
            above, below = above + 1, 0
        elif fc < sc and chg < 0:
            above, below = 0, below + 1
        else:
            above = below = 0            # equality, or a change of exactly zero
        bar[above_key] = above
        bar[below_key] = below


# --------------------------------------------------------------------------------------
# The strict crossing, and the distance it carries
# --------------------------------------------------------------------------------------

def cross_rule(fast: int, slow: int) -> str:
    """The sentence the sheet prints for the crossing row."""
    return (f"ABOVE: SMA {fast} was below SMA {slow} on the previous candle and is above it "
            "on this one; BELOW: SMA "
            f"{fast} was above SMA {slow} on the previous candle and is below it now; a pair "
            "that is equal on either candle is not a crossing, and the first candle of a "
            "session has no previous candle at all, so it carries none")


def cross_distance_rule(from_period: int, to_period: int) -> str:
    """The sentence the sheet prints for the distance row."""
    return (f"the signed distance ((SMA {from_period} - SMA {to_period}) / SMA {to_period}) "
            "* 100 on the candle that carries a crossing, rounded half-up to the configured "
            "percentage precision; blank when there is no crossing, when either average is "
            f"unavailable, or when SMA {to_period} is zero")


def add_cross(bars: list[dict], fast: int = 2, slow: int = 9, distance_from: int = 9,
              distance_to: int = 44, decimals: int = PCT_DECIMALS) -> None:
    """Attach the strict crossing direction and its distance (%) to each bar, in place.

    sma<fast>_vs_sma<slow>_cross_direction            'ABOVE' | 'BELOW' | None
    sma<from>_vs_sma<to>_distance_pct_at_cross        float | None
    sma<fast>_vs_sma<slow>_distance_pct_at_cross      float | None   (supplementary)

    ABOVE  -- the fast average was below the slow one on the previous candle and is
              above it on this one
    BELOW  -- the fast average was above the slow one on the previous candle and is
              below it on this one
    None   -- no crossing: the pair stayed on the same side, either candle's two
              averages are equal (an equal pair is never a strict crossing), or one of
              the four average values is unavailable. The first candle of a session has
              no previous candle, so it can never carry a crossing.

    The distances are read on the crossing candle itself, from the same averages that
    candle printed: (SMA from - SMA to) / SMA to * 100, rounded half-up to `decimals`.
    A zero divisor leaves the field empty rather than raising, and an average that does
    not exist yet leaves it empty too.

    The token is written upper case, exactly as the row displays it, so the CSV, the JSON
    and the rendered cell all carry the same word.

    Only the current and the previous candle are read, so nothing here can see a future
    bar; and a session's bars start at its own first candle, so a crossing is never
    carried across a session boundary.
    """
    direction_key = cross_key(fast, slow)
    distance_key = cross_distance_key(distance_from, distance_to)
    pair_distance_key = cross_distance_key(fast, slow)
    periods = sorted({fast, slow, distance_from, distance_to})
    cents = {p: [None if b[sma_key(p)] is None else to_cents(b[sma_key(p)]) for b in bars]
             for p in periods}

    for idx, bar in enumerate(bars):
        direction = None
        fc, sc = cents[fast][idx], cents[slow][idx]
        if idx > 0:
            pf, ps = cents[fast][idx - 1], cents[slow][idx - 1]
            if None not in (pf, ps, fc, sc):
                if pf < ps and fc > sc:
                    direction = "ABOVE"
                elif pf > ps and fc < sc:
                    direction = "BELOW"
        bar[direction_key] = direction
        if direction is None:
            bar[distance_key] = None
            bar[pair_distance_key] = None
            continue
        # the crossing candle's own averages; a missing or zero divisor is left blank
        from_cents, to_cents_ = cents[distance_from][idx], cents[distance_to][idx]
        bar[distance_key] = (pct_change(from_cents, to_cents_, decimals)
                             if None not in (from_cents, to_cents_) else None)
        bar[pair_distance_key] = pct_change(fc, sc, decimals)


# --------------------------------------------------------------------------------------
# The above/below relationship (one pair of averages)
# --------------------------------------------------------------------------------------

def relation_rule(fast: int, slow: int) -> str:
    """The sentence the sheet prints for the above/below relationship row."""
    return (f"ABOVE when SMA {fast} > SMA {slow} on this candle; BELOW when SMA {fast} < "
            f"SMA {slow}; empty when the two averages are equal on that candle, or when "
            "either one is unavailable")


def add_relation(bars: list[dict], fast: int = 9, slow: int = 44) -> None:
    """Attach the fast vs slow side relationship to each bar, in place.

    sma<fast>_vs_sma<slow>_relation       'ABOVE' | 'BELOW' | None

    ABOVE -- the fast average sits above the slow one on this candle
    BELOW -- it sits below it
    None  -- the two are equal (a tie belongs to neither side), or one of them does not
             exist yet, which every candle before the slow average's period is

    This is the current relationship, not a crossing: it is a plain comparison of the two
    averages on the candle itself, so it holds on every candle the averages both exist.
    `add_cross` answers the different question of when the pair changed side, and a candle
    can carry a word here while carrying no crossing at all.
    """
    key = relation_key(fast, slow)
    fast_cents = [None if b[sma_key(fast)] is None else to_cents(b[sma_key(fast)]) for b in bars]
    slow_cents = [None if b[sma_key(slow)] is None else to_cents(b[sma_key(slow)]) for b in bars]
    for idx, bar in enumerate(bars):
        fc, sc = fast_cents[idx], slow_cents[idx]
        bar[key] = None if (fc is None or sc is None or fc == sc) else (
            "ABOVE" if fc > sc else "BELOW")
