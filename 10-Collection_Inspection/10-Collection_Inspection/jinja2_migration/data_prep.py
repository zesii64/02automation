"""data_prep — Jinja2 迁移数据准备模块。

从 generate_v2_7.py (lines 84-1542) 抽取的数据处理逻辑，负责：
1. 加载 Excel 数据
2. 确定关键日期
3. 构建派生结构
4. 处理 natural_month_repay / process targets
5. 构建所有 JS 侧消费的 real_data 字段

入口函数：``build_context(excel_path, process_target_path=None) -> dict``
"""

from __future__ import annotations

import math
import re
from calendar import monthrange
from collections.abc import Iterable
from datetime import timedelta

import pandas as pd

from data_contract import TEMPLATE_CONTRACT_ID, PIPELINE_VERSION, validate_real_data_for_report
from data_prep_helpers import (
    build_consecutive_weeks_map,
    compute_consecutive_days,
    detect_day_only_cross_month_risk,
    extract_module_key,
    filter_report_month,
    format_week_range,
    get_week_label,
    map_group_to_dtr,
    module_key_to_bucket,
    norm,
    normalize_attd_rate_pct,
    normalize_week_label,
    parse_week_str,
    resolve_canonical_group_for_breakdown,
    sort_module_keys,
    week_start_dt,
    week_str_to_display,
)


# ============================================================================
# Section 0: Data loading
# ============================================================================
_SHEET_NAMES: tuple[str, ...] = (
    "tl_data",
    "stl_data",
    "agent_performance",
    "group_performance",
    "daily_target_agent_repay",
    "daily_target_group_repay",
    "ptp_agent_data",
    "ptp_group_data",
    "call_loss_agent_data",
    "call_loss_group_data",
    "natural_month_repay",
    "attd_group_daily_data",
    "attd_group_week_data",
    "daily_target_agent_breakdown",
    "week_target_group_breakdown",
)


def load_excel_sheets(excel_path: str) -> dict[str, pd.DataFrame]:
    """加载 Excel 所有 sheet 并执行基础清洗。

    Returns:
        dict 含 key: tl_data, stl_data, agent_perf, group_perf, daily_tr,
        agent_repay, group_repay, ptp_agent, ptp_group, cl_agent, cl_group,
        nat_month, attd_daily, attd_weekly, daily_target_agent_breakdown,
        week_target_group_breakdown
    """
    xl = pd.ExcelFile(excel_path)

    dfs: dict[str, pd.DataFrame] = {}
    dfs["tl_data"] = pd.read_excel(xl, "tl_data", index_col=0)
    dfs["stl_data"] = pd.read_excel(xl, "stl_data", index_col=0)
    dfs["agent_perf"] = pd.read_excel(xl, "agent_performance", index_col=0)
    dfs["group_perf"] = pd.read_excel(xl, "group_performance", index_col=0)
    dfs["daily_tr"] = pd.read_excel(xl, "daily_target_agent_repay", index_col=0)
    dfs["agent_repay"] = pd.read_excel(xl, "daily_target_agent_repay", index_col=0)
    dfs["group_repay"] = pd.read_excel(xl, "daily_target_group_repay", index_col=0)
    dfs["ptp_agent"] = pd.read_excel(xl, "ptp_agent_data", index_col=0)
    dfs["ptp_group"] = pd.read_excel(xl, "ptp_group_data", index_col=0)
    dfs["cl_agent"] = pd.read_excel(xl, "call_loss_agent_data", index_col=0)
    dfs["cl_group"] = pd.read_excel(xl, "call_loss_group_data", index_col=0)
    dfs["nat_month"] = pd.read_excel(xl, "natural_month_repay", index_col=0)
    dfs["attd_daily"] = pd.read_excel(xl, "attd_group_daily_data", index_col=0)
    dfs["attd_weekly"] = pd.read_excel(xl, "attd_group_week_data", index_col=0)
    dfs["daily_target_agent_breakdown"] = pd.read_excel(xl, "daily_target_agent_breakdown", index_col=0)
    dfs["week_target_group_breakdown"] = pd.read_excel(xl, "week_target_group_breakdown", index_col=0)

    # Strip whitespace
    dfs["tl_data"]["group_id"] = dfs["tl_data"]["group_id"].str.strip()
    dfs["agent_perf"]["group_id"] = dfs["agent_perf"]["group_id"].str.strip()
    dfs["group_perf"]["group_id"] = dfs["group_perf"]["group_id"].str.strip()
    dfs["daily_tr"]["owner_group"] = dfs["daily_tr"]["owner_group"].str.strip()
    dfs["agent_repay"]["owner_group"] = dfs["agent_repay"]["owner_group"].str.strip()
    dfs["group_repay"]["owner_group"] = dfs["group_repay"]["owner_group"].str.strip()
    dfs["ptp_agent"]["owner_group"] = dfs["ptp_agent"]["owner_group"].str.strip()
    dfs["cl_agent"]["group_name"] = dfs["cl_agent"]["group_name"].str.strip()
    dfs["cl_group"]["group_name"] = dfs["cl_group"]["group_name"].str.strip()
    dfs["attd_daily"]["group_id"] = dfs["attd_daily"]["group_id"].astype(str).str.strip()
    dfs["attd_weekly"]["group_id"] = dfs["attd_weekly"]["group_id"].astype(str).str.strip()
    dfs["daily_target_agent_breakdown"]["owner_group"] = dfs["daily_target_agent_breakdown"]["owner_group"].astype(str).str.strip()
    dfs["daily_target_agent_breakdown"]["owner_name"] = dfs["daily_target_agent_breakdown"]["owner_name"].astype(str).str.strip()
    dfs["week_target_group_breakdown"]["owner_group"] = dfs["week_target_group_breakdown"]["owner_group"].astype(str).str.strip()
    dfs["group_perf"]["week"] = dfs["group_perf"]["week"].astype(str)

    # Parse dates
    dfs["tl_data"]["dt"] = pd.to_datetime(dfs["tl_data"]["dt"])
    dfs["agent_perf"]["dt"] = pd.to_datetime(dfs["agent_perf"]["dt"])
    dfs["daily_tr"]["dt"] = pd.to_datetime(dfs["daily_tr"]["dt"])
    dfs["agent_repay"]["dt"] = pd.to_datetime(dfs["agent_repay"]["dt"])
    dfs["ptp_agent"]["dt"] = pd.to_datetime(dfs["ptp_agent"]["dt"])
    dfs["cl_agent"]["dt"] = pd.to_datetime(dfs["cl_agent"]["dt"])
    dfs["nat_month"]["dt_biz"] = pd.to_datetime(dfs["nat_month"]["dt_biz"])
    dfs["attd_daily"]["dt"] = pd.to_datetime(dfs["attd_daily"]["dt"])
    dfs["daily_target_agent_breakdown"]["dt"] = pd.to_datetime(dfs["daily_target_agent_breakdown"]["dt"])

    # Convert week columns to string
    for key in ("group_repay", "ptp_group", "cl_group", "group_perf", "attd_weekly", "week_target_group_breakdown"):
        dfs[key]["week"] = dfs[key]["week"].astype(str)

    return dfs


def _load_process_targets(path: str) -> pd.DataFrame:
    """加载 process_data_target.xlsx。"""
    try:
        return pd.read_excel(path, header=1)
    except Exception:
        return pd.DataFrame(columns=["module_key", "art_call_times", "connect_billhr"])


