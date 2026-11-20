"""Export Pydantic contract models as JSON Schema files.

Run after installing the project: python scripts/export_schemas.py
"""
import json
from pathlib import Path

from ai_screen_translator.contracts import models

OUTPUT = Path("schemas")
OUTPUT.mkdir(exist_ok=True)

MODEL_NAMES = (
    "BoundingBox",
    "OCRObservation",
    "SubtitleContext",
    "TranslationRequest",
    "TranslationResult",
    "OverlayUpdate",
    "LifecycleEvent",
)

for name in MODEL_NAMES:
    model = getattr(models, name)
    schema = model.model_json_schema()
    (OUTPUT / f"{name.lower()}.schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\\n",
        encoding="utf-8",
    )
print(f"Exported {len(MODEL_NAMES)} JSON Schemas to {OUTPUT}/")
