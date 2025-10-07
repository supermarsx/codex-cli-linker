"""Prompt helpers and interactive flows (facade).

Re-exports commonly used prompt utilities and interactive flows so callers can
import from ``codex_linker.prompts`` directly. Keep this module declarative —
actual implementations live in the sibling modules.
"""

from __future__ import annotations

from .input_utils import prompt_choice, prompt_yes_no, _safe_input  # re-export
from .base_pick import (
    pick_base_url,
    pick_model_interactive,
    interactive_prompts,
    _call_detect_base_url,
)
from .hub import interactive_settings_editor
from .profiles import manage_profiles_interactive
from .mcp import manage_mcp_servers_interactive
from .providers import manage_providers_interactive

__all__ = [
    "prompt_choice",
    "prompt_yes_no",
    "_safe_input",
    "pick_base_url",
    "pick_model_interactive",
    "interactive_prompts",
    "_call_detect_base_url",
    "interactive_settings_editor",
    "manage_profiles_interactive",
    "manage_mcp_servers_interactive",
    "manage_providers_interactive",
]
