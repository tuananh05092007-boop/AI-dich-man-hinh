"""W7 - Bounded queues, timeouts, worker failure and the generation guards (simulation).

    uv run python scripts/windows_tests/W7_queue_timeout.py
    uv run python scripts/windows_tests/W7_queue_timeout.py --seconds 8

Pure-Python simulation with fake workers; it needs no GPU, no game and no heavy model, so it also
runs off-Windows. It validates the *stability concepts* the architecture depends on (owner rule:
keep generation guard, bounded queues, timeouts, no blocking). It is NOT product code and does not
implement any Milestone 1 feature.

Scenarios
 A. Bounded latest-frame queue: a 60 fps producer and a slow consumer. Memory/queue stay bounded,
    the consumer always sees increasing frame ids, and old frames are dropped rather than queued.
 B. Timeout: a fake translation that takes much longer than its deadline must not block the
    capture loop; its late result is discarded.
 C. Generation guard: a generation-1 result arriving after generation 2 is rejected (real
    ``TranslationResult.is_current`` from the v0.2 contracts).
 D. F8 batches: a newer ``batch_id`` supersedes an older one; late results of the old batch are
    discarded; the overlap rule (overlap coefficient >= 0.5) behaves as documented (provisional).
 E. Worker exception: a crashing worker becomes a structured ``ErrorInfo`` and the loop continues.

Results on a non-Windows host are a dry run, not evidence for the target machine. Checks that only
exercise a helper or illustrate a filter are N/A, and a final N/A check records that no real
pipeline exists yet, so W7 reports PARTIAL (DRY_RUN_PARTIAL off-Windows) at best, never PASS.
"""

import argparse
import queue
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from datetime import UTC, datetime

from _common import Recorder, rss_mb, stats

try:  # the contracts are installed with the project (uv sync)
    from ai_screen_translator.contracts import (
        BoundingBox,
        ErrorCode,
        ErrorInfo,
        PipelineComponent,
        TranslationEngine,
        TranslationRequest,
        TranslationResult,
        TranslationStatus,
        Trigger,
    )

    HAVE_CONTRACTS = True
except ImportError:  # pragma: no cover - reported as a failed check below
    HAVE_CONTRACTS = False


class LatestQueue:
    """Bounded queue that drops the OLDEST item when full (latest-frame semantics)."""

    def __init__(self, maxsize: int) -> None:
        self.q: queue.Queue[tuple[int, float]] = queue.Queue(maxsize=maxsize)
        self.dropped = 0
        self.max_depth = 0
        self.lock = threading.Lock()

    def put(self, item: tuple[int, float]) -> None:
        with self.lock:
            while True:
                try:
                    self.q.put_nowait(item)
                    break
                except queue.Full:
                    try:
                        self.q.get_nowait()
                        self.dropped += 1
                    except queue.Empty:
                        pass
            self.max_depth = max(self.max_depth, self.q.qsize())


def scenario_a(rec: Recorder, seconds: float) -> None:
    print("A - bounded latest-frame queue")
    bound = 2
    fq = LatestQueue(bound)
    stop = threading.Event()
    produced = 0
    seen: list[int] = []
    ages: list[float] = []
    payload = bytes(512 * 1024)  # stand-in for a frame buffer reference

    def producer() -> None:
        nonlocal produced
        interval = 1 / 60
        next_t = time.perf_counter()
        while not stop.is_set():
            produced += 1
            fq.put((produced, time.perf_counter()))
            next_t += interval
            time.sleep(max(0.0, next_t - time.perf_counter()))

    def consumer() -> None:
        while not stop.is_set():
            try:
                frame_id, born = fq.q.get(timeout=0.1)
            except queue.Empty:
                continue
            ages.append((time.perf_counter() - born) * 1000)
            seen.append(frame_id)
            _ = payload
            time.sleep(0.05)  # a deliberately slow consumer (20 fps)

    before = rss_mb()
    threads = [threading.Thread(target=producer), threading.Thread(target=consumer)]
    for t in threads:
        t.start()
    time.sleep(seconds)
    stop.set()
    for t in threads:
        t.join(2)
    after = rss_mb()
    rec.measure("A_frames_produced", produced)
    rec.measure("A_frames_processed", len(seen))
    rec.measure("A_frames_dropped", fq.dropped)
    rec.measure("A_max_queue_depth", fq.max_depth)
    rec.measure("A_frame_age_at_processing_ms", stats(ages))
    rec.check(
        "A queue depth never exceeded its bound",
        fq.max_depth <= bound,
        f"max {fq.max_depth}, bound {bound}",
    )
    rec.check(
        "A frames were dropped instead of queued (producer faster than consumer)",
        fq.dropped > 0,
        f"{fq.dropped} dropped",
    )
    rec.check(
        "A consumer saw strictly increasing frame ids",
        all(b > a for a, b in zip(seen, seen[1:], strict=False)),
    )
    if before is not None and after is not None:
        rec.measure("A_rss_growth_mb", round(after - before, 1), "MiB")
        rec.check(
            "A memory growth stayed small (< 50 MiB)",
            after - before < 50,
            f"{after - before:.1f} MiB",
        )


