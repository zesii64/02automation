"""
Collection Operations Report v2.5 - Natural Month Repay Trend
Base: Collection_Operations_Report_v2_4.html
Data: 260318_output_automation_v3.xlsx (new Target group in natural_month_repay)

Changes vs v2.4:
  1. STL chart title: "Weekly Recovery Trend (12 Weeks)" -> "Recovery Trend"
  2. TL/STL/Data recovery trend charts: use natural_month_repay repay_rate for actual lines
  3. Target dashed line in all recovery trend charts: natural_month_repay group_name=Target
     (matched by module bucket, e.g. "M1-Large" -> agent_bucket "M1_Large")
  4. TL/STL metric cards (target amount, actual, achievement rate): still use daily_target_repay
  5. TL chart target line: changed from flat constant to daily cumulative series
  6. Auto-select first group/module in TL/STL views

Output: Collection_Operations_Report_v2_5.html
"""
import pandas as pd
import json
import math
import re
from datetime import datetime, timedelta

# ========================
# Paths
# ========================
BASE       = r'd:/11automation/02automation/10-Collection_Inspection/10-Collection_Inspection'
EXCEL_PATH = BASE + r'/data/260318_output_automation_v3.xlsx'
HTML_IN    = BASE + r'/reports/Collection_Operations_Report_v2_4.html'
HTML_OUT   = BASE + r'/reports/Collection_Operations_Report_v2_5.html'

# ========================
# Load data
# ========================
print("Loading Excel data...")
xl         = pd.ExcelFile(EXCEL_PATH)
tl_data    = pd.read_excel(xl, 'tl_data',             index_col=0)
stl_data   = pd.read_excel(xl, 'stl_data',            index_col=0)
agent_perf = pd.read_excel(xl, 'agent_performance',   index_col=0)
group_perf = pd.read_excel(xl, 'group_performance',   index_col=0)
daily_tr   = pd.read_excel(xl, 'daily_target_repay',  index_col=0)
nat_month  = pd.read_excel(xl, 'natural_month_repay', index_col=0)

# Strip whitespace
for df in [tl_data, agent_perf, group_perf]:
    df['group_id'] = df['group_id'].str.strip()
daily_tr['owner_group'] = daily_tr['owner_group'].str.strip()
group_perf['week']      = group_perf['week'].astype(str)

# Parse dates
tl_data['dt']       = pd.to_datetime(tl_data['dt'])
daily_tr['dt']      = pd.to_datetime(daily_tr['dt'])
nat_month['dt_biz'] = pd.to_datetime(nat_month['dt_biz'])
agent_perf['dt']    = pd.to_datetime(agent_perf['dt'])

latest_dt     = tl_data['dt'].max()
LATEST_DT_STR = latest_dt.strftime('%Y-%m-%d')
LATEST_DAY    = latest_dt.day
DAYS_IN_MONTH = 31   # March 2026

all_groups      = sorted(tl_data['group_id'].unique().tolist())
available_dates = sorted([d.strftime('%Y-%m-%d') for d in tl_data['dt'].unique()], reverse=True)

print(f"  Latest date : {LATEST_DT_STR}")
print(f"  Groups      : {len(all_groups)}")

# ========================
# natural_month_repay processing
# ========================
print("Processing natural_month_repay...")
nat_month['group_name']   = nat_month['group_name'].str.strip()
nat_month['agent_bucket'] = nat_month['agent_bucket'].str.strip()
nat_month['day']          = nat_month['dt_biz'].dt.day

# Target rows: {agent_bucket: {day: repay_rate * 100}}
target_nm = nat_month[nat_month['group_name'] == 'Target']
target_nm_dict = {}
for _, row in target_nm.iterrows():
    bucket = row['agent_bucket']
    day    = int(row['day'])
    rr     = float(row['repay_rate']) * 100
    target_nm_dict.setdefault(bucket, {})[day] = round(rr, 4)

# Non-target group rows: {group_name: {day: repay_rate * 100}}
nontar_nm = nat_month[nat_month['group_name'] != 'Target']
group_nm_dict = {}
for gn in nontar_nm['group_name'].unique():
    gdata = nontar_nm[nontar_nm['group_name'] == gn]
    group_nm_dict[gn] = {}
    for _, row in gdata.iterrows():
        day = int(row['day'])
        rr  = float(row['repay_rate']) * 100
        group_nm_dict[gn][day] = round(rr, 4)

