"""
nifty.recipe.config
============

One recipe drives a build. This module owns that recipe: it reads the file, applies the
command-line overrides, and validates the result into a `Config` the rest of the package
can trust.

    config/nifty.json         the recipe the build reads when it is given none
    config/nifty.toml         the same recipe, in TOML; either one may be --config'd
    load_config()             defaults  <-  file  <-  --set overrides, in that order
    Config                    the frozen result; every build parameter comes from it

**TOML or JSON, by suffix.** The two readers take the same table-of-sections shape, so a
recipe is written in whichever form a reader prefers and nothing else changes: `--config
config/nifty.toml` builds the same artifacts as `--config config/nifty.json`. Both files
ship, and the audit resolves them to the same `Config` field for field.

**A JSON recipe can explain itself.** JSON has no comment syntax, so a key whose name
starts with `_` is a note: its value is ignored and may be any type -- a string, or a
list of lines for a longer explanation (`_about`, `_note`, `_why`). A note that reads
like a real name is refused rather than ignored (`_enabled`, `_signal`), because that is
the one mistake the convention could otherwise hide; the error names the setting that was
meant. Real keys and sections are still unknown-key errors, so a typo is never silent.

The values a recipe may fall back to live in `nifty.recipe.defaults`, and everything that is
*derived* from the resolved recipe lives beside the thing that reads it: the column names
in `nifty.core.keys`, the series in `nifty.signals.series`, the arrow rules in `nifty.signals.rules`, and the
metadata blocks the artifacts carry in `nifty.output.meta`. What is left here is the recipe
itself -- the two dataclasses, the reader and the validation.

Nothing else in the package reads an argument, an environment variable or a global, so a
build is reproducible from its recipe alone. Values are validated with the message that
names the file, the section and the key, because the recipe is meant to be edited by hand.

Adding a knob
-------------
Add the default to `DEFAULTS` in `nifty.recipe.defaults`, the field to `Config`, and the reading
in `_build`; if it belongs in the sheet's metadata, add the payload key to the block that
carries it in `nifty/output/meta.py`. A new *section* is registered in `nifty.recipe.defaults` too --
that registration is what makes an unknown table in the file a clear error instead of a
silently ignored line.
"""

from __future__ import annotations

import difflib
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

from ..core.clock import clock_seconds, parse_timeframes, tf_slug
from .defaults import (BACKTEST_HARD_EXIT_DEFAULT, BACKTEST_LAST_ENTRY_DEFAULT, DEFAULTS,
                       DEFAULT_CONFIG_PATH, PROJECT_ROOT, SECTIONS)
from ..core.errors import ConfigError
from ..core.keys import (ABOVE, BELOW, CE_OI_CHANGE, PE_OI_CHANGE, red_key, relation_key,
                   signal_key)
from ..signals.rules import GreenArrowRule
from ..signals.series import (cross_distance_rule, cross_rule, direction_rule,
                              relation_rule)


# --------------------------------------------------------------------------------------
# The resolved recipe
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Paths:
    """Where a build reads from and writes to. Every path is absolute by now."""

    sources_dir: Path
    sources_glob: str
    template: Path
    chart_lib: Path
    output_dir: Path

    @property
    def data_dir(self) -> Path:
        """The per-session export folder inside the output directory."""
        return self.output_dir / "data"


@dataclass(frozen=True)
class SheetNaming:
    """How the delivered sheet is named, titled, and windowed when it opens."""

    name_template: str
    title_template: str
    window_bars: int


