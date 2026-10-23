"""Write, or check, the v1 API's generated contract artifacts from `webapp/api/contract.py`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import BaseModel, TypeAdapter  # noqa: E402

from webapp.api import contract  # noqa: E402

SCHEMA_PATH = ROOT / "docs" / "api" / "v1.schema.json"
DOC_PATH = ROOT / "docs" / "api" / "v1.md"
BEGIN_MARKER = "<!-- BEGIN GENERATED: tools/api_contract.py -->"
END_MARKER = "<!-- END GENERATED: tools/api_contract.py -->"

REFERENCE_MODELS: tuple[type[BaseModel], ...] = (
    contract.ProcessingPackage, contract.DocumentProgress, contract.ReadyPackage, contract.Review,
    contract.PackageFigures, contract.Funder, contract.PotentialLender, contract.MonthPositions,
    contract.AnalysedDocument, contract.IncludedAccount, contract.ExcludedAccount, contract.FailedDocument,
    contract.Failure, contract.DuplicateDocument, contract.ErrorResponse, contract.ApiError,
)


def schema_document() -> dict:
    roots, top = TypeAdapter.json_schemas(
        [("Package", "serialization", TypeAdapter(contract.Package)),
         ("ErrorResponse", "serialization", TypeAdapter(contract.ErrorResponse))],
    )
    definitions = dict(top["$defs"])
    definitions["Package"] = roots[("Package", "serialization")]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "bank-statement-analysis API v1",
        "x-api-version": contract.API_VERSION,
        "anyOf": [{"$ref": "#/$defs/Package"}, {"$ref": "#/$defs/ErrorResponse"}],
        "$defs": dict(sorted(definitions.items())),
    }


def schema_text() -> str:
    return json.dumps(schema_document(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _type_text(schema: dict) -> str:
    if "$ref" in schema:
        return f"`{schema['$ref'].rsplit('/', 1)[-1]}`"
    if "const" in schema:
        return f'`"{schema["const"]}"`'
    if "enum" in schema:
        return "one of " + ", ".join(f"`{value}`" for value in schema["enum"])
    for union in ("anyOf", "oneOf"):
        if union in schema:
            return " or ".join(_type_text(member) for member in schema[union])
    kind = schema.get("type")
    if kind == "array":
        return f"array of {_type_text(schema['items'])}"
    if kind == "null":
        return "null"
    text = f"{kind} ({schema['format']})" if "format" in schema else str(kind)
    if "minimum" in schema:
        text += f" ≥ {schema['minimum']}"
    if "pattern" in schema:
        text += f" `{schema['pattern']}`"
    return text


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def reference_text() -> str:
    definitions = schema_document()["$defs"]
    lines = [BEGIN_MARKER, "", "Generated from `webapp/api/contract.py` by `python -m tools.api_contract --write`; "
             "never edit it by hand.", ""]
    for model in REFERENCE_MODELS:
        schema = definitions[model.__name__]
        lines += [f"### `{model.__name__}`", ""]
        if "description" in schema:
            lines += [" ".join(schema["description"].split()), ""]
        lines += ["| Field | Type | Meaning | Source |", "|---|---|---|---|"]
        for name, prop in schema["properties"].items():
            source = f"`{prop['x-source']}`" if "x-source" in prop else ""
            lines.append(f"| `{name}` | {_cell(_type_text(prop))} | {_cell(prop.get('description', ''))} | "
                         f"{_cell(source)} |")
        lines.append("")
    lines += ["### Error codes", "", "| Code | HTTP status | Message |", "|---|---|---|"]
    lines += [f"| `{code}` | {entry.status} | {_cell(entry.message)} |" for code, entry in contract.ERRORS.items()]
    lines += ["", "### Document failure codes", "", "| Code | Message |", "|---|---|"]
    lines += [f"| `{code}` | {_cell(message)} |" for code, message in contract.FAILURE_MESSAGES.items()]
    lines += ["", END_MARKER]
    return "\n".join(lines)


def with_reference(document: str) -> str:
    start = document.index(BEGIN_MARKER)
    end = document.index(END_MARKER, start) + len(END_MARKER)
    return document[:start] + reference_text() + document[end:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="exit 1 when an artifact is stale; write nothing")
    mode.add_argument("--write", action="store_true", help="write both artifacts")
    args = parser.parse_args(argv)
    document = DOC_PATH.read_text(encoding="utf-8")
    expected = {SCHEMA_PATH: schema_text(), DOC_PATH: with_reference(document)}
    if args.write:
        for path, text in expected.items():
            path.write_text(text, encoding="utf-8")
        return 0
    stale = [path for path, text in expected.items()
             if not path.is_file() or path.read_text(encoding="utf-8") != text]
    for path in stale:
        print(f"stale: {path.relative_to(ROOT)}; run python -m tools.api_contract --write", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
