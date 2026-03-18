# -*- coding: utf-8 -*-
"""
Collection inspection - daily report (read local Excel -> metrics -> simple anomalies -> HTML).
v4.6 Upgrade:
- Standardized 'overdue_rate' naming (replacing entrant_rate).
- Preserves v4.4 logic perfectly (Base for sidebar UI upgrade).
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

    # 1. Base (Overdue Rate / previously Entrant) - Lag >= 1 (T+1)
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
    """Calculate WoW delta for risk metrics."""
    # Added dpd1 to list
    metrics = ["overdue_rate", "dpd1", "dpd5", "dpd7", "dpd15", "dpd30", "connect_conversion", "ptp_conversion"]
    for m in metrics:
        if m in curr and m in prev:
            vc = curr[m]
            vp = prev[m]
            if isinstance(vc, (int, float)) and isinstance(vp, (int, float)) and vp != 0:
                curr[f"{m}_wow"] = (vc - vp) / vp


def compute_term_monitoring_matrix(df_v, metric="overdue_rate"):
    """
    [v4.3] 期限监控矩阵: 纵轴=到期月, 横轴=MOB1~4 (period_no 1~4).
    period_no=当前期数(放款账龄), period_seq=总期数(1期/3期/6期).
    [v4.4] Support multiple metrics (overdue, dpd5, dpd7, dpd15, dpd30) and Lift.
    """
    out = {}
    if df_v is None or df_v.empty:
        return out
    df = df_v.copy()
    if "due_date" not in df.columns or "period_no" not in df.columns:
        return out
    df["due_month"] = pd.to_datetime(df["due_date"]).dt.to_period("M").astype(str)
    
    has_seq = "period_seq" in df.columns
    has_user = "user_type" in df.columns

    # [v4.4] User Type Mapping
    # "新客" -> "New"
    # "老客", "存量老客", "新转化老客" -> "Old"
    if has_user:
        def map_user(u):
            u_str = str(u)
            if "新客" in u_str: return "New"
            if any(x in u_str for x in ["老客", "存量", "转化"]): return "Old"
            return "Other"
        df["user_group"] = df["user_type"].apply(map_user)
    else:
        df["user_group"] = "All"

    # Pre-calculate lag for Safe Denominator
    today = pd.Timestamp.now().normalize()
    if "due_date" in df.columns:
        df["lag_days"] = (today - pd.to_datetime(df["due_date"])).dt.days
    else:
        df["lag_days"] = 999

    def _build_matrix(sub):
        if sub.empty:
            return {} # Return empty dict, will be filled with defaults
        
        # Metrics to calc
        # overdue_rate (DPD1+), dpd5 (d6), dpd7 (d8), dpd15 (d16), dpd30 (d31)
        # Using Safe Denominator logic
        
        # Group by due_month, period_no
        # We need to aggregate numerators and denominators separately to handle safe denom
        
        # 1. Base (Overdue Rate)
        g_base = sub.groupby(["due_month", "period_no"]).agg(
            owing=("owing_principal", "sum"),
            overdue=("overdue_principal", "sum")
        ).reset_index()
        
        # 2. DPD5 (d6, lag>=6)
        sub_d5 = sub[sub["lag_days"] >= 6]
        g_d5 = sub_d5.groupby(["due_month", "period_no"]).agg(
            owing_d5=("owing_principal", "sum"),
            d5=("d6_principal", "sum")
        ).reset_index() if not sub_d5.empty else pd.DataFrame(columns=["due_month", "period_no", "owing_d5", "d5"])
        
        # 3. DPD7 (d8, lag>=8)
        sub_d7 = sub[sub["lag_days"] >= 8]
        g_d7 = sub_d7.groupby(["due_month", "period_no"]).agg(
            owing_d7=("owing_principal", "sum"),
            d7=("d8_principal", "sum")
        ).reset_index() if not sub_d7.empty else pd.DataFrame(columns=["due_month", "period_no", "owing_d7", "d7"])

        # 4. DPD15 (d16, lag>=16)
        sub_d15 = sub[sub["lag_days"] >= 16]
        g_d15 = sub_d15.groupby(["due_month", "period_no"]).agg(
            owing_d15=("owing_principal", "sum"),
            d15=("d16_principal", "sum")
        ).reset_index() if not sub_d15.empty else pd.DataFrame(columns=["due_month", "period_no", "owing_d15", "d15"])

        # 5. DPD30 (d31, lag>=31)
        sub_d30 = sub[sub["lag_days"] >= 31]
        g_d30 = sub_d30.groupby(["due_month", "period_no"]).agg(
            owing_d30=("owing_principal", "sum"),
            d30=("d31_principal", "sum")
        ).reset_index() if not sub_d30.empty else pd.DataFrame(columns=["due_month", "period_no", "owing_d30", "d30"])

        # Merge all
        merged = g_base
        for g_other in [g_d5, g_d7, g_d15, g_d30]:
            if not g_other.empty:
                merged = pd.merge(merged, g_other, on=["due_month", "period_no"], how="left")
        
        # Calculate Rates
        merged["rate_overdue"] = merged["overdue"] / merged["owing"].replace(0, np.nan)
        if "d5" in merged.columns: merged["rate_dpd5"] = merged["d5"] / merged["owing_d5"].replace(0, np.nan)
        if "d7" in merged.columns: merged["rate_dpd7"] = merged["d7"] / merged["owing_d7"].replace(0, np.nan)
        if "d15" in merged.columns: merged["rate_dpd15"] = merged["d15"] / merged["owing_d15"].replace(0, np.nan)
        if "d30" in merged.columns: merged["rate_dpd30"] = merged["d30"] / merged["owing_d30"].replace(0, np.nan)
        
        # Pivot for each metric
        res = {}
        metrics_map = {
            "overdue_rate": "rate_overdue",
            "dpd5": "rate_dpd5", 
            "dpd7": "rate_dpd7",
            "dpd15": "rate_dpd15",
            "dpd30": "rate_dpd30"
        }
        
        # Dynamic columns (MOBs)
        cols = sorted(merged["period_no"].unique())
        
        for m_key, m_col in metrics_map.items():
            if m_col not in merged.columns:
                res[m_key] = {"matrix": [], "columns": cols}
                continue
                
            piv = merged.pivot(index="due_month", columns="period_no", values=m_col)
            piv = piv.reindex(columns=cols)
            piv = piv.sort_index(ascending=False)
            
            # Calculate Lift (MoM)
            # Row i vs Row i+1
            rows = []
            months = list(piv.index)
            for i, due_m in enumerate(months):
                row = {"due_month": due_m}
                for c in cols:
                    val = piv.loc[due_m, c]
                    row[f"MOB{c}"] = round(val, 4) if pd.notna(val) else None
                    
                    # Lift
                    lift = None
                    if i < len(months) - 1:
                        prev_m = months[i+1]
                        prev_val = piv.loc[prev_m, c]
                        if pd.notna(val) and pd.notna(prev_val) and prev_val > 0:
                            lift = round((val - prev_val) / prev_val, 4)
                    row[f"MOB{c}_lift"] = lift
                rows.append(row)
            
            res[m_key] = {"matrix": rows, "columns": cols}
            
        return res

    # [v4.4] Grouped User Slices
    # We use the mapped 'user_group'
    user_slices = [("user_all", None, "All")]
    if has_user:
        # Fixed groups
        user_slices.append(("user_new", "New", "新客"))
        user_slices.append(("user_old", "Old", "老客 (含转化)"))

    # Dynamic Seq Slices
    seq_slices = [("seq_all", None, "All")]
    if has_seq:
        seqs = sorted([s for s in df["period_seq"].dropna().unique()])
        for s in seqs:
            s_int = int(s) if s == int(s) else s
            skey = f"seq_{s_int}"
            seq_slices.append((skey, s, f"{s_int}期"))

    out["meta"] = {
        "user_labels": [(k, l) for k, _, l in user_slices],
        "seq_labels": [(k, l) for k, _, l in seq_slices],
        "metrics": ["overdue_rate", "dpd5", "dpd7", "dpd15", "dpd30"]
    }

    for ukey, uval, _ in user_slices:
        sub_u = df if uval is None else df[df["user_group"] == uval]
        out[ukey] = {}
        for skey, sval, _ in seq_slices:
            sub = sub_u if sval is None else sub_u[sub_u["period_seq"] == sval]
            out[ukey][skey] = _build_matrix(sub)
            
    return out


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
        "period_no": "放款账龄 (MOB)"
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
            curr_start = max_date
            curr_end = max_date
            prev_start = max_date - pd.Timedelta(days=1)
            prev_end = max_date - pd.Timedelta(days=1)
            meta_period = "Last 1 Day"
            
        elif mode == 'monthly':
            # Current Month vs Last Month
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
    [v3 Upgrade]: Uses Safe Denominator logic.
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
        
        # 1. Base (Overdue Rate)
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
    for i in range(len(results) - 1):
        curr = results[i]
        prev = results[i+1]
        for m in metrics_to_diff:
            if m in curr and m in prev:
                vc = curr[m]
                vp = prev[m]
                if isinstance(vc, (int, float)) and isinstance(vp, (int, float)):
                    if vp != 0:
                        curr[f"{m}_change"] = (vc - vp) / vp
                    elif vc > 0:
                        curr[f"{m}_change"] = 1.0 
                    elif vc == 0:
                        curr[f"{m}_change"] = 0.0

    return results

def compute_amount_pivot(df):
    """
    [v3.5 New] Generate Pivot Data for Heatmap (Month x Amount).
    Metrics: overdue_rate, dpd1, dpd5, dpd30.
    """
    if df is None or df.empty or "due_date" not in df.columns or "flag_principal" not in df.columns:
        return {}

    df = df.copy()
    if not np.issubdtype(df["due_date"].dtype, np.datetime64):
        df["due_date"] = pd.to_datetime(df["due_date"])
        
    df["due_month"] = df["due_date"].dt.to_period("M").dt.strftime("%Y-%m")
    
    # Group
    grouped = df.groupby(["due_month", "flag_principal"])
    
    pivot_data = {} 
    metrics = ["overdue_rate", "dpd1", "dpd5", "dpd7", "dpd15", "dpd30"]
    
    for m in metrics:
        pivot_data[m] = {}

    for (month, amt), grp in grouped:
        res = _calc_risk_metrics(grp)
        
        for m in metrics:
            val = res.get(m)
            if val is not None:
                if month not in pivot_data[m]:
                    pivot_data[m][month] = {}
                pivot_data[m][month][amt] = val
                
    return pivot_data

def compute_vintage_matrix(df, limit=30):
    """Legacy Daily Matrix."""
    return compute_aggregated_vintage(df, period='D', limit=limit)


def compute_aggregated_vintage(df, period='D', limit=30):
    """
    [v3.1 Enhanced] Multi-dimension Vintage Matrix (Daily/Weekly/Monthly).
    [v4.6] Renamed entrant_rate -> overdue_rate.
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
        
        # 1. Overdue Rate (Entrant)
        owing = grp["owing_principal"].sum()
        overdue = grp["overdue_principal"].sum()
        overdue_rate = overdue / owing if owing > 0 else 0.0
        
        item = {
            "period": key,
            "rows": len(grp),
            "overdue_rate": round(overdue_rate, 4), # Renamed
            "recovery": {},
            "dpd_rates": {} 
        }
        
        # 2. Loop D1..D30
        for k in range(1, 31): 
            # DPD Column (Balance at Dk)
            # Matrix 'D1' means DPD1 (Due+1), so use d2_principal.
            dpd_col = f"d{k+1}_principal" 
            
            # For Recovery, D1 Recovery (Rec at D1) uses d2 vs overdue.
            rec_src_col = dpd_col
            
            lags = (today - grp["due_date"]).dt.days
            
            # --- DPD Rate ---
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
    [v4.6] Renamed entrant_rate -> overdue_rate.
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
    
    # If no data for current month, try to infer 'today'
    if df_curr.empty:
        max_all = df["due_date"].max()
        if pd.notna(max_all):
            curr_month_start = max_all.replace(day=1)
            df_curr = df[df["due_date"] >= curr_month_start]
            today = max_all 

    max_curr_date = df_curr["due_date"].max()
    if pd.isna(max_curr_date):
        return {"status": "No current month data"}

    days_progress = (max_curr_date - curr_month_start).days + 1
    
    # Function to get MTD data for a target month start
    def get_mtd_data(target_start_date):
        target_end_mtd = target_start_date + pd.Timedelta(days=days_progress - 1)
        return df[(df["due_date"] >= target_start_date) & (df["due_date"] <= target_end_mtd)]

    # 2. Comparison Periods
    m1_start = (curr_month_start - pd.Timedelta(days=1)).replace(day=1)
    df_m1 = get_mtd_data(m1_start)
    
    m2_start = (m1_start - pd.Timedelta(days=1)).replace(day=1)
    df_m2 = get_mtd_data(m2_start)
    
    try:
        y1_start = curr_month_start.replace(year=curr_month_start.year - 1)
        df_y1 = get_mtd_data(y1_start)
    except ValueError: 
        y1_start = curr_month_start.replace(year=curr_month_start.year - 1, day=28) 
        df_y1 = get_mtd_data(y1_start)
    
    # 3. Aggregate Metrics Helper
    def calc_aggs(sub_df, label):
        if sub_df.empty:
            return None
            
        owing = sub_df["owing_principal"].sum()
        overdue = sub_df["overdue_principal"].sum()
        
        def slice_by_lag(lag_days):
            if days_progress <= lag_days:
                return pd.DataFrame() 
            period_len_days = days_progress - lag_days
            min_d = sub_df["due_date"].min()
            cutoff = min_d + pd.Timedelta(days=period_len_days - 1)
            return sub_df[sub_df["due_date"] <= cutoff]

        # DPD1 (d2)
        sub_d1 = slice_by_lag(1)
        if not sub_d1.empty:
            owing_d1 = sub_d1["owing_principal"].sum()
            bal_d1 = sub_d1["d2_principal"].sum() if "d2_principal" in sub_d1.columns else 0
            rate_d1 = (bal_d1 / owing_d1) if owing_d1 > 0 else None 
        else:
            rate_d1 = None
        
        # DPD5 (d6)
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
            "overdue_rate": overdue / owing if owing > 0 else 0, # Renamed
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
    return compute_trend_by_period(df, period='D', limit=max_days)