# ============================================================================
# Section 0.5: Key dates
# ============================================================================
def determine_key_dates(dfs: dict[str, pd.DataFrame]) -> dict:
    """从已加载数据确定 TL 最新日、STL 默认周、可用日期/周列表。"""
    RUN_YESTERDAY_DT = pd.Timestamp.now().normalize() - timedelta(days=1)

    agent_perf_dates = set(
        dfs["agent_perf"]
        .loc[dfs["agent_perf"]["dt"] <= RUN_YESTERDAY_DT, "dt"]
        .unique()
        .tolist()
    )
    agent_repay_dates = set(
        dfs["agent_repay"]
        .loc[dfs["agent_repay"]["dt"] <= RUN_YESTERDAY_DT, "dt"]
        .unique()
        .tolist()
    )
    ptp_agent_dates = set(
        dfs["ptp_agent"]
        .loc[dfs["ptp_agent"]["dt"] <= RUN_YESTERDAY_DT, "dt"]
        .unique()
        .tolist()
    )
    common_tl_dates = sorted(agent_perf_dates & agent_repay_dates & ptp_agent_dates)

    if common_tl_dates:
        TL_LATEST_DT = max(common_tl_dates)
    else:
        TL_CORE_MAX_DT = min(
            dfs["agent_perf"]["dt"].max(),
            dfs["agent_repay"]["dt"].max(),
            dfs["ptp_agent"]["dt"].max(),
        )
        TL_LATEST_DT = min(TL_CORE_MAX_DT, RUN_YESTERDAY_DT)

    TL_LATEST_STR = TL_LATEST_DT.strftime("%Y-%m-%d")
    TL_LATEST_DAY = TL_LATEST_DT.day
    REPORT_YEAR = TL_LATEST_DT.year
    REPORT_MONTH = TL_LATEST_DT.month

    all_weeks_sorted = sorted(dfs["group_repay"]["week"].unique(), key=week_start_dt)
    DEFAULT_STL_WEEK = all_weeks_sorted[-2] if len(all_weeks_sorted) >= 2 else all_weeks_sorted[-1]

    available_dates = sorted(
        [d.strftime("%Y-%m-%d") for d in dfs["agent_repay"]["dt"].unique() if pd.to_datetime(d) <= RUN_YESTERDAY_DT],
        reverse=True,
    )

    return {
        "RUN_YESTERDAY_DT": RUN_YESTERDAY_DT,
        "TL_LATEST_DT": TL_LATEST_DT,
        "TL_LATEST_STR": TL_LATEST_STR,
        "TL_LATEST_DAY": TL_LATEST_DAY,
        "REPORT_YEAR": REPORT_YEAR,
        "REPORT_MONTH": REPORT_MONTH,
        "DAYS_IN_MONTH": monthrange(REPORT_YEAR, REPORT_MONTH)[1],
        "all_weeks_sorted": all_weeks_sorted,
        "DEFAULT_STL_WEEK": DEFAULT_STL_WEEK,
        "available_dates": available_dates,
    }


# ============================================================================
# Section 0.8: Derived structures
# ============================================================================
def build_derived_structures(
    dfs: dict[str, pd.DataFrame], dates: dict
) -> dict:
    """构建 modules_list、submodule_groups、process_target_js、归一化列等。"""
    all_groups = sorted(dfs["tl_data"]["group_id"].unique().tolist())
    dfs["tl_data"]["group_module"] = dfs["tl_data"]["group_id"].apply(extract_module_key)

    submodule_groups: dict[str, list[str]] = {}
    for g in all_groups:
        mk = extract_module_key(g)
        submodule_groups.setdefault(mk, []).append(g)
    modules_list = sort_module_keys(list(submodule_groups.keys()))

    # Process targets
    process_target_js = _build_process_targets(dates.get("process_target_raw"), modules_list)

    submodule_dtr_groups = {
        mk: {map_group_to_dtr(g) for g in groups} for mk, groups in submodule_groups.items()
    }
    dtr_to_submodule = {map_group_to_dtr(g): extract_module_key(g) for g in all_groups}
    all_groups_norm = {norm(g): g for g in all_groups}

    # Normalized columns for cross-sheet joins
    _add_norm_columns(dfs)

    dfs["tl_data"]["group_module"] = dfs["tl_data"]["group_id"].apply(extract_module_key)

    return {
        "all_groups": all_groups,
        "submodule_groups": submodule_groups,
        "modules_list": modules_list,
        "process_target_js": process_target_js,
        "submodule_dtr_groups": submodule_dtr_groups,
        "dtr_to_submodule": dtr_to_submodule,
        "all_groups_norm": all_groups_norm,
    }


def _add_norm_columns(dfs: dict[str, pd.DataFrame]) -> None:
    """为各 DataFrame 添加 grp_norm / name_norm 列。"""
    dfs["agent_repay"]["grp_norm"] = dfs["agent_repay"]["owner_group"].apply(norm)
    dfs["agent_repay"]["name_norm"] = dfs["agent_repay"]["owner_name"].apply(
        lambda x: str(x).strip().lower() if pd.notna(x) else ""
    )
    dfs["ptp_agent"]["grp_norm"] = dfs["ptp_agent"]["owner_group"].apply(norm)
    dfs["ptp_agent"]["name_norm"] = dfs["ptp_agent"]["owner_name"].apply(
        lambda x: str(x).strip().lower() if pd.notna(x) else ""
    )
    dfs["cl_agent"]["grp_norm"] = dfs["cl_agent"]["group_name"].apply(norm)
    dfs["cl_agent"]["name_norm"] = dfs["cl_agent"]["owner_name"].apply(
        lambda x: str(x).strip().lower() if pd.notna(x) else ""
    )
    dfs["group_repay"]["grp_norm"] = dfs["group_repay"]["owner_group"].apply(norm)
    dfs["ptp_group"]["grp_norm"] = dfs["ptp_group"]["owner_group"].apply(norm)
    dfs["cl_group"]["grp_norm"] = dfs["cl_group"]["group_name"].apply(norm)
    dfs["attd_daily"]["grp_norm"] = dfs["attd_daily"]["group_id"].apply(norm)
    dfs["attd_weekly"]["grp_norm"] = dfs["attd_weekly"]["group_id"].apply(norm)


def _build_process_targets(process_target_raw: pd.DataFrame | None, modules_list: list[str]) -> dict:
    """构建 process_target_js dict。"""
    process_target_js: dict = {}
    if process_target_raw is None or len(process_target_raw) == 0:
        return process_target_js

    raw_cols_lower = {c: str(c).strip().lower() for c in process_target_raw.columns}

    def pick_col(needles_any, needles_all=None):
        needles_all = needles_all or []
        for c, lc in raw_cols_lower.items():
            if needles_all and not all(n in lc for n in needles_all):
                continue
            if any(n in lc for n in needles_any):
                return c
        return None

    module_key_col = pick_col(["module_key", "module"]) or process_target_raw.columns[0]
    art_call_times_col = pick_col(["art_call_times", "art_call"])
    call_billmin_col = pick_col(["call_billmin", "connect_billmin", "billmin"])
    call_billhr_col = pick_col(["call_billhr", "connect_billhr", "billhr"])

    pt_keep = [module_key_col]
    if art_call_times_col is not None:
        pt_keep.append(art_call_times_col)
    call_billmin_for_pt = call_billmin_col if call_billmin_col is not None else call_billhr_col
    if call_billmin_for_pt is not None:
        pt_keep.append(call_billmin_for_pt)
    if call_billhr_col is not None:
        pt_keep.append(call_billhr_col)

    pt_df = process_target_raw[pt_keep].copy()
    cols = ["module_key"]
    if art_call_times_col is not None:
        cols.append("art_call_times")
    cols.append("call_billmin_raw")
    if call_billhr_col is not None:
        cols.append("connect_billhr")
    pt_df.columns = cols

    pt_df["module"] = pt_df["module_key"].astype(str).str.strip().str.replace("_", "-", regex=False)
    pt_df["art_call_times"] = (
        pd.to_numeric(pt_df["art_call_times"], errors="coerce")
        if "art_call_times" in pt_df.columns
        else pd.Series(dtype=float)
    )
    pt_df["call_billmin_raw"] = pd.to_numeric(pt_df["call_billmin_raw"], errors="coerce")

    if "connect_billhr" not in pt_df.columns:
        pt_df["connect_billhr"] = pd.Series([None] * len(pt_df), dtype=float)
    else:
        pt_df["connect_billhr"] = pd.to_numeric(pt_df["connect_billhr"], errors="coerce")

    for _, r in pt_df.iterrows():
        mk = r["module"]
        if mk not in modules_list:
            continue
        art_call = (
            int(round(float(r["art_call_times"])))
            if "art_call_times" in r and pd.notna(r["art_call_times"])
            else None
        )
        call_billmin_target = (
            float(r["call_billmin_raw"]) * 60 if pd.notna(r["call_billmin_raw"]) else None
        )
        connect_raw = float(r["connect_billhr"]) if pd.notna(r["connect_billhr"]) else None
        connect_pct = (
            round(connect_raw * 100, 1)
            if connect_raw is not None and connect_raw <= 1.0
            else (round(connect_raw, 1) if connect_raw is not None else None)
        )
        process_target_js[mk] = {
            "artCallTimes": art_call,
            "callBillminRawTarget": call_billmin_target,
            "connectBillhrPct": connect_pct,
        }

    return process_target_js


