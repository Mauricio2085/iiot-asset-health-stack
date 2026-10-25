#!/usr/bin/env python3
"""Check telemetry contract v1 and the Asset Health dashboard."""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts" / "telemetry-v1.schema.json"
FIXTURES = ROOT / "contracts" / "fixtures"
DASHBOARD_PATH = ROOT / "grafana" / "dashboards" / "asset-health.json"

VALID = ("valid.json", "valid-extra.json")
INVALID = (
    "invalid-missing-quality.json",
    "invalid-temperature-type.json",
    "invalid-quality.json",
    "invalid-ts.json",
)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def datasource_errors(node, path="$"):
    found = []
    if isinstance(node, dict):
        if "datasource" in node:
            source = node["datasource"]
            uid = source.get("uid") if isinstance(source, dict) else None
            if uid != "timescaledb":
                found.append(f"{path}.datasource uid is {uid!r}")
        for key, value in node.items():
            found.extend(datasource_errors(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(datasource_errors(value, f"{path}[{index}]"))
    return found


def dashboard_errors(dashboard):
    if not isinstance(dashboard, dict):
        return ["dashboard is not an object"]
    errors = []
    if dashboard.get("uid") != "asset-health":
        errors.append(f"uid is {dashboard.get('uid')!r}")
    panels = dashboard.get("panels")
    if not isinstance(panels, list) or len(panels) == 0:
        errors.append("panels is empty")
    errors.extend(datasource_errors(dashboard))
    return errors


def main():
    errors = []
    schema = load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(
        schema, format_checker=Draft202012Validator.FORMAT_CHECKER
    )

    for name in VALID:
        path = FIXTURES / name
        instance = load_json(path)
        failures = sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
        for failure in failures:
            errors.append(f"{name} should pass: {failure.message}")

    for name in INVALID:
        path = FIXTURES / name
        instance = load_json(path)
        if not any(validator.iter_errors(instance)):
            errors.append(f"{name} should fail")

    dashboard_failures = dashboard_errors(load_json(DASHBOARD_PATH))
    for failure in dashboard_failures:
        errors.append(f"asset-health.json: {failure}")

    rejected = dashboard_errors(load_json(FIXTURES / "dashboard-wrong-datasource.json"))
    if not rejected:
        errors.append("dashboard-wrong-datasource.json should fail")

    broken = FIXTURES / "broken.json"
    try:
        json.loads(broken.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        pass
    else:
        errors.append("broken.json should not parse")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(
        f"ok: {len(VALID)} valid payloads, {len(INVALID)} rejected payloads, dashboard accepted"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
