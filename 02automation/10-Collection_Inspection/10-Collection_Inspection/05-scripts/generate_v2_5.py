"""
Collection Operations Report v2.5 - Real Data v3
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
Output: Collection_Operations_Report_v2_5.html
"""
import pandas as pd
import json
import math
import re
from datetime import timedelta

# ========================
# Paths
# ========================
BASE       = r'd:/11automation/02automation/10-Collection_Inspection/10-Collection_Inspection'
EXCEL_PATH = BASE + r'/data/260318_output_automation_v3.xlsx'
HTML_IN    = BASE + r'/reports/Collection_Operations_Report_v2_2.html'
HTML_OUT   = BASE + r'/reports/Collection_Operations_Report_v2_5.html'

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

# ========================
# Key dates
# ========================
# TL daily cutoff:
# - keep data up to yesterday (exclude today)
# - align with TL core daily sheets (repay/performance/ptp)
# - do NOT let call_loss availability pull cutoff back one extra day
RUN_YESTERDAY_DT = (pd.Timestamp.now().normalize() - timedelta(days=1))
TL_CORE_MAX_DT = min(
    agent_perf['dt'].max(),
    agent_repay['dt'].max(),
    ptp_agent['dt'].max()
)
TL_LATEST_DT = min(TL_CORE_MAX_DT, RUN_YESTERDAY_DT)
TL_LATEST_STR = TL_LATEST_DT.strftime('%Y-%m-%d')
TL_LATEST_DAY = TL_LATEST_DT.day  # 21

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

# ========================
# Build derived structures
# ========================
all_groups         = sorted(tl_data['group_id'].unique().tolist())
tl_data['group_module'] = tl_data['group_id'].apply(extract_module_key)

submodule_groups = {}
for g in all_groups:
    mk = extract_module_key(g)
    submodule_groups.setdefault(mk, []).append(g)
modules_list = sorted(submodule_groups.keys())

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
DAYS_IN_MONTH = 31

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
        date_str = f'2026-03-{day:02d}'
        in_cutoff = day <= TL_LATEST_DAY
        day_rows = g_dtr[g_dtr.index.day == day]
        if len(day_rows) > 0:
            r   = day_rows.iloc[0]
            tgt = round(float(r['target'])) if in_cutoff else None
            act = round(float(r['actual'])) if in_cutoff else None
            owing = float(r['owing'])
            rr   = round(float(r['actual']) / owing * 100, 4) if (in_cutoff and owing > 0) else None
            nm_trr = module_target_nm.get(day, None) if in_cutoff else None
            nm_rr  = module_nm_daily.get(day, None) if in_cutoff else None
            g_nm_rr = group_nm_daily.get(day, None) if in_cutoff else None
            days_series.append({'date': date_str, 'target': tgt, 'actual': act,
                                 'repayRate': rr, 'nmRepayRate': g_nm_rr,
                                 'targetRepayRate': nm_trr, 'moduleRepayRate': nm_rr})
        else:
            nm_trr = module_target_nm.get(day, None) if in_cutoff else None
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

        # Call metrics from agent_performance (same day)
        ap_a = agent_perf[(agent_perf['group_id'] == group) &
                          (agent_perf['dt'] == TL_LATEST_DT) &
                          (agent_perf['agent_id'] == agent_name)]
        if len(ap_a) > 0:
            calls    = int(ap_a['call_times'].sum())
            connects = int(ap_a['connect_times'].sum())
            conn_r   = round(connects / calls * 100, 1) if calls > 0 else 0.0
            wh       = float(ap_a['work_hours'].mean()) if pd.notna(ap_a['work_hours']).any() else 0.0
            full_att = int(ap_a['is_full_attendance'].max()) if pd.notna(ap_a['is_full_attendance']).any() else 0
            attd     = 100 if full_att == 1 else min(100, round(wh / 8 * 100))
        else:
            calls = connects = 0; conn_r = 0.0; attd = 0

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
            'ptp':             ptp_val,
            'callLossRate':    cl_val,
            'attendance':       attd
        })

        # Daily repay drill-down history (linked to TL date selector)
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
        if len(gp_lw) > 0:
            tot_calls = float(gp_lw['total_calls'].iloc[0])
            tot_conn  = float(gp_lw['total_connect'].iloc[0])
            headcount = float(gp_lw['headcount'].iloc[0])
            calls_pa  = round(tot_calls / headcount) if headcount > 0 else 0
            conn_r    = round(tot_conn / tot_calls * 100, 1) if tot_calls > 0 else 0.0
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