# ============================================================================
# Section 0.9: Natural month pre-processing
# ============================================================================
def preprocess_natural_month(
    dfs: dict[str, pd.DataFrame], modules_list: list[str], dates: dict
) -> dict:
    """处理 natural_month_repay，构建 target_nm_dict / module_nm_dict / module_group_nm_dict。"""
    nat_month = dfs["nat_month"].copy()
    nat_month["group_name"] = nat_month["group_name"].str.strip()
    nat_month["agent_bucket"] = nat_month["agent_bucket"].str.strip()

    # 不再过滤到仅当前报告月，保留数据中所有月份
    nat_buckets = set(nat_month["agent_bucket"].dropna().unique().tolist())

    # target_nm_dict: {bucket: {date_str: repay_rate}}
    target_nm_dict: dict = {}
    for _, row in nat_month[nat_month["group_name"] == "Target"].iterrows():
        bucket = row["agent_bucket"]
        date_str = pd.to_datetime(row["dt_biz"]).strftime("%Y-%m-%d")
        rr = float(row["repay_rate"]) * 100
        target_nm_dict.setdefault(bucket, {})[date_str] = round(rr, 4)

    # module_nm_dict: {mk: {date_str: repay_rate}}
    module_nm_dict: dict = {}
    module_group_nm_dict: dict = {}
    nontar_nm = nat_month[nat_month["group_name"] != "Target"]
    submodule_groups = _build_submodule_groups(dfs)

    for mk in modules_list:
        mk_bucket = module_key_to_bucket(mk, nat_buckets)
        mk_nm = nontar_nm[nontar_nm["agent_bucket"] == mk_bucket]
        module_nm_dict[mk] = {}
        module_group_nm_dict[mk] = {}
        for dt_biz, day_data in mk_nm.groupby("dt_biz"):
            date_str = pd.to_datetime(dt_biz).strftime("%Y-%m-%d")
            total_repay = day_data["repay_principal"].astype(float).sum()
            total_owing = day_data["start_owing_principal"].astype(float).sum()
            rr = total_repay / total_owing * 100 if total_owing > 0 else 0.0
            module_nm_dict[mk][date_str] = round(rr, 4)
        for g in submodule_groups.get(mk, []):
            g_nm = mk_nm[mk_nm["group_name"] == g.strip()]
            group_daily: dict = {}
            for dt_biz, day_data in g_nm.groupby("dt_biz"):
                date_str = pd.to_datetime(dt_biz).strftime("%Y-%m-%d")
                total_repay = day_data["repay_principal"].astype(float).sum()
                total_owing = day_data["start_owing_principal"].astype(float).sum()
                rr = total_repay / total_owing * 100 if total_owing > 0 else 0.0
                group_daily[date_str] = round(rr, 4)
            module_group_nm_dict[mk][g] = group_daily

    return {
        "nat_buckets": nat_buckets,
        "target_nm_dict": target_nm_dict,
        "module_nm_dict": module_nm_dict,
        "module_group_nm_dict": module_group_nm_dict,
        "nat_month": nat_month,
    }


def _build_submodule_groups(dfs: dict[str, pd.DataFrame]) -> dict[str, list[str]]:
    all_groups = sorted(dfs["tl_data"]["group_id"].unique().tolist())
    result: dict[str, list[str]] = {}
    for g in all_groups:
        mk = extract_module_key(g)
        result.setdefault(mk, []).append(g)
    return result


# ============================================================================
# Section 1: TL Data
# ============================================================================
def build_tl_data(
    dfs: dict[str, pd.DataFrame],
    structures: dict,
    nm_data: dict,
    dates: dict,
) -> dict:
    """构建 tl_data_js。"""
    all_groups = structures["all_groups"]
    submodule_dtr_groups = structures["submodule_dtr_groups"]
    process_target_js = structures["process_target_js"]
    target_nm_dict = nm_data["target_nm_dict"]
    module_nm_dict = nm_data["module_nm_dict"]
    module_group_nm_dict = nm_data["module_group_nm_dict"]
    nat_buckets = nm_data.get("nat_buckets", set())

    TL_LATEST_DT = dates["TL_LATEST_DT"]
    TL_LATEST_STR = dates["TL_LATEST_STR"]
    TL_LATEST_DAY = dates["TL_LATEST_DAY"]
    RUN_YESTERDAY_DT = dates["RUN_YESTERDAY_DT"]
    REPORT_YEAR = dates["REPORT_YEAR"]
    REPORT_MONTH = dates["REPORT_MONTH"]
    DAYS_IN_MONTH = dates["DAYS_IN_MONTH"]

    daily_tr = dfs["daily_tr"]
    tl_data = dfs["tl_data"]
    attd_daily = dfs["attd_daily"]

    # 计算数据中所有存在的年月，用于构建完整的日维度序列
    all_year_months: set[tuple[int, int]] = set()
    for df, col in [(daily_tr, "dt"), (nm_data["nat_month"], "dt_biz"), (attd_daily, "dt")]:
        dts = pd.to_datetime(df[col])
        all_year_months.update((dt.year, dt.month) for dt in dts.dropna().unique())
    sorted_year_months = sorted(all_year_months)

    # Module avg achievement (used in TL data)
    latest_dtr_agg = (
        daily_tr[daily_tr["dt"] == TL_LATEST_DT]
        .groupby("owner_group", as_index=False)
        .agg(
            target=("target_repay_principal", lambda x: x.astype(float).sum()),
            actual=("actual_repay_principal", lambda x: x.astype(float).sum()),
            owing=("daily_owing_principal", lambda x: x.astype(float).sum()),
        )
        .set_index("owner_group")
    )

    module_avg_ach: dict = {}
    for mk, dtr_groups in submodule_dtr_groups.items():
        sub = latest_dtr_agg[latest_dtr_agg.index.isin(dtr_groups)]
        if len(sub) > 0:
            t = sub["target"].sum()
            a = sub["actual"].sum()
            module_avg_ach[mk] = round(a / t * 100, 1) if t > 0 else 0.0
        else:
            module_avg_ach[mk] = 0.0

    tl_data_js: dict = {}
    groups_sorted = sorted(all_groups)

    for group in groups_sorted:
        group_rows = tl_data[tl_data["group_id"] == group]
        group_module = extract_module_key(group)
        dtr_name = map_group_to_dtr(group)
        g_norm = norm(group)
        dtr_norm = norm(dtr_name)
        grp_norm_candidates = {g_norm, dtr_norm}

        if dtr_name in latest_dtr_agg.index:
            row = latest_dtr_agg.loc[dtr_name]
            target = round(float(row["target"]))
            actual = round(float(row["actual"]))
            achievement = round(float(row["actual"]) / float(row["target"]) * 100, 1) if float(row["target"]) > 0 else 0.0
            gap = max(0.0, float(row["target"]) - float(row["actual"]))
        else:
            target = actual = achievement = gap = 0.0

        latest_tl_g = group_rows[group_rows["dt"] == TL_LATEST_DT]
        module_tl = tl_data[(tl_data["group_module"] == group_module) & (tl_data["dt"] == TL_LATEST_DT)]
        if len(latest_tl_g) > 0 and len(module_tl) > 0:
            g_calls = float(latest_tl_g["total_calls"].iloc[0])
            g_conn = float(latest_tl_g["connect_rate"].iloc[0]) * 100
            avg_calls = float(module_tl["total_calls"].mean())
            avg_conn = float(module_tl["connect_rate"].mean()) * 100
            call_gap = round(g_calls - avg_calls)
            connect_gap = round(g_conn - avg_conn, 1)
        else:
            call_gap = connect_gap = 0

        # Daily drill-down
        g_dtr = (
            daily_tr[daily_tr["owner_group"] == dtr_name]
            .groupby("dt", as_index=False)
            .agg(
                target=("target_repay_principal", lambda x: x.astype(float).sum()),
                actual=("actual_repay_principal", lambda x: x.astype(float).sum()),
                owing=("daily_owing_principal", lambda x: x.astype(float).sum()),
            )
            .set_index("dt")
        )
        module_bucket = module_key_to_bucket(group_module, nat_buckets)
        module_target_nm = target_nm_dict.get(module_bucket, {})
        module_nm_daily = module_nm_dict.get(group_module, {})
        group_nm_daily = module_group_nm_dict.get(group_module, {}).get(group, {})

        g_attd_daily = attd_daily[attd_daily["grp_norm"].isin(grp_norm_candidates)]
        attd_daily_by_date: dict = {}
        if len(g_attd_daily) > 0:
            for dt_key, day_df in g_attd_daily.groupby("dt"):
                dt_str = pd.to_datetime(dt_key).strftime("%Y-%m-%d")
                attd_vals = pd.to_numeric(day_df["attd_rate_8h"], errors="coerce").dropna()
                attd_daily_by_date[dt_str] = normalize_attd_rate_pct(attd_vals.mean()) if len(attd_vals) > 0 else None

        days_series = []
        for year, month in sorted_year_months:
            days_in_month = monthrange(year, month)[1]
            for day in range(1, days_in_month + 1):
                date_str = f"{year}-{month:02d}-{day:02d}"
                in_cutoff = date_str <= TL_LATEST_STR
                day_rows = g_dtr[g_dtr.index == pd.Timestamp(date_str)]

                nm_trr = module_target_nm.get(date_str, None)
                nm_rr = module_nm_daily.get(date_str, None) if in_cutoff else None
                g_nm_rr = group_nm_daily.get(date_str, None) if in_cutoff else None
                attd_val = attd_daily_by_date.get(date_str)

                if len(day_rows) > 0:
                    r = day_rows.iloc[0]
                    tgt = round(float(r["target"])) if in_cutoff else None
                    act = round(float(r["actual"])) if in_cutoff else None
                    owing = float(r["owing"])
                    rr = round(float(r["actual"]) / owing * 100, 4) if (in_cutoff and owing > 0) else None
                else:
                    tgt = act = rr = None

                days_series.append({
                    "date": date_str,
                    "target": tgt,
                    "actual": act,
                    "repayRate": rr,
                    "nmRepayRate": g_nm_rr,
                    "targetRepayRate": nm_trr,
                    "moduleRepayRate": nm_rr,
                    "attendanceRate": attd_val,
                })

        tl_data_js[group] = {
            "groupModule": group_module,
            "target": target,
            "actual": actual,
            "achievement": achievement,
            "moduleAvg": module_avg_ach.get(group_module, 0.0),
            "gap": round(gap),
            "callGap": call_gap,
            "connectGap": connect_gap,
            "days": days_series,
        }

    return tl_data_js


