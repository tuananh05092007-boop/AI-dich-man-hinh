# Product Scope

**Status:** Draft v1 for Project Owner review — 2026-11-22
**Audience:** Project Owner, architect/reviewer, implementer.
**Legend:** **[Approved]** = explicitly approved by the Project Owner (see [DECISIONS.md](DECISIONS.md) for the
date and ID). **[Draft]** = proposed by the implementer, not yet individually approved.

## 1. What this product is

AI Screen Translator is a **personal-use** Windows 11 application that recognizes English text on screen
(primarily in games), translates it to Vietnamese, and shows the Vietnamese text as an overlay.
It is not a commercial product, SaaS or multi-user system **[Approved]**. Any future distribution requires a
separate licence review (notably NLLB-200, see [DEPENDENCIES.md](DEPENDENCIES.md)).

Target machine: Windows 11, Ryzen 7 8745H, 16 GB RAM, RTX 4050 Laptop 6 GB. OCR runs on CPU so the game keeps
the GPU **[Approved]**. Translation direction is English → Vietnamese only **[Approved]**.

## 2. Two independent modes **[Approved]**

| Mode | Purpose | Trigger | Needs ROI? |
|---|---|---|---|
| **A — Auto** | Continuously translate dialogue/subtitles and keep the overlay in sync with the game | F6 toggles it on/off | **Yes** in the first phase |
| **B — Manual** | Translate what is on screen *now*, once | F8 | No (falls back to full screen) |

Both modes can be on at the same time. They share the same ROI list, translation engines, glossary and
overlay. Flow details: [FLOWS.md](FLOWS.md). Overlay and ROI details: [OVERLAY_AND_ROI.md](OVERLAY_AND_ROI.md).

## 3. Hotkeys

| Key | Action | Status |
|---|---|---|
| F6 | Toggle Auto | **[Approved]** |
| F7 | Toggle overlay visibility (hide/show only; does not clear or cancel anything) | **[Approved]** |
| F8 | Manual translate (one-shot) | **[Approved]** |
| F9 | Select ROI (drag a rectangle) | **[Approved]** |
| Ctrl+Alt+E | Toggle overlay **edit mode** | **[Approved]** 2026-11-22 |

* All hotkeys must be rebindable in Settings **[Approved]**. No settings contract exists yet; see
  [DECISIONS.md](DECISIONS.md) open question Q2.
* Before registering a hotkey, the app must check for conflicts with its own hotkeys and with the Windows
  hotkey mechanism, and must report a registration failure to the user. It must never fail silently
  **[Approved]**.
* Hotkeys are **not implemented anywhere in the repository yet** (verified by searching `src/`, `tests/`,
  `scripts/`, `docs/` on 2026-11-22). Registration behaviour with real games is a Windows test (W6).

## 4. Behaviour summary

### 4.1 Manual translate (F8) **[Approved]**
* Translates **all enabled ROIs** of the current game profile; if there is no enabled ROI it translates the
  **whole screen**.
* One-shot: it is not a continuous tracking loop and does not use the dialogue lifecycle state machine.
* One press can produce several text blocks. Initial limit: **20 text blocks per press** (to be benchmarked and
  adjusted).
* A new F8 replaces the previous F8 batch; results of the old batch that arrive late are discarded.
* Where an F8 result overlaps an Auto translation, F8 wins.

### 4.2 Select ROI (F9) **[Approved]**
* Drag to select a region. The ROI is saved in the current game's `GameProfile` and is used by **both** Auto and
  Manual.
* The user can re-select or delete an ROI. A saved ROI is reused when the game is opened again.
* Behaviour when resolution or DPI changes is **deferred**; the limitation and the future plan are documented in
  [OVERLAY_AND_ROI.md](OVERLAY_AND_ROI.md#6-roi-and-resolutiondpi-changes-known-limitation).

### 4.3 Auto **[Approved]**
* First phase: requires at least one enabled ROI. Without an ROI, Auto does not start and tells the user why.
* Uses the dialogue lifecycle (detect → stabilize → translate → display → change → clear) so that unchanged text
  is not re-translated and the overlay disappears when the original text disappears.

### 4.4 Overlay **[Approved]**
* Shows **Vietnamese only**. The game keeps its own English text; the app never redraws or replaces it.
* Position: **below** the original by default; the user can switch to **above**. Draggable, with adjustable font
  size, colour and opacity; always on top.
* During play it is **click-through** and never takes mouse/keyboard input from the game. Repositioning happens
  only in a separate **edit mode**.
* Style is stored **per game** (inside `GameProfile`).

## 5. Out of scope

* `bilingual` and `side_by_side` overlay modes, and the `floating_box` mode, are removed from product scope
  **[Approved]** (this supersedes the older Master Prompt wording; see [DECISIONS.md](DECISIONS.md) D-07).
* Any language pair other than English → Vietnamese.
* F8 as a continuous or tracking mode.
* Redrawing, erasing or replacing the game's original text.
* Guaranteed support for Fullscreen Exclusive (separate compatibility challenge with a fallback strategy).
* Automatic game identification, speaker identification without on-screen evidence.
* A mandatory CI pipeline at this stage **[Approved]** (tests are run manually and reported; see
  [TESTING.md](TESTING.md)).

## 6. Feature tiers **[Draft]**

Tiers describe importance, not build order; build order is in [ROADMAP.md](ROADMAP.md).

| Tier | Features |
|---|---|
| **Must-have** | Windowed/Borderless capture; F9 ROI per game; OCR on ROI; F8 manual translate (multi-ROI, full-screen fallback, 20-block cap); Auto with ROI plus lifecycle (dedupe, change detection, clear on disappearance); Vietnamese-only click-through overlay with placement below/above; local NLLB translation with optional OpenAI via the hybrid router; generation guard against stale results; F6–F9 hotkeys with conflict reporting; the stability mechanisms in §7 |
| **Should-have** | Overlay edit mode and persisted per-game style; translation cache/memory; JSON glossary and character names; sliding context window; translation history view; performance monitor; game profile manager |
| **Later** | Automatic region detection; ROI portability across resolution/DPI; SQLite translation memory; automatic glossary updates; speaker identification when evidence exists; automatic game detection; Fullscreen Exclusive support; packaging, model manager and update mechanism; Nuitka experiment |

## 7. Stability criteria kept despite personal use **[Approved]**

* Generation guard: a stale translation never overwrites newer content.
* Bounded queues with a documented drop/backpressure policy; no uncontrolled threads.
* Timeouts and cancellation on translation and OCR work.
* No blocking work on the UI thread.
* Real measurement of per-stage latency and CPU/RAM/GPU/VRAM; no invented numbers.
* The game stays the priority consumer of GPU and CPU.

## 8. Initial performance targets (to be measured, not guarantees)

From the Master Prompt, kept as hypotheses until benchmarked on the target machine: detect new dialogue within
about 500 ms; display a translation within about 1.5 s for common dialogue; clear stale overlay content within
about 700 ms after disappearance is confirmed. No measurement exists yet.

## 9. Known constraints and unverified areas

* Windows-only behaviour (DXGI capture, overlay click-through, global hotkeys, in-game impact) has **not** been
  verified on the target machine. See [MILESTONE-0.md](MILESTONE-0.md) and the W0–W8 scripts in
  `scripts/windows_tests/`.
* Whether a game receives a key that the app registered as a global hotkey is expected to depend on the Windows
  hotkey mechanism and must be confirmed in W6 before the key assignments are treated as final.
* Open questions awaiting the Project Owner are listed in [DECISIONS.md](DECISIONS.md).
