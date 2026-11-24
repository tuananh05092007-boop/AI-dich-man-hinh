"""Shared helpers for the Windows validation scripts (W0-W8).

Standard library only, so every script can at least start and report what is missing.

Design rules (owner rules 6 and 7):

* A result is only ever ``PASS`` when every recorded check ran and passed. Checks that need a human
  observation, or that could not be evaluated, are ``None`` and make the overall status
  ``PARTIAL`` (never ``PASS``).
* Every report states whether it was produced on Windows. A run on any other OS is labelled
  ``executed_on_target = false``, its status is ``DRY_RUN_PASS``/``DRY_RUN_PARTIAL``/
  ``DRY_RUN_FAIL`` (never plain ``PASS``/``FAIL``) and it is not evidence for the Windows machine.
* ``NOT_RUN`` is not written by any test: it is what ``summarize_results.py`` reports for a test
  that has no report from Windows at all.
* Secrets are redacted before anything is printed or written. API keys are read from environment
  variables only and are never logged.
"""

import json
import math
import os
import platform
import re
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

IS_WINDOWS = sys.platform == "win32"
RESULTS_DIR = Path(os.environ.get("W_RESULTS_DIR", "windows_test_results"))

_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/\-]+=*"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|token|secret|password|authorization)\b"
        r"\s*[:=]\s*\S+"
    ),
)


def redact(text: str) -> str:
    """Replace likely credentials with ``[REDACTED]`` (defense in depth, not a guarantee)."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (``pct`` in 0..100)."""
    if not values:
        raise ValueError("no values")
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def stats(values: list[float]) -> dict[str, float]:
    """Summary used for every latency report: n, min, median, mean, p95, max."""
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min": round(min(values), 3),
        "median": round(statistics.median(values), 3),
        "mean": round(statistics.fmean(values), 3),
        "p95": round(percentile(values, 95), 3),
        "max": round(max(values), 3),
    }


def levenshtein(a: str, b: str) -> int:
    """Character-level edit distance (no third-party dependency)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def cer(reference: str, hypothesis: str) -> float:
    """Character error rate after whitespace normalization."""
    ref, hyp = normalize_text(reference), normalize_text(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


def rss_mb() -> float | None:
    """Resident memory of this process in MiB, or None if it cannot be read."""
    try:
        if IS_WINDOWS:
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = Counters()
            counters.cb = ctypes.sizeof(Counters)
            kernel32 = ctypes.windll.kernel32
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi = ctypes.windll.psapi
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(Counters),
                wintypes.DWORD,
            ]
            ok = psapi.GetProcessMemoryInfo(
                kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
            )
            return counters.WorkingSetSize / 2**20 if ok else None
        with open("/proc/self/status", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except (OSError, ValueError, AttributeError):
        return None
    return None


class Recorder:
    """Collects checks, measurements and notes, then writes one JSON report."""

    def __init__(self, test_id: str, title: str) -> None:
        self.test_id = test_id
        self.title = title
        self.started = datetime.now(UTC)
        self.checks: list[dict[str, Any]] = []
        self.measurements: dict[str, Any] = {}
        self.notes: list[str] = []
        self.skip_reason: str | None = None
        self.extra: dict[str, Any] = {}

    # -- recording ---------------------------------------------------------------------------
    def check(self, name: str, passed: bool | None, detail: str = "") -> None:
        """``True``/``False`` = evaluated; ``None`` = not evaluated or needs a human."""
        self.checks.append({"name": name, "passed": passed, "detail": redact(detail)})
        mark = {True: "PASS", False: "FAIL", None: "N/A "}[passed]
        print(f"  [{mark}] {name}" + (f" - {redact(detail)}" if detail else ""))

    def measure(self, name: str, value: Any, unit: str = "") -> None:
        self.measurements[name] = {"value": value, "unit": unit}
        print(f"  [meas] {name} = {value} {unit}".rstrip())

    def note(self, text: str) -> None:
        self.notes.append(redact(text))
        print(f"  [note] {redact(text)}")

    def skip(self, reason: str) -> int:
        self.skip_reason = reason
        return self.finish()

    # -- result ------------------------------------------------------------------------------
    def status(self) -> str:
        if self.skip_reason is not None:
            return "SKIP"
        if any(c["passed"] is False for c in self.checks):
            return "FAIL"
        if not self.checks or any(c["passed"] is None for c in self.checks):
            return "PARTIAL"
        return "PASS"

    def reported_status(self) -> str:
        """The status printed in ``RESULT`` and stored in the report.

        On Windows it equals :meth:`status`. Elsewhere a would-be ``PASS``/``PARTIAL`` becomes
        ``DRY_RUN_PASS``/``DRY_RUN_PARTIAL``/``DRY_RUN_FAIL`` so that a Linux run can never be
        mistaken for evidence (good or bad) about the target machine. ``SKIP`` keeps its meaning.
        """
        status = self.status()
        if not IS_WINDOWS and status in ("PASS", "PARTIAL", "FAIL"):
            return f"DRY_RUN_{status}"
        return status

    def finish(self) -> int:
        status = self.reported_status()
        report = {
            "test_id": self.test_id,
            "title": self.title,
            "status": status,
            "check_status": self.status(),
            "skip_reason": self.skip_reason,
            "executed_on_target": IS_WINDOWS,
            "started_utc": self.started.isoformat(),
            "finished_utc": datetime.now(UTC).isoformat(),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "checks": self.checks,
            "measurements": self.measurements,
            "notes": self.notes,
            **self.extra,
        }
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = self.started.strftime("%Y%m%dT%H%M%SZ")
        path = RESULTS_DIR / f"{self.test_id}_{stamp}.json"
        path.write_text(
            redact(json.dumps(report, indent=2, ensure_ascii=False)) + "\n", encoding="utf-8"
        )
        print()
        if not IS_WINDOWS:
            print(
                "WARNING: not running on Windows. This is a dry run and is NOT evidence "
                "for the target machine."
            )
        if self.skip_reason:
            print(f"  skipped: {self.skip_reason}")
        print(f"RESULT {self.test_id}: {status}  (report: {path})")
        return 1 if self.status() == "FAIL" else 0


class Stopwatch:
    """``with Stopwatch() as sw: ...`` then ``sw.ms``."""

    def __enter__(self) -> "Stopwatch":
        self._start = time.perf_counter()
        self.ms = 0.0
        return self

    def __exit__(self, *exc: object) -> None:
        self.ms = (time.perf_counter() - self._start) * 1000


def require_windows(rec: Recorder) -> bool:
    """Record a skip and return False when not on Windows."""
    if not IS_WINDOWS:
        rec.skip_reason = "this test needs Windows 11 (dry run on another OS)"
        return False
    return True
