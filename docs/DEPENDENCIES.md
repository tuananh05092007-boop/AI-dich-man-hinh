# Dependency and Compatibility Plan

**Status:** Proposed; no dependency lock has been validated on the target Windows machine yet.

## Policy
- Pin exact versions after target-platform smoke tests; do not invent a lockfile from an untested environment.
- Separate runtime, development and optional accelerator dependencies.
- PaddleOCR must use the PaddleOCR 3.x API and a compatible PaddlePaddle 3.x CPU build.
- Do not install CUDA-enabled PaddlePaddle by default: approved OCR inference backend is CPU.
- DXGI capture must be verified on Windows 11 with the actual GPU driver.
- OpenAI integration must use the official SDK and Responses API where appropriate; model ID is configuration, not a hard-coded assumption.
- NLLB-200 Distilled 600M licensing and deployment constraints must be reviewed before distribution, especially commercial use.
- Keep optional GPU workloads isolated so the 6 GB VRAM budget remains available to the game.

## Dependency groups (version pins pending)
| Group | Candidate packages / system APIs | Acceptance evidence |
|---|---|---|
| Runtime | Python, PySide6, numpy, opencv-python, Pillow, pydantic, PyYAML | import + application smoke tests on Windows 11 |
| Capture | DXGI Desktop Duplication via a Windows-compatible Python binding or native helper | sustained capture, multi-monitor, device reset and game-mode tests |
| OCR | paddleocr 3.x, paddlepaddle 3.x CPU | PP-OCRv6 Small model download/load/inference; verify output adapter |
| Tracking | rapidfuzz, imagehash, scikit-image (SSIM) | deterministic lifecycle and stale-generation tests |
| Translation | transformers, sentencepiece, torch (CPU local NLLB); official openai SDK | offline NLLB smoke test; cloud timeout/fallback and mocked API tests |
| Storage | sqlite3 (stdlib) | migration, cache and settings tests |
| Quality | pytest, pytest-cov, ruff, mypy (if adopted) | CI and local test pass |

## Risks to resolve
1. Python version compatibility across PaddlePaddle, PaddleOCR, PyTorch/Transformers and PySide6.
2. DXcam/DXGI capture support and performance under Windows 11/game overlays.
3. PaddleOCR 3.x model naming, model download and CPU latency.
4. NLLB memory footprint and latency on CPU; do not assume GPU inference.
5. PySide6 click-through/always-on-top behavior across window modes.
6. Model licensing, redistribution and cache size.
7. OpenAI model selection, pricing, latency and API availability.

## Lockfile gate
After environment validation, generate a Windows-specific lock (prefer uv lock with pinned Python minor and platform markers), record package versions and test output in `docs/ENVIRONMENT-REPORT.md`. No fabricated successful status.
