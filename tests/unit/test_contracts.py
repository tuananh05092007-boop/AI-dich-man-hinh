"""Behavioral tests for the shared data contracts (valid and invalid cases)."""

import math
from datetime import UTC, datetime, timedelta, timezone
from itertools import product

import pytest
from contract_samples import (
    BBOX,
    error_event,
    failed_result,
    sample,
    skipped_result,
)
from pydantic import ValidationError

from ai_screen_translator.contracts import (
    ALLOWED_TRANSITIONS,
    PUBLIC_CONTRACTS,
    BoundingBox,
    CapturedFrame,
    DialogueEvent,
    ErrorInfo,
    GameProfile,
    LifecycleEvent,
    LifecycleState,
    OCRObservation,
    OCRResult,
    OverlayMessage,
    OverlayUpdate,
    PerformanceMetric,
    SubtitleContext,
    TextRegion,
    TrackedText,
    TranslationRequest,
    TranslationResult,
    is_valid_transition,
    redact_secrets,
)


def invalid(model, **changes):
    payload = sample(model)
    payload.update(changes)
    with pytest.raises(ValidationError):
        model.model_validate(payload)


# --------------------------------------------------------------------------- #
# Every public contract
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("model", PUBLIC_CONTRACTS, ids=lambda m: m.__name__)
def test_sample_round_trips_through_json(model):
    item = model.model_validate(sample(model))
    assert model.model_validate_json(item.model_dump_json()) == item


@pytest.mark.parametrize("model", PUBLIC_CONTRACTS, ids=lambda m: m.__name__)
def test_every_contract_rejects_unknown_fields(model):
    invalid(model, unreviewed_field=True)


@pytest.mark.parametrize(
    "model",
    [m for m in PUBLIC_CONTRACTS if "schema_version" in m.model_fields],
    ids=lambda m: m.__name__,
)
def test_top_level_contracts_carry_and_pin_schema_version(model):
    assert model.model_validate(sample(model)).schema_version == "0.1"
    invalid(model, schema_version="9.9")


def test_nested_value_objects_have_no_schema_version():
    assert "schema_version" not in BoundingBox.model_fields
    assert "schema_version" not in ErrorInfo.model_fields


def test_master_prompt_names_are_aliases_not_second_models():
    assert OCRResult is OCRObservation
    assert DialogueEvent is LifecycleEvent
    assert OverlayMessage is OverlayUpdate


# --------------------------------------------------------------------------- #
# BoundingBox
# --------------------------------------------------------------------------- #
def test_bbox_valid_and_helpers():
    box = BoundingBox.model_validate(BBOX)
    assert box.as_xyxy() == (250, 820, 1300, 900)
    assert (box.width, box.height) == (1050, 80)


def test_bbox_is_immutable():
    box = BoundingBox.model_validate(BBOX)
    with pytest.raises(ValidationError):
        box.x1 = 5


@pytest.mark.parametrize(
    "changes",
    [
        {"x2": 250},  # zero width
        {"x2": 100},  # right of left reversed
        {"y2": 820},  # zero height
        {"y2": 10},  # bottom above top
    ],
)
def test_bbox_rejects_bad_ordering(changes):
    with pytest.raises(ValidationError):
        BoundingBox.model_validate({**BBOX, **changes})


@pytest.mark.parametrize("field", ["x1", "y1", "x2", "y2"])
def test_bbox_rejects_negative_coordinates(field):
    with pytest.raises(ValidationError):
        BoundingBox.model_validate({**BBOX, field: -1})


@pytest.mark.parametrize("value", [None, "", "   ", " DISPLAY1", "A\nB"])
def test_bbox_requires_valid_monitor_id(value):
    with pytest.raises(ValidationError):
        BoundingBox.model_validate({**BBOX, "monitor_id": value})


def test_bbox_missing_monitor_id_is_rejected():
    payload = dict(BBOX)
    del payload["monitor_id"]
    with pytest.raises(ValidationError, match="monitor_id"):
        BoundingBox.model_validate(payload)


