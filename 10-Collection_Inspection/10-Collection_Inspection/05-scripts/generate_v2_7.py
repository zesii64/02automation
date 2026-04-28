"""
Collection Operations Report v3.4 - Real Data v3
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
Output: Collection_Operations_Report_v3_6_<TL最新日YYYY-MM-DD>.html
"""
import sys
import pandas as pd
import json
import math
import re
import os
from datetime import timedelta
from calendar import monthrange
from view_tl_stl import apply_tl_stl_view_patches
from view_data import apply_data_view_patches
from view_tl_stl_post_patches import apply_tl_stl_post_data_view_patches
from patch_utils import require_replace_once, require_replace_at_least_one, optional_replace
from real_data_contract import (
    TEMPLATE_CONTRACT_ID,
    PIPELINE_VERSION,
    validate_real_data_for_report,
    inject_pipeline_head_comment,
)
from check_report_anchors import check_html_anchors

# Patch counter for auto-generating patch_id
_patch_seq = 0

def _rp_once(html, old, new):
    """Replace once, warn if 0 or >1 occurrences."""
    global _patch_seq
    import traceback
    frame = traceback.extract_stack()[-2]
    patch_id = f"gen_{frame.lineno}_{_patch_seq}"
    _patch_seq += 1
    n = html.count(old)
    if n == 0:
        print(f"  [WARN][{patch_id}] 锚点未找到: ...{old[:60].replace(chr(10), '\\n')!r}...", file=sys.stderr)
        return html
    if n > 1:
        print(f"  [WARN][{patch_id}] 锚点出现 {n} 次(期望1): ...{old[:60].replace(chr(10), '\\n')!r}...", file=sys.stderr)
    return html.replace(old, new, 1)

def _rp_at_least(html, old, new):
    """require_replace_at_least_one with auto patch_id."""
    global _patch_seq
    import traceback
    frame = traceback.extract_stack()[-2]
    patch_id = f"gen_{frame.lineno}_{_patch_seq}"
    _patch_seq += 1
    n = html.count(old)
    if n == 0:
        print(f"  [WARN][{patch_id}] 锚点未找到: ...{old[:60].replace(chr(10), '\\n')!r}...", file=sys.stderr)
        return html
    print(f"  [INFO][{patch_id}] 替换 {n} 处: ...{old[:60].replace(chr(10), '\\n')!r}...")
    return html.replace(old, new)

# Shorthand
r1 = _rp_once
ra = _rp_at_least
opt = lambda html, old, new: optional_replace(html, old, new, "optional")

# ========================
# Paths
# ========================
BASE       = r'd:/11automation/02automation/10-Collection_Inspection/10-Collection_Inspection'
EXCEL_PATH = BASE + r'/data/260318_output_automation_v3.xlsx'
PROCESS_TARGET_PATH = BASE + r'/data/process_data_target.xlsx'
HTML_IN    = BASE + r'/reports/Collection_Operations_Report_v3_6_2026-04-21.html'
# HTML_OUT：在 TL_LATEST_STR（与目标/绩效对齐的 TL 最新日）确定后赋值

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
attd_daily   = pd.read_excel(xl, 'attd_group_daily_data', index_col=0)
attd_weekly  = pd.read_excel(xl, 'attd_group_week_data',  index_col=0)
daily_target_agent_breakdown = pd.read_excel(xl, 'daily_target_agent_breakdown', index_col=0)
week_target_group_breakdown  = pd.read_excel(xl, 'week_target_group_breakdown', index_col=0)

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
attd_daily['group_id']    = attd_daily['group_id'].astype(str).str.strip()
attd_weekly['group_id']   = attd_weekly['group_id'].astype(str).str.strip()
daily_target_agent_breakdown['owner_group'] = daily_target_agent_breakdown['owner_group'].astype(str).str.strip()
daily_target_agent_breakdown['owner_name']  = daily_target_agent_breakdown['owner_name'].astype(str).str.strip()
week_target_group_breakdown['owner_group']  = week_target_group_breakdown['owner_group'].astype(str).str.strip()
group_perf['week']        = group_perf['week'].astype(str)

# Parse dates
tl_data['dt']       = pd.to_datetime(tl_data['dt'])
agent_perf['dt']    = pd.to_datetime(agent_perf['dt'])
daily_tr['dt']      = pd.to_datetime(daily_tr['dt'])
agent_repay['dt']   = pd.to_datetime(agent_repay['dt'])
ptp_agent['dt']     = pd.to_datetime(ptp_agent['dt'])
cl_agent['dt']      = pd.to_datetime(cl_agent['dt'])
nat_month['dt_biz'] = pd.to_datetime(nat_month['dt_biz'])
attd_daily['dt']    = pd.to_datetime(attd_daily['dt'])
daily_target_agent_breakdown['dt'] = pd.to_datetime(daily_target_agent_breakdown['dt'])

group_repay['week'] = group_repay['week'].astype(str)
ptp_group['week']   = ptp_group['week'].astype(str)
cl_group['week']    = cl_group['week'].astype(str)
group_perf['week']  = group_perf['week'].astype(str)
attd_weekly['week'] = attd_weekly['week'].astype(str)
week_target_group_breakdown['week'] = week_target_group_breakdown['week'].astype(str)

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
attd_weekly['week'] = attd_weekly['week'].apply(normalize_week_label)
week_target_group_breakdown['week'] = week_target_group_breakdown['week'].apply(normalize_week_label)

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

HTML_OUT = BASE + f'/reports/Collection_Operations_Report_v3_6_{TL_LATEST_STR}.html'

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

# Canonical module order in JSON/UI: S0 → S1 → S2 → M1 (aligns with view_data Agent Overview).
_MODULE_SORT_PRIORITY = ['S0', 'S1', 'S2', 'M1']
_MODULE_SORT_RANK = {m: i for i, m in enumerate(_MODULE_SORT_PRIORITY)}

def _parse_module_parts_for_sort(module_key):
    text = str(module_key or '').strip()
    parts = text.split('-')
    base = (parts[0] or '').strip()
    raw_tier = (parts[1] or '').strip().lower() if len(parts) > 1 else ''
    if raw_tier == 'large' or '大额' in raw_tier:
        tier = 'large'
    elif raw_tier == 'small' or '小额' in raw_tier:
        tier = 'small'
    else:
        tier = raw_tier
    return base, tier

def sort_module_keys(keys):
    def key_fn(k):
        base, tier = _parse_module_parts_for_sort(k)
        rank = _MODULE_SORT_RANK.get(base, 999)
        tier_order = 0 if tier == 'large' else (1 if tier == 'small' else 2)
        return (rank, base, tier_order, str(k))
    return sorted(keys, key=key_fn)

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


def resolve_canonical_group_for_breakdown(
    owner_group_raw, a_norm, norm_to_group, all_groups, group_agent_name_map
):
    """
    Map daily_target_agent_breakdown.owner_group to tl_data group_id.
    - Exact match: norm(raw) in norm_to_group (full group name as in tl_data)
    - Else: all_groups with same extract_module_key(raw) as module bucket; if multiple,
      pick by agent (name_norm) membership in that group's agent list.
    Skips cases where the sheet uses a module code that cannot be disambiguated.
    """
    if owner_group_raw is None or (isinstance(owner_group_raw, float) and pd.isna(owner_group_raw)):
        return None
    raw = str(owner_group_raw).strip()
    if not raw:
        return None
    g_hit = norm_to_group.get(norm(raw))
    if g_hit:
        return g_hit
    try:
        mk = extract_module_key(raw)
    except Exception:
        mk = None
    if not mk:
        return None
    candidates = [g for g in all_groups if extract_module_key(g) == mk]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    an = (a_norm or "").strip().lower()
    if an:
        for g in candidates:
            if an in (group_agent_name_map.get(g) or {}):
                return g
    return None


def normalize_attd_rate_pct(v):
    """Normalize attendance rate to percentage [0,100]."""
    if pd.isna(v):
        return None
    fv = float(v)
    if fv <= 1.0:
        fv = fv * 100
    return round(fv, 1)

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
modules_list = sort_module_keys(list(submodule_groups.keys()))

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
attd_daily['grp_norm']   = attd_daily['group_id'].apply(norm)
attd_weekly['grp_norm']  = attd_weekly['group_id'].apply(norm)

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
    g_norm = norm(group)
    dtr_norm = norm(dtr_name)
    grp_norm_candidates = {g_norm, dtr_norm}

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
    g_attd_daily = attd_daily[attd_daily['grp_norm'].isin(grp_norm_candidates)]
    attd_daily_by_date = {}
    if len(g_attd_daily) > 0:
        for dt_key, day_df in g_attd_daily.groupby('dt'):
            dt_str = pd.to_datetime(dt_key).strftime('%Y-%m-%d')
            attd_vals = pd.to_numeric(day_df['attd_rate_8h'], errors='coerce').dropna()
            attd_daily_by_date[dt_str] = normalize_attd_rate_pct(attd_vals.mean()) if len(attd_vals) > 0 else None

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
                                 'targetRepayRate': nm_trr, 'moduleRepayRate': nm_rr,
                                 'attendanceRate': attd_daily_by_date.get(date_str)})
        else:
            # targetRepayRate should be visible for full month, not capped by data cutoff day.
            nm_trr = module_target_nm.get(day, None)
            nm_rr  = module_nm_daily.get(day, None) if in_cutoff else None
            g_nm_rr = group_nm_daily.get(day, None) if in_cutoff else None
            days_series.append({'date': date_str, 'target': None, 'actual': None,
                                 'repayRate': None, 'nmRepayRate': g_nm_rr,
                                 'targetRepayRate': nm_trr, 'moduleRepayRate': nm_rr,
                                 'attendanceRate': attd_daily_by_date.get(date_str)})

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

            # Prefer direct connect_rate; fallback to connect-count ratio, then legacy call_billhr.
            if 'connect_rate' in ap_a.columns and pd.notna(ap_a['connect_rate']).any():
                conn_val = float(ap_a['connect_rate'].astype(float).mean())
                conn_r = round(conn_val * 100, 1)
            elif 'call_connect_times' in ap_a.columns:
                connects = int(round(float(ap_a['call_connect_times'].astype(float).sum())))
                conn_r = round(connects / calls * 100, 1) if calls > 0 else 0.0
            elif 'connect_times' in ap_a.columns:
                connects = int(round(float(ap_a['connect_times'].astype(float).sum())))
                conn_r = round(connects / calls * 100, 1) if calls > 0 else 0.0
            elif 'call_billhr' in ap_a.columns and pd.notna(ap_a['call_billhr']).any():
                conn_val = float(ap_a['call_billhr'].astype(float).mean())
                conn_r = round(conn_val * 100, 1)
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
            if 'call_connect_times' in ap_hist.columns:
                agg_map['call_connects'] = ('call_connect_times', lambda x: x.astype(float).sum())
            elif 'connect_times' in ap_hist.columns:
                agg_map['connects'] = ('connect_times', lambda x: x.astype(float).sum())
            if 'call_billhr' in ap_hist.columns:
                agg_map['call_billhr'] = ('call_billhr', 'mean')

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
                elif 'call_connects' in hr and pd.notna(hr['call_connects']):
                    connects_d = int(round(float(hr['call_connects'])))
                    conn_r_d = round(connects_d / calls_d * 100, 1) if calls_d > 0 else 0.0
                elif 'connects' in hr and pd.notna(hr['connects']):
                    connects_d = int(round(float(hr['connects'])))
                    conn_r_d = round(connects_d / calls_d * 100, 1) if calls_d > 0 else 0.0
                elif 'call_billhr' in hr and pd.notna(hr['call_billhr']):
                    conn_r_d = round(float(hr['call_billhr']) * 100, 1)
                else:
                    conn_r_d = 0.0

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

        # Attendance from attd_group_week_data
        attd_w = attd_weekly[(attd_weekly['grp_norm'].isin(grp_norm_candidates)) &
                             (attd_weekly['week'] == DEFAULT_STL_WEEK)]
        attd_w_valid = pd.to_numeric(attd_w['attd_rate_8h'], errors='coerce').dropna() if len(attd_w) > 0 else pd.Series(dtype=float)
        attd = normalize_attd_rate_pct(attd_w_valid.mean()) if len(attd_w_valid) > 0 else None

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

        else:
            calls_pa = conn_r = 0

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
        attd_hist_week = attd_weekly[attd_weekly['grp_norm'].isin(grp_norm_candidates)]
        if len(attd_hist_week) > 0:
            attd_weekly_agg = (attd_hist_week.groupby('week', as_index=False)
                               .agg(attendance=('attd_rate_8h', lambda x: pd.to_numeric(x, errors='coerce').mean())))
            for _, ar in attd_weekly_agg.iterrows():
                wk_label = week_str_to_display(str(ar['week']))
                week_map.setdefault(wk_label, {})
                week_map[wk_label]['attendance'] = normalize_attd_rate_pct(ar.get('attendance'))
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
# Extra drilldown payloads (v3.5 compatibility)
# ========================
today_dt = pd.Timestamp.now().normalize()
norm_to_group = {norm(g): g for g in all_groups}

today_agent_rows = agent_repay[agent_repay['dt'] == today_dt].copy()
today_agent_target_by_group = {}
today_agent_target_by_group_agent = {}
if len(today_agent_rows) > 0:
    today_agent_rows['grp_norm'] = today_agent_rows['owner_group'].apply(norm)
    today_agent_rows['name_norm'] = today_agent_rows['owner_name'].apply(lambda x: str(x).strip().lower() if pd.notna(x) else '')

    for g_norm, sub in today_agent_rows.groupby('grp_norm'):
        canonical_group = norm_to_group.get(g_norm)
        if not canonical_group:
            continue
        today_agent_target_by_group[canonical_group] = float(sub['target_repay_principal'].fillna(0).sum())
        agent_target_map = {}
        for _, row in sub.iterrows():
            akey = str(row.get('name_norm', '')).strip().lower()
            if not akey:
                continue
            agent_target_map[akey] = float(row.get('target_repay_principal', 0) or 0)
        today_agent_target_by_group_agent[canonical_group] = agent_target_map

