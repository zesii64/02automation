# -*- coding: utf-8 -*-
"""
贷后数据巡检 - 聚合版专用下载脚本（943 平台用）

只跑 3 个聚合 SQL，不下明细、不跑探查，行数少、下载快。
产出：collection_inspection_data_local.xlsx，含 Sheet：vintage_risk、natural_month_repay、process_data，
与明细版同名，本地 run_daily_report / run_cashloan_report 可直接用。

依赖：同目录下 vintage_risk_agg.sql、natural_month_repay_agg.sql、process_data_agg.sql
"""

import sys
from pathlib import Path

ODPS_ACCESS_ID = __import__("os").environ.get("ODPS_ACCESS_ID", "")
ODPS_ACCESS_KEY = __import__("os").environ.get("ODPS_ACCESS_KEY", "")
ODPS_PROJECT = __import__("os").environ.get("ODPS_PROJECT", "phl_anls")
ODPS_ENDPOINT = __import__("os").environ.get("ODPS_ENDPOINT", "https://service.ap-southeast-1-vpc.maxcompute.aliyun-inc.com/api")

OUTPUT_EXCEL = "collection_inspection_data_local.xlsx"
MAX_EXCEL_ROWS = 1048575

# 聚合版：09 表 due_date+mob+user_type；回收 自然月+催员；过程 月+bucket+group
SQL_FILES = [
    ("vintage_risk_agg.sql", "vintage_risk"),
    ("natural_month_repay_agg.sql", "natural_month_repay"),
    ("process_data_agg.sql", "process_data"),
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
    sql = sql_path.read_text(encoding="utf-8", errors="replace").strip().rstrip(";").strip()
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
    parser = argparse.ArgumentParser(description="聚合版下载：只跑 3 个聚合 SQL，产出同名 Excel")
    parser.add_argument("--output", "-o", default=OUTPUT_EXCEL, help="输出 Excel 文件名")
    parser.add_argument("--dir", "-d", default=None, help="输出目录（默认脚本同目录）")
    parser.add_argument("--sql-dir", default=None, help="SQL 所在目录（默认与脚本同目录）")
    parser.add_argument("--no-pause", action="store_true", help="结束后不等待 Enter")
    args = parser.parse_args(argv)

    base_dir = Path(args.dir) if args.dir else _script_dir()
    sql_dir = Path(args.sql_dir) if args.sql_dir else _script_dir()
    output_path = base_dir / args.output

    print("=" * 60)
    print("贷后数据巡检 - 聚合版下载（09 表/回收/过程 均聚合，行数少）")
    print("=" * 60)
    print(f"SQL 目录: {sql_dir}")
    print(f"输出: {output_path}")
    print()

    import pandas as pd
    odps = get_odps()
    sheets = {}

    for sql_file, sheet_name in SQL_FILES:
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

    with pd.ExcelWriter(output_path, engine="openpyxl") as w:
        for name, df in sheets.items():
            base_name = name[:31]
            n_rows = len(df)
            if n_rows <= MAX_EXCEL_ROWS:
                df.to_excel(w, sheet_name=base_name, index=False)
            else:
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
    print("请将该 Excel 放到 10-Collection_Inspection/data/ 或脚本同目录，再运行 run_cashloan_report.py / run_daily_report.py。")
    print("=" * 60)
    if not getattr(args, "no_pause", False):
        try:
            input("按 Enter 键关闭窗口...")
        except EOFError:
            pass


if __name__ == "__main__":
    main()