valid_dtr_groups = {map_group_to_dtr(g) for g in all_groups}
anomaly_groups   = []
for dtr_group in daily_tr['owner_group'].unique():
    if dtr_group not in valid_dtr_groups:
        continue
    gdata_raw = daily_tr[daily_tr['owner_group'] == dtr_group]
    gdata_agg = (gdata_raw.groupby('dt', as_index=False)
                 .agg(target=('target_repay_principal', lambda x: x.astype(float).sum()),
                      actual=('actual_repay_principal', lambda x: x.astype(float).sum()))
                 .sort_values('dt'))
    gdata_agg['achieve_rate'] = gdata_agg.apply(
        lambda r: float(r['actual']) / float(r['target']) if float(r['target']) > 0 else 0.0, axis=1)
    module = dtr_to_submodule.get(dtr_group, '')
    streak = trailing_streak_df(gdata_agg)
    if streak >= 3:
        ld = gdata_agg[gdata_agg['dt'] == TL_LATEST_DT]
        if len(ld) == 0:
            ld = gdata_agg.tail(1)
        d_tgt = round(float(ld.iloc[0]['target']))
        d_act = round(float(ld.iloc[0]['actual']))
        m_tgt = round(float(gdata_agg['target'].sum()))
        m_act = round(float(gdata_agg['actual'].sum()))
        anomaly_groups.append({
            'name': dtr_group, 'module': module, 'days': streak,
            'dailyTarget': d_tgt, 'dailyActual': d_act,
            'mtdTarget': m_tgt, 'mtdActual': m_act
        })
anomaly_groups.sort(key=lambda x: -x['days'])

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
        date_str = f'2026-03-{day:02d}'
        in_cutoff = day <= TL_LATEST_DAY
        nm_rr  = mk_nm_daily.get(day, None) if in_cutoff else None
        nm_trr = module_target_nm.get(day, None) if in_cutoff else None
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
    'anomalyAgents':     [],
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
html = html.replace(
    "            const selectedMonth = selectedDate ? selectedDate.slice(0, 7) : ''; // YYYY-MM",
    "            const selectedMonth = selectedDate ? selectedDate.slice(0, 7) : ''; // YYYY-MM\n            const cutoffDate = REAL_DATA.dataDate;"
)
html = html.replace(
    "                monthData = REAL_DATA.tlData[allGroupsInModule[0]].days.filter(d => d.date.startsWith(selectedMonth));",
    "                monthData = REAL_DATA.tlData[allGroupsInModule[0]].days.filter(d => d.date.startsWith(selectedMonth) && d.date <= cutoffDate);"
)
html = html.replace(
    "                const filteredDays = groupData.days.filter(d => d.date.startsWith(selectedMonth));",
    "                const filteredDays = groupData.days.filter(d => d.date.startsWith(selectedMonth) && d.date <= cutoffDate);"
)

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
    "            // Generate daily data for the selected month (like TL does for daily trend)\n            // Generate dates for the month of selected week\n            const today = new Date();\n            const currentYear = today.getFullYear();\n            const month = parseInt(monthStr) - 1; // 0-indexed\n            const daysInMonth = new Date(currentYear, month + 1, 0).getDate();\n\n            const dates = [];",
    "            // Use selected month data up to dataDate cutoff\n            const cutoffDate = REAL_DATA.dataDate;\n            const dates = [];"
)
html = html.replace(
    "            // Get daily data from moduleDailyTrends (contains natural month repay target)\n            const trendData = REAL_DATA.moduleDailyTrends[module];\n            const dailyData = trendData ? trendData.daily : [];\n\n            for (let d = 1; d <= daysInMonth; d++) {\n                const dateStr = (month + 1).toString().padStart(2, '0') + '/' + d.toString().padStart(2, '0');\n                dates.push(dateStr);\n            }",
    "            // Get daily data from moduleDailyTrends (contains natural month repay target)\n            const trendData = REAL_DATA.moduleDailyTrends[module];\n            const selectedYearMonth = REAL_DATA.dataDate.slice(0, 4) + '-' + monthStr.padStart(2, '0');\n            const dailyData = trendData ? trendData.daily.filter(d => d.date.startsWith(selectedYearMonth) && d.date <= cutoffDate) : [];\n            dailyData.forEach(d => dates.push(d.date.slice(5)));"
)

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

