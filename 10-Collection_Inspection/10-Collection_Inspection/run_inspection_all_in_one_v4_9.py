# -*- coding: utf-8 -*-
"""
全链路巡检脚本 (All-in-One Inspection Script) v3.6
Feature:
- v3.6: Metric 'Rows' -> 'Loan Cnt' (Use sum of loan_cnt).
- v3.6: Risk Attribution (Structure Shift & Rate Shift) by Amount/Model/Batch.
- v3.6: Signature 'Mr. Yuan' in Footer.
- v3.5: Amount Segment Heatmap (Month x Amount).
- v3.5: Standardized Naming (Loan Cnt, Overdue Rate).
- v3.5: Lower Arrow Threshold (0.1%).
- Split Analysis (Overall/New/Old) for Trends, Lift, Matrix.
- Enhanced MTD Lift (M/M-1/M-2/Y-1) + MoM Lift (v3.3 Ordered).
- Vintage Matrix Split (Recovery & DPD Rate).
- Loan Count in SQL.
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
    """
    动态生成 Vintage SQL，保持代码灵活易读。
    核心思想：
    1. 维度 (Dims): 决定数据的颗粒度。
    2. 基础指标 (Basic): 应还、逾期、[v3.1 New] 借据数 (loan_cnt)。
    3. 动态指标 (Loop): D1-D31 自动生成，不用手写。
    4. 转化指标 (Conversion): 预计算以减小 Excel 体量。
    """
    
    # 1. 维度定义 (Dimensions)
    # [v4.9] 增加 period_seq 支持 1期/3期/6期 产品筛选
    dims = [
        "due_date", "mob", "user_type", "model_bin", 
        "period_no", "period_seq", "flag_principal"
    ]
    dim_str = "     , ".join(dims)
    
    # 2. DPD 动态列 (D1 - D31)
    dpd_columns = []
    for d in range(1, 32):
        col_src = "overdue_principal" if d == 1 else f"d{d}_principal"
        col_alias = f"d{d}_principal"
        dpd_columns.append(f"SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= {d} THEN {col_src} END) AS {col_alias}")
    dpd_sql_part = "\n     , ".join(dpd_columns)

    # 3. 完整 SQL 拼装
    return f"""
-- 09 表聚合版 (v3.1 增加 loan_cnt)：全链路风险口径
SELECT {dim_str}
     -- 基础资产 (Basic Asset)
     , SUM(owing_principal)     AS owing_principal
     , SUM(overdue_principal)   AS overdue_principal
     , COUNT(1)                 AS loan_cnt  -- [v3.1 New] 借据数
     
     -- DPD 动态风险 (Risk Buckets D1-D31)
     , {dpd_sql_part}
     
     -- [关键修正] 分子分母同口径 (Safe Denominators)
     -- DPD5 (D6): 表现期 >= 6 天
     , SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= 6 THEN owing_principal END) AS owing_principal_d6
     -- DPD15 (D16): 表现期 >= 16 天
     , SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= 16 THEN owing_principal END) AS owing_principal_d16
     -- DPD30 (D31): 表现期 >= 31 天
     , SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= 31 THEN owing_principal END) AS owing_principal_d31
     
     -- 转化率相关 (Conversion Metrics) - 预计算以控制行数
     -- 接通转化 (Connect Conversion): is_touch=2
     , SUM(CASE WHEN is_touch=2 AND d2_payoff_flag=0 THEN overdue_principal - d16_principal END) AS conn_conv_repay
     , SUM(CASE WHEN is_touch=2 AND d2_payoff_flag=0 THEN overdue_principal END) AS conn_conv_base
     
     -- PTP 转化 (PTP Conversion): action_code like %PTP%
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
-- 自然月回收聚合到催员维度
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
GROUP BY TO_CHAR(dt_biz, 'yyyyMM')
       , case_bucket
       , agent_bucket
       , group_name
       , owner_id
