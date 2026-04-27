"""Data contract for TL/STL Conclusions Jinja2 templates."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TeamAverage:
    achievement: float
    attendance: float
    connect_rate: float
    call_loss_rate: float
    art_call_times: float

    def fmt(self, value: float | None, d: int = 1, suffix: str = '') -> str:
        if value is None:
            return '--'
        return f"{value:.1f}{suffix}"


@dataclass
class LaggingAgent:
    name: str
    achievement: float | None
    attendance: float | None
    connect_rate: float | None
    art_call_times: float | None
    gap: float


@dataclass
class TLConclusionContext:
    """Context for rendering TL Conclusions HTML via Jinja2."""
    group: str
    selected_date: str
    module_key: str           # e.g. "S1-Large"
    coarse_module: str         # e.g. "S1" (归一化后)
    team_avg: TeamAverage
    lagging_agents: list[LaggingAgent]
    people_summary: str
    strategy_summary: str
    tool_summary: str
    weak_case_stages: list[str]
    weak_principal_stages: list[str]
    module_avg_dial: float    # module average dial for comparison


@dataclass
class LaggingGroup:
    name: str
    achievement: float | None
    attendance: float | None
    connect_rate: float | None
    calls: float | None
    gap: float


@dataclass
class STLConclusionContext:
    """Context for rendering STL Conclusions HTML via Jinja2."""
    module: str
    selected_week: str
    module_avg: TeamAverage
    all_avg: TeamAverage
    lagging_groups: list[LaggingGroup]
    people_summary: str
    strategy_summary: str
    tool_summary: str
    weak_case_stages: list[str]
    weak_principal_stages: list[str]
    improvement_plan_url: Optional[str] = None  # None means no doc link