# TL breakdown by date/group (for detailed table rendering)
tl_breakdown_by_date = {}
if len(daily_target_agent_breakdown) > 0:
    daily_target_agent_breakdown['grp_norm'] = daily_target_agent_breakdown['owner_group'].apply(norm)
    daily_target_agent_breakdown['name_norm'] = daily_target_agent_breakdown['owner_name'].apply(
        lambda x: str(x).strip().lower() if pd.notna(x) else ''
    )
    # name_norm -> display name by group, aligned with agentPerformance keys
    group_agent_name_map = {}
    for g in all_groups:
        mapping = {}
        for a in agent_perf_js.get(g, []):
            key = str(a.get('name', '')).strip().lower()
            if key:
                mapping[key] = a.get('name')
        group_agent_name_map[g] = mapping

    for _, row in daily_target_agent_breakdown.iterrows():
        g_norm = row.get('grp_norm', '')
        dt_val = row.get('dt')
        if not g_norm or pd.isna(dt_val):
            continue
        a_norm = str(row.get('name_norm', '') or '')
        g_canonical = norm_to_group.get(g_norm) or resolve_canonical_group_for_breakdown(
            row.get('owner_group'), a_norm, norm_to_group, all_groups, group_agent_name_map
        )
        if not g_canonical:
            continue
        dt_key = pd.to_datetime(dt_val).strftime('%Y-%m-%d')
        group_map = tl_breakdown_by_date.setdefault(g_canonical, {})
        date_rows = group_map.setdefault(dt_key, {'caseStage': {}, 'principalStage': {}})

        case_k = str(row.get('case_stage', '') or '')
        principal_k = str(row.get('principal_stage', '') or '')
        a_display = group_agent_name_map.get(g_canonical, {}).get(a_norm, str(row.get('owner_name', '') or '').strip() or '--')
        owing = float(row.get('owing_principal', 0) or 0)
        repay = float(row.get('repay_principal', 0) or 0)
        if case_k:
            k = f"{a_display}||{case_k}"
            c = date_rows['caseStage'].setdefault(k, {
                'agentName': a_display,
                'dimensionValue': case_k,
                'owingPrincipal': 0.0,
                'repayPrincipal': 0.0
            })
            c['owingPrincipal'] += owing
            c['repayPrincipal'] += repay
        if principal_k:
            k = f"{a_display}||{principal_k}"
            p = date_rows['principalStage'].setdefault(k, {
                'agentName': a_display,
                'dimensionValue': principal_k,
                'owingPrincipal': 0.0,
                'repayPrincipal': 0.0
            })
            p['owingPrincipal'] += owing
            p['repayPrincipal'] += repay

    # Convert dict payload to sorted list payload with repayRate (JS expects agentName + dimensionValue)
    for g in list(tl_breakdown_by_date.keys()):
        for d in list(tl_breakdown_by_date[g].keys()):
            for dim in ('caseStage', 'principalStage'):
                rows = []
                for _, vals in tl_breakdown_by_date[g][d][dim].items():
                    owing = vals['owingPrincipal']
                    repay = vals['repayPrincipal']
                    rows.append({
                        'agentName': vals['agentName'],
                        'dimensionValue': vals['dimensionValue'],
                        'owingPrincipal': round(owing, 2),
                        'repayPrincipal': round(repay, 2),
                        'repayRate': round((repay / owing * 100), 2) if owing > 0 else None
                    })
                rows.sort(key=lambda x: (x['dimensionValue'], x['agentName']))
                tl_breakdown_by_date[g][d][dim] = rows

# Ensure REAL_DATA.tlBreakdownByDate has every TL group key (empty {} = no dates yet; JS truthy group lookup)
for g in all_groups:
    tl_breakdown_by_date.setdefault(g, {})

# STL breakdown by week/module
stl_breakdown_by_week = {}
if len(week_target_group_breakdown) > 0:
    week_target_group_breakdown['module_key'] = week_target_group_breakdown['owner_bucket'].apply(lambda x: module_key_to_bucket(str(x).strip()))
    for _, row in week_target_group_breakdown.iterrows():
        module_key = row.get('module_key')
        week_label = row.get('week')
        if not module_key or not week_label:
            continue
        module_map = stl_breakdown_by_week.setdefault(module_key, {})
        week_map = module_map.setdefault(week_str_to_display(str(week_label)), {'caseStage': {}, 'principalStage': {}})

        case_k = str(row.get('case_stage', '') or '')
        principal_k = str(row.get('principal_stage', '') or '')
        owing = float(row.get('owing_principal', 0) or 0)
        repay = float(row.get('repay_principal', 0) or 0)

        if case_k:
            c = week_map['caseStage'].setdefault(case_k, {
                'dimensionValue': case_k,
                'owingPrincipal': 0.0,
                'repayPrincipal': 0.0
            })
            c['owingPrincipal'] += owing
            c['repayPrincipal'] += repay
        if principal_k:
            p = week_map['principalStage'].setdefault(principal_k, {
                'dimensionValue': principal_k,
                'owingPrincipal': 0.0,
                'repayPrincipal': 0.0
            })
            p['owingPrincipal'] += owing
            p['repayPrincipal'] += repay

    for mk in list(stl_breakdown_by_week.keys()):
        for wk in list(stl_breakdown_by_week[mk].keys()):
            for dim in ('caseStage', 'principalStage'):
                rows = []
                for _, vals in stl_breakdown_by_week[mk][wk][dim].items():
                    owing = vals['owingPrincipal']
                    repay = vals['repayPrincipal']
                    rows.append({
                        'dimensionValue': vals['dimensionValue'],
                        'owingPrincipal': round(owing, 2),
                        'repayPrincipal': round(repay, 2),
                        'repayRate': round((repay / owing * 100), 2) if owing > 0 else None
                    })
                rows.sort(key=lambda x: x['dimensionValue'])
                stl_breakdown_by_week[mk][wk][dim] = rows

has_stl_week_breakdown_data = len(stl_breakdown_by_week) > 0

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
    'moduleMonthly':     module_monthly_js,
    'todayAgentTargetByGroup': today_agent_target_by_group,
    'todayAgentTargetByGroupAgent': today_agent_target_by_group_agent,
    'tlBreakdownByDate': tl_breakdown_by_date,
    'stlBreakdownByWeek': stl_breakdown_by_week,
    'hasStlWeekBreakdownData': has_stl_week_breakdown_data,
    'templateContractId': TEMPLATE_CONTRACT_ID,
    'pipelineVersion': PIPELINE_VERSION,
}

validate_real_data_for_report(real_data)

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

# ---- 1. Replace data block (MOCK_DATA or REAL_DATA template) ----
# Templates differ: const vs var, indentation; end anchor is any line: // ===... ROLE SWITCHING
_data_pat = re.compile(
    r'(?m)^[ \t]*(?:(?P<a>const)\s+MOCK_DATA|(?P<b>const|var)\s+REAL_DATA)\s*=\s*\{'
)
_m_data = _data_pat.search(html)
if not _m_data:
    raise ValueError(
        "Data marker not found in template (expected const MOCK_DATA / const|var REAL_DATA = {)."
    )
data_start = _m_data.start()
m_role = re.search(
    r'(?m)^[ \t]*//[ \t]*=+[ \t]*ROLE\s+SWITCHING[ \t]*=+',
    html[data_start:],
)
if not m_role:
    raise ValueError(
        "role_marker not found after data block: line '// ... ROLE SWITCHING ...' required."
    )
data_end = data_start + m_role.start()
html = (
    html[:data_start]
    + f"        const REAL_DATA = {real_data_json};\n\n"
    + html[data_end:]
)

# ---- 2. MOCK_DATA. -> REAL_DATA. ----
html = opt(html, 'MOCK_DATA.', 'REAL_DATA.')

# ---- TL/STL view patches (modularized) ----
html = apply_tl_stl_view_patches(html)

# ---- Data view patches (modularized; Agent B) ----
html = apply_data_view_patches(html)

html = apply_tl_stl_post_data_view_patches(html)


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
html = r1(html, old_stl_init, new_stl_init)
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
html = r1(html, old_load_stl, new_load_stl)
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
    '<h3 style="font-size: 16px; font-weight: 600; margin-bottom: 16px; color: #991b1b;">Unmet Target — Detail Review</h3>\n                    <div style="display: flex; gap: 12px; margin-bottom: 20px;">',
    '<h3 style="font-size: 16px; font-weight: 600; margin-bottom: 16px; color: #991b1b;">Unmet Target — Detail Review</h3>\n                    <div id="tl-unmet-attendance" style="font-size: 13px; color: #334155; margin-bottom: 12px;">Attendance: --</div>\n                    <div style="display: flex; gap: 12px; margin-bottom: 20px;">'
)
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
html = r1(html, old_agent_header, new_agent_header)
# Compatible with template variant using font-size/color styles
old_agent_header_v2 = '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>'
new_agent_header_v2 = '''                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>
                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Process KPI</th>'''
html = r1(html, old_agent_header_v2, new_agent_header_v2)

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
html = r1(html, old_cl_td, new_cl_td)
# Compatible with template variant using font-size/color styles
old_stl_grp_header_v2 = '                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>'
new_stl_grp_header_v2 = '''                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Call Loss</th>
                                <th style="padding: 12px; text-align: right; font-size: 12px; color: #64748b;">Attendance</th>
                                <th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Process KPI</th>'''
html = r1(html, old_stl_grp_header_v2, new_stl_grp_header_v2)

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
html = r1(html, old_stl_grp_footer, new_stl_grp_footer)
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
html = r1(html, old_ptp_avg, new_ptp_avg)

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

