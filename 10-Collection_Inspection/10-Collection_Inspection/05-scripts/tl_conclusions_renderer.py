"""TL Conclusions Jinja2 renderer.

Renders the TL Conclusions HTML table with doc-link.
Used by generate_v2_7.py to produce the conclusions HTML
injected into the browser via generateTLConclusions().
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).parent / "templates"
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)
_tl_tmpl = env.get_template("tl_conclusions.html.j2")

# Doc URLs keyed by coarse module (S0/S1/S2/M1)
_DOC_URLS = {
    "S0": "https://doc.weixin.qq.com/sheet/e3_AGIATAbTANsCNWcq1Hf0CS76ZJaSp?scode=AGMA_AdxAAsSXn1aiyAGIATAbTANs&tab=BB08J2",
    "S1": "https://doc.weixin.qq.com/sheet/e3_AGIATAbTANsCNKGdG4MPaQreE00Ga?scode=AGMA_AdxAAs8sEUIewAagA5gaoAKA&tab=BB08J2",
    "S2": "https://doc.weixin.qq.com/sheet/e3_AGIATAbTANsCNk6txUBU0SG2hZ9A0?scode=AGMA_AdxAAs0D7crFlAagA5gaoAKA&tab=BB08J2",
    "M1": "https://doc.weixin.qq.com/sheet/e3_AGIATAbTANsCNs8XAuzKHQmq0m0W1?scode=AGMA_AdxAAsARFwfuoAagA5gaoAKA&tab=BB08J2",
}


def _normalize(module_key: str) -> str:
    """Normalize S1-Large -> S1, S2-Small -> S2, S0 -> S0."""
    return module_key.replace("-Large", "").replace("-Small", "").strip()


def _fmt(v: Optional[float], d: int = 1, suffix: str = "") -> str:
    if v is None:
        return "--"
    return f"{v:.{d}f}{suffix}"


def render_tl_conclusions_html(
    *,
    group: str,
    selected_date: str,
    module_key: str,
    team_avg_achievement: float,
    team_avg_attendance: float,
    team_avg_connect_rate: float,
    team_avg_call_loss_rate: float,
    team_avg_art_call_times: float,
    lagging_agents: list,
    people_summary: str,
    strategy_summary: str,
    tool_summary: str,
    weak_case_stages: list,
    weak_principal_stages: list,
    module_avg_dial: float,
) -> str:
    """Render the full TL conclusions HTML.

    All arguments come from REAL_DATA and DOM selectors in the browser.
    This function is called at HTML-generation time (Python), not at browser runtime.
    """
    coarse_module = _normalize(module_key)

    lagging_html_parts = []
    for idx, a in enumerate(lagging_agents):
        lagging_html_parts.append(
            f'<div style="padding:6px 8px; border:1px solid #e5e7eb; border-radius:6px; margin-bottom:6px;">'
            f'<b>#{idx + 1} {a["name"]}</b> | '
            f'Achv {_fmt(a.get("achievement"), 1, "%")} | '
            f'Attendance {_fmt(a.get("attendance"), 1, "%")} | '
            f'Dial {_fmt(a.get("artCallTimes"), 0)} | '
            f'Connect {_fmt(a.get("connectRate"), 1, "%")} | '
            f'Gap {_fmt(a.get("gap"), 0)}'
            f'</div>'
        )
    lagging_html = (
        '\n'.join(lagging_html_parts)
        if lagging_html_parts
        else '<div style="color:#6b7280;">No lagging agent identified for selected date.</div>'
    )

    team_avg = {
        "achievement": team_avg_achievement,
        "attendance": team_avg_attendance,
        "connect_rate": team_avg_connect_rate,
        "call_loss_rate": team_avg_call_loss_rate,
        "art_call_times": team_avg_art_call_times,
    }

    # Build doc-link block
    doc_link_html = ""
    if coarse_module in _DOC_URLS:
        doc_link_html = (
            f'<div style="margin-top:10px; padding-top:10px; border-top:1px solid #e5e7eb; font-size:12px;">'
            f'<div style="color:#374151; font-weight:600; margin-bottom:4px;">改进方案 · Improvement plan</div>'
            f'<div style="color:#6b7280; font-size:11px; line-height:1.45; margin-bottom:6px;">'
            f'在当前模块维度填写或跟踪改进动作（腾讯文档外链）。 / Fill in or track module-level improvement actions (Tencent Doc, external).</div>'
            f'<a href="{_DOC_URLS[coarse_module]}" target="_blank" rel="noopener noreferrer" style="color:#2563eb;">'
            f'打开「{coarse_module}」模块改进方案 · Open {coarse_module} improvement plan (Tencent Doc)</a>'
            f'</div>'
        )

    # Render via Jinja2 template
    return _tl_tmpl.render(
        group=group,
        selected_date=selected_date,
        module_key=module_key,
        coarse_module=coarse_module,
        team_avg=team_avg,
        lagging_agents=lagging_agents,
        people_summary=people_summary,
        strategy_summary=strategy_summary,
        tool_summary=tool_summary,
        weak_case_stages=weak_case_stages,
        weak_principal_stages=weak_principal_stages,
        module_avg_dial=module_avg_dial,
        doc_link_html=doc_link_html,
    )
