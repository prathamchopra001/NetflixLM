"""Deterministic, schema-valid stub outputs (NIP_PROFILE=cpu backends)."""

from typing import Any

from pydantic import BaseModel

_FORMATS = {"date-time": "1970-01-01T00:00:00Z", "date": "1970-01-01", "uri": "http://stub"}


def _value(s: dict[str, Any], defs: dict[str, Any]) -> Any:
    if "$ref" in s:
        return _value(defs[s["$ref"].rsplit("/", 1)[-1]], defs)
    for k in ("const", "default"):
        if k in s:
            return s[k]
    if "enum" in s:
        return s["enum"][0]
    for k in ("anyOf", "oneOf", "allOf"):
        if k in s:
            opts = s[k]
            return _value(next((o for o in opts if o.get("type") != "null"), opts[0]), defs)
    t = s.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), "null")
    if t == "object":
        props = s.get("properties", {})
        return {k: _value(props[k], defs) for k in s.get("required", [])}
    if t == "array":
        if "prefixItems" in s:
            return [_value(p, defs) for p in s["prefixItems"]]
        return [_value(s.get("items", {}), defs) for _ in range(s.get("minItems", 0))]
    if t == "string":
        return _FORMATS.get(s.get("format", ""), "stub".ljust(s.get("minLength", 0), "_"))
    if t in ("integer", "number"):
        lo = s.get("minimum", s["exclusiveMinimum"] + 1 if "exclusiveMinimum" in s else 0)
        return int(lo) if t == "integer" else float(lo)
    if t == "boolean":
        return False
    return None


def stub_instance[M: BaseModel](schema: type[M]) -> M:
    """The same minimal valid instance of `schema` every time: required fields only, first enum
    member, lower bounds, minItems elements. Covers constraints JSON Schema can express; custom
    validators (e.g. a non-empty frame range) need a schema-level bound or a hand-made stub."""
    js = schema.model_json_schema()
    return schema.model_validate(_value(js, js.get("$defs", {})))
