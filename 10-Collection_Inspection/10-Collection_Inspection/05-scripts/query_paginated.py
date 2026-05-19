# -*- coding: utf-8 -*-
"""
MaxCompute 分页查询工具 — 绕过 MCP/ODPS 行数限制，多次查询拼接结果。

适用场景：
  - MCP 工具自动追加 LIMIT 100/1000，单次拿不完
  - ODPS 直连下结果集过大，想分页拉取避免内存爆

用法：
  from query_paginated import query_all

  odps = get_odps()  # 你的 ODPS 连接
  sql = "select * from phl_anls.tmp_xxx where dt >= '2026-05-01'"
  df = query_all(odps, sql, chunk_size=1000)

分页策略（按优先级自动选择）：
  1. 列分页 — 传 order_col，用 WHERE col > last_val 分页，高效
  2. ROW_NUMBER 分页 — 通用，但大数据量较慢
"""

import pandas as pd
from typing import Optional


def query_all(
    odps,
    sql: str,
    chunk_size: int = 1000,
    order_col: Optional[str] = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    分页拉取全量数据。

    Parameters
    ----------
    odps : ODPS 连接对象
    sql : 基础 SQL（SELECT ... FROM ...），不要含 LIMIT/OFFSET
    chunk_size : 每批行数，默认 1000（MCP 上限）
    order_col : 排序列名，提供后使用列分页（如 'dt' 或 'id'），更快更可靠
    verbose : 打印进度

    Returns
    -------
    pd.DataFrame : 拼接后的全量数据
    """
    if order_col:
        return _query_by_column(odps, sql, chunk_size, order_col, verbose)
    else:
        return _query_by_row_number(odps, sql, chunk_size, verbose)


def _query_by_row_number(odps, sql: str, chunk_size: int, verbose: bool) -> pd.DataFrame:
    """ROW_NUMBER 分页 — 通用方案，不需要排序列。"""
    total = _count_rows(odps, sql)
    if verbose:
        print(f"Total: {total} rows, chunk_size={chunk_size}, batches={-(-total // chunk_size)}")

    all_chunks: list[pd.DataFrame] = []
    for offset in range(0, total, chunk_size):
        rn_from = offset + 1
        rn_to = offset + chunk_size
        chunk_sql = f"""
select * from (
    select _t.*, ROW_NUMBER() OVER() as __rn
    from (
{sql}
    ) _t
) _numbered
where __rn >= {rn_from} and __rn <= {rn_to}
"""
        chunk_df = odps.execute_sql(chunk_sql).to_pandas()
        chunk_df.drop(columns=["__rn"], inplace=True, errors="ignore")
        all_chunks.append(chunk_df)
        if verbose:
            print(f"  batch {offset // chunk_size + 1}: {len(chunk_df)} rows")

    result = pd.concat(all_chunks, ignore_index=True)
    if verbose:
        print(f"Done: {len(result)} rows total")
    return result


def _query_by_column(
    odps, sql: str, chunk_size: int, order_col: str, verbose: bool
) -> pd.DataFrame:
    """
    列值分页 — 利用排序列的 WHERE 条件分页。
    要求 order_col 在 SELECT 中且可排序。
    """
    total = _count_rows(odps, sql)
    if verbose:
        print(f"Total: {total} rows, chunk_size={chunk_size}, col={order_col}")

    all_chunks: list[pd.DataFrame] = []
    last_val = None

    while True:
        if last_val is None:
            where_clause = "1=1"
        else:
            # 转义字符串类型的 last_val
            val_repr = repr(last_val)
            where_clause = f"{order_col} > {val_repr}"

        chunk_sql = f"""
select * from (
{sql}
) _col_page
where {where_clause}
order by {order_col}
limit {chunk_size}
"""
        chunk_df = odps.execute_sql(chunk_sql).to_pandas()
        if chunk_df.empty:
            break

        all_chunks.append(chunk_df)
        last_val = chunk_df[order_col].iloc[-1]
        if verbose:
            print(f"  batch {len(all_chunks)}: {len(chunk_df)} rows, last {order_col}={last_val}")

        if len(chunk_df) < chunk_size:
            break

    result = pd.concat(all_chunks, ignore_index=True) if all_chunks else pd.DataFrame()
    if verbose:
        print(f"Done: {len(result)} rows total")
    return result


def _count_rows(odps, sql: str) -> int:
    count_sql = f"select count(*) as cnt from (\n{sql}\n) _cnt"
    df = odps.execute_sql(count_sql).to_pandas()
    return int(df.iloc[0, 0])


# ============================================================
# MCP 工具场景：如果你通过对话中的 MCP 工具查询，可以参考以下模板
# ============================================================
"""
MCP 分批查询模板（伪代码，在对话中手工执行）：

1. 先查总数：
   select count(*) as cnt from (<your_sql>) t

2. 分批拉取（假设按 dt 列分页）：
   select * from (<your_sql>) t where dt >= '2026-05-01' and dt < '2026-05-08' limit 1000
   select * from (<your_sql>) t where dt >= '2026-05-08' and dt < '2026-05-15' limit 1000
   ...

3. 在 notebook 中 concat：
   import pandas as pd
   df = pd.concat([df1, df2, df3], ignore_index=True)
"""
