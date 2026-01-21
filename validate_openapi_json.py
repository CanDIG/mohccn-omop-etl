import csv
import json
import sys
from collections import Counter
from pathlib import Path

import yaml
from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry, Resource


def load_openapi_schema(schema_path: Path) -> dict:
    with schema_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_validator(
    openapi_doc: dict,
    component_schema_name: str,
    base_uri: str,
) -> Draft7Validator:
    try:
        openapi_doc["components"]["schemas"][component_schema_name]
    except KeyError as exc:
        raise KeyError(f"Missing components.schemas.{component_schema_name}") from exc

    registry = Registry().with_resource(base_uri, Resource.opaque(openapi_doc))
    schema_ref = {"$ref": f"{base_uri}#/components/schemas/{component_schema_name}"}
    return Draft7Validator(schema_ref, registry=registry, format_checker=FormatChecker())


def format_error_path(error) -> str:
    if not error.path:
        return "<root>"
    parts = []
    for part in error.path:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            if parts and not parts[-1].startswith("["):
                parts.append(f".{part}")
            else:
                parts.append(str(part))
    return "".join(parts)


def validate_json(
    openapi_path: Path,
    data_path: Path,
    schema_name: str,
) -> tuple[list[dict], list[str], Counter]:
    warnings: list[str] = []
    openapi_doc = load_openapi_schema(openapi_path)
    validator = build_validator(
        openapi_doc,
        schema_name,
        openapi_path.resolve().as_uri(),
    )

    with data_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    errors: list[dict] = []
    error_type_counts: Counter = Counter()
    for error in validator.iter_errors(data):
        path = format_error_path(error)
        errors.append(
            {
                "path": path,
                "message": error.message,
                "validator": error.validator,
            }
        )
        error_type_counts[error.validator] += 1
    return errors, warnings, error_type_counts


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "Usage: python validate_openapi_json.py <openapi.yml> <data.json> "
            "[schema_name]",
            file=sys.stderr,
        )
        return 2

    openapi_path = Path(sys.argv[1])
    data_path = Path(sys.argv[2])
    schema_name = sys.argv[3] if len(sys.argv) > 3 else "IngestOmopDatasets"

    errors, warnings, error_type_counts = validate_json(
        openapi_path, data_path, schema_name
    )
    if warnings:
        print(f"Warnings: {len(warnings)}")
        for i, message in enumerate(warnings, 1):
            print(f"{i}. {message}")
    if errors:
        print(f"Found {len(errors)} schema violations:")
        for i, error in enumerate(errors, 1):
            print(f"{i}. {error['path']}: {error['message']} ({error['validator']})")
        if error_type_counts:
            print("Violation types:")
            for error_type, count in error_type_counts.most_common():
                print(f"  {error_type}: {count}")
        csv_path = Path("validation_errors.csv")
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["index", "path", "message", "validator"])
            writer.writeheader()
            for i, error in enumerate(errors, 1):
                writer.writerow(
                    {
                        "index": i,
                        "path": error["path"],
                        "message": error["message"],
                        "validator": error["validator"],
                    }
                )
        print(f"Wrote violations to {csv_path}")
        return 1

    print("No schema violations found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
