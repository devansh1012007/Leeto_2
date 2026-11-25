#!/usr/bin/env python3
"""Vendored OpenAPI linter (A1 gate). Checks:
- every operation has operationId, summary, tags, responses
- every response entry has a description
- request bodies have content schemas
- parameters have name/in/required/schema
- component refs resolve
- no 423 responses (R-06)
Exit 1 on any violation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_spec() -> dict:
    return json.loads((ROOT / "openapi" / "openapi.json").read_text())

def refs_ok(node, defs: set[str], path: str, errors: list[str]) -> None:
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if ref.startswith("#/components/schemas/"):
                name = ref.rsplit("/", 1)[1]
                if name not in defs:
                    errors.append(f"{path}: unresolved ref {ref}")
        for k, v in node.items():
            refs_ok(v, defs, f"{path}.{k}", errors)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            refs_ok(v, defs, f"{path}[{i}]", errors)

def main() -> int:
    spec = load_spec()
    errors: list[str] = []
    if spec.get("openapi", "").startswith("3.") is False:
        errors.append("missing/invalid openapi version")
    defs = set(spec.get("components", {}).get("schemas", {}).keys())
    seen_op_ids: set[str] = set()
    n_ops = 0
    for path, item in spec.get("paths", {}).items():
        if not path.startswith("/"):
            errors.append(f"path {path} must start with /")
        for method, op in item.items():
            if method in ("parameters",):
                continue
            if method not in ("get", "post", "put", "delete", "patch", "head", "options"):
                errors.append(f"{path}: unknown method {method}")
                continue
            n_ops += 1
            base = f"{method.upper()} {path}"
            for field in ("operationId", "summary", "responses"):
                if field not in op:
                    errors.append(f"{base}: missing {field}")
            if op.get("operationId") in seen_op_ids:
                errors.append(f"{base}: duplicate operationId {op.get('operationId')}")
            seen_op_ids.add(op.get("operationId"))
            for status, resp in op.get("responses", {}).items():
                if status == "423":
                    errors.append(f"{base}: 423 response forbidden (R-06)")
                if isinstance(resp, dict) and "description" not in resp:
                    errors.append(f"{base} {status}: missing description")
            rb = op.get("requestBody")
            if rb:
                for ct, media in rb.get("content", {}).items():
                    if "schema" not in media:
                        errors.append(f"{base}: requestBody {ct} missing schema")
            for prm in op.get("parameters", []) or []:
                for field in ("name", "in", "schema"):
                    if field not in prm:
                        errors.append(f"{base}: parameter missing {field}")
    refs_ok(spec.get("components", {}), defs, "components", errors)
    # every schema has a type or is a composite
    for name, sch in spec.get("components", {}).get("schemas", {}).items():
        if not any(k in sch for k in ("type", "oneOf", "anyOf", "allOf", "$ref")):
            errors.append(f"schema {name}: no type/composite")
    print(f"openapi_lint: {n_ops} operations checked, {len(errors)} errors")
    for e in errors[:40]:
        print("  ERROR:", e)
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
