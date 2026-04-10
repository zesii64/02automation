"""
Collection Operations Report v3.3 - Real Data v3
Base: Collection_Operations_Report_v2_2.html
Data: 260318_output_automation_v3.xlsx
Changes vs v2.4:
  - TL Agent tab: use daily_target_agent_repay for target/actual/achievement,
    ptp_agent_data for ptp, call_loss_agent_data for call loss rate
  - STL Group tab: use daily_target_group_repay for weekly repay,
    ptp_group_data for ptpRate, call_loss_group_data for call loss rate
  - consecutiveDays: computed from agent achieve_rate < 1.0
  - PTP stored as fraction -> JS displays as %
  - Default TL date: 2026-03-21 (max common date across all agent sources)
  - Default STL week: most-recent complete week
  - Call Loss Rate column added to all agent/group tables
Output: Collection_Operations_Report_v3_3.html
"""
import pandas as pd
import json
import math
import re
from datetime import timedelta
from calendar import monthrange

# ========================
# Paths
# ========================
BASE       = r'd:/11automation/02automation/10-Collection_Inspection/10-Collection_Inspection'
EXCEL_PATH = BASE + r'/data/260318_output_automation_v3.xlsx'
PROCESS_TARGET_PATH = BASE + r'/data/process_data_target.xlsx'
HTML_IN    = BASE + r'/reports/Collection_Operations_Report_v2_2.html'
HTML_OUT   = BASE + r'/reports/Collection_Operations_Report_v3_3.html'

# ========================
# Load data
# ========================
print("Loading Excel data (v3)...")
xl           = pd.ExcelFile(EXCEL_PATH)
tl_data      = pd.read_excel(xl, 'tl_data',              index_col=0)
stl_data     = pd.read_excel(xl, 'stl_data',             index_col=0)
agent_perf   = pd.read_excel(xl, 'agent_performance',    index_col=0)
group_perf   = pd.read_excel(xl, 'group_performance',    index_col=0)
daily_tr     = pd.read_excel(xl, 'daily_target_agent_repay', index_col=0)  # daily repay per agent; group/module agg done in code
agent_repay  = pd.read_excel(xl, 'daily_target_agent_repay', index_col=0)
group_repay  = pd.read_excel(xl, 'daily_target_group_repay', index_col=0)
ptp_agent    = pd.read_excel(xl, 'ptp_agent_data',        index_col=0)
ptp_group    = pd.read_excel(xl, 'ptp_group_data',         index_col=0)
cl_agent     = pd.read_excel(xl, 'call_loss_agent_data',   index_col=0)
cl_group     = pd.read_excel(xl, 'call_loss_group_data',   index_col=0)
nat_month    = pd.read_excel(xl, 'natural_month_repay',   index_col=0)

try:
    process_target_raw = pd.read_excel(PROCESS_TARGET_PATH, header=1)
except Exception as e:
    print(f"  WARN: process target file not loaded: {e}")
    process_target_raw = pd.DataFrame(columns=['module_key', 'art_call_times', 'connect_billhr'])

# Strip whitespace
tl_data['group_id']       = tl_data['group_id'].str.strip()
agent_perf['group_id']    = agent_perf['group_id'].str.strip()
group_perf['group_id']    = group_perf['group_id'].str.strip()
daily_tr['owner_group']   = daily_tr['owner_group'].str.strip()
agent_repay['owner_group']= agent_repay['owner_group'].str.strip()
group_repay['owner_group']= group_repay['owner_group'].str.strip()
ptp_agent['owner_group']  = ptp_agent['owner_group'].str.strip()
cl_agent['group_name']    = cl_agent['group_name'].str.strip()
cl_group['group_name']    = cl_group['group_name'].str.strip()
group_perf['week']        = group_perf['week'].astype(str)

# Parse dates
tl_data['dt']       = pd.to_datetime(tl_data['dt'])
agent_perf['dt']    = pd.to_datetime(agent_perf['dt'])
daily_tr['dt']      = pd.to_datetime(daily_tr['dt'])
agent_repay['dt']   = pd.to_datetime(agent_repay['dt'])
ptp_agent['dt']     = pd.to_datetime(ptp_agent['dt'])
cl_agent['dt']      = pd.to_datetime(cl_agent['dt'])
nat_month['dt_biz'] = pd.to_datetime(nat_month['dt_biz'])

group_repay['week'] = group_repay['week'].astype(str)
ptp_group['week']   = ptp_group['week'].astype(str)
cl_group['week']    = cl_group['week'].astype(str)
group_perf['week']  = group_perf['week'].astype(str)

data_warning_set = set()

def parse_week_str(ws):
    m = re.match(r'^(\d{4}-\d{2}-\d{2})-(\d{4}-\d{2}-\d{2})$', str(ws).strip())
    if not m:
        return None, None
    return pd.to_datetime(m.group(1)), pd.to_datetime(m.group(2))

def format_week_range(start_dt, end_dt):
    return f"{start_dt.strftime('%Y-%m-%d')}-{end_dt.strftime('%Y-%m-%d')}"

def normalize_week_label(ws):
    start_dt, end_dt = parse_week_str(ws)
    if start_dt is None or end_dt is None:
        data_warning_set.add(f"Unparseable week label: {ws}")
        return str(ws)

    # Required week definition: Saturday -> Friday
    if start_dt.weekday() == 5 and end_dt.weekday() == 4:
        return format_week_range(start_dt, end_dt)

    # Common source format: Sunday -> Saturday, shift back one day.
    if start_dt.weekday() == 6 and end_dt.weekday() == 5:
        shifted_start = start_dt - timedelta(days=1)
        shifted_end = end_dt - timedelta(days=1)
        data_warning_set.add(f"Week label converted Sun-Sat -> Sat-Fri: {ws} -> {format_week_range(shifted_start, shifted_end)}")
        return format_week_range(shifted_start, shifted_end)

    data_warning_set.add(f"Unexpected week boundary (not Sat-Fri): {ws}")
    return format_week_range(start_dt, end_dt)

def week_start_dt(ws):
    start_dt, _ = parse_week_str(ws)
    return start_dt if start_dt is not None else pd.Timestamp.min

group_repay['week'] = group_repay['week'].apply(normalize_week_label)
ptp_group['week']   = ptp_group['week'].apply(normalize_week_label)
cl_group['week']    = cl_group['week'].apply(normalize_week_label)
group_perf['week']  = group_perf['week'].apply(normalize_week_label)

# Core TL group list
all_groups = sorted(tl_data['group_id'].unique().tolist())

# ========================
# Key dates
# ========================
# TL daily cutoff:
# - keep data up to yesterday (exclude today)
# - align with TL core daily sheets (repay/performance/ptp)
# - only require 3 core sheets share the date
RUN_YESTERDAY_DT = (pd.Timestamp.now().normalize() - timedelta(days=1))
agent_perf_dates = set(agent_perf.loc[agent_perf['dt'] <= RUN_YESTERDAY_DT, 'dt'].unique().tolist())
agent_repay_dates = set(agent_repay.loc[agent_repay['dt'] <= RUN_YESTERDAY_DT, 'dt'].unique().tolist())
ptp_agent_dates = set(ptp_agent.loc[ptp_agent['dt'] <= RUN_YESTERDAY_DT, 'dt'].unique().tolist())
common_tl_dates = sorted(agent_perf_dates & agent_repay_dates & ptp_agent_dates)

# TL daily cutoff:
# - only exclude today (use <= yesterday)
# - keep latest day that all three TL core sheets share
if len(common_tl_dates) > 0:
    TL_LATEST_DT = max(common_tl_dates)
else:
    TL_CORE_MAX_DT = min(
        agent_perf['dt'].max(),
        agent_repay['dt'].max(),
        ptp_agent['dt'].max()
    )
    TL_LATEST_DT = min(TL_CORE_MAX_DT, RUN_YESTERDAY_DT)

TL_LATEST_STR = TL_LATEST_DT.strftime('%Y-%m-%d')
TL_LATEST_DAY = TL_LATEST_DT.day  # 21
REPORT_YEAR = TL_LATEST_DT.year
REPORT_MONTH = TL_LATEST_DT.month

# All weeks from group_repay
all_weeks_sorted = sorted(group_repay['week'].unique(), key=week_start_dt)
print(f"  TL latest date    : {TL_LATEST_STR}")
print(f"  Daily cutoff date : {RUN_YESTERDAY_DT.strftime('%Y-%m-%d')}")
print(f"  All weeks         : {all_weeks_sorted}")

# Default STL week: most-recent complete week (skip 2026-03-22-2026-03-28 if partial)
DEFAULT_STL_WEEK = all_weeks_sorted[-2] if len(all_weeks_sorted) >= 2 else all_weeks_sorted[-1]
print(f"  Default STL week  : {DEFAULT_STL_WEEK}")
if data_warning_set:
    print(f"  Data warnings     : {len(data_warning_set)}")
    for w in sorted(data_warning_set)[:8]:
        print(f"    - {w}")

# ========================
# Helpers
# ========================
def extract_module_key(group):
    g     = group.strip()
    parts = g.split('-')
    if len(parts) >= 2:
        first_word = parts[1].strip().split()[0].lower() if parts[1].strip() else ''
        if first_word in ('large', 'small'):
            return f"{parts[0]}-{parts[1].strip().split()[0].capitalize()}"
    return parts[0]

def map_group_to_dtr(group):
    g = group.strip()
    if g.startswith('S0-'):
        remainder = g[3:].strip()
        letter    = remainder.split()[0]
        return f'S0-{letter} Bucket'
    return g

def norm(g):
    """Normalize group name for cross-sheet matching."""
    return str(g).replace(' ', '').replace('-', '') if pd.notna(g) else ''

def get_week_label(dt):
    dow            = dt.dayofweek
    days_since_sat = (dow - 5) % 7
    week_start     = dt - timedelta(days=int(days_since_sat))
    week_end       = week_start + timedelta(days=6)
    return f"{week_start.strftime('%Y-%m-%d')}-{week_end.strftime('%Y-%m-%d')}"

def week_str_to_display(ws):
    start_dt, end_dt = parse_week_str(ws)
    if start_dt is None or end_dt is None:
        return str(ws)
    return f"{start_dt.strftime('%m/%d')} - {end_dt.strftime('%m/%d')}"

def detect_day_only_cross_month_risk(df, date_col, key_cols):
    """
    Generic guard for day-of-month aggregation:
    detect whether any (key_cols + day) appears in more than one month.
    """
    if date_col not in df.columns:
        return 0
    d = df.dropna(subset=[date_col]).copy()
    if len(d) == 0:
        return 0
    d['dom'] = pd.to_datetime(d[date_col]).dt.day
    d['ym'] = pd.to_datetime(d[date_col]).dt.to_period('M').astype(str)
    month_cnt = (
        d.groupby(key_cols + ['dom'], dropna=False)['ym']
         .nunique()
         .reset_index(name='month_cnt')
    )
    return int((month_cnt['month_cnt'] > 1).sum())

def filter_report_month(df, date_col, report_year, report_month):
    d = df.copy()
    d[date_col] = pd.to_datetime(d[date_col])
    return d[
        (d[date_col].dt.year == report_year) &
        (d[date_col].dt.month == report_month)
    ].copy()

# ========================
# Build derived structures
# ========================
tl_data['group_module'] = tl_data['group_id'].apply(extract_module_key)

submodule_groups = {}
for g in all_groups:
    mk = extract_module_key(g)
    submodule_groups.setdefault(mk, []).append(g)
modules_list = sorted(submodule_groups.keys())

# Module process targets from process_data_target.xlsx
process_target_js = {}
if len(process_target_raw) > 0:
    raw_cols_lower = {c: str(c).strip().lower() for c in process_target_raw.columns}

    def pick_col(needles_any, needles_all=None):
        """
        needles_any: list[str] - return the first column whose name contains any of these needles
        needles_all: optional list[str] - additionally require all needles to appear in the column name
        """
        needles_all = needles_all or []
        for c, lc in raw_cols_lower.items():
            if needles_all and not all(n in lc for n in needles_all):
                continue
            if any(n in lc for n in needles_any):
                return c
        return None

    module_key_col = pick_col(['module_key', 'module'], needles_all=[])
    if module_key_col is None:
        module_key_col = process_target_raw.columns[0]

    art_call_times_col = pick_col(['art_call_times', 'art_call'], needles_all=[])
    if art_call_times_col is None and len(process_target_raw.columns) >= 2:
        art_call_times_col = process_target_raw.columns[1]

    call_billmin_col = pick_col(['call_billmin', 'connect_billmin', 'billmin'])
    call_billhr_col = pick_col(['call_billhr', 'connect_billhr', 'billhr'])

    # Build a slim dataframe with the columns we need
    pt_keep = [module_key_col]
    if art_call_times_col is not None:
        pt_keep.append(art_call_times_col)
    call_billmin_for_pt = call_billmin_col if call_billmin_col is not None else call_billhr_col
    if call_billmin_for_pt is not None:
        pt_keep.append(call_billmin_for_pt)

    pt_df = process_target_raw[pt_keep].copy()
    pt_df.columns = ['module_key'] + (['art_call_times'] if art_call_times_col is not None else []) + ['call_billmin_raw']

    pt_df['module'] = pt_df['module_key'].astype(str).str.strip().str.replace('_', '-', regex=False)
    pt_df['art_call_times'] = pd.to_numeric(pt_df['art_call_times'], errors='coerce') if 'art_call_times' in pt_df.columns else pd.Series(dtype=float)
    pt_df['call_billmin_raw'] = pd.to_numeric(pt_df['call_billmin_raw'], errors='coerce')

    # Optionally keep connect_billhr for backward compatibility (not used for process KPI after switching)
    if call_billhr_col is not None:
        pt_df['connect_billhr'] = pd.to_numeric(process_target_raw[call_billhr_col], errors='coerce')
    else:
        pt_df['connect_billhr'] = pd.Series([None] * len(pt_df), dtype=float)

    for _, r in pt_df.iterrows():
        mk = r['module']
        if mk not in modules_list:
            continue
        art_call = int(round(float(r['art_call_times']))) if 'art_call_times' in r and pd.notna(r['art_call_times']) else None
        # `call_billmin` in process_data_target.xlsx appears to be in hours; convert to minutes for raw comparison/display.
        call_billmin_target = (float(r['call_billmin_raw']) * 60) if pd.notna(r['call_billmin_raw']) else None

        connect_raw = float(r['connect_billhr']) if pd.notna(r['connect_billhr']) else None
        connect_pct = (
            round(connect_raw * 100, 1)
            if connect_raw is not None and connect_raw <= 1.0
            else (round(connect_raw, 1) if connect_raw is not None else None)
        )

        process_target_js[mk] = {
            'artCallTimes': art_call,
            # New standard for process KPI judgement
            'callBillminRawTarget': call_billmin_target,
            # Kept for compatibility with parts not yet migrated
            'connectBillhrPct': connect_pct
        }

    target_modules = set(process_target_js.keys())
    missing_targets = [m for m in modules_list if m not in target_modules]
    if missing_targets:
        data_warning_set.add(f"Missing process targets for modules: {missing_targets}")

submodule_dtr_groups = {
    mk: {map_group_to_dtr(g) for g in groups}
    for mk, groups in submodule_groups.items()
}
dtr_to_submodule = {map_group_to_dtr(g): extract_module_key(g) for g in all_groups}

# Normalized lookups for cross-sheet joins
all_groups_norm = {norm(g): g for g in all_groups}

agent_repay['grp_norm']  = agent_repay['owner_group'].apply(norm)
agent_repay['name_norm'] = agent_repay['owner_name'].apply(lambda x: str(x).strip().lower() if pd.notna(x) else '')
ptp_agent['grp_norm']    = ptp_agent['owner_group'].apply(norm)
ptp_agent['name_norm']   = ptp_agent['owner_name'].apply(lambda x: str(x).strip().lower() if pd.notna(x) else '')
cl_agent['grp_norm']     = cl_agent['group_name'].apply(norm)
cl_agent['name_norm']    = cl_agent['owner_name'].apply(lambda x: str(x).strip().lower() if pd.notna(x) else '')

group_repay['grp_norm'] = group_repay['owner_group'].apply(norm)
ptp_group['grp_norm']    = ptp_group['owner_group'].apply(norm)
cl_group['grp_norm']     = cl_group['group_name'].apply(norm)

# TL available dates: all dates from agent_repay
available_dates = sorted(
    [d.strftime('%Y-%m-%d') for d in agent_repay['dt'].unique() if pd.to_datetime(d) <= RUN_YESTERDAY_DT],
    reverse=True
)
print(f"  Available TL dates: {len(available_dates)}")

# Consecutive days helper
def compute_consecutive_days(df_agent, cutoff_dt):
    df_agent = df_agent[df_agent['dt'] <= cutoff_dt]
    streak = 0
    for _, row in df_agent.sort_values('dt', ascending=False).iterrows():
        ach = float(row['achieve_rate']) if pd.notna(row['achieve_rate']) else 0.0
        if ach < 1.0:
            streak += 1
        else:
            break
    return streak

def build_consecutive_weeks_map(week_map):
    if not week_map:
        return {}
    sorted_weeks = sorted(week_map.keys(), key=week_start_dt)
    res = {}
    for i, wk in enumerate(sorted_weeks):
        streak = 0
        j = i
        while j >= 0:
            wj = sorted_weeks[j]
            ach = float(week_map[wj].get('achievement', 0.0))
            if ach < 100:
                streak += 1
                j -= 1
            else:
                break
        res[wk] = streak
    return res

# ========================
# ========================
# Pre-process natural_month_repay for targetRepayRate
# ========================
print("Processing natural_month_repay...")
nat_month['group_name']   = nat_month['group_name'].str.strip()
nat_month['agent_bucket'] = nat_month['agent_bucket'].str.strip()
nat_month['day']          = nat_month['dt_biz'].dt.day

# Generic guard: if this is >0, any day-only aggregation without month filter
# can mix multiple months and produce wrong rates.
nat_month_cross_month_day_key_cnt = detect_day_only_cross_month_risk(
    nat_month,
    date_col='dt_biz',
    key_cols=['agent_bucket', 'group_name']
)
if nat_month_cross_month_day_key_cnt > 0:
    data_warning_set.add(
        "natural_month_repay has cross-month day-key overlap: "
        f"{nat_month_cross_month_day_key_cnt} key-day combinations. "
        "Any day-of-month aggregation must filter report month first."
    )

# Always filter to report month before building day-of-month dicts.
nat_month = filter_report_month(nat_month, 'dt_biz', REPORT_YEAR, REPORT_MONTH)
if len(nat_month) == 0:
    data_warning_set.add(
        f"natural_month_repay has no rows for report month {REPORT_YEAR}-{REPORT_MONTH:02d}"
    )
nat_month_single_month_ok = (
    len(nat_month) == 0 or
    nat_month['dt_biz'].dt.to_period('M').nunique() == 1
)

nat_buckets = set(nat_month['agent_bucket'].dropna().unique().tolist())

def module_key_to_bucket(mk):
    # For non-split modules (e.g. S0/M2), use *_Other bucket if present.
    if '-' not in mk:
        other_bucket = f"{mk}_Other"
        if other_bucket in nat_buckets:
            return other_bucket
    direct_bucket = mk.replace('-', '_')
    if direct_bucket in nat_buckets:
        return direct_bucket
    fallback_bucket = f"{mk}_Other"
    return fallback_bucket if fallback_bucket in nat_buckets else direct_bucket

target_nm_dict = {}
for _, row in nat_month[nat_month['group_name'] == 'Target'].iterrows():
    bucket = row['agent_bucket']
    day    = int(row['day'])
    rr     = float(row['repay_rate']) * 100
    target_nm_dict.setdefault(bucket, {})[day] = round(rr, 4)

module_nm_dict = {}
nontar_nm = nat_month[nat_month['group_name'] != 'Target']
module_group_nm_dict = {}
for mk in modules_list:
    mk_bucket = module_key_to_bucket(mk)
    mk_nm     = nontar_nm[nontar_nm['agent_bucket'] == mk_bucket]
    module_nm_dict[mk] = {}
    module_group_nm_dict[mk] = {}
    for day, day_data in mk_nm.groupby('day'):
        total_repay = day_data['repay_principal'].astype(float).sum()
        total_owing = day_data['start_owing_principal'].astype(float).sum()
        rr = total_repay / total_owing * 100 if total_owing > 0 else 0.0
        module_nm_dict[mk][int(day)] = round(rr, 4)
    for g in submodule_groups.get(mk, []):
        g_nm = mk_nm[mk_nm['group_name'] == g.strip()]
        group_daily = {}
        for day, day_data in g_nm.groupby('day'):
            total_repay = day_data['repay_principal'].astype(float).sum()
            total_owing = day_data['start_owing_principal'].astype(float).sum()
            rr = total_repay / total_owing * 100 if total_owing > 0 else 0.0
            group_daily[int(day)] = round(rr, 4)
        module_group_nm_dict[mk][g] = group_daily

# ========================
# 1. TL DATA
# ========================
print("Building tlData...")
DAYS_IN_MONTH = monthrange(REPORT_YEAR, REPORT_MONTH)[1]

latest_dtr_agg = (daily_tr[daily_tr['dt'] == TL_LATEST_DT]
                  .groupby('owner_group', as_index=False)
                  .agg(target=('target_repay_principal', lambda x: x.astype(float).sum()),
                       actual=('actual_repay_principal', lambda x: x.astype(float).sum()),
                       owing =('daily_owing_principal',  lambda x: x.astype(float).sum()))
                  .set_index('owner_group'))

module_avg_ach = {}
for mk, dtr_groups in submodule_dtr_groups.items():
    sub = latest_dtr_agg[latest_dtr_agg.index.isin(dtr_groups)]
    if len(sub) > 0:
        t = sub['target'].sum(); a = sub['actual'].sum()
        module_avg_ach[mk] = round(a / t * 100, 1) if t > 0 else 0.0
    else:
        module_avg_ach[mk] = 0.0

tl_data_js = {}
for group in all_groups:
    group_rows   = tl_data[tl_data['group_id'] == group]
    group_module = extract_module_key(group)
    dtr_name     = map_group_to_dtr(group)

    if dtr_name in latest_dtr_agg.index:
        row   = latest_dtr_agg.loc[dtr_name]
        target      = round(float(row['target']))
        actual      = round(float(row['actual']))
        achievement = round(float(row['actual']) / float(row['target']) * 100, 1) if float(row['target']) > 0 else 0.0
        gap         = max(0.0, float(row['target']) - float(row['actual']))
    else:
        target = actual = achievement = gap = 0.0

    latest_tl_g = group_rows[group_rows['dt'] == TL_LATEST_DT]
    module_tl   = tl_data[(tl_data['group_module'] == group_module) & (tl_data['dt'] == TL_LATEST_DT)]
    if len(latest_tl_g) > 0 and len(module_tl) > 0:
        g_calls     = float(latest_tl_g['total_calls'].iloc[0])
        g_conn      = float(latest_tl_g['connect_rate'].iloc[0]) * 100
        avg_calls   = float(module_tl['total_calls'].mean())
        avg_conn    = float(module_tl['connect_rate'].mean()) * 100
        call_gap    = round(g_calls - avg_calls)
        connect_gap = round(g_conn - avg_conn, 1)
    else:
        call_gap = connect_gap = 0

    g_dtr = (daily_tr[daily_tr['owner_group'] == dtr_name]
             .groupby('dt', as_index=False)
             .agg(target=('target_repay_principal', lambda x: x.astype(float).sum()),
                  actual=('actual_repay_principal', lambda x: x.astype(float).sum()),
                  owing =('daily_owing_principal',  lambda x: x.astype(float).sum()))
             .set_index('dt'))
    module_bucket  = module_key_to_bucket(group_module)
    module_target_nm = target_nm_dict.get(module_bucket, {})
    module_nm_daily  = module_nm_dict.get(group_module, {})
    group_nm_daily   = module_group_nm_dict.get(group_module, {}).get(group, {})

    days_series = []
    for day in range(1, DAYS_IN_MONTH + 1):
        date_str = f'{REPORT_YEAR}-{REPORT_MONTH:02d}-{day:02d}'
        in_cutoff = day <= TL_LATEST_DAY
        day_rows = g_dtr[g_dtr.index.day == day]
        if len(day_rows) > 0:
            r   = day_rows.iloc[0]
            tgt = round(float(r['target'])) if in_cutoff else None
            act = round(float(r['actual'])) if in_cutoff else None
            owing = float(r['owing'])
            rr   = round(float(r['actual']) / owing * 100, 4) if (in_cutoff and owing > 0) else None
            # targetRepayRate should be visible for full month, not capped by data cutoff day.
            nm_trr = module_target_nm.get(day, None)
            nm_rr  = module_nm_daily.get(day, None) if in_cutoff else None
            g_nm_rr = group_nm_daily.get(day, None) if in_cutoff else None
            days_series.append({'date': date_str, 'target': tgt, 'actual': act,
                                 'repayRate': rr, 'nmRepayRate': g_nm_rr,
                                 'targetRepayRate': nm_trr, 'moduleRepayRate': nm_rr})
        else:
            # targetRepayRate should be visible for full month, not capped by data cutoff day.
            nm_trr = module_target_nm.get(day, None)
            nm_rr  = module_nm_daily.get(day, None) if in_cutoff else None
            g_nm_rr = group_nm_daily.get(day, None) if in_cutoff else None
            days_series.append({'date': date_str, 'target': None, 'actual': None,
                                 'repayRate': None, 'nmRepayRate': g_nm_rr,
                                 'targetRepayRate': nm_trr, 'moduleRepayRate': nm_rr})

    tl_data_js[group] = {
        'groupModule': group_module,
        'target':      target,
        'actual':      actual,
        'achievement': achievement,
        'moduleAvg':   module_avg_ach.get(group_module, 0.0),
        'gap':         round(gap),
        'callGap':     call_gap,
        'connectGap':  connect_gap,
        'days':        days_series
    }

