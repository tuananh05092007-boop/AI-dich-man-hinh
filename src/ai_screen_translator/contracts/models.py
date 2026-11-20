"""Initial shared contracts for cross-module integration."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "0.1"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    schema_version: Literal["0.1"] = SCHEMA_VERSION


class RecognitionStatus(StrEnum):
    ACCEPTED = "accepted"
    LOW_CONFIDENCE = "low_confidence"
    REJECTED = "rejected"


class LifecycleState(StrEnum):
    NO_TEXT = "NO_TEXT"
    TEXT_DETECTED = "TEXT_DETECTED"
    TEXT_STABILIZING = "TEXT_STABILIZING"
    TRANSLATION_PENDING = "TRANSLATION_PENDING"
    TRANSLATING = "TRANSLATING"
    DISPLAYING = "DISPLAYING"
    TEXT_CHANGED = "TEXT_CHANGED"
    CLEAR_PENDING = "CLEAR_PENDING"
    CLEARED = "CLEARED"
    ERROR = "ERROR"


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x1: int = Field(ge=0)
    y1: int = Field(ge=0)
    x2: int = Field(gt=0)
    y2: int = Field(gt=0)

    @field_validator("x2")
    @classmethod
    def right_after_left(cls, value: int, info):
        left = info.data.get("x1")
        if left is not None and value <= left:
            raise ValueError("x2 must be greater than x1")
        return value

    @field_validator("y2")
    @classmethod
    def bottom_after_top(cls, value: int, info):
        top = info.data.get("y1")
        if top is not None and value <= top:
            raise ValueError("y2 must be greater than y1")
        return value

    def as_xyxy(self) -> tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)


class OCRObservation(ContractModel):
    subtitle_id: str = Field(min_length=1)
    generation_id: int = Field(ge=1)
    source_text: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox
    timestamp: datetime
    region_id: str = Field(min_length=1)
    language: Literal["en"] = "en"
    recognition_status: RecognitionStatus
    frame_id: str | None = None


class SubtitleContext(ContractModel):
    game_id: str = Field(min_length=1)
    speaker: str = "unknown"
    conversation_history: list[dict[str, str]] = Field(default_factory=list)
    glossary: dict[str, str] = Field(default_factory=dict)
    translation_style: str = "context_adaptive"
    source_language: Literal["en"] = "en"
    target_language: Literal["vi"] = "vi"


class TranslationRequest(ContractModel):
    subtitle_id: str = Field(min_length=1)
    generation_id: int = Field(ge=1)
    source_text: str = Field(min_length=1)
    context: SubtitleContext
    requested_at: datetime
    deadline_ms: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1)


class TranslationStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TranslationEngine(StrEnum):
    NLLB = "nllb"
    OPENAI = "openai"


class TranslationResult(ContractModel):
    subtitle_id: str = Field(min_length=1)
    generation_id: int = Field(ge=1)
    source_text: str = Field(min_length=1)
    translated_text: str = ""
    engine: TranslationEngine
    status: TranslationStatus
    latency_ms: float = Field(ge=0)
    completed_at: datetime
    error_code: str | None = None
    error_message: str | None = None


class OverlayUpdate(ContractModel):
    subtitle_id: str = Field(min_length=1)
    generation_id: int = Field(ge=1)
    source_text: str
    translated_text: str
    bbox: BoundingBox
    display_mode: Literal["vietnamese_only", "bilingual", "side_by_side", "floating_box"]
    expires_at: datetime


class LifecycleEvent(ContractModel):
    subtitle_id: str = Field(min_length=1)
    generation_id: int = Field(ge=1)
    previous_state: LifecycleState
    current_state: LifecycleState
    timestamp: datetime
    reason: str = ""