@dataclass(frozen=True)
class Config:
    """A validated build recipe."""

    root: Path
    source: Path | None            # the config file, or None when only defaults applied
    instrument: str
    paths: Paths
    timeframes: tuple[int, ...]
    price_periods: tuple[int, ...]
    analytics_periods: tuple[int, ...]
    pct_decimals: int
    direction_fast: int
    direction_slow: int
    run_rule: str
    direction_rule: str
    cross_fast: int
    cross_slow: int
    cross_distance_from: int
    cross_distance_to: int
    cross_rule: str
    cross_distance_rule: str
    relation_fast: int
    relation_slow: int
    relation_rule: str
    signal_enabled: bool
    signal_cross_fast: int
    signal_cross_slow: int
    signal_distance_from: int
    signal_distance_to: int
    signal_fast: int
    signal_slow: int
    signal_cross_direction: str
    signal_relation: str
    signal_distance_pct_at_cross_min: float
    signal_distance_pct_at_cross_max: float
    signal_chg_pct_min: float
    signal_streak_minus_min: int
    signal_streak_minus_max: int
    signal_streak_plus_min: int
    signal_use_cross_direction: bool
    signal_use_distance_pct: bool
    signal_use_relation: bool
    signal_use_flow: bool
    signal_use_chg_pct: bool
    signal_use_streak_minus: bool
    signal_use_streak_plus: bool
    signal_rule: str
    signal_red_enabled: bool
    signal_red_rule: str
    sheet: SheetNaming
    # the independent red rule's own thresholds and flags (None = mirror of green)
    red_cross_direction: str | None = None
    red_relation: str | None = None
    red_distance_pct_at_cross_min: float | None = None
    red_distance_pct_at_cross_max: float | None = None
    red_chg_pct_min: float | None = None
    red_streak_minus_min: int | None = None
    red_streak_minus_max: int | None = None
    red_streak_plus_min: int | None = None
    red_use_cross_direction: bool = True
    red_use_distance_pct: bool = True
    red_use_relation: bool = True
    red_use_flow: bool = True
    red_use_chg_pct: bool = True
    red_use_streak_minus: bool = True
    red_use_streak_plus: bool = True
    # the trade clock, IST wall clock: no arrow after `backtest_last_entry` is taken, and a
    # position still open at `backtest_hard_exit` is closed there whatever it shows
    backtest_last_entry: str = BACKTEST_LAST_ENTRY_DEFAULT
    backtest_hard_exit: str = BACKTEST_HARD_EXIT_DEFAULT

    # ---- derived: naming -----------------------------------------------------------
    @property
    def direction_above_column(self) -> str:
        return f"sma{self.direction_fast}_vs_sma{self.direction_slow}_above_streak"

    @property
    def direction_below_column(self) -> str:
        return f"sma{self.direction_fast}_vs_sma{self.direction_slow}_below_streak"

    @property
    def cross_direction_column(self) -> str:
        return f"sma{self.cross_fast}_vs_sma{self.cross_slow}_cross_direction"

    @property
    def cross_distance_column(self) -> str:
        return (f"sma{self.cross_distance_from}_vs_sma{self.cross_distance_to}"
                "_distance_pct_at_cross")

    @property
    def cross_pair_distance_column(self) -> str:
        return f"sma{self.cross_fast}_vs_sma{self.cross_slow}_distance_pct_at_cross"

    @property
    def relation_column(self) -> str:
        return relation_key(self.relation_fast, self.relation_slow)

    @property
    def signal_column(self) -> str:
        return signal_key()

    @property
    def red_column(self) -> str:
        return red_key()

    @property
    def sma_slash(self) -> str:
        """'2/9/44' -- how the price periods read in a title."""
        return "/".join(str(p) for p in self.price_periods)

    def timeframe_slug(self, seconds: int) -> str:
        return tf_slug(seconds)

    # ---- derived: the two arrow rules ----------------------------------------------
    def signal_rule_obj(self) -> GreenArrowRule:
        """The green-arrow rule as the step and the payload both read it."""
        return GreenArrowRule(
            cross_fast=self.signal_cross_fast,
            cross_slow=self.signal_cross_slow,
            distance_from=self.signal_distance_from,
            distance_to=self.signal_distance_to,
            fast_period=self.signal_fast,
            slow_period=self.signal_slow,
            cross_direction=self.signal_cross_direction,
            relation=self.signal_relation,
            distance_pct_at_cross_min=self.signal_distance_pct_at_cross_min,
            distance_pct_at_cross_max=self.signal_distance_pct_at_cross_max,
            chg_pct_min=self.signal_chg_pct_min,
            streak_minus_min=self.signal_streak_minus_min,
            streak_minus_max=self.signal_streak_minus_max,
            streak_plus_min=self.signal_streak_plus_min,
            use_cross_direction=self.signal_use_cross_direction,
            use_distance_pct=self.signal_use_distance_pct,
            use_relation=self.signal_use_relation,
            use_flow=self.signal_use_flow,
            use_chg_pct=self.signal_use_chg_pct,
            use_streak_minus=self.signal_use_streak_minus,
            use_streak_plus=self.signal_use_streak_plus,
            decimals=self.pct_decimals,
        )

    def red_rule_obj(self) -> GreenArrowRule:
        """The red-arrow rule.

        When the recipe carries an independent [red_signal] section, its own thresholds
        and enable flags build the rule directly. Otherwise the red rule is the mirror
        of the green one: `mirrored()` flips the green rule's comparisons and swaps its
        two runs, so no threshold can drift.
        """
        if self.red_cross_direction is not None:
            return GreenArrowRule(
                cross_fast=self.signal_cross_fast,
                cross_slow=self.signal_cross_slow,
                distance_from=self.signal_distance_from,
                distance_to=self.signal_distance_to,
                fast_period=self.signal_fast,
                slow_period=self.signal_slow,
                cross_direction=self.red_cross_direction,
                relation=self.red_relation,
                distance_pct_at_cross_min=self.red_distance_pct_at_cross_min,
                distance_pct_at_cross_max=self.red_distance_pct_at_cross_max,
                chg_pct_min=self.red_chg_pct_min,
                streak_minus_min=self.red_streak_minus_min,
                streak_minus_max=self.red_streak_minus_max,
                streak_plus_min=self.red_streak_plus_min,
                use_cross_direction=self.red_use_cross_direction,
                use_distance_pct=self.red_use_distance_pct,
                use_relation=self.red_use_relation,
                # an independently configured red rule reads the flow comparison its own way
                # round: the green rule's reading, and its mirror's, is built by `mirrored()`
                flow_above=CE_OI_CHANGE,
                flow_below=PE_OI_CHANGE,
                use_flow=self.red_use_flow,
                use_chg_pct=self.red_use_chg_pct,
                use_streak_minus=self.red_use_streak_minus,
                use_streak_plus=self.red_use_streak_plus,
                decimals=self.pct_decimals,
                inverted=True,
            )
        return self.signal_rule_obj().mirrored()

    # ---- derived: paths and mapping -------------------------------------------------
    def source_path(self, path: Path) -> str:
        """A path as the payload records it: relative to the project, '/' separated."""
        try:
            relative = path.resolve().relative_to(self.root)
        except ValueError:                                    # pragma: no cover - outside tree
            return path.as_posix()
        return relative.as_posix()

    def check_inputs(self) -> None:
        """Fail before any work is done if the template or the chart library is absent."""
        for label, path in (("template", self.paths.template), ("chart library", self.paths.chart_lib)):
            if not path.is_file():
                raise ConfigError(f"missing required {label}: {path}")

    def to_mapping(self) -> dict:
        """The resolved recipe, as a plain mapping (what `--print-config` prints)."""
        return {
            "instrument": {"name": self.instrument},
            "paths": {
                "sources_dir": str(self.paths.sources_dir),
                "sources_glob": self.paths.sources_glob,
                "template": str(self.paths.template),
                "chart_lib": str(self.paths.chart_lib),
                "output_dir": str(self.paths.output_dir),
            },
            "timeframes": {"seconds": list(self.timeframes)},
            "sma": {"price_periods": list(self.price_periods)},
            "analytics": {"periods": list(self.analytics_periods),
                          "pct_decimals": self.pct_decimals,
                          "run_rule": self.run_rule},
            "direction_streak": {"fast_period": self.direction_fast,
                                 "slow_period": self.direction_slow,
                                 "rule": self.direction_rule},
            "cross": {"fast_period": self.cross_fast,
                      "slow_period": self.cross_slow,
                      "distance_from_period": self.cross_distance_from,
                      "distance_to_period": self.cross_distance_to,
                      "rule": self.cross_rule,
                      "distance_rule": self.cross_distance_rule},
            "relation": {"fast_period": self.relation_fast,
                         "slow_period": self.relation_slow,
                         "rule": self.relation_rule},
            "signal": {
                "enabled": self.signal_enabled,
                "fast_period": self.signal_fast,
                "slow_period": self.signal_slow,
                "cross_direction": self.signal_cross_direction,
                "relation": self.signal_relation,
                "distance_pct_at_cross_min": self.signal_distance_pct_at_cross_min,
                "distance_pct_at_cross_max": self.signal_distance_pct_at_cross_max,
                "chg_pct_min": self.signal_chg_pct_min,
                "streak_minus_min": self.signal_streak_minus_min,
                "streak_minus_max": self.signal_streak_minus_max,
                "streak_plus_min": self.signal_streak_plus_min,
                # one switch per condition, printed so a reader can see which of the seven
                # the build actually read -- use_flow is the CE / PE OI one
                "use_cross_direction": self.signal_use_cross_direction,
                "use_distance_pct": self.signal_use_distance_pct,
                "use_relation": self.signal_use_relation,
                "use_flow": self.signal_use_flow,
                "use_chg_pct": self.signal_use_chg_pct,
                "use_streak_minus": self.signal_use_streak_minus,
                "use_streak_plus": self.signal_use_streak_plus,
                "rule": self.signal_rule,
            },
            "backtest": {"last_entry": self.backtest_last_entry,
                         "hard_exit": self.backtest_hard_exit},
            "sheet": {"name_template": self.sheet.name_template,
                      "title_template": self.sheet.title_template,
                      "window_bars": self.sheet.window_bars},
        }


