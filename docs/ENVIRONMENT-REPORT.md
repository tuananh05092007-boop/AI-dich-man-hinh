# Environment Validation Report

**Status: PARTIALLY VALIDATED on the Project Owner's Windows machine.**

Target environment from project requirements: Windows 11, AMD Ryzen 7 8745H, NVIDIA RTX 4050 Laptop GPU 6 GB, 16 GB RAM.

## Evidence reported by Project Owner

| Check | Result | Evidence |
|---|---|---|
| Python | PASS | CPython 3.11.9 at `C:\Users\anhho\AppData\Local\Programs\Python\Python311\python.exe` |
| uv environment | PASS | `uv sync --all-extras` created `.venv` |
| Dependency resolution | PASS | 15 packages resolved, prepared and installed |
| Contract tests | PASS | `uv run pytest -q` → 6 passed in 0.51s |
| JSON Schema export | PASS | `uv run python scripts/export_schemas.py` → 7 schemas exported to `schemas/` |

Installed baseline versions reported:
- Pydantic 2.14.4
- pytest 8.4.2
- pytest-cov 6.3.0
- Ruff 0.17.6

These results validate the current lightweight project scaffold and contract tests only. They do **not** validate the full runtime stack or the generated schema files against an external consumer.

## Required evidence still outstanding
- [ ] Confirm Windows build and exact hardware/driver snapshot for this validation session.
- [ ] Run Ruff lint: `uv run ruff check .`
- [ ] Inspect generated JSON Schema files and commit them to the feature branch.
- [ ] Validate the full dependency matrix for PaddleOCR/PaddlePaddle CPU, PyTorch/Transformers, PySide6 and DXGI binding options.
- [ ] Clean install of the complete, pinned runtime environment from a committed Windows lockfile.
- [ ] DXGI Desktop Duplication capture test on target Windows.
- [ ] PP-OCRv6 Small model load and English subtitle inference.
- [ ] NLLB-200 Distilled 600M model load and EN→VI inference.
- [ ] OpenAI SDK Responses API integration test using an owner-provided key, kept out of source control.
- [ ] CPU/RAM/GPU/VRAM and per-stage latency measurements.

Record exact package versions, commands, exit codes, logs, date and machine state. Redact credentials and private game content.

## Current conclusion
The Python scaffold and shared contract tests pass on the Project Owner's machine. Milestone 0 remains in progress until the outstanding compatibility, hardware, dependency-lock and independent-review gates are complete.
