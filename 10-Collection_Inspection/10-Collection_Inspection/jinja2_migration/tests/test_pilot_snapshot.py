"""test_pilot_snapshot — Phase 2.5 Pilot 输出 L3 fragment 对比验证。

已由用户 browser GO 确认。后续若 snapshot 变化触发此测试 FAIL，
说明有回归，必须停下报告。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers.html_table import extract_table, summarize_rows

HERE = Path(__file__).resolve().parent
REPORTS_DIR = HERE.parent / "reports"
SNAPSHOT_PATH = REPORTS_DIR / "anomaly_snapshot.json"
PILOT_HTML_PATH = REPORTS_DIR / "pilot_under_performing.html"

TBODY_GROUP = "anomaly-group-table"
TBODY_AGENT = "anomaly-agent-table"


@pytest.fixture(scope="module")
def snapshot() -> dict:
    if not SNAPSHOT_PATH.exists():
        pytest.fail(f"Anomaly snapshot not found: {SNAPSHOT_PATH}")
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pilot_html_path() -> Path:
    if not PILOT_HTML_PATH.exists():
        pytest.fail(f"Pilot HTML not found: {PILOT_HTML_PATH}")
    return PILOT_HTML_PATH


class TestGroupFragment:
    """Group table L3 fragment 对比。"""

    def test_group_row_count(self, snapshot: dict, pilot_html_path: Path):
        """Group 表数据行数应与 snapshot 一致。"""
        rows = extract_table(pilot_html_path, TBODY_GROUP)
        summary = summarize_rows(rows, "group")
        expected = len(snapshot["anomalyGroups"])
        assert summary["data_rows"] == expected, (
            f"Group data rows: {summary['data_rows']} != expected {expected}"
        )

    def test_group_name_set(self, snapshot: dict, pilot_html_path: Path):
        """Group name set 应与 snapshot 一致。"""
        rows = extract_table(pilot_html_path, TBODY_GROUP)
        jinja_names = set()
        for r in rows:
            if r.startswith("[M]"):
                continue
            parts = [p.strip() for p in r.split("|")]
            if parts:
                jinja_names.add(parts[0])
        json_names = {g["name"] for g in snapshot["anomalyGroups"]}
        assert jinja_names == json_names, (
            f"Name mismatch. Only in JSON: {json_names - jinja_names}. "
            f"Only in Jinja2: {jinja_names - json_names}."
        )

    def test_group_weeks_match(self, snapshot: dict, pilot_html_path: Path):
        """Group weeks 值应与 snapshot 一致。"""
        rows = extract_table(pilot_html_path, TBODY_GROUP)
        jinja_weeks: dict[str, int] = {}
        for r in rows:
            if r.startswith("[M]"):
                continue
            parts = [p.strip() for p in r.split("|")]
            if parts and len(parts) >= 3:
                try:
                    jinja_weeks[parts[0]] = int(parts[2])
                except ValueError:
                    pass
        json_weeks = {g["name"]: g["weeks"] for g in snapshot["anomalyGroups"]}
        mismatches = [
            (n, json_weeks.get(n, "?"), w)
            for n, w in jinja_weeks.items()
            if json_weeks.get(n, "?") != w
        ]
        assert not mismatches, f"Group weeks mismatches: {mismatches}"

    def test_group_module_headers(self, snapshot: dict, pilot_html_path: Path):
        """Group 表的模块头数量应为 7（S0 / S1-Large / S1-Small / S2-Large / S2-Small / M1-Large / M1-Small）。"""
        rows = extract_table(pilot_html_path, TBODY_GROUP)
        summary = summarize_rows(rows, "group")
        assert summary["module_headers"] == 7, (
            f"Expected 7 module headers, got {summary['module_headers']}"
        )


class TestAgentFragment:
    """Agent table L3 fragment 对比。"""

    def test_agent_row_count(self, snapshot: dict, pilot_html_path: Path):
        """Agent 表数据行数应与 snapshot 一致。"""
        rows = extract_table(pilot_html_path, TBODY_AGENT)
        summary = summarize_rows(rows, "agent")
        expected = len(snapshot["anomalyAgents"])
        assert summary["data_rows"] == expected, (
            f"Agent data rows: {summary['data_rows']} != expected {expected}"
        )

    def test_agent_name_set(self, snapshot: dict, pilot_html_path: Path):
        """Agent name set 应与 snapshot 一致。"""
        rows = extract_table(pilot_html_path, TBODY_AGENT)
        jinja_names = set()
        for r in rows:
            if r.startswith("[M]"):
                continue
            parts = [p.strip() for p in r.split("|")]
            if parts:
                jinja_names.add(parts[0])
        json_names = {a["name"] for a in snapshot["anomalyAgents"]}
        assert jinja_names == json_names, (
            f"Name mismatch. Only in JSON: {json_names - jinja_names}. "
            f"Only in Jinja2: {jinja_names - json_names}."
        )

    def test_agent_days_match(self, snapshot: dict, pilot_html_path: Path):
        """Agent days 值应与 snapshot 一致。"""
        rows = extract_table(pilot_html_path, TBODY_AGENT)
        jinja_days: dict[str, int] = {}
        for r in rows:
            if r.startswith("[M]"):
                continue
            parts = [p.strip() for p in r.split("|")]
            if parts and len(parts) >= 4:
                try:
                    jinja_days[parts[0]] = int(parts[3])
                except ValueError:
                    pass
        json_days = {a["name"]: a["days"] for a in snapshot["anomalyAgents"]}
        mismatches = [
            (n, json_days.get(n, "?"), w)
            for n, w in jinja_days.items()
            if json_days.get(n, "?") != w
        ]
        assert not mismatches, f"Agent days mismatches: {mismatches}"

    def test_agent_module_headers(self, snapshot: dict, pilot_html_path: Path):
        """Agent 表的模块头数量应为 7。"""
        rows = extract_table(pilot_html_path, TBODY_AGENT)
        summary = summarize_rows(rows, "agent")
        assert summary["module_headers"] == 7, (
            f"Expected 7 module headers, got {summary['module_headers']}"
        )
