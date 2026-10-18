"""
nifty.signals
==============

What the bars mean: the derived series, the two arrow rules, and the statistics blocks.

    series.py   moving averages, change (%), run lengths, the direction streak, the two
                crossing rows and the above/below relationship
    rules.py    one arrow rule, its mirror, and the per-condition funnel
    stats.py    the per-timeframe and per-session summaries every export and the sheet read

The only *decisions* in the pipeline live here: the rest of the package writes columns and
moves data. Each condition names the column it reads, so the rule and the table cannot
describe different things.
"""
