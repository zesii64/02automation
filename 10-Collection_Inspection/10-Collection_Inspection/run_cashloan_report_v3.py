# -*- coding: utf-8 -*-
"""
CashLoan 巡检日报：vintage_risk = cashloan，先不分产品。
格式参照：WIKI/02_Report_Spec.md (及原周报模板)。
"""
import sys
import json
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REPORTS_DIR = SCRIPT_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR_EXCEL = SCRIPT_DIR / "data" / "collection_inspection_data_local.xlsx"
SAME_DIR_EXCEL = SCRIPT_DIR / "collection_inspection_data_local.xlsx"
LOCAL_EXCEL = PROJECT_ROOT / "collection_inspection_data_local.xlsx"
CORE_EXCEL = Path(r"D:\0_phirisk\11-Agent\Core_Digital_Assets\10-Collection_Inspection\0_basic_data.xlsx")


def find_excel():
    if DATA_DIR_EXCEL.exists():
        return str(DATA_DIR_EXCEL)
    if SAME_DIR_EXCEL.exists():
        return str(SAME_DIR_EXCEL)
    if LOCAL_EXCEL.exists():
        return str(LOCAL_EXCEL)
    if CORE_EXCEL.exists():
        return str(CORE_EXCEL)
    return None


def read_sheet(path, sheet_name):
    try:
        import pandas as pd
        return pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return None


def read_sheet_maybe_chunked(path, base_name):
    import re
    df = read_sheet(path, base_name)
    if df is None:
        return None
    try:
        import pandas as pd
        xl = pd.ExcelFile(path, engine="openpyxl")
        extra = [s for s in xl.sheet_names if re.match(r"^" + re.escape(base_name) + r"_\d+$", s)]
        if not extra:
            return df
        key = lambda s: int(s.split("_")[-1])
        chunks = [df] + [pd.read_excel(xl, sheet_name=s) for s in sorted(extra, key=key)]
        return pd.concat(chunks, ignore_index=True)
    except Exception:
        return df


def _compute_vintage_summary(df):
    from run_daily_report_v3 import compute_vintage_summary
    return compute_vintage_summary(df)


def _compute_repay_summary(df_list, names):
    from run_daily_report_v3 import compute_repay_summary
    return compute_repay_summary(df_list, names)


def _compute_process_summary(df):
    from run_daily_report_v3 import compute_process_summary
    return compute_process_summary(df)


def _compute_due_trend(df, max_days=21):
    from run_daily_report_v3 import compute_due_trend
    return compute_due_trend(df, max_days=max_days)


