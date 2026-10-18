"""
nifty.output
=============

Everything that leaves a build.

    exports.py  the CSV and JSON writers -- the header, the rows and the sheet's frame come
                from one column list, so they cannot drift apart
    meta.py     the recipe blocks the artifacts carry as JSON, built from the rule objects
    sheet.py    the self-contained HTML sheet and its payload

One home per artifact: a number that appears in the sheet appears in the exports because
both read the same payload, not because a second writer was kept in step by hand.
"""
