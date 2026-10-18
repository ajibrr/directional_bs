#!/usr/bin/env python3
"""
Backtest the green and red arrow signals against the day's own clock.

Reads the arrow signal out of the recipe's own output tree -- `output/nifty` for the NIFTY
recipe, `output/sensex` for SENSEX -- and applies:
- Entry at the close of the arrow signal candle, and **never after the entry cut-off**:
  `[backtest] last_entry` (15:10:00 IST by default). An arrow whose candle opens after
  that time is reported as `no entry` and is not traded.
- Exit when SMA 2 crosses back across SMA 9 (below for LONG, above for SHORT).
- **Hard exit** at `[backtest] hard_exit` (15:15:00 IST by default): anything still open
  when the clock reaches that time is closed there, at that candle's opening price,          whatever its profit or loss. No trade is carried past it; a session whose data
  stops earlier than that is closed on its last candle rather than left open.
- No fixed stop-loss or target prices.

Both times come from the recipe, so a different session's cut-offs are a config change
and not a code change. The report counts the arrows each rule took out of the book.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..recipe.config import load_config
from ..core.clock import (IST_OFFSET_SECONDS, clock_seconds, ist_clock, ist_full,
                          tf_slug)
from ..core.numeric import fmt_price, PRICE_DECIMALS

# IST offset: UTC+05:30 = 19800 seconds, the one in nifty.core.clock
__all__ = ["backtest_one", "make_report", "main"]


def load_arrow_signal(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_bars_for_date(date_str: str, timeframe_sec: int, cfg) -> list:
    """Return list of bar dicts from the JSON under the 'bars' key.

    The folder comes from the recipe's `paths.output_dir`, not a fixed `output/`: two
    indices are two builds into two folders, and a trade must be priced on the bars of the
    index its arrow came from.
    """
    day_dir = Path(cfg.paths.data_dir) / date_str
    if not day_dir.is_dir():
        return []
    slug = tf_slug(timeframe_sec)
    p1 = day_dir / f"nifty_{slug}.json"
    p2 = day_dir / "nifty_12sec.json"
    for p in (p1, p2):
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("bars", [])
    return []


def _ist_date_from_epoch(epoch):
    """Return 'YYYY-MM-DD' string in IST given a UTC epoch."""
    utc_dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    ist_dt = utc_dt + timedelta(seconds=IST_OFFSET_SECONDS)
    return ist_dt.strftime("%Y-%m-%d")


def _epoch_from_ist(date_str: str, time_str: str) -> int:
    """The UTC epoch of an IST date and time, for an arrow record without one."""
    pattern = "%Y-%m-%d %H:%M:%S" if time_str.count(":") == 2 else "%Y-%m-%d %H:%M"
    stamp = datetime.strptime(f"{date_str} {time_str}", pattern)
    return int(stamp.replace(tzinfo=timezone.utc).timestamp()) - IST_OFFSET_SECONDS


def fmt(val) -> str:
    """Format a float to PRICE_DECIMALS places, or empty string if None."""
    if val is None:
        return ""
    return f"{val:.{PRICE_DECIMALS}f}"


def sma_cross_direction(cross_dir: str) -> str:
    """Return 'above', 'below', or 'none' based on SMA 2/SMA 9 cross direction."""
    if cross_dir == "ABOVE":
        return "above"
    elif cross_dir == "BELOW":
        return "below"
    return "none"


def backtest_one(arrow: dict, cfg) -> dict | None:
    """Backtest a single arrow and return a trade record based on SMA cross."""
    arrow_type = arrow["arrow"]  # "green" or "red"
    signal_date_str = arrow["date"]
    timeframe_sec = arrow["timeframeSeconds"]
    bar_index = arrow["barIndex"]
    signal_time_str = arrow["time"]

    bar_objects = load_bars_for_date(signal_date_str, timeframe_sec, cfg)
    if not bar_objects or bar_index >= len(bar_objects):
        return {
            "srNo": arrow["srNo"],
            "date": signal_date_str,
            "time": signal_time_str,
            "timeframe": arrow["timeframe"],
            "arrow": arrow_type,
            "trade_status": "no data",
            "exit_reason": "no bar data available",
            "pnl": None,
            "exit_price": None,
            "entry_price": None,
            "entry_time": "",
        }

    bar = bar_objects[bar_index]
    close = bar.get("close")

    # =========================================================================
    # THE CLOCK: the entry cut-off and the hard exit, both from the recipe
    # =========================================================================
    last_entry_seconds = clock_seconds(cfg.backtest_last_entry)
    hard_exit_seconds = clock_seconds(cfg.backtest_hard_exit)
    entry_epoch = arrow.get("epoch")
    if entry_epoch is None:
        entry_epoch = _epoch_from_ist(signal_date_str, signal_time_str)

    # no entry after the cut-off: the arrow stays in the file (it is a fact about the
    # candles) but nothing is opened on it
    if ist_clock(int(entry_epoch)) > last_entry_seconds:
        return {
            "srNo": arrow["srNo"],
            "date": signal_date_str,
            "time": signal_time_str,
            "timeframe": arrow["timeframe"],
            "arrow": arrow_type,
            "entry_price": "",
            "entry_time": "",
            "exit_price": "",
            "exit_time": "",
            "exit_reason": f"signal after the {cfg.backtest_last_entry} entry cut-off",
            "pnl": None,
            "trade_status": "no entry",
        }

    # =========================================================================
    # ENTRY: at the close of the arrow signal candle
    # =========================================================================
    entry_price = close if close is not None else 0
    entry_time = f"{signal_date_str} {signal_time_str}"

    # Determine initial SMA 2/SMA 9 relationship at entry candle
    entry_bar = bar_objects[bar_index]
    sma2_entry = entry_bar.get("sma2")
    sma9_entry = entry_bar.get("sma9")
    if sma2_entry is not None and sma9_entry is not None:
        if sma2_entry > sma9_entry:
            initial_direction = "above"
        elif sma2_entry < sma9_entry:
            initial_direction = "below"
        else:
            initial_direction = "equal"
    else:
        initial_direction = "unknown"

    # =========================================================================
    # EXIT: find SMA 2/9 cross on subsequent candles
    # =========================================================================
    exit_price = None
    exit_time = None
    exit_reason = ""
    pnl = None

    for i in range(bar_index + 1, len(bar_objects)):
        candle = bar_objects[i]
        candle_epoch = int(candle.get("epoch", candle["time"]))

        # =====================================================================
        # THE HARD EXIT: at the cut-off the book is closed, win or lose. It is
        # tested before the SMA cross on the same candle, because the rule ends
        # the day rather than waiting to see what the next bars would say.
        # =====================================================================
        if ist_clock(candle_epoch) >= hard_exit_seconds:
            exit_price = candle["open"]
            exit_time = ist_full(candle_epoch)
            exit_reason = f"hard exit at {cfg.backtest_hard_exit}"
            pnl = (round(exit_price - entry_price, 2) if arrow_type == "green"
                   else round(entry_price - exit_price, 2))
            break

        sma2 = candle.get("sma2")
        sma9 = candle.get("sma9")
        cross_dir = candle.get("sma2_vs_sma9_cross_direction")

        if sma2 is None or sma9 is None:
            continue

        # Determine current SMA 2/SMA 9 relationship
        if sma2 > sma9:
            current_direction = "above"
        elif sma2 < sma9:
            current_direction = "below"
        else:
            current_direction = "equal"

        # Check for cross
        is_cross = False

        if arrow_type == "green":  # LONG
            # LONG exit: SMA 2 crosses BELOW SMA 9
            # Either cross_dir is BELOW and we were above at entry, OR
            # we transition from above to below
            if cross_dir == "BELOW" and initial_direction == "above":
                is_cross = True
            elif current_direction == "below" and initial_direction == "above":
                is_cross = True

            if is_cross:
                exit_price = candle["close"]
                exit_time = ist_full(candle_epoch)
                exit_reason = "LONG: SMA 2 crossed below SMA 9"
                pnl = round(exit_price - entry_price, 2)
                break

        else:  # SHORT ("red")
            # SHORT exit: SMA 2 crosses ABOVE SMA 9
            if cross_dir == "ABOVE" and initial_direction == "below":
                is_cross = True
            elif current_direction == "above" and initial_direction == "below":
                is_cross = True

            if is_cross:
                exit_price = candle["close"]
                exit_time = ist_full(candle_epoch)
                exit_reason = "SHORT: SMA 2 crossed above SMA 9"
                pnl = round(entry_price - exit_price, 2)
                break

    # a session whose data stops before the hard exit has no 15:15 candle to price; close on
    # the last candle it does have, so no position is ever left open for want of one
    if exit_price is None and bar_objects:
        last = bar_objects[-1]
        last_epoch = int(last.get("epoch", last["time"]))
        if ist_clock(last_epoch) < hard_exit_seconds:
            exit_price = last["close"]
            exit_time = ist_full(last_epoch)
            exit_reason = f"last bar before the {cfg.backtest_hard_exit} hard exit"
            pnl = (round(exit_price - entry_price, 2) if arrow_type == "green"
                   else round(entry_price - exit_price, 2))

    # No cross found
    if exit_price is None:
        return {
            "srNo": arrow["srNo"],
            "date": signal_date_str,
            "time": signal_time_str,
            "timeframe": arrow["timeframe"],
            "arrow": arrow_type,
            "entry_price": entry_price,
            "entry_time": entry_time,
            "exit_price": "",
            "exit_time": "",
            "exit_reason": "no SMA 2/9 cross observed",
            "pnl": None,
            "trade_status": "no cross",
        }

    return {
        "srNo": arrow["srNo"],
        "date": signal_date_str,
        "time": signal_time_str,
        "timeframe": arrow["timeframe"],
        "arrow": arrow_type,
        "entry_price": entry_price,
        "entry_time": entry_time,
        "exit_price": exit_price,
        "exit_time": exit_time or "",
        "exit_reason": exit_reason,
        "pnl": pnl,
        "trade_status": "exited",
    }


def make_report(records: list[dict], cfg) -> str:
    """Produce a text report from the backtest records, with the day's clock stated."""
    total = len(records)
    exited = [r for r in records if r.get("trade_status") == "exited"]
    no_cross = [r for r in records if r.get("trade_status") == "no cross"]
    no_data = [r for r in records if r.get("trade_status") == "no data"]
    no_entry = [r for r in records if r.get("trade_status") == "no entry"]
    hard_exits = [r for r in exited if str(r.get("exit_reason", "")).startswith("hard exit")]

    long_exited = [r for r in exited if r["arrow"] == "green"]
    short_exited = [r for r in exited if r["arrow"] == "red"]

    long_target = [r for r in long_exited if r["pnl"] is not None and r["pnl"] > 0]
    long_loss = [r for r in long_exited if r["pnl"] is not None and r["pnl"] <= 0]
    short_target = [r for r in short_exited if r["pnl"] is not None and r["pnl"] > 0]
    short_loss = [r for r in short_exited if r["pnl"] is not None and r["pnl"] <= 0]

    winning = len(long_target) + len(short_target)
    losing = len(long_loss) + len(short_loss)
    total_pnl = sum((r.get("pnl") or 0) for r in exited)

    # Compute average winning and losing trade amounts
    winning_trades = [r for r in exited if r.get("pnl") is not None and r["pnl"] > 0]
    losing_trades = [r for r in exited if r.get("pnl") is not None and r["pnl"] <= 0]
    avg_win = sum((r.get("pnl") or 0) for r in winning_trades) / len(winning_trades) if len(winning_trades) > 0 else None
    avg_loss = sum((r.get("pnl") or 0) for r in losing_trades) / len(losing_trades) if len(losing_trades) > 0 else None
    # Avoid negative average loss (show as positive number)
    avg_loss_display = abs(avg_loss) if avg_loss is not None else None

    # R multiples (since no fixed R, compute per-trade assuming 1 unit risk)
    r_multiples = [r.get("pnl", 0) / 1.0 for r in exited if r.get("pnl") is not None]
    avg_r = sum(r_multiples, 0.0) / len(r_multiples) if r_multiples else None

    # ---- extended performance metrics ------------------------------------------------
    gross_profit = sum(r["pnl"] for r in winning_trades) if winning_trades else 0.0
    gross_loss = abs(sum(r["pnl"] for r in losing_trades)) if losing_trades else 0.0

    # profit factor: gross profit per unit of gross loss
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

    # expectancy per trade, in points and in R (R = one average loss of risk, since
    # there is no fixed stop to define a unit risk)
    n_exited = len(exited)
    if n_exited > 0 and avg_win is not None and avg_loss_display is not None:
        win_rate = winning / n_exited
        loss_rate = losing / n_exited
        expectancy_pts = win_rate * avg_win - loss_rate * avg_loss_display
        expectancy_r = expectancy_pts / avg_loss_display if avg_loss_display > 0 else None
    else:
        expectancy_pts = expectancy_r = None

    # average win / average loss ratio
    aw_al_ratio = (avg_win / avg_loss_display) if (avg_win is not None
                                                   and avg_loss_display
                                                   and avg_loss_display > 0) else None

    # break-even win rate: the win rate at which expectancy is exactly zero
    # (win_rate * avg_win = (1 - win_rate) * avg_loss)
    if avg_win is not None and avg_loss_display is not None and (avg_win + avg_loss_display) > 0:
        breakeven_rate = avg_loss_display / (avg_win + avg_loss_display)
    else:
        breakeven_rate = None

    lines = []
    lines.append("=" * 60)
    lines.append("SMA CROSS BACKTEST REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Total signals    : {total}")
    lines.append(f"Entry cut-off    : {cfg.backtest_last_entry} IST (later arrows not taken)")
    lines.append(f"Hard exit        : {cfg.backtest_hard_exit} IST (anything open is closed)")
    lines.append(f"Exited trades    : {len(exited)}")
    lines.append(f"  of which hard exits : {len(hard_exits)}")
    lines.append(f"No SMA cross : {len(no_cross)}")
    lines.append(f"No entry (late)   : {len(no_entry)}")
    lines.append(f"No data            : {len(no_data)}")
    lines.append("")
    lines.append("LONG (GREEN) exits:")
    lines.append(f"  SMA 2/9 cross below: {len(long_exited)}")
    lines.append(f"    Winning (price rose): {len(long_target)}")
    lines.append(f"    Losing (price fell) : {len(long_loss)}")
    lines.append("")
    lines.append("SHORT (RED) exits:")
    lines.append(f"  SMA 2/9 cross above: {len(short_exited)}")
    lines.append(f"    Winning (price fell): {len(short_target)}")
    lines.append(f"    Losing (price rose) : {len(short_loss)}")
    lines.append("")
    lines.append("SUMMARY STATISTICS:")
    lines.append(f"  Total signals    : {total}")
    lines.append(f"  Exited trades    : {len(exited)}")
    lines.append(f"    Winning trades : {winning}")
    lines.append(f"    Losing trades  : {losing}")
    if len(exited) > 0:
        lines.append(f"    Win rate       : {winning / len(exited) * 100:.1f}%")
    else:
        lines.append(f"    Win rate       : N/A")
    lines.append(f"    Net P&L        : {fmt(total_pnl)}")
    lines.append(f"    Gross profit   : {fmt(gross_profit)}")
    lines.append(f"    Gross loss     : {fmt(gross_loss)}")
    lines.append(f"    Profit factor  : {fmt(profit_factor) if profit_factor is not None else 'N/A (no losses)'}")
    lines.append(f"    Average winning  : {fmt(avg_win) if avg_win is not None else 'N/A'}")
    lines.append(f"    Average losing   : {fmt(avg_loss_display) if avg_loss_display is not None else 'N/A'}")
    lines.append(f"    Avg win/loss ratio : {fmt(aw_al_ratio) if aw_al_ratio is not None else 'N/A'}")
    lines.append(f"    Average R      : {fmt(avg_r) if avg_r is not None else 'N/A'}")
    lines.append(f"    Expectancy/trade : {fmt(expectancy_pts) if expectancy_pts is not None else 'N/A'} points"
                 f"  ({fmt(expectancy_r) if expectancy_r is not None else 'N/A'} R)")
    lines.append(f"    Break-even win rate : {f'{breakeven_rate * 100:.1f}%' if breakeven_rate is not None else 'N/A'}")
    lines.append(f"    Hard exits at {cfg.backtest_hard_exit} : {len(hard_exits)}")
    lines.append(f"    Skipped (after {cfg.backtest_last_entry}) : {len(no_entry)}")
    lines.append("")
    lines.append("TRADES DETAIL:")
    lines.append(f"  {'srNo':>4s} | {'arrow':>5s} | {'entry':>8s} | {'exit':>8s} | {'reason':>30s} | {'P&L':>8s}")
    for r in exited:
        lines.append(f"  {r['srNo']:4d} | {r['arrow']:>5s} | {fmt(r['entry_price']):>8s} | {fmt(r['exit_price']):>8s} | {r['exit_reason'][:30]:>30s} | {fmt(r['pnl']):>8s}")
    lines.append("")
    lines.append("TRADES BY TYPE:")
    green_count = sum(1 for r in records if r['arrow'] == 'green')
    green_exited = sum(1 for r in records if r['arrow'] == 'green' and r.get('trade_status') == 'exited')
    green_no_cross = sum(1 for r in records if r['arrow'] == 'green' and r.get('trade_status') == 'no cross')
    red_count = sum(1 for r in records if r['arrow'] == 'red')
    red_exited = sum(1 for r in records if r['arrow'] == 'red' and r.get('trade_status') == 'exited')
    red_no_cross = sum(1 for r in records if r['arrow'] == 'red' and r.get('trade_status') == 'no cross')
    lines.append(f"  Green (LONG) signals: {green_count}")
    lines.append(f"    Exited (SMA cross): {green_exited}")
    lines.append(f"    No cross     : {green_no_cross}")
    lines.append(f"  Red (SHORT) signals: {red_count}")
    lines.append(f"    Exited (SMA cross): {red_exited}")
    lines.append(f"    No cross     : {red_no_cross}")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description="Backtest arrow signals with SMA 2/9 cross exit rules"
    )
    ap.add_argument(
        "--input", default=None,
        help="Path to arrow_signal.json (default: <recipe output_dir>/data/arrow_signal.json)"
    )
    ap.add_argument(
        "--output", default=None,
        help="Path to write text report (default: prints to stdout)"
    )
    ap.add_argument(
        "--config", default=None,
        help="Recipe to read the clock and the bar folder from (default: config/nifty.json); "
             "pass config/sensex.json for the SENSEX build"
    )
    args = ap.parse_args()

    cfg = load_config(args.config)
    signal_path = (Path(args.input) if args.input
                   else Path(cfg.paths.data_dir) / "arrow_signal.json")
    if not signal_path.is_file():
        print(f"ERROR: arrow signal file not found: {signal_path}", file=sys.stderr)
        sys.exit(1)

    arrows = load_arrow_signal(signal_path)
    print(f"Loaded {len(arrows)} arrow signals from {signal_path}")
    print(f"Recipe: {cfg.source if cfg.source else 'built-in defaults'}")
    print(f"Bars: {cfg.paths.data_dir}  |  clock: entries until {cfg.backtest_last_entry}, "
          f"hard exit {cfg.backtest_hard_exit} IST")
    print()

    records = []
    for arrow in arrows:
        rec = backtest_one(arrow, cfg)
        if rec is not None:
            records.append(rec)

    report_text = make_report(records, cfg)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"Report written to {args.output}")
    else:
        print(report_text)


if __name__ == "__main__":
    main()