# ============================================================================
# Section 2: Agent Performance
# ============================================================================
def build_agent_performance(
    dfs: dict[str, pd.DataFrame],
    structures: dict,
    dates: dict,
) -> tuple[dict, dict]:
    """构建 agent_perf_js 和 agent_perf_by_date_js。

    Returns:
        (agent_perf_js, agent_perf_by_date_js)
    """
    all_groups = structures["all_groups"]

    TL_LATEST_DT = dates["TL_LATEST_DT"]
    RUN_YESTERDAY_DT = dates["RUN_YESTERDAY_DT"]

    agent_perf = dfs["agent_perf"]
    agent_repay = dfs["agent_repay"]
    ptp_agent = dfs["ptp_agent"]
    cl_agent = dfs["cl_agent"]

    agent_perf_js: dict = {}
    agent_perf_by_date_js: dict = {}

    for group in all_groups:
        g_norm = norm(group)
        dtr_norm = norm(map_group_to_dtr(group))
        grp_norm_candidates = {g_norm, dtr_norm}
        agents_in_group = agent_perf[agent_perf["group_id"] == group]["agent_id"].unique()
        agent_perf_by_date_js[group] = {}

        for agent_name in agents_in_group:
            a_norm = str(agent_name).strip().lower()

            # Repay metrics
            ar = agent_repay[
                (agent_repay["grp_norm"].isin(grp_norm_candidates))
                & (agent_repay["name_norm"] == a_norm)
                & (agent_repay["dt"] == TL_LATEST_DT)
            ]
            if len(ar) > 0:
                ar_tgt_sum = float(ar["target_repay_principal"].astype(float).sum())
                ar_act_sum = float(ar["actual_repay_principal"].astype(float).sum())
                ar_tgt = round(ar_tgt_sum)
                ar_act = round(ar_act_sum)
                ar_ach = round(ar_act_sum / ar_tgt_sum * 100, 1) if ar_tgt_sum > 0 else 0.0
            else:
                ar_tgt = ar_act = 0
                ar_ach = 0.0

            # Consecutive days
            ar_all = agent_repay[
                (agent_repay["grp_norm"].isin(grp_norm_candidates))
                & (agent_repay["name_norm"] == a_norm)
            ]
            cd = compute_consecutive_days(ar_all, RUN_YESTERDAY_DT) if len(ar_all) > 0 else 0

            # Call metrics
            ap_a = agent_perf[
                (agent_perf["group_id"] == group)
                & (agent_perf["dt"] == TL_LATEST_DT)
                & (agent_perf["agent_id"] == agent_name)
            ]

            calls, conn_r, attd = 0, 0.0, 0
            cover_times_val = None
            call_times_val = None
            art_call_times_val = None
            call_billmin_val = None
            single_call_duration_val = None

            if len(ap_a) > 0:
                art_call_times_val, call_times_val, calls = _extract_call_metrics(ap_a)
                cover_times_val = _safe_int(ap_a, "cover_times")
                call_billmin_val = _safe_float_first(ap_a, ["call_billmin", "connect_billmin"])
                single_call_duration_val = _safe_float_first(ap_a, ["single_call_duration"])
                conn_r = _resolve_connect_rate(ap_a, calls)
                attd = _resolve_attendance(ap_a)

            # PTP
            ptp_val = _extract_ptp(ptp_agent, grp_norm_candidates, a_norm, TL_LATEST_DT)

            # Call loss
            cl_val = _extract_call_loss(cl_agent, grp_norm_candidates, a_norm, TL_LATEST_DT)

            agent_key = str(agent_name)
            agent_perf_js.setdefault(group, []).append({
                "name": agent_key,
                "consecutiveDays": cd,
                "target": ar_tgt,
                "actual": ar_act,
                "achievement": ar_ach,
                "calls": calls,
                "connectRate": conn_r,
                "coverTimes": cover_times_val,
                "callTimes": call_times_val,
                "artCallTimes": art_call_times_val,
                "callBillmin": call_billmin_val,
                "singleCallDuration": single_call_duration_val,
                "ptp": ptp_val,
                "callLossRate": cl_val,
                "attendance": attd,
            })

            # Daily drill-down
            hist_map = _build_agent_daily_history(
                agent_repay, agent_perf, ptp_agent, cl_agent,
                grp_norm_candidates, a_norm, group, agent_name,
            )
            agent_perf_by_date_js[group][agent_key] = hist_map

    return agent_perf_js, agent_perf_by_date_js


def _extract_call_metrics(ap_a: pd.DataFrame) -> tuple[int | None, int | None, int]:
    """从 agent_perf 行提取 art_call_times / call_times / calls。"""
    art_call_times_val = None
    call_times_val = None
    if "art_call_times" in ap_a.columns and pd.notna(ap_a["art_call_times"]).any():
        art_call_times_val = int(round(float(ap_a["art_call_times"].astype(float).sum())))
    if "call_times" in ap_a.columns and pd.notna(ap_a["call_times"]).any():
        call_times_val = int(round(float(ap_a["call_times"].astype(float).sum())))
    if art_call_times_val is not None:
        calls = art_call_times_val
    elif call_times_val is not None:
        calls = call_times_val
    else:
        calls = 0
    return art_call_times_val, call_times_val, calls


def _resolve_connect_rate(df: pd.DataFrame, calls: int) -> float:
    """连接率解析：优先 connect_rate → call_connect_times → connect_times → call_billhr。"""
    if "connect_rate" in df.columns and pd.notna(df["connect_rate"]).any():
        conn_val = float(df["connect_rate"].astype(float).mean())
        return round(conn_val * 100, 1)
    if "call_connect_times" in df.columns:
        connects = int(round(float(df["call_connect_times"].astype(float).sum())))
        return round(connects / calls * 100, 1) if calls > 0 else 0.0
    if "connect_times" in df.columns:
        connects = int(round(float(df["connect_times"].astype(float).sum())))
        return round(connects / calls * 100, 1) if calls > 0 else 0.0
    if "call_billhr" in df.columns and pd.notna(df["call_billhr"]).any():
        conn_val = float(df["call_billhr"].astype(float).mean())
        return round(conn_val * 100, 1)
    return 0.0


