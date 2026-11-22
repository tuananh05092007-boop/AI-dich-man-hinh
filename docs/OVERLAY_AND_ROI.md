# Overlay and ROI

**Status:** Draft — 2026-11-22. Intended behaviour; nothing here is implemented yet. Whether the PySide6 techniques
below work on the target machine and in real games is **unverified** and is covered by Windows test W6.

## 1. Overlay principles **[Approved]**

* Vietnamese text only. The game's English text is never redrawn or replaced.
* Default placement **below** the original text; the user may switch to **above**.
* Adjustable font size, text colour, background colour and opacity; always on top; transparent background.
* During play the overlay is **click-through** and must not take mouse or keyboard input from the game.
* Messages appear and update automatically and disappear when their source disappears (Auto) or when replaced or
  cleared (F8).
* Style is stored **per game** in `GameProfile.overlay_style` (D-17).

Targets: Windowed and Borderless Windowed first. Fullscreen Exclusive is a separate compatibility challenge: an
overlay is **not** assumed to appear above an exclusive-fullscreen game even if capture works, and a fallback
strategy is required (see §7).

## 2. Contract mapping (schema v0.2)

| Concept | Contract field |
|---|---|
| Where the overlay anchors | `OverlayUpdate.bbox` — box of the original text, monitor-relative pixels |
| Below / above | `OverlayStyle.placement` (`below` \| `above`) |
| Manual nudge from the anchor | `OverlayStyle.offset_x`, `offset_y` (pixels, signed) |
| Font size | `OverlayStyle.font_size_px` |
| Colours and opacity | `OverlayStyle.text_color`, `background_color` (`#RRGGBB`), `opacity` |
| Which game's style | `GameProfile.overlay_style` |
| Which F8 batch a message belongs to | `OverlayUpdate.batch_id` (null for Auto messages) |

`OverlayUpdate` no longer has a display mode, and `OverlayDisplayMode` no longer exists. Full field rules:
[DATA_CONTRACTS.md](DATA_CONTRACTS.md).

## 3. Edit mode vs play mode **[Approved]**

| | Play mode (default) | Edit mode |
|---|---|---|
| Input | Click-through; the game receives all input | Overlay is interactive so messages can be dragged |
| Activated by | Startup, leaving edit mode | **Ctrl+Alt+E** (rebindable) |
| Saved | — | New offset/style stored in the game's `OverlayStyle` on exit |

Rules (D-16):

1. The idle timer is **60 seconds** from the last interaction.
2. Every interaction resets it.
3. It does not expire while a drag or other edit operation is in progress.
4. On exit (key pressed again or timeout) the overlay **must** return to click-through.
5. Failure to restore click-through must be surfaced to the user.

Draft additions (P-04, not individually approved): a visible edit-mode indicator and a toggle in the main window
or tray, so the user is never stuck in an unknown state.

How click-through is toggled at runtime (Qt window flags versus the Win32 extended window style) and whether the
toggle flickers or loses always-on-top is an open technical question tested in W6.

## 4. Hotkey registration

Hotkeys: F6, F7, F8, F9, Ctrl+Alt+E ([PRODUCT_SCOPE.md](PRODUCT_SCOPE.md#3-hotkeys)).

Before registering, the app must:

1. check the key against its own hotkeys and reject duplicates;
2. attempt the Windows registration and treat failure as "already in use or refused", reporting the key and the
   reason to the user;
3. never register silently or ignore a failure.

Known risks to verify in W6 (none of these has been tested):

* A globally registered key is expected to be consumed by the registration and therefore not reach the game. If a
  game uses F6–F9 (for example for quick-save or quick-load), the owner must rebind.
* On keyboard layouts where AltGr is reported as Ctrl+Alt, Ctrl+Alt+E may also type a character. The owner's
  layout must be checked.
* Another application may already hold one of the keys.

## 5. F8 versus Auto at the same position **[Approved]**, rule **[Provisional]**

If an F8 message overlaps an Auto message on the same monitor, the F8 message is shown and the Auto message is
hidden at that position. "Overlap" is provisionally defined as the **overlap coefficient** (intersection area ÷
area of the smaller box) of the anchor boxes being at least **0.5** (P-01). The threshold must be tuned with real
screens. Non-overlapping messages coexist. Details: [FLOWS.md §3.1](FLOWS.md#31-f8-and-auto-at-the-same-position-d-14).

## 6. ROI and resolution/DPI changes (known limitation)

ROIs are stored in the `GameProfile` as monitor-relative **physical pixels** (`RoiConfig.bbox`), together with an
optional `reference_resolution` and `monitor_id`.

**Current limitation (deferred, D-22):** if the game resolution, monitor, or Windows DPI scaling changes after an
ROI was saved, the stored pixels may no longer cover the intended text. The contracts reject an ROI that does not
fit inside `reference_resolution` or is on another monitor than the profile, but they define **no scaling
algorithm**.

**Planned direction (not approved, not implemented):** when the current capture size differs from
`reference_resolution`, either (a) scale ROI boxes proportionally and ask the user to confirm, or (b) mark the ROIs
stale and ask the user to press F9 again. Per-monitor DPI handling belongs to the capture module (M0-05/M1).
Until then the user re-selects the ROI after changing resolution.

Rules that already hold:

* ROIs are per game, shared by Auto and Manual, and reused when the game is reopened.
* An empty or all-disabled ROI list means "no ROI": Auto does not start; F8 uses the whole screen.
* F8 with several enabled ROIs processes all of them, within the 20-block cap (D-18).
* A full-screen F8 labels its regions `auto_detected`, because text detection, not the user, produced them.

## 7. Fullscreen Exclusive

Not supported by default. Capture and overlay compatibility are tested separately after Windowed and Borderless.
A fallback strategy (for example recommending borderless mode for a game, or a different presentation path) must
be defined from test results, not assumed.

## 8. What is verified and what is not

| Item | State |
|---|---|
| Contract fields for placement/style/batch | Implemented and unit-tested (Linux) |
| Click-through, always-on-top, runtime toggle, drag | **Not verified** (W6) |
| Global hotkey registration and game key conflicts | **Not verified** (W6) |
| Overlay above a real game (Borderless / Fullscreen Exclusive) | **Not verified** (W6, W8) |
| F8 overlap threshold and 20-block cap | Provisional; need benchmarks |
