# System Architecture

**Status:** Draft for Project Owner review  
**Architecture:** Modular Monolith  
**Target:** Windows 11; Ryzen 7 8745H, RTX 4050 Laptop 6 GB, RAM 16 GB

## 1. Product goal
Continuously capture game/application frames, detect English dialogue, recognize and track subtitle changes, translate to natural Vietnamese with context, and render synchronized floating subtitles.

## 2. Approved pipeline
DXGI Desktop Duplication → ROI / region detection → OpenCV + Pillow preprocessing (Adaptive Thresholding, CLAHE) → PaddleOCR PP-OCRv6 Small (PaddlePaddle CPU) → normalization → text tracking → subtitle lifecycle state machine → context manager → translation router → NLLB-200 Distilled 600M or OpenAI API → RAM/SQLite cache → synchronization → PySide6 overlay.

The approved stack in the Master Prompt is binding. Any replacement requires an ADR, evidence/benchmark, and Project Owner approval.

## 3. Runtime boundaries
- **Capture worker:** owns DXGI capture and adaptive frame scheduling; publishes latest frames to a bounded buffer.
- **Vision/OCR worker:** ROI selection, preprocessing, OCR and normalized OCR events.
- **Tracking service:** compares text and image regions; owns subtitle IDs, generations and lifecycle state.
- **Context service:** sliding conversation window, speaker (unknown if uncertain), glossary and game profile.
- **Translation service:** pluggable local/cloud engines, routing, timeout, deduplication and cache.
- **Overlay/UI:** PySide6; consumes only current valid subtitle updates.
- **Persistence:** SQLite for cache/settings/history as appropriate; YAML for default configuration; structured logs.

No microservices. Use bounded queues and asyncio/thread/process workers. Capture must not wait on OCR or translation.

## 4. Data flow and concurrency
1. Capture publishes timestamped frames; consumers may drop stale frames rather than build an unbounded backlog.
2. ROI/preprocessing creates OCR input.
3. OCR emits normalized observations with confidence, bbox, timestamp and region.
4. Tracker stabilizes observations and transitions lifecycle state.
5. Only a new/changed stable generation may request translation.
6. Router checks cache/deduplication, chooses local NLLB or cloud OpenAI according to policy, and falls back locally on cloud failure when possible.
7. Completion is accepted only if subtitle_id and generation_id still match the active generation.
8. Overlay renders the latest accepted translation and clears only after lifecycle confirmation.

### 4.1 Manual translate (F8) path
F8 is a one-shot path beside the automatic one; it reuses capture, OCR, the router and the overlay but **bypasses the lifecycle state machine**. One press creates a `batch_id`; every text block (at most 20 initially) becomes a `TranslationRequest` with `trigger = hotkey` and that `batch_id`. A newer press supersedes the older batch and late results of the old batch are discarded by the generation guard plus the active-batch check. An F8 result takes priority over an Auto result at an overlapping position. Both paths read the same per-game ROI list; with no enabled ROI, F8 uses the whole screen and Auto does not start. See [FLOWS.md](FLOWS.md) and [OVERLAY_AND_ROI.md](OVERLAY_AND_ROI.md); decisions are indexed in [DECISIONS.md](DECISIONS.md).

## 4a. Contract conventions
All cross-module data uses the Pydantic contracts in `contracts/` (specification: [DATA_CONTRACTS.md](DATA_CONTRACTS.md)). Bounding boxes are **monitor-relative physical pixels and always carry `monitor_id`** (never virtual-desktop coordinates). Frames cross queues as lightweight `FrameBufferRef` leases, not pixel copies. Timestamps are UTC-aware; durations come from a monotonic clock.

## 5. Lifecycle
States: NO_TEXT, TEXT_DETECTED, TEXT_STABILIZING, TRANSLATION_PENDING, TRANSLATING, DISPLAYING, TEXT_CHANGED, CLEAR_PENDING, CLEARED, ERROR. The allowed transition graph is defined in DATA_CONTRACTS.md §9; `CLEARED` is terminal and a reappearing subtitle receives a new subtitle_id.

Every subtitle has a stable unique subtitle_id. Every replacement increments generation_id. A stale result is discarded; it must never overwrite a newer generation. Empty OCR is debounced. Translation tasks have timeouts and cancellation or safe-ignore semantics.

## 6. Performance and fault isolation
Measure capture_latency, ocr_latency, tracking_latency, translation_latency, render_latency, end_to_end_latency, cpu_usage, ram_usage, gpu_usage and vram_usage. Bound all queues and caches. Apply per-stage timeouts. A worker failure is surfaced as a structured error and must not terminate the application. Prefer latest-frame semantics for capture.

## 7. UI compatibility
Implement Windowed and Borderless Windowed first. Fullscreen Exclusive is an explicitly unverified compatibility target and requires testing plus fallback. Overlay shows Vietnamese only and supports transparent, always-on-top, click-through behavior (during play), a separate edit mode for repositioning, and a per-game `OverlayStyle` (placement below/above, offset, font size, colours, opacity). Behaviour on the target machine is unverified (Windows test W6).

## 8. Security
Never commit API keys, tokens, credentials, private screenshots or user data. Load secrets from environment variables or Windows credential storage. Redact secrets from logs. Keep game profiles and user settings local.

## 9. Proposed source layout
```
src/ai_screen_translator/
  app/              # startup and orchestration
  capture/          # DXGI adapter, frame buffer, ROI
  vision/           # preprocessing and region detection
  ocr/              # PaddleOCR adapter and normalization
  tracking/         # comparison, state machine, lifecycle
  context/          # sliding window, glossary, game profiles
  translation/      # engine protocol, NLLB, OpenAI, router, cache
  overlay/           # PySide6 rendering and settings UI
  storage/           # SQLite repositories and YAML config
  observability/    # structured logs and metrics
  contracts/        # shared Pydantic models
tests/
  unit/ integration/ fixtures/
configs/
docs/
```

## 10. Milestone 0 exit gates
See [MILESTONE-0.md](MILESTONE-0.md). Documentation alone is not acceptance: target-Windows dependency resolution and smoke tests remain required.
