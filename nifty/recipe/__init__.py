"""
nifty.recipe
=============

The recipe: the built-in defaults with their section/key map, and the reader that
turns a TOML or JSON file plus command-line overrides into one validated `Config`.

Nothing downstream reads a file, an environment variable or an argument -- it reads the
`Config` this package hands it, which is what makes a build reproducible from its recipe.
"""
