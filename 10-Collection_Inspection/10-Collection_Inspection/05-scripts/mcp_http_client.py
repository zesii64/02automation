"""
MCP HTTP Client — 直接调 MaxCompute MCP HTTP 端点，无需 Claude Code。

凭证从环境变量读取：
  ALIYUN_ACCESS_KEY_ID
  ALIYUN_ACCESS_KEY_SECRET
  ALIYUN_ACCESS_KEY_ID=Fallback值 (从 ~/.mcp.json 默认值，用于本地测试)
"""
import json
import os
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

# =====================================================================
# 配置
# =====================================================================
MCP_URL = "http://funmcp.overseafinvcorp.com/mcp"

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-Fun-Mcp-Region": "phl",
    "X-Fun-Mcp-Projects": "phl_data,phl_anls",
}


def _get_credentials() -> tuple[str, str]:
    """从环境变量读取凭证，找不到则抛错."""
    ak = os.environ.get("ALIYUN_ACCESS_KEY_ID", "").strip()
    sk = os.environ.get("ALIYUN_ACCESS_KEY_SECRET", "").strip()
    if not ak or not sk:
        raise RuntimeError(
            "Missing ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET in env vars. "
            "Run: set ALIYUN_ACCESS_KEY_ID=... && set ALIYUN_ACCESS_KEY_SECRET=..."
        )
    return ak, sk


# =====================================================================
# 核心调用
# =====================================================================

def mcp_call(tool_name: str, arguments: dict, timeout: int = 300, max_retries: int = 3) -> dict:
    """
    发 JSON-RPC 2.0 请求到 MCP HTTP 端点，带自动重试（503/429 限流保护）.

    Parameters
    ----------
    tool_name   : str — 如 'maxcompute_run_select_sql'
    arguments   : dict — 如 {'sql': 'select ...'}
    timeout     : int — 秒
    max_retries : int — 最大重试次数（默认 3 次）
    """
    ak, sk = _get_credentials()
    headers = {**MCP_HEADERS, "X-Aliyun-Access-Key-Id": ak, "X-Aliyun-Access-Key-Secret": sk}

    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
        "id": 1,
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(MCP_URL, json=payload, headers=headers, timeout=timeout)
            if resp.status_code in (503, 429):
                # 服务端限流 / 不可用 — 等一等再重试
                wait = min(30, 2 ** attempt)
                print("    [WARN] MCP 返回 %d，%ds 后重试 (%d/%d)..." % (resp.status_code, wait, attempt + 1, max_retries))
                time.sleep(wait)
                last_error = Exception("HTTP %d" % resp.status_code)
                continue
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            wait = min(30, 2 ** attempt)
            print("    [WARN] 请求失败: %s，%ds 后重试 (%d/%d)..." % (e, wait, attempt + 1, max_retries))
            time.sleep(wait)
            last_error = e
            continue

        result_obj = resp.json()

        # 错误检查
        if "error" in result_obj:
            raise RuntimeError("MCP error: %s" % result_obj["error"])

        # 提取 content.text
        content = result_obj.get("result", {}).get("content", [])
        if not content:
            raise RuntimeError("MCP returned no content: %s" % result_obj)

        text = content[0].get("text", "")
        is_error = result_obj.get("result", {}).get("isError", False)
        if is_error:
            raise RuntimeError("MCP tool error: %s" % text)

        return json.loads(text)

    # 所有重试都失败
    raise RuntimeError("MCP 调用失败（已重试 %d 次）: %s" % (max_retries, last_error))


def mcp_query(sql: str) -> pd.DataFrame:
    """
    执行一条 SQL，返回 DataFrame.

    对应原 notebook 的 mcp_query().
    自动加 LIMIT 1000 防止截断（MCP 默认 limit 100）。
    """
    _sql = sql.strip().rstrip(";").rstrip()
    if "LIMIT" not in _sql.upper():
        _sql += " LIMIT 1000"
    result = mcp_call("maxcompute_run_select_sql", {"sql": _sql})
    rows = result.get("rows", [])
    cols = result.get("columns", [])
    if not rows:
        return pd.DataFrame(columns=cols) if cols else pd.DataFrame()
    return pd.DataFrame(rows, columns=cols)


def query_all(
    sql_template: str,
    dt_start: str,
    dt_end: str,
    chunk_days: int = 3,
) -> pd.DataFrame:
    """
    按日期分片多次查询，pd.concat 拼接全量结果.

    Parameters
    ----------
    sql_template : str — SQL 模板，用 {dt_start} / {dt_end} 占位（不要用 f-string）
    dt_start      : str — 开始日期，格式 'YYYY-MM-DD'
    dt_end        : str — 结束日期，格式 'YYYY-MM-DD'
    chunk_days    : int — 每片天数，默认 3 天

    Returns
    -------
    pd.DataFrame — 拼接后的全量数据
    """
    all_dfs = []
    cur = datetime.strptime(dt_start, "%Y-%m-%d")
    end = datetime.strptime(dt_end, "%Y-%m-%d")
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    chunk_num = 0

    while cur <= end:
        chunk_num += 1
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end)

        # A2: when the chunk crosses 'today', merge today~end into one chunk
        if cur <= today <= chunk_end:
            chunk_end = end

        cs = cur.strftime("%Y-%m-%d")
        ce = chunk_end.strftime("%Y-%m-%d")

        chunk_sql = sql_template.format(dt_start=cs, dt_end=ce)

        # 自动加 LIMIT 防止单次量过大
        if "LIMIT" not in chunk_sql.upper():
            chunk_sql = chunk_sql.rstrip().rstrip(";") + " LIMIT 1000"

        try:
            df = mcp_query(chunk_sql)
            if df is not None and len(df) > 0:
                all_dfs.append(df)
                print("    chunk %d [%s ~ %s]: %d rows" % (chunk_num, cs, ce, len(df)))
            else:
                print("    chunk %d [%s ~ %s]: 0 rows (skipped)" % (chunk_num, cs, ce))
        except Exception as e:
            print("    chunk %d [%s ~ %s]: FAILED — %s" % (chunk_num, cs, ce, e))

        cur = chunk_end + timedelta(days=1)

    if all_dfs:
        return pd.concat(all_dfs, ignore_index=True)
    return pd.DataFrame()


def run_sql(sql: str) -> pd.DataFrame:
    """
    run_sql 接口 — 对应 extract_data.py 中 run_sql = lambda sql: odps.execute_sql(sql).to_pandas()
    用于 extract_data_mcp.py 的 run_sql 替换.
    """
    return mcp_query(sql)