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


def _validate_decision_book(snapshot: dict) -> list[str]:
    """Require every published market decision to answer the same eight questions."""
    errors: list[str] = []
    markets = snapshot.get("decision_book", {}).get("markets", {})
    required_markets = {"lme_zinc", "shfe_zinc", "gold", "usdjpy", "dxy"}
    for key in sorted(required_markets - set(markets)):
        errors.append(f"decision_book.{key}: missing market plan")
    audit_fields = {
        "1_market_direction", "2_evidence_consistency", "3_risk_location", "4_entry_permission",
        "5_loss_if_wrong", "6_exit_plan", "7_planned_rr", "8_no_trade_reason",
    }
    plan_fields = {"setup_zone", "trigger_price", "maximum_entry", "hard_stop",
                   "close_invalidation", "t1", "t2", "planned_rr_t1", "planned_rr_t2",
                   "conditional_order"}
    for key, plan in markets.items():
        missing_audit = audit_fields - set(plan.get("decision_audit", {}))
        if missing_audit:
            errors.append(f"decision_book.{key}: missing audit fields {sorted(missing_audit)}")
        if "evidence_completeness" not in plan or not isinstance(plan.get("evidence", []), list):
            errors.append(f"decision_book.{key}: evidence availability is not auditable")
        daily = plan.get("daily_plan", {})
        if daily:
            missing_plan = plan_fields - set(daily)
            if missing_plan:
                errors.append(f"decision_book.{key}: incomplete conditional plan {sorted(missing_plan)}")
            if plan.get("execution_gate") not in {"PENDING_LIVE_QUOTE", "PENDING_PRIVATE_EXECUTION_CHECK"}:
                errors.append(f"decision_book.{key}: public plan crossed the private execution boundary")
            risk_atr = daily.get("risk_distance_atr")
            if key != "lme_zinc" and (risk_atr is None or float(risk_atr) > 3):
                errors.append(f"decision_book.{key}: OHLC plan risk distance exceeds 3 ATR or is missing")
        elif plan.get("decision") != "NO_TRADE":
            errors.append(f"decision_book.{key}: non-No-Trade decision has no conditional plan")
    lme = markets.get("lme_zinc", {})
    if lme.get("reference", {}).get("cash") != snapshot.get("market", {}).get("lme_cash"):
        errors.append("decision_book.lme_zinc: Cash headline does not match the market snapshot")
    if "atr14" in lme.get("daily_plan", {}) or "candle" in lme.get("daily_plan", {}):
        errors.append("decision_book.lme_zinc: close-only plan must not infer ATR or a candle")
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

    provenance_errors = (_validate_core_provenance(snapshot, gate) + _validate_tc_provenance(snapshot)
                         + _validate_decision_book(snapshot))
    if provenance_errors:
        for error in provenance_errors:
            print(f"PROVENANCE_ERROR: {error}")
        raise SystemExit("BLOCK_DEPLOY: provenance/date/source metadata is incomplete. Previous deployed Pages site is preserved.")

    print("Provenance validation passed")
    print("Deploy validation passed")


if __name__ == "__main__":
    main()
