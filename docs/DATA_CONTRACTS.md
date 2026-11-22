# Shared Data Contracts

**Status:** Implemented v0.2 (M0-02 + owner-approved changes C1–C6 of 2026-11-22) — pending independent review and Project Owner acceptance.
**Canonical implementation:** `src/ai_screen_translator/contracts/models.py` (Pydantic v2).
**Generated artifacts:** `schemas/*.schema.json` (JSON Schema draft 2020-12, generated from the models).
**This document** is the authoritative human-readable specification. If it disagrees with the
models, that is a bug; `tests/unit/test_contract_docs.py` guards against drift (every contract,
enum value and example payload below is checked against the code).

## 1. Contract inventory

| Master Prompt type | Canonical model | Layer | Owner (producer) | Notes |
|---|---|---|---|---|
| CapturedFrame | `CapturedFrame` | Capture | capture | Carries a `FrameBufferRef`, never pixels |
| TextRegion | `TextRegion` | Region detection | vision | Candidate or configured region |
| OCRResult | `OCRObservation` | OCR | ocr | `OCRResult` is an alias of the same class |
| TrackedText | `TrackedText` | Tracking | tracking | Snapshot of one tracked subtitle |
| DialogueEvent | `LifecycleEvent` | Tracking | tracking | `DialogueEvent` is an alias of the same class |
| TranslationRequest | `TranslationRequest` | Translation | tracking/context | Contains `SubtitleContext` |
| TranslationResult | `TranslationResult` | Translation | translation | Status-dependent invariants |
| OverlayMessage | `OverlayUpdate` | Presentation | overlay input | `OverlayMessage` is an alias of the same class |
| GameProfile | `GameProfile` | Configuration | game_profiles | No secrets |
| PerformanceMetric | `PerformanceMetric` | Monitoring | every stage | One value per record |
| — (supporting) | `SubtitleContext`, `ErrorInfo`, `BoundingBox` | shared | — | Exported as standalone schemas too |

Nested value objects (no `schema_version`, immutable): `BoundingBox`, `Resolution`, `ErrorInfo`,
`ConversationMessage`, `FrameBufferRef`, `RoiConfig`, `OCRPreprocessingConfig`.

**One model per semantic event.** `OCRResult`, `DialogueEvent` and `OverlayMessage` are *aliases
bound to the same class object* (`OCRResult is OCRObservation`), not competing models. New code
may use either name; the schema file name always follows the canonical class name.

## 2. Common rules

These apply to every contract and are enforced by validation.

| Rule | Definition |
|---|---|
| Unknown fields | Rejected (`extra="forbid"`) on every model. No contract carries free-form extension data. |
| `schema_version` | Every top-level contract has `schema_version: "0.2"` (see §13). Nested value objects are versioned through their parent. |
| Timestamps | Timezone-aware, offset exactly UTC. Naive datetimes and non-UTC offsets are rejected (never silently converted). |
| Confidence | Float in `[0, 1]`; `NaN`/`inf` rejected. |
| `generation_id` | Strict integer `>= 1` (booleans and floats rejected). |
| Identifiers | Non-empty string, 1–128 chars, no leading/trailing whitespace, no control characters. Opaque. |
| Text | Valid UTF-8 (lone surrogates and NUL rejected), max 8192 chars. Fields that must carry content reject blank strings; there are no `""` defaults for meaningful content. |
| Language | `source_language` is the literal `"en"` and `target_language` the literal `"vi"` (defaults). No other direction is representable. |
| Secrets | No field carries credentials or request headers. `ErrorInfo.message` is redacted (§10). |

## 3. Timestamp rules

* Wall-clock fields (`*_at`, `timestamp`) are UTC-aware `datetime` objects.
* JSON form is ISO-8601 with a UTC designator, e.g. `2026-11-20T10:00:00Z`. Pydantic serializes
  UTC datetimes with `Z`; `+00:00` is also accepted on input. The JSON Schema declares
  `format: date-time` plus a pattern requiring a `Z`/`+00:00` suffix, so a schema-only validator
  also rejects offsets such as `+07:00` and offset-less strings.
* **Durations are never derived from wall-clock timestamps.** Producers measure elapsed time with
  a monotonic clock (`time.monotonic_ns()` / `perf_counter`) and carry the result as `*_ms`
  (`latency_ms`, `deadline_ms`, `PerformanceMetric.value`).
* `CapturedFrame.captured_monotonic_ns` is a process-local monotonic reading used only for
  latency within the same process; it is optional and must never be persisted or compared across
  processes/restarts.
* `deadline_ms` on a request is a budget measured from `requested_at`; `deadline_at` is a derived
  convenience property, not a serialized field.

## 4. BoundingBox and monitor identity

```
BoundingBox { monitor_id, x1, y1, x2, y2 }
```

* `monitor_id` — required, non-empty identifier naming the monitor the coordinates belong to.
  It is opaque to the contracts layer. The capture module defines the concrete value (the
  mapping to the DXGI adapter/output is an unresolved decision, see §17); it must be stable for
  a given physical display across a session.
* `x1, y1, x2, y2` — **physical pixels relative to that monitor**. Origin `(0, 0)` is the
  monitor's top-left pixel, x grows right, y grows down. **Virtual-desktop coordinates are never
  used**; a box on a monitor positioned at negative virtual-desktop offsets still has
  non-negative monitor-relative coordinates.
* Boundary convention: half-open `[x1, x2) × [y1, y2)`. `width = x2 - x1`,
  `height = y2 - y1`; `x2`/`y2` are exclusive, so a full-HD monitor's full box is
  `(0, 0, 1920, 1080)`.
