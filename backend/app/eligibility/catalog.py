"""Load and index the scheme catalogue.

The catalogue is plain JSON on disk so a policy change is an edit, not a
release. It is validated once at import: a typo in an operator should break
startup loudly rather than silently mark somebody ineligible.
"""
from __future__ import annotations

import json
from functools import lru_cache

from ..config import DATA_DIR

VALID_OPS = {
    "==", "!=", "in", "not_in", ">", ">=", "<", "<=",
    "is_true", "is_false", "exists",
}


def _validate_node(node: dict, scheme_id: str) -> None:
    for junction in ("all", "any"):
        if junction in node:
            for child in node[junction]:
                _validate_node(child, scheme_id)
            return
    if "not" in node:
        _validate_node(node["not"], scheme_id)
        return

    if "field" not in node or "op" not in node:
        raise ValueError(f"{scheme_id}: rule leaf needs field and op, got {node}")
    if node["op"] not in VALID_OPS:
        raise ValueError(f"{scheme_id}: unsupported operator {node['op']}")


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    path = DATA_DIR / "schemes.json"
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    seen: set[str] = set()
    for scheme in data["schemes"]:
        if scheme["id"] in seen:
            raise ValueError(f"duplicate scheme id: {scheme['id']}")
        seen.add(scheme["id"])
        _validate_node(scheme.get("rules") or {"all": []}, scheme["id"])
        _validate_node(scheme.get("exclusions") or {"any": []}, scheme["id"])

    return data


def all_schemes() -> list[dict]:
    return load_catalog()["schemes"]


def get_scheme(scheme_id: str) -> dict | None:
    return next((s for s in all_schemes() if s["id"] == scheme_id), None)


def catalog_meta() -> dict:
    return load_catalog().get("_meta", {})


def categories() -> list[str]:
    return sorted({s.get("category", "other") for s in all_schemes()})
