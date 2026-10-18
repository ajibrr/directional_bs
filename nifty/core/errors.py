"""
nifty.core.errors
============

The three failures the pipeline distinguishes, so the command line can report each
one in a sentence instead of a traceback:

    PipelineError   base class -- anything the CLI already knows how to print
    ConfigError     the recipe (config file / --set) cannot describe a build
    DataError       an input tape is missing, empty or unreadable
"""

from __future__ import annotations


class PipelineError(Exception):
    """Base class for the failures the pipeline reports to the user."""


class ConfigError(PipelineError):
    """A configuration file or command-line override is not usable."""


class DataError(PipelineError):
    """An input session file is missing, empty or malformed."""
