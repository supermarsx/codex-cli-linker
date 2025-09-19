import argparse
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location(
    "codex_cli_linker", Path(__file__).resolve().parents[1] / "codex-cli-linker.py"
)
cli_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cli_module
spec.loader.exec_module(cli_module)

run_doctor = cli_module.run_doctor
# Access the real doctor module for patching
if "codex_linker.doctor" in sys.modules:
    doctor = sys.modules["codex_linker.doctor"]
else:
    import codex_linker.doctor as doctor  # fallback when module not yet cached


class DummyState:
    def __init__(self, base_url: str = "", api_key: str = "", model: str = "") -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model


class DoctorSuccessTests(unittest.TestCase):
    def test_doctor_happy_path(self) -> None:
        args = argparse.Namespace(
            base_url="http://localhost:1234/v1",
            api_key="",
            model=None,
            json=False,
            yaml=False,
            doctor_detect_features=False,
        )
        state = DummyState()

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "codex"
            config = home / "config.toml"

            with mock.patch(
                "codex_linker.doctor.detect_base_url", return_value=None
            ), mock.patch(
                "codex_linker.doctor.urllib.request.urlopen"
            ) as mock_urlopen, mock.patch(
                "codex_linker.doctor._probe_models",
                return_value=(True, ["gpt-test"], "1 model"),
            ), mock.patch(
                "codex_linker.doctor.info"
            ), mock.patch(
                "codex_linker.doctor.ok"
            ), mock.patch(
                "codex_linker.doctor.err"
            ), mock.patch(
                "codex_linker.doctor.warn"
            ), mock.patch(
                "codex_linker.doctor.log_event", lambda *a, **k: None
            ):

                class _Resp:  # pragma: no cover - helper context manager
                    def __init__(self, status: int = 200, body: bytes = b"{}") -> None:
                        self.status = status
                        self._body = body

                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc, tb):
                        return False

                    def read(self) -> bytes:
                        return self._body

                mock_urlopen.return_value = _Resp()

                responses = [
                    (
                        {
                            "choices": [
                                {
                                    "message": {
                                        "content": [{"type": "text", "text": "pong"}]
                                    }
                                }
                            ]
                        },
                        None,
                    )
                ]

                def fake_post(url, payload, headers, timeout):
                    return (
                        responses.pop(0)
                        if responses
                        else ({"choices": [{"text": "pong"}]}, None)
                    )

                with mock.patch(
                    "codex_linker.doctor._http_post_json", side_effect=fake_post
                ):
                    exit_code = run_doctor(
                        args, home, [config], state=state, timeout=0.1
                    )

        self.assertEqual(exit_code, 0)

    def test_doctor_falls_back_to_completions(self) -> None:
        args = argparse.Namespace(
            base_url="http://localhost:1234/v1",
            api_key="",
            model=None,
            json=False,
            yaml=False,
            doctor_detect_features=False,
        )
        state = DummyState()

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "codex"
            config = home / "config.toml"

            with mock.patch(
                "codex_linker.doctor.detect_base_url", return_value=None
            ), mock.patch(
                "codex_linker.doctor.urllib.request.urlopen"
            ) as mock_urlopen, mock.patch(
                "codex_linker.doctor._probe_models",
                return_value=(True, ["gpt-test"], "1 model"),
            ), mock.patch(
                "codex_linker.doctor.info"
            ), mock.patch(
                "codex_linker.doctor.ok"
            ), mock.patch(
                "codex_linker.doctor.err"
            ), mock.patch(
                "codex_linker.doctor.warn"
            ), mock.patch(
                "codex_linker.doctor.log_event", lambda *a, **k: None
            ):

                class _Resp:  # pragma: no cover - helper context manager
                    def __init__(self, status: int = 200, body: bytes = b"{}") -> None:
                        self.status = status
                        self._body = body

                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc, tb):
                        return False

                    def read(self) -> bytes:
                        return self._body

                mock_urlopen.return_value = _Resp()

                responses = [
                    ({"error": {"message": "unsupported"}}, None),
                    (None, "bad payload"),
                    ({"choices": [{"text": "pong"}]}, None),
                ]

                def fake_post(url, payload, headers, timeout):
                    return responses.pop(0)

                with mock.patch(
                    "codex_linker.doctor._http_post_json", side_effect=fake_post
                ):
                    exit_code = run_doctor(
                        args, home, [config], state=state, timeout=0.1
                    )

        self.assertEqual(exit_code, 0)

    def test_doctor_feature_probe(self) -> None:
        args = argparse.Namespace(
            base_url="http://localhost:1234/v1",
            api_key="",
            model=None,
            json=False,
            yaml=False,
            doctor_detect_features=True,
        )
        state = DummyState()

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "codex"
            config = home / "config.toml"

            with mock.patch(
                "codex_linker.doctor.detect_base_url", return_value=None
            ), mock.patch(
                "codex_linker.doctor.urllib.request.urlopen"
            ) as mock_urlopen, mock.patch(
                "codex_linker.doctor._probe_models",
                return_value=(True, ["gpt-test"], "1 model"),
            ):

                class _Resp:  # pragma: no cover - helper context manager
                    def __init__(self, status: int = 200, body: bytes = b"{}") -> None:
                        self.status = status
                        self._body = body

                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc, tb):
                        return False

                    def read(self) -> bytes:
                        return self._body

                mock_urlopen.return_value = _Resp()

                responses = [({"choices": [{"message": {"content": "pong"}}]}, None)]

                def fake_post(url, payload, headers, timeout):
                    return responses[0]

                feature_check = doctor.CheckResult(
                    name="Feature probing",
                    success=True,
                    detail="tool_choice: ok; response_format: ok; reasoning: ok",
                )
                feature_status = {
                    "tool_choice": True,
                    "response_format": True,
                    "reasoning": True,
                }
                suggestions = [
                    "wire_api=chat",
                    "enable --model-supports-reasoning-summaries",
                ]

                info_messages: list[str] = []

                with mock.patch(
                    "codex_linker.doctor._http_post_json", side_effect=fake_post
                ), mock.patch(
                    "codex_linker.doctor._probe_feature_support",
                    return_value=(feature_check, feature_status, suggestions),
                ), mock.patch(
                    "codex_linker.doctor.info", side_effect=info_messages.append
                ), mock.patch(
                    "codex_linker.doctor.ok"
                ), mock.patch(
                    "codex_linker.doctor.err"
                ), mock.patch(
                    "codex_linker.doctor.warn"
                ), mock.patch(
                    "codex_linker.doctor.log_event", lambda *a, **k: None
                ):

                    exit_code = run_doctor(
                        args, home, [config], state=state, timeout=0.1
                    )

        self.assertEqual(exit_code, 0)
        assert any("Feature suggestions:" in msg for msg in info_messages)


class DoctorFailureTests(unittest.TestCase):
    def test_doctor_base_url_failure_sets_nonzero_exit(self) -> None:
        args = argparse.Namespace(
            base_url="http://localhost:9999/v1",
            api_key="",
            model=None,
            json=False,
            yaml=False,
        )
        state = DummyState()

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "codex"
            config = home / "config.toml"

            with mock.patch(
                "codex_linker.doctor._probe_base_url",
                return_value=(False, "Connection refused"),
            ), mock.patch("codex_linker.doctor.info"), mock.patch(
                "codex_linker.doctor.ok"
            ), mock.patch(
                "codex_linker.doctor.err"
            ), mock.patch(
                "codex_linker.doctor.warn"
            ), mock.patch(
                "codex_linker.doctor.log_event", lambda *a, **k: None
            ):

                exit_code = run_doctor(args, home, [config], state=state, timeout=0.1)

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
