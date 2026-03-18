# -*- coding: utf-8 -*-
import pandas as pd
xl = pd.ExcelFile('data/collection_inspection_data_local.xlsx', engine='openpyxl')
print("Sheets:", xl.sheet_names)
for s in xl.sheet_names:
    df = pd.read_excel(xl, sheet_name=s, nrows=2)
    print(f"  {s}: cols={list(df.columns)[:6]}...")