# --------------------------------------------------------------------------------------
# Reading a recipe
#
# A note is a key whose name starts with '_': JSON's stand-in for a comment. Notes are
# dropped before the recipe is merged, and the one way they could mislead -- a note named
# like the setting it sits beside -- is an error rather than a silent no-op.
# --------------------------------------------------------------------------------------

NOTE_PREFIX = "_"


def _note_miss(name: str, known: "tuple[str, ...] | list[str]") -> str | None:
    """The real name a note reads like, or None when it is just a note.

    `_enabled` beside `enabled`, or `_signal` beside `[signal]`, is almost certainly a
    setting someone meant to write: the note is refused and the real name is reported. A
    note that resembles nothing (`_why`, `_units`) is left alone.
    """
    bare = name.lstrip(NOTE_PREFIX)
    if not bare:
        return None
    if bare in known:
        return bare
    near = difflib.get_close_matches(bare, list(known), n=1, cutoff=0.85)
    return near[0] if near else None


def _read_file(path: Path) -> dict:
    if not path.is_file():
        raise ConfigError(f"no such config file: {path}")
    # utf-8-sig: a recipe saved by an editor that writes a byte-order mark still reads
    text = path.read_text(encoding="utf-8-sig")
    as_json = path.suffix.lower() == ".json"
    try:
        raw = json.loads(text) if as_json else tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError) as exc:
        raise ConfigError(
            f"{path} is not valid {'JSON' if as_json else 'TOML'}: {exc}") from exc
    if not isinstance(raw, dict):
        wanted = "an object of sections" if as_json else "a table of sections"
        raise ConfigError(f"{path} must contain {wanted}")
    return raw


