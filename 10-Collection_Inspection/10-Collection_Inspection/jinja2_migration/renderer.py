"""Jinja2 渲染器 — 将 context dict 渲染为完整 HTML。

阶段：Phase 1 骨架。Phase 4 模板转换完成后会真正渲染 base.j2 + 子模板。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _build_environment(templates_dir: Path = _TEMPLATES_DIR) -> Environment:
    """构造 Jinja2 Environment。

    关键配置：
    - `autoescape` 仅对 .html / .j2 启用；JSON / CSS / JS 注入点必须配 ``| safe``
    - `StrictUndefined`：未定义变量直接抛错，避免静默生成空字符串
    - `keep_trailing_newline=True`：保留模板末尾换行，便于 diff
    """
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(("html", "j2")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )


def render_report(
    context: dict[str, Any],
    *,
    template_name: str = "base.j2",
    templates_dir: Path = _TEMPLATES_DIR,
) -> str:
    """渲染入口。Phase 4 之前 base.j2 不存在，调用会抛 TemplateNotFound。"""
    env = _build_environment(templates_dir)
    template = env.get_template(template_name)
    return template.render(**context)
