#!/usr/bin/env python3
"""nanoclaw.__main__ - Package entry point for `python -m nanoclaw`."""

from .cli import run_repl

if __name__ == "__main__":
    run_repl()