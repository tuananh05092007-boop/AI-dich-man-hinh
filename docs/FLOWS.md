# Flows

**Status:** Draft — 2026-11-22. Describes intended behaviour; **nothing here is implemented yet** (the repository
contains contracts only). Decision IDs refer to [DECISIONS.md](DECISIONS.md). Terms:
[DATA_CONTRACTS.md](DATA_CONTRACTS.md).

## 1. Shared building blocks

* **Trigger** (`auto` | `hotkey`) records *what caused* a translation. **RegionSource** (`manual_roi` |
  `profile_roi` | `auto_detected`) records *where the OCR region came from*. They are independent.
* **Generation guard.** Every result is applied only if its `(subtitle_id, generation_id)` is still the active
  key. Applies to both flows.
* **ROI list** = the enabled `RoiConfig` entries of the current `GameProfile`. Auto and Manual read the same list.
* **Hotkeys** are listed in [PRODUCT_SCOPE.md](PRODUCT_SCOPE.md#3-hotkeys).

## 2. Auto flow (mode A, F6)

Precondition: at least one enabled ROI (D-15). If there is none, Auto refuses to start and tells the user to
press F9 first.

1. Capture publishes the latest frame; stale frames may be dropped (latest-frame semantics).
2. Each enabled ROI is cropped and preprocessed (adaptive threshold / CLAHE per game profile).
3. OCR runs on the ROI (CPU) and emits an `OCRObservation` with `region_id` of the ROI.
4. The tracker compares with the previous text of that ROI (exact, fuzzy, image comparison) and assigns
   `subtitle_id` / `generation_id`. Unchanged text never produces a new request.
5. After the text is stable, a `TranslationRequest` with `trigger = auto` and no `batch_id` is queued.
6. The router consults cache/translation memory, then chooses the local NLLB model or OpenAI; on cloud failure it
   falls back locally where possible.
7. The result is accepted only if the generation guard passes; an `OverlayUpdate` (no `batch_id`) is sent to the
   overlay.
8. If the text changes, the generation increments and the old translation is discarded. When OCR stays empty past
   the debounce, the lifecycle reaches `CLEARED` and the overlay message is removed. If the same subtitle
   disappears and later reappears, it receives a new `subtitle_id`.

Lifecycle states and allowed transitions: [DATA_CONTRACTS.md §9](DATA_CONTRACTS.md#9-lifecycle-vocabulary-and-allowed-transitions).

## 3. Manual flow (mode B, F8)

F8 is one-shot and does **not** use the lifecycle state machine (C5).

1. Debounce: an F8 inside the debounce window (about 300 ms, P-02 provisional) is ignored.
2. A new `batch_id` is created. Any earlier F8 batch becomes **superseded**: its pending work is cancelled where
   possible, its overlay messages are removed, and any result that still arrives for it is discarded (D-13).
3. One fresh frame is captured.
4. Regions to process:
   * one or more enabled ROIs → each ROI is a region (`RegionSource.PROFILE_ROI`, or `MANUAL_ROI` straight after
     F9);
   * no enabled ROI → the whole screen of the profile's monitor; OCR text detection finds the blocks
     (`RegionSource.AUTO_DETECTED`).
5. OCR returns text blocks. At most **20 blocks** per press are processed (D-18); with more than 20, the first
   20 in reading order are kept and a visible notice tells the user (P-03).
6. Each block gets its own `subtitle_id` (recommended `f8_<batch_id>_<n>`) and `generation_id = 1` (P-05) and a
   `TranslationRequest` with `trigger = hotkey` and the batch's `batch_id`.
7. Translation runs through the same router/engines as Auto.
8. A result is shown only if its key still belongs to the **active** F8 batch. Results for a superseded batch are
   dropped (recorded as skipped with `cancelled`).
9. Each accepted block becomes an `OverlayUpdate` carrying the `batch_id`. The overlay can remove all messages of
   one batch together.

Open: how long F8 overlays stay and how they are cleared (Q1).

### 3.1 F8 and Auto at the same position (D-14)

The overlay compares each new F8 message with existing messages on the same monitor. If the overlap coefficient
(intersection area ÷ smaller box) is at least 0.5 (P-01), the F8 message is shown and the Auto message is hidden
there. Auto keeps running in the background; when the F8 message is removed or replaced, the current Auto message
for that subtitle may reappear. Non-overlapping messages coexist.

## 4. ROI selection flow (F9)

1. F9 opens a full-screen selection layer for the current monitor.
2. The user drags a rectangle (cancel with Esc — Draft). The box is stored as monitor-relative physical pixels
   with `monitor_id` (see [DATA_CONTRACTS.md §4](DATA_CONTRACTS.md#4-boundingbox-and-monitor-identity)).
3. The ROI is saved to the current `GameProfile` immediately and is available to both modes; the user can
   re-select or delete it.
4. When the game starts again, the saved ROIs are reused. A resolution or DPI change is a known limitation
   ([OVERLAY_AND_ROI.md §6](OVERLAY_AND_ROI.md#6-roi-and-resolutiondpi-changes-known-limitation)).

## 5. Overlay edit-mode flow (Ctrl+Alt+E)

1. Press the edit-mode key: the overlay becomes interactive (not click-through) with a visible indicator (P-04) so
   the user can drag messages.
2. The 60 s idle timer (D-16) starts at the last interaction and resets on every further interaction. It does not
   run while a drag or edit is in progress.
3. The user presses the key again, or the timer expires: edit mode ends, the new position/style is saved to the
   game's `OverlayStyle`, and the overlay returns to click-through.
4. Hotkey registration failure or a failure to restore click-through must be reported, never ignored.

## 6. Cancellation, timeout and backpressure summary

| Situation | Behaviour |
|---|---|
| Text changes while a translation is pending | Result is dropped by the generation guard |
| New F8 while the previous batch is pending | Old batch cancelled/discarded; new batch proceeds |
| Translation exceeds `deadline_ms` | Request fails with a structured error; capture/OCR continue; local fallback is attempted where appropriate |
| Queue full | Documented drop policy; latest visible content wins; memory stays bounded |
| Worker exception | Surfaced as a structured error; application stays alive |

Queue sizes and exact drop policies are defined during implementation and benchmarked in Milestone 6.
