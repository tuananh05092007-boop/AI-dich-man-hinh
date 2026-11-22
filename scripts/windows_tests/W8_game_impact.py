"""W8 - Impact on a running game: resource sampling plus FPS analysis from PresentMon CSV files.

Two sub-commands.

1. ``run``: generate a load scenario while sampling CPU, RAM, GPU and VRAM once per second.

    uv run python scripts/windows_tests/W8_game_impact.py run --scenario baseline --seconds 120
    uv run python scripts/windows_tests/W8_game_impact.py run --scenario capture --seconds 120
    uv run python scripts/windows_tests/W8_game_impact.py run --scenario capture_ocr --seconds 120

   Scenarios: baseline (no load), capture (DXGI grabs at --fps on an ROI), capture_ocr (capture
   plus PP-OCR on the ROI every --ocr-interval s), capture_ocr_nllb (adds an NLLB translation after
   every OCR). The overlay's own cost is not generated here; measure it by keeping the W6 overlay
   open in a separate run.

2. ``analyze``: compute FPS statistics from PresentMon CSV files you captured for the game, and
   compare scenarios with the baseline.

    uv run python scripts/windows_tests/W8_game_impact.py analyze ^
        --baseline presentmon_baseline.csv --scenario capture=presentmon_capture.csv

Procedure: start the game in the SAME place and settings for every run. Start PresentMon for the
game process, start ``run`` for the scenario, run the same fixed game route for the same time, stop
both. Always repeat the baseline to see natural variance (run it at least twice).

The script never decides pass/fail on FPS: no budget has been approved. It reports numbers and the
percentage change versus the baseline for the owner to judge. PresentMon column names differ
between versions, so several spellings of the frame-time column are accepted.
"""

import argparse
import csv
import shutil
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

from _common import Recorder, percentile, rss_mb, stats

FRAME_TIME_COLUMNS = ("MsBetweenPresents", "msBetweenPresents", "FrameTime", "frametime")
SAMPLE_SENTENCES = ("You should not have come here.", "The gate is sealed.")