def test_bbox_rejects_non_integer_and_bool_coordinates():
    for bad in (1.5, "10", True):
        with pytest.raises(ValidationError):
            BoundingBox.model_validate({**BBOX, "x1": bad})


def test_bbox_bounds_check_is_explicit_and_uses_half_open_convention():
    box = BoundingBox.model_validate({**BBOX, "x2": 1920, "y2": 1080})
    assert box.fits_within(1920, 1080)  # x2 == width is inside (half-open)
    assert not box.fits_within(1919, 1080)
    with pytest.raises(ValueError, match="exceeds monitor bounds"):
        box.ensure_within(1280, 720)


def test_bbox_construction_does_not_invent_monitor_dimensions():
    # A huge box is valid on its own: bounds are only checked when dimensions are supplied.
    assert BoundingBox(monitor_id="m", x1=0, y1=0, x2=100_000, y2=100_000)


# --------------------------------------------------------------------------- #
# Timestamps
# --------------------------------------------------------------------------- #
def test_utc_aware_datetime_is_accepted_and_serialized_with_z():
    item = TextRegion.model_validate(
        {**sample(TextRegion), "detected_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)}
    )
    assert item.model_dump(mode="json")["detected_at"] == "2026-01-02T03:04:05Z"


def test_explicit_zero_offset_is_accepted():
    value = datetime(2026, 1, 2, tzinfo=timezone(timedelta(0)))
    assert (
        TextRegion.model_validate({**sample(TextRegion), "detected_at": value}).detected_at.tzinfo
        is UTC
    )


@pytest.mark.parametrize(
    "value,message",
    [
        (datetime(2026, 1, 2, 3, 4, 5), "naive datetimes are rejected"),
        ("2026-01-02T03:04:05", "naive datetimes are rejected"),
        (datetime(2026, 1, 2, tzinfo=timezone(timedelta(hours=7))), "must be UTC"),
        ("2026-01-02T03:04:05+07:00", "must be UTC"),
    ],
)
def test_naive_and_non_utc_datetimes_are_rejected(value, message):
    with pytest.raises(ValidationError, match=message):
        TextRegion.model_validate({**sample(TextRegion), "detected_at": value})


def test_assignment_is_revalidated():
    item = TextRegion.model_validate(sample(TextRegion))
    with pytest.raises(ValidationError):
        item.detected_at = datetime(2026, 1, 2)


# --------------------------------------------------------------------------- #
# Confidence and text
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value", [-0.01, 1.01, math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("model", [OCRObservation, TextRegion, TrackedText])
def test_confidence_outside_unit_interval_is_rejected(model, value):
    invalid(model, confidence=value)


@pytest.mark.parametrize("value", [0.0, 1.0])
def test_confidence_bounds_are_inclusive(value):
    assert TextRegion.model_validate({**sample(TextRegion), "confidence": value})


def test_similarity_must_also_be_normalized():
    invalid(TrackedText, similarity=1.5, change_kind="modified", generation_id=2)


@pytest.mark.parametrize("text", ["\ud800", "bad\x00nul"])
def test_text_must_be_valid_utf8(text):
    invalid(TranslationRequest, source_text=text)


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_meaningful_text_rejects_blank(text):
    invalid(TranslationRequest, source_text=text)
    invalid(OverlayUpdate, translated_text=text)


def test_vietnamese_and_multiline_text_is_preserved():
    payload = {**sample(OverlayUpdate), "translated_text": "Xin chào\nthế giới — ổn chứ?"}
    assert OverlayUpdate.model_validate(payload).translated_text.endswith("ổn chứ?")


def test_text_length_is_bounded():
    invalid(TranslationRequest, source_text="a" * 9000)


# --------------------------------------------------------------------------- #
# OCR
# --------------------------------------------------------------------------- #
def test_ocr_valid_payload():
    item = OCRObservation.model_validate(sample(OCRObservation))
    assert item.language == "en"
    assert item.monitor_id == "DISPLAY1"
    assert item.subtitle_id is None and item.generation_id is None


def test_ocr_after_tracking_carries_both_ids():
    payload = {**sample(OCRObservation), "subtitle_id": "s1", "generation_id": 2}
    assert OCRObservation.model_validate(payload).generation_id == 2


@pytest.mark.parametrize("changes", [{"subtitle_id": "s1"}, {"generation_id": 1}])
def test_ocr_subtitle_and_generation_ids_are_set_together(changes):
    invalid(OCRObservation, **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"source_text": ""},  # empty text but status accepted
        {"source_text": "   "},
        {"confidence": 1.1},
        {"frame_id": None},
        {"region_id": ""},
        {"recognition_status": "unknown"},
        {"language": "fr"},
        {"generation_id": 0, "subtitle_id": "s1"},
        {"bbox": {"x1": 1, "y1": 2, "x2": 30, "y2": 20}},  # no monitor_id
        {"timestamp": "2026-11-20T10:00:00"},
    ],
)
def test_ocr_invalid_payloads(changes):
    invalid(OCRObservation, **changes)


