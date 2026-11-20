# Shared Data Contracts

**Status:** Draft v0.1 — interface agreement required before parallel module implementation.  
**Canonical implementation:** Pydantic models in `src/ai_screen_translator/contracts/`; JSON Schema generated from those models. The examples below define semantics, not a claim that runtime models already exist.

## Common rules
- Timestamps are UTC-aware ISO-8601 for persisted/event data; monotonic seconds may be used separately for latency and local ordering.
- Bounding boxes use pixel coordinates `[x1, y1, x2, y2]`, with x2 > x1 and y2 > y1.
- IDs are opaque strings; generation_id is a positive integer.
- Confidence is normalized to [0, 1].
- Text is UTF-8; source_language defaults to `en`, target_language to `vi`.
- Every event carries schema_version for forward compatibility.

## OCRObservation
Required: schema_version, subtitle_id, generation_id, source_text, confidence, bbox, timestamp, region_id, language, recognition_status. Optional: frame_id, preprocessing_profile, raw_text.

## SubtitleContext
Required: schema_version, game_id, speaker, conversation_history, glossary, translation_style, source_language, target_language. speaker is `unknown` unless supported by visible evidence.

## TranslationRequest
Required: schema_version, subtitle_id, generation_id, source_text, context, requested_at, deadline_ms, idempotency_key.

## TranslationResult
Required: schema_version, subtitle_id, generation_id, source_text, translated_text, engine, status, latency_ms, completed_at. engine identifies the actual engine (`nllb` or `openai`); status is completed, failed, or skipped. Include error_code/message only on failure; never include credentials or secret request headers.

## OverlayUpdate
Required: schema_version, subtitle_id, generation_id, source_text, translated_text, bbox, display_mode, expires_at. UI must reject updates older than the currently displayed generation.

## LifecycleEvent
Required: schema_version, subtitle_id, generation_id, previous_state, current_state, timestamp, reason.

## Invariants
1. subtitle_id is stable for one tracked subtitle instance.
2. A changed/replaced subtitle increments generation_id.
3. Translation completion is accepted only for the active subtitle_id + generation_id.
4. OCR observations with unchanged normalized text do not trigger duplicate translation.
5. Empty OCR observations are debounced before CLEAR_PENDING/CLEARED.
6. Queues are bounded; overflow policy is explicit (capture favors dropping stale frames).
7. Every stage records timing and structured errors.
8. Schema changes require versioning and contract tests.

## Example OCR event
```json
{
  "schema_version": "0.1",
  "subtitle_id": "subtitle_0001",
  "generation_id": 1,
  "source_text": "You should not have come here.",
  "confidence": 0.97,
  "bbox": [250, 820, 1300, 900],
  "timestamp": "2026-11-20T10:00:00Z",
  "region_id": "dialogue_roi",
  "language": "en",
  "recognition_status": "accepted"
}
```

## Open decisions
- Exact timestamp representation in in-process events vs persisted records.
- Whether bbox is screen-space or ROI-local (recommend screen-space; ROI metadata separately).
- Stable subtitle identity rules when multiple text regions overlap.
- Final Pydantic field constraints and enum names.

These must be resolved in the contract review before Agents 1–7 implement against them.