def _check_keys(raw: dict, where: str) -> None:
    """Refuse a recipe the pipeline would not read, rather than half-honour it.

    A note section or note key is skipped -- its value is not looked at, so it can be a
    string or a list of lines -- unless its name reads like a real one, which is reported
    as the mistake it usually is. Everything else must be a known section of known keys.
    """
    for section, table in raw.items():
        if section.startswith(NOTE_PREFIX):
            like = _note_miss(section, SECTIONS)
            if like:
                raise ConfigError(
                    f"{where}: {section} is a note, but [{like}] is a real section"
                    f" -- rename the note, or use [{like}] if that was meant")
            continue
        if section not in SECTIONS:
            near = difflib.get_close_matches(section, SECTIONS, n=1)
            hint = (f" -- did you mean [{near[0]}]?" if near else
                    f" -- known sections: {', '.join(SECTIONS)}; a new one is registered with"
                    " its keys in nifty/recipe/defaults.py (SECTIONS and DEFAULTS), read into a field"
                    " in nifty/recipe/config.py (Config) and written by a step in nifty/data/analysis.py")
            raise ConfigError(f"{where}: unknown section [{section}]{hint}")
        if not isinstance(table, dict):
            raise ConfigError(f"{where}: [{section}] must be a table of key = value lines")
        for key in table:
            if key.startswith(NOTE_PREFIX):
                like = _note_miss(key, DEFAULTS[section])
                if like:
                    raise ConfigError(
                        f"{where}: [{section}] {key} is a note, but {like} is a real key"
                        f" -- rename the note, or set {like} if that was meant")
                continue
            if key not in DEFAULTS[section]:
                near = difflib.get_close_matches(key, DEFAULTS[section], n=1)
                hint = f" -- did you mean {near[0]}?" if near else \
                       f" -- known keys: {', '.join(DEFAULTS[section])}"
                raise ConfigError(f"{where}: unknown key [{section}] {key}{hint}")


def _merge(base: dict, extra: dict, where: str) -> dict:
    """The file's values over the defaults, with its notes left behind."""
    _check_keys(extra, where)
    merged = {section: dict(values) for section, values in base.items()}
    for section, table in extra.items():
        if section.startswith(NOTE_PREFIX):
            continue
        merged[section].update({key: value for key, value in table.items()
                                if not key.startswith(NOTE_PREFIX)})
    return merged


def _as_int(value: object, section: str, key: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"[{section}] {key} must be a whole number, got {value!r}")
    return value


def _as_text(value: object, section: str, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"[{section}] {key} must be a non-empty string, got {value!r}")
    return value


def _as_bool(value: object, section: str, key: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"[{section}] {key} must be true or false, got {value!r}")
    return value


def _as_number(value: object, section: str, key: str) -> float:
    """A percentage threshold: a float or an int, but never a bool."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"[{section}] {key} must be a number, got {value!r}")
    return float(value)


def _as_word(value: object, section: str, key: str) -> str:
    """One of the sheet's own tokens, so a rule can never compare against 'Above'."""
    return _as_choice(value, section, key, (ABOVE, BELOW))


def _as_clock(value: object, section: str, key: str) -> str:
    """An IST wall-clock time, normalised to 'HH:MM:SS'.

    Normalising rather than passing the text through means '9:15' and '09:15:00' resolve
    to one value, so the two recipes cannot differ only by how a time was written.
    """
    text = _as_text(value, section, key)
    parts = text.split(":")
    if len(parts) not in (2, 3) or not all(part.isdigit() for part in parts):
        raise ConfigError(f"[{section}] {key} must be an IST time like '15:15:00', got {value!r}")
    hours, minutes = int(parts[0]), int(parts[1])
    seconds = int(parts[2]) if len(parts) == 3 else 0
    if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59):
        raise ConfigError(f"[{section}] {key} is not a time of day: {value!r}")
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _as_choice(value: object, section: str, key: str, allowed: tuple[str, ...]) -> str:
    """One of a named set of tokens, spelled exactly as the code spells it."""
    text = _as_text(value, section, key)
    if text not in allowed:
        raise ConfigError(f"[{section}] {key} must be {' or '.join(allowed)}, got {text!r}")
    return text


