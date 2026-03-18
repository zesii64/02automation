# -*- coding: utf-8 -*-
"""
CashLoan 巡检日报 — 贷后巡检报告生成脚本。

Changelog:
- v4.22: Part 3 运营效能重构 — 移除非核心板块(Repay Summary/Collection Perf/
         Process Summary/Anomalies), 新增目标追踪看板、经办排行榜、效率分析、
         行动项清单; 可联性分析迁移至 Part 2; 新增"效率与行动"子标签页。
- v4.21+: CDN 内联 — ECharts/TailwindCSS 内联到 HTML, 支持离线传输。
- v4.21: 运营归因 Treemap — 3级钻取(模块→组→经办), 目标缺口/环比双视角。
- v4.19: 归因中心 Shift-Share — 时间窗口+客群+自动摘要+动态瀑布图。
- v4.16: 自然月回收序时总览层 Small Multiples。
- v4.14: 顶部导航栏。
- v4.13: 自然月回收序时 4层下钻。
- v4.10: Natural Month Progress + Due Month Recovery 目标达成。
- v4.9:  期限监控矩阵 (Term × MOB)。
- v4.0:  可联性分析、大重构 (Risk → Repay → Process)。
- v3.7:  催收团队效能 (Bucket → Group → Agent)。
- v3.5:  金额段热力图。
- v3.4:  多维拆解 (Daily/Weekly/Monthly × All/New/Old)。
- v3.3:  Lift Analysis 列重排, DPD1 定义。
- v3.2:  拆分 Matrix 为 Recovery & DPD, 恢复 Breakdown。
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

# --- [v4.21+] CDN Inline Cache ---
# Download & cache CDN files locally so that generated HTML is fully self-contained
# and can be opened offline on any machine without network access.
_CDN_CACHE_DIR = SCRIPT_DIR / "reports" / ".cdn_cache"

_CDN_URLS = {
    "echarts": "https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js",
    "tailwindcss": "https://cdn.tailwindcss.com",
}

def _get_cached_cdn(name: str) -> str:
    """Download CDN resource once, cache locally, return content as string."""
    _CDN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _CDN_CACHE_DIR / f"{name}.js"
    if cache_file.exists() and cache_file.stat().st_size > 0:
        return cache_file.read_text(encoding="utf-8", errors="ignore")
    url = _CDN_URLS[name]
    print(f"[CDN Cache] Downloading {name} from {url} ...")
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    cache_file.write_bytes(data)
    print(f"[CDN Cache] Saved {name} ({len(data):,} bytes)")
    return data.decode("utf-8", errors="ignore")

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
            else:
                # [v4.16] Stable: delta ≤ 0.1%
                ent_trend = f"<span class='lift-indicator text-[10px] text-gray-400 ml-1'>→</span>"

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
                        else:
                            # [v4.16] Stable
                            trend_html = f"<span class='lift-indicator text-[9px] text-gray-400 ml-0.5'>→</span>"
                            
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
                if wow is not None and isinstance(wow, (int, float)):
                    if abs(wow) > 0.001:
                        arrow = "↑" if wow > 0 else "↓"
                        color = "text-gray-400"
                        is_bad = (wow > 0) if not is_good_metric else (wow < 0)
                        if is_bad: color = "text-red-500"
                        elif not is_bad: color = "text-green-500"
                        return f"{s_val} <span class='text-xs {color}'>{arrow} {abs(wow):.0%}</span>"
                    else:
                        # [v4.16] Stable
                        return f"{s_val} <span class='text-xs text-gray-400'>→</span>"
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
            if change is not None:
                if abs(change) > 0.001: # Show if > 0.1% change
                    arrow = "↑" if change > 0 else "↓"
                    color = "text-red-500" if change > 0 else "text-green-500" # Risk metric: Increase is bad (Red)
                    # Assuming all metrics here (Entrant, DPD) are Risk metrics where Higher = Bad.
                    return f"{s_val} <span class='text-[10px] {color}'>{arrow}{abs(change):.1%}</span>"
                else:
                    # [v4.16] Stable
                    return f"{s_val} <span class='text-[10px] text-gray-400'>→</span>"
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
    
    if abs(delta) > 0.001:
        color = "text-red-600" if delta > 0 else "text-green-600"
        arrow = "↑" if delta > 0 else "↓"
    else:
        # [v4.16] Stable
        color = "text-gray-500"
        arrow = "→"
    
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
                if abs(rate_delta) > 0.001:
                    d_color = "text-red-500" if rate_delta > 0 else "text-green-500"
                    d_arrow = "↑" if rate_delta > 0 else "↓"
                    d_html = f"<span class='{d_color} text-xs'>{d_arrow} {abs(rate_delta):.2%}</span>"
                else:
                    # [v4.16] Stable
                    d_html = f"<span class='text-gray-400 text-xs'>→ stable</span>"
            
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
        
        if abs(delta) > 0.001:
            d_color = "text-green-600" if delta > 0 else "text-red-500" # High Conn is good
            d_arrow = "↑" if delta > 0 else "↓"
            d_html = f"<span class='{d_color} text-sm ml-1'>{d_arrow}{abs(delta):.1%}</span>"
        else:
            # [v4.16] Stable
            d_html = f"<span class='text-gray-400 text-sm ml-1'>→</span>"
        
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

def make_smart_diagnostics_section(data):
    """
    [v4.23 NEW] 智能诊断 — 诊断摘要卡片 + 多月趋势热力表 + Uplift 条形图
    """
    import json
    if not data:
        return ''

    findings = data.get('findings', [])
    group_trends = data.get('group_trends', {})
    uplift_table = data.get('uplift_table', [])
    summary = data.get('summary', {})

    findings_json = json.dumps(findings, ensure_ascii=True, default=str)
    uplift_json = json.dumps(uplift_table, ensure_ascii=True, default=str)
    gt_json = json.dumps(group_trends, ensure_ascii=True, default=str)
    summary_json = json.dumps(summary, ensure_ascii=True, default=str)

    months = summary.get('months', [])
    month_headers = ''
    for m in months:
        ms = str(m)
        label = f"{ms[2:4]}.{ms[4:]}"
        month_headers += f'<th style="padding:8px 10px;font-size:12px;white-space:nowrap;">{label}月达成</th>'

    html = f'''
    <div class="card" style="margin-top:20px;padding:0;overflow:hidden;">
    <!-- ====== SMART DIAGNOSTICS [v4.23] ====== -->
    <style>
        .sd-header {{
            background: linear-gradient(135deg, #dc2626 0%, #f97316 50%, #eab308 100%);
            padding: 20px 28px 16px;
            color: white;
        }}
        .sd-header h3 {{ margin:0 0 10px; font-size:17px; font-weight:700; }}
        .sd-summary-row {{
            display: flex; gap: 16px; flex-wrap: wrap;
        }}
        .sd-summary-chip {{
            background: rgba(255,255,255,0.2);
            backdrop-filter: blur(8px);
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 600;
        }}
        .sd-findings {{
            padding: 20px 28px; border-bottom: 1px solid #e2e8f0;
        }}
        .sd-finding-card {{
            border-radius: 10px;
            padding: 14px 18px;
            margin-bottom: 10px;
            border-left: 4px solid;
            font-size: 13px;
            line-height: 1.7;
            transition: all 0.2s;
        }}
        .sd-finding-card:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .sd-sev-critical {{ border-color: #dc2626; background: #fef2f2; }}
        .sd-sev-high {{ border-color: #f97316; background: #fff7ed; }}
        .sd-sev-medium {{ border-color: #eab308; background: #fefce8; }}
        .sd-sev-low {{ border-color: #22c55e; background: #f0fdf4; }}
        .sd-sev-badge {{
            display: inline-block; padding: 2px 8px; border-radius: 10px;
            font-size: 11px; font-weight: 700; color: white; margin-right: 6px;
        }}
        .sd-table-wrap {{
            padding: 20px 28px; border-bottom: 1px solid #e2e8f0;
        }}
        .sd-table {{
            width: 100%; border-collapse: collapse; font-size: 12px;
        }}
        .sd-table th {{
            background: #f8fafc; color: #475569; font-weight: 600;
            border-bottom: 2px solid #e2e8f0; text-align: center;
        }}
        .sd-table td {{
            padding: 8px 10px; border-bottom: 1px solid #f1f5f9;
            text-align: center; white-space: nowrap;
        }}
        .sd-table tr:hover {{ background: #f8fafc; }}
        .sd-ach-cell {{
            font-weight: 600; border-radius: 4px; padding: 3px 6px;
        }}
        .sd-uplift-wrap {{
            padding: 20px 28px;
        }}
        .sd-filter-row {{
            display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; align-items: center;
        }}
        .sd-filter-btn {{
            padding: 5px 14px; border-radius: 16px; border: 1.5px solid #e2e8f0;
            background: white; color: #475569; font-size: 12px; font-weight: 600;
            cursor: pointer; transition: all 0.2s;
        }}
        .sd-filter-btn.active {{
            background: #8b5cf6; color: white; border-color: #8b5cf6;
        }}
    </style>

    <!-- Header -->
    <div class="sd-header">
        <h3>智能诊断 (Smart Diagnostics)</h3>
        <div class="sd-summary-row" id="sd-summary-row"></div>
    </div>

    <!-- Findings Cards -->
    <div class="sd-findings">
        <div style="font-size:14px;font-weight:700;color:#1e293b;margin-bottom:12px;">
            关键发现 (Key Findings)
        </div>
        <div id="sd-findings-list"></div>
    </div>

    <!-- Trend Heatmap Table -->
    <div class="sd-table-wrap">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
            <div style="font-size:14px;font-weight:700;color:#1e293b;">
                多月趋势追踪 (Multi-Month Trend)
            </div>
            <div class="sd-filter-row" id="sd-filter-row"></div>
        </div>
        <div style="overflow-x:auto;">
            <table class="sd-table" id="sd-trend-table">
                <thead>
                    <tr>
                        <th style="padding:8px 10px;text-align:left;">模块</th>
                        <th style="padding:8px 10px;text-align:left;">组名</th>
                        {month_headers}
                        <th style="padding:8px 10px;">趋势</th>
                        <th style="padding:8px 10px;">覆盖率趋势</th>
                        <th style="padding:8px 10px;">诊断</th>
                        <th style="padding:8px 10px;">潜在提升</th>
                    </tr>
                </thead>
                <tbody id="sd-trend-tbody"></tbody>
            </table>
        </div>
    </div>

    <!-- Uplift Bar Chart -->
    <div class="sd-uplift-wrap">
        <div style="font-size:14px;font-weight:700;color:#1e293b;margin-bottom:12px;">
            修复优先级 (Uplift Priority) — 如达到模块均值可带来的提升
        </div>
        <div id="sd-uplift-chart" style="width:100%;height:350px;"></div>
    </div>

    <script>
    (function() {{
        try {{
        var sdFindings = {findings_json};
        var sdUplift = {uplift_json};
        var sdGroupTrends = {gt_json};
        var sdSummary = {summary_json};
        var sdMonths = sdSummary.months || [];

        // ── Severity config ──
        var sevConfig = {{
            'critical': {{ label: '严重', color: '#dc2626', bg: '#fef2f2', badge: '#dc2626' }},
            'high':     {{ label: '高', color: '#f97316', bg: '#fff7ed', badge: '#f97316' }},
            'medium':   {{ label: '中', color: '#eab308', bg: '#fefce8', badge: '#ca8a04' }},
            'low':      {{ label: '改善', color: '#22c55e', bg: '#f0fdf4', badge: '#16a34a' }},
            'info':     {{ label: '正常', color: '#64748b', bg: '#f8fafc', badge: '#94a3b8' }}
        }};

        // ── Summary chips ──
        (function renderSummary() {{
            var el = document.getElementById('sd-summary-row');
            if (!el) return;
            var cc = sdSummary.critical_count || 0;
            var hc = sdSummary.high_count || 0;
            var tp = sdSummary.potential_uplift_pp || 0;
            var tg = sdSummary.total_groups || 0;
            el.innerHTML =
                '<div class="sd-summary-chip">' + tg + ' \\u4e2a\\u7ec4\\u522b\\u8ffd\\u8e2a\\u4e2d</div>' +
                '<div class="sd-summary-chip" style="background:rgba(239,68,68,0.3);">' + cc + ' \\u4e2a\\u4e25\\u91cd\\u95ee\\u9898</div>' +
                '<div class="sd-summary-chip" style="background:rgba(249,115,22,0.3);">' + hc + ' \\u4e2a\\u9ad8\\u98ce\\u9669</div>' +
                '<div class="sd-summary-chip" style="background:rgba(34,197,94,0.3);">\\u6f5c\\u5728\\u63d0\\u5347 +' + tp.toFixed(2) + 'pp</div>';
        }})();

        // ── Findings cards ──
        (function renderFindings() {{
            var el = document.getElementById('sd-findings-list');
            if (!el) return;
            var html = '';
            var showCount = Math.min(sdFindings.length, 6);
            for (var i = 0; i < showCount; i++) {{
                var f = sdFindings[i];
                var sc = sevConfig[f.severity] || sevConfig['info'];
                var sevClass = 'sd-sev-' + f.severity;
                var upliftTag = f.uplift_pp > 0.01 ?
                    ' <span style="background:#dbeafe;color:#2563eb;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;">\\u2191 +' + f.uplift_pp.toFixed(2) + 'pp</span>' : '';
                html += '<div class="sd-finding-card ' + sevClass + '">' +
                    '<span class="sd-sev-badge" style="background:' + sc.badge + ';">' + sc.label + '</span>' +
                    '<b>' + f.bucket + '-' + f.group + '</b> ' +
                    '<span style="background:' + sc.bg + ';color:' + sc.color + ';padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;border:1px solid ' + sc.color + '30;">' + (f.type_label || f.type) + '</span>' +
                    upliftTag +
                    '<div style="margin-top:6px;color:#475569;">' + (f.narrative || '') + '</div>' +
                '</div>';
            }}
            if (sdFindings.length > showCount) {{
                html += '<div style="text-align:center;color:#94a3b8;font-size:12px;padding:8px 0;">... +' + (sdFindings.length - showCount) + ' more</div>';
            }}
            if (sdFindings.length === 0) {{
                html = '<div style="color:#94a3b8;text-align:center;padding:20px;">\\u6ca1\\u6709\\u53d1\\u73b0\\u663e\\u8457\\u95ee\\u9898\\uff0c\\u6240\\u6709\\u7ec4\\u8868\\u73b0\\u6b63\\u5e38\\u3002</div>';
            }}
            el.innerHTML = html;
        }})();

        // ── Filter buttons ──
        var sdCurrentFilter = 'all';
        var BUCKET_ORDER = ['S0','S1','S2','M1'];

        function renderFilterBtns() {{
            var el = document.getElementById('sd-filter-row');
            if (!el) return;
            var buckets = ['all'].concat(BUCKET_ORDER);
            var labels = {{'all': '\\u5168\\u90e8', 'S0': 'S0', 'S1': 'S1', 'S2': 'S2', 'M1': 'M1'}};
            var html = '';
            buckets.forEach(function(b) {{
                var active = b === sdCurrentFilter ? ' active' : '';
                html += '<button class="sd-filter-btn' + active + '" onclick="sdFilterBucket(&#39;' + b + '&#39;)">' + (labels[b] || b) + '</button>';
            }});
            el.innerHTML = html;
        }}

        window.sdFilterBucket = function(bkt) {{
            sdCurrentFilter = bkt;
            renderFilterBtns();
            renderTrendTable();
        }};

        // ── Trend heatmap table ──
        function achStyle(v) {{
            if (v >= 1.0) return 'background:#dcfce7;color:#15803d;';
            if (v >= 0.9) return 'background:#fef9c3;color:#a16207;';
            if (v >= 0.8) return 'background:#fee2e2;color:#dc2626;';
            return 'background:#fca5a5;color:#991b1b;font-weight:700;';
        }}

        function trendArrow(vals) {{
            if (vals.length < 2) return '<span style="color:#94a3b8;">-</span>';
            var ups = 0, downs = 0;
            for (var i = 1; i < vals.length; i++) {{
                if (vals[i] > vals[i-1] + 0.005) ups++;
                else if (vals[i] < vals[i-1] - 0.005) downs++;
            }}
            if (downs === vals.length - 1) return '<span style="color:#dc2626;font-weight:700;">\\u2193\\u2193</span>';
            if (downs > 0 && ups === 0) return '<span style="color:#f97316;">\\u2193</span>';
            if (ups === vals.length - 1) return '<span style="color:#22c55e;font-weight:700;">\\u2191\\u2191</span>';
            if (ups > 0 && downs === 0) return '<span style="color:#22c55e;">\\u2191</span>';
            return '<span style="color:#94a3b8;">\\u2194</span>';
        }}

        function covTrend(covs) {{
            var valid = covs.filter(function(c) {{ return c > 0; }});
            if (valid.length < 2) return '-';
            var first = valid[0], last = valid[valid.length - 1];
            var delta = last - first;
            var arrow = delta >= 0.005 ? '\\u2191' : (delta <= -0.005 ? '\\u2193' : '\\u2192');
            var color = delta >= 0.005 ? '#22c55e' : (delta <= -0.005 ? '#dc2626' : '#94a3b8');
            return '<span style="color:' + color + ';">' + (first * 100).toFixed(0) + '%\\u2192' + (last * 100).toFixed(0) + '% ' + arrow + '</span>';
        }}

        function renderTrendTable() {{
            var tbody = document.getElementById('sd-trend-tbody');
            if (!tbody) return;
            var html = '';

            // Collect and sort entries
            var entries = [];
            for (var key in sdGroupTrends) {{
                var g = sdGroupTrends[key];
                if (sdCurrentFilter !== 'all' && g.bucket !== sdCurrentFilter) continue;
                entries.push(g);
            }}

            // Sort by severity then bucket
            var sevOrder = {{'critical':0,'high':1,'medium':2,'low':3,'info':4}};
            entries.sort(function(a, b) {{
                var sa = sevOrder[a.severity] !== undefined ? sevOrder[a.severity] : 5;
                var sb = sevOrder[b.severity] !== undefined ? sevOrder[b.severity] : 5;
                if (sa !== sb) return sa - sb;
                var ba = BUCKET_ORDER.indexOf(a.bucket);
                var bb = BUCKET_ORDER.indexOf(b.bucket);
                if (ba === -1) ba = 99;
                if (bb === -1) bb = 99;
                return ba - bb;
            }});

            entries.forEach(function(g) {{
                html += '<tr>';
                html += '<td style="text-align:left;font-weight:600;color:#6366f1;">' + g.bucket + '</td>';
                html += '<td style="text-align:left;">' + g.group + '</td>';

                // Monthly achieve cells
                sdMonths.forEach(function(m) {{
                    var idx = g.months ? g.months.indexOf(m) : -1;
                    if (idx >= 0 && g.achieves && idx < g.achieves.length) {{
                        var ach = g.achieves[idx];
                        html += '<td><span class="sd-ach-cell" style="' + achStyle(ach) + '">' + (ach * 100).toFixed(0) + '%</span></td>';
                    }} else {{
                        html += '<td style="color:#cbd5e1;">-</td>';
                    }}
                }});

                // Trend arrow
                html += '<td>' + trendArrow(g.achieves || []) + '</td>';

                // Coverage trend
                html += '<td>' + covTrend(g.covs || []) + '</td>';

                // Diagnosis label
                var sc = sevConfig[g.severity] || sevConfig['info'];
                var patLabels = {{
                    'persistent_lazy': '\\u6301\\u7eed\\u4e0d\\u8fbe\\u6807+\\u4e0d\\u52e4\\u594b',
                    'persistent_strategy': '\\u6301\\u7eed\\u4e0d\\u8fbe\\u6807(\\u7b56\\u7565)',
                    'accelerating_decline': '\\u52a0\\u901f\\u6076\\u5316',
                    'new_issue': '\\u65b0\\u51fa\\u73b0\\u95ee\\u9898',
                    'improving': '\\u6301\\u7eed\\u6539\\u5584',
                    'stable_star': '\\u7a33\\u5b9a\\u8fbe\\u6807',
                    'declining': '\\u4e0b\\u6ed1',
                    'normal': '\\u6b63\\u5e38'
                }};
                var patLabel = patLabels[g.pattern] || g.pattern || '-';
                html += '<td><span style="background:' + sc.bg + ';color:' + sc.color + ';padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;border:1px solid ' + sc.color + '30;">' + patLabel + '</span></td>';

                // Uplift
                var up = null;
                for (var u = 0; u < sdUplift.length; u++) {{
                    if (sdUplift[u].bucket === g.bucket && sdUplift[u].group === g.group) {{
                        up = sdUplift[u];
                        break;
                    }}
                }}
                if (up && up.overall_uplift_pp > 0.01) {{
                    html += '<td style="color:#2563eb;font-weight:600;">+' + up.overall_uplift_pp.toFixed(2) + 'pp</td>';
                }} else {{
                    html += '<td style="color:#cbd5e1;">-</td>';
                }}

                html += '</tr>';
            }});

            tbody.innerHTML = html;
        }}

        // ── Uplift bar chart ──
        function renderUpliftChart() {{
            var dom = document.getElementById('sd-uplift-chart');
            if (!dom || sdUplift.length === 0) {{
                if (dom) dom.innerHTML = '<div style="color:#94a3b8;text-align:center;padding:40px;">\\u6240\\u6709\\u7ec4\\u5747\\u8fbe\\u5230\\u6a21\\u5757\\u5e73\\u5747\\u6c34\\u5e73</div>';
                return;
            }}

            var chart = echarts.init(dom);
            window._sdUpliftChart = chart;

            var top10 = sdUplift.slice(0, 10).reverse(); // reverse for horizontal bar
            var names = top10.map(function(u) {{ return u.bucket + '-' + u.group; }});
            var values = top10.map(function(u) {{ return u.overall_uplift_pp; }});
            var colors = top10.map(function(u) {{
                var sc = sevConfig[u.severity] || sevConfig['info'];
                return sc.badge || '#94a3b8';
            }});

            chart.setOption({{
                tooltip: {{
                    trigger: 'axis',
                    axisPointer: {{ type: 'shadow' }},
                    formatter: function(params) {{
                        var p = params[0];
                        var u = top10[top10.length - 1 - p.dataIndex];
                        return '<b>' + p.name + '</b><br/>' +
                            '\\u5f53\\u524d\\u56de\\u6536\\u7387: ' + (u.curr_rate * 100).toFixed(2) + '%<br/>' +
                            '\\u6a21\\u5757\\u5747\\u503c: ' + (u.bucket_avg * 100).toFixed(2) + '%<br/>' +
                            '\\u5dee\\u8ddd: ' + u.rate_gap_pp.toFixed(2) + 'pp<br/>' +
                            '<b>\\u6574\\u4f53\\u63d0\\u5347: +' + u.overall_uplift_pp.toFixed(3) + 'pp</b>';
                    }}
                }},
                grid: {{ left: 130, right: 40, top: 10, bottom: 30 }},
                xAxis: {{
                    type: 'value',
                    name: '\\u6574\\u4f53\\u63d0\\u5347 (pp)',
                    nameTextStyle: {{ fontSize: 11, color: '#94a3b8' }},
                    axisLabel: {{ fontSize: 11, formatter: '+{{value}}' }}
                }},
                yAxis: {{
                    type: 'category',
                    data: names,
                    axisLabel: {{ fontSize: 11, color: '#475569' }}
                }},
                series: [{{
                    type: 'bar',
                    data: values.map(function(v, i) {{
                        return {{ value: v, itemStyle: {{ color: colors[i] }} }};
                    }}),
                    barWidth: 18,
                    label: {{
                        show: true,
                        position: 'right',
                        formatter: function(p) {{ return '+' + p.value.toFixed(3) + 'pp'; }},
                        fontSize: 11,
                        color: '#475569'
                    }}
                }}]
            }});
        }}

        // ── Init ──
        renderFilterBtns();
        renderTrendTable();

        // Defer chart init until visible
        var sdChartInited = false;
        var sdObs = new MutationObserver(function() {{
            var el = document.getElementById('p3-attribution');
            if (el && el.style.display !== 'none' && !sdChartInited) {{
                sdChartInited = true;
                setTimeout(renderUpliftChart, 300);
                sdObs.disconnect();
            }}
        }});
        sdObs.observe(document.body, {{ attributes: true, subtree: true, attributeFilter: ['style'] }});

        setTimeout(function() {{
            var el = document.getElementById('p3-attribution');
            if (el && el.style.display !== 'none' && !sdChartInited) {{
                sdChartInited = true;
                renderUpliftChart();
            }}
        }}, 600);

        window.addEventListener('resize', function() {{
            if (window._sdUpliftChart) window._sdUpliftChart.resize();
        }});

        }} catch(err) {{
            var el = document.getElementById('sd-findings-list');
            if (el) el.innerHTML = '<div style="color:red;padding:20px;"><b>JS Error:</b> ' + err.message + '<br><pre>' + err.stack + '</pre></div>';
            console.error('SD Error:', err);
        }}
    }})();
    </script>
    </div>
    '''
    return html


def make_ops_attribution_section(data):
    """
    [v4.21 NEW] 运营归因 Treemap — 3 级钻取 (模块→组→经办)
    支持目标缺口和环比两种视角，包含 KPI 面板、ECharts Treemap、详情面板、大小额辅助图。
    """
    import json
    if not data:
        return '<div class="card"><p class="text-slate-400 text-center py-8">No attribution data available.</p></div>'

    summary = data.get("summary", {})
    treemap_data = data.get("treemap_data", [])
    size_breakdown = data.get("size_breakdown", {})
    meta = data.get("meta", {})

    # Serialize data for JS — use Unicode escapes for safety
    treemap_json = json.dumps(treemap_data, ensure_ascii=True)
    size_json = json.dumps(size_breakdown, ensure_ascii=True)
    summary_json = json.dumps(summary, ensure_ascii=True)

    curr_m = meta.get("curr_month", 0)
    prev_m = meta.get("prev_month", 0)
    curr_label = f"{str(curr_m)[:4]}\u5e74{str(curr_m)[4:]}\u6708" if curr_m else "-"
    prev_label = f"{str(prev_m)[:4]}\u5e74{str(prev_m)[4:]}\u6708" if prev_m else "-"

    html = f'''
    <div class="card" style="padding:0;overflow:hidden;">
    <!-- ====== OPS ATTRIBUTION SECTION [v4.21] ====== -->
    <style>
        .oa-header {{
            background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%);
            padding: 24px 28px 20px;
            color: white;
        }}
        .oa-header h3 {{ margin:0 0 16px; font-size:18px; font-weight:700; letter-spacing:0.5px; }}
        .oa-kpi-row {{
            display: flex; gap: 20px; flex-wrap: wrap;
        }}
        .oa-kpi-card {{
            background: rgba(255,255,255,0.15);
            backdrop-filter: blur(8px);
            border-radius: 10px;
            padding: 14px 20px;
            min-width: 150px;
            flex: 1;
        }}
        .oa-kpi-label {{ font-size:11px; opacity:0.8; margin-bottom:4px; }}
        .oa-kpi-value {{ font-size:24px; font-weight:700; }}
        .oa-kpi-sub {{ font-size:11px; opacity:0.7; margin-top:2px; }}
        .oa-controls {{
            display: flex; align-items: center; gap: 12px;
            padding: 16px 28px; background: #f8fafc; border-bottom: 1px solid #e2e8f0;
        }}
        .oa-mode-btn {{
            padding: 6px 18px; border-radius: 20px; border: 2px solid #8b5cf6;
            background: white; color: #8b5cf6; font-size: 13px; font-weight: 600;
            cursor: pointer; transition: all 0.2s;
        }}
        .oa-mode-btn.active {{
            background: #8b5cf6; color: white;
        }}
        .oa-mode-btn:hover {{ opacity: 0.85; }}
        .oa-body {{
            display: flex; gap: 0; min-height: 500px;
        }}
        .oa-treemap-wrap {{
            flex: 2; padding: 20px; border-right: 1px solid #e2e8f0;
            min-width: 0;
        }}
        .oa-detail-wrap {{
            flex: 1; padding: 20px; min-width: 300px; max-width: 420px;
            overflow-y: auto; max-height: 600px;
        }}
        .oa-detail-title {{ font-size:15px; font-weight:700; color:#1e293b; margin-bottom:12px; }}
        .oa-detail-metric {{
            display: flex; justify-content: space-between; padding: 6px 0;
            border-bottom: 1px solid #f1f5f9; font-size: 13px;
        }}
        .oa-detail-metric .lbl {{ color: #64748b; }}
        .oa-detail-metric .val {{ font-weight: 600; }}
        .oa-size-panel {{
            padding: 20px 28px; border-top: 1px solid #e2e8f0; background: #fafbfc;
        }}
        .oa-size-bar-row {{
            display: flex; align-items: center; gap: 12px; margin-bottom: 8px;
        }}
        .oa-size-bar-label {{ width: 90px; font-size: 12px; color: #475569; font-weight: 600; }}
        .oa-size-bar-track {{
            flex: 1; height: 22px; background: #e2e8f0; border-radius: 6px; position: relative; overflow: hidden;
        }}
        .oa-size-bar-fill {{
            height: 100%; border-radius: 6px; transition: width 0.5s;
            display: flex; align-items: center; padding-left: 8px;
            font-size: 11px; font-weight: 600; color: white;
        }}
        .oa-tag {{
            display: inline-block; padding: 2px 8px; border-radius: 10px;
            font-size: 11px; font-weight: 600; margin-left: 4px;
        }}
        .oa-tag-red {{ background: #fee2e2; color: #dc2626; }}
        .oa-tag-green {{ background: #dcfce7; color: #16a34a; }}
        .oa-tag-gray {{ background: #f1f5f9; color: #64748b; }}
        @media (max-width: 900px) {{
            .oa-body {{ flex-direction: column; }}
            .oa-detail-wrap {{ max-width: 100%; border-top: 1px solid #e2e8f0; }}
            .oa-treemap-wrap {{ border-right: none; }}
        }}
    </style>

    <!-- Header KPI -->
    <div class="oa-header">
        <h3>运营归因分析 (Operational Attribution)</h3>
        <div class="oa-kpi-row" id="oa-kpi-row"></div>
    </div>

    <!-- Controls -->
    <div class="oa-controls">
        <span style="font-size:13px;color:#64748b;font-weight:600;">视角:</span>
        <button class="oa-mode-btn active" id="oa-btn-gap" onclick="oaSwitchMode(&#39;gap&#39;)">目标缺口</button>
        <button class="oa-mode-btn" id="oa-btn-mom" onclick="oaSwitchMode(&#39;mom&#39;)">环比变化</button>
        <span style="margin-left:auto;font-size:12px;color:#94a3b8;" id="oa-breadcrumb"></span>
    </div>

    <!-- Body: Treemap + Detail -->
    <div class="oa-body">
        <div class="oa-treemap-wrap">
            <div id="oa-treemap" style="width:100%;height:460px;"></div>
        </div>
        <div class="oa-detail-wrap">
            <div id="oa-detail">
                <div style="color:#94a3b8;text-align:center;padding:40px 0;font-size:13px;">
                    点击 Treemap 查看详情
                </div>
            </div>
        </div>
    </div>

    <!-- Size Breakdown Panel -->
    <div class="oa-size-panel" id="oa-size-panel" style="display:none;">
        <div style="font-size:14px;font-weight:700;color:#1e293b;margin-bottom:12px;">
            大小额拆分 (Large/Small Breakdown)
        </div>
        <div id="oa-size-content"></div>
    </div>

    <script>
    (function() {{
        try {{
        // ── Data ──
        var treemapData = {treemap_json};
        var sizeData = {size_json};
        var summaryData = {summary_json};
        var currLabel = '{curr_label}';
        var prevLabel = '{prev_label}';
        var currentMode = 'gap'; // 'gap' or 'mom'

        // ── Render KPI ──
        function renderKPI() {{
            var s = summaryData;
            var gapPP = (s.gap * 100).toFixed(2);
            var momPP = (s.mom_change * 100).toFixed(2);
            var gapSign = s.gap >= 0 ? '+' : '';
            var momSign = s.mom_change >= 0 ? '+' : '';
            var gapColor = s.gap >= 0 ? '#10b981' : '#ef4444';
            var momColor = s.mom_change >= 0 ? '#10b981' : '#ef4444';

            document.getElementById('oa-kpi-row').innerHTML =
                '<div class="oa-kpi-card">' +
                    '<div class="oa-kpi-label">MTD \\u56de\\u6536\\u7387 (Day ' + s.latest_day + ')</div>' +
                    '<div class="oa-kpi-value">' + (s.overall_rate * 100).toFixed(2) + '%</div>' +
                    '<div class="oa-kpi-sub">' + currLabel + '</div>' +
                '</div>' +
                '<div class="oa-kpi-card">' +
                    '<div class="oa-kpi-label">\\u76ee\\u6807\\u56de\\u6536\\u7387</div>' +
                    '<div class="oa-kpi-value">' + (s.target_rate * 100).toFixed(2) + '%</div>' +
                    '<div class="oa-kpi-sub">Target @ Day ' + s.latest_day + '</div>' +
                '</div>' +
                '<div class="oa-kpi-card">' +
                    '<div class="oa-kpi-label">\\u76ee\\u6807\\u7f3a\\u53e3</div>' +
                    '<div class="oa-kpi-value" style="color:' + gapColor + '">' + gapSign + gapPP + 'pp</div>' +
                    '<div class="oa-kpi-sub">Actual - Target</div>' +
                '</div>' +
                '<div class="oa-kpi-card">' +
                    '<div class="oa-kpi-label">\\u73af\\u6bd4\\u53d8\\u5316</div>' +
                    '<div class="oa-kpi-value" style="color:' + momColor + '">' + momSign + momPP + 'pp</div>' +
                    '<div class="oa-kpi-sub">vs ' + prevLabel + '</div>' +
                '</div>';
        }}

        // ── Mode switch ──
        window.oaSwitchMode = function(mode) {{
            currentMode = mode;
            document.getElementById('oa-btn-gap').className = 'oa-mode-btn' + (mode === 'gap' ? ' active' : '');
            document.getElementById('oa-btn-mom').className = 'oa-mode-btn' + (mode === 'mom' ? ' active' : '');
            renderTreemap();
        }};

        // ── Treemap ──
        var tmChart = null;
        window._opsTreemapChart = null;

        function getColorVal(node) {{
            return currentMode === 'gap' ? (node.gap || 0) : (node.mom || 0);
        }}

        function formatPP(v) {{
            var sign = v >= 0 ? '+' : '';
            return sign + (v * 100).toFixed(2) + 'pp';
        }}

        function renderTreemap() {{
            var dom = document.getElementById('oa-treemap');
            if (!tmChart) {{
                tmChart = echarts.init(dom);
                window._opsTreemapChart = tmChart;
            }}

            // Find min/max gap for color mapping
            var allVals = [];
            function collectVals(nodes) {{
                nodes.forEach(function(n) {{
                    allVals.push(getColorVal(n));
                    if (n.children) collectVals(n.children);
                }});
            }}
            collectVals(treemapData);
            var maxAbs = Math.max(0.01, Math.max.apply(null, allVals.map(Math.abs)));

            // Prepare data — add colorVal to each node
            function addColorVal(nodes) {{
                return nodes.map(function(n) {{
                    var node = {{
                        name: n.name,
                        value: n.value,
                        rate: n.rate,
                        target: n.target,
                        gap: n.gap,
                        mom: n.mom,
                        colorVal: getColorVal(n),
                        proc: n.proc || null,
                        main_driver: n.main_driver || '-'
                    }};
                    if (n.children && n.children.length > 0) {{
                        node.children = addColorVal(n.children);
                    }}
                    return node;
                }});
            }}

            var chartData = addColorVal(treemapData);

            var option = {{
                tooltip: {{
                    formatter: function(info) {{
                        var d = info.data || {{}};
                        var vol = (d.value / 10000).toFixed(0);
                        var lines = [
                            '<b>' + info.name + '</b>',
                            '\\u5728\\u8d37\\u672c\\u91d1: ' + vol + '\\u4e07',
                            '\\u56de\\u6536\\u7387: ' + ((d.rate || 0) * 100).toFixed(2) + '%',
                            '\\u76ee\\u6807: ' + ((d.target || 0) * 100).toFixed(2) + '%',
                            '\\u7f3a\\u53e3: ' + formatPP(d.gap || 0),
                            '\\u73af\\u6bd4: ' + formatPP(d.mom || 0)
                        ];
                        if (d.main_driver && d.main_driver !== '-') {{
                            lines.push('\\u9a71\\u52a8\\u56e0\\u5b50: ' + d.main_driver);
                        }}
                        return lines.join('<br/>');
                    }}
                }},
                visualMap: {{
                    type: 'continuous',
                    dimension: 'colorVal',
                    min: -maxAbs,
                    max: maxAbs,
                    inRange: {{
                        color: ['#ef4444', '#fca5a5', '#fef2f2', '#ffffff', '#dcfce7', '#86efac', '#22c55e']
                    }},
                    text: ['+' + (maxAbs * 100).toFixed(1) + 'pp', '-' + (maxAbs * 100).toFixed(1) + 'pp'],
                    textStyle: {{ color: '#64748b', fontSize: 11 }},
                    show: true,
                    left: 'center',
                    bottom: 5,
                    orient: 'horizontal',
                    itemWidth: 14,
                    itemHeight: 120
                }},
                series: [{{
                    type: 'treemap',
                    data: chartData,
                    width: '96%',
                    height: '85%',
                    left: 'center',
                    top: 10,
                    roam: false,
                    nodeClick: 'zoomIn',
                    breadcrumb: {{
                        show: true,
                        left: 'center',
                        bottom: 35,
                        itemStyle: {{
                            color: '#8b5cf6',
                            borderColor: '#7c3aed',
                            textStyle: {{ color: '#fff', fontSize: 12 }}
                        }},
                        emphasis: {{
                            itemStyle: {{ color: '#a78bfa' }}
                        }}
                    }},
                    leafDepth: 1,
                    visibleMin: 200,
                    label: {{
                        show: true,
                        formatter: function(p) {{
                            var d = p.data || {{}};
                            var rate = ((d.rate || 0) * 100).toFixed(1);
                            var delta = currentMode === 'gap' ? d.gap : d.mom;
                            var deltaStr = formatPP(delta || 0);
                            return p.name + '\\n' + rate + '%\\n' + deltaStr;
                        }},
                        fontSize: 12,
                        color: '#1e293b',
                        fontWeight: 'bold'
                    }},
                    upperLabel: {{
                        show: true,
                        height: 26,
                        color: '#fff',
                        fontSize: 13,
                        fontWeight: 'bold',
                        backgroundColor: 'transparent'
                    }},
                    itemStyle: {{
                        borderColor: '#fff',
                        borderWidth: 2,
                        gapWidth: 2
                    }},
                    levels: [
                        {{
                            itemStyle: {{
                                borderColor: '#8b5cf6',
                                borderWidth: 3,
                                gapWidth: 3
                            }},
                            upperLabel: {{
                                show: true,
                                backgroundColor: '#8b5cf6',
                                padding: [4, 8],
                                borderRadius: 4
                            }}
                        }},
                        {{
                            itemStyle: {{
                                borderColor: '#c4b5fd',
                                borderWidth: 2,
                                gapWidth: 2
                            }},
                            upperLabel: {{
                                show: true,
                                backgroundColor: '#a78bfa',
                                padding: [3, 6],
                                borderRadius: 3
                            }}
                        }},
                        {{
                            itemStyle: {{
                                borderColor: '#e2e8f0',
                                borderWidth: 1,
                                gapWidth: 1
                            }}
                        }}
                    ]
                }}]
            }};

            tmChart.setOption(option, true);

            // Click handler for detail panel
            tmChart.off('click');
            tmChart.on('click', function(params) {{
                if (params.data) {{
                    renderDetail(params.data);
                    // Show size panel if clicking a module-level node
                    var name = params.data.name;
                    if (sizeData[name]) {{
                        renderSizePanel(name);
                    }} else {{
                        document.getElementById('oa-size-panel').style.display = 'none';
                    }}
                }}
            }});
        }}

        // ── Detail Panel ──
        function renderDetail(d) {{
            var detailDiv = document.getElementById('oa-detail');
            var gapTag = d.gap >= 0 ?
                '<span class="oa-tag oa-tag-green">' + formatPP(d.gap) + '</span>' :
                '<span class="oa-tag oa-tag-red">' + formatPP(d.gap) + '</span>';
            var momTag = d.mom >= 0 ?
                '<span class="oa-tag oa-tag-green">' + formatPP(d.mom) + '</span>' :
                '<span class="oa-tag oa-tag-red">' + formatPP(d.mom) + '</span>';

            var html = '<div class="oa-detail-title">' + d.name + ' ' + gapTag + '</div>';
            html += '<div class="oa-detail-metric"><span class="lbl">\\u56de\\u6536\\u7387</span><span class="val">' + ((d.rate || 0) * 100).toFixed(2) + '%</span></div>';
            html += '<div class="oa-detail-metric"><span class="lbl">\\u76ee\\u6807</span><span class="val">' + ((d.target || 0) * 100).toFixed(2) + '%</span></div>';
            html += '<div class="oa-detail-metric"><span class="lbl">\\u76ee\\u6807\\u7f3a\\u53e3</span><span class="val" style="color:' + (d.gap >= 0 ? '#10b981' : '#ef4444') + '">' + formatPP(d.gap || 0) + '</span></div>';
            html += '<div class="oa-detail-metric"><span class="lbl">\\u73af\\u6bd4</span><span class="val" style="color:' + (d.mom >= 0 ? '#10b981' : '#ef4444') + '">' + formatPP(d.mom || 0) + '</span></div>';
            html += '<div class="oa-detail-metric"><span class="lbl">\\u5728\\u8d37\\u672c\\u91d1</span><span class="val">' + ((d.value || 0) / 10000).toFixed(0) + '\\u4e07</span></div>';

            // Process drivers (group level)
            if (d.proc && Object.keys(d.proc).length > 0) {{
                var p = d.proc;
                html += '<div style="margin-top:16px;padding-top:12px;border-top:2px solid #e2e8f0;">';
                html += '<div style="font-size:13px;font-weight:700;color:#475569;margin-bottom:8px;">\\u8fc7\\u7a0b\\u6307\\u6807 (Process Drivers)</div>';

                function procRow(label, val, mom) {{
                    var momStr = mom !== 0 ? (' <span style="color:' + (mom >= 0 ? '#10b981' : '#ef4444') + ';font-size:11px;">' + (mom >= 0 ? '\\u2191' : '\\u2193') + Math.abs(mom * 100).toFixed(1) + 'pp</span>') : '';
                    return '<div class="oa-detail-metric"><span class="lbl">' + label + '</span><span class="val">' + (val * 100).toFixed(1) + '%' + momStr + '</span></div>';
                }}
                html += procRow('\\u8986\\u76d6\\u7387 (Coverage)', p.cov || 0, p.cov_mom || 0);
                html += procRow('\\u63a5\\u901a\\u7387 (Connect)', p.conn || 0, p.conn_mom || 0);
                html += '<div class="oa-detail-metric"><span class="lbl">\\u62e8\\u6253\\u5f3a\\u5ea6 (Intensity)</span><span class="val">' +
                    (p['int'] || 0).toFixed(1) +
                    (p.int_mom ? (' <span style="color:' + (p.int_mom >= 0 ? '#10b981' : '#ef4444') + ';font-size:11px;">' + (p.int_mom >= 0 ? '\\u2191' : '\\u2193') + Math.abs(p.int_mom).toFixed(1) + '</span>') : '') +
                    '</span></div>';

                if (d.main_driver && d.main_driver !== '-') {{
                    var driverColor = d.main_driver.indexOf('Cov') >= 0 ? '#8b5cf6' : (d.main_driver.indexOf('Conn') >= 0 ? '#f59e0b' : (d.main_driver.indexOf('Int') >= 0 ? '#3b82f6' : '#94a3b8'));
                    html += '<div style="margin-top:8px;padding:8px 12px;background:#faf5ff;border-radius:8px;border:1px solid #e9d5ff;">' +
                        '<span style="font-size:11px;color:#7c3aed;font-weight:600;">\\u4e3b\\u8981\\u9a71\\u52a8:</span> ' +
                        '<span style="font-size:13px;font-weight:700;color:' + driverColor + ';">' + d.main_driver + '</span></div>';
                }}
                html += '</div>';
            }}

            // Children summary (for drill-down context)
            if (d.children && d.children.length > 0) {{
                html += '<div style="margin-top:16px;padding-top:12px;border-top:2px solid #e2e8f0;">';
                html += '<div style="font-size:13px;font-weight:700;color:#475569;margin-bottom:8px;">\\u4e0b\\u7ea7\\u5b9e\\u4f53 (' + d.children.length + ')</div>';
                // Sort children by gap (worst first)
                var sorted = d.children.slice().sort(function(a, b) {{
                    var va = currentMode === 'gap' ? (a.gap || 0) : (a.mom || 0);
                    var vb = currentMode === 'gap' ? (b.gap || 0) : (b.mom || 0);
                    return va - vb;
                }});
                // Show top 8
                var showCount = Math.min(sorted.length, 8);
                for (var i = 0; i < showCount; i++) {{
                    var c = sorted[i];
                    var cv = currentMode === 'gap' ? (c.gap || 0) : (c.mom || 0);
                    var cColor = cv >= 0 ? '#10b981' : '#ef4444';
                    html += '<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:12px;">' +
                        '<span style="color:#475569;">' + c.name + '</span>' +
                        '<span style="color:' + cColor + ';font-weight:600;">' + formatPP(cv) + '</span></div>';
                }}
                if (sorted.length > showCount) {{
                    html += '<div style="text-align:center;color:#94a3b8;font-size:11px;padding-top:4px;">... +' + (sorted.length - showCount) + ' more</div>';
                }}
                html += '</div>';
            }}

            detailDiv.innerHTML = html;
        }}

        // ── Size Panel ──
        function renderSizePanel(bucketName) {{
            var panel = document.getElementById('oa-size-panel');
            var content = document.getElementById('oa-size-content');
            var items = sizeData[bucketName];
            if (!items || items.length === 0) {{
                panel.style.display = 'none';
                return;
            }}
            panel.style.display = 'block';

            var maxVol = Math.max.apply(null, items.map(function(x) {{ return x.volume; }}));
            var html = '';
            items.sort(function(a, b) {{ return b.volume - a.volume; }});
            items.forEach(function(item) {{
                var pct = maxVol > 0 ? (item.volume / maxVol * 100) : 0;
                var barColor = (item.gap || 0) >= 0 ? '#22c55e' : '#ef4444';
                var gapStr = formatPP(item.gap || 0);
                var rateStr = (item.rate * 100).toFixed(2) + '%';
                html += '<div class="oa-size-bar-row">' +
                    '<div class="oa-size-bar-label">' + item.name + '</div>' +
                    '<div class="oa-size-bar-track">' +
                        '<div class="oa-size-bar-fill" style="width:' + pct.toFixed(0) + '%;background:' + barColor + ';">' +
                            rateStr +
                        '</div>' +
                    '</div>' +
                    '<span style="font-size:12px;font-weight:600;color:' + (item.gap >= 0 ? '#10b981' : '#ef4444') + ';min-width:70px;text-align:right;">' +
                        gapStr +
                    '</span>' +
                '</div>';
            }});
            content.innerHTML = html;
        }}

        // ── Init ──
        renderKPI();
        // Defer treemap init to when Part 3 attribution tab is visible
        var tmInited = false;
        var observer = new MutationObserver(function() {{
            var el = document.getElementById('p3-attribution');
            if (el && el.style.display !== 'none' && !tmInited) {{
                tmInited = true;
                setTimeout(function() {{ renderTreemap(); }}, 200);
                observer.disconnect();
            }}
        }});
        observer.observe(document.body, {{ attributes: true, subtree: true, attributeFilter: ['style'] }});

        // Also try immediate init if already visible
        setTimeout(function() {{
            var el = document.getElementById('p3-attribution');
            if (el && el.style.display !== 'none' && !tmInited) {{
                tmInited = true;
                renderTreemap();
            }}
        }}, 500);

        // Resize handler
        window.addEventListener('resize', function() {{
            if (tmChart) tmChart.resize();
        }});

        }} catch(err) {{
            var detailDiv = document.getElementById('oa-detail');
            if (detailDiv) detailDiv.innerHTML = '<div style="color:red;padding:20px;font-size:14px;"><b>JS Error:</b> ' + err.message + '<br><pre>' + err.stack + '</pre></div>';
            console.error('OA Error:', err);
        }}
    }})();
    </script>
    </div>
    '''
    return html


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
        if bm > 0:
            if abs(delta) > 0.001:
                d_color = "text-green-600" if delta > 0 else "text-red-500"
                d_arrow = "↑" if delta > 0 else "↓"
                d_html = f"<span class='text-xs {d_color} ml-1'>{d_arrow}{abs(delta):.1%}</span>"
            else:
                # [v4.16] Stable
                d_html = f"<span class='text-xs text-gray-400 ml-1'>→</span>"
        else:
            d_html = ""

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

                            # Lift (MoM) [v4.16] Added → stable state
                            lift_html = ""
                            prev_rate = prev_rates.get(m)
                            if prev_rate is not None and prev_rate > 0:
                                lift = (rate - prev_rate) / prev_rate
                                if abs(lift) > 0.01:  # > 1% relative change
                                    arrow = "↑" if lift > 0 else "↓"
                                    color = "text-red-500" if lift > 0 else "text-green-500"
                                    lift_html = f"<span class='term-lift text-[9px] {color} ml-0.5'>{arrow}{abs(lift):.1%}</span>"
                                else:
                                    lift_html = f"<span class='term-lift text-[9px] text-gray-400 ml-0.5'>→</span>"
                            elif prev_rate is not None and prev_rate == 0 and rate == 0:
                                # [v4.16] Both zero → stable
                                lift_html = f"<span class='term-lift text-[9px] text-gray-400 ml-0.5'>→</span>"

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

        <!-- [v4.16 NEW] 总览层: 小型多图 -->
        <div id="nm-overview" style="margin-bottom:20px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;">
                <span style="font-size:14px;font-weight:700;color:#334155;">总览</span>
                <span style="font-size:12px;color:#94a3b8;">点击任意图表查看详情 ↓</span>
            </div>
            <div id="nm-overview-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;"></div>
            <!-- 总览层汇总表 -->
            <div class="mt-4">
                <table class="w-full text-sm" id="nm-overview-table">
                    <thead><tr class="bg-slate-50 text-slate-500 text-xs">
                        <th class="px-3 py-2 text-left">模块</th>
                        <th class="px-3 py-2 text-right">序时目标</th>
                        <th class="px-3 py-2 text-right">实际回收</th>
                        <th class="px-3 py-2 text-right">达成率</th>
                        <th class="px-3 py-2 text-left">进度</th>
                    </tr></thead>
                    <tbody id="nm-overview-tbody"></tbody>
                </table>
            </div>
        </div>

        <!-- [v4.13] 详情层 (默认隐藏, 点击总览小图后显示) -->
        <div id="nm-detail" style="display:none;">
            <!-- 返回总览按钮 -->
            <div style="margin-bottom:12px;">
                <button onclick="nmBackToOverview()" style="padding:4px 14px;border-radius:6px;font-size:12px;cursor:pointer;border:1px solid #e2e8f0;background:#f8fafc;color:#64748b;font-weight:500;">← 返回总览</button>
            </div>

            <!-- 面包屑导航 -->
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

        /* ---------- [v4.16b] Bucket 排序逻辑 (复用总览层排序) ---------- */
        var BUCKET_ORDER = ['S0','S1','S2','M1','M2','M3','M4'];
        var BUCKET_DESC = {{
            'S0': '-3~0天', 'S1': '1-7天', 'S2': '8-15天',
            'M1': '16-30天', 'M2': '31-60天', 'M3': '61-90天', 'M4': '90+天'
        }};
        function sortBucketList(bkts) {{
            return bkts.slice().sort(function(a, b) {{
                var ia = BUCKET_ORDER.indexOf(a);
                var ib = BUCKET_ORDER.indexOf(b);
                if (ia === -1) ia = 999;
                if (ib === -1) ib = 999;
                return ia - ib;
            }});
        }}

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
                // [v4.16b] 模块级排序: S0→S1→S2→M1...
                if (state.li === 0) bkts = sortBucketList(bkts);
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
                title: {{ text: title, textStyle: {{ fontSize: 13, color: '#475569' }}, left: 10, top: 4 }},
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
                grid: {{ left: 60, right: 30, top: 35, bottom: 50 }},
                xAxis: {{ type: 'value', name: 'Day', min: 1, max: 31, interval: 1, axisLabel: {{ fontSize: 11 }} }},
                yAxis: {{ type: 'value', axisLabel: {{ formatter: '{{value}}%', fontSize: 11 }} }},
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

        /* ================================================================
         *  [v4.16 NEW] 总览层: Small Multiples — 每个模块级 Bucket 一个小图
         * ================================================================ */
        var overviewCharts = [];
        window._nmOverviewCharts = overviewCharts; // expose for tab switch resize

        // [v4.16b] Bucket 排序 & 逾期时间描述
        var BUCKET_ORDER = ['S0','S1','S2','M1','M2','M3','M4'];
        var BUCKET_DESC = {{
            'S0': '-3~0天', 'S1': '1-7天', 'S2': '8-15天',
            'M1': '16-30天', 'M2': '31-60天', 'M3': '61-90天', 'M4': '90+天'
        }};
        function sortBuckets(bkts) {{
            return bkts.slice().sort(function(a, b) {{
                var ia = BUCKET_ORDER.indexOf(a);
                var ib = BUCKET_ORDER.indexOf(b);
                if (ia === -1) ia = 999;
                if (ib === -1) ib = 999;
                return ia - ib;
            }});
        }}

        function renderOverview() {{
            var grid = document.getElementById('nm-overview-grid');
            var tbody = document.getElementById('nm-overview-tbody');
            grid.innerHTML = '';
            overviewCharts.forEach(function(c) {{ c.dispose(); }});
            overviewCharts = [];

            // 使用模块级 (L0) 数据
            var l0 = LD['模块级'];
            if (!l0 || !l0.buckets || l0.buckets.length === 0) return;

            var buckets = sortBuckets(l0.buckets);
            var months = l0.months || [];
            var data = l0.data || {{}};
            var summ = l0.summary || {{}};
            var tm = l0.target_month || 250003;

            // [v4.16b] M2+ 折叠相关
            var CORE_BUCKETS = ['S0','S1','S2','M1'];
            var nmExtraVisible = false;

            // 渲染每个 Bucket 的小图
            buckets.forEach(function(bkt, idx) {{
                var isExtra = CORE_BUCKETS.indexOf(bkt) === -1;
                var card = document.createElement('div');
                card.style.cssText = 'border:1px solid #e2e8f0;border-radius:10px;padding:10px;cursor:pointer;transition:all 0.2s;background:white;';
                if (isExtra) {{
                    card.classList.add('nm-extra-card');
                    card.style.display = 'none';
                }}
                card.onmouseover = function() {{ card.style.borderColor='#93c5fd'; card.style.boxShadow='0 2px 8px rgba(37,99,235,0.1)'; }};
                card.onmouseout = function() {{ card.style.borderColor='#e2e8f0'; card.style.boxShadow='none'; }};
                card.onclick = function() {{ enterDetail(bkt); }};

                // 标题 + 达成率
                var s = summ[bkt];
                var achText = '';
                if (s) {{
                    var ac = s.achieve_pct || 0;
                    var bc = ac >= 1.0 ? '#22c55e' : (ac >= 0.9 ? '#f59e0b' : '#ef4444');
                    achText = '<span style="font-size:13px;font-weight:700;color:' + bc + ';">' + (ac*100).toFixed(1) + '%</span>';
                }}
                var descTag = BUCKET_DESC[bkt] ? ' <span style="font-size:11px;color:#94a3b8;font-weight:400;">(' + BUCKET_DESC[bkt] + ')</span>' : '';
                var header = document.createElement('div');
                header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;padding:0 4px;';
                header.innerHTML = '<span style="font-size:13px;font-weight:600;color:#334155;">' + bkt + descTag + '</span>' + achText;
                card.appendChild(header);

                // 图表容器
                var chartDiv = document.createElement('div');
                chartDiv.style.cssText = 'width:100%;height:180px;';
                card.appendChild(chartDiv);
                grid.appendChild(card);

                // 渲染 ECharts 迷你图
                var chart = echarts.init(chartDiv);
                overviewCharts.push(chart);

                var bktData = data[bkt] || {{}};
                var series = [];

                months.forEach(function(m, i) {{
                    if (!bktData[m]) return;
                    var pts = bktData[m];
                    var ci = Math.min(i, MC.length - 1);
                    var isLatest = (i === months.length - 1);
                    series.push({{
                        name: String(m), type: 'line', smooth: true, symbol: 'none',
                        lineStyle: {{ width: isLatest ? 2.5 : 1.2 }},
                        itemStyle: {{ color: MC[ci] }},
                        data: pts.map(function(p) {{ return [p.day, +(p.cum_rate * 100).toFixed(2)]; }})
                    }});
                }});

                // 目标线
                if (bktData[tm]) {{
                    series.push({{
                        name: 'Target', type: 'line', smooth: true, symbol: 'none',
                        lineStyle: {{ width: 2, type: 'dashed', color: TC }},
                        itemStyle: {{ color: TC }},
                        data: bktData[tm].map(function(p) {{ return [p.day, +(p.cum_rate * 100).toFixed(2)]; }})
                    }});
                }}

                chart.setOption({{
                    tooltip: {{
                        trigger: 'axis',
                        textStyle: {{ fontSize: 11 }},
                        formatter: function(params) {{
                            var sorted = params.slice().sort(function(a,b){{ return b.data[1] - a.data[1]; }});
                            var h = '<b>Day ' + params[0].data[0] + '</b><br/>';
                            sorted.forEach(function(p) {{
                                h += '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:'+p.color+';margin-right:4px;"></span>' + p.seriesName + ': ' + p.data[1].toFixed(2) + '%<br/>';
                            }});
                            return h;
                        }}
                    }},
                    grid: {{ left: 40, right: 10, top: 10, bottom: 24 }},
                    xAxis: {{ type: 'value', min: 1, max: 31, show: true, axisLabel: {{ fontSize: 10, interval: 4 }}, splitLine: {{ show: false }} }},
                    yAxis: {{ type: 'value', axisLabel: {{ formatter: '{{value}}%', fontSize: 10 }}, splitLine: {{ lineStyle: {{ color: '#f1f5f9' }} }} }},
                    legend: {{ show: false }},
                    series: series
                }});
            }});

            // [v4.16b] "显示更多" / "收起" 按钮
            var hasExtra = buckets.some(function(b) {{ return CORE_BUCKETS.indexOf(b) === -1; }});
            if (hasExtra) {{
                var toggleBtn = document.createElement('div');
                toggleBtn.id = 'nm-extra-toggle';
                toggleBtn.style.cssText = 'grid-column:1/-1;text-align:center;padding:8px;cursor:pointer;color:#3b82f6;font-size:13px;font-weight:500;border:1px dashed #93c5fd;border-radius:8px;margin-top:4px;transition:all 0.2s;';
                toggleBtn.innerHTML = '展开更多 (M2/M3/M4) ▼';
                toggleBtn.onmouseover = function() {{ toggleBtn.style.background='#eff6ff'; }};
                toggleBtn.onmouseout = function() {{ toggleBtn.style.background=''; }};
                toggleBtn.onclick = function() {{
                    nmExtraVisible = !nmExtraVisible;
                    document.querySelectorAll('.nm-extra-card').forEach(function(c) {{
                        c.style.display = nmExtraVisible ? '' : 'none';
                    }});
                    document.querySelectorAll('.nm-extra-row').forEach(function(r) {{
                        r.style.display = nmExtraVisible ? '' : 'none';
                    }});
                    toggleBtn.innerHTML = nmExtraVisible ? '收起 ▲' : '展开更多 (M2/M3/M4) ▼';
                    // 刷新图表尺寸
                    if (nmExtraVisible) {{
                        setTimeout(function() {{ overviewCharts.forEach(function(c) {{ c.resize(); }}); }}, 100);
                    }}
                }};
                grid.appendChild(toggleBtn);
            }}

            // 总览汇总表 (已排序)
            var thtml = '';
            buckets.forEach(function(bkt) {{
                var bDesc = BUCKET_DESC[bkt] ? ' <span style="font-size:11px;color:#94a3b8;">(' + BUCKET_DESC[bkt] + ')</span>' : '';
                var isExtra = CORE_BUCKETS.indexOf(bkt) === -1;
                var extraClass = isExtra ? ' nm-extra-row' : '';
                var extraStyle = isExtra ? ' style="display:none;"' : '';
                var s = summ[bkt];
                if (!s) {{
                    thtml += '<tr class="border-t border-slate-100' + extraClass + '"' + extraStyle + '><td class="px-3 py-2 font-medium">' + bkt + bDesc + '</td><td colspan="4" class="text-center text-slate-400">暂无目标</td></tr>';
                    return;
                }}
                var tr = s.target_rate_at_day || 0;
                var ar = s.actual_rate || 0;
                var ac = s.achieve_pct || 0;
                var ad = s.actual_day || 0;
                var bc = ac >= 1.0 ? '#22c55e' : (ac >= 0.9 ? '#f59e0b' : '#ef4444');
                var bw = Math.min(ac * 100, 100);
                thtml += '<tr class="border-t border-slate-100 cursor-pointer hover:bg-slate-50' + extraClass + '"' + extraStyle + ' onclick="enterDetail(\\''+bkt+'\\')"><td class="px-3 py-2 font-medium text-blue-600">' + bkt + bDesc + ' →</td><td class="px-3 py-2 text-right">' + (tr*100).toFixed(2) + '%</td><td class="px-3 py-2 text-right font-semibold">' + (ar*100).toFixed(2) + '%</td><td class="px-3 py-2 text-right font-bold" style="color:'+bc+'">' + (ac*100).toFixed(1) + '%</td><td class="px-3 py-2"><div style="background:#e2e8f0;border-radius:4px;height:8px;width:100px;"><div style="background:'+bc+';border-radius:4px;height:8px;width:'+bw.toFixed(0)+'px;"></div></div></td></tr>';
            }});
            tbody.innerHTML = thtml;

            // 响应式
            window.addEventListener('resize', function() {{ overviewCharts.forEach(function(c) {{ c.resize(); }}); }});
        }}

        /* 点击小图 → 进入详情层 */
        window.enterDetail = function(bkt) {{
            document.getElementById('nm-overview').style.display = 'none';
            document.getElementById('nm-detail').style.display = 'block';
            // 重置状态到模块级, 选中对应 bucket
            state.path = [];
            state.li = 0;
            state.selected = bkt;
            refreshAll();
            // 延迟 resize 确保图表正确渲染
            setTimeout(function() {{ nmChart.resize(); }}, 100);
        }};

        /* 返回总览 */
        window.nmBackToOverview = function() {{
            document.getElementById('nm-detail').style.display = 'none';
            document.getElementById('nm-overview').style.display = 'block';
            // 刷新总览图表尺寸
            setTimeout(function() {{ overviewCharts.forEach(function(c) {{ c.resize(); }}); }}, 100);
        }};

        // [v4.21] Expose renderOverview for lazy-init from navTo
        window._nmRenderOverview = renderOverview;
        window._nmOverviewRendered = false;
        // 初始化: 延迟到 Part 3 首次显示时调用 renderOverview()
        // (解决隐藏容器内 ECharts 宽高为 0 的 Bug)
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


# ─────────────────────────────────────────────────────────────────────────────
# [v4.19 MAJOR] 归因中心 — 时间窗口 + 客群 + 自动摘要 + 动态 Shift-Share
# ─────────────────────────────────────────────────────────────────────────────

def make_shift_share_section(ss_data):
    """[v4.20] Attribution Center — Purple Theme, Time Capsules, KPI Dashboard"""
    if not ss_data or not ss_data.get("agg"):
        return ""
    
    import json
    ss_json = json.dumps(ss_data, ensure_ascii=False)
    
    months = ss_data.get("months", [])
    user_types = ss_data.get("user_types", [])
    metric_defs = ss_data.get("metric_defs", {})
    dim_defs = ss_data.get("dim_defs", {})
    
    # Month dropdown options
    month_options = ''.join(f'<option value="{m}">{m}</option>' for m in months)
    
    # Helper for pill buttons
    def make_pill(cls, val, label, active=False):
        style = 'active' if active else ''
        return f'<button class="ss-pill {cls} {style}" data-val="{val}" onclick="ssClick(this, \'{cls}\')">{label}</button>'

    # User type buttons
    ut_btns = ''.join(
        make_pill('ss-ut', ut, ut, i==0)
        for i, ut in enumerate(user_types)
    )
    
    # Metric buttons
    mk_list = list(metric_defs.keys())
    default_mk = "dpd5" if "dpd5" in mk_list else (mk_list[0] if mk_list else "overdue_rate")
    mk_btns = ''.join(
        make_pill('ss-mk', mk, metric_defs[mk]["label"], mk == default_mk)
        for mk in mk_list
    )
    
    # Dimension buttons
    dk_list = list(dim_defs.keys())
    default_dk = dk_list[0] if dk_list else "user_type"
    dk_btns = ''.join(
        make_pill('ss-dk', dk, dim_defs[dk]["label"], dk == default_dk)
        for dk in dk_list
    )
    
    # HTML Structure
    html = f'''
    <style>
        /* v4.20 Purple Theme */
        :root {{ --ss-primary: #8b5cf6; --ss-primary-dark: #7c3aed; --ss-bg: #f5f3ff; --ss-border: #ddd6fe; }}
        
        #ss-card {{ border:1px solid #e2e8f0; border-radius:12px; background:white; overflow:hidden; margin-bottom:24px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05); }}
        
        /* 1. Top Bar */
        .ss-top-bar {{ background:white; padding:16px 20px; border-bottom:1px solid #e2e8f0; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px; }}
        .ss-title {{ display:flex; align-items:center; gap:8px; font-weight:700; font-size:16px; color:#1e293b; }}
        .ss-title-bar {{ width:4px; height:18px; background:var(--ss-primary); border-radius:2px; }}
        
        /* Time Capsules */
        .ss-time-group {{ display:flex; gap:12px; }}
        .ss-capsule {{ display:flex; align-items:center; background:#f8fafc; border:1px solid #cbd5e1; border-radius:8px; padding:4px 12px; gap:8px; transition:all 0.2s; }}
        .ss-capsule:hover {{ border-color:var(--ss-primary); background:white; box-shadow:0 2px 4px rgba(139, 92, 246, 0.1); }}
        .ss-capsule-label {{ font-size:11px; font-weight:600; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; }}
        .ss-select {{ border:none; background:transparent; font-size:13px; font-weight:600; color:#334155; cursor:pointer; outline:none; }}
        .ss-select:hover {{ color:var(--ss-primary-dark); }}
        
        /* Pill Buttons */
        .ss-pill {{ padding:6px 14px; border-radius:20px; font-size:12px; font-weight:500; border:1px solid #cbd5e1; background:white; color:#64748b; cursor:pointer; transition:all 0.15s; }}
        .ss-pill:hover {{ border-color:var(--ss-primary); color:var(--ss-primary); background:#f5f3ff; }}
        .ss-pill.active {{ background:var(--ss-primary); border-color:var(--ss-primary); color:white; font-weight:600; box-shadow:0 2px 4px rgba(139, 92, 246, 0.25); }}
        
        /* 2. Dashboard Panel */
        .ss-dashboard {{ background:#faf5ff; padding:20px; border-bottom:1px solid #f3e8ff; display:flex; gap:24px; flex-wrap:wrap; align-items:flex-start; }}
        
        /* KPI Big Number */
        .ss-kpi-box {{ flex:0 0 auto; min-width:200px; }}
        .ss-kpi-title {{ font-size:12px; color:#7c3aed; font-weight:600; margin-bottom:4px; opacity:0.8; }}
        .ss-kpi-val {{ font-size:28px; font-weight:800; line-height:1.1; letter-spacing:-0.5px; }}
        .ss-kpi-sub {{ font-size:12px; color:#64748b; margin-top:6px; display:flex; align-items:center; gap:4px; }}
        
        /* Impact List */
        .ss-impact-box {{ flex:1; display:flex; flex-direction:column; gap:8px; }}
        .ss-impact-title {{ font-size:11px; font-weight:700; color:#64748b; text-transform:uppercase; }}
        .ss-impact-list {{ display:flex; flex-wrap:wrap; gap:8px; }}
        .ss-impact-item {{ display:flex; align-items:center; padding:6px 10px; background:white; border:1px solid #e2e8f0; border-radius:6px; font-size:12px; cursor:pointer; transition:all 0.1s; gap:6px; }}
        .ss-impact-item:hover {{ border-color:var(--ss-primary); transform:translateY(-1px); box-shadow:0 2px 5px rgba(0,0,0,0.05); }}
        .ss-impact-rank {{ width:16px; height:16px; background:#f1f5f9; color:#64748b; border-radius:50%; font-size:10px; display:flex; align-items:center; justify-content:center; font-weight:700; }}
        .ss-impact-item:nth-child(1) .ss-impact-rank {{ background:#fee2e2; color:#ef4444; }}
        .ss-impact-item:nth-child(2) .ss-impact-rank {{ background:#ffedd5; color:#f97316; }}
        .ss-impact-item:nth-child(3) .ss-impact-rank {{ background:#fef9c3; color:#eab308; }}
        
        /* 3. Controls & Chart */
        .ss-controls {{ padding:16px 20px 0; display:flex; flex-wrap:wrap; gap:20px; align-items:center; border-bottom:1px solid #f1f5f9; padding-bottom:16px; }}
        .ss-control-group {{ display:flex; align-items:center; gap:8px; }}
        .ss-label {{ font-size:11px; font-weight:700; color:#94a3b8; text-transform:uppercase; }}
        
        .ss-chart-area {{ padding:20px; }}
        .ss-table-area {{ padding:0 20px 20px; }}
        
        /* Table Styles */
        .ss-table th {{ background:#f8fafc; font-weight:600; color:#475569; padding:8px 12px; font-size:11px; text-align:right; }}
        .ss-table th:first-child {{ text-align:left; border-radius:6px 0 0 6px; }}
        .ss-table th:last-child {{ border-radius:0 6px 6px 0; }}
        .ss-table td {{ padding:8px 12px; border-bottom:1px solid #f1f5f9; font-size:12px; text-align:right; color:#334155; }}
        .ss-table tr:last-child td {{ border-bottom:none; font-weight:600; background:#f8fafc; }}
    </style>
    
    <div id="ss-card">
        <!-- 1. Top Bar: Global Filters -->
        <div class="ss-top-bar">
            <div class="ss-title">
                <div class="ss-title-bar"></div>
                归因中心
            </div>
            
            <div class="ss-time-group">
                <div class="ss-capsule">
                    <span class="ss-capsule-label">Current</span>
                    <select id="ss-curr-start" class="ss-select">{month_options}</select>
                    <span style="color:#cbd5e1">/</span>
                    <select id="ss-curr-end" class="ss-select">{month_options}</select>
                </div>
                
                <div class="ss-capsule" style="opacity:0.8">
                    <span class="ss-capsule-label">Benchmark</span>
                    <select id="ss-prev-start" class="ss-select">{month_options}</select>
                    <span style="color:#cbd5e1">/</span>
                    <select id="ss-prev-end" class="ss-select">{month_options}</select>
                </div>
            </div>
            
            <div id="ss-ut-group">
                {ut_btns}
            </div>
        </div>
        
        <!-- 2. Dashboard: Smart Insights -->
        <div class="ss-dashboard" id="ss-dashboard">
            <!-- Populated by JS -->
            <div style="width:100%;height:60px;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:12px;">
                <span class="animate-pulse">Analyzing...</span>
            </div>
        </div>
        
        <!-- 3. Chart Controls -->
        <div class="ss-controls">
            <div class="ss-control-group">
                <span class="ss-label">Metric</span>
                <div id="ss-mk-group" style="display:flex;gap:4px;">{mk_btns}</div>
            </div>
            <div style="width:1px;height:24px;background:#e2e8f0;margin:0 8px;"></div>
            <div class="ss-control-group">
                <span class="ss-label">Dimension</span>
                <div id="ss-dk-group" style="display:flex;gap:4px;">{dk_btns}</div>
            </div>
        </div>
        
        <!-- 4. Waterfall Chart -->
        <div class="ss-chart-area">
            <div id="ss-waterfall" style="width:100%;height:380px;"></div>
        </div>
        
        <!-- 5. Detail Table -->
        <div class="ss-table-area">
            <table class="w-full ss-table">
                <thead id="ss-thead"></thead>
                <tbody id="ss-tbody"></tbody>
            </table>
        </div>
    </div>
    
    <script>
    (function() {{
        try {{
        var SS_AGG = {ss_json};
        var ssChart = echarts.init(document.getElementById('ss-waterfall'));
        window._ssChart = ssChart;
        var MONTHS = SS_AGG.months || [];
        var state = {{ ut: '{user_types[0] if user_types else "\u5168\u90e8"}', mk: '{default_mk}', dk: '{default_dk}' }};
        var MD = SS_AGG.metric_defs || {{}};
        var DD = SS_AGG.dim_defs || {{}};
        
        // --- Logic: Data Processing ---
        
        // Init dropdowns
        (function() {{
            var cs = document.getElementById('ss-curr-start');
            var ce = document.getElementById('ss-curr-end');
            var ps = document.getElementById('ss-prev-start');
            var pe = document.getElementById('ss-prev-end');
            if (MONTHS.length >= 2) {{
                cs.value = MONTHS[MONTHS.length - 1]; ce.value = MONTHS[MONTHS.length - 1];
                ps.value = MONTHS[MONTHS.length - 2]; pe.value = MONTHS[MONTHS.length - 2];
            }} else if (MONTHS.length === 1) {{
                cs.value = MONTHS[0]; ce.value = MONTHS[0]; ps.value = MONTHS[0]; pe.value = MONTHS[0];
            }}
            [cs, ce, ps, pe].forEach(function(sel) {{ sel.addEventListener('change', renderAll); }});
        }})();
        
        function getMonthRange(startId, endId) {{
            var s = document.getElementById(startId).value;
            var e = document.getElementById(endId).value;
            var arr = [], inRange = false;
            MONTHS.forEach(function(m) {{
                if (m === s) inRange = true;
                if (inRange) arr.push(m);
                if (m === e) inRange = false;
            }});
            return arr.length ? arr : [s];
        }}
        
        function mergeMonths(dimData, months) {{
            var merged = {{}};
            months.forEach(function(m) {{
                var segs = dimData[m];
                if (!segs) return;
                segs.forEach(function(s) {{
                    if (!merged[s.name]) merged[s.name] = {{name: s.name, num: 0, den: 0}};
                    merged[s.name].num += s.num;
                    merged[s.name].den += s.den;
                }});
            }});
            var total_den = 0;
            var arr = Object.values(merged);
            arr.forEach(function(s) {{ total_den += s.den; }});
            arr.forEach(function(s) {{
                s.rate = s.den > 0 ? s.num / s.den : 0;
                s.weight = total_den > 0 ? s.den / total_den : 0;
            }});
            return arr;
        }}
        
        function computeSS_dim(dk) {{
            var currMonths = getMonthRange('ss-curr-start', 'ss-curr-end');
            var prevMonths = getMonthRange('ss-prev-start', 'ss-prev-end');
            if (!currMonths.length || !prevMonths.length) return null;
            var utData = (SS_AGG.agg || {{}})[state.ut];
            if (!utData) return null;
            var mkData = utData[state.mk];
            if (!mkData) return null;
            var dimData = mkData[dk];
            if (!dimData) return null;
            
            var segsC = mergeMonths(dimData, currMonths);
            var segsP = mergeMonths(dimData, prevMonths);
            if (!segsC.length || !segsP.length) return null;
            
            var totalNumC=0, totalDenC=0, totalNumP=0, totalDenP=0;
            segsC.forEach(function(s) {{ totalNumC += s.num; totalDenC += s.den; }});
            segsP.forEach(function(s) {{ totalNumP += s.num; totalDenP += s.den; }});
            var rateC = totalDenC > 0 ? totalNumC / totalDenC : 0;
            var rateP = totalDenP > 0 ? totalNumP / totalDenP : 0;
            
            var allNames = {{}};
            segsC.forEach(function(s) {{ allNames[s.name] = true; }});
            segsP.forEach(function(s) {{ allNames[s.name] = true; }});
            var mapC = {{}}, mapP = {{}};
            segsC.forEach(function(s) {{ mapC[s.name] = s; }});
            segsP.forEach(function(s) {{ mapP[s.name] = s; }});
            
            var segments = [], totStr=0, totRisk=0, totCross=0;
            Object.keys(allNames).forEach(function(name) {{
                var c = mapC[name] || {{rate:0, weight:0, num:0, den:0}};
                var p = mapP[name] || {{rate:0, weight:0, num:0, den:0}};
                var dw = c.weight - p.weight;
                var dr = c.rate - p.rate;
                var wAvg = (c.weight + p.weight) / 2;
                var rAvg = (c.rate + p.rate) / 2;
                var str = dw * rAvg, risk = wAvg * dr, cross = dw * dr;
                totStr += str; totRisk += risk; totCross += cross;
                segments.push({{
                    name: name, wC: c.weight, wP: p.weight, rC: c.rate, rP: p.rate,
                    dw: dw, dr: dr, structure: str, risk: risk, cross: cross,
                    total: str + risk + cross, denC: c.den, denP: p.den
                }});
            }});
            segments.sort(function(a, b) {{ return Math.abs(b.total) - Math.abs(a.total); }});
            return {{
                rateC: rateC, rateP: rateP, delta: rateC - rateP,
                totStr: totStr, totRisk: totRisk, totCross: totCross,
                segments: segments,
                currLabel: getMonthRange('ss-curr-start','ss-curr-end').join('+'),
                prevLabel: getMonthRange('ss-prev-start','ss-prev-end').join('+'),
            }};
        }}
        
        function computeSS() {{ return computeSS_dim(state.dk); }}
        
        // --- Rendering ---
        
        function renderDashboard() {{
            var el = document.getElementById('ss-dashboard');
            var mkLabel = (MD[state.mk]||{{}}).label || state.mk;
            
            // Cross-dim analysis for top drivers
            // Skip dimensions with only 1 segment (redundant when filtering by specific user type etc.)
            var allDims = Object.keys(DD);
            var results = [];
            allDims.forEach(function(dk) {{
                var r = computeSS_dim(dk);
                if (r && r.segments.length > 1) {{
                    results.push({{ dk: dk, label: (DD[dk]||{{}}).label||dk, result: r, topSeg: r.segments[0] }});
                }}
            }});
            results.sort(function(a, b) {{ return Math.abs(b.topSeg.total) - Math.abs(a.topSeg.total); }});
            
            if (results.length === 0) {{ el.innerHTML = 'No data'; return; }}
            
            var main = results[0];
            var m = main.result;
            var delta = m.delta;
            var arrow = delta > 0.0001 ? '\u2191' : (delta < -0.0001 ? '\u2193' : '\u2192');
            var color = delta > 0.0001 ? '#ef4444' : (delta < -0.0001 ? '#10b981' : '#64748b');
            var deltaStr = (delta * 100).toFixed(2) + 'pp';
            
            var impactHtml = '';
            results.slice(0, 5).forEach(function(item, i) {{
                var seg = item.topSeg;
                var val = (seg.total * 100).toFixed(2) + 'pp';
                var sColor = seg.total > 0 ? '#ef4444' : '#10b981';
                var sSign = seg.total > 0 ? '+' : '';
                // Determine driver: structure vs risk
                var absStr = Math.abs(seg.structure);
                var absRisk = Math.abs(seg.risk);
                var driver = absStr > absRisk * 1.2 ? 'Str' : (absRisk > absStr * 1.2 ? 'Risk' : 'Mix');
                var driverColor = driver === 'Str' ? '#8b5cf6' : (driver === 'Risk' ? '#f59e0b' : '#94a3b8');
                impactHtml += '<div class="ss-impact-item" onclick="ssSetDimByName(&#39;' + item.dk + '&#39;)">' +
                    '<div class="ss-impact-rank">' + (i+1) + '</div>' +
                    '<span style="color:#64748b;font-weight:600">' + item.label + '</span>' +
                    '<span style="color:#94a3b8">\u00B7</span>' +
                    '<span style="color:#334155">' + seg.name + '</span>' +
                    '<span style="font-weight:700;color:' + sColor + '">' + sSign + val + '</span>' +
                    '<span style="font-size:10px;padding:1px 5px;border-radius:3px;background:' + driverColor + ';color:white;margin-left:4px">' + driver + '</span>' +
                    '</div>';
            }});
            
            el.innerHTML = 
                '<div class="ss-kpi-box">' +
                    '<div class="ss-kpi-title">' + mkLabel + ' Change</div>' +
                    '<div class="ss-kpi-val" style="color:' + color + '">' + arrow + ' ' + deltaStr + '</div>' +
                    '<div class="ss-kpi-sub">' +
                        '<span>' + (m.rateP * 100).toFixed(2) + '%</span>' +
                        '<span style="color:#cbd5e1">\u2192</span>' +
                        '<span>' + (m.rateC * 100).toFixed(2) + '%</span>' +
                    '</div>' +
                '</div>' +
                '<div style="width:1px;background:#f3e8ff;margin:0 10px;"></div>' +
                '<div class="ss-impact-box">' +
                    '<div class="ss-impact-title">Top Impact Drivers</div>' +
                    '<div class="ss-impact-list">' + impactHtml + '</div>' +
                '</div>';
        }}
        
        function renderWaterfall(m) {{
            if (!m) {{ ssChart.clear(); return; }}
            var segs = m.segments;
            var cats = ['Benchmark'];
            var structureData = ['-'], riskData = ['-'];
            var baseData = [m.rateP * 100], totalData = ['-'];
            var signMap = {{}};
            var running = m.rateP * 100;
            
            segs.forEach(function(s) {{
                if (Math.abs(s.structure) > 0.00001) {{
                    var label = s.name + ' (Str)';
                    cats.push(label);
                    var val = s.structure * 100;
                    signMap[cats.length - 1] = val >= 0 ? 1 : -1;
                    if (val >= 0) {{ baseData.push(running); structureData.push(val); }}
                    else {{ baseData.push(running + val); structureData.push(-val); }}
                    riskData.push('-'); totalData.push('-');
                    running += val;
                }}
            }});
            segs.forEach(function(s) {{
                if (Math.abs(s.risk) > 0.00001) {{
                    var label = s.name + ' (Risk)';
                    cats.push(label);
                    var val = s.risk * 100;
                    signMap[cats.length - 1] = val >= 0 ? 1 : -1;
                    if (val >= 0) {{ baseData.push(running); riskData.push(val); }}
                    else {{ baseData.push(running + val); riskData.push(-val); }}
                    structureData.push('-'); totalData.push('-');
                    running += val;
                }}
            }});
            
            cats.push('Current');
            baseData.push('-'); structureData.push('-'); riskData.push('-');
            totalData.push(m.rateC * 100);
            
            var barCount = cats.length;
            var chartH = barCount > 15 ? 450 : 380;
            document.getElementById('ss-waterfall').style.height = chartH + 'px';
            ssChart.resize();
            
            ssChart.setOption({{
                tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'shadow' }},
                    formatter: function(params) {{
                        var html = '<b>' + params[0].name + '</b><br/>';
                        params.forEach(function(p) {{
                            if (p.value !== '-' && p.seriesName !== 'Base') {{
                                var sign = signMap[p.dataIndex];
                                var dispVal = sign === -1 ? -p.value : p.value;
                                html += p.marker + p.seriesName + ': ' + (dispVal >= 0 ? '+' : '') + dispVal.toFixed(3) + 'pp<br/>';
                            }}
                        }});
                        return html;
                    }}
                }},
                legend: {{ bottom: 0, icon:'circle', itemGap:20 }},
                grid: {{ left: 50, right: 30, top: 30, bottom: barCount > 12 ? 80 : 50 }},
                xAxis: {{ type: 'category', data: cats, axisLabel: {{ fontSize: 9, rotate: barCount > 12 ? 45 : 30, interval: 0, color:'#64748b' }} }},
                yAxis: {{ type: 'value', splitLine:{{lineStyle:{{type:'dashed'}}}}, axisLabel: {{ formatter: '{{value}}%', fontSize: 11, color:'#64748b' }} }},
                series: [
                    {{ name: 'Base', type: 'bar', stack: 'waterfall', itemStyle: {{ color: 'transparent' }}, data: baseData }},
                    {{ name: 'Structure', type: 'bar', stack: 'waterfall', itemStyle: {{ color: '#8b5cf6' }}, data: structureData,
                       label: {{ show: true, position: 'top', fontSize: 10, color:'#8b5cf6',
                           formatter: function(p) {{ if (p.value === '-') return ''; var s = signMap[p.dataIndex]; return (s === -1 ? '-' : '+') + p.value.toFixed(3); }} }} }},
                    {{ name: 'Risk', type: 'bar', stack: 'waterfall', itemStyle: {{ color: '#f59e0b' }}, data: riskData,
                       label: {{ show: true, position: 'top', fontSize: 10, color:'#f59e0b',
                           formatter: function(p) {{ if (p.value === '-') return ''; var s = signMap[p.dataIndex]; return (s === -1 ? '-' : '+') + p.value.toFixed(3); }} }} }},
                    {{ name: 'Total', type: 'bar', stack: 'waterfall', itemStyle: {{ color: '#475569' }}, data: totalData,
                       label: {{ show: true, position: 'top', fontSize: 11, fontWeight: 'bold', formatter: function(p) {{ return p.value !== '-' ? p.value.toFixed(2)+'%' : ''; }} }} }}
                ]
            }}, true);
        }}
        
        function renderTable(m) {{
            var thead = document.getElementById('ss-thead');
            var tbody = document.getElementById('ss-tbody');
            if (!m || !m.segments.length) {{ thead.innerHTML = ''; tbody.innerHTML = ''; return; }}
            
            var dkLabel = (DD[state.dk]||{{}}).label || state.dk;
            thead.innerHTML = '<tr>' +
                '<th>' + dkLabel + '</th>' +
                '<th>Weight (Old)</th><th>Weight (New)</th><th>\u0394 Weight</th>' +
                '<th>Rate (Old)</th><th>Rate (New)</th><th>\u0394 Rate</th>' +
                '<th style="color:#8b5cf6">Structure Eff</th>' +
                '<th style="color:#f59e0b">Risk Eff</th>' +
                '<th>Total Contribution</th></tr>';
            
            function effStyle(v) {{
                var c = v > 0.00001 ? '#ef4444' : (v < -0.00001 ? '#10b981' : '#64748b');
                var bg = v > 0.00001 ? '#fef2f2' : (v < -0.00001 ? '#f0fdf4' : '');
                return 'color:' + c + (bg ? ';background:' + bg : '');
            }}
            var html = '';
            m.segments.forEach(function(s) {{
                var tc = s.total > 0.00001 ? '#ef4444' : (s.total < -0.00001 ? '#10b981' : '#64748b');
                
                html += '<tr>' +
                    '<td style="font-weight:600">' + s.name + '</td>' +
                    '<td>' + (s.wP * 100).toFixed(1) + '%</td>' +
                    '<td>' + (s.wC * 100).toFixed(1) + '%</td>' +
                    '<td style="color:' + (s.dw>0.001?'#3b82f6':(s.dw<-0.001?'#94a3b8':'#94a3b8')) + '">' + (s.dw>0?'+':'') + (s.dw*100).toFixed(1) + 'pp</td>' +
                    '<td>' + (s.rP * 100).toFixed(2) + '%</td>' +
                    '<td>' + (s.rC * 100).toFixed(2) + '%</td>' +
                    '<td style="color:' + (s.dr>0.0001?'#ef4444':(s.dr<-0.0001?'#10b981':'#94a3b8')) + '">' + (s.dr>0?'+':'') + (s.dr*100).toFixed(2) + 'pp</td>' +
                    '<td style="' + effStyle(s.structure) + '">' + (s.structure>0?'+':'') + (s.structure*100).toFixed(3) + 'pp</td>' +
                    '<td style="' + effStyle(s.risk) + '">' + (s.risk>0?'+':'') + (s.risk*100).toFixed(3) + 'pp</td>' +
                    '<td style="font-weight:700;color:' + tc + '">' + (s.total>0?'+':'') + (s.total*100).toFixed(3) + 'pp</td>' +
                    '</tr>';
            }});
            
            // Total Row
            var dtColor = m.delta > 0.0001 ? '#ef4444' : '#10b981';
            html += '<tr style="border-top:2px solid #e2e8f0">' +
                '<td>Total</td>' +
                '<td>100%</td><td>100%</td><td>-</td>' +
                '<td>' + (m.rateP * 100).toFixed(2) + '%</td>' +
                '<td>' + (m.rateC * 100).toFixed(2) + '%</td>' +
                '<td style="color:' + dtColor + '">' + (m.delta>0?'+':'') + (m.delta*100).toFixed(3) + 'pp</td>' +
                '<td style="' + effStyle(m.totStr) + '">' + (m.totStr>0?'+':'') + (m.totStr*100).toFixed(3) + 'pp</td>' +
                '<td style="' + effStyle(m.totRisk) + '">' + (m.totRisk>0?'+':'') + (m.totRisk*100).toFixed(3) + 'pp</td>' +
                '<td style="color:' + dtColor + '">' + (m.delta>0?'+':'') + (m.delta*100).toFixed(3) + 'pp</td>' +
                '</tr>';
            
            tbody.innerHTML = html;
        }}
        
        function renderAll() {{
            var result = computeSS();
            renderDashboard();
            renderWaterfall(result);
            renderTable(result);
        }}
        
        window.ssClick = function(btn, cls) {{
            document.querySelectorAll('.' + cls).forEach(function(b) {{ b.classList.remove('active'); }});
            btn.classList.add('active');
            var val = btn.dataset.val;
            if (cls === 'ss-ut') state.ut = val;
            if (cls === 'ss-mk') state.mk = val;
            if (cls === 'ss-dk') state.dk = val;
            renderAll();
        }};
        
        window.ssSetDimByName = function(dk) {{
            state.dk = dk;
            document.querySelectorAll('.ss-dk').forEach(function(b) {{
                if (b.dataset.val === dk) b.classList.add('active'); else b.classList.remove('active');
            }});
            renderAll();
        }};
        
        renderAll();
        window.addEventListener('resize', function() {{ ssChart.resize(); }});
        }} catch(err) {{
            var dashboard = document.getElementById('ss-dashboard');
            if (dashboard) dashboard.innerHTML = '<div style="color:red;padding:20px;font-size:14px;"><b>JS Error:</b> ' + err.message + '<br><pre>' + err.stack + '</pre></div>';
            console.error('SS Error:', err);
        }}
    }})();
    </script>
    '''
    return html


# ════════════════════════════════════════════════════════════════
# [v4.23] Part 3 — 智能诊断版板块
# ════════════════════════════════════════════════════════════════

def _build_group_diagnostics(nm_data, process_detail, perf_data):
    """
    [v4.23] 数据桥接：合并 nm_progress_data + process_detail + perf_data，
    生成每个组的综合诊断数据。返回按 (parent_bucket, group_name) 索引的字典。
    """
    diag = {}  # key = (parent_bucket, group_name)

    if not nm_data:
        return diag

    level_data = nm_data.get("level_data", {})
    group_level = level_data.get("组级", {})
    agent_level = level_data.get("经办级", {})

    # 1. 从 nm_progress 获取组级达成率
    for parent, pdata in group_level.get("by_parent", {}).items():
        for gname, sdata in pdata.get("summary", {}).items():
            key = (parent, gname)
            diag[key] = {
                "parent": parent,
                "group": gname,
                "actual": sdata.get("actual_rate", 0),
                "target": sdata.get("target_rate_at_day", 0),
                "achieve": sdata.get("achieve_pct", 0),
                "day": sdata.get("actual_day", 0),
                # process metrics (to be filled)
                "call_times_avg": None,
                "cover_rate": None,
                "call_billhr_avg": None,
                "case_connect_rate": None,
                "caseload": None,
                # diagnostics
                "agent_variance": 0,
                "agent_count": 0,
                "agents": [],
                "pattern": "",
                "mom_trend": [],  # month-over-month achieve_pct
            }

    # 2. 计算组内经办方差
    for gname, gdata in agent_level.get("by_parent", {}).items():
        agent_summary = gdata.get("summary", {})
        if not agent_summary:
            continue
        achieves = [s.get("achieve_pct", 0) for s in agent_summary.values() if s.get("achieve_pct") is not None]
        agents_list = []
        for aname, asdata in agent_summary.items():
            agents_list.append({
                "name": aname,
                "actual": asdata.get("actual_rate", 0),
                "target": asdata.get("target_rate_at_day", 0),
                "achieve": asdata.get("achieve_pct", 0),
            })
        agents_list.sort(key=lambda x: x["achieve"], reverse=True)

        variance = 0
        if len(achieves) > 1:
            mean_a = sum(achieves) / len(achieves)
            variance = (sum((a - mean_a) ** 2 for a in achieves) / len(achieves)) ** 0.5

        # Find which parent this group belongs to
        for key in diag:
            if key[1] == gname:
                diag[key]["agent_variance"] = variance
                diag[key]["agent_count"] = len(achieves)
                diag[key]["agents"] = agents_list
                break

    # 3. 从 process_detail 获取过程指标
    if process_detail:
        # Build lookup: (owner_bucket, owner_group) -> metrics
        proc_lookup = {}
        for row in process_detail:
            ob = str(row.get("owner_bucket", ""))
            og = str(row.get("owner_group", ""))
            if ob and og:
                pk = (ob, og)
                if pk not in proc_lookup:
                    proc_lookup[pk] = row
        # Match: parent_bucket (e.g. "S1_Large") prefix should match owner_bucket (e.g. "S1")
        for key, d in diag.items():
            parent_bucket = key[0]  # e.g. "S1_Large" or "S1"
            bucket_prefix = parent_bucket.split("_")[0]  # "S1"
            gname = key[1]
            # Try exact match first, then prefix match
            pk = (bucket_prefix, gname)
            if pk in proc_lookup:
                row = proc_lookup[pk]
                for metric in ["call_times_avg", "cover_rate", "call_billhr_avg", "case_connect_rate", "caseload"]:
                    val = row.get(metric)
                    if val is not None:
                        try:
                            d[metric] = float(val)
                        except (ValueError, TypeError):
                            pass

    # 4. 计算模块内平均值 (用于对比)
    bucket_groups = {}  # bucket_prefix -> list of diag entries
    for key, d in diag.items():
        bp = key[0].split("_")[0]
        bucket_groups.setdefault(bp, []).append(d)

    for bp, groups in bucket_groups.items():
        for metric in ["call_times_avg", "cover_rate", "call_billhr_avg"]:
            vals = [g[metric] for g in groups if g[metric] is not None and g[metric] > 0]
            avg = sum(vals) / len(vals) if vals else 0
            for g in groups:
                g[f"{metric}_module_avg"] = avg

    # 5. 判定 pattern 标签
    for key, d in diag.items():
        ach = d["achieve"]
        cover = d.get("cover_rate")
        calls = d.get("call_times_avg")
        cover_avg = d.get("cover_rate_module_avg", 0)
        calls_avg = d.get("call_times_avg_module_avg", 0)

        has_proc = cover is not None and calls is not None and cover_avg > 0 and calls_avg > 0

        if ach >= 1.1:
            d["pattern"] = "star"
        elif ach >= 1.0:
            d["pattern"] = "on_track"
        elif ach >= 0.85:
            if has_proc and cover < cover_avg * 0.85 and calls < calls_avg * 0.85:
                d["pattern"] = "lazy_close"
            else:
                d["pattern"] = "near"
        else:
            if has_proc and cover >= cover_avg * 0.95 and calls >= calls_avg * 0.95:
                d["pattern"] = "strategy_issue"
            elif has_proc and (cover < cover_avg * 0.8 or calls < calls_avg * 0.8):
                d["pattern"] = "mgmt_issue"
            else:
                d["pattern"] = "behind"

        # High variance check
        if d["agent_count"] >= 3 and d["agent_variance"] > 0.25:
            d["pattern"] += "+high_var"

    # 6. 从 perf_data 获取贡献度信息
    if perf_data:
        for bucket, bdata in perf_data.get("groups", {}).items():
            for agent in bdata.get("all", []):
                gname = agent.get("group_name", "")
                contrib = agent.get("contrib_to_delta", 0)
                driver = agent.get("main_driver", "-")
                for key, d in diag.items():
                    if d["group"] == gname:
                        d["contrib"] = contrib
                        d["main_driver"] = driver
                        break

    return diag


def make_target_dashboard(nm_data, ops_attr_data):
    """
    [v4.23] 目标追踪看板 — 精简版，仅展示 KPI 头（含环比），
    模块表和组表已在 nm_progress 和排行榜中展示，不再重复。
    """
    if not ops_attr_data:
        return ''

    ops_summary = ops_attr_data.get("summary", {})
    overall_rate = ops_summary.get("overall_rate", 0)
    target_rate = ops_summary.get("target_rate", 0)
    gap = ops_summary.get("gap", 0)
    prev_rate = ops_summary.get("prev_rate", 0)
    mom_change = ops_summary.get("mom_change", 0)
    latest_day = ops_summary.get("latest_day", 0)

    gap_display = f"{gap:+.2%}" if gap else "-"
    mom_display = f"{mom_change:+.2%}" if mom_change else "-"

    return f'''
    <div class="card" style="padding:0;overflow:hidden;">
        <div style="background:linear-gradient(135deg,#059669 0%,#34d399 100%);padding:20px 24px;color:white;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                <h3 style="margin:0;font-size:16px;font-weight:700;">目标追踪看板</h3>
                <span style="font-size:12px;opacity:0.8;margin-left:auto;">Day {latest_day} of Month (同日对齐)</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;">
                <div style="background:rgba(255,255,255,0.15);border-radius:10px;padding:12px 14px;">
                    <div style="font-size:10px;opacity:0.8;">当月实际回收率</div>
                    <div style="font-size:20px;font-weight:700;margin-top:2px;">{overall_rate:.2%}</div>
                </div>
                <div style="background:rgba(255,255,255,0.15);border-radius:10px;padding:12px 14px;">
                    <div style="font-size:10px;opacity:0.8;">序时目标</div>
                    <div style="font-size:20px;font-weight:700;margin-top:2px;">{target_rate:.2%}</div>
                </div>
                <div style="background:rgba(255,255,255,0.15);border-radius:10px;padding:12px 14px;">
                    <div style="font-size:10px;opacity:0.8;">vs 目标</div>
                    <div style="font-size:20px;font-weight:700;margin-top:2px;{'color:#fca5a5;' if gap < 0 else ''}">{gap_display}</div>
                </div>
                <div style="background:rgba(255,255,255,0.15);border-radius:10px;padding:12px 14px;">
                    <div style="font-size:10px;opacity:0.8;">上月同期(Day {latest_day})</div>
                    <div style="font-size:20px;font-weight:700;margin-top:2px;">{prev_rate:.2%}</div>
                </div>
                <div style="background:rgba(255,255,255,0.15);border-radius:10px;padding:12px 14px;">
                    <div style="font-size:10px;opacity:0.8;">vs 上月</div>
                    <div style="font-size:20px;font-weight:700;margin-top:2px;{'color:#fca5a5;' if mom_change < 0 else ''}">{mom_display}</div>
                </div>
            </div>
        </div>
    </div>
    '''


def make_agent_leaderboard(nm_data, process_detail, perf_data, diag):
    """
    [v4.23] 模块组级排行 — 按模块分组，同模块内比达成率。
    """
    if not diag:
        return ''

    PATTERN_LABELS = {
        "star": ("标杆", "#16a34a", "#dcfce7"),
        "on_track": ("达标", "#059669", "#ecfdf5"),
        "near": ("接近", "#d97706", "#fef3c7"),
        "lazy_close": ("懈怠", "#ea580c", "#fff7ed"),
        "strategy_issue": ("策略问题", "#9333ea", "#f5f3ff"),
        "mgmt_issue": ("管理问题", "#dc2626", "#fef2f2"),
        "behind": ("落后", "#ef4444", "#fef2f2"),
    }

    def _pattern_tag(pattern):
        base = pattern.split("+")[0] if "+" in pattern else pattern
        label, color, bg = PATTERN_LABELS.get(base, ("", "#64748b", "#f1f5f9"))
        extra = ""
        if "high_var" in pattern:
            extra = '<span style="display:inline-block;padding:1px 6px;border-radius:8px;font-size:9px;font-weight:600;background:#ede9fe;color:#7c3aed;margin-left:3px;">方差大</span>'
        if not label:
            return extra
        return f'<span style="display:inline-block;padding:1px 6px;border-radius:8px;font-size:9px;font-weight:600;background:{bg};color:{color};">{label}</span>{extra}'

    def _fmt_pct(v):
        if v is not None and isinstance(v, (int, float)) and v > 0:
            return f"{v:.1%}"
        return "-"

    def _fmt_num(v):
        if v is not None and isinstance(v, (int, float)) and v > 0:
            return f"{v:.1f}"
        return "-"

    # Group by module (bucket prefix)
    modules = {}
    for key, d in diag.items():
        bp = key[0].split("_")[0]
        modules.setdefault(bp, []).append(d)

    BUCKET_ORDER = ["S0", "S1", "S2", "M1", "M2", "M3", "M4"]
    sorted_modules = sorted(modules.keys(), key=lambda x: BUCKET_ORDER.index(x) if x in BUCKET_ORDER else 99)

    module_cards = []
    for bp in sorted_modules:
        groups = sorted(modules[bp], key=lambda x: x["achieve"])
        n = len(groups)
        avg_ach = sum(g["achieve"] for g in groups) / n if n else 0
        risk_count = sum(1 for g in groups if g["achieve"] < 0.85)
        status_color = "#10b981" if avg_ach >= 1.0 else ("#f59e0b" if avg_ach >= 0.85 else "#ef4444")

        group_rows = []
        for i, g in enumerate(groups):
            ach = g["achieve"]
            ach_color = "#10b981" if ach >= 1.0 else ("#f59e0b" if ach >= 0.85 else "#ef4444")
            rank = i + 1
            rank_icon = f'<span style="display:inline-block;width:20px;height:20px;border-radius:50%;background:#e2e8f0;text-align:center;line-height:20px;font-size:10px;font-weight:700;color:#64748b;">{rank}</span>'

            # Agent mini-list (top 3 + bottom 3 if enough)
            agents_html = ""
            if g.get("agents"):
                agents = g["agents"]
                show_agents = agents[:3] + (["..."] if len(agents) > 6 else []) + (agents[-3:] if len(agents) > 6 else agents[3:])
                agent_items = []
                for a in show_agents:
                    if a == "...":
                        agent_items.append('<div style="text-align:center;color:#94a3b8;font-size:10px;">...</div>')
                    else:
                        a_ach = a["achieve"]
                        a_color = "#10b981" if a_ach >= 1.0 else ("#f59e0b" if a_ach >= 0.85 else "#ef4444")
                        agent_items.append(f'<div style="display:flex;justify-content:space-between;font-size:11px;padding:1px 0;"><span class="text-slate-600 truncate" style="max-width:100px;">{a["name"]}</span><span style="color:{a_color};font-weight:600;">{a_ach:.0%}</span></div>')
                agents_html = f'<div style="margin-top:6px;padding:6px 8px;background:#f8fafc;border-radius:6px;border:1px solid #e2e8f0;">{"".join(agent_items)}</div>'

            group_rows.append(f'''
            <div style="padding:10px 14px;border-bottom:1px solid #f1f5f9;">
                <div style="display:flex;align-items:center;gap:8px;">
                    {rank_icon}
                    <div style="flex:1;min-width:0;">
                        <div style="display:flex;align-items:center;gap:4px;">
                            <span class="font-medium text-slate-700 text-sm truncate">{g["group"]}</span>
                            {_pattern_tag(g["pattern"])}
                        </div>
                        <div class="text-xs text-slate-400">{g["parent"]} | {g["agent_count"]}人</div>
                    </div>
                    <div style="text-align:right;min-width:80px;">
                        <div class="font-bold" style="color:{ach_color};">{ach:.0%}</div>
                        <div class="text-xs text-slate-400">目标 {g["target"]:.2%}</div>
                    </div>
                    <div style="text-align:right;min-width:100px;">
                        <div class="text-xs text-slate-500">覆盖 {_fmt_pct(g.get("cover_rate"))} | 拨打 {_fmt_num(g.get("call_times_avg"))}</div>
                        <div class="text-xs text-slate-400">通话 {_fmt_num(g.get("call_billhr_avg"))}h</div>
                    </div>
                </div>
                {agents_html}
            </div>''')

        module_cards.append(f'''
        <div style="border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin-bottom:16px;">
            <div style="padding:12px 16px;background:linear-gradient(90deg,{status_color}11,{status_color}05);border-bottom:1px solid #e2e8f0;display:flex;align-items:center;justify-content:space-between;">
                <div>
                    <span style="font-size:15px;font-weight:700;color:#1e293b;">{bp}</span>
                    <span class="text-xs text-slate-500 ml-2">{n} 组</span>
                </div>
                <div style="display:flex;align-items:center;gap:8px;">
                    <span class="text-sm font-bold" style="color:{status_color};">均值 {avg_ach:.0%}</span>
                    {"" if risk_count == 0 else f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;background:#fef2f2;color:#dc2626;">{risk_count} 组落后</span>'}
                </div>
            </div>
            <div style="max-height:500px;overflow-y:auto;">{"".join(group_rows)}</div>
        </div>''')

    return f'''
    <div class="card" style="padding:0;overflow:hidden;">
        <div style="padding:20px 24px;border-bottom:1px solid #e2e8f0;">
            <div class="flex items-center gap-2">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                <h3 class="text-lg font-bold text-slate-800" style="margin:0;">模块组级排行</h3>
                <span class="text-xs text-slate-400 ml-auto">同模块内比达成率，按达成率升序排列</span>
            </div>
        </div>
        <div style="padding:16px 24px;">
            {"".join(module_cards)}
        </div>
    </div>
    '''


def make_efficiency_analysis(nm_data, process_detail, diag):
    """
    [v4.23] 投入产出矩阵 — 横轴勤奋度，纵轴达成率，2x2 象限分析。
    """
    if not diag:
        return ''

    QUADRANT_LABELS = {
        "HH": ("全面优秀", "#10b981", "#dcfce7"),
        "LH": ("策略优秀", "#3b82f6", "#dbeafe"),
        "HL": ("策略问题", "#f59e0b", "#fef3c7"),
        "LL": ("管理问题", "#ef4444", "#fee2e2"),
    }

    # Collect groups with both achieve and process metrics
    points = []
    for key, d in diag.items():
        cover = d.get("cover_rate")
        calls = d.get("call_times_avg")
        billhr = d.get("call_billhr_avg")
        if cover is None and calls is None:
            continue
        # Compute effort score (normalized within module)
        cover_avg = d.get("cover_rate_module_avg", 0)
        calls_avg = d.get("call_times_avg_module_avg", 0)
        effort_score = 0
        n_metrics = 0
        if cover is not None and cover_avg > 0:
            effort_score += cover / cover_avg
            n_metrics += 1
        if calls is not None and calls_avg > 0:
            effort_score += calls / calls_avg
            n_metrics += 1
        if n_metrics > 0:
            effort_score /= n_metrics
        else:
            effort_score = 1.0

        ach = d["achieve"]
        bucket = key[0].split("_")[0]
        quadrant = ("H" if effort_score >= 1.0 else "L") + ("H" if ach >= 0.9 else "L")
        points.append({
            "group": d["group"],
            "parent": d["parent"],
            "bucket": bucket,
            "achieve": ach,
            "effort": effort_score,
            "cover": cover,
            "calls": calls,
            "quadrant": quadrant,
            "pattern": d["pattern"],
        })

    if not points:
        return ''

    # Sort into quadrants
    q_counts = {"HH": 0, "LH": 0, "HL": 0, "LL": 0}
    for p in points:
        q_counts[p["quadrant"]] = q_counts.get(p["quadrant"], 0) + 1

    # Build quadrant summary cards
    q_cards = []
    for qk, (label, color, bg) in QUADRANT_LABELS.items():
        cnt = q_counts.get(qk, 0)
        q_cards.append(f'''
            <div style="background:{bg};border-radius:10px;padding:14px 18px;border:1px solid {color}22;">
                <div style="font-size:11px;font-weight:700;color:{color};text-transform:uppercase;">{label}</div>
                <div style="font-size:28px;font-weight:800;color:{color};margin-top:4px;">{cnt}</div>
                <div style="font-size:11px;color:#64748b;margin-top:2px;">组</div>
            </div>''')

    # Build detail table
    points.sort(key=lambda x: x["effort"])
    detail_rows = []
    for p in points:
        qlabel, qcolor, qbg = QUADRANT_LABELS.get(p["quadrant"], ("", "#64748b", "#f1f5f9"))
        ach_color = "#10b981" if p["achieve"] >= 1.0 else ("#f59e0b" if p["achieve"] >= 0.85 else "#ef4444")
        eff_color = "#10b981" if p["effort"] >= 1.0 else ("#f59e0b" if p["effort"] >= 0.85 else "#ef4444")
        def _fv(v):
            return f"{v:.1%}" if v is not None and isinstance(v, (int, float)) else "-"
        def _fn(v):
            return f"{v:.1f}" if v is not None and isinstance(v, (int, float)) else "-"
        detail_rows.append(f'''
            <tr class="border-b last:border-0 hover:bg-slate-50">
                <td class="px-3 py-2 text-sm"><span class="font-medium text-slate-700">{p["group"]}</span><br/><span class="text-xs text-slate-400">{p["bucket"]}</span></td>
                <td class="px-3 py-2 text-right font-bold" style="color:{ach_color};">{p["achieve"]:.0%}</td>
                <td class="px-3 py-2 text-right font-bold" style="color:{eff_color};">{p["effort"]:.0%}</td>
                <td class="px-3 py-2 text-right text-sm text-slate-600">{_fv(p["cover"])}</td>
                <td class="px-3 py-2 text-right text-sm text-slate-600">{_fn(p["calls"])}</td>
                <td class="px-3 py-2 text-center"><span style="display:inline-block;padding:1px 6px;border-radius:8px;font-size:9px;font-weight:600;background:{qbg};color:{qcolor};">{qlabel}</span></td>
            </tr>''')

    import json as _json
    # Build scatter data for ECharts
    BUCKET_COLORS = {"S0": "#ef4444", "S1": "#f59e0b", "S2": "#8b5cf6", "M1": "#3b82f6", "M2": "#10b981", "M3": "#06b6d4", "M4": "#64748b"}
    scatter_series = {}
    for p in points:
        bk = p["bucket"]
        if bk not in scatter_series:
            scatter_series[bk] = []
        scatter_series[bk].append([
            round(p["effort"] * 100, 1),
            round(p["achieve"] * 100, 1),
            p["group"],
            p["parent"]
        ])
    scatter_json = _json.dumps(scatter_series, ensure_ascii=False)
    bucket_colors_json = _json.dumps(BUCKET_COLORS, ensure_ascii=False)

    return f'''
    <div class="card" style="padding:0;overflow:hidden;">
        <div style="padding:20px 24px;border-bottom:1px solid #e2e8f0;">
            <div class="flex items-center gap-2">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                <h3 class="text-lg font-bold text-slate-800" style="margin:0;">投入产出矩阵</h3>
                <span class="text-xs text-slate-400 ml-auto">勤奋度 = 覆盖率+拨打量 相对模块均值</span>
            </div>
        </div>

        <!-- Quadrant Summary -->
        <div style="padding:16px 24px;display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">
            {"".join(q_cards)}
        </div>

        <!-- Scatter Chart -->
        <div style="padding:4px 24px 16px;">
            <div id="chart-efficiency-scatter" style="width:100%;height:420px;"></div>
        </div>
        <script>
        (function() {{
            var scatterData = {scatter_json};
            var bucketColors = {bucket_colors_json};
            var dom = document.getElementById('chart-efficiency-scatter');
            if (!dom || typeof echarts === 'undefined') return;

            var chart = echarts.init(dom);
            var series = [];
            for (var bk in scatterData) {{
                series.push({{
                    name: bk,
                    type: 'scatter',
                    data: scatterData[bk].map(function(d) {{
                        return {{
                            value: [d[0], d[1]],
                            name: d[2],
                            parent: d[3]
                        }};
                    }}),
                    symbolSize: 14,
                    itemStyle: {{ color: bucketColors[bk] || '#64748b' }},
                    label: {{
                        show: true,
                        position: 'right',
                        formatter: function(p) {{ return p.data.name; }},
                        fontSize: 10,
                        color: '#475569'
                    }},
                    emphasis: {{
                        label: {{ fontSize: 12, fontWeight: 'bold' }},
                        itemStyle: {{ shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.2)' }}
                    }}
                }});
            }}
            /* Compute axis ranges from data */
            var allX = [], allY = [];
            for (var bk in scatterData) {{
                scatterData[bk].forEach(function(d) {{ allX.push(d[0]); allY.push(d[1]); }});
            }}
            var xMin = Math.max(0, Math.floor((Math.min.apply(null, allX) - 10) / 10) * 10);
            var xMax = Math.ceil((Math.max.apply(null, allX) + 10) / 10) * 10;
            var yMin = Math.max(0, Math.floor((Math.min.apply(null, allY) - 10) / 10) * 10);
            var yMax = Math.ceil((Math.max.apply(null, allY) + 10) / 10) * 10;

            var option = {{
                tooltip: {{
                    trigger: 'item',
                    formatter: function(p) {{
                        return '<b>' + p.data.name + '</b> (' + p.seriesName + ')<br/>'
                             + '\\u52e4\\u594b\\u5ea6: ' + p.value[0].toFixed(0) + '%<br/>'
                             + '\\u8fbe\\u6210\\u7387: ' + p.value[1].toFixed(0) + '%<br/>'
                             + p.data.parent;
                    }}
                }},
                legend: {{ top: 5, right: 10, textStyle: {{ fontSize: 11 }} }},
                grid: {{ left: 60, right: 40, top: 50, bottom: 55 }},
                xAxis: {{
                    name: '\\u52e4\\u594b\\u5ea6 (%)',
                    nameLocation: 'middle',
                    nameGap: 30,
                    nameTextStyle: {{ fontSize: 12, color: '#64748b' }},
                    min: xMin,
                    max: xMax,
                    axisLabel: {{ formatter: '{{value}}%' }},
                    splitLine: {{ show: true, lineStyle: {{ type: 'dashed', color: '#f1f5f9' }} }}
                }},
                yAxis: {{
                    name: '\\u8fbe\\u6210\\u7387 (%)',
                    nameLocation: 'middle',
                    nameGap: 40,
                    nameTextStyle: {{ fontSize: 12, color: '#64748b' }},
                    min: yMin,
                    max: yMax,
                    axisLabel: {{ formatter: '{{value}}%' }},
                    splitLine: {{ show: true, lineStyle: {{ type: 'dashed', color: '#f1f5f9' }} }}
                }},
                series: series
            }};
            /* Add quadrant markLines at 100% and 90% */
            if (series.length > 0) {{
                series[0].markLine = {{
                    silent: true,
                    lineStyle: {{ type: 'dashed', color: '#94a3b8', width: 1 }},
                    label: {{ show: true, fontSize: 10, color: '#94a3b8' }},
                    data: [
                        {{ xAxis: 100, label: {{ formatter: '\\u52e4\\u594b\\u57fa\\u51c6' }} }},
                        {{ yAxis: 90, label: {{ formatter: '\\u8fbe\\u6210\\u57fa\\u51c6 90%' }} }}
                    ]
                }};
                series[0].markArea = {{
                    silent: true,
                    data: [
                        [{{ xAxis: 'min', yAxis: 90, itemStyle: {{ color: 'rgba(16,185,129,0.04)' }} }}, {{ xAxis: 100, yAxis: 'max' }}],
                        [{{ xAxis: 100, yAxis: 90, itemStyle: {{ color: 'rgba(16,185,129,0.08)' }} }}, {{ xAxis: 'max', yAxis: 'max' }}],
                        [{{ xAxis: 'min', yAxis: 'min', itemStyle: {{ color: 'rgba(239,68,68,0.06)' }} }}, {{ xAxis: 100, yAxis: 90 }}],
                        [{{ xAxis: 100, yAxis: 'min', itemStyle: {{ color: 'rgba(245,158,11,0.06)' }} }}, {{ xAxis: 'max', yAxis: 90 }}]
                    ]
                }};
            }}
            chart.setOption(option);
            window.addEventListener('resize', function() {{ chart.resize(); }});
            /* Register for lazy init on tab switch */
            if (!window._effScatterChart) window._effScatterChart = chart;
        }})();
        </script>

        <!-- Detail Table -->
        <div style="padding:4px 24px 20px;">
            <div style="max-height:400px;overflow-y:auto;border:1px solid #e2e8f0;border-radius:8px;">
                <table class="w-full text-sm">
                    <thead class="sticky top-0"><tr class="bg-slate-50 text-slate-500 text-xs">
                        <th class="px-3 py-2 text-left">组</th>
                        <th class="px-3 py-2 text-right">达成率</th>
                        <th class="px-3 py-2 text-right">勤奋度</th>
                        <th class="px-3 py-2 text-right">覆盖率</th>
                        <th class="px-3 py-2 text-right">拨打量</th>
                        <th class="px-3 py-2 text-center">象限</th>
                    </tr></thead>
                    <tbody>{"".join(detail_rows)}</tbody>
                </table>
            </div>
        </div>
    </div>
    '''


def make_action_items(nm_data, process_detail, perf_data, ops_attr_data, vintage_anomalies, repay_anomalies, diag):
    """
    [v4.23] 智能诊断引擎 — 5类规则自动生成行动项。
    """
    items = []

    # ── Diagnosis 1 & 2: 低达成 + 低/高勤奋 ──
    for key, d in (diag or {}).items():
        pattern = d.get("pattern", "")
        ach = d["achieve"]
        cover = d.get("cover_rate")
        calls = d.get("call_times_avg")
        cover_avg = d.get("cover_rate_module_avg", 0)
        calls_avg = d.get("call_times_avg_module_avg", 0)

        def _metric_str():
            parts = []
            if cover is not None and cover_avg > 0:
                parts.append(f"覆盖率 {cover:.1%}(模块均值 {cover_avg:.1%})")
            if calls is not None and calls_avg > 0:
                parts.append(f"拨打量 {calls:.1f}(模块均值 {calls_avg:.1f})")
            return " | ".join(parts) if parts else ""

        if "mgmt_issue" in pattern:
            items.append({
                "priority": "high",
                "category": "管理问题",
                "cat_color": "#dc2626", "cat_bg": "#fee2e2",
                "title": f"{d['parent']} > {d['group']} — 达成率 {ach:.0%}，勤奋度低",
                "detail": _metric_str(),
                "action": "拨打量和覆盖率显著低于同模块平均，建议检查出勤和工作安排",
            })
        elif "strategy_issue" in pattern:
            items.append({
                "priority": "high",
                "category": "策略问题",
                "cat_color": "#9333ea", "cat_bg": "#f5f3ff",
                "title": f"{d['parent']} > {d['group']} — 达成率 {ach:.0%}，勤奋但低效",
                "detail": _metric_str(),
                "action": "拨打量正常但回收差，建议优化话术/策略，或排查案件质量",
            })

    # ── Diagnosis 3: 组内高方差 ──
    for key, d in (diag or {}).items():
        if "high_var" in d.get("pattern", ""):
            top_agent = d["agents"][0] if d["agents"] else None
            bot_agent = d["agents"][-1] if d["agents"] else None
            detail = f"组内标准差 {d['agent_variance']:.2f}"
            if top_agent and bot_agent:
                detail += f" | 最高: {top_agent['name']}({top_agent['achieve']:.0%}) vs 最低: {bot_agent['name']}({bot_agent['achieve']:.0%})"
            items.append({
                "priority": "medium",
                "category": "管理不均",
                "cat_color": "#7c3aed", "cat_bg": "#ede9fe",
                "title": f"{d['parent']} > {d['group']} — 经办间差异大（{d['agent_count']}人）",
                "detail": detail,
                "action": "组内经办表现分化严重，建议组长关注尾部经办，均衡案件分配",
            })

    # ── Diagnosis 4: 连续下滑（模块级月环比，同日对齐） ──
    if nm_data:
        level_data = nm_data.get("level_data", {})
        module_data = level_data.get("模块级", {})
        months = module_data.get("months", [])
        module_ts = module_data.get("data", {})
        module_summary = module_data.get("summary", {})

        if len(months) >= 2:
            for bucket, s in module_summary.items():
                # 取当月最新 day 作为对齐基准
                align_day = s.get("actual_day", 0)
                if align_day <= 0:
                    continue
                bdata = module_ts.get(bucket, {})
                recent_rates = []
                for m in sorted(months)[-3:]:
                    mdata = bdata.get(m, bdata.get(str(m), []))
                    if not mdata:
                        continue
                    # 找到 <= align_day 的最大 day 的 cum_rate（同日对齐）
                    aligned_rate = None
                    for pt in mdata:
                        if pt.get("day", 0) <= align_day:
                            aligned_rate = pt.get("cum_rate", 0)
                    if aligned_rate is not None:
                        recent_rates.append(aligned_rate)
                if len(recent_rates) >= 2:
                    declining = all(recent_rates[i] > recent_rates[i+1] for i in range(len(recent_rates)-1))
                    if declining:
                        items.append({
                            "priority": "high",
                            "category": "趋势恶化",
                            "cat_color": "#dc2626", "cat_bg": "#fee2e2",
                            "title": f"{bucket} 模块连续 {len(recent_rates)} 个月同期(Day {align_day})回收率下降",
                            "detail": " → ".join([f"{r:.2%}" for r in recent_rates]),
                            "action": "同日对齐后趋势仍在下降，建议立即排查原因，召开专项复盘",
                        })

    # ── Diagnosis 5: 明星经办 ──
    for key, d in (diag or {}).items():
        if "star" in d.get("pattern", ""):
            top_3 = d["agents"][:3] if d["agents"] else []
            star_names = [a["name"] for a in top_3 if a["achieve"] >= 1.1]
            if star_names:
                items.append({
                    "priority": "low",
                    "category": "标杆",
                    "cat_color": "#16a34a", "cat_bg": "#dcfce7",
                    "title": f"{d['parent']} > {d['group']} — 达成率 {d['achieve']:.0%}，表现优异",
                    "detail": f"标杆经办: {', '.join(star_names[:3])}",
                    "action": "建议提炼成功经验，组织分享带教",
                })

    # ── Overall gap (from ops_attr_data) ──
    if ops_attr_data:
        summary = ops_attr_data.get("summary", {})
        gap = summary.get("gap", 0)
        if gap < -0.02:
            items.insert(0, {
                "priority": "high",
                "category": "整体缺口",
                "cat_color": "#dc2626", "cat_bg": "#fee2e2",
                "title": f"整体目标缺口 {gap:+.2%}",
                "detail": f"当月回收率 {summary.get('overall_rate', 0):.2%}，目标 {summary.get('target_rate', 0):.2%}",
                "action": "建议召开运营复盘会议，制定追赶计划",
            })

    # ── Anomalies ──
    all_anomalies = (vintage_anomalies or []) + (repay_anomalies or [])
    for anom in all_anomalies[:5]:
        items.append({
            "priority": "medium",
            "category": "异常检测",
            "cat_color": "#d97706", "cat_bg": "#fef3c7",
            "title": str(anom),
            "detail": "",
            "action": "建议排查异常原因",
        })

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: priority_order.get(x["priority"], 9))
    items = items[:20]

    if not items:
        return f'''
        <div class="card">
            <div class="flex items-center gap-2 mb-4">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                <h3 class="text-lg font-bold text-slate-800" style="margin:0;">智能诊断</h3>
            </div>
            <div class="text-center py-8">
                <div style="font-size:40px;margin-bottom:8px;">&#10003;</div>
                <div class="text-slate-500">一切正常，暂无需要关注的行动项</div>
            </div>
        </div>'''

    # Render
    item_rows = []
    for item in items:
        p = item["priority"]
        if p == "high":
            p_badge = '<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;background:#fee2e2;color:#dc2626;">紧急</span>'
            border_color = "#ef4444"
        elif p == "medium":
            p_badge = '<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;background:#fef3c7;color:#d97706;">关注</span>'
            border_color = "#f59e0b"
        else:
            p_badge = '<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;background:#dcfce7;color:#16a34a;">参考</span>'
            border_color = "#10b981"

        cat = item.get("category", "")
        cat_color = item.get("cat_color", "#7c3aed")
        cat_bg = item.get("cat_bg", "#ede9fe")
        cat_badge = f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;background:{cat_bg};color:{cat_color};">{cat}</span>'
        detail_html = f'<div class="text-xs text-slate-500 mt-1">{item["detail"]}</div>' if item.get("detail") else ''

        item_rows.append(f'''
            <div style="border-left:3px solid {border_color};padding:12px 16px;margin-bottom:8px;background:#fafbfc;border-radius:0 8px 8px 0;">
                <div style="display:flex;align-items:center;gap:4px;margin-bottom:4px;">{p_badge} {cat_badge}</div>
                <div class="text-sm font-semibold text-slate-700">{item["title"]}</div>
                {detail_html}
                <div class="text-xs text-blue-600 mt-2" style="font-style:italic;">&#8594; {item["action"]}</div>
            </div>''')

    high_count = sum(1 for i in items if i["priority"] == "high")
    medium_count = sum(1 for i in items if i["priority"] == "medium")
    low_count = sum(1 for i in items if i["priority"] == "low")

    return f'''
    <div class="card" style="padding:0;overflow:hidden;">
        <div style="padding:20px 24px;border-bottom:1px solid #e2e8f0;display:flex;align-items:center;justify-content:space-between;">
            <div class="flex items-center gap-2">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                <h3 class="text-lg font-bold text-slate-800" style="margin:0;">智能诊断</h3>
            </div>
            <div style="display:flex;align-items:center;gap:6px;">
                {"" if high_count == 0 else f'<span style="display:inline-block;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:700;background:#fee2e2;color:#dc2626;">紧急 {high_count}</span>'}
                {"" if medium_count == 0 else f'<span style="display:inline-block;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:700;background:#fef3c7;color:#d97706;">关注 {medium_count}</span>'}
                {"" if low_count == 0 else f'<span style="display:inline-block;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:700;background:#dcfce7;color:#16a34a;">参考 {low_count}</span>'}
                <span class="text-xs text-slate-400">共 {len(items)} 项</span>
            </div>
        </div>
        <div style="padding:16px 24px;max-height:600px;overflow-y:auto;">
            {"".join(item_rows)}
        </div>
    </div>
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
    # v4.17 Shift-Share
    shift_share_data=None,
    # v4.21 Ops Attribution
    ops_attr_data=None,
    # v4.23 Process Detail
    process_detail=None,
    # v4.23 Smart Diagnostics
    smart_diag_data=None,
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

    # [v4.22] Removed: html_repay, html_process, html_anomalies (panels moved/removed)
    
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

    # [v4.22] Removed: html_perf (panel removed from Part 3)

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

    # [v4.17 NEW] Shift-Share 结构归因
    html_shift_share = make_shift_share_section(shift_share_data)

    # [v4.21 NEW] 运营归因 Treemap
    html_ops_attribution = make_ops_attribution_section(ops_attr_data) if ops_attr_data else ''

    # [v4.23 NEW] 智能诊断
    html_smart_diag = make_smart_diagnostics_section(smart_diag_data) if smart_diag_data else ''

    # [v4.23 NEW] Part 3 新板块 — 智能诊断版
    _diag = _build_group_diagnostics(nm_progress_data, process_detail, perf_data)
    html_target_dashboard = make_target_dashboard(nm_progress_data, ops_attr_data)
    html_agent_leaderboard = make_agent_leaderboard(nm_progress_data, process_detail, perf_data, _diag)
    html_efficiency_analysis = make_efficiency_analysis(nm_progress_data, process_detail, _diag)
    html_action_items = make_action_items(nm_progress_data, process_detail, perf_data, ops_attr_data, vintage_anomalies, repay_anomalies, _diag)

    # 6. Breakdown (v3.4: Multi-period Split)
    html_breakdown_section = make_breakdown_section_v3_4(
        bd_daily_all, bd_daily_new, bd_daily_old,
        bd_weekly_all, bd_weekly_new, bd_weekly_old,
        bd_monthly_all, bd_monthly_new, bd_monthly_old
    )

    # [v4.1] Removed Time Series Breakdown (Consolidated)

    # [v4.0 Restructure] Risk -> Repay -> Process

    # [v4.21+] Inline CDN resources for offline portability
    echarts_js = _get_cached_cdn("echarts")
    tailwind_js = _get_cached_cdn("tailwindcss")
    
    # NOTE: CDN content is inserted via str.replace() AFTER f-string formatting,
    # because the JS source contains { } which would conflict with f-string syntax.
    _ECHARTS_PLACEHOLDER = "/* __ECHARTS_INLINE_PLACEHOLDER__ */"
    _TAILWIND_PLACEHOLDER = "/* __TAILWIND_INLINE_PLACEHOLDER__ */"
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CashLoan Inspection Report {date_str} (v4.22)</title>
    <!-- [v4.21+] Inlined CDN resources for offline portability -->
    <script>{_ECHARTS_PLACEHOLDER}</script>
    <script>{_TAILWIND_PLACEHOLDER}</script>
    <style>
        body {{ font-family: 'Inter', system-ui, sans-serif; background: #f8fafc; color: #1e293b; padding-top: 52px; }}
        .card {{ background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 20px; margin-bottom: 24px; }}
        .tab-btn {{ padding: 6px 12px; border-radius: 6px; font-weight: 500; cursor: pointer; transition: all 0.2s; font-size: 14px; }}
        .tab-btn.active {{ background: #eff6ff; color: #2563eb; }}
        .tab-btn.hover {{ background: #f1f5f9; }}
        .hidden {{ display: none; }}
        .section-bar {{ width: 4px; height: 16px; background: #2563eb; border-radius: 2px; }}
        .section-title {{ font-size: 20px; font-weight: 800; color: #1e293b; margin: 32px 0 16px 0; display: flex; align-items: center; gap: 8px; scroll-margin-top: 60px; }}
        .section-title span {{ width: 24px; height: 24px; background: #3b82f6; color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; }}
        .hide-lift .lift-indicator {{ display: none !important; }}
        .lift-toggle {{ padding: 4px 10px; border-radius: 6px; font-size: 12px; cursor: pointer; border: 1px solid #cbd5e1; background: white; color: #64748b; transition: all 0.2s; }}
        .lift-toggle.active {{ background: #eff6ff; color: #2563eb; border-color: #93c5fd; }}
        /* [v4.14] Top Navigation Bar */
        .top-nav {{
            position: fixed; top: 0; left: 0; right: 0; z-index: 999;
            background: white; border-bottom: 1px solid #e2e8f0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }}
        .top-nav-inner {{
            max-width: 1400px; margin: 0 auto; padding: 0 24px;
            display: flex; align-items: center; height: 50px;
        }}
        .top-nav-title {{
            font-size: 15px; font-weight: 700; color: #1e293b;
            margin-right: 32px; white-space: nowrap;
        }}
        .top-nav-items {{
            display: flex; align-items: center; gap: 0; flex: 1;
        }}
        .top-nav-item {{
            display: flex; align-items: center; cursor: pointer;
            padding: 8px 0; position: relative; transition: color 0.2s;
            color: #64748b; font-size: 14px; font-weight: 500;
        }}
        .top-nav-item:hover {{ color: #1e293b; }}
        .top-nav-item.active {{ color: #1e293b; font-weight: 700; }}
        .top-nav-item.active::after {{
            content: ''; position: absolute; bottom: -1px; left: 0; right: 0;
            height: 2px; background: #3b82f6;
        }}
        .top-nav-num {{
            font-size: 13px; color: #94a3b8; margin-right: 6px; font-weight: 600;
        }}
        .top-nav-item.active .top-nav-num {{ color: #3b82f6; }}
        /* [v4.16b] Tab panel styles */
        .tab-panel {{ animation: tabFadeIn 0.3s ease-out; }}
        @keyframes tabFadeIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        .top-nav-sep {{
            flex: 1; border-bottom: 1px dotted #cbd5e1; margin: 0 16px;
            min-width: 30px; align-self: center;
        }}
        @media print {{
            .top-nav {{ display: none; }}
            body {{ padding-top: 0; }}
        }}
    </style>
</head>
<body class="p-6 max-w-[1400px] mx-auto">

    <!-- [v4.14] Top Navigation Bar -->
    <nav class="top-nav">
        <div class="top-nav-inner">
            <div class="top-nav-title">催收智检_CashLoan</div>
            <div class="top-nav-items">
                <a class="top-nav-item active" data-nav="part1" onclick="navTo('part1')">
                    <span class="top-nav-num">01</span>核心监控
                </a>
                <div class="top-nav-sep"></div>
                <a class="top-nav-item" data-nav="part2" onclick="navTo('part2')">
                    <span class="top-nav-num">02</span>归因与结构
                </a>
                <div class="top-nav-sep"></div>
                <a class="top-nav-item" data-nav="part3" onclick="navTo('part3')">
                    <span class="top-nav-num">03</span>运营效能
                </a>
            </div>
        </div>
    </nav>

    <!-- Header -->
    <div class="flex justify-between items-center mb-8">
        <div>
            <h1 class="text-2xl font-bold text-slate-800">CashLoan Inspection Report v4.22</h1>
            <p class="text-slate-500 mt-1">Generated: {date_str} | Source: {os.path.basename(excel_path) if excel_path else 'N/A'}</p>
        </div>
        <div class="text-right">
             <div class="text-sm font-medium text-slate-600">Overview</div>
             <div class="text-xs text-slate-400">Rows: V:{overview.get('vintage_rows',0)} R:{overview.get('repay_rows',0)}</div>
        </div>
    </div>

    <!-- [v4.18] Tab Panel Container — 重组: Part1核心监控 / Part2归因结构 / Part3运营 -->
    <!-- ═══════════════ Part 1: 核心监控 ═══════════════ -->
    <div class="tab-panel" id="panel-part1">
        <div class="section-title" id="part1"><span>1</span>核心监控 (Core Monitoring)</div>

        <!-- 1.0 KPI Cards (总览) -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {kpi_cards}
        </div>

        <!-- 1.1 Due Month Recovery Curve -->
        {html_dm_recovery}

        <!-- 1.2 Vintage Matrix -->
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
    </div>

    <!-- ═══════════════ Part 2: 归因与结构 ═══════════════ -->
    <div class="tab-panel" id="panel-part2" style="display:none;">
        <div class="section-title" id="part2"><span>2</span>归因与结构 (Attribution & Structure)</div>

        <!-- 2.1 [v4.19] 归因中心 (Shift-Share) — 核心模块 -->
        {html_shift_share}

        <!-- 2.2 结构透视 — 期限矩阵 -->
        {html_term_matrix}

        <!-- 2.3 结构透视 — 金额段热力图 & 多维拆解 -->
        {html_amount_heatmap}
        {html_breakdown_section}

        <!-- 2.4 可联性分析 (从 Part 3 迁移) -->
        {html_contact}
    </div>

    <!-- ═══════════════ Part 3: 运营效能 ═══════════════ -->
    <div class="tab-panel" id="panel-part3" style="display:none;">
        <div class="section-title" id="part3"><span>3</span>运营效能 (Operations & Efficiency)</div>

        <!-- [v4.22] Sub-tabs within Part 3 -->
        <div style="display:flex;gap:0;margin-bottom:20px;border-bottom:2px solid #e2e8f0;">
            <button class="p3-subtab active" data-p3tab="p3-progress" onclick="switchP3Tab('p3-progress')"
                style="padding:10px 24px;font-size:14px;font-weight:600;border:none;background:none;cursor:pointer;
                       color:#8b5cf6;border-bottom:3px solid #8b5cf6;margin-bottom:-2px;transition:all 0.2s;">
                回收进度
            </button>
            <button class="p3-subtab" data-p3tab="p3-attribution" onclick="switchP3Tab('p3-attribution')"
                style="padding:10px 24px;font-size:14px;font-weight:600;border:none;background:none;cursor:pointer;
                       color:#94a3b8;border-bottom:3px solid transparent;margin-bottom:-2px;transition:all 0.2s;">
                运营归因
            </button>
            <button class="p3-subtab" data-p3tab="p3-efficiency" onclick="switchP3Tab('p3-efficiency')"
                style="padding:10px 24px;font-size:14px;font-weight:600;border:none;background:none;cursor:pointer;
                       color:#94a3b8;border-bottom:3px solid transparent;margin-bottom:-2px;transition:all 0.2s;">
                效率与行动
            </button>
        </div>

        <!-- Sub-tab A: 回收进度 -->
        <div id="p3-progress" class="p3-tab-content">
            <!-- 3.1 Natural Month Recovery Progress (序时下钻) -->
            {html_nm_progress}

            <!-- 3.2 [v4.22] 目标追踪看板 -->
            {html_target_dashboard}

            <!-- 3.3 [v4.22] 经办排行榜 -->
            {html_agent_leaderboard}
        </div>

        <!-- Sub-tab B: 运营归因 -->
        <div id="p3-attribution" class="p3-tab-content" style="display:none;">
            {html_ops_attribution}
            {html_smart_diag}
        </div>

        <!-- Sub-tab C: 效率与行动 [v4.22] -->
        <div id="p3-efficiency" class="p3-tab-content" style="display:none;">
            <!-- 方法论说明 -->
            <div class="card" style="padding:0;overflow:hidden;margin-bottom:20px;border:1px solid #e0e7ff;">
                <div style="padding:16px 24px;background:linear-gradient(90deg,#eef2ff,#f5f3ff);border-bottom:1px solid #e0e7ff;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                        <span style="font-size:14px;font-weight:700;color:#4338ca;">诊断方法论</span>
                    </div>
                </div>
                <div style="padding:16px 24px;font-size:13px;color:#475569;line-height:1.8;">
                    <p style="margin:0 0 10px;"><b>投入产出矩阵</b>：横轴「勤奋度」= (覆盖率 / 模块均值 + 拨打量 / 模块均值) / 2，纵轴「达成率」= 实际回收 / 序时目标。同模块内对比，消除跨模块基数差异。</p>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
                        <div style="background:#f0fdf4;border-radius:8px;padding:10px 14px;border-left:3px solid #10b981;">
                            <b style="color:#059669;">全面优秀</b> (高投入 + 高达成)：标杆组，可提炼经验推广。
                        </div>
                        <div style="background:#dbeafe;border-radius:8px;padding:10px 14px;border-left:3px solid #3b82f6;">
                            <b style="color:#2563eb;">策略优秀</b> (低投入 + 高达成)：效率高，关注案件质量是否优于其他组。
                        </div>
                        <div style="background:#fee2e2;border-radius:8px;padding:10px 14px;border-left:3px solid #ef4444;">
                            <b style="color:#dc2626;">管理问题</b> (低投入 + 低达成)：拨打量/覆盖率低于均值，建议检查出勤和工作量。
                        </div>
                        <div style="background:#fef3c7;border-radius:8px;padding:10px 14px;border-left:3px solid #f59e0b;">
                            <b style="color:#d97706;">策略问题</b> (高投入 + 低达成)：很努力但效果差，建议优化话术策略或排查案件分配。
                        </div>
                    </div>
                    <p style="margin:0 0 6px;"><b>智能诊断规则</b>：</p>
                    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;">
                        <div style="background:#fef2f2;border-radius:6px;padding:8px 12px;font-size:12px;">
                            <span style="color:#dc2626;font-weight:700;">管理问题</span>：达成率 &lt; 85% 且 覆盖率或拨打量 &lt; 模块均值 80%
                        </div>
                        <div style="background:#f5f3ff;border-radius:6px;padding:8px 12px;font-size:12px;">
                            <span style="color:#9333ea;font-weight:700;">策略问题</span>：达成率 &lt; 85% 但 覆盖率和拨打量 ≥ 模块均值 95%
                        </div>
                        <div style="background:#ede9fe;border-radius:6px;padding:8px 12px;font-size:12px;">
                            <span style="color:#7c3aed;font-weight:700;">管理不均</span>：组内经办达成率标准差 &gt; 0.25
                        </div>
                        <div style="background:#fee2e2;border-radius:6px;padding:8px 12px;font-size:12px;">
                            <span style="color:#dc2626;font-weight:700;">趋势恶化</span>：连续 2+ 月同日(Day N)回收率环比下降
                        </div>
                        <div style="background:#dcfce7;border-radius:6px;padding:8px 12px;font-size:12px;">
                            <span style="color:#16a34a;font-weight:700;">标杆</span>：达成率连续 ≥ 110%，可提炼经验带教
                        </div>
                        <div style="background:#f1f5f9;border-radius:6px;padding:8px 12px;font-size:12px;">
                            <span style="color:#475569;font-weight:700;">同日对齐</span>：所有对比均取当月最新 Day 在历史月对齐
                        </div>
                    </div>
                </div>
            </div>

            <!-- 3.5 [v4.23] 投入产出矩阵 -->
            {html_efficiency_analysis}

            <!-- 3.6 [v4.23] 智能诊断 -->
            {html_action_items}
        </div>
    </div>

    <!-- Footer -->
    <div class="text-center text-slate-400 text-sm mt-8 pb-8">
        <p>Report System v4.22 | Maintainer: <strong>Mr. Yuan</strong></p>
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

        // [v4.16b] Lazy init: only render charts when their panel is visible
        // Part 1 is visible by default — init its charts
        // Part 2 trend chart: defer until panel is shown
        // Part 3 contact chart: defer until panel is shown

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

        /* [v4.21] Part 3 Sub-tab switching */
        window.switchP3Tab = function(tabId) {{
            // Hide all sub-tab contents
            document.querySelectorAll('.p3-tab-content').forEach(function(el) {{
                el.style.display = 'none';
            }});
            // Show selected
            var target = document.getElementById(tabId);
            if (target) target.style.display = 'block';
            // Update button styles
            document.querySelectorAll('.p3-subtab').forEach(function(btn) {{
                if (btn.dataset.p3tab === tabId) {{
                    btn.style.color = '#8b5cf6';
                    btn.style.borderBottom = '3px solid #8b5cf6';
                }} else {{
                    btn.style.color = '#94a3b8';
                    btn.style.borderBottom = '3px solid transparent';
                }}
            }});
            // Resize charts in the newly visible tab
            setTimeout(function() {{
                Object.values(charts).forEach(function(c) {{ c.resize(); }});
                if (tabId === 'p3-progress' && window._nmOverviewCharts) {{
                    window._nmOverviewCharts.forEach(function(c) {{ c.resize(); }});
                }}
                if (tabId === 'p3-attribution') {{
                    if (window._opsTreemapChart) window._opsTreemapChart.resize();
                    if (window._sdUpliftChart) window._sdUpliftChart.resize();
                }}
                if (tabId === 'p3-efficiency' && window._effScatterChart) {{
                    window._effScatterChart.resize();
                }}
            }}, 150);
        }};

        /* [v4.16b] Top Nav: Tab-based panel switching (replaces ScrollSpy) */
        var currentPanel = 'part1';
        var panelInitialized = {{ 'part1': true, 'part2': false, 'part3': false }};

        window.navTo = function(partId) {{
            if (partId === currentPanel) return;

            // Hide current panel
            var oldPanel = document.getElementById('panel-' + currentPanel);
            if (oldPanel) oldPanel.style.display = 'none';

            // Show new panel
            var newPanel = document.getElementById('panel-' + partId);
            if (newPanel) {{
                newPanel.style.display = 'block';
                // Re-trigger animation
                newPanel.style.animation = 'none';
                newPanel.offsetHeight; // force reflow
                newPanel.style.animation = '';
            }}

            // Update nav active state
            document.querySelectorAll('.top-nav-item[data-nav]').forEach(function(item) {{
                if (item.dataset.nav === partId) {{
                    item.classList.add('active');
                }} else {{
                    item.classList.remove('active');
                }}
            }});

            currentPanel = partId;

            // [v4.18] Lazy-init charts on first visit
            if (!panelInitialized[partId]) {{
                panelInitialized[partId] = true;
                // Init shift-share chart & contact chart if switching to Part 2
                if (partId === 'part2') {{
                    if (window._ssChart) setTimeout(function() {{ window._ssChart.resize(); }}, 150);
                    // [v4.22] Contact chart moved to Part 2
                    if (document.getElementById("chart-contact-trend") && !charts["chart-contact-trend"]) {{
                        initChart("chart-contact-trend", chartData["contact-trend"]);
                    }}
                }}
                // Init Part 3 charts
                if (partId === 'part3') {{
                    // [v4.21] Lazy-init overview charts on first Part 3 visit
                    if (window._nmRenderOverview && !window._nmOverviewRendered) {{
                        setTimeout(function() {{
                            window._nmRenderOverview();
                            window._nmOverviewRendered = true;
                        }}, 200);
                    }}
                }}
            }}

            // Resize all visible charts after panel switch
            setTimeout(function() {{
                Object.values(charts).forEach(function(c) {{ c.resize(); }});
                // Also resize nm overview charts if in Part 3
                if (partId === 'part3' && window._nmOverviewCharts) {{
                    window._nmOverviewCharts.forEach(function(c) {{ c.resize(); }});
                }}
            }}, 100);

            // Scroll to top
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }};

        // [v4.18] Part 1 now contains trend charts — init default view on load
        updateTrendView();
    </script>
</body>
</html>
"""
    # [v4.21+] Replace placeholders with actual CDN content (avoids f-string brace conflicts)
    html = html.replace(_ECHARTS_PLACEHOLDER, echarts_js)
    html = html.replace(_TAILWIND_PLACEHOLDER, tailwind_js)
    return html

def main():
    pass

if __name__ == "__main__":
    pass
