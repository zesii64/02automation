# -*- coding: utf-8 -*-
"""
Collection inspection - daily report (read local Excel -> metrics -> simple anomalies -> HTML).

Data: collection_inspection_data_local.xlsx in parent dir (from download script) or 0_basic_data.xlsx in Core.
Output: reports/Inspection_Report_YYYY-MM-DD.html
Sections: Risk overview, By product, By batch recovery (with Attribution), Contactability, Anomalies & recommendations.
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Paths: script under scripts/, project root is parent
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Data file candidates（优先 943 下载后放入 data/ 的文件）
LOCAL_EXCEL = PROJECT_ROOT / "collection_inspection_data_local.xlsx"
DATA_DIR_EXCEL = SCRIPT_DIR / "data" / "collection_inspection_data_local.xlsx"
CORE_EXCEL = Path(r"D:\0_phirisk\11-Agent\Core_Digital_Assets\10-Collection_Inspection\0_basic_data.xlsx")


def find_excel():
    """Prefer: 本目录 data/ 下 > 项目根目录 > Core 样本."""
    if DATA_DIR_EXCEL.exists():
        return str(DATA_DIR_EXCEL)
    if LOCAL_EXCEL.exists():
        return str(LOCAL_EXCEL)
    if CORE_EXCEL.exists():
        return str(CORE_EXCEL)
    return None


def read_sheet(path, sheet_name):
    """Read Excel sheet by name; return None if missing."""
    try:
        import pandas as pd
        df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
        return df
    except Exception:
        return None


def read_sheet_maybe_chunked(path, base_name):
    """Read base_name sheet; if 943 分片写入则合并 vintage_risk + vintage_risk_2 + ..."""
    import re
    df = read_sheet(path, base_name)
    if df is None:
        return None
    try:
        import pandas as pd
        xl = pd.ExcelFile(path, engine="openpyxl")
        # 分片名 pattern: vintage_risk_2, vintage_risk_3, ...
        extra = [s for s in xl.sheet_names if re.match(r"^" + re.escape(base_name) + r"_\d+$", s)]
        if not extra:
            return df
        key = lambda s: int(s.split("_")[-1])
        chunks = [df] + [pd.read_excel(xl, sheet_name=s) for s in sorted(extra, key=key)]
        return pd.concat(chunks, ignore_index=True)
    except Exception:
        return df


def _calc_risk_metrics(df_sub):
    """Helper: Calculate risk & conversion metrics for a dataframe subset.
    [v3.3 Upgrade]: Uses Safe Denominator logic (Partial Maturity).
    Only counts rows that have passed the maturity period for each metric.
    """
    if df_sub.empty:
        return {}
    
    res = {}
    # v3.6: Use loan_cnt if available
    if "loan_cnt" in df_sub.columns:
        res["rows"] = int(df_sub["loan_cnt"].sum())
    else:
        res["rows"] = len(df_sub)
    
    # Pre-calc lags for Safe Denominator
    today = pd.Timestamp.now().normalize()
    if "due_date" in df_sub.columns:
        dates = pd.to_datetime(df_sub["due_date"])
        lags = (today - dates).dt.days
    else:
        # Fallback: assume all mature if no date
        lags = pd.Series([999] * len(df_sub), index=df_sub.index)

    # 1. Base (Entrant / Overdue) - Lag >= 1 (T+1)
    # Usually Entrant is visible next day.
    owing = df_sub["owing_principal"].sum()
    if owing > 0:
        res["overdue_rate"] = round(df_sub["overdue_principal"].sum() / owing, 4)

    # Helper for Safe Denominator
    def get_rate(dpd_col, denom_col, min_lag):
        mask = lags >= min_lag
        if mask.any():
            sub = df_sub[mask]
            # Use specific denom col if exists, else owing
            denom = sub[denom_col].sum() if denom_col in sub.columns else sub["owing_principal"].sum()
            num = sub[dpd_col].sum() if dpd_col in sub.columns else 0
            return round(num / denom, 4) if denom > 0 else None
        return None

    # 2. Risk Buckets
    # DPD1 (d2): Needs Lag >= 2 (T+2)
    res["dpd1"] = get_rate("d2_principal", "owing_principal", 2)
    
    # DPD5 (d6): Needs Lag >= 6 (T+6)
    res["dpd5"] = get_rate("d6_principal", "owing_principal_d6", 6)
    
    # DPD7 (d8): Needs Lag >= 8 (T+8)
    res["dpd7"] = get_rate("d8_principal", "owing_principal_d8", 8)
    
    # DPD15 (d16): Needs Lag >= 16
    res["dpd15"] = get_rate("d16_principal", "owing_principal_d16", 16)
    
    # DPD30 (d31): Needs Lag >= 31
    res["dpd30"] = get_rate("d31_principal", "owing_principal_d31", 31)

    # 4. Conversion Rates
    conn_base = df_sub["conn_conv_base"].sum() if "conn_conv_base" in df_sub.columns else 0
    ptp_base = df_sub["ptp_conv_base"].sum() if "ptp_conv_base" in df_sub.columns else 0

    if conn_base > 0 and "conn_conv_repay" in df_sub.columns:
        res["connect_conversion"] = round(df_sub["conn_conv_repay"].sum() / conn_base, 4)
    if ptp_base > 0 and "ptp_conv_repay" in df_sub.columns:
        res["ptp_conversion"] = round(df_sub["ptp_conv_repay"].sum() / ptp_base, 4)
        
    return res


def _add_wow(curr, prev):
    """Calculate WoW delta for risk metrics.
    [v4.16] Always write _wow field when both curr/prev exist, even if delta=0 (→ stable).
    """
    # Added dpd1 to list
    metrics = ["overdue_rate", "dpd1", "dpd5", "dpd7", "dpd15", "dpd30", "connect_conversion", "ptp_conversion"]
    for m in metrics:
        if m in curr and m in prev:
            vc = curr[m]
            vp = prev[m]
            if isinstance(vc, (int, float)) and isinstance(vp, (int, float)):
                if vp != 0:
                    curr[f"{m}_wow"] = (vc - vp) / vp
                elif vc == 0:
                    curr[f"{m}_wow"] = 0.0  # [v4.16] Both zero → stable
                else:
                    curr[f"{m}_wow"] = 1.0  # prev=0, curr>0 → 100% increase

def compute_risk_attribution(df_curr, df_prev):
    """
    [v3.6 New] Risk Attribution Analysis (Structure Shift vs Rate Shift).
    [v4.0] Removed Connect Rate (Separated to Contactability Section).
    """
    if df_curr is None or df_curr.empty or df_prev is None or df_prev.empty:
        return {}

    # Helper: calc overall rate
    def _get_rate(d):
        o = d["owing_principal"].sum()
        ov = d["overdue_principal"].sum()
        return ov / o if o > 0 else 0.0

    rate_curr = _get_rate(df_curr)
    rate_prev = _get_rate(df_prev)
    total_delta = rate_curr - rate_prev

    attribution = {
        "overall": {
            "curr_rate": rate_curr,
            "prev_rate": rate_prev,
            "delta": total_delta
        },
        "dimensions": {}
    }

    # Dimensions to analyze
    # Map column -> Label
    dims = {
        "flag_principal": "Amount Segment",
        "model_bin": "Model Score",
        "mob": "MOB (Month on Book)"
    }
    
    # 1. Structural Dimensions (Amount, Model)
    for col, label in dims.items():
        if col not in df_curr.columns: continue
        
        # Group
        try:
            g_curr = df_curr.groupby(col)
            g_prev = df_prev.groupby(col) if col in df_prev.columns else None
            
            if g_prev is None: continue

            # Metrics per segment
            segments = set(g_curr.groups.keys()) | set(g_prev.groups.keys())
            
            rows = []
            total_vol_c = df_curr["owing_principal"].sum()
            total_vol_p = df_prev["owing_principal"].sum()
            
            for seg in segments:
                # Curr
                sub_c = g_curr.get_group(seg) if seg in g_curr.groups else pd.DataFrame()
                vol_c = sub_c["owing_principal"].sum() if not sub_c.empty else 0
                ov_c = sub_c["overdue_principal"].sum() if not sub_c.empty else 0
                
                # Prev
                sub_p = g_prev.get_group(seg) if seg in g_prev.groups else pd.DataFrame()
                vol_p = sub_p["owing_principal"].sum() if not sub_p.empty else 0
                ov_p = sub_p["overdue_principal"].sum() if not sub_p.empty else 0
                
                # Calc
                rate_c = ov_c / vol_c if vol_c > 0 else 0
                rate_p = ov_p / vol_p if vol_p > 0 else 0
                
                mix_c = vol_c / total_vol_c if total_vol_c > 0 else 0
                mix_p = vol_p / total_vol_p if total_vol_p > 0 else 0
                
                # Contribution to Total Delta
                contrib = (rate_c * mix_c) - (rate_p * mix_p)
                
                rows.append({
                    "segment": str(seg),
                    "curr_vol_pct": mix_c,
                    "curr_rate": rate_c,
                    "rate_delta": rate_c - rate_p,
                    "contribution": contrib
                })
                
            # Sort by Contribution descending (Positive = Caused Increase)
            rows.sort(key=lambda x: x["contribution"], reverse=True)
            attribution["dimensions"][label] = rows
        except Exception:
            pass
            
    # 2. Due Date (Batch) Analysis
    if "due_date" in df_curr.columns:
        g_date = df_curr.groupby(df_curr["due_date"].dt.strftime("%Y-%m-%d"))
        batch_rows = []
        total_vol = df_curr["owing_principal"].sum()
        
        for date, sub in g_date:
            vol = sub["owing_principal"].sum()
            ov = sub["overdue_principal"].sum()
            rate = ov / vol if vol > 0 else 0
            mix = vol / total_vol if total_vol > 0 else 0
            
            contrib = rate * mix 
            
            batch_rows.append({
                "segment": date,
                "curr_vol_pct": mix,
                "curr_rate": rate,
                "contribution": contrib
            })
        
        batch_rows.sort(key=lambda x: x["contribution"], reverse=True)
        attribution["dimensions"]["Due Batch (Risk Contrib)"] = batch_rows

    return attribution

def compute_term_monitoring_matrix(df):
    """
    [v4.9 New] 期限监控矩阵 (Term Monitoring Matrix).
    纵轴: 到期月 (due_date 按月聚合)
    横轴: MOB1~4 (period_no = 1~4)
    指标: overdue_rate, DPD5, DPD7, DPD15, DPD30
    筛选: user_type (All/新客/老客) + period_seq (All/1期/3期/6期)
    """
    if df is None or df.empty:
        return None
    
    required = ["due_date", "period_no", "owing_principal", "overdue_principal"]
    for c in required:
        if c not in df.columns:
            return None
    
    df_work = df.copy()
    df_work["due_date"] = pd.to_datetime(df_work["due_date"], errors="coerce")
    df_work = df_work.dropna(subset=["due_date"])
    df_work["due_month"] = df_work["due_date"].dt.strftime("%Y-%m")
    
    # 确定 MOB 范围 — 动态取所有可用 period_no
    all_pn = sorted([int(p) for p in df_work["period_no"].dropna().unique() if int(p) >= 1])
    mob_cols = all_pn if all_pn else [1, 2, 3, 4]
    
    # 指标定义: (名称, 分子列, 分母列)
    # overdue_rate = overdue_principal / owing_principal
    # DPD5 = d6_principal / owing_principal_d6  (表现期>=6天)
    # DPD7 = d8_principal / owing_principal  (近似, 无专用分母)
    # DPD15 = d16_principal / owing_principal_d16
    # DPD30 = d31_principal / owing_principal_d31
    metrics_def = [
        ("overdue_rate", "overdue_principal", "owing_principal"),
        ("DPD5",  "d6_principal",  "owing_principal_d6"),
        ("DPD7",  "d8_principal",  "owing_principal"),
        ("DPD15", "d16_principal", "owing_principal_d16"),
        ("DPD30", "d31_principal", "owing_principal_d31"),
    ]
    
    # 检测可用指标
    available_metrics = []
    for mname, num_col, den_col in metrics_def:
        if num_col in df_work.columns:
            available_metrics.append((mname, num_col, den_col))
    
    # 确保 overdue_rate 始终可用
    if not available_metrics:
        available_metrics = [("overdue_rate", "overdue_principal", "owing_principal")]
    
    # 确定筛选维度 — 新老客二元分类 (与主报告一致)
    # 规则: 新客=新客, 存量老客/新转化老客=老客 (即风险最高的type为新客, 其余合并为老客)
    user_types = ["all"]
    if "user_type" in df_work.columns:
        # 动态识别新客: 入催率最高的 user_type 认定为新客, 其余合并为老客
        try:
            risk_map = {}
            for ut_raw in df_work["user_type"].dropna().unique():
                sub_ut = df_work[df_work["user_type"] == ut_raw]
                ow = sub_ut["owing_principal"].sum()
                od = sub_ut["overdue_principal"].sum()
                risk_map[ut_raw] = od / ow if ow > 0 else 0
            if risk_map:
                new_type = max(risk_map, key=risk_map.get)
                # 将原始 user_type 映射为 "新客" / "老客"
                df_work["_ut_binary"] = df_work["user_type"].apply(
                    lambda x: "新客" if x == new_type else "老客 (含转化)"
                )
                user_types = ["all", "新客", "老客 (含转化)"]
            else:
                df_work["_ut_binary"] = "all"
        except Exception:
            df_work["_ut_binary"] = "all"
    else:
        df_work["_ut_binary"] = "all"
    
    period_seqs = ["all"]
    if "period_seq" in df_work.columns:
        for ps in sorted(df_work["period_seq"].dropna().unique()):
            period_seqs.append(str(int(ps)))
    
    all_months = sorted(df_work["due_month"].unique(), reverse=True)
    
    # result_data[(ut, ps, metric_name)] -> { month: { mob: rate } }
    result_data = {}
    
    for ut in user_types:
        for ps in period_seqs:
            # 筛选
            sub = df_work.copy()
            if ut != "all" and "_ut_binary" in sub.columns:
                sub = sub[sub["_ut_binary"] == ut]
            if ps != "all" and "period_seq" in sub.columns:
                sub = sub[sub["period_seq"].astype(int).astype(str) == ps]
            
            for mname, num_col, den_col in available_metrics:
                month_mob = {}
                for m in all_months:
                    mob_rates = {}
                    for mob in mob_cols:
                        cell = sub[(sub["due_month"] == m) & (sub["period_no"] == mob)]
                        numerator = cell[num_col].sum() if num_col in cell.columns else 0
                        denominator = cell[den_col].sum() if den_col in cell.columns else 0
                        rate = numerator / denominator if denominator > 0 else None
                        mob_rates[mob] = rate
                    month_mob[m] = mob_rates
                
                result_data[(ut, ps, mname)] = month_mob
    
    return {
        "months": all_months,
        "mob_cols": mob_cols,
        "data": result_data,
        "user_types": user_types,
        "period_seqs": period_seqs,
        "metrics": [m[0] for m in available_metrics]
    }


def compute_contact_stats(df):
    """
    [v4.0 New] Compute Contactability Stats (Trend & MTD).
    Returns: { "trend": [...], "mtd": {curr: .., prev: ..} }
    """
    if df is None or df.empty or "due_date" not in df.columns:
        return {}
    
    # Ensure datetime
    if not np.issubdtype(df["due_date"].dtype, np.datetime64):
        df = df.copy()
        df["due_date"] = pd.to_datetime(df["due_date"])
        
    out = {}
    
    # 1. Daily Trend (Last 30 days)
    today = pd.Timestamp.now().normalize()
    start_d = today - pd.Timedelta(days=30)
    
    sub = df[df["due_date"] >= start_d]
    g = sub.groupby(sub["due_date"].dt.strftime("%Y-%m-%d"))
    
    trend = []
    for date, grp in g:
        ov = grp["overdue_principal"].sum()
        conn = grp["conn_conv_base"].sum() if "conn_conv_base" in grp.columns else 0
        rate = conn / ov if ov > 0 else 0.0
        trend.append({"date": date, "rate": rate})
    
    out["trend"] = sorted(trend, key=lambda x: x["date"])
    
    # 2. MTD Comparison
    # Logic similar to compute_lift_analysis but simpler (just Curr vs Prev Month)
    # Align by progress days
    curr_month_start = today.replace(day=1)
    df_curr = df[df["due_date"] >= curr_month_start]
    
    if df_curr.empty:
        # Try infer
        max_d = df["due_date"].max()
        if pd.notna(max_d):
            curr_month_start = max_d.replace(day=1)
            df_curr = df[df["due_date"] >= curr_month_start]
    
    max_curr = df_curr["due_date"].max()
    if pd.isna(max_curr):
        out["mtd"] = {"curr": 0, "prev": 0, "progress": 0}
        return out
        
    progress = (max_curr - curr_month_start).days + 1
    
    # Curr Rate
    def calc_r(d):
        ov = d["overdue_principal"].sum()
        c = d["conn_conv_base"].sum() if "conn_conv_base" in d.columns else 0
        return c / ov if ov > 0 else 0.0
        
    r_curr = calc_r(df_curr)
    
    # Prev Month (Aligned)
    prev_start = (curr_month_start - pd.Timedelta(days=1)).replace(day=1)
    prev_end = prev_start + pd.Timedelta(days=progress - 1)
    
    df_prev = df[(df["due_date"] >= prev_start) & (df["due_date"] <= prev_end)]
    r_prev = calc_r(df_prev)
    
    out["mtd"] = {
        "curr": r_curr,
        "prev": r_prev,
        "progress": progress
    }
    
    return out

def compute_vintage_summary(df, mode='weekly'):
    """Vintage summary: Overall + Breakdowns (Model, User, Period, Amount).
    mode: 'daily' (Last 1 Day vs Prev 1 Day)
          'weekly' (Last 7 Days vs Prev 7 Days)
          'monthly' (Current Month vs Last Month)
    """
    if df is None or df.empty:
        return {}, []
    out = {}
    
    # 0. Split Windows
    df_curr = df
    df_prev = pd.DataFrame()
    meta_period = ""
    
    if "due_date" in df.columns:
        # Ensure datetime
        dates = pd.to_datetime(df["due_date"])
        max_date = dates.max()
        today = pd.Timestamp.now().normalize()
        
        if mode == 'daily':
            # Last 1 Day (Latest Batch) vs Previous Day
            # Ideally max_date vs max_date - 1
            curr_start = max_date
            curr_end = max_date
            prev_start = max_date - pd.Timedelta(days=1)
            prev_end = max_date - pd.Timedelta(days=1)
            meta_period = "Last 1 Day"
            
        elif mode == 'monthly':
            # Current Month vs Last Month
            # Note: This means "Full Month to Date" vs "Full Last Month"
            # Logic: All data in Current Month
            curr_month_start = max_date.replace(day=1)
            curr_start = curr_month_start
            curr_end = max_date
            
            prev_month_end = curr_month_start - pd.Timedelta(days=1)
            prev_month_start = prev_month_end.replace(day=1)
            prev_start = prev_month_start
            prev_end = prev_month_end
            meta_period = "Current Month"
            
        else: # weekly (default)
            # Last 7 Days vs Prev 7 Days
            curr_end = max_date
            curr_start = max_date - pd.Timedelta(days=6)
            prev_end = curr_start - pd.Timedelta(days=1)
            prev_start = prev_end - pd.Timedelta(days=6)
            meta_period = "Last 7 Days"
        
        df_curr = df[(dates >= curr_start) & (dates <= curr_end)]
        df_prev = df[(dates >= prev_start) & (dates <= prev_end)]
    
    # 1. Overall
    res_curr = _calc_risk_metrics(df_curr)
    res_prev = _calc_risk_metrics(df_prev)
    _add_wow(res_curr, res_prev)
    # Add meta info
    res_curr["meta_period"] = meta_period
        
    out["All"] = res_curr

    # 2. Dimensions to breakdown
    dims = {
        "model_bin": "Model",
        "user_type": "User",
        "period_no": "Period",
        "flag_principal": "Amount"
    }
    
    for col, label in dims.items():
        if col in df.columns:
            # Group Current
            try:
                # Get groups from Current
                curr_groups = df_curr.groupby(col)
                # Get groups from Prev (for matching)
                prev_groups = df_prev.groupby(col) if not df_prev.empty else None
                
                for name, grp_c in curr_groups:
                    key = f"{label}: {name}"
                    res_c = _calc_risk_metrics(grp_c)
                    
                    # Find matching prev group
                    if prev_groups is not None and name in prev_groups.groups:
                        grp_p = prev_groups.get_group(name)
                        res_p = _calc_risk_metrics(grp_p)
                        _add_wow(res_c, res_p)
                    
                    out[key] = res_c
            except Exception:
                pass

    # Anomalies check (Example: High Overdue in Current Window)
    anomalies = []
    for k, v in out.items():
        if v.get("overdue_rate", 0) > 0.5:
            anomalies.append(f"[{k}] Overdue rate {v['overdue_rate']} > 0.5")
            
    return out, anomalies


def compute_trend_by_period(df, period='D', limit=30):
    """
    Compute trend metrics by period.
    [v3 Upgrade]: Uses Safe Denominator logic to allow partial maturity display.
    (e.g. Jan month DPD5 will show Jan 1-29 weighted avg, ignoring Jan 30-31).
    """
    if df is None or df.empty or "due_date" not in df.columns:
        return []
    
    # Pre-check essential cols
    if "overdue_principal" not in df.columns or "owing_principal" not in df.columns:
        return []

    # Copy to avoid side effects
    df_wk = df.copy()
    if not np.issubdtype(df_wk["due_date"].dtype, np.datetime64):
        df_wk["due_date"] = pd.to_datetime(df_wk["due_date"])
    
    if period == 'W':
        df_wk["period_key"] = df_wk["due_date"].dt.to_period('W').apply(lambda r: r.start_time.strftime('%Y-%m-%d (W%V)'))
    elif period == 'M':
        df_wk["period_key"] = df_wk["due_date"].dt.strftime('%Y-%m')
    else:
        df_wk["period_key"] = df_wk["due_date"].dt.strftime('%Y-%m-%d')

    today = pd.Timestamp.now().normalize()
    
    # Group and Aggregate
    grouped = df_wk.groupby("period_key")
    results = []
    
    # Sort DESC
    sorted_keys = sorted(grouped.groups.keys(), reverse=True)[:limit]
    
    for key in sorted_keys:
        grp = grouped.get_group(key)
        
        # 1. Base (Entrant) - T+1 maturity assumed safe or handled by source
        owing = grp["owing_principal"].sum()
        overdue = grp["overdue_principal"].sum()
        
        item = {
            "period_key": key,
            "rows": len(grp),
            "overdue_rate": overdue / owing if owing > 0 else 0.0
        }
        
        # 2. DPD5 (d6) - Mature Rows Only
        mask_d5 = (today - grp["due_date"]).dt.days >= 6
        if mask_d5.any():
            denom_d5 = grp.loc[mask_d5, "owing_principal"].sum()
            num_d5 = grp.loc[mask_d5, "d6_principal"].sum() if "d6_principal" in grp.columns else 0
            item["dpd5"] = round(num_d5 / denom_d5, 4) if denom_d5 > 0 else None
        else:
            item["dpd5"] = None

        # [v3.3] Added DPD1, DPD7, DPD15 with Safe Denominator
        def _get_rate(day_offset, dpd_col):
            mask = (today - grp["due_date"]).dt.days >= day_offset
            if mask.any():
                denom = grp.loc[mask, "owing_principal"].sum()
                num = grp.loc[mask, dpd_col].sum() if dpd_col in grp.columns else 0
                return round(num / denom, 4) if denom > 0 else None
            return None

        # DPD1 (d2)
        item["dpd1"] = _get_rate(2, "d2_principal")
        # DPD7 (d8)
        item["dpd7"] = _get_rate(8, "d8_principal")
        # DPD15 (d16)
        item["dpd15"] = _get_rate(16, "d16_principal")
            
        # 3. DPD30 (d31) - Mature Rows Only
        mask_d30 = (today - grp["due_date"]).dt.days >= 31
        if mask_d30.any():
            denom_d30 = grp.loc[mask_d30, "owing_principal"].sum()
            num_d30 = grp.loc[mask_d30, "d31_principal"].sum() if "d31_principal" in grp.columns else 0
            item["dpd30"] = round(num_d30 / denom_d30, 4) if denom_d30 > 0 else None
        else:
            item["dpd30"] = None
            
        results.append(item)
    
    # [v3.3] Calc Change vs Prev
    metrics_to_diff = ["overdue_rate", "dpd1", "dpd5", "dpd7", "dpd15", "dpd30"]
    # Results are sorted DESC (Latest first).
    # item[i] is Current, item[i+1] is Prev.
    for i in range(len(results) - 1):
        curr = results[i]
        prev = results[i+1]
        for m in metrics_to_diff:
            if m in curr and m in prev:
                vc = curr[m]
                vp = prev[m]
                # [v3.5 Fix] Handle vp=0 case to allow infinite lift display or handle gracefully
                if isinstance(vc, (int, float)) and isinstance(vp, (int, float)):
                    if vp != 0:
                        curr[f"{m}_change"] = (vc - vp) / vp
                    elif vc > 0:
                        curr[f"{m}_change"] = 1.0 # 100% if prev is 0 and curr > 0
                    elif vc == 0:
                        curr[f"{m}_change"] = 0.0

    return results

def compute_amount_pivot(df):
    """
    [v3.5 New] Generate Pivot Data for Heatmap (Month x Amount).
    Metrics: overdue_rate, dpd1, dpd5, dpd30.
    Returns: { metric: { month: { amount: value } } }
    """
    if df is None or df.empty or "due_date" not in df.columns or "flag_principal" not in df.columns:
        return {}

    df = df.copy()
    if not np.issubdtype(df["due_date"].dtype, np.datetime64):
        df["due_date"] = pd.to_datetime(df["due_date"])
        
    df["due_month"] = df["due_date"].dt.to_period("M").dt.strftime("%Y-%m")
    
    # Sort data for consistent display
    # Group
    grouped = df.groupby(["due_month", "flag_principal"])
    
    pivot_data = {} # { metric: { month: { amount: value } } }
    metrics = ["overdue_rate", "dpd1", "dpd5", "dpd7", "dpd15", "dpd30"]
    
    # Init structure for all metrics
    for m in metrics:
        pivot_data[m] = {}

    for (month, amt), grp in grouped:
        # Use existing safe denominator logic
        res = _calc_risk_metrics(grp)
        
        for m in metrics:
            val = res.get(m)
            if val is not None:
                if month not in pivot_data[m]:
                    pivot_data[m][month] = {}
                pivot_data[m][month][amt] = val
                
    return pivot_data

def compute_vintage_matrix(df, limit=30):
    """
    [Legacy] Daily Vintage Matrix.
    Kept for backward compatibility or simple daily view.
    """
    if df is None or df.empty or "due_date" not in df.columns:
        return []
    
    # Ensure datetime
    df = df.copy()
    if not np.issubdtype(df["due_date"].dtype, np.datetime64):
        df["due_date"] = pd.to_datetime(df["due_date"])
        
    # Group by due_date
    cols_d = [f"d{i}_principal" for i in range(1, 32)] # d1..d31
    cols_needed = ["owing_principal", "overdue_principal"] + [c for c in cols_d if c in df.columns]
    
    # ... (Rest of existing logic, but we will upgrade it to a generalized function below)
    # Actually, let's redirect to the new generalized function with period='D'
    return compute_aggregated_vintage(df, period='D', limit=limit)


def compute_aggregated_vintage(df, period='D', limit=30):
    """
    [v3.1 Enhanced] Multi-dimension Vintage Matrix (Daily/Weekly/Monthly).
    Features:
    1. Safe Denominator.
    2. Lag 1 Mapping.
    3. [New] Supports pre-filtered DF.
    4. [v3.2] Returns both Recovery Rate and DPD Rate.
    """
    if df is None or df.empty or "due_date" not in df.columns:
        return []

    df = df.copy()
    if not np.issubdtype(df["due_date"].dtype, np.datetime64):
        df["due_date"] = pd.to_datetime(df["due_date"])

    # Define Period Key
    if period == 'W':
        df["period_key"] = df["due_date"].dt.to_period('W').apply(lambda r: r.start_time.strftime('%Y-%m-%d (W%V)'))
    elif period == 'M':
        df["period_key"] = df["due_date"].dt.strftime('%Y-%m')
    else:
        df["period_key"] = df["due_date"].dt.strftime('%Y-%m-%d')

    today = pd.Timestamp.now().normalize()
    
    grouped = df.groupby("period_key")
    results = []
    
    # Sort groups descending
    sorted_keys = sorted(grouped.groups.keys(), reverse=True)[:limit]
    
    for key in sorted_keys:
        grp = grouped.get_group(key)
        
        # 1. Entrant Rate
        owing = grp["owing_principal"].sum()
        overdue = grp["overdue_principal"].sum()
        entrant = overdue / owing if owing > 0 else 0.0
        
        item = {
            "period": key,
            "rows": len(grp),
            "entrant_rate": round(entrant, 4),
            "recovery": {},
            "dpd_rates": {} # [v3.2 New]
        }
        
        # 2. Loop D1..D30
        for k in range(1, 31): 
            # DPD Column (Balance at Dk)
            # [v3.3 Fix] Shift: Matrix 'D1' means DPD1 (Due+1), so use d2_principal.
            # Matrix 'Dk' uses d(k+1)_principal.
            dpd_col = f"d{k+1}_principal" 
            
            # For Recovery, D1 Recovery (Rec at D1) uses d2 vs overdue.
            # So Rec source matches DPD source (d2).
            # Logic: Rec = 1 - (d2 / overdue).
            rec_src_col = dpd_col
            
            lags = (today - grp["due_date"]).dt.days
            
            # --- DPD Rate (Overdue Rate) ---
            # DPDk Rate = SUM(dk+1_principal) / SUM(owing)
            # Constraint: Lag >= k+1 (Mature for Dk+1)
            # If k=1 (D1), need lag >= 2.
            mask_dpd = lags >= (k + 1)
            if mask_dpd.any() and dpd_col in grp.columns:
                mature_owing = grp.loc[mask_dpd, "owing_principal"].sum()
                mature_dpd = grp.loc[mask_dpd, dpd_col].sum()
                if mature_owing > 0:
                    item["dpd_rates"][f"D{k}"] = round(mature_dpd / mature_owing, 4)
                else:
                    item["dpd_rates"][f"D{k}"] = None
            else:
                item["dpd_rates"][f"D{k}"] = None

            # --- Recovery Rate ---
            # Recovery at Dk (end of day k overdue): 1 - (Remaining Balance at D(k+1) / Entrant Overdue)
            # If k=1 (D1), Remaining is d2_principal.
            # Rec = 1 - (d2 / overdue).
            # Constraint: Lag >= k+1 (Same as DPD)
            mask_rec = mask_dpd
            
            if not mask_rec.any() or rec_src_col not in grp.columns:
                item["recovery"][f"D{k}"] = None
            else:
                mature_overdue = grp.loc[mask_rec, "overdue_principal"].sum()
                mature_bal = grp.loc[mask_rec, rec_src_col].sum()
                
                if mature_overdue > 0:
                    rec = 1.0 - (mature_bal / mature_overdue)
                    item["recovery"][f"D{k}"] = round(rec, 4)
                else:
                    item["recovery"][f"D{k}"] = None
                    
        results.append(item)
        
    return results


def compute_lift_analysis(df, user_type_filter=None):
    """
    [v3.1 Enhanced] MTD (Month-to-Date) Comparison / Lift Analysis.
    Compares:
    1. Current Month (MTD)
    2. Last Month (Same Days MTD)
    3. [New] Month Before Last (M-2)
    4. [New] Last Year Same Period (Y-1)
    
    user_type_filter: Optional string (e.g. "新客") to filter data.
    """
    if df is None or df.empty or "due_date" not in df.columns:
        return {}
        
    df = df.copy()
    if user_type_filter and "user_type" in df.columns:
        df = df[df["user_type"] == user_type_filter]
        
    if df.empty:
        return {"status": "No data after filter"}

    df["due_date"] = pd.to_datetime(df["due_date"])
    today = pd.Timestamp.now().normalize()
    
    # 1. Define Time Windows
    curr_month_start = today.replace(day=1)
    
    # Filter Current Month Data
    df_curr = df[df["due_date"] >= curr_month_start]
    
    # If no data for current month, try to infer 'today' from max date in data (for offline testing)
    if df_curr.empty:
        max_all = df["due_date"].max()
        if pd.notna(max_all):
            curr_month_start = max_all.replace(day=1)
            df_curr = df[df["due_date"] >= curr_month_start]
            today = max_all # Adjust 'today' for offline test context

    max_curr_date = df_curr["due_date"].max()
    if pd.isna(max_curr_date):
        return {"status": "No current month data"}

    days_progress = (max_curr_date - curr_month_start).days + 1
    
    # Function to get MTD data for a target month start
    def get_mtd_data(target_start_date):
        target_end_mtd = target_start_date + pd.Timedelta(days=days_progress - 1)
        return df[(df["due_date"] >= target_start_date) & (df["due_date"] <= target_end_mtd)]

    # 2. Comparison Periods
    # M-1 (Last Month)
    m1_start = (curr_month_start - pd.Timedelta(days=1)).replace(day=1)
    df_m1 = get_mtd_data(m1_start)
    
    # M-2 (Month Before Last)
    m2_start = (m1_start - pd.Timedelta(days=1)).replace(day=1)
    df_m2 = get_mtd_data(m2_start)
    
    # Y-1 (Last Year)
    try:
        y1_start = curr_month_start.replace(year=curr_month_start.year - 1)
        df_y1 = get_mtd_data(y1_start)
    except ValueError: # Leap year edge case
        y1_start = curr_month_start.replace(year=curr_month_start.year - 1, day=28) # close enough
        df_y1 = get_mtd_data(y1_start)
    
    # 3. Aggregate Metrics Helper
    def calc_aggs(sub_df, label):
        if sub_df.empty:
            return None
            
        # [v3.3 Fix] Strict Observability Alignment
        # For historical comparison, we must restrict data to the EXACT SAME relative days 
        # as available in the Current Month.
        # Current Month Progress: 'days_progress' (e.g. 3 days: Feb 1-3)
        # Entrant (T+1): Valid for Days 1..3
        # DPD1 (T+2): Valid for Days 1..2 (Lag 1 day vs Progress)
        # DPD5 (T+6): Valid for Days 1..(3-5) (Lag 5 days vs Progress)
        
        # Base (Entrant): Uses full progress window
        owing = sub_df["owing_principal"].sum()
        overdue = sub_df["overdue_principal"].sum()
        
        # Helper to slice dataframe by day offset relative to window start
        def slice_by_lag(lag_days):
            # sub_df is already cut to [start, start + days_progress - 1]
            # We want [start, start + days_progress - 1 - lag_days]
            # Check if we have enough days
            if days_progress <= lag_days:
                return pd.DataFrame() # Not mature
            
            # Filter
            # Since sub_df might span months, we use relative calculation
            period_len_days = days_progress - lag_days
            # Find the start date of this sub_df
            min_d = sub_df["due_date"].min()
            cutoff = min_d + pd.Timedelta(days=period_len_days - 1)
            return sub_df[sub_df["due_date"] <= cutoff]

        # DPD1 (d2): Needs 1 more day of maturity than Entrant (T+2 vs T+1) -> Lag 1
        sub_d1 = slice_by_lag(1)
        if not sub_d1.empty:
            # For historical data, maturity is guaranteed if date is selected.
            # For current month, slice_by_lag(1) effectively removes the last day (Feb 3), leaving Feb 1-2.
            # Feb 2 is T+2 mature on Feb 4. Correct.
            owing_d1 = sub_d1["owing_principal"].sum()
            bal_d1 = sub_d1["d2_principal"].sum() if "d2_principal" in sub_d1.columns else 0
            rate_d1 = (bal_d1 / owing_d1) if owing_d1 > 0 else None 
        else:
            rate_d1 = None
        
        # DPD5 (d6): Needs 5 more days -> Lag 5
        sub_d5 = slice_by_lag(5)
        if not sub_d5.empty:
            owing_d5 = sub_d5["owing_principal"].sum()
            bal_d5 = sub_d5["d6_principal"].sum() if "d6_principal" in sub_d5.columns else 0
            rate_d5 = (bal_d5 / owing_d5) if owing_d5 > 0 else None
        else:
            rate_d5 = None
        
        return {
            "period": label,
            "owing": owing,
            "entrant_rate": overdue / owing if owing > 0 else 0,
            "dpd1_rate": rate_d1,
            "dpd5_rate": rate_d5
        }
        
    return {
        "current": calc_aggs(df_curr, "Current MTD"),
        "m1": calc_aggs(df_m1, "Last Month (M-1)"),
        "m2": calc_aggs(df_m2, "Month Before Last (M-2)"),
        "y1": calc_aggs(df_y1, "Last Year (Y-1)"),
        "days_progress": days_progress,
        "segment": user_type_filter or "Overall"
    }

def compute_due_trend(df, max_days=21):
    """Wrapper for backward compatibility (Daily Trend)."""
    return compute_trend_by_period(df, period='D', limit=max_days)



def compute_repay_summary(df_list, names):
    """
    Recovery summary with Attribution (Drill-down).
    """
    out = {}
    anomalies = []
    
    for df, name in zip(df_list, names):
        if df is None or df.empty:
            out[name] = {"rows": 0, "status": "No Data"}
            continue
            
        global_rows = len(df)
        global_rate = 0.0
        # Prefer repay_rate column; else compute from raw sums (取数只出原始量，分析时再算比率)
        if "repay_rate" in df.columns and str(df["repay_rate"].dtype) in ["float64", "int64"]:
            global_rate = float(df["repay_rate"].mean())
        elif "repay_principal" in df.columns and "start_owing_principal" in df.columns:
            denom = df["start_owing_principal"].sum()
            global_rate = float(df["repay_principal"].sum() / denom) if denom and denom != 0 else 0.0

        out[name] = {
            "rows": global_rows,
            "repay_rate": round(global_rate, 4),
            "breakdown": []
        }

        dims = []
        if "case_bucket" in df.columns: dims.append("case_bucket")
        if "group_name" in df.columns: dims.append("group_name")

        # Attribution: from repay_rate column or from raw sums
        if dims:
            try:
                if "repay_rate" in df.columns:
                    bd = df.groupby(dims)["repay_rate"].mean().reset_index()
                elif "repay_principal" in df.columns and "start_owing_principal" in df.columns:
                    bd = df.groupby(dims).agg(
                        repay_principal=("repay_principal", "sum"),
                        start_owing_principal=("start_owing_principal", "sum")
                    ).reset_index()
                    bd["repay_rate"] = bd["repay_principal"] / bd["start_owing_principal"].replace(0, float("nan"))
                else:
                    bd = None
                if bd is not None and "repay_rate" in bd.columns:
                    bd = bd.sort_values("repay_rate", ascending=True, na_position="last").head(3)
                    for _, row in bd.iterrows():
                        rv = row["repay_rate"]
                        if rv != rv or rv is None:  # NaN
                            continue
                        seg = "/".join([str(row[d]) for d in dims])
                        val = round(float(rv), 4)
                        out[name]["breakdown"].append(f"{seg}: {val}")
                        if val < 0.05:
                            anomalies.append(f"[{name}] Low segment {seg}: {val}")
            except Exception:
                pass

        if global_rate < 0.1:
            anomalies.append(f"[{name}] Global repay_rate {round(global_rate, 4)} < 0.1")

    return out, anomalies


def compute_process_summary(df):
    """Compute Strategy Execution metrics: Coverage, Connect Rate, Intensity."""
    if df is None or df.empty:
        return {}
    
    out = {}
    cols = ["raw_call_times", "raw_call_connect_times", "raw_owing_case_cnt", "raw_uncomm_case_cnt"]
    # Check if we have raw columns (from new agg sql); if not, try to use old columns or skip
    if not all(c in df.columns for c in cols):
        # Fallback or simple count if raw cols missing (old SQL)
        return {}

    # 1. By Bucket
    if "owner_bucket" in df.columns:
        gr = df.groupby("owner_bucket")[cols].sum()
        for b, row in gr.iterrows():
            total_cases = row["raw_owing_case_cnt"]
            total_calls = row["raw_call_times"]
            
            coverage = 1.0 - (row["raw_uncomm_case_cnt"] / total_cases) if total_cases > 0 else 0.0
            connect_rate = (row["raw_call_connect_times"] / total_calls) if total_calls > 0 else 0.0
            intensity = (total_calls / total_cases) if total_cases > 0 else 0.0
            
            out[f"Bucket: {b}"] = {
                "coverage_rate": round(coverage, 4),
                "connect_rate": round(connect_rate, 4),
                "intensity": round(intensity, 2)
            }

    # 2. By Group
    if "owner_group" in df.columns:
        gr = df.groupby("owner_group")[cols].sum()
        for g, row in gr.iterrows():
            total_cases = row["raw_owing_case_cnt"]
            total_calls = row["raw_call_times"]
            
            coverage = 1.0 - (row["raw_uncomm_case_cnt"] / total_cases) if total_cases > 0 else 0.0
            connect_rate = (row["raw_call_connect_times"] / total_calls) if total_calls > 0 else 0.0
            intensity = (total_calls / total_cases) if total_cases > 0 else 0.0
            
            out[f"Group: {g}"] = {
                "coverage_rate": round(coverage, 4),
                "connect_rate": round(connect_rate, 4),
                "intensity": round(intensity, 2)
            }
            
    return out


def build_html(vintage_summary, repay_summary, vintage_anomalies, repay_anomalies, excel_path, date_str, overview=None):
    """Build daily report HTML: 先基础分析报告，再异常数据检查，文末落款。overview 为 dict：vintage_rows, repay_rows, process_rows（可选）。"""
    all_anomalies = vintage_anomalies + repay_anomalies
    anomaly_html = "<br>".join(all_anomalies) if all_anomalies else "暂无异常。"

    rows_v = []
    for p, v in (vintage_summary or {}).items():
        r = v.get("rows", "-")
        ov = v.get("overdue_rate", v.get("dpd30_rate", "-"))
        rows_v.append(f"<tr><td>{p}</td><td>{r}</td><td>{ov}</td></tr>")
    table_product = "\n".join(rows_v) if rows_v else "<tr><td colspan='3'>无数据</td></tr>"

    rows_r = []
    for name, v in (repay_summary or {}).items():
        r = v.get("rows", "-")
        rr = v.get("repay_rate", "-")
        bd = "<br>".join(v.get("breakdown", []))
        if bd:
            bd = f"<br><span style='font-size:12px;color:#666'>归因最差 3 段：<br>{bd}</span>"
        rows_r.append(f"<tr><td>{name}{bd}</td><td>{r}</td><td>{rr}</td></tr>")
    table_batch = "\n".join(rows_r) if rows_r else "<tr><td colspan='3'>无数据</td></tr>"

    # 数据概览（先有基础，再做异常检查）
    ov = overview or {}
    n_v = ov.get("vintage_rows", "-")
    n_r = ov.get("repay_rows", "-")
    n_p = ov.get("process_rows", "-")
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 落款块（风险巡查重要部分）
    footer = f"""
    <p class="meta footer" style="margin-top:32px;padding-top:12px;border-top:1px solid #eee;">
        报告生成时间：{gen_time}<br/>
        数据源：{excel_path or 'None'}<br/>
        <strong>维护者</strong>：Mr. Yuan
    </p>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>贷后数据巡检日报 {date_str}</title>
    <style>
        body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 900px; margin: 0 auto; background: #fff; padding: 24px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 8px; }}
        h2 {{ color: #555; margin-top: 24px; border-left: 4px solid #4CAF50; padding-left: 10px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
        th {{ background: #f0f0f0; }}
        .meta {{ color: #666; font-size: 14px; margin-top: 20px; }}
        .anomaly {{ color: #c62828; }}
    </style>
</head>
<body>
<div class="container">
    <h1>贷后数据巡检日报</h1>

    <h2>一、数据概览</h2>
    <p>数据源与各表记录数（无基础分析则无法做异常检查）。</p>
    <table>
        <thead><tr><th>数据源</th><th>vintage_risk 记录数</th><th>natural_month_repay 记录数</th><th>process_data 记录数</th></tr></thead>
        <tbody><tr><td>{excel_path or 'None'}</td><td>{n_v}</td><td>{n_r}</td><td>{n_p}</td></tr></tbody>
    </table>

    <h2>二、基础数据分析</h2>
    <p>风险口径（Vintage）+ 回收口径（自然月回收率与归因）。参考 products/ 周报、dashboard/ 看板。</p>

    <h3>2.1 分产品 (Vintage)</h3>
    <table>
        <thead><tr><th>产品</th><th>记录数</th><th>逾期率/dpd30</th></tr></thead>
        <tbody>{table_product}</tbody>
    </table>

    <h3>2.2 分批次回收 (Attribution)</h3>
    <p>各回收表整体回收率，下钻<b>表现最差的 3 个细分维度</b>（如 Bucket/Group）。</p>
    <table>
        <thead><tr><th>批次/表</th><th>记录数</th><th>回收率</th></tr></thead>
        <tbody>{table_batch}</tbody>
    </table>

    <h3>2.3 可联率 / 过程</h3>
    <p>触达数据接入后在此展示可联率、发送量/成功率；process_data 接入后展示过程指标。</p>

    <h2>三、异常数据检查</h2>
    <p>在基础分析之上，按规则判定异常：逾期率&gt;0.5、回收率&lt;0.1、归因段&lt;0.05 等。</p>
    <div class="anomaly">{anomaly_html}</div>
{footer}
</div>
</body>
</html>"""


def main():
    import argparse
    parser = argparse.ArgumentParser(description="贷后数据巡检日报：读 Excel 生成 HTML")
    parser.add_argument("--excel", "-e", default=None, help="数据文件路径（默认：本目录下 collection_inspection_data_local.xlsx）")
    args = parser.parse_args()
    excel_path = args.excel if args.excel else find_excel()
    if args.excel and excel_path and not Path(excel_path).exists():
        print(f"File not found: {excel_path}")
        excel_path = None
    if not excel_path:
        print("Data file not found: run download script to produce collection_inspection_data_local.xlsx or place 0_basic_data.xlsx in Core dir.")
        print("Or: python run_daily_report.py --excel <你的Excel完整路径>")
        html = build_html({}, {}, [], [], None, datetime.now().strftime("%Y-%m-%d"), overview=None)
        out_path = REPORTS_DIR / f"Inspection_Report_{datetime.now().strftime('%Y-%m-%d')}.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"Placeholder report generated: {out_path}")
        try:
            input("Press Enter to close...")
        except EOFError:
            pass
        return

    print(f"Using data: {excel_path}")
    df_v = read_sheet_maybe_chunked(excel_path, "vintage_risk") or read_sheet(excel_path, "yya_vintage")
    df_repay = read_sheet(excel_path, "natural_month_repay")
    repay_name = "natural_month_repay"
    if df_repay is None:
        df_repay = read_sheet(excel_path, "repay_cl")
        repay_name = "repay_cl"
    if df_repay is None:
        df_repay = read_sheet(excel_path, "repay_tt")
        repay_name = "repay_tt"
    
    # Process data check (optional add)
    # df_process = read_sheet(excel_path, "process_data")

    vintage_summary, vintage_anomalies = compute_vintage_summary(df_v)
    repay_summary, repay_anomalies = compute_repay_summary(
        [df_repay] if df_repay is not None else [None],
        [repay_name] if df_repay is not None else ["natural_month_repay"],
    )

    df_process = read_sheet(excel_path, "process_data")
    overview = {
        "vintage_rows": len(df_v) if df_v is not None else 0,
        "repay_rows": len(df_repay) if df_repay is not None else 0,
        "process_rows": len(df_process) if df_process is not None else 0,
    }

    date_str = datetime.now().strftime("%Y-%m-%d")
    html = build_html(vintage_summary, repay_summary, vintage_anomalies, repay_anomalies, excel_path, date_str, overview=overview)
    out_path = REPORTS_DIR / f"Inspection_Report_{date_str}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Report generated: {out_path}")
    try:
        input("Press Enter to close...")
    except EOFError:
        pass


def compute_collection_performance(df, df_process=None):
    """
    [v4.1 New] Recovery Attribution & Driver Analysis.
    - Level 1: Contribution to Rate Delta (who caused the drop?)
    - Level 2: Process Drivers (why did they drop?) - MoM Comparison.
    
    Hierarchy: Agent Bucket -> Group Name -> Owner ID.
    """
    print(f"DEBUG: compute_collection_performance called. df shape: {df.shape if df is not None else 'None'}")
    if df is None or df.empty:
        print("DEBUG: df is None or empty. Returning empty.")
        return {}
        
    out = {}
    df = df.copy()
    
    # Ensure natural_month exists or create from dt
    if "natural_month" not in df.columns:
        print(f"DEBUG: 'natural_month' missing. Columns: {df.columns.tolist()}")
        return {}
    
    # [Fix] Ensure consistent type for natural_month (String)
    df["natural_month"] = df["natural_month"].astype(str)
    
    # 1. Identify Months
    all_months = sorted(df["natural_month"].unique().tolist())
    # [Fix] Exclude Target Month (e.g. 250003) from Trend
    months = [m for m in all_months if not m.startswith("25")]
    target_month = next((m for m in all_months if m.startswith("25")), None)
    
    print(f"DEBUG: Months found: {months} (Target: {target_month})")
    
    if not months: return {}
    
    curr_month = months[-1]
    prev_month = months[-2] if len(months) > 1 else None
    
    out["meta"] = {"current": curr_month, "prev": prev_month, "target": target_month}
    
    # Filter Repay Data
    df_curr = df[df["natural_month"] == curr_month]
    print(f"DEBUG: df_curr shape: {df_curr.shape}")
    
    df_prev = df[df["natural_month"] == prev_month] if prev_month else pd.DataFrame()

    # 2. Prepare Process Data (Current & Prev)
    proc_map_curr = {} 
    proc_map_prev = {}
    proc_bm_curr = {} # Bucket Level Benchmarks

    if df_process is not None and not df_process.empty:
        # Check format compatibility
        # Assumes df_process natural_month matches df natural_month format (e.g. '202601')
        
        def _get_proc_map(df_p_sub):
            m = {}
            if df_p_sub.empty: return m
            for _, row in df_p_sub.iterrows():
                k = (row.get("owner_bucket"), row.get("owner_group"))
                m[k] = {
                    "cov": row.get("cover_rate", 0),
                    "conn": row.get("case_connect_rate", 0),
                    "int": row.get("call_times_avg", 0)
                }
            return m

        # Current Process
        df_p_c = df_process[df_process["natural_month"].astype(str) == str(curr_month)]
        proc_map_curr = _get_proc_map(df_p_c)
        
        # Bucket Benchmarks (Current) - Weighted Avg
        if not df_p_c.empty:
            g_b_p = df_p_c.groupby("owner_bucket").apply(
                lambda x: pd.Series({
                    "cov": (x["cover_rate"] * x["raw_owing_case_cnt"]).sum() / x["raw_owing_case_cnt"].sum() if x["raw_owing_case_cnt"].sum() > 0 else 0,
                    "conn": (x["case_connect_rate"] * x["raw_owing_case_cnt"]).sum() / x["raw_owing_case_cnt"].sum() if x["raw_owing_case_cnt"].sum() > 0 else 0,
                    "int": (x["call_times_avg"] * x["raw_owing_case_cnt"]).sum() / x["raw_owing_case_cnt"].sum() if x["raw_owing_case_cnt"].sum() > 0 else 0,
                })
            ).to_dict("index")
            proc_bm_curr = g_b_p

        # Prev Process
        if prev_month:
            df_p_p = df_process[df_process["natural_month"].astype(str) == str(prev_month)]
            proc_map_prev = _get_proc_map(df_p_p)

    out["proc_benchmarks"] = proc_bm_curr
    
    # 3. Bucket Level Summary
    out["buckets"] = []
    out["groups"] = {}
    out["agents"] = {}
    
    if "agent_bucket" in df_curr.columns:
        # Current Bucket Stats
        g_bucket = df_curr.groupby("agent_bucket").agg({
            "repay_principal": "sum",
            "start_owing_principal": "sum"
        }).reset_index()
        g_bucket["repay_rate"] = g_bucket["repay_principal"] / g_bucket["start_owing_principal"]
        
        # Prev Bucket Stats (for Benchmark)
        bm_map = {}
        if not df_prev.empty and "agent_bucket" in df_prev.columns:
            g_prev_b = df_prev.groupby("agent_bucket").agg({
                "repay_principal": "sum",
                "start_owing_principal": "sum"
            })
            g_prev_b["rate"] = g_prev_b["repay_principal"] / g_prev_b["start_owing_principal"]
            bm_map = g_prev_b["rate"].to_dict()
            
        out["buckets"] = g_bucket.to_dict("records") # UI uses this for overview
        out["benchmarks"] = bm_map

        # Prev Group Stats (for MoM Delta)
        grp_prev_map = {} # (bucket, group) -> {rate, vol}
        if not df_prev.empty and "group_name" in df_prev.columns:
            g_grp_p = df_prev.groupby(["agent_bucket", "group_name"]).agg({
                "repay_principal": "sum",
                "start_owing_principal": "sum"
            }).reset_index()
            for _, r in g_grp_p.iterrows():
                vol = r["start_owing_principal"]
                rate = r["repay_principal"] / vol if vol > 0 else 0
                grp_prev_map[(r["agent_bucket"], r["group_name"])] = {"rate": rate, "vol": vol}

        # 4. Group Level Analysis (Attribution & Drivers)
        for bucket in g_bucket["agent_bucket"].unique():
            sub = df_curr[df_curr["agent_bucket"] == bucket]
            
            # Bucket Totals (Current)
            bkt_vol = sub["start_owing_principal"].sum()
            bkt_rate = sub["repay_principal"].sum() / bkt_vol if bkt_vol > 0 else 0
            
            # Prev Bucket Rate
            bkt_rate_prev = bm_map.get(bucket, 0.0)
            
            if "group_name" in sub.columns:
                g_grp = sub.groupby("group_name").agg({
                    "repay_principal": "sum",
                    "start_owing_principal": "sum"
                }).reset_index()
                
                # Calculate Metrics
                recs = []
                for _, row in g_grp.iterrows():
                    grp_name = row["group_name"]
                    vol = row["start_owing_principal"]
                    rate = row["repay_principal"] / vol if vol > 0 else 0
                    
                    # Mix (Weight)
                    weight = vol / bkt_vol if bkt_vol > 0 else 0
                    
                    # History Comparison (Group Self)
                    hist = grp_prev_map.get((bucket, grp_name), {})
                    rate_prev = hist.get("rate", 0.0)
                    # Note: If new group (no history), rate_prev=0 implies huge improvement? 
                    # Better to use Bucket Avg as fallback for new groups to avoid skew?
                    # For attribution, we want Contribution to Change. If new group added, it contributes to mix change.
                    # Simplified: If no history, assume rate_prev = bkt_rate_prev (neutral assumption)
                    has_hist = (bucket, grp_name) in grp_prev_map
                    if not has_hist: rate_prev = bkt_rate_prev 
                    
                    # [Attribution] Contribution to Rate Delta
                    # Contrib = (Rate_Curr - Rate_Prev) * Weight_Curr
                    rate_delta_mom = rate - rate_prev
                    contrib = rate_delta_mom * weight
                    
                    # [Drivers] Process MoM
                    p_curr = proc_map_curr.get((bucket, grp_name), {})
                    p_prev = proc_map_prev.get((bucket, grp_name), {}) # Empty if no history
                    
                    # If no prev process, use curr bucket benchmark? No, use 0 or None.
                    # We want to see DROP.
                    
                    rec = {
                        "group_name": grp_name,
                        "repay_rate": rate,
                        "vol": vol,
                        "weight": weight,
                        "rate_prev": rate_prev,
                        "rate_delta_mom": rate_delta_mom,
                        "contrib_to_delta": contrib,
                        # Process Drivers
                        "cov": p_curr.get("cov", 0),
                        "conn": p_curr.get("conn", 0),
                        "int": p_curr.get("int", 0),
                        "cov_mom": p_curr.get("cov", 0) - p_prev.get("cov", 0) if p_prev else 0,
                        "conn_mom": p_curr.get("conn", 0) - p_prev.get("conn", 0) if p_prev else 0,
                        "int_mom": p_curr.get("int", 0) - p_prev.get("int", 0) if p_prev else 0,
                        "has_hist": has_hist
                    }
                    
                    # Determine Main Driver (Negative only)
                    # If Rate Delta is negative, find the biggest negative process delta
                    drivers = []
                    if rate_delta_mom < -0.005: # Drop > 0.5%
                        pd_map = {
                            "Cov": rec["cov_mom"], 
                            "Conn": rec["conn_mom"], 
                            "Int": rec["int_mom"]
                        }
                        # Find negative drivers
                        neg_drivers = {k: v for k, v in pd_map.items() if v < -0.01} # Drop > 1%
                        if neg_drivers:
                            # Sort by magnitude (most negative first)
                            worst = sorted(neg_drivers.items(), key=lambda x: x[1])[0]
                            rec["main_driver"] = f"{worst[0]} {worst[1]:.1%}"
                        else:
                            rec["main_driver"] = "Efficiency" # Conversion dropped but process stable
                    else:
                        rec["main_driver"] = "-"
                        
                    recs.append(rec)
                
                # Sort by Contribution (ascending: largest negative contributor first)
                # Actually usually we want to see who dragged us down.
                recs.sort(key=lambda x: x["contrib_to_delta"]) 
                
                # Add Bucket Benchmark for Process (Context)
                p_bm = proc_bm_curr.get(bucket, {"cov":0, "conn":0, "int":0})
                
                out["groups"][bucket] = {
                    "all": recs,
                    "benchmark": bkt_rate_prev,
                    "proc_benchmark": p_bm
                }

            # Rank Agents (Existing Logic)
            if "owner_id" in sub.columns:
                g_agt = sub.groupby("owner_id").agg({
                    "repay_principal": "sum",
                    "start_owing_principal": "sum"
                }).reset_index()
                min_vol = g_agt["start_owing_principal"].median() * 0.1
                g_agt = g_agt[g_agt["start_owing_principal"] > min_vol]
                g_agt["repay_rate"] = g_agt["repay_principal"] / g_agt["start_owing_principal"]
                g_agt = g_agt.sort_values("repay_rate", ascending=False)
                out["agents"][bucket] = {
                    "top": g_agt.head(5).to_dict("records"),
                    "bottom": g_agt.tail(5).to_dict("records")
                }
                
    return out

# ─────────────────────────────────────────────────────────────────────────────
# [v4.21 NEW] 运营归因 Treemap
# ─────────────────────────────────────────────────────────────────────────────

def compute_ops_attribution(df_daily, df_process=None):
    """
    [v4.21] 运营归因分析 — 构建 3 级 Treemap 数据 (模块→组→经办)
    
    输入:
      df_daily   — natural_month_repay_daily 表 (含 data_level, case_bucket, group_name, owner_id)
      df_process — process_data 表 (含 owner_bucket, owner_group, 过程指标)

    输出:
      {
        "summary": {...},          # 总体 KPI
        "treemap_data": [...],     # ECharts treemap 嵌套数据
        "size_breakdown": {...},   # 大小额辅助数据
        "meta": {...}              # 月份信息
      }
    """
    import json
    if df_daily is None or df_daily.empty:
        return {}

    df = df_daily.copy()
    df['day'] = pd.to_numeric(df['day'], errors='coerce')
    df['natural_month'] = pd.to_numeric(df['natural_month'], errors='coerce')
    df['repay_principal'] = pd.to_numeric(df['repay_principal'], errors='coerce').fillna(0)
    df['start_owing_principal'] = pd.to_numeric(df['start_owing_principal'], errors='coerce').fillna(0)

    TARGET_MONTH = 250003
    SHOW_BUCKETS = ['S0', 'S1', 'S2', 'M1']

    # ── Identify months ──
    all_months = sorted(df['natural_month'].dropna().unique())
    actual_months = [m for m in all_months if m != TARGET_MONTH]
    if not actual_months:
        return {}
    curr_month = actual_months[-1]
    prev_month = actual_months[-2] if len(actual_months) > 1 else None

    # ── Helper: get latest-day rates from aggregated data ──
    def _latest_rates(df_level, group_col, parent_col=None):
        """
        For each entity in group_col, compute the rate at the latest available day
        for curr_month, target, and prev_month.
        Returns: dict { entity_name: {rate, target_rate, prev_rate, volume, day, parent} }
        """
        if df_level.empty:
            return {}
        agg = df_level.groupby(['natural_month', group_col, 'day'] + ([parent_col] if parent_col else []),
                                as_index=False).agg(
            repay_principal=('repay_principal', 'sum'),
            start_owing_principal=('start_owing_principal', 'sum')
        )

        # Find latest day in current month
        curr_data = agg[agg['natural_month'] == curr_month]
        if curr_data.empty:
            return {}
        latest_day = int(curr_data['day'].max())

        result = {}
        entities = curr_data[group_col].dropna().unique()
        for ent in entities:
            ent_str = str(ent).strip()
            ent_curr = curr_data[(curr_data[group_col].astype(str).str.strip() == ent_str) & (curr_data['day'] == latest_day)]
            if ent_curr.empty:
                # Try the max day available for this entity
                ent_all_days = curr_data[curr_data[group_col].astype(str).str.strip() == ent_str]
                if ent_all_days.empty:
                    continue
                ent_day = int(ent_all_days['day'].max())
                ent_curr = ent_all_days[ent_all_days['day'] == ent_day]
            else:
                ent_day = latest_day

            repay = ent_curr['repay_principal'].sum()
            start = ent_curr['start_owing_principal'].sum()
            rate = repay / start if start > 0 else 0

            # Target at same day
            target_data = agg[(agg['natural_month'] == TARGET_MONTH) &
                              (agg[group_col].astype(str).str.strip() == ent_str) &
                              (agg['day'] == ent_day)]
            target_rate = 0
            if not target_data.empty:
                tr = target_data['repay_principal'].sum()
                ts = target_data['start_owing_principal'].sum()
                target_rate = tr / ts if ts > 0 else 0
            else:
                # Fallback: find closest day <= ent_day
                t_all = agg[(agg['natural_month'] == TARGET_MONTH) &
                            (agg[group_col].astype(str).str.strip() == ent_str) &
                            (agg['day'] <= ent_day)]
                if not t_all.empty:
                    t_row = t_all.loc[t_all['day'].idxmax()]
                    target_rate = t_row['repay_principal'] / t_row['start_owing_principal'] if t_row['start_owing_principal'] > 0 else 0

            # Prev month at same day
            prev_rate = 0
            if prev_month is not None:
                prev_data = agg[(agg['natural_month'] == prev_month) &
                                (agg[group_col].astype(str).str.strip() == ent_str) &
                                (agg['day'] == ent_day)]
                if not prev_data.empty:
                    pr = prev_data['repay_principal'].sum()
                    ps = prev_data['start_owing_principal'].sum()
                    prev_rate = pr / ps if ps > 0 else 0
                else:
                    p_all = agg[(agg['natural_month'] == prev_month) &
                                (agg[group_col].astype(str).str.strip() == ent_str) &
                                (agg['day'] <= ent_day)]
                    if not p_all.empty:
                        p_row = p_all.loc[p_all['day'].idxmax()]
                        prev_rate = p_row['repay_principal'] / p_row['start_owing_principal'] if p_row['start_owing_principal'] > 0 else 0

            rec = {
                "rate": round(rate, 6),
                "target_rate": round(target_rate, 6),
                "prev_rate": round(prev_rate, 6),
                "volume": float(start),
                "gap": round(rate - target_rate, 6),
                "mom": round(rate - prev_rate, 6),
                "day": ent_day
            }
            if parent_col and parent_col in ent_curr.columns:
                rec["parent"] = str(ent_curr[parent_col].iloc[0]).strip()
            result[ent_str] = rec

        return result

    # ── L1: Module level ──
    df_l1 = df[df['data_level'] == '1.\u6a21\u5757\u5c42\u7ea7']
    l1_rates = _latest_rates(df_l1, 'case_bucket')

    # ── L2: Size level (supplementary) ──
    df_l2 = df[df['data_level'] == '1.5.\u5927\u5c0f\u6a21\u5757\u5c42\u7ea7'].copy()
    if not df_l2.empty:
        df_l2['case_bucket'] = df_l2['case_bucket'].astype(str).str.replace('_Outsource', '_Other')
    l2_rates = _latest_rates(df_l2, 'case_bucket') if not df_l2.empty else {}

    # ── L3: Group level ──
    df_l3 = df[df['data_level'] == '4.\u7ec4\u522b\u5c42\u7ea7'].copy()
    if not df_l3.empty:
        df_l3['group_name'] = df_l3['group_name'].astype(str).str.strip()
        df_l3 = df_l3[df_l3['group_name'] != 'Target']
    l3_rates = _latest_rates(df_l3, 'group_name', parent_col='agent_bucket') if not df_l3.empty else {}

    # ── L4: Handler level ──
    df_l4 = df[df['data_level'] == '5.\u7ecf\u529e\u5c42\u7ea7'].copy()
    if not df_l4.empty:
        df_l4['group_name'] = df_l4['group_name'].astype(str).str.strip()
        df_l4 = df_l4[df_l4['group_name'] != 'Target']
        df_l4['owner_id'] = df_l4['owner_id'].apply(
            lambda x: str(int(x)) if pd.notna(x) and isinstance(x, (int, float)) else str(x).strip()
        )
    l4_rates = _latest_rates(df_l4, 'owner_id', parent_col='group_name') if not df_l4.empty else {}

    # ── Process data mapping ──
    proc_map = {}
    proc_map_prev = {}
    if df_process is not None and not df_process.empty:
        dfp = df_process.copy()
        dfp['natural_month'] = dfp['natural_month'].astype(str)
        str_curr = str(int(curr_month))
        str_prev = str(int(prev_month)) if prev_month else None

        for _, row in dfp.iterrows():
            k = (str(row.get('owner_bucket', '')).strip(), str(row.get('owner_group', '')).strip())
            nm = str(row.get('natural_month', '')).strip()
            rec = {
                "cov": float(row.get('cover_rate', 0) or 0),
                "conn": float(row.get('case_connect_rate', 0) or 0),
                "int": float(row.get('call_times_avg', 0) or 0),
            }
            if nm == str_curr:
                proc_map[k] = rec
            elif str_prev and nm == str_prev:
                proc_map_prev[k] = rec

    # ── Build treemap hierarchy ──
    # Overall summary
    total_volume = sum(v["volume"] for k, v in l1_rates.items() if k in SHOW_BUCKETS)
    overall_repay = sum(v["rate"] * v["volume"] for k, v in l1_rates.items() if k in SHOW_BUCKETS)
    overall_target_repay = sum(v["target_rate"] * v["volume"] for k, v in l1_rates.items() if k in SHOW_BUCKETS)
    overall_prev_repay = sum(v["prev_rate"] * v["volume"] for k, v in l1_rates.items() if k in SHOW_BUCKETS)

    overall_rate = overall_repay / total_volume if total_volume > 0 else 0
    overall_target = overall_target_repay / total_volume if total_volume > 0 else 0
    overall_prev = overall_prev_repay / total_volume if total_volume > 0 else 0

    summary = {
        "overall_rate": round(overall_rate, 6),
        "target_rate": round(overall_target, 6),
        "gap": round(overall_rate - overall_target, 6),
        "prev_rate": round(overall_prev, 6),
        "mom_change": round(overall_rate - overall_prev, 6),
        "latest_day": l1_rates[list(l1_rates.keys())[0]]["day"] if l1_rates else 0,
        "curr_month": int(curr_month),
        "prev_month": int(prev_month) if prev_month else None,
    }

    # Build nested treemap data
    BUCKET_ORDER = ['S0', 'S1', 'S2', 'M1', 'M2', 'M3', 'M4']
    treemap_data = []

    for bkt in BUCKET_ORDER:
        if bkt not in l1_rates or bkt not in SHOW_BUCKETS:
            continue
        binfo = l1_rates[bkt]
        bkt_node = {
            "name": bkt,
            "value": binfo["volume"],
            "rate": binfo["rate"],
            "target": binfo["target_rate"],
            "gap": binfo["gap"],
            "mom": binfo["mom"],
            "children": []
        }

        # Find groups belonging to this bucket
        bkt_groups = {gn: gi for gn, gi in l3_rates.items() if gi.get("parent", "").startswith(bkt)}

        for gn, ginfo in sorted(bkt_groups.items(), key=lambda x: x[1]["volume"], reverse=True):
            # Process driver for this group
            pk = (bkt, gn)
            p_curr = proc_map.get(pk, {})
            p_prev = proc_map_prev.get(pk, {})
            proc_info = {}
            main_driver = "-"
            if p_curr:
                proc_info = {
                    "cov": round(p_curr.get("cov", 0), 4),
                    "conn": round(p_curr.get("conn", 0), 4),
                    "int": round(p_curr.get("int", 0), 2),
                    "cov_mom": round(p_curr.get("cov", 0) - p_prev.get("cov", 0), 4) if p_prev else 0,
                    "conn_mom": round(p_curr.get("conn", 0) - p_prev.get("conn", 0), 4) if p_prev else 0,
                    "int_mom": round(p_curr.get("int", 0) - p_prev.get("int", 0), 2) if p_prev else 0,
                }
                # Identify main driver if performance dropped
                if ginfo["mom"] < -0.005:
                    drv = {"Cov": proc_info.get("cov_mom", 0),
                           "Conn": proc_info.get("conn_mom", 0),
                           "Int": proc_info.get("int_mom", 0)}
                    neg = {k: v for k, v in drv.items() if isinstance(v, (int, float)) and v < -0.01}
                    if neg:
                        worst = sorted(neg.items(), key=lambda x: x[1])[0]
                        main_driver = f"{worst[0]} {worst[1]:+.1%}"
                    else:
                        main_driver = "Efficiency"

            grp_node = {
                "name": gn,
                "value": ginfo["volume"],
                "rate": ginfo["rate"],
                "target": ginfo["target_rate"],
                "gap": ginfo["gap"],
                "mom": ginfo["mom"],
                "proc": proc_info,
                "main_driver": main_driver,
                "children": []
            }

            # Find handlers belonging to this group
            grp_handlers = {oid: oi for oid, oi in l4_rates.items() if oi.get("parent", "") == gn}
            for oid, oinfo in sorted(grp_handlers.items(), key=lambda x: x[1]["volume"], reverse=True):
                handler_node = {
                    "name": oid,
                    "value": oinfo["volume"],
                    "rate": oinfo["rate"],
                    "target": oinfo["target_rate"],
                    "gap": oinfo["gap"],
                    "mom": oinfo["mom"],
                }
                grp_node["children"].append(handler_node)

            bkt_node["children"].append(grp_node)

        treemap_data.append(bkt_node)

    # ── Size breakdown (supplementary) ──
    size_breakdown = {}
    for ent, info in l2_rates.items():
        parent = ent.split('_')[0]
        if parent not in size_breakdown:
            size_breakdown[parent] = []
        size_breakdown[parent].append({
            "name": ent,
            "rate": info["rate"],
            "target": info["target_rate"],
            "gap": info["gap"],
            "mom": info["mom"],
            "volume": info["volume"]
        })

    return {
        "summary": summary,
        "treemap_data": treemap_data,
        "size_breakdown": size_breakdown,
        "meta": {
            "curr_month": int(curr_month),
            "prev_month": int(prev_month) if prev_month else None,
            "target_month": TARGET_MONTH
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# [v4.23 NEW] 智能诊断 — 多月趋势 + 模式识别 + Uplift 量化
# ─────────────────────────────────────────────────────────────────────────────

def compute_smart_diagnostics(df_daily, df_process=None):
    """
    [v4.23] 智能诊断 — 将观察窗口从2个月扩展到3-4个月，实现:
    1. 多月组级指标矩阵（同日对齐回收率 + 过程指标趋势）
    2. 持续性模式识别（连续不达标+不勤奋、加速恶化等）
    3. Uplift 量化（如果差的组提升到模块均值，整体能提升多少）
    4. 自然语言叙事生成

    输入:
      df_daily   — natural_month_repay_daily
      df_process — process_data

    输出:
      {
        "findings": [...],       # 按严重度排序的诊断发现（含叙事）
        "group_trends": {...},   # (bucket, group) -> 多月趋势数据
        "uplift_table": [...],   # 按 uplift 降序的修复优先级
        "summary": {...}         # 总体统计
      }
    """
    import json
    if df_daily is None or df_daily.empty:
        return {}

    df = df_daily.copy()
    df['day'] = pd.to_numeric(df['day'], errors='coerce')
    df['natural_month'] = pd.to_numeric(df['natural_month'], errors='coerce')
    df['repay_principal'] = pd.to_numeric(df['repay_principal'], errors='coerce').fillna(0)
    df['start_owing_principal'] = pd.to_numeric(df['start_owing_principal'], errors='coerce').fillna(0)

    TARGET_MONTH = 250003
    SHOW_BUCKETS = ['S0', 'S1', 'S2', 'M1']

    all_months = sorted(df['natural_month'].dropna().unique())
    actual_months = sorted([m for m in all_months if m != TARGET_MONTH])
    if len(actual_months) < 2:
        return {}

    curr_month = actual_months[-1]

    # ── Step 0: Build process data maps per (bucket, group, month) ──
    proc_by_month = {}  # (bucket, group, month) -> {cov, conn, int}
    if df_process is not None and not df_process.empty:
        dfp = df_process.copy()
        dfp['natural_month'] = dfp['natural_month'].astype(str).str.strip()
        for _, row in dfp.iterrows():
            bkt = str(row.get('owner_bucket', '')).strip()
            grp = str(row.get('owner_group', '')).strip()
            nm = str(row.get('natural_month', '')).strip()
            proc_by_month[(bkt, grp, nm)] = {
                "cov": float(row.get('cover_rate', 0) or 0),
                "conn": float(row.get('case_connect_rate', 0) or 0),
                "int": float(row.get('call_times_avg', 0) or 0),
            }

    # ── Step 1: Multi-month group-level metrics matrix ──
    # For each (bucket, group), compute rate at a reference day for each month
    df_l3 = df[df['data_level'] == '4.\u7ec4\u522b\u5c42\u7ea7'].copy()
    if df_l3.empty:
        return {}
    df_l3['group_name'] = df_l3['group_name'].astype(str).str.strip()
    df_l3 = df_l3[df_l3['group_name'] != 'Target']

    # Find latest day in current month as alignment reference
    curr_data = df_l3[df_l3['natural_month'] == curr_month]
    if curr_data.empty:
        return {}
    ref_day = int(curr_data['day'].max())

    # L1 module data for target rates and bucket weights
    df_l1 = df[df['data_level'] == '1.\u6a21\u5757\u5c42\u7ea7']

    group_trends = {}

    # Map agent_bucket (e.g. S1_Large) to module bucket (e.g. S1)
    def _to_module(ab):
        s = str(ab).strip()
        for bkt in SHOW_BUCKETS:
            if s == bkt or s.startswith(bkt + '_'):
                return bkt
        return None

    for ab in sorted(df_l3['agent_bucket'].dropna().unique()):
        ab_str = str(ab).strip()
        module_bkt = _to_module(ab_str)
        if module_bkt is None:
            continue

        sub = df_l3[df_l3['agent_bucket'] == ab]
        groups = sorted(sub['group_name'].dropna().unique())

        # Get module-level target rate at ref_day
        l1_sub = df_l1[df_l1['case_bucket'] == module_bkt]
        target_at_ref = 0
        if not l1_sub.empty:
            t_data = l1_sub[(l1_sub['natural_month'] == TARGET_MONTH) & (l1_sub['day'] <= ref_day)]
            if not t_data.empty:
                t_agg = t_data.groupby('day').agg(
                    repay=('repay_principal', 'sum'),
                    start=('start_owing_principal', 'sum')
                ).reset_index()
                t_row = t_agg.loc[t_agg['day'].idxmax()]
                target_at_ref = t_row['repay'] / t_row['start'] if t_row['start'] > 0 else 0

        # Current month bucket volume for weight calculation
        curr_bucket = sub[sub['natural_month'] == curr_month]
        bucket_vol = curr_bucket['start_owing_principal'].sum()

        for gn in groups:
            g_data = sub[sub['group_name'] == gn]
            months_list = []
            rates_list = []
            achieves_list = []
            covs_list = []
            conns_list = []
            ints_list = []

            for m in actual_months:
                m_data = g_data[(g_data['natural_month'] == m) & (g_data['day'] <= ref_day)]
                if m_data.empty:
                    continue
                # Find the row at the max day <= ref_day
                agg = m_data.groupby('day').agg(
                    repay=('repay_principal', 'sum'),
                    start=('start_owing_principal', 'sum')
                ).reset_index()
                row = agg.loc[agg['day'].idxmax()]
                rate = row['repay'] / row['start'] if row['start'] > 0 else 0

                months_list.append(int(m))
                rates_list.append(round(rate, 6))
                ach = rate / target_at_ref if target_at_ref > 0 else 0
                achieves_list.append(round(ach, 4))

                # Process metrics for this month
                m_str = str(int(m))
                pk = (module_bkt, gn, m_str)
                pm = proc_by_month.get(pk, {})
                covs_list.append(round(pm.get('cov', 0), 4))
                conns_list.append(round(pm.get('conn', 0), 4))
                ints_list.append(round(pm.get('int', 0), 2))

            if len(months_list) < 1:
                continue

            # Current volume & weight
            g_curr = g_data[g_data['natural_month'] == curr_month]
            vol = float(g_curr['start_owing_principal'].sum()) if not g_curr.empty else 0
            weight = vol / bucket_vol if bucket_vol > 0 else 0

            group_trends[(module_bkt, gn)] = {
                "bucket": module_bkt,
                "group": gn,
                "months": months_list,
                "rates": rates_list,
                "target_rate": round(target_at_ref, 6),
                "achieves": achieves_list,
                "covs": covs_list,
                "conns": conns_list,
                "ints": ints_list,
                "volume": vol,
                "weight": round(weight, 4),
            }

    # ── Step 2: Compute module-level averages for effort benchmarking ──
    module_avg_cov = {}
    module_avg_int = {}
    curr_str = str(int(curr_month))
    for bkt in SHOW_BUCKETS:
        covs = []
        ints_vals = []
        for (b, g), info in group_trends.items():
            if b != bkt:
                continue
            if not info['months'] or int(curr_month) not in info['months']:
                continue
            idx = info['months'].index(int(curr_month))
            c = info['covs'][idx]
            i = info['ints'][idx]
            w = info['weight']
            if c > 0:
                covs.append((c, w))
            if i > 0:
                ints_vals.append((i, w))
        if covs:
            tw = sum(x[1] for x in covs)
            module_avg_cov[bkt] = sum(x[0] * x[1] for x in covs) / tw if tw > 0 else 0
        if ints_vals:
            tw = sum(x[1] for x in ints_vals)
            module_avg_int[bkt] = sum(x[0] * x[1] for x in ints_vals) / tw if tw > 0 else 0

    # ── Step 3: Pattern recognition ──
    for key, info in group_trends.items():
        bkt = info['bucket']
        achieves = info['achieves']
        covs = info['covs']
        rates = info['rates']
        n = len(achieves)

        pattern = "normal"
        severity = "info"

        avg_cov = module_avg_cov.get(bkt, 0)
        avg_int_val = module_avg_int.get(bkt, 0)

        # Current month values
        curr_ach = achieves[-1] if achieves else 0
        curr_cov = covs[-1] if covs else 0
        curr_int = info['ints'][-1] if info['ints'] else 0

        is_low_effort = False
        if avg_cov > 0 and curr_cov > 0:
            is_low_effort = curr_cov < avg_cov * 0.85
        if avg_int_val > 0 and curr_int > 0 and curr_int < avg_int_val * 0.85:
            is_low_effort = True

        # Count consecutive months below target from end
        consecutive_below = 0
        for a in reversed(achieves):
            if a < 0.9:
                consecutive_below += 1
            else:
                break

        # Count consecutive months improving from end
        consecutive_improving = 0
        if n >= 2:
            for i in range(n - 1, 0, -1):
                if achieves[i] > achieves[i - 1]:
                    consecutive_improving += 1
                else:
                    break

        # Pattern classification
        if consecutive_below >= 2 and is_low_effort:
            pattern = "persistent_lazy"
            severity = "critical"
        elif n >= 3 and all(rates[i] > rates[i + 1] for i in range(n - 1)):
            # Check if decline is accelerating
            deltas = [rates[i] - rates[i + 1] for i in range(n - 1)]
            if len(deltas) >= 2 and deltas[-1] > deltas[-2]:
                pattern = "accelerating_decline"
                severity = "critical"
            elif consecutive_below >= 2:
                pattern = "persistent_strategy"
                severity = "high"
            else:
                pattern = "declining"
                severity = "medium"
        elif consecutive_below >= 2:
            pattern = "persistent_strategy"
            severity = "high"
        elif curr_ach < 0.85 and (n <= 1 or achieves[-2] >= 0.9 if n >= 2 else True):
            pattern = "new_issue"
            severity = "medium"
        elif consecutive_improving >= 2:
            pattern = "improving"
            severity = "low"
        elif curr_ach >= 1.0 and (n < 2 or achieves[-2] >= 1.0):
            pattern = "stable_star"
            severity = "info"

        info['pattern'] = pattern
        info['severity'] = severity
        info['consecutive_below'] = consecutive_below
        info['is_low_effort'] = is_low_effort

    # ── Step 4: Uplift quantification ──
    # Bucket-level weighted average rates
    bucket_avg_rates = {}
    bucket_total_vol = {}
    for bkt in SHOW_BUCKETS:
        groups_in_bkt = [(k, v) for k, v in group_trends.items() if v['bucket'] == bkt]
        total_vol = sum(v['volume'] for _, v in groups_in_bkt)
        if total_vol > 0:
            avg_rate = sum(v['rates'][-1] * v['volume'] for _, v in groups_in_bkt if v['rates']) / total_vol
            bucket_avg_rates[bkt] = avg_rate
            bucket_total_vol[bkt] = total_vol

    # Overall total volume across shown buckets
    overall_vol = sum(bucket_total_vol.values())

    uplift_table = []
    for key, info in group_trends.items():
        if not info['rates']:
            continue
        bkt = info['bucket']
        curr_rate = info['rates'][-1]
        bkt_avg = bucket_avg_rates.get(bkt, 0)

        if curr_rate >= bkt_avg or bkt_avg <= 0:
            continue  # Already at or above average

        # Uplift if this group improves to bucket average
        rate_gap = bkt_avg - curr_rate
        bucket_uplift_pp = rate_gap * info['weight']  # impact on bucket rate
        bkt_vol = bucket_total_vol.get(bkt, 1)
        bkt_weight_in_total = bkt_vol / overall_vol if overall_vol > 0 else 0
        overall_uplift_pp = bucket_uplift_pp * bkt_weight_in_total

        uplift_table.append({
            "bucket": bkt,
            "group": info['group'],
            "curr_rate": round(curr_rate, 4),
            "bucket_avg": round(bkt_avg, 4),
            "rate_gap_pp": round(rate_gap * 100, 2),
            "weight": info['weight'],
            "bucket_uplift_pp": round(bucket_uplift_pp * 100, 3),
            "overall_uplift_pp": round(overall_uplift_pp * 100, 3),
            "severity": info.get('severity', 'info'),
            "pattern": info.get('pattern', 'normal'),
        })

    uplift_table.sort(key=lambda x: x['overall_uplift_pp'], reverse=True)

    # ── Step 5: Narrative generation ──
    PATTERN_LABELS = {
        "persistent_lazy": "\u6301\u7eed\u4e0d\u8fbe\u6807+\u4e0d\u52e4\u594b",
        "persistent_strategy": "\u6301\u7eed\u4e0d\u8fbe\u6807(\u7b56\u7565\u95ee\u9898)",
        "accelerating_decline": "\u52a0\u901f\u6076\u5316",
        "new_issue": "\u65b0\u51fa\u73b0\u95ee\u9898",
        "improving": "\u6301\u7eed\u6539\u5584",
        "stable_star": "\u7a33\u5b9a\u8fbe\u6807",
        "declining": "\u4e0b\u6ed1\u8d8b\u52bf",
        "normal": "\u6b63\u5e38",
    }

    MONTH_LABELS = {}
    for m in actual_months:
        ms = str(int(m))
        MONTH_LABELS[int(m)] = f"{ms[:4]}\u5e74{ms[4:]}\u6708"

    findings = []
    for key, info in group_trends.items():
        pat = info.get('pattern', 'normal')
        sev = info.get('severity', 'info')
        if pat in ('normal', 'stable_star') and sev == 'info':
            continue

        bkt = info['bucket']
        grp = info['group']
        achieves = info['achieves']
        rates = info['rates']
        covs = info['covs']
        months = info['months']

        # Build narrative
        narrative_parts = []
        pat_label = PATTERN_LABELS.get(pat, pat)

        if pat in ('persistent_lazy', 'persistent_strategy', 'accelerating_decline', 'declining'):
            ach_str = '\u2192'.join([f"{a:.0%}" for a in achieves])
            narrative_parts.append(
                f"{bkt}-{grp} \u5df2\u8fde\u7eed{info['consecutive_below']}\u4e2a\u6708\u4e0d\u8fbe\u6807"
                f"\uff08\u8fbe\u6210\u7387 {ach_str}\uff09"
            )
        elif pat == 'new_issue':
            narrative_parts.append(
                f"{bkt}-{grp} \u672c\u6708\u65b0\u51fa\u73b0\u95ee\u9898"
                f"\uff08\u8fbe\u6210\u7387\u964d\u81f3 {achieves[-1]:.0%}\uff09"
            )
        elif pat == 'improving':
            ach_str = '\u2192'.join([f"{a:.0%}" for a in achieves])
            narrative_parts.append(
                f"{bkt}-{grp} \u6301\u7eed\u6539\u5584\uff08\u8fbe\u6210\u7387 {ach_str}\uff09"
            )

        # Coverage info
        if covs and any(c > 0 for c in covs) and pat in ('persistent_lazy', 'accelerating_decline'):
            valid_covs = [(m, c) for m, c in zip(months, covs) if c > 0]
            if len(valid_covs) >= 2:
                first_c = valid_covs[0][1]
                last_c = valid_covs[-1][1]
                avg_cov = module_avg_cov.get(bkt, 0)
                cov_trend = "down" if last_c < first_c else "up"
                narrative_parts.append(
                    f"\u8986\u76d6\u7387\u4ece{first_c:.0%}\u964d\u81f3{last_c:.0%}"
                    + (f"\uff0c\u4f4e\u4e8e\u6a21\u5757\u5747\u503c{avg_cov:.0%}" if avg_cov > 0 and last_c < avg_cov else "")
                )

        # Uplift info
        uplift_entry = next((u for u in uplift_table if u['bucket'] == bkt and u['group'] == grp), None)
        uplift_pp = 0
        if uplift_entry:
            uplift_pp = uplift_entry['overall_uplift_pp']
            if uplift_pp > 0.01:
                narrative_parts.append(
                    f"\u5982\u8be5\u7ec4\u63d0\u5347\u81f3{bkt}\u5e73\u5747\u6c34\u5e73\uff0c"
                    f"\u6574\u4f53\u53ef\u63d0\u5347\u7ea6{uplift_pp:.2f}pp"
                )

        narrative = "\uff0c".join(narrative_parts) + "\u3002" if narrative_parts else ""

        findings.append({
            "severity": sev,
            "type": pat,
            "type_label": pat_label,
            "bucket": bkt,
            "group": grp,
            "narrative": narrative,
            "achieves": achieves,
            "rates": rates,
            "covs": covs,
            "months": months,
            "uplift_pp": round(uplift_pp, 3),
            "volume": info['volume'],
        })

    # Sort by severity then uplift
    SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    findings.sort(key=lambda x: (SEVERITY_ORDER.get(x['severity'], 5), -x['uplift_pp']))

    # ── Summary ──
    critical_count = sum(1 for f in findings if f['severity'] == 'critical')
    high_count = sum(1 for f in findings if f['severity'] == 'high')
    total_potential = sum(u['overall_uplift_pp'] for u in uplift_table)

    # Serialize group_trends for JSON
    gt_serializable = {}
    for (bkt, grp), info in group_trends.items():
        gt_serializable[f"{bkt}|{grp}"] = info

    return {
        "findings": findings,
        "group_trends": gt_serializable,
        "uplift_table": uplift_table[:15],
        "summary": {
            "total_groups": len(group_trends),
            "critical_count": critical_count,
            "high_count": high_count,
            "potential_uplift_pp": round(float(total_potential), 2),
            "months": [int(m) for m in actual_months],
            "ref_day": ref_day,
        },
        "module_avg_cov": {k: round(v, 4) for k, v in module_avg_cov.items()},
        "module_avg_int": {k: round(v, 2) for k, v in module_avg_int.items()},
    }


# ─────────────────────────────────────────────────────────────────────────────
# [v4.10 NEW] 自然月回收序时 + 到期月回收曲线
# ─────────────────────────────────────────────────────────────────────────────

def compute_natural_month_progress(df_daily):
    """
    [v4.13] 计算自然月回收序时进度数据 — 4层下钻:
    L1 模块级(S0/S1/S2/M1...) → L2 大小额(S1_Large/S1_Small/S1_Other)
    → L3 组级(group_name) → L4 经办级(owner_id)

    计算口径: sum(repay_principal) / sum(start_owing_principal)  per day per month
    
    Outsource 合并规则: *_Outsource 统一合并到 *_Other (非大小额组)
    
    输出结构:
      levels: ["模块级","大小额","组级","经办级"]
      level_data:
        模块级:   {buckets, months, data, summary}              -- 多月模式
        大小额:   {buckets, months, data, summary, parent_map}  -- 多月模式
        组级:     {by_parent: {agent_bucket: {entities,months,data,summary}}} -- 对比模式
        经办级:   {by_parent: {group_name:  {entities,months,data,summary}}} -- 对比模式
    """
    if df_daily is None or df_daily.empty:
        return {}

    df_all = df_daily.copy()
    df_all['day'] = pd.to_numeric(df_all['day'], errors='coerce')
    df_all['natural_month'] = pd.to_numeric(df_all['natural_month'], errors='coerce')
    df_all['repay_principal'] = pd.to_numeric(df_all['repay_principal'], errors='coerce').fillna(0)
    df_all['start_owing_principal'] = pd.to_numeric(df_all['start_owing_principal'], errors='coerce').fillna(0)

    TARGET_MONTH = 250003

    def _merge_outsource(val):
        """将 *_Outsource 合并为 *_Other"""
        s = str(val)
        return s.replace('_Outsource', '_Other') if '_Outsource' in s else s

    def _points_from_agg(agg_df, group_col, filter_current_month=False):
        """从聚合 DF 生成标准数据结构
        [v4.16b] filter_current_month=True 时，只保留当月有数据的实体
        """
        if agg_df.empty:
            return [], [], {}, {}
        entities = sorted([str(b) for b in agg_df[group_col].dropna().unique()])
        all_months = sorted(agg_df['natural_month'].dropna().unique())
        actual_months = [m for m in all_months if m != TARGET_MONTH]

        result_data = {}
        summary = {}

        for ent in entities:
            ent_data = agg_df[agg_df[group_col].astype(str) == ent]
            result_data[ent] = {}

            for month in all_months:
                md = ent_data[ent_data['natural_month'] == month].sort_values('day')
                if md.empty:
                    continue
                pts = []
                for _, row in md.iterrows():
                    d = int(row['day'])
                    s = row['start_owing_principal']
                    r = row['repay_principal']
                    rate = r / s if s > 0 else 0
                    pts.append({"day": d, "cum_rate": round(rate, 6)})
                result_data[ent][int(month)] = pts

            # 达成率汇总
            if actual_months and TARGET_MONTH in result_data.get(ent, {}):
                lm = actual_months[-1]
                if lm in result_data[ent] and result_data[ent][lm]:
                    ap = result_data[ent][lm]
                    tp = result_data[ent].get(TARGET_MONTH, [])
                    ar = ap[-1]['cum_rate']
                    ad = ap[-1]['day']
                    trd = 0
                    trf = tp[-1]['cum_rate'] if tp else 0
                    for t in tp:
                        if t['day'] <= ad:
                            trd = t['cum_rate']
                    ach = ar / trd if trd > 0 else 0
                    summary[ent] = {
                        "target_rate": round(trf, 4),
                        "target_rate_at_day": round(trd, 4),
                        "actual_rate": round(ar, 4),
                        "achieve_pct": round(ach, 4),
                        "actual_day": ad,
                        "latest_month": int(lm)
                    }

        # [v4.16b] 过滤当月无数据的实体 (组级/经办级)
        if filter_current_month and actual_months:
            latest = int(actual_months[-1])
            entities = [e for e in entities if latest in result_data.get(e, {})]

        return entities, [int(m) for m in actual_months], result_data, summary

    # ==================================================================
    # L1: 模块级  (data_level = '1.模块层级', group by case_bucket)
    # ==================================================================
    df_l1 = df_all[df_all['data_level'] == '1.模块层级']
    if not df_l1.empty:
        l1_agg = df_l1.groupby(['natural_month', 'case_bucket', 'day'], as_index=False).agg(
            repay_principal=('repay_principal', 'sum'),
            start_owing_principal=('start_owing_principal', 'sum'))
        l1_ents, l1_months, l1_data, l1_summ = _points_from_agg(l1_agg, 'case_bucket')
    else:
        l1_ents, l1_months, l1_data, l1_summ = [], [], {}, {}

    l1_result = {"buckets": l1_ents, "months": l1_months, "target_month": TARGET_MONTH,
                 "data": l1_data, "summary": l1_summ}

    # ==================================================================
    # L2: 大小额  (data_level = '1.5.大小模块层级', merge Outsource→Other)
    # ==================================================================
    df_l2 = df_all[df_all['data_level'] == '1.5.大小模块层级'].copy()
    if not df_l2.empty:
        df_l2['case_bucket'] = df_l2['case_bucket'].apply(_merge_outsource)
        l2_agg = df_l2.groupby(['natural_month', 'case_bucket', 'day'], as_index=False).agg(
            repay_principal=('repay_principal', 'sum'),
            start_owing_principal=('start_owing_principal', 'sum'))
        l2_ents, l2_months, l2_data, l2_summ = _points_from_agg(l2_agg, 'case_bucket')
    else:
        l2_ents, l2_months, l2_data, l2_summ = [], [], {}, {}

    # parent_map: S1_Large → S1, S1_Other → S1
    l2_parent_map = {cb: cb.split('_')[0] for cb in l2_ents}

    l2_result = {"buckets": l2_ents, "months": l2_months, "target_month": TARGET_MONTH,
                 "data": l2_data, "summary": l2_summ, "parent_map": l2_parent_map}

    # ==================================================================
    # L3: 组级  (data_level = '4.组别层级', by_parent = agent_bucket)
    # ==================================================================
    df_l3 = df_all[df_all['data_level'] == '4.组别层级'].copy()
    l3_by_parent = {}
    if not df_l3.empty:
        df_l3['group_name'] = df_l3['group_name'].astype(str).str.strip()
        df_l3 = df_l3[df_l3['group_name'] != 'Target']
        df_l3['agent_bucket_m'] = df_l3['agent_bucket'].apply(_merge_outsource)

        for ab in sorted(df_l3['agent_bucket_m'].dropna().unique()):
            sub = df_l3[df_l3['agent_bucket_m'] == ab]
            agg = sub.groupby(['natural_month', 'group_name', 'day'], as_index=False).agg(
                repay_principal=('repay_principal', 'sum'),
                start_owing_principal=('start_owing_principal', 'sum'))
            ents, months, data, summ = _points_from_agg(agg, 'group_name', filter_current_month=True)
            if ents:
                l3_by_parent[str(ab)] = {"entities": ents, "months": months, "data": data, "summary": summ}

    l3_result = {"by_parent": l3_by_parent, "target_month": TARGET_MONTH}

    # ==================================================================
    # L4: 经办级  (data_level = '5.经办层级', by_parent = group_name)
    # ==================================================================
    df_l4 = df_all[df_all['data_level'] == '5.经办层级'].copy()
    l4_by_parent = {}
    if not df_l4.empty:
        df_l4['group_name'] = df_l4['group_name'].astype(str).str.strip()
        df_l4 = df_l4[df_l4['group_name'] != 'Target']
        # [v4.16b] owner_id → 去掉 .0 后缀, 转为整数字符串
        df_l4['owner_id'] = df_l4['owner_id'].apply(lambda x: str(int(x)) if pd.notna(x) and isinstance(x, (int, float)) else str(x).strip())

        for gn in sorted(df_l4['group_name'].dropna().unique()):
            sub = df_l4[df_l4['group_name'] == gn]
            agg = sub.groupby(['natural_month', 'owner_id', 'day'], as_index=False).agg(
                repay_principal=('repay_principal', 'sum'),
                start_owing_principal=('start_owing_principal', 'sum'))
            ents, months, data, summ = _points_from_agg(agg, 'owner_id', filter_current_month=True)
            if ents:
                l4_by_parent[str(gn)] = {"entities": ents, "months": months, "data": data, "summary": summ}

    l4_result = {"by_parent": l4_by_parent, "target_month": TARGET_MONTH}

    # ==================================================================
    # [v4.16b] 目标继承: 将模块级目标传递给组级/经办级子节点
    # 逻辑: 模块级 target 对整个模块通用, 子级没有自己的 target 数据,
    #        因此将父级 target 线 & summary 传递下去
    # ==================================================================
    def _inherit_target_to_children(child_result, parent_summary, parent_data, is_by_parent=False):
        """将模块级的 target 数据和达成率继承给子级实体"""
        if is_by_parent:
            # L3/L4: by_parent structure
            bp = child_result.get("by_parent", {})
            for parent_key, pg in bp.items():
                # 找到父级模块 (e.g. S1_Large_A → S1, or S1-Large A → S1)
                module = parent_key.split('_')[0].split('-')[0]
                parent_target = parent_data.get(module, {}).get(TARGET_MONTH)
                parent_summ = parent_summary.get(module, {})
                if not parent_target and not parent_summ:
                    continue

                ents = pg.get("entities", [])
                data = pg.get("data", {})
                summ = pg.get("summary", {})
                months = pg.get("months", [])
                actual_months = [m for m in months if m != TARGET_MONTH]

                for ent in ents:
                    ent_data = data.get(ent, {})
                    # 如果子级无 target 线，继承模块级 target
                    if TARGET_MONTH not in ent_data and parent_target:
                        ent_data[TARGET_MONTH] = parent_target
                        data[ent] = ent_data

                    # 如果子级无 summary，用实际值 + 模块级 target 计算
                    if ent not in summ and actual_months and parent_target:
                        lm = actual_months[-1]
                        if lm in ent_data and ent_data[lm]:
                            ap = ent_data[lm]
                            ar = ap[-1]['cum_rate']
                            ad = ap[-1]['day']
                            trd = 0
                            for t in parent_target:
                                if t['day'] <= ad:
                                    trd = t['cum_rate']
                            ach = ar / trd if trd > 0 else 0
                            summ[ent] = {
                                "target_rate": round(parent_target[-1]['cum_rate'], 4) if parent_target else 0,
                                "target_rate_at_day": round(trd, 4),
                                "actual_rate": round(ar, 4),
                                "achieve_pct": round(ach, 4),
                                "actual_day": ad,
                                "latest_month": int(lm)
                            }
                pg["summary"] = summ
                pg["data"] = data
        else:
            # L2: flat structure
            data = child_result.get("data", {})
            summ = child_result.get("summary", {})
            months = child_result.get("months", [])
            actual_months = [m for m in months if m != TARGET_MONTH]
            buckets = child_result.get("buckets", [])

            for ent in buckets:
                module = ent.split('_')[0].split('-')[0]
                parent_target = parent_data.get(module, {}).get(TARGET_MONTH)
                parent_summ_ent = parent_summary.get(module, {})
                if not parent_target:
                    continue

                ent_data = data.get(ent, {})
                if TARGET_MONTH not in ent_data:
                    ent_data[TARGET_MONTH] = parent_target
                    data[ent] = ent_data

                if ent not in summ and actual_months:
                    lm = actual_months[-1]
                    if lm in ent_data and ent_data[lm]:
                        ap = ent_data[lm]
                        ar = ap[-1]['cum_rate']
                        ad = ap[-1]['day']
                        trd = 0
                        for t in parent_target:
                            if t['day'] <= ad:
                                trd = t['cum_rate']
                        ach = ar / trd if trd > 0 else 0
                        summ[ent] = {
                            "target_rate": round(parent_target[-1]['cum_rate'], 4),
                            "target_rate_at_day": round(trd, 4),
                            "actual_rate": round(ar, 4),
                            "achieve_pct": round(ach, 4),
                            "actual_day": ad,
                            "latest_month": int(lm)
                        }
            child_result["summary"] = summ
            child_result["data"] = data

    # 继承目标到子级
    if l1_summ and l1_data:
        if l2_ents:
            _inherit_target_to_children(l2_result, l1_summ, l1_data, is_by_parent=False)
        if l3_by_parent:
            _inherit_target_to_children(l3_result, l1_summ, l1_data, is_by_parent=True)
        if l4_by_parent:
            _inherit_target_to_children(l4_result, l1_summ, l1_data, is_by_parent=True)

    # ==================================================================
    # 组装结果
    # ==================================================================
    levels = ["模块级"]
    level_data = {"模块级": l1_result}

    if l2_ents:
        levels.append("大小额")
        level_data["大小额"] = l2_result
    if l3_by_parent:
        levels.append("组级")
        level_data["组级"] = l3_result
    if l4_by_parent:
        levels.append("经办级")
        level_data["经办级"] = l4_result

    return {
        "levels": levels,
        "level_data": level_data,
        # 向后兼容: 顶层 = 模块级
        **l1_result
    }


def compute_due_month_recovery(df_due):
    """
    [v4.11 Fix] 计算到期月回收曲线数据 — 只按 user_type 区分，不拆 bucket。
    
    输入: DataFrame (due_month_repay sheet)
      - days_from_duedate, due_mth, user_type, flag_bucket, overdue_principal_boc, owing_principal_eoc
    
    逻辑:
      - 取 flag_bucket='ALL' 作为汇总层级 (如无 ALL 则手动聚合)
      - 回收率 = 1 - SUM(owing_principal_eoc) / SUM(overdue_principal_boc)
      - overdue_principal_boc: 到期且逾期的本金 (时序概念，从到期月1号开始累计)
    
    输出: dict {
        "user_types": ["新客", "老客"],
        "due_months": [202508, 202509, ...],
        "data": {
            "老客": {
                202508: [{"day": 2, "recovery_rate": 0.001}, ...],
                ...
            },
            ...
        }
    }
    """
    if df_due is None or df_due.empty:
        return {}
    
    df = df_due.copy()
    df['days_from_duedate'] = pd.to_numeric(df['days_from_duedate'], errors='coerce')
    df['due_mth'] = pd.to_numeric(df['due_mth'], errors='coerce')
    df['overdue_principal_boc'] = pd.to_numeric(df['overdue_principal_boc'], errors='coerce').fillna(0)
    df['owing_principal_eoc'] = pd.to_numeric(df['owing_principal_eoc'], errors='coerce').fillna(0)
    
    # [v4.11] 只取 ALL bucket (已是汇总层级)，不再区分 bucket
    if 'flag_bucket' in df.columns:
        df_all = df[df['flag_bucket'] == 'ALL']
        if df_all.empty:
            # 无 ALL 标记，手动聚合全部 bucket
            df_all = df.copy()
    else:
        df_all = df.copy()
    
    # 聚合到 (user_type, due_mth, days_from_duedate) 粒度
    agg = df_all.groupby(['user_type', 'due_mth', 'days_from_duedate'], as_index=False).agg(
        boc=('overdue_principal_boc', 'sum'),
        eoc=('owing_principal_eoc', 'sum')
    )
    
    user_types = sorted(agg['user_type'].dropna().unique())
    due_months = sorted(agg['due_mth'].dropna().unique())
    
    result_data = {}
    
    for ut in user_types:
        sub = agg[agg['user_type'] == ut]
        result_data[str(ut)] = {}
        
        for dm in due_months:
            dm_data = sub[sub['due_mth'] == dm].sort_values('days_from_duedate')
            if dm_data.empty:
                continue
            
            points = []
            for _, row in dm_data.iterrows():
                d = int(row['days_from_duedate'])
                boc = row['boc']
                eoc = row['eoc']
                recovery = 1 - (eoc / boc) if boc > 0 else 0
                points.append({"day": d, "recovery_rate": round(recovery, 6)})
            
            result_data[str(ut)][int(dm)] = points
    
    return {
        "user_types": [str(u) for u in user_types],
        "due_months": [int(m) for m in due_months],
        "data": result_data
    }


# ─────────────────────────────────────────────────────────────────────────────
# [v4.19 MAJOR] Shift-Share 归因中心 — 预聚合 + 前端动态计算
# ─────────────────────────────────────────────────────────────────────────────

def compute_shift_share(df_vintage):
    """
    [v4.19] 预聚合所有月份 × 维度 × 指标的段级数据，
    嵌入 HTML 后由前端 JS 实时计算 Shift-Share 分解。

    关键设计:
      - Python 端: 做重活（数据清洗、聚合、Safe Denominator 过滤）
      - JS 端: 做轻活（用户选月份/客群后，实时算 Shift-Share 公式）
      
    输出结构:
      {
        "months": ["2025-10", "2025-11", ...],       # 可选月份列表
        "user_types": ["全部", "新客", "老客"],        # 客群筛选选项
        "metric_defs": {"overdue_rate": {"label": "入催率", "maturity": 0}, ...},
        "dim_defs": {"user_type": {"label": "新老客"}, ...},
        "agg": {                                       # 预聚合数据
          "全部": {                                    #   客群
            "overdue_rate": {                          #     指标
              "user_type": {                           #       维度
                "2025-10": [                           #         月份
                  {"name": "新客", "num": 1000, "den": 50000},
                  {"name": "老客", "num": 2000, "den": 100000}
                ], ...
              }, ...
            }, ...
          }, ...
        }
      }
    """
    if df_vintage is None or df_vintage.empty:
        return {}

    df = df_vintage.copy()
    df['due_date'] = pd.to_datetime(df['due_date'], errors='coerce')
    df.dropna(subset=['due_date'], inplace=True)
    
    if df.empty:
        return {}

    # ── 数据清洗 ──
    df['amount_bin'] = df['flag_principal'].astype(str)
    for c in ['owing_principal', 'overdue_principal', 'd5_principal',
              'd7_principal', 'd15_principal', 'd30_principal', 'loan_cnt']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    
    df['period_seq_str'] = df['period_seq'].apply(
        lambda x: f"{int(x)}期" if pd.notna(x) else "Unknown")
    df['period_no_str'] = df['period_no'].apply(
        lambda x: f"第{int(x)}期" if pd.notna(x) else "Unknown")
    if 'mob' in df.columns:
        def _fmt_mob(x):
            if pd.isna(x):
                return "Unknown"
            try:
                return f"MOB{int(float(x))}"
            except (ValueError, TypeError):
                return str(x)
        df['mob_str'] = df['mob'].apply(_fmt_mob)
    else:
        df['mob_str'] = "Unknown"
    if 'model_bin' in df.columns:
        df['model_bin_str'] = df['model_bin'].astype(str)
    else:
        df['model_bin_str'] = "Unknown"
    
    df['ym'] = df['due_date'].dt.to_period('M')
    today = pd.Timestamp.now().normalize()
    df['days_since_due'] = (today - df['due_date']).dt.days
    
    months_all = sorted(df['ym'].dropna().unique())
    if len(months_all) < 2:
        return {}
    
    month_labels = [str(m) for m in months_all]
    
    # 识别新老客 — 合并"存量老客"和"新转化老客"为"老客"
    ut_merge_map = {'存量老客': '老客', '新转化老客': '老客'}
    df['user_type'] = df['user_type'].replace(ut_merge_map)
    user_types_raw = sorted(df['user_type'].dropna().unique())
    # 构建客群筛选器: "全部" + 各 user_type
    ut_filters = {"全部": None}  # None = 不过滤
    for ut in user_types_raw:
        ut_filters[str(ut)] = ut
    
    # ── 指标 & 维度定义 ──
    metric_defs = {
        "overdue_rate": {"num": "overdue_principal", "den": "owing_principal", "maturity": 0,  "label": "入催率"},
        "dpd5":         {"num": "d5_principal",      "den": "owing_principal", "maturity": 5,  "label": "DPD5"},
        "dpd7":         {"num": "d7_principal",      "den": "owing_principal", "maturity": 7,  "label": "DPD7"},
        "dpd15":        {"num": "d15_principal",     "den": "owing_principal", "maturity": 15, "label": "DPD15"},
        "dpd30":        {"num": "d30_principal",     "den": "owing_principal", "maturity": 30, "label": "DPD30"},
    }
    # 只保留数据中实际存在的指标
    metric_defs = {k: v for k, v in metric_defs.items() if v["num"] in df.columns}
    
    dim_defs = {
        "user_type":  {"col": "user_type",       "label": "新老客"},
        "period_seq": {"col": "period_seq_str",  "label": "产品期数"},
        "period_no":  {"col": "period_no_str",   "label": "当前期数"},
        "mob":        {"col": "mob_str",         "label": "MOB"},
        "amount_bin": {"col": "amount_bin",      "label": "金额段"},
        "model_bin":  {"col": "model_bin_str",   "label": "风险评分"},
    }

    # ── 预聚合: 遍历 客群 × 指标 × 维度 × 月份 ──
    agg_data = {}
    
    for ut_label, ut_value in ut_filters.items():
        df_ut = df if ut_value is None else df[df['user_type'] == ut_value]
        if df_ut.empty:
            continue
        
        ut_agg = {}
        
        for mk, mdef in metric_defs.items():
            num_col = mdef["num"]
            den_col = mdef["den"]
            maturity = mdef["maturity"]
            
            # Safe Denominator: 只取成熟样本
            df_mature = df_ut[df_ut['days_since_due'] >= maturity]
            if df_mature.empty:
                continue
            
            metric_agg = {}
            
            for dk, ddef in dim_defs.items():
                col = ddef["col"]
                dim_months = {}
                
                for m in months_all:
                    df_m = df_mature[df_mature['ym'] == m]
                    if df_m.empty:
                        continue
                    
                    g = df_m.groupby(col, dropna=False).agg(
                        num=(num_col, 'sum'),
                        den=(den_col, 'sum')
                    ).reset_index()
                    
                    segments = []
                    for _, row in g.iterrows():
                        name = str(row[col]) if pd.notna(row[col]) else "Unknown"
                        segments.append({
                            "name": name,
                            "num": round(float(row['num']), 2),
                            "den": round(float(row['den']), 2),
                        })
                    
                    if segments:
                        dim_months[str(m)] = segments
                
                if dim_months:
                    metric_agg[dk] = dim_months
            
            if metric_agg:
                ut_agg[mk] = metric_agg
        
        if ut_agg:
            agg_data[ut_label] = ut_agg
    
    if not agg_data:
        return {}
    
    # ── 构建输出 ──
    return {
        "months": month_labels,
        "user_types": list(ut_filters.keys()),
        "metric_defs": {k: {"label": v["label"], "maturity": v["maturity"]} for k, v in metric_defs.items()},
        "dim_defs": {k: {"label": v["label"]} for k, v in dim_defs.items()},
        "agg": agg_data,
    }


if __name__ == "__main__":
    main()
