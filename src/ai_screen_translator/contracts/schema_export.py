"""Generate and verify JSON Schema artifacts from the canonical Pydantic contracts.

Schemas are derived only from :data:`PUBLIC_CONTRACTS`; there is no second, hand-written
definition. Output is deterministic: sorted keys, 2-space indent, UTF-8, LF line endings.
"""

import json
from pathlib import Path

from pydantic import BaseModel

from ai_screen_translator.contracts.models import PUBLIC_CONTRACTS

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_SUFFIX = ".schema.json"


def schema_filename(model: type[BaseModel]) -> str:
    return f"{model.__name__.lower()}{SCHEMA_SUFFIX}"


def render_schema(model: type[BaseModel]) -> str:
    schema = {"$schema": SCHEMA_DIALECT, **model.model_json_schema()}
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def generate_schemas() -> dict[str, str]:
    """Return ``{filename: json_text}`` for every public contract."""
    return {schema_filename(model): render_schema(model) for model in PUBLIC_CONTRACTS}


def write_schemas(directory: Path) -> tuple[list[str], list[str]]:
    """Write all schemas and delete generated files that no longer correspond to a contract.

    Returns ``(written, removed)`` filenames.
    """
    directory.mkdir(parents=True, exist_ok=True)
    expected = generate_schemas()
    for name, text in expected.items():
        with open(directory / name, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    removed = sorted(
        path.name for path in directory.glob(f"*{SCHEMA_SUFFIX}") if path.name not in expected
    )
    for name in removed:
        (directory / name).unlink()
    return sorted(expected), removed


def check_schemas(directory: Path) -> list[str]:
    """Return human-readable problems; an empty list means committed schemas are current."""
    problems: list[str] = []
    expected = generate_schemas()
    for name, text in expected.items():
        path = directory / name
        if not path.is_file():
            problems.append(f"missing: {name}")
        elif path.read_bytes().decode("utf-8").replace("\r\n", "\n") != text:
            problems.append(f"stale: {name}")
    if directory.is_dir():
        problems.extend(
            f"unexpected: {path.name}"
            for path in sorted(directory.glob(f"*{SCHEMA_SUFFIX}"))
            if path.name not in expected
        )
    else:
        problems.append(f"missing directory: {directory}")
    return problems
