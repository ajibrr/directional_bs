"""
nifty
=====

A config-driven pipeline: 1-second NIFTY ticks -> multi-timeframe OHLC bars -> SMA
analytics -> one self-contained HTML sheet plus its CSV/JSON exports.

    from nifty import build, load_config
    build(load_config())                    # config/nifty.json, or the built-in defaults

One recipe in, one folder of artifacts out. Nothing in the package reads a global, an
environment variable or a command-line argument except `nifty.cli`, so a build is
reproducible from its recipe. The package is six folders, each reading only the ones
above it:

    core/       errors, model, numeric, clock, keys   the vocabulary -- no policy
    recipe/     defaults, config                     the recipe -> one Config
    data/       bars, flow, analysis, pipeline       session in, columns out
    signals/    series, rules, stats                 what the columns mean
    output/     exports, meta, sheet                 everything that leaves the build
    trade/      backtest                             arrows -> trades, per the clock
    cli.py                                           the command line
"""

from __future__ import annotations

from .recipe.config import Config, ConfigError, load_config
from .core.errors import DataError, PipelineError
from .core.model import Build, Day
from .data.pipeline import build

__version__ = "2.0"

__all__ = ["Config", "ConfigError", "DataError", "PipelineError", "Build", "Day",
           "build", "load_config", "__version__"]
