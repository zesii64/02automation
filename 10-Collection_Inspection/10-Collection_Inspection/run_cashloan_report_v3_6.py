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
    for r in matrix_data:
        ent = r["entrant_rate"]
        ent_cls = get_bg_color(ent, min_ent, max_ent, False)
        ent_html = f"<td class='text-right {ent_cls} font-medium p-1'>{ent:.2%}</td>" if ent is not None else "<td>-</td>"
        
        rec_html = ""
        d_map = r.get(data_key, {})
        for d in show_days:
            k = f"D{d}"
            v = d_map.get(k)
            if v is None:
                rec_html += "<td class='text-right text-gray-300 p-1'>-</td>"
            else:
                cmin, cmax = col_stats.get(k)
                # If DPD mode: Low is Good (Green), High is Bad (Red) -> is_inverse=False
                # If Recovery mode: High is Good (Green) -> is_inverse=True
                cls = get_bg_color(v, cmin, cmax, is_inverse=(not is_dpd_mode))
                rec_html += f"<td class='text-right {cls} p-1'>{v:.1%}</td>"
        
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

def make_attribution_section(attr_data):
    """
    [v3.6 New] Render Risk Attribution tables.
    """
    if not attr_data: return ""
    
    # Overview
    ov = attr_data.get("overall", {})
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
    dims = attr_data.get("dimensions", {})
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

    return f"""
    <div class="card">
        <div class="flex items-center gap-2 mb-4 border-b pb-4">
            <div class="section-bar accent"></div>
            <h2 class="text-lg font-bold text-slate-800">归因分析 (Risk Attribution)</h2>
        </div>
        {html_overview}
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {tables_html}
        </div>
        <p class="text-xs text-gray-400 mt-2">* Risk Contrib: Impact of this segment on the total risk (Rate * Volume or Change contribution).</p>
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
    # Compatibility
    matrix_all=None, matrix_new=None, matrix_old=None
):
    kpi_cards = make_kpi_cards(vintage_summary, repay_summary, process_summary)
    
    # ... (Charts logic unchanged)
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
    
    # ... (Matrix and Lift logic unchanged)
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

    # v3.5 Amount Heatmap
    html_amount_heatmap = make_amount_pivot_section(amount_pivot_data)

    # 6. Breakdown (v3.4: Multi-period Split)
    html_breakdown_section = make_breakdown_section_v3_4(
        bd_daily_all, bd_daily_new, bd_daily_old,
        bd_weekly_all, bd_weekly_new, bd_weekly_old,
        bd_monthly_all, bd_monthly_new, bd_monthly_old
    )

    # [v3.3] Time Series Breakdown (Keep it)
    t_d_all = make_trend_data_table(trend_d, "Overall Daily")
    t_d_new = make_trend_data_table(trend_d_new, "New User Daily")
    t_d_old = make_trend_data_table(trend_d_old, "Old User Daily")
    
    t_w_all = make_trend_data_table(trend_w, "Overall Weekly")
    t_w_new = make_trend_data_table(trend_w_new, "New User Weekly")
    t_w_old = make_trend_data_table(trend_w_old, "Old User Weekly")
    
    t_m_all = make_trend_data_table(trend_m, "Overall Monthly")
    t_m_new = make_trend_data_table(trend_m_new, "New User Monthly")
    t_m_old = make_trend_data_table(trend_m_old, "Old User Monthly")
    
    html_time_breakdown = f"""
    <div class="card">
        <div class="flex items-center justify-between mb-4 border-b pb-4">
             <div class="flex items-center gap-2">
                <div class="section-bar accent"></div>
                <h3 class="text-lg font-bold text-slate-800">分时明细 (Time Series Data)</h3>
            </div>
            <div class="flex space-x-2 bg-slate-100 p-1 rounded-lg">
                <button onclick="switchTimeBD('daily')" class="tab-btn active" id="btn-time-daily">Daily</button>
                <button onclick="switchTimeBD('weekly')" class="tab-btn" id="btn-time-weekly">Weekly</button>
                <button onclick="switchTimeBD('monthly')" class="tab-btn" id="btn-time-monthly">Monthly</button>
            </div>
        </div>
        
        <div id="time-bd-daily" class="time-bd-view">
            {t_d_all}{t_d_new}{t_d_old}
        </div>
        <div id="time-bd-weekly" class="time-bd-view hidden">
            {t_w_all}{t_w_new}{t_w_old}
        </div>
        <div id="time-bd-monthly" class="time-bd-view hidden">
            {t_m_all}{t_m_new}{t_m_old}
        </div>
    </div>
    <script>
    function switchTimeBD(period) {{
        document.querySelectorAll('.time-bd-view').forEach(el => el.classList.add('hidden'));
        document.getElementById(`time-bd-${{period}}`).classList.remove('hidden');
        
        document.querySelectorAll('[id^="btn-time-"]').forEach(el => el.classList.remove('active'));
        document.getElementById(`btn-time-${{period}}`).classList.add('active');
    }}
    </script>
    """

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CashLoan Inspection Report {date_str} (v3.4)</title>
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
    </style>
</head>
<body class="p-6 max-w-[1400px] mx-auto">
    <!-- Header -->
    <div class="flex justify-between items-center mb-8">
        <div>
            <h1 class="text-2xl font-bold text-slate-800">CashLoan Inspection Report v3.4</h1>
            <p class="text-slate-500 mt-1">Generated: {date_str} | Source: {os.path.basename(excel_path) if excel_path else 'N/A'}</p>
        </div>
        <div class="text-right">
             <div class="text-sm font-medium text-slate-600">Overview</div>
             <div class="text-xs text-slate-400">Rows: V:{overview.get('vintage_rows',0)} R:{overview.get('repay_rows',0)}</div>
        </div>
    </div>

    <!-- 1. KPI Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {kpi_cards}
    </div>

    <!-- 2. MTD Lift Analysis -->
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

    <!-- 2.5 Risk Attribution (v3.6) -->
    {html_attribution}

    <!-- 3. Risk Trends -->
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

    <!-- 3.5 Amount Heatmap -->
    {html_amount_heatmap}

    <!-- 4. Vintage Matrix -->
    <div class="card">
        <div class="flex items-center justify-between mb-4 border-b pb-4">
            <div class="flex items-center gap-2">
                <div class="section-bar accent"></div>
                <h2 class="text-lg font-bold text-slate-800">Vintage 矩阵 (Risk Matrix)</h2>
            </div>
            <div class="flex space-x-2 bg-slate-100 p-1 rounded-lg">
                <button onclick="switchMatrix('daily')" class="tab-btn active" id="btn-matrix-daily">Daily</button>
                <button onclick="switchMatrix('weekly')" class="tab-btn" id="btn-matrix-weekly">Weekly</button>
                <button onclick="switchMatrix('monthly')" class="tab-btn" id="btn-matrix-monthly">Monthly</button>
            </div>
        </div>
        
        <div id="matrix-view-daily" class="matrix-view">
             {html_matrix_daily}
        </div>
        <div id="matrix-view-weekly" class="matrix-view hidden">
             {html_matrix_weekly}
        </div>
        <div id="matrix-view-monthly" class="matrix-view hidden">
             {html_matrix_monthly}
        </div>
    </div>
    
    <!-- 5. Breakdown (v3.4 Multi-Period) -->
    {html_breakdown_section}
    
    <!-- 6. Time Series Data (v3.3) -->
    {html_time_breakdown}

    <!-- 7. Repay & Process -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div class="card">
            <h3 class="text-md font-bold mb-4">回收与归因 (Attribution)</h3>
            <div class="overflow-x-auto">{html_repay}</div>
        </div>
        <div class="card">
            <h3 class="text-md font-bold mb-4">过程指标 (Process)</h3>
            <div class="overflow-x-auto">{html_process}</div>
        </div>
    </div>

    <!-- 8. Anomalies -->
    <div class="card border-l-4 border-red-500">
        <h3 class="text-md font-bold text-red-600 mb-2">异常诊断 (Anomalies)</h3>
        <div class="text-sm text-slate-600 space-y-1">
            {html_anomalies}
        </div>
    </div>

    <!-- Footer -->
    <div class="text-center text-slate-400 text-sm mt-8 pb-8">
        <p>Report System v3.6 | Maintainer: <strong>Mr. Yuan</strong></p>
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
        }};

        // Render Initial Active Chart
        initChart("trend-all-daily", chartData["trend-all-daily"]);

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
        
        // Matrix Tab Logic
        function switchMatrix(period) {{
            document.querySelectorAll('.matrix-view').forEach(el => el.classList.add('hidden'));
            document.getElementById(`matrix-view-${{period}}`).classList.remove('hidden');
            document.querySelectorAll('[id^="btn-matrix-"]').forEach(el => el.classList.remove('active'));
            document.getElementById(`btn-matrix-${{period}}`).classList.add('active');
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