def _resolve_attendance(df: pd.DataFrame) -> int:
    """考勤率：is_full_attendance → headcount。"""
    if "is_full_attendance" in df.columns:
        full_att = int(df["is_full_attendance"].max()) if pd.notna(df["is_full_attendance"]).any() else 0
        if "work_hours" in df.columns:
            wh = float(df["work_hours"].mean()) if pd.notna(df["work_hours"]).any() else 0.0
            return 100 if full_att == 1 else min(100, round(wh / 8 * 100))
        return 100 if full_att == 1 else 0
    if "headcount" in df.columns:
        return 100 if float(df["headcount"].fillna(0).max()) > 0 else 0
    return 0


def _safe_int(df: pd.DataFrame, col: str) -> int | None:
    if col in df.columns and pd.notna(df[col]).any():
        return int(round(float(df[col].astype(float).sum())))
    return None


def _safe_float_first(df: pd.DataFrame, cols: list[str]) -> float | None:
    for c in cols:
        if c in df.columns and pd.notna(df[c]).any():
            return float(df[c].astype(float).mean())
    return None


def _extract_ptp(
    ptp_agent: pd.DataFrame, grp_norm_candidates: set, a_norm: str, dt: pd.Timestamp
) -> float | None:
    ptp_row = ptp_agent[
        (ptp_agent["grp_norm"].isin(grp_norm_candidates))
        & (ptp_agent["name_norm"] == a_norm)
        & (ptp_agent["dt"] == dt)
    ]
    ptp_valid = ptp_row["today_ptp_repay_rate"].dropna() if len(ptp_row) > 0 else pd.Series(dtype=float)
    return round(float(ptp_valid.iloc[0]) * 100, 1) if len(ptp_valid) > 0 else None


def _extract_call_loss(
    cl_agent: pd.DataFrame, grp_norm_candidates: set, a_norm: str, dt: pd.Timestamp
) -> float | None:
    cl_row = cl_agent[
        (cl_agent["grp_norm"].isin(grp_norm_candidates))
        & (cl_agent["name_norm"] == a_norm)
        & (cl_agent["dt"] == dt)
    ]
    cl_valid = cl_row["call_loss_rate"].dropna() if len(cl_row) > 0 else pd.Series(dtype=float)
    return round(float(cl_valid.iloc[0]) * 100, 1) if len(cl_valid) > 0 else None


def _build_agent_daily_history(
    agent_repay: pd.DataFrame,
    agent_perf: pd.DataFrame,
    ptp_agent: pd.DataFrame,
    cl_agent: pd.DataFrame,
    grp_norm_candidates: set,
    a_norm: str,
    group: str,
    agent_name: str,
) -> dict:
    """构建 agent_perf_by_date 单 agent 的每日历史。"""
    hist_map: dict = {}

    # Repay history
    ar_hist = agent_repay[
        (agent_repay["grp_norm"].isin(grp_norm_candidates))
        & (agent_repay["name_norm"] == a_norm)
    ]
    if len(ar_hist) > 0:
        ar_hist_daily = ar_hist.groupby("dt", as_index=False).agg(
            target=("target_repay_principal", lambda x: x.astype(float).sum()),
            actual=("actual_repay_principal", lambda x: x.astype(float).sum()),
        )
        for _, hr in ar_hist_daily.iterrows():
            dt_str = pd.to_datetime(hr["dt"]).strftime("%Y-%m-%d")
            tgt = float(hr["target"])
            act = float(hr["actual"])
            hist_map[dt_str] = {
                "target": round(tgt),
                "actual": round(act),
                "achievement": round(act / tgt * 100, 1) if tgt > 0 else 0.0,
            }

    # Process metrics history
    ap_hist = agent_perf[
        (agent_perf["group_id"] == group) & (agent_perf["agent_id"] == agent_name)
    ]
    if len(ap_hist) > 0:
        agg_map = _build_agent_daily_agg_map(ap_hist)
        ap_hist_daily = ap_hist.groupby("dt", as_index=False).agg(**agg_map)
        for _, hr in ap_hist_daily.iterrows():
            dt_str = pd.to_datetime(hr["dt"]).strftime("%Y-%m-%d")
            entry = _extract_agent_daily_entry(hr)
            hist_map.setdefault(dt_str, {}).update(entry)

    # PTP history
    ptp_hist = ptp_agent[
        (ptp_agent["grp_norm"].isin(grp_norm_candidates))
        & (ptp_agent["name_norm"] == a_norm)
    ]
    if len(ptp_hist) > 0:
        for dt_val, day_df in ptp_hist.groupby("dt"):
            dt_str = pd.to_datetime(dt_val).strftime("%Y-%m-%d")
            ptp_valid = day_df["today_ptp_repay_rate"].dropna()
            ptp_d = round(float(ptp_valid.iloc[0]) * 100, 1) if len(ptp_valid) > 0 else None
            hist_map.setdefault(dt_str, {})["ptp"] = ptp_d

    # Call loss history
    cl_hist = cl_agent[
        (cl_agent["grp_norm"].isin(grp_norm_candidates))
        & (cl_agent["name_norm"] == a_norm)
    ]
    if len(cl_hist) > 0:
        for dt_val, day_df in cl_hist.groupby("dt"):
            dt_str = pd.to_datetime(dt_val).strftime("%Y-%m-%d")
            cl_valid = day_df["call_loss_rate"].dropna()
            cl_d = round(float(cl_valid.iloc[0]) * 100, 1) if len(cl_valid) > 0 else None
            hist_map.setdefault(dt_str, {})["callLossRate"] = cl_d

    return hist_map


def _build_agent_daily_agg_map(ap_hist: pd.DataFrame) -> dict:
    agg_map: dict = {}
    if "art_call_times" in ap_hist.columns:
        agg_map["calls"] = ("art_call_times", lambda x: x.astype(float).sum())
        agg_map["artCallTimes"] = ("art_call_times", lambda x: x.astype(float).sum())
    if "call_times" in ap_hist.columns:
        if "calls" not in agg_map:
            agg_map["calls"] = ("call_times", lambda x: x.astype(float).sum())
        agg_map["callTimes"] = ("call_times", lambda x: x.astype(float).sum())
    if "cover_times" in ap_hist.columns:
        agg_map["coverTimes"] = ("cover_times", lambda x: x.astype(float).sum())
    if "connect_rate" in ap_hist.columns:
        agg_map["connect_rate"] = ("connect_rate", "mean")
    if "call_connect_times" in ap_hist.columns:
        agg_map["call_connects"] = ("call_connect_times", lambda x: x.astype(float).sum())
    elif "connect_times" in ap_hist.columns:
        agg_map["connects"] = ("connect_times", lambda x: x.astype(float).sum())
    if "call_billhr" in ap_hist.columns:
        agg_map["call_billhr"] = ("call_billhr", "mean")
    if "call_billmin" in ap_hist.columns:
        agg_map["callBillmin"] = ("call_billmin", "mean")
    elif "connect_billmin" in ap_hist.columns:
        agg_map["callBillmin"] = ("connect_billmin", "mean")
    if "single_call_duration" in ap_hist.columns:
        agg_map["singleCallDuration"] = ("single_call_duration", "mean")
    if "work_hours" in ap_hist.columns:
        agg_map["work_hours"] = ("work_hours", "mean")
    if "is_full_attendance" in ap_hist.columns:
        agg_map["full_attendance"] = ("is_full_attendance", "max")
    if "headcount" in ap_hist.columns:
        agg_map["headcount"] = ("headcount", "max")
    return agg_map


