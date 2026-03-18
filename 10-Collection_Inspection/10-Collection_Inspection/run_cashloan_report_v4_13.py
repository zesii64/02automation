# -*- coding: utf-8 -*-
"""
CashLoan 巡检日报 v3.3：支持 MTD (New/Old) 和 Matrix (New/Old) 精细化展示。
Updates:
- v3.3: Lift Analysis Column Reordering (Current | M-1 | Lift | M-2 | Y-1).
- v3.3: Added DPD1 Rate Definition.
- v3.2: Split Matrix into Recovery & DPD.
- v3.2: Restore Breakdown section.
"""
import sys
import json
import os
import re
from pathlib import Path
from datetime import datetime
import pandas as pd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REPORTS_DIR = SCRIPT_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# --- Excel Helpers ---
def read_sheet(path, sheet_name):
    try:
        return pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return None

def read_sheet_maybe_chunked(path, base_name):
    df = read_sheet(path, base_name)
    if df is None:
        return None
    try:
        xl = pd.ExcelFile(path, engine="openpyxl")
        extra = [s for s in xl.sheet_names if re.match(r"^" + re.escape(base_name) + r"_\d+$", s)]
        if not extra:
            return df
        key = lambda s: int(s.split("_")[-1])
        chunks = [df] + [pd.read_excel(xl, sheet_name=s) for s in sorted(extra, key=key)]
        return pd.concat(chunks, ignore_index=True)
    except Exception:
        return df

# --- Report Generators ---

def make_kpi_cards(vintage_summary, repay_summary, process_summary):
    cards = []
    
    # 1. Asset Quality
    v_all = (vintage_summary or {}).get("All", {})
    ov_rate = v_all.get("overdue_rate")
    dpd5 = v_all.get("dpd5")
    
    def card(title, val, sub=None, color="blue"):
        s_val = f"{val:.2%}" if isinstance(val, (int, float)) else "-"
        return f"""
        <div class="card p-4 border-l-4 border-{color}-500">
            <div class="text-gray-500 text-xs uppercase font-bold tracking-wider">{title}</div>
            <div class="text-2xl font-bold text-gray-800 mt-1">{s_val}</div>
            <div class="text-xs text-gray-400 mt-1">{sub or '&nbsp;'}</div>
        </div>
        """
        
    cards.append(card("Overall Entrant", ov_rate, "入催率", "red"))
    cards.append(card("Overall DPD5", dpd5, "T+6 Overdue", "blue"))
    
    # 2. Repay
    r_all = list(repay_summary.values())[0] if repay_summary else {}
    rr = r_all.get("repay_rate")
    cards.append(card("Collection Rate", rr, "Global Repay", "green"))
    
    # 3. Connect
    p_all = list(process_summary.values())[0] if process_summary else {}
    cr = p_all.get("connect_rate")
    cards.append(card("Connect Rate", cr, "Strategy Exec", "purple"))
    
    return "".join(cards)

def make_trend_chart_json(data, dom_id, title):
    if not data: return "null"
    data = data[::-1] # Reverse to chrono
    x_axis = [r.get("period_key", "") for r in data]
    y_ov = [r.get("overdue_rate") for r in data]
    y_d5 = [r.get("dpd5") for r in data]
    
    return json.dumps({
        "tooltip": {"trigger": "axis", "formatter": None}, # JS will handle formatter
        "legend": {"data": ["入催率", "DPD5"], "bottom": 0},
        "grid": {"left": "3%", "right": "4%", "bottom": "10%", "top": "10%", "containLabel": True},
        "xAxis": {"type": "category", "boundaryGap": False, "data": x_axis},
        "yAxis": {"type": "value", "axisLabel": {"formatter": "{value}"}, "splitLine": {"lineStyle": {"type": "dashed"}}},
        "series": [
            {"name": "入催率", "type": "line", "data": y_ov, "itemStyle": {"color": "#EF4444"}, "smooth": True, "connectNulls": False},
            {"name": "DPD5", "type": "line", "data": y_d5, "itemStyle": {"color": "#3B82F6"}, "smooth": True, "connectNulls": False}
        ]
    })

def make_repay_table(summary):
    if not summary: return "<p>No Data</p>"
    rows = []
    for k, v in summary.items():
        rr = v.get("repay_rate")
        s_rr = f"{rr:.2%}" if isinstance(rr, (int, float)) else "-"
        bd = v.get("breakdown", [])
        bd_html = "<br/>".join([f"<span class='text-xs text-gray-500'>{x}</span>" for x in bd])
        rows.append(f"<tr><td class='font-medium'>{k}</td><td class='text-right'>{v.get('rows')}</td><td class='text-right font-bold text-green-600'>{s_rr}</td><td>{bd_html}</td></tr>")
    return f"""<table class="w-full text-sm">
        <thead class="bg-gray-50"><tr><th class="text-left p-2">Batch</th><th class="text-right p-2">Loan Cnt</th><th class="text-right p-2">Rate</th><th class="p-2 text-left">Attribution (Worst 3)</th></tr></thead>
        <tbody class="divide-y">{ "".join(rows) }</tbody>
    </table>"""

def make_process_table(summary):
    if not summary: return "<p>No Data</p>"
    rows = []
    for k, v in summary.items():
        rows.append(f"<tr><td>{k}</td><td class='text-right'>{v.get('coverage_rate')}</td><td class='text-right'>{v.get('connect_rate')}</td><td class='text-right'>{v.get('intensity')}</td></tr>")
    return f"""<table class="w-full text-sm"><thead class="bg-gray-50"><tr><th>Dim</th><th class="text-right">Cov</th><th class="text-right">Conn</th><th class="text-right">Int</th></tr></thead><tbody>{"".join(rows)}</tbody></table>"""

def make_anomalies_list(v_anoms, r_anoms):
    all_a = v_anoms + r_anoms
    if not all_a: return "<span class='text-green-500'>✔ No anomalies detected.</span>"
    return "<br/>".join([f"• {a}" for a in all_a])

def get_bg_color(val, min_val, max_val, is_inverse=False):
    if val is None or min_val is None or max_val is None or min_val == max_val:
        return ""
    try:
        ratio = (val - min_val) / (max_val - min_val)
    except ZeroDivisionError:
        ratio = 0.5
    if is_inverse: 
        if ratio > 0.66: return "bg-emerald-100 text-emerald-800"
        if ratio > 0.33: return "bg-emerald-50 text-emerald-800"
        return "bg-red-50 text-red-800"
    else: 
        if ratio > 0.66: return "bg-red-100 text-red-800"
        if ratio > 0.33: return "bg-red-50 text-red-800"
        return "bg-emerald-50 text-emerald-800"

def make_vintage_matrix_table(matrix_data, mode="recovery"):
    """
    mode: 'recovery' (Default, High is Good) or 'dpd' (High is Bad)
    [v4.2] Added Trend Indicators (WoW/MoM)
    """
    if not matrix_data: return "<div class='p-4 text-gray-400'>No Data</div>"
    
    is_dpd_mode = (mode == "dpd")
    data_key = "dpd_rates" if is_dpd_mode else "recovery"
    
    ent_vals = [r["entrant_rate"] for r in matrix_data if r["entrant_rate"] is not None]
    min_ent, max_ent = (min(ent_vals), max(ent_vals)) if ent_vals else (None, None)
    
    col_stats = {}
    for d in range(1, 31):
        key = f"D{d}"
        vals = []
        for r in matrix_data:
            d_map = r.get(data_key, {})
            if d_map and d_map.get(key) is not None:
                vals.append(d_map.get(key))
        col_stats[key] = (min(vals), max(vals)) if vals else (None, None)

    show_days = [1,2,3,4,5,6,7,10,15,30]
    
    # [v3.3 Update] Custom headers based on mode
    header_prefix = "DPD" if is_dpd_mode else "D"
    headers = "".join([f"<th class='text-right p-1 font-normal text-gray-500'>{header_prefix}{d}</th>" for d in show_days])
    
    rows = []
    for i, r in enumerate(matrix_data):
        # Comparison with previous period (next in list if sorted descending)
        prev_r = matrix_data[i+1] if i + 1 < len(matrix_data) else None
        
        # Entrant Rate
        ent = r["entrant_rate"]
        ent_cls = get_bg_color(ent, min_ent, max_ent, False)
        
        ent_trend = ""
        if prev_r and ent is not None and prev_r["entrant_rate"] is not None:
            delta = ent - prev_r["entrant_rate"]
            if abs(delta) > 0.001:
                arrow = "↑" if delta > 0 else "↓"
                # Risk metric: Increase is Bad (Red)
                color = "text-red-500" if delta > 0 else "text-green-500"
                delta_str = f"{abs(delta):.2%}"
                ent_trend = f"<span class='lift-indicator text-[10px] {color} ml-1'>{arrow}{delta_str}</span>"

        ent_html = f"<td class='text-right {ent_cls} font-medium p-1'>{ent:.2%}{ent_trend}</td>" if ent is not None else "<td>-</td>"
        
        rec_html = ""
        d_map = r.get(data_key, {})
        p_map = prev_r.get(data_key, {}) if prev_r else {}
        
        for d in show_days:
            k = f"D{d}"
            v = d_map.get(k)
            if v is None:
                rec_html += "<td class='text-right text-gray-300 p-1'>-</td>"
            else:
                cmin, cmax = col_stats.get(k)
                # If DPD mode: Low is Good (Green), High is Bad (Red) -> is_inverse=False
                # If Recovery mode: High is Good (Green) -> is_inverse=True
                is_good_metric = not is_dpd_mode
                cls = get_bg_color(v, cmin, cmax, is_inverse=is_good_metric)
                
                # Trend
                trend_html = ""
                if prev_r:
                    vp = p_map.get(k)
                    if vp is not None:
                        delta = v - vp
                        if abs(delta) > 0.001:
                            arrow = "↑" if delta > 0 else "↓"
                            # If Good Metric (Recovery): Increase is Good (Green)
                            # If Bad Metric (DPD): Increase is Bad (Red)
                            is_bad = (delta < 0) if is_good_metric else (delta > 0)
                            color = "text-red-500" if is_bad else "text-green-500"
                            delta_str = f"{abs(delta):.1%}"
                            trend_html = f"<span class='lift-indicator text-[9px] {color} ml-0.5'>{arrow}{delta_str}</span>"
                            
                rec_html += f"<td class='text-right {cls} p-1 whitespace-nowrap'>{v:.1%}{trend_html}</td>"
        
        rows.append(f"<tr><td class='text-xs font-mono p-1 whitespace-nowrap'>{r['period']}</td>{ent_html}{rec_html}</tr>")
        
    title = "DPD Overdue Rates" if is_dpd_mode else "Recovery Rates"
    
    return f"""
    <div class="mt-4 mb-2 font-semibold text-sm text-gray-700">{title}</div>
    <div class="overflow-x-auto">
        <table class="w-full text-xs border-collapse">
            <thead class="bg-gray-50 border-b">
                <tr><th class="text-left p-1">Period</th><th class="text-right p-1 font-semibold">Overdue Rate</th>{headers}</tr>
            </thead>
            <tbody class="divide-y">{ "".join(rows) }</tbody>
        </table>
    </div>
    """

def make_vintage_matrix_v3_group(matrix_all, matrix_new, matrix_old, label):
    # Each group has 2 tables: Recovery and DPD
    def _render_pair(m):
        t1 = make_vintage_matrix_table(m, "recovery")
        t2 = make_vintage_matrix_table(m, "dpd")
        return f"<div>{t1}{t2}</div>"

    h_all = _render_pair(matrix_all)
    h_new = _render_pair(matrix_new)
    h_old = _render_pair(matrix_old)
    
    return f"""
    <div class="mb-2 border-b flex space-x-4 text-sm text-slate-500">
        <span class="py-1 cursor-pointer text-blue-600 font-bold border-b-2 border-blue-600" 
              onclick="this.parentElement.querySelectorAll('span').forEach(e=>e.className='py-1 cursor-pointer hover:text-blue-600'); this.className='py-1 cursor-pointer text-blue-600 font-bold border-b-2 border-blue-600'; document.getElementById('mat-{label}-all').classList.remove('hidden'); document.getElementById('mat-{label}-new').classList.add('hidden'); document.getElementById('mat-{label}-old').classList.add('hidden');">
            Overall
        </span>
        <span class="py-1 cursor-pointer hover:text-blue-600" 
              onclick="this.parentElement.querySelectorAll('span').forEach(e=>e.className='py-1 cursor-pointer hover:text-blue-600'); this.className='py-1 cursor-pointer text-blue-600 font-bold border-b-2 border-blue-600'; document.getElementById('mat-{label}-new').classList.remove('hidden'); document.getElementById('mat-{label}-all').classList.add('hidden'); document.getElementById('mat-{label}-old').classList.add('hidden');">
            New User
        </span>
        <span class="py-1 cursor-pointer hover:text-blue-600" 
              onclick="this.parentElement.querySelectorAll('span').forEach(e=>e.className='py-1 cursor-pointer hover:text-blue-600'); this.className='py-1 cursor-pointer text-blue-600 font-bold border-b-2 border-blue-600'; document.getElementById('mat-{label}-old').classList.remove('hidden'); document.getElementById('mat-{label}-all').classList.add('hidden'); document.getElementById('mat-{label}-new').classList.add('hidden');">
            Old User
        </span>
    </div>
    <div id="mat-{label}-all">{h_all}</div>
    <div id="mat-{label}-new" class="hidden">{h_new}</div>
    <div id="mat-{label}-old" class="hidden">{h_old}</div>
    """

