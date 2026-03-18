# -*- coding: utf-8 -*-
"""
贷后数据巡检 - 本地数据下载（943 平台用 Python 脚本）

取数底表以本目录下 3 个 SQL 为准，不做自定义查表：
1. vintage_risk.sql   → Sheet vintage_risk
2. natural_month_repay.sql → Sheet natural_month_repay
3. process_data.sql   → Sheet process_data

在 943 上运行：读取上述 3 个 SQL 文件内容，在 ODPS 中执行，将结果写入单个 Excel；
同时执行数据探查 SQL，将探查结果写入同 Excel 的额外 Sheet，便于带回后 Agent 读取。
产出：一个 Excel，含 3 个取数 Sheet + 若干探查 Sheet。
"""

import sys
from pathlib import Path

# ODPS 配置（943 上可用环境变量或平台默认，此处为占位，请按 943 要求修改）
ODPS_ACCESS_ID = __import__("os").environ.get("ODPS_ACCESS_ID", "")
ODPS_ACCESS_KEY = __import__("os").environ.get("ODPS_ACCESS_KEY", "")
ODPS_PROJECT = __import__("os").environ.get("ODPS_PROJECT", "phl_anls")
ODPS_ENDPOINT = __import__("os").environ.get("ODPS_ENDPOINT", "https://service.ap-southeast-1-vpc.maxcompute.aliyun-inc.com/api")

OUTPUT_EXCEL = "collection_inspection_data_local.xlsx"
# Excel 单表最大行数 = 1048576（含表头），故每片最多 1048575 行数据
MAX_EXCEL_ROWS = 1048575

# 3 个 SQL 文件（与 Sheet 名一一对应）
SQL_FILES = [
    ("vintage_risk.sql", "vintage_risk"),
    ("natural_month_repay.sql", "natural_month_repay"),
    ("process_data.sql", "process_data"),
]
# 聚合版：不下明细，行数少、下载快；产出 Sheet 名与上一致，报表无需改。
SQL_FILES_AGG = [
    ("vintage_risk_agg.sql", "vintage_risk"),
    ("natural_month_repay_agg.sql", "natural_month_repay"),
    ("process_data_agg.sql", "process_data"),
]

# 数据探查 SQL：跑完后写入同 Excel 的额外 Sheet，便于带回后 Agent 看到探查内容
EXPLORE_QUERIES = [
    ("explore_09_dims", """
SELECT DISTINCT predue_bin, collect_bin, user_type, model_bin
FROM tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE flag_dq = 1 AND due_date >= '2025-12-01'
    """),
    ("explore_09_region", """
SELECT DISTINCT province, conntact_carrier
FROM tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE flag_dq = 1 AND due_date >= '2025-12-01'
    """),
    ("explore_09_cnt", """
SELECT
    COUNT(DISTINCT due_date) AS cnt_due_date,
    COUNT(DISTINCT mob) AS cnt_mob,
    COUNT(DISTINCT user_type) AS cnt_user_type,
    COUNT(DISTINCT model_bin) AS cnt_model_bin,
    COUNT(DISTINCT predue_bin) AS cnt_predue_bin,
    COUNT(DISTINCT collect_bin) AS cnt_collect_bin,
    COUNT(DISTINCT province) AS cnt_province,
    COUNT(DISTINCT conntact_carrier) AS cnt_conntact_carrier
FROM tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE flag_dq = 1 AND due_date >= '2025-12-01'
    """),
    ("explore_repay_dims", """
SELECT DISTINCT data_level, case_bucket, agent_bucket, group_name
FROM phl_anls.tmp_maoruochen_phl_repay_natural_day_daily
WHERE TO_CHAR(dt_biz,'yyyyMM') >= '202512'
  AND case_bucket IN ('S0','S1','S2','M1','M2')
    """),
    ("explore_repay_datalvl", """
SELECT data_level, COUNT(*) AS cnt
FROM phl_anls.tmp_maoruochen_phl_repay_natural_day_daily
WHERE TO_CHAR(dt_biz,'yyyyMM') >= '202512'
  AND case_bucket IN ('S0','S1','S2','M1','M2')
GROUP BY data_level
ORDER BY cnt DESC
    """),
    ("explore_process_dims", """
SELECT DISTINCT owner_bucket, owner_group, owing_amount_alloc_bin
FROM phl_anls.tmp_liujun_ana_11_agent_process_daily
WHERE dt >= '2025-12-01'
  AND CAST(call_8h_flag AS string) = '1'
  AND owner_bucket IN ('M1','M2','M2+','S0','S1','S2')
  AND is_outs_owner = 0
    """),
    ("explore_process_cnt", """
SELECT
    COUNT(DISTINCT dt) AS cnt_dt,
    COUNT(DISTINCT owner_bucket) AS cnt_owner_bucket,
    COUNT(DISTINCT owner_group) AS cnt_owner_group,
    COUNT(DISTINCT owing_amount_alloc_bin) AS cnt_owing_amount_alloc_bin
FROM phl_anls.tmp_liujun_ana_11_agent_process_daily
WHERE dt >= '2025-12-01'
  AND CAST(call_8h_flag AS string) = '1'
  AND owner_bucket IN ('M1','M2','M2+','S0','S1','S2')
  AND is_outs_owner = 0
    """),
]


