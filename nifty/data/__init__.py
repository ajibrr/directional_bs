"""
nifty.data
===========

Session in, bars out.

    discovery and tick reading   bars.py      a tape, or a dashboard's `nifty_seconds`
    the dashboard join           flow.py      the minute CE / PE OI change beside the bars
    the ordered analysis steps   analysis.py  the extension point for a new column
    the build itself             pipeline.py  one session -> exports, sheet frame, summary

The steps read a list of bar dicts and add columns to it; nothing here knows what a chart
or a CSV looks like.
"""
