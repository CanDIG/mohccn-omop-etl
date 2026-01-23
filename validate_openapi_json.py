import csv
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.request import urlopen

import yaml
from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry, Resource


def load_openapi_schema(schema_path: str) -> dict:
	if (schema_path.startswith("http://") or schema_path.startswith("https://")):
		from urllib.error import HTTPError, URLError
		try:
			with urlopen(schema_path) as handle:
				return yaml.safe_load(handle)
		except HTTPError as e:
			if e.code != 200:
				raise RuntimeError(f"Failed to fetch schema from URL '{schema_path}': HTTP {e.code} {e.reason}")
			else:
				raise
		except URLError as e:
			raise RuntimeError(f"Failed to fetch schema from URL '{schema_path}': {e.reason}")
	else:
		path = Path(schema_path) if isinstance(schema_path, str) else schema_path
		with path.open("r", encoding="utf-8") as handle:
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
            parts.append(f".{part}")
    return "$" + "".join(parts)


def validate_json(
    openapi_schema_path_or_url: str,
    omop_json_file_path: str,
	output_issues_csv_file_path: str,
    schema_name: str,
) -> tuple[list[dict], Counter]:
    try:
        openapi_doc = load_openapi_schema(openapi_schema_path_or_url)
    except Exception as e:
        print(f"ERROR: {e}")
        return [], Counter()

    openapi_doc = load_openapi_schema(openapi_schema_path_or_url)
    
    # Determine base URI: use URL directly if it's a URL, otherwise convert Path to URI
    if isinstance(openapi_schema_path_or_url, str) and (openapi_schema_path_or_url.startswith("http://") or openapi_schema_path_or_url.startswith("https://")):
        base_uri = openapi_schema_path_or_url
    else:
        path = Path(openapi_schema_path_or_url) if isinstance(openapi_schema_path_or_url, str) else openapi_schema_path_or_url
        base_uri = path.resolve().as_uri()
    
    validator = build_validator(
        openapi_doc,
        schema_name,
        base_uri,
    )

    data_path = Path(omop_json_file_path)
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

    if ( output_issues_csv_file_path != "" and len(errors) > 0 ):
        write_errors_to_csv(errors, output_issues_csv_file_path)

    return errors, error_type_counts


def write_errors_to_csv(errors: list[dict], csv_path: str):
	"""Write validation errors to a CSV file.
	
	Args:
		errors: List of error dictionaries with 'path', 'message', and 'validator' keys
		csv_path: Path where the CSV file should be written (default: "validation_errors.csv")
	
	Returns:
		Path object of the written CSV file
	"""
	path = Path(csv_path) if isinstance(csv_path, str) else csv_path
	with path.open("w", encoding="utf-8", newline="") as handle:
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

