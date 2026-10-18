"""
nifty.data.analysis
==============

The ordered list of analysis steps a build runs over every timeframe's bars.

A step owns three things and nothing else:

    name      how the step is referred to in a report
    summary   one line saying what it derives
    columns   the bar keys it writes, for a given config  -> CSV / JSON / sheet
    run       the work itself, over one timeframe's bars

That is the whole extension point. `pipeline.build_day` runs `run_steps` for each
timeframe, `exports.csv_columns` asks this module for the column order, and the sheet
is handed the same names, so a new step appears in the CSV, the JSON exports and the
table together -- no writer, and no pipeline, needs to learn about it.

Steps are applied in the order listed, and a later step may rely on an earlier one
(the direction streak reads the percentage change the analytics step writes).

The two dashboard columns the arrow rules compare are not a step: they are an input the
pipeline joins onto the bars before any step runs (`nifty.data.flow.attach_flow`), which is why
they are declared in `nifty.output.exports` beside the tape's own `atm` and `ticks`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..signals import rules, series
from ..recipe.config import Config
from ..core.keys import (analytics_keys, cross_distance_key, cross_key, direction_keys, red_key,
                   relation_key, signal_key, sma_key)


@dataclass(frozen=True)
class Step:
    """One analysis over one timeframe's bars."""

    name: str
    summary: str
    columns: Callable[[Config], tuple[str, ...]]
    run: Callable[[list[dict], Config], None]


# --------------------------------------------------------------------------------------
# The steps
# --------------------------------------------------------------------------------------

def _sma_columns(cfg: Config) -> tuple[str, ...]:
    return tuple(sma_key(p) for p in cfg.price_periods)


def _run_sma(bars: list[dict], cfg: Config) -> None:
    for period in cfg.price_periods:
        series.add_sma(bars, period)


def _analytics_columns(cfg: Config) -> tuple[str, ...]:
    return tuple(key for period in cfg.analytics_periods
                 for key in analytics_keys(period))


def _run_analytics(bars: list[dict], cfg: Config) -> None:
    for period in cfg.analytics_periods:
        series.add_analytics(bars, period, cfg.pct_decimals)


def _direction_columns(cfg: Config) -> tuple[str, ...]:
    return direction_keys(cfg.direction_fast, cfg.direction_slow)


def _run_direction(bars: list[dict], cfg: Config) -> None:
    series.add_direction_streak(bars, cfg.direction_fast, cfg.direction_slow)


def _cross_columns(cfg: Config) -> tuple[str, ...]:
    return (cross_key(cfg.cross_fast, cfg.cross_slow),
            cross_distance_key(cfg.cross_distance_from, cfg.cross_distance_to),
            cross_distance_key(cfg.cross_fast, cfg.cross_slow))


def _run_cross(bars: list[dict], cfg: Config) -> None:
    series.add_cross(bars, cfg.cross_fast, cfg.cross_slow, cfg.cross_distance_from,
                     cfg.cross_distance_to, cfg.pct_decimals)


def _relation_columns(cfg: Config) -> tuple[str, ...]:
    return (relation_key(cfg.relation_fast, cfg.relation_slow),)


def _run_relation(bars: list[dict], cfg: Config) -> None:
    series.add_relation(bars, cfg.relation_fast, cfg.relation_slow)


def _signal_columns(cfg: Config) -> tuple[str, ...]:
    return (signal_key(),)


def _run_signal(bars: list[dict], cfg: Config) -> None:
    rules.add_signal(bars, cfg.signal_rule_obj(), cfg.signal_column)


def _red_signal_columns(cfg: Config) -> tuple[str, ...]:
    return (red_key(),)


def _run_red_signal(bars: list[dict], cfg: Config) -> None:
    rules.add_signal(bars, cfg.red_rule_obj(), cfg.red_column)


STEPS: tuple[Step, ...] = (
    Step(name="sma",
         summary="simple moving averages of the bar close, plotted on the price pane",
         columns=_sma_columns, run=_run_sma),
    Step(name="analytics",
         summary="per-candle percentage change and the current consecutive run of moves",
         columns=_analytics_columns, run=_run_analytics),
    Step(name="direction_streak",
         summary="the fast vs slow average direction row (ABOVE / BELOW run lengths)",
         columns=_direction_columns, run=_run_direction),
    Step(name="cross",
         summary="the strict fast/slow crossing row and, on that candle, the signed "
                 "distance between two other averages (%)",
         columns=_cross_columns, run=_run_cross),
    Step(name="relation",
         summary="which side of each other two averages sit on, one word per candle "
                 "(ABOVE / BELOW)",
         columns=_relation_columns, run=_run_relation),
    Step(name="signal",
         summary="the green-arrow rule: one flag per candle, 1 where all seven conditions "
                 "hold (three on this candle, one from the dashboard's minute it opens in, "
                 "three on the previous one), else 0",
         columns=_signal_columns, run=_run_signal),
    Step(name="red_signal",
         summary="the red-arrow rule, the green one's exact mirror: one flag per candle, "
                 "1 where all seven conditions hold the other way round, else 0",
         columns=_red_signal_columns, run=_run_red_signal),
)


# --------------------------------------------------------------------------------------
# Driving them
# --------------------------------------------------------------------------------------

def run_steps(bars: list[dict], cfg: Config) -> None:
    """Run every step, in order, over one timeframe's bars."""
    for step in STEPS:
        step.run(bars, cfg)


def column_names(cfg: Config) -> tuple[str, ...]:
    """Every bar key the steps write, in step order."""
    return tuple(key for step in STEPS for key in step.columns(cfg))
