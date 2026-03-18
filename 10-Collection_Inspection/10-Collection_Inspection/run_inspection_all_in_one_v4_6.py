# -*- coding: utf-8 -*-
"""
全链路巡检脚本 (All-in-One Inspection Script) v4.6
Feature:
- v4.6: Sidebar Layout, Reverted Waterfall, Standardized 'overdue_rate'.
- Based on v4.4 features.
"""

import sys
import os
import argparse
from datetime import datetime
from pathlib import Path
import pandas as pd

# -----------------------------------------------------------------------------
# 1. 内嵌 SQL 生成器 (SQL Generators)
# -----------------------------------------------------------------------------

def generate_vintage_sql():
    dims = [
        "due_date", "mob", "user_type", "model_bin", 
        "period_no", "period_seq", "flag_principal"
    ]
    dim_str = "     , ".join(dims)
    
    dpd_columns = []
    for d in range(1, 32):
        col_src = "overdue_principal" if d == 1 else f"d{d}_principal"
        col_alias = f"d{d}_principal"
        dpd_columns.append(f"SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= {d} THEN {col_src} END) AS {col_alias}")
    dpd_sql_part = "\n     , ".join(dpd_columns)

    return f"""
-- 09 表聚合版
SELECT {dim_str}
     , SUM(owing_principal)     AS owing_principal
     , SUM(overdue_principal)   AS overdue_principal
     , COUNT(1)                 AS loan_cnt
     , {dpd_sql_part}
     , SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= 6 THEN owing_principal END) AS owing_principal_d6
     , SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= 16 THEN owing_principal END) AS owing_principal_d16
     , SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= 31 THEN owing_principal END) AS owing_principal_d31
     , SUM(CASE WHEN is_touch=2 AND d2_payoff_flag=0 THEN overdue_principal - d16_principal END) AS conn_conv_repay
     , SUM(CASE WHEN is_touch=2 AND d2_payoff_flag=0 THEN overdue_principal END) AS conn_conv_base
     , SUM(CASE WHEN action_code LIKE '%PTP%' AND d2_payoff_flag=0 THEN overdue_principal - d16_principal END) AS ptp_conv_repay
     , SUM(CASE WHEN action_code LIKE '%PTP%' AND d2_payoff_flag=0 THEN overdue_principal END) AS ptp_conv_base
FROM tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE flag_dq = 1
  AND due_date >= '2025-12-01'
GROUP BY {dim_str}
;
"""

SQL_VINTAGE = generate_vintage_sql()

SQL_REPAY = """
SELECT TO_CHAR(dt_biz, 'yyyyMM') AS natural_month
     , case_bucket
     , agent_bucket
     , group_name
     , owner_id
     , SUM(repay_principal)         AS repay_principal
     , SUM(start_owing_principal)   AS start_owing_principal
FROM phl_anls.tmp_maoruochen_phl_repay_natural_day_daily
WHERE 1 = 1
  AND case_bucket IN ('S0','S1','S2','M1','M2')
  AND TO_CHAR(dt_biz, 'yyyyMM') >= '202512'
GROUP BY TO_CHAR(dt_biz, 'yyyyMM'), case_bucket, agent_bucket, group_name, owner_id
;
"""

SQL_PROCESS = """
SELECT TO_CHAR(TO_DATE(dt), 'yyyymm') AS natural_month
     , owner_bucket
     , owner_group
     , SUM(call_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS call_times_avg
     , SUM(owing_case_cnt) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour > 0 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS caseload
     , CASE WHEN SUM(owing_case_cnt) > 0 THEN 1 - SUM(own_uncomm_case_cnt) / SUM(owing_case_cnt) END AS cover_rate
     , SUM(comm_connect_own_case_cnt) / (SUM(owing_case_cnt) - SUM(own_uncomm_case_cnt)) AS case_connect_rate
     , SUM(call_connect_times) / SUM(call_times) AS call_connect_rate
     , SUM(call_times) AS raw_call_times
     , SUM(call_connect_times) AS raw_call_connect_times
     , SUM(owing_case_cnt) AS raw_owing_case_cnt
     , SUM(own_uncomm_case_cnt) AS raw_uncomm_case_cnt
FROM phl_anls.tmp_liujun_ana_11_agent_process_daily
WHERE CAST(call_8h_flag AS STRING) = '1'
  AND dt >= '2025-12-01'
  AND owner_bucket IN ('M1','M2','M2+','S0','S1','S2')
  AND is_outs_owner = 0
GROUP BY TO_CHAR(TO_DATE(dt), 'yyyymm'), owner_bucket, owner_group
;
"""

# -----------------------------------------------------------------------------
# 2. 功能函数 (Functions)
# -----------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REPORTS_DIR = SCRIPT_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

ODPS_ACCESS_ID = os.environ.get("ODPS_ACCESS_ID", "")
ODPS_ACCESS_KEY = os.environ.get("ODPS_ACCESS_KEY", "")
ODPS_PROJECT = os.environ.get("ODPS_PROJECT", "phl_anls")
ODPS_ENDPOINT = os.environ.get("ODPS_ENDPOINT", "https://service.ap-southeast-1-vpc.maxcompute.aliyun-inc.com/api")

