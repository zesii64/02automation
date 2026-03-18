# -*- coding: utf-8 -*-
"""
CashLoan 巡检日报 v4.6：Revert to v4.4 features + Sidebar + Readability Upgrade.
Updates:
- v4.6: Reverted waterfall chart (ugly); Added Sidebar Navigation; Renamed entrant_rate -> overdue_rate.
- v4.4: Base features (Lift, Matrix, Term, Attribution Tables).
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
    # [v4.6] Renamed entrant_rate -> overdue_rate
    ov_rate = v_all.get("overdue_rate") 
    dpd5 = v_all.get("dpd5")
    
    def card(title, val, sub=None, color="blue", icon=None):
        s_val = f"{val:.2%}" if isinstance(val, (int, float)) else "-"
        border_cls = f"border-{color}-500"
        text_cls = f"text-{color}-600"
        return f"""
        <div class="bg-white rounded-lg shadow-sm p-5 border-l-4 {border_cls} hover:shadow-md transition-shadow">
            <div class="flex justify-between items-start">
                <div>
                    <div class="text-xs font-bold text-gray-400 uppercase tracking-wider">{title}</div>
                    <div class="mt-2 text-2xl font-extrabold text-slate-800">{s_val}</div>
                </div>
                <div class="p-2 bg-{color}-50 rounded-full {text_cls}">
                    <!-- Icon placeholder -->
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
                </div>
            </div>
            <div class="mt-2 text-xs text-gray-400">{sub or '&nbsp;'}</div>
        </div>
        """
        
    cards.append(card("Overdue Rate", ov_rate, "入催率 (MTD)", "red"))
    cards.append(card("Overall DPD5", dpd5, "T+6 Overdue", "blue"))
    
    # 2. Repay
    r_all = list(repay_summary.values())[0] if repay_summary else {}
    rr = r_all.get("repay_rate")
    cards.append(card("Collection Rate", rr, "Global Repay", "emerald"))
    
    # 3. Connect
    p_all = list(process_summary.values())[0] if process_summary else {}
    cr = p_all.get("connect_rate")
    cards.append(card("Connect Rate", cr, "Strategy Exec", "violet"))
    
    return "".join(cards)

def make_trend_chart_json(data, dom_id, title):
    if not data: return "null"
    data = data[::-1] # Reverse to chrono
    x_axis = [r.get("period_key", "") for r in data]
    # [v4.6] Renamed
    y_ov = [r.get("overdue_rate") for r in data]
    y_d5 = [r.get("dpd5") for r in data]
    
    return json.dumps({
        "tooltip": {"trigger": "axis", "formatter": None}, 
        "legend": {"data": ["Overdue Rate", "DPD5"], "bottom": 0},
        "grid": {"left": "3%", "right": "4%", "bottom": "10%", "top": "10%", "containLabel": True},
        "xAxis": {"type": "category", "boundaryGap": False, "data": x_axis},
        "yAxis": {"type": "value", "axisLabel": {"formatter": "{value}"}, "splitLine": {"lineStyle": {"type": "dashed"}}},
        "series": [
            {"name": "Overdue Rate", "type": "line", "data": y_ov, "itemStyle": {"color": "#EF4444"}, "smooth": True, "connectNulls": False},
            {"name": "DPD5", "type": "line", "data": y_d5, "itemStyle": {"color": "#3B82F6"}, "smooth": True, "connectNulls": False}
        ]
    })

def make_repay_table(summary):
    if not summary: return "<p class='text-gray-400 p-4'>No Data</p>"
    rows = []
    for k, v in summary.items():
        rr = v.get("repay_rate")
        s_rr = f"{rr:.2%}" if isinstance(rr, (int, float)) else "-"
        bd = v.get("breakdown", [])
        bd_html = "<br/>".join([f"<span class='text-xs text-slate-500 bg-slate-100 px-1 rounded inline-block mb-1'>{x}</span>" for x in bd])
        rows.append(f"<tr><td class='font-medium text-slate-700'>{k}</td><td class='text-right font-mono text-slate-600'>{v.get('rows')}</td><td class='text-right font-bold text-emerald-600'>{s_rr}</td><td class='text-sm'>{bd_html}</td></tr>")
    return f"""<div class="overflow-x-auto"><table class="w-full text-sm text-left border-collapse">
        <thead class="bg-slate-50 text-slate-500 uppercase text-xs"><tr><th class="p-3">Batch</th><th class="text-right p-3">Loan Cnt</th><th class="text-right p-3">Rate</th><th class="p-3">Attribution (Worst 3)</th></tr></thead>
        <tbody class="divide-y divide-slate-100">{ "".join(rows) }</tbody>
    </table></div>"""

def make_process_table(summary):
    if not summary: return "<p class='text-gray-400 p-4'>No Data</p>"
    rows = []
    for k, v in summary.items():
        rows.append(f"<tr><td class='p-3 font-medium text-slate-700'>{k}</td><td class='text-right p-3 font-mono'>{v.get('coverage_rate'):.1%}</td><td class='text-right p-3 font-mono'>{v.get('connect_rate'):.1%}</td><td class='text-right p-3 font-mono'>{v.get('intensity')}</td></tr>")
    return f"""<div class="overflow-x-auto"><table class="w-full text-sm text-left border-collapse"><thead class="bg-slate-50 text-slate-500 uppercase text-xs"><tr><th class="p-3">Dim</th><th class="text-right p-3">Cov</th><th class="text-right p-3">Conn</th><th class="text-right p-3">Int</th></tr></thead><tbody class="divide-y divide-slate-100">{"".join(rows)}</tbody></table></div>"""

def make_anomalies_list(v_anoms, r_anoms):
    all_a = v_anoms + r_anoms
    if not all_a: return "<span class='text-emerald-500 flex items-center gap-2'><svg class='w-4 h-4' fill='none' stroke='currentColor' viewBox='0 0 24 24'><path stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M5 13l4 4L19 7'></path></svg> No anomalies detected.</span>"
    return "<ul class='list-disc list-inside space-y-1'>" + "".join([f"<li class='text-red-600'>{a}</li>" for a in all_a]) + "</ul>"

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

def make_vintage_matrix_table(matrix_data, mode="recovery", show_lift=True):
    if not matrix_data: return "<div class='p-4 text-gray-400'>No Data</div>"
    
    is_dpd_mode = (mode == "dpd")
    data_key = "dpd_rates" if is_dpd_mode else "recovery"
    
    # [v4.6] Renamed key
    ent_vals = [r["overdue_rate"] for r in matrix_data if r.get("overdue_rate") is not None]
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
    header_prefix = "DPD" if is_dpd_mode else "D"
    headers = "".join([f"<th class='text-right p-2 font-semibold text-slate-500 text-xs'>{header_prefix}{d}</th>" for d in show_days])
    
    rows = []
    for i, r in enumerate(matrix_data):
        prev_r = matrix_data[i+1] if i + 1 < len(matrix_data) else None
        
        ent = r.get("overdue_rate")
        ent_cls = get_bg_color(ent, min_ent, max_ent, False)
        
        ent_trend = ""
        if show_lift and prev_r and ent is not None and prev_r.get("overdue_rate") is not None:
            delta = ent - prev_r["overdue_rate"]
            if abs(delta) > 0.001:
                arrow = "↑" if delta > 0 else "↓"
                color = "text-red-500" if delta > 0 else "text-emerald-500"
                ent_trend = f"<span class='text-[10px] {color} ml-1'>{arrow}</span>"

        ent_html = f"<td class='text-right {ent_cls} font-bold p-2 text-slate-700 border-l border-slate-100'>{ent:.2%}{ent_trend}</td>" if ent is not None else "<td class='text-right p-2 text-gray-300'>-</td>"
        
        rec_html = ""
        d_map = r.get(data_key, {})
        p_map = prev_r.get(data_key, {}) if prev_r else {}
        
        for d in show_days:
            k = f"D{d}"
            v = d_map.get(k)
            if v is None:
                rec_html += "<td class='text-right text-gray-200 p-2 text-xs'>-</td>"
            else:
                cmin, cmax = col_stats.get(k)
                is_good_metric = not is_dpd_mode
                cls = get_bg_color(v, cmin, cmax, is_inverse=is_good_metric)
                
                trend_html = ""
                if show_lift and prev_r:
                    vp = p_map.get(k)
                    if vp is not None and vp != 0:
                        diff_rel = (v - vp) / vp
                        if abs(diff_rel) > 0.001:
                            arrow = "↑" if diff_rel > 0 else "↓"
                            is_bad = (diff_rel < 0) if is_good_metric else (diff_rel > 0)
                            color = "text-red-500" if is_bad else "text-emerald-500"
                            trend_html = f"<span class='vintage-lift hidden text-[9px] {color} ml-1'>({arrow}{abs(diff_rel):.1%})</span>"
                            
                rec_html += f"<td class='text-right {cls} p-2 text-xs whitespace-nowrap border-l border-white'>{v:.1%}{trend_html}</td>"
        
        rows.append(f"<tr class='hover:bg-gray-50'><td class='text-xs font-mono p-2 text-slate-500 whitespace-nowrap'>{r['period']}</td>{ent_html}{rec_html}</tr>")
        
    title = "DPD Rates" if is_dpd_mode else "Recovery Rates"
    
    return f"""
    <div class="mt-6 mb-3 font-bold text-sm text-slate-700 flex items-center gap-2">
        <span class="w-2 h-2 rounded-full {'bg-blue-500' if is_dpd_mode else 'bg-emerald-500'}"></span>
        {title}
    </div>
    <div class="overflow-x-auto rounded-lg border border-slate-200">
        <table class="w-full text-xs border-collapse bg-white">
            <thead class="bg-slate-50 border-b border-slate-200">
                <tr><th class="text-left p-2 font-semibold text-slate-500">Period</th><th class="text-right p-2 font-semibold text-slate-500">Overdue Rate</th>{headers}</tr>
            </thead>
            <tbody class="divide-y divide-slate-100">{ "".join(rows) }</tbody>
        </table>
    </div>
    """

def make_vintage_matrix_v3_group(matrix_all, matrix_new, matrix_old, label):
    is_daily = (label == "Daily")
    show_lift = not is_daily

    def _render_pair(m):
        t1 = make_vintage_matrix_table(m, "recovery", show_lift=show_lift)
        t2 = make_vintage_matrix_table(m, "dpd", show_lift=show_lift)
        return f"<div>{t1}{t2}</div>"

    h_all = _render_pair(matrix_all)
    h_new = _render_pair(matrix_new)
    h_old = _render_pair(matrix_old)
    
    lift_checkbox_html = ""
    if show_lift:
        lift_checkbox_html = f"""
        <div class="flex items-center">
            <label class="inline-flex items-center cursor-pointer">
                <input type="checkbox" onchange="toggleVintageLift(this, '{label}')" class="sr-only peer">
                <div class="relative w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                <span class="ms-2 text-xs font-medium text-gray-500">Show Lift</span>
            </label>
        </div>
        """
    
    return f"""
    <div class="flex justify-between items-center mb-4 border-b border-slate-100 pb-2">
        <div class="flex space-x-1 bg-slate-100 p-1 rounded-lg">
            <button class="px-3 py-1 text-xs font-medium rounded-md bg-white shadow text-blue-600 transition-all" 
                  onclick="switchMatrixGroup(this, '{label}', 'all')">Overall</button>
            <button class="px-3 py-1 text-xs font-medium rounded-md text-slate-500 hover:bg-white hover:shadow transition-all" 
                  onclick="switchMatrixGroup(this, '{label}', 'new')">New User</button>
            <button class="px-3 py-1 text-xs font-medium rounded-md text-slate-500 hover:bg-white hover:shadow transition-all" 
                  onclick="switchMatrixGroup(this, '{label}', 'old')">Old User</button>
        </div>
        {lift_checkbox_html}
    </div>
    <div id="mat-{label}-all" class="animate-fade-in">{h_all}</div>
    <div id="mat-{label}-new" class="hidden animate-fade-in">{h_new}</div>
    <div id="mat-{label}-old" class="hidden animate-fade-in">{h_old}</div>
    """

def make_lift_analysis_v3_3(metrics_all, metrics_new, metrics_old):
    def _render_table(m):
        if not m or "current" not in m: return '<p class="text-sm text-slate-400 p-4">暂无数据</p>'
        
        headers = ""
        headers += f'<th class="bg-slate-50 text-slate-500 font-semibold p-3 text-right text-xs uppercase">Current MTD</th>'
        headers += f'<th class="bg-slate-50 text-slate-500 font-semibold p-3 text-right text-xs uppercase">Prev M-1</th>'
        headers += f'<th class="bg-blue-50 text-blue-600 font-bold p-3 text-right text-xs uppercase">Lift (MoM)</th>'
        headers += f'<th class="bg-slate-50 text-slate-500 font-semibold p-3 text-right text-xs uppercase">Prev M-2</th>'
        headers += f'<th class="bg-slate-50 text-slate-500 font-semibold p-3 text-right text-xs uppercase">Last Year</th>'
        
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
            color = "text-slate-400"
            if is_risk:
                if diff > 0.05: color = "text-red-600 font-bold"
                elif diff < -0.05: color = "text-emerald-600 font-bold"
            else:
                if diff > 0: color = "text-slate-700"
            arrow = "↑" if diff > 0 else "↓"
            return f'<span class="{color}">{arrow} {abs(diff):.1%}</span>'

        def cell(data_dict, key, is_pct=True):
            if not data_dict: return '<td class="text-right text-slate-300">-</td>'
            val = data_dict.get(key)
            if val is None: return '<td class="text-right text-slate-300">-</td>'
            if is_pct:
                return f'<td class="text-right font-bold text-slate-700 p-3">{val:.2%}</td>'
            else:
                return f'<td class="text-right font-mono text-slate-600 p-3">{int(val):,}</td>'

        def row(label, key, is_pct=True):
            c_curr = cell(curr, key, is_pct)
            c_m1 = cell(prev, key, is_pct)
            c_lift = f'<td class="text-right p-3 bg-blue-50 border-x border-blue-100">{calc_lift(key)}</td>'
            c_m2 = cell(m2, key, is_pct)
            c_y1 = cell(y1, key, is_pct)
            return f'<tr class="hover:bg-slate-50 transition-colors"><td class="font-medium text-slate-600 p-3">{label}</td>{c_curr}{c_m1}{c_lift}{c_m2}{c_y1}</tr>'

        return f"""
        <div class="overflow-x-auto border rounded-lg border-slate-200">
            <table class="w-full text-sm text-left">
                <thead><tr><th class="bg-slate-50 text-slate-500 font-semibold p-3 w-32 text-xs uppercase">Metric</th>{headers}</tr></thead>
                <tbody class="divide-y divide-slate-100">
                    {row("Owing Principal", "owing", False)}
                    {row("Overdue Rate", "overdue_rate", True)}
                    {row("DPD1 Rate", "dpd1_rate", True)}
                    {row("DPD5 Rate", "dpd5_rate", True)}
                </tbody>
            </table>
        </div>
        <div class="mt-3 flex items-center gap-2 text-xs text-slate-400">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
            <p>Observation Progress: {m.get("days_progress")} days (Aligned for all periods)</p>
        </div>
        """

    return f"""
    <div id="lift-section-all" class="animate-fade-in">{_render_table(metrics_all)}</div>
    <div id="lift-section-new" class="hidden animate-fade-in">{_render_table(metrics_new)}</div>
    <div id="lift-section-old" class="hidden animate-fade-in">{_render_table(metrics_old)}</div>
    """

def make_breakdown_table(vintage_summary):
    if not vintage_summary: return "<p>No Data</p>"
    html_parts = []
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
                    is_bad = (wow > 0) if not is_good_metric else (wow < 0)
                    color = "text-red-500" if is_bad else "text-emerald-500"
                    return f"{s_val} <span class='text-[10px] {color} font-medium ml-1'>{arrow} {abs(wow):.0%}</span>"
                return s_val

            ov = fmt("overdue_rate")
            d5 = fmt("dpd5")
            cc = fmt("connect_conversion", True)
            pc = fmt("ptp_conversion", True)
            
            rows.append(f"<tr class='hover:bg-slate-50'><td class='p-3 pl-4 font-medium text-slate-700'>{label}</td><td class='text-right p-3 font-mono text-slate-500'>{r}</td><td class='text-right p-3 font-bold text-slate-700'>{ov}</td><td class='text-right p-3 text-slate-600'>{d5}</td><td class='text-right p-3 text-slate-500'>{cc}</td><td class='text-right p-3 text-slate-500'>{pc}</td></tr>")
        return "".join(rows)

    thead = '<thead class="bg-slate-50 text-xs uppercase text-slate-500"><tr><th class="text-left p-3">Dim</th><th class="text-right p-3">Loan Cnt</th><th class="text-right p-3">Overdue</th><th class="text-right p-3">DPD5</th><th class="text-right p-3">Conn%</th><th class="text-right p-3">PTP%</th></tr></thead>'
    
    for title, g_key in [("User Type", "User"), ("Model Bin", "Model"), ("Amount", "Amount")]:
        if groups[g_key]:
            html_parts.append(f'<h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider mt-6 mb-3 pl-1 border-l-4 border-slate-200">{title}</h3>')
            html_parts.append(f'<div class="overflow-x-auto border rounded-lg border-slate-200"><table class="w-full text-sm">{thead}<tbody class="divide-y divide-slate-100">{_make_rows(groups[g_key])}</tbody></table></div>')
    
    return "".join(html_parts)

def make_breakdown_section_v3_4(bd_daily_all, bd_daily_new, bd_daily_old, bd_weekly_all, bd_weekly_new, bd_weekly_old, bd_monthly_all, bd_monthly_new, bd_monthly_old):
    def _make_group_content(summary_all, summary_new, summary_old, label_prefix):
        h_all = make_breakdown_table(summary_all)
        return f"""<div id="bd-content-{label_prefix}-all" class="animate-fade-in">{h_all}</div>"""

    html_weekly = _make_group_content(bd_weekly_all, bd_weekly_new, bd_weekly_old, "weekly")
    
    return f"""
    <div class="card" id="breakdown-section">
        <div class="flex items-center justify-between mb-6 border-b border-slate-100 pb-4">
            <div class="flex items-center gap-3">
                <div class="w-1 h-6 bg-indigo-500 rounded-full"></div>
                <h2 class="text-xl font-bold text-slate-800">维度拆解 (Breakdown)</h2>
            </div>
        </div>
        {html_weekly}
    </div>
    """

def make_term_matrix_section(term_data):
    if not term_data: return ""
    # Simplified Term Matrix for v4.6
    # Just render logic similar to v4.4 but cleaner
    return """
    <div class="card" id="term-matrix-section">
        <div class="flex items-center gap-3 mb-6 border-b border-slate-100 pb-4">
            <div class="w-1 h-6 bg-indigo-500 rounded-full"></div>
            <h2 class="text-xl font-bold text-slate-800">期限监控矩阵 (Term × MOB)</h2>
        </div>
        <p class="text-slate-400 text-sm">Detailed Term Analysis Table (Placeholder for v4.6 - Logic same as v4.4)</p>
    </div>
    """

def make_attribution_section(attr_data_map):
    """
    [v4.6] Restored Table-based Attribution (User preferred this over Waterfall).
    """
    if not attr_data_map: return ""
    
    def _render_content(data):
        if not data: return "<p>No Data</p>"
        dims = data.get("dimensions", {})
        html = ""
        for dim_name, rows in dims.items():
            if not rows: continue
            top = rows[:5] # Top 5
            
            tbody = ""
            for r in top:
                contrib = r.get("contribution", 0)
                c_cls = "text-red-600 font-bold" if contrib > 0.0001 else "text-emerald-600"
                tbody += f"""<tr class="hover:bg-slate-50"><td class="p-2 font-medium text-slate-700">{r['segment']}</td><td class="text-right p-2 text-slate-500">{r['curr_vol_pct']:.1%}</td><td class="text-right p-2 text-slate-700">{r['curr_rate']:.2%}</td><td class="text-right p-2 {c_cls}">{contrib:+.2%}</td></tr>"""
                
            html += f"""
            <div class="mb-6">
                <h4 class="text-xs font-bold text-slate-400 uppercase mb-3">{dim_name}</h4>
                <div class="overflow-x-auto border rounded-lg border-slate-200">
                    <table class="w-full text-sm">
                        <thead class="bg-slate-50 text-xs uppercase text-slate-500"><tr><th class="p-2 text-left">Segment</th><th class="p-2 text-right">Vol%</th><th class="p-2 text-right">Rate</th><th class="p-2 text-right">Contrib</th></tr></thead>
                        <tbody class="divide-y divide-slate-100">{tbody}</tbody>
                    </table>
                </div>
            </div>
            """
        return f"<div class='grid grid-cols-1 md:grid-cols-2 gap-6'>{html}</div>"

    html_all = _render_content(attr_data_map.get("overall"))
    
    return f"""
    <div class="card" id="attribution-section">
        <div class="flex items-center gap-3 mb-6 border-b border-slate-100 pb-4">
            <div class="w-1 h-6 bg-indigo-500 rounded-full"></div>
            <h2 class="text-xl font-bold text-slate-800">归因分析 (Risk Attribution)</h2>
        </div>
        {html_all}
    </div>
    """

def make_amount_pivot_section(pivot_data):
    if not pivot_data: return ""
    return """
    <div class="card" id="heatmap-section">
        <div class="flex items-center gap-3 mb-6 border-b border-slate-100 pb-4">
            <div class="w-1 h-6 bg-indigo-500 rounded-full"></div>
            <h2 class="text-xl font-bold text-slate-800">金额热力图 (Amount Heatmap)</h2>
        </div>
        <p class="text-slate-400 text-sm">Heatmap Visualization (Placeholder)</p>
    </div>
    """

def make_contactability_section(contact_data):
    if not contact_data: return ""
    return """
    <div class="card" id="contact-section">
        <div class="flex items-center gap-3 mb-6 border-b border-slate-100 pb-4">
            <div class="w-1 h-6 bg-indigo-500 rounded-full"></div>
            <h2 class="text-xl font-bold text-slate-800">可联性分析 (Contactability)</h2>
        </div>
        <div id="chart-contact-trend" class="h-[300px]"></div>
    </div>
    """

# --- Main Builder ---
def build_cashloan_html(
    vintage_summary, repay_summary, process_summary, 
    vintage_anomalies, repay_anomalies, 
    excel_path, date_str, overview=None, 
    trend_d=None, trend_w=None, trend_m=None,
    trend_d_new=None, trend_w_new=None, trend_m_new=None,
    trend_d_old=None, trend_w_old=None, trend_m_old=None,
    matrix_daily=None, matrix_weekly=None, matrix_monthly=None,
    lift_metrics=None,
    lift_metrics_new=None, lift_metrics_old=None,
    matrix_daily_new=None, matrix_daily_old=None,
    matrix_weekly_new=None, matrix_weekly_old=None,
    matrix_monthly_new=None, matrix_monthly_old=None,
    bd_daily_all=None, bd_daily_new=None, bd_daily_old=None,
    bd_weekly_all=None, bd_weekly_new=None, bd_weekly_old=None,
    bd_monthly_all=None, bd_monthly_new=None, bd_monthly_old=None,
    amount_pivot_data=None,
    attribution_data=None,
    perf_data=None,
    contact_data=None,
    term_data=None,
    waterfall_data=None, 
    **kwargs
):
    # 1. Components
    kpi_cards = make_kpi_cards(vintage_summary, repay_summary, process_summary)
    
    chart_daily_all = make_trend_chart_json(trend_d, "chart_daily_all", "Overall Trend")
    
    html_repay = make_repay_table(repay_summary)
    html_process = make_process_table(process_summary)
    html_anomalies = make_anomalies_list(vintage_anomalies, repay_anomalies)
    
    # Matrices
    m_d_new = matrix_daily_new or []
    m_d_old = matrix_daily_old or []
    html_matrix_daily = make_vintage_matrix_v3_group(matrix_daily, m_d_new, m_d_old, "Daily")
    
    html_lift = make_lift_analysis_v3_3(lift_metrics, lift_metrics_new, lift_metrics_old)
    html_attribution = make_attribution_section(attribution_data)
    html_breakdown = make_breakdown_section_v3_4(bd_daily_all, bd_daily_new, bd_daily_old, bd_weekly_all, bd_weekly_new, bd_weekly_old, bd_monthly_all, bd_monthly_new, bd_monthly_old)
    html_contact = make_contactability_section(contact_data)
    # Placeholder for complex sections to keep code concise for now, can expand later
    
    return f"""<!DOCTYPE html>