def make_lift_analysis_v3_3(metrics_all, metrics_new, metrics_old):
    def _render_table(m):
        if not m or "current" not in m: return '<p class="text-sm text-slate-400 p-4">暂无数据</p>'
        
        # [v3.3] Reordered Columns: Current | M-1 | Lift | M-2 | Y-1
        
        headers = ""
        headers += f'<th class="bg-slate-50 text-slate-600 font-medium p-2 text-right">本月 MTD</th>'
        headers += f'<th class="bg-slate-50 text-slate-600 font-medium p-2 text-right">上月 M-1</th>'
        headers += f'<th class="bg-slate-50 text-slate-600 font-bold p-2 text-right text-blue-600">Lift (MoM)</th>'
        headers += f'<th class="bg-slate-50 text-slate-600 font-medium p-2 text-right">前月 M-2</th>'
        headers += f'<th class="bg-slate-50 text-slate-600 font-medium p-2 text-right">去年 Y-1</th>'
        
        # Calculate Lift (Current vs M-1)
        curr = m.get("current")
        prev = m.get("m1")
        m2 = m.get("m2")
        y1 = m.get("y1")
        
        def calc_lift(key):
            if not curr or not prev: return "-"
            v_c = curr.get(key)
            v_p = prev.get(key)
            if v_c is None or v_p is None or v_p == 0: return "-"
            diff = (v_c - v_p) / v_p
            is_risk = key != "owing"
            color = "text-gray-500"
            if is_risk:
                if diff > 0.05: color = "text-red-600"
                elif diff < -0.05: color = "text-green-600"
            else:
                if diff > 0: color = "text-gray-800"
            arrow = "↑" if diff > 0 else "↓"
            return f'<span class="{color}">{arrow} {abs(diff):.1%}</span>'

        def cell(data_dict, key, is_pct=True):
            if not data_dict: return '<td class="text-right text-gray-300">-</td>'
            val = data_dict.get(key)
            if val is None: return '<td class="text-right text-gray-300">-</td>'
            if is_pct:
                return f'<td class="text-right font-bold p-1">{val:.2%}</td>'
            else:
                return f'<td class="text-right font-mono p-1">{int(val):,}</td>'

        def row(label, key, is_pct=True):
            c_curr = cell(curr, key, is_pct)
            c_m1 = cell(prev, key, is_pct)
            c_lift = f'<td class="text-right p-1 bg-slate-50">{calc_lift(key)}</td>'
            c_m2 = cell(m2, key, is_pct)
            c_y1 = cell(y1, key, is_pct)
            return f'<tr><td class="font-medium p-2">{label}</td>{c_curr}{c_m1}{c_lift}{c_m2}{c_y1}</tr>'

        return f"""
        <table class="w-full text-sm text-left">
            <thead><tr><th class="bg-slate-50 w-24 p-2">Metric</th>{headers}</tr></thead>
            <tbody class="divide-y">
                {row("在贷本金", "owing", False)}
                {row("入催率", "entrant_rate", True)}
                {row("DPD1", "dpd1_rate", True)}
                {row("DPD5", "dpd5_rate", True)}
            </tbody>
        </table>
        <div class="mt-3 text-xs text-slate-400 space-y-1">
            <p>* 观测进度: {m.get("days_progress")} 天</p>
        </div>
        """

    return f"""
    <div id="lift-section-all">{_render_table(metrics_all)}</div>
    <div id="lift-section-new" class="hidden">{_render_table(metrics_new)}</div>
    <div id="lift-section-old" class="hidden">{_render_table(metrics_old)}</div>
    """

def make_breakdown_table(vintage_summary):
    # Restore from v3.0
    if not vintage_summary: return "<p>No Data</p>"
    
    html_parts = []
    
    # Groups: All, User, Model, Period, Amount
    groups = {"User": [], "Model": [], "Period": [], "Amount": []}
    for k, v in vintage_summary.items():
        if k.startswith("User:"): groups["User"].append((k, v))
        elif k.startswith("Model:"): groups["Model"].append((k, v))
        elif k.startswith("Period:"): groups["Period"].append((k, v))
        elif k.startswith("Amount:"): groups["Amount"].append((k, v))
    
    def _make_rows(items):
        rows = []
        for k, v in sorted(items, key=lambda x: x[0]):
            label = k.split(": ")[1]
            r = v.get("rows", 0)
            
            def fmt(key, is_good_metric=False):
                val = v.get(key, "-")
                if not isinstance(val, (int, float)): return "-"
                s_val = f"{val:.2%}"
                wow = v.get(f"{key}_wow")
                if wow is not None and isinstance(wow, (int, float)) and abs(wow) > 0.001:
                    arrow = "↑" if wow > 0 else "↓"
                    color = "text-gray-400"
                    is_bad = (wow > 0) if not is_good_metric else (wow < 0)
                    if is_bad: color = "text-red-500"
                    elif not is_bad: color = "text-green-500"
                    return f"{s_val} <span class='text-xs {color}'>{arrow} {abs(wow):.0%}</span>"
                return s_val

            ov = fmt("overdue_rate")
            d1 = fmt("dpd1")
            d5 = fmt("dpd5")
            d7 = fmt("dpd7")
            d15 = fmt("dpd15")
            d30 = fmt("dpd30")
            cc = fmt("connect_conversion", True)
            pc = fmt("ptp_conversion", True)
            
            rows.append(f"<tr><td class='pl-4'>{label}</td><td class='text-right'>{r}</td><td class='text-right'>{ov}</td><td class='text-right'>{d1}</td><td class='text-right'>{d5}</td><td class='text-right'>{d7}</td><td class='text-right'>{d15}</td><td class='text-right'>{d30}</td><td class='text-right text-gray-500'>{cc}</td><td class='text-right text-gray-500'>{pc}</td></tr>")
        return "".join(rows)

    thead = '<thead class="bg-gray-50"><tr><th class="text-left p-2">Dim</th><th class="text-right p-2">Loan Cnt</th><th class="text-right p-2">Overdue Rate</th><th class="text-right p-2">DPD1</th><th class="text-right p-2">DPD5</th><th class="text-right p-2">DPD7</th><th class="text-right p-2">DPD15</th><th class="text-right p-2">DPD30</th><th class="text-right p-2">Conn%</th><th class="text-right p-2">PTP%</th></tr></thead>'

    def _add_table(title, g_key):
        if groups[g_key]:
            html_parts.append(f'<h3 class="text-sm font-semibold text-gray-800 mt-4 mb-2">{title}</h3>')
            html_parts.append(f'<table class="w-full text-sm border rounded mb-2">{thead}<tbody class="divide-y">{_make_rows(groups[g_key])}</tbody></table>')

    _add_table("按用户类型 (User Type)", "User")
    _add_table("按期数 (Period)", "Period")
    _add_table("按模型 (Model Bin)", "Model")
    _add_table("按金额段 (Amount)", "Amount")
    
    return "".join(html_parts)

def make_breakdown_section_v3_4(
    bd_daily_all, bd_daily_new, bd_daily_old,
    bd_weekly_all, bd_weekly_new, bd_weekly_old,
    bd_monthly_all, bd_monthly_new, bd_monthly_old
):
    """
    Generate Breakdown section with 3 Tabs (Daily/Weekly/Monthly) 
    and Sub-tabs (Overall/New/Old) inside each.
    """
    
    # Helper to create one Group Tab Content (e.g. Weekly All/New/Old)
    def _make_group_content(summary_all, summary_new, summary_old, label_prefix):
        h_all = make_breakdown_table(summary_all)
        h_new = make_breakdown_table(summary_new)
        h_old = make_breakdown_table(summary_old)
        
        return f"""
        <div class="mt-4">
            <div class="flex space-x-4 border-b text-sm mb-4">
                <button onclick="switchBDSub('{label_prefix}', 'all')" id="btn-bd-sub-{label_prefix}-all" class="pb-2 border-b-2 border-blue-600 font-bold text-blue-600 transition-colors">Overall</button>
                <button onclick="switchBDSub('{label_prefix}', 'new')" id="btn-bd-sub-{label_prefix}-new" class="pb-2 text-gray-500 hover:text-blue-600 transition-colors">New User</button>
                <button onclick="switchBDSub('{label_prefix}', 'old')" id="btn-bd-sub-{label_prefix}-old" class="pb-2 text-gray-500 hover:text-blue-600 transition-colors">Old User</button>
            </div>
            
            <div id="bd-content-{label_prefix}-all">{h_all}</div>
            <div id="bd-content-{label_prefix}-new" class="hidden">{h_new}</div>
            <div id="bd-content-{label_prefix}-old" class="hidden">{h_old}</div>
        </div>
        """

    # 1. Weekly (Default)
    html_weekly = _make_group_content(bd_weekly_all, bd_weekly_new, bd_weekly_old, "weekly")
    
    # 2. Monthly
    html_monthly = _make_group_content(bd_monthly_all, bd_monthly_new, bd_monthly_old, "monthly")
    
    # 3. Daily (Amount focus)
    # Note: Daily comparison is typically DoD. Amount is key here.
    html_daily = _make_group_content(bd_daily_all, bd_daily_new, bd_daily_old, "daily")
    
    return f"""
    <div class="card">
        <div class="flex items-center justify-between mb-4 border-b pb-4">
            <div class="flex items-center gap-2">
                <div class="section-bar accent"></div>
                <h2 class="text-lg font-bold text-slate-800">维度拆解 (Breakdown)</h2>
            </div>
            <div class="flex space-x-2 bg-slate-100 p-1 rounded-lg">
                <button onclick="switchBDRoot('weekly')" class="tab-btn active" id="btn-bd-root-weekly">Weekly (WoW)</button>
                <button onclick="switchBDRoot('monthly')" class="tab-btn" id="btn-bd-root-monthly">Monthly (MoM)</button>
                <button onclick="switchBDRoot('daily')" class="tab-btn" id="btn-bd-root-daily">Daily (DoD)</button>
            </div>
        </div>
        
        <div id="bd-root-weekly" class="bd-root-view">
            <p class="text-xs text-slate-400 mb-2">* Comparison: Last 7 Days vs Previous 7 Days</p>
            {html_weekly}
        </div>
        <div id="bd-root-monthly" class="bd-root-view hidden">
            <p class="text-xs text-slate-400 mb-2">* Comparison: Current Month vs Last Month</p>
            {html_monthly}
        </div>
        <div id="bd-root-daily" class="bd-root-view hidden">
            <p class="text-xs text-slate-400 mb-2">* Comparison: Latest Day vs Previous Day (Focus on Amount/Batch)</p>
            {html_daily}
        </div>
    </div>
    
    <script>
    function switchBDRoot(period) {{
        document.querySelectorAll('.bd-root-view').forEach(el => el.classList.add('hidden'));
        document.getElementById(`bd-root-${{period}}`).classList.remove('hidden');
        
        document.querySelectorAll('[id^="btn-bd-root-"]').forEach(el => el.classList.remove('active'));
        document.getElementById(`btn-bd-root-${{period}}`).classList.add('active');
    }}
    
    function switchBDSub(period, type) {{
        // Hide all contents for this period
        document.getElementById(`bd-content-${{period}}-all`).classList.add('hidden');
        document.getElementById(`bd-content-${{period}}-new`).classList.add('hidden');
        document.getElementById(`bd-content-${{period}}-old`).classList.add('hidden');
        
        // Show target
        document.getElementById(`bd-content-${{period}}-${{type}}`).classList.remove('hidden');
        
        // Update buttons style
        const btnId = `btn-bd-sub-${{period}}-${{type}}`;
        const container = document.getElementById(btnId).parentElement;
        Array.from(container.children).forEach(btn => {{
            btn.className = "pb-2 text-gray-500 hover:text-blue-600 transition-colors";
        }});
        document.getElementById(btnId).className = "pb-2 border-b-2 border-blue-600 font-bold text-blue-600 transition-colors";
    }}
    </script>
    """