def get_odps_entry():
    if 'o' in globals(): return globals()['o']
    try:
        from odps import ODPS, options
        options.sql.settings = {"odps.sql.submit.mode": "script", "odps.sql.type.system.odps2": "true"}
        o = ODPS(ODPS_ACCESS_ID, ODPS_ACCESS_KEY, ODPS_PROJECT, endpoint=ODPS_ENDPOINT)
        return o
    except ImportError: print("错误: 缺少 pyodps 包。")
    except Exception as e: print(f"错误: 无法创建 ODPS 对象 ({e})")
    return None

def download_data(output_file="collection_inspection_data_local.xlsx"):
    o = get_odps_entry()
    if not o: return
    tasks = [("vintage_risk", SQL_VINTAGE), ("natural_month_repay", SQL_REPAY), ("process_data", SQL_PROCESS)]
    print(f"开始执行取数，将保存至 {output_file} ...")
    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            for sheet_name, sql in tasks:
                print(f"正在执行 {sheet_name} ...")
                inst = o.execute_sql(sql)
                with inst.open_reader() as reader:
                    df = reader.to_pandas()
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                print(f"  {sheet_name} 完成，行数: {len(df)}")
        print(f"所有数据已保存至 {output_file}")
    except Exception as e:
        print(f"取数流程异常: {e}")

