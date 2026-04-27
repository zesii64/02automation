"""HTML/模板补丁：可校验的 replace，避免静默未命中。"""

from __future__ import annotations
import sys


def require_replace_once(html: str, old: str, new: str, patch_id: str) -> str:
    """old 须恰好出现 1 次，否则 RuntimeError（含 patch_id 便于定位）。"""
    n = html.count(old)
    if n != 1:
        pre = old[:60].replace("\n", "\\n")
        raise RuntimeError(f"[{patch_id}] 期望锚点出现 1 次，实际 {n} 次: ...{pre!r}...")
    return html.replace(old, new, 1)


def require_replace_at_least_one(html: str, old: str, new: str, patch_id: str) -> str:
    """old 须至少 1 次；全部替换为 new（适用于模板中多处相同片段）。"""
    n = html.count(old)
    if n < 1:
        pre = old[:60].replace("\n", "\\n")
        raise RuntimeError(f"[{patch_id}] 期望锚点至少 1 次，实际 0 次: ...{pre!r}...")
    return html.replace(old, new)


def optional_replace(html: str, old: str, new: str, patch_id: str) -> str:
    """old 替换为 new；若不存在则跳过（0 次也正常）。"""
    n = html.count(old)
    if n == 0:
        print(f"  [WARN][{patch_id}] 锚点未找到，跳过: ...{old[:50]!r}...", file=sys.stderr)
        return html
    print(f"  [INFO][{patch_id}] 替换 {n} 处: ...{old[:50]!r}...")
    return html.replace(old, new)
