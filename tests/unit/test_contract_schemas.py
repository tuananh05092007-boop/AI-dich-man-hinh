"""JSON Schema export, staleness detection and schema/model consistency."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from contract_samples import (
    error_event,
    failed_result,
    sample,
    sample_models,
    skipped_result,
)
from jsonschema import Draft202012Validator, FormatChecker

from ai_screen_translator.contracts import PUBLIC_CONTRACTS
from ai_screen_translator.contracts.schema_export import (
    SCHEMA_DIALECT,
    check_schemas,
    generate_schemas,
    schema_filename,
    write_schemas,
)

REPO = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO / "schemas"


def validator(model):
    schema = json.loads(generate_schemas()[schema_filename(model)])
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_every_public_contract_has_a_sample():
    assert set(sample_models()) == set(PUBLIC_CONTRACTS)


def test_one_schema_per_public_contract_with_stable_names():
    schemas = generate_schemas()
    assert sorted(schemas) == sorted(f"{m.__name__.lower()}.schema.json" for m in PUBLIC_CONTRACTS)
    assert len(schemas) == len(PUBLIC_CONTRACTS) == 13


def test_generation_is_deterministic():
    assert generate_schemas() == generate_schemas()


def test_schemas_are_valid_json_schema_utf8_and_end_with_lf():
    for name, text in generate_schemas().items():
        assert text.endswith("}\n") and "\r" not in text
        schema = json.loads(text)
        assert schema["$schema"] == SCHEMA_DIALECT, name
        Draft202012Validator.check_schema(schema)
        assert text.encode("utf-8").decode("utf-8") == text


def test_nested_models_and_enums_are_included_in_defs():
    request = json.loads(generate_schemas()["translationrequest.schema.json"])
    assert {"SubtitleContext", "ConversationMessage", "TranslationStyle"} <= set(request["$defs"])
    result = json.loads(generate_schemas()["translationresult.schema.json"])
    assert {
        "ErrorInfo",
        "ErrorCode",
        "SkipReason",
        "TranslationEngine",
        "TranslationStatus",
    } <= set(result["$defs"])
    frame = json.loads(generate_schemas()["capturedframe.schema.json"])
    assert {"BoundingBox", "FrameBufferRef", "PixelFormat"} <= set(frame["$defs"])


@pytest.mark.parametrize("model", PUBLIC_CONTRACTS, ids=lambda m: m.__name__)
def test_schema_forbids_unknown_fields(model):
    schema = json.loads(generate_schemas()[schema_filename(model)])
    assert schema["additionalProperties"] is False
    for definition in schema.get("$defs", {}).values():
        if definition.get("type") == "object":
            assert definition["additionalProperties"] is False


@pytest.mark.parametrize("model", PUBLIC_CONTRACTS, ids=lambda m: m.__name__)
def test_model_output_validates_against_its_schema(model):
    payload = model.model_validate(sample(model)).model_dump(mode="json")
    validator(model).validate(payload)


@pytest.mark.parametrize("model", PUBLIC_CONTRACTS, ids=lambda m: m.__name__)
def test_schema_rejects_what_the_model_rejects_for_unknown_fields(model):
    errors = list(validator(model).iter_errors({**sample(model), "unreviewed_field": 1}))
    assert errors


def test_status_dependent_payloads_validate_against_schema():
    from ai_screen_translator.contracts import LifecycleEvent, TranslationResult

    for payload in (failed_result(), skipped_result()):
        validator(TranslationResult).validate(
            TranslationResult.model_validate(payload).model_dump(mode="json")
        )
    validator(LifecycleEvent).validate(
        LifecycleEvent.model_validate(error_event()).model_dump(mode="json")
    )


def test_v02_schema_shape_for_c1_c3():
    schemas = {name: json.loads(text) for name, text in generate_schemas().items()}
    request = schemas["translationrequest.schema.json"]
    assert request["properties"]["trigger"]["$ref"] == "#/$defs/Trigger"
    assert set(request["$defs"]["Trigger"]["enum"]) == {"auto", "hotkey"}
    assert "trigger" not in request["required"] and "batch_id" in request["properties"]
    overlay = schemas["overlayupdate.schema.json"]
    assert (
        "display_mode" not in overlay["properties"] and "OverlayDisplayMode" not in overlay["$defs"]
    )
    assert "batch_id" in overlay["properties"] and "batch_id" not in overlay["required"]
    profile = schemas["gameprofile.schema.json"]
    assert "overlay_display_mode" not in profile["properties"]
    assert "OverlayDisplayMode" not in profile["$defs"]
    style = profile["$defs"]["OverlayStyle"]
    assert style["additionalProperties"] is False
    assert set(profile["$defs"]["OverlayPlacement"]["enum"]) == {"below", "above"}
    assert style["properties"]["opacity"]["minimum"] == 0.1


def test_schema_rejects_legacy_v01_fields():
    from ai_screen_translator.contracts import GameProfile, OverlayUpdate

    overlay = OverlayUpdate.model_validate(sample(OverlayUpdate)).model_dump(mode="json")
    assert list(validator(OverlayUpdate).iter_errors({**overlay, "display_mode": "bilingual"}))
    profile = GameProfile.model_validate(sample(GameProfile)).model_dump(mode="json")
    assert list(validator(GameProfile).iter_errors({**profile, "overlay_display_mode": "x"}))
    assert list(validator(GameProfile).iter_errors({**profile, "schema_version": "0.1"}))


def test_schema_requires_monitor_id_and_pins_schema_version():
    bbox = json.loads(generate_schemas()["boundingbox.schema.json"])
    assert "monitor_id" in bbox["required"]
    assert bbox["properties"]["x1"]["minimum"] == 0
    ocr = json.loads(generate_schemas()["ocrobservation.schema.json"])
    assert ocr["properties"]["schema_version"]["const"] == "0.2"
    assert ocr["properties"]["confidence"]["minimum"] == 0
    assert ocr["properties"]["confidence"]["maximum"] == 1


def test_schema_rejects_naive_and_non_utc_timestamps():
    from ai_screen_translator.contracts import TextRegion

    check = validator(TextRegion)
    payload = TextRegion.model_validate(sample(TextRegion)).model_dump(mode="json")
    check.validate(payload)
    for bad in ("2026-11-20T10:00:00", "2026-11-20T10:00:00+07:00"):
        assert list(check.iter_errors({**payload, "detected_at": bad})), bad


def test_committed_schemas_match_pydantic_models():
    assert check_schemas(SCHEMA_DIR) == []


def test_stale_missing_and_extra_schemas_are_detected(tmp_path):
    write_schemas(tmp_path)
    assert check_schemas(tmp_path) == []

    (tmp_path / "boundingbox.schema.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "errorinfo.schema.json").unlink()
    (tmp_path / "legacy.schema.json").write_text("{}\n", encoding="utf-8")
    problems = check_schemas(tmp_path)
    assert "stale: boundingbox.schema.json" in problems
    assert "missing: errorinfo.schema.json" in problems
    assert "unexpected: legacy.schema.json" in problems


def test_write_schemas_removes_orphans_and_is_idempotent(tmp_path):
    (tmp_path / "old.schema.json").write_text("{}\n", encoding="utf-8")
    written, removed = write_schemas(tmp_path)
    assert removed == ["old.schema.json"] and len(written) == 13
    assert write_schemas(tmp_path)[1] == []
    assert check_schemas(tmp_path) == []


def test_crlf_checkout_is_not_reported_as_stale(tmp_path):
    write_schemas(tmp_path)
    path = tmp_path / "textregion.schema.json"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert check_schemas(tmp_path) == []


def test_export_script_check_mode_passes_and_fails_correctly(tmp_path):
    script = REPO / "scripts" / "export_schemas.py"
    env = {**os.environ, "PYTHONPATH": str(REPO / "src")}  # works without `pip install -e .`
    ok = subprocess.run(
        [sys.executable, str(script), "--check"], capture_output=True, text=True, env=env
    )
    assert ok.returncode == 0, ok.stderr

    subprocess.run(
        [sys.executable, str(script), "--dir", str(tmp_path)],
        check=True,
        capture_output=True,
        env=env,
    )
    (tmp_path / "overlayupdate.schema.json").write_text("{}\n", encoding="utf-8")
    bad = subprocess.run(
        [sys.executable, str(script), "--check", "--dir", str(tmp_path)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert bad.returncode == 1 and "stale: overlayupdate.schema.json" in bad.stderr