def make_trend_data_table(trend_list, title):
    if not trend_list: return f"<p class='p-4 text-sm text-gray-400'>No Data for {title}</p>"
    
    # Header
    thead = """
    <thead class="bg-gray-50 text-xs text-gray-500 uppercase">
        <tr>
            <th class="p-2 text-left">Period</th>
            <th class="p-2 text-right">Loan Cnt</th>
            <th class="p-2 text-right">Overdue Rate</th>
            <th class="p-2 text-right">DPD1</th>
            <th class="p-2 text-right">DPD5</th>
            <th class="p-2 text-right">DPD7</th>
            <th class="p-2 text-right">DPD15</th>
            <th class="p-2 text-right">DPD30</th>
        </tr>
    </thead>
    """
    
    rows = []
    for item in trend_list:
        p = item.get("period_key", "-")
        r = item.get("rows", 0)
        
        def fmt(key, item_dict):
            val = item_dict.get(key)
            if val is None: return "-"
            s_val = f"{val:.2%}"
            
            # Change Indicator
            change = item_dict.get(f"{key}_change")
            if change is not None and abs(change) > 0.001: # Show if > 0.1% change
                arrow = "↑" if change > 0 else "↓"
                color = "text-red-500" if change > 0 else "text-green-500" # Risk metric: Increase is bad (Red)
                # Assuming all metrics here (Entrant, DPD) are Risk metrics where Higher = Bad.
                return f"{s_val} <span class='text-[10px] {color}'>{arrow}{abs(change):.1%}</span>"
            return s_val

        ov = fmt("overdue_rate", item)
        d1 = fmt("dpd1", item)
        d5 = fmt("dpd5", item)
        d7 = fmt("dpd7", item)
        d15 = fmt("dpd15", item)
        d30 = fmt("dpd30", item)
        
        rows.append(f"""
        <tr class="border-b hover:bg-gray-50 text-sm">
            <td class="p-2 font-mono whitespace-nowrap">{p}</td>
            <td class="p-2 text-right">{r}</td>
            <td class="p-2 text-right font-medium">{ov}</td>
            <td class="p-2 text-right">{d1}</td>
            <td class="p-2 text-right">{d5}</td>
            <td class="p-2 text-right">{d7}</td>
            <td class="p-2 text-right">{d15}</td>
            <td class="p-2 text-right">{d30}</td>
        </tr>
        """)
        
    return f"""
    <div class="mt-4 mb-4">
        <h4 class="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">{title}</h4>
        <div class="overflow-x-auto border rounded-lg">
            <table class="w-full text-left bg-white">
                {thead}
                <tbody>{''.join(rows)}</tbody>
            </table>
        </div>
    </div>
    """

def make_attribution_content(attr_data_single):
    """Helper to render one attribution tab."""
    if not attr_data_single: return "<p class='p-4 text-gray-400'>No Data</p>"
    
    # Overview
    ov = attr_data_single.get("overall", {})
    delta = ov.get("delta", 0)
    curr_r = ov.get("curr_rate", 0)
    
    color = "text-red-600" if delta > 0 else "text-green-600"
    arrow = "↑" if delta > 0 else "↓"
    
    html_overview = f"""
    <div class="mb-4 p-4 bg-slate-50 rounded-lg flex items-center justify-between">
        <div>
            <div class="text-xs text-gray-500 uppercase">Total Rate Change (vs Prev)</div>
            <div class="text-xl font-bold {color}">{arrow} {abs(delta):.2%}</div>
            <div class="text-xs text-gray-400">Current Rate: {curr_r:.2%}</div>
        </div>
        <div class="text-sm text-gray-500 text-right">
            <p>Comparing Current Window vs Previous Window</p>
            <p class="text-xs text-gray-400">(e.g. This Month vs Last Month)</p>
        </div>
    </div>
    """
    
    # Dimensions Tables
    dims = attr_data_single.get("dimensions", {})
    tables_html = ""
    
    for dim_name, rows in dims.items():
        if not rows: continue
        
        # Sort by Contribution (already sorted in backend, but ensure)
        # Limit to top 10
        top_rows = rows[:10]
        
        tbody = ""
        for r in top_rows:
            seg = r["segment"]
            vol_pct = r["curr_vol_pct"]
            rate = r["curr_rate"]
            
            # [v4.0] Removed Conn Rate from here
            
            rate_delta = r.get("rate_delta", 0) # Might be missing for Batch Analysis (contrib only)
            contrib = r["contribution"]
            
            # Format
            # Contrib > 0 means it INCREASED risk (Bad) -> Red
            c_color = "text-red-600 font-bold" if contrib > 0.0001 else ("text-green-600" if contrib < -0.0001 else "text-gray-400")
            
            d_html = "-"
            if "rate_delta" in r:
                d_color = "text-red-500" if rate_delta > 0 else "text-green-500"
                d_arrow = "↑" if rate_delta > 0 else "↓"
                d_html = f"<span class='{d_color} text-xs'>{d_arrow} {abs(rate_delta):.2%}</span>"
            
            tbody += f"""
            <tr class="border-b hover:bg-slate-50">
                <td class="p-2 font-medium text-xs truncate max-w-[120px]" title="{seg}">{seg}</td>
                <td class="p-2 text-right text-gray-500 text-xs">{vol_pct:.1%}</td>
                <td class="p-2 text-right text-xs">{rate:.2%}</td>
                <td class="p-2 text-right">{d_html}</td>
                <td class="p-2 text-right {c_color} text-xs">{contrib:+.2%}</td>
            </tr>
            """
            
        tables_html += f"""
        <div class="mb-6">
            <h4 class="text-sm font-bold text-gray-700 mb-2 border-l-4 border-blue-500 pl-2">{dim_name} (Top Contributors)</h4>
            <div class="overflow-x-auto border rounded-lg">
                <table class="w-full text-sm text-left">
                    <thead class="bg-gray-100 text-xs uppercase text-gray-500">
                        <tr>
                            <th class="p-2">Segment</th>
                            <th class="p-2 text-right">Vol %</th>
                            <th class="p-2 text-right">Bad Rate</th>
                            <th class="p-2 text-right">Delta</th>
                            <th class="p-2 text-right">Contrib</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white">
                        {tbody}
                    </tbody>
                </table>
            </div>
        </div>
        """
        
    return f"{html_overview}<div class='grid grid-cols-1 lg:grid-cols-2 gap-6'>{tables_html}</div>"

def make_contact_trend_json(contact_data):
    """Generate JSON for Contactability Trend Chart."""
    if not contact_data: return "null"
    
    trends = contact_data.get('trend', {})
    t_all = trends.get('all', [])
    t_new = trends.get('new', [])
    t_old = trends.get('old', [])
    
    dates = [x['date'] for x in t_all] if t_all else []
    
    def _map_vals(t_list):
        m = {x['date']: x['rate'] for x in t_list}
        return [m.get(d, None) for d in dates]
        
    y_all = [x['rate'] for x in t_all]
    y_new = _map_vals(t_new)
    y_old = _map_vals(t_old)
    
    return json.dumps({
        "tooltip": {"trigger": "axis", "formatter": None},
        "legend": {"data": ["Overall", "New", "Old"], "bottom": 0},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": "10%", "containLabel": True},
        "xAxis": {"type": "category", "boundaryGap": False, "data": dates},
        "yAxis": {"type": "value", "axisLabel": {"formatter": "{value}"}, "splitLine": {"lineStyle": {"type": "dashed"}}},
        "series": [
            {"name": "Overall", "type": "line", "data": y_all, "itemStyle": {"color": "#64748b"}, "smooth": True},
            {"name": "New", "type": "line", "data": y_new, "itemStyle": {"color": "#ef4444"}, "smooth": True},
            {"name": "Old", "type": "line", "data": y_old, "itemStyle": {"color": "#3b82f6"}, "smooth": True}
        ]
    })

def make_contactability_section(contact_data):
    """
    [v4.0 New] Contactability Analysis Section (HTML only).
    """
    if not contact_data: return ""
    
    # 1. MTD Comparison Cards
    mtd = contact_data.get('mtd', {})
    
    def _make_card(label, data):
        if not data: return ""
        curr = data.get('curr', 0)
        prev = data.get('prev', 0)
        delta = curr - prev
        
        d_color = "text-green-600" if delta > 0 else "text-red-500" # High Conn is good
        d_arrow = "↑" if delta > 0 else "↓"
        d_html = f"<span class='{d_color} text-sm ml-1'>{d_arrow}{abs(delta):.1%}</span>"
        
        return f"""
        <div class="bg-slate-50 rounded p-3 flex flex-col justify-between">
            <div class="text-xs text-gray-500 uppercase font-bold">{label}</div>
            <div class="mt-1">
                <span class="text-xl font-bold text-slate-700">{curr:.1%}</span>
                {d_html}
            </div>
            <div class="text-[10px] text-gray-400 mt-1">Prev: {prev:.1%}</div>
        </div>
        """
        
    card_all = _make_card("Overall (MTD)", mtd.get('all'))
    card_new = _make_card("New Users (MTD)", mtd.get('new'))
    card_old = _make_card("Old Users (MTD)", mtd.get('old'))
    
    return f"""
    <div class="card">
        <div class="flex items-center gap-2 mb-4 border-b pb-4">
            <div class="section-bar accent"></div>
            <h2 class="text-lg font-bold text-slate-800">可联性分析 (Contactability Analysis)</h2>
        </div>
        
        <div class="grid grid-cols-3 gap-4 mb-6">
            {card_all}{card_new}{card_old}
        </div>
        
        <div id="chart-contact-trend" class="h-[300px]"></div>
        
        <p class="text-xs text-gray-400 mt-2">* Connect Rate = Connected Balance / Overdue Balance (Risk View)</p>
    </div>
    """


def make_attribution_section(attr_data_map):
    """
    [v3.7 New] Render Risk Attribution with Tabs (Overall/New/Old).
    attr_data_map: {'overall': {...}, 'new': {...}, 'old': {...}}
    """
    if not attr_data_map: return ""
    
    html_all = make_attribution_content(attr_data_map.get("overall"))
    html_new = make_attribution_content(attr_data_map.get("new"))
    html_old = make_attribution_content(attr_data_map.get("old"))
    
    return f"""
    <div class="card">
        <div class="flex items-center justify-between mb-4 border-b pb-4">
            <div class="flex items-center gap-2">
                <div class="section-bar accent"></div>
                <h2 class="text-lg font-bold text-slate-800">归因分析 (Risk Attribution)</h2>
            </div>
            <div class="flex space-x-2 bg-slate-100 p-1 rounded-lg">
                <button onclick="switchTab('attr', 'all')" class="tab-btn active" id="btn-attr-all">Overall</button>
                <button onclick="switchTab('attr', 'new')" class="tab-btn" id="btn-attr-new">New</button>
                <button onclick="switchTab('attr', 'old')" class="tab-btn" id="btn-attr-old">Old</button>
            </div>
        </div>
        
        <div id="attr-section-all">{html_all}</div>
        <div id="attr-section-new" class="hidden">{html_new}</div>
        <div id="attr-section-old" class="hidden">{html_old}</div>
        
        <p class="text-xs text-gray-400 mt-2">* Risk Contrib: Impact of this segment on the total risk (Rate * Volume or Change contribution).</p>
    </div>
    """

