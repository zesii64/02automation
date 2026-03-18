# -*- coding: utf-8 -*-
import pandas as pd
df = pd.read_excel('data/collection_inspection_data_local.xlsx', sheet_name='natural_month_repay_daily', engine='openpyxl')
with open('_new_data_check.txt', 'w', encoding='utf-8') as f:
    f.write(f"Total rows: {len(df)}\n")
    f.write(f"Columns: {list(df.columns)}\n\n")
    
    levels = sorted(df['data_level'].dropna().unique().tolist())
    f.write(f"data_level values ({len(levels)}):\n")
    for l in levels:
        cnt = len(df[df['data_level']==l])
        f.write(f"  {l}: {cnt} rows\n")
    
    f.write(f"\n=== Per data_level breakdown ===\n")
    for l in levels:
        sub = df[df['data_level']==l]
        cb = sorted(sub['case_bucket'].dropna().unique().tolist())
        f.write(f"\n--- {l} ({len(sub)} rows) ---\n")
        f.write(f"  case_bucket: {cb}\n")
        if 'agent_bucket' in sub.columns:
            ab = [x for x in sub['agent_bucket'].dropna().unique().tolist() if str(x).strip()]
            if ab:
                f.write(f"  agent_bucket: {sorted(ab)}\n")
        if 'group_name' in sub.columns:
            gn = [x for x in sub['group_name'].dropna().unique().tolist() if str(x).strip()]
            if gn:
                f.write(f"  group_name ({len(gn)}): {sorted(gn)[:10]}{'...' if len(gn)>10 else ''}\n")
        if 'owner_id' in sub.columns:
            oid = sub['owner_id'].dropna().unique()
            f.write(f"  owner_id count: {len(oid)}\n")
        nm = sorted(sub['natural_month'].dropna().unique().tolist())
        f.write(f"  natural_month: {nm}\n")

    # Check 1.5 specifically
    f.write(f"\n=== 1.5.大小模块层级 detail ===\n")
    ls = [l for l in levels if '1.5' in str(l) or '大小' in str(l)]
    if ls:
        sub15 = df[df['data_level'] == ls[0]]
        f.write(f"  Level name: {ls[0]}\n")
        f.write(f"  Rows: {len(sub15)}\n")
        cb15 = sorted(sub15['case_bucket'].dropna().unique().tolist())
        f.write(f"  case_bucket values: {cb15}\n")
        # Check which have Large/Small
        large_small = [c for c in cb15 if 'Large' in str(c) or 'Small' in str(c)]
        f.write(f"  Large/Small only: {large_small}\n")
    else:
        f.write("  NOT FOUND in data!\n")

print("Done")
