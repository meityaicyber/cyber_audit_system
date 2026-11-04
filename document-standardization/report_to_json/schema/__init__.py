"""
Master schema: ``master_schema.json`` is the single source of truth for the output.

Every output JSON has exactly the template's structure: every key present, no
other keys, every value of the declared type or null. ``enforce`` produces that
shape and reports anything it could not keep, so the pipeline can record the
original values outside the output instead of losing them.

Template leaf notation:
  "string" / "number" / "boolean"   -> that type, or null
  "YYYY-MM-DD"                      -> ISO date string, or null
  "A | B | C"                       -> one of the listed values, or null
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from functools import lru_cache
from typing import Any, Dict, List, Tuple

import jsonschema

from ..config import SCHEMA_TEMPLATE_PATH

_ISO_DATE = r"^\d{4}-\d{2}-\d{2}$"


@lru_cache(maxsize=None)
def template() -> Dict[str, Any]:
    with open(SCHEMA_TEMPLATE_PATH, encoding="utf-8-sig") as f:
        return json.load(f)


def _leaf_schema(spec: str) -> Dict[str, Any]:
    if spec == "string":
        return {"type": ["string", "null"]}
    if spec == "number":
        return {"type": ["number", "null"]}
    if spec == "boolean":
        return {"type": ["boolean", "null"]}
    if spec == "YYYY-MM-DD":
        return {"anyOf": [{"type": "string", "pattern": _ISO_DATE}, {"type": "null"}]}
    if "|" in spec:
        return {"enum": [v.strip() for v in spec.split("|")] + [None]}
    return {}


def _to_schema(node: Any, strict: bool = False) -> Dict[str, Any]:
    if isinstance(node, dict):
        out = {
            "type": "object",
            "properties": {k: _to_schema(v, strict) for k, v in node.items()},
            "required": list(node),
        }
        if strict:
            out["additionalProperties"] = False
        return out
    if isinstance(node, list):
        return {"type": "array", "items": _to_schema(node[0], strict) if node else {}}
    return _leaf_schema(node)


def section_schema(keys: List[str]) -> Dict[str, Any]:
    """Strict JSON Schema for an object holding the given top-level template sections.

    Used for constrained decoding in pass 2 (no keys beyond the template).
    """
    return _to_schema({k: template()[k] for k in keys}, strict=True)


def item_schema(key: str) -> Dict[str, Any]:
    """Strict JSON Schema for one element of a top-level list section (e.g. a finding)."""
    return _to_schema(template()[key][0], strict=True)


@lru_cache(maxsize=None)
def json_schema() -> Dict[str, Any]:
    """JSON Schema of the output: the template's keys only, at every level."""
    schema = _to_schema(template(), strict=True)
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return schema


# --------------------------------------------------------------------------- enforcement

def _coerce(value: Any, spec: str) -> Tuple[bool, Any]:
    """(ok, value) for a leaf. Only lossless normalisation; anything else is not ok."""
    if spec == "string":
        if isinstance(value, str):
            return True, value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return True, str(value)
        return False, None
    if spec == "number":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return True, value
        if isinstance(value, str) and re.fullmatch(r"\s*-?\d+(\.\d+)?\s*", value):
            number = float(value)
            return True, int(number) if number.is_integer() and "." not in value else number
        return False, None
    if spec == "boolean":
        if isinstance(value, bool):
            return True, value
        if isinstance(value, str) and value.strip().lower() in ("true", "false"):
            return True, value.strip().lower() == "true"
        return False, None
    if spec == "YYYY-MM-DD":
        if not isinstance(value, str):
            return False, None
        if re.fullmatch(_ISO_DATE, value.strip()):
            try:
                _dt.date.fromisoformat(value.strip())
                return True, value.strip()
            except ValueError:
                return False, None
        from ..textparse import DATE_RE, parse_date

        # Only a value that is entirely one full date is rewritten to ISO; text around it would be lost.
        if DATE_RE.fullmatch(value.strip()):
            iso = parse_date(value)
            if iso:
                return True, iso
        return False, None
    if "|" in spec:
        options = [o.strip() for o in spec.split("|")]
        if isinstance(value, str):
            for option in options:
                if value.strip().lower() == option.lower():
                    return True, option
        return False, None
    return True, value