# ========================
# 2. AGENT PERFORMANCE  (from new v3 sheets)
# ========================
# 2. AGENT PERFORMANCE  (from new v3 sheets)
# ========================
print("Building agentPerformance...")

agent_perf_js = {}
agent_perf_by_date_js = {}
for group in all_groups:
    g_norm = norm(group)
    dtr_norm = norm(map_group_to_dtr(group))
    grp_norm_candidates = {g_norm, dtr_norm}
    agents_in_group = agent_perf[agent_perf['group_id'] == group]['agent_id'].unique()
    agent_perf_by_date_js[group] = {}

    for agent_name in agents_in_group:
        a_norm = str(agent_name).strip().lower()

        # Repay metrics from daily_target_agent_repay
        ar = agent_repay[(agent_repay['grp_norm'].isin(grp_norm_candidates)) &
                         (agent_repay['name_norm'] == a_norm) &
                         (agent_repay['dt'] == TL_LATEST_DT)]
        if len(ar) > 0:
            ar_tgt_sum = float(ar['target_repay_principal'].astype(float).sum())
            ar_act_sum = float(ar['actual_repay_principal'].astype(float).sum())
            ar_tgt = round(ar_tgt_sum)
            ar_act = round(ar_act_sum)
            ar_ach = round(ar_act_sum / ar_tgt_sum * 100, 1) if ar_tgt_sum > 0 else 0.0
        else:
            ar_tgt = ar_act = 0; ar_ach = 0.0

        # Consecutive days: count backward from TL_LATEST_DT where achieve_rate < 1.0
        ar_all = agent_repay[(agent_repay['grp_norm'].isin(grp_norm_candidates)) &
                             (agent_repay['name_norm'] == a_norm)]
        cd = compute_consecutive_days(ar_all, RUN_YESTERDAY_DT) if len(ar_all) > 0 else 0

        # Process metrics (for drill-down)
        cover_times_val = None
        call_times_val = None
        art_call_times_val = None
        call_billmin_val = None
        single_call_duration_val = None

        # Call metrics from agent_performance (same day)
        ap_a = agent_perf[(agent_perf['group_id'] == group) &
                          (agent_perf['dt'] == TL_LATEST_DT) &
                          (agent_perf['agent_id'] == agent_name)]
        if len(ap_a) > 0:
            # call_times / art_call_times can both exist; we must populate both.
            if 'art_call_times' in ap_a.columns and pd.notna(ap_a['art_call_times']).any():
                art_call_times_val = int(round(float(ap_a['art_call_times'].astype(float).sum())))
            if 'call_times' in ap_a.columns and pd.notna(ap_a['call_times']).any():
                call_times_val = int(round(float(ap_a['call_times'].astype(float).sum())))

            # "calls" is only used for legacy connect-rate calculations in some templates.
            if art_call_times_val is not None:
                calls = art_call_times_val
            elif call_times_val is not None:
                calls = call_times_val
            else:
                calls = 0

            if 'cover_times' in ap_a.columns and pd.notna(ap_a['cover_times']).any():
                cover_times_val = int(round(float(ap_a['cover_times'].astype(float).sum())))

            if 'call_billmin' in ap_a.columns and pd.notna(ap_a['call_billmin']).any():
                call_billmin_val = float(ap_a['call_billmin'].astype(float).mean())
            elif 'connect_billmin' in ap_a.columns and pd.notna(ap_a['connect_billmin']).any():
                call_billmin_val = float(ap_a['connect_billmin'].astype(float).mean())

            if 'single_call_duration' in ap_a.columns and pd.notna(ap_a['single_call_duration']).any():
                single_call_duration_val = float(ap_a['single_call_duration'].astype(float).mean())

            if 'connect_rate' in ap_a.columns and pd.notna(ap_a['connect_rate']).any():
                conn_r = round(float(ap_a['connect_rate'].astype(float).mean()) * 100, 1)
            elif 'call_billhr' in ap_a.columns:
                conn_val = float(ap_a['call_billhr'].astype(float).mean())
                conn_r = round(conn_val * 100, 1)
            elif 'call_connect_times' in ap_a.columns:
                connects = int(round(float(ap_a['call_connect_times'].astype(float).sum())))
                conn_r = round(connects / calls * 100, 1) if calls > 0 else 0.0
            elif 'connect_times' in ap_a.columns:
                connects = int(round(float(ap_a['connect_times'].astype(float).sum())))
                conn_r = round(connects / calls * 100, 1) if calls > 0 else 0.0
            else:
                conn_r = 0.0

            if 'is_full_attendance' in ap_a.columns:
                full_att = int(ap_a['is_full_attendance'].max()) if pd.notna(ap_a['is_full_attendance']).any() else 0
                if 'work_hours' in ap_a.columns:
                    wh = float(ap_a['work_hours'].mean()) if pd.notna(ap_a['work_hours']).any() else 0.0
                    attd = 100 if full_att == 1 else min(100, round(wh / 8 * 100))
                else:
                    attd = 100 if full_att == 1 else 0
            elif 'headcount' in ap_a.columns:
                attd = 100 if float(ap_a['headcount'].fillna(0).max()) > 0 else 0
            else:
                attd = 0
        else:
            calls = 0; conn_r = 0.0; attd = 0

        # PTP from ptp_agent_data
        ptp_row = ptp_agent[(ptp_agent['grp_norm'].isin(grp_norm_candidates)) &
                            (ptp_agent['name_norm'] == a_norm) &
                            (ptp_agent['dt'] == TL_LATEST_DT)]
        ptp_valid = ptp_row['today_ptp_repay_rate'].dropna() if len(ptp_row) > 0 else pd.Series(dtype=float)
        ptp_val = round(float(ptp_valid.iloc[0]) * 100, 1) if len(ptp_valid) > 0 else None

        # Call loss rate from call_loss_agent_data
        cl_row = cl_agent[(cl_agent['grp_norm'].isin(grp_norm_candidates)) &
                          (cl_agent['name_norm'] == a_norm) &
                          (cl_agent['dt'] == TL_LATEST_DT)]
        cl_valid = cl_row['call_loss_rate'].dropna() if len(cl_row) > 0 else pd.Series(dtype=float)
        cl_val = round(float(cl_valid.iloc[0]) * 100, 1) if len(cl_valid) > 0 else None

        agent_key = str(agent_name)
        if group not in agent_perf_js:
            agent_perf_js[group] = []
        agent_perf_js[group].append({
            'name':            agent_key,
            'consecutiveDays': cd,
            'target':          ar_tgt,
            'actual':          ar_act,
            'achievement':     ar_ach,
            'calls':           calls,
            'connectRate':     conn_r,
            'coverTimes':      cover_times_val,
            'callTimes':       call_times_val,
            'artCallTimes':    art_call_times_val,
            # Raw process KPI standard (call_billmin)
            'callBillmin':     call_billmin_val,
            'singleCallDuration': single_call_duration_val,
            'ptp':             ptp_val,
            'callLossRate':    cl_val,
            'attendance':       attd
        })

        # Daily drill-down history (linked to TL date selector)
        ar_hist = agent_repay[(agent_repay['grp_norm'].isin(grp_norm_candidates)) &
                              (agent_repay['name_norm'] == a_norm)]
        hist_map = {}
        if len(ar_hist) > 0:
            ar_hist_daily = (ar_hist.groupby('dt', as_index=False)
                             .agg(target=('target_repay_principal', lambda x: x.astype(float).sum()),
                                  actual=('actual_repay_principal', lambda x: x.astype(float).sum())))
            for _, hr in ar_hist_daily.iterrows():
                dt_str = pd.to_datetime(hr['dt']).strftime('%Y-%m-%d')
                tgt = float(hr['target'])
                act = float(hr['actual'])
                hist_map[dt_str] = {
                    'target': round(tgt),
                    'actual': round(act),
                    'achievement': round(act / tgt * 100, 1) if tgt > 0 else 0.0
                }

        # Process metrics come from agent_performance by date
        ap_hist = agent_perf[(agent_perf['group_id'] == group) &
                             (agent_perf['agent_id'] == agent_name)]
        if len(ap_hist) > 0:
            agg_map = {}
            # Keep legacy "calls" for connect-rate fallback, but also populate both raw metrics.
            if 'art_call_times' in ap_hist.columns:
                agg_map['calls'] = ('art_call_times', lambda x: x.astype(float).sum())
                agg_map['artCallTimes'] = ('art_call_times', lambda x: x.astype(float).sum())
            if 'call_times' in ap_hist.columns:
                if 'calls' not in agg_map:
                    agg_map['calls'] = ('call_times', lambda x: x.astype(float).sum())
                agg_map['callTimes'] = ('call_times', lambda x: x.astype(float).sum())

            if 'cover_times' in ap_hist.columns:
                agg_map['coverTimes'] = ('cover_times', lambda x: x.astype(float).sum())

            if 'connect_rate' in ap_hist.columns:
                agg_map['connect_rate'] = ('connect_rate', 'mean')
            elif 'call_billhr' in ap_hist.columns:
                agg_map['call_billhr'] = ('call_billhr', 'mean')
            elif 'call_connect_times' in ap_hist.columns:
                agg_map['connects'] = ('call_connect_times', lambda x: x.astype(float).sum())
            elif 'connect_times' in ap_hist.columns:
                agg_map['connects'] = ('connect_times', lambda x: x.astype(float).sum())

            # Raw call duration standard for process KPI judgment (call_billmin)
            if 'call_billmin' in ap_hist.columns:
                agg_map['callBillmin'] = ('call_billmin', 'mean')
            elif 'connect_billmin' in ap_hist.columns:
                agg_map['callBillmin'] = ('connect_billmin', 'mean')

            if 'single_call_duration' in ap_hist.columns:
                agg_map['singleCallDuration'] = ('single_call_duration', 'mean')

            if 'work_hours' in ap_hist.columns:
                agg_map['work_hours'] = ('work_hours', 'mean')
            if 'is_full_attendance' in ap_hist.columns:
                agg_map['full_attendance'] = ('is_full_attendance', 'max')
            if 'headcount' in ap_hist.columns:
                agg_map['headcount'] = ('headcount', 'max')

            ap_hist_daily = ap_hist.groupby('dt', as_index=False).agg(**agg_map)
            for _, hr in ap_hist_daily.iterrows():
                dt_str = pd.to_datetime(hr['dt']).strftime('%Y-%m-%d')
                calls_d = int(round(float(hr['calls']))) if ('calls' in hr and pd.notna(hr['calls'])) else 0

                if 'connect_rate' in hr and pd.notna(hr['connect_rate']):
                    conn_r_d = round(float(hr['connect_rate']) * 100, 1)
                elif 'call_billhr' in hr and pd.notna(hr['call_billhr']):
                    conn_r_d = round(float(hr['call_billhr']) * 100, 1)
                else:
                    connects_d = int(round(float(hr['connects']))) if ('connects' in hr and pd.notna(hr['connects'])) else 0
                    conn_r_d = round(connects_d / calls_d * 100, 1) if calls_d > 0 else 0.0

                coverTimes_d = int(round(float(hr['coverTimes']))) if ('coverTimes' in hr and pd.notna(hr['coverTimes'])) else None
                callTimes_d = int(round(float(hr['callTimes']))) if ('callTimes' in hr and pd.notna(hr['callTimes'])) else None
                artCallTimes_d = int(round(float(hr['artCallTimes']))) if ('artCallTimes' in hr and pd.notna(hr['artCallTimes'])) else None
                callBillmin_d = round(float(hr['callBillmin']), 2) if ('callBillmin' in hr and pd.notna(hr['callBillmin'])) else None
                singleCallDuration_d = round(float(hr['singleCallDuration']), 2) if ('singleCallDuration' in hr and pd.notna(hr['singleCallDuration'])) else None

                if 'full_attendance' in hr and pd.notna(hr['full_attendance']):
                    full_att_d = int(hr['full_attendance'])
                    if 'work_hours' in hr and pd.notna(hr['work_hours']):
                        wh_d = float(hr['work_hours'])
                        attd_d = 100 if full_att_d == 1 else min(100, round(wh_d / 8 * 100))
                    else:
                        attd_d = 100 if full_att_d == 1 else 0
                elif 'headcount' in hr and pd.notna(hr['headcount']):
                    attd_d = 100 if float(hr['headcount']) > 0 else 0
                else:
                    attd_d = 0

                hist_map.setdefault(dt_str, {})
                hist_map[dt_str].update({
                    'calls': calls_d,
                    'connectRate': conn_r_d,
                    'coverTimes': coverTimes_d,
                    'callTimes': callTimes_d,
                    'artCallTimes': artCallTimes_d,
                    'callBillmin': callBillmin_d,
                    'singleCallDuration': singleCallDuration_d,
                    'attendance': attd_d
                })

        # Also align ptp/call-loss with selected date for drill-down display
        ptp_hist = ptp_agent[(ptp_agent['grp_norm'].isin(grp_norm_candidates)) &
                             (ptp_agent['name_norm'] == a_norm)]
        if len(ptp_hist) > 0:
            for dt, day_df in ptp_hist.groupby('dt'):
                dt_str = pd.to_datetime(dt).strftime('%Y-%m-%d')
                ptp_valid = day_df['today_ptp_repay_rate'].dropna()
                ptp_d = round(float(ptp_valid.iloc[0]) * 100, 1) if len(ptp_valid) > 0 else None
                hist_map.setdefault(dt_str, {})
                hist_map[dt_str]['ptp'] = ptp_d

        cl_hist = cl_agent[(cl_agent['grp_norm'].isin(grp_norm_candidates)) &
                           (cl_agent['name_norm'] == a_norm)]
        if len(cl_hist) > 0:
            for dt, day_df in cl_hist.groupby('dt'):
                dt_str = pd.to_datetime(dt).strftime('%Y-%m-%d')
                cl_valid = day_df['call_loss_rate'].dropna()
                cl_d = round(float(cl_valid.iloc[0]) * 100, 1) if len(cl_valid) > 0 else None
                hist_map.setdefault(dt_str, {})
                hist_map[dt_str]['callLossRate'] = cl_d

        agent_perf_by_date_js[group][agent_key] = hist_map

# ========================
# 3. GROUP PERFORMANCE (STL, weekly from new v3 sheets)
# ========================
print("Building groupPerformance...")

group_perf_js = {}
group_perf_by_week_js = {}
group_consecutive_by_week_js = {}
for mk in modules_list:
    mk_groups = submodule_groups.get(mk, [])
    group_perf_by_week_js[mk] = {}
    group_consecutive_by_week_js[mk] = {}

    groups_list = []
    for group in mk_groups:
        g_norm = norm(group)
        dtr_norm = norm(map_group_to_dtr(group))
        grp_norm_candidates = {g_norm, dtr_norm}

        # Weekly repay from daily_target_group_repay
        gr = group_repay[(group_repay['grp_norm'].isin(grp_norm_candidates)) &
                         (group_repay['week'] == DEFAULT_STL_WEEK)]
        if len(gr) > 0:
            w_tgt_sum = float(gr['target_repay_principal'].sum())
            w_act_sum = float(gr['actual_repay_principal'].sum())
            w_tgt = round(w_tgt_sum)
            w_act = round(w_act_sum)
            w_ach = round(w_act_sum / w_tgt_sum * 100, 1) if w_tgt_sum > 0 else 0.0
        else:
            w_tgt = w_act = 0; w_ach = 0.0

        # PTP from ptp_group_data
        ptp_g   = ptp_group[(ptp_group['grp_norm'].isin(grp_norm_candidates)) &
                            (ptp_group['week'] == DEFAULT_STL_WEEK)]
        ptp_g_valid = ptp_g['today_ptp_repay_rate'].dropna() if len(ptp_g) > 0 else pd.Series(dtype=float)
        ptp_rate = round(float(ptp_g_valid.iloc[0]) * 100, 1) if len(ptp_g_valid) > 0 else None

        # Call loss from call_loss_group_data
        cl_g    = cl_group[(cl_group['grp_norm'].isin(grp_norm_candidates)) &
                           (cl_group['week'] == DEFAULT_STL_WEEK)]
        cl_g_valid = cl_g['call_loss_rate'].dropna() if len(cl_g) > 0 else pd.Series(dtype=float)
        cl_rate = round(float(cl_g_valid.iloc[0]) * 100, 1) if len(cl_g_valid) > 0 else None

        # Call metrics from group_performance
        gp_lw = group_perf[(group_perf['group_id'] == group) &
                           (group_perf['week'] == DEFAULT_STL_WEEK)]
        cover_times_pa = None
        call_times_pa = None
        art_call_times_pa = None
        call_billmin_pa = None
        single_call_duration_pa = None
        if len(gp_lw) > 0:
            if 'art_call_times' in gp_lw.columns and pd.notna(gp_lw['art_call_times']).any():
                calls_pa = round(float(gp_lw['art_call_times'].iloc[0]))
                art_call_times_pa = int(round(float(gp_lw['art_call_times'].iloc[0])))
            elif 'call_times' in gp_lw.columns and pd.notna(gp_lw['call_times']).any():
                calls_pa = round(float(gp_lw['call_times'].iloc[0]))
                call_times_pa = int(round(float(gp_lw['call_times'].iloc[0])))
            else:
                tot_calls = float(gp_lw['total_calls'].iloc[0]) if 'total_calls' in gp_lw.columns else 0.0
                headcount = float(gp_lw['headcount'].iloc[0]) if 'headcount' in gp_lw.columns else 0.0
                calls_pa  = round(tot_calls / headcount) if headcount > 0 else 0

            if 'cover_times' in gp_lw.columns and pd.notna(gp_lw['cover_times']).any():
                cover_times_pa = int(round(float(gp_lw['cover_times'].iloc[0])))
            if 'call_times' in gp_lw.columns and pd.notna(gp_lw['call_times']).any():
                call_times_pa = int(round(float(gp_lw['call_times'].iloc[0])))
            if 'art_call_times' in gp_lw.columns and pd.notna(gp_lw['art_call_times']).any():
                art_call_times_pa = int(round(float(gp_lw['art_call_times'].iloc[0])))

            if 'call_billhr' in gp_lw.columns and pd.notna(gp_lw['call_billhr']).any():
                conn_r = round(float(gp_lw['call_billhr'].iloc[0]) * 100, 1)
            elif 'total_connect' in gp_lw.columns and 'total_calls' in gp_lw.columns:
                tot_calls = float(gp_lw['total_calls'].iloc[0])
                tot_conn = float(gp_lw['total_connect'].iloc[0])
                conn_r = round(tot_conn / tot_calls * 100, 1) if tot_calls > 0 else 0.0
            elif 'connect_rate' in gp_lw.columns:
                conn_r = round(float(gp_lw['connect_rate'].iloc[0]) * 100, 1)
            else:
                conn_r = 0.0

            # Raw call duration standards for process KPI judgment (call_billmin)
            if 'call_billmin' in gp_lw.columns and pd.notna(gp_lw['call_billmin']).any():
                call_billmin_pa = float(gp_lw['call_billmin'].iloc[0])
            elif 'connect_billmin' in gp_lw.columns and pd.notna(gp_lw['connect_billmin']).any():
                call_billmin_pa = float(gp_lw['connect_billmin'].iloc[0])
            if 'single_call_duration' in gp_lw.columns and pd.notna(gp_lw['single_call_duration']).any():
                single_call_duration_pa = float(gp_lw['single_call_duration'].iloc[0])

            gtl = tl_data[(tl_data['group_id'] == group) & (tl_data['dt'] == TL_LATEST_DT)]
            if len(gtl) > 0:
                owner = float(gtl['ownercount'].iloc[0])
                head  = float(gtl['headcount'].iloc[0])
                attd  = round(head / owner * 100) if owner > 0 else 0
            else:
                attd = 0
        else:
            calls_pa = conn_r = attd = 0

        # Weekly repay drill-down history (linked to STL week selector)
        gr_hist = group_repay[group_repay['grp_norm'].isin(grp_norm_candidates)]
        week_map = {}
        if len(gr_hist) > 0:
            gr_hist_weekly = (gr_hist.groupby('week', as_index=False)
                              .agg(target=('target_repay_principal', lambda x: x.astype(float).sum()),
                                   actual=('actual_repay_principal', lambda x: x.astype(float).sum())))
            for _, wr in gr_hist_weekly.iterrows():
                wk = str(wr['week'])
                tgt = float(wr['target'])
                act = float(wr['actual'])
                week_map[week_str_to_display(wk)] = {
                    'target': round(tgt),
                    'actual': round(act),
                    'achievement': round(act / tgt * 100, 1) if tgt > 0 else 0.0
                }

        # Weekly process metrics history from group_performance (for STL selected week)
        gp_hist = group_perf[group_perf['group_id'] == group]
        if len(gp_hist) > 0:
            gp_hist_weekly = gp_hist.groupby('week', as_index=False).first()
            for _, gwr in gp_hist_weekly.iterrows():
                wk = str(gwr['week'])
                wk_label = week_str_to_display(wk)
                coverTimes_w = int(round(float(gwr.get('cover_times')))) if 'cover_times' in gp_hist_weekly.columns and pd.notna(gwr.get('cover_times')) else None
                callTimes_w = int(round(float(gwr.get('call_times')))) if 'call_times' in gp_hist_weekly.columns and pd.notna(gwr.get('call_times')) else None
                artCallTimes_w = int(round(float(gwr.get('art_call_times')))) if 'art_call_times' in gp_hist_weekly.columns and pd.notna(gwr.get('art_call_times')) else None
                callBillmin_w = float(gwr.get('call_billmin')) if 'call_billmin' in gp_hist_weekly.columns and pd.notna(gwr.get('call_billmin')) else (
                    float(gwr.get('connect_billmin')) if 'connect_billmin' in gp_hist_weekly.columns and pd.notna(gwr.get('connect_billmin')) else None
                )
                singleCallDuration_w = float(gwr.get('single_call_duration')) if 'single_call_duration' in gp_hist_weekly.columns and pd.notna(gwr.get('single_call_duration')) else None

                if 'art_call_times' in gp_hist_weekly.columns and pd.notna(gwr.get('art_call_times')):
                    calls_w = round(float(gwr.get('art_call_times')))
                else:
                    tot_calls_w = float(gwr.get('total_calls', 0.0))
                    headcount_w = float(gwr.get('headcount', 0.0))
                    calls_w = round(tot_calls_w / headcount_w) if headcount_w > 0 else 0

                if 'call_billhr' in gp_hist_weekly.columns and pd.notna(gwr.get('call_billhr')):
                    conn_w = round(float(gwr.get('call_billhr')) * 100, 1)
                elif 'connect_rate' in gp_hist_weekly.columns and pd.notna(gwr.get('connect_rate')):
                    conn_w = round(float(gwr.get('connect_rate')) * 100, 1)
                elif pd.notna(gwr.get('total_connect')) and pd.notna(gwr.get('total_calls')) and float(gwr.get('total_calls', 0.0)) > 0:
                    conn_w = round(float(gwr.get('total_connect')) / float(gwr.get('total_calls')) * 100, 1)
                else:
                    conn_w = 0.0

                week_map.setdefault(wk_label, {})
                week_map[wk_label]['calls'] = calls_w
                week_map[wk_label]['connectRate'] = conn_w
                week_map[wk_label]['coverTimes'] = coverTimes_w
                week_map[wk_label]['callTimes'] = callTimes_w
                week_map[wk_label]['artCallTimes'] = artCallTimes_w if artCallTimes_w is not None else calls_w
                week_map[wk_label]['callBillmin'] = callBillmin_w
                week_map[wk_label]['singleCallDuration'] = singleCallDuration_w

        cl_hist_week = cl_group[cl_group['grp_norm'].isin(grp_norm_candidates)]
        if len(cl_hist_week) > 0:
            for _, cr in cl_hist_week.iterrows():
                wk_label = week_str_to_display(str(cr['week']))
                clv = pd.to_numeric(cr['call_loss_rate'], errors='coerce')
                week_map.setdefault(wk_label, {})
                week_map[wk_label]['callLossRate'] = round(float(clv) * 100, 1) if pd.notna(clv) else None
        consecutive_map = build_consecutive_weeks_map(week_map)
        cw_default = int(consecutive_map.get(week_str_to_display(DEFAULT_STL_WEEK), 0))

        groups_list.append({
            'name':             group,
            'consecutiveWeeks': cw_default,
            'target':           w_tgt,
            'actual':           w_act,
            'achievement':      w_ach,
            'calls':            calls_pa,
            'connectRate':      conn_r,
            'coverTimes':       cover_times_pa,
            'callTimes':        call_times_pa,
            'artCallTimes':     art_call_times_pa if art_call_times_pa is not None else calls_pa,
            'callBillmin':      call_billmin_pa,
            'singleCallDuration': single_call_duration_pa,
            'ptpRate':          ptp_rate,
            'callLossRate':     cl_rate,
            'attendance':       attd
        })
        group_perf_by_week_js[mk][group] = week_map
        group_consecutive_by_week_js[mk][group] = consecutive_map
    group_perf_js[mk] = groups_list