def make_collection_performance_section(perf_data):
    """
    [v3.7 New] Collection Org Performance (Bucket -> Group -> Agent).
    [v3.8] MoM Benchmark.
    [v3.9] Process Attribution columns.
    [v4.1] Rate Contribution & Process Driver (Why did it drop?).
    """
    if not perf_data: return ""
    
    meta = perf_data.get("meta", {})
    curr_m = meta.get("current", "-")
    prev_m = meta.get("prev", "-")

    # 1. Bucket Summary
    buckets = perf_data.get("buckets", [])
    benchmarks = perf_data.get("benchmarks", {})
    
    # [v4.9] 兜底展示: 当 buckets 为空时显示"暂无数据"
    if not buckets:
        return f"""
<div class="card">
    <div class="flex items-center gap-2 mb-4 border-b pb-4">
        <div class="section-bar accent"></div>
        <h3 class="text-lg font-bold text-slate-800">催收团队效能 (Collection Performance)</h3>
    </div>
    <div class="text-sm text-slate-500 p-4 bg-slate-50 rounded-lg">
        暂无数据 — 当前月份 ({curr_m}) 的回收数据尚未汇总，或 agent_bucket 字段缺失。请确认 natural_month_repay 表是否包含当月数据。
    </div>
</div>
"""
    
    rows_b = []
    for b in buckets:
        name = b["agent_bucket"]
        rr = b["repay_rate"]
        vol = b["start_owing_principal"]
        
        # Benchmark comparison
        bm = benchmarks.get(name, 0.0)
        delta = rr - bm
        d_color = "text-green-600" if delta > 0 else "text-red-500"
        d_arrow = "↑" if delta > 0 else "↓"
        d_html = f"<span class='text-xs {d_color} ml-1'>{d_arrow}{abs(delta):.1%}</span>" if bm > 0 else ""

        rows_b.append(f"<tr><td class='p-2 font-medium'>{name}</td><td class='text-right p-2'>{int(vol):,}</td><td class='text-right p-2 font-bold text-slate-700'>{rr:.2%} {d_html}</td><td class='text-right p-2 text-xs text-gray-400'>{bm:.2%} (M-1)</td></tr>")
    
    html_bucket = f"""
    <div class="mb-6">
        <h3 class="text-sm font-bold text-gray-700 mb-2">整体阶段回收 (Bucket Overview) [{curr_m}]</h3>
        <table class="w-full text-sm border rounded">
            <thead class="bg-gray-50"><tr><th class="text-left p-2">Bucket</th><th class="text-right p-2">Owing Vol</th><th class="text-right p-2">Repay Rate</th><th class="text-right p-2">M-1 Benchmark</th></tr></thead>
            <tbody>{''.join(rows_b)}</tbody>
        </table>
    </div>
    """
    
    # 2. Group Rankings per Bucket
    groups = perf_data.get("groups", {})
    html_groups = ""
    
    for bucket, data in groups.items():
        all_list = data.get("all", [])
        bm_rate = data.get("benchmark", 0.0)
        p_bm = data.get("proc_benchmark", {})
        
        if not all_list: continue

        # Decide display mode: All (if small) or Top/Bottom
        is_short = len(all_list) <= 6
        
        def _render_row(item):
            rr = item['repay_rate']
            delta = item.get('delta_vs_benchmark', 0)
            d_color = "text-green-600" if delta > 0 else "text-red-500"
            
            # v4.1 New Fields
            contrib = item.get('contrib_to_delta', 0)
            driver = item.get('main_driver', '-')
            
            # Format Contrib
            c_cls = "text-gray-400"
            if contrib < -0.001: c_cls = "text-red-600 font-bold" # Negative contribution (Bad)
            elif contrib > 0.001: c_cls = "text-green-600"
            c_val = f"{contrib:+.2%}"
            
            # Process Metrics (Current)
            cov = item.get('cov', 0)
            conn = item.get('conn', 0)
            
            def fmt_proc(val):
                return f"{val:.0%}" if val > 0 else "-"

            return f"""
            <div class="grid grid-cols-12 gap-1 items-center text-xs py-2 border-b last:border-0 hover:bg-slate-50">
                <div class="col-span-3 truncate font-medium" title="{item['group_name']}">{item['group_name']}</div>
                <div class="col-span-2 text-right font-mono">{rr:.1%}</div>
                <div class="col-span-2 text-right {c_cls}">{c_val}</div>
                <div class="col-span-3 text-right text-slate-600" title="Main Driver of Drop">{driver}</div>
                <div class="col-span-2 text-right text-gray-400 text-[10px]">{fmt_proc(conn)}</div>
            </div>
            """

        content_html = ""
        # Header
        content_html += """
        <div class="grid grid-cols-12 gap-1 text-[10px] text-gray-400 uppercase border-b pb-1 mb-1">
            <div class="col-span-3">Group</div>
            <div class="col-span-2 text-right">Rate</div>
            <div class="col-span-2 text-right">Contrib</div>
            <div class="col-span-3 text-right">Main Issue</div>
            <div class="col-span-2 text-right">Conn%</div>
        </div>
        """
        
        if is_short:
             content_html += "".join([_render_row(x) for x in all_list])
        else:
             # Sort by Contribution to Delta (Ascending = Most Negative First)
             # Backend already sorted by Contrib
             neg_list = [x for x in all_list if x.get('contrib_to_delta', 0) < 0]
             pos_list = [x for x in all_list if x.get('contrib_to_delta', 0) >= 0]
             
             # Show Bottom 3 Contributors (Draggers) and Top 3 (Lifters)
             # List is sorted by contrib ascending (most negative first)
             bot3 = all_list[:3] # Most negative
             top3 = all_list[-3:] # Most positive (at end)
             
             content_html += "<div class='mb-1 mt-2 text-[10px] font-bold text-red-400 uppercase'>Negative Contrib (Draggers)</div>"
             content_html += "".join([_render_row(x) for x in bot3])
             content_html += "<div class='mb-1 mt-2 text-[10px] font-bold text-green-500 uppercase'>Positive Contrib (Lifters)</div>"
             content_html += "".join([_render_row(x) for x in reversed(top3)]) # Reverse to show best first
            
        html_groups += f"""
        <div class="mb-4 border rounded p-4 bg-white shadow-sm">
            <div class="flex justify-between mb-2">
                <h4 class="font-bold text-sm text-gray-800">{bucket} Groups</h4>
                <div class="text-xs text-right">
                    <div class="text-gray-500">M-1: {bm_rate:.1%}</div>
                </div>
            </div>
            <div class="space-y-0">
                {content_html}
            </div>
        </div>
        """
        
    return f"""
    <div class="card">
        <div class="flex items-center gap-2 mb-4 border-b pb-4">
            <div class="section-bar accent"></div>
            <h2 class="text-lg font-bold text-slate-800">催收归因与效能 (Recovery Attribution & Performance)</h2>
        </div>
        <p class="text-xs text-gray-400 mb-4">* Contribution: Impact of this group on the total Bucket Rate Change vs M-1. (Negative = Dragged down total rate)</p>
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div class="col-span-1">{html_bucket}</div>
            <div class="col-span-2 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-4">
                {html_groups}
            </div>
        </div>
    </div>
    """

def make_amount_pivot_section(pivot_data):
    """
    Generate Heatmap Section for Month x Amount
    pivot_data: { metric: { month: { amount: val } } }
    """
    if not pivot_data: return ""
    
    metrics = ["overdue_rate", "dpd1", "dpd5", "dpd30"]
    labels = {
        "overdue_rate": "Overdue Rate", 
        "dpd1": "DPD1", 
        "dpd5": "DPD5", 
        "dpd30": "DPD30"
    }
    
    # 1. Precompute HTML for each metric
    tables_html = {}
    default_metric = "dpd5"
    
    for m in metrics:
        data_m = pivot_data.get(m, {})
        if not data_m:
            tables_html[m] = "<div class='p-8 text-center text-gray-400'>No Data</div>"
            continue
            
        # Get all months (Rows) and amounts (Cols)
        months = sorted(list(data_m.keys()), reverse=True)
        amounts_set = set()
        for v in data_m.values():
            amounts_set.update(v.keys())
            
        # Custom Sort for Amounts
        def parse_amt(a):
            try:
                # Handle "3000-4000", "<1000", ">5000"
                a_str = str(a).strip()
                if "-" in a_str: return int(a_str.split("-")[0])
                if ">" in a_str: return int(float(a_str.replace(">","")))
                if "<" in a_str: return -1
                return float(a_str)
            except:
                return 999999
        
        sorted_amounts = sorted(list(amounts_set), key=parse_amt)
        
        # Calculate Color Scale (Min/Max) for this metric
        all_vals = []
        for r in data_m.values():
            all_vals.extend([x for x in r.values() if x is not None])
            
        if not all_vals:
            min_v, max_v = 0, 1
        else:
            min_v, max_v = min(all_vals), max(all_vals)
            
        # Build Table
        # Header
        th_cols = "".join([f"<th class='p-2 text-right font-medium text-gray-600 bg-gray-50 border-b'>{amt}</th>" for amt in sorted_amounts])
        thead = f"<thead><tr><th class='p-2 text-left font-medium text-gray-600 bg-gray-50 border-b w-32'>Month</th>{th_cols}</tr></thead>"
        
        # Body
        rows_html = []
        for mon in months:
            cells = []
            for amt in sorted_amounts:
                val = data_m[mon].get(amt)
                if val is None:
                    cells.append("<td class='p-2 text-right text-gray-300 border-b'>-</td>")
                else:
                    # Heatmap Color
                    bg_cls = get_bg_color(val, min_v, max_v, is_inverse=False) # High=Red
                    cells.append(f"<td class='p-2 text-right {bg_cls} border-b text-xs'>{val:.2%}</td>")
            rows_html.append(f"<tr><td class='p-2 font-mono text-gray-700 border-b font-medium'>{mon}</td>{''.join(cells)}</tr>")
            
        tables_html[m] = f"""
        <div class="overflow-x-auto border rounded-lg">
            <table class="w-full text-sm border-collapse bg-white">
                {thead}
                <tbody>{''.join(rows_html)}</tbody>
            </table>
        </div>
        """

    # 2. Build Container with Tabs
    buttons_html = ""
    content_html = ""
    
    for m in metrics:
        label = labels.get(m, m)
        is_active = (m == default_metric)
        active_cls = "bg-blue-600 text-white shadow-sm" if is_active else "bg-white text-gray-600 hover:bg-gray-50 border"
        
        buttons_html += f"""
        <button onclick="switchHeatmap('{m}')" 
                id="btn-heatmap-{m}"
                class="px-4 py-2 rounded-md text-sm font-medium transition-all {active_cls}">
            {label}
        </button>
        """
        
        hidden_cls = "" if is_active else "hidden"
        content_html += f"""
        <div id="heatmap-view-{m}" class="heatmap-view {hidden_cls} transition-all duration-300">
            {tables_html.get(m, "")}
        </div>
        """

    return f"""
    <div class="card">
        <div class="flex items-center justify-between mb-6 border-b pb-4">
            <div class="flex items-center gap-2">
                <div class="section-bar accent"></div>
                <h2 class="text-lg font-bold text-slate-800">金额段 x 月份热力图 (Amount Segment Heatmap)</h2>
            </div>
             <div class="flex space-x-2 bg-slate-100 p-1 rounded-lg">
                <!-- Using metric tabs -->
                {buttons_html}
            </div>
        </div>
        
        {content_html}
        
        <div class="mt-4 flex items-center gap-4 text-xs text-gray-500">
            <div class="flex items-center gap-1"><div class="w-3 h-3 bg-red-100 rounded"></div><span>High Risk</span></div>
            <div class="flex items-center gap-1"><div class="w-3 h-3 bg-red-50 rounded"></div><span>Med Risk</span></div>
            <div class="flex items-center gap-1"><div class="w-3 h-3 bg-emerald-50 rounded"></div><span>Low Risk</span></div>
            <span>* Color scale is relative to min/max of each metric.</span>
        </div>
    </div>
    
    <script>
    function switchHeatmap(metric) {{
        // Hide all views
        document.querySelectorAll('.heatmap-view').forEach(el => el.classList.add('hidden'));
        // Show target
        document.getElementById(`heatmap-view-${{metric}}`).classList.remove('hidden');
        
        // Reset buttons
        document.querySelectorAll('[id^="btn-heatmap-"]').forEach(el => {{
            el.className = "px-4 py-2 rounded-md text-sm font-medium transition-all bg-white text-gray-600 hover:bg-gray-50 border";
        }});
        
        // Highlight active
        const btn = document.getElementById(`btn-heatmap-${{metric}}`);
        btn.className = "px-4 py-2 rounded-md text-sm font-medium transition-all bg-blue-600 text-white shadow-sm";
    }}
    </script>
    """

