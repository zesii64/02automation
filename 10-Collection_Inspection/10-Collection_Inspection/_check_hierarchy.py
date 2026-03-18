# -*- coding: utf-8 -*-
import pandas as pd
df = pd.read_excel('data/collection_inspection_data_local.xlsx', sheet_name='natural_month_repay_daily', engine='openpyxl')

with open('_hierarchy_check.txt', 'w', encoding='utf-8') as f:
    # 4.组别层级: group_name -> case_bucket mapping
    df4 = df[df['data_level'] == '4.组别层级']
    f.write("=== 4.组别层级: group_name -> case_bucket mapping ===\n")
    mapping = df4.groupby('group_name')['case_bucket'].apply(lambda x: sorted(x.unique().tolist())).to_dict()
    for gn in sorted(mapping.keys()):
        f.write(f"  {gn.strip()}: {mapping[gn]}\n")
    
    # Also check agent_bucket for groups
    f.write("\n=== 4.组别层级: group_name -> agent_bucket mapping ===\n")
    mapping2 = df4.groupby('group_name')['agent_bucket'].apply(lambda x: sorted(x.unique().tolist())).to_dict()
    for gn in sorted(mapping2.keys()):
        f.write(f"  {gn.strip()}: {mapping2[gn]}\n")

    # 5.经办层级: sample group -> owner count
    df5 = df[df['data_level'] == '5.经办层级']
    f.write("\n=== 5.经办层级: group_name -> owner count ===\n")
    owner_count = df5.groupby('group_name')['owner_id'].nunique().sort_values(ascending=False)
    for gn, cnt in owner_count.items():
        f.write(f"  {gn.strip()}: {cnt} agents\n")
    
    # Check: does case_bucket in 4.组别层级 include both module-level AND sub-module-level?
    f.write("\n=== Unique case_bucket at 4.组别层级 ===\n")
    for cb in sorted(df4['case_bucket'].unique()):
        groups = sorted([str(g) for g in df4[df4['case_bucket']==cb]['group_name'].dropna().unique()])
        f.write(f"  {cb}: {len(groups)} groups -> {[g.strip() for g in groups[:5]]}{'...' if len(groups)>5 else ''}\n")

print("Done")
