"""
MCP Pipeline entry point — Calls MaxCompute via MCP HTTP, generates HTML report.

Usage:
    python run_mcp_pipeline.py
    # Auto-uses date range: 1st of current month ~ yesterday

Dependencies (set env vars before running):
    ALIYUN_ACCESS_KEY_ID
    ALIYUN_ACCESS_KEY_SECRET
"""
from __future__ import print_function

import os
import sys

# ---- Paths ----
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "generate_v2_7_package", "data")
sys.path.insert(0, PROJECT_ROOT)

from datetime import datetime, timedelta
import calendar

# ---- Dynamic date range: past 3 weeks ~ end of current month ----
today = datetime.now()
DT_START = (today - timedelta(days=21)).strftime("%Y-%m-%d")
_last_day = calendar.monthrange(today.year, today.month)[1]
DT_END   = datetime(today.year, today.month, _last_day).strftime("%Y-%m-%d")
CHUNK_DAYS = 2  # MCP single query limit is 1000 rows; 2-day chunks reduce truncation risk
REPORT_DATE = DT_END  # report data date = data cutoff date


def _load_keys_from_file():
    """Fallback: parse AccessKey from accesskey.txt in project root."""
    key_file = os.path.join(PROJECT_ROOT, "accesskey.txt")
    if not os.path.exists(key_file):
        return
    try:
        with open(key_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("AccessKey ID:"):
                    val = line.split(":", 1)[1].strip()
                    if val and not os.environ.get("ALIYUN_ACCESS_KEY_ID"):
                        os.environ["ALIYUN_ACCESS_KEY_ID"] = val
                elif line.startswith("AccessKey Secret:"):
                    val = line.split(":", 1)[1].strip()
                    if val and not os.environ.get("ALIYUN_ACCESS_KEY_SECRET"):
                        os.environ["ALIYUN_ACCESS_KEY_SECRET"] = val
    except Exception:
        pass


def _check_env():
    """Check required env vars, load from file if missing, raise RuntimeError if still missing."""
    _load_keys_from_file()
    missing = []
    if not os.environ.get("ALIYUN_ACCESS_KEY_ID"):
        missing.append("ALIYUN_ACCESS_KEY_ID")
    if not os.environ.get("ALIYUN_ACCESS_KEY_SECRET"):
        missing.append("ALIYUN_ACCESS_KEY_SECRET")
    if missing:
        raise RuntimeError(
            "Missing env vars: %s\n"
            "Run: set ALIYUN_ACCESS_KEY_ID=... && set ALIYUN_ACCESS_KEY_SECRET=..."
            % ", ".join(missing)
        )


def _excel_path():
    """Generate Excel output path (consistent with pipeline_zip version)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, "260318_output_automation_v3.xlsx")


def run_extraction():
    """Phase 1: Extract data via MCP HTTP into Excel."""
    from generate_v2_7_package.pipeline_zip import extract_data_mcp

    excel_path = _excel_path()
    print("=" * 60)
    print("  Phase 1: Data Extraction (MCP HTTP)")
    print("  Date range: %s ~ %s" % (DT_START, DT_END))
    print("=" * 60)
    print()

    extract_data_mcp.main(DT_START, DT_END, excel_path, chunk_days=CHUNK_DAYS)

    # Phase 2: generate HTML report (module-level execution)
    # generate_v2_7.py has no def main() — it runs at import time via module-level code
    scripts_dir = os.path.join(PROJECT_ROOT, "generate_v2_7_package", "05-scripts")
    sys.path.insert(0, scripts_dir)
    print()
    print("=" * 60)
    print("  Phase 2: Generate HTML Report")
    print("  Report date: %s" % REPORT_DATE)
    print("=" * 60)
    print()
    import generate_v2_7  # noqa: F401 — runs at import, outputs HTML


def main():
    _check_env()
    run_extraction()
    print("=" * 60)
    print("  All phases completed successfully!")
    print("  Report: %s" % (
        os.path.join(PROJECT_ROOT, "generate_v2_7_package", "reports",
                     "Collection_Operations_Report_v3_6_%s.html" % REPORT_DATE)
    ))
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    finally:
        # Skip interactive pause when running headless (e.g., Task Scheduler)
        if sys.stdin.isatty():
            try:
                raw_input("Press Enter to close window...")
            except Exception:
                pass