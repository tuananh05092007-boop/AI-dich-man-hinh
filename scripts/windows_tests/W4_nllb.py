"""W4 - NLLB-200 Distilled 600M on CPU: load, EN->VI smoke test, RAM and latency.

    uv run python scripts/windows_tests/W4_nllb.py
    uv run python scripts/windows_tests/W4_nllb.py --threads 4 --beams 1

The model is forced onto the CPU so the game keeps the GPU. The first run downloads about 2.4 GB
from Hugging Face into the user cache (not into the repository). License: NLLB-200 weights are
CC-BY-NC-4.0; this is fine for personal use but must be re-checked before any distribution.

Output quality is NOT graded automatically. The checks only assert that translations are
non-empty, differ from the source and contain Vietnamese characters; read the printed
translations and judge them yourself (the report keeps them for review).
"""

import argparse
import re
import sys
import time

from _common import Recorder, rss_mb, stats

MODEL_ID = "facebook/nllb-200-distilled-600M"
SOURCE_LANG = "eng_Latn"
TARGET_LANG = "vie_Latn"

SENTENCES = (
    "You should not have come here.",
    "The gate is sealed. We cannot go back.",
    "Press E to open the chest.",
    "Quest updated: Find the missing merchant.",
    "I have been waiting for you, traveler.",
    "Your inventory is full.",
    "We need to leave before sunrise!",
    "Do you accept this mission?",
)
VIETNAMESE_CHARS = re.compile(
    "[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument("--threads", type=int, default=None, help="torch CPU threads")
    parser.add_argument("--beams", type=int, default=1, help="1 = greedy (fastest)")
    parser.add_argument("--max-new-tokens", type=int, default=96)
    parser.add_argument("--runs", type=int, default=3, help="timed passes over all sentences")
    args = parser.parse_args()

    rec = Recorder("W4", "NLLB-200 Distilled 600M on CPU")
    print("W4 - NLLB-200 Distilled 600M, CPU")
    rec.measure("model", args.model)
    rec.measure("beams", args.beams)
    rec.measure("max_new_tokens", args.max_new_tokens)

    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except Exception as exc:  # noqa: BLE001
        rec.check("import torch / transformers", False, f"{type(exc).__name__}: {exc}")
        return rec.finish()

    if args.threads:
        torch.set_num_threads(args.threads)
    rec.measure("torch_threads", int(torch.get_num_threads()))

    before = rss_mb()
    start = time.perf_counter()
    try:
        tokenizer = AutoTokenizer.from_pretrained(args.model, src_lang=SOURCE_LANG)
        model = AutoModelForSeq2SeqLM.from_pretrained(args.model)
        model.to("cpu").eval()
    except Exception as exc:  # noqa: BLE001
        rec.check("model and tokenizer load", False, f"{type(exc).__name__}: {exc}")
        rec.note("A download failure usually means no network or a blocked Hugging Face host.")
        return rec.finish()
    load_s = time.perf_counter() - start
    rec.check("model and tokenizer load", True, f"{load_s:.1f} s")
    rec.measure("load_seconds", round(load_s, 1), "s")
    after = rss_mb()
    if before is not None and after is not None:
        rec.measure("rss_after_load_mb", round(after), "MiB")
        rec.measure("rss_growth_on_load_mb", round(after - before), "MiB")

    forced_bos = tokenizer.convert_tokens_to_ids(TARGET_LANG)
    rec.check(
        "target language token vie_Latn exists",
        isinstance(forced_bos, int) and forced_bos != tokenizer.unk_token_id,
        str(forced_bos),
    )

    def translate(text: str) -> tuple[str, int]:
        inputs = tokenizer(text, return_tensors="pt")
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                forced_bos_token_id=forced_bos,
                num_beams=args.beams,
                max_new_tokens=args.max_new_tokens,
            )
        return tokenizer.batch_decode(output, skip_special_tokens=True)[0], int(output.shape[-1])

    start = time.perf_counter()
    try:
        first, _ = translate(SENTENCES[0])
    except Exception as exc:  # noqa: BLE001
        rec.check("first translation runs", False, f"{type(exc).__name__}: {exc}")
        return rec.finish()
    rec.measure("first_translation_ms", round((time.perf_counter() - start) * 1000))
    rec.check("first translation is non-empty", bool(first.strip()), first[:100])

    latencies: list[float] = []
    outputs: dict[str, str] = {}
    out_tokens = 0
    for _ in range(args.runs):
        for sentence in SENTENCES:
            start = time.perf_counter()
            text, length = translate(sentence)
            latencies.append((time.perf_counter() - start) * 1000)
            outputs[sentence] = text
            out_tokens += length
    rec.measure("latency_per_sentence_ms", stats(latencies))
    rec.extra["translations"] = outputs
    for source, target in outputs.items():
        print(f"    {source}  ->  {target}")

    rec.check(
        "all translations non-empty",
        all(t.strip() for t in outputs.values()),
    )
    rec.check(
        "no translation is identical to its source",
        all(t.strip() != s for s, t in outputs.items()),
    )
    rec.check(
        "every translation contains Vietnamese characters",
        all(VIETNAMESE_CHARS.search(t) for t in outputs.values()),
        "heuristic only; a short reply may legitimately lack diacritics",
    )
    peak = rss_mb()
    if peak is not None:
        rec.measure("rss_after_runs_mb", round(peak), "MiB")
    total_s = sum(latencies) / 1000
    if total_s > 0:
        rec.measure("output_tokens_per_second", round(out_tokens / total_s, 1), "tok/s")
    rec.note(
        "Translation quality needs human review of extra['translations'] in the report. No "
        "quality score is claimed. Compare latency with the 1.5 s display target in "
        "PRODUCT_SCOPE.md, but remember OCR and capture add to it."
    )
    return rec.finish()


if __name__ == "__main__":
    sys.exit(main())
