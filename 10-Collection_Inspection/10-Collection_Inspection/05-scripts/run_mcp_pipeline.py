"""
MCP Pipeline entry point — Calls MaxCompute via MCP HTTP, generates HTML report.

Usage:
    python run_mcp_pipeline.py

Dependencies (set env vars before running):
    ALIYUN_ACCESS_KEY_ID
    ALIYUN_ACCESS_KEY_SECRET
"""
from __future__ import print_function

import os
import sys
import requests
from datetime import datetime, timedelta
import calendar

# ---- Paths ----
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "generate_v2_7_package", "data")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "generate_v2_7_package", "reports")
sys.path.insert(0, PROJECT_ROOT)

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


def _report_path():
    """Generate HTML report output path."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return os.path.join(REPORTS_DIR, "Collection_Operations_Report_v3_6_%s.html" % REPORT_DATE)


def _latest_report():
    """Find the most recently generated report file in reports dir."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    prefix = "Collection_Operations_Report_v3_6_"
    files = [f for f in os.listdir(REPORTS_DIR) if f.startswith(prefix) and f.endswith(".html")]
    if not files:
        return ""
    # Sort by modification time, newest first
    full_paths = [(os.path.join(REPORTS_DIR, f), f) for f in files]
    full_paths.sort(key=lambda x: os.path.getmtime(x[0]), reverse=True)
    return full_paths[0][0]


# ---- QYWX Robot Config ----
QYWX_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=b8b153b3-7155-4e4e-a8e6-971354ea2731"


def _qywx_upload_file(filepath):
    """Upload file to QYWX robot, return media_id."""
    try:
        from requests_toolbelt import MultipartEncoder
        from urllib import parse
    except ImportError:
        print("  [SKIP] requests_toolbelt not installed, QYWX notification disabled")
        return ""

    webHookUrl = QYWX_WEBHOOK
    params = parse.parse_qs(parse.urlparse(webHookUrl).query)
    webHookKey = params["key"][0]
    upload_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key=%s&type=file" % webHookKey

    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    filename = os.path.basename(filepath)
    try:
        multipart = MultipartEncoder(
            fields={
                "filename": filename,
                "filelength": "",
                "name": "media",
                "media": (filename, open(filepath, "rb"), "application/octet-stream"),
            },
            boundary="-------------------------acebdf13572468",
        )
        headers["Content-Type"] = multipart.content_type
        resp = requests.post(upload_url, headers=headers, data=multipart)
        json_res = resp.json()
        if json_res.get("media_id"):
            return json_res.get("media_id")
    except Exception as e:
        print("  [WARN] QYWX upload failed: %s" % e)
    return ""


def _qywx_send_file(filepath):
    """Send file via QYWX group robot."""
    media_id = _qywx_upload_file(filepath)
    if not media_id:
        print("  [WARN] QYWX: no media_id, skip sending")
        return False

    url = QYWX_WEBHOOK
    headers = {"Content-Type": "application/json"}
    msg = {"msgtype": "file", "file": {"media_id": media_id}}
    try:
        requests.post(url, headers=headers, json=msg)
        print("  [OK] QYWX notification sent")
        return True
    except Exception as e:
        print("  [WARN] QYWX send failed: %s" % e)
        return False


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

    excel_path = _excel_path()
    report_path = _latest_report()

    print("=" * 60)
    print("  Phase 3: Send QYWX Notification")
    print("=" * 60)
    if report_path and os.path.exists(report_path):
        print("  Sending HTML report to QYWX group robot...")
        _qywx_send_file(report_path)
    else:
        print("  [SKIP] No report file found to send")
    print()
    print("=" * 60)
    print("  All phases completed successfully!")
    print("  Excel : %s" % excel_path)
    print("  Report: %s" % report_path)
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