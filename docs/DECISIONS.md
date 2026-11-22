# Decision Log

**Status:** 2026-11-22. This file is the single index of product and engineering decisions. Detailed
architecture decisions that need long-form reasoning stay in [ADR/](ADR/) (ADR 0001–0003 are still
**Proposed**; owner acceptance pending).

Status vocabulary: **Approved** (explicit owner approval), **Provisional** (implementer's working value, not
individually approved, may change after measurement), **Open** (needs an owner decision).

## 1. Approved decisions

| ID | Decision | Date | Notes |
|---|---|---|---|
| D-01 | Technology baseline from the Master Prompt (DXGI + ROI, OpenCV/Pillow, PaddleOCR 3.x + PP-OCRv6 Small + PaddlePaddle CPU, RapidFuzz/imagehash/SSIM, NLLB-200 Distilled 600M + OpenAI via hybrid router, PySide6, SQLite + YAML, modular monolith) | earlier | Changing it needs evidence and owner approval |
| D-02 | Claude is the primary implementer; ChatGPT is architect and independent reviewer and writes code only if Claude cannot continue or the owner asks; single-writer policy | earlier, reaffirmed 2026-11-22 | |
| D-03 | Git sync **plan A**: create backup branches first; on `feature/m0-data-contracts` keep the feature's schemas and `tests/unit/test_contracts.py`, take `docs/ENVIRONMENT-REPORT.md` and `uv.lock` from `architect/milestone-0`, run `uv lock`, re-verify. No force-push. PR #8 is not merged into `main` without explicit permission | 2026-11-22 | Executed; result in §4 |
| D-04 | Personal-use product (not commercial/SaaS/multi-user) | earlier | |
| D-05 | Two independently toggled modes: A Auto, B Manual | earlier | |
| D-06 | Hotkeys: F6 Auto, F7 overlay visibility, F8 manual translate, F9 select ROI; all rebindable in Settings | earlier | |
| D-07 | Overlay shows Vietnamese only; the game's English text is never redrawn; `bilingual`, `side_by_side` (and the unused `floating_box`) are out of scope | earlier, confirmed 2026-11-22 | **Supersedes** Master Prompt §III-F wording about "below or beside the original" and "multiple overlay display modes". The Project instructions still contain the old wording and should be updated by the owner |
| D-08 | `OverlayDisplayMode` is deleted and replaced by `OverlayPlacement` (`below`/`above`) and `OverlayStyle` | 2026-11-22 | Contract change C2/C3 |
| D-09 | Add `Trigger` (`auto`/`hotkey`) and `batch_id` to `TranslationRequest`; `batch_id` required iff `hotkey` | 2026-11-22 | Contract change C1 |
| D-10 | `RegionSource` (where the region came from) stays separate from `Trigger` (what caused the translation) | earlier | |
| D-11 | ROIs are stored per `GameProfile` and shared by Auto and Manual; no new ROI fields (empty or all-disabled list = no ROI) | 2026-11-22 | Contract change C4 |
| D-12 | F8 translates all enabled ROIs; with no enabled ROI it translates the whole screen; F8 is one-shot | 2026-11-22 | |
| D-13 | A new F8 replaces the previous F8 batch; late results of the old batch are discarded | 2026-11-22 | |
| D-14 | F8 takes priority over an Auto translation at an overlapping position | 2026-11-22 | Overlap rule is Provisional (P-01) |
| D-15 | In the first phase Auto requires at least one ROI | 2026-11-22 | |
| D-16 | Overlay has a separate **edit mode** for drag/drop; while playing it is click-through. Toggle: **Ctrl+Alt+E**, rebindable. Auto-exit after **60 s** since the last interaction; the timer resets on interaction; no auto-exit while dragging or editing; on exit the overlay returns to click-through | 2026-11-22 | The key must be conflict-checked before registration |
| D-17 | `OverlayStyle` is stored per game | 2026-11-22 | |
| D-18 | Initial limit of 20 text blocks per F8 press; recorded for benchmarking | 2026-11-22 | |
| D-19 | No new `LifecycleReason`; F8 blocks bypass the lifecycle state machine (C5). Contract version moves from `0.1` to `0.2` (C6) | 2026-11-22 | |
| D-20 | No mandatory CI at this stage | 2026-11-22 | |
| D-21 | Keep stability mechanisms (generation guard, bounded queues, timeouts, no UI-thread blocking, real measurements) | earlier | |
| D-22 | ROI behaviour on resolution/DPI change is deferred; the limitation and the future plan are documented | earlier | See OVERLAY_AND_ROI.md §6 |
| D-23 | Do not start Milestone 1 until Milestone 0 is accepted | earlier, reaffirmed 2026-11-22 | |

## 2. Provisional working values (not individually approved)

| ID | Value | Why it is provisional |
|---|---|---|
| P-01 | "Overlapping position" = same monitor and **overlap coefficient ≥ 0.5** (intersection area ÷ area of the smaller box) | Chosen because an F8 text block is usually a sub-area of the ROI that Auto uses, where IoU would under-report overlap. Threshold needs tuning on real screens |
| P-02 | F8 debounce of about 300 ms (a press inside the window is ignored; outside it, it replaces the batch) | Prevents accidental double-press cost; not yet discussed with the owner |
| P-03 | If OCR finds more than 20 blocks, process the first 20 in reading order (top-to-bottom, then left-to-right) and show a visible notice; never drop silently | The owner approved the cap, not the overflow policy |
| P-04 | Edit mode shows a clear visual indicator (border) and can also be toggled from the main window or tray | Proposed to avoid an overlay stuck in the wrong state; not individually approved |
| P-05 | F8 blocks get their own `subtitle_id` (recommended form `f8_<batch_id>_<n>`) with `generation_id = 1` | Needed so the generation guard still works; naming is advisory |
| P-06 | Default overlay style values in the contract (below, offset 0/0, 24 px, `#FFFFFF` on `#000000`, opacity 0.85) | Reasonable defaults; no UX testing yet |

## 3. Open questions for the Project Owner

| ID | Question | Why it matters |
|---|---|---|
| Q1 | How long does an F8 overlay stay, and how does the user clear it (timeout? a key? only replaced by the next F8?) | `OverlayUpdate.expires_at` is required, so a default is needed; "clear all results of one F8" is approved but has no trigger yet. The contract supports clearing by `batch_id` |
| Q2 | Where do rebindable hotkeys live? There is no settings contract in v0.2 | Needed in Milestone 5; adding a settings contract is a contract change that needs approval |
| Q3 | Please update the Project instructions (Master Prompt) to remove "beside the original" and "multiple overlay display modes", which now conflict with D-07 | Avoids future agents re-introducing the removed modes |
| Q4 | Should ADR 0001–0003 move from Proposed to Accepted at Milestone 0 acceptance? | Documentation hygiene |

## 4. Git synchronisation record (D-03)

* Backup branches pushed (not force-pushed): `backup/pre-sync-20261122-main` = `f6cc0eb`,
  `backup/pre-sync-20261122-feature` = `04b50fc`, `backup/pre-sync-20261122-architect` = `c15f101`.
* `feature/m0-data-contracts`: `04b50fc` → `fb2838d` (cherry-pick of `2193c78`, environment report) → `b02613b`
  (`uv.lock` taken from architect, then `uv lock`, adding `jsonschema` and four transitive packages).
* `main` is unchanged (`f6cc0eb`). PR #8 is not merged.