def test_ocr_empty_status_requires_empty_text():
    empty = {
        **sample(OCRObservation),
        "recognition_status": "empty",
        "source_text": "",
        "raw_text": None,
        "confidence": 0.9,
    }
    assert OCRObservation.model_validate(empty).source_text == ""
    invalid(OCRObservation, **{**empty, "source_text": "Hello"})
    invalid(OCRObservation, **{**empty, "raw_text": "Hello"})


# --------------------------------------------------------------------------- #
# Capture / region
# --------------------------------------------------------------------------- #
def test_captured_frame_valid_and_contains_bbox():
    frame = CapturedFrame.model_validate(sample(CapturedFrame))
    assert frame.contains(BoundingBox.model_validate(BBOX))
    assert not frame.contains(BoundingBox(monitor_id="DISPLAY2", x1=0, y1=0, x2=5, y2=5))
    assert not frame.contains(BoundingBox(monitor_id="DISPLAY1", x1=0, y1=0, x2=5000, y2=5))


@pytest.mark.parametrize(
    "path,value",
    [
        (("buffer", "stride_bytes"), 100),  # smaller than one row
        (("buffer", "size_bytes"), 1000),  # smaller than stride * height
        (("width",), 0),
        (("pixel_format",), "h264"),
        (("sequence",), -1),
        (("buffer", "slot_generation"), 0),
    ],
)
def test_captured_frame_invalid_layout(path, value):
    payload = sample(CapturedFrame)
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        CapturedFrame.model_validate(payload)


def test_captured_frame_carries_no_pixel_payload():
    assert not {"pixels", "data", "image", "bytes"} & set(CapturedFrame.model_fields)
    assert not {"pixels", "data", "image", "bytes"} & set(
        CapturedFrame.model_fields["buffer"].annotation.model_fields
    )


def test_captured_frame_dirty_region_must_be_on_frame():
    bad = {"monitor_id": "DISPLAY2", "x1": 0, "y1": 0, "x2": 10, "y2": 10}
    invalid(CapturedFrame, dirty_regions=[bad])
    invalid(CapturedFrame, dirty_regions=[{**BBOX, "x2": 5000}])


def test_text_region_valid_and_invalid():
    region = TextRegion.model_validate(sample(TextRegion))
    assert region.monitor_id == "DISPLAY1"
    invalid(TextRegion, source="telepathy")
    invalid(TextRegion, frame_id="")
    invalid(TextRegion, bbox={"x1": 1, "y1": 1, "x2": 5, "y2": 5})


# --------------------------------------------------------------------------- #
# SubtitleContext
# --------------------------------------------------------------------------- #
def test_subtitle_context_is_strongly_typed():
    context = SubtitleContext.model_validate(sample(SubtitleContext))
    assert context.conversation_history[0].speaker == "Elara"
    assert context.speaker == "unknown"
    assert (context.source_language, context.target_language) == ("en", "vi")