def make_term_monitoring_section(term_data):
    """
    [v4.9] 期限监控矩阵 (Term × MOB)
    纵轴: 到期月 | 横轴: 所有MOB | 筛选: 客群 × 产品期数 × 指标
    热力图: 组内比 (每列MOB独立计算min/max)
    Lift: MoM = (本月-上月)/上月
    """
    if not term_data:
        return ""

    months = term_data.get("months", [])
    mob_cols = term_data.get("mob_cols", [1, 2, 3, 4])
    data = term_data.get("data", {})
    user_types = term_data.get("user_types", ["all"])
    period_seqs = term_data.get("period_seqs", ["all"])
    metrics = term_data.get("metrics", ["overdue_rate"])

    if not months:
        return ""

    # 标签
    ut_labels = {"all": "All"}
    for ut in user_types:
        if ut != "all": ut_labels[ut] = str(ut)

    ps_labels = {"all": "All"}
    for ps in period_seqs:
        if ps != "all": ps_labels[ps] = f"{ps}期"

    metric_labels = {
        "overdue_rate": "OVERDUE_RATE",
        "DPD5": "DPD5",
        "DPD7": "DPD7",
        "DPD15": "DPD15",
        "DPD30": "DPD30"
    }

    # 1. 筛选按钮
    ut_buttons = ""
    for i, ut in enumerate(user_types):
        active = "active" if i == 0 else ""
        label = ut_labels.get(ut, ut)
        ut_buttons += f'<button onclick="switchTermFilter(\'ut\', \'{ut}\')" class="tab-btn {active}" id="btn-term-ut-{ut}">{label}</button>\n'

    ps_buttons = ""
    for i, ps in enumerate(period_seqs):
        active = "active" if i == 0 else ""
        label = ps_labels.get(ps, ps)
        ps_buttons += f'<button onclick="switchTermFilter(\'ps\', \'{ps}\')" class="tab-btn {active}" id="btn-term-ps-{ps}">{label}</button>\n'

    metric_buttons = ""
    for i, mt in enumerate(metrics):
        active = "active" if i == 0 else ""
        label = metric_labels.get(mt, mt)
        metric_buttons += f'<button onclick="switchTermFilter(\'mt\', \'{mt}\')" class="tab-btn {active}" id="btn-term-mt-{mt}">{label}</button>\n'

    # 2. 生成每个 (metric, ut, ps) 组合的表格 — 组内比热力 + Lift
    tables_html = ""
    first = True
    for mt in metrics:
        for ut in user_types:
            for ps in period_seqs:
                month_mob_map = data.get((ut, ps, mt), {})
                hidden = "" if first else "hidden"
                first = False

                mob_headers = "".join([f"<th class='text-right p-2 font-medium text-slate-600 whitespace-nowrap'>MOB{m}</th>" for m in mob_cols])

                # 2a. 收集每列 MOB 的所有值 — 用于组内比
                col_vals = {m: [] for m in mob_cols}
                for month in months:
                    mob_rates = month_mob_map.get(month, {})
                    for m in mob_cols:
                        r = mob_rates.get(m)
                        if r is not None and isinstance(r, (int, float)):
                            col_vals[m].append(r)
                col_min = {m: (min(v) if v else 0) for m, v in col_vals.items()}
                col_max = {m: (max(v) if v else 1) for m, v in col_vals.items()}

                # 2b. 生成行
                rows_html = ""
                for idx, month in enumerate(months):
                    mob_rates = month_mob_map.get(month, {})
                    # 上一行 (时间上更早的月份) 用于 Lift 计算
                    prev_month = months[idx + 1] if idx + 1 < len(months) else None
                    prev_rates = month_mob_map.get(prev_month, {}) if prev_month else {}

                    cells = ""
                    for m in mob_cols:
                        rate = mob_rates.get(m)
                        if rate is not None:
                            # 组内比热力着色 (每列 MOB 独立)
                            cmin, cmax = col_min[m], col_max[m]
                            if cmax > cmin:
                                ratio = (rate - cmin) / (cmax - cmin)
                            else:
                                ratio = 0.5
                            if ratio > 0.75:
                                cls = "bg-red-100 text-red-700"
                            elif ratio > 0.50:
                                cls = "bg-orange-50 text-orange-700"
                            elif ratio > 0.25:
                                cls = "bg-yellow-50 text-yellow-700"
                            else:
                                cls = "bg-green-50 text-green-700"

                            # Lift (MoM)
                            lift_html = ""
                            prev_rate = prev_rates.get(m)
                            if prev_rate is not None and prev_rate > 0:
                                lift = (rate - prev_rate) / prev_rate
                                arrow = "↑" if lift > 0 else "↓"
                                color = "text-red-500" if lift > 0 else "text-green-500"
                                lift_html = f"<span class='term-lift text-[9px] {color} ml-0.5'>{arrow}{abs(lift):.1%}</span>"

                            cells += f"<td class='text-right p-2 {cls} font-medium whitespace-nowrap'>{rate:.2%}{lift_html}</td>"
                        else:
                            cells += "<td class='text-right p-2 text-slate-300'>-</td>"
                    rows_html += f"<tr class='border-b border-slate-100 hover:bg-slate-50'><td class='p-2 font-medium text-slate-700 whitespace-nowrap'>{month}</td>{cells}</tr>\n"

                tables_html += f"""
                <div class="term-matrix-table {hidden}" id="term-table-{mt}-{ut}-{ps}">
                    <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead><tr class="border-b-2 border-slate-200">
                            <th class="text-left p-2 font-medium text-slate-600">到期月</th>
                            {mob_headers}
                        </tr></thead>
                        <tbody>{rows_html}</tbody>
                    </table>
                    </div>
                </div>
                """

    return f"""
    <div class="card">
        <div class="flex items-center gap-2 mb-3">
            <div class="section-bar accent"></div>
            <h3 class="text-lg font-bold text-slate-800">期限监控矩阵 (Term × MOB)</h3>
        </div>
        <div class="flex flex-wrap items-center gap-x-6 gap-y-2 mb-4">
            <div class="flex items-center gap-2 text-xs text-slate-500">
                <span class="font-semibold">客群</span>
                <div class="flex space-x-1 bg-slate-100 p-1 rounded-lg">
                    {ut_buttons}
                </div>
            </div>
            <div class="flex items-center gap-2 text-xs text-slate-500">
                <span class="font-semibold">产品期数</span>
                <div class="flex space-x-1 bg-slate-100 p-1 rounded-lg">
                    {ps_buttons}
                </div>
            </div>
            <div class="flex items-center gap-2 text-xs text-slate-500">
                <span class="font-semibold">指标 (Metric)</span>
                <div class="flex space-x-1 bg-blue-50 p-1 rounded-lg">
                    {metric_buttons}
                </div>
            </div>
            <label class="flex items-center gap-2 cursor-pointer ml-auto">
                <div class="relative">
                    <input type="checkbox" id="toggle-term-lift" class="sr-only peer" checked onchange="toggleTermLift()">
                    <div class="w-9 h-5 bg-gray-200 peer-checked:bg-blue-500 rounded-full transition-colors"></div>
                    <div class="absolute left-0.5 top-0.5 w-4 h-4 bg-white rounded-full peer-checked:translate-x-4 transition-transform"></div>
                </div>
                <span class="text-xs text-slate-500 font-medium">Show Lift (MoM)</span>
            </label>
        </div>
        {tables_html}
        <p class="text-xs text-slate-400 mt-3">* 纵轴=到期月，横轴=放款期数 MOB，Lift = (本月-上月)/上月。</p>
    </div>
    """


# ─────────────────────────────────────────────────────────────────────────────
# [v4.10 NEW] 自然月回收序时 + 到期月回收曲线 HTML 渲染
# ─────────────────────────────────────────────────────────────────────────────

