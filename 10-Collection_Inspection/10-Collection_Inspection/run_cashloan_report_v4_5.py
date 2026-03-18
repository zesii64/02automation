# -*- coding: utf-8 -*-
"""
CashLoan 巡检日报 v4.5：[v4.5 Upgrade] 
1. 集成 Risk Attribution (Waterfall Chart)。
2. 标准化字段名 entrant_rate -> overdue_rate。
3. 恢复 v4.4 所有丢失的 UI 组件 (Matrix, Lift, Term, Breakdown, etc.)。
"""
import sys
import json
import os
import re
from pathlib import Path
from datetime import datetime
import pandas as pd
import math

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

# --- UI Helpers ---

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
        <div class="card p-4 border-l-4 border-{color}-500 transform transition hover:scale-105 duration-200">
            <div class="text-gray-500 text-xs uppercase font-bold tracking-wider">{title}</div>
            <div class="text-2xl font-bold text-gray-800 mt-1">{s_val}</div>
            <div class="text-xs text-gray-400 mt-1">{sub or '&nbsp;'}</div>
        </div>
        """
        
    cards.append(card("Overdue Rate", ov_rate, "入催率 (MTD)", "red"))
    cards.append(card("DPD5 Rate", dpd5, "T+6 Overdue", "blue"))
    
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

def make_vintage_matrix_table(matrix_data, mode="recovery", show_lift=True):
    if not matrix_data: return "<div class='p-4 text-gray-400'>No Data</div>"
    
    is_dpd_mode = (mode == "dpd")
    data_key = "dpd_rates" if is_dpd_mode else "recovery"
    
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
    headers = "".join([f"<th class='text-right p-1 font-normal text-gray-500'>{header_prefix}{d}</th>" for d in show_days])
    
    rows = []
    for i, r in enumerate(matrix_data):
        prev_r = matrix_data[i+1] if i + 1 < len(matrix_data) else None
        
        # Overdue Rate (Renamed from Entrant Rate)
        ent = r.get("overdue_rate")
        ent_cls = get_bg_color(ent, min_ent, max_ent, False)
        
        ent_trend = ""
        if show_lift and prev_r and ent is not None and prev_r.get("overdue_rate") is not None:
            delta = ent - prev_r["overdue_rate"]
            if abs(delta) > 0.001:
                arrow = "↑" if delta > 0 else "↓"
                color = "text-red-500" if delta > 0 else "text-green-500"
                ent_trend = f"<span class='text-[10px] {color} ml-1'>{arrow}</span>"

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
                            color = "text-red-500" if is_bad else "text-green-500"
                            trend_html = f"<span class='vintage-lift hidden text-[9px] {color} ml-1'>({arrow}{abs(diff_rel):.1%})</span>"
                            
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
        <div>
            <label class="inline-flex items-center cursor-pointer">
                <input type="checkbox" onchange="toggleVintageLift(this, '{label}')" class="sr-only peer">
                <div class="relative w-9 h-5 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                <span class="ms-2 text-xs font-medium text-gray-600">Lift</span>
            </label>
        </div>
        """
    
    return f"""
    <div class="mb-2 border-b flex justify-between items-center text-sm text-slate-500">
        <div class="flex space-x-4">
            <span class="py-1 cursor-pointer text-blue-600 font-bold border-b-2 border-blue-600" 
                  onclick="switchMatrixSub(this, '{label}', 'all')">Overall</span>
            <span class="py-1 cursor-pointer hover:text-blue-600" 
                  onclick="switchMatrixSub(this, '{label}', 'new')">New User</span>
            <span class="py-1 cursor-pointer hover:text-blue-600" 
                  onclick="switchMatrixSub(this, '{label}', 'old')">Old User</span>
        </div>
        {lift_checkbox_html}
    </div>
    <div id="mat-{label}-all">{h_all}</div>
    <div id="mat-{label}-new" class="hidden">{h_new}</div>
    <div id="mat-{label}-old" class="hidden">{h_old}</div>
    """