* Rules: all four are strict integers; `x1 >= 0`, `y1 >= 0`; `x2 > x1`; `y2 > y1`.
  Floats, negatives and a missing/blank `monitor_id` are rejected.
* Convenience: `as_xyxy()` returns `(x1, y1, x2, y2)`; `width`/`height` properties.
* **Out-of-bounds policy.** The model never invents monitor dimensions, so a bare `BoundingBox`
  is validated only for ordering/non-negativity. When dimensions *are* known the check is
  applied by the owner of those dimensions: `bbox.fits_within(w, h)` / `bbox.ensure_within(w, h)`
  (requires `x2 <= w and y2 <= h`). Built-in enforcement:
  * `CapturedFrame` — `dirty_regions` must be on the frame's `monitor_id` and inside
    `width × height`.
  * `GameProfile` — if `reference_resolution` is set, every ROI must fit inside it; if
    `monitor_id` is set, every ROI must be on that monitor.
* DPI: boxes are physical pixels. Handling of per-monitor DPI scaling is the capture module's
  responsibility and is listed in §17.

## 5. Identity and generation semantics

| Id | Scope & lifetime | Assigned by |
|---|---|---|
| `monitor_id` | One physical display, stable for the session | capture |
| `frame_id` | One capture of one monitor; unique, never reused | capture |
| `region_id` | A region *slot* that persists across frames (e.g. `dialogue_roi`); one frame can have many regions | region detection / profile |
| `subtitle_id` | One tracked subtitle *instance*, from first detection to `CLEARED`; stable across frames and across text changes | tracker |
| `generation_id` | Version of the text of one `subtitle_id`; starts at 1 | tracker |

Relationships: a frame contains 0..n regions; an OCR observation is the output for
`(frame_id, region_id)` (its natural key); the tracker maps observations of a region over time to
a `subtitle_id`. A `subtitle_id` is bound to one `region_id` (and thus one monitor). `CLEARED` is
terminal: a subtitle that disappears and later reappears receives a **new** `subtitle_id`
(generation resets to 1).

* **Assignment timing.** `subtitle_id`/`generation_id` do not exist at OCR time. On raw OCR
  output both are `null`; after tracking both are set. They must be both set or both null.