;
"""

SQL_PROCESS = """
-- 过程表聚合版：按 月 + owner_bucket + owner_group 聚合
SELECT TO_CHAR(TO_DATE(dt), 'yyyymm') AS natural_month
     , owner_bucket
     , owner_group
     , SUM(call_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS call_times_avg
     , SUM(art_call_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS art_call_times_avg
     , SUM(batch_call_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS batch_call_times_avg
     , SUM(call_user_mobile_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS call_user_mobile_times_avg
     , SUM(call_contact_mobile_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS call_contact_mobile_times_avg
     , SUM(art_call_connect_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS art_call_connect_times_avg
     , SUM(call_billsec / 60) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * 60 * COUNT(DISTINCT dt)) AS call_billhr_avg
     , 60 * (SUM(call_billsec / 60) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * 60 * COUNT(DISTINCT dt)))
         / (SUM(call_connect_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt))) AS single_call_duration
     , CASE WHEN SUM(owing_case_cnt) > 0 THEN SUM(comm_times) / (SUM(owing_case_cnt) - SUM(own_uncomm_case_cnt)) END AS cover_times
     , CASE WHEN SUM(owing_case_cnt) > 0 THEN 1 - SUM(own_uncomm_case_cnt) / SUM(owing_case_cnt) END AS cover_rate
     , SUM(owing_case_cnt) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour > 0 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS caseload
     , SUM(call_mobile_cnt) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour > 0 THEN owner_name END), 1) * COUNT(DISTINCT dt)
         * GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
         / GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour > 0 THEN owner_name END), 1)) AS penetration_rate
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

# 缺省配置
ODPS_ACCESS_ID = os.environ.get("ODPS_ACCESS_ID", "")
ODPS_ACCESS_KEY = os.environ.get("ODPS_ACCESS_KEY", "")
ODPS_PROJECT = os.environ.get("ODPS_PROJECT", "phl_anls")
ODPS_ENDPOINT = os.environ.get("ODPS_ENDPOINT", "https://service.ap-southeast-1-vpc.maxcompute.aliyun-inc.com/api")

def get_odps_entry():
    """尝试获取 ODPS 入口对象：先找全局 o，没有则创建"""
    if 'o' in globals():
        return globals()['o']
    try:
        from odps import ODPS, options
        options.sql.settings = {"odps.sql.submit.mode": "script", "odps.sql.type.system.odps2": "true"}
        o = ODPS(ODPS_ACCESS_ID, ODPS_ACCESS_KEY, ODPS_PROJECT, endpoint=ODPS_ENDPOINT)
        return o
    except ImportError:
        print("错误: 缺少 pyodps 包。")
    except Exception as e:
        print(f"错误: 无法创建 ODPS 对象 ({e})")
    return None

