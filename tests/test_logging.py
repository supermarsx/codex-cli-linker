import importlib.util
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
    cli.configure_logging(args.verbose)
    logging.debug("debug")
    logging.info("info")
    logging.warning("warn")
    assert [r.getMessage() for r in caplog.records] == ["warn"]


def test_logging_verbose_level(monkeypatch, caplog):
    monkeypatch.setattr(sys, "argv", ["codex-cli-linker.py", "--verbose"])
    args = cli.parse_args()
    cli.configure_logging(args.verbose)
    logging.debug("debug")
    logging.info("info")
    logging.warning("warn")
    assert [r.getMessage() for r in caplog.records] == ["debug", "info", "warn"]