# ========================
# 4. STL DATA  (module-level weekly, from group_repay aggregated by sub-module)
# ========================
print("Building stlData...")
stl_data_js = {}
for mk in modules_list:
    dtr_groups   = submodule_dtr_groups.get(mk, set())
    mk_grp_repay = group_repay[group_repay['owner_group'].isin(dtr_groups)]

    mk_weeks = sorted(mk_grp_repay['week'].unique(), key=week_start_dt)

    weekly = (mk_grp_repay.groupby('week')
              .agg(target=('target_repay_principal', lambda x: x.astype(float).sum()),
                   actual=('actual_repay_principal', lambda x: x.astype(float).sum()))
              .reset_index().sort_values('week'))
    weekly['achievement'] = weekly.apply(
        lambda r: round(r['actual'] / r['target'] * 100, 1) if r['target'] > 0 else 0.0, axis=1)

    weeks_list = []
    for _, w in weekly.iterrows():
        weeks_list.append({
            'weekLabel':   week_str_to_display(str(w['week'])),
            'target':      round(float(w['target'])),
            'actual':      round(float(w['actual'])),
            'achievement': float(w['achievement'])
        })

    if weeks_list:
        lw          = weeks_list[-1]
        prev_actual = weeks_list[-2]['actual'] if len(weeks_list) > 1 else 0
        tpct        = (lw['actual'] - prev_actual) / prev_actual * 100 if prev_actual > 0 else 0.0
        trend_str   = ('+' if tpct >= 0 else '') + f'{tpct:.1f}%'
        latest_gap  = max(0, lw['target'] - lw['actual'])
    else:
        lw = {'target': 0, 'actual': 0, 'achievement': 0.0}
        trend_str = 'N/A'; latest_gap = 0

    stl_data_js[mk] = {
        'target':      lw['target'],
        'actual':      lw['actual'],
        'achievement': lw['achievement'],
        'lastWeek':    weeks_list[-2]['actual'] if len(weeks_list) > 1 else 0,
        'trend':       trend_str,
        'gap':         round(latest_gap),
        'weeks':       weeks_list,
        'allWeeks':    [week_str_to_display(w) for w in mk_weeks]
    }

# ========================
# ========================
# 5. ANOMALY GROUPS  (aggregate agent -> group level first)
# ========================
print("Building anomalyGroups...")

def trailing_streak_df(df):
    streak = 0
    for _, row in df.sort_values('dt', ascending=False).iterrows():
        ach = float(row['achieve_rate']) if pd.notna(row['achieve_rate']) else 0.0
        if ach < 1.0:
            streak += 1
        else:
            break
    return streak

default_week_label = week_str_to_display(DEFAULT_STL_WEEK)
anomaly_groups = []
for mk in modules_list:
    for group in submodule_groups.get(mk, []):
        cw_map = group_consecutive_by_week_js.get(mk, {}).get(group, {})
        streak = int(cw_map.get(default_week_label, 0))
        if streak < 2:
            continue
        wk_map = group_perf_by_week_js.get(mk, {}).get(group, {})
        wk = wk_map.get(default_week_label, {})
        w_tgt = round(float(wk.get('target', 0) or 0))
        w_act = round(float(wk.get('actual', 0) or 0))
        anomaly_groups.append({
            'name': group,
            'module': mk,
            'weeks': streak,
            'weeklyTarget': w_tgt,
            'weeklyActual': w_act
        })
anomaly_groups.sort(key=lambda x: -x['weeks'])

# ========================
# 5b. ANOMALY AGENTS (continuous unmet days, 3+)
# ========================
anomaly_agents = []
for group, agents in agent_perf_js.items():
    module = tl_data_js.get(group, {}).get('groupModule', '')
    for a in agents:
        streak = int(a.get('consecutiveDays', 0) or 0)
        if streak < 3:
            continue
        anomaly_agents.append({
            'name': a.get('name', ''),
            'group': group,
            'module': module,
            'days': streak,
            'dailyTarget': round(float(a.get('target', 0) or 0)),
            'dailyActual': round(float(a.get('actual', 0) or 0)),
            'calls': int(a.get('artCallTimes', a.get('calls', 0)) or 0),
            'connectRate': float(a.get('connectRate', 0.0) or 0.0),
            'callLossRate': a.get('callLossRate'),
            'attendance': int(a.get('attendance', 0) or 0)
        })
anomaly_agents.sort(key=lambda x: -x['days'])

# ========================
# ========================
# 6. MODULE DAILY TRENDS
# ========================
print("Building moduleDailyTrends...")
module_daily_js = {}
for mk in modules_list:
    mk_nm_daily = module_nm_dict.get(mk, {})
    module_bucket    = module_key_to_bucket(mk)
    module_target_nm = target_nm_dict.get(module_bucket, {})

    daily_series = []
    for day in range(1, DAYS_IN_MONTH + 1):
        date_str = f'{REPORT_YEAR}-{REPORT_MONTH:02d}-{day:02d}'
        in_cutoff = day <= TL_LATEST_DAY
        nm_rr  = mk_nm_daily.get(day, None) if in_cutoff else None
        # Module target line should remain available for the whole selected month.
        nm_trr = module_target_nm.get(day, None)
        daily_series.append({
            'date': date_str, 'target': None, 'actual': None,
            'repayRate': nm_rr, 'targetRepayRate': nm_trr
        })
    module_daily_js[mk] = {'daily': daily_series}

# ========================
# ========================
# 7. MODULE MONTHLY  (from group_repay weekly data)
# ========================
print("Building moduleMonthly...")
module_monthly_js = {}
for mk in modules_list:
    dtr_groups = submodule_dtr_groups.get(mk, set())
    m_grp = group_repay[group_repay['owner_group'].isin(dtr_groups)]
    if len(m_grp) > 0:
        total_tgt = m_grp['target_repay_principal'].astype(float).sum()
        total_act = m_grp['actual_repay_principal'].astype(float).sum()
        month_target   = round(total_tgt)
        current_actual = round(total_act)
    else:
        month_target   = 0
        current_actual = 0
    module_monthly_js[mk] = {
        'monthTarget': month_target, 'monthDays': DAYS_IN_MONTH,
        'currentDay': TL_LATEST_DAY, 'currentActual': current_actual
    }
# 8. RISK MODULE GROUPS
# ========================
risk_module_groups = {}
for mk in modules_list:
    risk_module_groups[mk] = [
        {
            'group': g['name'], 'target': g['target'], 'actual': g['actual'],
            'achievement': g['achievement'], 'calls': g['calls'],
            'connectRate': g['connectRate'], 'ptpRate': g['ptpRate'],
            'callLossRate': g.get('callLossRate'), 'attendance': g['attendance']
        }
        for g in group_perf_js.get(mk, [])
    ]

# ========================
# Assemble REAL_DATA
# ========================
real_data = {
    'dataDate':          TL_LATEST_STR,
    'dataDay':           TL_LATEST_DAY,
    'availableDates':    available_dates,
    'availableWeeks':    [week_str_to_display(w) for w in all_weeks_sorted],
    'defaultStlWeek':    week_str_to_display(DEFAULT_STL_WEEK),
    'modules':           modules_list,
    'groups':            all_groups,
    'tlData':            tl_data_js,
    'stlData':           stl_data_js,
    'agentPerformance':  agent_perf_js,
    'agentPerformanceByDate': agent_perf_by_date_js,
    'groupPerformance':  group_perf_js,
    'groupPerformanceByWeek': group_perf_by_week_js,
    'groupConsecutiveWeeksByWeek': group_consecutive_by_week_js,
    'anomalyGroups':     anomaly_groups,
    'anomalyAgents':     anomaly_agents,
    'processTargets':    process_target_js,
    'riskModuleGroups':  risk_module_groups,
    'moduleDailyTrends': module_daily_js,
    'moduleMonthly':     module_monthly_js
}

class SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, float) and math.isnan(obj):
            return 0
        return super().default(obj)

real_data_json = json.dumps(real_data, cls=SafeEncoder, ensure_ascii=False, separators=(',', ':'))
print(f"  JSON size  : {len(real_data_json)//1024} KB")

# ========================
# Read HTML template
# ========================
print("Patching HTML...")
with open(HTML_IN, 'r', encoding='utf-8') as f:
    html = f.read()

# ---- 1. Replace MOCK_DATA block ----
mock_marker = '        const MOCK_DATA = {'
role_marker = '        // ===================== ROLE SWITCHING ====================='
mock_start  = html.index(mock_marker)
mock_end    = html.index(role_marker)
html = (html[:mock_start]
        + f'        const REAL_DATA = {real_data_json};\n\n        '
        + html[mock_end:])

# ---- 2. MOCK_DATA. -> REAL_DATA. ----
html = html.replace('MOCK_DATA.', 'REAL_DATA.')

# ---- 3. renderTLChart: module extraction + group filter ----
html = html.replace(
    "const module = group.replace(/^G-/, '').replace(/-\\d+$/, '');",
    "const module = REAL_DATA.tlData[group] ? REAL_DATA.tlData[group].groupModule : group.split('-')[0];"
)
html = html.replace(
    "const allGroupsInModule = REAL_DATA.groups.filter(g => g.includes('-' + module + '-'));",
    "const allGroupsInModule = REAL_DATA.groups.filter(g => REAL_DATA.tlData[g] && REAL_DATA.tlData[g].groupModule === module);"
)

# ---- 4. renderSTLChart: group filter ----
html = html.replace(
    "const groupsInModule = REAL_DATA.groups.filter(g => g.includes('-' + module + '-'));",
    "const groupsInModule = REAL_DATA.groups.filter(g => REAL_DATA.tlData[g] && REAL_DATA.tlData[g].groupModule === module);"
)

# ---- 5. renderTLChart: actuals -> repayRate ----
html = html.replace(
    "                const actuals = filteredDays.map(d => Math.round(d.actual));",
    "                const actuals = filteredDays.map(d => d.nmRepayRate !== null && d.nmRepayRate !== undefined ? d.nmRepayRate : (d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null));"
)

# ---- 5b. TL Recovery Trend: X-axis full month; target continues; actual null for future ----
old_tl_month_block = """\
            // Filter to only show selected date's month
            const selectedMonth = selectedDate ? selectedDate.slice(0, 7) : ''; // YYYY-MM

            const dates = [];
            const series = [];
            const legendData = ['Module Target'];

            // Get date labels and module target from first group's data, filtered by month
            let monthData = [];
            let moduleTargetValues = [];
            if (REAL_DATA.tlData[allGroupsInModule[0]] && REAL_DATA.tlData[allGroupsInModule[0]].days) {
                monthData = REAL_DATA.tlData[allGroupsInModule[0]].days.filter(d => d.date.startsWith(selectedMonth));
                monthData.forEach(d => dates.push(d.date.slice(5))); // MM-DD format
                // Get module target from first day of filtered data
                if (monthData.length > 0) {
                    moduleTargetValues = monthData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);
                }
            }
"""
new_tl_month_block = """\
            // Selected month (YYYY-MM). X-axis shows full month; actual may be null for future days.
            const selectedMonth = selectedDate ? selectedDate.slice(0, 7) : REAL_DATA.dataDate.slice(0, 7); // YYYY-MM
            const cutoffDate = REAL_DATA.dataDate;

            const dates = [];
            const series = [];
            const legendData = ['Module Target'];

            // Build full month labels: MM-DD
            const ymParts = selectedMonth.split('-');
            const year = parseInt(ymParts[0], 10);
            const month = parseInt(ymParts[1], 10); // 1-12
            const daysInMonth = new Date(year, month, 0).getDate();
            for (let d = 1; d <= daysInMonth; d++) {
                const mm = String(month).padStart(2, '0');
                const dd = String(d).padStart(2, '0');
                dates.push(mm + '-' + dd);
            }

            // Module target should be available for the full month (even if actual stops at dataDate)
            let moduleTargetValues = [];
            const trendData = (REAL_DATA.moduleDailyTrends && REAL_DATA.moduleDailyTrends[module]) ? REAL_DATA.moduleDailyTrends[module] : null;
            const targetRows = (trendData && trendData.daily) ? trendData.daily.filter(d => d.date.startsWith(selectedMonth)) : [];
            const targetByLabel = {};
            targetRows.forEach(r => {
                targetByLabel[r.date.slice(5)] = (r.targetRepayRate !== null && r.targetRepayRate !== undefined) ? r.targetRepayRate : null;
            });
            moduleTargetValues = dates.map(lbl => (Object.prototype.hasOwnProperty.call(targetByLabel, lbl) ? targetByLabel[lbl] : null));
"""
html = html.replace(old_tl_month_block, new_tl_month_block)

old_tl_group_days = """\
                // Filter data by selected month
                const filteredDays = groupData.days.filter(d => d.date.startsWith(selectedMonth));
                if (filteredDays.length === 0) return;

                const isSelected = g === group;
                const actuals = filteredDays.map(d => d.nmRepayRate !== null && d.nmRepayRate !== undefined ? d.nmRepayRate : (d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null));
"""
new_tl_group_days = """\
                // Filter actuals to selected month up to dataDate cutoff; fill future days with nulls
                const filteredDays = groupData.days.filter(d => d.date.startsWith(selectedMonth) && d.date <= cutoffDate);
                if (filteredDays.length === 0) return;

                const isSelected = g === group;
                const actualByLabel = {};
                filteredDays.forEach(d => {
                    const v = (d.nmRepayRate !== null && d.nmRepayRate !== undefined) ? d.nmRepayRate : ((d.repayRate !== null && d.repayRate !== undefined) ? d.repayRate : null);
                    actualByLabel[d.date.slice(5)] = v;
                });
                const actuals = dates.map(lbl => (Object.prototype.hasOwnProperty.call(actualByLabel, lbl) ? actualByLabel[lbl] : null));
"""
html = html.replace(old_tl_group_days, new_tl_group_days)

# ---- 6. renderTLChart: moduleTarget -> targetRepayRate ----
html = html.replace(
    "            const legendData = ['Module Target'];",
    "            const legendData = ['Module Target'];"
)
html = html.replace(
    "            let moduleTarget = 0;",
    "            let moduleTargetValues = [];"
)
html = html.replace(
    "                    moduleTarget = monthData[0].target;",
    "                    moduleTargetValues = monthData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);"
)
html = html.replace(
    "                    moduleTarget = (monthData[0].targetRepayRate !== null && monthData[0].targetRepayRate !== undefined) ? monthData[0].targetRepayRate : 0;",
    "                    moduleTargetValues = monthData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);"
)

# ---- 7. renderTLChart: target line fill (rate, no rounding) ----
html = html.replace(
    "                data: Array(dates.length).fill(Math.round(moduleTarget));",
    "                data: moduleTargetValues,"
)
html = html.replace(
    "                data: Array(dates.length).fill(moduleTarget);",
    "                data: moduleTargetValues,"
)
html = html.replace(
    "                data: Array(dates.length).fill(Math.round(moduleTarget)),",
    "                data: moduleTargetValues,"
)
html = html.replace(
    "            // Add SINGLE module-level target line (dashed green)\n            series.push({\n                name: 'Module Target',",
    "            // Add SINGLE module-level target line (dashed green)\n            series.push({\n                name: 'Module Target',"
)

# ---- 8. Shared tooltip: amount -> rate % (TL + STL charts) ----
old_shared_tooltip = """\
                tooltip: { trigger: 'axis', formatter: params => {
                    const date = params[0].name;
                    let html = date + '<br>';
                    // Show target first
                    const targetParam = params.find(p => p.seriesName === 'Module Target');
                    if (targetParam) {
                        html += targetParam.marker + ' Module Target: ' + formatNumber(targetParam.value) + '<br>';
                    }
                    // Then show groups
                    params.forEach(p => {
                        if (p.seriesName === 'Module Target') return;
                        html += p.marker + ' ' + p.seriesName + ': ' + formatNumber(p.value) + '<br>';
                    });
                    return html;
                }},"""
new_shared_tooltip = """\
                tooltip: { trigger: 'axis', formatter: params => {
                    const date = params[0].name;
                    let html = date + '<br>';
                    const sortedParams = params.slice().sort((a, b) => {
                        const av = (a.value !== null && a.value !== undefined) ? a.value : -999999;
                        const bv = (b.value !== null && b.value !== undefined) ? b.value : -999999;
                        return bv - av; // desc
                    });
                    sortedParams.forEach(p => {
                        html += p.marker + ' ' + p.seriesName + ': ' + (p.value !== null && p.value !== undefined ? p.value.toFixed(2) + '%' : '-') + '<br>';
                    });
                    return html;
                }},"""
html = html.replace(old_shared_tooltip, new_shared_tooltip)

# ---- 9. TL+STL Y-axis -> % ----
html = html.replace(
    "                yAxis: { type: 'value', axisLabel: { formatter: v => formatNumber(v) } },",
    "                yAxis: { type: 'value', axisLabel: { formatter: v => v !== null && v !== undefined ? v.toFixed(2) + '%' : '' } },"
)

# ---- 10. renderSTLChart: target values -> targetRepayRate ----
html = html.replace(
    "            const targetValues = dailyData.map(d => d.target);",
    "            const targetValues = dailyData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);"
)
html = html.replace(
    "            const monthStr = weekLabel.split('/')[0]; // Get month from \"MM/DD - MM/DD\"",
    "            const weekParts = weekLabel.split(' - ');\n            const endPart = weekParts.length > 1 ? weekParts[1] : weekParts[0];\n            const monthStr = endPart.split('/')[0]; // Use week-end month for cross-month week labels"
)
html = html.replace(
    "            // Generate daily data for the selected month (like TL does for daily trend)\n            // Generate dates for the month of selected week\n            const today = new Date();\n            const currentYear = today.getFullYear();\n            const month = parseInt(monthStr) - 1; // 0-indexed\n            const daysInMonth = new Date(currentYear, month + 1, 0).getDate();\n\n            const dates = [];",
    "            // Use selected month data up to dataDate cutoff\n            const cutoffDate = REAL_DATA.dataDate;\n            const dates = [];"
)

# ---- 10b. STL Recovery Trend: X-axis full month; target continues; actual null for future ----
old_stl_dates_block = """\
            // Use selected month data up to dataDate cutoff
            const cutoffDate = REAL_DATA.dataDate;
            const dates = [];

            // Get module from selector
            const module = document.getElementById('stl-module-select').value;

            // Get daily data from moduleDailyTrends (contains natural month repay target)
            const trendData = REAL_DATA.moduleDailyTrends[module];
            const selectedYearMonth = REAL_DATA.dataDate.slice(0, 4) + '-' + monthStr.padStart(2, '0');
            const dailyData = trendData ? trendData.daily.filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate) : [];
            dailyData.forEach(d => dates.push(d.date.slice(5)));
"""
new_stl_dates_block = """\
            // X-axis shows full month; actual may be null for future days.
            const cutoffDate = REAL_DATA.dataDate;
            const dates = [];

            // Get module from selector
            const module = document.getElementById('stl-module-select').value;

            // Build full month labels: MM-DD for selected month
            const selectedYearMonth = REAL_DATA.dataDate.slice(0, 4) + '-' + monthStr.padStart(2, '0');
            const ymParts = selectedYearMonth.split('-');
            const year = parseInt(ymParts[0], 10);
            const month = parseInt(ymParts[1], 10); // 1-12
            const daysInMonth = new Date(year, month, 0).getDate();
            for (let d = 1; d <= daysInMonth; d++) {
                const mm = String(month).padStart(2, '0');
                const dd = String(d).padStart(2, '0');
                dates.push(mm + '-' + dd);
            }

            // Get daily data from moduleDailyTrends (contains natural month repay target)
            const trendData = REAL_DATA.moduleDailyTrends[module];
            const dailyAll = trendData ? trendData.daily.filter(d => d.date.startsWith(selectedYearMonth)) : [];
            const dailyActual = dailyAll.filter(d => d.date <= cutoffDate);

            const targetByLabel = {};
            dailyAll.forEach(r => {
                targetByLabel[r.date.slice(5)] = (r.targetRepayRate !== null && r.targetRepayRate !== undefined) ? r.targetRepayRate : null;
            });

            const moduleActualByLabel = {};
            dailyActual.forEach(r => {
                moduleActualByLabel[r.date.slice(5)] = (r.repayRate !== null && r.repayRate !== undefined) ? r.repayRate : null;
            });
"""
html = html.replace(old_stl_dates_block, new_stl_dates_block)

# Target line: from full-month targetByLabel (not truncated by dataDate)
html = html.replace(
    "            const targetValues = dailyData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);",
    "            const targetValues = dates.map(lbl => (Object.prototype.hasOwnProperty.call(targetByLabel, lbl) ? targetByLabel[lbl] : null));"
)

# Module total: actual only up to dataDate, rest null
html = html.replace(
    "            const moduleActuals = dailyData.map(d => d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null);",
    "            const moduleActuals = dates.map(lbl => (Object.prototype.hasOwnProperty.call(moduleActualByLabel, lbl) ? moduleActualByLabel[lbl] : null));"
)

# Per-group series: align to full-month dates
old_stl_group_series = """\
                const repayRates = gData.days
                    .filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate)
                    .map(d => d.nmRepayRate !== null && d.nmRepayRate !== undefined ? d.nmRepayRate : (d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null));
"""
new_stl_group_series = """\
                const filteredDays = gData.days
                    .filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate);
                const repayByLabel = {};
                filteredDays.forEach(d => {
                    const v = (d.nmRepayRate !== null && d.nmRepayRate !== undefined) ? d.nmRepayRate : ((d.repayRate !== null && d.repayRate !== undefined) ? d.repayRate : null);
                    repayByLabel[d.date.slice(5)] = v;
                });
                const repayRates = dates.map(lbl => (Object.prototype.hasOwnProperty.call(repayByLabel, lbl) ? repayByLabel[lbl] : null));
"""
html = html.replace(old_stl_group_series, new_stl_group_series)