tl_conclusion_fn = """\
        function generateTLConclusions(data, isMet) {
            var group = document.getElementById('tl-group-select') ? document.getElementById('tl-group-select').value : '';
            var selectedDate = document.getElementById('tl-date-select') ? document.getElementById('tl-date-select').value : REAL_DATA.dataDate;
            var selectedDateForSort = (typeof selectedDate !== 'undefined' && selectedDate) ? selectedDate : (document.getElementById('tl-date-select') ? document.getElementById('tl-date-select').value : REAL_DATA.dataDate);
            var agents = (REAL_DATA.agentPerformance[group] || []).filter(a => {
                var dm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][a.name]
                    ? REAL_DATA.agentPerformanceByDate[group][a.name][selectedDateForSort]
                    : null;
                return !!dm;
            });
            agents.sort((a, b) => {
                var adm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][a.name]
                    ? REAL_DATA.agentPerformanceByDate[group][a.name][selectedDateForSort]
                    : null;
                var bdm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][b.name]
                    ? REAL_DATA.agentPerformanceByDate[group][b.name][selectedDateForSort]
                    : null;
                var av = (adm && adm.achievement !== null && adm.achievement !== undefined) ? adm.achievement : ((a.achievement !== null && a.achievement !== undefined) ? a.achievement : 999);
                var bv = (bdm && bdm.achievement !== null && bdm.achievement !== undefined) ? bdm.achievement : ((b.achievement !== null && b.achievement !== undefined) ? b.achievement : 999);
                return av - bv;
            });
            var groupMeta = REAL_DATA.tlData[group] || {};
            var moduleKey = groupMeta.groupModule || '';
            var coarseModule = moduleKey.replace(/-Large|-Small/g, '');
            var TL_MODULE_IMPROVEMENT_PLAN_URL = {
                'S0': 'https://doc.weixin.qq.com/sheet/e3_AGIATAbTANsCNWcq1Hf0CS76ZJaSp?scode=AGMA_AdxAAsFy3PXtQAagA5gaoAKA&tab=BB08J2',
                'S1': 'https://doc.weixin.qq.com/sheet/e3_AGIATAbTANsCNKGdG4MPaQreE00Ga?scode=AGMA_AdxAAswoBPuhvAagA5gaoAKA&tab=BB08J2',
                'S2': 'https://doc.weixin.qq.com/sheet/e3_AGIATAbTANsCNk6txUBU0SG2hZ9A0?scode=AGMA_AdxAAsARq92dVAagA5gaoAKA&tab=BB08J2',
                'M1': 'https://doc.weixin.qq.com/sheet/e3_AGIATAbTANsCNs8XAuzKHQmq0m0W1?scode=AGMA_AdxAAsXVhLkssAagA5gaoAKA&tab=BB08J2'
            };
            var improvementPlanUrl = TL_MODULE_IMPROVEMENT_PLAN_URL[coarseModule] || '';
            var improvementPlanBlock = '';
            if (!isMet && improvementPlanUrl) {
                improvementPlanBlock = '<div style="margin-top:10px; padding-top:10px; border-top:1px solid #e5e7eb; font-size:12px;">' +
                    '<div style="color:#374151; font-weight:600; margin-bottom:4px;">改进方案 · Improvement plan</div>' +
                    '<div style="color:#6b7280; font-size:11px; line-height:1.45; margin-bottom:6px;">在当前模块维度填写或跟踪改进动作（腾讯文档外链）。 / Fill in or track module-level improvement actions (Tencent Doc, external).</div>' +
                    '<a href="' + improvementPlanUrl + '" target="_blank" rel="noopener noreferrer" style="color:#2563eb;">打开「' + coarseModule + '」模块改进方案 · Open ' + coarseModule + ' improvement plan (Tencent Doc)</a>' +
                '</div>';
            }
            var moduleGroups = (REAL_DATA.groups || []).filter(g => REAL_DATA.tlData[g] && REAL_DATA.tlData[g].groupModule === moduleKey);
            var fmt = (v, d = 1, suffix = '') => (v === null || v === undefined || Number.isNaN(Number(v))) ? '--' : (Number(v).toFixed(d) + suffix);

            var getAgentMetric = (groupId, agent, key) => {
                var dm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[groupId] && REAL_DATA.agentPerformanceByDate[groupId][agent.name]
                    ? REAL_DATA.agentPerformanceByDate[groupId][agent.name][selectedDate]
                    : null;
                if (dm && dm[key] !== undefined && dm[key] !== null) return Number(dm[key]);
                if (agent && agent[key] !== undefined && agent[key] !== null) return Number(agent[key]);
                return null;
            };

            var tAch = 0, tAttd = 0, tConn = 0, tLoss = 0, tDial = 0, tCnt = 0;
            agents.forEach(a => {
                tAch += getAgentMetric(group, a, 'achievement') || 0;
                tAttd += getAgentMetric(group, a, 'attendance') || 0;
                tConn += getAgentMetric(group, a, 'connectRate') || 0;
                tLoss += getAgentMetric(group, a, 'callLossRate') || 0;
                tDial += getAgentMetric(group, a, 'artCallTimes') || 0;
                tCnt += 1;
            });
            var teamCnt = Math.max(1, tCnt);
            var teamAvg = { achievement: tAch / teamCnt, attendance: tAttd / teamCnt, connectRate: tConn / teamCnt, callLossRate: tLoss / teamCnt, artCallTimes: tDial / teamCnt };

            var mDial = 0, mAttd = 0, mConn = 0, mLoss = 0, mCnt = 0;
            moduleGroups.forEach(gid => {
                var rows = REAL_DATA.agentPerformance[gid] || [];
                rows.forEach(a => {
                    mDial += getAgentMetric(gid, a, 'artCallTimes') || 0;
                    mAttd += getAgentMetric(gid, a, 'attendance') || 0;
                    mConn += getAgentMetric(gid, a, 'connectRate') || 0;
                    mLoss += getAgentMetric(gid, a, 'callLossRate') || 0;
                    mCnt += 1;
                });
            });
            var moduleAvgDial = mCnt > 0 ? (mDial / mCnt) : teamAvg.artCallTimes;
            var moduleAvgAttendance = mCnt > 0 ? (mAttd / mCnt) : teamAvg.attendance;
            var moduleAvgConnectRate = mCnt > 0 ? (mConn / mCnt) : teamAvg.connectRate;
            var moduleAvgCallLossRate = mCnt > 0 ? (mLoss / mCnt) : teamAvg.callLossRate;

            // 容忍带配置（相对模块均值）
            const ATTENDANCE_TOLERANCE = 2.0;   // pp
            const CONNECT_TOLERANCE = 5.0;      // pp
            const LOSS_TOLERANCE = 5.0;         // pp
            const DIAL_TOLERANCE = 0.10;        // 10%

            var laggingAgents = [...agents]
                .map(a => ({
                    name: a.name,
                    achievement: getAgentMetric(group, a, 'achievement'),
                    attendance: getAgentMetric(group, a, 'attendance'),
                    connectRate: getAgentMetric(group, a, 'connectRate'),
                    artCallTimes: getAgentMetric(group, a, 'artCallTimes'),
                    gap: (getAgentMetric(group, a, 'target') || 0) - (getAgentMetric(group, a, 'actual') || 0)
                }))
                .sort((x, y) => {
                    var ax = x.achievement !== null && x.achievement !== undefined ? x.achievement : 999;
                    var ay = y.achievement !== null && y.achievement !== undefined ? y.achievement : 999;
                    if (ax !== ay) return ax - ay;
                    return (y.gap || 0) - (x.gap || 0);
                })
                .slice(0, 3);

            var breakdownByDate = REAL_DATA.tlBreakdownByDate && REAL_DATA.tlBreakdownByDate[group]
                ? REAL_DATA.tlBreakdownByDate[group][selectedDate]
                : null;
            var pickWeakDims = (rows) => {
                var valid = (rows || []).filter(r => r.repayRate !== null && r.repayRate !== undefined);
                if (valid.length === 0) return [];
                var avg = valid.reduce((s, r) => s + Number(r.repayRate), 0) / valid.length;
                return valid.filter(r => Number(r.repayRate) < avg)
                    .sort((a, b) => Number(a.repayRate) - Number(b.repayRate))
                    .slice(0, 2)
                    .map(r => `${r.dimensionValue}(${fmt(r.repayRate, 1, '%')})`);
            };
            var weakCaseStages = pickWeakDims(breakdownByDate ? breakdownByDate.caseStage : []);
            var weakPrincipalStages = pickWeakDims(breakdownByDate ? breakdownByDate.principalStage : []);

            var peopleSummary = (teamAvg.attendance < moduleAvgAttendance - ATTENDANCE_TOLERANCE || teamAvg.artCallTimes < moduleAvgDial * (1 - DIAL_TOLERANCE))
                ? `People factor risk: attendance ${fmt(teamAvg.attendance, 1, '%')} (module avg ${fmt(moduleAvgAttendance, 1, '%')}), dial ${fmt(teamAvg.artCallTimes, 0)} (module avg ${fmt(moduleAvgDial, 0)}).`
                : `People factors are stable on selected date.`;
            var strategySummary = (weakCaseStages.length > 0 || weakPrincipalStages.length > 0)
                ? `Stage preference imbalance (strategy): some agents/groups show declining contribution in overdue or amount stages. Action: adjust follow-up strategy and prioritize these stages.`
                : `No clear stage preference imbalance detected from current breakdown data.`;
            var toolSummary = (teamAvg.connectRate < moduleAvgConnectRate - CONNECT_TOLERANCE || teamAvg.callLossRate > moduleAvgCallLossRate + LOSS_TOLERANCE)
                ? `Tool usage risk: connect ${fmt(teamAvg.connectRate, 1, '%')} (module avg ${fmt(moduleAvgConnectRate, 1, '%')}), call loss ${fmt(teamAvg.callLossRate, 1, '%')} (module avg ${fmt(moduleAvgCallLossRate, 1, '%')}); check phone channel quality and outreach time window.`
                : `Tool usage appears stable (phone channel metrics in normal range).`;

            var peopleAction = '';
            var attdLow = teamAvg.attendance < moduleAvgAttendance - ATTENDANCE_TOLERANCE;
            var dialLow = teamAvg.artCallTimes < moduleAvgDial * (1 - DIAL_TOLERANCE);
            if (attdLow && dialLow) {
                peopleAction = 'Attendance & dial below module average. Check absenteeism and reallocate staff if needed; review low-productivity agents for system issues or idle time.';
            } else if (attdLow) {
                peopleAction = 'Attendance below module average. Check absenteeism and consider temporary shift adjustments or cross-group support.';
            } else if (dialLow) {
                peopleAction = 'Dial volume below module average. Follow up with low-productivity agents and review system allocation and online hours.';
            } else {
                peopleAction = 'People metrics stable. Maintain current scheduling and productivity monitoring.';
            }

            var strategyAction = '';
            if (weakCaseStages.length > 0 && weakPrincipalStages.length > 0) {
                strategyAction = 'Reprioritize follow-up on stages ' + weakCaseStages.join(', ') + ' and increase weight for principal stages ' + weakPrincipalStages.join(', ') + '.';
            } else if (weakCaseStages.length > 0) {
                strategyAction = 'Reprioritize follow-up on stages ' + weakCaseStages.join(', ') + ' and verify script coverage and training.';
            } else if (weakPrincipalStages.length > 0) {
                strategyAction = 'Increase allocation weight or customize collection strategy for principal stages ' + weakPrincipalStages.join(', ') + '.';
            } else {
                strategyAction = 'Stage distribution normal. Maintain current strategy.';
            }

            var toolAction = '';
            var connLow = teamAvg.connectRate < moduleAvgConnectRate - CONNECT_TOLERANCE;
            var lossHigh = teamAvg.callLossRate > moduleAvgCallLossRate + LOSS_TOLERANCE;
            if (connLow && lossHigh) {
                toolAction = 'Channel quality check: verify number quality and line stability; adjust dialing hours. Also investigate drop-off causes (line/network/script) to improve first-call retention.';
            } else if (connLow) {
                toolAction = 'Channel quality check: verify number quality and line stability; try adjusting dialing hours (e.g. avoid local rush hours).';
            } else if (lossHigh) {
                toolAction = 'Drop-off root cause: investigate post-connection drops (line/network/script) and optimize opening lines.';
            } else {
                toolAction = 'Outbound channel stable. Maintain current line configuration.';
            }

            var environmentAction = 'If confirmed, document impact in improvement plan and adjust priority accordingly.';

            var laggingAction = '';
            if (laggingAgents.length === 0) {
                laggingAction = 'No lagging agents today. Maintain current management rhythm.';
            } else {
                laggingAction = 'One-on-one follow-up with lagging agents: ' + laggingAgents.map(a => a.name).join(', ') + '. Set 3-5 day improvement plan with daily check-ins.';
            }

            var laggingHtml = laggingAgents.length === 0
                ? '<div style="color:#6b7280;">No lagging agent identified for selected date.</div>'
                : laggingAgents.map((a, idx) => `<div style="padding:6px 8px; border:1px solid #e5e7eb; border-radius:6px; margin-bottom:6px;">
                        <b>#${idx + 1} ${a.name}</b> |
                        Achv ${fmt(a.achievement, 1, '%')} |
                        Attendance ${fmt(a.attendance, 1, '%')} |
                        Dial ${fmt(a.artCallTimes, 0)} |
                        Connect ${fmt(a.connectRate, 1, '%')} |
                        Gap ${fmt(a.gap, 0)}
                    </div>`).join('');

            var laggingAction = '';
            if (laggingAgents.length === 0) {
                laggingAction = 'No lagging agents today. Maintain current management rhythm.';
            } else {
                laggingAction = 'One-on-one follow-up with lagging agents: ' + laggingAgents.map(a => a.name).join(', ') + '. Set 3-5 day improvement plan with daily check-ins.';
            }

            var tableHtml = `
                <div style="font-size:12px; color:#111827; line-height:1.5;">
                    <div style="font-weight:700; margin-bottom:8px;">TL conclusion = group-level overview + lagging agents</div>
                    <table style="width:100%; border-collapse:collapse; font-size:12px;">
                        <tr style="background:#f8fafc;">
                            <td style="border:1px solid #d1d5db; padding:8px; width:140px; font-weight:700;">Dimension</td>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">Diagnosis</td>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700; width:280px;">Suggested Action</td>
                        </tr>
                        <tr style="background:#f8fafc;">
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">Group overview</td>
                            <td style="border:1px solid #d1d5db; padding:8px;">
                                Group: <b>${group}</b> (${moduleKey || '--'}) @ ${selectedDate}<br>
                                Achievement: <b>${fmt(teamAvg.achievement, 1, '%')}</b> | Attendance: <b>${fmt(teamAvg.attendance, 1, '%')}</b> | Dial: <b>${fmt(teamAvg.artCallTimes, 0)}</b>
                            </td>
                            <td style="border:1px solid #d1d5db; padding:8px; color:#065f46; background:#f0fdf4;">Continue monitoring core group metrics and watch gaps vs module average.</td>
                        </tr>
                        <tr>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">People factors</td>
                            <td style="border:1px solid #d1d5db; padding:8px;">${peopleSummary}</td>
                            <td style="border:1px solid #d1d5db; padding:8px; color:#065f46; background:#f0fdf4;">${peopleAction}</td>
                        </tr>
                        <tr>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">Strategy factors</td>
                            <td style="border:1px solid #d1d5db; padding:8px;">
                                ${strategySummary}<br>
                                Overdue stages with weak contribution: ${weakCaseStages.length ? weakCaseStages.join(', ') : '--'}<br>
                                Amount stages with weak contribution: ${weakPrincipalStages.length ? weakPrincipalStages.join(', ') : '--'}
                            </td>
                            <td style="border:1px solid #d1d5db; padding:8px; color:#065f46; background:#f0fdf4;">${strategyAction}</td>
                        </tr>
                        <tr>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">Tool factors</td>
                            <td style="border:1px solid #d1d5db; padding:8px;">${toolSummary}</td>
                            <td style="border:1px solid #d1d5db; padding:8px; color:#065f46; background:#f0fdf4;">${toolAction}</td>
                        </tr>
                        <tr>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">Environment/other</td>
                            <td style="border:1px solid #d1d5db; padding:8px;">If holiday/policy/system events occurred, use manual override for action priority.</td>
                            <td style="border:1px solid #d1d5db; padding:8px; color:#065f46; background:#f0fdf4;">${environmentAction}</td>
                        </tr>
                        <tr>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">Lagging agents</td>
                            <td style="border:1px solid #d1d5db; padding:8px;">${laggingHtml}</td>
                            <td style="border:1px solid #d1d5db; padding:8px; color:#065f46; background:#f0fdf4;">${laggingAction}</td>
                        </tr>
                    </table>${improvementPlanBlock}
                </div>
            `;
            document.getElementById('tl-conclusions').innerHTML = tableHtml;
        }
"""
# DEBUG: check before re.sub
var_before = html.count('var MODULE_IMPROVEMENT_PLAN_URL')
const_before = html.count('const MODULE_IMPROVEMENT_PLAN_URL')
pattern_tl = r"(?s)\n\s*function generateTLConclusions\(data, isMet\) \{.*?\n\s*\}\n\s*\n\s*function initSTLView"
m_before = re.search(pattern_tl, html)
print(f"DEBUG before re.sub: var={var_before}, const={const_before}, tl_match={m_before is not None}", file=sys.stderr)

html = re.sub(
    r"(?s)\n\s*function generateTLConclusions\(data, isMet\) \{.*?\n\s*\}\n\s*\n\s*function initSTLView",
    "\n" + tl_conclusion_fn + "\n\n        function initSTLView",
    html,
    count=1
)

# DEBUG: check after re.sub
var_after = html.count('var MODULE_IMPROVEMENT_PLAN_URL')
const_after = html.count('const MODULE_IMPROVEMENT_PLAN_URL')
m_after = re.search(pattern_tl, html)
print(f"DEBUG after re.sub: var={var_after}, const={const_after}, tl_match={m_after is not None}", file=sys.stderr)

