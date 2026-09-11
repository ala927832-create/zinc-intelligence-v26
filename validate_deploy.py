from __future__ import annotations

import json
from pathlib import Path

SNAPSHOT = Path("data/latest_snapshot.json")


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
    print("Deploy validation passed")


if __name__ == "__main__":
    main()
