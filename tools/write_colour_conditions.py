"""
tools/write_colour_conditions.py
================================

Regenerate `docs/colour_conditions.md` -- the indicators this build derives and the two arrow
rules read on top of them -- from the recipe and the rule objects themselves.

    python tools/write_colour_conditions.py

Nothing here is transcription: the two condition tables come from
`Config.signal_rule_obj()` and its `mirrored()`, the thresholds in the "where to change
it" table from the resolved recipe, and the counts in the last section from the delivered
`output/nifty/data/session_summary.json`. A changed recipe therefore changes the document on
the next run, and a value that moves in the code moves here too.

The counts section is the one part that needs a build to have happened: if the summary is
absent the generator still writes the document and says so there, rather than inventing
numbers or failing the run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# run as `python tools/write_colour_conditions.py` from anywhere: the package sits one
# level up, next to build_charts.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nifty.recipe.config import Config, load_config  # noqa: E402  (after the path bootstrap)
from nifty.recipe.defaults import PROJECT_ROOT
from nifty.core.keys import (CE_OI_CHANGE, PE_OI_CHANGE, cross_distance_key, cross_key, direction_keys,
                        relation_key)
from nifty.signals.rules import GreenArrowRule

OUTPUT = PROJECT_ROOT / "docs" / "colour_conditions.md"
SUMMARY = PROJECT_ROOT / "output" / "nifty" / "data" / "session_summary.json"

# the seven conditions in the order `GreenArrowRule.tests()` returns them, and where each
# one's recipe key lives; the red table names the green key it is derived from instead
CONDITION_KEYS = ("cross_direction", "distance_pct_at_cross", "relation", "flow", "chg_pct",
                  "streak_minus", "streak_plus")

GREEN_KEYS = {
    "cross_direction": "`signal.cross_direction`",
    "distance_pct_at_cross": "`signal.distance_pct_at_cross_min` / `_max`",
    "relation": "`signal.relation`",
    "flow": "`signal.use_flow` (the pair itself is the dashboard's own columns)",
    "chg_pct": "`signal.chg_pct_min`",
    "streak_minus": "`signal.streak_minus_min` / `_max`",
    "streak_plus": "`signal.streak_plus_min`",
}

RED_DERIVED_FROM = {
    "cross_direction": "`signal.cross_direction`, flipped (ABOVE &harr; BELOW)",
    "distance_pct_at_cross": "`signal.distance_pct_at_cross_min` / `_max`, negated with "
                             "the ends swapped",
    "relation": "`signal.relation`, flipped (ABOVE &harr; BELOW)",
    "flow": "the green pair, swapped: `pe_oi_change` above `ce_oi_change` becomes "
            "`ce_oi_change` above `pe_oi_change`",
    "chg_pct": "`signal.chg_pct_min`, negated, and the comparison reversed to *below*",
    "streak_minus": "`signal.streak_minus_min` / `_max`, read from the opposite run",
    "streak_plus": "`signal.streak_plus_min`, read from the opposite run",
}

READ_ON = ("current", "current", "current", "current's minute", "previous", "previous",
           "previous")


def num(value: float) -> str:
    """A threshold the way a rule sentence writes it: `0.025`, not `0.0250`."""
    return f"{value:g}"


def code(text: str) -> str:
    return f"`{text}`"


# --------------------------------------------------------------------------------------
# The two condition tables
# --------------------------------------------------------------------------------------

def conditions(rule: GreenArrowRule) -> tuple[str, ...]:
    """The six conditions in plain words, in the rule's own direction-aware vocabulary."""
    fast_run = "rising" if rule.inverted else "falling"
    slow_run = "falling" if rule.inverted else "rising"
    other_run = "falling" if rule.inverted else "rising"
    return (
        f"the crossing row reads {code(rule.cross_direction)}",
        f"the distance (%) at that cross is {code(num(rule.distance_pct_at_cross_min))} to"
        f" {code(num(rule.distance_pct_at_cross_max))}, both ends included",
        f"the relationship row reads {code(rule.relation)}",
        f"the dashboard's minute this candle opens in reads {code(rule.flow_above)} **greater"
        f" than** {code(rule.flow_below)}",
        f"the SMA {rule.slow_period} change (%) is strictly"
        f" {'below' if rule.inverted else 'above'} {code(num(rule.chg_pct_min))}",
        f"the SMA {rule.fast_period} **{fast_run}** run is {code(rule.streak_minus_min)} to"
        f" {code(rule.streak_minus_max)}, and its {other_run} run is {code(0)}",
        f"the SMA {rule.slow_period} **{slow_run}** run is"
        f" {code(rule.streak_plus_min)} or more",
    )


