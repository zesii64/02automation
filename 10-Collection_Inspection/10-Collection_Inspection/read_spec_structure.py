# -*- coding: utf-8 -*-
"""One-off: read 【数据巡检】数据准备.xlsx and print sheet names + column names to stdout (UTF-8)."""
import sys
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT = Path(__file__).resolve().parent
# Find spec file by name pattern
spec = None
for f in PROJECT.glob("*.xlsx"):
    if "数据准备" in f.name or "数据巡检" in f.name:
        spec = f
        break
if spec is None:
    print("No 【数据巡检】数据准备.xlsx found")
    sys.exit(1)

import pandas as pd
out_path = PROJECT / "spec_structure.txt"
lines = []
xl = pd.ExcelFile(spec, engine="openpyxl")
lines.append("File: " + spec.name)
lines.append("Sheets: " + str(xl.sheet_names))
for s in xl.sheet_names:
    df = pd.read_excel(xl, sheet_name=s, nrows=2)
    lines.append("Sheet: " + s + " | Columns: " + str(list(df.columns)))
    df_full = pd.read_excel(xl, sheet_name=s)
    lines.append("--- Full content (all rows) ---")
    lines.append(df_full.to_string())
out_path.write_text("\n".join(lines), encoding="utf-8")
print("Written:", out_path)
