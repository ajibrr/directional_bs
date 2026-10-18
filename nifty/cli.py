"""
nifty.cli
=========

The command line.

    python build_charts.py                                  # build with config/nifty.toml

Exit status: 0 when the build (or the requested report) succeeded, 2 when the recipe
or the input tape cannot support one -- in which case the reason is one line on
stderr rather than a traceback.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Callable, Sequence

from .data import analysis
from .core.clock import tf_label
from .recipe.config import Config, load_config
from .recipe.defaults import DEFAULT_CONFIG_PATH
from .core.errors import PipelineError
from .data.flow import dashboard_glob
from .core.model import Build
from .data.pipeline import build

PROGRAM = "build_charts.py"

# how an empty recipe is reported: the file is optional, the defaults are not
DEFAULTS_LABEL = "built-in defaults"


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Build the multi-session SMA analytics sheet and its data exports.",
        epilog="A new analysis is a step in nifty/data/analysis.py plus its own config "
               "section; --describe lists the steps, --print-config the resolved recipe.")
    ap.add_argument("--config", metavar="PATH", default=None,
                    help="recipe to build from, TOML or JSON by the file's suffix "
                         f"(default: {DEFAULT_CONFIG_PATH})")
    ap.add_argument("--set", metavar="SECTION.KEY=VALUE", action="append", default=[],
                    help="override one recipe value; repeatable, e.g. "
                         "--set timeframes.seconds='[\"1m\",\"3m\"]'")
    ap.add_argument("--input-dir", metavar="DIR", default=None,
                    help="read the session files from here instead of the recipe's sources_dir "
                         "(absolute, or relative to the project root)")
    ap.add_argument("--out-dir", metavar="DIR", default=None,
                    help="write every artifact here instead of the recipe's output_dir "
                         "(absolute, or relative to the project root)")
    ap.add_argument("--print-config", action="store_true",
                    help="print the resolved recipe and stop")
    ap.add_argument("--describe", action="store_true",
                    help="list the analysis steps, their columns and the naming tokens, then stop")
    ap.add_argument("--quiet", action="store_true", help="build without the console report")
    return ap


def describe(cfg: Config, out: Callable[[str], None] = print) -> None:
    """What this build computes -- the place to look before adding a step."""
    out(f"recipe           : {cfg.source if cfg.source else DEFAULTS_LABEL}")
    out(f"instrument       : {cfg.instrument}")
    out(f"timeframes       : " + ", ".join(f"{tf_label(s)} ({s}s)" for s in cfg.timeframes))
    out(f"price averages   : SMA {cfg.sma_slash} (editable in the sheet's toolbar)")
    out(f"analytics        : SMA {', '.join(str(p) for p in cfg.analytics_periods)}"
        f" at {cfg.pct_decimals} decimals")
    out(f"direction row    : SMA {cfg.direction_fast} vs SMA {cfg.direction_slow}")
    out(f"crossing rows    : SMA {cfg.cross_fast} vs SMA {cfg.cross_slow}, distance on"
        f" SMA {cfg.cross_distance_from} vs SMA {cfg.cross_distance_to}")
    out(f"relationship row : SMA {cfg.relation_fast} vs SMA {cfg.relation_slow}")
    # the conditions are listed from the rule itself, so this line cannot describe a rule
    # the build is not running: each condition names the column it reads and the bound the
    # recipe put on it
    rule = cfg.signal_rule_obj()
    out(f"green arrow      : " + ("on" if cfg.signal_enabled else "off") +
        f"  (column {cfg.signal_column}; {len(rule.tests())} conditions, all required: "
        f"{', '.join(name for name, _, _ in rule.tests())})")
    for name, description, _ in rule.tests():
        out(f"                   {name:<20} {description}")
    # the red arrow is the same rule mirrored, so it is listed from the mirrored rule
    # rather than from a second paragraph here: what it reads is shown, not described
    red = cfg.red_rule_obj()
    out(f"red arrow        : " + ("on" if cfg.signal_red_enabled else "off") +
        f"  (column {cfg.red_column}; the exact mirror of the green arrow, so all seven"
        " conditions are the green ones read the other way round)")
    for name, description, _ in red.tests():
        out(f"                   {name:<20} {description}")
    # the backtest's own clock, printed here because it is a recipe value a reader should
    # be able to see without opening nifty/trade/backtest.py
    out(f"trade clock      : entries until {cfg.backtest_last_entry} IST, hard exit "
        f"{cfg.backtest_hard_exit} IST (nifty/trade/backtest.py)")
    out(f"sources          : {cfg.paths.sources_dir} / {cfg.paths.sources_glob}")
    dashboards = dashboard_glob(cfg.paths.sources_glob)
    if dashboards:
        out(f"                   a session with no tape beside it is read from "
            f"{dashboards}")
    out(f"output           : {cfg.paths.output_dir}")
    out(f"sheet            : {cfg.sheet.name_template}")
    out("")
    out("analysis steps (nifty/data/analysis.py), run over every timeframe of every session:")
    for index, step in enumerate(analysis.STEPS, 1):
        out(f"  {index}. {step.name} -- {step.summary}")
        out(f"     columns: {', '.join(step.columns(cfg))}")
    out("")
    out("The next analysis is a step in that list plus its own config section; the CSV,")
    out("the JSON exports and the sheet's payload all follow the list.")


def report(result: Build, cfg: Config, out: Callable[[str], None] = print) -> None:
    """The console summary: what was read, what each timeframe looks like, what was written."""
    out(f"recipe: {cfg.source if cfg.source else DEFAULTS_LABEL}")
    for day in result.days:
        out(f"\n{day.date}  ({day.source})")
        for seconds in cfg.timeframes:
            stat = day.summary[str(seconds)]
            averages = "  ".join(
                f"SMA{p}={stat['smaLast'][str(p)]:.2f}"
                if stat["smaLast"][str(p)] is not None else f"SMA{p}=n/a"
                for p in cfg.price_periods)
            counts = "  ".join(f"SMA{p}:{stat['analytics'][str(p)]['displayLabel']}"
                               for p in cfg.analytics_periods)
            out(f"  [{stat['label']:>6}] bars={stat['bars']:>5}  C={stat['close']:.2f}  "
                f"{averages}   counts {counts}   "
                f"{cfg.direction_fast}v{cfg.direction_slow}:{stat['direction']['displayLabel']}"
                f"   arrows={stat['signal']['arrows']}"
                f" red={stat['redSignal']['arrows']}")
    out("")
    for day in result.days:
        session = day.session
        out(f"{day.date}: {session['ticks']} ticks  {session['sessionStartIST']} -> "
            f"{session['sessionEndIST']}  coverage={session['coveragePct']}%")
    out(f"{len(result.days)} session(s): {result.dates[0]} .. {result.dates[-1]}")
    out(f"wrote {cfg.source_path(result.sheet)}  ({result.sheet.stat().st_size / 1024:.0f} KiB)")
    if result.pruned:
        out(f"pruned {len(result.pruned)} stale export(s)")
    if result.dropped:
        out(f"dropped {len(result.dropped)} superseded sheet(s)")


def main(argv: Sequence[str] | None = None, out: Callable[[str], None] = print,
         err: Callable[[str], None] | None = None) -> int:
    """Run the command line. Returns the process exit status."""
    err = err or (lambda line: print(line, file=sys.stderr))
    args = parser().parse_args(argv)

    overrides = list(args.set)
    if args.input_dir:
        overrides.append(f"paths.sources_dir={args.input_dir}")
    if args.out_dir:
        overrides.append(f"paths.output_dir={args.out_dir}")

    try:
        cfg = load_config(args.config, overrides)
        if args.print_config:
            out(json.dumps(cfg.to_mapping(), indent=2))
            return 0
        if args.describe:
            describe(cfg, out)
            return 0
        result = build(cfg)
    except PipelineError as exc:
        err(f"error: {exc}")
        return 2

    if not args.quiet:
        report(result, cfg, out)
    return 0
