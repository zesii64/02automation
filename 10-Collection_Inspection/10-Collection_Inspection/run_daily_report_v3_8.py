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
    """Calculate WoW delta for risk metrics."""
    # Added dpd1 to list
    metrics = ["overdue_rate", "dpd1", "dpd5", "dpd7", "dpd15", "dpd30", "connect_conversion", "ptp_conversion"]
    for m in metrics:
        if m in curr and m in prev:
            vc = curr[m]
            vp = prev[m]
            if isinstance(vc, (int, float)) and isinstance(vp, (int, float)) and vp != 0:
                curr[f"{m}_wow"] = (vc - vp) / vp

def compute_risk_attribution(df_curr, df_prev):
    """
    [v3.6 New] Risk Attribution Analysis (Structure Shift vs Rate Shift).
    [v3.8 Enhanced] Added Connect Rate (Contactability).
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
                
                # [v3.8 New] Connect Rate
                conn_bal_c = sub_c["conn_conv_base"].sum() if "conn_conv_base" in sub_c.columns and not sub_c.empty else 0
                conn_rate_c = conn_bal_c / ov_c if ov_c > 0 else 0.0
                
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
                    "curr_conn_rate": conn_rate_c, # [v3.8]
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
            
            # [v3.8] Connect Rate
            conn_bal = sub["conn_conv_base"].sum() if "conn_conv_base" in sub.columns else 0
            conn_rate = conn_bal / ov if ov > 0 else 0.0
            
            contrib = rate * mix 
            
            batch_rows.append({
                "segment": date,
                "curr_vol_pct": mix,
                "curr_rate": rate,
                "curr_conn_rate": conn_rate, # [v3.8]
                "contribution": contrib
            })
        
        batch_rows.sort(key=lambda x: x["contribution"], reverse=True)
        attribution["dimensions"]["Due Batch (Risk Contrib)"] = batch_rows

    return attribution

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


def compute_collection_performance(df):
    """
    [v3.7 New] Analyze Collection Organization Performance.
    [v3.8 Enhanced] MoM Benchmark (Current vs M-1 Overall).
    Hierarchy: Agent Bucket -> Group Name -> Owner ID.
    Metrics: Repay Rate, Contribution.
    """
    if df is None or df.empty:
        return {}
        
    out = {}
    df = df.copy()
    
    # Ensure natural_month exists or create from dt
    if "natural_month" not in df.columns:
        # Try to infer? Assuming df is already filtered or has natural_month
        return {} # Can't do MoM without month column
    
    # 1. Identify Months
    months = sorted(df["natural_month"].unique().tolist())
    if not months: return {}
    
    curr_month = months[-1]
    prev_month = months[-2] if len(months) > 1 else None
    
    out["meta"] = {"current": curr_month, "prev": prev_month}
    
    # Filter Data
    df_curr = df[df["natural_month"] == curr_month]
    df_prev = df[df["natural_month"] == prev_month] if prev_month else pd.DataFrame()
    
    # 2. Bucket Level Summary (Current)
    if "agent_bucket" in df_curr.columns:
        g_bucket = df_curr.groupby("agent_bucket").agg({
            "repay_principal": "sum",
            "start_owing_principal": "sum"
        }).reset_index()
        g_bucket["repay_rate"] = g_bucket["repay_principal"] / g_bucket["start_owing_principal"]
        out["buckets"] = g_bucket.to_dict("records")
        
        # Calculate Benchmarks (Prev Month Overall per Bucket)
        benchmarks = {}
        if not df_prev.empty and "agent_bucket" in df_prev.columns:
            g_prev_b = df_prev.groupby("agent_bucket").agg({
                "repay_principal": "sum",
                "start_owing_principal": "sum"
            })
            g_prev_b["rate"] = g_prev_b["repay_principal"] / g_prev_b["start_owing_principal"]
            benchmarks = g_prev_b["rate"].to_dict() # {bucket: rate}
            
        out["benchmarks"] = benchmarks
        
        # 3. For each Bucket, Rank Groups (MoM Delta Focus)
        out["groups"] = {}
        out["agents"] = {}
        
        for bucket in g_bucket["agent_bucket"].unique():
            sub = df_curr[df_curr["agent_bucket"] == bucket]
            bm_rate = benchmarks.get(bucket, 0.0)
            
            # Rank Groups
            if "group_name" in sub.columns:
                g_grp = sub.groupby("group_name").agg({
                    "repay_principal": "sum",
                    "start_owing_principal": "sum"
                }).reset_index()
                
                g_grp["repay_rate"] = g_grp["repay_principal"] / g_grp["start_owing_principal"]
                
                # [v3.8] Calculate Delta vs M-1 Benchmark
                g_grp["delta_vs_benchmark"] = g_grp["repay_rate"] - bm_rate
                
                # Sort by Delta (Performance vs Market)
                g_grp = g_grp.sort_values("delta_vs_benchmark", ascending=False)
                
                # If few groups (<6), show all
                all_records = g_grp.to_dict("records")
                
                out["groups"][bucket] = {
                    "all": all_records, # Frontend decides to show all or top/bottom
                    "benchmark": bm_rate
                }
                
            # Rank Agents (Global in Bucket) - Keep simple rate sort for agents
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
    main()
