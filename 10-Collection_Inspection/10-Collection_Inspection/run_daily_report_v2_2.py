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
    [Global Constraint]: Enforce maturity check. If cohort contains immature data, return None for lag metrics.
    """
    if df_sub.empty:
        return {}
    
    res = {"rows": len(df_sub)}
    
    # --- Global Maturity Constraint ---
    # 默认认为成熟，除非检测到 Due Date 过近
    is_dpd5_mature = True
    is_dpd15_mature = True
    is_dpd30_mature = True
    
    if "due_date" in df_sub.columns:
        try:
            today = pd.Timestamp.now().normalize()
            dates = pd.to_datetime(df_sub["due_date"])
            max_date = dates.max()
            if not pd.isna(max_date):
                lag = (today - max_date).days
                # 如果组内最新的订单都没跑满表现期，则整个组的该指标不可用
                # DPD5: T+6
                if lag < 6: is_dpd5_mature = False
                # DPD15: T+16
                if lag < 16: is_dpd15_mature = False
                # DPD30: T+31
                if lag < 31: is_dpd30_mature = False
        except Exception:
            pass # Fallback to show data if date parse fails

    # 1. Denominators
    owing = df_sub["owing_principal"].sum()
    conn_base = df_sub["conn_conv_base"].sum() if "conn_conv_base" in df_sub.columns else 0
    ptp_base = df_sub["ptp_conv_base"].sum() if "ptp_conv_base" in df_sub.columns else 0
    
    # 2. Basic Risk (Overdue / DPD30)
    if owing > 0:
        res["overdue_rate"] = round(df_sub["overdue_principal"].sum() / owing, 4)
        
        # DPD30 Check
        if is_dpd30_mature:
            if "d31_principal" in df_sub.columns:
                res["dpd30"] = round(df_sub["d31_principal"].sum() / owing, 4)
            elif "owing_principal_d31" in df_sub.columns: # Fallback for old SQL
                 denom_d31 = df_sub["owing_principal_d31"].sum()
                 if denom_d31 > 0:
                     res["dpd30"] = round(df_sub["d31_principal"].sum() / denom_d31, 4)
    
    # 3. New Risk Buckets (DPD5 / DPD15)
    if owing > 0:
        # DPD5
        if is_dpd5_mature and "d6_principal" in df_sub.columns:
            denom = df_sub["owing_principal_d6"].sum() if "owing_principal_d6" in df_sub.columns else owing
            if denom > 0:
                res["dpd5"] = round(df_sub["d6_principal"].sum() / denom, 4)
        # DPD15
        if is_dpd15_mature and "d16_principal" in df_sub.columns:
            denom = df_sub["owing_principal_d16"].sum() if "owing_principal_d16" in df_sub.columns else owing
            if denom > 0:
                res["dpd15"] = round(df_sub["d16_principal"].sum() / denom, 4)
        
    # 4. Conversion Rates
    if conn_base > 0 and "conn_conv_repay" in df_sub.columns:
        res["connect_conversion"] = round(df_sub["conn_conv_repay"].sum() / conn_base, 4)
    if ptp_base > 0 and "ptp_conv_repay" in df_sub.columns:
        res["ptp_conversion"] = round(df_sub["ptp_conv_repay"].sum() / ptp_base, 4)
        
    return res


def _add_wow(curr, prev):
    """Calculate WoW delta for risk metrics."""
    metrics = ["overdue_rate", "dpd5", "dpd30", "connect_conversion", "ptp_conversion"]
    for m in metrics:
        if m in curr and m in prev:
            vc = curr[m]
            vp = prev[m]
            if isinstance(vc, (int, float)) and isinstance(vp, (int, float)) and vp != 0:
                curr[f"{m}_wow"] = (vc - vp) / vp

def compute_vintage_summary(df):
    """Vintage summary: Overall + Breakdowns (Model, User, Period, Amount).
    New logic: Focus on [Last 7 Days] vs [Previous 7 Days].
    """
    if df is None or df.empty:
        return {}, []
    out = {}
    
    # 0. Split Windows (Current 7 days vs Prev 7 days)
    df_curr = df
    df_prev = pd.DataFrame()
    
    if "due_date" in df.columns:
        # Ensure datetime
        dates = pd.to_datetime(df["due_date"])
        max_date = dates.max()
        # Windows
        curr_end = max_date
        curr_start = max_date - pd.Timedelta(days=6)
        prev_end = curr_start - pd.Timedelta(days=1)
        prev_start = prev_end - pd.Timedelta(days=6)
        
        df_curr = df[(dates >= curr_start) & (dates <= curr_end)]
        df_prev = df[(dates >= prev_start) & (dates <= prev_end)]
    
    # 1. Overall
    res_curr = _calc_risk_metrics(df_curr)
    res_prev = _calc_risk_metrics(df_prev)
    _add_wow(res_curr, res_prev)
    # Add meta info
    if not df_prev.empty:
        res_curr["meta_period"] = "Last 7 Days"
    else:
        res_curr["meta_period"] = "All Data"
        
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
    period: 'D' (Day), 'W' (Week), 'M' (Month).
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
        # Start of week (Monday) + Week Number
        # dt.to_period('W') usually starts Monday
        df_wk["period_key"] = df_wk["due_date"].dt.to_period('W').apply(lambda r: r.start_time.strftime('%Y-%m-%d (W%V)'))
    elif period == 'M':
        df_wk["period_key"] = df_wk["due_date"].dt.strftime('%Y-%m')
    else:
        df_wk["period_key"] = df_wk["due_date"].dt.strftime('%Y-%m-%d')

    # Aggregate
    metric_cols = [
        "overdue_principal", "owing_principal", 
        "d6_principal", "d16_principal", "d31_principal",
        "conn_conv_repay", "conn_conv_base",
        "ptp_conv_repay", "ptp_conv_base"
    ]
    cols_to_sum = [c for c in metric_cols if c in df_wk.columns]
    
    gr = df_wk.groupby("period_key")[cols_to_sum + ["period_key", "due_date"]].agg(
        {c: "sum" for c in cols_to_sum} | {"period_key": "count", "due_date": "max"}
    ).rename(columns={"period_key": "rows"})
    
    gr = gr.reset_index()
    
    results = []
    
    for _, row in gr.iterrows():
        item = _calc_risk_metrics(pd.DataFrame([row])) 
        item["period_key"] = row["period_key"]
        item["rows"] = row["rows"]
        results.append(item)
        
    # Sort DESC
    results.sort(key=lambda x: x["period_key"], reverse=True)
    return results[:limit]

def compute_vintage_matrix(df, limit=30):
    """
    Compute Vintage Matrix (Entrant & Recovery).
    Logic:
      - Entrant: overdue / owing
      - Recovery D(N): 1 - d(N) / overdue
      - Maturity Check: Only calc if Today - DueDate >= N
    Returns: List of dicts (one per due_date)
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
    
    gr = df.groupby("due_date")[cols_needed].sum().reset_index()
    gr.sort_values("due_date", ascending=False, inplace=True)
    gr = gr.head(limit)
    
    today = pd.Timestamp.now().normalize()
    results = []
    
    for _, row in gr.iterrows():
        due_dt = row["due_date"]
        days_on_book = (today - due_dt).days
        
        # 1. Entrant
        owing = row["owing_principal"]
        overdue = row["overdue_principal"]
        entrant = overdue / owing if owing > 0 else 0.0
        
        item = {
            "due_date": due_dt.strftime("%Y-%m-%d"),
            "entrant_rate": round(entrant, 4),
            "recovery": {}
        }
        
        # 2. Recovery D1..D30
        # Logic: Report D(k) uses Source d(k+1)
        # E.g. D1 Recovery uses d2_principal (Observed at T+2)
        for k in range(1, 31): # Report shows D1 to D30
            # Maturity: Need T+(k+1) to see D(k) result
            if days_on_book < k + 1:
                item["recovery"][f"D{k}"] = None
            else:
                # Source column is shifted by 1
                col = f"d{k+1}_principal"
                if col in row and overdue > 0:
                    bal = row[col]
                    rec = 1.0 - (bal / overdue)
                    item["recovery"][f"D{k}"] = round(rec, 4)
                else:
                    item["recovery"][f"D{k}"] = None
                    
        results.append(item)
        
    return results

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


if __name__ == "__main__":
    main()