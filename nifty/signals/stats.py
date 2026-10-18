"""
nifty.signals.stats
===========

The summaries a build ships beside its bars.

`timeframe_stats` describes one timeframe of one session: its bar count, the session
OHLC it covers, the average bar range, the last value of every average, the state of
every run, and the summaries of the direction-streak, crossing, above/below relationship
and green-arrow rows.

`session_meta` describes the session itself: its source file (the tape, or the dashboard
when that is all it ships), its tick count and the time it covers, how much of that span
the source actually filled, and the configuration that produced it -- so a reader of session_summary.json can tell what was run, and a
verifier can tell that one day was not built with another day's settings.

The field order here is the order the exports and the sheet's payload serialise, so it
is part of the artifact contract rather than an accident of the code.
"""

from __future__ import annotations

from pathlib import Path

from ..output import meta
from ..core.clock import ist_full, ist_label, tf_label, tf_short, tf_slug
from ..recipe.config import Config
from ..core.keys import (count_label, count_label_ascii, cross_distance_key, cross_key,
                   direction_keys, relation_key, sma_key)
from ..core.numeric import r2
from .rules import GreenArrowRule, signal_funnel
from .series import bar_color


def direction_stats(bars: list[dict], fast: int, slow: int, rule: str) -> dict:
    """Summary of the fast vs slow direction streak for one timeframe."""
    above_key, below_key = direction_keys(fast, slow)

    def side(bar: dict) -> int:
        return 1 if bar[above_key] else (-1 if bar[below_key] else 0)

    sides = [side(b) for b in bars]
    switches = sum(1 for i in range(1, len(bars))
                   if sides[i] != 0 and sides[i - 1] != 0 and sides[i] != sides[i - 1])
    last = bars[-1]
    return {
        "fastPeriod": fast,
        "slowPeriod": slow,
        "aboveKey": above_key,
        "belowKey": below_key,
        "rule": rule,
        "lastAbove": last[above_key],
        "lastBelow": last[below_key],
        "lastLabel": count_label(last[above_key], last[below_key]),
        "displayLabel": count_label_ascii(last[above_key], last[below_key]),
        "maxAbove": max(b[above_key] for b in bars),
        "maxBelow": max(b[below_key] for b in bars),
        "aboveBars": sum(1 for b in bars if b[above_key] > 0),
        "belowBars": sum(1 for b in bars if b[below_key] > 0),
        "resetBars": sum(1 for b in bars if not b[above_key] and not b[below_key]),
        "switches": switches,
        "firstAboveIndex": next((i for i, b in enumerate(bars) if b[above_key] > 0), None),
        "firstBelowIndex": next((i for i, b in enumerate(bars) if b[below_key] > 0), None),
    }


def relation_stats(bars: list[dict], cfg: Config) -> dict:
    """Summary of the fast vs slow above/below relationship, for one timeframe."""
    key = relation_key(cfg.relation_fast, cfg.relation_slow)
    words = [b[key] for b in bars]

    def longest(word: str) -> int:
        run = best = 0
        for value in words:
            run = run + 1 if value == word else 0
            best = max(best, run)
        return best

    switches = sum(1 for i in range(1, len(words))
                   if words[i] and words[i - 1] and words[i] != words[i - 1])
    return {
        "fastPeriod": cfg.relation_fast,
        "slowPeriod": cfg.relation_slow,
        "column": key,
        "rule": cfg.relation_rule,
        "last": words[-1],
        "aboveBars": words.count("ABOVE"),
        "belowBars": words.count("BELOW"),
        "blankBars": words.count(None),
        "maxAboveRun": longest("ABOVE"),
        "maxBelowRun": longest("BELOW"),
        "switches": switches,
        "firstIndex": next((i for i, w in enumerate(words) if w), None),
    }


