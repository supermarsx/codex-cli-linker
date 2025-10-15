"""Final summary and hint printing.

Collects the output responsibilities at the end of a successful run so the
main entrypoint can remain focused on flow control. Shows the target paths,
selected profile/provider/model, and any optional editor/launch commands.
"""

from __future__ import annotations

from pathlib import Path
from ..ui import c, CYAN, ok, info


def print_summary_and_hints(args, state, *, config_toml: Path) -> None:
    """Print final summary and optional open/launch hints."""
    print()
    ok(
        f"Configured profile '{state.profile}' using provider '{state.provider}' → {state.base_url} (model: {state.model})"
    )
    info("Summary:")
    print(c(f"  target: {config_toml}", CYAN))
    try:
        last_bak = max(config_toml.parent.glob("config.toml.*.bak"), default=None)
    except Exception:
        last_bak = None
    if last_bak:
        print(c(f"  backup: {last_bak}", CYAN))
    print(c(f"  profile: {state.profile}", CYAN))
    print(c(f"  provider: {state.provider}", CYAN))
    print(c(f"  model: {state.model}", CYAN))
    print(c(f"  context_window: {args.model_context_window or 0}", CYAN))
    print(c(f"  max_output_tokens: {args.model_max_output_tokens or 0}", CYAN))
    info("Run Codex manually with:")
    print(c(f"  npx codex --profile {state.profile}", CYAN))
    print(c(f"  codex --profile {state.profile}", CYAN))

    if getattr(args, "open_config", False):
        opener = (args.file_opener or "vscode").strip().lower()
        if opener == "vscode-insiders":
            cmd = f'code-insiders "{config_toml}"'
        else:
            cmd = f'code "{config_toml}"'
        info("Open config in your editor:")
        print(c(f"  {cmd}", CYAN))

    if getattr(args, "_guided_action", "") == "write_and_launch":
        info("Launch Codex manually with:")
        print(c(f"  npx codex --profile {state.profile}", CYAN))
        print(c(f"  codex --profile {state.profile}", CYAN))
