import pandas as pd

EXCEL = 'D:/0_phirisk/12-agent_finalize/10-Collection_Inspection/data/collection_inspection_data_local.xlsx'

# Check target (250003) data
df = pd.read_excel(EXCEL, sheet_name='natural_month_repay_daily')
data_levels = sorted(df['data_level'].dropna().unique())
module_level = data_levels[0]
df_m = df[df['data_level'] == module_level]

target = df_m[df_m['natural_month'] == 250003].sort_values(['case_bucket', 'day'])
print("Target (250003) data at module level:")
print(f"  Rows: {len(target)}")
print(f"  Buckets: {sorted(target['case_bucket'].unique())}")

for bkt in sorted(target['case_bucket'].unique()):
    bkt_t = target[target['case_bucket'] == bkt].sort_values('day')
    print(f"\n  {bkt}: {len(bkt_t)} rows")
    print(bkt_t[['day', 'repay_principal', 'start_owing_principal']].head(5).to_string())

# Verify: if repay_principal is already cumulative
print("\n\n=== Check M1 202511 (more data) ===")
m1_511 = df_m[(df_m['case_bucket'] == 'M1') & (df_m['natural_month'] == 202511)].sort_values('day')
print(f"M1 202511: {len(m1_511)} rows")
print(m1_511[['day', 'repay_principal', 'start_owing_principal']].head(10).to_string())
print()
print(m1_511[['day', 'repay_principal', 'start_owing_principal']].tail(5).to_string())

# Calculate rate = repay/start_owing for each day
m1_511_rate = (m1_511['repay_principal'] / m1_511['start_owing_principal']).values
print(f"\nRates: first 5 = {[round(r*100,2) for r in m1_511_rate[:5]]}")
print(f"Rates: last 5 = {[round(r*100,2) for r in m1_511_rate[-5:]]}")
