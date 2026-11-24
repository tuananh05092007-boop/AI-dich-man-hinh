"""Summarize the W0-W8 reports into one table and one JSON file (standard library only).

    python scripts/windows_tests/summarize_results.py
    python scripts/windows_tests/summarize_results.py --dir windows_test_results

Per test the summary shows ONE of:

* ``PASS``     - every check ran on Windows and passed.
* ``PARTIAL``  - ran on Windows, nothing failed, but some checks were N/A (human observation needed
                 or not measurable). Never counted as PASS.
* ``FAIL``     - ran on Windows and at least one check failed.
* ``SKIP``     - on Windows, the test could not be performed (reason shown).
* ``DRY_RUN``  - only a non-Windows report exists. Not evidence for the target machine.
* ``NOT_RUN``  - no report exists at all.

Several reports of the same test (W2 desktop/borderless/exclusive, W6 win32/qt, W8 scenarios) are
all listed; the newest report of each distinct title is used. The output file
``SUMMARY.json`` is written next to the reports. It contains no secrets (reports are redacted when
written) but does contain machine details, so look at it before sharing.
"""

import argparse
import json
import os
import sys
from pathlib import Path

TESTS = {
    "W0": "Environment snapshot",
    "W1": "Dependency imports",
    "W2": "DXGI Desktop Duplication",
    "W3": "PP-OCRv6 Small (CPU)",
    "W4": "NLLB-200 Distilled 600M (CPU)",
    "W5": "OpenAI API",
    "W6": "Overlay, click-through, hotkeys",
    "W7": "Queue, timeout, generation guard (simulation)",
    "W8": "Game impact (resources, FPS)",
}
GATE = ("W0", "W1")


def classify(report: dict) -> str:
    """Map one report to the user-facing state. Anything not run on Windows is a DRY_RUN."""
    status = str(report.get("check_status") or report.get("status") or "").upper()
    if not report.get("executed_on_target") or status.startswith("DRY_RUN"):
        return "DRY_RUN"
    if status == "SKIP":
        return "SKIP"
    return status if status in {"PASS", "PARTIAL", "FAIL"} else "UNKNOWN"


def load_reports(folder: Path) -> list[dict]:
    reports = []
    for path in sorted(folder.glob("W[0-8]_*.json")):
        if path.name == "SUMMARY.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warning: cannot read {path.name}: {exc}", file=sys.stderr)
            continue
        if isinstance(data, dict) and data.get("test_id") in TESTS:
            data["_file"] = path.name
            reports.append(data)
    return reports


def newest_per_title(reports: list[dict]) -> dict[str, list[dict]]:
    latest: dict[tuple[str, str], dict] = {}
    for report in reports:
        key = (report["test_id"], str(report.get("title")))
        if key not in latest or str(report.get("started_utc")) > str(
            latest[key].get("started_utc")
        ):
            latest[key] = report
    grouped: dict[str, list[dict]] = {test_id: [] for test_id in TESTS}
    for (test_id, _), report in sorted(latest.items()):
        grouped[test_id].append(report)
    return grouped


def build_summary(folder: Path) -> dict:
    grouped = newest_per_title(load_reports(folder))
    rows = []
    for test_id, name in TESTS.items():
        entries = grouped[test_id]
        if not entries:
            rows.append({"test": test_id, "name": name, "state": "NOT_RUN", "reports": []})
            continue
        reports = [
            {
                "title": r.get("title"),
                "state": classify(r),
                "file": r["_file"],
                "skip_reason": r.get("skip_reason"),
                "failed_checks": [
                    c["name"] for c in r.get("checks", []) if c.get("passed") is False
                ],
                "na_checks": sum(1 for c in r.get("checks", []) if c.get("passed") is None),
            }
            for r in entries
        ]
        states = [r["state"] for r in reports]
        for worst in ("FAIL", "PARTIAL", "SKIP", "DRY_RUN", "UNKNOWN", "PASS"):
            if worst in states:
                overall = worst
                break
        rows.append({"test": test_id, "name": name, "state": overall, "reports": reports})
    by_id = {r["test"]: r["state"] for r in rows}
    gate_ok = all(by_id[t] == "PASS" for t in GATE)  # W0/W1 have no manual checks: PASS or not
    return {
        "rows": rows,
        "gate_w0_w1_ok": gate_ok,
        "next_step": (
            "Run W0 and W1 on Windows first."
            if not gate_ok
            else "W0 and W1 PASSED on Windows; W2-W8 may be run."
        ),
        "note": "Only reports with executed_on_target=true count as evidence for Windows.",
    }


def render(summary: dict) -> str:
    lines = ["| Test | Name | State |", "|---|---|---|"]
    for row in summary["rows"]:
        lines.append(f"| {row['test']} | {row['name']} | {row['state']} |")
        for report in row["reports"]:
            extra = []
            if report["failed_checks"]:
                extra.append("failed: " + "; ".join(report["failed_checks"]))
            if report["skip_reason"]:
                extra.append("skipped: " + str(report["skip_reason"]))
            if report["na_checks"]:
                extra.append(f"{report['na_checks']} N/A")
            detail = f" ({', '.join(extra)})" if extra else ""
            lines.append(f"|  | - {report['title']} | {report['state']}{detail} |")
    lines += ["", summary["next_step"], summary["note"]]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dir", type=Path, default=Path(os.environ.get("W_RESULTS_DIR", "windows_test_results"))
    )
    args = parser.parse_args()
    summary = build_summary(args.dir)
    print(render(summary))
    if args.dir.is_dir():
        (args.dir / "SUMMARY.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"\nwritten: {args.dir / 'SUMMARY.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
