from __future__ import annotations
import os
import subprocess
import sys

from .ui import ok, warn

def _keychain_backend_auto() -> str:
    if sys.platform == "darwin":
        return "macos"
    if os.name == "nt":
        return "dpapi"
    return "secretstorage"


def store_api_key_in_keychain(backend: str, env_var: str, api_key: str) -> bool:
    """Best-effort storage of API key in OS keychain/credential store.

    Returns True on success. Never raises; logs warnings instead. Not required.
    """
    try:
        if backend == "auto":
            backend = _keychain_backend_auto()

        if backend == "macos":
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
            except Exception as e:
                warn(f"macOS Keychain storage failed: {e}")
                return False

        if backend == "secretstorage":
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
            except Exception as e:  # pragma: no cover
                warn(f"Secret Service storage failed: {e}")
                return False

        if backend == "dpapi":
            if os.name != "nt":
                warn("DPAPI backend requested on non-Windows; skipping.")
                return False
            try:
                import ctypes
                from ctypes import wintypes

                CRED_TYPE_GENERIC = 1
                CRED_PERSIST_LOCAL_MACHINE = 2

                class CREDENTIAL(ctypes.Structure):
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

                CredWriteW = ctypes.windll.advapi32.CredWriteW
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
            except Exception as e:  # pragma: no cover
                warn(f"DPAPI storage failed: {e}")
                return False

        return False
    except Exception as e:  # pragma: no cover
        warn(f"Keychain storage error: {e}")
        return False



__all__ = ["store_api_key_in_keychain"]
