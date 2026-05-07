"""data_prep_payloads — 额外载荷构建器。

从 generate_v2_7.py (lines 1225-1542) 抽取：anomalies, module daily/monthly,
risk module groups, today agent targets, TL/STL breakdowns。
"""

from __future__ import annotations

import re

import pandas as pd

from data_prep_helpers import (
    extract_module_key,
    norm,
    resolve_canonical_group_for_breakdown,
    week_str_to_display,
)


_MODULE_SORT_RANK: dict[str, int] = {"S0": 0, "S1": 1, "S2": 2, "M1": 3}


def _module_sort_key(item: dict) -> tuple[int, str, int]:
    """与 JS moduleSort 完全一致的排序键：(rank, module_name, -weeks)。

    JS 中 S1-Large D(3) 排在 S1-Small A(4) 之前，说明：
    - 同 rank 按 module_name 字母序（S1-Large < S1-Small）
    - 同 module 按 weeks 降序
    与 (rank, mk, -weeks) 等价。
    """
    mk = item["module"]
    base = mk.split("-")[0]
    rank = _MODULE_SORT_RANK.get(base, 999)
    weeks = item.get("weeks", 0)
    return (rank, mk, -weeks)


def build_anomaly_groups(
    modules_list: list[str],
    submodule_groups: dict[str, list[str]],
    group_consecutive_by_week_js: dict,
    group_perf_by_week_js: dict,
    default_week_label: str,
) -> list[dict]:
    """构建 anomaly_groups 列表（连续未达标 >= 2 周的组）。"""
    anomaly_groups: list[dict] = []
    for mk in modules_list:
        for group in submodule_groups.get(mk, []):
            cw_map = group_consecutive_by_week_js.get(mk, {}).get(group, {})
            streak = int(cw_map.get(default_week_label, 0))
            if streak < 2:
                continue
            wk_map = group_perf_by_week_js.get(mk, {}).get(group, {})
            wk = wk_map.get(default_week_label, {})
            w_tgt = round(float(wk.get("target", 0) or 0))
            w_act = round(float(wk.get("actual", 0) or 0))
            anomaly_groups.append({
                "name": group,
                "module": mk,
                "weeks": streak,
                "weeklyTarget": w_tgt,
                "weeklyActual": w_act,
            })
    anomaly_groups.sort(key=_module_sort_key)
    return anomaly_groups


def build_group_table_rows(anomaly_groups: list[dict]) -> list[dict]:
    """将 anomaly_groups 扩展为含模块头行的渲染列表。

    返回的列表元素有两种类型：
      - row_type="header": 模块头行，含 module / label 字段
      - row_type="data":   数据行，与 anomaly_groups 元素结构一致
    与 JS 渲染逻辑完全对齐：模块内按 weeks 降序，同模块只插一个模块头。
    """
    rows: list[dict] = []
    last_module: str | None = None
    for g in anomaly_groups:
        mk = g["module"]
        if mk != last_module:
            rows.append({"row_type": "header", "module": mk, "label": mk})
            last_module = mk
        rows.append({"row_type": "data", **g})
    return rows


def build_anomaly_agents(
    agent_perf_js: dict,
    tl_data_js: dict,
) -> list[dict]:
    """构建 anomaly_agents 列表（连续未达标 >= 3 天的 agent）。

    过滤逻辑与生产 HTML JS 对齐：
    1. streak >= 3
    2. dailyTarget > 0（零目标 agent 在 agentPerformance 中无近期 entry，
       JS computeAgentStreakByDate 返回 0，不在 anomaly 表中）
    """
    anomaly_agents: list[dict] = []
    for group, agents in agent_perf_js.items():
        module = tl_data_js.get(group, {}).get("groupModule", "")
        for a in agents:
            streak = int(a.get("consecutiveDays", 0) or 0)
            if streak < 3:
                continue
            daily_target = round(float(a.get("target", 0) or 0))
            if daily_target == 0:
                continue  # 与 JS computeAgentStreakByDate 等价：零目标 agent 在 APD 中无 entry
            anomaly_agents.append({
                "name": a.get("name", ""),
                "group": group,
                "module": module,
                "days": streak,
                "dailyTarget": daily_target,
                "dailyActual": round(float(a.get("actual", 0) or 0)),
                "calls": int(a.get("artCallTimes", a.get("calls", 0)) or 0),
                "connectRate": float(a.get("connectRate", 0.0) or 0.0),
                "callLossRate": a.get("callLossRate"),
                "attendance": int(a.get("attendance", 0) or 0),
            })
    anomaly_agents.sort(key=_agent_sort_key)
    return anomaly_agents


