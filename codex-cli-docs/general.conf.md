| `model`                   | string                                                   | Model to use (e.g., `gpt-5-codex`).                     |
| ------------------------- | -------------------------------------------------------- | ------------------------------------------------------- |
| `model_provider`          | string                                                   | Provider id from `model_providers` (default: `openai`). |
| `model_context_window`    | number                                                   | Context window tokens.                                  |
| `model_max_output_tokens` | number                                                   | Max output tokens.                                      |
| `approval_policy`         | `untrusted` \| `on-failure` \| `on-request` \| `never`   | When to prompt for approval.                            |
| `sandbox_mode`            | `read-only` \| `workspace-write` \| `danger-full-access` | OS sandbox policy.                                      |

| `model`                   | string                                                   | Model to use (e.g., `gpt-5-codex`).                     |
| ------------------------- | -------------------------------------------------------- | ------------------------------------------------------- |
| `model_provider`          | string                                                   | Provider id from `model_providers` (default: `openai`). |
| `model_context_window`    | number                                                   | Context window tokens.                                  |
| `model_max_output_tokens` | number                                                   | Max output tokens.                                      |
| `approval_policy`         | `untrusted` \| `on-failure` \| `on-request` \| `never`   | When to prompt for approval.                            |
| `sandbox_mode`            | `read-only` \| `workspace-write` \| `danger-full-access` | OS sandbox policy.                                      |

| `project_doc_max_bytes` | number | Max bytes to read from `AGENTS.md`. |
| ----------------------- | ------ | ----------------------------------- |
| `profile`               | string | Active profile name.                |

| `history.persistence`                           | `save-all` \| `none`                                              | History file persistence (default: `save-all`).           |
| ----------------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------- |
| `history.max_bytes`                             | number                                                            | Currently ignored (not enforced).                         |
| `file_opener`                                   | `vscode` \| `vscode-insiders` \| `windsurf` \| `cursor` \| `none` | URI scheme for clickable citations (default: `vscode`).   |
| `tui`                                           | table                                                             | TUI‑specific options.                                     |
| `tui.notifications`                             | boolean \| array                                                  | Enable desktop notifications in the tui (default: false). |
| `hide_agent_reasoning`                          | boolean                                                           | Hide model reasoning events.                              |
| `show_raw_agent_reasoning`                      | boolean                                                           | Show raw reasoning (when available).                      |
| `model_reasoning_effort`                        | `minimal` \| `low` \| `medium` \| `high`                          | Responses API reasoning effort.                           |
| `model_reasoning_summary`                       | `auto` \| `concise` \| `detailed` \| `none`                       | Reasoning summaries.                                      |
| `model_verbosity`                               | `low` \| `medium` \| `high`                                       | GPT‑5 text verbosity (Responses API).                     |
| `model_supports_reasoning_summaries`            | boolean                                                           | Force‑enable reasoning summaries.                         |
| `model_reasoning_summary_format`                | `none` \| `experimental`                                          | Force reasoning summary format.                           |
| `chatgpt_base_url`                              | string                                                            | Base URL for ChatGPT auth flow.                           |
| `experimental_resume`                           | string (path)                                                     | Resume JSONL path (internal/experimental).                |
| `experimental_instructions_file`                | string (path)                                                     | Replace built‑in instructions (experimental).             |
| `experimental_use_exec_command_tool`            | boolean                                                           | Use experimental exec command tool.                       |
| `responses_originator_header_internal_override` | string                                                            | Override `originator` header value.                       |

| `tools.web_search` | boolean | Enable web search tool (alias: `web_search_request`) (default: false). |
| ------------------ | ------- | ---------------------------------------------------------------------- |

Notes (interactive editor semantics):
- Most fields support Enter to skip (no change) and the literal `null` to clear (set to empty string or unset as applicable).
- `notify` is accepted as a JSON array in prompts (e.g., `["-y", "mcp-server"]`), with quoted values.
- The editor exposes common `file_opener` options for convenience.