def scenario_b(rec: Recorder) -> None:
    print("B - timeout does not block the capture loop")
    deadline_s, slow_s = 0.4, 2.0
    ticks: list[float] = []
    stop = threading.Event()

    def capture_loop() -> None:
        while not stop.is_set():
            ticks.append(time.perf_counter())
            time.sleep(0.01)

    loop = threading.Thread(target=capture_loop)
    loop.start()
    pool = ThreadPoolExecutor(max_workers=1)
    started = time.perf_counter()
    future = pool.submit(lambda: (time.sleep(slow_s), "late translation")[1])
    timed_out = False
    try:
        future.result(timeout=deadline_s)
    except FutureTimeout:
        timed_out = True
    waited = time.perf_counter() - started
    time.sleep(slow_s - waited + 0.2)  # let the late result arrive
    stop.set()
    loop.join(2)
    gaps = [(b - a) * 1000 for a, b in zip(ticks, ticks[1:], strict=False)]
    pool.shutdown(wait=True)
    rec.measure("B_caller_unblocked_after_ms", round(waited * 1000))
    rec.measure("B_capture_tick_gap_ms", stats(gaps))
    rec.check(
        "B caller gave up at the deadline",
        timed_out and abs(waited - deadline_s) < 0.25,
        f"{waited * 1000:.0f} ms for a {deadline_s * 1000:.0f} ms deadline",
    )
    rec.check(
        "B capture loop kept ticking during the slow call (max gap < 200 ms)",
        bool(gaps) and max(gaps) < 200,
        f"max gap {max(gaps):.0f} ms" if gaps else "no ticks",
    )
    rec.check(
        "B the late result is available but must be discarded by the caller",
        future.done() and future.result() == "late translation",
    )


def make_request(subtitle_id, generation_id, trigger="auto", batch_id=None):
    context = {
        "schema_version": "0.2",
        "game_id": "w7",
        "speaker": "unknown",
        "conversation_history": [],
        "glossary": {},
        "translation_style": "context_adaptive",
        "source_language": "en",
        "target_language": "vi",
    }
    return TranslationRequest.model_validate(
        {
            "schema_version": "0.2",
            "subtitle_id": subtitle_id,
            "generation_id": generation_id,
            "source_text": "You should not have come here.",
            "context": context,
            "requested_at": datetime.now(UTC),
            "deadline_ms": 1500,
            "idempotency_key": f"{subtitle_id}:{generation_id}",
            "trigger": trigger,
            "batch_id": batch_id,
        }
    )


def make_result(subtitle_id, generation_id):
    return TranslationResult.model_validate(
        {
            "schema_version": "0.2",
            "subtitle_id": subtitle_id,
            "generation_id": generation_id,
            "source_text": "x",
            "translated_text": "y",
            "engine": TranslationEngine.NLLB.value,
            "model_id": "fake",
            "status": TranslationStatus.COMPLETED.value,
            "latency_ms": 1.0,
            "completed_at": datetime.now(UTC),
        }
    )


def overlap_coefficient(a: "BoundingBox", b: "BoundingBox") -> float:
    """Intersection area / area of the smaller box; 0 on different monitors (PROVISIONAL P-01)."""
    if a.monitor_id != b.monitor_id:
        return 0.0
    w = min(a.x2, b.x2) - max(a.x1, b.x1)
    h = min(a.y2, b.y2) - max(a.y1, b.y1)
    if w <= 0 or h <= 0:
        return 0.0
    smaller = min((a.x2 - a.x1) * (a.y2 - a.y1), (b.x2 - b.x1) * (b.y2 - b.y1))
    return (w * h) / smaller


def scenario_c(rec: Recorder) -> None:
    print("C - generation guard (v0.2 contracts)")
    gen1_result = make_result("subtitle_1", 1)
    gen2_active = ("subtitle_1", 2)
    rec.check(
        "C a generation-1 result is stale once generation 2 is active",
        not gen1_result.is_current(*gen2_active),
    )
    rec.check(
        "C a generation-2 result is accepted", make_result("subtitle_1", 2).is_current(*gen2_active)
    )
    rec.check(
        "C a result for a different subtitle is rejected",
        not make_result("subtitle_2", 2).is_current(*gen2_active),
    )
    rec.note(
        "C: SkipReason.STALE_GENERATION exists in the contracts, but nothing here proves a real "
        "pipeline emits it; that needs the real implementation."
    )


