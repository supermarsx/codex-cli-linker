| `model_providers.<id>.name`                   | string                | Display name.                                   |
| --------------------------------------------- | --------------------- | ----------------------------------------------- |
| `model_providers.<id>.base_url`               | string                | API base URL.                                   |
| `model_providers.<id>.env_key`                | string                | Env var for API key.                            |
| `model_providers.<id>.wire_api`               | `chat` \| `responses` | Protocol used (default: `chat`).                |
| `model_providers.<id>.query_params`           | map<string,string>    | Extra query params (e.g., Azure `api-version`). |
| `model_providers.<id>.http_headers`           | map<string,string>    | Additional static headers.                      |
| `model_providers.<id>.env_http_headers`       | map<string,string>    | Headers sourced from env vars.                  |
| `model_providers.<id>.request_max_retries`    | number                | Per‑provider HTTP retry count (default: 4).     |
| `model_providers.<id>.stream_max_retries`     | number                | SSE stream retry count (default: 5).            |
| `model_providers.<id>.stream_idle_timeout_ms` | number                | SSE idle timeout (ms) (default: 300000).        |

Notes (interactive editor semantics):
- For string fields, pressing Enter keeps the current value; typing `null` clears the value (empty string). For maps, `null` clears to `{}`.
- Headers input supports CSV `KEY=VAL` for static headers and CSV `KEY=ENVVAR` for env headers.
- Query params accept a brace-style object in prompts (e.g., `{api-version="2025-04-01-preview"}`), and values should be quoted.
