"""
Tool Schema Registry — versioned JSON Schema repository for all public tools.

Each tool has a JSON Schema (Draft 2020-12) stored in schemas/*.json.
This module loads them, validates against the schema meta-schema on startup,
and provides Pydantic model generation for internal use.

§12.3: The MCP server advertises __tool_set_version__ so an LLM client can
detect a stale cached tool list after an engine upgrade.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from referencing import Registry, Resource

HERE = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = HERE / "schemas"

# Loaded registry (schema_id -> schema dict)
_registry: dict[str, dict[str, Any]] = {}
_ref_registry: Registry | None = None


def load_all() -> dict[str, dict[str, Any]]:
    """Load and validate all schemas from the schemas/ directory."""
    global _registry, _ref_registry
    if _registry:
        return _registry

    schemas: dict[str, dict[str, Any]] = {}
    resources: list[tuple[str, Resource]] = []

    for schema_path in sorted(SCHEMAS_DIR.glob("*.json")):
        with open(schema_path) as f:
            schema = json.load(f)

        # Validate the schema itself against the JSON Schema meta-schema
        jsonschema.Draft202012Validator.check_schema(schema)
        schema_id = schema.get("$id")
        if schema_id:
            resources.append((schema_id, Resource.from_contents(schema)))

        if schema_path.name.startswith("_"):
            continue

        tool_name = schema.get("title", schema_path.stem)
        schemas[tool_name] = schema

    _registry = schemas
    _ref_registry = Registry().with_resources(resources)
    return schemas


def get_schema(tool_name: str) -> dict[str, Any]:
    """Get a single tool's schema by tool name (e.g. 'create_element')."""
    if not _registry:
        load_all()
    schema = _registry.get(tool_name)
    if schema is None:
        raise KeyError(f"Unknown tool: {tool_name}")
    return schema


def get_input_schema(tool_name: str) -> dict[str, Any]:
    """Get the input schema (properties) for a tool, prepared for MCP tool registration."""
    schema = get_schema(tool_name)
    input_schema = {
        "type": "object",
        "properties": schema.get("properties", {}),
        "required": schema.get("required", []),
        "additionalProperties": schema.get("additionalProperties", False),
    }
    for key in ("$defs", "anyOf", "oneOf", "allOf"):
        if key in schema:
            input_schema[key] = schema[key]
    return input_schema


def validate_input(tool_name: str, input_data: dict[str, Any]) -> list[str]:
    """
    Validate tool call input against the schema registry.

    Returns a list of error messages (empty = valid).
    """
    schema = get_schema(tool_name)
    validator = jsonschema.Draft202012Validator(schema, registry=_ref_registry)
    errors = list(validator.iter_errors(input_data))
    return [f"{e.path}: {e.message}" if e.path else e.message for e in errors]


def list_tool_names() -> list[str]:
    """Return sorted list of registered tool names."""
    if not _registry:
        load_all()
    return sorted(_registry.keys())


def list_tool_schemas() -> list[dict[str, Any]]:
    """Return all tool schemas as a list (for MCP tool registration)."""
    if not _registry:
        load_all()
    result = []
    for name, schema in sorted(_registry.items()):
        result.append({
            "name": name,
            "description": schema.get("description", ""),
            "inputSchema": get_input_schema(name),
        })
    return result