def build_cashloan_html(vintage_summary, repay_summary, process_summary, vintage_anomalies, repay_anomalies, excel_path, date_str, overview=None, repay_name="natural_month_repay", is_placeholder=False, 
                        trend_d=None, trend_w=None, trend_m=None,
                        trend_d_new=None, trend_w_new=None, trend_m_new=None,
                        trend_d_old=None, trend_w_old=None, trend_m_old=None,
                        matrix_daily=None, matrix_weekly=None, matrix_monthly=None,
                        lift_metrics=None,
                        matrix_all=None, matrix_new=None, matrix_old=None):
    """复刻周报格式：KPI 卡片、资产质量(含图表+矩阵)、策略执行、回收结果、异常、落款。"""
    all_anomalies = vintage_anomalies + repay_anomalies
    anomaly_html = "<br>".join(all_anomalies) if all_anomalies else "暂无异常。"

    placeholder_banner = ""
    if is_placeholder or not excel_path:
        placeholder_banner = """
        <div class="rounded-xl border-2 border-amber-300 bg-amber-50 p-4 mb-6 text-amber-800">
            <p class="font-semibold">【占位】未找到数据文件</p>
            <p class="text-sm mt-1">请将 <code class="bg-amber-100 px-1 rounded">collection_inspection_data_local.xlsx</code> 放入 <code class="bg-amber-100 px-1 rounded">10-Collection_Inspection/data/</code> 或与 <code class="bg-amber-100 px-1 rounded">run_cashloan_report.py</code> 同目录后重新运行脚本。</p>
        </div>"""

    v_all = (vintage_summary or {}).get("All", {})
    overdue_rate = v_all.get("overdue_rate", "-")
    dpd30 = v_all.get("dpd30", "-")
    v_rows = v_all.get("rows", 0)

    r_all = (repay_summary or {}).get(repay_name, {}) if repay_summary else {}
    repay_rate = r_all.get("repay_rate", "-")
    r_rows = r_all.get("rows", 0)
    breakdown = r_all.get("breakdown", [])
    bd_html = "<br>".join(breakdown) if breakdown else "-"

    ov = overview or {}
    n_v = ov.get("vintage_rows", "-")
    n_r = ov.get("repay_rows", "-")
    n_p = ov.get("process_rows", "-")
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. 资产质量 (Asset Quality)
    # 辅助函数：生成表格行
    def _make_rows(items, label_func=lambda k: k):
        rows = []
        for k, v in items:
            label = label_func(k)
            r = v.get("rows", 0)
            
            def fmt_metric(key, is_good_metric=False):
                val = v.get(key, "-")
                if not isinstance(val, (int, float)):
                    return "-"
                s_val = f"{val:.2%}"
                wow = v.get(f"{key}_wow")
                if wow is not None and isinstance(wow, (int, float)):
                    is_bad = False
                    is_good = False
                    if is_good_metric:
                        if wow > 0.05: is_good = True
                        elif wow < -0.05: is_bad = True
                    else:
                        if wow > 0.05: is_bad = True
                        elif wow < -0.05: is_good = True
                    color = "text-gray-400"
                    if is_bad: color = "text-danger"
                    elif is_good: color = "text-success"
                    arrow = "↑" if wow > 0 else "↓"
                    if abs(wow) > 0.01:
                        return f"{s_val} <span class='text-xs {color} ml-1'>{arrow} {abs(wow):.0%}</span>"
                return s_val

            ov = fmt_metric("overdue_rate", is_good_metric=False)
            d5 = fmt_metric("dpd5", is_good_metric=False)
            d30 = fmt_metric("dpd30", is_good_metric=False)
            cc = fmt_metric("connect_conversion", is_good_metric=True)
            pc = fmt_metric("ptp_conversion", is_good_metric=True)
            
            rows.append(
                f"<tr>"
                f"<td class='text-gray-700 pl-4'>{label}</td>"
                f"<td class='text-right data-cell'>{r}</td>"
                f"<td class='text-right data-cell'>{ov}</td>"
                f"<td class='text-right data-cell'>{d5}</td>"
                f"<td class='text-right data-cell'>{d30}</td>"
                f"<td class='text-right data-cell text-xs text-gray-500'>{cc}</td>"
                f"<td class='text-right data-cell text-xs text-gray-500'>{pc}</td>"
                f"</tr>"
            )
        return "\n".join(rows)

    groups = {"All": [], "User": [], "Model": [], "Period": [], "Amount": []}
    for k, v in vintage_summary.items():
        if k == "All": groups["All"].append((k, v))
        elif k.startswith("User:"): groups["User"].append((k, v))
        elif k.startswith("Model:"): groups["Model"].append((k, v))
        elif k.startswith("Period:"): groups["Period"].append((k, v))
        elif k.startswith("Amount:"): groups["Amount"].append((k, v))
        else: pass 

    asset_html_parts = []
    thead = """
    <thead class="bg-gray-50 border-b border-gray-200">
        <tr>
            <th class="text-left py-2 px-4 text-gray-700">Dimension</th>
            <th class="text-right py-2 px-4 text-gray-700">Rows</th>
            <th class="text-right py-2 px-4 text-gray-700">入催率</th>
            <th class="text-right py-2 px-4 text-gray-700">DPD5</th>
            <th class="text-right py-2 px-4 text-gray-700">DPD30</th>
            <th class="text-right py-2 px-4 text-gray-700">接通转化</th>
            <th class="text-right py-2 px-4 text-gray-700">PTP转化</th>
        </tr>
    </thead>"""

    if groups["All"]:
        rows = _make_rows(groups["All"], lambda k: "Overall (Last 7 Days)")
        asset_html_parts.append(f'<table class="w-full text-sm border border-gray-200 rounded-lg overflow-hidden mb-4">{thead}<tbody class="divide-y divide-gray-100">{rows}</tbody></table>')

    def _add_sub_table(title, group_key, clean_label=True):
        items = sorted(groups[group_key], key=lambda x: x[0]) 
        if items:
            rows = _make_rows(items, lambda k: k.split(": ")[1] if clean_label else k)
            asset_html_parts.append(f'<h3 class="text-sm font-semibold text-gray-800 mt-4 mb-2 ml-1">{title}</h3>')
            asset_html_parts.append(f'<table class="w-full text-sm border border-gray-200 rounded-lg overflow-hidden mb-2">{thead}<tbody class="divide-y divide-gray-100">{rows}</tbody></table>')

    _add_sub_table("按新老客 (User Type)", "User")
    _add_sub_table("按期数 (Period)", "Period")
    _add_sub_table("按模型 (Model Bin)", "Model")
    _add_sub_table("按金额段 (Amount)", "Amount")

    asset_content = "".join(asset_html_parts) if asset_html_parts else '<p class="text-gray-400">无数据</p>'

    # --- Trend Visualization (Chart + Table) ---
    def make_trend_block(trend_data, period_name, chart_id):
        if not trend_data:
            return f"<p class='text-gray-400 text-sm'>无 {period_name} 数据</p>"
        
        chart_data = trend_data[::-1]
        x_axis = [r.get("period_key", "") for r in chart_data]
        # [Fix]: 移除默认值 0，保留 None，让 ECharts 渲染为断点
        y_overdue = [r.get("overdue_rate") for r in chart_data]
        y_dpd5 = [r.get("dpd5") for r in chart_data]
        
        # Handle None in charts (ECharts handles null as gaps)
        
        chart_json = json.dumps({
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["入催率", "DPD5"]},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {"type": "category", "boundaryGap": False, "data": x_axis},
            "yAxis": {"type": "value", "axisLabel": {"formatter": "{value}"}},
            "series": [
                {"name": "入催率", "type": "line", "data": y_overdue, "itemStyle": {"color": "#DC2626"}, "smooth": True, "connectNulls": False},
                {"name": "DPD5", "type": "line", "data": y_dpd5, "itemStyle": {"color": "#2563EB"}, "smooth": True, "connectNulls": False}
            ]
        })

        t_rows = []
        for r in trend_data:
            pk = r.get("period_key", "")
            rows = r.get("rows", 0)
            ov = r.get("overdue_rate", "-")
            d5 = r.get("dpd5", "-")
            d30 = r.get("dpd30", "-")
            def p(v): return f"{v:.2%}" if isinstance(v, (int, float)) else "-"
            t_rows.append(f"<tr><td class='text-gray-700'>{pk}</td><td class='text-right data-cell'>{rows}</td><td class='text-right data-cell text-brand'>{p(ov)}</td><td class='text-right data-cell'>{p(d5)}</td><td class='text-right data-cell'>{p(d30)}</td></tr>")
        
        table_html = (
            f'<div class="mt-4"><table class="w-full text-sm border border-gray-200 rounded-lg overflow-hidden mb-2">'
            f'<thead class="bg-gray-50 border-b border-gray-200">'
            f'<tr><th class="text-left py-2 px-4 text-gray-700">Period</th><th class="text-right py-2 px-4 text-gray-700">Rows</th><th class="text-right py-2 px-4 text-gray-700">入催率</th><th class="text-right py-2 px-4 text-gray-700">DPD5</th><th class="text-right py-2 px-4 text-gray-700">DPD30</th></tr>'
            f'</thead><tbody class="divide-y divide-gray-100">{"".join(t_rows)}</tbody></table></div>'
        )

        return f"""
        <div id="{chart_id}" style="width: 100%; height: 300px;"></div>
        <script>
            (function() {{
                var chart = echarts.init(document.getElementById('{chart_id}'));
                chart.setOption({chart_json});
                window.addEventListener('resize', function() {{ chart.resize(); }});
            }})();
        </script>
        {table_html}
        """

    # Generate trends for All, New, Old
    trend_sections = {}
    for scope, (td, tw, tm) in {
        "all": (trend_d, trend_w, trend_m),
        "new": (trend_d_new, trend_w_new, trend_m_new),
        "old": (trend_d_old, trend_w_old, trend_m_old)
    }.items():
        trend_sections[scope] = {
            "d": make_trend_block(td, f"日趋势 ({scope})", f"chart-d-{scope}"),
            "w": make_trend_block(tw, f"周趋势 ({scope})", f"chart-w-{scope}"),
            "m": make_trend_block(tm, f"月趋势 ({scope})", f"chart-m-{scope}")
        }

    # [v3 Helper] Heatmap Color Generator
    def get_bg_color(val, min_val, max_val, is_inverse=False):
        """Generate heatmap color. inverse=True for Recovery (High is Good/Green)."""
        if val is None or min_val is None or max_val is None or min_val == max_val:
            return ""
        
        # Normalize 0..1
        try:
            ratio = (val - min_val) / (max_val - min_val)
        except ZeroDivisionError:
            ratio = 0.5

        if is_inverse: # Recovery: High is Green
            if ratio > 0.75: return "bg-emerald-100 text-emerald-800"
            if ratio > 0.5: return "bg-emerald-50 text-emerald-800"
            if ratio < 0.25: return "bg-red-50 text-red-800"
            return ""
        else: # Entrant: Low is Good (Green), High is Bad (Red)
            if ratio > 0.75: return "bg-red-100 text-red-800"
            if ratio > 0.5: return "bg-red-50 text-red-800"
            if ratio < 0.25: return "bg-emerald-50 text-emerald-800"
            return ""

    # [v3 Component] Lift Analysis Table
    lift_html = ""
    if lift_metrics and "current" in lift_metrics and "prev" in lift_metrics:
        curr = lift_metrics["current"]
        prev = lift_metrics["prev"]
        days = lift_metrics.get("days_progress", 0)
        
        def fmt_row(label, key, is_pct=True):
            v_c = curr.get(key)
            v_p = prev.get(key)
            s_c = f"{v_c:.2%}" if is_pct and v_c is not None else (f"{v_c:,.0f}" if v_c is not None else "-")
            s_p = f"{v_p:.2%}" if is_pct and v_p is not None else (f"{v_p:,.0f}" if v_p is not None else "-")
            
            diff_html = "-"
            if v_c is not None and v_p is not None and v_p != 0:
                diff = (v_c - v_p) / v_p
                color = "text-red-600" if diff > 0 else "text-green-600" # Default: Increase is Bad (Risk)
                if key == "owing": color = "text-gray-600" # Volume increase is neutral
                arrow = "↑" if diff > 0 else "↓"
                diff_html = f"<span class='{color} font-medium'>{arrow} {abs(diff):.1%}</span>"
            
            return f"<tr><td class='text-gray-600'>{label}</td><td class='text-right data-cell'>{s_c}</td><td class='text-right data-cell'>{s_p}</td><td class='text-right data-cell bg-gray-50'>{diff_html}</td></tr>"

        lift_html = f"""
        <div class="card p-5 mb-5">
            <div class="flex items-center gap-2 mb-4">
                <div class="section-bar accent"></div>
                <h2 class="font-semibold text-gray-900">二、MTD 环比分析 (Lift Analysis)</h2>
                <span class="text-xs text-gray-400 ml-2">对比周期：本月前 {days} 天 vs 上月同进度</span>
            </div>
            <table class="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
                <thead class="bg-gray-50 border-b border-gray-200">
                    <tr><th class="text-left py-2 px-4 text-gray-700">Metric</th><th class="text-right py-2 px-4 text-gray-700">Current MTD</th><th class="text-right py-2 px-4 text-gray-700">Last Month MTD</th><th class="text-right py-2 px-4 text-gray-700">Lift (MoM)</th></tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                    {fmt_row("入催体量 (Owing)", "owing", False)}
                    {fmt_row("入催率 (Entrant)", "entrant_rate", True)}
                    {fmt_row("DPD1 率 (Overdue)", "dpd1_rate", True)}
                    {fmt_row("DPD5 率 (Overdue)", "dpd5_rate", True)}
                </tbody>
            </table>
        </div>
        """

    # [v3 Component] Vintage Matrix with Heatmap
    def make_vintage_matrix_v3(matrix_data, title, period_label="Period"):
        if not matrix_data:
            return f"<p class='text-gray-400 text-sm'>无 {title} 数据</p>"
        
        # Calc Stats for Color (Group Scoped)
        ent_vals = [r["entrant_rate"] for r in matrix_data if r["entrant_rate"] is not None]
        min_ent, max_ent = (min(ent_vals), max(ent_vals)) if ent_vals else (None, None)
        
        # For columns, we calculate stats per column to be fair
        col_stats = {}
        for d in range(1, 31):
            key = f"D{d}"
            vals = [r["recovery"].get(key) for r in matrix_data if r["recovery"].get(key) is not None]
            if vals:
                col_stats[key] = (min(vals), max(vals))
            else:
                col_stats[key] = (None, None)

        show_days = [1,2,3,4,5,6,7,10,15,30]
        header_html = "".join([f"<th class='text-right py-2 px-2 text-gray-600 font-normal'>D{d}</th>" for d in show_days])
        
        rows = []
        for r in matrix_data:
            period = r["period"]
            ent = r["entrant_rate"]
            
            # Heatmap Color
            ent_cls = get_bg_color(ent, min_ent, max_ent, is_inverse=False)
            ent_cell = f"<td class='text-right data-cell {ent_cls} font-medium'>{ent:.2%}</td>"
            
            rec_cells = []
            for d in show_days:
                key = f"D{d}"
                val = r["recovery"].get(key)
                if val is None:
                    rec_cells.append("<td class='text-right data-cell bg-gray-50 text-gray-300'>-</td>")
                else:
                    c_min, c_max = col_stats.get(key, (None, None))
                    cls = get_bg_color(val, c_min, c_max, is_inverse=True)
                    rec_cells.append(f"<td class='text-right data-cell {cls}'>{val:.1%}</td>")
            
            rows.append(f"<tr><td class='text-gray-700 whitespace-nowrap font-mono text-xs'>{period}</td>{ent_cell}{''.join(rec_cells)}</tr>")
            
        return f"""
        <div class="overflow-x-auto">
            <table class="w-full text-xs border border-gray-200 rounded-lg mb-2">
                <thead class="bg-gray-50 border-b border-gray-200">
                    <tr>
                        <th class="text-left py-2 px-2 text-gray-700 sticky left-0 bg-gray-50">{period_label}</th>
                        <th class="text-right py-2 px-2 text-gray-700 font-semibold border-r border-gray-200">入催率</th>
                        {header_html}
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-100">
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
        """

    mat_d = make_vintage_matrix_v3(matrix_daily, "Daily", "Due Date")
    mat_w = make_vintage_matrix_v3(matrix_weekly, "Weekly", "Week")
    mat_m = make_vintage_matrix_v3(matrix_monthly, "Monthly", "Month")

    # 2. 策略执行 (Strategy Execution)
    exec_rows = []
    for k, v in process_summary.items():
        exec_rows.append(f"<tr><td class='text-gray-600'>{k}</td><td class='text-right data-cell'>{v.get('coverage_rate','-')}</td><td class='text-right data-cell'>{v.get('connect_rate','-')}</td><td class='text-right data-cell'>{v.get('intensity','-')}</td></tr>")
    exec_table = "\n".join(exec_rows) if exec_rows else "<tr><td colspan='4' class='text-center py-4 text-gray-400'>无过程数据 (process_data)</td></tr>"

    # 3. 回收结果 (Collection Outcome)
    repay_rows = []
    if repay_name in (repay_summary or {}):
        v = repay_summary[repay_name]
        repay_rows.append(f"<tr><td class='font-medium text-gray-900'>Overall</td><td class='text-right data-cell'>{v.get('rows',0)}</td><td class='text-right data-cell text-success'>{v.get('repay_rate','-')}</td><td class='text-gray-500 text-xs'>-</td></tr>")
        for bd in v.get("breakdown", []):
             repay_rows.append(f"<tr><td class='text-gray-600 pl-6'>Attribution (Worst)</td><td class='text-right data-cell'>-</td><td class='text-right data-cell text-danger'>{bd.split(': ')[1]}</td><td class='text-gray-500 text-xs'>{bd.split(': ')[0]}</td></tr>")
    repay_table = "\n".join(repay_rows) if repay_rows else "<tr><td colspan='4' class='text-center py-4 text-gray-400'>无回收数据</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CashLoan 巡检日报 (Strategic) {date_str}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    colors: {{
                        'brand': '#2563EB', 'brand-dark': '#1D4ED8', 'brand-light': '#DBEAFE',
                        'accent': '#EA580C', 'accent-light': '#FED7AA',
                        'success': '#059669', 'danger': '#DC2626', 'warning': '#D97706',
                    }},
                    fontFamily: {{ 'sans': ['Inter', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'] }}
                }}
            }}
        }};
    </script>
    <style>
        body {{ font-family: Inter, "Noto Sans SC", "Microsoft YaHei", sans-serif; background: linear-gradient(180deg, #F0F4F8 0%, #F8FAFC 100%); color: #111827; font-size: 14px; min-height: 100vh; padding: 28px 36px; }}
        .container {{ max-width: 1320px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03); }}
        .section-bar {{ width: 4px; height: 20px; background: linear-gradient(180deg, #2563EB 0%, #3B82F6 100%); border-radius: 2px; }}
        .section-bar.accent {{ background: linear-gradient(180deg, #EA580C 0%, #F97316 100%); }}
        .data-cell {{ font-variant-numeric: tabular-nums; font-weight: 500; }}
        .footer-block {{ margin-top: 32px; padding-top: 12px; border-top: 1px solid #E5E7EB; color: #6B7280; font-size: 13px; }}
        .tab-btn {{ cursor: pointer; padding: 8px 16px; border-radius: 8px; font-weight: 500; color: #6B7280; transition: all 0.2s; }}
        .tab-btn:hover {{ background-color: #F3F4F6; color: #111827; }}
        .tab-btn.active {{ background-color: #DBEAFE; color: #1D4ED8; }}
        /* For Matrix Table */
        th {{ font-size: 11px; }}
        td {{ font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="flex items-center justify-between rounded-xl bg-white border border-gray-200 shadow-sm px-5 py-4 mb-6">
            <h1 class="text-xl font-bold text-gray-900">CashLoan 巡检日报 (Strategic View)</h1>
            <span class="text-sm text-gray-500">{date_str}</span>
        </div>
        {placeholder_banner}

        <!-- Section 1: Due Trends -->
        <div class="card p-5 mb-5">
            <div class="flex items-center gap-2 mb-4">
                <div class="section-bar accent"></div>
                <h2 class="font-semibold text-gray-900">一、资产质量趋势 (Due Trends)</h2>
            </div>
            
            <!-- Top Tabs: Overall / New / Old -->
            <div class="flex space-x-2 mb-4 border-b border-gray-100 pb-2">
                <div id="btn-trend-all" class="tab-btn active" onclick="switchTab('trend-all', 'btn-trend-all', 'trend-scope-tabs')">Overall</div>
                <div id="btn-trend-new" class="tab-btn" onclick="switchTab('trend-new', 'btn-trend-new', 'trend-scope-tabs')">新客 (New)</div>
                <div id="btn-trend-old" class="tab-btn" onclick="switchTab('trend-old', 'btn-trend-old', 'trend-scope-tabs')">老客 (Old)</div>
            </div>

            <!-- Content Area for Each Scope -->
            <div id="trend-all" class="tab-content-trend-scope-tabs block">
                <div class="flex space-x-2 mb-2 bg-gray-50 p-1 rounded inline-block">
                    <button class="px-3 py-1 text-xs font-medium rounded bg-white shadow text-gray-800" onclick="toggleSubTab('all-d', 'trend-all')">Daily</button>
                    <button class="px-3 py-1 text-xs font-medium rounded text-gray-500 hover:text-gray-800" onclick="toggleSubTab('all-w', 'trend-all')">Weekly</button>
                    <button class="px-3 py-1 text-xs font-medium rounded text-gray-500 hover:text-gray-800" onclick="toggleSubTab('all-m', 'trend-all')">Monthly</button>
                </div>
                <div id="sub-all-d" class="sub-tab-content block">{trend_sections['all']['d']}</div>
                <div id="sub-all-w" class="sub-tab-content hidden">{trend_sections['all']['w']}</div>
                <div id="sub-all-m" class="sub-tab-content hidden">{trend_sections['all']['m']}</div>
            </div>

            <div id="trend-new" class="tab-content-trend-scope-tabs hidden">
                <div class="flex space-x-2 mb-2 bg-gray-50 p-1 rounded inline-block">
                    <button class="px-3 py-1 text-xs font-medium rounded bg-white shadow text-gray-800" onclick="toggleSubTab('new-d', 'trend-new')">Daily</button>
                    <button class="px-3 py-1 text-xs font-medium rounded text-gray-500 hover:text-gray-800" onclick="toggleSubTab('new-w', 'trend-new')">Weekly</button>
                    <button class="px-3 py-1 text-xs font-medium rounded text-gray-500 hover:text-gray-800" onclick="toggleSubTab('new-m', 'trend-new')">Monthly</button>
                </div>
                <div id="sub-new-d" class="sub-tab-content block">{trend_sections['new']['d']}</div>
                <div id="sub-new-w" class="sub-tab-content hidden">{trend_sections['new']['w']}</div>
                <div id="sub-new-m" class="sub-tab-content hidden">{trend_sections['new']['m']}</div>
            </div>

            <div id="trend-old" class="tab-content-trend-scope-tabs hidden">
                <div class="flex space-x-2 mb-2 bg-gray-50 p-1 rounded inline-block">
                    <button class="px-3 py-1 text-xs font-medium rounded bg-white shadow text-gray-800" onclick="toggleSubTab('old-d', 'trend-old')">Daily</button>
                    <button class="px-3 py-1 text-xs font-medium rounded text-gray-500 hover:text-gray-800" onclick="toggleSubTab('old-w', 'trend-old')">Weekly</button>
                    <button class="px-3 py-1 text-xs font-medium rounded text-gray-500 hover:text-gray-800" onclick="toggleSubTab('old-m', 'trend-old')">Monthly</button>
                </div>
                <div id="sub-old-d" class="sub-tab-content block">{trend_sections['old']['d']}</div>
                <div id="sub-old-w" class="sub-tab-content hidden">{trend_sections['old']['w']}</div>
                <div id="sub-old-m" class="sub-tab-content hidden">{trend_sections['old']['m']}</div>
            </div>
        </div>

        {lift_html}

        <!-- Section 3: Vintage Matrix (Multi-dim + Heatmap) -->
        <div class="card p-5 mb-5">
            <div class="flex items-center gap-2 mb-4">
                <div class="section-bar accent"></div>
                <h2 class="font-semibold text-gray-900">三、Vintage 矩阵 (Entrant & Recovery)</h2>
            </div>
            <p class="text-xs text-gray-500 mb-3">说明：入催率 = 入催本金/应还本金；Dx = 1 - (Dx本金/入催本金) [催回率]。颜色反映该时间周期内的相对表现。</p>
            
            <div class="flex space-x-2 mb-4 border-b border-gray-100 pb-2">
                <div id="btn-mat-d" class="tab-btn active" onclick="switchTab('mat-d', 'btn-mat-d', 'mat-tabs')">Daily</div>
                <div id="btn-mat-w" class="tab-btn" onclick="switchTab('mat-w', 'btn-mat-w', 'mat-tabs')">Weekly</div>
                <div id="btn-mat-m" class="tab-btn" onclick="switchTab('mat-m', 'btn-mat-m', 'mat-tabs')">Monthly</div>
            </div>

            <div id="mat-d" class="tab-content-mat-tabs block">{mat_d}</div>
            <div id="mat-w" class="tab-content-mat-tabs hidden">{mat_w}</div>
            <div id="mat-m" class="tab-content-mat-tabs hidden">{mat_m}</div>
        </div>

        <!-- Section 4: Breakdown -->
        <div class="card p-5 mb-5">
            <div class="flex items-center gap-2 mb-4">
                <div class="section-bar accent"></div>
                <h2 class="font-semibold text-gray-900">四、维度拆解 (Breakdown)</h2>
            </div>
            <p class="text-xs text-gray-500 mt-2 mb-3">说明：基于最近 7 天 Due 数据与上期对比。</p>
            {asset_content}
        </div>

        <!-- Section 5: Process & Outcome -->
        <div class="grid grid-cols-2 gap-5 mb-5">
            <div class="card p-5">
                <div class="flex items-center gap-2 mb-4">
                    <div class="section-bar"></div>
                    <h2 class="font-semibold text-gray-900">五、策略执行</h2>
                </div>
                <table class="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
                    <thead class="bg-gray-50 border-b border-gray-200">
                        <tr><th class="text-left py-2 px-4 text-gray-700">Segment</th><th class="text-right py-2 px-4 text-gray-700">Cov%</th><th class="text-right py-2 px-4 text-gray-700">Conn%</th></tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100">{exec_table}</tbody>
                </table>
            </div>
            <div class="card p-5">
                <div class="flex items-center gap-2 mb-4">
                    <div class="section-bar"></div>
                    <h2 class="font-semibold text-gray-900">六、回收结果</h2>
                </div>
                <table class="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
                    <thead class="bg-gray-50 border-b border-gray-200">
                        <tr><th class="text-left py-2 px-4 text-gray-700">Dim</th><th class="text-right py-2 px-4 text-gray-700">Rows</th><th class="text-right py-2 px-4 text-gray-700">Repay%</th></tr>
                    </thead>
                    <tbody class="divide-y divide-gray-100">{repay_table}</tbody>
                </table>
            </div>
        </div>

        <!-- Section 6: Anomalies -->
        <div class="card p-5 mb-5">
            <div class="flex items-center gap-2 mb-4">
                <div class="section-bar bg-danger"></div>
                <h2 class="font-semibold text-gray-900">七、异常数据检查</h2>
            </div>
            <div class="text-sm text-danger font-medium bg-red-50 p-3 rounded-lg border border-red-100">{anomaly_html}</div>
        </div>

        <div class="footer-block">
            <p>报告生成时间：{gen_time}</p>
            <p>数据源：{excel_path or 'None'}</p>
            <p><strong>维护者</strong>：Mr. Yuan</p>
        </div>
    </div>
    
    <script>
        // Main Tab Switcher
        function switchTab(contentId, btnId, groupClass) {{
            document.querySelectorAll('.tab-content-' + groupClass).forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.tab-content-' + groupClass).forEach(el => el.classList.remove('block'));
            
            var btn = document.getElementById(btnId);
            btn.parentElement.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            
            document.getElementById(contentId).classList.remove('hidden');
            document.getElementById(contentId).classList.add('block');
            document.getElementById(btnId).classList.add('active');
            
            // Resize charts in target
            var chartDom = document.getElementById(contentId).querySelector('div[id^="chart-"]');
            if(chartDom) {{
                var chart = echarts.getInstanceByDom(chartDom);
                if(chart) chart.resize();
            }}
            
            // If opening a scope tab (e.g. trend-all), also ensure sub-tab chart is resized
            if(groupClass === 'trend-scope-tabs') {{
                // Find visible sub-tab inside contentId
                var visibleSub = document.getElementById(contentId).querySelector('.sub-tab-content.block div[id^="chart-"]');
                if(visibleSub) {{
                     var c = echarts.getInstanceByDom(visibleSub);
                     if(c) c.resize();
                }}
            }}
        }}

        // Sub Tab Switcher (Daily/Weekly/Monthly)
        function toggleSubTab(targetId, parentId) {{
            // Hide all sub-tabs in parent
            var parent = document.getElementById(parentId);
            parent.querySelectorAll('.sub-tab-content').forEach(el => el.classList.add('hidden'));
            parent.querySelectorAll('.sub-tab-content').forEach(el => el.classList.remove('block'));
            
            // Update buttons style
            // Note: simple implementation assumes button is previous sibling container
            // Reset all buttons in the button container
            var btnContainer = parent.querySelector('div.flex'); 
            btnContainer.querySelectorAll('button').forEach(btn => {{
                btn.className = "px-3 py-1 text-xs font-medium rounded text-gray-500 hover:text-gray-800";
            }});
            
            // Set active button style (event.target)
            event.target.className = "px-3 py-1 text-xs font-medium rounded bg-white shadow text-gray-800";

            // Show target
            var target = document.getElementById('sub-' + targetId);
            target.classList.remove('hidden');
            target.classList.add('block');
            
            // Resize
            var chartDom = target.querySelector('div[id^="chart-"]');
            if(chartDom) {{
                var chart = echarts.getInstanceByDom(chartDom);
                if(chart) chart.resize();
            }}
        }}
    </script>
</body>
</html>"""


def main():
    pass

if __name__ == "__main__":
    pass
