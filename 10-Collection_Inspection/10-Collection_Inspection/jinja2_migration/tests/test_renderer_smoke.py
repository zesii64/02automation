"""test_renderer_smoke — Jinja2 环境配置 & 渲染基础行为验证。"""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import StrictUndefined


class TestEnvironment:
    """_build_environment 配置验证。"""

    def test_strict_undefined_enabled(self):
        """Environment should use StrictUndefined."""
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        from renderer import _build_environment

        env = _build_environment()
        assert isinstance(env.undefined, type)
        assert issubclass(env.undefined, StrictUndefined)

    def test_autoescape_enabled_for_html(self):
        """Autoescape should transform HTML in {{ }} but not | safe."""
        from renderer import _build_environment

        env = _build_environment()
        tpl = env.from_string("{{ content }}{{ content_safe | safe }}")
        result = tpl.render(content="<div>", content_safe="<div>")
        assert "&lt;div&gt;" in result, f"Expected escaped '<div>', got: {result}"
        assert "<div>" in result, "| safe content should NOT be escaped"

    def test_undefined_variable_raises(self):
        """Accessing undefined variable should raise, not silently produce ''."""
        from renderer import _build_environment

        env = _build_environment()
        tpl = env.from_string("{{ undefined_var }}")
        with pytest.raises(Exception, match="undefined_var"):
            tpl.render()

    def test_render_report_raises_for_missing_template(self):
        """render_report should raise TemplateNotFound if template doesn't exist."""
        from renderer import render_report

        with pytest.raises(Exception, match="base.j2"):
            render_report({"dataDate": "2026-01-01"})

    def test_render_report_with_pilot_template(self):
        """Render Pilot standalone template — should produce HTML with DOCTYPE."""
        from pathlib import Path

        from renderer import render_report

        HERE = Path(__file__).resolve().parent
        TEMPLATES = HERE.parent / "templates"

        html = render_report(
            {
                "anomaly_content": "<div>test</div>",
                "anomaly_groups": [],
                "anomaly_agents": [],
                "data_date": "2026-01-01",
                "snapshot_date": "2026-01-01",
                "n_group_data_rows": 0,
                "n_agent_data_rows": 0,
                "n_module_headers": 0,
            },
            template_name="pilot_standalone.html.j2",
            templates_dir=TEMPLATES,
        )
        assert "<!DOCTYPE html>" in html
        assert "data_date" in html or "2026-01-01" in html
