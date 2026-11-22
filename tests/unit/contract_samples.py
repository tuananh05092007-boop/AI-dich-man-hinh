"""Valid, JSON-compatible sample payloads for every public contract.

Used by contract, schema-consistency and documentation tests. Each call returns a fresh dict.
"""

from copy import deepcopy
from typing import Any

from ai_screen_translator.contracts import (
    PUBLIC_CONTRACTS,
    BoundingBox,
    CapturedFrame,
    ErrorInfo,
    GameProfile,
    LifecycleEvent,
    OCRObservation,
    OverlayUpdate,
    PerformanceMetric,
    SubtitleContext,
    TextRegion,
    TrackedText,
    TranslationRequest,
    TranslationResult,
)

T0 = "2026-11-20T10:00:00Z"
T1 = "2026-11-20T10:00:01Z"
T2 = "2026-11-20T10:00:02Z"

BBOX: dict[str, Any] = {"monitor_id": "DISPLAY1", "x1": 250, "y1": 820, "x2": 1300, "y2": 900}

_CONTEXT: dict[str, Any] = {
    "schema_version": "0.2",
    "game_id": "demo_rpg",
    "speaker": "unknown",
    "conversation_history": [
        {
            "speaker": "Elara",
            "content": "The gate is sealed.",
            "translation": "Cánh cổng đã bị phong ấn.",
            "timestamp": T0,
        }
    ],
    "glossary": {"Elara": "Elara", "gate": "cổng"},
    "translation_style": "context_adaptive",
    "source_language": "en",
    "target_language": "vi",
}

_ERROR: dict[str, Any] = {
    "code": "timeout",
    "component": "translation",
    "message": "Provider did not answer within the deadline.",
    "retryable": True,
    "error_type": "TimeoutError",
    "status_code": None,
}