def download_data(output_file="collection_inspection_data_local.xlsx"):
    """在 ODPS 环境执行 SQL 并保存为 Excel"""
    o = get_odps_entry()
    if not o:
        print("错误: 无法获取 ODPS 入口对象 (o)，无法执行取数。")
        return

    tasks = [
        ("vintage_risk", SQL_VINTAGE),
        ("natural_month_repay", SQL_REPAY),
        ("process_data", SQL_PROCESS)
    ]
    
    print(f"开始执行取数，将保存至 {output_file} ...")
    
    try:
        data_found = False
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            for sheet_name, sql in tasks:
                print(f"正在执行 {sheet_name} ...")
                try:
                    inst = o.execute_sql(sql)
                    with inst.open_reader() as reader:
                        df = reader.to_pandas()
                    
                    MAX_ROWS = 1000000
                    if len(df) > MAX_ROWS:
                        parts = (len(df) // MAX_ROWS) + 1
                        print(f"  数据量 {len(df)} 行，将拆分为 {parts} 个 Sheet...")
                        for i in range(parts):
                            start = i * MAX_ROWS
                            end = (i + 1) * MAX_ROWS
                            sub_df = df.iloc[start:end]
                            s_name = f"{sheet_name}_{i+1}" if i > 0 else sheet_name
                            sub_df.to_excel(writer, sheet_name=s_name, index=False)
                    else:
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    print(f"  {sheet_name} 完成，行数: {len(df)}")
                    data_found = True
                    
                except Exception as e:
                    print(f"  {sheet_name} 执行失败: {e}")
            
            if not data_found:
                pd.DataFrame({"Info": ["No data fetched"]}).to_excel(writer, sheet_name="Error_Log", index=False)
                
        print(f"所有数据已保存至 {output_file}")
        
    except Exception as e:
        print(f"取数流程异常: {e}")
        import traceback
        traceback.print_exc()


def generate_report(excel_path):
    """读取 Excel 并生成 HTML 报表"""
    print(f"正在读取数据: {excel_path} ...")
    
    # 尝试导入 run_daily_report 中的计算逻辑
    # [Versioning Check]: Force import from v4.1 modules
    try:
        from run_daily_report_v4_9 import (
            compute_vintage_summary,
            compute_due_trend,
            compute_repay_summary,
            compute_process_summary,
            compute_trend_by_period,
            compute_aggregated_vintage,
            compute_lift_analysis,
            compute_amount_pivot,
            compute_risk_attribution,
            compute_collection_performance,
            compute_contact_stats,
            compute_term_monitoring_matrix  # [v4.9 New]
        )
        from run_cashloan_report_v4_9 import build_cashloan_html, read_sheet_maybe_chunked, read_sheet
    except ImportError as e:
        print(f"错误: 缺少 v4.2 依赖脚本 ({e})。")
        return

    # 1. 读取数据 (从 v2.2 恢复)
    df_v = read_sheet_maybe_chunked(excel_path, "vintage_risk")
    if df_v is None: df_v = read_sheet(excel_path, "yya_vintage")
    
    df_repay = read_sheet(excel_path, "natural_month_repay")
    repay_name = "natural_month_repay"
    if df_repay is None:
        df_repay = read_sheet(excel_path, "repay_cl") or read_sheet(excel_path, "repay_tt")
        repay_name = "repay_cl" if df_repay is not None else "repay_tt"

    df_process = read_sheet(excel_path, "process_data")
    
    # 2. 计算指标
    print("正在计算指标 (v4.2)...")
    
    # Trends (Base)
    trend_d = compute_trend_by_period(df_v, period='D', limit=21)
    trend_w = compute_trend_by_period(df_v, period='W', limit=12)
    trend_m = compute_trend_by_period(df_v, period='M', limit=6)

    # Trends (New/Old)
    trend_d_new, trend_w_new, trend_m_new = [], [], []
    trend_d_old, trend_w_old, trend_m_old = [], [], []
    
    df_new = pd.DataFrame()
    df_old = pd.DataFrame()
    
    if df_v is not None and "user_type" in df_v.columns:
        # [v3.3 Fix] 动态识别新客 (Dynamic New Customer Detection)
        # 解决编码乱码问题：不再硬匹配 "新客"，而是假设风险最高(Entrant Rate)的组为新客
        try:
            risk_map = {}
            unique_types = df_v["user_type"].unique()
            for ut in unique_types:
                sub = df_v[df_v["user_type"] == ut]
                owing = sub["owing_principal"].sum()
                overdue = sub["overdue_principal"].sum()
                rate = overdue / owing if owing > 0 else 0
                risk_map[ut] = rate
            
            if risk_map:
                # 找到风险最高的类型 -> 认定为 "新客"
                new_type_detected = max(risk_map, key=risk_map.get)
                print(f"自动识别新客标识 (High Risk Group): '{new_type_detected}' (Rate: {risk_map[new_type_detected]:.2%})")
                
                df_new = df_v[df_v["user_type"] == new_type_detected]
                df_old = df_v[df_v["user_type"] != new_type_detected] # 其余均为老客
            else:
                df_new = df_v[df_v["user_type"] == "新客"]
                df_old = df_v[df_v["user_type"] != "新客"]
        except Exception as e:
            print(f"动态识别失败 ({e})，回退到默认逻辑")
            df_new = df_v[df_v["user_type"] == "新客"]
            df_old = df_v[df_v["user_type"] != "新客"]
        
        trend_d_new = compute_trend_by_period(df_new, period='D', limit=21)
        trend_w_new = compute_trend_by_period(df_new, period='W', limit=12)
        trend_m_new = compute_trend_by_period(df_new, period='M', limit=6)
        
        trend_d_old = compute_trend_by_period(df_old, period='D', limit=21)
        trend_w_old = compute_trend_by_period(df_old, period='W', limit=12)
        trend_m_old = compute_trend_by_period(df_old, period='M', limit=6)

    # [v3.4 New] Multi-Period Breakdown Summaries
    print("  计算维度拆解 (Weekly/Monthly/Daily)...")
    
    # 1. Weekly (Default)
    bd_weekly_all, _ = compute_vintage_summary(df_v, mode='weekly')
    bd_weekly_new, _ = compute_vintage_summary(df_new, mode='weekly') if not df_new.empty else ({}, [])
    bd_weekly_old, _ = compute_vintage_summary(df_old, mode='weekly') if not df_old.empty else ({}, [])
    
    # 2. Monthly
    bd_monthly_all, _ = compute_vintage_summary(df_v, mode='monthly')
    bd_monthly_new, _ = compute_vintage_summary(df_new, mode='monthly') if not df_new.empty else ({}, [])
    bd_monthly_old, _ = compute_vintage_summary(df_old, mode='monthly') if not df_old.empty else ({}, [])
    
    # 3. Daily (Amount focus)
    bd_daily_all, _ = compute_vintage_summary(df_v, mode='daily')
    bd_daily_new, _ = compute_vintage_summary(df_new, mode='daily') if not df_new.empty else ({}, [])
    bd_daily_old, _ = compute_vintage_summary(df_old, mode='daily') if not df_old.empty else ({}, [])
    
    # Legacy variable for compatibility (uses weekly)
    vintage_summary = bd_weekly_all
    vintage_anomalies = []

    # [v3.2 New] Lift Analysis (Split) - Pass Filtered DF directly!
    lift_metrics = {}
    lift_metrics_new = {}
    lift_metrics_old = {}
    
    if df_v is not None:
        lift_metrics = compute_lift_analysis(df_v)
        if not df_new.empty:
            lift_metrics_new = compute_lift_analysis(df_new) # Pass DF directly
        if not df_old.empty:
            lift_metrics_old = compute_lift_analysis(df_old) # Pass DF directly

    # [v3.2 New] Multi-dim Vintage Matrix (Split)
    matrix_daily = []
    matrix_weekly = []
    matrix_monthly = []
    
    # Split Matrices
    md_new, mw_new, mm_new = [], [], []
    md_old, mw_old, mm_old = [], [], []
    
    if df_v is not None:
        # Overall
        matrix_daily = compute_aggregated_vintage(df_v, period='D', limit=21)
        matrix_weekly = compute_aggregated_vintage(df_v, period='W', limit=12)
        matrix_monthly = compute_aggregated_vintage(df_v, period='M', limit=6)
        
        # New
        if not df_new.empty:
            md_new = compute_aggregated_vintage(df_new, period='D', limit=21)
            mw_new = compute_aggregated_vintage(df_new, period='W', limit=12)
            mm_new = compute_aggregated_vintage(df_new, period='M', limit=6)
            
        # Old
        if not df_old.empty:
            md_old = compute_aggregated_vintage(df_old, period='D', limit=21)
            mw_old = compute_aggregated_vintage(df_old, period='W', limit=12)
            mm_old = compute_aggregated_vintage(df_old, period='M', limit=6)
        
    repay_summary, repay_anomalies = compute_repay_summary(
        [df_repay] if df_repay is not None else [None],
        [repay_name] if df_repay is not None else ["natural_month_repay"]
    )
    
    process_summary = compute_process_summary(df_process)
    
    overview = {
        "vintage_rows": len(df_v) if df_v is not None else 0,
        "repay_rows": len(df_repay) if df_repay is not None else 0,
        "process_rows": len(df_process) if df_process is not None else 0,
    }
    
    # [v3.5 New] Amount Pivot (Heatmap)
    print("  计算金额段热力图 (Amount Pivot)...")
    amount_pivot_data = {}
    if df_v is not None:
        amount_pivot_data = compute_amount_pivot(df_v)

    # [v3.6 New] Risk Attribution (MoM) - [v3.7 Enhanced] Segmented (All/New/Old)
    print("  计算归因分析 (Risk Attribution - Segmented)...")
    attribution_data = {}
    
    if df_v is not None and "due_date" in df_v.columns:
        # Helper to get Curr/Prev MTD slices
        def get_mtd_slices(df_target):
            if df_target is None or df_target.empty: return None, None
            
            dates_t = pd.to_datetime(df_target["due_date"])
            max_d = dates_t.max()
            if pd.isna(max_d): return None, None
            
            # Use GLOBAL max date to determine progress, or local max?
            # Usually better to align with Global Calendar.
            # But let's use the passed df's max for safety if filtered.
            # Actually, consistent MTD requires aligning to "Today" or Global Max.
            # Let's use Global Max from df_v (already computed above) or recompute here.
            
            # Re-derive global context
            g_dates = pd.to_datetime(df_v["due_date"])
            g_max = g_dates.max()
            g_start = g_max.replace(day=1)
            g_prog = (g_max - g_start).days + 1
            
            # Slices
            curr_s = g_start
            curr_e = g_max
            
            prev_e_month = g_start - pd.Timedelta(days=1)
            prev_s = prev_e_month.replace(day=1)
            prev_e = prev_s + pd.Timedelta(days=g_prog - 1)
            
            # Filter
            d_curr = df_target[(dates_t >= curr_s) & (dates_t <= curr_e)]
            d_prev = df_target[(dates_t >= prev_s) & (dates_t <= prev_e)]
            
            return d_curr, d_prev

        # 1. Overall
        dc, dp = get_mtd_slices(df_v)
        attribution_data["overall"] = compute_risk_attribution(dc, dp)
        
        # 2. New
        if not df_new.empty:
            dc_n, dp_n = get_mtd_slices(df_new)
            attribution_data["new"] = compute_risk_attribution(dc_n, dp_n)
            
        # 3. Old
        if not df_old.empty:
            dc_o, dp_o = get_mtd_slices(df_old)
            attribution_data["old"] = compute_risk_attribution(dc_o, dp_o)

    # [v4.0 New] Contactability Analysis (Segmented)
    print("  计算可联性分析 (Contactability Analysis)...")
    contact_data = { "trend": {}, "mtd": {} }
    
    if df_v is not None:
        c_all = compute_contact_stats(df_v)
        contact_data["trend"]["all"] = c_all.get("trend", [])
        contact_data["mtd"]["all"] = c_all.get("mtd", {})
        
        if not df_new.empty:
            c_new = compute_contact_stats(df_new)
            contact_data["trend"]["new"] = c_new.get("trend", [])
            contact_data["mtd"]["new"] = c_new.get("mtd", {})
            
        if not df_old.empty:
            c_old = compute_contact_stats(df_old)
            contact_data["trend"]["old"] = c_old.get("trend", [])
            contact_data["mtd"]["old"] = c_old.get("mtd", {})

    # [v3.7 New] Collection Org Performance
    print("  计算催收团队效能 (Collection Performance)...")
    # [v3.9] Pass df_process for attribution
    perf_data = compute_collection_performance(df_repay, df_process)

    # [v4.9 New] Term Monitoring Matrix
    print("  计算期限监控矩阵 (Term Monitoring Matrix)...")
    term_data = compute_term_monitoring_matrix(df_v)

    # 3. 生成 HTML
    date_str = datetime.now().strftime("%Y-%m-%d")
    html = build_cashloan_html(
        vintage_summary, repay_summary, process_summary, 
        vintage_anomalies, repay_anomalies, 
        excel_path, date_str, overview=overview, 
        repay_name=repay_name, is_placeholder=False, 
        trend_d=trend_d, trend_w=trend_w, trend_m=trend_m,
        trend_d_new=trend_d_new, trend_w_new=trend_w_new, trend_m_new=trend_m_new,
        trend_d_old=trend_d_old, trend_w_old=trend_w_old, trend_m_old=trend_m_old,
        # v3.1 Params
        matrix_daily=matrix_daily, 
        matrix_weekly=matrix_weekly, 
        matrix_monthly=matrix_monthly,
        lift_metrics=lift_metrics,
        
        lift_metrics_new=lift_metrics_new, lift_metrics_old=lift_metrics_old,
        matrix_daily_new=md_new, matrix_daily_old=md_old,
        matrix_weekly_new=mw_new, matrix_weekly_old=mw_old,
        matrix_monthly_new=mm_new, matrix_monthly_old=mm_old,
        
        # v3.4 Breakdown
        bd_daily_all=bd_daily_all, bd_daily_new=bd_daily_new, bd_daily_old=bd_daily_old,
        bd_weekly_all=bd_weekly_all, bd_weekly_new=bd_weekly_new, bd_weekly_old=bd_weekly_old,
        bd_monthly_all=bd_monthly_all, bd_monthly_new=bd_monthly_new, bd_monthly_old=bd_monthly_old,

        # v3.5 Pivot
        amount_pivot_data=amount_pivot_data,
        
        # v3.6 Attribution
        attribution_data=attribution_data,
        
        # v3.7 Collection Perf
        perf_data=perf_data,
        
        # v4.0 Contactability
        contact_data=contact_data,
        # v4.9 Term Monitoring Matrix
        term_data=term_data
    )
    
    # 4. 写入文件
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(exist_ok=True)
    out_path = reports_dir / f"CashLoan_Inspection_Report_{date_str}_v4_9.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"报告已生成: {out_path.absolute()}")


def find_excel_path(default_name):
    """自动查找 Excel 文件：当前目录 > data/ 目录 > 上级目录"""
    candidates = [
        Path(default_name),
        Path("data") / default_name,
        Path("10-Collection_Inspection/data") / default_name,
        Path(__file__).parent / "data" / default_name,
        Path(__file__).parent / default_name
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None

def main():
    import argparse
    parser = argparse.ArgumentParser(description="全链路巡检脚本 (All-in-One)")
    parser.add_argument("--mode", choices=["download", "report", "all"], default="report", 
                        help="运行模式: download(仅取数), report(仅报表), all(取数+报表)")
    parser.add_argument("--excel", default="collection_inspection_data_local.xlsx", help="Excel 文件路径")
    
    # 兼容 Jupyter/Notebook 环境：使用 parse_known_args 忽略 kernel 参数
    args, unknown = parser.parse_known_args()
    
    # 如果在 Notebook 中且未指定 mode，默认为 download (假设是在 943 上跑)
    if 'ipykernel' in sys.modules and args.mode == 'report' and len(sys.argv) > 1 and '-f' in sys.argv[1]:
         print("检测到 Notebook 环境，默认模式调整为: download")
         args.mode = 'download'

    if args.mode in ["download", "all"]:
        download_data(args.excel)
        
    if args.mode in ["report", "all"]:
        # 智能查找文件
        excel_path = args.excel
        if not os.path.exists(excel_path):
            found = find_excel_path(os.path.basename(excel_path))
            if found:
                print(f"自动定位到数据文件: {found}")
                excel_path = found
            else:
                print(f"未找到数据文件: {args.excel}")
                print("请检查文件是否在当前目录或 data/ 目录下，或先运行 --mode download。")
                return
        
        generate_report(excel_path)

if __name__ == "__main__":
    main()