# ---- 10c. TL+STL recovery trend finalization (robust patching) ----
# TL: ensure full-month x-axis + cutoffDate defined + target continues beyond actuals
html = html.replace(
    "            const selectedMonth = selectedDate ? selectedDate.slice(0, 7) : ''; // YYYY-MM",
    "            const selectedMonth = selectedDate ? selectedDate.slice(0, 7) : REAL_DATA.dataDate.slice(0, 7); // YYYY-MM\n            const cutoffDate = REAL_DATA.dataDate;"
)
html = html.replace(
    "                monthData.forEach(d => dates.push(d.date.slice(5))); // MM-DD format",
    "                const ymParts = selectedMonth.split('-');\n                const year = parseInt(ymParts[0], 10);\n                const month = parseInt(ymParts[1], 10); // 1-12\n                const daysInMonth = new Date(year, month, 0).getDate();\n                for (let d = 1; d <= daysInMonth; d++) {\n                    const mm = String(month).padStart(2, '0');\n                    const dd = String(d).padStart(2, '0');\n                    dates.push(mm + '-' + dd);\n                }"
)
html = html.replace(
    "                    moduleTargetValues = monthData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);",
    "                    const trendData = (REAL_DATA.moduleDailyTrends && REAL_DATA.moduleDailyTrends[module]) ? REAL_DATA.moduleDailyTrends[module] : null;\n                    const targetRows = (trendData && trendData.daily) ? trendData.daily.filter(d => d.date.startsWith(selectedMonth)) : [];\n                    const targetByLabel = {};\n                    targetRows.forEach(r => { targetByLabel[r.date.slice(5)] = (r.targetRepayRate !== null && r.targetRepayRate !== undefined) ? r.targetRepayRate : null; });\n                    moduleTargetValues = dates.map(lbl => (Object.prototype.hasOwnProperty.call(targetByLabel, lbl) ? targetByLabel[lbl] : null));"
)

# STL: replace month-date block to full-month dates + build target/actual maps
old_stl_month_block = """\
            // Use selected month data up to dataDate cutoff
            const cutoffDate = REAL_DATA.dataDate;
            const dates = [];

            // Get module from selector
            const module = document.getElementById('stl-module-select').value;

            // Get daily data from moduleDailyTrends (contains natural month repay target)
            const trendData = REAL_DATA.moduleDailyTrends[module];
            const selectedYearMonth = REAL_DATA.dataDate.slice(0, 4) + '-' + monthStr.padStart(2, '0');
            const dailyData = trendData ? trendData.daily.filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate) : [];
            dailyData.forEach(d => dates.push(d.date.slice(5)));
"""
new_stl_month_block = """\
            // X-axis shows full month; actual may be null for future days.
            const cutoffDate = REAL_DATA.dataDate;
            const dates = [];

            // Get module from selector
            const module = document.getElementById('stl-module-select').value;

            const selectedYearMonth = REAL_DATA.dataDate.slice(0, 4) + '-' + monthStr.padStart(2, '0');
            const ymParts = selectedYearMonth.split('-');
            const year = parseInt(ymParts[0], 10);
            const month = parseInt(ymParts[1], 10); // 1-12
            const daysInMonth = new Date(year, month, 0).getDate();
            for (let d = 1; d <= daysInMonth; d++) {
                const mm = String(month).padStart(2, '0');
                const dd = String(d).padStart(2, '0');
                dates.push(mm + '-' + dd);
            }

            // Get daily data from moduleDailyTrends (contains natural month repay target)
            const trendData = REAL_DATA.moduleDailyTrends[module];
            const dailyAll = trendData ? trendData.daily.filter(d => d.date.startsWith(selectedYearMonth)) : [];
            const dailyData = dailyAll.filter(d => d.date <= cutoffDate);

            const targetByLabel = {};
            dailyAll.forEach(r => { targetByLabel[r.date.slice(5)] = (r.targetRepayRate !== null && r.targetRepayRate !== undefined) ? r.targetRepayRate : null; });

            const moduleActualByLabel = {};
            dailyData.forEach(r => { moduleActualByLabel[r.date.slice(5)] = (r.repayRate !== null && r.repayRate !== undefined) ? r.repayRate : null; });
"""
html = html.replace(old_stl_month_block, new_stl_month_block)

# STL target + module total + per-group aligned to full-month dates
html = html.replace(
    "            const targetValues = dailyData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null);",
    "            const targetValues = dates.map(lbl => (Object.prototype.hasOwnProperty.call(targetByLabel, lbl) ? targetByLabel[lbl] : null));"
)
html = html.replace(
    "            const moduleActuals = dailyData.map(d => d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null);",
    "            const moduleActuals = dates.map(lbl => (Object.prototype.hasOwnProperty.call(moduleActualByLabel, lbl) ? moduleActualByLabel[lbl] : null));"
)
html = html.replace(
    "                const repayRates = gData.days\n                    .filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate)\n                    .map(d => d.nmRepayRate !== null && d.nmRepayRate !== undefined ? d.nmRepayRate : (d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null));",
    "                const filteredDays = gData.days\n                    .filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate);\n                const repayByLabel = {};\n                filteredDays.forEach(d => {\n                    const v = (d.nmRepayRate !== null && d.nmRepayRate !== undefined) ? d.nmRepayRate : ((d.repayRate !== null && d.repayRate !== undefined) ? d.repayRate : null);\n                    repayByLabel[d.date.slice(5)] = v;\n                });\n                const repayRates = dates.map(lbl => (Object.prototype.hasOwnProperty.call(repayByLabel, lbl) ? repayByLabel[lbl] : null));"
)
# NOTE: STL recovery trend month-axis is handled by the full-month patch above (10c).

# ---- 11. renderSTLChart: per-group data -> real repayRate from tlData ----
old_stl_simulated = """\
            // Add each group's daily trend for the month (line chart, like TL)
            groupsInModule.forEach((g, idx) => {
                // Generate simulated daily data for this group
                const groupDailyData = dailyData.map(d => ({
                    date: d.date,
                    actual: Math.floor(d.actual * (0.3 + Math.random() * 0.4)) // Distribute module total to groups
                }));

                const color = idx % 2 === 0 ? '#1e3a5f' : '#3b82f6';
                const actuals = groupDailyData.map(d => Math.round(d.actual));

                series.push({
                    name: g,
                    type: 'line',
                    data: actuals,
                    smooth: true,
                    lineStyle: { color: color, width: 1.5, opacity: 0.6 },
                    itemStyle: { color: color },
                    symbol: 'none',
                    z: idx + 1
                });
                legendData.unshift(g);
            });"""
new_stl_real = """\
            // Add each group's daily repay rate from natural_month_repay
            groupsInModule.forEach((g, idx) => {
                const gData = REAL_DATA.tlData[g];
                if (!gData || !gData.days) return;
                const color = idx % 2 === 0 ? '#1e3a5f' : '#3b82f6';
                const repayRates = gData.days
                    .filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate)
                    .map(d => d.nmRepayRate !== null && d.nmRepayRate !== undefined ? d.nmRepayRate : (d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null));

                series.push({
                    name: g,
                    type: 'line',
                    data: repayRates,
                    smooth: true,
                    lineStyle: { color: color, width: 1.5, opacity: 0.6 },
                    itemStyle: { color: color },
                    symbol: 'none',
                    z: idx + 1
                });
                legendData.unshift(g);
            });"""
html = html.replace(old_stl_simulated, new_stl_real)

# ---- 12. renderSTLChart: module total -> repayRate ----
html = html.replace(
    "            const moduleActuals = dailyData.map(d => Math.round(d.actual));",
    "            const moduleActuals = dailyData.map(d => d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null);"
)

# ---- 13. loadTrendChart: actual/target -> rate + null-safe avg ----
old_trend_vals = """\
                    if (d < dailyData.length) {
                        actualValues.push(dailyData[d].actual);
                        targetValues.push(dailyData[d].target);
                        avgDailyTarget += dailyData[d].target;
                        targetCount++;
                    } else {"""
new_trend_vals = """\
                    if (d < dailyData.length) {
                        actualValues.push(dailyData[d].repayRate !== null && dailyData[d].repayRate !== undefined ? dailyData[d].repayRate : null);
                        targetValues.push(dailyData[d].targetRepayRate !== null && dailyData[d].targetRepayRate !== undefined ? dailyData[d].targetRepayRate : null);
                        if (dailyData[d].targetRepayRate !== null && dailyData[d].targetRepayRate !== undefined) {
                            avgDailyTarget += dailyData[d].targetRepayRate;
                            targetCount++;
                        }
                    } else {"""
html = html.replace(old_trend_vals, new_trend_vals)

# ---- 14. loadTrendChart: tooltip -> % ----
html = html.replace(
    "                    tooltip: { trigger: 'axis', formatter: params => {\n                        return params[0].name + '<br>' + params.map(p => p.marker + p.seriesName + ': ' + (p.value ? formatNumber(p.value) : '-')).join('<br>');\n                    }},",
    "                    tooltip: { trigger: 'axis', formatter: params => {\n                        return params[0].name + '<br>' + params.map(p => p.marker + p.seriesName + ': ' + (p.value !== null && p.value !== undefined ? p.value.toFixed(2) + '%' : '-')).join('<br>');\n                    }},"
)

# ---- 15. loadTrendChart: Y-axis -> % ----
html = html.replace(
    "                    yAxis: { type: 'value', axisLabel: { formatter: v => formatNumber(v), fontSize: 10 } },",
    "                    yAxis: { type: 'value', axisLabel: { formatter: v => v !== null && v !== undefined ? v.toFixed(2) + '%' : '', fontSize: 10 } },"
)

# ---- 16. loadTrendChart: card metric -> rate format ----
html = html.replace(
    "                        '<span>Daily Target: ' + formatNumber(Math.round(avgDailyTarget)) + ' (Natural Month Repay)</span>' +",
    "                        '<span>Avg Daily Target Rate: ' + avgDailyTarget.toFixed(2) + '% (Natural Month Repay)</span>' +"
)

# ---- 16.1 loadTrendChart: remove "today" red dot marker ----
html = re.sub(
    r"(?s)\n\s*markPoint:\s*\{\s*data:\s*\[\s*\{\s*coord:\s*\[currentDayOfMonth - 1,\s*actualValues\[currentDayOfMonth - 1\]\s*\|\|\s*0\],\s*value:\s*'Today',.*?symbolSize:\s*10\s*\}\s*",
    "\n",
    html,
    count=1
)
html = html.replace(" Red line = today.", "")

# ---- 17. TL Date selector -> REAL_DATA.availableDates ----
old_date_sel = """\
            // Populate date selector: last 30 days
            const dateSel = document.getElementById('tl-date-select');
            dateSel.innerHTML = '';
            const defaultDate = getDefaultDate();
            for (let i = 1; i <= 30; i++) {
                const d = new Date();
                d.setDate(d.getDate() - i);
                const val = d.toISOString().split('T')[0];
                const selected = val === defaultDate ? ' selected' : '';
                dateSel.innerHTML += '<option value="' + val + '"' + selected + '>' + val + '</option>';
            }"""
new_date_sel = """\
            // Populate TL date selector from real agent_repay dates
            const dateSel = document.getElementById('tl-date-select');
            dateSel.innerHTML = '';
            REAL_DATA.availableDates.forEach((dateStr, i) => {
                const selected = i === 0 ? ' selected' : '';
                dateSel.innerHTML += '<option value="' + dateStr + '"' + selected + '>' + dateStr + '</option>';
            });"""
html = html.replace(old_date_sel, new_date_sel)

# ---- 18. initSTLView: populate week selector ----
old_stl_init = """\
        function initSTLView() {
            const moduleSel = document.getElementById('stl-module-select');
            moduleSel.innerHTML = '<option value="">-- Select Module --</option>';
            REAL_DATA.modules.forEach(m => {
                moduleSel.innerHTML += '<option value="' + m + '">' + m + '</option>';
            });
            // Auto-select first module
            if (REAL_DATA.modules.length > 0) {
                moduleSel.value = REAL_DATA.modules[0];
            }
            loadSTLData();
        }"""
new_stl_init = """\
        function initSTLView() {
            const moduleSel = document.getElementById('stl-module-select');
            moduleSel.innerHTML = '<option value="">-- Select Module --</option>';
            REAL_DATA.modules.forEach(m => {
                moduleSel.innerHTML += '<option value="' + m + '">' + m + '</option>';
            });
            if (REAL_DATA.modules.length > 0) {
                moduleSel.value = REAL_DATA.modules[0];
            }

            // Populate STL week selector
            const weekSel = document.getElementById('stl-week-select');
            if (weekSel) {
                weekSel.innerHTML = '';
                REAL_DATA.availableWeeks.forEach((weekLabel, i) => {
                    const selected = weekLabel === REAL_DATA.defaultStlWeek ? ' selected' : '';
                    weekSel.innerHTML += '<option value="' + weekLabel + '"' + selected + '>' + weekLabel + '</option>';
                });
            }

            loadSTLData();
        }"""
html = html.replace(old_stl_init, new_stl_init)
# Fallback for v2.2 template structure (week options generated by getWeekOptions)
html = html.replace(
    """            const weekSel = document.getElementById('stl-week-select');
            weekSel.innerHTML = '';
            const weekOptions = getWeekOptions();
            weekOptions.forEach((opt, i) => {
                const selected = i === 0 ? ' selected' : '';
                weekSel.innerHTML += '<option value="' + opt.value + '"' + selected + '>' + opt.label + '</option>';
            });""",
    """            const weekSel = document.getElementById('stl-week-select');
            weekSel.innerHTML = '';
            REAL_DATA.availableWeeks.forEach((weekLabel, i) => {
                const selected = weekLabel === REAL_DATA.defaultStlWeek ? ' selected' : '';
                weekSel.innerHTML += '<option value="' + weekLabel + '"' + selected + '>' + weekLabel + '</option>';
            });"""
)

# ---- 19. loadSTLData: use week from selector, add weekIdx variable ----
old_load_stl = """\
        function loadSTLData() {
            const module = document.getElementById('stl-module-select').value;
            const emptyState = document.getElementById('stl-empty-state');
            const metricsContainer = document.getElementById('stl-metrics-container');
            const chartCard = document.getElementById('stl-chart-card');
            if (!module) {
                emptyState.style.display = 'flex';
                metricsContainer.style.display = 'none';
                chartCard.style.display = 'none';
                return;
            }
            emptyState.style.display = 'none';
            metricsContainer.style.display = 'block';
            chartCard.style.display = 'block';

            const data = REAL_DATA.stlData[module];
            if (!data || !data.weeks || data.weeks.length === 0) return;"""
new_load_stl = """\
        function loadSTLData() {
            const module = document.getElementById('stl-module-select').value;
            const emptyState = document.getElementById('stl-empty-state');
            const metricsContainer = document.getElementById('stl-metrics-container');
            const chartCard = document.getElementById('stl-chart-card');
            if (!module) {
                emptyState.style.display = 'flex';
                metricsContainer.style.display = 'none';
                chartCard.style.display = 'none';
                return;
            }
            emptyState.style.display = 'none';
            metricsContainer.style.display = 'block';
            chartCard.style.display = 'block';

            const data = REAL_DATA.stlData[module];
            if (!data || !data.weeks || data.weeks.length === 0) return;

            // Use selected week from week selector
            const weekSel = document.getElementById('stl-week-select');
            const selectedWeekLabel = weekSel ? weekSel.value : REAL_DATA.defaultStlWeek;
            const selectedWeekIdx = data.weeks.findIndex(w => w.weekLabel === selectedWeekLabel);
            const weekIdx = selectedWeekIdx >= 0 ? selectedWeekIdx : data.weeks.length - 1;"""
html = html.replace(old_load_stl, new_load_stl)
# Fallback for v2.2 template structure (W1/W2... week selector)
html = html.replace(
    """            const weekSel = document.getElementById('stl-week-select');
            const weekIdx = parseInt(weekSel.value.replace('W', '')) - 1;
            const weeksArr = data.weeks;
            const weekData = weeksArr[weeksArr.length - 1 - weekIdx] || weeksArr[weeksArr.length - 1];""",
    """            const weekSel = document.getElementById('stl-week-select');
            const weeksArr = data.weeks;
            const selectedWeekLabel = weekSel ? weekSel.value : REAL_DATA.defaultStlWeek;
            const selectedWeekPos = weeksArr.findIndex(w => w.weekLabel === selectedWeekLabel);
            const weekIdx = selectedWeekPos >= 0 ? (weeksArr.length - 1 - selectedWeekPos) : 0;
            const weekData = weeksArr[weeksArr.length - 1 - weekIdx] || weeksArr[weeksArr.length - 1];"""
)

# STL unmet section: add Call/Connect gap cards
html = html.replace(
    """                    <h3 style="font-size: 16px; font-weight: 600; margin-bottom: 16px; color: #991b1b;">Unmet Target — Group Drill-down</h3>
                    <p style="font-size: 12px; color: #64748b; margin-bottom: 12px;">
                        <span style="display: inline-block; width: 12px; height: 12px; background: #fef2f2; border: 1px solid #fca5a5; border-radius: 2px; margin-right: 4px;"></span>3+ consecutive weeks &nbsp;
                        <span style="display: inline-block; width: 12px; height: 12px; background: #fffbeb; border: 1px solid #fcd34d; border-radius: 2px; margin-right: 4px;"></span>1–2 consecutive weeks
                    </p>""",
    """                    <h3 style="font-size: 16px; font-weight: 600; margin-bottom: 16px; color: #991b1b;">Unmet Target — Group Drill-down</h3>
                    <p style="font-size: 12px; color: #64748b; margin-bottom: 12px;">
                        <span style="display: inline-block; width: 12px; height: 12px; background: #fef2f2; border: 1px solid #fca5a5; border-radius: 2px; margin-right: 4px;"></span>3+ consecutive weeks &nbsp;
                        <span style="display: inline-block; width: 12px; height: 12px; background: #fffbeb; border: 1px solid #fcd34d; border-radius: 2px; margin-right: 4px;"></span>1–2 consecutive weeks
                    </p>
                    <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px;">
                        <div class="metric-card">
                            <div class="metric-value" id="stl-gap-amount">--</div>
                            <div class="metric-label">Gap to Target</div>
                            <div id="stl-gap-meta" style="font-size: 12px; color: #64748b; margin-top: 4px;">Target: -- | Actual: --</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value" id="stl-call-gap">--</div>
                            <div class="metric-label">Call Volume Gap</div>
                            <div id="stl-call-gap-meta" style="font-size: 12px; color: #64748b; margin-top: 4px;">Target: -- | Actual: --</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value" id="stl-connect-gap">--</div>
                            <div class="metric-label">Call Billmin Gap</div>
                            <div id="stl-connect-gap-meta" style="font-size: 12px; color: #64748b; margin-top: 4px;">Target: -- | Actual: --</div>
                        </div>
                    </div>"""
)

# TL unmet section: add target/actual sub-lines under each gap card
html = html.replace(
    '<div class="metric-value" id="tl-gap-amount">--</div>\n                            <div class="metric-label">Gap to Target</div>',
    '<div class="metric-value" id="tl-gap-amount">--</div>\n                            <div class="metric-label">Gap to Target</div>\n                            <div id="tl-gap-meta" style="font-size: 12px; color: #64748b; margin-top: 4px;">Target: -- | Actual: --</div>'
)
html = html.replace(
    '<div class="metric-value" id="tl-call-gap">--</div>\n                            <div class="metric-label">Call Volume Gap</div>',
    '<div class="metric-value" id="tl-call-gap">--</div>\n                            <div class="metric-label">Call Volume Gap</div>\n                            <div id="tl-call-gap-meta" style="font-size: 12px; color: #64748b; margin-top: 4px;">Target: -- | Actual: --</div>'
)
html = html.replace(
    '<div class="metric-value" id="tl-connect-gap">--</div>\n                            <div class="metric-label">Connect Rate Gap</div>',
    '<div class="metric-value" id="tl-connect-gap">--</div>\n                            <div class="metric-label">Call Billmin Gap</div>\n                            <div id="tl-connect-gap-meta" style="font-size: 12px; color: #64748b; margin-top: 4px;">Target: -- | Actual: --</div>'
)

# Fix display metrics to use weekIdx
html = html.replace(
    "            const displayTarget = data.weeks[data.weeks.length - 1 - selectedWeekIdx] ? data.weeks[data.weeks.length - 1 - selectedWeekIdx].target : 0;",
    "            const displayTarget = data.weeks[data.weeks.length - 1 - weekIdx] ? data.weeks[data.weeks.length - 1 - weekIdx].target : 0;"
)
html = html.replace(
    "            const displayActual = data.weeks[data.weeks.length - 1 - selectedWeekIdx] ? data.weeks[data.weeks.length - 1 - selectedWeekIdx].actual : 0;",
    "            const displayActual = data.weeks[data.weeks.length - 1 - weekIdx] ? data.weeks[data.weeks.length - 1 - weekIdx].actual : 0;"
)
html = html.replace(
    "            const displayAchievement = data.weeks[data.weeks.length - 1 - selectedWeekIdx] ? data.weeks[data.weeks.length - 1 - selectedWeekIdx].achievement : 0;",
    "            const displayAchievement = data.weeks[data.weeks.length - 1 - weekIdx] ? data.weeks[data.weeks.length - 1 - weekIdx].achievement : 0;"
)

# Fix renderSTLChart parameter name
html = html.replace(
    "        function renderSTLChart(weeks, selectedWeekIdx) {",
    "        function renderSTLChart(weeks, weekIdx) {"
)
html = html.replace(
    "            const selectedWeek = weeks[weeks.length - 1 - selectedWeekIdx] || weeks[weeks.length - 1];",
    "            const selectedWeek = weeks[weeks.length - 1 - weekIdx] || weeks[weeks.length - 1];"
)

