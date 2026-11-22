# Roadmap

**Status:** Draft — 2026-11-22. Milestone order follows the Master Prompt; scope follows
[PRODUCT_SCOPE.md](PRODUCT_SCOPE.md). Statuses use the vocabulary **Implemented / Partially implemented /
Tested / Not tested / Blocked / Planned** and never claim more than recorded evidence.

**Current focus: Milestone 0 only.** Milestone 1 has **not** been started and must not start until the Project
Owner accepts Milestone 0.

## Milestone 0 — Repository and technical validation (IN PROGRESS)

Per-item status lives in [MILESTONE-0.md](MILESTONE-0.md). Summary:

| Area | State |
|---|---|
| Shared contracts (v0.2) and schemas | Implemented; tested on Linux/CPython 3.11 only; independent review and Windows re-run pending |
| Architecture and scope documents | Drafted; awaiting owner review |
| Windows validation scripts W0–W8 | Written; **not yet run on Windows** |
| DXGI, PP-OCRv6 Small, NLLB, OpenAI, overlay/hotkeys, in-game impact | **Blocked on Windows runs** (W2–W8) |

Exit criteria: [MILESTONE-0.md](MILESTONE-0.md#exit-criteria).

## Milestone 1 — Minimum viable product (PLANNED, not started)

Scope aligned with the approved product decisions:

* Basic screen capture (Windowed/Borderless first).
* F9 manual ROI selection, stored in the `GameProfile`.
* OCR on the ROI.
* English → Vietnamese translation.
* Vietnamese-only click-through overlay.
* F8 manual translate (all enabled ROIs; full-screen fallback; 20-block cap; newest batch wins).
* Manual start/stop (F6, F7).

Goal: capture text, recognize it, translate it, display the result. Entry gate: Milestone 0 accepted.

## Milestone 2 — Automatic region detection (PLANNED)

Candidate region detection, ROI processing and tracking, OCR preprocessing, adaptive FPS. Goal: less manual
configuration and less unnecessary processing. (In the first phase Auto still requires an ROI; automatic
detection relaxes that later.)

## Milestone 3 — Dialogue tracking (PLANNED)

Exact and fuzzy matching, image comparison, the lifecycle state machine, disappearance detection, duplicate
request prevention. Goal: translations stay in sync with changing dialogue. F8 text blocks bypass this state
machine by design.

## Milestone 4 — Context-aware translation (PLANNED)

Context window, translation memory, glossary and game terminology, hybrid local/API routing, translation style.

## Milestone 5 — Complete desktop application (PLANNED)

Main PySide6 UI, overlay edit mode and per-game style persistence, game profiles, history, settings (including
hotkey rebinding), model manager, performance monitor.

## Milestone 6 — Performance and reliability (PLANNED)

Resource management, queue tuning, caching, error recovery, benchmarking (including the 20-block F8 limit and
the overlap threshold), memory-leak investigation, long-session stability.

## Milestone 7 — Packaging and release (PLANNED)

PyInstaller build, model download management, configuration, update strategy, release notes. Nuitka remains a
later experiment. Distribution requires the NLLB licence check.

## Cross-cutting decisions that affect scheduling

* No mandatory CI for now; tests are run manually and reported with real results (D-20 in
  [DECISIONS.md](DECISIONS.md)).
* ROI portability across resolution/DPI is deferred (limitation documented in
  [OVERLAY_AND_ROI.md](OVERLAY_AND_ROI.md)).
* Fullscreen Exclusive is a separate compatibility challenge, validated after Windowed and Borderless.