def generate_report(excel_path):
    print(f"正在读取数据: {excel_path} ...")
    
    # Import v4.6 modules
    try:
        from run_daily_report_v4_6 import (
            compute_vintage_summary, compute_repay_summary, compute_process_summary,
            compute_trend_by_period, compute_aggregated_vintage, compute_lift_analysis,
            compute_amount_pivot, compute_risk_attribution, compute_collection_performance,
            compute_contact_stats, compute_term_monitoring_matrix
        )
        from run_cashloan_report_v4_6 import build_cashloan_html, read_sheet_maybe_chunked, read_sheet
    except ImportError as e:
        print(f"错误: 缺少 v4.6 依赖脚本 ({e})。")
        return

    # 1. Read Data
    df_v = read_sheet_maybe_chunked(excel_path, "vintage_risk")
    if df_v is None: df_v = read_sheet(excel_path, "yya_vintage")
    
    df_repay = read_sheet(excel_path, "natural_month_repay")
    repay_name = "natural_month_repay"
    if df_repay is None:
        df_repay = read_sheet(excel_path, "repay_cl") or read_sheet(excel_path, "repay_tt")
        repay_name = "repay_cl" if df_repay is not None else "repay_tt"

    df_process = read_sheet(excel_path, "process_data")
    
    # 2. Compute Metrics
    print("正在计算指标 (v4.6)...")
    
    trend_d = compute_trend_by_period(df_v, period='D', limit=21)
    trend_w = compute_trend_by_period(df_v, period='W', limit=12)
    trend_m = compute_trend_by_period(df_v, period='M', limit=6)

    # New/Old Split
    trend_d_new, trend_w_new, trend_m_new = [], [], []
    trend_d_old, trend_w_old, trend_m_old = [], [], []
    df_new = pd.DataFrame()
    df_old = pd.DataFrame()
    
    if df_v is not None and "user_type" in df_v.columns:
        try:
            # Simple heuristic: Group with highest rate is usually New
            risk_map = {}
            for ut in df_v["user_type"].unique():
                sub = df_v[df_v["user_type"] == ut]
                owing = sub["owing_principal"].sum()
                overdue = sub["overdue_principal"].sum()
                risk_map[ut] = overdue / owing if owing > 0 else 0
            
            new_type = max(risk_map, key=risk_map.get) if risk_map else "新客"
            print(f"  识别新客: {new_type}")
            df_new = df_v[df_v["user_type"] == new_type]
            df_old = df_v[df_v["user_type"] != new_type]
        except:
            df_new = df_v[df_v["user_type"] == "新客"]
            df_old = df_v[df_v["user_type"] != "新客"]
            
        trend_d_new = compute_trend_by_period(df_new, 'D')
        trend_w_new = compute_trend_by_period(df_new, 'W')
        trend_m_new = compute_trend_by_period(df_new, 'M')
        trend_d_old = compute_trend_by_period(df_old, 'D')
        trend_w_old = compute_trend_by_period(df_old, 'W')
        trend_m_old = compute_trend_by_period(df_old, 'M')

    # Breakdowns
    bd_weekly_all, _ = compute_vintage_summary(df_v, 'weekly')
    bd_weekly_new, _ = compute_vintage_summary(df_new, 'weekly')
    bd_weekly_old, _ = compute_vintage_summary(df_old, 'weekly')
    
    bd_monthly_all, _ = compute_vintage_summary(df_v, 'monthly')
    bd_monthly_new, _ = compute_vintage_summary(df_new, 'monthly')
    bd_monthly_old, _ = compute_vintage_summary(df_old, 'monthly')
    
    bd_daily_all, _ = compute_vintage_summary(df_v, 'daily')
    bd_daily_new, _ = compute_vintage_summary(df_new, 'daily')
    bd_daily_old, _ = compute_vintage_summary(df_old, 'daily')
    
    vintage_summary = bd_weekly_all
    
    # Lift
    lift_metrics = compute_lift_analysis(df_v)
    lift_metrics_new = compute_lift_analysis(df_new)
    lift_metrics_old = compute_lift_analysis(df_old)
    
    # Matrix
    matrix_daily = compute_aggregated_vintage(df_v, 'D', 21)
    matrix_weekly = compute_aggregated_vintage(df_v, 'W', 12)
    matrix_monthly = compute_aggregated_vintage(df_v, 'M', 6)
    
    md_new = compute_aggregated_vintage(df_new, 'D', 21)
    mw_new = compute_aggregated_vintage(df_new, 'W', 12)
    mm_new = compute_aggregated_vintage(df_new, 'M', 6)
    
    md_old = compute_aggregated_vintage(df_old, 'D', 21)
    mw_old = compute_aggregated_vintage(df_old, 'W', 12)
    mm_old = compute_aggregated_vintage(df_old, 'M', 6)
    
    repay_summary, repay_anomalies = compute_repay_summary([df_repay], [repay_name])
    process_summary = compute_process_summary(df_process)
    
    overview = {"vintage_rows": len(df_v), "repay_rows": len(df_repay)}
    
    # Deep Dive modules
    amount_pivot_data = compute_amount_pivot(df_v)
    
    # Attribution (Table mode)
    attribution_data = {}
    if df_v is not None:
        def get_slices(d):
            dates = pd.to_datetime(d["due_date"])
            curr_s = dates.max().replace(day=1)
            prev_s = (curr_s - pd.Timedelta(days=1)).replace(day=1)
            # Simple full month logic for attribution tables
            dc = d[dates >= curr_s]
            dp = d[(dates >= prev_s) & (dates < curr_s)]
            return dc, dp
            
        dc, dp = get_slices(df_v)
        attribution_data["overall"] = compute_risk_attribution(dc, dp)
        
    term_data = compute_term_monitoring_matrix(df_v)
    perf_data = compute_collection_performance(df_repay, df_process)
    contact_data = {"trend": {}, "mtd": {}} # Simplified placeholders if needed or full compute
    # Re-enable full contact compute
    if df_v is not None:
        c_all = compute_contact_stats(df_v)
        contact_data["trend"]["all"] = c_all.get("trend", [])
        contact_data["mtd"]["all"] = c_all.get("mtd", {})

    # 3. Build HTML
    date_str = datetime.now().strftime("%Y-%m-%d")
    html = build_cashloan_html(
        vintage_summary, repay_summary, process_summary, [], repay_anomalies,
        excel_path, date_str, overview=overview,
        trend_d=trend_d, trend_w=trend_w, trend_m=trend_m,
        trend_d_new=trend_d_new, trend_w_new=trend_w_new, trend_m_new=trend_m_new,
        trend_d_old=trend_d_old, trend_w_old=trend_w_old, trend_m_old=trend_m_old,
        matrix_daily=matrix_daily, matrix_weekly=matrix_weekly, matrix_monthly=matrix_monthly,
        lift_metrics=lift_metrics, lift_metrics_new=lift_metrics_new, lift_metrics_old=lift_metrics_old,
        matrix_daily_new=md_new, matrix_daily_old=md_old,
        matrix_weekly_new=mw_new, matrix_weekly_old=mw_old,
        matrix_monthly_new=mm_new, matrix_monthly_old=mm_old,
        bd_daily_all=bd_daily_all, bd_daily_new=bd_daily_new, bd_daily_old=bd_daily_old,
        bd_weekly_all=bd_weekly_all, bd_weekly_new=bd_weekly_new, bd_weekly_old=bd_weekly_old,
        bd_monthly_all=bd_monthly_all, bd_monthly_new=bd_monthly_new, bd_monthly_old=bd_monthly_old,
        amount_pivot_data=amount_pivot_data,
        attribution_data=attribution_data,
        perf_data=perf_data,
        contact_data=contact_data,
        term_data=term_data
    )
    
    out_path = REPORTS_DIR / f"CashLoan_Inspection_Report_{date_str}_v4_6.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"报告已生成: {out_path.absolute()}")

def find_excel_path(default_name):
    candidates = [
        Path(default_name),
        Path("data") / default_name,
        Path("10-Collection_Inspection/data") / default_name,
        Path(__file__).parent / "data" / default_name,
        Path(__file__).parent / default_name
    ]
    for p in candidates:
        if p.exists(): return str(p)
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="report")
    parser.add_argument("--excel", default="collection_inspection_data_local.xlsx")
    args, _ = parser.parse_known_args()
    
    if args.mode in ["download", "all"]:
        download_data(args.excel)
        
    if args.mode in ["report", "all"]:
        path = find_excel_path(os.path.basename(args.excel))
        if path: generate_report(path)
        else: print(f"未找到数据文件: {args.excel}")

if __name__ == "__main__":
    main()