def test_subtitle_context_rejects_untyped_history_entries():
    invalid(SubtitleContext, conversation_history=[{"role": "npc", "text": "hi"}])
    invalid(SubtitleContext, conversation_history=["just a string"])
    invalid(SubtitleContext, conversation_history=[{"speaker": "A", "content": " "}])


@pytest.mark.parametrize(
    "changes",
    [
        {"game_id": ""},
        {"speaker": "  "},
        {"translation_style": "sarcastic"},
        {"source_language": "vi"},
        {"target_language": "fr"},
        {"glossary": {"": "x"}},
        {"glossary": {"gate": ""}},
        {"conversation_history": [{"speaker": "A", "content": "x"}] * 33},
    ],
)
def test_subtitle_context_invalid(changes):
    invalid(SubtitleContext, **changes)


def test_conversation_timestamps_must_be_utc():
    payload = sample(SubtitleContext)
    payload["conversation_history"][0]["timestamp"] = "2026-11-20T10:00:00"
    with pytest.raises(ValidationError):
        SubtitleContext.model_validate(payload)


# --------------------------------------------------------------------------- #
# Translation request / result
# --------------------------------------------------------------------------- #
def test_translation_request_valid_and_deadline():
    request = TranslationRequest.model_validate(sample(TranslationRequest))
    assert request.deadline_at == request.requested_at + timedelta(milliseconds=1500)
    assert request.generation_key == ("subtitle_0001", 1)
    assert (request.source_language, request.target_language) == ("en", "vi")


@pytest.mark.parametrize(
    "changes",
    [
        {"subtitle_id": ""},
        {"generation_id": 0},
        {"generation_id": "1"},
        {"generation_id": True},
        {"deadline_ms": 0},
        {"deadline_ms": 10_000_000},
        {"idempotency_key": ""},
        {"target_language": "en"},
        {"source_language": "vi"},
        {"context": None},
        {"requested_at": "2026-11-20T10:00:00"},
    ],
)
def test_translation_request_invalid(changes):
    invalid(TranslationRequest, **changes)


def test_translation_result_completed_invariants():
    result = TranslationResult.model_validate(sample(TranslationResult))
    assert result.generation_key == ("subtitle_0001", 1)
    invalid(TranslationResult, translated_text=None)
    invalid(TranslationResult, translated_text="")
    invalid(TranslationResult, translated_text="   ")
    invalid(TranslationResult, engine=None)
    invalid(TranslationResult, error=failed_result()["error"])
    invalid(TranslationResult, skip_reason="cancelled")
    invalid(TranslationResult, latency_ms=-1)
    invalid(TranslationResult, latency_ms=math.nan)


def test_translation_result_failed_invariants():
    result = TranslationResult.model_validate(failed_result())
    assert result.error.code == "timeout"
    for changes in (
        {"error": None},
        {"translated_text": "Xin chào"},
        {"skip_reason": "cancelled"},
    ):
        with pytest.raises(ValidationError):
            TranslationResult.model_validate({**failed_result(), **changes})


def test_translation_result_skipped_semantics():
    result = TranslationResult.model_validate(skipped_result())
    assert result.skip_reason == "stale_generation" and result.error is None
    for changes in (
        {"skip_reason": None},
        {"translated_text": "Xin chào"},
        {"error": failed_result()["error"]},
    ):
        with pytest.raises(ValidationError):
            TranslationResult.model_validate({**skipped_result(), **changes})


def test_translation_result_status_is_required_and_closed():
    invalid(TranslationResult, status="done")
    payload = sample(TranslationResult)
    del payload["status"]
    with pytest.raises(ValidationError):
        TranslationResult.model_validate(payload)


