from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .detect import detect_base_url
from .logging_utils import log_event
from .ui import c, info, ok, warn, err, GREEN, RED

_DOCTOR_TIMEOUT = 3.0
_DOCTOR_PROMPT = "ping"


@dataclass
class CheckResult:
    name: str
    success: bool
    detail: str = ""


def run_doctor(
    args,
    home: Path,
    config_targets: Sequence[Path],
    *,
    state,
    timeout: float = _DOCTOR_TIMEOUT,
) -> int:
    """Run connectivity and filesystem diagnostics.

    Returns ``0`` on success, ``1`` when any check fails."""

    info("Running doctor preflight checks...")
    checks: List[CheckResult] = []

    base_source = ""
    base_url = (getattr(args, "base_url", None) or "").strip() or ""
    if base_url:
        base_source = "command line"
    else:
        saved = getattr(state, "base_url", "")
        if saved:
            base_url = saved.strip()
            base_source = "saved state"
        else:
            detected = detect_base_url()
            if detected:
                base_url = detected.strip()
                base_source = "auto-detected"

    if base_url:
        checks.append(
            CheckResult(
                "Resolve base URL", True, f"{base_source or 'provided'}: {base_url}"
            )
        )
    else:
        checks.append(
            CheckResult(
                "Resolve base URL",
                False,
                "Provide --base-url, set it in state, or ensure auto-detectable server",
            )
        )

    auth_token = (
        getattr(args, "api_key", None) or getattr(state, "api_key", "") or ""
    ).strip()
    headers: Dict[str, str] = {}
    if auth_token and auth_token.upper() != "NULLKEY":
        headers["Authorization"] = f"Bearer {auth_token}"

    models: List[str] = []

    if base_url:
        success, detail = _probe_base_url(base_url, headers, timeout)
    else:
        success, detail = False, "Skipped (no base URL)"
    checks.append(CheckResult("Probe base URL", success, detail))

    if success:
        models_success, models, models_detail = _probe_models(
            base_url, headers, timeout
        )
    else:
        models_success, models_detail = False, "Skipped (base URL check failed)"
    checks.append(CheckResult("Fetch /models", models_success, models_detail))

    model_for_chat = (
        getattr(args, "model", None)
        or getattr(state, "model", None)
        or (models[0] if models else None)
    )
    if not models_success:
        chat_success, chat_detail = False, "Skipped (no models)"
    elif not model_for_chat:
        chat_success, chat_detail = False, "No model available for chat completion"
    else:
        chat_success, chat_detail = _probe_chat_echo(
            base_url, model_for_chat, headers, timeout
        )
    checks.append(CheckResult("Chat completion echo", chat_success, chat_detail))

    # Track optional capabilities we discover so the CLI can suggest matching flags.
    feature_suggestions: List[str] = []
    feature_status: Optional[Dict[str, bool]] = None
    if getattr(args, "doctor_detect_features", False):
        if chat_success:
            feature_check, feature_status, feature_suggestions = _probe_feature_support(
                base_url, model_for_chat, headers, timeout
            )
            checks.append(feature_check)
            log_event(
                "doctor_feature_probe",
                supported=feature_status,
                base_url=base_url or "",
                model=model_for_chat or "",
            )
        else:
            checks.append(
                CheckResult("Feature probing", False, "Skipped (chat check failed)")
            )
            log_event("doctor_feature_probe", supported=None, skipped=True)
    else:
        feature_status = None

    fs_success, fs_detail = _probe_filesystem(home, config_targets)
    checks.append(CheckResult("Filesystem write access", fs_success, fs_detail))

    _print_results(checks)

    if getattr(args, "doctor_detect_features", False) and feature_suggestions:
        unique_suggestions = list(dict.fromkeys(feature_suggestions))
        info("Feature suggestions: " + "; ".join(unique_suggestions))

    if all(check.success for check in checks):
        ok("Doctor checks passed. You're ready to generate configs.")
        return 0
    err("Doctor detected issues. See checklist above for details.")
    return 1