def nvidia_sample() -> tuple[float | None, float | None]:
    """(GPU utilisation %, VRAM used MiB) from nvidia-smi, or (None, None)."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return (None, None)
    try:
        out = (
            subprocess.run(
                [smi, "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            .stdout.strip()
            .splitlines()[0]
        )
        util, mem = (float(x) for x in out.split(","))
        return (util, mem)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return (None, None)


def system_cpu_percent() -> float | None:
    try:
        import psutil
    except ImportError:
        return None
    return psutil.cpu_percent(interval=None)


class Sampler(threading.Thread):
    def __init__(self, csv_path: Path) -> None:
        super().__init__(daemon=True)
        self.csv_path = csv_path
        self.stop_event = threading.Event()
        self.rows: list[dict[str, float | None]] = []

    def run(self) -> None:
        system_cpu_percent()  # prime psutil
        start = time.perf_counter()
        while not self.stop_event.wait(1.0):
            util, vram = nvidia_sample()
            self.rows.append(
                {
                    "t_s": round(time.perf_counter() - start, 1),
                    "system_cpu_percent": system_cpu_percent(),
                    "process_rss_mib": rss_mb(),
                    "gpu_percent": util,
                    "vram_used_mib": vram,
                }
            )

    def write(self) -> None:
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self.rows[0]) if self.rows else ["t_s"])
            writer.writeheader()
            writer.writerows(self.rows)


def column_stats(rows: list[dict[str, float | None]], key: str) -> dict[str, float] | None:
    values = [float(r[key]) for r in rows if r.get(key) is not None]
    return stats(values) if values else None


def run_load(args: argparse.Namespace, rec: Recorder, stop_at: float) -> dict[str, object]:
    """Generate the requested load until ``stop_at`` (perf_counter time)."""
    counters: dict[str, object] = {"captures": 0, "ocr_runs": 0, "translations": 0}
    if args.scenario == "baseline":
        time.sleep(max(0.0, stop_at - time.perf_counter()))
        return counters

    import dxcam

    roi = tuple(int(x) for x in args.roi.split(",")) if args.roi else None
    camera = dxcam.create(output_idx=args.monitor, output_color="BGR")
    ocr = None
    translate = None
    if args.scenario in ("capture_ocr", "capture_ocr_nllb"):
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(
            text_detection_model_name=args.det_model,
            text_recognition_model_name=args.rec_model,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device="cpu",
            **({"cpu_threads": args.cpu_threads} if args.cpu_threads else {}),
        )
    if args.scenario == "capture_ocr_nllb":
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        if args.cpu_threads:
            torch.set_num_threads(args.cpu_threads)
        tokenizer = AutoTokenizer.from_pretrained(args.nllb_model, src_lang="eng_Latn")
        model = AutoModelForSeq2SeqLM.from_pretrained(args.nllb_model).to("cpu").eval()
        bos = tokenizer.convert_tokens_to_ids("vie_Latn")

        def translate(text: str) -> str:
            inputs = tokenizer(text, return_tensors="pt")
            with torch.inference_mode():
                out = model.generate(
                    **inputs, forced_bos_token_id=bos, num_beams=1, max_new_tokens=96
                )
            return tokenizer.batch_decode(out, skip_special_tokens=True)[0]

    interval = 1.0 / args.fps
    next_ocr = time.perf_counter()
    try:
        while time.perf_counter() < stop_at:
            tick = time.perf_counter()
            frame = camera.grab(region=roi) if roi else camera.grab()
            if frame is not None:
                counters["captures"] += 1
                if ocr is not None and tick >= next_ocr:
                    ocr.predict(frame)
                    counters["ocr_runs"] += 1
                    next_ocr = time.perf_counter() + args.ocr_interval
                    if translate is not None:
                        translate(SAMPLE_SENTENCES[counters["ocr_runs"] % 2])
                        counters["translations"] += 1
            time.sleep(max(0.0, interval - (time.perf_counter() - tick)))
    finally:
        camera.release()
    return counters


def cmd_run(args: argparse.Namespace) -> int:
    rec = Recorder("W8", f"Game impact - resource sampling [{args.scenario}]")
    print(f"W8 run - scenario {args.scenario}, {args.seconds:.0f} s")
    rec.measure("scenario", args.scenario)
    rec.measure("fps_target", args.fps)
    rec.measure("roi", args.roi)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    csv_path = Path(f"W8_{args.scenario}_{stamp}.csv")
    sampler = Sampler(csv_path)
    sampler.start()
    stop_at = time.perf_counter() + args.seconds
    try:
        counters = run_load(args, rec, stop_at)
        rec.check("load generator ran to the end without error", True)
        rec.extra["counters"] = counters
        rec.measure("counters", counters)
    except Exception as exc:  # noqa: BLE001
        rec.check(
            "load generator ran to the end without error", False, f"{type(exc).__name__}: {exc}"
        )
    finally:
        sampler.stop_event.set()
        sampler.join(3)
        sampler.write()
    rec.measure("samples_csv", str(csv_path))
    for key, unit in (
        ("system_cpu_percent", "%"),
        ("process_rss_mib", "MiB"),
        ("gpu_percent", "%"),
        ("vram_used_mib", "MiB"),
    ):
        summary = column_stats(sampler.rows, key)
        rec.measure(key, summary, unit)
    rec.check(
        "GPU/VRAM were sampled (nvidia-smi)", column_stats(sampler.rows, "gpu_percent") is not None
    )
    rec.note(
        "GPU and VRAM here are for the WHOLE system, including the game. Compare against the "
        "baseline run, which has the same game state. FPS comes from PresentMon (see 'analyze')."
    )
    return rec.finish()


def read_frame_times(path: Path) -> list[float]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        column = next((c for c in FRAME_TIME_COLUMNS if c in (reader.fieldnames or [])), None)
        if column is None:
            raise SystemExit(
                f"{path}: no frame-time column among {FRAME_TIME_COLUMNS}; "
                f"found {reader.fieldnames}"
            )
        return [float(row[column]) for row in reader if row.get(column) not in (None, "")]


def fps_summary(frame_ms: list[float]) -> dict[str, float]:
    if not frame_ms:
        return {"frames": 0}
    return {
        "frames": len(frame_ms),
        "avg_fps": round(1000 / statistics.fmean(frame_ms), 2),
        "p95_frame_ms": round(percentile(frame_ms, 95), 2),
        "one_percent_low_fps": round(1000 / percentile(frame_ms, 99), 2),
        "point_one_percent_low_fps": round(1000 / percentile(frame_ms, 99.9), 2),
        "max_frame_ms": round(max(frame_ms), 2),
    }


def cmd_analyze(args: argparse.Namespace) -> int:
    rec = Recorder("W8", "Game impact - FPS analysis (PresentMon CSV)")
    print("W8 analyze")
    base = fps_summary(read_frame_times(args.baseline))
    rec.measure("baseline", base)
    rec.check("baseline has frames", base.get("frames", 0) > 0, str(base))
    comparisons = {}
    for item in args.scenario:
        name, _, path = item.partition("=")
        if not path:
            raise SystemExit("--scenario must look like name=path.csv")
        summary = fps_summary(read_frame_times(Path(path)))
        change = None
        if base.get("avg_fps") and summary.get("avg_fps"):
            change = round((summary["avg_fps"] / base["avg_fps"] - 1) * 100, 2)
        comparisons[name] = {**summary, "avg_fps_change_vs_baseline_percent": change}
        rec.measure(name, comparisons[name])
        rec.check(f"{name} has frames", summary.get("frames", 0) > 0)
    rec.extra["comparisons"] = comparisons
    rec.note(
        "No FPS budget is approved, so no verdict is computed. Judge the change against the "
        "natural run-to-run variance of two baseline runs. 1% low matters more than the average."
    )
    return rec.finish()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="generate load and sample resources")
    run.add_argument(
        "--scenario",
        required=True,
        choices=("baseline", "capture", "capture_ocr", "capture_ocr_nllb"),
    )
    run.add_argument("--seconds", type=float, default=120.0)
    run.add_argument("--fps", type=float, default=10.0, help="capture rate")
    run.add_argument("--ocr-interval", type=float, default=1.0, help="seconds between OCR runs")
    run.add_argument("--monitor", type=int, default=0)
    run.add_argument("--roi", help="left,top,right,bottom")
    run.add_argument("--cpu-threads", type=int, default=None)
    run.add_argument("--det-model", default="PP-OCRv6_small_det", help="UNVERIFIED default")
    run.add_argument("--rec-model", default="PP-OCRv6_small_rec", help="UNVERIFIED default")
    run.add_argument("--nllb-model", default="facebook/nllb-200-distilled-600M")
    run.set_defaults(func=cmd_run)

    analyze = sub.add_parser("analyze", help="compare PresentMon CSV files")
    analyze.add_argument("--baseline", type=Path, required=True)
    analyze.add_argument("--scenario", action="append", default=[], metavar="NAME=CSV")
    analyze.set_defaults(func=cmd_analyze)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
