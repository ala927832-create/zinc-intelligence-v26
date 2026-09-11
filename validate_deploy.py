from __future__ import annotations

import json
from pathlib import Path

SNAPSHOT = Path("data/latest_snapshot.json")


def _missing_metadata(record: dict, fields: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for field in fields:
        value = record.get(field)
        if value is None or value == "":
            missing.append(field)
    return missing


def _validate_core_provenance(snapshot: dict, gate: dict) -> list[str]:
    """Require every deployable core datum to retain source/date/freshness metadata."""
    health = snapshot.get("market", {}).get("data_health", {})
    errors: list[str] = []
    required = ("source", "source_grade", "as_of", "age_days", "expected_update", "freshness")

    for field in gate.get("usable_core", []):
        record = health.get(field, {})
        missing = _missing_metadata(record, required)
        if missing:
            errors.append(f"{field}: missing provenance metadata {missing}")
        if record.get("freshness") != "CURRENT_ENOUGH":
            errors.append(f"{field}: usable core field is not CURRENT_ENOUGH")

    return errors


def _validate_tc_provenance(snapshot: dict) -> list[str]:
    """Available TC references must be date/source/basis traceable; missing data may stay missing."""
    tc = snapshot.get("china_tc", {})
    errors: list[str] = []
    required = ("value", "unit", "as_of", "age_days", "expected_update", "source", "source_grade", "status")

    for key in ("import_weekly", "domestic_weekly", "domestic_monthly", "annual_benchmark"):
        record = tc.get(key, {})
        if record.get("status") not in {"AVAILABLE", "VERIFIED_REFERENCE"}:
            continue
        missing = _missing_metadata(record, required)
        if missing:
            errors.append(f"china_tc.{key}: missing provenance/basis metadata {missing}")

    return errors


def main() -> None:
    if not SNAPSHOT.exists():
        raise SystemExit("BLOCK_DEPLOY: data/latest_snapshot.json missing")
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    gate = snapshot.get("core_data_gate", {})
    status = gate.get("status", "BLOCK_DEPLOY")
    print(f"Core data gate: {status}")
    print(f"Usable: {gate.get('usable_core', [])}")
    print(f"Stale: {gate.get('stale_core', [])}")
    print(f"Missing: {gate.get('missing_core', [])}")
    if status == "BLOCK_DEPLOY":
        raise SystemExit("BLOCK_DEPLOY: current run does not have enough verified/fresh LME core data. Previous deployed Pages site is preserved.")

    provenance_errors = _validate_core_provenance(snapshot, gate) + _validate_tc_provenance(snapshot)
    if provenance_errors:
        for error in provenance_errors:
            print(f"PROVENANCE_ERROR: {error}")
        raise SystemExit("BLOCK_DEPLOY: provenance/date/source metadata is incomplete. Previous deployed Pages site is preserved.")

    print("Provenance validation passed")
    print("Deploy validation passed")


if __name__ == "__main__":
    main()