def columns(rule: GreenArrowRule) -> tuple[str, ...]:
    """The column each condition reads, as the bar key it is written under."""
    return (f"{code(rule.cross_column)}",
            f"{code(rule.distance_column)}",
            f"{code(rule.relation_column)}",
            f"{code(rule.flow_above)} + {code(rule.flow_below)}",
            f"{code(rule.slow_change_column)}",
            f"{code(rule.fast_run_column)} + {code(rule.fast_run_zero_column)} = {code(0)}",
            f"{code(rule.slow_run_column)}")


def values(rule: GreenArrowRule) -> tuple[str, ...]:
    """The bound each condition compares against, as the resolved rule carries it."""
    return (code(rule.cross_direction),
            f"{code(num(rule.distance_pct_at_cross_min))} /"
            f" {code(num(rule.distance_pct_at_cross_max))}",
            code(rule.relation),
            f"{code(rule.flow_above)} > {code(rule.flow_below)}",
            code(num(rule.chg_pct_min)),
            f"{code(rule.streak_minus_min)} / {code(rule.streak_minus_max)}",
            code(rule.streak_plus_min))


def condition_table(rule: GreenArrowRule, sources: dict[str, str], source_header: str) -> str:
    """One rule's seven conditions as a table: when, which column, what, from where, bound."""
    cols, texts, bounds = columns(rule), conditions(rule), values(rule)
    rows = [(str(index + 1), READ_ON[index], cols[index], texts[index], sources[name],
             bounds[index])
            for index, name in enumerate(CONDITION_KEYS)]
    return table(("#", "Read on", "Column in the table", "Condition", source_header, "Value"),
                 rows)


def legend(rule: GreenArrowRule) -> str:
    """Which bar key each numbered condition reads, for the tally tables below."""
    reads = (code(rule.cross_column), code(rule.distance_column), code(rule.relation_column),
             f"{code(rule.flow_above)} > {code(rule.flow_below)}",
             code(rule.slow_change_column),
             f"{code(rule.fast_run_column)} (with {code(rule.fast_run_zero_column)} = 0)",
             code(rule.slow_run_column))
    return ("Legend: " + ", ".join(f"{index + 1} = {read}" for index, read in enumerate(reads))
            + ".")


