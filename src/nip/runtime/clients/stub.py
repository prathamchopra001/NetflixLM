"""Stub outputs for NIP_PROFILE=cpu backends (D-020): recorded real responses, replayed by key,
else a deterministic schema-valid minimal instance.

Recordings live in `tests/fixtures/llm/{key}.json`, key = sha256(variant, system, prompt, JSON
schema) of the real call. `LLMClient` writes them when NIP_LLM_RECORD_DIR is set; `StubLLM` replays
the ones recorded for REPLAY_VARIANT (the laptop's text model). Images are not part of the key
(no VLM recordings yet).
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

FIXTURES = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "llm"
REPLAY_VARIANT = "qwen3.5-4b-awq"
_FORMATS = {"date-time": "1970-01-01T00:00:00Z", "date": "1970-01-01", "uri": "http://stub"}


def record_key(variant: str, prompt: str, schema: type[BaseModel], system: str | None) -> str:
    blob = json.dumps(
        [variant, system, prompt, schema.model_json_schema()], sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def recorded(key: str, root: Path | None = None) -> str | None:
    """The recorded response text (the model's JSON) for `key` (in FIXTURES), or None."""
    p = (root or FIXTURES) / f"{key}.json"
    return json.loads(p.read_text(encoding="utf-8"))["response"] if p.is_file() else None


def record(key: str, variant: str, schema: str, response: str, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    body = {"variant": variant, "schema": schema, "response": response}
    (root / f"{key}.json").write_text(
        json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
    )


def _number(s: dict[str, Any], integer: bool) -> float:
    lo = s.get("minimum")
    hi = s.get("maximum", s.get("exclusiveMaximum"))
    if "exclusiveMinimum" in s:
        x = s["exclusiveMinimum"]
        lo = x + 1 if integer or hi is None else (x + hi) / 2
    if lo is None:  # no lower bound: 0, unless the upper bound is at or below 0
        lo = 0 if hi is None or hi > 0 else hi - ("exclusiveMaximum" in s)
    return float(lo)


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
        text = "stub"[: s.get("maxLength", 4)].ljust(s.get("minLength", 0), "_")
        return _FORMATS.get(s.get("format", ""), text)
    if t in ("integer", "number"):
        n = _number(s, t == "integer")
        return int(n) if t == "integer" else float(n)
    if t == "boolean":
        return False
    return None


def stub_instance[M: BaseModel](schema: type[M]) -> M:
    """The same minimal valid instance of `schema` every time: required fields only, first enum
    member, the lowest value within numeric bounds (the midpoint for an exclusive float minimum),
    min/maxLength strings, minItems elements. Not covered: `pattern`, `uniqueItems` and custom
    validators (e.g. a non-empty frame range): those need a recording or a hand-made stub."""
    js = schema.model_json_schema()
    return schema.model_validate(_value(js, js.get("$defs", {})))
