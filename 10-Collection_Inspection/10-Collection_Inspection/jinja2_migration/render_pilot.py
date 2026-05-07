"""render_pilot.py — Phase 2.5 Pilot: 串联 build_context → Jinja2 渲染 → 独立 HTML。

Usage:
    cd jinja2_migration
    python render_pilot.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

# Resolve paths relative to this file
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from data_prep import build_context
from renderer import _build_environment

EXCEL_PATH = PROJECT_ROOT / "data" / "260318_output_automation_v3.xlsx"
PROCESS_TARGET_PATH = PROJECT_ROOT / "data" / "process_data_target.xlsx"
SNAPSHOT_IN = HERE / "reports" / "anomaly_snapshot.json"
HTML_OUT = HERE / "reports" / "pilot_under_performing.html"
TEMPLATE_NAME = "data_view_under_performing.html.j2"
STANDALONE_NAME = "pilot_standalone.html.j2"


def main() -> int:
    print("=== Phase 2.5 Pilot — Under-performing Card Render ===\n")

    # ── 1. build_context ────────────────────────────────────────────────────
    if EXCEL_PATH.exists():
        print(f"[build_context] Excel: {EXCEL_PATH.name}")
        warnings: set[str] = set()
        real_data = build_context(
            str(EXCEL_PATH),
            str(PROCESS_TARGET_PATH) if PROCESS_TARGET_PATH.exists() else None,
            warnings=warnings,
        )
        anomaly_groups = real_data.get("anomalyGroups", [])
        anomaly_agents = real_data.get("anomalyAgents", [])
        group_table_rows = real_data.get("anomalyGroupTableRows", [])
        agent_table_rows = real_data.get("anomalyAgentTableRows", [])
        data_date = real_data.get("dataDate", str(date.today()))
    elif SNAPSHOT_IN.exists():
        print(f"[fallback] Using existing snapshot: {SNAPSHOT_IN.name}")
        snapshot = json.loads(SNAPSHOT_IN.read_text(encoding="utf-8"))
        anomaly_groups = snapshot.get("anomalyGroups", [])
        anomaly_agents = snapshot.get("anomalyAgents", [])
        data_date = snapshot.get("dataDate", str(date.today()))
    else:
        print("[ERROR] No data source found.", file=sys.stderr)
        return 1

    print(f"  anomalyGroups: {len(anomaly_groups)} rows")
    print(f"  anomalyAgents: {len(anomaly_agents)} rows")
    print(f"  dataDate      : {data_date}\n")

    # ── 2. render data_view_under_performing.html.j2 ─────────────────────────
    env = _build_environment(HERE / "templates")
    card_tpl = env.get_template(TEMPLATE_NAME)
    anomaly_content = card_tpl.render(
        anomaly_groups=anomaly_groups,
        anomaly_agents=anomaly_agents,
        anomalyGroupTableRows=group_table_rows,
        anomalyAgentTableRows=agent_table_rows,
    )

    # ── 3. wrap in standalone shell ──────────────────────────────────────────
    shell_tpl = env.get_template(STANDALONE_NAME)
    html = shell_tpl.render(
        anomaly_content=anomaly_content,
        anomaly_groups=anomaly_groups,
        anomaly_agents=anomaly_agents,
        data_date=data_date,
        snapshot_date=date.today().isoformat(),
        # Summary counts
        n_group_data_rows=sum(1 for r in group_table_rows if r.get("row_type") == "data"),
        n_agent_data_rows=sum(1 for r in agent_table_rows if r.get("row_type") == "data"),
        n_module_headers=sum(1 for r in group_table_rows if r.get("row_type") == "header"),
    )

    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    HTML_OUT.write_text(html, encoding="utf-8")
    print(f"[output] {HTML_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
