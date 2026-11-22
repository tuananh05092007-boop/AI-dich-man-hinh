# AI Screen Translator

Ứng dụng Windows dịch hội thoại tiếng Anh trên màn hình/game sang tiếng Việt theo thời gian thực.

> **Project status:** Milestone 0 — Architecture and Environment (in progress).  
> Chưa bắt đầu triển khai pipeline tính năng. Chưa xác nhận môi trường Windows, DXGI, PP-OCRv6 hay NLLB trên máy đích.

## Approved stack
- Capture: DXGI Desktop Duplication; ROI + adaptive FPS.
- Vision: OpenCV, Pillow, Adaptive Thresholding, CLAHE.
- OCR: PaddleOCR 3.x, PP-OCRv6 Small, PaddlePaddle CPU.
- Tracking: RapidFuzz, image hashing, SSIM, Python state machine.
- Translation: NLLB-200 Distilled 600M + OpenAI API through a hybrid router.
- UI: PySide6 transparent always-on-top click-through overlay.
- Architecture: Modular Monolith, bounded queues, asyncio/workers, SQLite and YAML.

See [Product scope](docs/PRODUCT_SCOPE.md), [Roadmap](docs/ROADMAP.md), [Decisions](docs/DECISIONS.md), [Flows](docs/FLOWS.md), [Overlay and ROI](docs/OVERLAY_AND_ROI.md), [Architecture](docs/ARCHITECTURE.md), [Contracts](docs/DATA_CONTRACTS.md), [Dependencies](docs/DEPENDENCIES.md), [Testing](docs/TESTING.md), and [Milestone 0](docs/MILESTONE-0.md).

## Development rules
- Never commit secrets, API keys, private screenshots or copyrighted game assets without permission.
- Work on feature branches; never push directly to `main`.
- Every change must include tests and a PR handoff report.
- Do not claim hardware tests passed without recorded evidence.
- Milestone 1 is blocked until Milestone 0 exit criteria are reviewed and approved.
