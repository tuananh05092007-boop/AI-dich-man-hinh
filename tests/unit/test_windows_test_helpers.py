"""The shared helpers of scripts/windows_tests must never turn missing evidence into a PASS."""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "windows_tests"
sys.path.insert(0, str(SCRIPTS))

import _common  # noqa: E402


@pytest.fixture
def recorder(tmp_path, monkeypatch):
    monkeypatch.setattr(_common, "RESULTS_DIR", tmp_path)
    return _common.Recorder("WX", "unit test")


def test_status_is_pass_only_when_every_check_passed(recorder):
    recorder.check("a", True)
    recorder.check("b", True)
    assert recorder.status() == "PASS"


def test_unevaluated_check_makes_the_result_partial_not_pass(recorder):
    recorder.check("a", True)
    recorder.check("manual observation", None)
    assert recorder.status() == "PARTIAL"


def test_no_checks_is_partial_not_pass(recorder):
    assert recorder.status() == "PARTIAL"


def test_one_failure_wins_over_passes_and_unknowns(recorder):
    recorder.check("a", True)
    recorder.check("b", None)
    recorder.check("c", False)
    assert recorder.status() == "FAIL"
    assert recorder.finish() == 1


def test_skip_is_reported_as_skip(recorder):
    assert recorder.skip("needs a key") == 0
    assert recorder.status() == "SKIP"


def test_report_records_whether_it_ran_on_the_target_and_never_contains_secrets(recorder, tmp_path):
    recorder.check("leaky", True, "api_key=sk-abcdef1234567890 leaked")
    recorder.note("Authorization: Bearer abc.def.ghi")
    recorder.finish()
    report_text = next(tmp_path.glob("WX_*.json")).read_text(encoding="utf-8")
    report = json.loads(report_text)
    assert report["executed_on_target"] is (sys.platform == "win32")
    assert "sk-abcdef" not in report_text and "abc.def.ghi" not in report_text
    assert "[REDACTED]" in report_text


def test_percentile_uses_nearest_rank():
    values = [float(x) for x in range(1, 101)]
    assert _common.percentile(values, 95) == 95.0
    assert _common.percentile(values, 100) == 100.0
    assert _common.percentile([5.0], 99) == 5.0
    with pytest.raises(ValueError):
        _common.percentile([], 50)


def test_stats_of_empty_input_reports_zero_samples():
    assert _common.stats([]) == {"n": 0}
    summary = _common.stats([1.0, 2.0, 3.0])
    assert (summary["n"], summary["min"], summary["median"], summary["max"]) == (3, 1.0, 2.0, 3.0)


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [("", "", 0), ("abc", "abc", 0), ("abc", "", 3), ("kitten", "sitting", 3), ("a", "b", 1)],
)
def test_levenshtein(a, b, expected):
    assert _common.levenshtein(a, b) == expected


def test_cer_normalizes_whitespace_and_handles_empty_reference():
    assert _common.cer("Hello  world", "Hello world") == 0.0
    assert _common.cer("abcd", "abxd") == 0.25
    assert _common.cer("", "") == 0.0
    assert _common.cer("", "x") == 1.0