def scenario_d(rec: Recorder) -> None:
    print("D - F8 batches and overlap rule")
    batch_a = [make_request(f"f8_batch_a_{i}", 1, "hotkey", "batch_a") for i in range(3)]
    batch_b = [make_request(f"f8_batch_b_{i}", 1, "hotkey", "batch_b") for i in range(2)]
    rec.check(
        "D hotkey requests carry their batch_id",
        all(r.trigger is Trigger.HOTKEY and r.batch_id for r in batch_a + batch_b),
    )
    active = "batch_b"  # a newer F8 press superseded batch_a
    late_old = [r for r in batch_a if r.batch_id != active]
    accepted_new = [r for r in batch_b if r.batch_id == active]
    rec.check(
        "D late results of the superseded batch are discarded",
        None,
        "illustration of a list filter on contract fields; not evidence about real code "
        f"(filter kept {len(accepted_new)} new, dropped {len(late_old)} old)",
    )
    rec.note(
        "D: the batch check only illustrates the filter 'batch_id == active batch' on contract "
        "fields. It is NOT evidence about real code; the real test belongs with the F8 "
        "implementation."
    )

    def box(x1, y1, x2, y2, monitor="DISPLAY1"):
        return BoundingBox(monitor_id=monitor, x1=x1, y1=y1, x2=x2, y2=y2)

    big, inside = box(0, 0, 1000, 100), box(100, 10, 400, 60)
    far, partial = box(0, 500, 1000, 600), box(900, 0, 1100, 100)
    other_monitor = box(100, 10, 400, 60, monitor="DISPLAY2")
    # These exercise overlap_coefficient() defined in THIS script (a helper), so a pass says the
    # provisional P-01 formula is self-consistent, not that any product code implements it.
    # They are therefore N/A for the purpose of the overall status.
    helper_ok = (
        overlap_coefficient(big, inside) == 1.0
        and overlap_coefficient(big, far) == 0.0
        and overlap_coefficient(big, partial) == 0.5
        and overlap_coefficient(big, other_monitor) == 0.0
    )
    rec.measure("D_script_helper_overlap_formula_self_consistent", helper_ok)
    rec.check(
        "D overlap rule (provisional P-01) implemented in product code",
        None,
        f"only the script's own helper was exercised (self-consistent: {helper_ok})",
    )


def scenario_e(rec: Recorder) -> None:
    print("E - worker exception becomes a structured error and the loop continues")
    processed = 0
    errors: list = []

    def worker(item: int) -> str:
        if item == 2:
            raise RuntimeError("simulated engine crash; api_key=sk-test1234567890 must not leak")
        return f"ok {item}"

    for item in range(5):
        try:
            worker(item)
            processed += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(
                ErrorInfo(
                    code=ErrorCode.ENGINE_ERROR,
                    component=PipelineComponent.TRANSLATION,
                    message=str(exc),
                    retryable=False,
                )
            )
    rec.check("E loop survived a worker exception", processed == 4 and len(errors) == 1)
    rec.check(
        "E error is structured and the secret is redacted",
        bool(errors) and "sk-test" not in errors[0].message,
        errors[0].message if errors else "no error recorded",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seconds", type=float, default=5.0, help="duration of scenario A")
    args = parser.parse_args()

    rec = Recorder("W7", "Bounded queues, timeouts, worker failure, generation guards")
    print("W7 - queue / timeout / guards (simulation)")
    rec.check("contracts v0.2 importable", HAVE_CONTRACTS)
    if not HAVE_CONTRACTS:
        rec.note("Run through 'uv run' from the repository root so the project is installed.")
        return rec.finish()
    scenario_a(rec, args.seconds)
    scenario_b(rec)
    scenario_c(rec)
    scenario_d(rec)
    scenario_e(rec)
    rec.check(
        "the real pipeline (queues, workers, guards in product code) behaves correctly",
        None,
        "not testable yet: no pipeline code exists before M1; W7 reaches PARTIAL at best",
    )
    rec.note(
        "Simulation of the concepts only. Real queue sizes, drop policies and threading model "
        "are decided and benchmarked during implementation (Milestone 6)."
    )
    return rec.finish()


if __name__ == "__main__":
    sys.exit(main())
