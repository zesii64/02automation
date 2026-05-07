"""Extract anomaly snapshot — Phase 2.5 Pilot helper.

运行 build_context() → 抽取 anomalyGroups / anomalyAgents → 保存为 JSON snapshot
供后续 Jinja2 渲染对比。

Usage:
    cd jinja2_migration
    python extract_anomaly_snapshot.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# 允许从 jinja2_migration 目录直接运行
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from data_prep import build_context  # noqa: E402


EXCEL_PATH = PROJECT_ROOT / "data" / "260318_output_automation_v3.xlsx"
PROCESS_TARGET_PATH = PROJECT_ROOT / "data" / "process_data_target.xlsx"
OUT_DIR = HERE / "reports"
OUT_PATH = OUT_DIR / "anomaly_snapshot.json"


def extract_anomaly_fields(real_data: dict[str, Any]) -> dict[str, Any]:
    """从 real_data 抽取 Pilot 关心的最小切片。"""
    return {
        "templateContractId": real_data.get("templateContractId"),
        "dataDate": real_data.get("dataDate"),
        "modules": real_data.get("modules"),
        "anomalyGroups": real_data.get("anomalyGroups", []),
        "anomalyAgents": real_data.get("anomalyAgents", []),
        "anomalyGroupTableRows": real_data.get("anomalyGroupTableRows", []),
        "anomalyAgentTableRows": real_data.get("anomalyAgentTableRows", []),
    }


def main() -> int:
    if not EXCEL_PATH.exists():
        print(f"[ERROR] Excel not found: {EXCEL_PATH}", file=sys.stderr)
        return 1

    print(f"Excel    : {EXCEL_PATH}")
    print(f"Process  : {PROCESS_TARGET_PATH if PROCESS_TARGET_PATH.exists() else '(skip)'}")

    warnings: set[str] = set()
    real_data = build_context(
        str(EXCEL_PATH),
        str(PROCESS_TARGET_PATH) if PROCESS_TARGET_PATH.exists() else None,
        warnings=warnings,
    )

    snapshot = extract_anomaly_fields(real_data)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    n_groups = len(snapshot["anomalyGroups"])
    n_agents = len(snapshot["anomalyAgents"])
    print()
    print("=== Anomaly Snapshot ===")
    print(f"  templateContractId : {snapshot['templateContractId']}")
    print(f"  dataDate           : {snapshot['dataDate']}")
    print(f"  modules            : {snapshot['modules']}")
    print(f"  anomalyGroups      : {n_groups} rows")
    print(f"  anomalyAgents      : {n_agents} rows")
    print()
    print(f"Saved → {OUT_PATH}")
    if warnings:
        print(f"\n[WARN] {len(warnings)} data warnings collected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
