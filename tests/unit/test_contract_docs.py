"""docs/DATA_CONTRACTS.md must match the implementation (no silent drift)."""

import json
import re
from enum import StrEnum
from pathlib import Path

import pytest

from ai_screen_translator.contracts import PUBLIC_CONTRACTS, models

DOC = (Path(__file__).resolve().parents[2] / "docs" / "DATA_CONTRACTS.md").read_text(
    encoding="utf-8"
)
EXAMPLE = re.compile(r"<!-- contract: (\w+) -->\n```json\n(.*?)\n```", re.S)
ENUMS = [
    obj
    for obj in vars(models).values()
    if isinstance(obj, type) and issubclass(obj, StrEnum) and obj is not StrEnum
]


def _examples():
    return [(name, json.loads(body)) for name, body in EXAMPLE.findall(DOC)]


@pytest.mark.parametrize("model", PUBLIC_CONTRACTS, ids=lambda m: m.__name__)
def test_every_public_contract_is_documented(model):
    assert f"`{model.__name__}`" in DOC


@pytest.mark.parametrize("enum", ENUMS, ids=lambda e: e.__name__)
def test_every_enum_value_is_documented(enum):
    row = next((line for line in DOC.splitlines() if line.startswith(f"| `{enum.__name__}`")), None)
    assert row is not None, f"{enum.__name__} missing from the vocabulary table"
    for member in enum:
        assert f"`{member.value}`" in row, f"{enum.__name__}.{member.value} not documented"


def test_aliases_are_documented_and_identical():
    for alias, canonical in (
        ("OCRResult", "OCRObservation"),
        ("DialogueEvent", "LifecycleEvent"),
        ("OverlayMessage", "OverlayUpdate"),
    ):
        assert getattr(models, alias) is getattr(models, canonical)
        assert alias in DOC and canonical in DOC


def test_documented_examples_cover_every_public_contract_and_validate():
    examples = _examples()
    assert {name for name, _ in examples} >= {m.__name__ for m in PUBLIC_CONTRACTS} - {
        "BoundingBox",
        "ErrorInfo",
    }
    for name, payload in examples:
        getattr(models, name).model_validate(payload)


def test_documented_schema_count_and_version_match_code():
    assert f"{len(PUBLIC_CONTRACTS)} files" in DOC
    assert f'`"{models.SCHEMA_VERSION}"`' in DOC
