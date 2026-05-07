"""data_prep_helpers — 从 generate_v2_7.py 抽取的工具函数。

设计原则：
- 全部为**纯函数**（或参数化纯函数）；模块级 state（如旧脚本的 `data_warning_set`、
  `nat_buckets`）改为显式参数。
- 类型注解齐全，便于 IDE 与 mypy。
- 行为与 generate_v2_7.py 当前实现严格等价；如发现不一致按 generate_v2_7.py 为准。

抽取来源：05-scripts/generate_v2_7.py (lines 148-179, 241-345, 493-521, 559-569)
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import timedelta

import pandas as pd

# ============================================================================
# 模块排序优先级（与 view_data Agent Overview 对齐：S0 → S1 → S2 → M1）
# ============================================================================
_MODULE_SORT_PRIORITY: tuple[str, ...] = ("S0", "S1", "S2", "M1")
_MODULE_SORT_RANK: dict[str, int] = {m: i for i, m in enumerate(_MODULE_SORT_PRIORITY)}


# ============================================================================
# 周字符串处理
# ============================================================================
_WEEK_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{4}-\d{2}-\d{2})$")


def parse_week_str(ws: object) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """解析形如 ``YYYY-MM-DD-YYYY-MM-DD`` 的周字符串为 (start, end)。

    无法解析时返回 ``(None, None)``。
    """
    m = _WEEK_PATTERN.match(str(ws).strip())
    if not m:
        return None, None
    return pd.to_datetime(m.group(1)), pd.to_datetime(m.group(2))


def format_week_range(start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> str:
    """格式化为 ``YYYY-MM-DD-YYYY-MM-DD``。"""
    return f"{start_dt.strftime('%Y-%m-%d')}-{end_dt.strftime('%Y-%m-%d')}"


def normalize_week_label(
    ws: object,
    *,
    warnings: set[str] | None = None,
) -> str:
    """归一化周标签到 Saturday → Friday 边界。

    - Sat→Fri 输入：原样返回
    - Sun→Sat 输入：整体平移 -1 天（同步记录警告）
    - 其他边界：原样格式化（同步记录警告）
    - 解析失败：返回 ``str(ws)``（同步记录警告）

    若提供 ``warnings`` 集合，警告文本会被加入；否则静默处理。

    与 ``Series.apply`` 配合时建议用 ``functools.partial`` 绑定 warnings 集合：

    >>> from functools import partial
    >>> warnings_set: set[str] = set()
    >>> df['week'] = df['week'].apply(partial(normalize_week_label, warnings=warnings_set))
    """
    start_dt, end_dt = parse_week_str(ws)
    if start_dt is None or end_dt is None:
        if warnings is not None:
            warnings.add(f"Unparseable week label: {ws}")
        return str(ws)

    if start_dt.weekday() == 5 and end_dt.weekday() == 4:
        return format_week_range(start_dt, end_dt)

    if start_dt.weekday() == 6 and end_dt.weekday() == 5:
        shifted_start = start_dt - timedelta(days=1)
        shifted_end = end_dt - timedelta(days=1)
        if warnings is not None:
            warnings.add(
                "Week label converted Sun-Sat -> Sat-Fri: "
                f"{ws} -> {format_week_range(shifted_start, shifted_end)}"
            )
        return format_week_range(shifted_start, shifted_end)

    if warnings is not None:
        warnings.add(f"Unexpected week boundary (not Sat-Fri): {ws}")
    return format_week_range(start_dt, end_dt)


def week_start_dt(ws: object) -> pd.Timestamp:
    """返回周字符串的 start dt；解析失败返回 ``pd.Timestamp.min``（用于排序兜底）。"""
    start_dt, _ = parse_week_str(ws)
    return start_dt if start_dt is not None else pd.Timestamp.min


def get_week_label(dt: pd.Timestamp) -> str:
    """根据日期返回所属周的 ``YYYY-MM-DD-YYYY-MM-DD`` 标签（Sat→Fri）。"""
    dow = dt.dayofweek
    days_since_sat = (dow - 5) % 7
    week_start = dt - timedelta(days=int(days_since_sat))
    week_end = week_start + timedelta(days=6)
    return f"{week_start.strftime('%Y-%m-%d')}-{week_end.strftime('%Y-%m-%d')}"


def week_str_to_display(ws: object) -> str:
    """周字符串转 ``MM/DD - MM/DD`` 展示格式；解析失败返回 ``str(ws)``。"""
    start_dt, end_dt = parse_week_str(ws)
    if start_dt is None or end_dt is None:
        return str(ws)
    return f"{start_dt.strftime('%m/%d')} - {end_dt.strftime('%m/%d')}"


# ============================================================================
# 模块/分组键处理
# ============================================================================
def extract_module_key(group: str) -> str:
    """从 group_id 提取模块 key。

    示例：
    - ``"S1-Large A"`` → ``"S1-Large"``
    - ``"S1-Small B"`` → ``"S1-Small"``
    - ``"S0-A Bucket"`` → ``"S0"``
    """
    g = group.strip()
    parts = g.split("-")
    if len(parts) >= 2:
        first_word = parts[1].strip().split()[0].lower() if parts[1].strip() else ""
        if first_word in ("large", "small"):
            return f"{parts[0]}-{parts[1].strip().split()[0].capitalize()}"
    return parts[0]


def _parse_module_parts_for_sort(module_key: object) -> tuple[str, str]:
    """``"S1-Large"`` → ``("S1", "large")``；用于 sort_module_keys。"""
    text = str(module_key or "").strip()
    parts = text.split("-")
    base = (parts[0] or "").strip()
    raw_tier = (parts[1] or "").strip().lower() if len(parts) > 1 else ""
    if raw_tier == "large" or "大额" in raw_tier:
        tier = "large"
    elif raw_tier == "small" or "小额" in raw_tier:
        tier = "small"
    else:
        tier = raw_tier
    return base, tier


def sort_module_keys(keys: Iterable[str]) -> list[str]:
    """按 S0 → S1 → S2 → M1 优先级排序；同组内 large 优先于 small。"""

    def key_fn(k: str) -> tuple[int, str, int, str]:
        base, tier = _parse_module_parts_for_sort(k)
        rank = _MODULE_SORT_RANK.get(base, 999)
        tier_order = 0 if tier == "large" else (1 if tier == "small" else 2)
        return (rank, base, tier_order, str(k))

    return sorted(keys, key=key_fn)


def map_group_to_dtr(group: str) -> str:
    """``"S0-A Foo"`` → ``"S0-A Bucket"``；其他情况原样返回。"""
    g = group.strip()
    if g.startswith("S0-"):
        remainder = g[3:].strip()
        letter = remainder.split()[0]
        return f"S0-{letter} Bucket"
    return g


def norm(g: object) -> str:
    """跨表匹配用的归一化：移除空格和短横线；NaN 返回空串。"""
    if pd.isna(g):
        return ""
    return str(g).replace(" ", "").replace("-", "")


def resolve_canonical_group_for_breakdown(
    owner_group_raw: object,
    a_norm: str | None,
    norm_to_group: dict[str, str],
    all_groups: Iterable[str],
    group_agent_name_map: dict[str, dict[str, object] | set[str]],
) -> str | None:
    """将 daily_target_agent_breakdown.owner_group 映射到 tl_data.group_id。

    规则：
    1. 精确匹配：``norm(raw)`` 命中 ``norm_to_group``
    2. 否则：所有 ``extract_module_key(raw)`` 一致的 group 候选
       - 唯一候选：直接返回
       - 多个候选：用 agent name 在 group 名单中的归属决定
    3. 无法消歧返回 ``None``（调用方应跳过该行）。
    """
    if owner_group_raw is None or (
        isinstance(owner_group_raw, float) and pd.isna(owner_group_raw)
    ):
        return None
    raw = str(owner_group_raw).strip()
    if not raw:
        return None

    g_hit = norm_to_group.get(norm(raw))
    if g_hit:
        return g_hit

    try:
        mk = extract_module_key(raw)
    except Exception:
        mk = None
    if not mk:
        return None

    candidates = [g for g in all_groups if extract_module_key(g) == mk]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    an = (a_norm or "").strip().lower()
    if an:
        for g in candidates:
            if an in (group_agent_name_map.get(g) or {}):
                return g
    return None


def module_key_to_bucket(mk: str, nat_buckets: set[str]) -> str:
    """模块 key → natural_month_repay 的 agent_bucket。

    匹配优先级：
    1. 非拆分模块（``S0`` / ``M2``，无 ``-``）且 ``{mk}_Other`` 在 nat_buckets：返回 ``{mk}_Other``
    2. ``direct_bucket = mk.replace('-', '_')`` 在 nat_buckets：返回 ``direct_bucket``
    3. ``fallback_bucket = f"{mk}_Other"`` 在 nat_buckets：返回 ``fallback_bucket``
    4. 都不命中：返回 ``direct_bucket``（``mk`` 中 ``-`` 替换为 ``_``，可能是不存在的桶）

    与 ``05-scripts/generate_v2_7.py:559-569`` 行为严格一致；
    ``nat_buckets`` 由调用方注入（旧脚本是模块全局 set）。
    """
    if "-" not in mk:
        other_bucket = f"{mk}_Other"
        if other_bucket in nat_buckets:
            return other_bucket
    direct_bucket = mk.replace("-", "_")
    if direct_bucket in nat_buckets:
        return direct_bucket
    fallback_bucket = f"{mk}_Other"
    return fallback_bucket if fallback_bucket in nat_buckets else direct_bucket


# ============================================================================
# 数值/比率
# ============================================================================
def normalize_attd_rate_pct(v: object) -> float | None:
    """考勤率归一化到 [0, 100]。NaN 返回 ``None``；≤1 视为小数自动 ×100。"""
    if pd.isna(v):
        return None
    fv = float(v)  # type: ignore[arg-type]
    if fv <= 1.0:
        fv = fv * 100
    return round(fv, 1)


# ============================================================================
# 连续未达标计算
# ============================================================================
def compute_consecutive_days(df_agent: pd.DataFrame, cutoff_dt: pd.Timestamp) -> int:
    """以 ``cutoff_dt`` 为截止，从最近一天倒序计连续未达标天数。

    DataFrame 需含列 ``dt``（日期）与 ``achieve_rate``。NaN 视为 0（未达标）。
    """
    df_agent = df_agent[df_agent["dt"] <= cutoff_dt]
    streak = 0
    for _, row in df_agent.sort_values("dt", ascending=False).iterrows():
        ach = float(row["achieve_rate"]) if pd.notna(row["achieve_rate"]) else 0.0
        if ach < 1.0:
            streak += 1
        else:
            break
    return streak


def build_consecutive_weeks_map(
    week_map: dict[str, dict[str, object]],
) -> dict[str, int]:
    """对每个周 key，倒序计连续 ``achievement < 100`` 的周数。"""
    if not week_map:
        return {}
    sorted_weeks = sorted(week_map.keys(), key=week_start_dt)
    res: dict[str, int] = {}
    for i, wk in enumerate(sorted_weeks):
        streak = 0
        j = i
        while j >= 0:
            wj = sorted_weeks[j]
            ach = float(week_map[wj].get("achievement", 0.0))  # type: ignore[arg-type]
            if ach < 100:
                streak += 1
                j -= 1
            else:
                break
        res[wk] = streak
    return res


def detect_day_only_cross_month_risk(
    df: pd.DataFrame, date_col: str, key_cols: list[str]
) -> int:
    """检测 day-of-month 聚合的跨月风险。

    返回 key_cols + day 组合出现在多个月份的次数（>0 表示有跨月重叠风险）。
    """
    if date_col not in df.columns:
        return 0
    d = df.dropna(subset=[date_col]).copy()
    if len(d) == 0:
        return 0
    d["dom"] = pd.to_datetime(d[date_col]).dt.day
    d["ym"] = pd.to_datetime(d[date_col]).dt.to_period("M").astype(str)
    month_cnt = (
        d.groupby(key_cols + ["dom"], dropna=False)["ym"]
        .nunique()
        .reset_index(name="month_cnt")
    )
    return int((month_cnt["month_cnt"] > 1).sum())


def filter_report_month(
    df: pd.DataFrame, date_col: str, report_year: int, report_month: int
) -> pd.DataFrame:
    """过滤 DataFrame 到指定年月。"""
    d = df.copy()
    d[date_col] = pd.to_datetime(d[date_col])
    return d[
        (d[date_col].dt.year == report_year)
        & (d[date_col].dt.month == report_month)
    ].copy()


__all__ = [
    "parse_week_str",
    "format_week_range",
    "normalize_week_label",
    "week_start_dt",
    "get_week_label",
    "week_str_to_display",
    "extract_module_key",
    "sort_module_keys",
    "map_group_to_dtr",
    "norm",
    "resolve_canonical_group_for_breakdown",
    "module_key_to_bucket",
    "normalize_attd_rate_pct",
    "compute_consecutive_days",
    "build_consecutive_weeks_map",
    "detect_day_only_cross_month_risk",
    "filter_report_month",
]