# STL gap metrics in unmet section, aligned to module process targets
html = html.replace(
    "            generateSTLConclusions(data, isMet, displayAchievement, displayGap);",
    "            const processTarget = REAL_DATA.processTargets && REAL_DATA.processTargets[module] ? REAL_DATA.processTargets[module] : {};\n            const callBenchmark = processTarget.artCallTimes !== null && processTarget.artCallTimes !== undefined ? processTarget.artCallTimes : null;\n            const callBillminBenchmark = processTarget.callBillminRawTarget !== null && processTarget.callBillminRawTarget !== undefined ? processTarget.callBillminRawTarget : null;\n            const groupsForGap = REAL_DATA.groupPerformance[module] || [];\n            const selectedWeekLabelForGap = document.getElementById('stl-week-select') ? document.getElementById('stl-week-select').value : REAL_DATA.defaultStlWeek;\n            const weekRows = groupsForGap.map(g => {\n                const wm = REAL_DATA.groupPerformanceByWeek && REAL_DATA.groupPerformanceByWeek[module] && REAL_DATA.groupPerformanceByWeek[module][g.name] ? REAL_DATA.groupPerformanceByWeek[module][g.name][selectedWeekLabelForGap] : null;\n                return { calls: wm && wm.calls !== undefined ? wm.calls : g.calls, callBillmin: wm && wm.callBillmin !== undefined ? wm.callBillmin : g.callBillmin };\n            });\n            const avgCalls = weekRows.length > 0 ? weekRows.reduce((sum, r) => sum + (r.calls || 0), 0) / weekRows.length : 0;\n            const avgCallBillmin = weekRows.length > 0 ? weekRows.reduce((sum, r) => sum + (r.callBillmin || 0), 0) / weekRows.length : 0;\n            const hasProcessTarget = callBenchmark !== null && callBillminBenchmark !== null;\n            const callGap = hasProcessTarget ? (avgCalls - callBenchmark) : null;\n            const callBillminGap = hasProcessTarget ? (avgCallBillmin - callBillminBenchmark) : null;\n            const processTargetMet = hasProcessTarget ? (avgCalls >= callBenchmark) && (avgCallBillmin >= callBillminBenchmark) : null;\n            const processTargetBadge = processTargetMet === null ? '<span class=\\\"status-badge\\\" style=\\\"background:#f3f4f6;color:#6b7280;\\\">Process Target: No Target</span>' : (processTargetMet ? '<span class=\\\"status-badge status-success\\\">Process Target: Met</span>' : '<span class=\\\"status-badge status-danger\\\">Process Target: Unmet</span>');\n            badge.innerHTML += ' <br>' + processTargetBadge;\n            const stlGapEl = document.getElementById('stl-gap-amount');\n            if (stlGapEl) stlGapEl.textContent = (displayActual > displayTarget ? '+' : '') + formatNumber(Math.round(displayActual - displayTarget));\n            const stlCallGapEl = document.getElementById('stl-call-gap');\n            if (stlCallGapEl) stlCallGapEl.textContent = callGap !== null ? ((callGap > 0 ? '+' : '') + callGap.toFixed(0)) : '--';\n            const stlConnectGapEl = document.getElementById('stl-connect-gap');\n            if (stlConnectGapEl) stlConnectGapEl.textContent = callBillminGap !== null ? ((callBillminGap > 0 ? '+' : '') + callBillminGap.toFixed(1)) : '--';\n            const stlGapMeta = document.getElementById('stl-gap-meta');\n            if (stlGapMeta) stlGapMeta.textContent = 'Target: ' + formatNumber(displayTarget) + ' | Actual: ' + formatNumber(displayActual);\n            const stlCallGapMeta = document.getElementById('stl-call-gap-meta');\n            if (stlCallGapMeta) stlCallGapMeta.textContent = 'Target: ' + (callBenchmark !== null ? callBenchmark.toFixed(0) : '--') + ' | Actual: ' + avgCalls.toFixed(0);\n            const stlConnectGapMeta = document.getElementById('stl-connect-gap-meta');\n            if (stlConnectGapMeta) stlConnectGapMeta.textContent = 'Target: ' + (callBillminBenchmark !== null ? callBillminBenchmark.toFixed(1) : '--') + ' | Actual: ' + avgCallBillmin.toFixed(1);\n            generateSTLConclusions(data, isMet, displayAchievement, displayGap);"
)

# TL: gap and status should compare against process targets (group/module means)
html = html.replace(
    """            const isMet = data.achievement >= 100;
            const badge = document.getElementById('tl-status-badge');
            if (isMet) {
                badge.innerHTML = '<span class="status-badge status-success">Target Met</span>';
                document.getElementById('tl-unmet-section').style.display = 'none';
            } else {
                badge.innerHTML = '<span class="status-badge status-danger">Target Not Met</span>';
                document.getElementById('tl-unmet-section').style.display = 'block';
                document.getElementById('tl-gap-amount').textContent = formatNumber(data.gap);
                document.getElementById('tl-call-gap').textContent = (data.callGap > 0 ? '+' : '') + data.callGap;
                document.getElementById('tl-connect-gap').textContent = (data.connectGap > 0 ? '+' : '') + data.connectGap.toFixed(1);
                loadTLAgentTable(group);
            }""",
    """            const isMet = data.achievement >= 100;
            const badge = document.getElementById('tl-status-badge');
            const processTarget = REAL_DATA.processTargets && REAL_DATA.processTargets[data.groupModule] ? REAL_DATA.processTargets[data.groupModule] : null;
            const callBenchmark = processTarget && processTarget.artCallTimes !== undefined && processTarget.artCallTimes !== null ? processTarget.artCallTimes : null;
            const callBillminBenchmark = processTarget && processTarget.callBillminRawTarget !== undefined && processTarget.callBillminRawTarget !== null ? processTarget.callBillminRawTarget : null;

            const getGroupDateAverages = (groupId, dateVal) => {
                const rows = REAL_DATA.agentPerformance[groupId] || [];
                let calls = 0, callBillmin = 0, cnt = 0;
                rows.forEach(a => {
                    const dm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[groupId] && REAL_DATA.agentPerformanceByDate[groupId][a.name] ? REAL_DATA.agentPerformanceByDate[groupId][a.name][dateVal] : null;
                const c = dm && dm.artCallTimes !== undefined ? dm.artCallTimes : a.artCallTimes;
                    const r = dm && dm.callBillmin !== undefined ? dm.callBillmin : a.callBillmin;
                    if (c !== null && c !== undefined && r !== null && r !== undefined) {
                        calls += c; callBillmin += r; cnt += 1;
                    }
                });
                return { callsAvg: cnt > 0 ? calls / cnt : 0, callBillminAvg: cnt > 0 ? callBillmin / cnt : 0 };
            };

            const groupAvg = getGroupDateAverages(group, selectedDate);
            const moduleGroups = REAL_DATA.groups.filter(g => REAL_DATA.tlData[g] && REAL_DATA.tlData[g].groupModule === data.groupModule);
            let moduleCalls = 0, moduleConn = 0, moduleCnt = 0;
            moduleGroups.forEach(g => {
                const ga = getGroupDateAverages(g, selectedDate);
                if (ga.callsAvg !== null && ga.callsAvg !== undefined && ga.callBillminAvg !== null && ga.callBillminAvg !== undefined) {
                    moduleCalls += ga.callsAvg; moduleConn += ga.callBillminAvg; moduleCnt += 1;
                }
            });
            const moduleAvg = { callsAvg: moduleCnt > 0 ? moduleCalls / moduleCnt : 0, callBillminAvg: moduleCnt > 0 ? moduleConn / moduleCnt : 0 };

            const groupProcessMet = (callBenchmark !== null && callBillminBenchmark !== null) ? (groupAvg.callsAvg >= callBenchmark && groupAvg.callBillminAvg >= callBillminBenchmark) : null;
            const moduleProcessMet = (callBenchmark !== null && callBillminBenchmark !== null) ? (moduleAvg.callsAvg >= callBenchmark && moduleAvg.callBillminAvg >= callBillminBenchmark) : null;
            const groupBadge = groupProcessMet === null ? '<span class=\"status-badge\" style=\"background:#f3f4f6;color:#6b7280;\">Group Avg: No Target</span>' : (groupProcessMet ? '<span class=\"status-badge status-success\">Group Avg: Met</span>' : '<span class=\"status-badge status-danger\">Group Avg: Unmet</span>');
            const moduleBadge = moduleProcessMet === null ? '<span class=\"status-badge\" style=\"background:#f3f4f6;color:#6b7280;\">Module Avg: No Target</span>' : (moduleProcessMet ? '<span class=\"status-badge status-success\">Module Avg: Met</span>' : '<span class=\"status-badge status-danger\">Module Avg: Unmet</span>');
            const processTargetMet = (groupProcessMet !== null && moduleProcessMet !== null) ? (groupProcessMet && moduleProcessMet) : null;
            const processTargetBadge = processTargetMet === null ? '<span class="status-badge" style="background:#f3f4f6;color:#6b7280;">Process Target: No Target</span>' : (processTargetMet ? '<span class="status-badge status-success">Process Target: Met</span>' : '<span class="status-badge status-danger">Process Target: Unmet</span>');

            if (isMet) {
                badge.innerHTML = '<span class=\"status-badge status-success\">Repay Target: Met</span> <br>' + processTargetBadge;
                document.getElementById('tl-unmet-section').style.display = 'none';
            } else {
                badge.innerHTML = '<span class=\"status-badge status-danger\">Repay Target: Unmet</span> <br>' + processTargetBadge;
                document.getElementById('tl-unmet-section').style.display = 'block';
                document.getElementById('tl-gap-amount').textContent = formatNumber(data.gap);
                const callGap = callBenchmark !== null ? Math.round(groupAvg.callsAvg - callBenchmark) : data.callGap;
                const connectGap = callBillminBenchmark !== null ? Math.round((groupAvg.callBillminAvg - callBillminBenchmark) * 10) / 10 : data.connectGap;
                document.getElementById('tl-call-gap').textContent = (callGap > 0 ? '+' : '') + callGap;
                document.getElementById('tl-connect-gap').textContent = (connectGap > 0 ? '+' : '') + connectGap.toFixed(1);
                loadTLAgentTable(group);
            }"""
)

# ---- 20. Agent TL table: PTP null-safe + Call Loss Rate column ----
# TL drill-down metrics linked to selected date
html = html.replace(
    "                const achColor = agent.achievement >= 100 ? '#22c55e' : '#ef4444';",
    "                const selectedDate = document.getElementById('tl-date-select') ? document.getElementById('tl-date-select').value : REAL_DATA.dataDate;\n                const dateMetrics = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][agent.name] ? REAL_DATA.agentPerformanceByDate[group][agent.name][selectedDate] : null;\n                const displayTarget = dateMetrics && dateMetrics.target !== undefined ? dateMetrics.target : agent.target;\n                const displayActual = dateMetrics && dateMetrics.actual !== undefined ? dateMetrics.actual : agent.actual;\n                const displayAchievement = dateMetrics && dateMetrics.achievement !== undefined ? dateMetrics.achievement : agent.achievement;\n                const displayCalls = dateMetrics && dateMetrics.calls !== undefined ? dateMetrics.calls : agent.calls;\n                const displayConnectRate = dateMetrics && dateMetrics.connectRate !== undefined ? dateMetrics.connectRate : agent.connectRate;\n                const displayCoverTimes = dateMetrics && dateMetrics.coverTimes !== undefined ? dateMetrics.coverTimes : agent.coverTimes;\n                const displayCallTimes = dateMetrics && dateMetrics.callTimes !== undefined ? dateMetrics.callTimes : agent.callTimes;\n                const displayArtCallTimes = dateMetrics && dateMetrics.artCallTimes !== undefined ? dateMetrics.artCallTimes : agent.artCallTimes;\n                const displayCallBillmin = dateMetrics && dateMetrics.callBillmin !== undefined ? dateMetrics.callBillmin : agent.callBillmin;\n                const displaySingleCallDuration = dateMetrics && dateMetrics.singleCallDuration !== undefined ? dateMetrics.singleCallDuration : agent.singleCallDuration;\n                const displayPtp = dateMetrics && dateMetrics.ptp !== undefined ? dateMetrics.ptp : agent.ptp;\n                const displayAttendance = dateMetrics && dateMetrics.attendance !== undefined ? dateMetrics.attendance : agent.attendance;\n                const displayCallLossRate = dateMetrics && dateMetrics.callLossRate !== undefined ? dateMetrics.callLossRate : agent.callLossRate;\n                const processTarget = REAL_DATA.processTargets && REAL_DATA.processTargets[REAL_DATA.tlData[group].groupModule] ? REAL_DATA.processTargets[REAL_DATA.tlData[group].groupModule] : null;\n                const procCallTarget = processTarget && processTarget.artCallTimes !== undefined && processTarget.artCallTimes !== null ? processTarget.artCallTimes : null;\n                const procCallBillminTarget = processTarget && processTarget.callBillminRawTarget !== undefined && processTarget.callBillminRawTarget !== null ? processTarget.callBillminRawTarget : null;\n                const processMet = (procCallTarget !== null && procCallBillminTarget !== null) ? (displayCalls >= procCallTarget && displayCallBillmin >= procCallBillminTarget) : null;\n                const processBadge = processMet === null ? '<span style=\"color:#6b7280;\">No Target</span>' : (processMet ? '<span style=\"color:#16a34a;font-weight:600;\">Met</span>' : '<span style=\"color:#dc2626;font-weight:600;\">Unmet</span>');\n                const achColor = displayAchievement >= 100 ? '#22c55e' : '#ef4444';"
)
html = html.replace(
    "'<td style=\"padding: 12px; text-align: right;\">' + formatNumber(agent.target) + '</td>' +",
    "'<td style=\"padding: 12px; text-align: right;\">' + formatNumber(displayTarget) + '</td>' +"
)
html = html.replace(
    "'<td style=\"padding: 12px; text-align: right;\">' + formatNumber(agent.actual) + '</td>' +",
    "'<td style=\"padding: 12px; text-align: right;\">' + formatNumber(displayActual) + '</td>' +"
)
html = html.replace(
    "'<td style=\"padding: 12px; text-align: right; color: ' + achColor + '; font-weight: 600;\">' + agent.achievement.toFixed(1) + '%</td>' +",
    "'<td style=\"padding: 12px; text-align: right; color: ' + achColor + '; font-weight: 600;\">' + displayAchievement.toFixed(1) + '%</td>' +"
)
html = html.replace(
    "'<td style=\"padding: 12px; text-align: right;\">' + agent.calls + '</td>' +",
    "'' +"
)
html = html.replace(
    "'<td style=\"padding: 12px; text-align: right;\">' + agent.connectRate.toFixed(1) + '%</td>' +",
    "'<td style=\"padding: 12px; text-align: right;\">' + displayConnectRate.toFixed(1) + '%</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + (displayCoverTimes !== null && displayCoverTimes !== undefined ? formatNumber(displayCoverTimes) : '--') + '</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + (displayCallTimes !== null && displayCallTimes !== undefined ? formatNumber(displayCallTimes) : '--') + '</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + (displayArtCallTimes !== null && displayArtCallTimes !== undefined ? formatNumber(displayArtCallTimes) : '--') + '</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + (displayCallBillmin !== null && displayCallBillmin !== undefined ? displayCallBillmin.toFixed(2) : '--') + '</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + (displaySingleCallDuration !== null && displaySingleCallDuration !== undefined ? displaySingleCallDuration.toFixed(2) : '--') + '</td>' +"
)
# PTP null-safe
html = html.replace(
    "agent.ptp.toFixed(1) + '%</td>' +",
    "(displayPtp !== null && displayPtp !== undefined ? displayPtp.toFixed(1) + '%' : '--') + '</td>' +"
)
# Add Call Loss column header
old_agent_header = "                    <th style=\"padding: 12px; text-align: right; background: #f1f5f9;\">Attendance</th>"
new_agent_header = """                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Call Loss</th>
                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Attendance</th>
                    <th style="padding: 12px; text-align: center; background: #f1f5f9;">Process KPI</th>"""
html = html.replace(old_agent_header, new_agent_header)
# Compatible with template variant using font-size/color styles
old_agent_header_v2 = '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>'
new_agent_header_v2 = '''                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>
                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Process KPI</th>'''
html = html.replace(old_agent_header_v2, new_agent_header_v2)

# Remove TL Calls column (keep Conn. Rate + PTP for later drill-down injection)
html = html.replace(
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Calls</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Conn. Rate</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">PTP</th>',
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Conn. Rate</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">PTP</th>'
)

# Insert process KPI drill-down columns after Conn. Rate (TL)
old_tl_conn_ptp_header = '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Conn. Rate</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">PTP</th>'
new_tl_conn_ptp_header = '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Conn. Rate</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Cover Times</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Times</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Art Call Times</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Billmin</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Single Call Duration</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">PTP</th>'
html = html.replace(old_tl_conn_ptp_header, new_tl_conn_ptp_header)
# Add Call Loss cell
old_cl_td = "                    '<td style=\"padding: 12px; text-align: right;\">' + agent.attendance + '%</td>' +\n                    '</tr>';"
new_cl_td = "                    '<td style=\"padding: 12px; text-align: right;\">' + (displayCallLossRate !== null && displayCallLossRate !== undefined ? displayCallLossRate.toFixed(1) + '%' : '--') + '</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + displayAttendance + '%</td>' +\n                    '<td style=\"padding: 12px; text-align: center;\">' + processBadge + '</td>' +\n                    '</tr>';"
html = html.replace(old_cl_td, new_cl_td)

# ---- 21. STL group table: PTP null-safe + Call Loss column ----
html = html.replace(
    "                const cw = group.consecutiveWeeks;",
    "                const selectedWeekLabel = document.getElementById('stl-week-select') ? document.getElementById('stl-week-select').value : REAL_DATA.defaultStlWeek;\n                const cwMap = REAL_DATA.groupConsecutiveWeeksByWeek && REAL_DATA.groupConsecutiveWeeksByWeek[module] && REAL_DATA.groupConsecutiveWeeksByWeek[module][group.name] ? REAL_DATA.groupConsecutiveWeeksByWeek[module][group.name] : null;\n                const cw = cwMap && cwMap[selectedWeekLabel] !== undefined ? cwMap[selectedWeekLabel] : group.consecutiveWeeks;"
)
html = html.replace(
    "                const achColor = group.achievement >= 100 ? '#22c55e' : '#ef4444';",
    "                const weekMetrics = REAL_DATA.groupPerformanceByWeek && REAL_DATA.groupPerformanceByWeek[module] && REAL_DATA.groupPerformanceByWeek[module][group.name] ? REAL_DATA.groupPerformanceByWeek[module][group.name][selectedWeekLabel] : null;\n                const displayTarget = weekMetrics && weekMetrics.target !== undefined ? weekMetrics.target : group.target;\n                const displayActual = weekMetrics && weekMetrics.actual !== undefined ? weekMetrics.actual : group.actual;\n                const displayAchievement = weekMetrics && weekMetrics.achievement !== undefined ? weekMetrics.achievement : group.achievement;\n                const displayCalls = weekMetrics && weekMetrics.calls !== undefined ? weekMetrics.calls : group.calls;\n                const displayConnectRate = weekMetrics && weekMetrics.connectRate !== undefined ? weekMetrics.connectRate : group.connectRate;\n                const displayCoverTimes = weekMetrics && weekMetrics.coverTimes !== undefined ? weekMetrics.coverTimes : group.coverTimes;\n                const displayCallTimes = weekMetrics && weekMetrics.callTimes !== undefined ? weekMetrics.callTimes : group.callTimes;\n                const displayArtCallTimes = weekMetrics && weekMetrics.artCallTimes !== undefined ? weekMetrics.artCallTimes : group.artCallTimes;\n                const displayCallBillmin = weekMetrics && weekMetrics.callBillmin !== undefined ? weekMetrics.callBillmin : group.callBillmin;\n                const displaySingleCallDuration = weekMetrics && weekMetrics.singleCallDuration !== undefined ? weekMetrics.singleCallDuration : group.singleCallDuration;\n                const displayCallLossRate = weekMetrics && weekMetrics.callLossRate !== undefined ? weekMetrics.callLossRate : group.callLossRate;\n                const displayAttendance = group.attendance;\n                const processTarget = REAL_DATA.processTargets && REAL_DATA.processTargets[module] ? REAL_DATA.processTargets[module] : null;\n                const procCallTarget = processTarget && processTarget.artCallTimes !== undefined && processTarget.artCallTimes !== null ? processTarget.artCallTimes : null;\n                const procCallBillminTarget = processTarget && processTarget.callBillminRawTarget !== undefined && processTarget.callBillminRawTarget !== null ? processTarget.callBillminRawTarget : null;\n                const processMet = (procCallTarget !== null && procCallBillminTarget !== null) ? (displayCalls >= procCallTarget && displayCallBillmin >= procCallBillminTarget) : null;\n                const processBadge = processMet === null ? '<span style=\"color:#6b7280;\">No Target</span>' : (processMet ? '<span style=\"color:#16a34a;font-weight:600;\">Met</span>' : '<span style=\"color:#dc2626;font-weight:600;\">Unmet</span>');\n                const achColor = displayAchievement >= 100 ? '#22c55e' : '#ef4444';"
)
html = html.replace(
    "'<td style=\"padding: 12px; text-align: right;\">' + formatNumber(group.target) + '</td>' +",
    "'<td style=\"padding: 12px; text-align: right;\">' + formatNumber(displayTarget) + '</td>' +"
)
html = html.replace(
    "'<td style=\"padding: 12px; text-align: right;\">' + formatNumber(group.actual) + '</td>' +",
    "'<td style=\"padding: 12px; text-align: right;\">' + formatNumber(displayActual) + '</td>' +"
)
html = html.replace(
    "'<td style=\"padding: 12px; text-align: right; color: ' + achColor + '; font-weight: 600;\">' + group.achievement.toFixed(1) + '%</td>' +",
    "'<td style=\"padding: 12px; text-align: right; color: ' + achColor + '; font-weight: 600;\">' + displayAchievement.toFixed(1) + '%</td>' +"
)
html = html.replace(
    "'<td style=\"padding: 12px; text-align: right;\">' + group.calls + '</td>' +",
    "'' +"
)
html = html.replace(
    "'<td style=\"padding: 12px; text-align: right;\">' + group.connectRate.toFixed(1) + '%</td>' +",
    "'<td style=\"padding: 12px; text-align: right;\">' + displayConnectRate.toFixed(1) + '%</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + (displayCoverTimes !== null && displayCoverTimes !== undefined ? formatNumber(displayCoverTimes) : '--') + '</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + (displayCallTimes !== null && displayCallTimes !== undefined ? formatNumber(displayCallTimes) : '--') + '</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + (displayArtCallTimes !== null && displayArtCallTimes !== undefined ? formatNumber(displayArtCallTimes) : '--') + '</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + (displayCallBillmin !== null && displayCallBillmin !== undefined ? displayCallBillmin.toFixed(2) : '--') + '</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + (displaySingleCallDuration !== null && displaySingleCallDuration !== undefined ? displaySingleCallDuration.toFixed(2) : '--') + '</td>' +"
)
html = html.replace(
    "group.ptpRate.toFixed(1) + '%</td>' +",
    "(group.ptpRate !== null && group.ptpRate !== undefined ? group.ptpRate.toFixed(1) + '%' : '--') + '</td>' +"
)
old_stl_grp_header = "                    <th style=\"padding: 12px; text-align: right; background: #f1f5f9;\">Attendance</th>"
new_stl_grp_header = """                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Call Loss</th>
                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Attendance</th>
                    <th style="padding: 12px; text-align: center; background: #f1f5f9;">Process KPI</th>"""
html = html.replace(old_stl_grp_header, new_stl_grp_header)
# Compatible with template variant using font-size/color styles
old_stl_grp_header_v2 = '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>'
new_stl_grp_header_v2 = '''                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>
                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Process KPI</th>'''
html = html.replace(old_stl_grp_header_v2, new_stl_grp_header_v2)

# Remove STL Calls/Agent column header (keep Conn. Rate + PTP Rate for later drill-down injection)
html = html.replace(
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Calls/Agent</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Conn. Rate</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">PTP Rate</th>',
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Conn. Rate</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">PTP Rate</th>'
)

# Insert process KPI drill-down columns after Conn. Rate (STL)
old_stl_conn_ptp_header = '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Conn. Rate</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">PTP Rate</th>'
new_stl_conn_ptp_header = '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Conn. Rate</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Cover Times</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Times</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Art Call Times</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Billmin</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Single Call Duration</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">PTP Rate</th>'
html = html.replace(old_stl_conn_ptp_header, new_stl_conn_ptp_header)
old_stl_grp_footer = "                    '<td style=\"padding: 12px; text-align: right;\">' + group.attendance + '%</td>' +\n                    '</tr>';"
new_stl_grp_footer = "                    '<td style=\"padding: 12px; text-align: right;\">' + (displayCallLossRate !== null && displayCallLossRate !== undefined ? displayCallLossRate.toFixed(1) + '%' : '--') + '</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + displayAttendance + '%</td>' +\n                    '<td style=\"padding: 12px; text-align: center;\">' + processBadge + '</td>' +\n                    '</tr>';"
html = html.replace(old_stl_grp_footer, new_stl_grp_footer)
# Deduplicate accidental repeated Call Loss headers after repeated runs
html = html.replace(
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>',
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>'
)
html = html.replace(
    '                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Call Loss</th>\n                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Attendance</th>\n                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Call Loss</th>',
    '                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Call Loss</th>\n                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Attendance</th>'
)
html = html.replace(
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>',
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>'
)
html = html.replace(
    '                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Call Loss</th>\n                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Call Loss</th>\n                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Attendance</th>',
    '                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Call Loss</th>\n                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Attendance</th>'
)
# Deduplicate accidental repeated Process KPI headers after repeated runs
html = html.replace(
    '                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Process KPI</th>\n                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Process KPI</th>',
    '                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Process KPI</th>'
)
html = html.replace(
    '                    <th style="padding: 12px; text-align: center; background: #f1f5f9;">Process KPI</th>\n                    <th style="padding: 12px; text-align: center; background: #f1f5f9;">Process KPI</th>',
    '                    <th style="padding: 12px; text-align: center; background: #f1f5f9;">Process KPI</th>'
)
# Keep Process KPI only in TL/STL drill-down; remove from anomaly agent table
html = html.replace(
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>\n                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Process KPI</th>',
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>'
)
# Re-add Process KPI header only for TL/STL drill-down tables
html = html.replace(
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">PTP</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>',
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">PTP</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>\n                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Process KPI</th>'
)
html = html.replace(
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">PTP Rate</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>',
    '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">PTP Rate</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>\n                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>\n                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Process KPI</th>'
)