stl_conclusion_fn = """\
        function generateSTLConclusions(data, isMet, displayAchievement, displayGap) {
            const module = document.getElementById('stl-module-select').value;
            const moduleForPlan = (module === 'all' || !module) ? '' : module;
            const improvementPlanBlock = isMet ? '' : buildImprovementPlanBlock(moduleForPlan);
            const selectedWeekLabel = document.getElementById('stl-week-select') ? document.getElementById('stl-week-select').value : REAL_DATA.defaultStlWeek;
            const groups = (REAL_DATA.groupPerformance[module] || []).map(g => {
                const wm = REAL_DATA.groupPerformanceByWeek && REAL_DATA.groupPerformanceByWeek[module] && REAL_DATA.groupPerformanceByWeek[module][g.name]
                    ? REAL_DATA.groupPerformanceByWeek[module][g.name][selectedWeekLabel]
                    : null;
                return wm || g;
            });
            const fmt = (v, d = 1, suffix = '') => (v === null || v === undefined || Number.isNaN(Number(v))) ? '--' : (Number(v).toFixed(d) + suffix);
            const summarize = (list) => {
                const n = Math.max(1, list.length);
                return {
                    achievement: list.reduce((s, g) => s + (Number(g.achievement) || 0), 0) / n,
                    attendance: list.reduce((s, g) => s + (Number(g.attendance) || 0), 0) / n,
                    connectRate: list.reduce((s, g) => s + (Number(g.connectRate) || 0), 0) / n,
                    callLossRate: list.reduce((s, g) => s + (Number(g.callLossRate) || 0), 0) / n,
                    calls: list.reduce((s, g) => s + (Number(g.calls) || 0), 0) / n
                };
            };
            const moduleAvg = summarize(groups);
            const allGroups = Object.keys(REAL_DATA.groupPerformance || {}).flatMap(k => REAL_DATA.groupPerformance[k] || []);
            const allAvg = summarize(allGroups);

            const laggingGroups = [...groups]
                .map(g => ({
                    name: g.name || '--',
                    achievement: Number(g.achievement),
                    attendance: Number(g.attendance),
                    connectRate: Number(g.connectRate),
                    calls: Number(g.calls),
                    gap: (Number(g.target) || 0) - (Number(g.actual) || 0)
                }))
                .sort((a, b) => {
                    const ax = a.achievement !== null && a.achievement !== undefined ? a.achievement : 999;
                    const ay = b.achievement !== null && b.achievement !== undefined ? b.achievement : 999;
                    if (ax !== ay) return ax - ay;
                    return (b.gap || 0) - (a.gap || 0);
                })
                .slice(0, 3);

            const bd = REAL_DATA.stlBreakdownByWeek && REAL_DATA.stlBreakdownByWeek[module] ? REAL_DATA.stlBreakdownByWeek[module][selectedWeekLabel] : null;
            const pickWeakDims = (rows) => {
                const valid = (rows || []).filter(r => r.repayRate !== null && r.repayRate !== undefined);
                if (valid.length === 0) return [];
                const avg = valid.reduce((s, r) => s + Number(r.repayRate), 0) / valid.length;
                return valid.filter(r => Number(r.repayRate) < avg)
                    .sort((a, b) => Number(a.repayRate) - Number(b.repayRate))
                    .slice(0, 2)
                    .map(r => `${r.dimensionValue}(${fmt(r.repayRate, 1, '%')})`);
            };
            const weakCaseStages = pickWeakDims(bd ? bd.caseStage : []);
            const weakPrincipalStages = pickWeakDims(bd ? bd.principalStage : []);

            // 容忍带配置（相对全模块均值）
            const ATTENDANCE_TOLERANCE = 2.0;
            const CONNECT_TOLERANCE = 5.0;
            const LOSS_TOLERANCE = 5.0;
            const CALLS_TOLERANCE = 0.10;

            const peopleSummary = (moduleAvg.attendance < allAvg.attendance - ATTENDANCE_TOLERANCE || moduleAvg.calls < allAvg.calls * (1 - CALLS_TOLERANCE))
                ? `People factor risk: attendance ${fmt(moduleAvg.attendance, 1, '%')} (all-module avg ${fmt(allAvg.attendance, 1, '%')}), calls ${fmt(moduleAvg.calls, 0)} (all-module avg ${fmt(allAvg.calls, 0)}).`
                : `People factors are stable at module level this week.`;
            const strategySummary = (weakCaseStages.length > 0 || weakPrincipalStages.length > 0)
                ? `Stage preference imbalance (strategy): some agents/groups show declining contribution in overdue or amount stages. Action: adjust follow-up strategy and prioritize these stages.`
                : `No clear stage preference imbalance detected from current breakdown data.`;
            const toolSummary = (moduleAvg.connectRate < allAvg.connectRate - CONNECT_TOLERANCE || moduleAvg.callLossRate > allAvg.callLossRate + LOSS_TOLERANCE)
                ? `Tool usage risk: connect ${fmt(moduleAvg.connectRate, 1, '%')} (all-module avg ${fmt(allAvg.connectRate, 1, '%')}), call loss ${fmt(moduleAvg.callLossRate, 1, '%')} (all-module avg ${fmt(allAvg.callLossRate, 1, '%')}); inspect channel quality and dialing schedule.`
                : `Tool usage appears stable at module level.`;

            let peopleAction = '';
            const attdLow = moduleAvg.attendance < allAvg.attendance - ATTENDANCE_TOLERANCE;
            const callsLow = moduleAvg.calls < allAvg.calls * (1 - CALLS_TOLERANCE);
            if (attdLow && callsLow) {
                peopleAction = 'Attendance & calls below all-module average. Check absenteeism and reallocate staff if needed; review low-productivity groups for system issues or idle time.';
            } else if (attdLow) {
                peopleAction = 'Attendance below all-module average. Check absenteeism and consider cross-group support.';
            } else if (callsLow) {
                peopleAction = 'Call volume below all-module average. Follow up with low-productivity groups and review system allocation and online hours.';
            } else {
                peopleAction = 'People metrics stable. Maintain current scheduling and productivity monitoring.';
            }

            let strategyAction = '';
            if (weakCaseStages.length > 0 && weakPrincipalStages.length > 0) {
                strategyAction = 'Reprioritize follow-up on stages ' + weakCaseStages.join(', ') + ' and increase weight for principal stages ' + weakPrincipalStages.join(', ') + '.';
            } else if (weakCaseStages.length > 0) {
                strategyAction = 'Reprioritize follow-up on stages ' + weakCaseStages.join(', ') + ' and verify script coverage and training.';
            } else if (weakPrincipalStages.length > 0) {
                strategyAction = 'Increase allocation weight or customize collection strategy for principal stages ' + weakPrincipalStages.join(', ') + '.';
            } else {
                strategyAction = 'Stage distribution normal. Maintain current strategy.';
            }

            let toolAction = '';
            const connLow = moduleAvg.connectRate < allAvg.connectRate - CONNECT_TOLERANCE;
            const lossHigh = moduleAvg.callLossRate > allAvg.callLossRate + LOSS_TOLERANCE;
            if (connLow && lossHigh) {
                toolAction = 'Channel quality check: verify number quality and line stability; adjust dialing hours. Also investigate drop-off causes (line/network/script) to improve first-call retention.';
            } else if (connLow) {
                toolAction = 'Channel quality check: verify number quality and line stability; try adjusting dialing hours (e.g. avoid local rush hours).';
            } else if (lossHigh) {
                toolAction = 'Drop-off root cause: investigate post-connection drops (line/network/script) and optimize opening lines.';
            } else {
                toolAction = 'Outbound channel stable. Maintain current line configuration.';
            }

            const environmentAction = 'If confirmed, document impact in improvement plan and adjust priority accordingly.';

            let laggingAction = '';
            if (laggingGroups.length === 0) {
                laggingAction = 'No lagging groups this week. Maintain current management rhythm.';
            } else {
                laggingAction = 'One-on-one follow-up with lagging groups: ' + laggingGroups.map(g => g.name).join(', ') + '. Set 3-5 day improvement plan with daily check-ins.';
            }

            const laggingHtml = laggingGroups.length === 0
                ? '<div style="color:#6b7280;">No lagging group identified for selected week.</div>'
                : laggingGroups.map((g, idx) => `<div style="padding:6px 8px; border:1px solid #e5e7eb; border-radius:6px; margin-bottom:6px;">
                        <b>#${idx + 1} ${g.name}</b> |
                        Achv ${fmt(g.achievement, 1, '%')} |
                        Attendance ${fmt(g.attendance, 1, '%')} |
                        Calls ${fmt(g.calls, 0)} |
                        Connect ${fmt(g.connectRate, 1, '%')} |
                        Gap ${fmt(g.gap, 0)}
                    </div>`).join('');

            const tableHtml = `
                <div style="font-size:12px; color:#111827; line-height:1.5;">
                    <div style="font-weight:700; margin-bottom:8px;">STL conclusion = module-level overview + lagging groups</div>
                    <table style="width:100%; border-collapse:collapse; font-size:12px;">
                        <tr style="background:#f8fafc;">
                            <td style="border:1px solid #d1d5db; padding:8px; width:140px; font-weight:700;">Dimension</td>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">Diagnosis</td>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700; width:280px;">Suggested Action</td>
                        </tr>
                        <tr style="background:#f8fafc;">
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">Module overview</td>
                            <td style="border:1px solid #d1d5db; padding:8px;">
                                Module: <b>${module}</b> @ ${selectedWeekLabel}<br>
                                Achievement: <b>${fmt(moduleAvg.achievement, 1, '%')}</b> | Attendance: <b>${fmt(moduleAvg.attendance, 1, '%')}</b> | Calls: <b>${fmt(moduleAvg.calls, 0)}</b>
                            </td>
                            <td style="border:1px solid #d1d5db; padding:8px; color:#065f46; background:#f0fdf4;">Continue monitoring core module metrics and watch gaps vs all-module average.</td>
                        </tr>
                        <tr>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">People factors</td>
                            <td style="border:1px solid #d1d5db; padding:8px;">${peopleSummary}</td>
                            <td style="border:1px solid #d1d5db; padding:8px; color:#065f46; background:#f0fdf4;">${peopleAction}</td>
                        </tr>
                        <tr>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">Strategy factors</td>
                            <td style="border:1px solid #d1d5db; padding:8px;">
                                ${strategySummary}<br>
                                Overdue stages with weak contribution: ${weakCaseStages.length ? weakCaseStages.join(', ') : '--'}<br>
                                Amount stages with weak contribution: ${weakPrincipalStages.length ? weakPrincipalStages.join(', ') : '--'}
                            </td>
                            <td style="border:1px solid #d1d5db; padding:8px; color:#065f46; background:#f0fdf4;">${strategyAction}</td>
                        </tr>
                        <tr>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">Tool factors</td>
                            <td style="border:1px solid #d1d5db; padding:8px;">${toolSummary}</td>
                            <td style="border:1px solid #d1d5db; padding:8px; color:#065f46; background:#f0fdf4;">${toolAction}</td>
                        </tr>
                        <tr>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">Environment/other</td>
                            <td style="border:1px solid #d1d5db; padding:8px;">If holiday/policy/system events occurred, use manual override for action priority.</td>
                            <td style="border:1px solid #d1d5db; padding:8px; color:#065f46; background:#f0fdf4;">${environmentAction}</td>
                        </tr>
                        <tr>
                            <td style="border:1px solid #d1d5db; padding:8px; font-weight:700;">Lagging groups</td>
                            <td style="border:1px solid #d1d5db; padding:8px;">${laggingHtml}</td>
                            <td style="border:1px solid #d1d5db; padding:8px; color:#065f46; background:#f0fdf4;">${laggingAction}</td>
                        </tr>
                    </table>${improvementPlanBlock}
                </div>
            `;
            document.getElementById('stl-conclusions').innerHTML = tableHtml;
        }
"""
html = re.sub(
    r"(?s)\n\s*function generateSTLConclusions\(data, isMet, displayAchievement, displayGap\) \{.*?\n\s*\}\n\s*\n\s*// ===================== DATA VIEW =====================",
    "\n" + stl_conclusion_fn + "\n\n        // ===================== DATA VIEW =====================",
    html,
    count=1
)

# ---- 24. Recovery Trend status: same metric as chart — repayRate vs targetRepayRate @ dataDate ----
risk_status_fn = """\
        function calculateAtRisk(module) {
            // Extensibility: e.g. 'mtd_linear' | 'rate_vs_target_cutoff' (default matches Recovery Trend chart).
            const RECOVERY_TREND_STATUS_POLICY = { mode: 'rate_vs_target_cutoff' };

            const mData = REAL_DATA.moduleMonthly[module];
            const monthTarget = mData ? Number(mData.monthTarget || 0) : 0;
            const currentActual = mData ? Number(mData.currentActual || 0) : 0;
            const currentDay = mData ? Math.max(1, Number(mData.currentDay || 1)) : 1;
            const monthDays = mData ? Math.max(1, Number(mData.monthDays || 1)) : 1;
            const remainingDays = Math.max(0, monthDays - currentDay);
            const dailyAvg = currentDay > 0 ? (currentActual / currentDay) : 0;
            const projectedSimple = currentActual + (dailyAvg * remainingDays);
            const projectedConservative = projectedSimple;
            const projectedMomentum = projectedSimple;
            const dailyTrend = dailyAvg;
            const progressRatio = monthDays > 0 ? (currentDay / monthDays) : 0;
            const achievementRatio = monthTarget > 0 ? (currentActual / monthTarget) : 0;
            const mtdTargetLinear = monthTarget * progressRatio;
            const progressGap = achievementRatio - progressRatio;
            const gap = monthTarget - currentActual;
            const simpleAch = monthTarget > 0 ? ((projectedSimple / monthTarget) * 100) : 0;
            const conservativeAch = simpleAch;
            const momentumAch = simpleAch;

            const cutoff = REAL_DATA.dataDate;
            const trend = REAL_DATA.moduleDailyTrends && REAL_DATA.moduleDailyTrends[module]
                ? REAL_DATA.moduleDailyTrends[module]
                : null;
            const dailyRows = trend && trend.daily ? trend.daily : [];
            let compareRow = null;
            for (let i = dailyRows.length - 1; i >= 0; i--) {
                const r = dailyRows[i];
                if (r.date > cutoff) continue;
                const a = r.repayRate;
                const t = r.targetRepayRate;
                if (a !== null && a !== undefined && t !== null && t !== undefined) {
                    compareRow = r;
                    break;
                }
            }

            let status = 'tentative';
            let statusLabel = 'Tentative';
            let badgeClass = 'status-badge';
            let isAtRisk = false;

            if (RECOVERY_TREND_STATUS_POLICY.mode === 'rate_vs_target_cutoff') {
                if (!compareRow) {
                    status = 'tentative';
                    statusLabel = 'Tentative';
                    badgeClass = 'status-badge';
                    isAtRisk = false;
                } else {
                    const a = compareRow.repayRate;
                    const t = compareRow.targetRepayRate;
                    if (a >= t) {
                        status = 'on_track';
                        statusLabel = 'On Track';
                        badgeClass = 'status-badge status-success';
                        isAtRisk = false;
                    } else {
                        status = 'at_risk';
                        statusLabel = 'At Risk';
                        badgeClass = 'status-badge status-danger';
                        isAtRisk = true;
                    }
                }
            } else if (RECOVERY_TREND_STATUS_POLICY.mode === 'mtd_linear' && monthTarget > 0) {
                if (currentActual >= mtdTargetLinear) {
                    status = 'on_track';
                    statusLabel = 'On Track';
                    badgeClass = 'status-badge status-success';
                    isAtRisk = false;
                } else {
                    status = 'at_risk';
                    statusLabel = 'At Risk';
                    badgeClass = 'status-badge status-danger';
                    isAtRisk = true;
                }
            }

            return {
                isAtRisk: isAtRisk,
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
                requiredDaily: remainingDays > 0 ? (gap / remainingDays) : 0,
                targetByNow: mtdTargetLinear,
                progressRatio: progressRatio,
                achievementRatio: achievementRatio,
                progressGap: progressGap,
                compareDate: compareRow ? compareRow.date : null,
                compareActualRate: compareRow ? compareRow.repayRate : null,
                compareTargetRate: compareRow ? compareRow.targetRepayRate : null
            };
        }
"""
html = re.sub(
    r"(?s)\n\s*function calculateAtRisk\(module\) \{.*?\n\s*\}\n\s*\n\s*function loadRiskModuleReview",
    "\n" + risk_status_fn + "\n\n        function loadRiskModuleReview",
    html,
    count=1
)

