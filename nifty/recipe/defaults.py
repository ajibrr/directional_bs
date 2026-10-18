"""
nifty.recipe.defaults
==============

The built-in recipe: every value a build falls back to when `config/nifty.toml` and the
command line say nothing, plus the two maps that make the file checkable.

    SECTIONS   the tables a recipe may carry
    DEFAULTS   the keys each table may carry, with their default value

`nifty.recipe.config` reads a recipe file on top of these and validates the result, so those two
maps are what turn a typo in the file into an error that names the section and the key
instead of a silently ignored line. The code holds only these defaults; every parameter a
delivered artifact was built with is the recipe's, never a constant here.

The recipe ships in two interchangeable forms -- `config/nifty.json`, which the build
reads when no `--config` is given, and `config/nifty.toml`, the same values with TOML's
comment syntax. Either may be passed to `--config`, and the audit asserts both resolve to
the same `Config`, field for field, so the pair cannot drift apart.

`RUN_RULE` is the one default that is prose: the sentence that says what a consecutive
run means, printed in the summary and quoted in the recipe so a reader can see the rule
the counts were made under.
"""

from __future__ import annotations

from pathlib import Path

from ..core.keys import ABOVE

PROJECT_ROOT = Path(__file__).resolve().parents[2]   # nifty/recipe/defaults.py -> project root

# the recipe a build reads when it is given none, and the same recipe in TOML: both are
# loadable, both are audited, and neither may drift away from the other
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "nifty.json"
MIRROR_CONFIG_PATH = PROJECT_ROOT / "config" / "nifty.toml"

RUN_RULE = ("consecutive: a rise extends the rising run and zeroes the falling one "
            "(and vice versa); a reversal starts a new run at 1; a zero change zeroes both")

INSTRUMENT_DEFAULT = "NIFTY 50"
TIMEFRAMES_DEFAULT = (12, 36, 60, 180, 300)
PRICE_PERIODS_DEFAULT = (2, 9, 44)
ANALYTICS_PERIODS_DEFAULT = (2, 9, 44)
PCT_DECIMALS_DEFAULT = 4
DIRECTION_FAST_DEFAULT = 2
DIRECTION_SLOW_DEFAULT = 9
CROSS_FAST_DEFAULT = 2
CROSS_SLOW_DEFAULT = 9
CROSS_DISTANCE_FROM_DEFAULT = 9
CROSS_DISTANCE_TO_DEFAULT = 44
RELATION_FAST_DEFAULT = 9
RELATION_SLOW_DEFAULT = 44
SIGNAL_ENABLED_DEFAULT = True
SIGNAL_CROSS_DIRECTION_DEFAULT = ABOVE
SIGNAL_RELATION_DEFAULT = ABOVE
SIGNAL_DISTANCE_PCT_AT_CROSS_MIN_DEFAULT = 0.0
SIGNAL_DISTANCE_PCT_AT_CROSS_MAX_DEFAULT = 0.025
SIGNAL_CHG_PCT_MIN_DEFAULT = 0.0005
SIGNAL_STREAK_MINUS_MIN_DEFAULT = 7
SIGNAL_STREAK_MINUS_MAX_DEFAULT = 15
SIGNAL_STREAK_PLUS_MIN_DEFAULT = 7
SIGNAL_RED_DEFAULT = True
# the trade clock: no arrow after this is taken, and any position still open at the hard-exit
# time is closed at that moment's price whatever it is showing
BACKTEST_LAST_ENTRY_DEFAULT = "15:10:00"
BACKTEST_HARD_EXIT_DEFAULT = "15:15:00"
SHEET_NAME_DEFAULT = "NIFTY_{range_slug}_SMA_sheet.html"
SHEET_TITLE_DEFAULT = "{instrument} \u00b7 {range_label} \u00b7 SMA {sma_slash} analytics"
SHEET_WINDOW_BARS_DEFAULT = 100

SECTIONS = ("instrument", "paths", "timeframes", "sma", "analytics", "direction_streak",
            "cross", "relation", "signal", "red_signal", "backtest", "sheet")