def _agent_sort_key(item: dict) -> tuple[int, str, int]:
    """与 JS 渲染逻辑一致的 agent 排序：(rank, module_name, -days)。

    同 module 的 agent 必须连续（与 group 表同理）。
    """
    mk = item["module"]
    base = mk.split("-")[0]
    rank = _MODULE_SORT_RANK.get(base, 999)
    days = item.get("days", 0)
    return (rank, mk, -days)


def build_agent_table_rows(anomaly_agents: list[dict]) -> list[dict]:
    """将 anomaly_agents 扩展为含模块头行的渲染列表。

    与 build_group_table_rows 同理：在 Python 侧完成模块头行插入，
    模板无需追踪 current_module。
    """
    rows: list[dict] = []
    last_module: str | None = None
    for a in anomaly_agents:
        mk = a["module"]
        if mk != last_module:
            rows.append({"row_type": "header", "module": mk, "label": mk})
            last_module = mk
        rows.append({"row_type": "data", **a})
    return rows


def build_module_daily_trends(
    modules_list: list[str],
    module_nm_dict: dict,
    target_nm_dict: dict,
    nat_buckets: set[str],
    sorted_year_months: list[tuple[int, int]],
    tl_latest_str: str,
) -> dict:
    """构建 module_daily_js，包含数据中所有年月的日维度数据。"""
    from calendar import monthrange
    from data_prep_helpers import module_key_to_bucket

    module_daily_js: dict = {}
    for mk in modules_list:
        mk_nm_daily = module_nm_dict.get(mk, {})
        module_bucket = module_key_to_bucket(mk, nat_buckets)
        module_target_nm = target_nm_dict.get(module_bucket, {})

        daily_series = []
        for year, month in sorted_year_months:
            days_in_month = monthrange(year, month)[1]
            for day in range(1, days_in_month + 1):
                date_str = f"{year}-{month:02d}-{day:02d}"
                in_cutoff = date_str <= tl_latest_str
                nm_rr = mk_nm_daily.get(date_str, None) if in_cutoff else None
                nm_trr = module_target_nm.get(date_str, None)
                daily_series.append({
                    "date": date_str,
                    "target": None,
                    "actual": None,
                    "repayRate": nm_rr,
                    "targetRepayRate": nm_trr,
                })
        module_daily_js[mk] = {"daily": daily_series}
    return module_daily_js


def build_module_monthly(
    modules_list: list[str],
    submodule_dtr_groups: dict[str, set[str]],
    group_repay: pd.DataFrame,
    days_in_month: int,
    tl_latest_day: int,
) -> dict:
    """构建 module_monthly_js。"""
    module_monthly_js: dict = {}
    for mk in modules_list:
        dtr_groups = submodule_dtr_groups.get(mk, set())
        m_grp = group_repay[group_repay["owner_group"].isin(dtr_groups)]
        if len(m_grp) > 0:
            total_tgt = m_grp["target_repay_principal"].astype(float).sum()
            total_act = m_grp["actual_repay_principal"].astype(float).sum()
            month_target = round(total_tgt)
            current_actual = round(total_act)
        else:
            month_target = 0
            current_actual = 0
        module_monthly_js[mk] = {
            "monthTarget": month_target,
            "monthDays": days_in_month,
            "currentDay": tl_latest_day,
            "currentActual": current_actual,
        }
    return module_monthly_js


def build_risk_module_groups(
    modules_list: list[str],
    group_perf_js: dict,
) -> dict:
    """构建 risk_module_groups（浅拷贝 group_perf_js 字段）。"""
    risk_module_groups: dict = {}
    for mk in modules_list:
        risk_module_groups[mk] = [
            {
                "group": g["name"],
                "target": g["target"],
                "actual": g["actual"],
                "achievement": g["achievement"],
                "calls": g["calls"],
                "connectRate": g["connectRate"],
                "ptpRate": g["ptpRate"],
                "callLossRate": g.get("callLossRate"),
                "attendance": g["attendance"],
            }
            for g in group_perf_js.get(mk, [])
        ]
    return risk_module_groups