def _extract_agent_daily_entry(hr: pd.Series) -> dict:
    calls_d = int(round(float(hr["calls"]))) if ("calls" in hr and pd.notna(hr["calls"])) else 0

    if "connect_rate" in hr and pd.notna(hr["connect_rate"]):
        conn_r_d = round(float(hr["connect_rate"]) * 100, 1)
    elif "call_connects" in hr and pd.notna(hr["call_connects"]):
        connects_d = int(round(float(hr["call_connects"])))
        conn_r_d = round(connects_d / calls_d * 100, 1) if calls_d > 0 else 0.0
    elif "connects" in hr and pd.notna(hr["connects"]):
        connects_d = int(round(float(hr["connects"])))
        conn_r_d = round(connects_d / calls_d * 100, 1) if calls_d > 0 else 0.0
    elif "call_billhr" in hr and pd.notna(hr["call_billhr"]):
        conn_r_d = round(float(hr["call_billhr"]) * 100, 1)
    else:
        conn_r_d = 0.0

    coverTimes_d = int(round(float(hr["coverTimes"]))) if ("coverTimes" in hr and pd.notna(hr["coverTimes"])) else None
    callTimes_d = int(round(float(hr["callTimes"]))) if ("callTimes" in hr and pd.notna(hr["callTimes"])) else None
    artCallTimes_d = int(round(float(hr["artCallTimes"]))) if ("artCallTimes" in hr and pd.notna(hr["artCallTimes"])) else None
    callBillmin_d = round(float(hr["callBillmin"]), 2) if ("callBillmin" in hr and pd.notna(hr["callBillmin"])) else None
    singleCallDuration_d = round(float(hr["singleCallDuration"]), 2) if ("singleCallDuration" in hr and pd.notna(hr["singleCallDuration"])) else None

    if "full_attendance" in hr and pd.notna(hr["full_attendance"]):
        full_att_d = int(hr["full_attendance"])
        if "work_hours" in hr and pd.notna(hr["work_hours"]):
            wh_d = float(hr["work_hours"])
            attd_d = 100 if full_att_d == 1 else min(100, round(wh_d / 8 * 100))
        else:
            attd_d = 100 if full_att_d == 1 else 0
    elif "headcount" in hr and pd.notna(hr["headcount"]):
        attd_d = 100 if float(hr["headcount"]) > 0 else 0
    else:
        attd_d = 0

    return {
        "calls": calls_d,
        "connectRate": conn_r_d,
        "coverTimes": coverTimes_d,
        "callTimes": callTimes_d,
        "artCallTimes": artCallTimes_d,
        "callBillmin": callBillmin_d,
        "singleCallDuration": singleCallDuration_d,
        "attendance": attd_d,
    }


# ============================================================================
# Section 3: Group Performance
# ============================================================================
def build_group_performance(
    dfs: dict[str, pd.DataFrame],
    structures: dict,
    dates: dict,
) -> tuple[dict, dict, dict]:
    """构建 group_perf_js, group_perf_by_week_js, group_consecutive_by_week_js。"""
    modules_list = structures["modules_list"]
    submodule_groups = structures["submodule_groups"]

    DEFAULT_STL_WEEK = dates["DEFAULT_STL_WEEK"]

    group_repay = dfs["group_repay"]
    ptp_group = dfs["ptp_group"]
    cl_group = dfs["cl_group"]
    attd_weekly = dfs["attd_weekly"]
    group_perf = dfs["group_perf"]

    group_perf_js: dict = {}
    group_perf_by_week_js: dict = {}
    group_consecutive_by_week_js: dict = {}

    for mk in modules_list:
        mk_groups = submodule_groups.get(mk, [])
        group_perf_by_week_js[mk] = {}
        group_consecutive_by_week_js[mk] = {}

        groups_list = []
        for group in mk_groups:
            g_norm = norm(group)
            dtr_norm = norm(map_group_to_dtr(group))
            grp_norm_candidates = {g_norm, dtr_norm}

            # Weekly repay
            gr = group_repay[
                (group_repay["grp_norm"].isin(grp_norm_candidates))
                & (group_repay["week"] == DEFAULT_STL_WEEK)
            ]
            if len(gr) > 0:
                w_tgt_sum = float(gr["target_repay_principal"].sum())
                w_act_sum = float(gr["actual_repay_principal"].sum())
                w_tgt = round(w_tgt_sum)
                w_act = round(w_act_sum)
                w_ach = round(w_act_sum / w_tgt_sum * 100, 1) if w_tgt_sum > 0 else 0.0
            else:
                w_tgt = w_act = 0
                w_ach = 0.0

            # PTP
            ptp_rate = _extract_ptp_weekly(ptp_group, grp_norm_candidates, DEFAULT_STL_WEEK)

            # Call loss
            cl_rate = _extract_call_loss_weekly(cl_group, grp_norm_candidates, DEFAULT_STL_WEEK)

            # Attendance
            attd = _extract_attendance_weekly(attd_weekly, grp_norm_candidates, DEFAULT_STL_WEEK)

            # Call metrics from group_performance
            calls_pa, conn_r, cover_times_pa, call_times_pa, art_call_times_pa, call_billmin_pa, single_call_duration_pa = (
                _extract_group_call_metrics(group_perf, group, DEFAULT_STL_WEEK)
            )

            # Weekly drill-down history
            week_map = _build_group_weekly_history(
                group_repay, group_perf, cl_group, attd_weekly,
                grp_norm_candidates, group,
            )
            consecutive_map = build_consecutive_weeks_map(week_map)
            cw_default = int(consecutive_map.get(week_str_to_display(DEFAULT_STL_WEEK), 0))

            groups_list.append({
                "name": group,
                "consecutiveWeeks": cw_default,
                "target": w_tgt,
                "actual": w_act,
                "achievement": w_ach,
                "calls": calls_pa,
                "connectRate": conn_r,
                "coverTimes": cover_times_pa,
                "callTimes": call_times_pa,
                "artCallTimes": art_call_times_pa if art_call_times_pa is not None else calls_pa,
                "callBillmin": call_billmin_pa,
                "singleCallDuration": single_call_duration_pa,
                "ptpRate": ptp_rate,
                "callLossRate": cl_rate,
                "attendance": attd,
            })
            group_perf_by_week_js[mk][group] = week_map
            group_consecutive_by_week_js[mk][group] = consecutive_map

        group_perf_js[mk] = groups_list

    return group_perf_js, group_perf_by_week_js, group_consecutive_by_week_js


def _extract_ptp_weekly(
    ptp_group: pd.DataFrame, grp_norm_candidates: set, week: str
) -> float | None:
    ptp_g = ptp_group[
        (ptp_group["grp_norm"].isin(grp_norm_candidates))
        & (ptp_group["week"] == week)
    ]
    ptp_g_valid = ptp_g["today_ptp_repay_rate"].dropna() if len(ptp_g) > 0 else pd.Series(dtype=float)
    return round(float(ptp_g_valid.iloc[0]) * 100, 1) if len(ptp_g_valid) > 0 else None


def _extract_call_loss_weekly(
    cl_group: pd.DataFrame, grp_norm_candidates: set, week: str
) -> float | None:
    cl_g = cl_group[
        (cl_group["grp_norm"].isin(grp_norm_candidates))
        & (cl_group["week"] == week)
    ]
    cl_g_valid = cl_g["call_loss_rate"].dropna() if len(cl_g) > 0 else pd.Series(dtype=float)
    return round(float(cl_g_valid.iloc[0]) * 100, 1) if len(cl_g_valid) > 0 else None


def _extract_attendance_weekly(
    attd_weekly: pd.DataFrame, grp_norm_candidates: set, week: str
) -> float | None:
    attd_w = attd_weekly[
        (attd_weekly["grp_norm"].isin(grp_norm_candidates))
        & (attd_weekly["week"] == week)
    ]
    attd_w_valid = (
        pd.to_numeric(attd_w["attd_rate_8h"], errors="coerce").dropna()
        if len(attd_w) > 0
        else pd.Series(dtype=float)
    )
    return normalize_attd_rate_pct(attd_w_valid.mean()) if len(attd_w_valid) > 0 else None


