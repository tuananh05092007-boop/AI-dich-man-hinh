"""W3 - PaddleOCR 3.x with PP-OCRv6 Small on CPU: load, accuracy (CER) and latency.

    uv run python scripts/windows_tests/W3_ocr_ppocr.py
    uv run python scripts/windows_tests/W3_ocr_ppocr.py --dir my_screens --cpu-threads 4

Test images: by default synthetic subtitle-style images are rendered with Pillow from sentences
written for this test (no game assets). For a more meaningful result pass ``--dir`` with your own
screenshots: for each ``name.png`` put the exact expected text in ``name.txt`` next to it. Keep
private screenshots out of the repository.

The exact PP-OCRv6 *small* model names are NOT confirmed (see DECISIONS.md / MILESTONE-0). The
defaults below follow the naming pattern and are a guess; override with ``--det-model`` and
``--rec-model`` and record which names actually load. A failed load is a finding, not a script bug.

CER and latency are *recorded*, not graded: no accuracy or latency budget has been approved yet.
The checks only assert that the model loaded and produced non-empty text.
"""

import argparse
import random
import sys
from pathlib import Path

from _common import Recorder, cer, rss_mb, stats

SENTENCES = (
    "You should not have come here.",
    "The gate is sealed. We cannot go back.",
    "Press E to open the chest.",
    "Quest updated: Find the missing merchant.",
    "I have been waiting for you, traveler.",
    "Your inventory is full.",
    "Elara: We need to leave before sunrise!",
    "Do you accept this mission?",
)


