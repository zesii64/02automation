"""dump_full_snapshot.py — 运行 build_context 并 dump 完整 real_data 到 fixture。

输出：tests/fixtures/real_data_baseline.json（已 gitignore 不进版本库）
L1 context lock：后续测试通过 deep-equal 与 fixture 对比，确保 data_prep 无回归。

Usage:
    cd jinja2_migration
    python dump_full_snapshot.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from data_prep import build_context  # noqa: E402

EXCEL_PATH = PROJECT_ROOT / "data" / "260318_output_automation_v3.xlsx"
PROCESS_TARGET_PATH = PROJECT_ROOT / "data" / "process_data_target.xlsx"
FIXTURE_DIR = HERE / "tests" / "fixtures"
OUT_PATH = FIXTURE_DIR / "real_data_baseline.json"


class SafeEncoder(json.JSONEncoder):
    """NaN → null, Inf → null, Decimal → float 的 Safe JSON Encoder。"""

    def default(self, o):
        import math
        from decimal import Decimal
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)

    def encode(self, o):
        return super().encode(_sanitize(o))


def _sanitize(obj):
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def main() -> int:
    if not EXCEL_PATH.exists():
        print(f"[ERROR] Excel not found: {EXCEL_PATH}", file=sys.stderr)
        return 1

    print(f"Excel  : {EXCEL_PATH}")
    print(f"Process: {PROCESS_TARGET_PATH if PROCESS_TARGET_PATH.exists() else '(skip)'}")

    warnings: set[str] = set()
    real_data = build_context(
        str(EXCEL_PATH),
        str(PROCESS_TARGET_PATH) if PROCESS_TARGET_PATH.exists() else None,
        warnings=warnings,
    )

    # Exclude non-deterministic / runtime-only fields
    snapshot_keys = {k for k in real_data if k not in ("dataDay", "pipelineVersion")}
    snapshot = {k: real_data[k] for k in sorted(snapshot_keys, key=str)}

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, cls=SafeEncoder),
        encoding="utf-8",
    )

    n_keys = len(snapshot)
    size_mb = OUT_PATH.stat().st_size / (1024 * 1024)
    print(f"\n=== Fixture Dump ===")
    print(f"  Keys        : {n_keys}")
    print(f"  Size        : {size_mb:.2f} MB")
    print(f"  Keys list   : {sorted(snapshot.keys())}")
    print(f"\nSaved → {OUT_PATH}")

    if warnings:
        print(f"\n[WARN] {len(warnings)} data warnings collected.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
