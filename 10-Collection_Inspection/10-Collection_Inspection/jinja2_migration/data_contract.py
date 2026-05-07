"""real_data 契约 — Jinja2 迁移版（基于 05-scripts/real_data_contract.py 增强）。

迁移说明：
- 沿用旧契约 ID 语义；新增 chart/table/dropdown 等结构化字段校验时 bump。
- Jinja2 渲染路径产物的 `templateContractId` 必须等于 TEMPLATE_CONTRACT_ID。
"""

from __future__ import annotations

# 模板/补丁基线；变更 .j2 结构、重锚点或新增必填字段时 bump
TEMPLATE_CONTRACT_ID = "v3_5+jinja2@2026-05-06"
# 渲染管线发行线（与 Git tag 可对照）
PIPELINE_VERSION = "jinja2_migration+build@1"

# 必填顶层键（与 generate_v2_7.py 输出对齐）
_REQUIRED_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "dataDate",
    "dataDay",
    "availableDates",
    "availableWeeks",
    "defaultStlWeek",
    "groups",
    "modules",
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
    "pipelineVersion",
)


def validate_real_data_for_report(d: dict) -> None:
    """注数前校验。键名与 real_data 中 camelCase 一致。

    随 .j2 模板新增依赖字段同步扩展本函数。
    """
    missing = [k for k in _REQUIRED_TOP_LEVEL_KEYS if k not in d]
    if missing:
        raise ValueError(f"real_data 缺少必填键: {missing}")
    if not d.get("groups"):
        raise ValueError("real_data.groups 须为非空")
    if d.get("templateContractId") != TEMPLATE_CONTRACT_ID:
        raise ValueError(
            "templateContractId 与契约常量不一致: "
            f"{d.get('templateContractId')!r} != {TEMPLATE_CONTRACT_ID!r}"
        )


def inject_pipeline_head_comment(
    html: str,
    *,
    contract_id: str,
    pipeline_version: str,
    data_date: str,
) -> str:
    """在 <head> 内注入可追溯 HTML 注释。"""
    mark = (
        f"<!-- report-pipeline: templateContractId={contract_id} "
        f"pipelineVersion={pipeline_version} dataDate={data_date} -->\n"
    )
    if "<head>" in html:
        return html.replace("<head>", "<head>\n" + mark, 1)
    return mark + html
