"""Optional keychain helpers for storing API keys.

These helpers provide best‑effort integration with platform keychains and
common CLI secret managers. They are entirely optional and never block normal
CLI flows; failures are logged as warnings and result in ``False``.

Supported backends
- ``auto``: pick a sensible default (macOS Keychain on Darwin, DPAPI on
  Windows, Secret Service on Linux)
- ``macos``: macOS Keychain via the ``security`` command
- ``secretservice`` / ``secretstorage``: Linux Secret Service (uses the
  optional ``secretstorage`` Python package if available)
- ``dpapi``: Windows Credential Manager via Win32 APIs
- ``pass``: the pass(1) password manager (inserts an entry)
- ``bitwarden`` / ``bw`` / ``bitwarden-cli``: detect CLI and instruct manual use
- ``1password`` / ``1passwd`` / ``op``: detect CLI and instruct manual use
- ``none`` / ``skip``: disable storage

No third‑party dependencies are required; Linux Secret Service is attempted
only when the ``secretstorage`` package is present.
"""

from __future__ import annotations
import os
import subprocess
import sys

from .ui import ok, warn


def _keychain_backend_auto() -> str:
    """Return a default keychain backend for the current platform.

    - macOS → ``macos`` (Keychain)
    - Windows → ``dpapi`` (Credential Manager)
    - Other → ``secretstorage`` (Linux Secret Service)
    """
    if sys.platform == "darwin":
        return "macos"
    if os.name == "nt":
        return "dpapi"
    return "secretstorage"