def enforce(data: Any) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Shape ``data`` exactly like the template.

    Returns (output, dropped) where ``dropped`` lists every value that could not be
    kept as ``{"path", "value", "reason"}``: keys the schema does not define, and
    values that are not of the declared type (e.g. a severity the schema's list does
    not include). Such values become null in the output; nothing is guessed.
    """
    dropped: List[Dict[str, Any]] = []

    def note(path: str, value: Any, reason: str) -> None:
        dropped.append({"path": path, "value": value, "reason": reason})

    def walk(value: Any, node: Any, path: str) -> Any:
        if isinstance(node, dict):
            if value is not None and not isinstance(value, dict):
                note(path, value, "expected an object")
                value = None
            value = value or {}
            for key in value:
                if key not in node:
                    note(f"{path}.{key}".lstrip("."), value[key], "not defined in the master schema")
            return {key: walk(value.get(key), sub, f"{path}.{key}".lstrip(".")) for key, sub in node.items()}
        if isinstance(node, list):
            if value is None:
                return []
            if not isinstance(value, list):
                note(path, value, "expected a list")
                return []
            items = [walk(item, node[0], f"{path}[{i}]") for i, item in enumerate(value)]
            return [item for item in items if item is not None] if not isinstance(node[0], dict) else items
        if value is None:
            return None
        ok, coerced = _coerce(value, node)
        if not ok:
            note(path, value, f"not a valid {node!r}")
            return None
        return coerced

    return walk(data, template(), ""), dropped


def validate(data: Dict[str, Any], limit: int = 50) -> List[str]:
    """Schema violations as ``"path: message"`` strings (empty list when valid)."""
    validator = jsonschema.Draft202012Validator(json_schema())
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    out = []
    for err in errors[:limit]:
        path = "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in err.absolute_path).lstrip(".")
        out.append(f"{path or '<root>'}: {err.message[:200]}")
    return out


def _empty_like(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _empty_like(v) for k, v in node.items()}
    if isinstance(node, list):
        return []
    return None


def conform(data: Any, node: Any = None) -> Any:
    """Add any keys the template defines but ``data`` lacks (as null / [] / {...}).

    Extra keys are kept; values are never changed.
    """
    node = template() if node is None else node
    if isinstance(node, dict):
        if not isinstance(data, dict):
            return _empty_like(node) if data is None else data
        out = dict(data)
        for key, sub in node.items():
            out[key] = conform(out.get(key), sub) if key in out else _empty_like(sub)
        return out
    if isinstance(node, list) and node:
        if isinstance(data, list):
            return [conform(item, node[0]) for item in data]
        return [] if data is None else data
    return data


def missing_fields(data: Dict[str, Any]) -> List[str]:
    """Template paths with no value in ``data``; list items are aggregated per field."""
    out: List[str] = []

    def walk(value: Any, node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, sub in node.items():
                walk(value.get(key) if isinstance(value, dict) else None, sub, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            if not value:
                out.append(f"{path} (empty)")
            elif node and isinstance(node[0], dict):
                for key in node[0]:
                    empty = sum(1 for item in value if isinstance(item, dict) and item.get(key) in (None, "", []))
                    if empty:
                        out.append(f"{path}[*].{key} ({empty}/{len(value)} missing)")
        elif value in (None, ""):
            out.append(path)

    walk(data, template(), "")
    return out


def prompt_template() -> str:
    """The template as pretty JSON, for LLM prompts."""
    return json.dumps(template(), indent=2)


def validate_against(data: Any, json_schema_: Dict[str, Any], limit: int = 20) -> List[str]:
    validator = jsonschema.Draft202012Validator(json_schema_)
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:200]}"
            for e in list(validator.iter_errors(data))[:limit]]


__all__ = ["template", "json_schema", "section_schema", "item_schema", "validate", "validate_against",
           "conform", "enforce", "missing_fields", "prompt_template"]
