#!/usr/bin/env python3
"""
Combined run command for the nifty project.

    python tools/run_all.py        # from the project root, or from anywhere

Runs the whole chain in dependency order, from the project root whichever directory it is
launched in:

1. build_charts.py                          the NIFTY build -> output/nifty/
2. build_charts.py --config config/sensex.json  the SENSEX build -> output/sensex/
3. verify.py                                the audit (reads the NIFTY delivery)
4. python -m nifty.trade.backtest           the NIFTY trades
5. the same, --config config/sensex.json    the SENSEX trades
6. tools/write_colour_conditions.py         regenerates docs/colour_conditions.md
7. python -m nifty.cli --help               the command line's own help

Exit status: 0 when every step succeeded, the first non-zero status otherwise. A failing
step is reported and the remaining steps still run, so one run shows everything that is
wrong rather than only the first thing.
"""

import subprocess
import sys
from pathlib import Path

# the project root, so the chain works from any working directory
ROOT = Path(__file__).resolve().parents[1]


def run_command(cmd, description):
    """Run a command and report results."""
    print(f"\n{'='*60}")
    print(f"RUN: {description}")
    print(f"Cmd: {' '.join(cmd)}")
    print(f"{'='*60}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print(f"Exit status: {result.returncode}")
    return result.returncode


def main():
    """Run all project checks in pipeline order."""
    checks = [
        # 1. the NIFTY build: recipe -> sheet at output/nifty, exports under output/nifty/data
        ([sys.executable, "build_charts.py"],
         "Build the NIFTY sheet (session_summary.json + arrow_signal.json)"),

        # 2. the SENSEX build: its own recipe, its own folder, the same pipeline
        ([sys.executable, "build_charts.py", "--config", "config/sensex.json"],
         "Build the SENSEX sheet into output/sensex"),

        # 3. the audit -- it reads the NIFTY delivery (audit/harness.py pins that glob)
        ([sys.executable, "verify.py"], "Independent audit (the run prints its tally)"),

        # 4. the trades, per index, each priced on its own bars
        ([sys.executable, "-m", "nifty.trade.backtest"],
         "Backtest NIFTY under the [backtest] entry cut-off and hard exit"),
        ([sys.executable, "-m", "nifty.trade.backtest", "--config", "config/sensex.json"],
         "Backtest SENSEX under the same clock"),

        # 5. the generated reference
        ([sys.executable, "tools/write_colour_conditions.py"],
         "Regenerate docs/colour_conditions.md"),

        # 6. the command line's own help
        ([sys.executable, "-m", "nifty.cli", "--help"], "The command line's help"),
    ]

    exit_code = 0
    for cmd, description in checks:
        rc = run_command(cmd, description)
        if rc != 0:
            exit_code = rc
            print(f"\nCHECK FAILED: {description} (exit {rc})")
            # Continue running remaining checks but track failure

    if exit_code == 0:
        print("\n" + "="*60)
        print("ALL CHECKS PASSED")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("SOME CHECKS FAILED")
        print("="*60)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()