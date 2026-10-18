"""
nifty.core.keys
==========

The column vocabulary. Every derived column this pipeline writes is named here and
nowhere else, so the writers, the summaries, the verifier and the sheet all speak one
language:

    sma<period>                                   the price averages
    sma<period>_chg_pct                           percentage change vs the previous candle
    sma<period>_streak_plus / _streak_minus       the consecutive runs of moves
    sma<fast>_vs_sma<slow>_above_streak           the direction streak, one pair
    sma<fast>_vs_sma<slow>_below_streak
    sma<fast>_vs_sma<slow>_cross_direction        the strict crossing, one pair
    sma<from>_vs_sma<to>_distance_pct_at_cross    the signed distance read at a crossing
    sma<fast>_vs_sma<slow>_relation               which side of each other two sit on
    green_arrow / red_arrow                       the two arrow flags
    ce_oi_change / pe_oi_change                   the dashboard's minute change, per candle

Two words travel with those names -- `ABOVE` and `BELOW` -- and the only thing ever done
to a word is to flip it (`flipped_word`), because a rule's mirror is exactly its
comparisons read the other way round. The threshold helpers here (`scaled`, `negated`)
are the same idea for numbers: a percentage becomes the integer the comparison is
actually made in, and a mirrored bound is its negation with a negative zero folded back
to 0.0.

`count_label` and `count_label_ascii` are the other shared spelling: how a pair of run
tallies is written, once for the table (U+2212) and once for a cp1252 console (a plain
hyphen). Both live here because a label that differs between the artifact and the console
report is the kind of drift this module exists to prevent.
"""

from __future__ import annotations

from .errors import ConfigError
from .numeric import PCT_DECIMALS

PLUS_SUFFIX = "_streak_plus"
MINUS_SUFFIX = "_streak_minus"
CROSS_SUFFIX = "_cross_direction"
CROSS_DISTANCE_SUFFIX = "_distance_pct_at_cross"
RELATION_SUFFIX = "_relation"

SIGNAL_KEY = "green_arrow"
RED_KEY = "red_arrow"

# The dashboard's two per-minute columns. They are an input like `atm` and `ticks` rather
# than a derived series: each bar carries the minute it opens in, and the flow condition
# of both arrow rules compares the pair. A session with no dashboard carries None here,
# which is how the condition knows not to be read at all.
CE_OI_CHANGE = "ce_oi_change"
PE_OI_CHANGE = "pe_oi_change"
FLOW_KEYS = (CE_OI_CHANGE, PE_OI_CHANGE)

ABOVE = "ABOVE"
BELOW = "BELOW"


# --------------------------------------------------------------------------------------
# Key naming
# --------------------------------------------------------------------------------------

def sma_key(period: int) -> str:
    return f"sma{period}"


def analytics_keys(period: int) -> tuple[str, str, str]:
    """(change, rising run, falling run) for one period, in export order."""
    return (f"sma{period}_chg_pct", f"sma{period}{PLUS_SUFFIX}", f"sma{period}{MINUS_SUFFIX}")


def direction_keys(fast: int, slow: int) -> tuple[str, str]:
    """(above run, below run) for one pair of averages."""
    return (f"sma{fast}_vs_sma{slow}_above_streak", f"sma{fast}_vs_sma{slow}_below_streak")


def cross_key(fast: int, slow: int) -> str:
    """The crossing column for one pair of averages."""
    return f"sma{fast}_vs_sma{slow}{CROSS_SUFFIX}"


def cross_distance_key(from_period: int, to_period: int) -> str:
    """The signed distance (%) column for one pair of averages, read at a crossing."""
    return f"sma{from_period}_vs_sma{to_period}{CROSS_DISTANCE_SUFFIX}"


def relation_key(fast: int, slow: int) -> str:
    """The side-relationship column for one pair of averages: one word per candle."""
    return f"sma{fast}_vs_sma{slow}{RELATION_SUFFIX}"


def signal_key() -> str:
    """The green-arrow column: 1 on the candles the rule fires on, 0 on every other."""
    return SIGNAL_KEY


def red_key() -> str:
    """The red-arrow column: the mirror rule's flag, the same 1 / 0 shape."""
    return RED_KEY


# --------------------------------------------------------------------------------------
# The two words, and the numbers a rule reads them against
# --------------------------------------------------------------------------------------

def flipped_word(word: str) -> str:
    """ABOVE <-> BELOW: the whole of what a mirrored rule does to a word.

    Every word either rule compares is one of these two, so flipping one cannot leave a
    second spelling to keep in step. Anything else is a recipe that should never have
    reached a rule -- `ConfigError` rather than a silent non-match.
    """
    if word == ABOVE:
        return BELOW
    if word == BELOW:
        return ABOVE
    raise ConfigError(f"{word!r} is neither {ABOVE} nor {BELOW}")


def scaled(value: float, decimals: int = PCT_DECIMALS) -> int:
    """A configured threshold as the integer the sheet's own precision compares in.

    Every percentage in this package is an exact decimal at `decimals` places, so the
    bounds are compared as scaled integers rather than floats: `0.025` and
    `0.025000000000000001` are then the same number, and a value sitting exactly on a
    bound falls on the side the operator says it does.
    """
    return int(round(value * 10 ** decimals))


def negated(value: float) -> float:
    """`-value`, with a negative zero folded back to 0.0. The mirror of 0.0 is 0.0, and
    `-0.0` would otherwise reach the rule sentence and the payload as '-0'."""
    return 0.0 if value == 0 else -value


# --------------------------------------------------------------------------------------
# Display
# --------------------------------------------------------------------------------------

def count_label(plus: int, minus: int) -> str:
    """The table's display form: '+10 / -5' (U+2212 for the negative half)."""
    return f"+{plus} / \u2212{minus}"


def count_label_ascii(plus: int, minus: int) -> str:
    """Same tallies with a plain hyphen, so console output survives a cp1252 stdout."""
    return f"+{plus}/-{minus}"