def find_font(size: int):
    from PIL import ImageFont

    for name in (
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def synthetic_samples(count: int, seed: int = 7):
    """Subtitle-like images: plain, outlined on gradient, and noisy background."""
    import numpy as np
    from PIL import Image, ImageDraw

    rng = random.Random(seed)
    font = find_font(34)
    samples = []
    for i in range(count):
        text = SENTENCES[i % len(SENTENCES)]
        style = i % 3
        width, height = 1100, 110
        if style == 0:
            image = Image.new("RGB", (width, height), (15, 15, 15))
            ImageDraw.Draw(image).text((20, 30), text, font=font, fill=(245, 245, 245))
        else:
            base = np.zeros((height, width, 3), dtype=np.uint8)
            gradient = np.linspace(60, 140, width, dtype=np.uint8)
            base[:, :, :] = gradient[None, :, None]
            if style == 2:
                noise = np.random.default_rng(rng.randrange(1 << 30)).integers(
                    0, 40, size=base.shape, dtype=np.uint8
                )
                base = np.clip(base.astype(int) + noise, 0, 255).astype(np.uint8)
            image = Image.fromarray(base)
            draw = ImageDraw.Draw(image)
            for dx in (-2, 0, 2):
                for dy in (-2, 0, 2):
                    draw.text((20 + dx, 30 + dy), text, font=font, fill=(0, 0, 0))
            draw.text((20, 30), text, font=font, fill=(255, 255, 255))
        samples.append((f"synthetic_{i}_style{style}", np.array(image)[:, :, ::-1], text))
    return samples


def directory_samples(folder: Path):
    import cv2

    samples = []
    for image_path in sorted(folder.glob("*.png")):
        truth = image_path.with_suffix(".txt")
        if not truth.exists():
            continue
        image = cv2.imread(str(image_path))
        if image is not None:
            samples.append((image_path.name, image, truth.read_text(encoding="utf-8").strip()))
    return samples


def texts_from_result(result) -> list[str]:
    """Adapter for the PaddleOCR 3.x ``predict`` output (dict-like items with ``rec_texts``)."""
    texts: list[str] = []
    for item in result:
        rec = None
        try:
            rec = item["rec_texts"]
        except (KeyError, TypeError):
            rec = getattr(item, "rec_texts", None)
        if rec is None:
            raise RuntimeError(f"unexpected PaddleOCR result type: {type(item).__name__}")
        texts.extend(str(t) for t in rec)
    return texts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, help="folder of name.png + name.txt pairs")
    parser.add_argument("--det-model", default="PP-OCRv6_small_det", help="UNVERIFIED default")
    parser.add_argument("--rec-model", default="PP-OCRv6_small_rec", help="UNVERIFIED default")
    parser.add_argument("--cpu-threads", type=int, default=None)
    parser.add_argument("--runs", type=int, default=3, help="timed passes over all samples")
    parser.add_argument("--synthetic-count", type=int, default=12)
    args = parser.parse_args()

    rec = Recorder("W3", "PP-OCRv6 Small on CPU (load, CER, latency)")
    print("W3 - PaddleOCR PP-OCRv6 Small, CPU")
    rec.measure("det_model_requested", args.det_model)
    rec.measure("rec_model_requested", args.rec_model)
    rec.measure("cpu_threads", args.cpu_threads)

    try:
        samples = (
            directory_samples(args.dir) if args.dir else synthetic_samples(args.synthetic_count)
        )
    except Exception as exc:  # noqa: BLE001
        rec.check("prepare test images", False, f"{type(exc).__name__}: {exc}")
        return rec.finish()
    rec.check("test images available", len(samples) > 0, f"{len(samples)} samples")
    if not samples:
        return rec.finish()
    rec.measure("image_source", str(args.dir) if args.dir else "synthetic (Pillow)")

    try:
        from paddleocr import PaddleOCR
    except Exception as exc:  # noqa: BLE001
        rec.check("import paddleocr", False, f"{type(exc).__name__}: {exc}")
        return rec.finish()

    kwargs = {
        "text_detection_model_name": args.det_model,
        "text_recognition_model_name": args.rec_model,
        "use_doc_orientation_classify": False,
        "use_doc_unwarping": False,
        "use_textline_orientation": False,
        "device": "cpu",
    }
    if args.cpu_threads:
        kwargs["cpu_threads"] = args.cpu_threads

    import time

    before = rss_mb()
    start = time.perf_counter()
    try:
        ocr = PaddleOCR(**kwargs)
    except Exception as exc:  # noqa: BLE001
        rec.check(
            "PaddleOCR loads with the requested small models", False, f"{type(exc).__name__}: {exc}"
        )
        rec.note(
            "Model names or constructor arguments may differ from PaddleOCR 3.x docs. Look up "
            "the exact PP-OCRv6 small names in the official docs, pass them with --det-model / "
            "--rec-model, and record which pair works. Do not guess in the repository."
        )
        return rec.finish()
    load_ms = (time.perf_counter() - start) * 1000
    rec.check("PaddleOCR loads with the requested small models", True, f"{load_ms:.0f} ms")
    rec.measure("model_load_ms", round(load_ms))
    after = rss_mb()
    if before is not None and after is not None:
        rec.measure("rss_after_load_mb", round(after), "MiB")
        rec.measure("rss_growth_on_load_mb", round(after - before), "MiB")

    # First call = cold start (lazy initialisation); record it separately from warm runs.
    name, image, truth = samples[0]
    start = time.perf_counter()
    try:
        first = texts_from_result(ocr.predict(image))
    except Exception as exc:  # noqa: BLE001
        rec.check("first inference runs", False, f"{type(exc).__name__}: {exc}")
        return rec.finish()
    rec.measure("first_inference_ms", round((time.perf_counter() - start) * 1000))
    rec.check("first inference produced text", bool(first), f"{first!r}"[:120])

    latencies: list[float] = []
    cers: list[float] = []
    empty = 0
    detail = []
    for run_index in range(args.runs):
        for name, image, truth in samples:
            start = time.perf_counter()
            texts = texts_from_result(ocr.predict(image))
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            joined = " ".join(texts)
            if not joined.strip():
                empty += 1
            if run_index == 0:
                cers.append(cer(truth, joined))
                detail.append({"image": name, "cer": round(cers[-1], 3), "text": joined[:120]})
    rec.measure("latency_per_image_ms", stats(latencies))
    rec.measure("cer_mean", round(sum(cers) / len(cers), 4))
    rec.measure("cer_max", round(max(cers), 4))
    rec.measure("exact_matches", sum(1 for c in cers if c == 0.0), f"of {len(cers)}")
    rec.extra["per_image"] = detail
    peak = rss_mb()
    if peak is not None:
        rec.measure("rss_after_runs_mb", round(peak), "MiB")
    rec.check("every warm inference returned non-empty text", empty == 0, f"{empty} empty results")
    rec.note(
        "CER and latency are recorded, not graded: no budget is approved. Synthetic images are "
        "easier than real game frames; repeat with --dir on real screenshots before relying on it. "
        "Measure game impact separately (W8)."
    )
    return rec.finish()


if __name__ == "__main__":
    sys.exit(main())
