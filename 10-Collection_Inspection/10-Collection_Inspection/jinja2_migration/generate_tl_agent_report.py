"""生成含 TL Agent Tab 的测试报告，供人工抽检。"""
from pathlib import Path
import sys
import json

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from data_prep import build_context
from renderer import _build_environment

BASE = Path(__file__).parent.parent
EXCEL = BASE / 'data/260318_output_automation_v3.xlsx'
PROCESS_TARGET = BASE / 'data/process_data_target.xlsx'
OUTPUT = BASE / 'reports/tl_agent_tab_test.html'


def json_dumps(data):
    """Serialize to JSON, handling datetime and other types."""
    return json.dumps(data, default=str, ensure_ascii=False)


def main():
    print("Building context...")
    ctx = build_context(str(EXCEL), str(PROCESS_TARGET))

    print("Rendering tl_agent tab...")
    env = _build_environment()
    template = env.get_template('tl_agent/_index.html.j2')
    html = template.render(**ctx)

    # Serialize REAL_DATA to JavaScript
    real_data_js = f"const REAL_DATA = {json_dumps(ctx)};"

    # Helper functions needed by TL tab
    helper_funcs = """
// Helper functions
function formatNumber(n) {
    if (n === null || n === undefined) return '--';
    return Number(n).toLocaleString('en-US', {maximumFractionDigits: 0});
}

function getBreakdownUiText() {
    return {
        dimension: 'Dimension',
        principal: 'Principal Band',
        overdue: 'Overdue Stage',
        show: 'Show Breakdown',
        hide: 'Hide Breakdown',
        owingSharePivot: 'Owing Share Pivot',
        repayRatePivot: 'Repay Rate Pivot',
        noTlData: 'No breakdown data for selected date.',
        noStlData: 'No STL breakdown data.',
        noStlTable: 'No STL breakdown table.'
    };
}

var currentLang = 'en';
var tlChart = null;
"""

    # Wrap in minimal HTML shell for testing
    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TL Agent Tab Test</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; }}
        .tab-content {{ display: block; }}
        .card {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 16px; background: #fff; }}
        .metric-card {{ background: #f8fafc; border-radius: 8px; padding: 12px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: 700; color: #1e293b; }}
        .metric-label {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
        .status-badge {{ display: inline-block; padding: 4px 12px; border-radius: 16px; font-size: 12px; font-weight: 600; }}
        .status-success {{ background: #dcfce7; color: #16a34a; }}
        .status-danger {{ background: #fee2e2; color: #dc2626; }}
        select {{ padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px; }}
        .drilldown-row {{ border-bottom: 1px solid #f1f5f9; }}
        .red-row {{ background: #fef2f2 !important; }}
        .yellow-row {{ background: #fffbeb !important; }}
        .empty-state {{ padding: 40px; text-align: center; color: #64748b; }}
        .empty-state-icon {{ font-size: 48px; margin-bottom: 16px; }}
        .empty-state-title {{ font-size: 18px; font-weight: 600; margin-bottom: 8px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #f8fafc; padding: 12px; text-align: left; font-size: 12px; color: #64748b; border-bottom: 2px solid #e2e8f0; }}
        td {{ padding: 12px; font-size: 13px; border-bottom: 1px solid #f1f5f9; }}
        .chart-container {{ height: 300px; }}
    </style>
</head>
<body>
    <h1>TL Agent Tab Test Report</h1>
    <p>Data Date: {ctx.get('dataDate', 'N/A')}</p>
    <hr>

    {html}

    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <script>
    // ===================== REAL_DATA =====================
    {real_data_js}

    // ===================== HELPERS =====================
    {helper_funcs}

    // Initialize on load
    window.onload = function() {{
        if (typeof initTLTab === 'function') {{
            initTLTab();
        }}
    }};
    </script>
</body>
</html>"""

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(full_html, encoding='utf-8')
    print(f"Report saved to: {OUTPUT}")
    print(f"Open in browser to test TL Agent Tab functionality")

if __name__ == '__main__':
    main()