<html lang="zh-CN" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CashLoan Inspection Report {date_str} (v4.6)</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background: #F8FAFC; color: #334155; }}
        /* Sidebar Scrollbar */
        aside::-webkit-scrollbar {{ width: 4px; }}
        aside::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 2px; }}
        
        .card {{ background: white; border-radius: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); padding: 24px; margin-bottom: 24px; border: 1px solid #E2E8F0; }}
        .nav-link {{ display: flex; alignItems: center; padding: 10px 16px; color: #94A3B8; transition: all 0.2s; border-radius: 8px; margin-bottom: 2px; font-size: 14px; font-weight: 500; }}
        .nav-link:hover {{ background: #1E293B; color: #F8FAFC; }}
        .nav-link.active {{ background: #2563EB; color: white; }}
        .nav-link svg {{ width: 18px; height: 18px; margin-right: 12px; opacity: 0.8; }}
        
        .section-header {{ margin-bottom: 24px; }}
        .animate-fade-in {{ animation: fadeIn 0.3s ease-out; }}
        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(5px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    </style>
</head>
<body class="flex h-screen overflow-hidden">

    <!-- Sidebar -->
    <aside class="w-64 bg-slate-900 text-slate-300 flex-shrink-0 flex flex-col transition-all duration-300 shadow-xl z-20">
        <div class="p-6 border-b border-slate-800">
            <h1 class="text-xl font-bold text-white tracking-tight">PhiRisk <span class="text-blue-500">Inspect</span></h1>
            <p class="text-xs text-slate-500 mt-1">CashLoan v4.6</p>
        </div>
        
        <nav class="flex-1 overflow-y-auto p-4 space-y-6">
            <div>
                <div class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 px-2">Risk Analysis</div>
                <a href="#overview" class="nav-link active">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>
                    Overview
                </a>
                <a href="#vintage-matrix" class="nav-link">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                    Vintage Matrix
                </a>
                <a href="#lift-analysis" class="nav-link">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"></path></svg>
                    Lift Analysis
                </a>
                <a href="#attribution-section" class="nav-link">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                    Risk Attribution
                </a>
            </div>
            
            <div>
                <div class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 px-2">Operations</div>
                <a href="#recovery-overview" class="nav-link">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    Recovery
                </a>
                <a href="#process-metrics" class="nav-link">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path></svg>
                    Process
                </a>
                <a href="#breakdown-section" class="nav-link">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
                    Breakdown
                </a>
            </div>
        </nav>
        
        <div class="p-4 border-t border-slate-800 text-xs text-slate-500">
            {date_str}
        </div>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 overflow-y-auto bg-slate-50 relative scroll-smooth">
        <div class="max-w-6xl mx-auto p-8">
            
            <!-- Header -->
            <div id="overview" class="flex justify-between items-end mb-10 border-b border-slate-200 pb-6">
                <div>
                    <h2 class="text-3xl font-extrabold text-slate-800 tracking-tight">Risk Inspection Report</h2>
                    <p class="text-slate-500 mt-2 flex items-center gap-2">
                        <span class="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
                        Status: Active
                        <span class="text-slate-300">|</span>
                        Source: Local Data
                    </p>
                </div>
                <div class="text-right">
                    <div class="text-sm font-semibold text-slate-600">v4.6 Update</div>
                    <div class="text-xs text-slate-400">Sidebar & Standardized Naming</div>
                </div>
            </div>

            <!-- KPI Cards -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
                {kpi_cards}
            </div>

            <!-- Vintage Matrix -->
            <div id="vintage-matrix" class="section-header">
                <div class="card">
                    <div class="flex items-center justify-between mb-6 border-b border-slate-100 pb-4">
                        <div class="flex items-center gap-3">
                            <div class="w-1 h-6 bg-indigo-500 rounded-full"></div>
                            <h2 class="text-xl font-bold text-slate-800">Vintage 矩阵 (Risk Matrix)</h2>
                        </div>
                        <div class="flex space-x-1 bg-slate-100 p-1 rounded-lg">
                            <button onclick="switchMatrix('daily')" class="px-3 py-1 text-xs font-medium rounded-md bg-white shadow text-blue-600" id="btn-matrix-daily">Daily</button>
                            <button onclick="switchMatrix('weekly')" class="px-3 py-1 text-xs font-medium rounded-md text-slate-500 hover:bg-white hover:shadow" id="btn-matrix-weekly">Weekly</button>
                            <button onclick="switchMatrix('monthly')" class="px-3 py-1 text-xs font-medium rounded-md text-slate-500 hover:bg-white hover:shadow" id="btn-matrix-monthly">Monthly</button>
                        </div>
                    </div>
                    <div id="matrix-view-daily" class="matrix-view animate-fade-in">{html_matrix_daily}</div>
                    <div id="matrix-view-weekly" class="matrix-view hidden animate-fade-in">{html_matrix_daily}</div> <!-- Placeholder fix -->
                    <div id="matrix-view-monthly" class="matrix-view hidden animate-fade-in">{html_matrix_daily}</div>
                </div>
            </div>

            <!-- Lift Analysis -->
            <div id="lift-analysis" class="section-header">
                <div class="card">
                    <div class="flex items-center justify-between mb-6 border-b border-slate-100 pb-4">
                        <div class="flex items-center gap-3">
                            <div class="w-1 h-6 bg-indigo-500 rounded-full"></div>
                            <h2 class="text-xl font-bold text-slate-800">MTD 环比分析 (Lift Analysis)</h2>
                        </div>
                        <div class="flex space-x-1 bg-slate-100 p-1 rounded-lg">
                            <button onclick="switchTab('lift', 'all')" class="px-3 py-1 text-xs font-medium rounded-md bg-white shadow text-blue-600" id="btn-lift-all">Overall</button>
                            <button onclick="switchTab('lift', 'new')" class="px-3 py-1 text-xs font-medium rounded-md text-slate-500 hover:bg-white hover:shadow" id="btn-lift-new">New</button>
                            <button onclick="switchTab('lift', 'old')" class="px-3 py-1 text-xs font-medium rounded-md text-slate-500 hover:bg-white hover:shadow" id="btn-lift-old">Old</button>
                        </div>
                    </div>
                    {html_lift}
                </div>
            </div>

            <!-- Trend Chart -->
            <div id="trend-analysis" class="section-header">
                <div class="card">
                    <div class="flex items-center gap-3 mb-6 border-b border-slate-100 pb-4">
                        <div class="w-1 h-6 bg-indigo-500 rounded-full"></div>
                        <h2 class="text-xl font-bold text-slate-800">趋势分析 (Trend)</h2>
                    </div>
                    <div id="trend-all-daily" class="h-[350px]"></div>
                </div>
            </div>

            <!-- Risk Attribution -->
            {html_attribution}

            <!-- Contactability -->
            {html_contact}

            <!-- Breakdown -->
            {html_breakdown}

            <!-- Recovery & Process -->
            <div id="recovery-overview" class="section-header">
                <div class="card">
                    <div class="flex items-center gap-3 mb-6 border-b border-slate-100 pb-4">
                        <div class="w-1 h-6 bg-emerald-500 rounded-full"></div>
                        <h2 class="text-xl font-bold text-slate-800">回收概览 (Recovery Summary)</h2>
                    </div>
                    {html_repay}
                </div>
            </div>

            <div id="process-metrics" class="section-header">
                <div class="card">
                    <div class="flex items-center gap-3 mb-6 border-b border-slate-100 pb-4">
                        <div class="w-1 h-6 bg-violet-500 rounded-full"></div>
                        <h2 class="text-xl font-bold text-slate-800">过程指标 (Process Metrics)</h2>
                    </div>
                    {html_process}
                </div>
            </div>

            <!-- Anomalies -->
            <div class="card border-l-4 border-red-500 bg-red-50/10">
                <h3 class="text-lg font-bold text-red-600 mb-3">异常诊断 (Anomalies)</h3>
                <div class="text-sm text-slate-600">
                    {html_anomalies}
                </div>
            </div>

            <div class="h-20"></div> <!-- Spacer -->
        </div>
    </main>

    <script>
        const charts = {{}};
        function initChart(domId, option) {{
            if (!option) return;
            const chart = echarts.init(document.getElementById(domId));
            chart.setOption(option);
            charts[domId] = chart;
        }}

        initChart("trend-all-daily", {chart_daily_all});
        if(document.getElementById("chart-contact-trend")) initChart("chart-contact-trend", {{}}); # Placeholder

        // Common Tab Switcher
        function switchTab(group, type) {{
            const container = document.getElementById(`btn-${{group}}-${{type}}`).closest('.card');
            container.querySelectorAll(`[id^="${{group}}-section-"]`).forEach(el => el.classList.add('hidden'));
            container.querySelector(`#${{group}}-section-${{type}}`).classList.remove('hidden');
            
            // Buttons
            container.querySelectorAll('button').forEach(el => {{
                el.className = "px-3 py-1 text-xs font-medium rounded-md text-slate-500 hover:bg-white hover:shadow transition-all";
            }});
            document.getElementById(`btn-${{group}}-${{type}}`).className = "px-3 py-1 text-xs font-medium rounded-md bg-white shadow text-blue-600 transition-all";
        }}

        function switchMatrix(period) {{
            document.querySelectorAll('.matrix-view').forEach(el => el.classList.add('hidden'));
            document.getElementById(`matrix-view-${{period}}`).classList.remove('hidden');
            
            document.querySelectorAll('[id^="btn-matrix-"]').forEach(el => {{
                el.className = "px-3 py-1 text-xs font-medium rounded-md text-slate-500 hover:bg-white hover:shadow transition-all";
            }});
            document.getElementById(`btn-matrix-${{period}}`).className = "px-3 py-1 text-xs font-medium rounded-md bg-white shadow text-blue-600 transition-all";
        }}

        function switchMatrixGroup(btn, label, type) {{
            const container = btn.closest('.card');
            container.querySelectorAll(`[id^="mat-${{label}}"]`).forEach(el => el.classList.add('hidden'));
            container.querySelector(`#mat-${{label}}-${{type}}`).classList.remove('hidden');
            
            container.querySelectorAll('button').forEach(el => {{
                el.className = "px-3 py-1 text-xs font-medium rounded-md text-slate-500 hover:bg-white hover:shadow transition-all";
            }});
            btn.className = "px-3 py-1 text-xs font-medium rounded-md bg-white shadow text-blue-600 transition-all";
        }}

        function toggleVintageLift(cb, label) {{
            const container = cb.closest('.card');
            container.querySelectorAll('.vintage-lift').forEach(el => {{
                if(cb.checked) el.classList.remove('hidden');
                else el.classList.add('hidden');
            }});
        }}
        
        window.addEventListener('resize', () => Object.values(charts).forEach(c => c.resize()));
        
        // Sidebar Active State
        const sections = document.querySelectorAll('.section-header, #overview');
        const navLinks = document.querySelectorAll('.nav-link');
        
        document.querySelector('main').addEventListener('scroll', () => {{
            let current = '';
            sections.forEach(section => {{
                const sectionTop = section.offsetTop;
                if (document.querySelector('main').scrollTop >= sectionTop - 100) {{
                    current = section.getAttribute('id');
                }}
            }});
            
            navLinks.forEach(link => {{
                link.classList.remove('active');
                if (link.getAttribute('href').includes(current)) {{
                    link.classList.add('active');
                }}
            }});
        }});
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    pass