def test_translation_result_has_no_place_for_credentials():
    fields = set(TranslationResult.model_fields) | set(TranslationRequest.model_fields)
    assert not {"api_key", "headers", "authorization", "token", "secret"} & fields
    invalid(TranslationRequest, api_key="sk-live-123")


def test_translation_memory_is_a_valid_actual_engine():
    assert TranslationResult.model_validate(
        {**sample(TranslationResult), "engine": "translation_memory"}
    )


# --------------------------------------------------------------------------- #
# Structured errors
# --------------------------------------------------------------------------- #
def test_error_info_redacts_secrets():
    info = ErrorInfo.model_validate(
        {
            **sample(ErrorInfo),
            "message": (
                "401 using sk-proj-ABCDEF123456 with Authorization: Bearer abc.def api_key=hunter2"
            ),
        }
    )
    for leaked in ("sk-proj", "abc.def", "hunter2"):
        assert leaked not in info.message
    assert "[REDACTED]" in info.message


def test_redaction_is_idempotent_and_leaves_normal_text():
    text = "Provider did not answer within the deadline."
    assert redact_secrets(text) == text
    once = redact_secrets("token=abc123")
    assert redact_secrets(once) == once


@pytest.mark.parametrize(
    "changes",
    [
        {"code": "oops"},
        {"component": "toaster"},
        {"message": ""},
        {"message": "  "},
        {"status_code": 99},
        {"status_code": 700},
        {"traceback": "..."},
    ],
)
def test_error_info_invalid(changes):
    invalid(ErrorInfo, **changes)


# --------------------------------------------------------------------------- #
# Generation guard / overlay
# --------------------------------------------------------------------------- #
def test_generation_guard_rejects_stale_and_foreign_items():
    update = OverlayUpdate.model_validate(sample(OverlayUpdate))
    assert update.is_current("subtitle_0001", 1)
    assert not update.is_current("subtitle_0001", 2)  # stale generation
    assert not update.is_current("subtitle_0002", 1)  # different subtitle


@pytest.mark.parametrize(
    "model", [TranslationRequest, TranslationResult, OverlayUpdate, LifecycleEvent, TrackedText]
)
def test_generation_scoped_contracts_require_both_ids(model):
    for missing in ("subtitle_id", "generation_id"):
        payload = sample(model)
        del payload[missing]
        with pytest.raises(ValidationError):
            model.model_validate(payload)


def test_overlay_valid_and_metadata():
    update = OverlayUpdate.model_validate(sample(OverlayUpdate))
    assert update.bbox.monitor_id == "DISPLAY1"
    assert update.display_mode == "bilingual"
    assert update.is_expired(datetime(2026, 11, 20, 10, 0, 2, tzinfo=UTC))
    assert not update.is_expired(datetime(2026, 11, 20, 10, 0, 1, 500000, tzinfo=UTC))
    with pytest.raises(ValueError):
        update.is_expired(datetime(2026, 11, 20, 10, 0, 2))  # naive "now" rejected


@pytest.mark.parametrize(
    "changes",
    [
        {"display_mode": "hologram"},
        {"expires_at": "2026-11-20T10:00:01Z"},  # equal to created_at
        {"expires_at": "2026-11-20T09:00:00Z"},
        {"expires_at": None},
        {"bbox": {"x1": 1, "y1": 1, "x2": 5, "y2": 5}},
    ],
)
def test_overlay_invalid(changes):
    invalid(OverlayUpdate, **changes)


# --------------------------------------------------------------------------- #
# Tracking / lifecycle
# --------------------------------------------------------------------------- #
def test_tracked_text_valid():
    item = TrackedText.model_validate(sample(TrackedText))
    assert item.monitor_id == "DISPLAY1" and item.change_kind == "new"