def _probe_base_url(
    base_url: str, headers: Dict[str, str], timeout: float
) -> Tuple[bool, str]:
    req = urllib.request.Request(base_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", getattr(resp, "code", 0))
            return True, f"HTTP {status or 200}"
    except urllib.error.HTTPError as exc:
        return True, f"HTTP {exc.code} ({exc.reason or 'response'})"
    except Exception as exc:  # pragma: no cover - networking exceptions vary
        return False, str(exc)


def _probe_models(
    base_url: str,
    headers: Dict[str, str],
    timeout: float,
) -> Tuple[bool, List[str], str]:
    url = base_url.rstrip("/") + "/models"
    data, error = _http_get_json(url, headers, timeout)
    if data and isinstance(data.get("data"), list):
        models = [
            item.get("id")
            for item in data["data"]
            if isinstance(item, dict) and item.get("id")
        ]
        if models:
            return (
                True,
                models,
                f"{len(models)} model(s): {', '.join(models[:5])}"
                + ("..." if len(models) > 5 else ""),
            )
        return False, [], "No models returned"
    return False, [], error or "Unexpected response"


def _probe_chat_echo(
    base_url: str,
    model_id: str,
    headers: Dict[str, str],
    timeout: float,
) -> Tuple[bool, str]:
    url = base_url.rstrip("/") + "/chat/completions"
    attempts = [
        {"messages": [{"role": "user", "content": _DOCTOR_PROMPT}]},
        {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": _DOCTOR_PROMPT}]}
            ]
        },
    ]
    errors: List[str] = []
    for extra in attempts:
        payload = {
            "model": model_id,
            "max_tokens": 16,
            "temperature": 0,
            "stream": False,
            **extra,
        }
        data, error = _http_post_json(url, payload, headers, timeout)
        success, detail = _parse_chat_response(data, error)
        if success:
            return True, detail
        if detail:
            errors.append(detail)
    comp_url = base_url.rstrip("/") + "/completions"
    comp_payload = {
        "model": model_id,
        "prompt": _DOCTOR_PROMPT,
        "max_tokens": 16,
        "temperature": 0,
        "stream": False,
    }
    data, error = _http_post_json(comp_url, comp_payload, headers, timeout)
    success, detail = _parse_completions_response(data, error)
    if success:
        return True, detail
    if detail:
        errors.append(detail)
    joined = "; ".join(err for err in errors if err)
    return False, joined or (error or "Chat/completions failed")

    return False, joined or (error or "Chat/completions failed")


def _probe_feature_support(
    base_url: str,
    model_id: str,
    headers: Dict[str, str],
    timeout: float,
) -> Tuple[CheckResult, Dict[str, bool], List[str]]:
    url = base_url.rstrip("/") + "/chat/completions"
    base_payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": _DOCTOR_PROMPT}],
        "max_tokens": 1,
        "temperature": 0,
        "stream": False,
    }
    # Probe a minimal payload for each optional field we surface in the CLI.
    features = [
        ("tool_choice", {"tool_choice": "none"}),
        ("response_format", {"response_format": {"type": "json_object"}}),
        ("reasoning", {"reasoning": {"effort": "low"}}),
    ]
    supported: Dict[str, bool] = {}
    details: List[str] = []
    for name, extra in features:
        payload = {**base_payload, **extra}
        data, error = _http_post_json(url, payload, headers, timeout)
        success, detail = _parse_chat_response(data, error)
        supported[name] = success
        if success:
            details.append(f"{name}: ok")
        else:
            msg = detail or error or "unsupported"
            msg = (msg or "unsupported")[:60]
            details.append(f"{name}: {msg}")
    suggestions: List[str] = []
    if supported.get("tool_choice"):
        suggestions.append("wire_api=chat")
    else:
        suggestions.append("wire_api=completions")
    if supported.get("response_format"):
        suggestions.append("enable --response-format json")
    if supported.get("reasoning"):
        suggestions.append("enable --model-supports-reasoning-summaries")
        suggestions.append("leave --hide-agent-reasoning disabled")
    else:
        suggestions.append("set --hide-agent-reasoning")
    check = CheckResult("Feature probing", all(supported.values()), "; ".join(details))
    return check, supported, suggestions