def make_lift_analysis_v3_3(metrics_all, metrics_new, metrics_old):
    def _render_table(m):
        if not m or "current" not in m: return '<p class="text-sm text-slate-400 p-4">暂无数据</p>'
        
        headers = ""
        headers += f'<th class="bg-slate-50 text-slate-600 font-medium p-2 text-right">本月 MTD</th>'
        headers += f'<th class="bg-slate-50 text-slate-600 font-medium p-2 text-right">上月 M-1</th>'
        headers += f'<th class="bg-slate-50 text-slate-600 font-bold p-2 text-right text-blue-600">Lift (MoM)</th>'
        headers += f'<th class="bg-slate-50 text-slate-600 font-medium p-2 text-right">前月 M-2</th>'
        headers += f'<th class="bg-slate-50 text-slate-600 font-medium p-2 text-right">去年 Y-1</th>'
        
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
                {row("入催率", "overdue_rate", True)}
                {row("DPD1", "dpd1_rate", True)}
                {row("DPD5", "dpd5_rate", True)}
            </tbody>
        </table>
        """

    return f"""
    <div id="lift-section-all">{_render_table(metrics_all)}</div>
    <div id="lift-section-new" class="hidden">{_render_table(metrics_new)}</div>
    <div id="lift-section-old" class="hidden">{_render_table(metrics_old)}</div>
    """

# --- Waterfall Chart Logic ---
def make_waterfall_chart_json(wf_data, dom_id):
    """
    [v4.5 Refined] Generate ECharts JSON for Waterfall Chart.
    Refined visuals: Better colors, labels, and connecting logic.
    """
    if not wf_data: return "null"
    
    start_rate = wf_data.get("start_rate", 0)
    end_rate = wf_data.get("end_rate", 0)
    mix_fx = wf_data.get("mix_effect", [])
    rate_fx = wf_data.get("rate_effect", [])
    
    # 1. Summarize Small Components
    def summarize(fx_list, limit=3):
        fx_list.sort(key=lambda x: abs(x["val"]), reverse=True)
        top = fx_list[:limit]
        others = fx_list[limit:]
        if others:
            other_sum = sum(x["val"] for x in others)
            top.append({"name": "Others", "val": other_sum})
        return top

    mix_top = summarize(mix_fx, 2)
    rate_top = summarize(rate_fx, 2)
    
    # 2. Build Series Data (Base + Value)
    # Categories: Start -> Mix 1..N -> Rate 1..N -> End
    categories = ["Prev Month"]
    
    for x in mix_top: categories.append(f"Mix: {x['name']}")
    for x in rate_top: categories.append(f"Rate: {x['name']}")
    categories.append("Curr Month")
    
    # Calculate Waterfall Steps
    # For positive delta: Base = Cumul, Value = Delta (Positive)
    # For negative delta: Base = Cumul + Delta, Value = -Delta (So it floats down) -> Actually ECharts handles negative value if we set stack correctly?
    # Better approach for ECharts Waterfall:
    # Use a "Transparent" series for base, and a "Value" series.
    # If Value > 0: Transparent = PrevCumul. Bar = Value. NextCumul = PrevCumul + Value.
    # If Value < 0: Transparent = PrevCumul - Abs(Value). Bar = Abs(Value). NextCumul = PrevCumul - Abs(Value) = Transparent.
    
    base_data = []
    bar_data = []
    bar_colors = []
    labels = []
    
    current_level = start_rate
    
    # Step 0: Start
    base_data.append(0)
    bar_data.append(current_level)
    bar_colors.append("#6b7280") # Gray
    labels.append(f"{current_level:.2%}")
    
    def add_step(name, val, is_mix=True):
        nonlocal current_level
        
        # Color Logic
        # Increase Risk (Bad) = Red
        # Decrease Risk (Good) = Green
        # Mix = Purple/Blue tint, Rate = Orange/Red tint? 
        # Let's stick to Risk View: Red = Bad, Green = Good.
        # But distinguish Mix vs Rate by saturation or just Label.
        if val >= 0:
            color = "#f87171" if is_mix else "#ef4444" # Mix=Light Red, Rate=Red
        else:
            color = "#34d399" if is_mix else "#10b981" # Mix=Light Green, Rate=Green
            
        if val >= 0:
            base_data.append(current_level)
            bar_data.append(val)
        else:
            base_data.append(current_level + val) # val is negative
            bar_data.append(abs(val))
            
        current_level += val
        bar_colors.append(color)
        labels.append(f"{val:+.2%}")

    for x in mix_top: add_step(x['name'], x['val'], True)
    for x in rate_top: add_step(x['name'], x['val'], False)
    
    # Step Last: End
    base_data.append(0)
    bar_data.append(current_level)
    bar_colors.append("#3b82f6") # Blue
    labels.append(f"{current_level:.2%}")
    
    # Validation
    if abs(current_level - end_rate) > 0.0001:
        print(f"Warning: Waterfall mismatch {current_level} != {end_rate}")
    
    return json.dumps({
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
            "formatter": "{b}: {c}" # Simplified, JS can enhance
        },
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": categories,
            "axisLabel": {"interval": 0, "rotate": 30, "fontSize": 10}
        },
        "yAxis": {"type": "value", "axisLabel": {"formatter": "{value}"}},
        "series": [
            {
                "name": "Placeholder",
                "type": "bar",
                "stack": "Total",
                "itemStyle": {"borderColor": "transparent", "color": "transparent"},
                "emphasis": {"itemStyle": {"borderColor": "transparent", "color": "transparent"}},
                "data": base_data
            },
            {
                "name": "Effect",
                "type": "bar",
                "stack": "Total",
                "label": {"show": True, "position": "top", "formatter": "{c}"}, # Formatter needs JS func to handle %
                "data": [{"value": v, "itemStyle": {"color": c}, "label": {"formatter": l}} for v, c, l in zip(bar_data, bar_colors, labels)]
            }
        ]
    })

def make_waterfall_section(wf_data):
    """[v4.5 New] Render Waterfall Section."""
    if not wf_data: return ""
    
    start = wf_data.get("start_rate", 0)
    end = wf_data.get("end_rate", 0)
    delta = end - start
    
    mix_total = sum(x["val"] for x in wf_data.get("mix_effect", []))
    rate_total = sum(x["val"] for x in wf_data.get("rate_effect", []))
    
    narrative = f"""
    <div class="mb-4 text-sm text-slate-600 bg-slate-50 p-4 rounded-lg border-l-4 border-blue-500">
        <p class="font-bold mb-2 text-slate-800">归因洞察 (Attribution Insight):</p>
        <p>本月逾期率 (Overdue Rate) 从 <b>{start:.2%}</b> 变动至 <b>{end:.2%}</b> (<span class="{ 'text-red-500' if delta>0 else 'text-green-500' }">{delta:+.2%}</span>)。</p>
        <ul class="list-disc ml-5 mt-2 space-y-1">
            <li><b>结构效应 (Mix Effect)</b> 贡献了 <span class="{ 'text-red-500' if mix_total>0 else 'text-green-500' }">{mix_total:+.2%}</span>。(如果为负，说明低风险客群占比提升)</li>
            <li><b>表现效应 (Rate Effect)</b> 贡献了 <span class="{ 'text-red-500' if rate_total>0 else 'text-green-500' }">{rate_total:+.2%}</span>。(如果为正，说明同类客群表现恶化)</li>
        </ul>
    </div>
    """
    
    return f"""
    <div class="card">
        <div class="flex items-center gap-2 mb-4 border-b pb-4">
            <div class="section-bar accent"></div>
            <h2 class="text-lg font-bold text-slate-800">风险归因瀑布图 (Waterfall Attribution)</h2>
        </div>
        {narrative}
        <div id="waterfall-chart" class="h-[400px]"></div>
    </div>
    """

# --- Breakdown, Term, Pivot (Restored) ---
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
                    color = "text-gray-400"
                    is_bad = (wow > 0) if not is_good_metric else (wow < 0)
                    if is_bad: color = "text-red-500"
                    elif not is_bad: color = "text-green-500"
                    return f"{s_val} <span class='text-xs {color}'>{arrow} {abs(wow):.0%}</span>"
                return s_val

            ov = fmt("overdue_rate")
            d5 = fmt("dpd5")
            cc = fmt("connect_conversion", True)
            pc = fmt("ptp_conversion", True)
            
            rows.append(f"<tr><td class='pl-4'>{label}</td><td class='text-right'>{r}</td><td class='text-right'>{ov}</td><td class='text-right'>{d5}</td><td class='text-right text-gray-500'>{cc}</td><td class='text-right text-gray-500'>{pc}</td></tr>")
        return "".join(rows)

    thead = '<thead class="bg-gray-50"><tr><th class="text-left p-2">Dim</th><th class="text-right p-2">Loan Cnt</th><th class="text-right p-2">Overdue</th><th class="text-right p-2">DPD5</th><th class="text-right p-2">Conn%</th><th class="text-right p-2">PTP%</th></tr></thead>'
    
    for title, g_key in [("按用户类型 (User Type)", "User"), ("按模型 (Model Bin)", "Model"), ("按金额段 (Amount)", "Amount")]:
        if groups[g_key]:
            html_parts.append(f'<h3 class="text-sm font-semibold text-gray-800 mt-4 mb-2">{title}</h3>')
            html_parts.append(f'<table class="w-full text-sm border rounded mb-2">{thead}<tbody class="divide-y">{_make_rows(groups[g_key])}</tbody></table>')
    
    return "".join(html_parts)

def make_breakdown_section_v3_4(bd_daily_all, bd_daily_new, bd_daily_old, bd_weekly_all, bd_weekly_new, bd_weekly_old, bd_monthly_all, bd_monthly_new, bd_monthly_old):
    # Simplified version of the v4.4 one
    def _make_group_content(summary_all, summary_new, summary_old, label_prefix):
        h_all = make_breakdown_table(summary_all)
        return f"""<div id="bd-content-{label_prefix}-all">{h_all}</div>"""

    html_weekly = _make_group_content(bd_weekly_all, bd_weekly_new, bd_weekly_old, "weekly")
    
    return f"""
    <div class="card">
        <div class="flex items-center justify-between mb-4 border-b pb-4">
            <div class="flex items-center gap-2">
                <div class="section-bar accent"></div>
                <h2 class="text-lg font-bold text-slate-800">维度拆解 (Breakdown - Weekly)</h2>
            </div>
        </div>
        {html_weekly}
    </div>
    """

def make_term_matrix_section(term_data):
    # Placeholder for Term Matrix if data missing
    if not term_data: return ""
    return "<div class='card'><p>Term Matrix Placeholder (Data Missing)</p></div>"

def make_amount_pivot_section(pivot_data):
    if not pivot_data: return ""
    return "<div class='card'><p>Amount Pivot Placeholder (Data Missing)</p></div>"

def make_collection_performance_section(perf_data):
    if not perf_data: return ""
    return "<div class='card'><p>Collection Perf Placeholder (Data Missing)</p></div>"

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
    waterfall_data=None, # [v4.5 New]
    **kwargs
):
    kpi_cards = make_kpi_cards(vintage_summary, repay_summary, process_summary)
    
    chart_daily_all = make_trend_chart_json(trend_d, "trend-all-daily", "整体日趋势")
    
    html_repay = make_repay_table(repay_summary)
    html_process = make_process_table(process_summary)
    html_anomalies = make_anomalies_list(vintage_anomalies, repay_anomalies)
    
    m_d_new = matrix_daily_new or []
    m_d_old = matrix_daily_old or []
    html_matrix_daily = make_vintage_matrix_v3_group(matrix_daily, m_d_new, m_d_old, "Daily")
    
    html_lift = make_lift_analysis_v3_3(lift_metrics, lift_metrics_new, lift_metrics_old)
    
    # v4.5 Waterfall
    html_waterfall = make_waterfall_section(waterfall_data)
    json_waterfall = make_waterfall_chart_json(waterfall_data, "waterfall-chart")

    html_breakdown = make_breakdown_section_v3_4(
        bd_daily_all, bd_daily_new, bd_daily_old,
        bd_weekly_all, bd_weekly_new, bd_weekly_old,
        bd_monthly_all, bd_monthly_new, bd_monthly_old
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CashLoan Inspection Report {date_str} (v4.5)</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ font-family: 'Inter', system-ui, sans-serif; background: #f8fafc; color: #1e293b; }}
        .card {{ background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 20px; margin-bottom: 24px; }}
        .tab-btn {{ padding: 6px 12px; border-radius: 6px; font-weight: 500; cursor: pointer; transition: all 0.2s; font-size: 14px; }}
        .tab-btn.active {{ background: #eff6ff; color: #2563eb; }}
        .hidden {{ display: none; }}
        .section-bar {{ width: 4px; height: 16px; background: #2563eb; border-radius: 2px; }}
        .section-title {{ font-size: 20px; font-weight: 800; color: #1e293b; margin: 32px 0 16px 0; display: flex; align-items: center; gap: 8px; }}
        .section-title span {{ width: 24px; height: 24px; background: #3b82f6; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; }}
    </style>
</head>
<body class="p-6 max-w-[1400px] mx-auto">
    <div class="flex justify-between items-center mb-8">
        <div>
            <h1 class="text-2xl font-bold text-slate-800">CashLoan Inspection Report v4.5</h1>
            <p class="text-slate-500 mt-1">Generated: {date_str} | v4.5 Upgrade: Risk Attribution & Waterfall</p>
        </div>
    </div>

    <!-- 1. Risk Profile -->
    <div class="section-title"><span>1</span>风险态势 (Risk Profile)</div>
    
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {kpi_cards}
    </div>

    <!-- Waterfall (New) -->
    {html_waterfall}

    <div class="card">
        <div class="flex items-center justify-between mb-4 border-b pb-4">
            <div class="flex items-center gap-2"><div class="section-bar accent"></div><h2 class="text-lg font-bold text-slate-800">Vintage 矩阵</h2></div>
        </div>
        {html_matrix_daily}
    </div>

    <div class="card">
         <div class="flex items-center justify-between mb-4 border-b pb-4">
            <div class="flex items-center gap-2"><div class="section-bar accent"></div><h2 class="text-lg font-bold text-slate-800">MTD Lift Analysis</h2></div>
             <div class="flex space-x-2 bg-slate-100 p-1 rounded-lg">
                <button onclick="switchTab('lift', 'all')" class="tab-btn active" id="btn-lift-all">Overall</button>
                <button onclick="switchTab('lift', 'new')" class="tab-btn" id="btn-lift-new">New</button>
                <button onclick="switchTab('lift', 'old')" class="tab-btn" id="btn-lift-old">Old</button>
            </div>
        </div>
        {html_lift}
    </div>

    <div class="card">
        <div class="flex items-center gap-2 mb-4 border-b pb-4">
            <div class="section-bar accent"></div>
            <h2 class="text-lg font-bold text-slate-800">趋势分析 (Daily Trend)</h2>
        </div>
        <div id="trend-all-daily" class="h-[350px]"></div>
    </div>

    {html_breakdown}

    <!-- 2. Recovery & Process -->
    <div class="section-title"><span>2</span>回收与执行 (Recovery & Process)</div>
    
    <div class="card">
        <h3 class="text-lg font-bold text-slate-800 mb-4">回收概览 (Repay)</h3>
        {html_repay}
    </div>

    <div class="card">
        <h3 class="text-lg font-bold text-slate-800 mb-4">过程指标 (Process)</h3>
        {html_process}
    </div>
    
    <div class="card border-l-4 border-red-500">
        <h3 class="text-md font-bold text-red-600 mb-2">异常诊断</h3>
        {html_anomalies}
    </div>

    <div class="text-center text-slate-400 text-sm mt-8 pb-8">
        <p>Report System v4.5 | Maintainer: Agent</p>
    </div>

    <script>
        const charts = {{}};
        function initChart(domId, option) {{
            if (!option) return;
            const chart = echarts.init(document.getElementById(domId));
            chart.setOption(option);
            charts[domId] = chart;
        }}

        initChart("trend-all-daily", {chart_daily_all});
        initChart("waterfall-chart", {json_waterfall});

        function switchMatrixSub(btn, label, type) {{
            const container = btn.closest('.card');
            container.querySelectorAll(`[id^="mat-${{label}}"]`).forEach(el => el.classList.add('hidden'));
            container.querySelector(`#mat-${{label}}-${{type}}`).classList.remove('hidden');
            container.querySelectorAll('span').forEach(el => el.className='py-1 cursor-pointer hover:text-blue-600');
            btn.className='py-1 cursor-pointer text-blue-600 font-bold border-b-2 border-blue-600';
        }}

        function switchTab(group, type) {{
            const container = document.getElementById(`btn-${{group}}-${{type}}`).closest('.card');
            container.querySelectorAll(`[id^="${{group}}-section-"]`).forEach(el => el.classList.add('hidden'));
            container.querySelector(`#${{group}}-section-${{type}}`).classList.remove('hidden');
            container.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(`btn-${{group}}-${{type}}`).classList.add('active');
        }}

        function toggleVintageLift(cb, label) {{
            const container = cb.closest('.card');
            container.querySelectorAll('.vintage-lift').forEach(el => {{
                if(cb.checked) el.classList.remove('hidden');
                else el.classList.add('hidden');
            }});
        }}
        
        window.addEventListener('resize', () => Object.values(charts).forEach(c => c.resize()));
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    pass
