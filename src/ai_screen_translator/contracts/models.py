"""Shared, versioned data contracts for the AI Screen Translator pipeline.

This module is the single canonical definition of every cross-module data type.
JSON Schemas are generated from these models (see ``schema_export``); the
human-readable specification lives in ``docs/DATA_CONTRACTS.md``.

Conventions (all enforced by validation):

* Unknown fields are rejected.
* Top-level contracts carry ``schema_version``; nested value objects do not.
* Datetimes are timezone-aware UTC. Elapsed durations are measured with a
  monotonic clock by the producer and carried as ``*_ms`` numbers.
* Confidence values are normalized to ``[0, 1]``.
* Bounding boxes are monitor-relative pixels and always name their monitor.
* Text is valid UTF-8; fields that must carry content reject blank strings.
"""

import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

SCHEMA_VERSION = "0.1"
MAX_TEXT_LENGTH = 8192
UNKNOWN_SPEAKER = "unknown"
REDACTED = "[REDACTED]"

__all__ = [
    "ALLOWED_TRANSITIONS",
    "MAX_TEXT_LENGTH",
    "PUBLIC_CONTRACTS",
    "REDACTED",
    "SCHEMA_VERSION",
    "UNKNOWN_SPEAKER",
    "BoundingBox",
    "CapturedFrame",
    "ChangeKind",
    "ContentType",
    "ContractModel",
    "ContractValue",
    "ConversationMessage",
    "DialogueEvent",
    "ErrorCode",
    "ErrorInfo",
    "FrameBufferRef",
    "GameDisplayMode",
    "GameProfile",
    "GenerationScopedContract",
    "LifecycleEvent",
    "LifecycleReason",
    "LifecycleState",
    "MetricUnit",
    "OCRObservation",
    "OCRPreprocessingConfig",
    "OCRResult",
    "OverlayDisplayMode",
    "OverlayMessage",
    "OverlayUpdate",
    "PerformanceMetric",
    "PerformanceMetricName",
    "PipelineComponent",
    "PixelFormat",
    "RecognitionStatus",
    "RegionSource",
    "Resolution",
    "RoiConfig",
    "SkipReason",
    "SubtitleContext",
    "TextRegion",
    "TrackedText",
    "TranslationEngine",
    "TranslationRequest",
    "TranslationResult",
    "TranslationStatus",
    "TranslationStyle",
    "is_valid_transition",
    "redact_secrets",
]


# --------------------------------------------------------------------------- #
# Reusable validated types
# --------------------------------------------------------------------------- #
def _valid_utf8(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("text must be valid UTF-8 (lone surrogates are not allowed)") from exc
    if "\x00" in value:
        raise ValueError("text must not contain NUL characters")
    return value


def _meaningful(value: str) -> str:
    _valid_utf8(value)
    if not value.strip():
        raise ValueError("text must not be blank")
    return value


def _identifier(value: str) -> str:
    if value != value.strip():
        raise ValueError("identifier must not have leading or trailing whitespace")
    if not value.isprintable():
        raise ValueError("identifier must not contain control characters")
    return value


def _require_utc(value: datetime) -> datetime:
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError("datetime must be timezone-aware UTC (naive datetimes are rejected)")
    if offset != timedelta(0):
        raise ValueError("datetime must be UTC (offset +00:00 / 'Z')")
    return value.astimezone(UTC)


Identifier = Annotated[str, Field(min_length=1, max_length=128), AfterValidator(_identifier)]
Utf8Text = Annotated[str, Field(max_length=MAX_TEXT_LENGTH), AfterValidator(_valid_utf8)]
MeaningfulText = Annotated[
    str, Field(min_length=1, max_length=MAX_TEXT_LENGTH), AfterValidator(_meaningful)
]
Term = Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_meaningful)]
Label = Annotated[str, Field(min_length=1, max_length=128), AfterValidator(_meaningful)]
ExecutableName = Annotated[str, Field(min_length=1, max_length=260), AfterValidator(_meaningful)]
GenerationId = Annotated[int, Field(ge=1, strict=True)]
PixelCoord = Annotated[int, Field(ge=0, strict=True)]
Confidence = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
NonNegativeFloat = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
UtcDatetime = Annotated[
    datetime,
    AfterValidator(_require_utc),
    Field(
        description="Timezone-aware UTC ISO-8601 timestamp (serialized with 'Z').",
        json_schema_extra={"pattern": r"(Z|\+00:00)$"},
    ),
]

