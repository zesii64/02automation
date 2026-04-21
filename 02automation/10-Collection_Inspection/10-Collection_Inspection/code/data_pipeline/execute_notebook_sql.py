import argparse
import json
import os
import re
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import uuid

import pandas as pd
import requests
from requests import exceptions as req_exc

# region agent log
def _debug_log(hypothesis_id: str, location: str, message: str, data: Dict[str, Any], run_id: str = "pre-fix") -> None:
    payload = {
        "sessionId": "cca29b",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(__import__("time").time() * 1000),
        "id": f"log_{uuid.uuid4().hex}",
    }
    with open(r"d:\11automation\debug-cca29b.log", "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
# endregion


def _sanitize_sql(sql: str) -> str:
    cleaned_lines = []
    for line in str(sql).splitlines():
        if "--" in line:
            line = line.split("--", 1)[0]
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines).strip()
    return cleaned


def _normalize_rows(payload: Any) -> pd.DataFrame:
    if isinstance(payload, list):
        return pd.DataFrame(payload)

    if isinstance(payload, dict):
        if payload.get("success") is False:
            raise ValueError(f"SQL API returned success=false: {payload}")

        cols = payload.get("columns")
        data_rows = payload.get("data")
        if isinstance(cols, list) and isinstance(data_rows, list):
            return pd.DataFrame(data_rows, columns=cols)

        for key in ("data", "result", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return pd.DataFrame(value)

        rows = payload.get("rows")
        if isinstance(cols, list) and isinstance(rows, list):
            return pd.DataFrame(rows, columns=cols)

    raise ValueError("Unsupported SQL API response format. Expected list or dict with data/result/rows.")


def _build_run_sql(endpoint: str, auth_token: Optional[str]):
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    # region agent log
    _debug_log(
        "H1-H3",
        "execute_notebook_sql.py:_build_run_sql",
        "Prepared SQL API request context",
        {
            "endpoint_preview": endpoint[:120],
            "endpoint_has_non_ascii": any(ord(ch) > 127 for ch in endpoint),
            "auth_token_present": bool(auth_token),
            "auth_token_len": len(auth_token) if auth_token else 0,
            "auth_token_has_non_ascii": any(ord(ch) > 127 for ch in auth_token) if auth_token else False,
        },
    )
    # endregion

    def run_sql(sql: str) -> pd.DataFrame:
        sql_text = _sanitize_sql(sql)
        if not sql_text:
            raise ValueError("Empty SQL passed to run_sql.")
        # region agent log
        _debug_log(
            "H4",
            "execute_notebook_sql.py:run_sql",
            "About to execute SQL",
            {
                "sql_prefix": sql_text[:120],
                "sql_len": len(sql_text),
            },
        )
        # endregion
        try:
            resp = requests.post(endpoint, headers=headers, json={"sql": sql_text}, timeout=600)
        except Exception as post_exc:
            # region agent log
            _debug_log(
                "H1-H3",
                "execute_notebook_sql.py:run_sql",
                "HTTP request failed before response",
                {
                    "exception_type": type(post_exc).__name__,
                    "exception_text": str(post_exc)[:300],
                },
            )
            # endregion
            raise
        resp.raise_for_status()
        try:
            payload = resp.json()
        except req_exc.JSONDecodeError as exc:
            text = resp.text.strip()
            if text:
                try:
                    return pd.read_csv(StringIO(text))
                except Exception:
                    snippet = text[:500]
                    raise ValueError(f"Non-JSON response from SQL API. Text snippet: {snippet}") from exc
            raise ValueError("SQL API returned empty non-JSON response.") from exc
        return _normalize_rows(payload)

    return run_sql


def _transform_cell_code(code: str, dt_start: Optional[str], dt_end: Optional[str]) -> str:
    lines = []
    for line in code.splitlines():
        if re.match(r"^\s*from\s+get_write_data_from_dataworks\s+import\s+run_sql\s*$", line):
            continue
        if line.strip().startswith("%"):
            continue
        lines.append(line)
    transformed = "\n".join(lines)

    if dt_start:
        transformed = re.sub(
            r"^\s*dt_start\s*=\s*['\"].*?['\"].*$",
            f"dt_start = '{dt_start}'",
            transformed,
            flags=re.MULTILINE,
        )
    if dt_end:
        transformed = re.sub(
            r"^\s*dt_end\s*=\s*['\"].*?['\"].*$",
            f"dt_end = '{dt_end}'",
            transformed,
            flags=re.MULTILINE,
        )
    return transformed


def _execute_notebook(
    notebook_path: Path,
    run_sql_func,
    output_dir: Path,
    dt_start: Optional[str],
    dt_end: Optional[str],
) -> None:
    nb = json.loads(notebook_path.read_text(encoding="utf-8"))
    cells: Iterable[Dict[str, Any]] = nb.get("cells", [])

    exec_globals: Dict[str, Any] = {
        "__name__": "__main__",
        "run_sql": run_sql_func,
    }

    original_cwd = Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        os.chdir(output_dir)
        code_cells = [c for c in cells if c.get("cell_type") == "code"]
        # region agent log
        _debug_log(
            "H5",
            "execute_notebook_sql.py:_execute_notebook",
            "Notebook execution started",
            {"code_cell_count": len(code_cells), "output_dir": str(output_dir)},
        )
        # endregion
        for idx, cell in enumerate(code_cells, start=1):
            if cell.get("cell_type") != "code":
                continue
            source = "".join(cell.get("source", []))
            transformed = _transform_cell_code(source, dt_start=dt_start, dt_end=dt_end)
            if transformed.strip():
                # region agent log
                _debug_log(
                    "H5",
                    "execute_notebook_sql.py:_execute_notebook",
                    "Executing code cell",
                    {"cell_index": idx, "cell_source_len": len(source)},
                )
                # endregion
                exec(compile(transformed, filename=str(notebook_path), mode="exec"), exec_globals, exec_globals)
        # region agent log
        _debug_log(
            "H5",
            "execute_notebook_sql.py:_execute_notebook",
            "Notebook execution completed",
            {"code_cell_count": len(code_cells)},
        )
        # endregion
    finally:
        os.chdir(original_cwd)


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute notebook SQL pipeline via HTTP SQL endpoint.")
    parser.add_argument("--notebook", required=True, help="Path to notebook file (.ipynb)")
    parser.add_argument("--endpoint", required=True, help="SQL API endpoint")
    parser.add_argument("--auth-token", default="", help="Bearer token (optional)")
    parser.add_argument("--output-xlsx", required=True, help="Target xlsx path")
    parser.add_argument("--dt-start", default="", help="Override dt_start in notebook")
    parser.add_argument("--dt-end", default="", help="Override dt_end in notebook")
    args = parser.parse_args()

    notebook_path = Path(args.notebook).resolve()
    output_xlsx = Path(args.output_xlsx).resolve()
    output_dir = output_xlsx.parent
    expected_name = output_xlsx.name

    run_sql = _build_run_sql(args.endpoint, args.auth_token or None)
    _execute_notebook(
        notebook_path=notebook_path,
        run_sql_func=run_sql,
        output_dir=output_dir,
        dt_start=args.dt_start or None,
        dt_end=args.dt_end or None,
    )

    produced = output_dir / "260318_output_automation_v3.xlsx"
    if produced.exists() and produced.name != expected_name:
        produced.rename(output_xlsx)
    elif produced.exists() and produced.name == expected_name:
        pass
    elif output_xlsx.exists():
        pass
    else:
        raise FileNotFoundError(
            f"Notebook executed but output file not found. Expected one of: {produced} or {output_xlsx}"
        )

    print(f"Notebook SQL pipeline completed. Output: {output_xlsx}")


if __name__ == "__main__":
    main()
