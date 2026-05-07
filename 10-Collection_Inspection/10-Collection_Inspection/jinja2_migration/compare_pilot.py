"""compare_pilot.py — Phase 2.5 Pilot: 提取 Jinja2 渲染结果，做结构比对与数据验证。

Usage:
    cd jinja2_migration
    python compare_pilot.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tests.helpers.html_table import extract_table, summarize_rows

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "reports" / "anomaly_snapshot.json"
PILOT_HTML = HERE / "reports" / "pilot_under_performing.html"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    pilot_rows_group = extract_table(PILOT_HTML, "anomaly-group-table")
    pilot_rows_agent = extract_table(PILOT_HTML, "anomaly-agent-table")

    # ── JSON ground truth ───────────────────────────────────────────────────
    json_groups = snapshot["anomalyGroups"]
    json_agents = snapshot["anomalyAgents"]

    # ── extract from Jinja2 rendered HTML ───────────────────────────────────
    jinja_group_summary = summarize_rows(pilot_rows_group, "group")
    jinja_agent_summary = summarize_rows(pilot_rows_agent, "agent")

    # ── compare: JSON rows vs Jinja2 data rows ───────────────────────────────
    print("=" * 70)
    print("PHASE 2.5 PILOT — UNDER-PERFORMING CARD COMPARISON REPORT")
    print("=" * 70)
    print(f"Snapshot date : {snapshot['dataDate']}")
    print(f"Pilot HTML    : {PILOT_HTML}")
    print()

    # ── Group table ──────────────────────────────────────────────────────────
    print("┌─ GROUP TABLE (anomaly-group-table) ──────────────────────────────")
    print(f"│  JSON anomalyGroups  : {len(json_groups)} rows")
    print(f"│  Jinja2 data rows   : {jinja_group_summary['data_rows']} rows")
    match_g = len(json_groups) == jinja_group_summary["data_rows"]
    print(f"│  Row count match    : {'✅ PASS' if match_g else '❌ FAIL'}")
    print(f"│  Module headers     : {jinja_group_summary['module_headers']}")
    modules_g = jinja_group_summary["module_list"]
    print(f"│  Modules rendered   : {sorted(set(modules_g), key=str)}")
    print()
    print("│  First 3 Jinja2 rows:")
    for r in jinja_group_summary["first_3_data"]:
        print(f"│    {r[:120]}")
    print()

    # Check group names match (set comparison — sort order differs by design)
    jinja_group_names = []
    for r in pilot_rows_group:
        parts = [p.strip() for p in r.split("|")]
        if parts and not r.startswith("[M]"):
            jinja_group_names.append(parts[0])
    json_group_names_set = set(g["name"] for g in json_groups)
    jinja_group_names_set = set(jinja_group_names)
    name_match_g = json_group_names_set == jinja_group_names_set
    print(f"│  Group name set match: {'✅ PASS' if name_match_g else '❌ FAIL'}")
    if not name_match_g:
        print(f"│    Only in JSON  : {json_group_names_set - jinja_group_names_set}")
        print(f"│    Only in Jinja2: {jinja_group_names_set - json_group_names_set}")
    print("└────────────────────────────────────────────────────────────────────")

    # ── Agent table ──────────────────────────────────────────────────────────
    print()
    print("┌─ AGENT TABLE (anomaly-agent-table) ──────────────────────────────")
    print(f"│  JSON anomalyAgents : {len(json_agents)} rows")
    print(f"│  Jinja2 data rows   : {jinja_agent_summary['data_rows']} rows")
    match_a = len(json_agents) == jinja_agent_summary["data_rows"]
    print(f"│  Row count match    : {'✅ PASS' if match_a else '❌ FAIL'}")
    print(f"│  Module headers     : {jinja_agent_summary['module_headers']}")
    modules_a = jinja_agent_summary["module_list"]
    print(f"│  Modules rendered   : {sorted(set(modules_a), key=str)}")
    print()
    print("│  First 3 Jinja2 rows:")
    for r in jinja_agent_summary["first_3_data"]:
        print(f"│    {r[:120]}")

    # Check agent names match (set comparison — sort order differs by design)
    jinja_agent_names = []
    for r in pilot_rows_agent:
        parts = [p.strip() for p in r.split("|")]
        if parts and not r.startswith("[M]"):
            jinja_agent_names.append(parts[0])
    json_agent_names_set = set(a["name"] for a in json_agents)
    jinja_agent_names_set = set(jinja_agent_names)
    name_match_a = json_agent_names_set == jinja_agent_names_set
    print()
    print(f"│  Agent name set match: {'✅ PASS' if name_match_a else '❌ FAIL'}")
    if not name_match_a:
        print(f"│    Only in JSON  : {json_agent_names_set - jinja_agent_names_set}")
        print(f"│    Only in Jinja2: {jinja_agent_names_set - json_agent_names_set}")
    print("└────────────────────────────────────────────────────────────────────")

    # ── Streak/Weeks validation ──────────────────────────────────────────────
    print()
    print("┌─ STREAK/DAYS VALIDATION ─────────────────────────────────────────")
    # Build name→weeks map from Jinja2 rows
    jinja_group_weeks: dict[str, int] = {}
    for r in pilot_rows_group:
        if r.startswith("[M]"):
            continue
        parts = [p.strip() for p in r.split("|")]
        if parts and len(parts) >= 3:
            try:
                jinja_group_weeks[parts[0]] = int(parts[2])
            except ValueError:
                pass

    json_group_weeks = {g["name"]: g["weeks"] for g in json_groups}
    week_mismatch_g = [(n, json_group_weeks.get(n, "?"), w) for n, w in jinja_group_weeks.items() if json_group_weeks.get(n, "?") != w]
    print(f"│  Group weeks match  : {'✅ PASS' if not week_mismatch_g else '❌ FAIL'}")
    if week_mismatch_g:
        for n, jw, pw in week_mismatch_g:
            print(f"│    {n}: JSON={jw}, Jinja2={pw}")

    jinja_agent_days: dict[str, int] = {}
    for r in pilot_rows_agent:
        if r.startswith("[M]"):
            continue
        parts = [p.strip() for p in r.split("|")]
        if parts and len(parts) >= 4:
            try:
                jinja_agent_days[parts[0]] = int(parts[3])
            except ValueError:
                pass

    json_agent_days = {a["name"]: a["days"] for a in json_agents}
    week_mismatch_a = [(n, json_agent_days.get(n, "?"), w) for n, w in jinja_agent_days.items() if json_agent_days.get(n, "?") != w]
    print(f"│  Agent days match   : {'✅ PASS' if not week_mismatch_a else '❌ FAIL'}")
    if week_mismatch_a:
        for n, jw, pw in week_mismatch_a:
            print(f"│    {n}: JSON={jw}, Jinja2={pw}")
    print("└────────────────────────────────────────────────────────────────────")

    # ── Summary ──────────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    all_pass = match_g and match_a and name_match_g and name_match_a and not week_mismatch_g and not week_mismatch_a
    if all_pass:
        print("✅ ALL CHECKS PASSED — Pilot data equivalence confirmed")
        print()
        print("NEXT: Please open the Pilot HTML in a browser to verify visual output:")
        print(f"  file://{PILOT_HTML}")
        print()
        print("Key verification points:")
        print("  1. Group table shows correct modules and row counts")
        print("  2. Agent table shows correct names and streak counts")
        print("  3. No console errors (F12 → Console)")
        print("  4. Row colors: red (3+ weeks/days) vs yellow (2 weeks/3 days)")
    else:
        print("❌ MISMATCH DETECTED — Review discrepancies above")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