def table(header: tuple[str, ...], rows) -> str:
    lines = ["| " + " | ".join(header) + " |",
             "|" + "|".join("---" for _ in header) + "|"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


# --------------------------------------------------------------------------------------
# The recipe
# --------------------------------------------------------------------------------------

def indicator_table(cfg: Config) -> str:
    above_key, below_key = direction_keys(cfg.direction_fast, cfg.direction_slow)
    periods = ", ".join(code(p) for p in cfg.analytics_periods)
    direction_pair = f"{cfg.direction_fast} / {cfg.direction_slow}"
    cross_pair = f"{cfg.cross_fast} / {cfg.cross_slow}"
    distance_pair = f"{cfg.cross_distance_from} / {cfg.cross_distance_to}"
    relation_pair = f"{cfg.relation_fast} / {cfg.relation_slow}"
    return table(("Column (bar key)", "Holds", "What it is", "Written by"), (
        (code("sma<p>"), "float or blank",
         f"the simple moving average of the bar close over `p` candles, summed in integer"
         f" paise so it is exactly reproducible; blank for the first `p - 1` candles."
         f" `<p>` is {periods}",
         code("series.add_sma")),
        (code("sma<p>_chg_pct"), "float or blank",
         f"(this candle's SMA - the previous candle's SMA) / the previous candle's SMA x 100,"
         f" rounded half-up to `analytics.pct_decimals` = {code(cfg.pct_decimals)}; blank on"
         f" a session's first candle",
         code("series.add_analytics")),
        (code("sma<p>_streak_plus"), "int",
         "the length of the unbroken run of *rising* changes of that average; `0` when the"
         " last measurable change was not rising",
         code("series.add_analytics")),
        (code("sma<p>_streak_minus"), "int",
         "the same for *falling* changes (`0` when the last one was not falling). A rise"
         " zeroes this one; a reversal starts a new run at `1`; a change of exactly zero"
         " resets both",
         code("series.add_analytics")),
        (code(above_key), "int",
         f"consecutive candles where SMA {cfg.direction_fast} > SMA {cfg.direction_slow}"
         f" **and** the SMA {cfg.direction_slow} change is positive; anything else resets"
         f" it to 0 (pair: {direction_pair})",
         code("series.add_direction_streak")),
        (code(below_key), "int",
         f"consecutive candles where SMA {cfg.direction_fast} < SMA {cfg.direction_slow}"
         f" **and** the SMA {cfg.direction_slow} change is negative",
         code("series.add_direction_streak")),
        (code(cross_key(cfg.cross_fast, cfg.cross_slow)), "`ABOVE` / `BELOW` / blank",
         f"the *strict* crossing of the pair {cross_pair}: `ABOVE` when the fast average was"
         f" below the slow one on the previous candle and is above it now, `BELOW` for the"
         f" mirror image; blank when the pair stayed on its side, when the two are equal (a"
         f" tie is never a crossing), and on a session's first candle",
         code("series.add_cross")),
        (code(cross_distance_key(cfg.cross_distance_from, cfg.cross_distance_to)),
         "float or blank",
         f"((SMA {cfg.cross_distance_from} - SMA {cfg.cross_distance_to}) /"
         f" SMA {cfg.cross_distance_to}) x 100, read **only on the candle that carries a"
         f" crossing**, at `analytics.pct_decimals`; blank when there is no crossing, when"
         f" an average is unavailable, or when the divisor is zero. Pair: {distance_pair}",
         code("series.add_cross")),
        (code(cross_distance_key(cfg.cross_fast, cfg.cross_slow)), "float or blank",
         f"the same distance measured on the crossing pair itself ({cross_pair}); carried"
         f" for reference -- **no arrow condition reads it**",
         code("series.add_cross")),
        (code(relation_key(cfg.relation_fast, cfg.relation_slow)),
         "`ABOVE` / `BELOW` / blank",
         f"which side SMA {cfg.relation_fast} sits on relative to SMA {cfg.relation_slow} on"
         f" *this* candle -- a plain comparison, not a crossing, so it holds on every candle"
         f" both averages exist; blank when they are equal or either is unavailable."
         f" Pair: {relation_pair}",
         code("series.add_relation")),
        (code(CE_OI_CHANGE), "integer or blank",
         "the session's dashboard gives one row per minute, and every bar of a minute reads"
         " that row: this is the minute's call open-interest change, copied as the feed"
         " publishes it. Blank on a session that ships no dashboard",
         code("flow.attach_flow")),
        (code(PE_OI_CHANGE), "integer or blank",
         "the same minute's put open-interest change. The green rule fires only where"
         " `pe_oi_change > ce_oi_change`, its mirror only where `ce_oi_change > pe_oi_change`",
         code("flow.attach_flow")),
        (code(cfg.signal_column), "`0` / `1`",
         "`1` exactly where all seven green conditions below hold, else `0`",
         code("rules.add_signal")),
        (code(cfg.red_column), "`0` / `1`",
         "`1` exactly where all seven red conditions below hold, else `0`",
         code("rules.add_signal")),
    ))


def derivation_table(cfg: Config, green: GreenArrowRule, red: GreenArrowRule) -> str:
    return table(("Green value", "Red value", "Transform"), (
        (f"`signal.cross_direction` = {code(green.cross_direction)}",
         code(red.cross_direction), "`flipped_word` (ABOVE &harr; BELOW)"),
        (f"`signal.relation` = {code(green.relation)}", code(red.relation), "`flipped_word`"),
        (f"the flow pair: {code(green.flow_above)} above {code(green.flow_below)}",
         f"{code(red.flow_above)} above {code(red.flow_below)}",
         "the two sides swapped -- this comparison mirrors by exchanging its operands"),
        (f"`distance_pct_at_cross_min` = {code(num(green.distance_pct_at_cross_min))}",
         code(num(red.distance_pct_at_cross_min)), "the green **max**, negated"),
        (f"`distance_pct_at_cross_max` = {code(num(green.distance_pct_at_cross_max))}",
         code(num(red.distance_pct_at_cross_max)),
         "the green **min**, negated; a negated `0.0` is folded back to `0.0`, so no rule"
         " sentence and no payload carries a `-0`"),
        (f"`chg_pct_min` = {code(num(green.chg_pct_min))}", code(num(red.chg_pct_min)),
         "negated, and `>` becomes `<`: strictly above the threshold becomes strictly below"
         " its negative"),
        (f"`streak_minus_min` / `_max` = {code(green.streak_minus_min)} /"
         f" {code(green.streak_minus_max)}",
         f"{code(red.streak_minus_min)} / {code(red.streak_minus_max)}",
         f"unchanged; the red rule reads that window off {code(red.fast_run_column)} instead"
         f" of {code(green.fast_run_column)}"),
        (f"`streak_plus_min` = {code(green.streak_plus_min)}", code(red.streak_plus_min),
         f"unchanged; read off {code(red.slow_run_column)} instead of"
         f" {code(green.slow_run_column)}"),
        (f"`red_arrow` = {code(str(cfg.signal_red_enabled).lower())}", "--",
         "a switch, not a threshold"),
    ))


def settings_table(cfg: Config, green: GreenArrowRule) -> str:
    on, red_on = str(cfg.signal_enabled).lower(), str(cfg.signal_red_enabled).lower()
    return table(("Recipe key", "Now", "What changing it does"), (
        ("`signal.enabled`", code(on),
         "whether the green arrow is drawn at all; the column stays, carrying `0`"),
        ("`signal.cross_direction`", code(green.cross_direction),
         "the word condition 1 must read"),
        ("`signal.relation`", code(green.relation), "the word condition 3 must read"),
        ("`signal.distance_pct_at_cross_min` / `_max`",
         f"{code(num(green.distance_pct_at_cross_min))} /"
         f" {code(num(green.distance_pct_at_cross_max))}",
         "the window condition 2 must fall inside, both ends included"),
        ("`signal.chg_pct_min`", code(num(green.chg_pct_min)),
         "the threshold condition 4 is compared strictly against"),
        ("`signal.streak_minus_min` / `_max`",
         f"{code(green.streak_minus_min)} / {code(green.streak_minus_max)}",
         "the window condition 5 must fall inside"),
        ("`signal.streak_plus_min`", code(green.streak_plus_min),
         "how long the run condition 6 demands"),
        ("`signal.red_arrow`", code(red_on),
         "whether the mirror is drawn; the thresholds it reads are the green ones either way"),
        ("`signal.fast_period` / `slow_period`",
         f"{code(green.fast_period)} / {code(green.slow_period)}",
         "the pair whose runs and change the previous candle contributes; left unset they"
         " are taken from `[relation]`"),
        ("`cross.fast_period` / `slow_period`", f"{code(cfg.cross_fast)} / {code(cfg.cross_slow)}",
         "the crossing pair condition 1 reads"),
        ("`cross.distance_from_period` / `distance_to_period`",
         f"{code(cfg.cross_distance_from)} / {code(cfg.cross_distance_to)}",
         "the pair behind the distance column condition 2 reads"),
        ("`relation.fast_period` / `slow_period`",
         f"{code(cfg.relation_fast)} / {code(cfg.relation_slow)}",
         "the pair behind the relationship row condition 3 reads"),
        ("`analytics.periods`", ", ".join(code(p) for p in cfg.analytics_periods),
         "which averages exist to be read; every period a rule names must be among them"),
        ("`analytics.pct_decimals`", code(cfg.pct_decimals),
         "the precision every percentage is *compared* at: the bounds become scaled"
         " integers, so a value sitting exactly on one falls on the side the operator says"),
        ("`signal.rule` / `red_rule`", "written from the values above",
         "override the two sentences only, never a threshold"),
    ))


# --------------------------------------------------------------------------------------
# The delivered counts
# --------------------------------------------------------------------------------------

def counts_section(cfg: Config, green: GreenArrowRule, red: GreenArrowRule) -> str:
    """The arrows fired and the per-condition tallies, read from the delivered summary."""
    if not SUMMARY.is_file():
        return ("_No `output/nifty/data/session_summary.json` here, so this section is empty: run"
                " `python build_charts.py` and generate the document again._")

    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    days = summary["days"]
    labels = {str(seconds): None for seconds in cfg.timeframes}

    arrows = []
    for date in sorted(days):
        for seconds in cfg.timeframes:
            entry = days[date]["timeframes"][str(seconds)]
            labels[str(seconds)] = entry["label"]
            arrows.append((date, entry["label"], str(entry["bars"]),
                           str(entry["signal"]["arrows"]), str(entry["redSignal"]["arrows"])))

    latest = sorted(days)[-1]
    entries = days[latest]["timeframes"]

    def tally(block: str) -> str:
        rows = []
        for seconds in cfg.timeframes:
            entry = entries[str(seconds)]
            counts = entry[block]["perCondition"]
            rows.append((entry["label"], str(entry["bars"]),
                         *(str(counts[name]) for name in CONDITION_KEYS),
                         str(entry[block]["arrows"])))
        return table(("Timeframe", "Bars", "1 cross", "2 distance", "3 relation", "4 chg",
                      "5 fast run", "6 slow run", "Arrows"), rows)

    # the narrowest and widest condition by total candles held, over this session's charts
    def extremes(block: str) -> tuple[str, str]:
        totals = {name: sum(entries[str(s)][block]["perCondition"][name]
                            for s in cfg.timeframes) for name in CONDITION_KEYS}

        def describe(name: str) -> str:
            return f"{CONDITION_KEYS.index(name) + 1} ({code(name)}, {totals[name]}"

        narrowest = min(totals, key=lambda name: totals[name])
        widest = max(totals, key=lambda name: totals[name])
        return describe(narrowest), describe(widest)

    green_narrow, green_wide = extremes("signal")
    red_narrow, red_wide = extremes("redSignal")

    return (
        table(("Session", "Timeframe", "Bars", "Green arrows", "Red arrows"), arrows)
        + f"\n\nFor the latest session ({latest}), with each condition numbered as in its"
        + " table above:\n\n"
        + f"**Green.** {legend(green)}\n\n" + tally("signal")
        + f"\n\n**Red.** {legend(red)}\n\n" + tally("redSignal")
        + f"\n\nAcross this session's {len(cfg.timeframes)} charts, counted over every"
        + f" candle, the narrowest green condition is {green_narrow} candles held) and the"
        + f" widest is {green_wide} candles held); for the red rule the same pair is"
        + f" {red_narrow} candles held) against {red_wide} candles held). That spread is why"
        + " the funnels are here: the condition holding on a handful of candles is what"
        + " actually narrows an arrow, and the one holding on more than a"
        + " thousand is doing almost no filtering at all."
    )


# --------------------------------------------------------------------------------------
# The document
# --------------------------------------------------------------------------------------

def document(cfg: Config) -> str:
    green, red = cfg.signal_rule_obj(), cfg.red_rule_obj()
    enabled, red_enabled = str(cfg.signal_enabled).lower(), str(cfg.signal_red_enabled).lower()
    shared = ", ".join(code(name) for name in green.read_columns)
    # the recipe as a reader knows it: relative to the project, not an absolute path
    source = code(cfg.source_path(Path(cfg.source))) if cfg.source else "the built-in defaults"

    return f"""# Colour conditions

The indicators this build derives, and the two arrow rules read on top of them.

Every value below is the **resolved recipe** -- read from the recipe
`python build_charts.py` builds with when it is given no `--config` ({source}) -- through
the very rule objects the build runs. Nothing here is transcribed by hand: this document is
generated by [{code('tools/write_colour_conditions.py')}](../tools/write_colour_conditions.py),
so re-run it after a change and the tables follow the recipe.

* the indicators are the columns written by the steps in `nifty/data/analysis.py`, defined in
  `nifty/signals/series.py`;
* the two arrows are one rule in `nifty/signals/rules.py` read two ways round: the recipe declares
  the green one, and the red one is its `mirrored()` -- derived, never restated;
* the build itself states the same seven conditions for both rules when it runs, so it is the
  live cross-check for this file.

Condition 4 of each rule is the session's own dashboard: the feed's `ce_oi_change` and
`pe_oi_change` for the minute the candle opens in, joined onto the bar by `nifty/data/flow.py`.
A session that ships no dashboard has no such reading, and that one condition is then not
read rather than read as a zero.

## 1. The indicators

Nothing in this table decides anything. The rows are descriptive: they say where two
averages swapped sides, which side they sit on, how long a run is, and how far apart they
were when they crossed. The only thing that decides is the arrow rule in section 2 and its
mirror in section 3, and it reads these columns rather than adding a series of its own.

{indicator_table(cfg)}

**The candle's own body** is not a column. `series.bar_color` reads a bar's `open` and
`close` in exact integer paise and returns `green` (close above open), `red` (below) or
`doji` (equal -- a tie, so it belongs to neither colour); the summary's green / red / doji
counts come from there and nowhere else.

**How a run is counted** -- both `sma<p>_streak_plus` and `_streak_minus`, and the pairing
of the two arrow conditions that read them, are kept under `analytics.run_rule`, quoted
from the recipe:

> {cfg.run_rule}

## 2. Green arrow

**Six conditions, all of them required (AND).** The first three are read from the candle
itself, the last three from the candle before it. A blank column is never a hit, and a
session's first candle can never fire because there is no previous candle to read.

{condition_table(green, GREEN_KEYS, "Recipe key")}

In the recipe's own words:

> {cfg.signal_rule}

The flag ships as {code(cfg.signal_column)} -- `1` on the candles that fire, `0` on every
other -- and the arrow is drawn **below** the bar on the price pane of every timeframe.
`signal.enabled` is {code(enabled)}.

## 3. Red arrow

**The same six conditions, read the other way round.** Every word is flipped, the distance
window is negated with its ends swapped, the change threshold is negated and its
comparison reversed, and each run is read from the other run's column. The mirror is built
by transform rather than restated, so there is no second set of numbers to keep in step:

{condition_table(red, RED_DERIVED_FROM, "Comes from (green)")}

In the recipe's own words:

> {cfg.signal_red_rule}

The flag ships as {code(cfg.red_column)} and the arrow is drawn **above** the bar.
`signal.red_arrow` is {code(red_enabled)} -- a switch, not a threshold: `false` keeps the
column, always `0`, and draws no mark. There is no red threshold in the recipe to edit, and
a key that names one is refused rather than ignored.

## 4. How the red rule is derived, key by key

{derivation_table(cfg, green, red)}

Both rules read the same set of columns -- {shared} -- which is what lets their
per-condition tallies be read side by side under one set of names.

## 5. Where to change any of it

All of these live in [config/nifty.json](config/nifty.json) (the same keys exist in
[config/nifty.toml](config/nifty.toml)), and `--set section.key=value` overrides one for a
single run. A key left out keeps its built-in default, so a short recipe is a valid recipe.

{settings_table(cfg, green)}

## 6. What the delivered build saw

The counts below are the delivered artifacts' data
([output/nifty/data/session_summary.json](output/nifty/data/session_summary.json)): arrows fired per
session and timeframe, then each condition's own tally. A per-condition count is **not**
cumulative -- it says how many candles satisfied that condition on its own, which is what
makes the funnel show a narrow condition next to a wide one instead of hiding five of them
behind the sixth.

{counts_section(cfg, green, red)}

## 7. What the rules guarantee

* **No future bar is read.** The three conditions on the current candle read that candle
  only, and the three on the previous candle read the one before it. Nothing later.
* **A session starts clean.** A session's bars begin at its own first candle, so no
  crossing, run or arrow is ever carried across a session boundary.
* **A blank column is not a hit.** An unavailable average, a missing previous candle or a
  zero divisor produces a blank, and a blank never satisfies a condition -- it is not read
  as a zero worth counting.
* **One definition, two rules.** Both arrows run through one `GreenArrowRule.hits`, and the
  per-condition funnel and the rule sentences are generated from that same object, so the
  tallies, the sentences and the arrows cannot describe different rules.
* **Every arrow marks a candle that has already closed.**
"""


def main() -> int:
    cfg = load_config(None, [])
    # newline="\n" pinned: the document is regenerated, so its bytes must not depend on
    # the machine that ran the generator (Windows would otherwise write CRLF)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(document(cfg), encoding="utf-8", newline="\n")
    print(f"wrote {cfg.source_path(OUTPUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
