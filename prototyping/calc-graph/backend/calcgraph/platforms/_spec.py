"""Build platform raw objects THROUGH the generated, spec-derived models.

`shaped(name, raw)`:
1. checks `raw` against the extracted OpenAPI schema `name` (procore_subset.openapi.json):
   every key must be a spec property (no invented fields), every value must have the spec's
   JSON type, enum values must be in the spec's enum, `format: date` / `date-time` must parse;
2. loads it into the generated attrs model (generated/procore_rest/models) and returns
   `model.to_dict()`, so the emitted object is exactly what the typed model serialises.
A mismatch raises SpecMismatch at build time: drift fails loudly instead of shipping a guessed field.

Procore custom fields are keyed `custom_field_<definition id>` in real responses; the spec templates
that key as `custom_field_%{..._definition_id}`, so keys of that form are checked against the template
for their data type.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from functools import lru_cache

HERE = os.path.dirname(__file__)
SUBSETS = {"procore": os.path.join(HERE, "generated", "procore_subset.openapi.json")}


class SpecMismatch(ValueError):
    pass


@lru_cache(maxsize=None)
def _schemas(platform: str) -> dict:
    with open(SUBSETS[platform]) as fh:
        return json.load(fh)["components"]["schemas"]


def _model(platform: str, name: str):
    if platform == "procore":
        from .generated.procore_rest import models
        return getattr(models, name)
    raise KeyError(platform)


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CF_TEMPLATE = {"boolean": "custom_field_%{custom_field_boolean_definition_id}",
                "decimal": "custom_field_%{custom_field_decimal_definition_id}",
                "lov_entries": "custom_field_%{custom_field_lov_entries_definition_id}",
                "lov_entry": "custom_field_%{custom_field_lov_entry_definition_id}",
                "string": "custom_field_%{custom_field_string_definition_id}"}


def check(value, schema: dict, path: str) -> None:
    if value is None:
        if schema.get("nullable"):
            return
        raise SpecMismatch(f"{path}: null but the spec field is not nullable")
    t = schema.get("type") or ("object" if "properties" in schema else None)
    if "enum" in schema and value not in schema["enum"]:
        raise SpecMismatch(f"{path}: {value!r} not in spec enum {schema['enum']}")
    if t == "integer":
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif t == "number":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif t == "boolean":
        ok = isinstance(value, bool)
    elif t == "string":
        ok = isinstance(value, str)
        if ok and schema.get("format") == "date" and not _DATE.match(value):
            raise SpecMismatch(f"{path}: {value!r} is not format date")
        if ok and schema.get("format") == "date-time":
            try:
                dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as e:
                raise SpecMismatch(f"{path}: {value!r} is not format date-time") from e
    elif t == "array":
        ok = isinstance(value, list)
        if ok:
            for i, v in enumerate(value):
                check(v, schema.get("items") or {}, f"{path}[{i}]")
    elif t == "object":
        ok = isinstance(value, dict)
        if ok:
            props = schema.get("properties", {})
            for k, v in value.items():
                if k in props:
                    check(v, props[k], f"{path}.{k}")
                elif k.startswith("custom_field_") and _CF_TEMPLATE["string"] in props:
                    kind = (v or {}).get("data_type") if isinstance(v, dict) else None
                    tpl = props.get(_CF_TEMPLATE.get(kind, ""))
                    if tpl is None:
                        raise SpecMismatch(f"{path}.{k}: custom field data_type {kind!r} has no spec template")
                    check(v, tpl, f"{path}.{k}")
                else:
                    raise SpecMismatch(f"{path}.{k}: not a field of the spec schema")
    else:
        ok = True   # untyped in the spec
    if not ok:
        raise SpecMismatch(f"{path}: {type(value).__name__} {value!r} but the spec says {t}")


def shaped(platform: str, name: str, raw: dict) -> dict:
    check(raw, _schemas(platform)[name], name)
    return _model(platform, name).from_dict(raw).to_dict()