* **Increment rule.** When the normalized text of a visible subtitle changes (replaced, or
  edited beyond the tracker's tolerance), `generation_id` increases by exactly 1 and a
  `TEXT_CHANGED` event is emitted with `previous_generation_id = generation_id - 1`. Unchanged
  text never changes the generation (no duplicate translation).
* **Generation guard.** Every `TranslationRequest`, `TranslationResult`, `OverlayUpdate` and
  `TrackedText`/`LifecycleEvent` carries `subtitle_id` + `generation_id` (these models derive
  from `GenerationScopedContract`). Consumers accept an item only if
  `item.is_current(active_subtitle_id, active_generation_id)` is true — both ids must match
  exactly. A lower *or higher* generation is rejected; stale results are dropped, never applied.
  The overlay additionally removes a message at `expires_at` even if no clear arrives.
* `idempotency_key` identifies one logical translation attempt for deduplication/caching. Format
  is opaque to the contract; the recommended form is `<subtitle_id>:<generation_id>:<text hash>`.

## 6. Contract reference

Legend: **R** required, **O** optional (default shown). All models also require/accept
`schema_version` (default `"0.2"`) unless marked *nested*.

### 6.1 CapturedFrame (R: all except noted)
A full-monitor frame. Pixels are **not** in the contract.

| Field | Type / constraint |
|---|---|
| `frame_id` | Identifier, R |
| `sequence` | int ≥ 0, per-monitor, strictly increasing (producer duty), R |
| `monitor_id` | Identifier, R |
| `width`, `height` | strict int > 0, monitor physical pixels, R |
| `pixel_format` | `bgra8` \| `bgr8` \| `rgb8` \| `gray8`, R |
| `captured_at` | UTC datetime, R |
| `captured_monotonic_ns` | int ≥ 0 or null, O (null) |
| `buffer` | `FrameBufferRef`, R |
| `dirty_regions` | list of `BoundingBox` (≤ 256), O (`[]`) |

Cross-field: `buffer.stride_bytes >= width × bytes_per_pixel`; `buffer.size_bytes >= stride_bytes × height`;
each dirty region lies on this monitor and inside the frame.

`FrameBufferRef` *(nested)*: `pool_id`, `slot` (≥ 0), `slot_generation` (≥ 1), `stride_bytes` (> 0),
`size_bytes` (> 0).

**Ownership and lifetime of the frame reference.** Pixels live in a pre-allocated pool owned by
the capture module. A `FrameBufferRef` is a *lease*: consumers treat the buffer as read-only,
must not retain it beyond processing of that frame, and release it through the capture
interface. `slot_generation` changes whenever a slot is recycled, so a consumer holding a stale
reference can detect it and must discard the frame. The reference is process-local and must not
be persisted or sent to another process. No capture technology is implied (DXGI remains the
approved baseline; its adapter is not part of this task).

### 6.2 TextRegion
| Field | Type / constraint |
|---|---|
| `region_id` | Identifier, R |
| `frame_id` | Identifier, R — frame it was detected in |
| `bbox` | `BoundingBox`, R (monitor identity via `bbox.monitor_id`; `monitor_id` property) |
| `confidence` | `[0, 1]`, R — detection confidence (use `1.0` for manual/profile ROIs) |
| `source` | `manual_roi` \| `profile_roi` \| `auto_detected`, R |
| `content_type` | `subtitle` \| `dialogue` \| `choice` \| `quest` \| `item_description` \| `ui` \| `unknown`, O (`unknown`) |
| `detected_at` | UTC datetime, R |

### 6.3 OCRObservation (Master Prompt `OCRResult`)
| Field | Type / constraint |
|---|---|
| `frame_id`, `region_id` | Identifier, R — natural key `(frame_id, region_id)` |
| `subtitle_id`, `generation_id` | Identifier / int ≥ 1, O (null) — both set or both null |
| `source_text` | UTF-8 text, R — **normalized** text |
| `raw_text` | UTF-8 text or null, O — raw OCR output when it differs |
| `confidence` | `[0, 1]`, R |
| `bbox` | `BoundingBox`, R |
| `timestamp` | UTC datetime, R |
| `language` | literal `en`, O (`en`) |
| `recognition_status` | `accepted` \| `low_confidence` \| `rejected` \| `empty`, R |
| `preprocessing_profile` | Identifier or null, O |

Cross-field: `empty` requires `source_text == ""` and no recognized `raw_text` (this is the
"region has no text" signal that feeds clear-debouncing); every other status requires non-blank
`source_text`.

### 6.4 TrackedText
Generation-scoped (`subtitle_id`, `generation_id`).

| Field | Type / constraint |
|---|---|
| `region_id` | Identifier, R (monitor via `bbox`) |
| `text` | non-blank text, R — current text |
| `bbox` | `BoundingBox`, R — current box |
| `state` | `LifecycleState` except `NO_TEXT`, R |
| `first_seen_at` ≤ `generation_started_at` ≤ `last_seen_at` | UTC datetimes, R (ordering enforced) |
| `confidence` | `[0, 1]`, R |
| `change_kind` | `new` \| `unchanged` \| `appended` \| `modified` \| `replaced`, R |
| `similarity` | `[0, 1]` or null, O — vs previous generation; null when new |
| `observation_count` | int ≥ 1, R |
| `last_frame_id` | Identifier or null, O |

Cross-field: `new` ⇒ `generation_id == 1` and no `similarity`; generation 1 may only be `new` or
`unchanged`. `appended` covers progressive (typewriter) text where the new text extends the old.

### 6.5 LifecycleEvent (Master Prompt `DialogueEvent`)
Generation-scoped. One event per state *change*.

| Field | Type / constraint |
|---|---|
| `previous_state`, `current_state` | `LifecycleState`, R — must differ and be an allowed transition (§9) |
| `timestamp` | UTC datetime, R |
| `reason` | `LifecycleReason`, R |
| `region_id`, `frame_id` | Identifier or null, O |
| `previous_generation_id` | int ≥ 1 or null, O — only on `TEXT_CHANGED`, must equal `generation_id - 1` |
| `error` | `ErrorInfo` or null, O — **required iff** `current_state == ERROR` |

Cross-field: leaving `NO_TEXT` requires `generation_id == 1`.

### 6.6 SubtitleContext
Replaces the earlier `list[dict[str, str]]` history with typed messages (decision: a dedicated
model, because untyped dicts could not enforce speaker/content/timestamp and leaked arbitrary
keys into prompts). It stays deliberately small — a bounded sliding window, no retrieval/RAG.

| Field | Type / constraint |
|---|---|
| `game_id` | Identifier, R |
| `speaker` | label, O (`"unknown"`) — `unknown` unless visible evidence supports a name |
| `conversation_history` | list of `ConversationMessage` (≤ 32), O (`[]`) |
| `glossary` | `{term: translation}` (≤ 256 entries, non-blank keys/values), O (`{}`) |
| `translation_style` | `context_adaptive` \| `literal` \| `natural`, O (`context_adaptive`) |
| `source_language`, `target_language` | literals `en` / `vi` |

`ConversationMessage` *(nested)*: `speaker` (label, default `unknown`), `content` (non-blank, R),
`translation` (non-blank or null), `timestamp` (UTC or null).

### 6.7 TranslationRequest
Generation-scoped.

| Field | Type / constraint |
|---|---|
| `source_text` | non-blank text, R |
| `context` | `SubtitleContext`, R |
| `source_language`, `target_language` | literals `en` / `vi` |
| `requested_at` | UTC datetime, R |
| `deadline_ms` | strict int, `0 < x <= 600000`, R — budget from `requested_at` |
| `idempotency_key` | Identifier, R |
| `trigger` | `auto` \| `hotkey`, O (`auto`) — what caused the request (independent of `RegionSource`) |
| `batch_id` | Identifier or null — **required iff `trigger` is `hotkey`**, forbidden for `auto` |

One manual-translate (F8) press yields several requests that share one `batch_id`, so a newer
press can discard the whole older batch. F8 text blocks do not use the lifecycle state machine;
each block gets its own `subtitle_id` and `generation_id = 1` so the generation guard still applies.

### 6.8 TranslationResult
Generation-scoped. See §8 for the status invariants.

| Field | Type / constraint |
|---|---|
| `source_text` | non-blank text, R |
| `translated_text` | non-blank text or null |
| `engine` | `nllb` \| `openai` \| `translation_memory` or null — the engine that **actually produced** the text |
| `model_id` | string (1–128) or null — concrete model identifier (configurable; never assumed) |
| `status` | `completed` \| `failed` \| `skipped`, R |
| `latency_ms` | float ≥ 0, R — monotonic-clock measurement |
| `completed_at` | UTC datetime, R |
| `error` | `ErrorInfo` or null |
| `skip_reason` | `stale_generation` \| `cancelled` \| `duplicate_request` or null |

### 6.9 OverlayUpdate (Master Prompt `OverlayMessage`)
Generation-scoped.

| Field | Type / constraint |
|---|---|
| `source_text`, `translated_text` | non-blank text, R |
| `bbox` | `BoundingBox`, R — original-text box the overlay anchors to |
| `created_at` | UTC datetime, R |
| `expires_at` | UTC datetime, R, must be after `created_at` |
| `batch_id` | Identifier or null — set for messages from one F8 press, null for Auto messages |

The overlay shows Vietnamese only. Placement and look come from the game's `OverlayStyle`
(§6.10), not from this message; the former `display_mode` field was removed in v0.2.

Stale rejection: the overlay keeps the active `(subtitle_id, generation_id)` and drops the
message unless `update.is_current(...)`. `is_expired(now)` supports expiry. Clearing on
disappearance is driven by a `LifecycleEvent` reaching `CLEARED`, not by an overlay message type
(see §17).

### 6.10 GameProfile
Local configuration; contains no secrets (extra fields rejected; no key/credential field exists).

| Field | Type / constraint |
|---|---|
| `game_id` | Identifier, R |
| `display_name`, `executable_name` | text or null |
| `monitor_id` | Identifier or null — applicable monitor |
| `display_mode` | `windowed` \| `borderless_windowed` \| `fullscreen_exclusive` \| `unknown`, O (`unknown`) |
| `reference_resolution` | `Resolution{width,height}` or null — resolution the ROIs were authored at |
| `roi` | list of `RoiConfig{region_id, bbox, content_type=subtitle, enabled=true}` (≤ 32, unique `region_id`) |
| `ocr` | `OCRPreprocessingConfig{profile="default", adaptive_threshold, clahe, invert, scale_factor (0,8], min_confidence [0,1]}` |
| `translation_style` | enum as above, O (`context_adaptive`) |
| `overlay_style` | `OverlayStyle` (nested, per game), O (defaults below) |
| `glossary_path` | **relative** path (no drive, no leading slash, no `..`) or null |
| `glossary` | `{term: translation}` (≤ 1024), O |
| `character_names` | unique list of terms (≤ 256), O |
| `source_language`, `target_language` | literals `en` / `vi` |

`roi` is shared by Auto and Manual. There is no extra ROI field: an empty list, or a list with
no `enabled` entry, means "no ROI" (Auto does not start; F8 uses the whole screen).

**`OverlayStyle`** (nested value object, no `schema_version`):

| Field | Type / constraint |
|---|---|
| `placement` | `below` \| `above`, O (`below`) |
| `offset_x`, `offset_y` | strict int in `[-4096, 4096]` pixels, O (`0`) — signed adjustment from the anchor |
| `font_size_px` | strict int in `[8, 128]`, O (`24`) |
| `text_color`, `background_color` | `#RRGGBB` string, O (`#FFFFFF` / `#000000`) |
| `opacity` | float in `[0.1, 1.0]`, O (`0.85`) — lower bound keeps the overlay visible |

### 6.11 PerformanceMetric
One measured value per record.

| Field | Type / constraint |
|---|---|
| `metric` | `capture_latency` \| `ocr_latency` \| `tracking_latency` \| `translation_latency` \| `render_latency` \| `end_to_end_latency` \| `cpu_usage` \| `ram_usage` \| `gpu_usage` \| `vram_usage`, R |
| `value` | float ≥ 0, finite, R |
| `unit` | `ms` \| `percent` \| `bytes`, R — must match the metric (latencies `ms`, cpu/gpu `percent`, ram/vram `bytes`) |
| `timestamp` | UTC datetime, R |
| `component` | `capture` \| `preprocessing` \| `region_detection` \| `ocr` \| `normalization` \| `tracking` \| `context` \| `translation` \| `translation_memory` \| `overlay` \| `storage` \| `app`, R |
| `subtitle_id`, `generation_id`, `frame_id`, `region_id`, `engine` | optional correlation ids; `generation_id` requires `subtitle_id` |

Percent values must be ≤ 100. Latency values come from monotonic measurements.

## 7. Enumerations (vocabulary)

| Enum | Values |
|---|---|
| `LifecycleState` | `NO_TEXT`, `TEXT_DETECTED`, `TEXT_STABILIZING`, `TRANSLATION_PENDING`, `TRANSLATING`, `DISPLAYING`, `TEXT_CHANGED`, `CLEAR_PENDING`, `CLEARED`, `ERROR` |
| `LifecycleReason` | `text_appeared`, `text_stabilized`, `translation_requested`, `translation_started`, `translation_completed`, `text_changed`, `text_disappeared`, `text_reappeared`, `clear_debounce_elapsed`, `stage_error`, `recovered` |
| `TranslationStatus` | `completed`, `failed`, `skipped` |
| `TranslationEngine` | `nllb`, `openai`, `translation_memory` |
| `SkipReason` | `stale_generation`, `cancelled`, `duplicate_request` |
| `RecognitionStatus` | `accepted`, `low_confidence`, `rejected`, `empty` |
| `ChangeKind` | `new`, `unchanged`, `appended`, `modified`, `replaced` |
| `ErrorCode` | `timeout`, `network_error`, `auth_error`, `rate_limited`, `model_unavailable`, `invalid_request`, `invalid_response`, `resource_exhausted`, `engine_error`, `internal_error` |
| `RegionSource` | `manual_roi`, `profile_roi`, `auto_detected` |
| `ContentType` | `subtitle`, `dialogue`, `choice`, `quest`, `item_description`, `ui`, `unknown` |
| `Trigger` | `auto`, `hotkey` |
| `OverlayPlacement` | `below`, `above` |
| `GameDisplayMode` | `windowed`, `borderless_windowed`, `fullscreen_exclusive`, `unknown` |
| `TranslationStyle` | `context_adaptive`, `literal`, `natural` |
| `PixelFormat` | `bgra8`, `bgr8`, `rgb8`, `gray8` |
| `PipelineComponent` | `capture`, `preprocessing`, `region_detection`, `ocr`, `normalization`, `tracking`, `context`, `translation`, `translation_memory`, `overlay`, `storage`, `app` |
| `PerformanceMetricName` | `capture_latency`, `ocr_latency`, `tracking_latency`, `translation_latency`, `render_latency`, `end_to_end_latency`, `cpu_usage`, `ram_usage`, `gpu_usage`, `vram_usage` |
| `MetricUnit` | `ms`, `percent`, `bytes` |

The lifecycle states are the existing approved set (unchanged from the initial contract). The
Master Prompt's proposed names (DETECTED, OCR_PENDING, …) were explicitly "initial proposals";
the committed vocabulary above supersedes them.

## 8. TranslationResult status invariants

| Status | `translated_text` | `engine` | `error` | `skip_reason` |
|---|---|---|---|---|
| `completed` | **required**, non-blank | **required** (actual engine) | must be null | must be null |
| `failed` | must be null | optional (engine that failed, if known) | **required** | must be null |
| `skipped` | must be null | optional | must be null | **required** |

* A completed result can never carry an empty or whitespace-only translation (there is no `""`
  default).
* **`skipped` semantics:** translation was deliberately not performed and this is *not* an
  error — e.g. the generation became stale before work started (`stale_generation`), the request
  was cancelled (`cancelled`), or an identical request is already in flight/cached
  (`duplicate_request`). A skipped result never changes lifecycle state on its own and is never
  displayed.
* A failed result never contains a partial translation; callers decide on fallback.
* The generation guard still applies to all three statuses.

## 9. Lifecycle vocabulary and allowed transitions

`ALLOWED_TRANSITIONS` (in `models.py`) is the contract-level graph; the Milestone 3 state machine
may be stricter but must not exceed it. `LifecycleEvent` rejects any other transition and any
self-transition.

| From | Allowed next states |
|---|---|
| `NO_TEXT` | `TEXT_DETECTED` |
| `TEXT_DETECTED` | `TEXT_STABILIZING`, `CLEAR_PENDING`, `ERROR` |
| `TEXT_STABILIZING` | `TRANSLATION_PENDING`, `TEXT_CHANGED`, `CLEAR_PENDING`, `ERROR` |
| `TRANSLATION_PENDING` | `TRANSLATING`, `TEXT_CHANGED`, `CLEAR_PENDING`, `ERROR` |
| `TRANSLATING` | `DISPLAYING`, `TEXT_CHANGED`, `CLEAR_PENDING`, `ERROR` |
| `DISPLAYING` | `TEXT_CHANGED`, `CLEAR_PENDING`, `ERROR` |
| `TEXT_CHANGED` | `TEXT_STABILIZING`, `CLEAR_PENDING`, `ERROR` |
| `CLEAR_PENDING` | `CLEARED`, `DISPLAYING` (text reappeared before debounce elapsed), `TEXT_CHANGED`, `ERROR` |
| `CLEARED` | — (terminal; reappearance creates a new `subtitle_id`) |
| `ERROR` | `TEXT_CHANGED`, `CLEAR_PENDING`, `CLEARED` |

Notes: a translation-memory cache hit still passes `TRANSLATION_PENDING → TRANSLATING →
DISPLAYING` (with `engine = translation_memory`). `reason` is validated as a vocabulary but is
not cross-checked against each transition pair (see §17). `CLEAR_PENDING` is entered only after
the debounce rules in the tracker confirm that OCR is consistently empty.

## 10. Error structure

`ErrorInfo` *(nested)*: `code` (`ErrorCode`), `component` (`PipelineComponent`), `message`
(1–500 chars), `retryable` (bool, default false), `error_type` (exception class name or null),
`status_code` (HTTP-style 100–599 or null).

* No tracebacks, request headers, bodies or arbitrary dictionaries.
* `message` is passed through `redact_secrets()`, which replaces `sk-…` style keys, `Bearer`
  tokens and `api_key/token/secret/password/authorization = value` pairs with `[REDACTED]`.
  This is defense in depth, **not** a guarantee: producers must still never put secrets into
  messages.

## 11. JSON Schema generation

Schemas are generated from `PUBLIC_CONTRACTS` — there is no hand-written second definition.

```bash
pip install -e ".[dev]"                  # once; or set PYTHONPATH=src
python scripts/export_schemas.py         # (re)generate schemas/*.schema.json
python scripts/export_schemas.py --check # exit 1 if committed schemas are stale/missing/orphaned
```

* 13 files, named `<lowercased class name>.schema.json` (stable, deterministic).
* Draft 2020-12, `sort_keys`, 2-space indent, UTF-8 (`ensure_ascii=False`), LF line endings
  (`.gitattributes` pins `schemas/*.json` to LF; the checker also tolerates CRLF checkouts).
* Nested models/enums are emitted as `$defs` inside each schema.
* The export removes generated files that no longer correspond to a contract.
* `tests/unit/test_contract_schemas.py` fails if the committed schemas differ from the models,
  validates sample payloads against the schemas with `jsonschema`, and checks that schema-level
  constraints match Pydantic behaviour.
* Known limitation: cross-field invariants (e.g. status-dependent rules, bbox ordering,
  transition graph) cannot be expressed fully in JSON Schema; Pydantic is authoritative and
  schema-only consumers get structural validation only.

## 12. Example payloads

All examples below are validated against the models by `tests/unit/test_contract_docs.py`.

### CapturedFrame (reference, no pixels)
<!-- contract: CapturedFrame -->
```json
{
  "schema_version": "0.2",
  "frame_id": "frame_000042",
  "sequence": 42,
  "monitor_id": "DISPLAY1",
  "width": 1920,
  "height": 1080,
  "pixel_format": "bgra8",
  "captured_at": "2026-11-20T10:00:00Z",
  "captured_monotonic_ns": 123456789,
  "buffer": {
    "pool_id": "capture_pool",
    "slot": 3,
    "slot_generation": 7,
    "stride_bytes": 7680,
    "size_bytes": 8294400
  },
  "dirty_regions": [
    {
      "monitor_id": "DISPLAY1",
      "x1": 0,
      "y1": 800,
      "x2": 1920,
      "y2": 1000
    }
  ]
}
```

### TextRegion
<!-- contract: TextRegion -->
```json
{
  "schema_version": "0.2",
  "region_id": "dialogue_roi",
  "frame_id": "frame_000042",
  "bbox": {
    "monitor_id": "DISPLAY1",
    "x1": 250,
    "y1": 820,
    "x2": 1300,
    "y2": 900
  },
  "confidence": 0.91,
  "source": "profile_roi",
  "content_type": "subtitle",
  "detected_at": "2026-11-20T10:00:00Z"
}
```

### OCRObservation / OCRResult (raw, before tracking: ids null)
<!-- contract: OCRObservation -->
```json
{
  "schema_version": "0.2",
  "frame_id": "frame_000042",
  "region_id": "dialogue_roi",
  "subtitle_id": null,
  "generation_id": null,
  "source_text": "You should not have come here.",
  "raw_text": "You should not have come here .",
  "confidence": 0.97,
  "bbox": {
    "monitor_id": "DISPLAY1",
    "x1": 250,
    "y1": 820,
    "x2": 1300,
    "y2": 900
  },
  "timestamp": "2026-11-20T10:00:00Z",
  "language": "en",
  "recognition_status": "accepted",
  "preprocessing_profile": "outlined_text"
}
```

### TrackedText
<!-- contract: TrackedText -->
```json
{
  "schema_version": "0.2",
  "subtitle_id": "subtitle_0001",
  "generation_id": 1,
  "region_id": "dialogue_roi",
  "text": "You should not have come here.",
  "bbox": {
    "monitor_id": "DISPLAY1",
    "x1": 250,
    "y1": 820,
    "x2": 1300,
    "y2": 900
  },
  "state": "TEXT_STABILIZING",
  "first_seen_at": "2026-11-20T10:00:00Z",
  "generation_started_at": "2026-11-20T10:00:00Z",
  "last_seen_at": "2026-11-20T10:00:01Z",
  "confidence": 0.96,
  "change_kind": "new",
  "similarity": null,
  "observation_count": 3,
  "last_frame_id": "frame_000044"
}
```

### LifecycleEvent / DialogueEvent (text changed)
<!-- contract: LifecycleEvent -->
```json
{
  "schema_version": "0.2",
  "subtitle_id": "subtitle_0001",
  "generation_id": 2,
  "previous_state": "DISPLAYING",
  "current_state": "TEXT_CHANGED",
  "timestamp": "2026-11-20T10:00:01Z",
  "reason": "text_changed",
  "region_id": "dialogue_roi",
  "frame_id": "frame_000043",
  "previous_generation_id": 1,
  "error": null
}
```

### LifecycleEvent (error)
<!-- contract: LifecycleEvent -->
```json
{
  "schema_version": "0.2",
  "subtitle_id": "subtitle_0001",
  "generation_id": 1,
  "previous_state": "TRANSLATING",
  "current_state": "ERROR",
  "timestamp": "2026-11-20T10:00:01Z",
  "reason": "stage_error",
  "region_id": "dialogue_roi",
  "frame_id": "frame_000043",
  "previous_generation_id": null,
  "error": {
    "code": "timeout",
    "component": "translation",
    "message": "Provider did not answer within the deadline.",
    "retryable": true,
    "error_type": "TimeoutError",
    "status_code": null
  }
}
```

### TranslationRequest (embeds SubtitleContext)
<!-- contract: TranslationRequest -->
```json
{
  "schema_version": "0.2",
  "subtitle_id": "subtitle_0001",
  "generation_id": 1,
  "source_text": "You should not have come here.",
  "context": {
    "schema_version": "0.2",
    "game_id": "demo_rpg",
    "speaker": "unknown",
    "conversation_history": [
      {
        "speaker": "Elara",
        "content": "The gate is sealed.",
        "translation": "Cánh cổng đã bị phong ấn.",
        "timestamp": "2026-11-20T10:00:00Z"
      }
    ],
    "glossary": {
      "Elara": "Elara",
      "gate": "cổng"
    },
    "translation_style": "context_adaptive",
    "source_language": "en",
    "target_language": "vi"
  },
  "source_language": "en",
  "target_language": "vi",
  "requested_at": "2026-11-20T10:00:01Z",
  "deadline_ms": 1500,
  "idempotency_key": "subtitle_0001:1:7f3a9c",
  "trigger": "auto",
  "batch_id": null
}
```

### TranslationResult — completed
<!-- contract: TranslationResult -->
```json
{
  "schema_version": "0.2",
  "subtitle_id": "subtitle_0001",
  "generation_id": 1,
  "source_text": "You should not have come here.",
  "translated_text": "Ngươi không nên đến đây.",
  "engine": "nllb",
  "model_id": "nllb-200-distilled-600M",
  "status": "completed",
  "latency_ms": 412.0,
  "completed_at": "2026-11-20T10:00:02Z",
  "error": null,
  "skip_reason": null
}
```

### TranslationResult — failed
<!-- contract: TranslationResult -->
```json
{
  "schema_version": "0.2",
  "subtitle_id": "subtitle_0001",
  "generation_id": 1,
  "source_text": "You should not have come here.",
  "translated_text": null,
  "engine": "openai",
  "model_id": null,
  "status": "failed",
  "latency_ms": 412.0,
  "completed_at": "2026-11-20T10:00:02Z",
  "error": {
    "code": "timeout",
    "component": "translation",
    "message": "Provider did not answer within the deadline.",
    "retryable": true,
    "error_type": "TimeoutError",
    "status_code": null
  },
  "skip_reason": null
}
```

### TranslationResult — skipped
<!-- contract: TranslationResult -->
```json
{
  "schema_version": "0.2",
  "subtitle_id": "subtitle_0001",
  "generation_id": 1,
  "source_text": "You should not have come here.",
  "translated_text": null,
  "engine": null,
  "model_id": null,
  "status": "skipped",
  "latency_ms": 412.0,
  "completed_at": "2026-11-20T10:00:02Z",
  "error": null,
  "skip_reason": "stale_generation"
}
```

### OverlayUpdate / OverlayMessage
<!-- contract: OverlayUpdate -->
```json
{
  "schema_version": "0.2",
  "subtitle_id": "subtitle_0001",
  "generation_id": 1,
  "source_text": "You should not have come here.",
  "translated_text": "Ngươi không nên đến đây.",
  "bbox": {
    "monitor_id": "DISPLAY1",
    "x1": 250,
    "y1": 820,
    "x2": 1300,
    "y2": 900
  },
  "created_at": "2026-11-20T10:00:01Z",
  "expires_at": "2026-11-20T10:00:02Z",
  "batch_id": null
}
```

### GameProfile
<!-- contract: GameProfile -->
```json
{
  "schema_version": "0.2",
  "game_id": "demo_rpg",
  "display_name": "Demo RPG",
  "executable_name": "demo_rpg.exe",
  "monitor_id": "DISPLAY1",
  "display_mode": "borderless_windowed",
  "reference_resolution": {
    "width": 1920,
    "height": 1080
  },
  "roi": [
    {
      "region_id": "dialogue_roi",
      "bbox": {
        "monitor_id": "DISPLAY1",
        "x1": 250,
        "y1": 820,
        "x2": 1300,
        "y2": 900
      },
      "content_type": "subtitle",
      "enabled": true
    }
  ],
  "ocr": {
    "profile": "outlined_text",
    "adaptive_threshold": true,
    "clahe": true,
    "invert": false,
    "scale_factor": 2.0,
    "min_confidence": 0.6
  },
  "translation_style": "context_adaptive",
  "overlay_style": {
    "placement": "below",
    "offset_x": 0,
    "offset_y": 12,
    "font_size_px": 28,
    "text_color": "#FFFFFF",
    "background_color": "#101010",
    "opacity": 0.85
  },
  "glossary_path": "glossaries/demo_rpg.json",
  "glossary": {
    "Elara": "Elara"
  },
  "character_names": [
    "Elara"
  ],
  "source_language": "en",
  "target_language": "vi"
}
```

### PerformanceMetric
<!-- contract: PerformanceMetric -->
```json
{
  "schema_version": "0.2",
  "metric": "ocr_latency",
  "value": 84.5,
  "unit": "ms",
  "timestamp": "2026-11-20T10:00:00Z",
  "component": "ocr",
  "subtitle_id": "subtitle_0001",
  "generation_id": 1,
  "frame_id": "frame_000042",
  "region_id": "dialogue_roi",
  "engine": null
}
```

### SubtitleContext
<!-- contract: SubtitleContext -->
```json
{
  "schema_version": "0.2",
  "game_id": "demo_rpg",
  "speaker": "unknown",
  "conversation_history": [
    {
      "speaker": "Elara",
      "content": "The gate is sealed.",
      "translation": "Cánh cổng đã bị phong ấn.",
      "timestamp": "2026-11-20T10:00:00Z"
    }
  ],
  "glossary": {
    "Elara": "Elara",
    "gate": "cổng"
  },
  "translation_style": "context_adaptive",
  "source_language": "en",
  "target_language": "vi"
}
```


## 13. Versioning policy

* A single contract-set version string, currently `"0.2"`, carried as `schema_version` and typed
  `Literal["0.2"]`. A payload with any other version (including `"0.1"`) is rejected rather than
  guessed at.
* `0.x` is the pre-release line. Until a first release, breaking changes are allowed but each
  must bump the minor (`0.3`, …), be listed in the compatibility table in §14, and ship with
  regenerated schemas and updated tests.
* From `1.0`: additive, backward-compatible changes (new optional field, new enum value
  consumers can ignore) bump minor; removed/renamed fields, tightened constraints or changed
  semantics bump major.
* **v0.1 → v0.2 (owner-approved 2026-11-22, change C6)** removes `OverlayDisplayMode`,
  `OverlayUpdate.display_mode` and `GameProfile.overlay_display_mode` and adds `Trigger`,
  `OverlayPlacement`, `OverlayStyle`, `batch_id` and `trigger`. No payload was ever persisted or
  exchanged under `0.1`, so no migration function is provided (§14).

## 14. Backward compatibility and migration

Baseline: the initial scaffold on `main` (`f6cc0eb`). No other module in the repository
references the contracts, and no persisted data exists, so no runtime migration is required.

| Area | Scaffold | Now | Reason |
|---|---|---|---|
| `BoundingBox` | `x1..y2` only | + required `monitor_id`, strict non-negative ints | Owner-approved monitor-relative decision |
| BoundingBox JSON | doc example used a list `[x1,y1,x2,y2]` | object with `monitor_id` | schema alignment; use `as_xyxy()` for tuples |
| Datetimes | any `datetime` (naive allowed) | UTC-aware only | approved rule |
| `OCRObservation` ids | required | optional pair (both null before tracking) | tracker assigns ids after OCR |
| `OCRObservation` | — | + `raw_text`, `preprocessing_profile`, `EMPTY` status | OCRResult requirements |
| `TranslationRequest` | `SubtitleContext` with `dict` history, free `str` style | typed `ConversationMessage`, `TranslationStyle` enum | strong typing |
| `TranslationResult` | `translated_text=""` default, required `engine`, `error_code`/`error_message` strings | nullable text, optional engine, `model_id`, structured `ErrorInfo`, `skip_reason`, status invariants | no silent empty success |
| `TranslationEngine` | `nllb`, `openai` | + `translation_memory` | cache hits need an honest engine |
| `OverlayUpdate` | `str` display mode, no `created_at` | enum, + `created_at`, expiry ordering | OverlayMessage requirements |
| `LifecycleEvent` | free `reason: str = ""` | `LifecycleReason` enum, transition graph validation, `error` | DialogueEvent requirements |
| Config | `schema_version`, `extra=forbid` | unchanged | — |
| `schema_version` | `"0.1"` | `"0.2"` | C6 |
| `TranslationRequest` (v0.1→v0.2) | no origin information | + `trigger` (`auto` default), + `batch_id` (required iff `hotkey`) | C1: F8 batches |
| `OverlayUpdate` (v0.1→v0.2) | `display_mode` required | `display_mode` removed, + optional `batch_id` | C2: Vietnamese-only overlay |
| `GameProfile` (v0.1→v0.2) | `overlay_display_mode` enum | removed; + `overlay_style: OverlayStyle` | C3: per-game placement and style |
| `OverlayDisplayMode` (v0.1→v0.2) | 4 values | enum deleted; + `OverlayPlacement`, `Trigger` | `bilingual`, `side_by_side`, `floating_box` out of scope |
| ROI, `LifecycleReason` (v0.1→v0.2) | — | unchanged (C4, C5) | F8 bypasses the state machine |

Compatibility names: `OCRResult`, `DialogueEvent`, `OverlayMessage` are aliases of the canonical
classes. Existing class names were all retained, so imports from `ai_screen_translator.contracts`
keep working.

**Migration policy.** When a persisted contract changes: bump `schema_version`, keep a pure
function `migrate_<old>_to_<new>(dict) -> dict` next to the models, test it with a frozen
fixture of the old payload, and never mutate stored data without a backup. Events (queues) are
in-process and are not migrated; persisted records (history, profiles, metrics) are.

## 15. Using the guards (non-normative)

```python
update.is_current(active_subtitle_id, active_generation_id)  # reject stale overlay/translation
bbox.ensure_within(monitor_width, monitor_height)  # when dimensions are known
is_valid_transition(LifecycleState.DISPLAYING, LifecycleState.CLEARED)  # False
```

## 16. Out of scope for this layer

Frame pixels, cropped ROI images, the tracker state machine implementation, queue/backpressure
policy, SQLite schemas, persistence code, and any capture/OCR/translation/overlay behaviour.

## 17. Unresolved decisions (for reviewer / Project Owner)

1. **`monitor_id` format and DXGI mapping.** Contracts treat it as an opaque stable identifier.
   The concrete value (adapter/output index vs device name vs hash) must be fixed during the
   DXGI prototype (M0-05) and documented in the capture module.
2. **DPI scaling and ROI portability.** Boxes are physical pixels; `GameProfile.reference_resolution`
   records the authoring resolution but the contract defines no scaling algorithm for other
   resolutions/DPI.
3. **Overlay clear message.** Clearing is derived from `LifecycleEvent(CLEARED)`. Decide in M1/M3
   whether an explicit `OverlayClear` contract is also needed.
4. **Lifecycle `reason` ↔ transition pairing** is not enforced (only each vocabulary separately).
5. **Version bump.** Resolved: the contract set moved to `0.2` (C6, §13).
6. **Idempotency key format** is opaque; the recommended format is advisory.
7. **Subtitle identity for overlapping regions** is a tracker (M3) concern, not specified here.
8. **Translation memory as an engine value** is an addition not present in the scaffold; confirm
   the naming.
9. **Text length limit** (8192) and list bounds (history 32, glossary 256/1024, ROI 32) are
   defensive defaults chosen here, not benchmarked.
10. **F8 overlay lifetime and clearing.** `expires_at` is required, so a default lifetime is
    needed, and "clear all results of one F8" has no trigger yet. The contract supports removal
    by `batch_id`; the policy is an open owner question (DECISIONS.md Q1).
11. **Settings contract.** Rebindable hotkeys need a settings contract that does not exist in
    v0.2 (DECISIONS.md Q2).
12. **`OverlayStyle` defaults and bounds** (24 px, 0.85 opacity, offsets ±4096, font 8–128 px,
    opacity ≥ 0.1) are working values chosen here, not UX-tested.
