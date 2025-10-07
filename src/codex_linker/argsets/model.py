"""Argument definitions: Model selection and runtime model behavior.

This module contains flags that influence model choice, context window,
token limits, reasoning metadata, and related toggles.
"""

from __future__ import annotations

import argparse


def _has_option(p: argparse.ArgumentParser, opt: str) -> bool:
    try:
        return any(opt in (a.option_strings or []) for a in p._actions)
    except Exception:
        return False


def add_model_args(p: argparse.ArgumentParser) -> None:
    """Attach model-related arguments to the parser.

    Covers model id or index selection, context window/max output tokens, and
    UX metadata such as reasoning effort/summary, verbosity, and whether to
    hide/show agent reasoning streams.
    """
    # If '-m' already present, assume model group is attached
    if _has_option(p, "-m"):
        return
    model_opts = p.add_argument_group("Model options")
    model_opts.add_argument("-m", "--model", help="Model id to use (skip model picker)")
    model_opts.add_argument(
        "-i",
        "--model-index",
        type=int,
        help="When auto-selecting, index into the models list (default 0)",
    )
    model_opts.add_argument(
        "-w",
        "--model-context-window",
        type=int,
        default=0,
        help="Context window tokens",
    )
    model_opts.add_argument(
        "-t", "--model-max-output-tokens", type=int, default=0, help="Max output tokens"
    )
    model_opts.add_argument(
        "-r",
        "--reasoning-effort",
        default="low",
        choices=["minimal", "low", "medium", "high"],
        help="model_reasoning_effort (spec)",
    )
    model_opts.add_argument(
        "-u",
        "--reasoning-summary",
        default="auto",
        choices=["auto", "concise", "detailed", "none"],
        help="model_reasoning_summary (spec)",
    )
    model_opts.add_argument(
        "-B",
        "--verbosity",
        default="medium",
        choices=["low", "medium", "high"],
        help="model_verbosity (spec)",
    )
    model_opts.add_argument(
        "-g",
        "--hide-agent-reasoning",
        action="store_true",
        help="Hide agent reasoning messages",
    )
    model_opts.add_argument(
        "-G",
        "--show-raw-agent-reasoning",
        action="store_true",
        help="Show raw agent reasoning messages",
    )
    model_opts.add_argument(
        "-Y",
        "--model-supports-reasoning-summaries",
        action="store_true",
        help="Indicate model supports reasoning summaries",
    )


__all__ = ["add_model_args"]
