# -*- coding: utf-8 -*-
"""
Collection inspection - daily report (read local Excel -> metrics -> simple anomalies -> HTML).

Data: collection_inspection_data_local.xlsx in parent dir (from download script) or 0_basic_data.xlsx in Core.
Output: reports/Inspection_Report_YYYY-MM-DD.html
Sections: Risk overview, By product, By batch recovery, Contactability, Anomalies & recommendations.
"""
import os
import sys
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Paths: script under scripts/, project root is parent
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Data file candidates
LOCAL_EXCEL = PROJECT_ROOT / "collection_inspection_data_local.xlsx"
CORE_EXCEL = Path(r"D:\0_phirisk\11-Agent\Core_Digital_Assets\10-Collection_Inspection\0_basic_data.xlsx")


def find_excel():
    """Prefer local download file, then Core sample data."""
    if LOCAL_EXCEL.exists():
        return str(LOCAL_EXCEL)
    if CORE_EXCEL.exists():
        return str(CORE_EXCEL)
    return None


def read_sheet(path, sheet_name):
    """Read Excel sheet by name; return None if missing."""
    try:
        import pandas as pd
        df = pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")
        return df
    except Exception:
        return None


def compute_vintage_summary(df):
    """Vintage summary: rows by product and mean overdue rate when column exists."""
    if df is None or df.empty:
        return {}, []
    out = {}
    if "product" in df.columns:
        by_product = df.groupby("product").agg(
            rows=("product", "count")
        ).reset_index()
        for _, row in by_product.iterrows():
            out[str(row["product"])] = {"rows": int(row["rows"])}
    else:
        out["All"] = {"rows": len(df)}
    for col in ["overdue_rate", "dpd30", "dpd30_rate"]:
        if col in df.columns and str(df[col].dtype) in ["float64", "int64"]:
            if "product" in df.columns:
                means = df.groupby("product")[col].mean()
                for p, v in means.items():
                    if str(p) not in out:
                        out[str(p)] = {}
                    out[str(p)][col] = round(float(v), 4)
            else:
                out.setdefault("All", {})[col] = round(float(df[col].mean()), 4)
            break
    anomalies = []
    for p, v in out.items():
        if isinstance(v, dict) and v.get("overdue_rate", 0) > 0.5:
            anomalies.append(f"Product {p}: overdue_rate {v['overdue_rate']} exceeds threshold 0.5")
    return out, anomalies


def compute_repay_summary(df_list, names):
    """Recovery summary: row counts and mean repay_rate per table."""
    out = {}
    anomalies = []
    for df, name in zip(df_list, names):
        if df is None or df.empty:
            out[name] = {"rows": 0}
            continue
        out[name] = {"rows": len(df)}
        if "repay_rate" in df.columns and str(df["repay_rate"].dtype) in ["float64", "int64"]:
            r = float(df["repay_rate"].mean())
            out[name]["repay_rate"] = round(r, 4)
            if r < 0.1:
                anomalies.append(f"{name}: repay_rate {r} below threshold 0.1")
    return out, anomalies


def build_html(vintage_summary, repay_summary, vintage_anomalies, repay_anomalies, excel_path, date_str):
    """Build daily report HTML with sections: Risk overview, By product, By batch, Contactability, Anomalies."""
    all_anomalies = vintage_anomalies + repay_anomalies
    anomaly_html = "<br>".join(all_anomalies) if all_anomalies else "No anomalies."

    rows_v = []
    for p, v in (vintage_summary or {}).items():
        r = v.get("rows", "-")
        ov = v.get("overdue_rate", v.get("dpd30_rate", "-"))
        rows_v.append(f"<tr><td>{p}</td><td>{r}</td><td>{ov}</td></tr>")
    table_product = "\n".join(rows_v) if rows_v else "<tr><td colspan='3'>No data</td></tr>"

    rows_r = []
    for name, v in (repay_summary or {}).items():
        r = v.get("rows", "-")
        rr = v.get("repay_rate", "-")
        rows_r.append(f"<tr><td>{name}</td><td>{r}</td><td>{rr}</td></tr>")
    table_batch = "\n".join(rows_r) if rows_r else "<tr><td colspan='3'>No data</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Inspection Report {date_str}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 900px; margin: 0 auto; background: #fff; padding: 24px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 8px; }}
        h2 {{ color: #555; margin-top: 24px; border-left: 4px solid #4CAF50; padding-left: 10px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
        th {{ background: #f0f0f0; }}
        .meta {{ color: #666; font-size: 14px; margin-top: 20px; }}
        .anomaly {{ color: #c62828; }}
    </style>
</head>
<body>
<div class="container">
    <h1>Collection Inspection Daily Report</h1>
    <p class="meta">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Data source: {excel_path or 'None'}</p>

    <h2>1. Risk Overview</h2>
    <p>Scope: vintage risk + recovery rate. Data from local Excel; metrics by product/table; simple thresholds (overdue_rate &gt; 0.5, repay_rate &lt; 0.1).</p>

    <h2>2. By Product</h2>
    <table>
        <thead><tr><th>Product</th><th>Rows</th><th>Overdue rate / DPD30</th></tr></thead>
        <tbody>{table_product}</tbody>
    </table>

    <h2>3. By Batch (Recovery)</h2>
    <table>
        <thead><tr><th>Batch / Table</th><th>Rows</th><th>Repay rate</th></tr></thead>
        <tbody>{table_batch}</tbody>
    </table>

    <h2>4. Contactability</h2>
    <p>To be added; will show contact rate and send volume/success rate when touch data is available.</p>

    <h2>5. Anomalies &amp; Recommendations</h2>
    <div class="anomaly">{anomaly_html}</div>
</div>
</body>
</html>"""


def main():
    excel_path = find_excel()
    if not excel_path:
        print("Data file not found: run download script to produce collection_inspection_data_local.xlsx or place 0_basic_data.xlsx in Core dir.")
        html = build_html({}, {}, [], [], None, datetime.now().strftime("%Y-%m-%d"))
        out_path = REPORTS_DIR / f"Inspection_Report_{datetime.now().strftime('%Y-%m-%d')}.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"Placeholder report generated: {out_path}")
        input("Press Enter to close...")
        return

    print(f"Using data: {excel_path}")
    df_v = read_sheet(excel_path, "yya_vintage")
    df_cl = read_sheet(excel_path, "repay_cl")
    df_tt = read_sheet(excel_path, "repay_tt")

    vintage_summary, vintage_anomalies = compute_vintage_summary(df_v)
    repay_summary, repay_anomalies = compute_repay_summary(
        [df_cl, df_tt], ["repay_cl", "repay_tt"]
    )

    date_str = datetime.now().strftime("%Y-%m-%d")
    html = build_html(vintage_summary, repay_summary, vintage_anomalies, repay_anomalies, excel_path, date_str)
    out_path = REPORTS_DIR / f"Inspection_Report_{date_str}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Report generated: {out_path}")
    input("Press Enter to close...")


if __name__ == "__main__":
    main()
