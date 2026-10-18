"""
nifty.core.numeric
=============

Exact decimal arithmetic and the formatting that goes with it.

Every derived number in the pipeline is computed in integer paise with explicit
half-up rounding, never in floats. A float pipeline is not usable for these series:

  * an SMA(2) mean lands exactly on a half-paise boundary whenever the two closes
    differ by an odd number of paise, so float drift would decide the rounding;
  * a percentage change is a rational, and a decimal tie there would round one way
    in Python and the other in the browser.

Integer arithmetic makes every value reproducible across the pipeline, the sheet and
the verifier -- and the formatters below are the single place a value becomes text,
so the CSV and the JSON can never disagree about a decimal.
"""

from __future__ import annotations

PRICE_DECIMALS = 2
PCT_DECIMALS = 4


def r2(value: float) -> float:
    """Round a price to the shipped precision (2 decimals)."""
    return round(float(value) + 0.0, PRICE_DECIMALS)


def to_cents(price: float) -> int:
    """Exact integer paise. All prices in this feed carry at most 2 decimals."""
    return int(round(float(price) * 100))


def div_round_half_up(numerator: int, denominator: int) -> int:
    """round(numerator / denominator), halves away from zero, all in integers."""
    if denominator <= 0:
        raise ZeroDivisionError("denominator must be positive")
    if numerator >= 0:
        return (2 * numerator + denominator) // (2 * denominator)
    return -((-2 * numerator + denominator) // (2 * denominator))


def cents_to_price(total_cents: int, period: int) -> float:
    """Mean of `period` integer-paise prices, rounded half-up to the nearest paisa."""
    return div_round_half_up(total_cents, period) / 100.0


def pct_change(cur_cents: int, prev_cents: int, decimals: int = PCT_DECIMALS) -> float | None:
    """(cur - prev) / prev * 100, to `decimals`, half-up.

    Returns None when there is no previous value to divide by, and never divides by
    zero. The scale factor is 10**decimals so the result is an exact decimal at the
    stated precision.
    """
    if prev_cents == 0:
        return None
    scale = 100 * (10 ** decimals)
    return div_round_half_up((cur_cents - prev_cents) * scale, prev_cents) / (10 ** decimals)


# --------------------------------------------------------------------------------------
# Formatting -- one place where a number becomes text
# --------------------------------------------------------------------------------------

def fmt_price(value: float | None) -> str:
    """A price as the CSV writes it, or '' when it does not exist yet."""
    return "" if value is None else f"{value:.{PRICE_DECIMALS}f}"


def fmt_pct(value: float | None, decimals: int = PCT_DECIMALS) -> str:
    """A percentage as the CSV writes it, or '' when it does not exist yet."""
    return "" if value is None else f"{value:.{decimals}f}"


def fmt_signed(value: float | None, decimals: int) -> str:
    """A signed value ('+1.23' / '-0.50'), or '' when it does not exist yet."""
    return "" if value is None else f"{value:+.{decimals}f}"