# ---- 22. riskModuleGroups table: PTP null-safe + Call Loss column ----
html = html.replace(
    "g.ptpRate.toFixed(1) + '%</td>' +",
    "(g.ptpRate !== null && g.ptpRate !== undefined ? g.ptpRate.toFixed(1) + '%' : '--') + '</td>' +"
)
old_risk_row_end = "                        '<td style=\"padding: 8px; text-align: right;\">' + g.attendance + '%</td>' +"
new_risk_row_end = "                        '<td style=\"padding: 8px; text-align: right;\">' + (g.callLossRate !== null && g.callLossRate !== undefined ? g.callLossRate.toFixed(1) + '%' : '--') + '</td>' +\n                        '<td style=\"padding: 8px; text-align: right;\">' + g.attendance + '%</td>' +"
html = html.replace(old_risk_row_end, new_risk_row_end)
old_risk_header = "                        <th style=\"padding: 8px; text-align: right; background: #f1f5f9;\">Attendance</th>"
new_risk_header = "                        <th style=\"padding: 8px; text-align: right; background: #f1f5f9;\">Call Loss</th>\n                        <th style=\"padding: 8px; text-align: right; background: #f1f5f9;\">Attendance</th>"
html = html.replace(old_risk_header, new_risk_header)

# ---- 23. generateSTLConclusions: avgPtpRate null-safe ----
old_ptp_avg = """\
                const avgCalls = groups.reduce((sum, g) => sum + g.artCallTimes, 0) / groups.length;
                const avgConnectRate = groups.reduce((sum, g) => sum + g.connectRate, 0) / groups.length;
                const avgPtpRate = groups.reduce((sum, g) => sum + g.ptpRate, 0) / groups.length;
                const avgAttendance = groups.reduce((sum, g) => sum + g.attendance, 0) / groups.length;"""
new_ptp_avg = """\
                const avgCalls = groups.reduce((sum, g) => sum + g.artCallTimes, 0) / groups.length;
                const avgConnectRate = groups.reduce((sum, g) => sum + g.connectRate, 0) / groups.length;
                const validPtpGroups = groups.filter(g => g.ptpRate !== null && g.ptpRate !== undefined);
                const avgPtpRate = validPtpGroups.length > 0 ? validPtpGroups.reduce((sum, g) => sum + g.ptpRate, 0) / validPtpGroups.length : 999;
                const avgAttendance = groups.reduce((sum, g) => sum + g.attendance, 0) / groups.length;"""
html = html.replace(old_ptp_avg, new_ptp_avg)

# ---- 23.1 generateSTLConclusions: module-level process targets benchmark ----
html = html.replace(
    """                const callBenchmark = 50;
                const connectRateBenchmark = 22;
                const ptpRateBenchmark = 8;
                const attendanceBenchmark = 95;""",
    """                const processTarget = REAL_DATA.processTargets && REAL_DATA.processTargets[module] ? REAL_DATA.processTargets[module] : {};
                const callBenchmark = processTarget.artCallTimes !== null && processTarget.artCallTimes !== undefined ? processTarget.artCallTimes : 50;
                const connectRateBenchmark = processTarget.callBillminRawTarget !== null && processTarget.callBillminRawTarget !== undefined ? processTarget.callBillminRawTarget : 22;
                const ptpRateBenchmark = 8;
                const attendanceBenchmark = 95;"""
)

# ---- 23.2 generateSTLConclusions: use call_billmin for connect-gap analysis ----
html = html.replace(
    "                const avgConnectRate = groups.reduce((sum, g) => sum + g.connectRate, 0) / groups.length;",
    "                const avgConnectRate = groups.reduce((sum, g) => sum + g.callBillmin, 0) / groups.length;"
)
html = html.replace(
    "                    conclusions.push('Connect rate is ' + Math.abs(connectGap).toFixed(1) + '% below benchmark. Root cause: poor contact quality — either (a) outdated phone numbers, (b) customers unreachable during working hours, or (c) ineffective calling scripts.');",
    "                    conclusions.push('Call billmin is ' + Math.abs(connectGap).toFixed(1) + ' minutes below benchmark. Root cause: poor contact quality — either (a) outdated phone numbers, (b) customers unreachable during working hours, or (c) ineffective calling scripts.');"
)

# ---- 24. Recovery Trend status: On Track / Tentative / At Risk (time-aware) ----
risk_status_fn = """\
        function calculateAtRisk(module) {
            const mData = REAL_DATA.moduleMonthly[module];
            if (!mData) {
                return {
                    isAtRisk: false,
                    status: 'tentative',
                    statusLabel: 'Tentative',
                    badgeClass: 'status-badge'
                };
            }

            const monthTarget = Number(mData.monthTarget || 0);
            const currentActual = Number(mData.currentActual || 0);
            const currentDay = Math.max(1, Number(mData.currentDay || 1));
            const monthDays = Math.max(1, Number(mData.monthDays || 1));
            const remainingDays = Math.max(0, monthDays - currentDay);
            const dailyAvg = currentActual / currentDay;
            const projectedSimple = currentActual + (dailyAvg * remainingDays);
            const projectedConservative = projectedSimple;
            const projectedMomentum = projectedSimple;
            const dailyTrend = dailyAvg;

            if (monthTarget <= 0) {
                return {
                    isAtRisk: false,
                    status: 'tentative',
                    statusLabel: 'Tentative',
                    badgeClass: 'status-badge',
                    monthTarget: monthTarget,
                    currentActual: currentActual,
                    currentDay: currentDay,
                    monthDays: monthDays,
                    remainingDays: remainingDays,
                    dailyAvg: dailyAvg,
                    dailyTrend: dailyTrend,
                    projectedSimple: projectedSimple,
                    projectedConservative: projectedConservative,
                    projectedMomentum: projectedMomentum,
                    gap: 0,
                    simpleAch: 0,
                    conservativeAch: 0,
                    momentumAch: 0,
                    requiredDaily: 0,
                    targetByNow: 0,
                    progressRatio: currentDay / monthDays,
                    achievementRatio: 0,
                    progressGap: 0
                };
            }

            const progressRatio = currentDay / monthDays;
            const achievementRatio = currentActual / monthTarget;
            const targetByNow = monthTarget * progressRatio;
            const progressGap = achievementRatio - progressRatio;

            // Time-aware thresholds:
            // - On Track: clearly ahead of current pace
            // - Tentative: near current pace
            // - At Risk: significantly behind; tolerance shrinks late-month
            const onTrackLead = 0.02;
            const shortfallTolerance = 0.20 * (1 - progressRatio) + 0.04;

            let status = 'tentative';
            let statusLabel = 'Tentative';
            let badgeClass = 'status-badge';
            if (progressGap >= onTrackLead) {
                status = 'on_track';
                statusLabel = 'On Track';
                badgeClass = 'status-badge status-success';
            } else if (progressGap < -shortfallTolerance) {
                status = 'at_risk';
                statusLabel = 'At Risk';
                badgeClass = 'status-badge status-danger';
            }

            const gap = monthTarget - currentActual;
            const simpleAch = (projectedSimple / monthTarget) * 100;
            const conservativeAch = (projectedConservative / monthTarget) * 100;
            const momentumAch = (projectedMomentum / monthTarget) * 100;

            return {
                isAtRisk: status === 'at_risk',
                status: status,
                statusLabel: statusLabel,
                badgeClass: badgeClass,
                monthTarget: monthTarget,
                currentActual: currentActual,
                currentDay: currentDay,
                monthDays: monthDays,
                remainingDays: remainingDays,
                dailyAvg: dailyAvg,
                dailyTrend: dailyTrend,
                projectedSimple: projectedSimple,
                projectedConservative: projectedConservative,
                projectedMomentum: projectedMomentum,
                gap: gap,
                simpleAch: simpleAch,
                conservativeAch: conservativeAch,
                momentumAch: momentumAch,
                requiredDaily: remainingDays > 0 ? gap / remainingDays : 0,
                targetByNow: targetByNow,
                progressRatio: progressRatio,
                achievementRatio: achievementRatio,
                progressGap: progressGap
            };
        }
"""
html = re.sub(
    r"(?s)\n\s*function calculateAtRisk\(module\) \{.*?\n\s*\}\n\s*\n\s*function loadRiskModuleReview",
    "\n" + risk_status_fn + "\n\n        function loadRiskModuleReview",
    html,
    count=1
)

html = html.replace(
    "                const risk = calculateAtRisk(module);\n                const isAtRisk = risk.isAtRisk;\n                const badgeClass = isAtRisk ? 'status-badge status-danger' : 'status-badge status-success';\n                const badgeText = isAtRisk ? 'At Risk' : 'On Track';",
    "                const risk = calculateAtRisk(module);\n                const badgeClass = risk.badgeClass;\n                const badgeText = risk.statusLabel;"
)

html = html.replace(
    "<strong>At-Risk Logic:</strong> Module is at risk if projected month-end recovery (based on 7-day average) is below monthly target. ' +\n                'Projection = Current MTD + (7-day Avg × Remaining Days).'",
    "<strong>Status Logic:</strong> On Track if clearly ahead of current month pace; Tentative if near pace; At Risk if significantly behind. ' +\n                'Late-month tolerance is tighter because catch-up gets harder.'"
)

# ---- 24.1 TL/STL Target Met logic align to repay-rate target; remove VS module avg ----
# TL: hide VS MODULE AVG metric card
html = html.replace(
    """            const vsAvg = data.achievement - data.moduleAvg;
            document.getElementById('tl-module-avg').textContent = (vsAvg >= 0 ? '+' : '') + vsAvg.toFixed(1) + '%';
            document.getElementById('tl-module-avg').style.color = vsAvg >= 0 ? '#059669' : '#dc2626';""",
    """            const vsAvgCard = document.getElementById('tl-module-avg') ? document.getElementById('tl-module-avg').closest('.metric-card') : null;
            if (vsAvgCard) vsAvgCard.style.display = 'none';"""
)

# TL: target met should follow amount achievement (>=100%)
html = html.replace(
    "            const isMet = data.achievement >= 100;",
    "            const isMet = data.achievement >= 100;"
)

# TL: process KPI gap cards should use call_billmin (remove %)
html = html.replace(
    "                document.getElementById('tl-call-gap').textContent = (data.callGap > 0 ? '+' : '') + data.callGap;\n                document.getElementById('tl-connect-gap').textContent = (data.connectGap > 0 ? '+' : '') + data.connectGap.toFixed(1) + '%';\n                loadTLAgentTable(group);",
    "                const processTarget = REAL_DATA.processTargets && REAL_DATA.processTargets[data.groupModule] ? REAL_DATA.processTargets[data.groupModule] : null;\n                const callBenchmark = processTarget && processTarget.artCallTimes !== undefined && processTarget.artCallTimes !== null ? processTarget.artCallTimes : null;\n                const callBillminBenchmark = processTarget && processTarget.callBillminRawTarget !== undefined && processTarget.callBillminRawTarget !== null ? processTarget.callBillminRawTarget : null;\n                const agentsForAvg = REAL_DATA.agentPerformance[group] || [];\n                let callsSum = 0, billminSum = 0, cnt = 0;\n                agentsForAvg.forEach(agent => {\n                    const dm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][agent.name] ? REAL_DATA.agentPerformanceByDate[group][agent.name][selectedDate] : null;\n                    const c = dm && dm.calls !== undefined ? dm.calls : agent.calls;\n                    const b = dm && dm.callBillmin !== undefined ? dm.callBillmin : agent.callBillmin;\n                    if (c !== null && c !== undefined && b !== null && b !== undefined) { callsSum += c; billminSum += b; cnt += 1; }\n                });\n                const groupAvgCalls = cnt > 0 ? callsSum / cnt : 0;\n                const groupAvgBillmin = cnt > 0 ? billminSum / cnt : 0;\n                const callGap = callBenchmark !== null ? Math.round(groupAvgCalls - callBenchmark) : null;\n                const callBillminGap = callBillminBenchmark !== null ? Math.round((groupAvgBillmin - callBillminBenchmark) * 10) / 10 : null;\n                const repayTarget = (typeof displayTarget !== 'undefined') ? displayTarget : data.target;\n                const repayActual = (typeof displayActual !== 'undefined') ? displayActual : data.actual;\n                const repayGap = (repayActual !== null && repayActual !== undefined && repayTarget !== null && repayTarget !== undefined) ? (repayActual - repayTarget) : null;\n                const tlGapEl = document.getElementById('tl-gap-amount');\n                if (tlGapEl) tlGapEl.textContent = repayGap !== null ? ((repayGap > 0 ? '+' : '') + formatNumber(Math.round(repayGap))) : '--';\n                document.getElementById('tl-call-gap').textContent = callGap !== null ? (callGap > 0 ? '+' : '') + callGap : '--';\n                document.getElementById('tl-connect-gap').textContent = callBillminGap !== null ? (callBillminGap > 0 ? '+' : '') + callBillminGap.toFixed(1) : '--';\n                const tlGapMeta = document.getElementById('tl-gap-meta');\n                if (tlGapMeta) tlGapMeta.textContent = 'Target: ' + formatNumber(repayTarget) + ' | Actual: ' + formatNumber(repayActual);\n                const tlCallGapMeta = document.getElementById('tl-call-gap-meta');\n                if (tlCallGapMeta) tlCallGapMeta.textContent = 'Target: ' + (callBenchmark !== null ? callBenchmark.toFixed(0) : '--') + ' | Actual: ' + groupAvgCalls.toFixed(0);\n                const tlConnectGapMeta = document.getElementById('tl-connect-gap-meta');\n                if (tlConnectGapMeta) tlConnectGapMeta.textContent = 'Target: ' + (callBillminBenchmark !== null ? callBillminBenchmark.toFixed(1) : '--') + ' | Actual: ' + groupAvgBillmin.toFixed(1);\n                loadTLAgentTable(group);"
)

# STL: target met should follow weekly amount achievement (>=100%)
html = html.replace(
    "            const isMet = displayAchievement >= 100;",
    "            const isMet = displayAchievement >= 100;"
)

# ---- TL table/group sorting + selected line highlight ----
# 1) TL agent drill-down table: sort by achievement (ascending, worst first)
html = html.replace(
    "            const agents = REAL_DATA.agentPerformance[group] || [];\n",
    "            const selectedDate = document.getElementById('tl-date-select') ? document.getElementById('tl-date-select').value : REAL_DATA.dataDate;\n            const agents = (REAL_DATA.agentPerformance[group] || []).filter(a => {\n                const dm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][a.name]\n                    ? REAL_DATA.agentPerformanceByDate[group][a.name][selectedDate]\n                    : null;\n                return !!dm;\n            });\n            agents.sort((a, b) => {\n                const adm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][a.name]\n                    ? REAL_DATA.agentPerformanceByDate[group][a.name][selectedDate]\n                    : null;\n                const bdm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][b.name]\n                    ? REAL_DATA.agentPerformanceByDate[group][b.name][selectedDate]\n                    : null;\n                const av = (adm && adm.achievement !== null && adm.achievement !== undefined) ? adm.achievement : ((a.achievement !== null && a.achievement !== undefined) ? a.achievement : 999);\n                const bv = (bdm && bdm.achievement !== null && bdm.achievement !== undefined) ? bdm.achievement : ((b.achievement !== null && b.achievement !== undefined) ? b.achievement : 999);\n                return av - bv;\n            });\n"
)

# 2) STL group drill-down table: sort by achievement (ascending, worst first)
html = html.replace(
    "            const groups = REAL_DATA.groupPerformance[module] || [];\n",
    "            const selectedWeekLabel = document.getElementById('stl-week-select') ? document.getElementById('stl-week-select').value : REAL_DATA.defaultStlWeek;\n            const groups = (REAL_DATA.groupPerformance[module] || []).filter(g => {\n                const wm = REAL_DATA.groupPerformanceByWeek && REAL_DATA.groupPerformanceByWeek[module] && REAL_DATA.groupPerformanceByWeek[module][g.name]\n                    ? REAL_DATA.groupPerformanceByWeek[module][g.name][selectedWeekLabel]\n                    : null;\n                return !!wm;\n            });\n            groups.sort((a, b) => {\n                const awm = REAL_DATA.groupPerformanceByWeek && REAL_DATA.groupPerformanceByWeek[module] && REAL_DATA.groupPerformanceByWeek[module][a.name]\n                    ? REAL_DATA.groupPerformanceByWeek[module][a.name][selectedWeekLabel]\n                    : null;\n                const bwm = REAL_DATA.groupPerformanceByWeek && REAL_DATA.groupPerformanceByWeek[module] && REAL_DATA.groupPerformanceByWeek[module][b.name]\n                    ? REAL_DATA.groupPerformanceByWeek[module][b.name][selectedWeekLabel]\n                    : null;\n                const av = (awm && awm.achievement !== null && awm.achievement !== undefined) ? awm.achievement : ((a.achievement !== null && a.achievement !== undefined) ? a.achievement : 999);\n                const bv = (bwm && bwm.achievement !== null && bwm.achievement !== undefined) ? bwm.achievement : ((b.achievement !== null && b.achievement !== undefined) ? b.achievement : 999);\n                return av - bv;\n            });\n"
)

# 3) Risk module review table: sort groups by achievement (ascending)
html = html.replace(
    "                const groups = REAL_DATA.riskModuleGroups[module] || [];\n\n                let html = '<div style=\"margin-bottom: 24px;\">';",
    "                const groups = REAL_DATA.riskModuleGroups[module] || [];\n                groups.sort((a, b) => {\n                    const av = (a.achievement !== null && a.achievement !== undefined) ? a.achievement : 999;\n                    const bv = (b.achievement !== null && b.achievement !== undefined) ? b.achievement : 999;\n                    return av - bv;\n                });\n\n                let html = '<div style=\"margin-bottom: 24px;\">';"
)

# 4) TL recovery trend: selected group line in red
html = html.replace(
    "                const color = isSelected ? '#1e3a5f' : (idx % 2 === 0 ? '#3b82f6' : '#60a5fa');",
    "                const color = isSelected ? '#dc2626' : (idx % 2 === 0 ? '#3b82f6' : '#60a5fa');"
)

# ---- 25. Title + repay badge labels (STL base template still says Weekly Target) ----
html = html.replace('Collection Operations Report v2.2', 'Collection Operations Report v3.2')
html = html.replace(
    "badge.innerHTML = '<span class=\"status-badge status-success\">Weekly Target Met</span>';",
    "badge.innerHTML = '<span class=\"status-badge status-success\">Weekly Repay Target: Met</span>';",
)
html = html.replace(
    "badge.innerHTML = '<span class=\"status-badge status-danger\">Weekly Target Not Met</span>';",
    "badge.innerHTML = '<span class=\"status-badge status-danger\">Weekly Repay Target: Unmet</span>';",
)
html = html.replace('Weekly Recovery Trend (12 Weeks)', 'Recovery Trend (Selected Month)')

# ---- 25b. Data View: rename first subtab + under-performing criteria ----
# Subtab button label
html = html.replace(
    "<button class=\"subtab-btn active\" id=\"subtab-anomaly\" onclick=\"switchDataSubTab('anomaly')\">Anomaly Detection</button>",
    "<button class=\"subtab-btn active\" id=\"subtab-anomaly\" onclick=\"switchDataSubTab('anomaly')\">Under-performing</button>"
)
# Add Agent Overview as the 3rd subtab
html = html.replace(
    "<button class=\"subtab-btn\" id=\"subtab-trend\" onclick=\"switchDataSubTab('trend')\">Recovery Trend</button>",
    "<button class=\"subtab-btn\" id=\"subtab-trend\" onclick=\"switchDataSubTab('trend')\">Recovery Trend</button>\n                <button class=\"subtab-btn\" id=\"subtab-agent-overview\" onclick=\"switchDataSubTab('agent-overview')\">Agent Overview</button>"
)

# Group card heading + helper text
html = html.replace(
    "Group — Continuous Unmet Target (3+ Days)",
    "Group — Continuous Unmet Target (2+ Weeks)"
)
html = html.replace(
    "Groups with 3+ consecutive days below daily target, sorted by consecutive days (descending).",
    "Groups with 2+ consecutive weeks below weekly target, sorted by consecutive weeks (descending)."
)

# Group empty-state copy
html = html.replace(
    "No groups with 3+ consecutive unmet days",
    "No groups with 2+ consecutive unmet weeks"
)

# Agent card copy stays 3+ days, but fix the subtitle wording (personal)
html = html.replace(
    "Agent — Continuous Unmet Target (3+ Days)",
    "Individual — Continuous Unmet Target (3+ Days)"
)

# Rewrite Data View loader to use weekly-groups (2+ weeks) + individuals (3+ days)
old_load_anomaly = """        function loadAnomalyData() {
            // Load Group anomaly data (3+ days only, sorted by days desc)
            const groupTbody = document.getElementById('anomaly-group-table');
            const groupEmpty = document.getElementById('anomaly-group-empty');
            groupTbody.innerHTML = '';
            const groups = [...REAL_DATA.anomalyGroups].filter(g => g.days >= 3).sort((a, b) => b.days - a.days);

            if (groups.length === 0) {
                groupEmpty.style.display = 'block';
            } else {
                groupEmpty.style.display = 'none';
                groups.forEach(item => {
                    const mtdAch = item.mtdTarget > 0 ? (item.mtdActual / item.mtdTarget * 100) : 0;
                    const achColor = mtdAch >= 100 ? '#22c55e' : mtdAch >= 90 ? '#d97706' : '#ef4444';
                    const dailyGap = item.dailyTarget - item.dailyActual;
                    groupTbody.innerHTML += '<tr class="drilldown-row red-row">' +
                        '<td style="padding: 12px; font-weight: 500;">' + item.name + '</td>' +
                        '<td style="padding: 12px; text-align: center;">' + item.module + '</td>' +
                        '<td style="padding: 12px; text-align: center; font-weight: 700; color: #ef4444;">' + item.days + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + formatNumber(item.dailyTarget) + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + formatNumber(item.dailyActual) + '</td>' +
                        '<td style="padding: 12px; text-align: right; color: #ef4444; font-weight: 600;">-' + formatNumber(dailyGap) + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + formatNumber(item.mtdTarget) + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + formatNumber(item.mtdActual) + '</td>' +
                        '<td style="padding: 12px; text-align: right; color: ' + achColor + '; font-weight: 600;">' + mtdAch.toFixed(1) + '%</td>' +
                        '</tr>';
                });
            }

            // Load Agent anomaly data (3+ days only, sorted by days desc)
            const agentTbody = document.getElementById('anomaly-agent-table');
            const agentEmpty = document.getElementById('anomaly-agent-empty');
            agentTbody.innerHTML = '';
            const agents = [...REAL_DATA.anomalyAgents].filter(a => a.days >= 3).sort((a, b) => b.days - a.days);

            if (agents.length === 0) {
                agentEmpty.style.display = 'block';
            } else {
                agentEmpty.style.display = 'none';
                agents.forEach(item => {
                    const dailyGap = item.dailyTarget - item.dailyActual;
                    agentTbody.innerHTML += '<tr class="drilldown-row red-row">' +
                        '<td style="padding: 12px; font-weight: 500;">' + item.name + '</td>' +
                        '<td style="padding: 12px;">' + item.group + '</td>' +
                        '<td style="padding: 12px; text-align: center;">' + item.module + '</td>' +
                        '<td style="padding: 12px; text-align: center; font-weight: 700; color: #ef4444;">' + item.days + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + formatNumber(item.dailyTarget) + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + formatNumber(item.dailyActual) + '</td>' +
                        '<td style="padding: 12px; text-align: right; color: #ef4444; font-weight: 600;">-' + formatNumber(dailyGap) + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + item.calls + '</td>' +
                        '<td style="padding: 12px; text-align: right;">' + item.connectRate.toFixed(1) + '%</td>' +
                        '<td style="padding: 12px; text-align: right;">' + item.attendance + '%</td>' +
                        '</tr>';
                });
            }
        }"""