def store_api_key_in_keychain(backend: str, env_var: str, api_key: str) -> bool:
    """Store an API key in a platform keychain or CLI secret manager.

    Parameters
    - ``backend``: One of the supported identifiers listed in the module
      header; use ``"auto"`` to pick a sensible default per platform.
    - ``env_var``: The environment variable name associated with the key
      (used to label the secret entry).
    - ``api_key``: The secret value to store.

    Returns ``True`` when storage succeeds; returns ``False`` otherwise. This
    function never raises and logs warnings explaining why a backend was
    skipped or failed (e.g., CLI not present, platform mismatch).
    """
    try:
        if backend == "auto":
            backend = _keychain_backend_auto()
        backend = (backend or "").strip().lower()

        if backend in {"macos", "keychain"}:
            if sys.platform != "darwin":
                warn("Keychain backend macos requested on non-macOS; skipping.")
                return False
            svc = f"codex-cli-linker:{env_var}"
            cmd = [
                "security",
                "add-generic-password",
                "-a",
                env_var,
                "-s",
                svc,
                "-w",
                api_key,
                "-U",
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                ok("Stored API key in macOS Keychain.")
                return True
            except Exception as exc:  # pragma: no cover
                warn(f"macOS Keychain storage failed: {exc}")
                return False

        if backend in {"secretservice", "secretstorage"}:
            try:
                import secretstorage  # type: ignore
            except Exception:
                warn("secretstorage not available; skipping keychain storage.")
                return False
            try:
                bus = secretstorage.dbus_init()
                coll = secretstorage.get_default_collection(bus)
                if coll.is_locked():
                    coll.unlock()
                attrs = {"service": "codex-cli-linker", "account": env_var}
                coll.create_item(
                    f"codex-cli-linker:{env_var}", attrs, api_key, replace=True
                )
                ok("Stored API key in Secret Service.")
                return True
            except Exception as exc:  # pragma: no cover
                warn(f"Secret Service storage failed: {exc}")
                return False

        if backend == "dpapi":
            if os.name != "nt":
                warn("DPAPI backend requested on non-Windows; skipping.")
                return False
            try:
                import ctypes
                from ctypes import wintypes
                from typing import Any, cast

                CRED_TYPE_GENERIC = 1
                CRED_PERSIST_LOCAL_MACHINE = 2

                class CREDENTIAL(ctypes.Structure):  # pragma: no cover - Windows only
                    _fields_ = [
                        ("Flags", wintypes.DWORD),
                        ("Type", wintypes.DWORD),
                        ("TargetName", wintypes.LPWSTR),
                        ("Comment", wintypes.LPWSTR),
                        ("LastWritten", wintypes.FILETIME),
                        ("CredentialBlobSize", wintypes.DWORD),
                        ("CredentialBlob", ctypes.c_void_p),
                        ("Persist", wintypes.DWORD),
                        ("AttributeCount", wintypes.DWORD),
                        ("Attributes", ctypes.c_void_p),
                        ("TargetAlias", wintypes.LPWSTR),
                        ("UserName", wintypes.LPWSTR),
                    ]

                windll = cast(Any, getattr(ctypes, "windll"))
                CredWriteW = windll.advapi32.CredWriteW
                CredWriteW.argtypes = [ctypes.POINTER(CREDENTIAL), wintypes.DWORD]
                CredWriteW.restype = wintypes.BOOL

                target = f"codex-cli-linker/{env_var}"
                blob = api_key.encode("utf-16le")
                cred = CREDENTIAL()
                cred.Flags = 0
                cred.Type = CRED_TYPE_GENERIC
                cred.TargetName = ctypes.c_wchar_p(target)
                cred.CredentialBlobSize = len(blob)
                cred.CredentialBlob = ctypes.cast(
                    ctypes.create_string_buffer(blob), ctypes.c_void_p
                )
                cred.Persist = CRED_PERSIST_LOCAL_MACHINE
                cred.AttributeCount = 0
                cred.Attributes = None
                cred.UserName = ctypes.c_wchar_p("")

                if not CredWriteW(ctypes.byref(cred), 0):
                    warn("DPAPI CredWriteW failed.")
                    return False
                ok("Stored API key in Windows Credential Manager.")
                return True
            except Exception as exc:  # pragma: no cover
                warn(f"DPAPI storage failed: {exc}")
                return False

        if backend == "pass":
            pass_cmd = (
                os.environ.get("CODEX_PASS_CMD") or os.environ.get("PASS_CMD") or "pass"
            )
            try:
                check = subprocess.run([pass_cmd, "--version"], capture_output=True)
                if check.returncode != 0:
                    warn("`pass` CLI not available; skipping keychain storage.")
                    return False
                target = f"codex-cli-linker/{env_var}"
                proc = subprocess.run(
                    [pass_cmd, "insert", "-m", "-f", target],
                    input=api_key.encode(),
                    capture_output=True,
                    check=False,
                )
                if proc.returncode != 0:
                    warn("`pass insert` failed; skipping.")
                    return False
                ok("Stored API key with pass.")
                return True
            except Exception as exc:  # pragma: no cover
                warn(f"pass storage failed: {exc}")
                return False

        if backend in {"bitwarden", "bw", "bitwarden-cli"}:
            bw_cmd = os.environ.get("CODEX_BW_CMD") or "bw"
            try:
                proc = subprocess.run([bw_cmd, "--version"], capture_output=True)
                if proc.returncode != 0:
                    warn("Bitwarden CLI not available; skipping.")
                    return False
                warn(
                    "Bitwarden CLI detected. Run `bw encode`/`bw set item` manually to store secrets."
                )
                return False
            except Exception as exc:  # pragma: no cover
                warn(f"Bitwarden CLI storage failed: {exc}")
                return False

        if backend in {"1password", "1passwd", "op"}:
            op_cmd = os.environ.get("CODEX_OP_CMD") or "op"
            try:
                proc = subprocess.run([op_cmd, "--version"], capture_output=True)
                if proc.returncode != 0:
                    warn("1Password CLI not available; skipping.")
                    return False
                warn(
                    "1Password CLI detected. Use `op item create` manually to store secrets."
                )
                return False
            except Exception as exc:  # pragma: no cover
                warn(f"1Password CLI storage failed: {exc}")
                return False

        if backend in {"none", "", "skip"}:
            return False

        if backend not in {
            "macos",
            "secretstorage",
            "secretservice",
            "dpapi",
            "pass",
            "bitwarden",
            "bw",
            "bitwarden-cli",
            "1password",
            "1passwd",
            "op",
        }:
            warn(f"Unknown keychain backend '{backend}'; skipping.")
        return False
    except Exception as exc:  # pragma: no cover
        warn(f"Keychain storage error: {exc}")
        return False


__all__ = ["store_api_key_in_keychain"]