def _extract_group_call_metrics(
    group_perf: pd.DataFrame, group: str, week: str
) -> tuple:
    gp_lw = group_perf[
        (group_perf["group_id"] == group) & (group_perf["week"] == week)
    ]
    cover_times_pa = call_times_pa = art_call_times_pa = None
    call_billmin_pa = single_call_duration_pa = None
    calls_pa = conn_r = 0

    if len(gp_lw) > 0:
        if "art_call_times" in gp_lw.columns and pd.notna(gp_lw["art_call_times"]).any():
            calls_pa = round(float(gp_lw["art_call_times"].iloc[0]))
            art_call_times_pa = int(round(float(gp_lw["art_call_times"].iloc[0])))
        elif "call_times" in gp_lw.columns and pd.notna(gp_lw["call_times"]).any():
            calls_pa = round(float(gp_lw["call_times"].iloc[0]))
            call_times_pa = int(round(float(gp_lw["call_times"].iloc[0])))
        else:
            tot_calls = float(gp_lw["total_calls"].iloc[0]) if "total_calls" in gp_lw.columns else 0.0
            headcount = float(gp_lw["headcount"].iloc[0]) if "headcount" in gp_lw.columns else 0.0
            calls_pa = round(tot_calls / headcount) if headcount > 0 else 0

        if "cover_times" in gp_lw.columns and pd.notna(gp_lw["cover_times"]).any():
            cover_times_pa = int(round(float(gp_lw["cover_times"].iloc[0])))
        if "call_times" in gp_lw.columns and pd.notna(gp_lw["call_times"]).any():
            call_times_pa = int(round(float(gp_lw["call_times"].iloc[0])))
        if "art_call_times" in gp_lw.columns and pd.notna(gp_lw["art_call_times"]).any():
            art_call_times_pa = int(round(float(gp_lw["art_call_times"].iloc[0])))

        if "call_billhr" in gp_lw.columns and pd.notna(gp_lw["call_billhr"]).any():
            conn_r = round(float(gp_lw["call_billhr"].iloc[0]) * 100, 1)
        elif "total_connect" in gp_lw.columns and "total_calls" in gp_lw.columns:
            tot_calls = float(gp_lw["total_calls"].iloc[0])
            tot_conn = float(gp_lw["total_connect"].iloc[0])
            conn_r = round(tot_conn / tot_calls * 100, 1) if tot_calls > 0 else 0.0
        elif "connect_rate" in gp_lw.columns:
            conn_r = round(float(gp_lw["connect_rate"].iloc[0]) * 100, 1)
        else:
            conn_r = 0.0

        if "call_billmin" in gp_lw.columns and pd.notna(gp_lw["call_billmin"]).any():
            call_billmin_pa = float(gp_lw["call_billmin"].iloc[0])
        elif "connect_billmin" in gp_lw.columns and pd.notna(gp_lw["connect_billmin"]).any():
            call_billmin_pa = float(gp_lw["connect_billmin"].iloc[0])
        if "single_call_duration" in gp_lw.columns and pd.notna(gp_lw["single_call_duration"]).any():
            single_call_duration_pa = float(gp_lw["single_call_duration"].iloc[0])

    return calls_pa, conn_r, cover_times_pa, call_times_pa, art_call_times_pa, call_billmin_pa, single_call_duration_pa


def _build_group_weekly_history(
    group_repay: pd.DataFrame,
    group_perf: pd.DataFrame,
    cl_group: pd.DataFrame,
    attd_weekly: pd.DataFrame,
    grp_norm_candidates: set,
    group: str,
) -> dict:
    """构建 group_perf_by_week 的周历史 map。"""
    week_map: dict = {}

    # Repay history
    gr_hist = group_repay[group_repay["grp_norm"].isin(grp_norm_candidates)]
    if len(gr_hist) > 0:
        gr_hist_weekly = gr_hist.groupby("week", as_index=False).agg(
            target=("target_repay_principal", lambda x: x.astype(float).sum()),
            actual=("actual_repay_principal", lambda x: x.astype(float).sum()),
        )
        for _, wr in gr_hist_weekly.iterrows():
            wk = str(wr["week"])
            tgt = float(wr["target"])
            act = float(wr["actual"])
            week_map[week_str_to_display(wk)] = {
                "target": round(tgt),
                "actual": round(act),
                "achievement": round(act / tgt * 100, 1) if tgt > 0 else 0.0,
            }

    # Process metrics history
    gp_hist = group_perf[group_perf["group_id"] == group]
    if len(gp_hist) > 0:
        gp_hist_weekly = gp_hist.groupby("week", as_index=False).first()
        for _, gwr in gp_hist_weekly.iterrows():
            wk = str(gwr["week"])
            wk_label = week_str_to_display(wk)

            coverTimes_w = (
                int(round(float(gwr["cover_times"])))
                if "cover_times" in gp_hist_weekly.columns and pd.notna(gwr.get("cover_times"))
                else None
            )
            callTimes_w = (
                int(round(float(gwr["call_times"])))
                if "call_times" in gp_hist_weekly.columns and pd.notna(gwr.get("call_times"))
                else None
            )
            artCallTimes_w = (
                int(round(float(gwr["art_call_times"])))
                if "art_call_times" in gp_hist_weekly.columns and pd.notna(gwr.get("art_call_times"))
                else None
            )
            callBillmin_w = (
                float(gwr["call_billmin"])
                if "call_billmin" in gp_hist_weekly.columns and pd.notna(gwr.get("call_billmin"))
                else (
                    float(gwr["connect_billmin"])
                    if "connect_billmin" in gp_hist_weekly.columns and pd.notna(gwr.get("connect_billmin"))
                    else None
                )
            )
            singleCallDuration_w = (
                float(gwr["single_call_duration"])
                if "single_call_duration" in gp_hist_weekly.columns and pd.notna(gwr.get("single_call_duration"))
                else None
            )

            if "art_call_times" in gp_hist_weekly.columns and pd.notna(gwr.get("art_call_times")):
                calls_w = round(float(gwr["art_call_times"]))
            else:
                tot_calls_w = float(gwr.get("total_calls", 0.0))
                headcount_w = float(gwr.get("headcount", 0.0))
                calls_w = round(tot_calls_w / headcount_w) if headcount_w > 0 else 0

            if "call_billhr" in gp_hist_weekly.columns and pd.notna(gwr.get("call_billhr")):
                conn_w = round(float(gwr["call_billhr"]) * 100, 1)
            elif "connect_rate" in gp_hist_weekly.columns and pd.notna(gwr.get("connect_rate")):
                conn_w = round(float(gwr["connect_rate"]) * 100, 1)
            elif (
                pd.notna(gwr.get("total_connect"))
                and pd.notna(gwr.get("total_calls"))
                and float(gwr.get("total_calls", 0.0)) > 0
            ):
                conn_w = round(float(gwr["total_connect"]) / float(gwr["total_calls"]) * 100, 1)
            else:
                conn_w = 0.0

            week_map.setdefault(wk_label, {}).update({
                "calls": calls_w,
                "connectRate": conn_w,
                "coverTimes": coverTimes_w,
                "callTimes": callTimes_w,
                "artCallTimes": artCallTimes_w if artCallTimes_w is not None else calls_w,
                "callBillmin": callBillmin_w,
                "singleCallDuration": singleCallDuration_w,
            })

    # Call loss history
    cl_hist_week = cl_group[cl_group["grp_norm"].isin(grp_norm_candidates)]
    if len(cl_hist_week) > 0:
        for _, cr in cl_hist_week.iterrows():
            wk_label = week_str_to_display(str(cr["week"]))
            clv = pd.to_numeric(cr["call_loss_rate"], errors="coerce")
            week_map.setdefault(wk_label, {})["callLossRate"] = (
                round(float(clv) * 100, 1) if pd.notna(clv) else None
            )

    # Attendance history
    attd_hist_week = attd_weekly[attd_weekly["grp_norm"].isin(grp_norm_candidates)]
    if len(attd_hist_week) > 0:
        attd_weekly_agg = attd_hist_week.groupby("week", as_index=False).agg(
            attendance=("attd_rate_8h", lambda x: pd.to_numeric(x, errors="coerce").mean())
        )
        for _, ar in attd_weekly_agg.iterrows():
            wk_label = week_str_to_display(str(ar["week"]))
            week_map.setdefault(wk_label, {})["attendance"] = normalize_attd_rate_pct(
                ar.get("attendance")
            )

    return week_map