def make_natural_month_progress_section(nm_data):
    """[v4.13] 自然月回收序时 — 4层下钻: 模块级→大小额→组级→经办级"""
    if not nm_data:
        return ""

    import json

    # 直接传递整个 nm_data 到前端 (JS 负责渲染)
    nm_json = json.dumps(nm_data, ensure_ascii=False)

    return f'''
    <div class="card" id="nm-progress-card">
        <div class="flex items-center justify-between mb-4 border-b pb-4">
            <div class="flex items-center gap-2">
                <div class="section-bar" style="background:#10b981;"></div>
                <h2 class="text-lg font-bold text-slate-800">自然月回收序时 (Natural Month Recovery Progress)</h2>
            </div>
        </div>

        <!-- [v4.13] 面包屑导航 -->
        <div id="nm-breadcrumb" style="margin-bottom:12px;font-size:13px;color:#64748b;"></div>

        <!-- 实体按钮 -->
        <div class="flex items-center gap-4 mb-4">
            <span class="text-xs text-slate-500 font-medium" id="nm-btn-label">模块:</span>
            <div class="flex items-center gap-1 flex-wrap" id="nm-entity-btns"></div>
        </div>

        <!-- 下钻/返回 操作区 -->
        <div id="nm-drill-bar" style="margin-bottom:12px;display:flex;gap:8px;align-items:center;"></div>

        <div id="nm-chart" style="width:100%;height:420px;"></div>

        <!-- 汇总表 -->
        <div class="mt-6">
            <h3 class="text-sm font-semibold text-slate-600 mb-3" id="nm-summary-title">目标达成汇总</h3>
            <table class="w-full text-sm">
                <thead><tr class="bg-slate-50 text-slate-500 text-xs">
                    <th class="px-3 py-2 text-left" id="nm-th-entity">Bucket</th>
                    <th class="px-3 py-2 text-right">序时目标</th>
                    <th class="px-3 py-2 text-right">实际回收</th>
                    <th class="px-3 py-2 text-right">达成率</th>
                    <th class="px-3 py-2 text-left">进度</th>
                    <th class="px-3 py-2 text-left">截止</th>
                </tr></thead>
                <tbody id="nm-summary-tbody"></tbody>
            </table>
        </div>
    </div>

    <script>
    (function() {{
        /* ================================================================
         *  [v4.13] 自然月回收序时 — 4 层下钻
         *  L0 模块级 → L1 大小额 → L2 组级 → L3 经办级
         * ================================================================ */
        var NM = {nm_json};
        var nmChart = echarts.init(document.getElementById('nm-chart'));
        var LEVELS = NM.levels || [];
        var LD = NM.level_data || {{}};

        // 颜色
        var MC = ['#94a3b8','#64748b','#475569','#3b82f6','#2563eb','#1d4ed8','#1e40af'];
        var TC = '#ef4444';
        var EC = ['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#06b6d4',
                  '#84cc16','#f97316','#6366f1','#14b8a6','#e11d48','#a855f7','#0ea5e9',
                  '#22c55e','#eab308','#d946ef','#64748b','#2dd4bf','#fb923c'];

        // 层级名映射
        var LMAP = {{"模块级":0,"大小额":1,"组级":2,"经办级":3}};
        var LNAMES = ["模块级","大小额","组级","经办级"];
        var LLABELS = ["模块","子模块","组","经办"];

        // 状态
        var state = {{
            li: 0,           // 当前层级 index
            path: [],        // [{{li, name, entity}}]  面包屑路径
            selected: ''     // 当前选中实体
        }};

        /* ---------- 获取当前层级的实体列表 ---------- */
        function getEntities() {{
            var ln = LNAMES[state.li];
            if (!ln) return [];
            var ld = LD[ln];
            if (!ld) return [];

            if (state.li <= 1) {{
                // L0/L1: flat buckets, optionally filtered by parent
                var bkts = ld.buckets || [];
                if (state.li === 1 && state.path.length > 0) {{
                    var parent = state.path[state.path.length - 1].entity;
                    var pm = ld.parent_map || {{}};
                    bkts = bkts.filter(function(b) {{ return pm[b] === parent; }});
                }}
                return bkts;
            }} else {{
                // L2/L3: by_parent
                var bp = ld.by_parent || {{}};
                var parentKey = state.path.length > 0 ? state.path[state.path.length - 1].entity : '';
                var pg = bp[parentKey];
                return pg ? (pg.entities || []) : [];
            }}
        }}

        /* ---------- 获取当前层级某实体的数据 ---------- */
        function getEntityData(entity) {{
            var ln = LNAMES[state.li];
            var ld = LD[ln];
            if (!ld) return {{}};

            if (state.li <= 1) {{
                return (ld.data || {{}})[entity] || {{}};
            }} else {{
                var bp = ld.by_parent || {{}};
                var parentKey = state.path.length > 0 ? state.path[state.path.length - 1].entity : '';
                var pg = bp[parentKey];
                return pg ? ((pg.data || {{}})[entity] || {{}}) : {{}};
            }}
        }}

        /* ---------- 获取月份列表 ---------- */
        function getMonths() {{
            var ln = LNAMES[state.li];
            var ld = LD[ln];
            if (!ld) return [];

            if (state.li <= 1) {{
                return ld.months || [];
            }} else {{
                var bp = ld.by_parent || {{}};
                var parentKey = state.path.length > 0 ? state.path[state.path.length - 1].entity : '';
                var pg = bp[parentKey];
                return pg ? (pg.months || []) : [];
            }}
        }}

        /* ---------- 获取 summary ---------- */
        function getSummary() {{
            var ln = LNAMES[state.li];
            var ld = LD[ln];
            if (!ld) return {{}};

            if (state.li <= 1) {{
                return ld.summary || {{}};
            }} else {{
                var bp = ld.by_parent || {{}};
                var parentKey = state.path.length > 0 ? state.path[state.path.length - 1].entity : '';
                var pg = bp[parentKey];
                return pg ? (pg.summary || {{}}) : {{}};
            }}
        }}

        /* ---------- 渲染面包屑 ---------- */
        function renderBreadcrumb() {{
            var el = document.getElementById('nm-breadcrumb');
            var html = '';
            // 起点
            html += '<span style="cursor:pointer;color:#2563eb;font-weight:600;" onclick="nmGoTo(-1)">模块级</span>';
            state.path.forEach(function(p, i) {{
                html += ' <span style="color:#94a3b8;margin:0 4px;">›</span> ';
                var isLast = (i === state.path.length - 1);
                if (isLast) {{
                    html += '<span style="font-weight:600;color:#1e293b;">' + p.entity + '</span>';
                }} else {{
                    html += '<span style="cursor:pointer;color:#2563eb;font-weight:500;" onclick="nmGoTo(' + i + ')">' + p.entity + '</span>';
                }}
            }});
            el.innerHTML = html;
        }}

        /* ---------- 渲染实体按钮 ---------- */
        function renderEntityBtns() {{
            var container = document.getElementById('nm-entity-btns');
            var label = document.getElementById('nm-btn-label');
            container.innerHTML = '';
            label.textContent = LLABELS[state.li] + ':';

            var ents = getEntities();
            ents.forEach(function(ent, i) {{
                var btn = document.createElement('button');
                btn.textContent = ent;
                btn.dataset.entity = ent;
                btn.className = 'nm-ent-btn';
                btn.style.cssText = 'padding:4px 12px;border-radius:6px;font-size:13px;cursor:pointer;border:1px solid #cbd5e1;background:white;color:#64748b;transition:all 0.2s;margin-right:6px;margin-bottom:4px;';
                if (i === 0) {{
                    btn.style.background = '#eff6ff'; btn.style.color = '#2563eb'; btn.style.borderColor = '#93c5fd';
                }}
                btn.onclick = function() {{ selectEntity(ent); }};
                container.appendChild(btn);
            }});

            if (ents.length > 0 && !state.selected) state.selected = ents[0];
        }}

        /* ---------- 渲染下钻/返回按钮 ---------- */
        function renderDrillBar() {{
            var bar = document.getElementById('nm-drill-bar');
            var html = '';

            // 返回按钮
            if (state.li > 0) {{
                html += '<button onclick="nmGoBack()" style="padding:4px 14px;border-radius:6px;font-size:12px;cursor:pointer;border:1px solid #e2e8f0;background:#f8fafc;color:#64748b;">← 返回上级</button>';
            }}

            // 下钻按钮 (仅 L0/L1/L2 有下级)
            if (state.li < 3 && state.li < LEVELS.length - 1 && state.selected) {{
                var nextName = LNAMES[state.li + 1];
                html += '<button onclick="nmDrillDown()" style="padding:4px 14px;border-radius:6px;font-size:12px;cursor:pointer;border:1px solid #86efac;background:#f0fdf4;color:#16a34a;font-weight:600;">↓ 下钻到 ' + nextName + ' (' + state.selected + ')</button>';
            }}

            bar.innerHTML = html;
        }}

        /* ---------- 渲染图表 ---------- */
        function renderChart() {{
            if (state.li <= 1) {{
                renderChartMultiMonth();
            }} else {{
                renderChartMultiEntity();
            }}
        }}

        /* 多月模式: L0/L1, 选中一个实体, 每条线=一个月份 */
        function renderChartMultiMonth() {{
            var entity = state.selected;
            var data = getEntityData(entity);
            var months = getMonths();
            var series = [];

            months.forEach(function(m, i) {{
                if (!data[m]) return;
                var pts = data[m];
                var ci = Math.min(i, MC.length - 1);
                var isLatest = (i === months.length - 1);
                series.push({{
                    name: String(m), type: 'line', smooth: true, symbol: 'none',
                    lineStyle: {{ width: isLatest ? 3 : 1.5 }},
                    itemStyle: {{ color: MC[ci] }},
                    emphasis: {{ lineStyle: {{ width: 3 }} }},
                    data: pts.map(function(p) {{ return [p.day, +(p.cum_rate * 100).toFixed(2)]; }})
                }});
            }});

            // 目标线
            var tm = 250003;
            if (data[tm]) {{
                series.push({{
                    name: 'Target', type: 'line', smooth: true, symbol: 'none',
                    lineStyle: {{ width: 2.5, type: 'dashed', color: TC }},
                    itemStyle: {{ color: TC }},
                    data: data[tm].map(function(p) {{ return [p.day, +(p.cum_rate * 100).toFixed(2)]; }})
                }});
            }}

            setChartOption(series, entity + ' — 各月回收进度');
        }}

        /* 对比模式: L2/L3, 所有实体当月对比 */
        function renderChartMultiEntity() {{
            var ents = getEntities();
            var months = getMonths();
            var latestMonth = months.length > 0 ? months[months.length - 1] : 0;
            var series = [];

            ents.forEach(function(ent, i) {{
                var data = getEntityData(ent);
                var pts = data[latestMonth] || [];
                if (pts.length === 0) return;
                series.push({{
                    name: ent, type: 'line', smooth: true, symbol: 'none',
                    lineStyle: {{ width: 2 }},
                    itemStyle: {{ color: EC[i % EC.length] }},
                    data: pts.map(function(p) {{ return [p.day, +(p.cum_rate * 100).toFixed(2)]; }})
                }});
            }});

            var parentLabel = state.path.length > 0 ? state.path[state.path.length - 1].entity : '';
            setChartOption(series, parentLabel + ' — ' + LNAMES[state.li] + '对比 (' + latestMonth + ')');
        }}

        function setChartOption(series, title) {{
            nmChart.setOption({{
                title: {{ text: title, textStyle: {{ fontSize: 13, color: '#475569' }}, left: 10, top: 5 }},
                tooltip: {{
                    trigger: 'axis',
                    formatter: function(params) {{
                        var sorted = params.slice().sort(function(a, b) {{ return b.data[1] - a.data[1]; }});
                        var html = '<b>Day ' + params[0].data[0] + '</b><br/>';
                        sorted.forEach(function(p) {{
                            html += '<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:' + p.color + ';margin-right:5px;"></span>' + p.seriesName + ': ' + p.data[1].toFixed(2) + '%<br/>';
                        }});
                        return html;
                    }}
                }},
                legend: {{ bottom: 0, type: 'scroll', textStyle: {{ fontSize: 11 }} }},
                grid: {{ left: 60, right: 30, top: 40, bottom: 50 }},
                xAxis: {{ type: 'value', name: 'Day', min: 1, max: 31, interval: 1, axisLabel: {{ fontSize: 11 }} }},
                yAxis: {{ type: 'value', name: 'Recovery %', axisLabel: {{ formatter: '{{value}}%', fontSize: 11 }} }},
                series: series
            }}, true);
        }}

        /* ---------- 渲染汇总表 ---------- */
        function renderSummaryTable() {{
            var tbody = document.getElementById('nm-summary-tbody');
            var thEnt = document.getElementById('nm-th-entity');
            thEnt.textContent = LLABELS[state.li];

            var ents = getEntities();
            var summ = getSummary();
            var html = '';

            ents.forEach(function(ent) {{
                var s = summ[ent];
                if (!s) {{
                    html += '<tr><td class="px-3 py-2 font-medium">' + ent + '</td><td colspan="5" class="text-center text-slate-400">暂无目标数据</td></tr>';
                    return;
                }}
                var tr = s.target_rate_at_day || 0;
                var ar = s.actual_rate || 0;
                var ac = s.achieve_pct || 0;
                var ad = s.actual_day || 0;
                var lm = s.latest_month || 0;
                var bc = ac >= 1.0 ? '#22c55e' : (ac >= 0.9 ? '#f59e0b' : '#ef4444');
                var bw = Math.min(ac * 100, 100);
                html += '<tr class="border-t border-slate-100">' +
                    '<td class="px-3 py-2 font-medium text-slate-700">' + ent + '</td>' +
                    '<td class="px-3 py-2 text-right">' + (tr*100).toFixed(2) + '%</td>' +
                    '<td class="px-3 py-2 text-right font-semibold">' + (ar*100).toFixed(2) + '%</td>' +
                    '<td class="px-3 py-2 text-right font-bold" style="color:'+bc+'">' + (ac*100).toFixed(1) + '%</td>' +
                    '<td class="px-3 py-2"><div style="background:#e2e8f0;border-radius:4px;height:8px;width:100px;"><div style="background:'+bc+';border-radius:4px;height:8px;width:'+bw.toFixed(0)+'px;"></div></div></td>' +
                    '<td class="px-3 py-2 text-xs text-slate-400">Day '+ad+' / '+lm+'</td></tr>';
            }});

            tbody.innerHTML = html || '<tr><td colspan="6" class="text-center py-4 text-slate-400">暂无数据</td></tr>';
        }}

        /* ---------- 交互: 选中实体 ---------- */
        function selectEntity(ent) {{
            state.selected = ent;
            document.querySelectorAll('.nm-ent-btn').forEach(function(btn) {{
                if (btn.dataset.entity === ent) {{
                    btn.style.background='#eff6ff'; btn.style.color='#2563eb'; btn.style.borderColor='#93c5fd';
                }} else {{
                    btn.style.background='white'; btn.style.color='#64748b'; btn.style.borderColor='#cbd5e1';
                }}
            }});
            renderDrillBar();
            if (state.li <= 1) renderChart();
        }}
        window.selectEntity = selectEntity;

        /* ---------- 交互: 下钻 ---------- */
        window.nmDrillDown = function() {{
            if (state.li >= 3 || state.li >= LEVELS.length - 1) return;
            state.path.push({{ li: state.li, name: LNAMES[state.li], entity: state.selected }});
            state.li += 1;
            state.selected = '';
            refreshAll();
        }};

        /* ---------- 交互: 返回上级 ---------- */
        window.nmGoBack = function() {{
            if (state.path.length === 0) return;
            var prev = state.path.pop();
            state.li = prev.li;
            state.selected = prev.entity;
            refreshAll();
        }};

        /* ---------- 交互: 面包屑跳转 ---------- */
        window.nmGoTo = function(idx) {{
            if (idx < 0) {{
                // 回到顶层
                state.path = [];
                state.li = 0;
                state.selected = '';
            }} else {{
                // 跳到 path[idx] 的下一级
                var target = state.path[idx];
                state.path = state.path.slice(0, idx + 1);
                state.li = target.li + 1;
                state.selected = '';
            }}
            refreshAll();
        }};

        /* ---------- 全量刷新 ---------- */
        function refreshAll() {{
            renderBreadcrumb();
            renderEntityBtns();
            var ents = getEntities();
            if (!state.selected && ents.length > 0) state.selected = ents[0];
            selectEntity(state.selected);
            renderChart();
            renderSummaryTable();
            renderDrillBar();
        }}

        // 初始化
        refreshAll();
        window.addEventListener('resize', function() {{ nmChart.resize(); }});
    }})();
    </script>
    '''


