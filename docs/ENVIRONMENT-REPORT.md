# Environment Validation Report

**Status: NOT RUN on target machine.**

Target environment from project requirements: Windows 11, AMD Ryzen 7 8745H, NVIDIA RTX 4050 Laptop GPU 6 GB, 16 GB RAM.

No compatibility claim is made until the following commands and smoke tests are run on the target machine and logs are attached.

## Required evidence
- [ ] `python --version` and `uv --version`
- [ ] `uv sync --all-extras` from a clean environment
- [ ] Import smoke tests for PaddleOCR/PaddlePaddle CPU, PySide6, OpenCV, Pillow, RapidFuzz and SSIM implementation
- [ ] DXGI Desktop Duplication capture test on target Windows
- [ ] PP-OCRv6 Small model load and English subtitle inference
- [ ] NLLB-200 Distilled 600M model load and EN→VI inference
- [ ] OpenAI SDK Responses API mocked integration and live test only with owner-provided key
- [ ] CPU/RAM/GPU/VRAM and per-stage latency measurements

Record exact package versions, commands, exit codes, logs, date and machine state. Redact credentials and private game content.
