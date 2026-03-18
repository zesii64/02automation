# -*- coding: utf-8 -*-
"""
全链路巡检脚本 (All-in-One Inspection Script)

功能：
1. 取数 (Download): 在 943 上执行内嵌 SQL，产出 collection_inspection_data_local.xlsx
2. 报表 (Report): 读取 Excel，计算指标，生成 HTML 日报

使用方式：
    python run_inspection_all_in_one_v2_2.py --mode download  (在 943 上跑)
    python run_inspection_all_in_one_v2_2.py --mode report    (在本地跑)
    python run_inspection_all_in_one_v2_2.py --mode all       (如果本地能连库)

维护者: Mr. Yuan
Last Updated: 2026-02-04 (v2.2)
Changes: Dynamic SQL, Global Maturity Check, Trend Tabs (New/Old)
"""

import sys
import os
import argparse
from datetime import datetime
from pathlib import Path
import pandas as pd

# -----------------------------------------------------------------------------
# 1. 内嵌 SQL (Embedded SQLs)
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# 1. 内嵌 SQL 生成器 (SQL Generators)
# -----------------------------------------------------------------------------

def generate_vintage_sql():
    """
    动态生成 Vintage SQL，保持代码灵活易读。
    核心思想：
    1. 维度 (Dims): 决定数据的颗粒度。
    2. 基础指标 (Basic): 应还、逾期。
    3. 动态指标 (Loop): D1-D31 自动生成，不用手写。
    4. 转化指标 (Conversion): 预计算以减小 Excel 体量。
    """
    
    # 1. 维度定义 (Dimensions)
    dims = [
        "due_date", "mob", "user_type", "model_bin", 
        "period_no", "flag_principal"
    ]
    dim_str = "     , ".join(dims)
    
    # 2. DPD 动态列 (D1 - D31)
    # 逻辑：当表现期 (Today - DueDate) >= N 天时，取 dN_principal，否则为空
    dpd_columns = []
    for d in range(1, 32):
        # [Fix]: 源表无 d1_principal，用户指定用 overdue_principal 替代
        col_src = "overdue_principal" if d == 1 else f"d{d}_principal"
        col_alias = f"d{d}_principal"
        dpd_columns.append(f"SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= {d} THEN {col_src} END) AS {col_alias}")
    dpd_sql_part = "\n     , ".join(dpd_columns)

    # 3. 完整 SQL 拼装
    return f"""
-- 09 表聚合版 (v2.3 分母同口径)：全链路风险口径
SELECT {dim_str}
     -- 基础资产 (Basic Asset)
     , SUM(owing_principal)     AS owing_principal
     , SUM(overdue_principal)   AS overdue_principal
     
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

# 缺省配置 (从 download_agg_only.py 迁移，确保能独立运行)
ODPS_ACCESS_ID = os.environ.get("ODPS_ACCESS_ID", "")
ODPS_ACCESS_KEY = os.environ.get("ODPS_ACCESS_KEY", "")
ODPS_PROJECT = os.environ.get("ODPS_PROJECT", "phl_anls")
ODPS_ENDPOINT = os.environ.get("ODPS_ENDPOINT", "https://service.ap-southeast-1-vpc.maxcompute.aliyun-inc.com/api")

def get_odps_entry():
    """尝试获取 ODPS 入口对象：先找全局 o，没有则创建"""
    # 1. Try global 'o' (Notebook 注入)
    if 'o' in globals():
        return globals()['o']
    
    # 2. Try creating new (Script mode)
    try:
        from odps import ODPS, options
        # 设置 SQL 模式
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
    
    # 使用 Pandas ExcelWriter
    try:
        # 确保至少能写出一个文件，避免 IndexError
        data_found = False
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            for sheet_name, sql in tasks:
                print(f"正在执行 {sheet_name} ...")
                try:
                    # 执行 SQL
                    inst = o.execute_sql(sql)
                    with inst.open_reader() as reader:
                        df = reader.to_pandas()
                    
                    # 大表分 Sheet 写入逻辑
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
                # 如果所有 SQL 都失败，手动创建一个空 Sheet 避免报错
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
    # [Versioning Check]: Force import from v3.0 modules
    try:
        from run_daily_report_v3 import (
            compute_vintage_summary,
            compute_due_trend,
            compute_repay_summary,
            compute_process_summary,
            compute_trend_by_period,
            compute_aggregated_vintage,
            compute_lift_analysis
        )
        from run_cashloan_report_v3 import build_cashloan_html, read_sheet_maybe_chunked, read_sheet
    except ImportError:
        print("错误: 缺少 v3.0 依赖脚本。")
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
    print("正在计算指标 (v3)...")
    vintage_summary, vintage_anomalies = compute_vintage_summary(df_v)
    
    # Trends (Base)
    trend_d = compute_trend_by_period(df_v, period='D', limit=21)
    trend_w = compute_trend_by_period(df_v, period='W', limit=12)
    trend_m = compute_trend_by_period(df_v, period='M', limit=6)

    # Trends (New/Old)
    trend_d_new, trend_w_new, trend_m_new = [], [], []
    trend_d_old, trend_w_old, trend_m_old = [], [], []
    
    if df_v is not None and "user_type" in df_v.columns:
        df_new = df_v[df_v["user_type"] == "新客"]
        df_old = df_v[df_v["user_type"] != "新客"]
        
        trend_d_new = compute_trend_by_period(df_new, period='D', limit=21)
        trend_w_new = compute_trend_by_period(df_new, period='W', limit=12)
        trend_m_new = compute_trend_by_period(df_new, period='M', limit=6)
        
        trend_d_old = compute_trend_by_period(df_old, period='D', limit=21)
        trend_w_old = compute_trend_by_period(df_old, period='W', limit=12)
        trend_m_old = compute_trend_by_period(df_old, period='M', limit=6)

    # [v3 New] Lift Analysis
    lift_metrics = {}
    if df_v is not None:
        lift_metrics = compute_lift_analysis(df_v)

    # [v3 New] Multi-dim Vintage Matrix
    matrix_daily = []
    matrix_weekly = []
    matrix_monthly = []
    
    if df_v is not None:
        matrix_daily = compute_aggregated_vintage(df_v, period='D', limit=21)
        matrix_weekly = compute_aggregated_vintage(df_v, period='W', limit=12)
        matrix_monthly = compute_aggregated_vintage(df_v, period='M', limit=6)
        
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
        # v3 Params
        matrix_daily=matrix_daily, 
        matrix_weekly=matrix_weekly, 
        matrix_monthly=matrix_monthly,
        lift_metrics=lift_metrics
    )
    
    # 4. 写入文件
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    out_path = reports_dir / f"CashLoan_Inspection_Report_{date_str}.html"
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
