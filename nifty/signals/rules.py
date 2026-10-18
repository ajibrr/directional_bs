"""
nifty.signals.rules
===========

The two arrow rules -- and, deliberately, only two.

One rule, seven conditions, all of them required (AND). Four are read from the candle
itself, three from the candle before it:

    current   the cross direction column reads the configured word (ABOVE / BELOW)
    current   the distance (%) carried at that cross is inside the configured window,
              both ends included
    current   the above/below relationship column reads the configured word
    current   the dashboard's per-minute flow: one of the two OI-change columns is the
              greater one on the minute this candle opens in (the green rule reads PE
              above CE, its mirror the other way round). A session with no dashboard does
              not read this condition at all, rather than reading it as a zero
    previous  the slow average's change (%) is strictly above/below its threshold
    previous  the fast average's consecutive count is a run of the rule's own direction
              inside its window, while the opposite run is zero (a run is one or the other)
    previous  the slow average's consecutive count is a run of the other direction at
              least that long

The recipe declares ONE of them -- the green one -- and the red rule is `mirrored()`:
every word flipped, the distance window negated and its ends swapped, the change threshold
negated with its comparison reversed, and each run read from the other run's column. A
price inversion turns a green candle into a red one, so the mirror is what "the opposite
condition" means here, and building it by transform rather than by restatement is what
keeps the two in step: there is no second set of numbers to drift.

Neither rule adds a series of its own: the price values they read off the table were
written by the steps in `nifty.signals.series`, and the two flow columns were joined onto the bars
from the session's dashboard (`nifty.data.flow`), which is why those columns are declared
rather than assumed. A candle can only fire if the column it reads exists and is not None,
and the first candle of a session has no previous candle to read, so a session never
inherits the previous session's state.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from ..core.keys import (CE_OI_CHANGE, PE_OI_CHANGE, analytics_keys, cross_distance_key, cross_key,
                   flipped_word, negated, relation_key, scaled)
from ..core.numeric import PCT_DECIMALS


def _always_true(bar: dict, prev: dict | None) -> bool:
    """A condition that is disabled: always passes regardless of the data."""
    return True


@dataclass(frozen=True)
class GreenArrowRule:
    """One arrow rule: which columns to read, and the thresholds that decide a hit.

    The periods are named rather than inferred, so the rule reads exactly the rows the
    recipe names -- the crossing row, its distance, and the above/below pair whose runs
    and change the previous candle contributes. One instance is a direction: the recipe's
    own values are the green rule (a crossing ABOVE, candles whose averages sit ABOVE, a
    rising slow average), and `mirrored()` returns the red one -- every comparison read the
    other way round, with no threshold restated.
    """

    cross_fast: int                      # the crossing pair whose direction is read
    cross_slow: int
    distance_from: int                   # the averages behind the distance column
    distance_to: int
    fast_period: int                     # the pair whose runs and change are read
    slow_period: int
    cross_direction: str                 # the word the cross direction column must read
    relation: str                        # the word the relationship column must read
    distance_pct_at_cross_min: float     # inclusive, in percent
    distance_pct_at_cross_max: float     # inclusive, in percent
    chg_pct_min: float                   # the slow change (%) must be strictly above this
    streak_minus_min: int                # the fast FALLING run, inclusive window
    streak_minus_max: int
    streak_plus_min: int                 # the slow run of the rule's direction, at least
                                         # this long
    # the dashboard's per-minute pair, read on the candle's own minute: this rule fires
    # when `flow_above` is the greater of the two, its mirror when `flow_below` is. The
    # names are swapped by `mirrored()` like the two words, so the mirror of the flow
    # comparison is built the same way the mirror of every other comparison is.
    flow_above: str = PE_OI_CHANGE
    flow_below: str = CE_OI_CHANGE
    # boolean flags: true = condition is checked, false = condition is skipped (always passes)
    use_cross_direction: bool = True
    use_distance_pct: bool = True
    use_relation: bool = True
    use_flow: bool = True
    use_chg_pct: bool = True
    use_streak_minus: bool = True
    use_streak_plus: bool = True
    decimals: int = PCT_DECIMALS
    inverted: bool = False               # the mirror: every comparison read the other way

    # ---- the columns the rule reads ------------------------------------------------
    @property
    def cross_column(self) -> str:
        return cross_key(self.cross_fast, self.cross_slow)

    @property
    def distance_column(self) -> str:
        return cross_distance_key(self.distance_from, self.distance_to)

    @property
    def relation_column(self) -> str:
        return relation_key(self.fast_period, self.slow_period)

    @property
    def slow_change_column(self) -> str:
        return analytics_keys(self.slow_period)[0]

    @property
    def fast_run_plus_column(self) -> str:
        return analytics_keys(self.fast_period)[1]

    @property
    def fast_run_minus_column(self) -> str:
        return analytics_keys(self.fast_period)[2]

    @property
    def slow_run_plus_column(self) -> str:
        return analytics_keys(self.slow_period)[1]

    @property
    def slow_run_minus_column(self) -> str:
        return analytics_keys(self.slow_period)[2]

    @property
    def fast_run_column(self) -> str:
        """The previous candle's fast run this rule reads: the FALLING one when green,
        the RISING one when mirrored -- a run is always one direction or the other."""
        return self.fast_run_plus_column if self.inverted else self.fast_run_minus_column

    @property
    def fast_run_zero_column(self) -> str:
        """The fast run that must be zero for a hit: the other direction's count, since a
        candle in a falling run carries no rising run and vice versa."""
        return self.fast_run_minus_column if self.inverted else self.fast_run_plus_column

    @property
    def slow_run_column(self) -> str:
        """The slow average's run this rule reads: RISING when green, FALLING when
        mirrored."""
        return self.slow_run_minus_column if self.inverted else self.slow_run_plus_column

    @property
    def read_columns(self) -> tuple[str, ...]:
        """The analytics columns a hit is decided from, in the order they are read.

        Both runs' columns are declared whichever direction the rule reads: the one it
        counts and the one it requires to be zero are the same two columns either way, so
        a mirrored rule reads exactly the set its original did.
        """
        return (self.cross_column, self.distance_column, self.relation_column,
                self.slow_change_column, self.fast_run_plus_column,
                self.fast_run_minus_column, self.slow_run_plus_column)

    @property
    def flow_columns(self) -> tuple[str, ...]:
        """The two dashboard columns the flow condition compares, in the order it reads
        them: the one that must be the greater, then the other. The price columns above are
        written by `nifty.signals.series`; these two are joined on from the session's dashboard, so
        they are declared separately rather than mixed into that tuple."""
        return (self.flow_above, self.flow_below)

    # ---- the mirror ----------------------------------------------------------------
    def mirrored(self) -> "GreenArrowRule":
        """The exact inverse of this rule: every comparison read the other way around.

        A price inversion (P -> -P) turns a crossing ABOVE into one BELOW, a positive
        distance into its negative, a rising run into a falling one of the same length,
        the side relationship inside out, and a change above the threshold into one below
        it. The mirror is that transform applied to the rule itself -- the words flipped,
        the distance window negated with its ends swapped, the change threshold negated --
        and `inverted` remembers which way round the comparison is made. Nothing is
        retyped, so no threshold can drift away from the rule it inverts, and the two rules
        read the same columns by construction.
        """
        return replace(
            self,
            cross_direction=flipped_word(self.cross_direction),
            relation=flipped_word(self.relation),
            # the flow comparison is the one condition whose mirror is a swap rather than
            # a negation: "PE is the larger" read the other way round is "CE is the larger"
            flow_above=self.flow_below,
            flow_below=self.flow_above,
            distance_pct_at_cross_min=negated(self.distance_pct_at_cross_max),
            distance_pct_at_cross_max=negated(self.distance_pct_at_cross_min),
            chg_pct_min=negated(self.chg_pct_min),
            inverted=not self.inverted,
        )

    # ---- the conditions ------------------------------------------------------------
    def scaled_bounds(self) -> tuple[int, int, int]:
        """(distance_pct_at_cross_min, distance_pct_at_cross_max, chg_pct_min) as integers."""
        return (scaled(self.distance_pct_at_cross_min, self.decimals),
                scaled(self.distance_pct_at_cross_max, self.decimals),
                scaled(self.chg_pct_min, self.decimals))

    def tests(self) -> tuple[tuple[str, str, Callable[[dict, dict | None], bool]], ...]:
        """The seven conditions as (key, description, test), in the order they are read.

        One definition drives both the column and the per-condition funnel the summary
        reports, so the tally can never describe a rule the arrows were not built from.
        """
        # the locals carry the field names so a threshold is spelled the same way in
        # the recipe, the field, the payload and here
        (distance_pct_at_cross_min, distance_pct_at_cross_max,
         chg_pct_min) = self.scaled_bounds()

        def cross_ok(bar: dict, prev: dict | None) -> bool:
            return bar[self.cross_column] == self.cross_direction

        def distance_ok(bar: dict, prev: dict | None) -> bool:
            value = bar[self.distance_column]
            return (value is not None
                    and distance_pct_at_cross_min <= scaled(value, self.decimals)
                    <= distance_pct_at_cross_max)

        def relation_ok(bar: dict, prev: dict | None) -> bool:
            return bar[self.relation_column] == self.relation

        def flow_ok(bar: dict, prev: dict | None) -> bool:
            above = bar.get(self.flow_above)
            below = bar.get(self.flow_below)
            if above is None or below is None:
                # no dashboard for this session, or no row for the minute this candle opens
                # in: the condition is not read, so it cannot refuse the candle
                return True
            return above > below

        def change_ok(bar: dict, prev: dict | None) -> bool:
            if prev is None:
                return False
            value = prev[self.slow_change_column]
            if value is None:
                return False
            # green: strictly above the threshold; mirrored: strictly below it
            return (scaled(value, self.decimals) < chg_pct_min if self.inverted
                    else scaled(value, self.decimals) > chg_pct_min)

        def fast_run_ok(bar: dict, prev: dict | None) -> bool:
            if prev is None or prev[self.fast_run_zero_column]:
                return False
            return (self.streak_minus_min <= prev[self.fast_run_column]
                    <= self.streak_minus_max)

        def slow_run_ok(bar: dict, prev: dict | None) -> bool:
            return (prev is not None
                    and prev[self.slow_run_column] >= self.streak_plus_min)

        return (("cross_direction", f"current candle: {self.cross_column} reads"
                                     f" {self.cross_direction}",
                cross_ok if self.use_cross_direction else _always_true),
                ("distance_pct_at_cross", f"current candle: {self.distance_column} is"
                                          f" {self.distance_pct_at_cross_min:g}"
                                          f" to {self.distance_pct_at_cross_max:g} inclusive",
                distance_ok if self.use_distance_pct else _always_true),
                ("relation", f"current candle: {self.relation_column} reads {self.relation}",
                relation_ok if self.use_relation else _always_true),
                ("flow", f"current candle: {self.flow_above} is greater than"
                         f" {self.flow_below}",
                flow_ok if self.use_flow else _always_true),
                ("chg_pct", f"previous candle: {self.slow_change_column} is"
                             f" {'below' if self.inverted else 'above'}"
                             f" {self.chg_pct_min:g}",
                change_ok if self.use_chg_pct else _always_true),
                ("streak_minus", f"previous candle: {self.fast_run_column} is"
                                  f" {self.streak_minus_min} to {self.streak_minus_max}",
                fast_run_ok if self.use_streak_minus else _always_true),
                ("streak_plus", f"previous candle: {self.slow_run_column} is"
                                 f" {self.streak_plus_min} or more",
                slow_run_ok if self.use_streak_plus else _always_true))

    def hits(self, bar: dict, prev: dict | None) -> bool:
        """True only when all seven conditions hold on this candle."""
        return all(test(bar, prev) for _, _, test in self.tests())

    def rule_text(self) -> str:
        """The sentence the sheet prints, and the recipe records, for this rule.

        Every word that depends on the direction is chosen here from `inverted` -- the
        name, the side of the bar, above/below, rising/falling -- so a mirrored rule
        cannot describe itself in the green rule's vocabulary. The last clause is
        direction-neutral because both rules are in the same sheet.
        """
        name = "RED ARROW" if self.inverted else "GREEN ARROW"
        side = "above" if self.inverted else "below"
        fast_run = "rising" if self.inverted else "falling"
        slow_run = "falling" if self.inverted else "rising"
        return (
            f"{name}, drawn {side} the bar on the price pane of every timeframe, "
            f"on the candles where all seven conditions hold (AND); the current candle: "
            f"SMA {self.cross_fast} vs SMA {self.cross_slow} cross direction is "
            f"{self.cross_direction}, the SMA {self.distance_from} vs SMA "
            f"{self.distance_to} distance (%) at that cross is"
            f" {self.distance_pct_at_cross_min:g} to "
            f"{self.distance_pct_at_cross_max:g} inclusive, SMA {self.fast_period} vs SMA "
            f"{self.slow_period} reads {self.relation}, and the dashboard's minute this "
            f"candle opens in reads {self.flow_above} above {self.flow_below} "
            f"(a session with no dashboard does not read that condition); the "
            f"previous candle: the SMA "
            f"{self.slow_period} change (%) is strictly"
            f" {'below' if self.inverted else 'above'} {self.chg_pct_min:g}, "
            f"the SMA {self.fast_period} consecutive count is a {fast_run} run of "
            f"{self.streak_minus_min} to {self.streak_minus_max}, and the SMA "
            f"{self.slow_period} consecutive count is a {slow_run} run of "
            f"{self.streak_plus_min} or more. It marks a candle that has already "
            f"closed, reads no later bar, and is one of this sheet's two marker rules,"
            f" each the exact mirror of the other."
        )


# --------------------------------------------------------------------------------------
# Applying a rule, and counting what it saw
# --------------------------------------------------------------------------------------

def add_signal(bars: list[dict], rule: GreenArrowRule, key: str) -> None:
    """Attach one rule's flag to each bar, in place: 1 where the rule fires, else 0.

    The conditions are read from the columns the steps in `nifty.signals.series` wrote -- the
    crossing row and its distance, the relationship row, the two consecutive counts and the
    slow average's change -- and from the two dashboard columns `nifty.data.flow` joined onto the
    bars, so this step adds no series and cannot disagree with the rows the reader sees. A blank column reads as "not a hit" rather than as a zero worth
    counting, and the session's first candle can never fire because there is no previous
    candle to read.

    The flag is a plain integer so the CSV, the JSON and the rendered arrow are the same
    number everywhere. `key` is the rule's own column -- `green_arrow` or, for the mirror,
    `red_arrow` -- so the two rules share one implementation.
    """
    for idx, bar in enumerate(bars):
        bar[key] = 1 if rule.hits(bar, bars[idx - 1] if idx else None) else 0


def signal_funnel(bars: list[dict], rule: GreenArrowRule) -> dict:
    """How many candles each of a rule's seven conditions held on, one at a time.

    The count is per condition on its own, which is what makes the tallies useful: they
    show a rule that looks narrow (the distance window) next to one that is wide (the
    relationship word), and a condition that never holds would show up as a zero here
    rather than hiding behind five others. The keys are the same for a rule and its
    mirror, which is what lets the two funnels be read side by side.
    """
    tests = rule.tests()
    counts = {name: 0 for name, _, _ in tests}
    for idx, bar in enumerate(bars):
        prev = bars[idx - 1] if idx else None
        for name, _, test in tests:
            if test(bar, prev):
                counts[name] += 1
    return counts


def signal_rule(rule: GreenArrowRule) -> str:
    """The rule sentence, kept as a function so the recipe can call it by name."""
    return rule.rule_text()