def compute_repay_summary(df_list, names):
    """Recovery summary with Attribution (Drill-down)."""
    out = {}
    anomalies = []
    
    for df, name in zip(df_list, names):
        if df is None or df.empty:
            out[name] = {"rows": 0, "status": "No Data"}
            continue
            
        global_rows = len(df)
        global_rate = 0.0
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
                        if rv != rv or rv is None:  
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
    if not all(c in df.columns for c in cols):
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

def compute_collection_performance(df, df_process=None):
    """
    [v4.1 New] Recovery Attribution & Driver Analysis.
    """
    if df is None or df.empty:
        return {}
        
    out = {}
    df = df.copy()
    
    if "natural_month" not in df.columns:
        return {}
    
    df["natural_month"] = df["natural_month"].astype(str)
    
    # 1. Identify Months
    all_months = sorted(df["natural_month"].unique().tolist())
    months = [m for m in all_months if not m.startswith("25")]
    target_month = next((m for m in all_months if m.startswith("25")), None)
    
    if not months: return {}
    
    curr_month = months[-1]
    prev_month = months[-2] if len(months) > 1 else None
    
    out["meta"] = {"current": curr_month, "prev": prev_month, "target": target_month}
    
    # Filter Repay Data
    df_curr = df[df["natural_month"] == curr_month]
    df_prev = df[df["natural_month"] == prev_month] if prev_month else pd.DataFrame()

    # 2. Prepare Process Data
    proc_map_curr = {} 
    proc_map_prev = {}
    proc_bm_curr = {} 

    if df_process is not None and not df_process.empty:
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

        df_p_c = df_process[df_process["natural_month"].astype(str) == str(curr_month)]
        proc_map_curr = _get_proc_map(df_p_c)
        
        if not df_p_c.empty:
            g_b_p = df_p_c.groupby("owner_bucket").apply(
                lambda x: pd.Series({
                    "cov": (x["cover_rate"] * x["raw_owing_case_cnt"]).sum() / x["raw_owing_case_cnt"].sum() if x["raw_owing_case_cnt"].sum() > 0 else 0,
                    "conn": (x["case_connect_rate"] * x["raw_owing_case_cnt"]).sum() / x["raw_owing_case_cnt"].sum() if x["raw_owing_case_cnt"].sum() > 0 else 0,
                    "int": (x["call_times_avg"] * x["raw_owing_case_cnt"]).sum() / x["raw_owing_case_cnt"].sum() if x["raw_owing_case_cnt"].sum() > 0 else 0,
                })
            ).to_dict("index")
            proc_bm_curr = g_b_p

        if prev_month:
            df_p_p = df_process[df_process["natural_month"].astype(str) == str(prev_month)]
            proc_map_prev = _get_proc_map(df_p_p)

    out["proc_benchmarks"] = proc_bm_curr
    
    # 3. Bucket Level Summary
    out["buckets"] = []
    out["groups"] = {}
    out["agents"] = {}
    
    if "agent_bucket" in df_curr.columns:
        g_bucket = df_curr.groupby("agent_bucket").agg({
            "repay_principal": "sum",
            "start_owing_principal": "sum"
        }).reset_index()
        g_bucket["repay_rate"] = g_bucket["repay_principal"] / g_bucket["start_owing_principal"]
        
        bm_map = {}
        if not df_prev.empty and "agent_bucket" in df_prev.columns:
            g_prev_b = df_prev.groupby("agent_bucket").agg({
                "repay_principal": "sum",
                "start_owing_principal": "sum"
            })
            g_prev_b["rate"] = g_prev_b["repay_principal"] / g_prev_b["start_owing_principal"]
            bm_map = g_prev_b["rate"].to_dict()
            
        out["buckets"] = g_bucket.to_dict("records")
        out["benchmarks"] = bm_map

        grp_prev_map = {} 
        if not df_prev.empty and "group_name" in df_prev.columns:
            g_grp_p = df_prev.groupby(["agent_bucket", "group_name"]).agg({
                "repay_principal": "sum",
                "start_owing_principal": "sum"
            }).reset_index()
            for _, r in g_grp_p.iterrows():
                vol = r["start_owing_principal"]
                rate = r["repay_principal"] / vol if vol > 0 else 0
                grp_prev_map[(r["agent_bucket"], r["group_name"])] = {"rate": rate, "vol": vol}

        for bucket in g_bucket["agent_bucket"].unique():
            sub = df_curr[df_curr["agent_bucket"] == bucket]
            
            bkt_vol = sub["start_owing_principal"].sum()
            bkt_rate_prev = bm_map.get(bucket, 0.0)
            
            if "group_name" in sub.columns:
                g_grp = sub.groupby("group_name").agg({
                    "repay_principal": "sum",
                    "start_owing_principal": "sum"
                }).reset_index()
                
                recs = []
                for _, row in g_grp.iterrows():
                    grp_name = row["group_name"]
                    vol = row["start_owing_principal"]
                    rate = row["repay_principal"] / vol if vol > 0 else 0
                    
                    weight = vol / bkt_vol if bkt_vol > 0 else 0
                    
                    hist = grp_prev_map.get((bucket, grp_name), {})
                    rate_prev = hist.get("rate", 0.0)
                    has_hist = (bucket, grp_name) in grp_prev_map
                    if not has_hist: rate_prev = bkt_rate_prev 
                    
                    rate_delta_mom = rate - rate_prev
                    contrib = rate_delta_mom * weight
                    
                    p_curr = proc_map_curr.get((bucket, grp_name), {})
                    p_prev = proc_map_prev.get((bucket, grp_name), {}) 
                    
                    rec = {
                        "group_name": grp_name,
                        "repay_rate": rate,
                        "vol": vol,
                        "weight": weight,
                        "rate_prev": rate_prev,
                        "rate_delta_mom": rate_delta_mom,
                        "contrib_to_delta": contrib,
                        "cov": p_curr.get("cov", 0),
                        "conn": p_curr.get("conn", 0),
                        "int": p_curr.get("int", 0),
                        "cov_mom": p_curr.get("cov", 0) - p_prev.get("cov", 0) if p_prev else 0,
                        "conn_mom": p_curr.get("conn", 0) - p_prev.get("conn", 0) if p_prev else 0,
                        "int_mom": p_curr.get("int", 0) - p_prev.get("int", 0) if p_prev else 0,
                        "has_hist": has_hist
                    }
                    
                    drivers = []
                    if rate_delta_mom < -0.005: 
                        pd_map = {
                            "Cov": rec["cov_mom"], 
                            "Conn": rec["conn_mom"], 
                            "Int": rec["int_mom"]
                        }
                        neg_drivers = {k: v for k, v in pd_map.items() if v < -0.01} 
                        if neg_drivers:
                            worst = sorted(neg_drivers.items(), key=lambda x: x[1])[0]
                            rec["main_driver"] = f"{worst[0]} {worst[1]:.1%}"
                        else:
                            rec["main_driver"] = "Efficiency" 
                    else:
                        rec["main_driver"] = "-"
                        
                    recs.append(rec)
                
                recs.sort(key=lambda x: x["contrib_to_delta"]) 
                
                p_bm = proc_bm_curr.get(bucket, {"cov":0, "conn":0, "int":0})
                
                out["groups"][bucket] = {
                    "all": recs,
                    "benchmark": bkt_rate_prev,
                    "proc_benchmark": p_bm
                }

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

if __name__ == "__main__":
    pass
