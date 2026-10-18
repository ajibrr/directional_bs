"""
nifty.output.meta
==========

The metadata blocks: what each artifact says about the recipe it was built from.

Four artifacts carry the same statement of the rule they ran -- the inlined sheet
payload, each frame inside it, `session_summary.json`, and every per-timeframe
`nifty_<slug>.json` -- and a reader is expected to be able to compare them. So the
blocks are built here, once each, and every artifact composes the ones it needs:

    indicator_periods   the price averages and the analytics averages
    direction           the direction-streak pair and its rule sentence
    cross               the crossing pair, the distance pair and both sentences
    relation            the above/below pair and its rule sentence
    signal              the green-arrow rule: its periods, thresholds and sentence
    red_signal          the red-arrow rule, in the same keys and the same order

`side_blocks` and `arrow_blocks` group the last two rows of that list the way the
artifacts carry them (direction, cross, relation, then signal, redSignal), so a site
splices in the same shape with `**`.

Key order is part of the contract, not an accident: the artifacts are diffed and read
side by side, and the two arrow blocks are compared field by field -- which is only
meaningful while both are written in the same order. Nothing here computes a value; it
formats a `Config` and a `GreenArrowRule` for JSON.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:                                    # a type only: no import at run time
    from ..recipe.config import Config
    from ..signals.rules import GreenArrowRule


def indicator_periods(cfg: "Config") -> dict:
    """The averages every artifact's meta block opens with."""
    return {"smaPeriods": list(cfg.price_periods),
            "analyticsSmas": list(cfg.analytics_periods)}


def direction(cfg: "Config", with_columns: bool = True) -> dict:
    """The direction-streak block as the payload carries it, key order included.

    `with_columns=False` drops the two run columns: a frame inside the sheet carries the
    periods and the sentence, and the columns are already the sheet's own table headings.
    """
    meta: dict[str, object] = {"fastPeriod": cfg.direction_fast,
                               "slowPeriod": cfg.direction_slow}
    if with_columns:
        meta["aboveColumn"] = cfg.direction_above_column
        meta["belowColumn"] = cfg.direction_below_column
    meta["rule"] = cfg.direction_rule
    return meta


def cross(cfg: "Config", with_columns: bool = True) -> dict:
    """The crossing block as the payload carries it, key order included."""
    meta: dict[str, object] = {"fastPeriod": cfg.cross_fast,
                               "slowPeriod": cfg.cross_slow,
                               "distanceFromPeriod": cfg.cross_distance_from,
                               "distanceToPeriod": cfg.cross_distance_to}
    if with_columns:
        meta["directionColumn"] = cfg.cross_direction_column
        meta["distanceColumn"] = cfg.cross_distance_column
        meta["pairDistanceColumn"] = cfg.cross_pair_distance_column
    meta["rule"] = cfg.cross_rule
    meta["distanceRule"] = cfg.cross_distance_rule
    return meta


def relation(cfg: "Config", with_columns: bool = True) -> dict:
    """The above/below relationship block as the payload carries it."""
    meta: dict[str, object] = {"fastPeriod": cfg.relation_fast,
                               "slowPeriod": cfg.relation_slow}
    if with_columns:
        meta["relationColumn"] = cfg.relation_column
    meta["rule"] = cfg.relation_rule
    return meta


def side_blocks(cfg: "Config", with_columns: bool = True) -> dict:
    """The three descriptive rows every artifact carries, in the order it carries them."""
    return {"directionStreak": direction(cfg, with_columns),
            "cross": cross(cfg, with_columns),
            "relation": relation(cfg, with_columns)}


def arrow_rule(rule: "GreenArrowRule", enabled: bool, column: str, sentence: str,
               label: str, mark: str, marker_position: str) -> dict:
    """One arrow rule as the payload carries it, thresholds included.

    The thresholds travel twice: as the percentages a reader recognises, and as the
    scaled integers the comparison is actually made in. The sheet reads the scaled
    pair, so its arrow cannot land on a different candle than the pipeline's flag. What
    else the comparison needs travels too -- which word each row must read, whether the
    change is read above or below its threshold, and which of the two runs on the
    previous candle is the counted one -- so the sheet runs a mirrored rule from the
    payload rather than from a second copy of the rule.
    """
    distance_pct_at_cross_min, distance_pct_at_cross_max, chg_pct_min = rule.scaled_bounds()
    return {
        "enabled": enabled,
        "column": column,
        "crossFastPeriod": rule.cross_fast,
        "crossSlowPeriod": rule.cross_slow,
        "distanceFromPeriod": rule.distance_from,
        "distanceToPeriod": rule.distance_to,
        "fastPeriod": rule.fast_period,
        "slowPeriod": rule.slow_period,
        "crossDirection": rule.cross_direction,
        "relation": rule.relation,
        "distancePctAtCrossMin": rule.distance_pct_at_cross_min,
        "distancePctAtCrossMax": rule.distance_pct_at_cross_max,
        "distancePctAtCrossMinScaled": distance_pct_at_cross_min,
        "distancePctAtCrossMaxScaled": distance_pct_at_cross_max,
        "chgPctMin": rule.chg_pct_min,
        "chgPctMinScaled": chg_pct_min,
        "streakMinusMin": rule.streak_minus_min,
        "streakMinusMax": rule.streak_minus_max,
        "streakPlusMin": rule.streak_plus_min,
        "rule": sentence,
        "label": label,
        "mark": mark,
        "markerPosition": marker_position,
        "inverted": rule.inverted,
        "chgAbove": not rule.inverted,
        "fastRun": "plus" if rule.inverted else "minus",
        "slowRun": "minus" if rule.inverted else "plus",
        # the dashboard pair the flow condition compares, in the rule's own order: the
        # sheet runs the comparison from these two names, and `mirrored()` has swapped
        # them, so a red rule cannot compare the pair the green way round
        "flowAbove": rule.flow_above,
        "flowBelow": rule.flow_below,
        "useFlow": rule.use_flow,
    }


def signal(cfg: "Config") -> dict:
    """The green-arrow block as the payload carries it, thresholds included."""
    return arrow_rule(cfg.signal_rule_obj(), cfg.signal_enabled, cfg.signal_column,
                      cfg.signal_rule, "green arrow", "\u25b2", "belowBar")


def red_signal(cfg: "Config") -> dict:
    """The red-arrow block: the mirror rule, in the same keys and the same order.

    Both rules travel as one shape, so the sheet runs them through one implementation
    and a reader can compare the two field by field. The mirror shows up as data rather
    than as code: `inverted` true, both words flipped, the distance window negated with
    its ends swapped, `chgPctMinScaled` negated with `chgAbove` false, and the two run
    roles exchanged -- everything else is the green rule's own number.
    """
    return arrow_rule(cfg.red_rule_obj(), cfg.signal_red_enabled, cfg.red_column,
                      cfg.signal_red_rule, "red arrow", "\u25bc", "aboveBar")


def arrow_blocks(cfg: "Config") -> dict:
    """Both arrow rules, in the order every artifact carries them."""
    return {"signal": signal(cfg), "redSignal": red_signal(cfg)}
