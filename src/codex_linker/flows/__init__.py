"""High-level flow helpers extracted from the monolithic main_flow.

These functions mirror the former inline sections in main_flow.py to keep the
entrypoint small and focused while preserving behavior. Each helper is a thin
wrapper around existing prompts/utils to avoid duplicating logic.
"""

from __future__ import annotations

from .startup import (
    handle_early_exits,
    maybe_run_update_check,
)
from .stateflow import (
    select_state_path,
    load_and_apply_state,
)
from .provider_flow import (
    determine_base_and_provider,
    maybe_prompt_openai_auth_method,
    set_profile_and_api_key,
    maybe_prompt_and_store_openai_key,
)
from .model_flow import choose_model
from .context_flow import maybe_detect_context_window
from .summary_flow import print_summary_and_hints
from .editor_flow import maybe_run_interactive_editor, maybe_post_editor_management

__all__ = [
    "handle_early_exits",
    "maybe_run_update_check",
    "select_state_path",
    "load_and_apply_state",
    "determine_base_and_provider",
    "maybe_prompt_openai_auth_method",
    "set_profile_and_api_key",
    "maybe_prompt_and_store_openai_key",
    "choose_model",
    "maybe_detect_context_window",
    "print_summary_and_hints",
    "maybe_run_interactive_editor",
    "maybe_post_editor_management",
]