risk_review_fn = """\
        function loadRiskModuleReview() {
            const riskModules = [];
            getVisibleModules().forEach(module => {
                const risk = calculateAtRisk(module);
                if (risk.isAtRisk) riskModules.push(module);
            });

            riskModules.sort((a, b) => {
                const riskA = calculateAtRisk(a);
                const riskB = calculateAtRisk(b);
                return riskA.conservativeAch - riskB.conservativeAch;
            });

            const reviewSection = document.getElementById('risk-module-review');
            const content = document.getElementById('risk-module-content');
            if (riskModules.length === 0) {
                reviewSection.style.display = 'none';
                return;
            }

            reviewSection.style.display = 'block';
            content.innerHTML = '';

            const headerHtml = '<div style="background: #fef3c7; border-left: 4px solid #d97706; padding: 12px; border-radius: 0 4px 4px 0; margin-bottom: 16px; font-size: 12px; color: #92400e;">' +
                '<strong>Status Logic:</strong> On Track if natural-month actual repay rate ≥ daily target rate on REAL_DATA.dataDate (same as chart); otherwise At Risk. ' +
                'Policy: RECOVERY_TREND_STATUS_POLICY.mode \\'rate_vs_target_cutoff\\' (alt: \\'mtd_linear\\').' +
                '</div>';
            content.innerHTML += headerHtml;

            riskModules.forEach(module => {
                const groups = (REAL_DATA.riskModuleGroups[module] || []).slice().sort((a, b) => {
                    const av = (a.achievement !== null && a.achievement !== undefined) ? a.achievement : 999;
                    const bv = (b.achievement !== null && b.achievement !== undefined) ? b.achievement : 999;
                    return av - bv;
                });

                let html = '<div style="margin-bottom: 24px;">';
                html += '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">';
                html += '<h4 style="font-size: 14px; font-weight: 600; color: #991b1b;">Module ' + module + '</h4>';
                html += '<span class="status-badge status-danger">At Risk</span>';
                html += '</div>';

                html += '<table style="width: 100%; border-collapse: collapse; font-size: 13px;">';
                html += '<tr style="background: #f8fafc; border-bottom: 1px solid #e2e8f0;">' +
                    '<th style="padding: 8px; text-align: left;">Group</th>' +
                    '<th style="padding: 8px; text-align: right;">Target</th>' +
                    '<th style="padding: 8px; text-align: right;">Actual</th>' +
                    '<th style="padding: 8px; text-align: right;">Achievement</th>' +
                    '<th style="padding: 8px; text-align: right;">Calls</th>' +
                    '<th style="padding: 8px; text-align: right;">Conn%</th>' +
                    '<th style="padding: 8px; text-align: right;">PTP%</th>' +
                    '<th style="padding: 8px; text-align: right;">Call Loss%</th>' +
                    '<th style="padding: 8px; text-align: right;">Attd%</th></tr>';
                groups.forEach(g => {
                    const achColor = (g.achievement !== null && g.achievement !== undefined && g.achievement < 90) ? '#ef4444' : '#22c55e';
                    html += '<tr style="border-bottom: 1px solid #f1f5f9;">' +
                        '<td style="padding: 8px;">' + g.group + '</td>' +
                        '<td style="padding: 8px; text-align: right;">' + formatNumber(g.target) + '</td>' +
                        '<td style="padding: 8px; text-align: right;">' + formatNumber(g.actual) + '</td>' +
                        '<td style="padding: 8px; text-align: right; color: ' + achColor + '; font-weight: 600;">' + (g.achievement !== null && g.achievement !== undefined ? g.achievement.toFixed(1) + '%' : '--') + '</td>' +
                        '<td style="padding: 8px; text-align: right;">' + (g.calls !== null && g.calls !== undefined ? g.calls : '--') + '</td>' +
                        '<td style="padding: 8px; text-align: right;">' + (g.connectRate !== null && g.connectRate !== undefined ? g.connectRate.toFixed(1) + '%' : '--') + '</td>' +
                        '<td style="padding: 8px; text-align: right;">' + (g.ptpRate !== null && g.ptpRate !== undefined ? g.ptpRate.toFixed(1) + '%' : '--') + '</td>' +
                        '<td style="padding: 8px; text-align: right;">' + (g.callLossRate !== null && g.callLossRate !== undefined ? g.callLossRate.toFixed(1) + '%' : '--') + '</td>' +
                        '<td style="padding: 8px; text-align: right;">' + (g.attendance !== null && g.attendance !== undefined ? g.attendance + '%' : '--') + '</td>' +
                        '</tr>';
                });
                html += '</table></div>';
                content.innerHTML += html;
            });
        }
"""
html = re.sub(
    r"(?s)\n\s*function loadRiskModuleReview\(\) \{.*?\n\s*\}\n\s*\n\s*// ===================== INIT =====================",
    "\n" + risk_review_fn + "\n\n        // ===================== INIT =====================",
    html,
    count=1
)
# Safety: avoid leaking `orderedTrendModules` scope into risk review.
html = html.replace(
    "const riskModules = [];\n            orderedTrendModules.forEach(module => {",
    "const riskModules = [];\n            getVisibleModules().forEach(module => {"
)

html = html.replace(
    "                const risk = calculateAtRisk(module);\n                const isAtRisk = risk.isAtRisk;\n                const badgeClass = isAtRisk ? 'status-badge status-danger' : 'status-badge status-success';\n                const badgeText = isAtRisk ? 'At Risk' : 'On Track';",
    "                const risk = calculateAtRisk(module);\n                const badgeClass = risk.badgeClass;\n                const badgeText = risk.statusLabel;"
)

