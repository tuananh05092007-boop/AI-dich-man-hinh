from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ai_screen_translator.contracts.models import (
    BoundingBox, LifecycleState, OCRObservation, RecognitionStatus,
    TranslationEngine, TranslationResult, TranslationStatus,
)


def test_bbox_xyxy_order_is_validated():
    with pytest.raises(ValidationError):
        BoundingBox(x1=20, y1=10, x2=20, y2=30)


def test_ocr_observation_accepts_valid_payload():
    item = OCRObservation(
        subtitle_id="subtitle_1", generation_id=1, source_text="Hello", confidence=0.98,
        bbox={"x1": 1, "y1": 2, "x2": 30, "y2": 20},
        timestamp=datetime.now(timezone.utc), region_id="dialogue_roi",
        recognition_status=RecognitionStatus.ACCEPTED,
    )
    assert item.language == "en"
    assert item.bbox.as_xyxy() == (1, 2, 30, 20)


def test_ocr_confidence_must_be_normalized():
    with pytest.raises(ValidationError):
        OCRObservation(
            subtitle_id="subtitle_1", generation_id=1, source_text="Hello", confidence=1.1,
            bbox={"x1": 1, "y1": 2, "x2": 30, "y2": 20},
            timestamp=datetime.now(timezone.utc), region_id="roi",
            recognition_status=RecognitionStatus.ACCEPTED,
        )


def test_contract_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        OCRObservation(
            subtitle_id="s1", generation_id=1, source_text="Hi", confidence=0.5,
            bbox={"x1": 0, "y1": 0, "x2": 2, "y2": 2},
            timestamp=datetime.now(timezone.utc), region_id="roi",
            recognition_status=RecognitionStatus.ACCEPTED, unreviewed_field=True,
        )


def test_translation_result_has_generation_guard_fields():
    result = TranslationResult(
        subtitle_id="s1", generation_id=2, source_text="Hello", translated_text="Xin chào",
        engine=TranslationEngine.NLLB, status=TranslationStatus.COMPLETED,
        latency_ms=10, completed_at=datetime.now(timezone.utc),
    )
    assert (result.subtitle_id, result.generation_id) == ("s1", 2)


def test_lifecycle_state_vocabulary_matches_master_prompt():
    assert {state.value for state in LifecycleState} == {
        "NO_TEXT", "TEXT_DETECTED", "TEXT_STABILIZING", "TRANSLATION_PENDING",
        "TRANSLATING", "DISPLAYING", "TEXT_CHANGED", "CLEAR_PENDING", "CLEARED", "ERROR",
    }
