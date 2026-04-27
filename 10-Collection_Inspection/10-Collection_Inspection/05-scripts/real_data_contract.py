"""real_data 最小契约：与注数/图表消费路径对齐；bump 见计划 §②-5、§②-6。"""

from __future__ import annotations

# 模板/补丁基线；变更 v3_5 结构、重锚点或新增必填字段时 bump
TEMPLATE_CONTRACT_ID = "v3_5+pipeline@2026-04-22"
# 生成脚本发行线（与 Git tag 可对照）
PIPELINE_VERSION = "generate_v2_7+build@1"


def validate_real_data_for_report(d: dict) -> None:
    """
    注数前校验。键名与 real_data 中 camelCase 一致。
    随 apply_* 新增依赖字段增量扩展本函数。
    """
    must = (
        "dataDate",
        "groups",
        "modules",
        "tlData",
        "stlData",
        "moduleDailyTrends",
        "templateContractId",
        "pipelineVersion",
    )
    missing = [k for k in must if k not in d]
    if missing:
        raise ValueError(f"real_data 缺少必填键: {missing}")
    if not d.get("groups"):
        raise ValueError("real_data.groups 须为非空")
    if d.get("templateContractId") != TEMPLATE_CONTRACT_ID:
        raise ValueError(
            f"templateContractId 与契约常量不一致: {d.get('templateContractId')!r} != {TEMPLATE_CONTRACT_ID!r}"
        )


def inject_pipeline_head_comment(
    html: str,
    *,
    contract_id: str,
    pipeline_version: str,
    data_date: str,
) -> str:
    """在 <head> 内注入可追溯 HTML 注释（计划 §②-6）。"""
    mark = (
        f"<!-- report-pipeline: templateContractId={contract_id} "
        f"pipelineVersion={pipeline_version} dataDate={data_date} -->\n"
    )
    if "<head>" in html:
        return html.replace("<head>", "<head>\n" + mark, 1)
    return mark + html
