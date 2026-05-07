"""生成后 HTML 轻量锚点检查 — Jinja2 迁移版。

用法:
  python check_anchors.py [path.html]
  未传路径时仅执行模块自检；CI 可生成后传入产物路径。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 与 .j2 模板/注数强相关的稳定子串，随大改版增量维护
REQUIRED_SUBSTRINGS: tuple[str, ...] = (
    "templateContractId",
    "pipelineVersion",
    "report-pipeline:",
)


def check_html_anchors(html: str) -> list[str]:
    """返回缺失项列表；空列表表示通过。"""
    missing: list[str] = []
    if "const REAL_DATA =" not in html and "var REAL_DATA =" not in html:
        missing.append("REAL_DATA = (const 或 var，注数块)")
    for s in REQUIRED_SUBSTRINGS:
        if s not in html:
            missing.append(s)
    return missing


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        return 0
    path = Path(argv[0])
    text = path.read_text(encoding="utf-8", errors="replace")
    bad = check_html_anchors(text)
    if bad:
        print("锚点检查失败，缺少:", file=sys.stderr)
        for s in bad:
            print(f"  - {s!r}", file=sys.stderr)
        return 1
    print("锚点检查通过:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
