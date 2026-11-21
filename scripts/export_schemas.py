"""Export or verify JSON Schema files generated from the Pydantic contract models.

    python scripts/export_schemas.py           # (re)generate schemas/*.schema.json
    python scripts/export_schemas.py --check   # exit 1 if committed schemas are stale

The directory is resolved relative to the repository root, not the current directory.
"""

import argparse
import sys
from pathlib import Path

from ai_screen_translator.contracts.schema_export import check_schemas, write_schemas

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "schemas"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify instead of writing")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="schema directory")
    args = parser.parse_args(argv)

    if args.check:
        problems = check_schemas(args.dir)
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            print("Schemas are out of date. Run: python scripts/export_schemas.py", file=sys.stderr)
            return 1
        print(f"Schemas in {args.dir} are up to date.")
        return 0

    written, removed = write_schemas(args.dir)
    print(f"Exported {len(written)} JSON Schemas to {args.dir}")
    for name in removed:
        print(f"Removed stale schema: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