def _as_periods(value: object, section: str, key: str) -> tuple[int, ...]:
    """A list of periods, or a compact string such as '2,9,44' / '2/9/44'."""
    if isinstance(value, str):
        value = [piece for piece in value.replace("/", ",").split(",") if piece.strip()]
    if not isinstance(value, (list, tuple)):
        raise ConfigError(f"[{section}] {key} must be a list of periods, got {value!r}")
    periods: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise ConfigError(f"[{section}] {key}: {item!r} is not a positive period")
        if item in periods:
            raise ConfigError(f"[{section}] {key}: {item} is listed twice")
        periods.append(item)
    if not periods:
        raise ConfigError(f"[{section}] {key} must name at least one period")
    return tuple(periods)


def _as_path(value: object, section: str, key: str, root: Path) -> Path:
    text = _as_text(value, section, key)
    path = Path(text).expanduser()
    return path if path.is_absolute() else (root / path)


def _resolve_period(table: dict, key: str, fallback: int) -> int:
    """A [signal] period, or the row it reads when the recipe leaves it out."""
    value = table.get(key)
    return fallback if value is None else _as_int(value, "signal", key)


def _build(raw: dict, root: Path, source: Path | None) -> Config:
    instrument = _as_text(raw["instrument"]["name"], "instrument", "name")

    paths = Paths(
        sources_dir=_as_path(raw["paths"]["sources_dir"], "paths", "sources_dir", root),
        sources_glob=_as_text(raw["paths"]["sources_glob"], "paths", "sources_glob"),
        template=_as_path(raw["paths"]["template"], "paths", "template", root),
        chart_lib=_as_path(raw["paths"]["chart_lib"], "paths", "chart_lib", root),
        output_dir=_as_path(raw["paths"]["output_dir"], "paths", "output_dir", root),
    )

    try:
        timeframes = parse_timeframes(raw["timeframes"]["seconds"])
    except ValueError as exc:
        raise ConfigError(f"[timeframes] seconds: {exc}") from exc

    price_periods = _as_periods(raw["sma"]["price_periods"], "sma", "price_periods")
    analytics_periods = _as_periods(raw["analytics"]["periods"], "analytics", "periods")

    pct_decimals = _as_int(raw["analytics"]["pct_decimals"], "analytics", "pct_decimals")
    if not 0 <= pct_decimals <= 8:
        raise ConfigError(f"[analytics] pct_decimals must be between 0 and 8, got {pct_decimals}")

    window_bars = _as_int(raw["sheet"]["window_bars"], "sheet", "window_bars")
    if not 10 <= window_bars <= 5000:
        raise ConfigError(
            f"[sheet] window_bars must be between 10 and 5000 candles, got {window_bars}")

    backtest = raw["backtest"]
    last_entry = _as_clock(backtest["last_entry"], "backtest", "last_entry")
    hard_exit = _as_clock(backtest["hard_exit"], "backtest", "hard_exit")
    if clock_seconds(hard_exit) <= clock_seconds(last_entry):
        raise ConfigError(
            f"[backtest] hard_exit ({hard_exit}) must be later than last_entry "
            f"({last_entry}) -- otherwise a trade is cut before it can be taken")

    direction = raw["direction_streak"]
    fast = _as_int(direction.get("fast_period", analytics_periods[0]),
                   "direction_streak", "fast_period")
    slow = _as_int(direction.get("slow_period", analytics_periods[min(1, len(analytics_periods) - 1)]),
                   "direction_streak", "slow_period")
    if fast == slow:
        raise ConfigError("[direction_streak] fast_period and slow_period must differ")
    for label, period in (("fast_period", fast), ("slow_period", slow)):
        if period not in analytics_periods:
            raise ConfigError(
                f"[direction_streak] {label} {period} is not in [analytics] periods "
                f"{list(analytics_periods)} -- the row reads that average's printed change")

    configured_rule = direction.get("rule")
    rule_text = (direction_rule(fast, slow) if configured_rule is None
                 else _as_text(configured_rule, "direction_streak", "rule"))

    cross = raw["cross"]
    cross_fast = _as_int(cross["fast_period"], "cross", "fast_period")
    cross_slow = _as_int(cross["slow_period"], "cross", "slow_period")
    cross_from = _as_int(cross["distance_from_period"], "cross", "distance_from_period")
    cross_to = _as_int(cross["distance_to_period"], "cross", "distance_to_period")
    if cross_fast == cross_slow:
        raise ConfigError("[cross] fast_period and slow_period must differ")
    if cross_from == cross_to:
        raise ConfigError("[cross] distance_from_period and distance_to_period must differ")
    if (cross_from, cross_to) == (cross_fast, cross_slow):
        raise ConfigError("[cross] the distance pair is the crossing pair, so the two "
                          "distance columns would carry the same name")
    for label, period in (("fast_period", cross_fast), ("slow_period", cross_slow),
                          ("distance_from_period", cross_from),
                          ("distance_to_period", cross_to)):
        if period not in analytics_periods:
            raise ConfigError(
                f"[cross] {label} {period} is not in [analytics] periods "
                f"{list(analytics_periods)} -- the analytics table has to carry that average")

    cross_text = (cross_rule(cross_fast, cross_slow) if cross.get("rule") is None
                  else _as_text(cross["rule"], "cross", "rule"))
    cross_distance_text = (cross_distance_rule(cross_from, cross_to)
                           if cross.get("distance_rule") is None
                           else _as_text(cross["distance_rule"], "cross", "distance_rule"))

    relation = raw["relation"]
    relation_fast = _as_int(relation["fast_period"], "relation", "fast_period")
    relation_slow = _as_int(relation["slow_period"], "relation", "slow_period")
    if relation_fast == relation_slow:
        raise ConfigError("[relation] fast_period and slow_period must differ")
    for label, period in (("fast_period", relation_fast), ("slow_period", relation_slow)):
        if period not in analytics_periods:
            raise ConfigError(
                f"[relation] {label} {period} is not in [analytics] periods "
                f"{list(analytics_periods)} -- the row reads that average on every candle")

    relation_text = (relation_rule(relation_fast, relation_slow)
                     if relation.get("rule") is None
                     else _as_text(relation["rule"], "relation", "rule"))

    # ---- the green-arrow rule ------------------------------------------------------
    # The rule reads rows the sections above already define: the crossing row and the
    # distance row it carries (both from [cross]), and the run lengths and change of one
    # pair of averages (the [relation] pair unless the recipe names another). Its periods
    # are therefore read from those sections rather than repeated here, so the rule and
    # the rows it reads can never point at different averages.
    signal = raw["signal"]
    signal_enabled = _as_bool(signal["enabled"], "signal", "enabled")
    signal_fast = _resolve_period(signal, "fast_period", relation_fast)
    signal_slow = _resolve_period(signal, "slow_period", relation_slow)
    if signal_fast == signal_slow:
        raise ConfigError("[signal] fast_period and slow_period must differ")
    for label, period in (("fast_period", signal_fast), ("slow_period", signal_slow)):
        if period not in analytics_periods:
            raise ConfigError(
                f"[signal] {label} {period} is not in [analytics] periods "
                f"{list(analytics_periods)} -- the rule reads that average's own rows")

    signal_cross_direction = _as_word(signal["cross_direction"], "signal", "cross_direction")
    signal_relation_word = _as_word(signal["relation"], "signal", "relation")
    distance_pct_at_cross_min = _as_number(signal["distance_pct_at_cross_min"], "signal",
                                           "distance_pct_at_cross_min")
    distance_pct_at_cross_max = _as_number(signal["distance_pct_at_cross_max"], "signal",
                                           "distance_pct_at_cross_max")
    # Read condition enable flags (default to True if not specified)
    signal_use_cross_direction = _as_bool(signal.get("use_cross_direction", True), "signal", "use_cross_direction")
    signal_use_distance_pct = _as_bool(signal.get("use_distance_pct", True), "signal", "use_distance_pct")
    signal_use_relation = _as_bool(signal.get("use_relation", True), "signal", "use_relation")
    signal_use_flow = _as_bool(signal.get("use_flow", True), "signal", "use_flow")
    signal_use_chg_pct = _as_bool(signal.get("use_chg_pct", True), "signal", "use_chg_pct")
    signal_use_streak_minus = _as_bool(signal.get("use_streak_minus", True), "signal", "use_streak_minus")
    signal_use_streak_plus = _as_bool(signal.get("use_streak_plus", True), "signal", "use_streak_plus")
    if distance_pct_at_cross_min > distance_pct_at_cross_max:
        raise ConfigError(
            f"[signal] distance_pct_at_cross_min {distance_pct_at_cross_min} is above "
            f"distance_pct_at_cross_max {distance_pct_at_cross_max}")
    chg_pct_min = _as_number(signal["chg_pct_min"], "signal", "chg_pct_min")
    streak_minus_min = _as_int(signal["streak_minus_min"], "signal", "streak_minus_min")
    streak_minus_max = _as_int(signal["streak_minus_max"], "signal", "streak_minus_max")
    streak_plus_min = _as_int(signal["streak_plus_min"], "signal", "streak_plus_min")
    if streak_minus_min < 1 or streak_minus_max < streak_minus_min:
        raise ConfigError("[signal] streak_minus_min / streak_minus_max must be a run of "
                          f"at least 1, got {streak_minus_min} to {streak_minus_max}")
    if streak_plus_min < 1:
        raise ConfigError(f"[signal] streak_plus_min must be at least 1, got {streak_plus_min}")

    signal_obj = GreenArrowRule(
        cross_fast=cross_fast, cross_slow=cross_slow,
        distance_from=cross_from, distance_to=cross_to,
        fast_period=signal_fast, slow_period=signal_slow,
        cross_direction=signal_cross_direction, relation=signal_relation_word,
        distance_pct_at_cross_min=distance_pct_at_cross_min,
        distance_pct_at_cross_max=distance_pct_at_cross_max,
        chg_pct_min=chg_pct_min, streak_minus_min=streak_minus_min,
        streak_minus_max=streak_minus_max, streak_plus_min=streak_plus_min,
        use_cross_direction=signal_use_cross_direction,
        use_distance_pct=signal_use_distance_pct,
        use_relation=signal_use_relation,
        use_flow=signal_use_flow,
        use_chg_pct=signal_use_chg_pct,
        use_streak_minus=signal_use_streak_minus,
        use_streak_plus=signal_use_streak_plus,
        decimals=pct_decimals)
    signal_text = (signal_obj.rule_text() if signal.get("rule") is None
                   else _as_text(signal["rule"], "signal", "rule"))

    # Validate signal.red_arrow is a boolean before the red_signal/mirror decision.
    # This must be checked regardless of whether red_signal section is present.
    signal_red_arrow = signal.get("red_arrow")
    if signal_red_arrow is not None and not isinstance(signal_red_arrow, bool):
        raise ConfigError(
            f"[signal] red_arrow must be true or false, got {signal_red_arrow!r}"
        )

    # ---- the red arrow: use red_signal section if present, otherwise mirror green ---
    # If [red_signal] section is in the recipe, its values are used independently.
    # Otherwise, the red rule is the mirror of the green rule.
    red_signal = raw.get("red_signal")
    if red_signal and isinstance(red_signal, dict):
        # Independent red_signal section: use its own values
        red_enabled = _as_bool(red_signal.get("enabled", True), "red_signal", "enabled")
        red_cross_direction = _as_word(red_signal.get("cross_direction", "BELOW"), "red_signal", "cross_direction")
        red_relation = _as_word(red_signal.get("relation", "BELOW"), "red_signal", "relation")
        red_distance_min = _as_number(red_signal.get("distance_pct_at_cross_min", 0.0), "red_signal", "distance_pct_at_cross_min")
        red_distance_max = _as_number(red_signal.get("distance_pct_at_cross_max", 0.025), "red_signal", "distance_pct_at_cross_max")
        red_chg_min = _as_number(red_signal.get("chg_pct_min", 0.0005), "red_signal", "chg_pct_min")
        red_streak_minus_min = _as_int(red_signal.get("streak_minus_min", 7), "red_signal", "streak_minus_min")
        red_streak_minus_max = _as_int(red_signal.get("streak_minus_max", 15), "red_signal", "streak_minus_max")
        red_streak_plus_min = _as_int(red_signal.get("streak_plus_min", 7), "red_signal", "streak_plus_min")
        red_use_cross_direction = _as_bool(red_signal.get("use_cross_direction", True), "red_signal", "use_cross_direction")
        red_use_distance_pct = _as_bool(red_signal.get("use_distance_pct", True), "red_signal", "use_distance_pct")
        red_use_relation = _as_bool(red_signal.get("use_relation", True), "red_signal", "use_relation")
        red_use_flow = _as_bool(red_signal.get("use_flow", True), "red_signal", "use_flow")
        red_use_chg_pct = _as_bool(red_signal.get("use_chg_pct", True), "red_signal", "use_chg_pct")
        red_use_streak_minus = _as_bool(red_signal.get("use_streak_minus", True), "red_signal", "use_streak_minus")
        red_use_streak_plus = _as_bool(red_signal.get("use_streak_plus", True), "red_signal", "use_streak_plus")
        red_arrow = True  # red_signal implies red arrows are drawn
        red_rule_text = (
            f"RED ARROW, cross direction {red_cross_direction}, relation {red_relation}, "
            f"distance {red_distance_min:g} to {red_distance_max:g} inclusive, "
            f"change strictly {'below' if red_chg_min < 0 else 'above'} {red_chg_min:g}, "
            f"fast falling run {red_streak_minus_min} to {red_streak_minus_max}, "
            f"slow rising run {red_streak_plus_min} or more"
        )
    else:
        # Mirror of the green rule (original behavior)
        signal_red_enabled = _as_bool(signal["red_arrow"], "signal", "red_arrow")
        signal_red_text = (signal_obj.mirrored().rule_text() if signal.get("red_rule") is None
                           else _as_text(signal["red_rule"], "signal", "red_rule"))
        red_enabled = signal_red_enabled
        red_rule_text = signal_red_text
        # no independent [red_signal]: every red_* stays None so red_rule_obj mirrors green
        red_cross_direction = red_relation = None
        red_distance_min = red_distance_max = red_chg_min = None
        red_streak_minus_min = red_streak_minus_max = red_streak_plus_min = None
        red_use_cross_direction = red_use_distance_pct = red_use_relation = True
        red_use_flow = signal_use_flow
        red_use_chg_pct = red_use_streak_minus = red_use_streak_plus = True

    return Config(
        root=root,
        source=source,
        instrument=instrument,
        paths=paths,
        timeframes=timeframes,
        price_periods=price_periods,
        analytics_periods=analytics_periods,
        pct_decimals=pct_decimals,
        direction_fast=fast,
        direction_slow=slow,
        run_rule=_as_text(raw["analytics"]["run_rule"], "analytics", "run_rule"),
        direction_rule=rule_text,
        cross_fast=cross_fast,
        cross_slow=cross_slow,
        cross_distance_from=cross_from,
        cross_distance_to=cross_to,
        cross_rule=cross_text,
        cross_distance_rule=cross_distance_text,
        relation_fast=relation_fast,
        relation_slow=relation_slow,
        relation_rule=relation_text,
        signal_enabled=signal_enabled,
        signal_cross_fast=cross_fast,
        signal_cross_slow=cross_slow,
        signal_distance_from=cross_from,
        signal_distance_to=cross_to,
        signal_fast=signal_fast,
        signal_slow=signal_slow,
        signal_cross_direction=signal_cross_direction,
        signal_relation=signal_relation_word,
        signal_distance_pct_at_cross_min=distance_pct_at_cross_min,
        signal_distance_pct_at_cross_max=distance_pct_at_cross_max,
        signal_chg_pct_min=chg_pct_min,
        signal_streak_minus_min=streak_minus_min,
        signal_streak_minus_max=streak_minus_max,
        signal_streak_plus_min=streak_plus_min,
        signal_use_cross_direction=signal_use_cross_direction,
        signal_use_distance_pct=signal_use_distance_pct,
        signal_use_relation=signal_use_relation,
        signal_use_flow=signal_use_flow,
        signal_use_chg_pct=signal_use_chg_pct,
        signal_use_streak_minus=signal_use_streak_minus,
        signal_use_streak_plus=signal_use_streak_plus,
        signal_rule=signal_text,
        signal_red_enabled=red_enabled,
        signal_red_rule=red_rule_text,
        red_cross_direction=red_cross_direction if red_signal else None,
        red_relation=red_relation if red_signal else None,
        red_distance_pct_at_cross_min=red_distance_min if red_signal else None,
        red_distance_pct_at_cross_max=red_distance_max if red_signal else None,
        red_chg_pct_min=red_chg_min if red_signal else None,
        red_streak_minus_min=red_streak_minus_min if red_signal else None,
        red_streak_minus_max=red_streak_minus_max if red_signal else None,
        red_streak_plus_min=red_streak_plus_min if red_signal else None,
        red_use_cross_direction=red_use_cross_direction if red_signal else True,
        red_use_distance_pct=red_use_distance_pct if red_signal else True,
        red_use_relation=red_use_relation if red_signal else True,
        red_use_flow=red_use_flow if red_signal else signal_use_flow,
        red_use_chg_pct=red_use_chg_pct if red_signal else True,
        red_use_streak_minus=red_use_streak_minus if red_signal else True,
        red_use_streak_plus=red_use_streak_plus if red_signal else True,
        backtest_last_entry=last_entry,
        backtest_hard_exit=hard_exit,
        sheet=SheetNaming(
            name_template=_as_text(raw["sheet"]["name_template"], "sheet", "name_template"),
            title_template=_as_text(raw["sheet"]["title_template"], "sheet", "title_template"),
            window_bars=window_bars,
        ),
    )