_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/\-]+=*"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|token|secret|password|authorization)\b"
        r"\s*[:=]\s*\S+"
    ),
)


def redact_secrets(text: str) -> str:
    """Replace likely credentials with ``[REDACTED]`` (defense in depth, not a guarantee)."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(REDACTED, text)
    return text


def _redacted_message(value: str) -> str:
    return redact_secrets(_meaningful(value))


ErrorMessage = Annotated[
    str, Field(min_length=1, max_length=500), AfterValidator(_redacted_message)
]


# --------------------------------------------------------------------------- #
# Base classes
# --------------------------------------------------------------------------- #
class ContractModel(BaseModel):
    """Base for every top-level, externally exchanged contract (carries schema_version)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    schema_version: Literal["0.1"] = SCHEMA_VERSION


class ContractValue(BaseModel):
    """Base for immutable nested value objects (versioned through their parent contract)."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GenerationScopedContract(ContractModel):
    """Contract bound to one generation of one tracked subtitle (the generation guard key).

    ``subtitle_id`` is stable for one tracked subtitle instance. ``generation_id`` starts at 1
    and increments each time the normalized text of that subtitle changes while it stays
    visible. Consumers accept an item only if it matches the *active* key.
    """

    subtitle_id: Identifier
    generation_id: GenerationId

    @property
    def generation_key(self) -> tuple[str, int]:
        return (self.subtitle_id, self.generation_id)

    def is_current(self, active_subtitle_id: str, active_generation_id: int) -> bool:
        """True only when both ids match the active subtitle generation exactly."""
        return self.subtitle_id == active_subtitle_id and self.generation_id == active_generation_id


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #
class PipelineComponent(StrEnum):
    CAPTURE = "capture"
    PREPROCESSING = "preprocessing"
    REGION_DETECTION = "region_detection"
    OCR = "ocr"
    NORMALIZATION = "normalization"
    TRACKING = "tracking"
    CONTEXT = "context"
    TRANSLATION = "translation"
    TRANSLATION_MEMORY = "translation_memory"
    OVERLAY = "overlay"
    STORAGE = "storage"
    APP = "app"


class PixelFormat(StrEnum):
    BGRA8 = "bgra8"
    BGR8 = "bgr8"
    RGB8 = "rgb8"
    GRAY8 = "gray8"


_BYTES_PER_PIXEL = {
    PixelFormat.BGRA8: 4,
    PixelFormat.BGR8: 3,
    PixelFormat.RGB8: 3,
    PixelFormat.GRAY8: 1,
}


class ContentType(StrEnum):
    SUBTITLE = "subtitle"
    DIALOGUE = "dialogue"
    CHOICE = "choice"
    QUEST = "quest"
    ITEM_DESCRIPTION = "item_description"
    UI = "ui"
    UNKNOWN = "unknown"


class RegionSource(StrEnum):
    MANUAL_ROI = "manual_roi"
    PROFILE_ROI = "profile_roi"
    AUTO_DETECTED = "auto_detected"


class RecognitionStatus(StrEnum):
    ACCEPTED = "accepted"
    LOW_CONFIDENCE = "low_confidence"
    REJECTED = "rejected"
    EMPTY = "empty"


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


class LifecycleReason(StrEnum):
    TEXT_APPEARED = "text_appeared"
    TEXT_STABILIZED = "text_stabilized"
    TRANSLATION_REQUESTED = "translation_requested"
    TRANSLATION_STARTED = "translation_started"
    TRANSLATION_COMPLETED = "translation_completed"
    TEXT_CHANGED = "text_changed"
    TEXT_DISAPPEARED = "text_disappeared"
    TEXT_REAPPEARED = "text_reappeared"
    CLEAR_DEBOUNCE_ELAPSED = "clear_debounce_elapsed"
    STAGE_ERROR = "stage_error"
    RECOVERED = "recovered"


class ChangeKind(StrEnum):
    NEW = "new"
    UNCHANGED = "unchanged"
    APPENDED = "appended"  # progressive text rendering: new text extends the old
    MODIFIED = "modified"  # small edit of the previous text
    REPLACED = "replaced"  # substantially different text


class TranslationStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TranslationEngine(StrEnum):
    NLLB = "nllb"
    OPENAI = "openai"
    TRANSLATION_MEMORY = "translation_memory"


class SkipReason(StrEnum):
    STALE_GENERATION = "stale_generation"
    CANCELLED = "cancelled"
    DUPLICATE_REQUEST = "duplicate_request"


class TranslationStyle(StrEnum):
    CONTEXT_ADAPTIVE = "context_adaptive"
    LITERAL = "literal"
    NATURAL = "natural"


class OverlayDisplayMode(StrEnum):
    VIETNAMESE_ONLY = "vietnamese_only"
    BILINGUAL = "bilingual"
    SIDE_BY_SIDE = "side_by_side"
    FLOATING_BOX = "floating_box"


class GameDisplayMode(StrEnum):
    WINDOWED = "windowed"
    BORDERLESS_WINDOWED = "borderless_windowed"
    FULLSCREEN_EXCLUSIVE = "fullscreen_exclusive"
    UNKNOWN = "unknown"


class ErrorCode(StrEnum):
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    AUTH_ERROR = "auth_error"
    RATE_LIMITED = "rate_limited"
    MODEL_UNAVAILABLE = "model_unavailable"
    INVALID_REQUEST = "invalid_request"
    INVALID_RESPONSE = "invalid_response"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    ENGINE_ERROR = "engine_error"
    INTERNAL_ERROR = "internal_error"


class PerformanceMetricName(StrEnum):
    CAPTURE_LATENCY = "capture_latency"
    OCR_LATENCY = "ocr_latency"
    TRACKING_LATENCY = "tracking_latency"
    TRANSLATION_LATENCY = "translation_latency"
    RENDER_LATENCY = "render_latency"
    END_TO_END_LATENCY = "end_to_end_latency"
    CPU_USAGE = "cpu_usage"
    RAM_USAGE = "ram_usage"
    GPU_USAGE = "gpu_usage"
    VRAM_USAGE = "vram_usage"


class MetricUnit(StrEnum):
    MILLISECONDS = "ms"
    PERCENT = "percent"
    BYTES = "bytes"


# --------------------------------------------------------------------------- #
# Shared value objects
# --------------------------------------------------------------------------- #
class BoundingBox(ContractValue):
    """Axis-aligned rectangle in *monitor-relative* physical pixels.

    Origin is the top-left pixel of the monitor named by ``monitor_id``; x grows right and y
    grows down. The box is half-open: it covers pixels ``x1 <= x < x2`` and ``y1 <= y < y2``,
    so ``width = x2 - x1``. Coordinates are never virtual-desktop coordinates.
    """

    monitor_id: Identifier
    x1: PixelCoord
    y1: PixelCoord
    x2: PixelCoord
    y2: PixelCoord

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.x2 <= self.x1:
            raise ValueError("x2 must be greater than x1")
        if self.y2 <= self.y1:
            raise ValueError("y2 must be greater than y1")
        return self

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    def as_xyxy(self) -> tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)

    def fits_within(self, monitor_width: int, monitor_height: int) -> bool:
        """Whether the box lies inside a monitor of the given size (caller supplies the size)."""
        return self.x2 <= monitor_width and self.y2 <= monitor_height

    def ensure_within(self, monitor_width: int, monitor_height: int) -> Self:
        if not self.fits_within(monitor_width, monitor_height):
            raise ValueError(
                f"bbox {self.as_xyxy()} exceeds monitor bounds {monitor_width}x{monitor_height}"
            )
        return self


class Resolution(ContractValue):
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)


class ErrorInfo(ContractValue):
    """Structured, secret-free error description.

    ``message`` is passed through :func:`redact_secrets`. No tracebacks, request headers or
    free-form dictionaries are carried.
    """

    code: ErrorCode
    component: PipelineComponent
    message: ErrorMessage
    retryable: bool = False
    error_type: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    status_code: Annotated[int, Field(ge=100, le=599, strict=True)] | None = None


class ConversationMessage(ContractValue):
    """One previous dialogue line in the sliding context window."""

    speaker: Label = UNKNOWN_SPEAKER
    content: MeaningfulText
    translation: MeaningfulText | None = None
    timestamp: UtcDatetime | None = None


# --------------------------------------------------------------------------- #
# Capture layer
# --------------------------------------------------------------------------- #
class FrameBufferRef(ContractValue):
    """Lightweight reference to pixels held in the capture module's frame pool.

    Pixels are never copied through queues. Ownership stays with the capture module's pool:
    consumers treat the buffer as read-only and must release it through the capture interface.
    ``slot_generation`` changes whenever the slot is recycled, so a stale reference is detectable.
    A reference is process-local and must not be persisted or sent across processes.
    """

    pool_id: Identifier
    slot: int = Field(ge=0, strict=True)
    slot_generation: int = Field(ge=1, strict=True)
    stride_bytes: int = Field(gt=0, strict=True)
    size_bytes: int = Field(gt=0, strict=True)


class CapturedFrame(ContractModel):
    """One captured full-monitor frame.

    ``width``/``height`` are the monitor's physical pixel size, so monitor-relative bounding
    boxes map 1:1 onto frame pixels. Cropped ROI images are internal to preprocessing and are
    not contracts.
    """

    frame_id: Identifier
    sequence: int = Field(ge=0, strict=True, description="Per-monitor, strictly increasing.")
    monitor_id: Identifier
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    pixel_format: PixelFormat
    captured_at: UtcDatetime
    captured_monotonic_ns: int | None = Field(
        default=None,
        ge=0,
        strict=True,
        description="Process-local monotonic clock; for latency only, never persisted.",
    )
    buffer: FrameBufferRef
    dirty_regions: list[BoundingBox] = Field(default_factory=list, max_length=256)

    @model_validator(mode="after")
    def _consistent_layout(self) -> Self:
        min_stride = self.width * _BYTES_PER_PIXEL[self.pixel_format]
        if self.buffer.stride_bytes < min_stride:
            raise ValueError("buffer.stride_bytes is smaller than one row of pixels")
        if self.buffer.size_bytes < self.buffer.stride_bytes * self.height:
            raise ValueError("buffer.size_bytes is smaller than stride_bytes * height")
        for region in self.dirty_regions:
            if not self.contains(region):
                raise ValueError("dirty region must be on this monitor and inside the frame")
        return self

    def contains(self, bbox: BoundingBox) -> bool:
        return bbox.monitor_id == self.monitor_id and bbox.fits_within(self.width, self.height)


class TextRegion(ContractModel):
    """Candidate text region detected in (or configured for) a frame.

    ``region_id`` identifies a region slot that persists across frames (e.g. ``dialogue_roi``);
    ``frame_id`` identifies the capture it was detected in.
    """

    region_id: Identifier
    frame_id: Identifier
    bbox: BoundingBox
    confidence: Confidence
    source: RegionSource
    content_type: ContentType = ContentType.UNKNOWN
    detected_at: UtcDatetime

    @property
    def monitor_id(self) -> str:
        return self.bbox.monitor_id


# --------------------------------------------------------------------------- #
# OCR layer (Master Prompt "OCRResult")
# --------------------------------------------------------------------------- #
class OCRObservation(ContractModel):
    """OCR output for one region of one frame. Natural key: ``(frame_id, region_id)``.

    ``subtitle_id`` and ``generation_id`` are assigned by the tracker *after* OCR, so they are
    both ``None`` on raw OCR output and both set once tracked. ``source_text`` is the normalized
    text; ``raw_text`` keeps the unnormalized text when it differs. ``EMPTY`` status reports a
    region with no recognized text (input to clear debouncing) and requires empty text.
    """

    frame_id: Identifier
    region_id: Identifier
    subtitle_id: Identifier | None = None
    generation_id: GenerationId | None = None
    source_text: Utf8Text
    raw_text: Utf8Text | None = None
    confidence: Confidence
    bbox: BoundingBox
    timestamp: UtcDatetime
    language: Literal["en"] = "en"
    recognition_status: RecognitionStatus
    preprocessing_profile: Identifier | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if (self.subtitle_id is None) != (self.generation_id is None):
            raise ValueError("subtitle_id and generation_id must be set together or not at all")
        if self.recognition_status is RecognitionStatus.EMPTY:
            if self.source_text != "":
                raise ValueError("EMPTY observations must have empty source_text")
            if self.raw_text is not None and self.raw_text.strip():
                raise ValueError("EMPTY observations must not carry recognized raw_text")
        elif not self.source_text.strip():
            raise ValueError("source_text must not be blank unless recognition_status is empty")
        return self

    @property
    def monitor_id(self) -> str:
        return self.bbox.monitor_id


# --------------------------------------------------------------------------- #
# Tracking layer
# --------------------------------------------------------------------------- #
class TrackedText(GenerationScopedContract):
    """Snapshot of one subtitle tracked across frames (owned by the tracker)."""

    region_id: Identifier
    text: MeaningfulText
    bbox: BoundingBox
    state: LifecycleState
    first_seen_at: UtcDatetime
    generation_started_at: UtcDatetime
    last_seen_at: UtcDatetime
    confidence: Confidence
    change_kind: ChangeKind
    similarity: Confidence | None = Field(
        default=None, description="Similarity to the previous generation's text; None if new."
    )
    observation_count: int = Field(ge=1, strict=True)
    last_frame_id: Identifier | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.state is LifecycleState.NO_TEXT:
            raise ValueError("a tracked subtitle cannot be in NO_TEXT")
        if not self.first_seen_at <= self.generation_started_at <= self.last_seen_at:
            raise ValueError("require first_seen_at <= generation_started_at <= last_seen_at")
        if self.change_kind is ChangeKind.NEW and (
            self.generation_id != 1 or self.similarity is not None
        ):
            raise ValueError("change_kind 'new' requires generation_id 1 and no similarity")
        if self.generation_id == 1 and self.change_kind not in (
            ChangeKind.NEW,
            ChangeKind.UNCHANGED,
        ):
            raise ValueError("generation 1 can only be 'new' or 'unchanged'")
        return self

    @property
    def monitor_id(self) -> str:
        return self.bbox.monitor_id


# Contract-level lifecycle: the M3 state machine must stay within these transitions.
# CLEARED is terminal for a subtitle_id; a reappearing subtitle gets a new subtitle_id.
ALLOWED_TRANSITIONS: Mapping[LifecycleState, frozenset[LifecycleState]] = MappingProxyType(
    {
        LifecycleState.NO_TEXT: frozenset({LifecycleState.TEXT_DETECTED}),
        LifecycleState.TEXT_DETECTED: frozenset(
            {LifecycleState.TEXT_STABILIZING, LifecycleState.CLEAR_PENDING, LifecycleState.ERROR}
        ),
        LifecycleState.TEXT_STABILIZING: frozenset(
            {
                LifecycleState.TRANSLATION_PENDING,
                LifecycleState.TEXT_CHANGED,
                LifecycleState.CLEAR_PENDING,
                LifecycleState.ERROR,
            }
        ),
        LifecycleState.TRANSLATION_PENDING: frozenset(
            {
                LifecycleState.TRANSLATING,
                LifecycleState.TEXT_CHANGED,
                LifecycleState.CLEAR_PENDING,
                LifecycleState.ERROR,
            }
        ),
        LifecycleState.TRANSLATING: frozenset(
            {
                LifecycleState.DISPLAYING,
                LifecycleState.TEXT_CHANGED,
                LifecycleState.CLEAR_PENDING,
                LifecycleState.ERROR,
            }
        ),
        LifecycleState.DISPLAYING: frozenset(
            {LifecycleState.TEXT_CHANGED, LifecycleState.CLEAR_PENDING, LifecycleState.ERROR}
        ),
        LifecycleState.TEXT_CHANGED: frozenset(
            {LifecycleState.TEXT_STABILIZING, LifecycleState.CLEAR_PENDING, LifecycleState.ERROR}
        ),
        LifecycleState.CLEAR_PENDING: frozenset(
            {
                LifecycleState.CLEARED,
                LifecycleState.DISPLAYING,
                LifecycleState.TEXT_CHANGED,
                LifecycleState.ERROR,
            }
        ),
        LifecycleState.CLEARED: frozenset(),
        LifecycleState.ERROR: frozenset(
            {LifecycleState.TEXT_CHANGED, LifecycleState.CLEAR_PENDING, LifecycleState.CLEARED}
        ),
    }
)


def is_valid_transition(previous: LifecycleState, current: LifecycleState) -> bool:
    return current in ALLOWED_TRANSITIONS[previous]


class LifecycleEvent(GenerationScopedContract):
    """One subtitle lifecycle transition (Master Prompt "DialogueEvent")."""

    previous_state: LifecycleState
    current_state: LifecycleState
    timestamp: UtcDatetime
    reason: LifecycleReason
    region_id: Identifier | None = None
    frame_id: Identifier | None = None
    previous_generation_id: GenerationId | None = Field(
        default=None, description="Set only on TEXT_CHANGED events; equals generation_id - 1."
    )
    error: ErrorInfo | None = None

    @model_validator(mode="after")
    def _valid_transition(self) -> Self:
        if self.previous_state is self.current_state:
            raise ValueError("an event must describe a state change")
        if not is_valid_transition(self.previous_state, self.current_state):
            raise ValueError(
                f"transition {self.previous_state} -> {self.current_state} is not allowed"
            )
        if self.previous_state is LifecycleState.NO_TEXT and self.generation_id != 1:
            raise ValueError("a new subtitle starts at generation_id 1")
        if (self.current_state is LifecycleState.ERROR) != (self.error is not None):
            raise ValueError("error is required if and only if current_state is ERROR")
        if self.current_state is LifecycleState.TEXT_CHANGED:
            if self.previous_generation_id != self.generation_id - 1:
                raise ValueError(
                    "TEXT_CHANGED requires previous_generation_id == generation_id - 1"
                )
        elif self.previous_generation_id is not None:
            raise ValueError("previous_generation_id is only valid on TEXT_CHANGED events")
        return self


# --------------------------------------------------------------------------- #
# Translation layer
# --------------------------------------------------------------------------- #
class SubtitleContext(ContractModel):
    """Context supplied with a translation request (bounded; no RAG machinery)."""

    game_id: Identifier
    speaker: Label = UNKNOWN_SPEAKER
    conversation_history: list[ConversationMessage] = Field(default_factory=list, max_length=32)
    glossary: dict[Term, Term] = Field(default_factory=dict, max_length=256)
    translation_style: TranslationStyle = TranslationStyle.CONTEXT_ADAPTIVE
    source_language: Literal["en"] = "en"
    target_language: Literal["vi"] = "vi"


class TranslationRequest(GenerationScopedContract):
    """Request to translate one subtitle generation (English to Vietnamese only)."""

    source_text: MeaningfulText
    context: SubtitleContext
    source_language: Literal["en"] = "en"
    target_language: Literal["vi"] = "vi"
    requested_at: UtcDatetime
    deadline_ms: int = Field(
        gt=0, le=600_000, strict=True, description="Budget measured from requested_at."
    )
    idempotency_key: Identifier

    @property
    def deadline_at(self) -> datetime:
        return self.requested_at + timedelta(milliseconds=self.deadline_ms)


class TranslationResult(GenerationScopedContract):
    """Outcome of a translation request.

    Status semantics (enforced):

    * ``completed``: ``translated_text`` is meaningful, ``engine`` is the engine that actually
      produced it, and neither ``error`` nor ``skip_reason`` is set.
    * ``failed``: ``error`` is set; no ``translated_text`` and no ``skip_reason``.
    * ``skipped``: translation was deliberately not performed and is not an error;
      ``skip_reason`` is set; no ``translated_text`` and no ``error``. A skipped result never
      changes lifecycle state by itself.
    """

    source_text: MeaningfulText
    translated_text: MeaningfulText | None = None
    engine: TranslationEngine | None = None
    model_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    status: TranslationStatus
    latency_ms: NonNegativeFloat = Field(description="Measured with a monotonic clock.")
    completed_at: UtcDatetime
    error: ErrorInfo | None = None
    skip_reason: SkipReason | None = None

    @model_validator(mode="after")
    def _status_invariants(self) -> Self:
        if self.status is TranslationStatus.COMPLETED:
            if self.translated_text is None:
                raise ValueError("completed results require translated_text")
            if self.engine is None:
                raise ValueError("completed results require the actual engine")
            if self.error is not None or self.skip_reason is not None:
                raise ValueError("completed results must not carry error or skip_reason")
        elif self.status is TranslationStatus.FAILED:
            if self.error is None:
                raise ValueError("failed results require structured error information")
            if self.translated_text is not None or self.skip_reason is not None:
                raise ValueError("failed results must not carry translated_text or skip_reason")
        else:
            if self.skip_reason is None:
                raise ValueError("skipped results require skip_reason")
            if self.translated_text is not None or self.error is not None:
                raise ValueError("skipped results must not carry translated_text or error")
        return self


# --------------------------------------------------------------------------- #
# Presentation layer (Master Prompt "OverlayMessage")
# --------------------------------------------------------------------------- #
class OverlayUpdate(GenerationScopedContract):
    """Show or replace the translation for one subtitle generation.

    The overlay must drop the message unless ``is_current(...)`` holds for its active
    subtitle/generation, and must remove it at ``expires_at`` even if no clear arrives.
    Clearing on disappearance is driven by ``LifecycleEvent`` (``CLEARED``).
    """

    source_text: MeaningfulText
    translated_text: MeaningfulText
    bbox: BoundingBox
    display_mode: OverlayDisplayMode
    created_at: UtcDatetime
    expires_at: UtcDatetime

    @model_validator(mode="after")
    def _expiry_after_creation(self) -> Self:
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        return self

    def is_expired(self, now: datetime) -> bool:
        return _require_utc(now) >= self.expires_at


# --------------------------------------------------------------------------- #
# Configuration and monitoring
# --------------------------------------------------------------------------- #
class OCRPreprocessingConfig(ContractValue):
    """Per-game OCR preprocessing (Adaptive Thresholding / CLAHE are approved techniques)."""

    profile: Identifier = "default"
    adaptive_threshold: bool = False
    clahe: bool = False
    invert: bool = False
    scale_factor: float = Field(default=1.0, gt=0.0, le=8.0, allow_inf_nan=False)
    min_confidence: Confidence = 0.5


class RoiConfig(ContractValue):
    """A configured region of interest, in monitor-relative pixels."""

    region_id: Identifier
    bbox: BoundingBox
    content_type: ContentType = ContentType.SUBTITLE
    enabled: bool = True


def _relative_path(value: str) -> str:
    _meaningful(value)
    if re.match(r"^([A-Za-z]:|[\\/])", value) or ".." in re.split(r"[\\/]", value):
        raise ValueError("path must be relative and must not contain '..'")
    return value


RelativePath = Annotated[str, Field(max_length=260), AfterValidator(_relative_path)]


class GameProfile(ContractModel):
    """Per-game configuration. Never contains secrets (extra fields are rejected)."""

    game_id: Identifier
    display_name: Label | None = None
    executable_name: ExecutableName | None = None
    monitor_id: Identifier | None = None
    display_mode: GameDisplayMode = GameDisplayMode.UNKNOWN
    reference_resolution: Resolution | None = None
    roi: list[RoiConfig] = Field(default_factory=list, max_length=32)
    ocr: OCRPreprocessingConfig = Field(default_factory=OCRPreprocessingConfig)
    translation_style: TranslationStyle = TranslationStyle.CONTEXT_ADAPTIVE
    overlay_display_mode: OverlayDisplayMode = OverlayDisplayMode.BILINGUAL
    glossary_path: RelativePath | None = None
    glossary: dict[Term, Term] = Field(default_factory=dict, max_length=1024)
    character_names: list[Term] = Field(default_factory=list, max_length=256)
    source_language: Literal["en"] = "en"
    target_language: Literal["vi"] = "vi"

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [roi.region_id for roi in self.roi]
        if len(ids) != len(set(ids)):
            raise ValueError("roi region_id values must be unique")
        if len(self.character_names) != len(set(self.character_names)):
            raise ValueError("character_names must be unique")
        for roi in self.roi:
            if self.monitor_id is not None and roi.bbox.monitor_id != self.monitor_id:
                raise ValueError(f"roi {roi.region_id!r} is not on the profile monitor")
            ref = self.reference_resolution
            if ref is not None and not roi.bbox.fits_within(ref.width, ref.height):
                raise ValueError(f"roi {roi.region_id!r} exceeds reference_resolution")
        return self


_METRIC_UNITS: Mapping[PerformanceMetricName, MetricUnit] = MappingProxyType(
    {
        PerformanceMetricName.CAPTURE_LATENCY: MetricUnit.MILLISECONDS,
        PerformanceMetricName.OCR_LATENCY: MetricUnit.MILLISECONDS,
        PerformanceMetricName.TRACKING_LATENCY: MetricUnit.MILLISECONDS,
        PerformanceMetricName.TRANSLATION_LATENCY: MetricUnit.MILLISECONDS,
        PerformanceMetricName.RENDER_LATENCY: MetricUnit.MILLISECONDS,
        PerformanceMetricName.END_TO_END_LATENCY: MetricUnit.MILLISECONDS,
        PerformanceMetricName.CPU_USAGE: MetricUnit.PERCENT,
        PerformanceMetricName.GPU_USAGE: MetricUnit.PERCENT,
        PerformanceMetricName.RAM_USAGE: MetricUnit.BYTES,
        PerformanceMetricName.VRAM_USAGE: MetricUnit.BYTES,
    }
)


class PerformanceMetric(ContractModel):
    """One measured performance value. Latencies come from a monotonic clock."""

    metric: PerformanceMetricName
    value: NonNegativeFloat
    unit: MetricUnit
    timestamp: UtcDatetime
    component: PipelineComponent
    subtitle_id: Identifier | None = None
    generation_id: GenerationId | None = None
    frame_id: Identifier | None = None
    region_id: Identifier | None = None
    engine: TranslationEngine | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        expected = _METRIC_UNITS[self.metric]
        if self.unit is not expected:
            raise ValueError(f"metric {self.metric} must use unit {expected}")
        if self.unit is MetricUnit.PERCENT and self.value > 100.0:
            raise ValueError("percent metrics must be within [0, 100]")
        if self.generation_id is not None and self.subtitle_id is None:
            raise ValueError("generation_id requires subtitle_id")
        return self


# Master Prompt names that map to canonical models (same class objects, not copies).
OCRResult = OCRObservation
DialogueEvent = LifecycleEvent
OverlayMessage = OverlayUpdate

# Every externally relevant contract; the JSON Schema exporter and tests iterate this.
PUBLIC_CONTRACTS: tuple[type[BaseModel], ...] = (
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
