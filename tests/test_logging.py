import importlib.util
import io
import json
import logging
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "codex_cli_linker", Path(__file__).resolve().parents[1] / "codex-cli-linker.py"
)
cli = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cli
spec.loader.exec_module(cli)


def test_logging_default_level(monkeypatch, caplog):
    monkeypatch.setattr(sys, "argv", ["codex-cli-linker.py"])
    args = cli.parse_args()
    cli.configure_logging(args.verbose, args.log_file, args.log_json, args.log_remote)
    logging.debug("debug")
    logging.info("info")
    logging.warning("warn")
    assert [r.getMessage() for r in caplog.records] == ["warn"]


def test_logging_verbose_level(monkeypatch, caplog):
    monkeypatch.setattr(sys, "argv", ["codex-cli-linker.py", "--verbose"])
    args = cli.parse_args()
    cli.configure_logging(args.verbose, args.log_file, args.log_json, args.log_remote)
    logging.debug("debug")
    logging.info("info")
    logging.warning("warn")
    assert [r.getMessage() for r in caplog.records] == ["debug", "info", "warn"]


def test_log_file_handler(monkeypatch, tmp_path):
    log_path = tmp_path / "test.log"
    monkeypatch.setattr(
        sys, "argv", ["codex-cli-linker.py", "--log-file", str(log_path), "--verbose"]
    )
    args = cli.parse_args()
    cli.configure_logging(args.verbose, args.log_file, args.log_json, args.log_remote)
    logging.info("file-log")
    assert "file-log" in log_path.read_text(encoding="utf-8")


def test_log_remote_handler(monkeypatch):
    captured = {}

    def fake_emit(self, record):
        captured["host"] = self.host
        captured["url"] = self.url
        captured["msg"] = record.getMessage()

    monkeypatch.setattr(logging.handlers.HTTPHandler, "emit", fake_emit)
    monkeypatch.setattr(
        sys,
        "argv",
        ["codex-cli-linker.py", "--log-remote", "http://example.com/log", "--verbose"],
    )
    args = cli.parse_args()
    cli.configure_logging(args.verbose, args.log_file, args.log_json, args.log_remote)
    logging.warning("remote-log")
    assert captured == {
        "host": "example.com",
        "url": "/log",
        "msg": "remote-log",
    }


def test_log_json_handler(monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    monkeypatch.setattr(sys, "argv", ["codex-cli-linker.py", "--log-json"])
    args = cli.parse_args()
    cli.configure_logging(args.verbose, args.log_file, args.log_json, args.log_remote)
    msg = 'bad "quote" \\ newline\nhere'
    logging.warning(msg)
    json_output = buf.getvalue().strip().splitlines()[-1]
    assert json.loads(json_output) == {"level": "WARNING", "message": msg}


def test_reconfigure_logging_replaces_handlers(monkeypatch):
    calls = []

    def fake_emit(self, record):
        calls.append(record.getMessage())

    monkeypatch.setattr(logging.handlers.HTTPHandler, "emit", fake_emit)
    monkeypatch.setattr(
        sys,
        "argv",
        ["codex-cli-linker.py", "--log-remote", "http://example.com/log"],
    )
    args = cli.parse_args()
    cli.configure_logging(args.verbose, args.log_file, args.log_json, args.log_remote)
    cli.configure_logging(args.verbose, args.log_file, args.log_json, args.log_remote)
    logging.warning("remote-log")
    assert calls == ["remote-log"]


def test_reconfigure_logging_closes_file_handlers(monkeypatch, tmp_path):
    log1 = tmp_path / "one.log"
    monkeypatch.setattr(sys, "argv", ["codex-cli-linker.py", "--log-file", str(log1)])
    args = cli.parse_args()
    cli.configure_logging(args.verbose, args.log_file, args.log_json, args.log_remote)
    logger = logging.getLogger()
    old = next(
        h
        for h in logger.handlers
        if isinstance(h, logging.FileHandler)
        and getattr(h, "_added_by_configure_logging", False)
    )

    log2 = tmp_path / "two.log"
    monkeypatch.setattr(sys, "argv", ["codex-cli-linker.py", "--log-file", str(log2)])
    args = cli.parse_args()
    cli.configure_logging(args.verbose, args.log_file, args.log_json, args.log_remote)

    assert old.stream is None or old.stream.closed
