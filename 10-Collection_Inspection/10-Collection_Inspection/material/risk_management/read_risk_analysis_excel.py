# -*- coding: utf-8 -*-
"""
Read 250512_risk_analysis.xlsx and print sheet names + first rows for Wiki/doc alignment.
Run: python read_risk_analysis_excel.py
"""
import sys
import io
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
EXCEL_NAME = "250512_risk_analysis.xlsx"
EXCEL_PATH = SCRIPT_DIR / EXCEL_NAME

def main():
    if not EXCEL_PATH.exists():
        print(f"File not found: {EXCEL_PATH}")
        print("Please place 250512_risk_analysis.xlsx in the same folder as this script.")
        return 1
    try:
        import pandas as pd
    except ImportError:
        print("Need pandas and openpyxl: pip install pandas openpyxl")
        return 1

    xl = pd.ExcelFile(EXCEL_PATH, engine="openpyxl")
    print("Sheets:", xl.sheet_names)
    print()
    for sheet in xl.sheet_names[:25]:
        df = pd.read_excel(xl, sheet_name=sheet, header=None)
        print(f"--- {sheet} --- shape {df.shape}")
        print(df.head(12).to_string())
        print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
