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


# --- dry-run labelling and the results summary -------------------------------------------------


def test_off_windows_pass_is_reported_as_dry_run_never_pass(recorder, monkeypatch, capsys):
    monkeypatch.setattr(_common, "IS_WINDOWS", False)
    recorder.check("a", True)
    assert recorder.status() == "PASS"
    assert recorder.reported_status() == "DRY_RUN_PASS"
    recorder.finish()
    assert "RESULT WX: DRY_RUN_PASS" in capsys.readouterr().out


def test_off_windows_partial_fail_are_dry_run_and_skip_stays_skip(recorder, monkeypatch):
    monkeypatch.setattr(_common, "IS_WINDOWS", False)
    recorder.check("a", None)
    assert recorder.reported_status() == "DRY_RUN_PARTIAL"
    recorder.check("b", False)
    assert recorder.reported_status() == "DRY_RUN_FAIL"
    assert recorder.finish() == 1  # still a non-zero exit code for developers
    other = _common.Recorder("WY", "skip")
    other.skip_reason = "x"
    assert other.reported_status() == "SKIP"


def test_on_windows_status_is_unchanged(recorder, monkeypatch):
    monkeypatch.setattr(_common, "IS_WINDOWS", True)
    recorder.check("a", True)
    assert recorder.reported_status() == "PASS"


def _write_report(folder, test_id, *, windows, check_status, title="t", checks=()):
    report = {
        "test_id": test_id,
        "title": title,
        "status": check_status if windows else f"DRY_RUN_{check_status}",
        "check_status": check_status,
        "skip_reason": None,
        "executed_on_target": windows,
        "started_utc": "2026-11-23T00:00:00+00:00",
        "checks": list(checks),
    }
    (folder / f"{test_id}_{title}.json").write_text(json.dumps(report), encoding="utf-8")


def test_summary_marks_missing_tests_not_run_and_linux_reports_dry_run(tmp_path):
    import summarize_results

    _write_report(tmp_path, "W7", windows=False, check_status="PASS")
    summary = summarize_results.build_summary(tmp_path)
    states = {row["test"]: row["state"] for row in summary["rows"]}
    assert states["W7"] == "DRY_RUN"  # a Linux run is never evidence
    _write_report(tmp_path, "W2", windows=False, check_status="SKIP")
    skipped_off_windows = summarize_results.build_summary(tmp_path)
    assert {r["test"]: r["state"] for r in skipped_off_windows["rows"]}["W2"] == "DRY_RUN"
    assert states["W0"] == states["W5"] == "NOT_RUN"
    assert summary["gate_w0_w1_ok"] is False


def test_summary_gate_opens_only_when_w0_and_w1_pass_on_windows(tmp_path):
    import summarize_results

    _write_report(tmp_path, "W0", windows=True, check_status="PASS")
    assert summarize_results.build_summary(tmp_path)["gate_w0_w1_ok"] is False
    _write_report(tmp_path, "W1", windows=True, check_status="PARTIAL")
    assert summarize_results.build_summary(tmp_path)["gate_w0_w1_ok"] is False
    _write_report(tmp_path, "W1", windows=True, check_status="PASS", title="t2")
    # the PARTIAL report (title "t") is still listed, so the overall W1 state stays PARTIAL
    assert summarize_results.build_summary(tmp_path)["gate_w0_w1_ok"] is False


def test_summary_reports_failed_checks_and_worst_state(tmp_path):
    import summarize_results

    checks = [{"name": "paddle is CPU", "passed": False, "detail": ""}]
    _write_report(tmp_path, "W1", windows=True, check_status="FAIL", checks=checks)
    row = next(r for r in summarize_results.build_summary(tmp_path)["rows"] if r["test"] == "W1")
    assert row["state"] == "FAIL"
    assert row["reports"][0]["failed_checks"] == ["paddle is CPU"]


# --- W5 must not accept the wrong kind of failure ---------------------------------------------


def test_w5_error_classification_is_specific():
    openai = pytest.importorskip("openai")
    try:  # newer openai SDK releases depend on httpx2, older ones on httpx
        import httpx2 as httpx
    except ImportError:
        httpx = pytest.importorskip("httpx")
    import W5_openai

    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    timeout = openai.APITimeoutError(request=request)
    connection = openai.APIConnectionError(request=request)
    auth = openai.AuthenticationError(
        "bad key", response=httpx.Response(401, request=request), body=None
    )
    assert W5_openai.is_timeout_or_connection_error(timeout, openai)
    assert W5_openai.is_timeout_or_connection_error(connection, openai)
    assert not W5_openai.is_timeout_or_connection_error(auth, openai)
    assert W5_openai.is_auth_error(auth, openai)
    assert not W5_openai.is_auth_error(connection, openai)  # offline must not look like "401 works"
    assert not W5_openai.is_auth_error(ValueError("x"), openai)


# --- W7 can never reach PASS -------------------------------------------------------------------


def test_w7_never_reports_plain_pass(tmp_path, monkeypatch, capsys):
    import W7_queue_timeout

    monkeypatch.setattr(_common, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(sys, "argv", ["W7", "--seconds", "1"])
    W7_queue_timeout.main()
    report = json.loads(next(tmp_path.glob("W7_*.json")).read_text(encoding="utf-8"))
    assert report["check_status"] == "PARTIAL"
    assert not any(c["passed"] is False for c in report["checks"]), report["checks"]
    assert any(c["passed"] is None for c in report["checks"])
    assert "RESULT W7: PASS" not in capsys.readouterr().out
