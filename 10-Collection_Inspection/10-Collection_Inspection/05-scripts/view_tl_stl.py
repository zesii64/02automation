"""TL/STL view patch set for Collection report HTML."""

import sys
from patch_utils import require_replace_once, require_replace_at_least_one


_patch_seq = 0

def _r1(html, old, new):
    """Replace once, warn if 0 or >1 occurrences."""
    global _patch_seq
    import traceback
    frame = traceback.extract_stack()[-2]
    patch_id = f"tlstl_{frame.lineno}_{_patch_seq}"
    _patch_seq += 1
    n = html.count(old)
    if n == 0:
        print(f"  [WARN][{patch_id}] 锚点未找到: ...{old[:60].replace(chr(10), '\\n')!r}...", file=sys.stderr)
        return html
    if n > 1:
        print(f"  [WARN][{patch_id}] 锚点出现 {n} 次(期望1): ...{old[:60].replace(chr(10), '\\n')!r}...", file=sys.stderr)
    return html.replace(old, new, 1)


def apply_tl_stl_view_patches(html: str) -> str:
    """Apply TL/STL specific HTML replacements."""
    # ---- 3. renderTLChart: module extraction + group filter ----
    html = html.replace(
        "const module = group.replace(/^G-/, '').replace(/-\\d+$/, '');",
        "const module = REAL_DATA.tlData[group] ? REAL_DATA.tlData[group].groupModule : group.split('-')[0];"
    )
    html = html.replace(
        "const allGroupsInModule = REAL_DATA.groups.filter(g => g.includes('-' + module + '-'));",
        "const allGroupsInModule = REAL_DATA.groups.filter(g => REAL_DATA.tlData[g] && REAL_DATA.tlData[g].groupModule === module);"
    )

    # ---- 4. renderSTLChart: group filter ----
    html = html.replace(
        "const groupsInModule = REAL_DATA.groups.filter(g => g.includes('-' + module + '-'));",
        "const groupsInModule = REAL_DATA.groups.filter(g => REAL_DATA.tlData[g] && REAL_DATA.tlData[g].groupModule === module);"
    )

    # ---- 5. renderTLChart: actuals -> repayRate ----
    html = html.replace(
        "                const actuals = filteredDays.map(d => Math.round(d.actual));",
        "                const actuals = filteredDays.map(d => d.nmRepayRate !== null && d.nmRepayRate !== undefined ? d.nmRepayRate : (d.repayRate !== null && d.repayRate !== undefined ? d.repayRate : null));"
    )

    # ---- Drilldown sorting: achievement asc (low -> high) ----
    html = html.replace(
        "            const agents = REAL_DATA.agentPerformance[group] || [];",
        "            const agents = REAL_DATA.agentPerformance[group] || [];\n            agents.sort((a, b) => {\n                const av = (a.achievement !== null && a.achievement !== undefined) ? a.achievement : 999;\n                const bv = (b.achievement !== null && b.achievement !== undefined) ? b.achievement : 999;\n                return av - bv;\n            });"
    )
    html = html.replace(
        "            const groups = REAL_DATA.groupPerformance[module] || [];",
        "            const groups = REAL_DATA.groupPerformance[module] || [];\n            groups.sort((a, b) => {\n                const av = (a.achievement !== null && a.achievement !== undefined) ? a.achievement : 999;\n                const bv = (b.achievement !== null && b.achievement !== undefined) ? b.achievement : 999;\n                return av - bv;\n            });"
    )

    # ---- Drilldown legend wording (EN) ----
    html = html.replace("3+ consecutive days &nbsp;", "3+ consecutive unmet days &nbsp;")
    html = html.replace(">1–2 consecutive days<", ">1–2 consecutive unmet days<")
    return html
