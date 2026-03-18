import pandas as pd

EXCEL = 'D:/0_phirisk/12-agent_finalize/10-Collection_Inspection/data/collection_inspection_data_local.xlsx'

# === Issue 1: Natural Month data ===
df = pd.read_excel(EXCEL, sheet_name='natural_month_repay_daily')
data_levels = sorted(df['data_level'].dropna().unique())
module_level = data_levels[0]
print("module_level:", repr(module_level))

df_m = df[df['data_level'] == module_level]
print(f"Module level rows: {len(df_m)}")

# Check how many rows per (natural_month, case_bucket, day) at module level
dup_check = df_m.groupby(['natural_month','case_bucket','day']).size().reset_index(name='cnt')
print(f"Max rows per group: {dup_check['cnt'].max()}")
print(f"Groups with >1 row: {(dup_check['cnt']>1).sum()}")

# Show M1 202602 data
m1 = df_m[(df_m['case_bucket']=='M1') & (df_m['natural_month']==202602)].sort_values('day')
print(f"\nM1 202602: {len(m1)} rows")
if not m1.empty:
    print(m1[['day','repay_principal','start_owing_principal']].head(10).to_string())
    # Aggregate
    agg = m1.groupby('day').agg(repay=('repay_principal','sum'), start=('start_owing_principal','sum')).reset_index()
    print(f"\nAfter agg: {len(agg)} rows")
    print(agg.head(10).to_string())
    total_repay = agg['repay'].sum()
    start_owing = agg['start'].iloc[0]
    print(f"\nTotal repay: {total_repay:,.0f}")
    print(f"Start owing (day1 agg): {start_owing:,.0f}")
    print(f"Cum rate: {total_repay/start_owing*100:.1f}%")
    print(f"\nNote: start_owing varies by day?")
    print(agg[['day','start']].describe().to_string())

# === Issue 2: Due Month data ===
print("\n\n=== Due Month Recovery ===")
df2 = pd.read_excel(EXCEL, sheet_name='due_month_repay')
print("user_type values:", df2['user_type'].unique().tolist())
print("flag_bucket values:", df2['flag_bucket'].unique().tolist())
for ut in df2['user_type'].unique():
    sub = df2[(df2['flag_bucket']=='ALL') & (df2['user_type']==ut)]
    d_min = sub['days_from_duedate'].min()
    d_max = sub['days_from_duedate'].max()
    dms = sorted(sub['due_mth'].unique())
    print(f"  user_type={repr(ut)}, ALL rows={len(sub)}, days={d_min}-{d_max}, months={dms}")