print(f"  Target buckets in natural_month_repay: {sorted(target_nm_dict.keys())}")
print(f"  Non-target groups: {len(group_nm_dict)}")

def module_key_to_bucket(mk):
    """Map sub-module key to natural_month_repay agent_bucket for Target lookup.
    e.g. "M1-Large" -> "M1_Large", "S0" -> "S0", "M2" -> "M2"
    """
    return mk.replace('-', '_')

# ========================
# S0 group name mapping: tl_data -> daily_target_repay
#   "S0- A Module" -> "S0-A Bucket"
# ========================
def map_group_to_dtr(group):
    g = group.strip()
    if g.startswith('S0-'):
        remainder = g[3:].strip()
        letter    = remainder.split()[0]
        return f'S0-{letter} Bucket'
    return g

# ========================
# Sub-module key extraction
#   "M1-Large A" -> "M1-Large"
#   "M1-Small A" -> "M1-Small"
#   "S0- A Module" -> "S0"
#   "S1-Large A"  -> "S1-Large"
# ========================
def extract_module_key(group):
    g     = group.strip()
    parts = g.split('-')
    if len(parts) >= 2:
        first_word = parts[1].strip().split()[0].lower() if parts[1].strip() else ''
        if first_word in ('large', 'small'):
            return f"{parts[0]}-{parts[1].strip().split()[0].capitalize()}"
    return parts[0]

# Build sub-module mappings
submodule_groups = {}
for g in all_groups:
    mk = extract_module_key(g)
    submodule_groups.setdefault(mk, []).append(g)

modules_list = sorted(submodule_groups.keys())

# Sub-module -> set of DTR owner_group names
submodule_dtr_groups = {
    mk: {map_group_to_dtr(g) for g in groups}
    for mk, groups in submodule_groups.items()
}

# DTR group name -> sub-module key
dtr_to_submodule = {map_group_to_dtr(g): extract_module_key(g) for g in all_groups}

print(f"  Sub-modules : {modules_list}")

# ========================
# Module-level natural_month_repay aggregate
#   {module_key: {day: weighted_aggregate_rate * 100}}
#   Weighted: sum(repay_principal) / sum(start_owing_principal)
# ========================
module_nm_dict = {}
for mk in modules_list:
    mk_groups  = [g.strip() for g in submodule_groups[mk]]
    mk_nm      = nontar_nm[nontar_nm['group_name'].isin(mk_groups)]
    module_nm_dict[mk] = {}
    for day, day_data in mk_nm.groupby('day'):
        total_repay = day_data['repay_principal'].astype(float).sum()
        total_owing = day_data['start_owing_principal'].astype(float).sum()
        rr = total_repay / total_owing * 100 if total_owing > 0 else 0.0
        module_nm_dict[mk][int(day)] = round(rr, 4)

# ========================
# Week label helpers
# ========================
def get_week_label(dt):
    dow            = dt.dayofweek           # 0=Mon, 6=Sun
    days_since_sun = (dow + 1) % 7
    week_start     = dt - timedelta(days=int(days_since_sun))
    week_end       = week_start + timedelta(days=6)
    return f"{week_start.strftime('%Y-%m-%d')}-{week_end.strftime('%Y-%m-%d')}"

def week_str_to_display(week_str):
    p = week_str.split('-')
    return f"{p[1]}/{p[2]} - {p[4]}/{p[5]}"

daily_tr['week'] = daily_tr['dt'].apply(get_week_label)

# ========================
# Latest-day sub-module avg achievement (from daily_target_repay)
# ========================
latest_dtr     = daily_tr[daily_tr['dt'] == latest_dt]
module_avg_ach = {}
for mk, dtr_groups in submodule_dtr_groups.items():
    m = latest_dtr[latest_dtr['owner_group'].isin(dtr_groups)]
    if len(m) > 0:
        t = m['target_repay_principal'].astype(float).sum()
        a = m['actual_repay_principal'].astype(float).sum()
        module_avg_ach[mk] = round(a / t * 100, 1) if t > 0 else 0.0
    else:
        module_avg_ach[mk] = 0.0

# Pre-compute group_module column
tl_data['group_module'] = tl_data['group_id'].apply(extract_module_key)