def cross_stats(bars: list[dict], cfg: Config) -> dict:
    """Summary of the strict crossings and the distances they carried, for one timeframe."""
    direction_key = cross_key(cfg.cross_fast, cfg.cross_slow)
    distance_key = cross_distance_key(cfg.cross_distance_from, cfg.cross_distance_to)
    pair_key = cross_distance_key(cfg.cross_fast, cfg.cross_slow)

    above = [i for i, b in enumerate(bars) if b[direction_key] == "ABOVE"]
    below = [i for i, b in enumerate(bars) if b[direction_key] == "BELOW"]
    crossings = sorted(above + below)
    distances = [b[distance_key] for b in bars if b[distance_key] is not None]
    pair_distances = [b[pair_key] for b in bars if b[pair_key] is not None]
    last = crossings[-1] if crossings else None

    def spread(values: list[float]) -> dict:
        return {
            "count": len(values),
            "last": values[-1] if values else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "avg": round(sum(values) / len(values), cfg.pct_decimals) if values else None,
        }

    return {
        "fastPeriod": cfg.cross_fast,
        "slowPeriod": cfg.cross_slow,
        "distanceFromPeriod": cfg.cross_distance_from,
        "distanceToPeriod": cfg.cross_distance_to,
        "directionColumn": direction_key,
        "distanceColumn": distance_key,
        "pairDistanceColumn": pair_key,
        "rule": cfg.cross_rule,
        "distanceRule": cfg.cross_distance_rule,
        "aboveCrossings": len(above),
        "belowCrossings": len(below),
        "crossings": len(crossings),
        "firstCrossIndex": crossings[0] if crossings else None,
        "lastCrossIndex": last,
        "lastCrossDirection": bars[last][direction_key] if last is not None else None,
        "distance": spread(distances),
        "distanceAbove": sum(1 for v in distances if v > 0),
        "distanceBelow": sum(1 for v in distances if v < 0),
        "distanceZero": sum(1 for v in distances if v == 0),
        "distanceBlank": len(crossings) - len(distances),
        "pairDistance": spread(pair_distances),
    }


def timeframe_stats(seconds: int, bars: list[dict], cfg: Config) -> dict:
    """Everything the summary, the chips and the comparison matrix state about one timeframe."""
    last = bars[-1]
    session_open = bars[0]["open"]
    session_close = last["close"]
    high = max(b["high"] for b in bars)
    low = min(b["low"] for b in bars)
    # one reading of the candle's own body, in the paise every other series is compared in
    colors = [bar_color(b) for b in bars]
    return {
        "seconds": seconds,
        "label": tf_label(seconds),
        "short": tf_short(seconds),
        "slug": tf_slug(seconds),
        "bars": len(bars),
        "firstBar": bars[0]["time"],
        "lastBar": last["time"],
        "firstBarIST": ist_label(bars[0]["time"]),
        "lastBarIST": ist_label(last["time"]),
        "open": session_open, "high": high, "low": low, "close": session_close,
        "changePts": r2(session_close - session_open),
        "changePct": round((session_close - session_open) / session_open * 100.0, 3),
        "rangePts": r2(high - low),
        "avgBarRange": r2(sum(b["high"] - b["low"] for b in bars) / len(bars)),
        "smaLast": {str(p): last[sma_key(p)] for p in cfg.price_periods},
        "analytics": {
            str(p): {
                "lastChgPct": last[f"sma{p}_chg_pct"],
                "streakPlus": last[f"sma{p}_streak_plus"],
                "streakMinus": last[f"sma{p}_streak_minus"],
                "lastLabel": count_label(last[f"sma{p}_streak_plus"], last[f"sma{p}_streak_minus"]),
                "displayLabel": count_label_ascii(last[f"sma{p}_streak_plus"],
                                                  last[f"sma{p}_streak_minus"]),
                "maxStreakPlus": max(b[f"sma{p}_streak_plus"] for b in bars),
                "maxStreakMinus": max(b[f"sma{p}_streak_minus"] for b in bars),
                "risingChanges": sum(1 for b in bars if (b[f"sma{p}_chg_pct"] or 0) > 0),
                "fallingChanges": sum(1 for b in bars if (b[f"sma{p}_chg_pct"] or 0) < 0),
                "zeroChanges": sum(1 for b in bars if b[f"sma{p}_chg_pct"] == 0),
                "blankChanges": sum(1 for b in bars if b[f"sma{p}_chg_pct"] is None),
                "firstChgIndex": next((i for i, b in enumerate(bars)
                                       if b[f"sma{p}_chg_pct"] is not None), None),
                "definedFrom": next((i for i, b in enumerate(bars)
                                     if b[sma_key(p)] is not None), None),
            } for p in cfg.analytics_periods
        },
        "direction": direction_stats(bars, cfg.direction_fast, cfg.direction_slow,
                                     cfg.direction_rule),
        "cross": cross_stats(bars, cfg),
        "signal": signal_stats(bars, cfg),
        "redSignal": red_signal_stats(bars, cfg),
        "relation": relation_stats(bars, cfg),
        "avgTicksPerBar": round(sum(b["ticks"] for b in bars) / len(bars), 1),
        "greenBars": colors.count("green"),
        "redBars": colors.count("red"),
        "dojiBars": colors.count("doji"),
    }