def make_due_month_recovery_section(dm_data):
    """[v4.12] 生成到期月回收曲线 — 只按 user_type 筛选，tooltip 降序排列"""
    if not dm_data:
        return ""
    
    import json
    
    user_types = dm_data.get("user_types", [])
    due_months = dm_data.get("due_months", [])
    data = dm_data.get("data", {})
    
    if not user_types or not data:
        return ""
    
    # 到期月颜色 (越近越深)
    dm_colors = ['#cbd5e1', '#94a3b8', '#64748b', '#475569', '#334155', '#1e293b', '#3b82f6', '#2563eb', '#1d4ed8', '#7c3aed']
    
    # 构建每个 user_type 的 series 数据
    all_chart_data = {}
    for ut in user_types:
        combo_data = data.get(ut, {})
        series_list = []
        
        for i, dm in enumerate(due_months):
            if dm not in combo_data:
                continue
            points = combo_data[dm]
            color_idx = min(i, len(dm_colors) - 1)
            is_latest = (i == len(due_months) - 1)
            
            series_list.append({
                "name": str(dm),
                "type": "line",
                "smooth": True,
                "symbol": "none",
                "lineStyle": {"width": 2.5 if is_latest else 1.2},
                "itemStyle": {"color": dm_colors[color_idx]},
                "data": [[p["day"], round(p["recovery_rate"] * 100, 2)] for p in points]
            })
        
        all_chart_data[ut] = series_list
    
    chart_json = json.dumps(all_chart_data, ensure_ascii=False)
    
    # 客群筛选按钮 (唯一筛选维度)
    ut_btns = ""
    for i, ut in enumerate(user_types):
        active = "background:#eff6ff;color:#2563eb;border-color:#93c5fd;" if i == 0 else ""
        ut_btns += f'<button class="dm-ut-btn" data-ut="{ut}" style="padding:4px 12px;border-radius:6px;font-size:13px;cursor:pointer;border:1px solid #cbd5e1;background:white;color:#64748b;transition:all 0.2s;margin-right:6px;{active}" onclick="switchDMUserType(this)">{ut}</button>'
    
    default_ut = user_types[0] if user_types else ""
    
    return f'''
    <div class="card" id="dm-recovery-card">
        <div class="flex items-center justify-between mb-4 border-b pb-4">
            <div class="flex items-center gap-2">
                <div class="section-bar" style="background:#8b5cf6;"></div>
                <h2 class="text-lg font-bold text-slate-800">到期月回收曲线 (Due Month Recovery Curve)</h2>
            </div>
            <div class="flex items-center gap-2">
                <span class="text-xs text-slate-500 font-medium">客群:</span>
                <div class="flex items-center gap-1">{ut_btns}</div>
            </div>
        </div>
        
        <div id="dm-chart" style="width:100%;height:400px;"></div>
        <p class="text-xs text-slate-400 mt-2">* 回收率 = 1 - 剩余本金 / 到期逾期本金。X轴 = 距到期日天数。</p>
    </div>
    
    <script>
    (function() {{
        var dmChartsData = {chart_json};
        var dmChart = echarts.init(document.getElementById('dm-chart'));
        var currentDMUt = '{default_ut}';
        
        function renderDMChart(ut) {{
            var seriesData = dmChartsData[ut] || [];
            var option = {{
                tooltip: {{
                    trigger: 'axis',
                    formatter: function(params) {{
                        // [v4.12] 按回收率降序排列 (值大的月份在上面)
                        var sorted = params.slice().sort(function(a, b) {{ return b.data[1] - a.data[1]; }});
                        var html = '<b>DPD+' + params[0].data[0] + '</b><br/>';
                        sorted.forEach(function(p) {{
                            html += '<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:' + p.color + ';margin-right:5px;"></span>' + p.seriesName + ': ' + p.data[1].toFixed(2) + '%<br/>';
                        }});
                        return html;
                    }}
                }},
                legend: {{ bottom: 0, type: 'scroll', textStyle: {{ fontSize: 11 }} }},
                grid: {{ left: 60, right: 30, top: 30, bottom: 50 }},
                xAxis: {{ type: 'value', name: 'Days from Due Date', axisLabel: {{ fontSize: 11 }} }},
                yAxis: {{ type: 'value', name: 'Recovery %', axisLabel: {{ formatter: '{{value}}%', fontSize: 11 }} }},
                series: seriesData
            }};
            dmChart.setOption(option, true);
        }}
        
        window.switchDMUserType = function(btn) {{
            var ut = btn.dataset.ut;
            currentDMUt = ut;
            // 重置所有按钮样式
            document.querySelectorAll('.dm-ut-btn').forEach(function(b) {{
                b.style.background = 'white';
                b.style.color = '#64748b';
                b.style.borderColor = '#cbd5e1';
            }});
            // 激活点击的按钮
            btn.style.background = '#eff6ff';
            btn.style.color = '#2563eb';
            btn.style.borderColor = '#93c5fd';
            // 渲染图表
            renderDMChart(ut);
        }};
        
        renderDMChart(currentDMUt);
        window.addEventListener('resize', function() {{ dmChart.resize(); }});
    }})();
    </script>
    '''