html = html.replace(
    "<strong>At-Risk Logic:</strong> Module is at risk if projected month-end recovery (based on 7-day average) is below monthly target. ' +\n                'Projection = Current MTD + (7-day Avg × Remaining Days).'",
    "<strong>Status Logic:</strong> On Track if natural-month actual repay rate ≥ daily target rate on REAL_DATA.dataDate (same as chart); otherwise At Risk. ' +\n                'Policy: RECOVERY_TREND_STATUS_POLICY.mode \\'rate_vs_target_cutoff\\' (alt: \\'mtd_linear\\').'"
)
html = html.replace(
    "<strong>Status Logic:</strong> On Track if MTD actual ≥ linear prorated month target (by calendar day); otherwise At Risk. ' +\n                'Policy hook: RECOVERY_TREND_STATUS_POLICY.mode === \\'mtd_linear\\' (extendable).'",
    "<strong>Status Logic:</strong> On Track if natural-month actual repay rate ≥ daily target rate on REAL_DATA.dataDate (same as chart); otherwise At Risk. ' +\n                'Policy: RECOVERY_TREND_STATUS_POLICY.mode \\'rate_vs_target_cutoff\\' (alt: \\'mtd_linear\\').'"
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

# ---- 24.2 TL/STL dynamic status override by Recovery Trend + today target badge ----
tl_init_date_selector_patch = """\
            // Populate TL date selector from real agent_repay dates
            const dateSel = document.getElementById('tl-date-select');
            dateSel.innerHTML = '';
            REAL_DATA.availableDates.forEach((dateStr, i) => {
                const selected = i === 0 ? ' selected' : '';
                dateSel.innerHTML += '<option value="' + dateStr + '"' + selected + '>' + dateStr + '</option>';
            });
"""
tl_init_date_selector_new = """\
            // Populate TL date selector from real agent_repay dates (+ today as selectable placeholder)
            const dateSel = document.getElementById('tl-date-select');
            dateSel.innerHTML = '';
            const todayStr = new Date().toISOString().split('T')[0];
            const selectorDates = (REAL_DATA.availableDates || []).slice();
            if (!selectorDates.includes(todayStr)) selectorDates.unshift(todayStr);
            selectorDates.forEach((dateStr, i) => {
                const selected = i === 0 ? ' selected' : '';
                dateSel.innerHTML += '<option value="' + dateStr + '"' + selected + '>' + dateStr + '</option>';
            });
"""
html = r1(html, tl_init_date_selector_patch, tl_init_date_selector_new)

tl_load_fn = """\
        function loadTLData() {
            const group = document.getElementById('tl-group-select').value;
            const selectedDate = document.getElementById('tl-date-select').value;
            const emptyState = document.getElementById('tl-empty-state');
            const metricsContainer = document.getElementById('tl-metrics-container');
            const chartCard = document.getElementById('tl-chart-card');
            const conclusionsCard = document.getElementById('tl-conclusions-card');

            const getTodayStr = () => new Date().toISOString().split('T')[0];
            const isTodaySelection = (d) => d === getTodayStr();
            const getGroupRateCompareAtDate = (groupId, dateStr) => {
                const gData = REAL_DATA.tlData && REAL_DATA.tlData[groupId] ? REAL_DATA.tlData[groupId] : null;
                const rows = gData && gData.days ? gData.days : [];
                for (let i = 0; i < rows.length; i++) {
                    if (rows[i].date === dateStr) {
                        const r = rows[i];
                        const groupRate = (r.nmRepayRate !== null && r.nmRepayRate !== undefined) ? r.nmRepayRate : r.repayRate;
                        if (groupRate !== null && groupRate !== undefined && r.targetRepayRate !== null && r.targetRepayRate !== undefined) {
                            return { actualRate: groupRate, targetRate: r.targetRepayRate };
                        }
                        return null;
                    }
                }
                return null;
            };
            const getGroupDailyTargetByDate = (groupId, dateStr) => {
                const agents = REAL_DATA.agentPerformance[groupId] || [];
                let sum = 0, cnt = 0;
                agents.forEach(a => {
                    const dm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[groupId] && REAL_DATA.agentPerformanceByDate[groupId][a.name]
                        ? REAL_DATA.agentPerformanceByDate[groupId][a.name][dateStr]
                        : null;
                    if (dm && dm.target !== null && dm.target !== undefined) { sum += Number(dm.target); cnt += 1; }
                });
                return cnt > 0 ? Math.round(sum) : null;
            };

            if (!group || !REAL_DATA.agentPerformance[group]) {
                emptyState.style.display = 'block';
                metricsContainer.style.display = 'none';
                chartCard.style.display = 'none';
                conclusionsCard.style.display = 'none';
                document.getElementById('tl-unmet-section').style.display = 'none';
                document.getElementById('tl-status-badge').innerHTML = '';
                return;
            }

            emptyState.style.display = 'none';
            metricsContainer.style.display = 'block';
            chartCard.style.display = 'block';
            conclusionsCard.style.display = 'block';

            const data = REAL_DATA.tlData[group];
            if (!data) return;
            const dayRows = data.days || [];
            const selectedDay = dayRows.find(d => d.date === selectedDate) || null;
            const displayTarget = selectedDay && selectedDay.target !== undefined && selectedDay.target !== null ? selectedDay.target : data.target;
            const displayActual = selectedDay && selectedDay.actual !== undefined && selectedDay.actual !== null ? selectedDay.actual : data.actual;
            const displayAchievement = displayTarget > 0 ? (displayActual / displayTarget * 100) : 0;
            const displayGap = Math.max(0, displayTarget - displayActual);

            const badge = document.getElementById('tl-status-badge');
            if (isTodaySelection(selectedDate)) {
                const todayTargetAmt = getGroupDailyTargetByDate(group, selectedDate);
                document.getElementById('tl-yesterday-target').textContent = todayTargetAmt !== null ? formatNumber(todayTargetAmt) : '--';
                document.getElementById('tl-yesterday-actual').textContent = '--';
                document.getElementById('tl-achievement-rate').textContent = '--';
                badge.innerHTML = '<span class=\"status-badge\" style=\"background:#eff6ff;color:#1d4ed8;\">Today Repay Target: ' + (todayTargetAmt !== null ? formatNumber(todayTargetAmt) : '--') + '</span>';
                document.getElementById('tl-unmet-section').style.display = 'none';
                chartCard.style.display = 'none';
                conclusionsCard.style.display = 'none';
                const ctn = document.getElementById('tl-conclusions');
                if (ctn) ctn.innerHTML = '';
                return;
            }

            chartCard.style.display = 'block';
            conclusionsCard.style.display = 'block';
            document.getElementById('tl-yesterday-target').textContent = formatNumber(displayTarget);
            document.getElementById('tl-yesterday-actual').textContent = formatNumber(displayActual);
            document.getElementById('tl-achievement-rate').textContent = displayAchievement.toFixed(1) + '%';
            const vsAvgCard = document.getElementById('tl-module-avg') ? document.getElementById('tl-module-avg').closest('.metric-card') : null;
            if (vsAvgCard) vsAvgCard.style.display = 'none';

            const compareRow = getGroupRateCompareAtDate(group, selectedDate);
            const isMet = !!(compareRow && compareRow.actualRate >= compareRow.targetRate);
            if (!compareRow) {
                badge.innerHTML = '<span class=\"status-badge\" style=\"background:#f3f4f6;color:#6b7280;\">Repay Target: N/A</span>';
                document.getElementById('tl-unmet-section').style.display = 'none';
            } else if (isMet) {
                badge.innerHTML = '<span class=\"status-badge status-success\">Repay Target: Met</span>';
                document.getElementById('tl-unmet-section').style.display = 'none';
            } else {
                badge.innerHTML = '<span class=\"status-badge status-danger\">Repay Target: Unmet</span>';
                document.getElementById('tl-unmet-section').style.display = 'block';
                document.getElementById('tl-gap-amount').textContent = formatNumber(displayGap);
                const processTarget = REAL_DATA.processTargets && REAL_DATA.processTargets[data.groupModule] ? REAL_DATA.processTargets[data.groupModule] : null;
                const callBenchmark = processTarget && processTarget.artCallTimes !== undefined && processTarget.artCallTimes !== null ? processTarget.artCallTimes : null;
                const callBillminBenchmark = processTarget && processTarget.callBillminRawTarget !== undefined && processTarget.callBillminRawTarget !== null ? processTarget.callBillminRawTarget : null;
                const agentsForAvg = REAL_DATA.agentPerformance[group] || [];
                let callsSum = 0, billminSum = 0, cnt = 0;
                agentsForAvg.forEach(agent => {
                    const dm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][agent.name] ? REAL_DATA.agentPerformanceByDate[group][agent.name][selectedDate] : null;
                    const c = dm && dm.artCallTimes !== undefined ? dm.artCallTimes : agent.artCallTimes;
                    const b = dm && dm.callBillmin !== undefined ? dm.callBillmin : agent.callBillmin;
                    if (c !== null && c !== undefined && b !== null && b !== undefined) { callsSum += c; billminSum += b; cnt += 1; }
                });
                const groupAvgCalls = cnt > 0 ? callsSum / cnt : 0;
                const groupAvgBillmin = cnt > 0 ? billminSum / cnt : 0;
                const processTargetMet = (callBenchmark !== null && callBillminBenchmark !== null) ? (groupAvgCalls >= callBenchmark && groupAvgBillmin >= callBillminBenchmark) : null;
                const processTargetBadge = processTargetMet === null ? '<span class=\"status-badge\" style=\"background:#f3f4f6;color:#6b7280;\">Process Target: No Target</span>' : (processTargetMet ? '<span class=\"status-badge status-success\">Process Target: Met</span>' : '<span class=\"status-badge status-danger\">Process Target: Unmet</span>');
                badge.innerHTML += ' <br>' + processTargetBadge;
                const callGap = callBenchmark !== null ? Math.round(groupAvgCalls - callBenchmark) : null;
                const callBillminGap = callBillminBenchmark !== null ? Math.round((groupAvgBillmin - callBillminBenchmark) * 10) / 10 : null;
                const repayTarget = displayTarget;
                const repayActual = displayActual;
                const repayGap = (repayActual !== null && repayActual !== undefined && repayTarget !== null && repayTarget !== undefined) ? (repayActual - repayTarget) : null;
                const tlGapEl = document.getElementById('tl-gap-amount');
                if (tlGapEl) tlGapEl.textContent = repayGap !== null ? ((repayGap > 0 ? '+' : '') + formatNumber(Math.round(repayGap))) : '--';
                document.getElementById('tl-call-gap').textContent = callGap !== null ? (callGap > 0 ? '+' : '') + callGap : '--';
                document.getElementById('tl-connect-gap').textContent = callBillminGap !== null ? (callBillminGap > 0 ? '+' : '') + callBillminGap.toFixed(1) : '--';
                const tlGapMeta = document.getElementById('tl-gap-meta');
                if (tlGapMeta) tlGapMeta.textContent = 'Target: ' + formatNumber(repayTarget) + ' | Actual: ' + formatNumber(repayActual);
                const tlCallGapMeta = document.getElementById('tl-call-gap-meta');
                if (tlCallGapMeta) tlCallGapMeta.textContent = 'Target: ' + (callBenchmark !== null ? callBenchmark.toFixed(0) : '--') + ' | Actual: ' + groupAvgCalls.toFixed(0);
                const tlConnectGapMeta = document.getElementById('tl-connect-gap-meta');
                if (tlConnectGapMeta) tlConnectGapMeta.textContent = 'Target: ' + (callBillminBenchmark !== null ? callBillminBenchmark.toFixed(1) : '--') + ' | Actual: ' + groupAvgBillmin.toFixed(1);
            }

            loadTLAgentTable(group);
            const tlViewData = Object.assign({}, data, {
                target: displayTarget,
                actual: displayActual,
                achievement: displayAchievement,
                gap: displayGap
            });
            generateTLConclusions(tlViewData, isMet);
            const selectedDateVal = document.getElementById('tl-date-select').value;
            renderTLChart(group, selectedDateVal);
        }
"""
html = re.sub(
    r"(?s)\n\s*function loadTLData\(\) \{.*?\n\s*\}\n\s*\n\s*function loadTLAgentTable",
    "\n" + tl_load_fn + "\n\n        function loadTLAgentTable",
    html,
    count=1
)

stl_load_fn = """\
        function loadSTLData() {
            const module = document.getElementById('stl-module-select').value;
            const emptyState = document.getElementById('stl-empty-state');
            const metricsContainer = document.getElementById('stl-metrics-container');
            const chartCard = document.getElementById('stl-chart-card');
            const conclusionsCard = document.getElementById('stl-conclusions-card');

            const getTodayStr = () => new Date().toISOString().split('T')[0];
            const weekEndDateFromLabel = (weekLabel) => {
                if (!weekLabel) return null;
                const year = String(REAL_DATA.dataDate || '').slice(0, 4);
                const parts = String(weekLabel).split(' - ');
                const endPart = parts.length > 1 ? parts[1] : parts[0];
                const md = endPart.split('/');
                if (md.length !== 2) return null;
                const mm = String(parseInt(md[0], 10)).padStart(2, '0');
                const dd = String(parseInt(md[1], 10)).padStart(2, '0');
                return year + '-' + mm + '-' + dd;
            };
            const getRateCompareAtDate = (moduleKey, dateStr) => {
                const trend = REAL_DATA.moduleDailyTrends && REAL_DATA.moduleDailyTrends[moduleKey] ? REAL_DATA.moduleDailyTrends[moduleKey] : null;
                const rows = trend && trend.daily ? trend.daily : [];
                let exact = null;
                for (let i = 0; i < rows.length; i++) {
                    if (rows[i].date === dateStr) { exact = rows[i]; break; }
                }
                if (exact && exact.repayRate !== null && exact.repayRate !== undefined && exact.targetRepayRate !== null && exact.targetRepayRate !== undefined) return exact;
                let fallback = null;
                for (let i = rows.length - 1; i >= 0; i--) {
                    const r = rows[i];
                    if (r.date > dateStr) continue;
                    if (r.repayRate !== null && r.repayRate !== undefined && r.targetRepayRate !== null && r.targetRepayRate !== undefined) { fallback = r; break; }
                }
                return fallback;
            };
            const isRecoveryTrendAheadAtDate = (moduleKey, dateStr) => {
                const row = getRateCompareAtDate(moduleKey, dateStr);
                return !!(row && row.repayRate >= row.targetRepayRate);
            };
            const weekContainsDate = (weekLabel, dateStr) => {
                if (!weekLabel || !dateStr) return false;
                const md = String(dateStr).slice(5).replace('-', '/');
                return String(weekLabel).includes(md);
            };
            const getModuleDailyTargetByDate = (moduleKey, dateStr) => {
                const groupsInModule = (REAL_DATA.groups || []).filter(g => REAL_DATA.tlData[g] && REAL_DATA.tlData[g].groupModule === moduleKey);
                let sum = 0, cnt = 0;
                groupsInModule.forEach(groupId => {
                    const agents = REAL_DATA.agentPerformance[groupId] || [];
                    agents.forEach(a => {
                        const dm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[groupId] && REAL_DATA.agentPerformanceByDate[groupId][a.name]
                            ? REAL_DATA.agentPerformanceByDate[groupId][a.name][dateStr]
                            : null;
                        if (dm && dm.target !== null && dm.target !== undefined) { sum += Number(dm.target); cnt += 1; }
                    });
                });
                return cnt > 0 ? Math.round(sum) : null;
            };

            if (!module || !REAL_DATA.stlData[module]) {
                emptyState.style.display = 'block';
                metricsContainer.style.display = 'none';
                chartCard.style.display = 'none';
                conclusionsCard.style.display = 'none';
                document.getElementById('stl-unmet-section').style.display = 'none';
                document.getElementById('stl-status-badge').innerHTML = '';
                return;
            }

            emptyState.style.display = 'none';
            metricsContainer.style.display = 'block';
            chartCard.style.display = 'block';
            conclusionsCard.style.display = 'block';

            const data = REAL_DATA.stlData[module];

            const weekSel = document.getElementById('stl-week-select');
            const weeksArr = data.weeks;
            const selectedWeekLabel = weekSel ? weekSel.value : REAL_DATA.defaultStlWeek;
            const selectedWeekPos = weeksArr.findIndex(w => w.weekLabel === selectedWeekLabel);
            const weekIdx = selectedWeekPos >= 0 ? (weeksArr.length - 1 - selectedWeekPos) : 0;
            const weekData = weeksArr[weeksArr.length - 1 - weekIdx] || weeksArr[weeksArr.length - 1];

            const displayTarget = weekData ? weekData.target : data.target;
            const displayActual = weekData ? weekData.actual : data.actual;
            const displayAchievement = displayTarget > 0 ? (displayActual / displayTarget * 100) : 0;
            const displayGap = Math.max(0, displayTarget - displayActual);
            const prevWeekData = (selectedWeekPos > 0) ? weeksArr[selectedWeekPos - 1] : null;
            const prevWeekActual = prevWeekData && prevWeekData.actual !== undefined && prevWeekData.actual !== null ? prevWeekData.actual : 0;
            const displayTrendPct = prevWeekActual > 0 ? ((displayActual - prevWeekActual) / prevWeekActual * 100) : 0;
            const displayTrend = (prevWeekActual > 0 ? ((displayTrendPct >= 0 ? '+' : '') + displayTrendPct.toFixed(1) + '%') : 'N/A');

            const compareDate = weekEndDateFromLabel(selectedWeekLabel) || REAL_DATA.dataDate;
            const trendAhead = isRecoveryTrendAheadAtDate(module, compareDate);
            const isMetByAchievement = displayAchievement >= 100;
            const isMet = trendAhead || isMetByAchievement;

            document.getElementById('stl-week-target').textContent = formatNumber(displayTarget);
            document.getElementById('stl-week-actual').textContent = formatNumber(displayActual);
            document.getElementById('stl-achievement-rate').textContent = displayAchievement.toFixed(1) + '%';
            document.getElementById('stl-trend').textContent = displayTrend;

            const badge = document.getElementById('stl-status-badge');
            if (isMet) {
                badge.innerHTML = '<span class=\"status-badge status-success\">Weekly Repay Target: Met</span>';
                document.getElementById('stl-unmet-section').style.display = 'none';
            } else {
                badge.innerHTML = '<span class=\"status-badge status-danger\">Weekly Repay Target: Unmet</span>';
                document.getElementById('stl-unmet-section').style.display = 'block';
            }

            const processTarget = REAL_DATA.processTargets && REAL_DATA.processTargets[module] ? REAL_DATA.processTargets[module] : {};
            const callBenchmark = processTarget.artCallTimes !== null && processTarget.artCallTimes !== undefined ? processTarget.artCallTimes : null;
            const callBillminBenchmark = processTarget.callBillminRawTarget !== null && processTarget.callBillminRawTarget !== undefined ? processTarget.callBillminRawTarget : null;
            const groupsForGap = REAL_DATA.groupPerformance[module] || [];
            const selectedWeekLabelForGap = document.getElementById('stl-week-select') ? document.getElementById('stl-week-select').value : REAL_DATA.defaultStlWeek;
            const weekRows = groupsForGap.map(g => {
                const wm = REAL_DATA.groupPerformanceByWeek && REAL_DATA.groupPerformanceByWeek[module] && REAL_DATA.groupPerformanceByWeek[module][g.name] ? REAL_DATA.groupPerformanceByWeek[module][g.name][selectedWeekLabelForGap] : null;
                return { calls: wm && wm.calls !== undefined ? wm.calls : g.calls, callBillmin: wm && wm.callBillmin !== undefined ? wm.callBillmin : g.callBillmin };
            });
            const avgCalls = weekRows.length > 0 ? weekRows.reduce((sum, r) => sum + (r.calls || 0), 0) / weekRows.length : 0;
            const avgCallBillmin = weekRows.length > 0 ? weekRows.reduce((sum, r) => sum + (r.callBillmin || 0), 0) / weekRows.length : 0;
            const hasProcessTarget = callBenchmark !== null && callBillminBenchmark !== null;
            const callGap = hasProcessTarget ? (avgCalls - callBenchmark) : null;
            const callBillminGap = hasProcessTarget ? (avgCallBillmin - callBillminBenchmark) : null;
            const processTargetMet = hasProcessTarget ? (avgCalls >= callBenchmark) && (avgCallBillmin >= callBillminBenchmark) : null;
            const processTargetBadge = processTargetMet === null ? '<span class=\"status-badge\" style=\"background:#f3f4f6;color:#6b7280;\">Process Target: No Target</span>' : (processTargetMet ? '<span class=\"status-badge status-success\">Process Target: Met</span>' : '<span class=\"status-badge status-danger\">Process Target: Unmet</span>');
            badge.innerHTML += ' <br>' + processTargetBadge;
            const stlGapEl = document.getElementById('stl-gap-amount');
            if (stlGapEl) stlGapEl.textContent = (displayActual > displayTarget ? '+' : '') + formatNumber(Math.round(displayActual - displayTarget));
            const stlCallGapEl = document.getElementById('stl-call-gap');
            if (stlCallGapEl) stlCallGapEl.textContent = callGap !== null ? ((callGap > 0 ? '+' : '') + callGap.toFixed(0)) : '--';
            const stlConnectGapEl = document.getElementById('stl-connect-gap');
            if (stlConnectGapEl) stlConnectGapEl.textContent = callBillminGap !== null ? ((callBillminGap > 0 ? '+' : '') + callBillminGap.toFixed(1)) : '--';
            const stlGapMeta = document.getElementById('stl-gap-meta');
            if (stlGapMeta) stlGapMeta.textContent = 'Target: ' + formatNumber(displayTarget) + ' | Actual: ' + formatNumber(displayActual);
            const stlCallGapMeta = document.getElementById('stl-call-gap-meta');
            if (stlCallGapMeta) stlCallGapMeta.textContent = 'Target: ' + (callBenchmark !== null ? callBenchmark.toFixed(0) : '--') + ' | Actual: ' + avgCalls.toFixed(0);
            const stlConnectGapMeta = document.getElementById('stl-connect-gap-meta');
            if (stlConnectGapMeta) stlConnectGapMeta.textContent = 'Target: ' + (callBillminBenchmark !== null ? callBillminBenchmark.toFixed(1) : '--') + ' | Actual: ' + avgCallBillmin.toFixed(1);

            const todayStr = getTodayStr();
            if (weekContainsDate(selectedWeekLabel, todayStr)) {
                const todayTargetAmt = getModuleDailyTargetByDate(module, todayStr);
                const targetHtml = todayTargetAmt !== null ? formatNumber(todayTargetAmt) : '--';
                badge.innerHTML += ' <br><span class=\"status-badge\" style=\"background:#eff6ff;color:#1d4ed8;\">Today Repay Target: ' + targetHtml + '</span>';
            }

            loadSTLGroupTable(module);
            const stlViewData = Object.assign({}, data, {
                target: displayTarget,
                actual: displayActual,
                achievement: displayAchievement,
                trend: displayTrend
            });
            generateSTLConclusions(stlViewData, isMet, displayAchievement, displayGap);
            renderSTLChart(data.weeks, weekIdx);
        }
"""
html = re.sub(
    r"(?s)\n\s*function loadSTLData\(\) \{.*?\n\s*\}\n\s*\n\s*function loadSTLGroupTable",
    "\n" + stl_load_fn + "\n\n        function loadSTLGroupTable",
    html,
    count=1
)

# TL consecutive unmet days in drilldown should follow selected date history instead of fixed latest value
html = html.replace(
    "                const cd = agent.consecutiveDays;",
    "                const hist = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][agent.name] ? REAL_DATA.agentPerformanceByDate[group][agent.name] : null;\n                const allDatesAsc = (REAL_DATA.availableDates || []).slice().reverse();\n                const anchorDate = document.getElementById('tl-date-select') ? document.getElementById('tl-date-select').value : REAL_DATA.dataDate;\n                const anchorIdx = allDatesAsc.indexOf(anchorDate);\n                let cd = 0;\n                if (hist && anchorIdx >= 0) {\n                    for (let i = anchorIdx; i >= 0; i--) {\n                        const d = allDatesAsc[i];\n                        const row = hist[d];\n                        if (!row || row.achievement === null || row.achievement === undefined) break;\n                        if (row.achievement < 100) cd += 1;\n                        else break;\n                    }\n                }"
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
    "            const selectedDateForSort = (typeof selectedDate !== 'undefined' && selectedDate) ? selectedDate : (document.getElementById('tl-date-select') ? document.getElementById('tl-date-select').value : REAL_DATA.dataDate);\n            const agents = (REAL_DATA.agentPerformance[group] || []).filter(a => {\n                const dm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][a.name]\n                    ? REAL_DATA.agentPerformanceByDate[group][a.name][selectedDateForSort]\n                    : null;\n                return !!dm;\n            });\n            agents.sort((a, b) => {\n                const adm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][a.name]\n                    ? REAL_DATA.agentPerformanceByDate[group][a.name][selectedDateForSort]\n                    : null;\n                const bdm = REAL_DATA.agentPerformanceByDate && REAL_DATA.agentPerformanceByDate[group] && REAL_DATA.agentPerformanceByDate[group][b.name]\n                    ? REAL_DATA.agentPerformanceByDate[group][b.name][selectedDateForSort]\n                    : null;\n                const av = (adm && adm.achievement !== null && adm.achievement !== undefined) ? adm.achievement : ((a.achievement !== null && a.achievement !== undefined) ? a.achievement : 999);\n                const bv = (bdm && bdm.achievement !== null && bdm.achievement !== undefined) ? bdm.achievement : ((b.achievement !== null && b.achievement !== undefined) ? b.achievement : 999);\n                return av - bv;\n            });\n"
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

# ---- 26c. Recovery Trend layout: S0 single row; Large row; Small row; no wrapping ----
html = html.replace(
    "        function loadTrendChart() {\n            const grid = document.getElementById('module-charts-grid');\n            grid.innerHTML = '';",
    """        function loadTrendChart() {
            const grid = document.getElementById('module-charts-grid');
            grid.innerHTML = '';
            // Force deterministic row layout (avoid CSS grid auto-wrap from global stylesheet).
            grid.style.display = 'block';
            grid.style.gap = '0';

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

            const orderedTrendModules = getVisibleModules().slice().sort(sortModules);
            const groupedByBase = {};
            orderedTrendModules.forEach(module => {
                const p = parseModuleParts(module);
                if (!groupedByBase[p.base]) groupedByBase[p.base] = [];
                groupedByBase[p.base].push(module);
            });

            const baseOrder = ['S0', 'S1', 'S2', 'M1'].filter(b => groupedByBase[b]);
            Object.keys(groupedByBase)
                .filter(b => !baseOrder.includes(b))
                .sort()
                .forEach(b => baseOrder.push(b));

            const rowByBase = {};
            baseOrder.forEach(base => {
                const row = document.createElement('div');
                row.style.display = 'grid';
                row.style.gridTemplateColumns = base === 'S0' ? '1fr' : '1fr 1fr';
                row.style.gap = '20px';
                row.style.marginBottom = '16px';
                row.style.alignItems = 'start';
                grid.appendChild(row);
                rowByBase[base] = row;
            });

            function getTrendRowContainer(module) {
                const p = parseModuleParts(module);
                return rowByBase[p.base] || null;
            }""",
)

# `loadRiskModuleReview` must not depend on `orderedTrendModules` (scoped in `loadTrendChart`).
html = html.replace(
    "        function loadRiskModuleReview() {\n            // Calculate At-Risk for all modules dynamically\n            const riskModules = [];\n            orderedTrendModules.forEach(module => {",
    "        function loadRiskModuleReview() {\n            // Calculate At-Risk for all modules dynamically\n            const riskModules = [];\n            getVisibleModules().forEach(module => {"
)

html = html.replace(
    "                grid.appendChild(card);",
    "                getTrendRowContainer(module).appendChild(card);"
)

html = html.replace(
    "            getVisibleModules().forEach(module => {\n                // Dynamic At-Risk calculation based on projection",
    """            orderedTrendModules.forEach(module => {
                // Dynamic At-Risk calculation based on projection"""
)

html = html.replace(
    "            });\n        }\n\n        function calculateAtRisk(module) {",
    """            });

            // Hide empty rows while keeping fixed row order.
            baseOrder.forEach(base => {
                const row = rowByBase[base];
                row.style.display = row.children.length > 0 ? 'grid' : 'none';
            });
        }

        function calculateAtRisk(module) {"""
)
html = html.replace(
    "                });\n            });\n        }\n\n        // Calculate At-Risk based on recovery projection",
    """                });
            });

            // Hide empty rows while keeping fixed row order.
            baseOrder.forEach(base => {
                const row = rowByBase[base];
                row.style.display = row.children.length > 0 ? 'grid' : 'none';
            });
        }

        // Calculate At-Risk based on recovery projection"""
)

# Trend cards are appended into row containers (not yet in DOM during loop),
# so chartDom must be resolved from the `card` element, not the document.
html = html.replace(
    "                const chartDom = document.getElementById('trend-chart-' + module);",
    "                const chartDom = card.querySelector('#trend-chart-' + module);"
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

            const module = document.getElementById('stl-module-select').value;
            const selectedYearMonth = REAL_DATA.dataDate.slice(0, 4) + '-' + monthStr.padStart(2, '0'); // YYYY-MM
            const endMd = endPart.split('/');
            const endDay = endMd.length > 1 ? String(parseInt(endMd[1], 10)).padStart(2, '0') : '31';
            const weekEndDate = selectedYearMonth.slice(0, 4) + '-' + monthStr.padStart(2, '0') + '-' + endDay;
            const cutoffDate = weekEndDate < REAL_DATA.dataDate ? weekEndDate : REAL_DATA.dataDate;

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
    r"(?s)\n\s*function renderSTLChart\(weeks, weekIdx\) \{.*?\n\s*\}\n\s*function generateSTLConclusions",
    "\n        var stlChart = null;\n" + stl_chart_fn + "\n\n        function generateSTLConclusions",
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
    "<p style=\"font-size: 14px; opacity: 0.9; margin-top: 4px;\">Generated: <span id=\"report-date\"></span> | Data Date: <span id=\"data-date\"></span></p>"
)

html = html.replace(
    "<div style=\"display: flex; justify-content: space-between; align-items: center; max-width: 1400px; margin: 0 auto;\">",
    "<div style=\"display: flex; justify-content: space-between; align-items: center; max-width: 1400px; margin: 0 auto; position: relative;\">"
)

html = html.replace(
    "<div class=\"role-selector\">",
    "<div id=\"lang-switch\" style=\"position:absolute; left:50%; transform:translateX(-50%); top:50%; margin-top:2px; z-index:12;\">\n                <div style=\"position:relative; display:inline-block;\">\n                    <button id=\"lang-toggle\" title=\"Language\" onclick=\"toggleLanguageMenu(event)\" style=\"border:1px solid rgba(255,255,255,0.45); background:rgba(255,255,255,0.15); color:#fff; padding:4px 10px; border-radius:8px; cursor:pointer; font-size:14px; line-height:1;\">🌐</button>\n                    <div id=\"lang-menu\" style=\"display:none; position:absolute; top:36px; right:0; min-width:110px; background:#fff; border:1px solid #cbd5e1; border-radius:8px; box-shadow:0 6px 18px rgba(15,23,42,0.14); z-index:20; overflow:hidden;\">\n                        <button id=\"lang-option-en\" onclick=\"setLanguage('en')\" style=\"display:block; width:100%; border:none; background:#fff; color:#1e293b; text-align:left; padding:8px 10px; cursor:pointer; font-size:13px;\">English</button>\n                        <button id=\"lang-option-zh\" onclick=\"setLanguage('zh')\" style=\"display:block; width:100%; border:none; background:#fff; color:#1e293b; text-align:left; padding:8px 10px; cursor:pointer; font-size:13px;\">中文</button>\n                    </div>\n                </div>\n            </div>\n            <div class=\"role-selector\">"
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
            'Fail to meet target': '连续未达标',
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
            'Call Loss': '呼损率',
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
            'Conn. Rate': '接通率',
            'Cover Times': '覆盖次数',
            'Call Times': '拨打次数',
            'Art': '点呼',
            'Call Billmin': '接通时长（分钟）',
            'Single Call Duration': '单次通话时长',
            'Process KPI': '过程KPI',
            'PTP': 'PTP',
            'PTP Rate': 'PTP率',
            '3+ consecutive days': '连续3天+未达成',
            '1–2 consecutive days': '连续1-2天未达成',
            '3+ consecutive unmet days': '连续3天+未达成',
            '1–2 consecutive unmet days': '连续1-2天未达成',
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
            'Attd%': '出勤率%',
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
            // Sentence-level normalization for readable Chinese word order.
            out = out.replace(/目标已达成，达成率\s*([0-9.]+)%\s*achievement rate\./g, '目标已达成，达成率为 $1%。');
            out = out.replace(/周目标已达成，达成率\s*([0-9.]+)%\s*achievement rate\./g, '周目标已达成，达成率为 $1%。');
            out = out.replace(/表现较模块均值\s*([0-9.]+)%\s*高于。/g, '表现较模块均值高 $1%。');
            out = out.replace(/表现较模块均值\s*([0-9.]+)%\s*低于。/g, '表现较模块均值低 $1%。');
            out = out.replace(/目标差额\s*([0-9,]+)\s*PHP\s*\(([0-9.]+)%\s*低于目标\)\./g, '目标差额为 $1 PHP，较目标低 $2%。');
            out = out.replace(/周差额\s*([0-9,]+)\s*PHP\s*\(([0-9.]+)%\s*低于目标\)\./g, '周差额为 $1 PHP，较目标低 $2%。');
            out = out.replace(/周环比趋势为\s*up\./gi, '周环比趋势：上升。');
            out = out.replace(/周环比趋势为\s*down\./gi, '周环比趋势：下降。');
            out = out.replace(/周环比趋势为\s*flat\./gi, '周环比趋势：持平。');
            out = out.replace(/周环比趋势为\s*([^。.\n]+)\./g, '周环比趋势：$1。');
            out = out.replace(/([0-9]+)\s*名连续3天以上未达标坐席需立即辅导：([^。]+)\./g, '有 $1 名坐席连续 3 天以上未达标，建议立即辅导：$2。');
            out = out.replace(/([0-9]+)\s*个连续3周以上未达标组：([^。]+)。建议立即进行TL辅导干预。/g, '有 $1 个组连续 3 周以上未达标：$2。建议立即进行 TL 辅导干预。');
            out = out.replace(/总结：未达标主要由以下因素驱动：([^。]+)。建议STL在周行动计划中优先修复这些过程短板。/g, '总结：未达标主要由 $1 导致。建议 STL 在周行动计划中优先修复这些过程短板。');
            out = out.replace(/达标中/g, '进度正常');
            out = out.replace(/有风险/g, '存在风险');
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

        const ORIGINAL_TEXT = new WeakMap();
        let ORIGINAL_TITLE = '';
        let languageObserver = null;

        function applyLanguage(root = document.body) {
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
                if (!ORIGINAL_TEXT.has(n)) ORIGINAL_TEXT.set(n, n.nodeValue);
                const base = ORIGINAL_TEXT.get(n);
                n.nodeValue = currentLang === 'zh' ? localizeText(base) : base;
            });
            if (!ORIGINAL_TITLE) ORIGINAL_TITLE = document.title;
            document.title = currentLang === 'zh' ? localizeText(ORIGINAL_TITLE) : ORIGINAL_TITLE;
        }

        function refreshLanguageButtons() {
            const enBtn = document.getElementById('lang-option-en');
            const zhBtn = document.getElementById('lang-option-zh');
            if (!enBtn || !zhBtn) return;
            enBtn.style.background = currentLang === 'en' ? '#e2e8f0' : '#fff';
            zhBtn.style.background = currentLang === 'zh' ? '#e2e8f0' : '#fff';
        }

        function toggleLanguageMenu(event) {
            if (event) event.stopPropagation();
            const menu = document.getElementById('lang-menu');
            if (!menu) return;
            menu.style.display = (menu.style.display === 'block') ? 'none' : 'block';
        }

        function closeLanguageMenu() {
            const menu = document.getElementById('lang-menu');
            if (menu) menu.style.display = 'none';
        }

        function enhanceConsecutiveDaysHint() {
            const hint = currentLang === 'zh'
                ? '连续天数：表示连续 X 天达成率低于 100%（未达成目标）。'
                : 'Consecutive days: number of days in a row with achievement below 100% (target not met).';
            const dayLabels = [
                'Consecutive Days',
                '3+ consecutive days',
                '1–2 consecutive days',
                '连续天数',
                '连续3天+未达成',
                '连续1-2天未达成',
                '连续3天+',
                '连续1-2天'
            ];
            const dayLabelSet = new Set(dayLabels.map(v => String(v).toLowerCase()));

            document.querySelectorAll('th,span,div').forEach(el => {
                const txt = (el.textContent || '').trim();
                if (!txt) return;
                if (dayLabelSet.has(txt.toLowerCase())) {
                    el.title = hint;
                    el.style.cursor = 'help';
                    if (el.tagName && el.tagName.toUpperCase() === 'TH') {
                        el.style.textDecoration = 'underline dotted';
                        el.style.textUnderlineOffset = '3px';
                    }
                }
            });

            document.querySelectorAll('th[title*="days in a row"], th[title*="X days"]').forEach(el => {
                el.title = currentLang === 'zh'
                    ? '连续未达标：表示连续 X 天未达成目标。'
                    : 'Fail to meet target: consecutive X days with target not met.';
                el.style.cursor = 'help';
                el.style.textDecoration = 'underline dotted';
                el.style.textUnderlineOffset = '3px';
            });
        }

        function captureUIState() {
            const activeSubtab = document.querySelector('.subtab-btn.active');
            return {
                role: currentRole,
                tlGroup: document.getElementById('tl-group-select') ? document.getElementById('tl-group-select').value : '',
                tlDate: document.getElementById('tl-date-select') ? document.getElementById('tl-date-select').value : '',
                stlModule: document.getElementById('stl-module-select') ? document.getElementById('stl-module-select').value : '',
                stlWeek: document.getElementById('stl-week-select') ? document.getElementById('stl-week-select').value : '',
                dataSubtab: activeSubtab ? activeSubtab.id.replace('subtab-', '') : 'anomaly',
                dataAgentDate: document.getElementById('data-agent-date') ? document.getElementById('data-agent-date').value : '',
            };
        }

        function restoreUIState(state) {
            if (!state) return;
            const role = state.role || currentRole;
            if (role === 'TL') {
                initTLView();
                const g = document.getElementById('tl-group-select');
                const d = document.getElementById('tl-date-select');
                if (g && state.tlGroup && Array.from(g.options).some(o => o.value === state.tlGroup)) g.value = state.tlGroup;
                if (d && state.tlDate && Array.from(d.options).some(o => o.value === state.tlDate)) d.value = state.tlDate;
                loadTLData();
            } else if (role === 'STL') {
                initSTLView();
                const m = document.getElementById('stl-module-select');
                const w = document.getElementById('stl-week-select');
                if (m && state.stlModule && Array.from(m.options).some(o => o.value === state.stlModule)) m.value = state.stlModule;
                if (w && state.stlWeek && Array.from(w.options).some(o => o.value === state.stlWeek)) w.value = state.stlWeek;
                loadSTLData();
            } else {
                initDataView();
                const subtab = state.dataSubtab || 'anomaly';
                switchDataSubTab(subtab);
                if (subtab === 'agent-overview') {
                    const ds = document.getElementById('data-agent-date');
                    if (ds && state.dataAgentDate && Array.from(ds.options).some(o => o.value === state.dataAgentDate)) {
                        ds.value = state.dataAgentDate;
                    }
                    loadAgentOverviewData();
                }
            }
        }

        function setLanguage(lang) {
            const next = (lang === 'zh') ? 'zh' : 'en';
            localStorage.setItem('collection_report_lang', next);
            if (next === currentLang) {
                closeLanguageMenu();
                return;
            }
            const state = captureUIState();
            currentLang = next;
            refreshLanguageButtons();
            restoreUIState(state);
            applyLanguage(document.body);
            enhanceConsecutiveDaysHint();
            closeLanguageMenu();
        }

        function initLanguageToggle() {
            const saved = localStorage.getItem('collection_report_lang');
            currentLang = (saved === 'zh') ? 'zh' : 'en';
            refreshLanguageButtons();
            if (!languageObserver) {
                languageObserver = new MutationObserver(() => {
                    applyLanguage(document.body);
                    enhanceConsecutiveDaysHint();
                });
                languageObserver.observe(document.body, { childList: true, subtree: true });
                document.addEventListener('click', closeLanguageMenu);
            }
            applyLanguage(document.body);
            enhanceConsecutiveDaysHint();
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

# Avoid duplicate declaration crashes when template already contains language toggle blocks.
html = re.sub(
    r"\blet\s+currentLang\s*=\s*'en';",
    "var currentLang = window.currentLang || 'en'; window.currentLang = currentLang;",
    html
)
html = re.sub(
    r"\bconst\s+I18N_ZH\s*=\s*\{",
    "var I18N_ZH = window.I18N_ZH || {",
    html
)
html = re.sub(
    r"\bconst\s+ORIGINAL_TEXT\s*=\s*new\s+WeakMap\(\);",
    "var ORIGINAL_TEXT = window.ORIGINAL_TEXT || new WeakMap(); window.ORIGINAL_TEXT = ORIGINAL_TEXT;",
    html
)
html = re.sub(
    r"\blet\s+languageObserver\s*=\s*null;",
    "var languageObserver = window.languageObserver || null;",
    html
)
html = re.sub(
    r"\blet\s+ORIGINAL_TITLE\s*=\s*'';",
    "var ORIGINAL_TITLE = window.ORIGINAL_TITLE || ''; window.ORIGINAL_TITLE = ORIGINAL_TITLE;",
    html
)

def dedupe_language_blocks(html_text: str) -> str:
    marker = "var I18N_ZH = window.I18N_ZH || {"
    end_marker = "initializeLanguage();"
    if marker not in html_text:
        return html_text
    cursor = 0
    kept = False
    chunks = []
    while True:
        start = html_text.find(marker, cursor)
        if start == -1:
            chunks.append(html_text[cursor:])
            break
        end = html_text.find(end_marker, start)
        if end == -1:
            chunks.append(html_text[cursor:])
            break
        end += len(end_marker)
        chunks.append(html_text[cursor:start])
        if not kept:
            chunks.append(html_text[start:end])
            kept = True
        cursor = end
    return ''.join(chunks)

html = dedupe_language_blocks(html)


def inject_theme(html_text: str, theme_key: str, css_text: str) -> str:
    themed = html_text.replace("<body>", f"<body class=\"theme-{theme_key}\">", 1)
    return themed.replace("</head>", f"\n<style id=\"theme-{theme_key}\">\n{css_text}\n</style>\n</head>", 1)

def inject_chart_palette(html_text: str) -> str:
    # Skip if already injected (template may have been pre-modified)
    if 'chart-palette-patch' in html_text:
        return html_text
    chart_palette_js = """
<script id="chart-palette-patch">
(function () {
  if (window.__chartPalettePatched) return;
  window.__chartPalettePatched = true;
  function patch() {
    if (!window.echarts || !window.echarts.init || window.echarts.__chartPaletteWrapped) return;
    const baseInit = window.echarts.init;
    window.echarts.init = function() {
      const chart = baseInit.apply(this, arguments);
      const originalSetOption = chart.setOption.bind(chart);
      chart.setOption = function(option, ...rest) {
        const palette = ['#0f172a', '#334155', '#64748b', '#94a3b8', '#cbd5e1', '#c8102e'];
        if (!option.color) option.color = palette;
        if (option.legend && option.legend.textStyle) {
          option.legend.textStyle.color = '#111827';
        } else if (option.legend) {
          option.legend.textStyle = { color: '#111827' };
        }
        if (option.xAxis && !Array.isArray(option.xAxis)) {
          option.xAxis.axisLine = option.xAxis.axisLine || {};
          option.xAxis.axisLine.lineStyle = Object.assign({ color: '#9ca3af' }, option.xAxis.axisLine.lineStyle || {});
          option.xAxis.axisLabel = Object.assign({ color: '#374151' }, option.xAxis.axisLabel || {});
        }
        if (option.yAxis && !Array.isArray(option.yAxis)) {
          option.yAxis.axisLine = option.yAxis.axisLine || {};
          option.yAxis.axisLine.lineStyle = Object.assign({ color: '#9ca3af' }, option.yAxis.axisLine.lineStyle || {});
          option.yAxis.axisLabel = Object.assign({ color: '#374151' }, option.yAxis.axisLabel || {});
          option.yAxis.splitLine = Object.assign({ lineStyle: { color: '#e5e7eb' } }, option.yAxis.splitLine || {});
        }
        return originalSetOption(option, ...rest);
      };
      return chart;
    };
    window.echarts.__chartPaletteWrapped = true;
  }
  patch();
  const timer = setInterval(() => {
    patch();
    if (window.echarts && window.echarts.__chartPaletteWrapped) clearInterval(timer);
  }, 50);
})();
</script>
"""
    return html_text.replace("</head>", chart_palette_js + "\n</head>", 1)


THEME_CSS = {
    # ① Reference image-inspired dashboard style
    "style_1_reference": """
body.theme-style_1_reference {
  background: #e8e4dc !important;
  color: #1f2937 !important;
  font-family: "Inter", "Segoe UI", system-ui, sans-serif !important;
}
body.theme-style_1_reference > div:first-child {
  background: #1f2432 !important;
  border-radius: 20px;
  margin: 16px auto 10px auto;
  max-width: 1460px;
  box-shadow: 0 12px 32px rgba(17, 24, 39, 0.22);
}
body.theme-style_1_reference .card,
body.theme-style_1_reference .metric-card {
  border-radius: 18px !important;
  border: none !important;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08) !important;
}
body.theme-style_1_reference .role-btn,
body.theme-style_1_reference .subtab-btn {
  border-radius: 999px !important;
}
body.theme-style_1_reference .role-btn.active,
body.theme-style_1_reference .subtab-btn.active {
  background: #f2d15c !important;
  color: #1f2937 !important;
  border-color: #f2d15c !important;
}
body.theme-style_1_reference select {
  border-radius: 12px !important;
  background: #f8fafc !important;
}
""",
    # ② Bauhaus style
    "style_2_bauhaus": """
body.theme-style_2_bauhaus {
  background: #f6f6f3 !important;
  color: #111 !important;
  font-family: "Futura", "Avenir Next", "Segoe UI", sans-serif !important;
}
body.theme-style_2_bauhaus > div:first-child {
  background: #0057b8 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
}
body.theme-style_2_bauhaus .card,
body.theme-style_2_bauhaus .metric-card {
  border: 2px solid #111 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
}
body.theme-style_2_bauhaus .role-btn.active,
body.theme-style_2_bauhaus .subtab-btn.active {
  background: #ffcc00 !important;
  color: #111 !important;
  border-color: #111 !important;
}
body.theme-style_2_bauhaus .status-success { background: #0057b8 !important; color: #fff !important; }
body.theme-style_2_bauhaus .status-danger { background: #e10600 !important; color: #fff !important; }
body.theme-style_2_bauhaus .metric-value { color: #111 !important; }
body.theme-style_2_bauhaus .empty-state-icon { color: #0057b8 !important; }
""",
    # ③ Default report theme (v3.3 main output)
    "style_3": """
body.theme-style_3 {
  background: #f7f7f7 !important;
  color: #111 !important;
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif !important;
}
body.theme-style_3 > div:first-child {
  background: #ffffff !important;
  color: #111 !important;
  border-bottom: 1px solid #d1d5db;
}
body.theme-style_3 > div:first-child h1,
body.theme-style_3 > div:first-child p { color: #111 !important; }
body.theme-style_3 #lang-toggle {
  background: #f8fafc !important;
  color: #111 !important;
  border-color: #cbd5e1 !important;
}
body.theme-style_3 .card,
body.theme-style_3 .metric-card {
  background: #fff !important;
  border: 1px solid #d1d5db !important;
  border-radius: 2px !important;
  box-shadow: none !important;
}
body.theme-style_3 .role-btn,
body.theme-style_3 .subtab-btn {
  color: #334155 !important;
  border-color: #cbd5e1 !important;
  border-radius: 0 !important;
  border-bottom: 2px solid transparent !important;
}
body.theme-style_3 .role-btn.active,
body.theme-style_3 .subtab-btn.active {
  background: #fff !important;
  color: #c8102e !important;
  border-bottom-color: #c8102e !important;
}
body.theme-style_3 .empty-state-icon { color: #c8102e !important; }
body.theme-style_3 .metric-label { color: #6b7280 !important; }
body.theme-style_3 .metric-value { color: #111827 !important; letter-spacing: 0.2px; }
body.theme-style_3 .status-badge { border-radius: 2px !important; }
body.theme-style_3 .status-success { background: #0f766e !important; color: #fff !important; }
body.theme-style_3 .status-danger { background: #c8102e !important; color: #fff !important; }
body.theme-style_3 .drilldown-row:hover { background: #f3f4f6 !important; }
body.theme-style_3 .metric-value { letter-spacing: 0.2px; }
body.theme-style_3 .status-success,
body.theme-style_3 .status-danger {
  border-radius: 2px !important;
}
""",
}

# ========================
# Write output
# ========================
base_html = inject_theme(html, "style_3", THEME_CSS["style_3"])
base_html = inject_chart_palette(base_html)
base_html = dedupe_language_blocks(base_html)
# Hotfix REMOVED: was converting all const/let to var, causing duplicate MODULE_IMPROVEMENT_PLAN_URL
# base_html = re.sub(r"\bconst\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=", r"var \1 =", base_html)
# base_html = re.sub(r"\blet\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=", r"var \1 =", base_html)
base_html = inject_pipeline_head_comment(
    base_html,
    contract_id=TEMPLATE_CONTRACT_ID,
    pipeline_version=PIPELINE_VERSION,
    data_date=TL_LATEST_STR,
)
_missing_anchors = check_html_anchors(base_html)
if _missing_anchors:
    raise RuntimeError(f"HTML anchor check failed, missing: {_missing_anchors}")
with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(base_html)

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

def _onclick_has_escaped_quote(html: str) -> bool:
    """检查 onclick handler 内是否有 \\' 转义（HTML属性中非法的JS字符串转义）。"""
    handlers = re.findall(r'onclick=[^>]+>', html)
    pattern = chr(92) + chr(39)  # backslash + single quote
    return any(pattern in h for h in handlers)

hard_checks = [
    ("Natural-month day-mix guard", nat_month_single_month_ok),
    ("TL actual trend <= dataDate", tl_trend_cutoff_ok),
    ("Module actual trend <= dataDate", module_trend_cutoff_ok),
    ("Actual hidden after dataDate", post_cutoff_actual_ok),
    ("Target source consistency", target_source_consistency_ok),
]

soft_checks = [
    ("REAL_DATA var/const",      'const REAL_DATA = {' in html),
    ("REAL_DATA present",        'REAL_DATA.availableDates' in html and 'REAL_DATA.defaultStlWeek' in html),
    ("groupModule in data",      '"groupModule"' in html),
    ("nmRepayRate in data",      '"nmRepayRate"' in html),
    ("moduleRepayRate in data",  '"moduleRepayRate"' in html),
    ("repayRate in data",        '"repayRate"' in html),
    ("callLossRate in data",    '"callLossRate"' in html),
    ("ptpRate in data",         '"ptpRate"' in html),
    ("dataDate in JSON",         '"dataDate"' in html),
    ("TL date selector",         'REAL_DATA.availableDates' in html),
    ("STL week selector",        'REAL_DATA.availableWeeks' in html),
    ("STL default week",        'REAL_DATA.defaultStlWeek' in html),
    ("PTP null-safe (agent)",   'displayPtp !== null' in html or 'agent.ptp !== null' in html),
    ("callLossRate in agent",   'agent.callLossRate' in html),
    ("callLossRate in stl week", 'displayCallLossRate' in html),
    ("TL call loss header",      'Call Loss</th>' in html and 'displayCallLossRate' in html),
    ("processTargets in data",   '"processTargets"' in html),
    ("module process benchmark", 'processTarget.artCallTimes' in html and 'processTarget.callBillminRawTarget' in html),
    ("STL gap cards",            'id="stl-call-gap"' in html and 'id="stl-connect-gap"' in html),
    ("STL trend title copy",     'Recovery Trend (Selected Month)' in html),
    ("templateContractId in HTML", 'templateContractId' in html),
    ("pipelineVersion in HTML",  'pipelineVersion' in html),
    ("onclick no JS escape quotes", not _onclick_has_escaped_quote(html)),
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