DEFAULTS: dict[str, dict[str, object]] = {
    "instrument": {
        "name": INSTRUMENT_DEFAULT,
    },
    "paths": {
        "sources_dir": "input data",
        "sources_glob": "NIFTY_*_PRICE_1SEC.jsonl",
        "template": "templates/sheet.html",
        "chart_lib": "vendor/lightweight-charts.standalone.production.js",
        "output_dir": "output/nifty",
    },
    "timeframes": {
        "seconds": list(TIMEFRAMES_DEFAULT),
    },
    "sma": {
        "price_periods": list(PRICE_PERIODS_DEFAULT),
    },
    "analytics": {
        "periods": list(ANALYTICS_PERIODS_DEFAULT),
        "pct_decimals": PCT_DECIMALS_DEFAULT,
        "run_rule": RUN_RULE,
    },
    "direction_streak": {
        "fast_period": DIRECTION_FAST_DEFAULT,
        "slow_period": DIRECTION_SLOW_DEFAULT,
        # None = the sentence is written from the two periods, see nifty.recipe.config._build
        "rule": None,
    },
    "cross": {
        "fast_period": CROSS_FAST_DEFAULT,
        "slow_period": CROSS_SLOW_DEFAULT,
        "distance_from_period": CROSS_DISTANCE_FROM_DEFAULT,
        "distance_to_period": CROSS_DISTANCE_TO_DEFAULT,
        # None = both sentences are written from the periods above, see nifty.recipe.config._build
        "rule": None,
        "distance_rule": None,
    },
    "relation": {
        "fast_period": RELATION_FAST_DEFAULT,
        "slow_period": RELATION_SLOW_DEFAULT,
        # None = the sentence is written from the two periods, see nifty.recipe.config._build
        "rule": None,
    },
    "signal": {
        "enabled": SIGNAL_ENABLED_DEFAULT,
        "cross_direction": SIGNAL_CROSS_DIRECTION_DEFAULT,
        "relation": SIGNAL_RELATION_DEFAULT,
        "distance_pct_at_cross_min": SIGNAL_DISTANCE_PCT_AT_CROSS_MIN_DEFAULT,
        "distance_pct_at_cross_max": SIGNAL_DISTANCE_PCT_AT_CROSS_MAX_DEFAULT,
        "chg_pct_min": SIGNAL_CHG_PCT_MIN_DEFAULT,
        "streak_minus_min": SIGNAL_STREAK_MINUS_MIN_DEFAULT,
        "streak_minus_max": SIGNAL_STREAK_MINUS_MAX_DEFAULT,
        "streak_plus_min": SIGNAL_STREAK_PLUS_MIN_DEFAULT,
        # boolean flags: true = condition is checked, false = condition is skipped
        "use_cross_direction": True,
        "use_distance_pct": True,
        "use_relation": True,
        # the flow condition reads the session's own dashboard (ce_oi_change against
        # pe_oi_change); a session with no dashboard does not read the condition
        "use_flow": True,
        "use_chg_pct": True,
        "use_streak_minus": True,
        "use_streak_plus": True,
        # the red arrow: the green rule's exact mirror, so there is nothing to configure
        # but whether it is drawn; false keeps the column, always 0, and drops the marks
        "red_arrow": SIGNAL_RED_DEFAULT,
        # None = the pair whose runs and change the previous candle contributes, taken
        # from [relation]; the crossing and distance rows are [cross] by definition
        "fast_period": None,
        "slow_period": None,
        # None = the sentence is written from the periods and thresholds, see nifty.recipe.config._build
        "rule": None,
        # None = the red sentence is written from the mirrored rule, see nifty.recipe.config._build
        "red_rule": None,
    },
    "red_signal": {
        "enabled": True,
        "cross_direction": "ABOVE",
        "relation": "ABOVE",
        "distance_pct_at_cross_min": 0.0,
        "distance_pct_at_cross_max": 0.025,
        "chg_pct_min": 0.0005,
        "streak_minus_min": 7,
        "streak_minus_max": 15,
        "streak_plus_min": 7,
        # boolean flags: true = condition is checked, false = condition is skipped
        "use_cross_direction": True,
        "use_distance_pct": True,
        "use_relation": True,
        "use_flow": True,
        "use_chg_pct": True,
        "use_streak_minus": True,
        "use_streak_plus": True,
        "red_arrow": True,
    },
    "backtest": {
        # IST wall clock, 'HH:MM:SS'. An arrow whose candle opens after last_entry is not
        # taken at all; a position still open when the clock reaches hard_exit is closed
        # there, at that bar's opening price, whatever its profit or loss.
        "last_entry": BACKTEST_LAST_ENTRY_DEFAULT,
        "hard_exit": BACKTEST_HARD_EXIT_DEFAULT,
    },
    "sheet": {
        "name_template": SHEET_NAME_DEFAULT,
        "title_template": SHEET_TITLE_DEFAULT,
        "window_bars": SHEET_WINDOW_BARS_DEFAULT,
    },
}