def _script_dir():
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path.cwd()


def get_odps():
    try:
        from odps import ODPS, options
        odps = ODPS(ODPS_ACCESS_ID, ODPS_ACCESS_KEY, ODPS_PROJECT, endpoint=ODPS_ENDPOINT)
        options.sql.settings = {"odps.sql.submit.mode": "script", "odps.sql.type.system.odps2": "true"}
        return odps
    except ImportError:
        print("请先安装: pip install pyodps pandas openpyxl")
        sys.exit(1)


def run_sql_file(odps, sql_path):
    """读取 SQL 文件内容并执行，返回 DataFrame；表名无 project 时按 ODPS 当前 project。"""
    sql = sql_path.read_text(encoding="utf-8", errors="replace").strip()
    sql = sql.rstrip(";").strip()
    if not sql:
        return None
    try:
        return odps.execute_sql(sql).to_pandas()
    except Exception as e:
        print(f"     失败: {e}")
        return None


def run_sql_string(odps, sql):
    """执行 SQL 字符串，返回 DataFrame。"""
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        return None
    try:
        return odps.execute_sql(sql).to_pandas()
    except Exception as e:
        print(f"     失败: {e}")
        return None


def main():
    import argparse

    argv = [a for a in sys.argv[1:] if a != "-f" and "kernel" not in a]
    parser = argparse.ArgumentParser(description="943 平台用：按 3 个 SQL 取数，写入单 Excel 多 Sheet")
    parser.add_argument("--output", "-o", default=OUTPUT_EXCEL, help="输出 Excel 文件名")
    parser.add_argument("--dir", "-d", default=None, help="输出目录（默认脚本同目录）")
    parser.add_argument("--sql-dir", default=None, help="SQL 文件所在目录（默认与脚本同目录）")
    parser.add_argument("--agg", action="store_true", help="使用聚合版 SQL（不下明细，行数少、下载快）")
    args = parser.parse_args(argv)

    base_dir = Path(args.dir) if args.dir else _script_dir()
    sql_dir = Path(args.sql_dir) if args.sql_dir else _script_dir()
    output_path = base_dir / args.output

    sql_list = SQL_FILES_AGG if args.agg else SQL_FILES
    mode_hint = " [聚合模式：09表 due_date+mob+user_type，回收按催员，过程按月+bucket+group]" if args.agg else ""

    print("=" * 60)
    print("贷后数据巡检 - 以 3 个 SQL 为取数底表（943 平台用）" + mode_hint)
    print("=" * 60)
    print(f"SQL 目录: {sql_dir}")
    print(f"输出: {output_path}")
    print()

    import pandas as pd
    odps = get_odps()
    sheets = {}

    for sql_file, sheet_name in sql_list:
        sql_path = sql_dir / sql_file
        if not sql_path.exists():
            print(f"[跳过] 未找到 {sql_file}")
            continue
        print(f"[{len(sheets)+1}/3] 执行 {sql_file} -> Sheet {sheet_name} ...")
        df = run_sql_file(odps, sql_path)
        if df is not None:
            sheets[sheet_name] = df
            print(f"     -> {len(df)} 行")

    if not sheets:
        print("无数据可写，退出")
        sys.exit(1)

    # 数据探查：执行探查 SQL，结果写入同 Excel 的额外 Sheet，便于带回后 Agent 看到
    print()
    print("[数据探查] 执行探查 SQL，写入同 Excel ...")
    for i, (sheet_name, sql) in enumerate(EXPLORE_QUERIES, 1):
        print(f"  探查 {i}/{len(EXPLORE_QUERIES)}: {sheet_name} ...")
        df = run_sql_string(odps, sql)
        if df is not None and not df.empty:
            sheets[sheet_name] = df
            print(f"     -> {len(df)} 行")

    with pd.ExcelWriter(output_path, engine="openpyxl") as w:
        for name, df in sheets.items():
            base_name = name[:31]
            n_rows = len(df)
            if n_rows <= MAX_EXCEL_ROWS:
                df.to_excel(w, sheet_name=base_name, index=False)
            else:
                # 超过单表行数限制则分片写入多张 sheet（vintage_risk -> vintage_risk, vintage_risk_2, ...）
                written = 0
                part = 1
                while written < n_rows:
                    chunk = df.iloc[written : written + MAX_EXCEL_ROWS]
                    sheet_name = base_name if part == 1 else (base_name[:28] + f"_{part}")[:31]
                    chunk.to_excel(w, sheet_name=sheet_name, index=False)
                    written += len(chunk)
                    part += 1
                print(f"    [分片] {name} 共 {n_rows} 行 -> {part - 1} 张 sheet")

    print()
    print(f"已保存: {output_path}")
    print("含取数 3 Sheet + 探查若干 Sheet，请将该 Excel 发回，Agent 可据此看到探查内容并做维度映射。")
    print("=" * 60)
    print()
    try:
        input("按 Enter 键关闭窗口...")
    except EOFError:
        pass


if __name__ == "__main__":
    main()