# ---- 20. Agent TL table: PTP null-safe + Call Loss Rate column ----
# TL drill-down metrics linked to selected date
html = html.replace(
    "                const achColor = agent.achievement >= 100 ? '#22c55e' : '#ef4444';",
    "                const selectedDate = document.getElementById('tl-date-select') ? document.getElementById('tl-date-select').value : REAL_DATA.dataDate;\n                const dateMetrics = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][agent.name] ? REAL_DATA.agentPerformanceByDate[group][agent.name][selectedDate] : null;\n                const displayTarget = dateMetrics && dateMetrics.target !== undefined ? dateMetrics.target : agent.target;\n                const displayActual = dateMetrics && dateMetrics.actual !== undefined ? dateMetrics.actual : agent.actual;\n                const displayAchievement = dateMetrics && dateMetrics.achievement !== undefined ? dateMetrics.achievement : agent.achievement;\n                const achColor = displayAchievement >= 100 ? '#22c55e' : '#ef4444';"
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
# PTP null-safe
html = html.replace(
    "agent.ptp.toFixed(1) + '%</td>' +",
    "(agent.ptp !== null && agent.ptp !== undefined ? agent.ptp.toFixed(1) + '%' : '--') + '</td>' +"
)
# Add Call Loss column header
old_agent_header = "                    <th style=\"padding: 12px; text-align: right; background: #f1f5f9;\">Attendance</th>"
new_agent_header = """                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Attendance</th>
                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Call Loss</th>"""
html = html.replace(old_agent_header, new_agent_header)
# Add Call Loss cell
old_cl_td = "                    '<td style=\"padding: 12px; text-align: right;\">' + agent.attendance + '%</td>' +\n                    '</tr>';"
new_cl_td = "                    '<td style=\"padding: 12px; text-align: right;\">' + agent.attendance + '%</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + (agent.callLossRate !== null && agent.callLossRate !== undefined ? agent.callLossRate.toFixed(1) + '%' : '--') + '</td>' +\n                    '</tr>';"
html = html.replace(old_cl_td, new_cl_td)

# ---- 21. STL group table: PTP null-safe + Call Loss column ----
html = html.replace(
    "                const cw = group.consecutiveWeeks;",
    "                const selectedWeekLabel = document.getElementById('stl-week-select') ? document.getElementById('stl-week-select').value : REAL_DATA.defaultStlWeek;\n                const cwMap = REAL_DATA.groupConsecutiveWeeksByWeek && REAL_DATA.groupConsecutiveWeeksByWeek[module] && REAL_DATA.groupConsecutiveWeeksByWeek[module][group.name] ? REAL_DATA.groupConsecutiveWeeksByWeek[module][group.name] : null;\n                const cw = cwMap && cwMap[selectedWeekLabel] !== undefined ? cwMap[selectedWeekLabel] : group.consecutiveWeeks;"
)
html = html.replace(
    "                const achColor = group.achievement >= 100 ? '#22c55e' : '#ef4444';",
    "                const weekMetrics = REAL_DATA.groupPerformanceByWeek && REAL_DATA.groupPerformanceByWeek[module] && REAL_DATA.groupPerformanceByWeek[module][group.name] ? REAL_DATA.groupPerformanceByWeek[module][group.name][selectedWeekLabel] : null;\n                const displayTarget = weekMetrics && weekMetrics.target !== undefined ? weekMetrics.target : group.target;\n                const displayActual = weekMetrics && weekMetrics.actual !== undefined ? weekMetrics.actual : group.actual;\n                const displayAchievement = weekMetrics && weekMetrics.achievement !== undefined ? weekMetrics.achievement : group.achievement;\n                const achColor = displayAchievement >= 100 ? '#22c55e' : '#ef4444';"
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
    "group.ptpRate.toFixed(1) + '%</td>' +",
    "(group.ptpRate !== null && group.ptpRate !== undefined ? group.ptpRate.toFixed(1) + '%' : '--') + '</td>' +"
)
old_stl_grp_header = "                    <th style=\"padding: 12px; text-align: right; background: #f1f5f9;\">Attendance</th>"
new_stl_grp_header = """                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Call Loss</th>
                    <th style="padding: 12px; text-align: right; background: #f1f5f9;">Attendance</th>"""
html = html.replace(old_stl_grp_header, new_stl_grp_header)
old_stl_grp_footer = "                    '<td style=\"padding: 12px; text-align: right;\">' + group.attendance + '%</td>' +\n                    '</tr>';"
new_stl_grp_footer = "                    '<td style=\"padding: 12px; text-align: right;\">' + (group.callLossRate !== null && group.callLossRate !== undefined ? group.callLossRate.toFixed(1) + '%' : '--') + '</td>' +\n                    '<td style=\"padding: 12px; text-align: right;\">' + group.attendance + '%</td>' +\n                    '</tr>';"
html = html.replace(old_stl_grp_footer, new_stl_grp_footer)

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
                const avgCalls = groups.reduce((sum, g) => sum + g.calls, 0) / groups.length;
                const avgConnectRate = groups.reduce((sum, g) => sum + g.connectRate, 0) / groups.length;
                const avgPtpRate = groups.reduce((sum, g) => sum + g.ptpRate, 0) / groups.length;
                const avgAttendance = groups.reduce((sum, g) => sum + g.attendance, 0) / groups.length;"""
new_ptp_avg = """\
                const avgCalls = groups.reduce((sum, g) => sum + g.calls, 0) / groups.length;
                const avgConnectRate = groups.reduce((sum, g) => sum + g.connectRate, 0) / groups.length;
                const validPtpGroups = groups.filter(g => g.ptpRate !== null && g.ptpRate !== undefined);
                const avgPtpRate = validPtpGroups.length > 0 ? validPtpGroups.reduce((sum, g) => sum + g.ptpRate, 0) / validPtpGroups.length : 999;
                const avgAttendance = groups.reduce((sum, g) => sum + g.attendance, 0) / groups.length;"""
html = html.replace(old_ptp_avg, new_ptp_avg)

# ---- 24. calculateAtRisk: null-safe 7/3 day trend ----
old_atrisk_pat = (
    r'Projection 2: Conservative - use last 7 days average if available\s+'
    r'const trendData = REAL_DATA\.moduleDailyTrends\[module\];\s+'
    r'let dailyTrend = dailyAvg;\s+'
    r'if \(trendData && trendData\.daily\.length >= 7\) \{[^}]+\}\s+'
    r'const projectedConservative[^;]+;\s+'
    r'// Projection 3[^}]+\} else \{\s+'
    r'var projectedMomentum = projectedSimple;\s+\}'
)
new_atrisk_trend = (
    "Projection 2: Conservative - use last 7 days (null-safe)\n"
    "            const trendData = REAL_DATA.moduleDailyTrends[module];\n"
    "            const validDays = trendData ? trendData.daily.filter(d => d.actual !== null && d.actual !== undefined) : [];\n"
    "            let dailyTrend = dailyAvg;\n"
    "            if (validDays.length >= 7) {\n"
    "                const last7Days = validDays.slice(-7);\n"
    "                dailyTrend = last7Days.reduce((sum, d) => sum + d.actual, 0) / 7;\n"
    "            } else if (validDays.length > 0) {\n"
    "                dailyTrend = validDays.reduce((sum, d) => sum + d.actual, 0) / validDays.length;\n"
    "            }\n"
    "            const projectedConservative = mData.currentActual + (dailyTrend * remainingDays);\n\n"
    "            // Projection 3: Aggressive - use last 3 days (null-safe)\n"
    "            var projectedMomentum = projectedSimple;\n"
    "            if (validDays.length >= 3) {\n"
    "                const last3Days = validDays.slice(-3);\n"
    "                const dailyMomentum = last3Days.reduce((sum, d) => sum + d.actual, 0) / 3;\n"
    "                projectedMomentum = mData.currentActual + (dailyMomentum * remainingDays);\n"
    "            }"
)
html = re.sub(old_atrisk_pat, new_atrisk_trend, html, flags=re.DOTALL)

# ---- TL table/group sorting + selected line highlight ----
# 1) TL agent drill-down table: sort by achievement (ascending, worst first)
html = html.replace(
    "            const agents = REAL_DATA.agentPerformance[group] || [];\n",
    "            const agents = REAL_DATA.agentPerformance[group] || [];\n            agents.sort((a, b) => {\n                const av = (a.achievement !== null && a.achievement !== undefined) ? a.achievement : 999;\n                const bv = (b.achievement !== null && b.achievement !== undefined) ? b.achievement : 999;\n                return av - bv;\n            });\n"
)

# 2) STL group drill-down table: sort by achievement (ascending, worst first)
html = html.replace(
    "            const groups = REAL_DATA.groupPerformance[module] || [];\n",
    "            const groups = REAL_DATA.groupPerformance[module] || [];\n            groups.sort((a, b) => {\n                const av = (a.achievement !== null && a.achievement !== undefined) ? a.achievement : 999;\n                const bv = (b.achievement !== null && b.achievement !== undefined) ? b.achievement : 999;\n                return av - bv;\n            });\n"
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

# ---- 25. Title ----
html = html.replace('Collection Operations Report v2.2', 'Collection Operations Report v2.5')

# ---- 26. Data date ----
html = html.replace(
    "document.getElementById('data-date').textContent = new Date(Date.now() - 86400000).toISOString().split('T')[0];",
    f"document.getElementById('data-date').textContent = REAL_DATA.dataDate;"
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

# Trend cutoff checks: no daily trend point should be later than dataDate.
data_date_dt = pd.to_datetime(TL_LATEST_STR)
latest_tl_trend_dt = None
for g in all_groups:
    for d in tl_data_js.get(g, {}).get('days', []):
        has_value = any(d.get(k) is not None for k in ('nmRepayRate', 'moduleRepayRate', 'targetRepayRate', 'repayRate'))
        if has_value:
            d_dt = pd.to_datetime(d['date'])
            latest_tl_trend_dt = d_dt if latest_tl_trend_dt is None or d_dt > latest_tl_trend_dt else latest_tl_trend_dt

latest_module_trend_dt = None
for mk in modules_list:
    for d in module_daily_js.get(mk, {}).get('daily', []):
        has_value = any(d.get(k) is not None for k in ('repayRate', 'targetRepayRate'))
        if has_value:
            d_dt = pd.to_datetime(d['date'])
            latest_module_trend_dt = d_dt if latest_module_trend_dt is None or d_dt > latest_module_trend_dt else latest_module_trend_dt

tl_trend_cutoff_ok = (latest_tl_trend_dt is None) or (latest_tl_trend_dt <= data_date_dt)
module_trend_cutoff_ok = (latest_module_trend_dt is None) or (latest_module_trend_dt <= data_date_dt)

# Verification checks
checks = [
    ("Title v2.5",               'Collection Operations Report v2.5' in html),
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
    ("PTP null-safe (agent)",   'agent.ptp !== null' in html),
    ("callLossRate in agent",   'agent.callLossRate' in html),
    ("validDays atRisk",        'const validDays = trendData' in html),
    ("TL trend <= dataDate",    tl_trend_cutoff_ok),
    ("Module trend <= dataDate", module_trend_cutoff_ok),
]
print("\nVerification:")
all_ok = True
for name, ok in checks:
    status = "OK" if ok else "FAIL"
    print(f"  [{status}] {name}")
    if not ok:
        all_ok = False

if all_ok:
    print("\nAll checks passed.")
else:
    print("\nSome checks FAILED.")

input("\nPress Enter to close...")