@pytest.mark.parametrize(
    "changes",
    [
        {"state": "NO_TEXT"},
        {"first_seen_at": "2026-11-20T11:00:00Z"},
        {"last_seen_at": "2026-11-20T09:00:00Z"},
        {"observation_count": 0},
        {"text": " "},
        {"change_kind": "new", "generation_id": 2},
        {"change_kind": "new", "similarity": 0.4},
        {"change_kind": "modified", "generation_id": 1},
    ],
)
def test_tracked_text_invalid(changes):
    invalid(TrackedText, **changes)


def test_tracked_text_later_generation_with_change_metadata():
    payload = {
        **sample(TrackedText),
        "generation_id": 3,
        "change_kind": "appended",
        "similarity": 0.82,
    }
    assert TrackedText.model_validate(payload).similarity == 0.82


def test_lifecycle_state_vocabulary_matches_architecture():
    assert {state.value for state in LifecycleState} == {
        "NO_TEXT", "TEXT_DETECTED", "TEXT_STABILIZING", "TRANSLATION_PENDING",
        "TRANSLATING", "DISPLAYING", "TEXT_CHANGED", "CLEAR_PENDING", "CLEARED", "ERROR",
    }  # fmt: skip


def test_transition_table_covers_every_state_and_stays_in_vocabulary():
    assert set(ALLOWED_TRANSITIONS) == set(LifecycleState)
    for targets in ALLOWED_TRANSITIONS.values():
        assert targets <= set(LifecycleState)


def test_cleared_is_terminal_and_nothing_re_enters_no_text():
    assert ALLOWED_TRANSITIONS[LifecycleState.CLEARED] == frozenset()
    assert all(LifecycleState.NO_TEXT not in t for t in ALLOWED_TRANSITIONS.values())


def test_lifecycle_event_valid():
    event = LifecycleEvent.model_validate(sample(LifecycleEvent))
    assert event.generation_key == ("subtitle_0001", 2)


@pytest.mark.parametrize(
    "previous,current",
    [
        (p, c)
        for p, c in product(LifecycleState, LifecycleState)
        if p is not c and not is_valid_transition(p, c)
    ],
)
def test_lifecycle_event_rejects_every_disallowed_transition(previous, current):
    payload = {
        **sample(LifecycleEvent),
        "previous_state": previous.value,
        "current_state": current.value,
        "generation_id": 1,
        "previous_generation_id": None,
        "error": None,
        "reason": "stage_error",
    }
    with pytest.raises(ValidationError):
        LifecycleEvent.model_validate(payload)


def test_lifecycle_event_rejects_self_transition():
    invalid(
        LifecycleEvent,
        previous_state="DISPLAYING",
        current_state="DISPLAYING",
        previous_generation_id=None,
    )


def test_lifecycle_new_subtitle_starts_at_generation_one():
    base = {
        **sample(LifecycleEvent),
        "previous_state": "NO_TEXT",
        "current_state": "TEXT_DETECTED",
        "previous_generation_id": None,
        "reason": "text_appeared",
    }
    assert LifecycleEvent.model_validate({**base, "generation_id": 1})
    with pytest.raises(ValidationError):
        LifecycleEvent.model_validate({**base, "generation_id": 2})


def test_lifecycle_error_state_requires_structured_error_and_only_then():
    assert LifecycleEvent.model_validate(error_event()).error.code == "timeout"
    invalid(LifecycleEvent, **{**error_event(), "error": None})
    invalid(LifecycleEvent, **{**sample(LifecycleEvent), "error": error_event()["error"]})


def test_text_changed_event_must_increment_generation_by_one():
    assert LifecycleEvent.model_validate(sample(LifecycleEvent))
    invalid(LifecycleEvent, previous_generation_id=None)
    invalid(LifecycleEvent, previous_generation_id=2)  # equal to generation_id
    invalid(LifecycleEvent, generation_id=5, previous_generation_id=1)
    # previous_generation_id is meaningless outside TEXT_CHANGED
    invalid(LifecycleEvent, previous_state="TEXT_CHANGED", current_state="TEXT_STABILIZING")