def build_today_agent_targets(
    agent_repay: pd.DataFrame,
    all_groups: list[str],
) -> tuple[dict, dict]:
    """构建 today_agent_target_by_group 和 today_agent_target_by_group_agent。"""
    today_dt = pd.Timestamp.now().normalize()
    norm_to_group = {norm(g): g for g in all_groups}

    today_agent_target_by_group: dict = {}
    today_agent_target_by_group_agent: dict = {}

    today_rows = agent_repay[agent_repay["dt"] == today_dt].copy()
    if len(today_rows) > 0:
        today_rows["grp_norm"] = today_rows["owner_group"].apply(norm)
        today_rows["name_norm"] = today_rows["owner_name"].apply(
            lambda x: str(x).strip().lower() if pd.notna(x) else ""
        )

        for g_norm, sub in today_rows.groupby("grp_norm"):
            canonical_group = norm_to_group.get(g_norm)
            if not canonical_group:
                continue
            today_agent_target_by_group[canonical_group] = float(
                sub["target_repay_principal"].fillna(0).sum()
            )
            agent_target_map: dict = {}
            for _, row in sub.iterrows():
                akey = str(row.get("name_norm", "")).strip().lower()
                if not akey:
                    continue
                agent_target_map[akey] = float(row.get("target_repay_principal", 0) or 0)
            today_agent_target_by_group_agent[canonical_group] = agent_target_map

    return today_agent_target_by_group, today_agent_target_by_group_agent


def build_tl_breakdown_by_date(
    daily_target_agent_breakdown: pd.DataFrame,
    all_groups: list[str],
    agent_perf_js: dict,
) -> dict:
    """构建 tl_breakdown_by_date。"""
    tl_breakdown_by_date: dict = {}
    if len(daily_target_agent_breakdown) == 0:
        for g in all_groups:
            tl_breakdown_by_date.setdefault(g, {})
        return tl_breakdown_by_date

    daily_target_agent_breakdown = daily_target_agent_breakdown.copy()
    daily_target_agent_breakdown["grp_norm"] = daily_target_agent_breakdown["owner_group"].apply(norm)
    daily_target_agent_breakdown["name_norm"] = daily_target_agent_breakdown["owner_name"].apply(
        lambda x: str(x).strip().lower() if pd.notna(x) else ""
    )

    # Build agent name maps
    group_agent_name_map: dict = {}
    for g in all_groups:
        mapping = {}
        for a in agent_perf_js.get(g, []):
            key = str(a.get("name", "")).strip().lower()
            if key:
                mapping[key] = a.get("name")
        group_agent_name_map[g] = mapping

    norm_to_group = {norm(g): g for g in all_groups}

    for _, row in daily_target_agent_breakdown.iterrows():
        g_norm = row.get("grp_norm", "")
        dt_val = row.get("dt")
        if not g_norm or pd.isna(dt_val):
            continue
        a_norm = str(row.get("name_norm", "") or "")
        g_canonical = norm_to_group.get(g_norm) or resolve_canonical_group_for_breakdown(
            row.get("owner_group"), a_norm, norm_to_group, all_groups, group_agent_name_map
        )
        if not g_canonical:
            continue
        dt_key = pd.to_datetime(dt_val).strftime("%Y-%m-%d")
        group_map = tl_breakdown_by_date.setdefault(g_canonical, {})
        date_rows = group_map.setdefault(dt_key, {"caseStage": {}, "principalStage": {}})

        case_k = str(row.get("case_stage", "") or "")
        principal_k = str(row.get("principal_stage", "") or "")
        a_display = group_agent_name_map.get(g_canonical, {}).get(
            a_norm, str(row.get("owner_name", "") or "").strip() or "--"
        )
        owing = float(row.get("owing_principal", 0) or 0)
        repay = float(row.get("repay_principal", 0) or 0)

        if case_k:
            k = f"{a_display}||{case_k}"
            c = date_rows["caseStage"].setdefault(k, {
                "agentName": a_display,
                "dimensionValue": case_k,
                "owingPrincipal": 0.0,
                "repayPrincipal": 0.0,
            })
            c["owingPrincipal"] += owing
            c["repayPrincipal"] += repay
        if principal_k:
            k = f"{a_display}||{principal_k}"
            p = date_rows["principalStage"].setdefault(k, {
                "agentName": a_display,
                "dimensionValue": principal_k,
                "owingPrincipal": 0.0,
                "repayPrincipal": 0.0,
            })
            p["owingPrincipal"] += owing
            p["repayPrincipal"] += repay

    # Finalize: dict → sorted list with repayRate
    for g in list(tl_breakdown_by_date.keys()):
        for d in list(tl_breakdown_by_date[g].keys()):
            for dim in ("caseStage", "principalStage"):
                rows = []
                for _, vals in tl_breakdown_by_date[g][d][dim].items():
                    owing = vals["owingPrincipal"]
                    repay = vals["repayPrincipal"]
                    rows.append({
                        "agentName": vals["agentName"],
                        "dimensionValue": vals["dimensionValue"],
                        "owingPrincipal": round(owing, 2),
                        "repayPrincipal": round(repay, 2),
                        "repayRate": round((repay / owing * 100), 2) if owing > 0 else None,
                    })
                rows.sort(key=lambda x: (x["dimensionValue"], x["agentName"]))
                tl_breakdown_by_date[g][d][dim] = rows

    for g in all_groups:
        tl_breakdown_by_date.setdefault(g, {})

    return tl_breakdown_by_date