new_load_anomaly = """        function loadAnomalyData() {
            // Under-performing groups: 2+ consecutive unmet weeks (sorted by weeks desc)
            const groupTbody = document.getElementById('anomaly-group-table');
            const groupEmpty = document.getElementById('anomaly-group-empty');
            groupTbody.innerHTML = '';
            const groups = [...REAL_DATA.anomalyGroups].filter(g => (g.weeks || 0) >= 2).sort((a, b) => (b.weeks || 0) - (a.weeks || 0));

            if (groups.length === 0) {
                groupEmpty.style.display = 'block';
            } else {
                groupEmpty.style.display = 'none';
                groups.forEach(item => {
                    const wTgt = item.weeklyTarget || 0;
                    const wAct = item.weeklyActual || 0;
                    const wAch = wTgt > 0 ? (wAct / wTgt * 100) : 0;
                    const achColor = wAch >= 100 ? '#22c55e' : wAch >= 90 ? '#d97706' : '#ef4444';
                    const wGap = Math.max(0, wTgt - wAct);
                    const rowClass = (item.weeks || 0) >= 3 ? 'drilldown-row red-row' : 'drilldown-row yellow-row';
                    groupTbody.innerHTML += '<tr class=\"' + rowClass + '\">' +
                        '<td style=\"padding: 12px; font-weight: 500;\">' + item.name + '</td>' +
                        '<td style=\"padding: 12px; text-align: center;\">' + item.module + '</td>' +
                        '<td style=\"padding: 12px; text-align: center; font-weight: 700;\">' + item.weeks + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + formatNumber(wTgt) + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + formatNumber(wAct) + '</td>' +
                        '<td style=\"padding: 12px; text-align: right; color: #ef4444; font-weight: 600;\">-' + formatNumber(wGap) + '</td>' +
                        '<td style=\"padding: 12px; text-align: right; color: ' + achColor + '; font-weight: 600;\">' + wAch.toFixed(1) + '%</td>' +
                        '</tr>';
                });
            }

            // Under-performing individuals: 3+ consecutive unmet days (sorted by days desc)
            const agentTbody = document.getElementById('anomaly-agent-table');
            const agentEmpty = document.getElementById('anomaly-agent-empty');
            agentTbody.innerHTML = '';
            const agents = [...REAL_DATA.anomalyAgents].filter(a => (a.days || 0) >= 3).sort((a, b) => (b.days || 0) - (a.days || 0));

            if (agents.length === 0) {
                agentEmpty.style.display = 'block';
            } else {
                agentEmpty.style.display = 'none';
                agents.forEach(item => {
                    const dailyGap = Math.max(0, (item.dailyTarget || 0) - (item.dailyActual || 0));
                    const callLoss = (item.callLossRate !== null && item.callLossRate !== undefined) ? item.callLossRate.toFixed(1) + '%' : '--';
                    agentTbody.innerHTML += '<tr class=\"drilldown-row red-row\">' +
                        '<td style=\"padding: 12px; font-weight: 500;\">' + item.name + '</td>' +
                        '<td style=\"padding: 12px;\">' + item.group + '</td>' +
                        '<td style=\"padding: 12px; text-align: center;\">' + item.module + '</td>' +
                        '<td style=\"padding: 12px; text-align: center; font-weight: 700; color: #ef4444;\">' + item.days + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + formatNumber(item.dailyTarget) + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + formatNumber(item.dailyActual) + '</td>' +
                        '<td style=\"padding: 12px; text-align: right; color: #ef4444; font-weight: 600;\">-' + formatNumber(dailyGap) + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + (item.calls !== null && item.calls !== undefined ? item.calls : '--') + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + (item.connectRate !== null && item.connectRate !== undefined ? item.connectRate.toFixed(1) + '%' : '--') + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + callLoss + '</td>' +
                        '<td style=\"padding: 12px; text-align: right;\">' + item.attendance + '%</td>' +
                        '</tr>';
                });
            }
        }"""

html = html.replace(old_load_anomaly, new_load_anomaly)

# Add Agent Overview subtab container (before existing trend subtab)
html = html.replace(
    "            <!-- Recovery Trend Sub-tab -->",
    """            <!-- Agent Overview Sub-tab -->
            <div id="data-agent-overview" class="data-subtab-content" style="display: none;">
                <div class="card" style="margin-bottom: 20px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom: 8px;">
                        <h2 style="font-size: 18px; font-weight: 700; color: #1e293b; margin: 0;">Agent Overview</h2>
                        <div style="display:flex; align-items:center; gap:8px;">
                            <label style="font-size: 13px; color: #64748b;">Date:</label>
                            <select id="data-agent-date" onchange="loadAgentOverviewData()" style="padding:6px 10px; border:1px solid #cbd5e1; border-radius:6px; font-size:13px;"></select>
                        </div>
                    </div>
                    <p style="color: #64748b; font-size: 13px; margin-bottom: 0;">Per module, agents are sorted by daily actual repay amount (high to low).</p>
                </div>
                <div id="agent-overview-content"></div>
            </div>

            <!-- Recovery Trend Sub-tab -->"""
)

# Data subtab switching: include agent-overview branch
html = html.replace(
    """        function switchDataSubTab(subtab) {
            document.querySelectorAll('.subtab-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('subtab-' + subtab).classList.add('active');
            document.querySelectorAll('.data-subtab-content').forEach(c => c.style.display = 'none');
            document.getElementById('data-' + subtab).style.display = 'block';
            if (subtab === 'trend') loadTrendData();
        }""",
    """        function switchDataSubTab(subtab) {
            document.querySelectorAll('.subtab-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById('subtab-' + subtab).classList.add('active');
            document.querySelectorAll('.data-subtab-content').forEach(c => c.style.display = 'none');
            document.getElementById('data-' + subtab).style.display = 'block';
            if (subtab === 'trend') loadTrendData();
            else if (subtab === 'agent-overview') loadAgentOverviewData();
        }"""
)

# Agent Overview renderer/functions
html = html.replace(
    "        function loadTrendData() {",
    """        function initAgentOverviewDateSelector() {
            const sel = document.getElementById('data-agent-date');
            if (!sel) return;
            const dates = REAL_DATA.availableDates || [];
            sel.innerHTML = '';
            dates.forEach(d => {
                sel.innerHTML += '<option value=\"' + d + '\">' + d + '</option>';
            });
            if (dates.length > 0) {
                const defDate = (REAL_DATA.dataDate && dates.includes(REAL_DATA.dataDate)) ? REAL_DATA.dataDate : dates[0];
                sel.value = defDate;
            }
        }

        function computeAgentConsecutiveDaysByDate(groupId, agentId, selectedDate) {
            const hist = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[groupId] && REAL_DATA.agentPerformanceByDate[groupId][agentId]
                ? REAL_DATA.agentPerformanceByDate[groupId][agentId]
                : null;
            if (!hist) return 0;
            const dates = (REAL_DATA.availableDates || []).slice().reverse(); // oldest -> newest
            const endIdx = dates.indexOf(selectedDate);
            if (endIdx < 0) return 0;
            let streak = 0;
            for (let i = endIdx; i >= 0; i--) {
                const d = dates[i];
                const row = hist[d];
                if (!row || row.achievement === null || row.achievement === undefined) break;
                if (row.achievement < 100) streak += 1;
                else break;
            }
            return streak;
        }

        function loadAgentOverviewData() {
            const container = document.getElementById('agent-overview-content');
            const sel = document.getElementById('data-agent-date');
            if (!container || !sel) return;
            const selectedDate = sel.value || REAL_DATA.dataDate;
            container.innerHTML = '';
            window.agentOverviewExpanded = window.agentOverviewExpanded || {};

            const modulePriority = ['S0', 'S1', 'S2', 'M1'];
            const moduleRank = {};
            modulePriority.forEach((m, i) => { moduleRank[m] = i; });

            function parseModuleParts(module) {
                const text = String(module || '').trim();
                const parts = text.split('-');
                const base = (parts[0] || '').trim();
                const rawTier = (parts[1] || '').trim().toLowerCase();
                const tier = (rawTier === 'large' || rawTier.includes('大额'))
                    ? 'large'
                    : ((rawTier === 'small' || rawTier.includes('小额')) ? 'small' : rawTier);
                return { base, tier };
            }

            function sortModules(a, b) {
                const pa = parseModuleParts(a);
                const pb = parseModuleParts(b);
                const ra = Object.prototype.hasOwnProperty.call(moduleRank, pa.base) ? moduleRank[pa.base] : 999;
                const rb = Object.prototype.hasOwnProperty.call(moduleRank, pb.base) ? moduleRank[pb.base] : 999;
                if (ra !== rb) return ra - rb;
                if (pa.base !== pb.base) return pa.base.localeCompare(pb.base);
                const ta = pa.tier === 'large' ? 0 : (pa.tier === 'small' ? 1 : 2);
                const tb = pb.tier === 'large' ? 0 : (pb.tier === 'small' ? 1 : 2);
                if (ta !== tb) return ta - tb;
                return String(a).localeCompare(String(b));
            }

            function renderModuleTable(module) {
                const groupsInModule = (REAL_DATA.groups || []).filter(g => REAL_DATA.tlData[g] && REAL_DATA.tlData[g].groupModule === module);
                let rows = [];
                groupsInModule.forEach(groupId => {
                    const agents = REAL_DATA.agentPerformance[groupId] || [];
                    agents.forEach(agent => {
                        const dm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[groupId] && REAL_DATA.agentPerformanceByDate[groupId][agent.name]
                            ? REAL_DATA.agentPerformanceByDate[groupId][agent.name][selectedDate]
                            : null;
                        const actual = dm && dm.actual !== undefined ? dm.actual : agent.actual;
                        const target = dm && dm.target !== undefined ? dm.target : agent.target;
                        const achievement = dm && dm.achievement !== undefined ? dm.achievement : agent.achievement;
                        rows.push({
                            name: agent.name,
                            group: groupId,
                            actual: actual || 0,
                            target: target || 0,
                            achievement: achievement || 0,
                            consecutiveDays: computeAgentConsecutiveDaysByDate(groupId, agent.name, selectedDate)
                        });
                    });
                });

                rows.sort((a, b) => (b.actual || 0) - (a.actual || 0));
                rows = rows.map((r, idx) => ({ ...r, rank: idx + 1 }));
                const expanded = !!window.agentOverviewExpanded[module];
                const showTopN = 10;
                const visibleRows = expanded ? rows : rows.slice(0, showTopN);

                let section = '<div class=\"card\">';
                section += '<h3 style=\"font-size:16px; font-weight:600; margin-bottom:10px; color:#1e293b;\">' + module + '</h3>';
                if (rows.length === 0) {
                    section += '<div class=\"empty-state\" style=\"display:block;\"><div class=\"empty-state-title\">No agent data</div><div class=\"empty-state-sub\">No records available for selected date.</div></div>';
                } else {
                    section += '<div style=\"width:100%; overflow-x:auto;\">';
                    section += '<table style=\"width:100%; border-collapse:collapse;\">';
                    section += '<thead><tr style=\"background:#f8fafc; border-bottom:2px solid #e2e8f0;\">'
                        + '<th style=\"padding:12px; text-align:center; font-size:12px; color:#64748b; white-space:nowrap;\">Rank</th>'
                        + '<th style=\"padding:12px; text-align:left; font-size:12px; color:#64748b; white-space:nowrap;\">Agent</th>'
                        + '<th style=\"padding:12px; text-align:left; font-size:12px; color:#64748b; white-space:nowrap;\">Group</th>'
                        + '<th style=\"padding:12px; text-align:right; font-size:12px; color:#64748b; white-space:nowrap;\">Daily Actual</th>'
                        + '<th style=\"padding:12px; text-align:right; font-size:12px; color:#64748b; white-space:nowrap;\">Daily Target</th>'
                        + '<th style=\"padding:12px; text-align:right; font-size:12px; color:#64748b; white-space:nowrap;\">Achievement</th>'
                        + '<th style=\"padding:12px; text-align:center; font-size:12px; color:#64748b; white-space:nowrap;\">Consecutive Days</th>'
                        + '</tr></thead><tbody>';
                    visibleRows.forEach(r => {
                        const achColor = r.achievement >= 100 ? '#16a34a' : '#dc2626';
                        section += '<tr class=\"drilldown-row\">'
                            + '<td style=\"padding:12px; text-align:center; font-weight:600; white-space:nowrap;\">' + r.rank + '</td>'
                            + '<td style=\"padding:12px; font-weight:500; white-space:nowrap;\">' + r.name + '</td>'
                            + '<td style=\"padding:12px; white-space:nowrap;\">' + r.group + '</td>'
                            + '<td style=\"padding:12px; text-align:right; white-space:nowrap;\">' + formatNumber(r.actual) + '</td>'
                            + '<td style=\"padding:12px; text-align:right; white-space:nowrap;\">' + formatNumber(r.target) + '</td>'
                            + '<td style=\"padding:12px; text-align:right; color:' + achColor + '; font-weight:600; white-space:nowrap;\">' + r.achievement.toFixed(1) + '%</td>'
                            + '<td style=\"padding:12px; text-align:center; font-weight:600; white-space:nowrap;\">' + r.consecutiveDays + '</td>'
                            + '</tr>';
                    });
                    section += '</tbody></table>';
                    section += '</div>';
                    if (rows.length > showTopN) {
                        const btnText = expanded ? 'Show Top 10' : ('Show All (' + rows.length + ')');
                        section += '<div style=\"display:flex; justify-content:flex-end; margin-top:10px;\">'
                            + '<button onclick=\"toggleAgentOverviewModule(\\'' + module + '\\')\" style=\"border:1px solid #cbd5e1; background:#fff; color:#334155; padding:6px 10px; border-radius:6px; cursor:pointer; font-size:12px;\">'
                            + btnText
                            + '</button></div>';
                    }
                }
                section += '</div>';
                return section;
            }

            function toggleAgentOverviewModule(module) {
                window.agentOverviewExpanded[module] = !window.agentOverviewExpanded[module];
                loadAgentOverviewData();
            }
            window.toggleAgentOverviewModule = toggleAgentOverviewModule;

            const orderedModules = (REAL_DATA.modules || []).slice().sort(sortModules);
            const groupedByBase = {};
            orderedModules.forEach(module => {
                const p = parseModuleParts(module);
                if (!groupedByBase[p.base]) groupedByBase[p.base] = [];
                groupedByBase[p.base].push(module);
            });

            const baseOrder = Object.keys(groupedByBase).sort((a, b) => {
                const ra = Object.prototype.hasOwnProperty.call(moduleRank, a) ? moduleRank[a] : 999;
                const rb = Object.prototype.hasOwnProperty.call(moduleRank, b) ? moduleRank[b] : 999;
                if (ra !== rb) return ra - rb;
                return a.localeCompare(b);
            });

            baseOrder.forEach(base => {
                const modules = groupedByBase[base];
                const largeModule = modules.find(m => parseModuleParts(m).tier === 'large');
                const smallModule = modules.find(m => parseModuleParts(m).tier === 'small');
                const otherModules = modules.filter(m => {
                    const t = parseModuleParts(m).tier;
                    return t !== 'large' && t !== 'small';
                });

                if (largeModule && smallModule) {
                    let rowHtml = '<div style=\"display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px; align-items:start;\">';
                    rowHtml += '<div>' + renderModuleTable(largeModule) + '</div>';
                    rowHtml += '<div>' + renderModuleTable(smallModule) + '</div>';
                    rowHtml += '</div>';
                    container.innerHTML += rowHtml;
                    otherModules.forEach(module => {
                        container.innerHTML += '<div style=\"margin-bottom:16px;\">' + renderModuleTable(module) + '</div>';
                    });
                } else {
                    modules.forEach(module => {
                        container.innerHTML += '<div style=\"margin-bottom:16px;\">' + renderModuleTable(module) + '</div>';
                    });
                }
            });
        }

        function loadTrendData() {"""
)

# Init Data view: also init Agent Overview date selector
html = html.replace(
    """        function initDataView() {
            loadAnomalyData();
        }""",
    """        function initDataView() {
            loadAnomalyData();
            initAgentOverviewDateSelector();
        }"""
)

# Update group under-performing table headers to weekly schema (keep tbody id)
old_underperf_group_header = """                            <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                                <th style="padding: 12px; text-align: left; font-size: 12px; color: #64748b;">Group</th>
                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Module</th>
                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Consecutive Days</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Daily Target</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Daily Actual</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Daily Gap</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">MTD Target</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">MTD Actual</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">MTD Achievement</th>
                            </tr>"""
new_underperf_group_header = """                            <tr style="background: #f8fafc; border-bottom: 2px solid #e2e8f0;">
                                <th style="padding: 12px; text-align: left; font-size: 12px; color: #64748b;">Group</th>
                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Module</th>
                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Consecutive Weeks</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Weekly Target</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Weekly Actual</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Weekly Gap</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Weekly Achievement</th>
                            </tr>"""
html = html.replace(old_underperf_group_header, new_underperf_group_header)

# ---- 26. Data date ----
html = html.replace(
    "document.getElementById('data-date').textContent = new Date(Date.now() - 86400000).toISOString().split('T')[0];",
    f"document.getElementById('data-date').textContent = REAL_DATA.dataDate;"
)

# Process KPI drill-down: use art_call_times for call volume comparisons
html = html.replace("displayCalls >= procCallTarget", "displayArtCallTimes >= procCallTarget")

# ---- 26b. Hide M2 in all views (temporary) ----
html = html.replace(
    "        // ===================== TL VIEW =====================",
    """        function isM2Module(module) {
            return String(module || '').trim().toUpperCase() === 'M2';
        }

        function getVisibleModules() {
            return (REAL_DATA.modules || []).filter(m => !isM2Module(m));
        }

        // ===================== TL VIEW ====================="""
)

html = html.replace(
    """            REAL_DATA.groups.forEach(g => {
                groupSel.innerHTML += '<option value="' + g + '">' + g + '</option>';
            });""",
    """            REAL_DATA.groups.forEach(g => {
                const groupModule = REAL_DATA.tlData[g] ? REAL_DATA.tlData[g].groupModule : '';
                if (isM2Module(groupModule)) return;
                groupSel.innerHTML += '<option value="' + g + '">' + g + '</option>';
            });"""
)

html = html.replace(
    "REAL_DATA.modules.forEach(m => {",
    "getVisibleModules().forEach(m => {"
)

html = html.replace(
    "const groups = [...REAL_DATA.anomalyGroups].filter(g => (g.weeks || 0) >= 2).sort((a, b) => (b.weeks || 0) - (a.weeks || 0));",
    """const groups = [...REAL_DATA.anomalyGroups]
                .filter(g => !isM2Module(g.module))
                .filter(g => (g.weeks || 0) >= 2)
                .sort((a, b) => (b.weeks || 0) - (a.weeks || 0));"""
)

html = html.replace(
    "const agents = [...REAL_DATA.anomalyAgents].filter(a => (a.days || 0) >= 3).sort((a, b) => (b.days || 0) - (a.days || 0));",
    """const agents = [...REAL_DATA.anomalyAgents]
                .filter(a => !isM2Module(a.module))
                .filter(a => (a.days || 0) >= 3)
                .sort((a, b) => (b.days || 0) - (a.days || 0));"""
)

html = html.replace(
    "const orderedModules = (REAL_DATA.modules || []).slice().sort(sortModules);",
    "const orderedModules = getVisibleModules().slice().sort(sortModules);"
)

html = html.replace(
    "REAL_DATA.modules.forEach(module => {",
    "getVisibleModules().forEach(module => {"
)

# ---- TL: unify repay badge labels + show process badge only when repay not met ----
html = html.replace(
    "badge.innerHTML = '<span class=\"status-badge status-success\">Target Met</span>';",
    "badge.innerHTML = '<span class=\"status-badge status-success\">Repay Target: Met</span>';")
html = html.replace(
    "badge.innerHTML = '<span class=\"status-badge status-danger\">Target Not Met</span>';",
    "badge.innerHTML = '<span class=\"status-badge status-danger\">Repay Target: Unmet</span>';")

# TL process badge should use art_call_times + call_billmin (raw minutes)
html = html.replace(
    "const c = dm && dm.calls !== undefined ? dm.calls : agent.calls;",
    "const c = dm && dm.artCallTimes !== undefined ? dm.artCallTimes : agent.artCallTimes;")

# When repay target is NOT met (TL else-branch), append process target badge to TL header
html = html.replace(
    "const callGap = callBenchmark !== null ? Math.round(groupAvgCalls - callBenchmark) : null;",
    "const processTargetMet = (callBenchmark !== null && callBillminBenchmark !== null) ? (groupAvgCalls >= callBenchmark && groupAvgBillmin >= callBillminBenchmark) : null;\n                const processTargetBadge = processTargetMet === null ? '<span class=\"status-badge\" style=\"background:#f3f4f6;color:#6b7280;\">Process Target: No Target</span>' : (processTargetMet ? '<span class=\"status-badge status-success\">Process Target: Met</span>' : '<span class=\"status-badge status-danger\">Process Target: Unmet</span>');\n                badge.innerHTML += ' <br>' + processTargetBadge;\n                const callGap = callBenchmark !== null ? Math.round(groupAvgCalls - callBenchmark) : null;")