def test_lifecycle_reason_is_a_closed_vocabulary():
    invalid(LifecycleEvent, reason="")
    invalid(LifecycleEvent, reason="because")


# --------------------------------------------------------------------------- #
# GameProfile
# --------------------------------------------------------------------------- #
def test_game_profile_valid_and_defaults():
    profile = GameProfile.model_validate(sample(GameProfile))
    assert profile.roi[0].bbox.monitor_id == "DISPLAY1"
    minimal = GameProfile.model_validate({"game_id": "g"})
    assert minimal.display_mode == "unknown" and minimal.roi == []
    assert minimal.ocr.profile == "default" and (
        minimal.source_language,
        minimal.target_language,
    ) == ("en", "vi")


def _roi(region_id="r2", **bbox):
    return {"region_id": region_id, "bbox": {**BBOX, **bbox}}


@pytest.mark.parametrize(
    "changes",
    [
        {"game_id": ""},
        {"display_mode": "vr"},
        {"roi": [_roi("a"), _roi("a")]},  # duplicate region ids
        {"roi": [_roi(monitor_id="DISPLAY2")]},  # other monitor than profile
        {"roi": [_roi(x2=4000)]},  # outside reference resolution
        {"character_names": ["Elara", "Elara"]},
        {"glossary_path": "/etc/passwd"},
        {"glossary_path": "C:\\games\\g.json"},
        {"glossary_path": "..\\secrets.json"},
        {"glossary_path": "a/../../b.json"},
        {"ocr": {"profile": "p", "scale_factor": 0}},
        {"ocr": {"profile": "p", "min_confidence": 2}},
        {"ocr": {"profile": "p", "unknown": 1}},
        {"api_key": "sk-secret"},
        {"openai_api_key": "sk-secret"},
        {"target_language": "ja"},
    ],
)
def test_game_profile_invalid(changes):
    invalid(GameProfile, **changes)


def test_game_profile_without_reference_resolution_does_not_invent_bounds():
    payload = {**sample(GameProfile), "reference_resolution": None, "roi": [_roi(x2=99_999)]}
    assert GameProfile.model_validate(payload)


def test_game_profile_has_no_secret_fields():
    assert not {"api_key", "token", "secret", "password"} & set(GameProfile.model_fields)


# --------------------------------------------------------------------------- #
# PerformanceMetric
# --------------------------------------------------------------------------- #
def test_performance_metric_valid():
    metric = PerformanceMetric.model_validate(sample(PerformanceMetric))
    assert (metric.metric, metric.unit, metric.component) == ("ocr_latency", "ms", "ocr")


@pytest.mark.parametrize(
    "metric,unit,value",
    [
        ("capture_latency", "ms", 3.2),
        ("ocr_latency", "ms", 80),
        ("tracking_latency", "ms", 1),
        ("translation_latency", "ms", 400),
        ("render_latency", "ms", 5),
        ("end_to_end_latency", "ms", 900),
        ("cpu_usage", "percent", 12.5),
        ("gpu_usage", "percent", 0),
        ("ram_usage", "bytes", 2_000_000_000),
        ("vram_usage", "bytes", 500_000_000),
    ],
)
def test_performance_metric_accommodates_every_required_metric(metric, unit, value):
    payload = {**sample(PerformanceMetric), "metric": metric, "unit": unit, "value": value}
    assert PerformanceMetric.model_validate(payload)


@pytest.mark.parametrize(
    "changes",
    [
        {"metric": "fps"},
        {"value": -1},
        {"value": math.nan},
        {"value": math.inf},
        {"unit": "percent"},  # wrong unit for ocr_latency
        {"unit": "furlongs"},
        {"metric": "cpu_usage", "unit": "percent", "value": 150},
        {"subtitle_id": None},  # generation_id without subtitle_id
        {"component": "toaster"},
        {"timestamp": "2026-11-20T10:00:00"},
    ],
)
def test_performance_metric_invalid(changes):
    invalid(PerformanceMetric, **changes)
