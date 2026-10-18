"""
nifty.trade
============

The backtest: one trade per arrow, booked against the day's own clock.

    backtest.py  entry at the signal candle's close, exit on the SMA 2/9 cross, no entry
                 after `[backtest] last_entry`, and a hard exit at `[backtest] hard_exit`
                 that closes whatever is still open at that candle's opening price

It reads the arrow signal from the recipe's own output tree
(`<paths.output_dir>/data/arrow_signal.json`, `output/nifty` by default), so a trade is
always a trade in the arrows the sheet draws.
"""
