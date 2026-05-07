"""HTML table extraction helpers — reused by snapshot tests and compare_pilot."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Any


class TableExtractor(HTMLParser):
    """从 HTML 中提取指定 tbody 的行内容，区分模块头行和数据行。"""

    def __init__(self, target_id: str) -> None:
        super().__init__()
        self.target_id = target_id
        self.in_tbody = False
        self.rows: list[str] = []
        self.current_row: list[str] = []
        self.in_cell = False
        self.is_module_row = False
        self._skip_button = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "tbody" and attrs_dict.get("id") == self.target_id:
            self.in_tbody = True
            self.rows = []
        elif self.in_tbody:
            if tag == "tr":
                self.current_row = []
                self.is_module_row = False
            elif tag in ("td", "th"):
                self.in_cell = True
                style = attrs_dict.get("style", "")
                if "eef2ff" in style.lower() and attrs_dict.get("colspan"):
                    self.is_module_row = True
                    self.current_row.append("[M]")
            elif tag == "button":
                self._skip_button = True

    def handle_endtag(self, tag: str) -> None:
        if self.in_tbody:
            if tag == "tr":
                if self.current_row:
                    self.rows.append(" | ".join(self.current_row))
            elif tag in ("td", "th"):
                self.in_cell = False
            elif tag == "button":
                self._skip_button = False
            elif tag == "tbody":
                self.in_tbody = False

    def handle_data(self, data: str) -> None:
        if self.in_tbody and self.in_cell and not self._skip_button:
            stripped = data.strip()
            if stripped:
                self.current_row.append(stripped)


def extract_table(html_path: Path, tbody_id: str) -> list[str]:
    """从 HTML 文件提取指定 tbody 的行文本列表。"""
    html = html_path.read_text(encoding="utf-8")
    parser = TableExtractor(tbody_id)
    parser.feed(html)
    return parser.rows


def summarize_rows(rows: list[str], table_type: str = "group") -> dict[str, Any]:
    """从行文本中提取模块头行和数据行统计。

    table_type: 'group' or 'agent'
      - group: [M] | GroupName | ModuleName | Weeks | ...
      - agent: [M] | AgentName | GroupName | ModuleName | Days | ...
    """
    module_headers: list[str] = []
    data_rows: list[str] = []
    module_list: list[str] = []
    for r in rows:
        if r.startswith("[M] "):
            module_headers.append(r)
            parts = [p.strip() for p in r[4:].split("|")]
            if table_type == "group":
                module_idx = 2
            else:
                module_idx = 3
            if len(parts) > module_idx and parts[module_idx]:
                module_list.append(parts[module_idx])
        else:
            data_rows.append(r)
    return {
        "total_rows": len(rows),
        "module_headers": len(module_headers),
        "data_rows": len(data_rows),
        "module_list": module_list,
        "first_3_data": data_rows[:3],
        "last_3_data": data_rows[-3:],
    }