# ============================================================================
# Section 4: STL Data
# ============================================================================
def build_stl_data(
    dfs: dict[str, pd.DataFrame],
    structures: dict,
) -> dict:
    """构建 stl_data_js（module 级周汇总）。"""
    modules_list = structures["modules_list"]
    submodule_dtr_groups = structures["submodule_dtr_groups"]

    group_repay = dfs["group_repay"]

    stl_data_js: dict = {}
    for mk in modules_list:
        dtr_groups = submodule_dtr_groups.get(mk, set())
        mk_grp_repay = group_repay[group_repay["owner_group"].isin(dtr_groups)]
        mk_weeks = sorted(mk_grp_repay["week"].unique(), key=week_start_dt)

        weekly = (
            mk_grp_repay.groupby("week")
            .agg(
                target=("target_repay_principal", lambda x: x.astype(float).sum()),
                actual=("actual_repay_principal", lambda x: x.astype(float).sum()),
            )
            .reset_index()
            .sort_values("week")
        )
        weekly["achievement"] = weekly.apply(
            lambda r: round(r["actual"] / r["target"] * 100, 1) if r["target"] > 0 else 0.0,
            axis=1,
        )

        weeks_list = []
        for _, w in weekly.iterrows():
            weeks_list.append({
                "weekLabel": week_str_to_display(str(w["week"])),
                "target": round(float(w["target"])),
                "actual": round(float(w["actual"])),
                "achievement": float(w["achievement"]),
            })

        if weeks_list:
            lw = weeks_list[-1]
            prev_actual = weeks_list[-2]["actual"] if len(weeks_list) > 1 else 0
            tpct = (lw["actual"] - prev_actual) / prev_actual * 100 if prev_actual > 0 else 0.0
            trend_str = ("+" if tpct >= 0 else "") + f"{tpct:.1f}%"
            latest_gap = max(0, lw["target"] - lw["actual"])
        else:
            lw = {"target": 0, "actual": 0, "achievement": 0.0}
            trend_str = "N/A"
            latest_gap = 0

        stl_data_js[mk] = {
            "target": lw["target"],
            "actual": lw["actual"],
            "achievement": lw["achievement"],
            "lastWeek": weeks_list[-2]["actual"] if len(weeks_list) > 1 else 0,
            "trend": trend_str,
            "gap": round(latest_gap),
            "weeks": weeks_list,
            "allWeeks": [week_str_to_display(w) for w in mk_weeks],
        }

    return stl_data_js


# ============================================================================
# build_context — 主入口
# ============================================================================
def build_context(
    excel_path: str,
    process_target_path: str | None = None,
    *,
    warnings: set[str] | None = None,
) -> dict:
    """加载 Excel 数据 → 处理 → 构建 real_data dict。

    Args:
        excel_path: 260318_output_automation_v3.xlsx 路径
        process_target_path: process_data_target.xlsx 路径（可选）
        warnings: 用于收集数据质量警告的集合

    Returns:
        real_data dict，字段名 camelCase，与 JS 侧期望对齐
    """
    from data_prep_payloads import (
        build_agent_table_rows,
        build_anomaly_agents,
        build_anomaly_groups,
        build_group_table_rows,
        build_module_daily_trends,
        build_module_monthly,
        build_risk_module_groups,
        build_stl_breakdown_by_week,
        build_tl_breakdown_by_date,
        build_today_agent_targets,
    )

    wset = warnings if warnings is not None else set()

    # 0. Load data
    print("Loading Excel data (v3)...")
    dfs = load_excel_sheets(excel_path)

    # Normalize week labels
    for key in ("group_repay", "ptp_group", "cl_group", "group_perf", "attd_weekly", "week_target_group_breakdown"):
        dfs[key]["week"] = dfs[key]["week"].apply(
            lambda ws, w=wset: normalize_week_label(ws, warnings=w)
        )

    # All groups
    all_groups = sorted(dfs["tl_data"]["group_id"].unique().tolist())

    # 0.5. Key dates
    dates = determine_key_dates(dfs)
    print(f"  TL latest date    : {dates['TL_LATEST_STR']}")
    print(f"  All weeks         : {dates['all_weeks_sorted']}")
    print(f"  Default STL week  : {dates['DEFAULT_STL_WEEK']}")
    if wset:
        print(f"  Data warnings     : {len(wset)}")

    # Load process targets
    process_target_raw = None
    if process_target_path:
        try:
            process_target_raw = pd.read_excel(process_target_path, header=1)
        except Exception:
            process_target_raw = pd.DataFrame(columns=["module_key", "art_call_times", "connect_billhr"])
    else:
        process_target_raw = pd.DataFrame(columns=["module_key", "art_call_times", "connect_billhr"])
    dates["process_target_raw"] = process_target_raw

    # 0.8. Derived structures
    structures = build_derived_structures(dfs, dates)
    all_groups = structures["all_groups"]
    modules_list = structures["modules_list"]
    submodule_groups = structures["submodule_groups"]
    submodule_dtr_groups = structures["submodule_dtr_groups"]
    process_target_js = structures["process_target_js"]

    # 0.9. Natural month
    nm_data = preprocess_natural_month(dfs, modules_list, dates)

    # 1-4. Core data
    tl_data_js = build_tl_data(dfs, structures, nm_data, dates)
    agent_perf_js, agent_perf_by_date_js = build_agent_performance(dfs, structures, dates)
    group_perf_js, group_perf_by_week_js, group_consecutive_by_week_js = build_group_performance(
        dfs, structures, dates
    )
    stl_data_js = build_stl_data(dfs, structures)

    # 5-8. Payloads
    default_week_label = week_str_to_display(dates["DEFAULT_STL_WEEK"])
    anomaly_groups = build_anomaly_groups(
        modules_list, submodule_groups,
        group_consecutive_by_week_js, group_perf_by_week_js, default_week_label,
    )
    anomaly_agents = build_anomaly_agents(agent_perf_js, tl_data_js)

    # Anomaly table rows with module headers pre-computed (avoids Jinja2 state tracking)
    group_table_rows = build_group_table_rows(anomaly_groups)
    agent_table_rows = build_agent_table_rows(anomaly_agents)

    module_daily_js = build_module_daily_trends(
        modules_list, nm_data["module_nm_dict"], nm_data["target_nm_dict"],
        nm_data.get("nat_buckets", set()),
        dates["REPORT_YEAR"], dates["REPORT_MONTH"],
        dates["DAYS_IN_MONTH"], dates["TL_LATEST_DAY"],
    )
    module_monthly_js = build_module_monthly(
        modules_list, submodule_dtr_groups, dfs["group_repay"],
        dates["DAYS_IN_MONTH"], dates["TL_LATEST_DAY"],
    )
    risk_module_groups = build_risk_module_groups(modules_list, group_perf_js)

    # 9. Extra drilldown payloads
    today_agent_target_by_group, today_agent_target_by_group_agent = build_today_agent_targets(
        dfs["agent_repay"], all_groups,
    )
    tl_breakdown_by_date = build_tl_breakdown_by_date(
        dfs["daily_target_agent_breakdown"], all_groups, agent_perf_js,
    )
    stl_breakdown_by_week, has_stl_week_breakdown_data = build_stl_breakdown_by_week(
        dfs["week_target_group_breakdown"], all_groups, modules_list,
    )

    # ========================
    # Assemble real_data
    # ========================
    real_data = {
        "dataDate": dates["TL_LATEST_STR"],
        "dataDay": dates["TL_LATEST_DAY"],
        "availableDates": dates["available_dates"],
        "availableWeeks": [week_str_to_display(w) for w in dates["all_weeks_sorted"]],
        "defaultStlWeek": week_str_to_display(dates["DEFAULT_STL_WEEK"]),
        "modules": modules_list,
        "groups": all_groups,
        "tlData": tl_data_js,
        "stlData": stl_data_js,
        "agentPerformance": agent_perf_js,
        "agentPerformanceByDate": agent_perf_by_date_js,
        "groupPerformance": group_perf_js,
        "groupPerformanceByWeek": group_perf_by_week_js,
        "groupConsecutiveWeeksByWeek": group_consecutive_by_week_js,
        "anomalyGroups": anomaly_groups,
        "anomalyAgents": anomaly_agents,
        # Pre-rendered table rows with module headers (for Jinja2 templates)
        "anomalyGroupTableRows": group_table_rows,
        "anomalyAgentTableRows": agent_table_rows,
        "processTargets": process_target_js,
        "riskModuleGroups": risk_module_groups,
        "moduleDailyTrends": module_daily_js,
        "moduleMonthly": module_monthly_js,
        "todayAgentTargetByGroup": today_agent_target_by_group,
        "todayAgentTargetByGroupAgent": today_agent_target_by_group_agent,
        "tlBreakdownByDate": tl_breakdown_by_date,
        "stlBreakdownByWeek": stl_breakdown_by_week,
        "hasStlWeekBreakdownData": has_stl_week_breakdown_data,
        "templateContractId": TEMPLATE_CONTRACT_ID,
        "pipelineVersion": PIPELINE_VERSION,
    }

    validate_real_data_for_report(real_data)

    # Log warnings
    if wset:
        print(f"  Total data warnings: {len(wset)}")
        for w in sorted(wset)[:10]:
            print(f"    - {w}")

    return real_data