# ========================
# 1. TL DATA
#    - Metric cards (target/actual/achievement): from daily_target_repay
#    - days[].repayRate: from natural_month_repay (group-level cumulative rate)
#    - days[].targetRepayRate: from natural_month_repay Target (module bucket)
# ========================
print("Building tlData...")
tl_data_js = {}
for group in all_groups:
    group_rows   = tl_data[tl_data['group_id'] == group]
    group_module = extract_module_key(group)
    dtr_name     = map_group_to_dtr(group)

    # Latest-day repay metrics (from daily_target_repay) -> metric cards
    latest_g_dtr = daily_tr[(daily_tr['owner_group'] == dtr_name) & (daily_tr['dt'] == latest_dt)]
    if len(latest_g_dtr) > 0:
        target      = float(latest_g_dtr['target_repay_principal'].astype(float).sum())
        actual      = float(latest_g_dtr['actual_repay_principal'].astype(float).sum())
        achievement = round(actual / target * 100, 1) if target > 0 else 0.0
        gap         = max(0.0, target - actual)
    else:
        target = actual = achievement = gap = 0.0

    # Call metrics vs sub-module avg (latest day)
    latest_tl_g = group_rows[group_rows['dt'] == latest_dt]
    module_tl   = tl_data[(tl_data['group_module'] == group_module) & (tl_data['dt'] == latest_dt)]
    if len(latest_tl_g) > 0 and len(module_tl) > 0:
        g_calls     = float(latest_tl_g['total_calls'].iloc[0])
        g_conn      = float(latest_tl_g['connect_rate'].iloc[0]) * 100
        avg_calls   = float(module_tl['total_calls'].mean())
        avg_conn    = float(module_tl['connect_rate'].mean()) * 100
        call_gap    = round(g_calls - avg_calls)
        connect_gap = round(g_conn - avg_conn, 1)
    else:
        call_gap = connect_gap = 0

    # 31-day series: target/actual amounts from DTR; repayRate/targetRepayRate from natural_month_repay
    g_dtr    = daily_tr[daily_tr['owner_group'] == dtr_name]
    dtr_dict = {}
    for _, row in g_dtr.iterrows():
        tgt = round(float(row['target_repay_principal']))
        act = round(float(row['actual_repay_principal']))
        dtr_dict[row['dt'].day] = (tgt, act)

    # Natural month repay for this group and module target
    group_nm_data    = group_nm_dict.get(group.strip(), {})
    module_bucket    = module_key_to_bucket(group_module)
    module_target_nm = target_nm_dict.get(module_bucket, {})

    days_series = []
    for day in range(1, DAYS_IN_MONTH + 1):
        date_str = f'2026-03-{day:02d}'
        nm_rr  = group_nm_data.get(day, None)       # actual cumulative rate from nat month repay
        nm_trr = module_target_nm.get(day, None)    # target cumulative rate from nat month repay
        if day in dtr_dict:
            days_series.append({
                'date':            date_str,
                'target':          dtr_dict[day][0],
                'actual':          dtr_dict[day][1],
                'repayRate':       nm_rr,
                'targetRepayRate': nm_trr
            })
        else:
            days_series.append({
                'date':            date_str,
                'target':          None,
                'actual':          None,
                'repayRate':       nm_rr,
                'targetRepayRate': nm_trr
            })

    tl_data_js[group] = {
        'groupModule': group_module,
        'target':      round(target),
        'actual':      round(actual),
        'achievement': achievement,
        'moduleAvg':   module_avg_ach.get(group_module, 0.0),
        'gap':         round(gap),
        'callGap':     call_gap,
        'connectGap':  connect_gap,
        'days':        days_series
    }

