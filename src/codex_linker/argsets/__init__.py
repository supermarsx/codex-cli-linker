"""Aggregated CLI argument groups (argsets).

This package provides small, focused helpers to attach related groups of
arguments to an ``argparse.ArgumentParser``. It mirrors the structure of the
``prompts`` module: independent, importable helpers that keep ``args.py``
minimal and easy to read.

Public helpers:
  - add_general_args(parser)
  - add_model_args(parser)
  - add_provider_args(parser), SetProviderAction
  - add_profile_args(parser)
  - add_mcp_args(parser)
  - add_file_mgmt_args(parser)
  - add_other_args(parser)
"""

from __future__ import annotations

from .general import add_general_args
from .model import add_model_args
from .providers import add_provider_args, SetProviderAction
from .profiles import add_profile_args
from .mcp import add_mcp_args
from .files import add_file_mgmt_args
from .other import add_other_args
from .backups import add_backup_args

__all__ = [
    "add_general_args",
    "add_model_args",
    "add_provider_args",
    "SetProviderAction",
    "add_profile_args",
    "add_mcp_args",
    "add_file_mgmt_args",
    "add_other_args",
    "add_backup_args",
]
