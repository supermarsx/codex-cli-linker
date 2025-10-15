"""Argument definitions: MCP servers.

This module provides flags to manage MCP server entries and a compact JSON
input path for automation.
"""

from __future__ import annotations

import argparse


def _has_option(p: argparse.ArgumentParser, opt: str) -> bool:
    try:
        return any(opt in (a.option_strings or []) for a in p._actions)
    except Exception:
        return False


def add_mcp_args(p: argparse.ArgumentParser) -> None:
    """Attach MCP server arguments to the parser.

    Supports an interactive manager and ``--mcp-json`` which accepts a JSON
    object mapping names to entries of the form:
      {"command": "npx", "args": ["-y", "mcp-server"], "env": {"KEY": "VAL"}}
    """
    if _has_option(p, "-mm"):
        return
    mcp = p.add_argument_group("MCP servers")
    mcp.add_argument(
        "-mm",
        "--manage-mcp",
        action="store_true",
        help="Interactive: add/remove/edit mcp_servers entries before writing",
    )
    mcp.add_argument(
        "-mj",
        "--mcp-json",
        help=(
            'JSON object for mcp_servers (e.g., \'{"srv": {"command": "npx", "args": ["-y", "mcp-server"], "env": {"API_KEY": "v"}}}\')'
        ),
    )


__all__ = ["add_mcp_args"]