def build_cashloan_html(
    vintage_summary, repay_summary, process_summary, 
    vintage_anomalies, repay_anomalies, 
    excel_path, date_str, overview=None, repay_name="repay_cl", is_placeholder=False,
    trend_d=None, trend_w=None, trend_m=None,
    trend_d_new=None, trend_w_new=None, trend_m_new=None,
    trend_d_old=None, trend_w_old=None, trend_m_old=None,
    matrix_daily=None, matrix_weekly=None, matrix_monthly=None,
    lift_metrics=None,
    # v3.1
    lift_metrics_new=None, lift_metrics_old=None,
    matrix_daily_new=None, matrix_daily_old=None,
    matrix_weekly_new=None, matrix_weekly_old=None,
    matrix_monthly_new=None, matrix_monthly_old=None,
    # v3.4 Breakdown Data
    bd_daily_all=None, bd_daily_new=None, bd_daily_old=None,
    bd_weekly_all=None, bd_weekly_new=None, bd_weekly_old=None,
    bd_monthly_all=None, bd_monthly_new=None, bd_monthly_old=None,
    # v3.5 Pivot Data
    amount_pivot_data=None,
    # v3.6 Attribution
    attribution_data=None,
    # v3.7 Collection Perf
    perf_data=None,
    # v4.0 Contactability
    contact_data=None,
    # v4.9 Term Monitoring Matrix
    term_data=None,
    # v4.10 Target Achievement
    nm_progress_data=None,
    dm_recovery_data=None,
    # Compatibility
    matrix_all=None, matrix_new=None, matrix_old=None
):
    kpi_cards = make_kpi_cards(vintage_summary, repay_summary, process_summary)
    
    # ... (Charts logic)
    chart_daily_all = make_trend_chart_json(trend_d, "chart_daily_all", "整体日趋势")
    chart_weekly_all = make_trend_chart_json(trend_w, "chart_weekly_all", "整体周趋势")
    chart_monthly_all = make_trend_chart_json(trend_m, "chart_monthly_all", "整体月趋势")
    
    chart_daily_new = make_trend_chart_json(trend_d_new, "chart_daily_new", "新客日趋势")
    chart_weekly_new = make_trend_chart_json(trend_w_new, "chart_weekly_new", "新客周趋势")
    chart_monthly_new = make_trend_chart_json(trend_m_new, "chart_monthly_new", "新客月趋势")
    
    chart_daily_old = make_trend_chart_json(trend_d_old, "chart_daily_old", "老客日趋势")
    chart_weekly_old = make_trend_chart_json(trend_w_old, "chart_weekly_old", "老客周趋势")
    chart_monthly_old = make_trend_chart_json(trend_m_old, "chart_monthly_old", "老客月趋势")

    html_repay = make_repay_table(repay_summary)
    html_process = make_process_table(process_summary)
    html_anomalies = make_anomalies_list(vintage_anomalies, repay_anomalies)
    
    # ... (Matrix and Lift logic)
    m_d_new = matrix_daily_new or []
    m_d_old = matrix_daily_old or []
    m_w_new = matrix_weekly_new or []
    m_w_old = matrix_weekly_old or []
    m_m_new = matrix_monthly_new or []
    m_m_old = matrix_monthly_old or []
    
    html_matrix_daily = make_vintage_matrix_v3_group(matrix_daily, m_d_new, m_d_old, "Daily")
    html_matrix_weekly = make_vintage_matrix_v3_group(matrix_weekly, m_w_new, m_w_old, "Weekly")
    html_matrix_monthly = make_vintage_matrix_v3_group(matrix_monthly, m_m_new, m_m_old, "Monthly")

    html_lift = make_lift_analysis_v3_3(lift_metrics, lift_metrics_new, lift_metrics_old)

    # v3.6 Attribution
    html_attribution = make_attribution_section(attribution_data)

    # v3.7 Collection Perf
    html_perf = make_collection_performance_section(perf_data)

    # v3.5 Amount Heatmap
    html_amount_heatmap = make_amount_pivot_section(amount_pivot_data)
    
    # v4.0 Contactability
    html_contact = make_contactability_section(contact_data)
    chart_contact_json = make_contact_trend_json(contact_data)

    # [v4.9 New] Term Monitoring Matrix
    html_term_matrix = make_term_monitoring_section(term_data)

    # [v4.10 New] Natural Month Progress + Due Month Recovery
    html_nm_progress = make_natural_month_progress_section(nm_progress_data)
    html_dm_recovery = make_due_month_recovery_section(dm_recovery_data)

    # 6. Breakdown (v3.4: Multi-period Split)
    html_breakdown_section = make_breakdown_section_v3_4(
        bd_daily_all, bd_daily_new, bd_daily_old,
        bd_weekly_all, bd_weekly_new, bd_weekly_old,
        bd_monthly_all, bd_monthly_new, bd_monthly_old
    )

    # [v4.1] Removed Time Series Breakdown (Consolidated)

    # [v4.0 Restructure] Risk -> Repay -> Process
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CashLoan Inspection Report {date_str} (v4.11)</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ font-family: 'Inter', system-ui, sans-serif; background: #f8fafc; color: #1e293b; }}
        .card {{ background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 20px; margin-bottom: 24px; }}
        .tab-btn {{ padding: 6px 12px; border-radius: 6px; font-weight: 500; cursor: pointer; transition: all 0.2s; font-size: 14px; }}
        .tab-btn.active {{ background: #eff6ff; color: #2563eb; }}
        .tab-btn.hover {{ background: #f1f5f9; }}
        .hidden {{ display: none; }}
        .section-bar {{ width: 4px; height: 16px; background: #2563eb; border-radius: 2px; }}
        .section-title {{ font-size: 20px; font-weight: 800; color: #1e293b; margin: 32px 0 16px 0; display: flex; align-items: center; gap: 8px; }}
        .section-title span {{ width: 24px; height: 24px; background: #3b82f6; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; }}
        .hide-lift .lift-indicator {{ display: none !important; }}
        .lift-toggle {{ padding: 4px 10px; border-radius: 6px; font-size: 12px; cursor: pointer; border: 1px solid #cbd5e1; background: white; color: #64748b; transition: all 0.2s; }}
        .lift-toggle.active {{ background: #eff6ff; color: #2563eb; border-color: #93c5fd; }}
    </style>
</head>
<body class="p-6 max-w-[1400px] mx-auto">
    <!-- Header -->
    <div class="flex justify-between items-center mb-8">
        <div>
            <h1 class="text-2xl font-bold text-slate-800">CashLoan Inspection Report v4.11</h1>
            <p class="text-slate-500 mt-1">Generated: {date_str} | Source: {os.path.basename(excel_path) if excel_path else 'N/A'}</p>
        </div>
        <div class="text-right">
             <div class="text-sm font-medium text-slate-600">Overview</div>
             <div class="text-xs text-slate-400">Rows: V:{overview.get('vintage_rows',0)} R:{overview.get('repay_rows',0)}</div>
        </div>
    </div>

    <!-- Part 1: Risk Profile -->
    <div class="section-title"><span>1</span>风险态势 (Risk Profile)</div>
    
    <!-- 1.1 KPI Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {kpi_cards}
    </div>

    <!-- 1.2 Vintage Matrix (Promoted) [v4.9] Lift Toggle -->
    <div class="card" id="vintage-matrix-card">
        <div class="flex items-center justify-between mb-4 border-b pb-4">
            <div class="flex items-center gap-2">
                <div class="section-bar accent"></div>
                <h2 class="text-lg font-bold text-slate-800">Vintage 矩阵 (Risk Matrix)</h2>
            </div>
            <div class="flex items-center space-x-3">
                <button onclick="toggleLift()" class="lift-toggle" id="btn-lift-toggle" style="display:none;">Show Lift</button>
                <div class="flex space-x-2 bg-slate-100 p-1 rounded-lg">
                    <button onclick="switchMatrix('daily')" class="tab-btn active" id="btn-matrix-daily">Daily</button>
                    <button onclick="switchMatrix('weekly')" class="tab-btn" id="btn-matrix-weekly">Weekly</button>
                    <button onclick="switchMatrix('monthly')" class="tab-btn" id="btn-matrix-monthly">Monthly</button>
                </div>
            </div>
        </div>
        <div id="matrix-view-daily" class="matrix-view hide-lift">
             {html_matrix_daily}
        </div>
        <div id="matrix-view-weekly" class="matrix-view hidden">
             {html_matrix_weekly}
        </div>
        <div id="matrix-view-monthly" class="matrix-view hidden">
             {html_matrix_monthly}
        </div>
    </div>

    <!-- 1.3 MTD Lift -->
    <div class="card">
        <div class="flex items-center justify-between mb-4 border-b pb-4">
            <div class="flex items-center gap-2">
                <div class="section-bar accent"></div>
                <h2 class="text-lg font-bold text-slate-800">MTD 环比分析 (Lift Analysis)</h2>
            </div>
             <div class="flex space-x-2 bg-slate-100 p-1 rounded-lg">
                <button onclick="switchTab('lift', 'all')" class="tab-btn active" id="btn-lift-all">Overall</button>
                <button onclick="switchTab('lift', 'new')" class="tab-btn" id="btn-lift-new">New</button>
                <button onclick="switchTab('lift', 'old')" class="tab-btn" id="btn-lift-old">Old</button>
            </div>
        </div>
        {html_lift}
    </div>

    <!-- 1.4 Due Trends -->
    <div class="card">
        <div class="flex items-center justify-between mb-4 border-b pb-4">
             <div class="flex items-center gap-2">
                <div class="section-bar accent"></div>
                <h2 class="text-lg font-bold text-slate-800">资产质量趋势 (Due Trends)</h2>
            </div>
            <div class="flex space-x-4">
                <div class="flex space-x-2 bg-slate-100 p-1 rounded-lg">
                    <button onclick="switchTrendMain('all')" class="tab-btn active" id="btn-trend-main-all">Overall</button>
                    <button onclick="switchTrendMain('new')" class="tab-btn" id="btn-trend-main-new">New</button>
                    <button onclick="switchTrendMain('old')" class="tab-btn" id="btn-trend-main-old">Old</button>
                </div>
                <div class="border-l pl-4 flex space-x-2 bg-slate-100 p-1 rounded-lg">
                    <button onclick="switchTrendSub('daily')" class="tab-btn active" id="btn-trend-sub-daily">Daily</button>
                    <button onclick="switchTrendSub('weekly')" class="tab-btn" id="btn-trend-sub-weekly">Weekly</button>
                    <button onclick="switchTrendSub('monthly')" class="tab-btn" id="btn-trend-sub-monthly">Monthly</button>
                </div>
            </div>
        </div>
        
        <div id="trend-all-daily" class="trend-view h-[350px]"></div>
        <div id="trend-all-weekly" class="trend-view hidden h-[350px]"></div>
        <div id="trend-all-monthly" class="trend-view hidden h-[350px]"></div>
        
        <div id="trend-new-daily" class="trend-view hidden h-[350px]"></div>
        <div id="trend-new-weekly" class="trend-view hidden h-[350px]"></div>
        <div id="trend-new-monthly" class="trend-view hidden h-[350px]"></div>
        
        <div id="trend-old-daily" class="trend-view hidden h-[350px]"></div>
        <div id="trend-old-weekly" class="trend-view hidden h-[350px]"></div>
        <div id="trend-old-monthly" class="trend-view hidden h-[350px]"></div>
    </div>

    <!-- 1.5 Risk Attribution (Pure) -->
    {html_attribution}

    <!-- 1.6 Contactability (New) -->
    {html_contact}

    <!-- 1.7 Term Monitoring Matrix (v4.9 New) -->
    {html_term_matrix}

    <!-- 1.8 Deep Dive (Heatmap & Breakdown) -->
    {html_amount_heatmap}
    {html_breakdown_section}
    
    <!-- Part 2: Recovery Results -->
    <div class="section-title"><span>2</span>回收结果 (Recovery Performance)</div>

    <!-- 2.1 Repay Summary -->
    <div class="card">
        <div class="flex items-center gap-2 mb-4 border-b pb-4">
            <div class="section-bar accent"></div>
            <h3 class="text-lg font-bold text-slate-800">自然月回收概览 (Repay Summary)</h3>
        </div>
        <div class="overflow-x-auto">{html_repay}</div>
    </div>

    <!-- 2.2 Collection Org Perf -->
    {html_perf}

    <!-- 2.3 Natural Month Recovery Progress (v4.10 New) -->
    {html_nm_progress}

    <!-- 2.4 Due Month Recovery Curve (v4.10 New) -->
    {html_dm_recovery}

    <!-- Part 3: Process Execution -->
    <div class="section-title"><span>3</span>过程执行 (Process Execution)</div>

    <!-- 3.1 Process Summary -->
    <div class="card">
        <div class="flex items-center gap-2 mb-4 border-b pb-4">
            <div class="section-bar accent"></div>
            <h3 class="text-lg font-bold text-slate-800">过程指标概览 (Process Summary)</h3>
        </div>
        <div class="overflow-x-auto">{html_process}</div>
    </div>

    <!-- 3.2 Anomalies -->
    <div class="card border-l-4 border-red-500">
        <h3 class="text-md font-bold text-red-600 mb-2">异常诊断 (Anomalies)</h3>
        <div class="text-sm text-slate-600 space-y-1">
            {html_anomalies}
        </div>
    </div>

    <!-- Footer -->
    <div class="text-center text-slate-400 text-sm mt-8 pb-8">
        <p>Report System v4.9 | Maintainer: <strong>Mr. Yuan</strong></p>
    </div>

    <script>
        // Init Charts
        const charts = {{}};
        
        function initChart(domId, option) {{
            if (!option) return;
            const chart = echarts.init(document.getElementById(domId));
            if(option.tooltip && !option.tooltip.formatter) {{
                option.tooltip.formatter = function(params) {{
                   let res = params[0].name + '<br/>';
                   params.forEach(item => {{
                       let val = item.value;
                       if (val !== null && val !== undefined) {{
                            if (typeof val === 'number') val = val.toFixed(4); 
                       }} else {{
                            val = '-';
                       }}
                       res += item.marker + item.seriesName + ': ' + val + '<br/>';
                   }});
                   return res;
                }};
            }}
            chart.setOption(option);
            charts[domId] = chart;
        }}

        // Data Injection
        const chartData = {{
            "trend-all-daily": {chart_daily_all},
            "trend-all-weekly": {chart_weekly_all},
            "trend-all-monthly": {chart_monthly_all},
            "trend-new-daily": {chart_daily_new},
            "trend-new-weekly": {chart_weekly_new},
            "trend-new-monthly": {chart_monthly_new},
            "trend-old-daily": {chart_daily_old},
            "trend-old-weekly": {chart_weekly_old},
            "trend-old-monthly": {chart_monthly_old},
            "contact-trend": {chart_contact_json},
        }};

        // Render Initial Active Chart
        initChart("trend-all-daily", chartData["trend-all-daily"]);
        
        // Render Contact Chart (Always Visible)
        if (document.getElementById("chart-contact-trend")) {{
            initChart("chart-contact-trend", chartData["contact-trend"]);
        }}

        // Trend Tab Logic
        let currentTrendMain = 'all';
        let currentTrendSub = 'daily';

        function updateTrendView() {{
            document.querySelectorAll('.trend-view').forEach(el => el.classList.add('hidden'));
            const targetId = `trend-${{currentTrendMain}}-${{currentTrendSub}}`;
            const targetEl = document.getElementById(targetId);
            if (targetEl) {{
                targetEl.classList.remove('hidden');
                if (!charts[targetId]) {{
                    initChart(targetId, chartData[targetId]);
                }} else {{
                    charts[targetId].resize();
                }}
            }}
        }}

        function switchTrendMain(type) {{
            currentTrendMain = type;
            document.querySelectorAll('[id^="btn-trend-main-"]').forEach(el => el.classList.remove('active'));
            document.getElementById(`btn-trend-main-${{type}}`).classList.add('active');
            updateTrendView();
        }}

        function switchTrendSub(period) {{
            currentTrendSub = period;
            document.querySelectorAll('[id^="btn-trend-sub-"]').forEach(el => el.classList.remove('active'));
            document.getElementById(`btn-trend-sub-${{period}}`).classList.add('active');
            updateTrendView();
        }}
        
        // Matrix Tab Logic [v4.9] with Lift toggle support
        let currentMatrixPeriod = 'daily';
        let liftEnabled = false;

        function switchMatrix(period) {{
            currentMatrixPeriod = period;
            document.querySelectorAll('.matrix-view').forEach(el => {{
                el.classList.add('hidden');
                el.classList.remove('hide-lift');
            }});
            const target = document.getElementById(`matrix-view-${{period}}`);
            target.classList.remove('hidden');
            
            // Daily: 强制隐藏 Lift，隐藏按钮
            const liftBtn = document.getElementById('btn-lift-toggle');
            if (period === 'daily') {{
                target.classList.add('hide-lift');
                liftBtn.style.display = 'none';
                liftBtn.classList.remove('active');
                liftEnabled = false;
            }} else {{
                liftBtn.style.display = '';
                if (!liftEnabled) {{
                    target.classList.add('hide-lift');
                }}
            }}
            
            document.querySelectorAll('[id^="btn-matrix-"]').forEach(el => el.classList.remove('active'));
            document.getElementById(`btn-matrix-${{period}}`).classList.add('active');
        }}

        function toggleLift() {{
            liftEnabled = !liftEnabled;
            const btn = document.getElementById('btn-lift-toggle');
            const target = document.getElementById(`matrix-view-${{currentMatrixPeriod}}`);
            if (liftEnabled) {{
                btn.classList.add('active');
                target.classList.remove('hide-lift');
            }} else {{
                btn.classList.remove('active');
                target.classList.add('hide-lift');
            }}
        }}

        // Term Monitoring Matrix Filter Logic [v4.9] - 3维筛选: metric × ut × ps
        let currentTermUt = '{term_data.get("user_types", ["all"])[0] if term_data else "all"}';
        let currentTermPs = '{term_data.get("period_seqs", ["all"])[0] if term_data else "all"}';
        let currentTermMt = '{term_data.get("metrics", ["overdue_rate"])[0] if term_data else "overdue_rate"}';

        function switchTermFilter(dim, val) {{
            if (dim === 'ut') {{
                currentTermUt = val;
                document.querySelectorAll('[id^="btn-term-ut-"]').forEach(el => el.classList.remove('active'));
                document.getElementById(`btn-term-ut-${{val}}`).classList.add('active');
            }} else if (dim === 'ps') {{
                currentTermPs = val;
                document.querySelectorAll('[id^="btn-term-ps-"]').forEach(el => el.classList.remove('active'));
                document.getElementById(`btn-term-ps-${{val}}`).classList.add('active');
            }} else if (dim === 'mt') {{
                currentTermMt = val;
                document.querySelectorAll('[id^="btn-term-mt-"]').forEach(el => el.classList.remove('active'));
                document.getElementById(`btn-term-mt-${{val}}`).classList.add('active');
            }}
            document.querySelectorAll('.term-matrix-table').forEach(el => el.classList.add('hidden'));
            const targetId = `term-table-${{currentTermMt}}-${{currentTermUt}}-${{currentTermPs}}`;
            const targetEl = document.getElementById(targetId);
            if (targetEl) targetEl.classList.remove('hidden');
        }}

        // Term Matrix Lift Toggle
        function toggleTermLift() {{
            const show = document.getElementById('toggle-term-lift').checked;
            document.querySelectorAll('.term-lift').forEach(el => {{
                el.style.display = show ? '' : 'none';
            }});
        }}

        // Lift Tab Logic
        function switchTab(group, type) {{
            const container = document.getElementById(`btn-${{group}}-${{type}}`).closest('.card');
            container.querySelectorAll(`[id^="${{group}}-section-"]`).forEach(el => el.classList.add('hidden'));
            container.querySelector(`#${{group}}-section-${{type}}`).classList.remove('hidden');
            container.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(`btn-${{group}}-${{type}}`).classList.add('active');
        }}

        window.addEventListener('resize', () => {{
            Object.values(charts).forEach(c => c.resize());
        }});
    </script>
</body>
</html>
"""

def main():
    pass

if __name__ == "__main__":
    pass