def build_stl_breakdown_by_week(
    week_target_group_breakdown: pd.DataFrame,
    all_groups: list[str],
    modules_list: list[str],
) -> tuple[dict, bool]:
    """构建 stl_breakdown_by_week 和 has_stl_week_breakdown_data。"""
    stl_breakdown_by_week: dict = {}
    if len(week_target_group_breakdown) == 0:
        return stl_breakdown_by_week, False

    def _resolve_module_key_from_group_name(g):
        g_upper = str(g).strip().upper()
        if "LARGE" in g_upper:
            prefix = g_upper.split("-")[0] if "-" in g_upper else g_upper.split("_")[0]
            return f"{prefix}-Large"
        if "SMALL" in g_upper:
            prefix = g_upper.split("-")[0] if "-" in g_upper else g_upper.split("_")[0]
            return f"{prefix}-Small"
        return extract_module_key(g)

    # Build mapping for cross-sheet group name matching
    norm_prefix_to_group: dict = {}
    for g in all_groups:
        norm_prefix_to_group[norm(g)] = g
        g_clean = re.sub(r"(Module|Bucket)$", "", g, flags=re.IGNORECASE).strip()
        norm_prefix_to_group[norm(g_clean)] = g

    def _resolve_canonical_group_for_stl(owner_group):
        og = str(owner_group).strip()
        if og in all_groups:
            return og
        og_norm = norm(og)
        if og_norm in norm_prefix_to_group:
            return norm_prefix_to_group[og_norm]
        og_clean = re.sub(r"(Module|Bucket)$", "", og, flags=re.IGNORECASE).strip()
        og_clean_norm = norm(og_clean)
        if og_clean_norm in norm_prefix_to_group:
            return norm_prefix_to_group[og_clean_norm]
        return og

    week_target_group_breakdown = week_target_group_breakdown.copy()
    week_target_group_breakdown["module_key"] = week_target_group_breakdown["owner_group"].apply(
        _resolve_module_key_from_group_name
    )
    week_target_group_breakdown["group_name"] = week_target_group_breakdown["owner_group"].apply(
        _resolve_canonical_group_for_stl
    )

    for _, row in week_target_group_breakdown.iterrows():
        module_key = row.get("module_key")
        week_label = row.get("week")
        group_name = row.get("group_name")
        if not module_key or not week_label or not group_name:
            continue
        if module_key not in modules_list:
            continue
        if group_name not in all_groups:
            continue
        module_map = stl_breakdown_by_week.setdefault(module_key, {})
        week_map = module_map.setdefault(
            week_str_to_display(str(week_label)),
            {"caseStage": {}, "principalStage": {}},
        )

        case_k = str(row.get("case_stage", "") or "")
        principal_k = str(row.get("principal_stage", "") or "")
        owing = float(row.get("owing_principal", 0) or 0)
        repay = float(row.get("repay_principal", 0) or 0)

        if case_k:
            k = f"{group_name}||{case_k}"
            c = week_map["caseStage"].setdefault(k, {
                "groupName": group_name,
                "dimensionValue": case_k,
                "owingPrincipal": 0.0,
                "repayPrincipal": 0.0,
            })
            c["owingPrincipal"] += owing
            c["repayPrincipal"] += repay
        if principal_k:
            k = f"{group_name}||{principal_k}"
            p = week_map["principalStage"].setdefault(k, {
                "groupName": group_name,
                "dimensionValue": principal_k,
                "owingPrincipal": 0.0,
                "repayPrincipal": 0.0,
            })
            p["owingPrincipal"] += owing
            p["repayPrincipal"] += repay

    # Finalize: dict → sorted list with repayRate
    for mk in list(stl_breakdown_by_week.keys()):
        for wk in list(stl_breakdown_by_week[mk].keys()):
            for dim in ("caseStage", "principalStage"):
                rows = []
                for _, vals in stl_breakdown_by_week[mk][wk][dim].items():
                    owing = vals["owingPrincipal"]
                    repay = vals["repayPrincipal"]
                    rows.append({
                        "groupName": vals["groupName"],
                        "dimensionValue": vals["dimensionValue"],
                        "owingPrincipal": round(owing, 2),
                        "repayPrincipal": round(repay, 2),
                        "repayRate": round((repay / owing * 100), 2) if owing > 0 else None,
                    })
                rows.sort(key=lambda x: (x["dimensionValue"], x["groupName"]))
                stl_breakdown_by_week[mk][wk][dim] = rows

    has_stl_week_breakdown_data = len(stl_breakdown_by_week) > 0
    return stl_breakdown_by_week, has_stl_week_breakdown_data