def signal_stats(bars: list[dict], cfg: Config) -> dict:
    """Summary of the green-arrow rule for one timeframe."""
    return _rule_stats(bars, cfg.signal_rule_obj(), cfg.signal_enabled, cfg.signal_column)


def red_signal_stats(bars: list[dict], cfg: Config) -> dict:
    """Summary of the red-arrow rule: the same block, read from the mirror rule.

    The two summaries are the one function over two rules, so their keys line up field by
    field and the sheet can present them side by side without a second reader.
    """
    return _rule_stats(bars, cfg.red_rule_obj(), cfg.signal_red_enabled, cfg.red_column)


def _rule_stats(bars: list[dict], rule: GreenArrowRule, enabled: bool,
                key: str) -> dict:
    """One arrow rule's summary for one timeframe.

    The arrows themselves, where the first and last of them landed, and -- for each of
    the seven conditions -- how many candles held that condition on its own. The tallies
    come from the same tests the flag was built from, so they describe the rule that was
    actually applied rather than a second reading of it.
    """
    hits = [i for i, bar in enumerate(bars) if bar[key]]
    return {
        "enabled": enabled,
        "column": key,
        "arrows": len(hits),
        "candles": len(bars),
        "firstIndex": hits[0] if hits else None,
        "lastIndex": hits[-1] if hits else None,
        "firstArrowIST": ist_full(bars[hits[0]]["time"]) if hits else None,
        "lastArrowIST": ist_full(bars[hits[-1]]["time"]) if hits else None,
        "conditions": rule.rule_text(),
        "perCondition": signal_funnel(bars, rule),
    }


def session_meta(cfg: Config, src: Path, ticks: list[dict], date: str) -> dict:
    """The session block: its source file, what it covers, and the recipe that read it."""
    expected = ticks[-1]["epoch"] - ticks[0]["epoch"] + 1
    session = {
        "source": cfg.source_path(src),
        "instrument": cfg.instrument,
        "dateIST": date,
        "sessionStartIST": ist_full(ticks[0]["epoch"]),
        "sessionEndIST": ist_full(ticks[-1]["epoch"]),
        "ticks": len(ticks),
        "secondsExpected": expected,
        "secondsMissing": expected - len({t["epoch"] for t in ticks}),
        "coveragePct": round(len(ticks) / expected * 100.0, 2),
        "dayOpen": r2(ticks[0]["nifty"]),
        "dayHigh": r2(max(t["nifty"] for t in ticks)),
        "dayLow": r2(min(t["nifty"] for t in ticks)),
        "dayClose": r2(ticks[-1]["nifty"]),
        "timeframes": list(cfg.timeframes),
        **meta.indicator_periods(cfg),
        **meta.side_blocks(cfg),
        **meta.arrow_blocks(cfg),
        "runRule": cfg.run_rule,
        "pctDecimals": cfg.pct_decimals,
        # two audited marker rules run over every timeframe -- the green arrow and the red
        # one that mirrors it. They are the only signal-like output in the sheet, and their
        # conditions and thresholds travel with the session so a reader can see exactly
        # what was applied. The red rule is derived, so the recipe has one set of numbers.
        "signalLogic": True,
        "atmStrikes": sorted({t["atm"] for t in ticks}),
    }
    session["dayChangePts"] = r2(session["dayClose"] - session["dayOpen"])
    session["dayChangePct"] = round(
        (session["dayClose"] - session["dayOpen"]) / session["dayOpen"] * 100.0, 3)
    return session