_SAMPLES: dict[type, dict[str, Any]] = {
    BoundingBox: dict(BBOX),
    CapturedFrame: {
        "schema_version": "0.2",
        "frame_id": "frame_000042",
        "sequence": 42,
        "monitor_id": "DISPLAY1",
        "width": 1920,
        "height": 1080,
        "pixel_format": "bgra8",
        "captured_at": T0,
        "captured_monotonic_ns": 123456789,
        "buffer": {
            "pool_id": "capture_pool",
            "slot": 3,
            "slot_generation": 7,
            "stride_bytes": 7680,
            "size_bytes": 8294400,
        },
        "dirty_regions": [{"monitor_id": "DISPLAY1", "x1": 0, "y1": 800, "x2": 1920, "y2": 1000}],
    },
    ErrorInfo: dict(_ERROR),
    GameProfile: {
        "schema_version": "0.2",
        "game_id": "demo_rpg",
        "display_name": "Demo RPG",
        "executable_name": "demo_rpg.exe",
        "monitor_id": "DISPLAY1",
        "display_mode": "borderless_windowed",
        "reference_resolution": {"width": 1920, "height": 1080},
        "roi": [
            {
                "region_id": "dialogue_roi",
                "bbox": dict(BBOX),
                "content_type": "subtitle",
                "enabled": True,
            }
        ],
        "ocr": {
            "profile": "outlined_text",
            "adaptive_threshold": True,
            "clahe": True,
            "invert": False,
            "scale_factor": 2.0,
            "min_confidence": 0.6,
        },
        "translation_style": "context_adaptive",
        "overlay_style": {
            "placement": "below",
            "offset_x": 0,
            "offset_y": 12,
            "font_size_px": 28,
            "text_color": "#FFFFFF",
            "background_color": "#101010",
            "opacity": 0.85,
        },
        "glossary_path": "glossaries/demo_rpg.json",
        "glossary": {"Elara": "Elara"},
        "character_names": ["Elara"],
        "source_language": "en",
        "target_language": "vi",
    },
    LifecycleEvent: {
        "schema_version": "0.2",
        "subtitle_id": "subtitle_0001",
        "generation_id": 2,
        "previous_state": "DISPLAYING",
        "current_state": "TEXT_CHANGED",
        "timestamp": T1,
        "reason": "text_changed",
        "region_id": "dialogue_roi",
        "frame_id": "frame_000043",
        "previous_generation_id": 1,
        "error": None,
    },
    OCRObservation: {
        "schema_version": "0.2",
        "frame_id": "frame_000042",
        "region_id": "dialogue_roi",
        "subtitle_id": None,
        "generation_id": None,
        "source_text": "You should not have come here.",
        "raw_text": "You should not have come here .",
        "confidence": 0.97,
        "bbox": dict(BBOX),
        "timestamp": T0,
        "language": "en",
        "recognition_status": "accepted",
        "preprocessing_profile": "outlined_text",
    },
    OverlayUpdate: {
        "schema_version": "0.2",
        "subtitle_id": "subtitle_0001",
        "generation_id": 1,
        "source_text": "You should not have come here.",
        "translated_text": "Ngươi không nên đến đây.",
        "bbox": dict(BBOX),
        "created_at": T1,
        "expires_at": T2,
        "batch_id": None,
    },
    PerformanceMetric: {
        "schema_version": "0.2",
        "metric": "ocr_latency",
        "value": 84.5,
        "unit": "ms",
        "timestamp": T0,
        "component": "ocr",
        "subtitle_id": "subtitle_0001",
        "generation_id": 1,
        "frame_id": "frame_000042",
        "region_id": "dialogue_roi",
        "engine": None,
    },
    SubtitleContext: dict(_CONTEXT),
    TextRegion: {
        "schema_version": "0.2",
        "region_id": "dialogue_roi",
        "frame_id": "frame_000042",
        "bbox": dict(BBOX),
        "confidence": 0.91,
        "source": "profile_roi",
        "content_type": "subtitle",
        "detected_at": T0,
    },
    TrackedText: {
        "schema_version": "0.2",
        "subtitle_id": "subtitle_0001",
        "generation_id": 1,
        "region_id": "dialogue_roi",
        "text": "You should not have come here.",
        "bbox": dict(BBOX),
        "state": "TEXT_STABILIZING",
        "first_seen_at": T0,
        "generation_started_at": T0,
        "last_seen_at": T1,
        "confidence": 0.96,
        "change_kind": "new",
        "similarity": None,
        "observation_count": 3,
        "last_frame_id": "frame_000044",
    },
    TranslationRequest: {
        "schema_version": "0.2",
        "subtitle_id": "subtitle_0001",
        "generation_id": 1,
        "source_text": "You should not have come here.",
        "context": dict(_CONTEXT),
        "source_language": "en",
        "target_language": "vi",
        "requested_at": T1,
        "deadline_ms": 1500,
        "idempotency_key": "subtitle_0001:1:7f3a9c",
        "trigger": "auto",
        "batch_id": None,
    },
    TranslationResult: {
        "schema_version": "0.2",
        "subtitle_id": "subtitle_0001",
        "generation_id": 1,
        "source_text": "You should not have come here.",
        "translated_text": "Ngươi không nên đến đây.",
        "engine": "nllb",
        "model_id": "nllb-200-distilled-600M",
        "status": "completed",
        "latency_ms": 412.0,
        "completed_at": T2,
        "error": None,
        "skip_reason": None,
    },
}


def sample(model: type) -> dict[str, Any]:
    """A fresh, valid payload for ``model``."""
    return deepcopy(_SAMPLES[model])


def sample_models() -> tuple[type, ...]:
    return tuple(_SAMPLES)


def hotkey_request() -> dict[str, Any]:
    payload = sample(TranslationRequest)
    payload.update(
        subtitle_id="f8_batch_0007_1",
        trigger="hotkey",
        batch_id="batch_0007",
        idempotency_key="f8_batch_0007_1:1:7f3a9c",
    )
    return payload


def failed_result() -> dict[str, Any]:
    payload = sample(TranslationResult)
    payload.update(
        status="failed", translated_text=None, error=dict(_ERROR), model_id=None, engine="openai"
    )
    return payload


def skipped_result() -> dict[str, Any]:
    payload = sample(TranslationResult)
    payload.update(
        status="skipped",
        translated_text=None,
        engine=None,
        model_id=None,
        skip_reason="stale_generation",
    )
    return payload


def error_event() -> dict[str, Any]:
    payload = sample(LifecycleEvent)
    payload.update(
        previous_state="TRANSLATING",
        current_state="ERROR",
        generation_id=1,
        previous_generation_id=None,
        reason="stage_error",
        error=dict(_ERROR),
    )
    return payload


assert set(_SAMPLES) == set(PUBLIC_CONTRACTS), "add a sample for every public contract"