# ---- STL Recovery Trend: enforce full-month axis + target continues ----
stl_chart_fn = """\
        function renderSTLChart(weeks, weekIdx) {
            const chartDom = document.getElementById('stl-chart');
            if (stlChart) stlChart.dispose();
            stlChart = echarts.init(chartDom);

            // Get selected week to determine the month
            const selectedWeek = weeks[weeks.length - 1 - weekIdx] || weeks[weeks.length - 1];
            const weekLabel = selectedWeek.weekLabel; // e.g., "03/09 - 03/15"
            const weekParts = weekLabel.split(' - ');
            const endPart = weekParts.length > 1 ? weekParts[1] : weekParts[0];
            const monthStr = endPart.split('/')[0]; // Use week-end month for cross-month week labels

            const cutoffDate = REAL_DATA.dataDate;
            const module = document.getElementById('stl-module-select').value;
            const selectedYearMonth = REAL_DATA.dataDate.slice(0, 4) + '-' + monthStr.padStart(2, '0'); // YYYY-MM

            // Full-month labels: MM-DD
            const ymParts = selectedYearMonth.split('-');
            const year = parseInt(ymParts[0], 10);
            const month = parseInt(ymParts[1], 10); // 1-12
            const daysInMonth = new Date(year, month, 0).getDate();
            const labels = [];
            for (let d = 1; d <= daysInMonth; d++) {
                const mm = String(month).padStart(2, '0');
                const dd = String(d).padStart(2, '0');
                labels.push(mm + '-' + dd);
            }

            // Trend source (includes target)
            const trendData = REAL_DATA.moduleDailyTrends[module];
            const dailyAll = (trendData && trendData.daily) ? trendData.daily.filter(d => d.date.startsWith(selectedYearMonth)) : [];
            const dailyActual = dailyAll.filter(d => d.date <= cutoffDate);

            const targetByLabel = {};
            dailyAll.forEach(r => { targetByLabel[r.date.slice(5)] = (r.targetRepayRate !== null && r.targetRepayRate !== undefined) ? r.targetRepayRate : null; });

            const moduleActualByLabel = {};
            dailyActual.forEach(r => { moduleActualByLabel[r.date.slice(5)] = (r.repayRate !== null && r.repayRate !== undefined) ? r.repayRate : null; });

            const series = [];
            const legendData = ['Module Target'];

            // Module target (full month)
            const targetValues = labels.map(lbl => (Object.prototype.hasOwnProperty.call(targetByLabel, lbl) ? targetByLabel[lbl] : null));
            series.push({
                name: 'Module Target',
                type: 'line',
                data: targetValues,
                smooth: false,
                lineStyle: { color: '#059669', width: 2, type: 'dashed' },
                itemStyle: { color: '#059669' },
                symbol: 'none',
                z: 5
            });

            const groupsInModule = REAL_DATA.groups.filter(g => REAL_DATA.tlData[g] && REAL_DATA.tlData[g].groupModule === module);
            groupsInModule.forEach((g, idx) => {
                const gData = REAL_DATA.tlData[g];
                if (!gData || !gData.days) return;
                const color = idx % 2 === 0 ? '#1e3a5f' : '#3b82f6';

                const filteredDays = gData.days.filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate);
                const repayByLabel = {};
                filteredDays.forEach(d => {
                    const v = (d.nmRepayRate !== null && d.nmRepayRate !== undefined) ? d.nmRepayRate : ((d.repayRate !== null && d.repayRate !== undefined) ? d.repayRate : null);
                    repayByLabel[d.date.slice(5)] = v;
                });
                const repayRates = labels.map(lbl => (Object.prototype.hasOwnProperty.call(repayByLabel, lbl) ? repayByLabel[lbl] : null));

                series.push({
                    name: g,
                    type: 'line',
                    data: repayRates,
                    smooth: true,
                    lineStyle: { color: color, width: 1.5, opacity: 0.6 },
                    itemStyle: { color: color },
                    symbol: 'none',
                    z: idx + 1
                });
                legendData.unshift(g);
            });

            // Module total actual (null for future)
            const moduleActuals = labels.map(lbl => (Object.prototype.hasOwnProperty.call(moduleActualByLabel, lbl) ? moduleActualByLabel[lbl] : null));
            series.push({
                name: 'Module Total',
                type: 'line',
                data: moduleActuals,
                smooth: true,
                lineStyle: { color: '#0ea5e9', width: 3 },
                itemStyle: { color: '#0ea5e9' },
                symbol: 'none',
                z: 10
            });
            legendData.unshift('Module Total');

            stlChart.setOption({
                tooltip: { trigger: 'axis', formatter: params => {
                    const date = params[0].name;
                    let html = date + '<br>';
                    const sortedParams = params.slice().sort((a, b) => {
                        const av = (a.value !== null && a.value !== undefined) ? a.value : -999999;
                        const bv = (b.value !== null && b.value !== undefined) ? b.value : -999999;
                        return bv - av; // desc
                    });
                    sortedParams.forEach(p => {
                        html += p.marker + ' ' + p.seriesName + ': ' + (p.value !== null && p.value !== undefined ? p.value.toFixed(2) + '%' : '-') + '<br>';
                    });
                    return html;
                }},
                legend: { data: legendData, bottom: 0, type: 'scroll', itemWidth: 20 },
                grid: { left: '3%', right: '4%', bottom: '15%', top: '8%', containLabel: true },
                xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 10, interval: Math.max(0, Math.floor(labels.length / 10) - 1) } },
                yAxis: { type: 'value', axisLabel: { formatter: v => v !== null && v !== undefined ? v.toFixed(2) + '%' : '' } },
                series: series
            });
        }
"""

# Replace the whole function body to avoid fragile string matching.
html = re.sub(
    r"(?s)\n\s*function renderSTLChart\(weeks, weekIdx\) \{.*?\n\s*\}\n\s*\n\s*function generateSTLConclusions",
    "\n" + stl_chart_fn + "\n\n        function generateSTLConclusions",
    html,
    count=1
)

# ========================
# v3.3: bilingual (EN/ZH) display layer
# - Data and calculations unchanged
# - Only UI text rendering switches by language
# ========================
html = html.replace("Collection Operations Report v3.2", "Collection Operations Report v3.3")

html = html.replace(
    "<p style=\"font-size: 14px; opacity: 0.9; margin-top: 4px;\">Generated: <span id=\"report-date\"></span> | Data Date: <span id=\"data-date\"></span></p>",
    "<p style=\"font-size: 14px; opacity: 0.9; margin-top: 4px;\">Generated: <span id=\"report-date\"></span> | Data Date: <span id=\"data-date\"></span></p>\n                <div id=\"lang-switch\" style=\"margin-top:10px; display:flex; gap:8px;\">\n                    <button class=\"role-btn\" id=\"lang-en\" style=\"padding:4px 10px; font-size:12px;\" onclick=\"setLanguage('en')\">English</button>\n                    <button class=\"role-btn\" id=\"lang-zh\" style=\"padding:4px 10px; font-size:12px;\" onclick=\"setLanguage('zh')\">中文</button>\n                </div>"
)

i18n_inject = r"""
        let currentLang = 'en';
        const I18N_ZH = {
            'Generated: ': '生成时间：',
            'Data Date: ': '数据日期：',
            'TL View': 'TL视图',
            'STL View': 'STL视图',
            'Data View': '数据视图',
            'TL Daily Review': 'TL日度复盘',
            'Group:': '组别：',
            'Date:': '日期：',
            '-- Select Group --': '-- 选择组别 --',
            'Select a group to view daily performance': '请选择组别以查看日度表现',
            'Use the Group selector above to get started': '请使用上方组别选择器开始',
            'Target': '目标',
            'Actual': '实际',
            'Achievement Rate': '达成率',
            'vs Module Avg': '对比模块均值',
            'Daily Recovery Trend (Selected Month)': '日回收趋势（所选月份）',
            'Unmet Target — Detail Review': '未达标明细复盘',
            'Gap to Target': '目标差额',
            'Call Gap': '通话差额',
            'Conn/BillMin Gap': '接通分钟差额',
            'Agent Level Drill-down': '坐席明细下钻',
            'Agent': '坐席',
            'Automated Conclusions': '自动结论',
            'STL Weekly Review': 'STL周度复盘',
            'Module:': '模块：',
            '-- Select Module --': '-- 选择模块 --',
            'Select a module to view weekly performance': '请选择模块以查看周度表现',
            'Use the Module selector above to get started': '请使用上方模块选择器开始',
            'Week Target': '周目标',
            'Recovery Trend (Selected Month)': '回收趋势（所选月份）',
            'Unmet Target — Group Drill-down': '未达标组下钻',
            'Group': '组别',
            'Call Loss': '失联率',
            'Attendance': '出勤率',
            'Under-performing': '连续未达标',
            'Recovery Trend': '回收趋势',
            'Agent Overview': '坐席总览',
            'Group — Continuous Unmet Target (2+ Weeks)': '组别连续未达标（2周+）',
            'Individual — Continuous Unmet Target (3+ Days)': '个人连续未达标（3天+）',
            'Consecutive Weeks': '连续周数',
            'Weekly Target': '周目标',
            'Weekly Actual': '周实际',
            'Weekly Gap': '周差额',
            'Weekly Achievement': '周达成率',
            'Consecutive Days': '连续天数',
            'Daily Target': '日目标',
            'Daily Actual': '日实际',
            'Daily Gap': '日差额',
            'Calls': '通话量',
            '3+ consecutive days': '连续3天+',
            '1–2 consecutive days': '连续1-2天',
            '3+ consecutive weeks': '连续3周+',
            '1–2 consecutive weeks': '连续1-2周',
            'Groups with 2+ consecutive weeks below weekly target, sorted by consecutive weeks (descending).': '连续2周及以上未达周目标的组，按连续周数降序。',
            'Agents with 3+ consecutive days below daily target, sorted by consecutive days (descending).': '连续3天及以上未达日目标的坐席，按连续天数降序。',
            'No groups with 2+ consecutive unmet weeks': '暂无连续2周以上未达标组',
            'No agents with 3+ consecutive unmet days': '暂无连续3天以上未达标坐席',
            'No records found for current criteria': '当前条件下无数据',
            'No records found for current threshold': '当前阈值下无数据',
            'Recovery Trend by Module': '模块回收趋势',
            'At-Risk Modules — Group Drill-down': '风险模块—组别下钻',
            'No at-risk modules in current data.': '当前数据暂无风险模块',
            'At Risk': '有风险',
            'On Track': '达标中',
            'Repay Target: Met': '回款目标：达标',
            'Repay Target: Unmet': '回款目标：未达标',
            'Process Target: Met': '过程目标：达标',
            'Process Target: Unmet': '过程目标：未达标',
            'Process Target: No Target': '过程目标：无目标',
            'Show Top 10': '仅看前10',
            'No agent data': '无坐席数据',
            'No records available for selected date.': '所选日期暂无记录',
            'Rank': '排名',
            'Conn%': '接通率%',
            'PTP%': 'PTP%',
            'Attd%': '失联率%',
            'Conservative': '保守预测',
            'Simple Avg': '简单均值',
            'Momentum (3-day)': '动量（近3天）',
            'Month Target': '月目标',
            'Gap to Close': '待弥补差额',
            'Required Daily Avg': '所需日均',
            'Module Total': '模块汇总',
            'Module Target': '模块目标',
            'Daily Target': '日目标',
            'Today': '今日',
            'Target achieved with ': '目标已达成，达成率',
            'Performance is ': '表现较模块均值',
            ' module average.': '。',
            'above': '高于',
            'below': '低于',
            'Target gap of ': '目标差额 ',
            '% below target': '% 低于目标',
            'Call volume is ': '通话量较目标少 ',
            ' calls below target. Review attendance and dial rate.': ' 通，建议复核出勤与拨号效率。',
            'Connect rate is ': '接通率较基准低 ',
            '% below benchmark. Review contact list quality and call timing.': '%，建议复核名单质量与外呼时段。',
            ' agent(s) with 3+ consecutive unmet days require immediate coaching: ': ' 名连续3天以上未达标坐席需立即辅导：',
            'Weekly target achieved with ': '周目标已达成，达成率',
            'Week-over-week trend is ': '周环比趋势为',
            '. Requires improvement.': '，需改进。',
            'Weekly gap of ': '周差额 ',
            ' calls/agent below benchmark. Root cause: insufficient outbound attempts due to either (a) agent absenteeism, (b) low dialer efficiency, or (c) inadequate contact list coverage.': ' 通/人低于基准。可能原因：出勤不足、外呼效率低或名单覆盖不足。',
            ' minutes below benchmark. Root cause: poor contact quality — either (a) outdated phone numbers, (b) customers unreachable during working hours, or (c) ineffective calling scripts.': ' 分钟低于基准。可能原因：联系方式质量不足、工作时段难触达、或话术效果不佳。',
            '% below benchmark. Root cause: weak negotiation skills — agents failing to (a) secure firm payment commitments, (b) explain consequences of non-payment, or (c) schedule callbacks at convenient times.': '% 低于基准。可能原因：谈判能力不足（承诺确认、后果说明、回访预约）。',
            '% below benchmark. Root cause: either (a) low team morale, (b) inadequate attendance incentives, or (c) scheduling conflicts.': '% 低于基准。可能原因：士气偏低、激励不足或排班冲突。',
            ' group(s) with 3+ consecutive unmet weeks: ': ' 个连续3周以上未达标组：',
            '. Recommend immediate TL coaching intervention.': '。建议立即进行TL辅导干预。',
            'Summary: Underperformance driven by ': '总结：未达标主要由以下因素驱动：',
            '. STL should prioritize addressing these process gaps in weekly action plan.': '。建议STL在周行动计划中优先修复这些过程短板。'
        };

        function localizeText(text) {
            if (!text || currentLang !== 'zh') return text;
            let out = text;
            Object.keys(I18N_ZH).forEach(k => {
                out = out.split(k).join(I18N_ZH[k]);
            });
            out = out.replace(/MTD: /g, '当月累计：');
            out = out.replace(/Avg Daily Target Rate:/g, '日均目标回款率：');
            out = out.replace(/Natural Month Repay/g, '自然月回款');
            out = out.replace(/MTD Actual \(Day (\d+)\)/g, '当月累计实际（第$1天）');
            out = out.replace(/Daily Avg: /g, '日均：');
            out = out.replace(/7-Day Avg: /g, '7日均值：');
            out = out.replace(/Remaining Days: /g, '剩余天数：');
            out = out.replace(/Show All \((\d+)\)/g, '查看全部（$1）');
            return out;
        }

        function applyLanguage(root = document.body) {
            if (currentLang !== 'zh') return;
            if (!root) return;
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
            const nodes = [];
            let node = walker.nextNode();
            while (node) {
                const p = node.parentNode;
                const tag = p && p.tagName ? p.tagName.toUpperCase() : '';
                if (tag !== 'SCRIPT' && tag !== 'STYLE') nodes.push(node);
                node = walker.nextNode();
            }
            nodes.forEach(n => {
                n.nodeValue = localizeText(n.nodeValue);
            });
            document.title = localizeText(document.title);
        }

        function refreshLanguageButtons() {
            const enBtn = document.getElementById('lang-en');
            const zhBtn = document.getElementById('lang-zh');
            if (!enBtn || !zhBtn) return;
            enBtn.classList.toggle('active', currentLang === 'en');
            zhBtn.classList.toggle('active', currentLang === 'zh');
        }

        function rerenderCurrentRole() {
            if (currentRole === 'TL') {
                initTLView();
            } else if (currentRole === 'STL') {
                initSTLView();
            } else if (currentRole === 'Data') {
                initDataView();
                const activeSubtab = document.querySelector('.subtab-btn.active');
                if (activeSubtab && activeSubtab.id === 'subtab-trend') loadTrendData();
                else if (activeSubtab && activeSubtab.id === 'subtab-agent-overview') loadAgentOverviewData();
                else loadAnomalyData();
            }
        }

        function setLanguage(lang) {
            const next = (lang === 'zh') ? 'zh' : 'en';
            localStorage.setItem('collection_report_lang', next);
            if (next === currentLang) return;
            currentLang = next;
            refreshLanguageButtons();
            rerenderCurrentRole();
            if (currentLang === 'zh') {
                applyLanguage(document.body);
            } else {
                location.reload();
            }
        }

        function initLanguageToggle() {
            const saved = localStorage.getItem('collection_report_lang');
            currentLang = (saved === 'zh') ? 'zh' : 'en';
            refreshLanguageButtons();
            if (currentLang === 'zh') {
                applyLanguage(document.body);
                const observer = new MutationObserver(() => applyLanguage(document.body));
                observer.observe(document.body, { childList: true, subtree: true });
            }
        }
"""

html = html.replace(
    "        function isM2Module(module) {",
    i18n_inject + "\n\n        function isM2Module(module) {"
)

# Chart legend/series labels: switch by language at render time
html = html.replace("legend: { data: ['Actual', 'Daily Target'], bottom: 0, itemGap: 16, textStyle: { fontSize: 11 } },",
                    "legend: { data: [currentLang === 'zh' ? '实际值' : 'Actual', currentLang === 'zh' ? '日目标' : 'Daily Target'], bottom: 0, itemGap: 16, textStyle: { fontSize: 11 } },")
html = html.replace("name: 'Actual',", "name: currentLang === 'zh' ? '实际值' : 'Actual',")
html = html.replace("name: 'Daily Target',", "name: currentLang === 'zh' ? '日目标' : 'Daily Target',")
html = html.replace("const legendData = ['Module Target'];", "const legendData = [currentLang === 'zh' ? '模块目标' : 'Module Target'];")
html = html.replace("name: 'Module Target',", "name: currentLang === 'zh' ? '模块目标' : 'Module Target',")
html = html.replace("name: 'Module Total',", "name: currentLang === 'zh' ? '模块汇总' : 'Module Total',")
html = html.replace("legendData.unshift('Module Total');", "legendData.unshift(currentLang === 'zh' ? '模块汇总' : 'Module Total');")

html = html.replace(
    "        initTLView();",
    "        initLanguageToggle();\n        initTLView();\n        if (currentLang === 'zh') applyLanguage(document.body);"
)

# ========================
# Write output
# ========================
with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\nGenerated: {HTML_OUT}")
print(f"  Data date   : {TL_LATEST_STR}")
print(f"  Sub-modules : {modules_list}")
print(f"  Groups      : {len(all_groups)}")
print(f"  Anomalies   : {len(anomaly_groups)}")

# Trend cutoff checks: no actual daily trend point should be later than dataDate.
data_date_dt = pd.to_datetime(TL_LATEST_STR)
latest_tl_trend_dt = None
for g in all_groups:
    for d in tl_data_js.get(g, {}).get('days', []):
        # Cutoff applies to actual series only; full-month target series is expected.
        has_value = any(d.get(k) is not None for k in ('nmRepayRate', 'moduleRepayRate', 'repayRate'))
        if has_value:
            d_dt = pd.to_datetime(d['date'])
            latest_tl_trend_dt = d_dt if latest_tl_trend_dt is None or d_dt > latest_tl_trend_dt else latest_tl_trend_dt

latest_module_trend_dt = None
for mk in modules_list:
    for d in module_daily_js.get(mk, {}).get('daily', []):
        # Cutoff applies to actual module repay rate; targetRepayRate can extend to month end.
        has_value = d.get('repayRate') is not None
        if has_value:
            d_dt = pd.to_datetime(d['date'])
            latest_module_trend_dt = d_dt if latest_module_trend_dt is None or d_dt > latest_module_trend_dt else latest_module_trend_dt

tl_trend_cutoff_ok = (latest_tl_trend_dt is None) or (latest_tl_trend_dt <= data_date_dt)
module_trend_cutoff_ok = (latest_module_trend_dt is None) or (latest_module_trend_dt <= data_date_dt)

# Target/actual separation checks:
# - actual series must be None after dataDate day
# - targetRepayRate can remain available for the full month
post_cutoff_actual_ok = True
for g in all_groups:
    for d in tl_data_js.get(g, {}).get('days', []):
        d_dt = pd.to_datetime(d.get('date'), errors='coerce')
        if pd.isna(d_dt):
            continue
        day = d_dt.day
        if day > TL_LATEST_DAY and any(d.get(k) is not None for k in ('repayRate', 'nmRepayRate', 'moduleRepayRate')):
            post_cutoff_actual_ok = False
            break
    if not post_cutoff_actual_ok:
        break
if post_cutoff_actual_ok:
    for mk in modules_list:
        for d in module_daily_js.get(mk, {}).get('daily', []):
            d_dt = pd.to_datetime(d.get('date'), errors='coerce')
            if pd.isna(d_dt):
                continue
            day = d_dt.day
            if day > TL_LATEST_DAY and d.get('repayRate') is not None:
                post_cutoff_actual_ok = False
                break
        if not post_cutoff_actual_ok:
            break

# Target source consistency check:
# moduleDailyTrends.targetRepayRate should match target_nm_dict by module/day.
target_source_consistency_ok = True
TARGET_TOL = 1e-4
for mk in modules_list:
    bucket = module_key_to_bucket(mk)
    src_map = target_nm_dict.get(bucket, {})
    for d in module_daily_js.get(mk, {}).get('daily', []):
        d_dt = pd.to_datetime(d.get('date'), errors='coerce')
        if pd.isna(d_dt):
            continue
        day = d_dt.day
        got = d.get('targetRepayRate')
        exp = src_map.get(day, None)
        if got is None and exp is None:
            continue
        if got is None or exp is None:
            target_source_consistency_ok = False
            break
        if abs(float(got) - float(exp)) > TARGET_TOL:
            target_source_consistency_ok = False
            break
    if not target_source_consistency_ok:
        break

# Target coverage checks: verify moduleDailyTrends has full-month target rows for the data month.
# If upstream data doesn't provide future days' targets, charts will show nulls even if UI x-axis spans full month.
try:
    data_month_start = data_date_dt.replace(day=1)
    next_month = (data_month_start + pd.offsets.MonthBegin(1)).to_pydatetime()
    data_month_end = pd.to_datetime(next_month) - pd.Timedelta(days=1)
    month_days = pd.date_range(data_month_start, data_month_end, freq="D")
    expected_dates = set(d.strftime("%Y-%m-%d") for d in month_days)

    missing_targets_by_module = {}
    for mk in modules_list:
        rows = module_daily_js.get(mk, {}).get("daily", []) or []
        # Only consider rows in the data month
        month_rows = [r for r in rows if isinstance(r, dict) and r.get("date", "").startswith(TL_LATEST_STR[:7])]
        present_target_dates = set(
            r.get("date")
            for r in month_rows
            if r.get("targetRepayRate") is not None and r.get("date") is not None
        )
        missing = sorted(expected_dates - present_target_dates)
        if missing:
            missing_targets_by_module[mk] = missing

    if missing_targets_by_module:
        print("\nWARN: Natural month target is NOT full-month for some modules.")
        print("      This usually means upstream `natural_month_repay` does not include future dates' targets.")
        for mk, miss in missing_targets_by_module.items():
            sample = ", ".join(miss[:5]) + (" ..." if len(miss) > 5 else "")
            print(f"      - {mk}: missing targetRepayRate for {len(miss)} day(s). e.g. {sample}")
except Exception as e:
    print(f"\nWARN: Target coverage check skipped due to error: {e}")

# Verification checks
hard_checks = [
    ("Natural-month day-mix guard", nat_month_single_month_ok),
    ("TL actual trend <= dataDate", tl_trend_cutoff_ok),
    ("Module actual trend <= dataDate", module_trend_cutoff_ok),
    ("Actual hidden after dataDate", post_cutoff_actual_ok),
    ("Target source consistency", target_source_consistency_ok),
]

soft_checks = [
    ("Title v3.3",               'Collection Operations Report v3.3' in html),
    ("REAL_DATA present",        'const REAL_DATA = {' in html),
    ("No MOCK_DATA",             'MOCK_DATA.' not in html),
    ("No legacy moduleTarget var", "Math.round(moduleTarget)" not in html and "fill(moduleTarget)" not in html),
    ("No fixed target fill",     'Array(dates.length).fill' not in html),
    ("groupModule in data",      '"groupModule"' in html),
    ("nmRepayRate in data",      '"nmRepayRate"' in html),
    ("moduleRepayRate in data",  '"moduleRepayRate"' in html),
    ("repayRate in data",        '"repayRate"' in html),
    ("callLossRate in data",    '"callLossRate"' in html),
    ("ptpRate in data",         '"ptpRate"' in html),
    ("TL date selector",         'REAL_DATA.availableDates' in html),
    ("STL week selector",        'REAL_DATA.availableWeeks' in html),
    ("STL default week",        'REAL_DATA.defaultStlWeek' in html),
    ("PTP null-safe (agent)",   'displayPtp !== null' in html or 'agent.ptp !== null' in html),
    ("callLossRate in agent",   'agent.callLossRate' in html),
    ("callLossRate in stl week", 'displayCallLossRate' in html),
    ("TL call loss header",      'Call Loss</th>' in html and 'displayCallLossRate' in html),
    ("processTargets in data",   '"processTargets"' in html),
    ("module process benchmark", 'processTarget.artCallTimes' in html and 'processTarget.callBillminRawTarget' in html),
    ("STL gap cards",            'id=\"stl-call-gap\"' in html and 'id=\"stl-connect-gap\"' in html),
    ("STL trend title copy",     'Recovery Trend (Selected Month)' in html),
    ("STL week-end month logic", "const weekParts = weekLabel.split(' - ');" in html and "const monthStr = endPart.split('/')[0];" in html),
    ("validDays atRisk",        'const validDays = trendData' in html),
]
print("\nVerification:")
hard_ok = True
for name, ok in hard_checks:
    status = "HARD_OK" if ok else "HARD_FAIL"
    print(f"  [{status}] {name}")
    if not ok:
        hard_ok = False

soft_fail_cnt = 0
for name, ok in soft_checks:
    status = "SOFT_OK" if ok else "SOFT_WARN"
    print(f"  [{status}] {name}")
    if not ok:
        soft_fail_cnt += 1

if hard_ok and soft_fail_cnt == 0:
    print("\nAll checks passed (hard+soft).")
elif hard_ok:
    print(f"\nHard checks passed. Soft warnings: {soft_fail_cnt}.")
else:
    print("\nHard checks FAILED.")

input("\nPress Enter to close...")