# --------------------------------------------------------------------------------------
# Command-line overrides
# --------------------------------------------------------------------------------------

def parse_overrides(pairs: list[str] | None) -> dict:
    """Turn ['analytics.pct_decimals=6', ...] into {'analytics': {'pct_decimals': 6}}.

    The value is read as TOML, so `12`, `6`, `'1m'`, `["1m","3m"]` and `true` all work;
    anything TOML rejects is taken as a plain string.
    """
    overrides: dict[str, dict[str, object]] = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ConfigError(f"--set expects section.key=value, got {pair!r}")
        dotted, _, raw_value = pair.partition("=")
        parts = dotted.strip().split(".")
        if len(parts) != 2 or not all(parts):
            raise ConfigError(f"--set expects section.key=value, got {pair!r}")
        section, key = parts
        try:
            value = tomllib.loads(f"value = {raw_value}")["value"]
        except tomllib.TOMLDecodeError:
            value = raw_value
        overrides.setdefault(section, {})[key] = value
    return overrides


def load_config(path: Path | str | None = None,
                overrides: list[str] | dict | None = None,
                root: Path | None = None) -> Config:
    """Defaults <- config file <- overrides, validated into a `Config`.

    `path=None` reads the project's own config/nifty.toml; pass `path=False` for the
    built-in defaults alone (useful in tests and in the entry-point aliases).
    """
    root = Path(root) if root is not None else PROJECT_ROOT
    raw = {section: dict(values) for section, values in DEFAULTS.items()}

    if path is False or path is None:
        source = None if path is False else DEFAULT_CONFIG_PATH
        if source is not None and not source.is_file():
            source = None                      # defaults alone; the CLI says so out loud
    else:
        source = Path(path)
        if not source.is_absolute():
            source = root / source

    if source is not None:
        raw = _merge(raw, _read_file(source), str(source))

    if isinstance(overrides, dict):
        extra = overrides
    else:
        extra = parse_overrides(overrides)
    if extra:
        raw = _merge(raw, extra, "--set")

    return _build(raw, root, source)
