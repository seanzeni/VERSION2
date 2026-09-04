from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "after_action_report.py"
SPEC = importlib.util.spec_from_file_location("after_action_report", SCRIPT_PATH)
after_action_module = importlib.util.module_from_spec(SPEC)
sys.modules["after_action_report"] = after_action_module
assert SPEC.loader is not None
SPEC.loader.exec_module(after_action_module)


def test_parse_efforts_splits_comma_separated_values() -> None:
    """Verifies CLI effort filters accept comma-separated values with spaces."""
    assert after_action_module.parse_efforts("RD861J, BC1234,, abc999 ") == {
        "RD861J",
        "BC1234",
        "ABC999",
    }


def test_parse_efforts_empty_value_returns_empty_set() -> None:
    """Verifies omitted effort filters include all scheduled efforts."""
    assert after_action_module.parse_efforts(None) == set()