# ========================
# 2. STL DATA (metric cards from daily_target_repay — unchanged)
# ========================
print("Building stlData...")
stl_data_js = {}
for mk in modules_list:
    dtr_groups = submodule_dtr_groups.get(mk, set())
    module_dtr = daily_tr[daily_tr['owner_group'].isin(dtr_groups)]

    if len(module_dtr) == 0:
        stl_data_js[mk] = {
            'target': 0, 'actual': 0, 'achievement': 0.0,
            'lastWeek': 0, 'trend': 'N/A', 'gap': 0, 'weeks': []
        }
        continue

    weekly = (module_dtr.groupby('week')
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
        lw         = {'target': 0, 'actual': 0, 'achievement': 0.0}
        trend_str  = 'N/A'
        latest_gap = 0

    stl_data_js[mk] = {
        'target':      lw['target'],
        'actual':      lw['actual'],
        'achievement': lw['achievement'],
        'lastWeek':    weeks_list[-2]['actual'] if len(weeks_list) > 1 else 0,
        'trend':       trend_str,
        'gap':         round(latest_gap),
        'weeks':       weeks_list
    }

# ========================
# 3. AGENT PERFORMANCE (achievement/target/actual = null - no agent-level repay data)
# ========================
print("Building agentPerformance...")
agent_perf_js = {}
for group in all_groups:
    group_agents = agent_perf[(agent_perf['group_id'] == group) & (agent_perf['dt'] == latest_dt)]
    agent_agg    = (group_agents.groupby('agent_id')
                   .agg(work_hours        =('work_hours',         'first'),
                        is_full_attendance=('is_full_attendance', 'max'),
                        call_times        =('call_times',         'sum'),
                        connect_times     =('connect_times',      'sum'))
                   .reset_index())
    agents_list = []
    for _, a in agent_agg.iterrows():
        calls    = int(a['call_times'])
        connects = int(a['connect_times'])
        conn_r   = round(connects / calls * 100, 1) if calls > 0 else 0.0
        wh       = float(a['work_hours']) if pd.notna(a['work_hours']) else 0.0
        full_att = int(a['is_full_attendance']) if pd.notna(a['is_full_attendance']) else 0
        attd     = 100 if full_att == 1 else min(100, round(wh / 8 * 100))
        agents_list.append({
            'name':            str(a['agent_id']),
            'consecutiveDays': 0,
            'target':          None,
            'actual':          None,
            'achievement':     None,
            'calls':           calls,
            'connectRate':     conn_r,
            'ptp':             None,
            'attendance':      attd
        })
    agent_perf_js[group] = agents_list

# ========================
# 4. GROUP PERFORMANCE (by sub-module)
# ========================
print("Building groupPerformance...")
group_perf_js = {}
for mk in modules_list:
    mk_groups = submodule_groups.get(mk, [])

    gp_mk           = group_perf[group_perf['group_id'].isin(mk_groups)]
    latest_week_str = gp_mk['week'].max() if len(gp_mk) > 0 else None

    groups_list = []
    for group in mk_groups:
        dtr_name = map_group_to_dtr(group)

        if latest_week_str and latest_week_str != 'nan':
            try:
                wp   = latest_week_str.split('-')
                ws   = pd.Timestamp(f"{wp[0]}-{wp[1]}-{wp[2]}")
                we   = pd.Timestamp(f"{wp[3]}-{wp[4]}-{wp[5]}")
                gdtr = daily_tr[(daily_tr['owner_group'] == dtr_name) &
                                (daily_tr['dt'] >= ws) & (daily_tr['dt'] <= we)]
            except Exception:
                gdtr = pd.DataFrame()
        else:
            gdtr = pd.DataFrame()

        if len(gdtr) > 0:
            w_tgt = float(gdtr['target_repay_principal'].astype(float).sum())
            w_act = float(gdtr['actual_repay_principal'].astype(float).sum())
            w_ach = round(w_act / w_tgt * 100, 1) if w_tgt > 0 else 0.0
        else:
            w_tgt = w_act = w_ach = 0.0

        gp_lw = (group_perf[(group_perf['group_id'] == group) & (group_perf['week'] == latest_week_str)]
                 if latest_week_str and latest_week_str != 'nan' else pd.DataFrame())
        if len(gp_lw) > 0:
            tot_calls = float(gp_lw['total_calls'].iloc[0])
            tot_conn  = float(gp_lw['total_connect'].iloc[0])
            headcount = float(gp_lw['headcount'].iloc[0])
            calls_pa  = round(tot_calls / headcount) if headcount > 0 else 0
            conn_r    = round(tot_conn / tot_calls * 100, 1) if tot_calls > 0 else 0.0
            gtl = tl_data[(tl_data['group_id'] == group) & (tl_data['dt'] == latest_dt)]
            if len(gtl) > 0:
                owner = float(gtl['ownercount'].iloc[0])
                head  = float(gtl['headcount'].iloc[0])
                attd  = round(head / owner * 100) if owner > 0 else 0
            else:
                attd = 0
        else:
            calls_pa = conn_r = attd = 0

        groups_list.append({
            'name':             group,
            'consecutiveWeeks': 0,
            'target':           round(w_tgt),
            'actual':           round(w_act),
            'achievement':      w_ach,
            'calls':            calls_pa,
            'connectRate':      conn_r,
            'ptpRate':          None,
            'attendance':       attd
        })
    group_perf_js[mk] = groups_list

# ========================
# 5. ANOMALY GROUPS (from daily_target_repay — unchanged)
# ========================
print("Building anomalyGroups...")
def trailing_streak(df):
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
    gdata  = daily_tr[daily_tr['owner_group'] == dtr_group].sort_values('dt')
    module = dtr_to_submodule.get(dtr_group, gdata['owner_bucket'].iloc[0])
    streak = trailing_streak(gdata)
    if streak >= 3:
        ld    = gdata[gdata['dt'] == latest_dt]
        if len(ld) == 0:
            ld = gdata.tail(1)
        d_tgt = float(ld['target_repay_principal'].astype(float).sum())
        d_act = float(ld['actual_repay_principal'].astype(float).sum())
        m_tgt = float(gdata['target_repay_principal'].astype(float).sum())
        m_act = float(gdata['actual_repay_principal'].astype(float).sum())
        anomaly_groups.append({
            'name':        dtr_group,
            'module':      module,
            'days':        streak,
            'dailyTarget': round(d_tgt),
            'dailyActual': round(d_act),
            'mtdTarget':   round(m_tgt),
            'mtdActual':   round(m_act)
        })
anomaly_groups.sort(key=lambda x: -x['days'])

# ========================
# 6. MODULE DAILY TRENDS
#    - target/actual amounts: from daily_target_repay (used by at-risk projection etc.)
#    - repayRate: from natural_month_repay module aggregate
#    - targetRepayRate: from natural_month_repay Target (module bucket)
# ========================
print("Building moduleDailyTrends...")
module_daily_js = {}
for mk in modules_list:
    dtr_groups = submodule_dtr_groups.get(mk, set())
    m_dtr = (daily_tr[daily_tr['owner_group'].isin(dtr_groups)]
             .groupby('dt')
             .agg(target=('target_repay_principal', lambda x: x.astype(float).sum()),
                  actual=('actual_repay_principal', lambda x: x.astype(float).sum()),
                  owing =('daily_owing_principal',  lambda x: x.astype(float).sum()))
             .reset_index().sort_values('dt'))

    dtr_day = {}
    for _, row in m_dtr.iterrows():
        tgt = round(float(row['target']))
        act = round(float(row['actual']))
        dtr_day[row['dt'].day] = (tgt, act)

    # Natural month repay for module aggregate and Target
    module_bucket    = module_key_to_bucket(mk)
    module_target_nm = target_nm_dict.get(module_bucket, {})
    mk_nm_daily      = module_nm_dict.get(mk, {})

    daily_series = []
    for day in range(1, DAYS_IN_MONTH + 1):
        date_str = f'2026-03-{day:02d}'
        nm_rr  = mk_nm_daily.get(day, None)       # module aggregate actual rate
        nm_trr = module_target_nm.get(day, None)  # module target rate
        if day in dtr_day:
            daily_series.append({
                'date':            date_str,
                'target':          dtr_day[day][0],
                'actual':          dtr_day[day][1],
                'repayRate':       nm_rr,
                'targetRepayRate': nm_trr
            })
        else:
            daily_series.append({
                'date':            date_str,
                'target':          None,
                'actual':          None,
                'repayRate':       nm_rr,
                'targetRepayRate': nm_trr
            })
    module_daily_js[mk] = {'daily': daily_series}

# ========================
# 7. MODULE MONTHLY (for At-Risk calculation — unchanged)
# ========================
print("Building moduleMonthly...")
module_monthly_js = {}
for mk in modules_list:
    dtr_groups = submodule_dtr_groups.get(mk, set())
    m_dtr      = daily_tr[daily_tr['owner_group'].isin(dtr_groups)]
    if len(m_dtr) > 0:
        unique_days   = m_dtr['dt'].nunique()
        total_tgt     = m_dtr['target_repay_principal'].astype(float).sum()
        avg_daily_tgt = total_tgt / unique_days if unique_days > 0 else 0.0
        month_target  = round(avg_daily_tgt * DAYS_IN_MONTH)
        current_actual = round(float(m_dtr['actual_repay_principal'].astype(float).sum()))
    else:
        month_target   = 0
        current_actual = 0
    module_monthly_js[mk] = {
        'monthTarget':   month_target,
        'monthDays':     DAYS_IN_MONTH,
        'currentDay':    LATEST_DAY,
        'currentActual': current_actual
    }

# ========================
# 8. RISK MODULE GROUPS
# ========================
risk_module_groups = {}
for mk in modules_list:
    risk_module_groups[mk] = [
        {
            'group':       g['name'],
            'target':      g['target'],
            'actual':      g['actual'],
            'achievement': g['achievement'],
            'calls':       g['calls'],
            'connectRate': g['connectRate'],
            'ptpRate':     None,
            'attendance':  g['attendance']
        }
        for g in group_perf_js.get(mk, [])
    ]

# ========================
# Assemble REAL_DATA
# ========================
real_data = {
    'dataDate':          LATEST_DT_STR,
    'dataDay':           LATEST_DAY,
    'availableDates':     available_dates,
    'modules':           modules_list,
    'groups':            all_groups,
    'tlData':            tl_data_js,
    'stlData':           stl_data_js,
    'agentPerformance':  agent_perf_js,
    'groupPerformance':  group_perf_js,
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
# Read HTML template (v2_4 base — JS logic already patched)
# ========================
print("Patching HTML...")
with open(HTML_IN, 'r', encoding='utf-8') as f:
    html = f.read()

# ---- 1. Replace REAL_DATA block ----
# In v2_4.html, REAL_DATA is on a single line: "        const REAL_DATA = {...};"
real_marker = '        const REAL_DATA = '
real_start  = html.index(real_marker)
real_end    = html.index('\n', real_start) + 1
html = html[:real_start] + f'        const REAL_DATA = {real_data_json};\n' + html[real_end:]

# ---- 2. Title: v2.4 -> v2.5 ----
html = html.replace('Collection Operations Report v2.4', 'Collection Operations Report v2.5')

# ---- 3. STL chart card title: "Weekly Recovery Trend (12 Weeks)" -> "Recovery Trend" ----
html = html.replace('Weekly Recovery Trend (12 Weeks)', 'Recovery Trend')

# ---- 4. TL chart target line: flat constant -> daily cumulative series ----
# Use monthData (first group in module, same scope as the series.push call).
# filteredDays is scoped inside the forEach closure so is NOT accessible here.
html = html.replace(
    '                data: Array(dates.length).fill(moduleTarget),',
    '                data: monthData.map(d => d.targetRepayRate !== null && d.targetRepayRate !== undefined ? d.targetRepayRate : null),'
)

# ---- 5. Auto-select first group in TL view ----
html = html.replace(
    "            REAL_DATA.groups.forEach(g => {\n                groupSel.innerHTML += '<option value=\"' + g + '\">' + g + '</option>';\n            });",
    "            REAL_DATA.groups.forEach((g, i) => {\n                const selected = i === 0 ? ' selected' : '';\n                groupSel.innerHTML += '<option value=\"' + g + '\"' + selected + '>' + g + '</option>';\n            });"
)

# ---- 6. Auto-select first module in STL view ----
html = html.replace(
    "            REAL_DATA.modules.forEach(m => {\n                moduleSel.innerHTML += '<option value=\"' + m + '\">' + m + '</option>';\n            });",
    "            REAL_DATA.modules.forEach((m, i) => {\n                const selected = i === 0 ? ' selected' : '';\n                moduleSel.innerHTML += '<option value=\"' + m + '\"' + selected + '>' + m + '</option>';\n            });"
)

# ========================
# Write output
# ========================
with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"\nGenerated: {HTML_OUT}")
print(f"  Data date  : {LATEST_DT_STR}")
print(f"  Sub-modules: {modules_list}")
print(f"  Groups     : {len(all_groups)}")
print(f"  Anomalies  : {len(anomaly_groups)}")
print(f"  STL weeks  : {[(m, len(stl_data_js.get(m, {}).get('weeks', []))) for m in modules_list]}")

# Quick verification
checks = [
    ("Title v2.5",               'Collection Operations Report v2.5' in html),
    ("REAL_DATA present",        'const REAL_DATA = {' in html),
    ("No 'Weekly 12 Weeks'",     'Weekly Recovery Trend (12 Weeks)' not in html),
    ("Recovery Trend title",     'Recovery Trend' in html),
    ("repayRate in data",        '"repayRate"' in html),
    ("targetRepayRate in data",  '"targetRepayRate"' in html),
    ("TL daily target series",   'monthData.map(d => d.targetRepayRate' in html),
    ("Y-axis toFixed",           'toFixed(2)' in html),
    ("PTP null-safe",            'agent.ptp !== null' in html),
    ("Achievement null-safe",    'agent.achievement !== null' in html),
    ("Date selector real",       'REAL_DATA.availableDates' in html),
    ("TL auto-select group",     "REAL_DATA.groups.forEach((g, i)" in html),
    ("STL auto-select module",    "REAL_DATA.modules.forEach((m, i)" in html),
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
    print("\nSome checks FAILED - review patches above.")

input("\nPress Enter to close...")
