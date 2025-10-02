from __future__ import annotations

from typing import List, Dict, Any

from ..ui import c, BOLD, CYAN, GRAY, info, warn, ok, clear_screen
from .input_utils import prompt_choice, _input_list_json, _input_env_kv, fmt


def manage_mcp_servers_interactive(args) -> None:
    """Interactive editor for args.mcp_servers (top-level mcp_servers)."""

    def list_servers() -> List[str]:
        return sorted(list((args.mcp_servers or {}).keys()))

    while True:
        if not getattr(args, "continuous", False):
            try:
                clear_screen()
            except Exception:
                pass
        names = list_servers()
        print()
        print(c(fmt("MCP servers 🧰:"), BOLD))
        if not names:
            info("(none)")
        else:
            for n in names:
                curr = dict((args.mcp_servers or {}).get(n) or {})
                cmd = curr.get("command", "npx")
                a = curr.get("args") or ["-y", "mcp-server"]
                env = curr.get("env") or {}
                to_ms = curr.get("startup_timeout_ms", 10000)
                print(c(f" - {n}", CYAN))
                print(c(f"    command: {cmd}", GRAY))
                print(c(f"    args: {', '.join(a)}", GRAY))
                if env:
                    kv = ", ".join(f"{k}={v}" for k, v in env.items())
                    print(c(f"    env: {kv}", GRAY))
                print(c(f"    startup_timeout_ms: {to_ms}", GRAY))
        i = prompt_choice(
            "Choose",
            [
                "Add server ➕",
                "Edit server ✏️",
                "Remove server 🗑️",
                fmt("🏠 Back to main menu"),
            ],
        )
        if not getattr(args, "continuous", False):
            try:
                clear_screen()
            except Exception:
                pass
        if i == 0:
            name = input("Server name (identifier): ").strip()
            if not name:
                continue
            entry: Dict[str, Any] = {
                "command": "npx",
                "args": ["-y", "mcp-server"],
                "env": {},
            }
            _edit_mcp_entry_interactive(args, name, entry, creating=True)
        elif i == 1:
            if not names:
                warn("No servers to edit.")
                continue
            idx = prompt_choice("Edit which?", names)
            name = names[idx]
            curr = dict((args.mcp_servers or {}).get(name) or {})
            _edit_mcp_entry_interactive(
                args,
                name,
                curr or {"command": "npx", "args": ["-y", "mcp-server"], "env": {}},
                creating=False,
            )
        elif i == 2:
            if not names:
                warn("No servers to remove.")
                continue
            idx = prompt_choice("Remove which?", names)
            name = names[idx]
            m = dict(args.mcp_servers or {})
            m.pop(name, None)
            args.mcp_servers = m
            info(f"Removed mcp server '{name}'")
        elif i == 3:
            return


def _edit_mcp_entry_interactive(
    args, name: str, entry: Dict[str, Any], creating: bool
) -> None:
    curr = dict(entry)
    while True:
        print()
        print(c(f"Edit MCP server [{name}]", BOLD))
        items = [
            ("Command", curr.get("command", "npx")),
            (
                "Args (JSON array)",
                __import__("json").dumps(curr.get("args") or ["-y", "mcp-server"]),
            ),
            (
                "Env (CSV KEY=VAL)",
                ", ".join(f"{k}={v}" for k, v in (curr.get("env") or {}).items()),
            ),
            ("Startup timeout (ms)", str(curr.get("startup_timeout_ms", 10000))),
        ]
        for i, (lbl, val) in enumerate(items, 1):
            print(f"  {i}. {lbl}: {val}")
        act = prompt_choice(
            "Action",
            ["Edit field ✏️", "Save 💾", "Cancel ❎", fmt("🏠 Back to main menu")],
        )
        if not getattr(args, "continuous", False):
            try:
                clear_screen()
            except Exception:
                pass
        if act == 0:
            s = input("Field number: ").strip()
            if not s.isdigit():
                continue
            idx = int(s) - 1
            if idx == 0:
                curr["command"] = input("Command: ").strip() or curr.get(
                    "command", "npx"
                )
            elif idx == 1:
                curr["args"] = _input_list_json(
                    'Args JSON array (e.g., ["-y", "mcp-server"]): ',
                    curr.get("args") or ["-y", "mcp-server"],
                )
            elif idx == 2:
                curr["env"] = _input_env_kv(
                    "Env CSV (KEY=VAL,...): ", curr.get("env") or {}
                )
            elif idx == 3:
                try:
                    curr["startup_timeout_ms"] = int(
                        input("Startup timeout (ms): ").strip() or "10000"
                    )
                except Exception:
                    pass
        elif act == 1:
            args.mcp_servers = dict(args.mcp_servers or {})
            args.mcp_servers[name] = curr
            if creating:
                ok(f"Added mcp server '{name}'")
            else:
                ok(f"Updated mcp server '{name}'")
            return
        elif act == 3:
            raise KeyboardInterrupt
        else:
            return
