# Testing and Evaluation Strategy

## Test layers
- **Unit:** contract validation, normalization, ROI transforms, text similarity, lifecycle transitions, generation guards, routing decisions, cache keys and expiry.
- **Integration:** DXGI adapter, preprocessing→OCR, OCR→tracker, tracker→translation router, SQLite cache, overlay update delivery.
- **System:** real game screenshots, Windowed/Borderless overlay, multi-monitor, DPI scaling, alt-tab, game focus and recovery after device/API errors.
- **Performance:** repeatable warm/cold runs; report median, p95 and max latency plus CPU/RAM/GPU/VRAM.
- **Human evaluation:** Vietnamese fluency, meaning preservation, tone/character consistency and game glossary adherence.

## Metrics
Capture: capture_latency. OCR: ocr_latency, CER, WER, Levenshtein. Tracking: tracking_latency, false-change rate, missed-change rate, stale-result rejection rate. Translation: translation_latency, SacreBLEU, chrF++, optional COMET and human evaluation. Rendering: render_latency. End-to-end: end_to_end_latency. Resources: cpu_usage, ram_usage, gpu_usage, vram_usage.

## Required race-condition tests
1. Generation 1 translation completes after generation 2: generation 1 must be discarded.
2. Duplicate OCR event for unchanged text: only one translation request.
3. Subtitle disappears briefly then returns: debounce prevents flicker/false clear.
4. Queue saturation: bounded memory and documented drop/backpressure behavior.
5. API timeout/offline: capture and OCR continue; local fallback is attempted where appropriate.
6. OCR or translation worker exception: application remains alive and emits structured error.
7. Cache hit: no unnecessary inference or API call.

## Test data
Maintain three separated datasets: OCR Game Dataset, Game Dialogue EN-VI Dataset and Subtitle Lifecycle Dataset. Store source, license, split and annotation provenance. Do not commit copyrighted game assets or private screenshots without permission.

## Contract verification commands
```bash
pip install -e ".[dev]"
python -m pytest                          # includes schema-staleness and docs-drift tests
python -m ruff check . && python -m ruff format --check .
python scripts/export_schemas.py --check  # fails if committed schemas are stale
```

## CI baseline
Run pytest on supported Python versions, lint, contract/schema checks and static checks. Hardware-dependent DXGI and performance tests are tagged and run manually or on a Windows self-hosted runner; CI must not pretend those tests ran.