def _parse_chat_response(data, error):
    if not data:
        return False, error or "No response"
    if isinstance(data, dict) and data.get("error"):
        message = None
        if isinstance(data.get("error"), dict):
            message = data.get("error", {}).get("message")
        return False, message or error or "Chat error"
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or not choices:
        return False, "Response missing choices"
    choice0 = choices[0] if isinstance(choices[0], dict) else {}
    message = choice0.get("message") if isinstance(choice0, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    text_content = _extract_text(content)
    if text_content:
        snippet = text_content.replace("\n", " ").replace("\r", " ").strip()
        if len(snippet) > 60:
            snippet = snippet[:57] + "..."
        return True, f"Received reply: {snippet}"
    return False, "First choice has no text content"


def _parse_completions_response(data, error):
    if not data:
        return False, error or "No response"
    if isinstance(data, dict) and data.get("error"):
        message = None
        if isinstance(data.get("error"), dict):
            message = data.get("error", {}).get("message")
        return False, message or error or "Completion error"
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or not choices:
        return False, "Response missing choices"
    choice0 = choices[0] if isinstance(choices[0], dict) else {}
    text = choice0.get("text") if isinstance(choice0, dict) else None
    if isinstance(text, str) and text.strip():
        snippet = text.strip().replace("\n", " ").replace("\r", " ").strip()
        if len(snippet) > 60:
            snippet = snippet[:57] + "..."
        return True, f"Received completion: {snippet}"
    return False, "First choice has no text content"


def _extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        if parts:
            return " ".join(parts)
    return None


def _probe_filesystem(home: Path, targets: Sequence[Path]) -> Tuple[bool, str]:
    temp_files: List[Path] = []
    try:
        home.mkdir(parents=True, exist_ok=True)
        tmp = home / ".doctor_write_test"
        tmp.write_text("ok", encoding="utf-8")
        temp_files.append(tmp)
        for target in targets:
            if not target:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            marker = target.parent / f".{target.name}.doctor"
            marker.write_text("ok", encoding="utf-8")
            temp_files.append(marker)
        return True, f"Writable: {home}"
    except Exception as exc:
        return False, str(exc)
    finally:
        for file in temp_files:
            try:
                file.unlink()
            except Exception:
                pass


def _http_get_json(
    url: str,
    headers: Dict[str, str],
    timeout: float,
) -> Tuple[Optional[dict], Optional[str]]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return json.loads(body or "{}"), None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="ignore")
            return json.loads(body or "{}"), f"HTTP {exc.code}: {exc.reason}"
        except Exception:
            return None, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # pragma: no cover - networking exceptions vary
        return None, str(exc)


def _http_post_json(
    url: str,
    payload: dict,
    headers: Dict[str, str],
    timeout: float,
) -> Tuple[Optional[dict], Optional[str]]:
    data = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return json.loads(body or "{}"), None
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="ignore")
            return json.loads(body or "{}"), f"HTTP {exc.code}: {exc.reason}"
        except Exception:
            return None, f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:  # pragma: no cover
        return None, str(exc)


def _print_results(checks: Iterable[CheckResult]) -> None:
    for check in checks:
        prefix = "[ OK ]" if check.success else "[FAIL]"
        color = GREEN if check.success else RED
        detail = f" - {check.detail}" if check.detail else ""
        print(c(f"{prefix} {check.name}{detail}", color))
        if not check.success and "Skipped" in check.detail:
            warn(f"{check.name}: {check.detail}")


__all__ = ["run_doctor"]
