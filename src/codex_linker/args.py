from __future__ import annotations
import argparse
import sys
from typing import List, Optional


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments, tracking which were explicitly provided."""
    epilog = (
        "Shortcuts:\n"
        "  Providers: -oa/--openai, -oA/--openai-api, -og/--openai-gpt, -ls/--lmstudio, -ol/--ollama, -vl/--vllm, -tg/--tgwui, -ti/--tgi,\n"
        "             -or/--openrouter, -an/--anthropic, -gq/--groq, -mi/--mistral, -ds/--deepseek, -ch/--cohere, -bt/--baseten, -al/--anythingllm, -jn/--jan, -lc/--llamacpp, -kb/--koboldcpp\n"
        "  Guided: --guided (start guided pipeline), --no-emojis (hide emojis).\n"
    )
    p = argparse.ArgumentParser(
        description="Codex CLI Linker",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=epilog,
    )

    # Attach groups via argsets to keep this file concise and conflict-free
    from .argsets import (
        add_general_args as _add_general_args,
        add_model_args as _add_model_args,
        add_provider_args as _add_provider_args,
        add_profile_args as _add_profile_args,
        add_mcp_args as _add_mcp_args,
        add_file_mgmt_args as _add_file_mgmt_args,
        add_other_args as _add_other_args,
        add_backup_args as _add_backup_args,
    )

    _add_general_args(p)
    _add_model_args(p)
    _add_provider_args(p)
    _add_profile_args(p)
    _add_mcp_args(p)
    _add_file_mgmt_args(p)
    _add_other_args(p)
    _add_backup_args(p)

    if argv is None:
        argv = sys.argv[1:]
    ns = p.parse_args(argv)
    # Initialize mcp servers container
    ns.mcp_servers = {}
    # Initialize per-profile overrides container (interactive-only)
    ns.profile_overrides = {}
    if getattr(ns, "mcp_json", None):
        try:
            import json

            data = json.loads(ns.mcp_json)
            if isinstance(data, dict):
                ns.mcp_servers = data
        except Exception:
            pass
    # Azure resource/path can synthesize base URL when given
    if getattr(ns, "azure", False):
        if getattr(ns, "azure_resource", None) or getattr(ns, "azure_path", None):
            res = getattr(ns, "azure_resource", "") or ""
            path = getattr(ns, "azure_path", "openai/v1") or "openai/v1"
            if res and not getattr(ns, "base_url", None):
                ns.base_url = f"https://{res}.openai.azure.com/{path}"
    # Normalize providers list
    provs = []
    if getattr(ns, "providers", None):
        provs = [p.strip() for p in str(ns.providers).split(",") if p.strip()]
    ns.providers_list = provs
    ns._explicit = {
        a.dest
        for a in p._actions
        if any(
            opt in argv or any(arg.startswith(opt + "=") for arg in argv)
            for opt in a.option_strings
        )
    }
    # True when invoked without any CLI arguments
    ns._no_args = len(argv) == 0
    return ns


__all__ = ["parse_args"]
