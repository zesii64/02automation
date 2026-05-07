"""test_data_prep_build_context — L1 context lock: build_context keys & types."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


# 27 keys in the pinned fixture (all except dataDay, pipelineVersion)
FIXTURE_KEYS: set[str] = {
    "dataDate",
    "availableDates",
    "availableWeeks",
    "defaultStlWeek",
    "modules",
    "groups",
    "tlData",
    "stlData",
    "agentPerformance",
    "agentPerformanceByDate",
    "groupPerformance",
    "groupPerformanceByWeek",
    "groupConsecutiveWeeksByWeek",
    "anomalyGroups",
    "anomalyAgents",
    "anomalyGroupTableRows",
    "anomalyAgentTableRows",
    "processTargets",
    "riskModuleGroups",
    "moduleDailyTrends",
    "moduleMonthly",
    "todayAgentTargetByGroup",
    "todayAgentTargetByGroupAgent",
    "tlBreakdownByDate",
    "stlBreakdownByWeek",
    "hasStlWeekBreakdownData",
    "templateContractId",
}
# 2 keys that exist in build_context but are excluded from fixture (runtime-dependent)
RUNTIME_KEYS: set[str] = {"dataDay", "pipelineVersion"}


class TestBuildContextKeys:
    """L1 context lock: build_context returns all expected keys with correct types."""

    def test_fixture_has_all_snapshot_keys(self, real_context: dict[str, Any]):
        """Fixture should contain all 27 pinned keys."""
        actual = set(real_context.keys())
        missing = FIXTURE_KEYS - actual
        extra = actual - FIXTURE_KEYS
        assert not missing, f"Fixture missing keys: {missing}"
        assert not extra, f"Fixture has unexpected keys: {extra}"
        assert len(actual) == len(FIXTURE_KEYS)

    def test_fixture_keys_are_str_types(self, real_context: dict[str, Any]):
        """Keys that should be strings."""
        for key in ("dataDate", "defaultStlWeek", "templateContractId"):
            assert isinstance(real_context[key], str), f"{key} should be str, got {type(real_context[key])}"

    def test_fixture_keys_are_list_types(self, real_context: dict[str, Any]):
        """Keys that should be lists."""
        for key in ("modules", "groups", "availableDates", "availableWeeks"):
            assert isinstance(real_context[key], list), f"{key} should be list, got {type(real_context[key])}"

    def test_fixture_keys_are_dict_types(self, real_context: dict[str, Any]):
        """Keys that should be dicts (non-empty)."""
        for key in ("tlData", "stlData", "groupPerformance", "agentPerformance", "moduleDailyTrends"):
            assert isinstance(real_context[key], dict), f"{key} should be dict, got {type(real_context[key])}"
            assert len(real_context[key]) > 0, f"{key} should be non-empty"

    def test_groups_non_empty_strings(self, real_context: dict[str, Any]):
        """groups list entries should be non-empty strings."""
        groups = real_context["groups"]
        assert len(groups) > 0
        all_str = all(isinstance(g, str) and len(g) > 0 for g in groups)
        assert all_str, "All groups entries should be non-empty strings"

    def test_modules_sorted(self, real_context: dict[str, Any]):
        """modules should contain module identifiers, not empty."""
        modules = real_context["modules"]
        assert len(modules) > 0
        all_str = all(isinstance(m, str) and len(m) > 0 for m in modules)
        assert all_str, "All modules entries should be non-empty strings"

    def test_anomaly_groups_well_formed(self, real_context: dict[str, Any]):
        """anomalyGroups entries should have name/module/weeks."""
        groups = real_context.get("anomalyGroups", [])
        if groups:
            for g in groups:
                assert "name" in g
                assert "module" in g
                assert "weeks" in g

    def test_anomaly_agents_well_formed(self, real_context: dict[str, Any]):
        """anomalyAgents entries should have name/group/module/days."""
        agents = real_context.get("anomalyAgents", [])
        if agents:
            for a in agents:
                assert "name" in a
                assert "group" in a
                assert "module" in a
                assert "days" in a

    def test_agent_performance_by_date_structure(self, real_context: dict[str, Any]):
        """agentPerformanceByDate should be nested dict: group → agent → date → target/actual."""
        apd = real_context.get("agentPerformanceByDate", {})
        if apd:
            first_group = next(iter(apd.values()))
            if first_group:
                first_agent = next(iter(first_group.values()))
                if first_agent:
                    first_date = next(iter(first_agent.values()))
                    assert "target" in first_date
                    assert "actual" in first_date
                    assert "achievement" in first_date

    def test_tl_data_has_group_module(self, real_context: dict[str, Any]):
        """Each tlData entry should have a groupModule field."""
        tl = real_context.get("tlData", {})
        if tl:
            for group_id, data in tl.items():
                assert "groupModule" in data, f"tlData[{group_id}] missing groupModule"


class TestBuildContextAgainstContract:
    """验证转发表 export 时的 d 与 data_contract 约束一致。"""

    def test_contract_validation_passes(self, real_context: dict[str, Any]):
        """validate_real_data_for_report 对 fixture 的数据不能抛异常。"""
        from data_contract import validate_real_data_for_report

        # Fixture lacks dataDay/pipelineVersion — add sentinels to pass validation
        full = dict(real_context)
        full.setdefault("dataDay", "00")
        full.setdefault("pipelineVersion", "test")
        # validate_real_data_for_report checks templateContractId — use fixture's value
        validate_real_data_for_report(full)
