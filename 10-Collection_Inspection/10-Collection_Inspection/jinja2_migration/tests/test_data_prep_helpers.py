"""data_prep_helpers 单元测试（Phase 2 抽取后行为等价性）。

测试目标：
- 13 个对外函数的核心路径与边界
- 与 generate_v2_7.py 当前实现行为一致
- NaN / 空输入 / 解析失败的兜底
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# 把 jinja2_migration/ 加到 path（不依赖 conftest，便于独立运行）
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data_prep_helpers import (  # noqa: E402
    build_consecutive_weeks_map,
    compute_consecutive_days,
    extract_module_key,
    format_week_range,
    get_week_label,
    map_group_to_dtr,
    module_key_to_bucket,
    norm,
    normalize_attd_rate_pct,
    normalize_week_label,
    parse_week_str,
    resolve_canonical_group_for_breakdown,
    sort_module_keys,
    week_start_dt,
    week_str_to_display,
)


# ----------------------------------------------------------------------------
# 周字符串
# ----------------------------------------------------------------------------
class TestWeekParsing:
    def test_parse_week_str_valid_sat_fri(self):
        start, end = parse_week_str("2026-04-04-2026-04-10")
        assert start == pd.Timestamp("2026-04-04")
        assert end == pd.Timestamp("2026-04-10")

    def test_parse_week_str_invalid_returns_none(self):
        assert parse_week_str("garbage") == (None, None)
        assert parse_week_str("") == (None, None)
        assert parse_week_str("2026-04-04") == (None, None)

    def test_parse_week_str_strips_whitespace(self):
        start, end = parse_week_str("  2026-04-04-2026-04-10  ")
        assert start == pd.Timestamp("2026-04-04")
        assert end == pd.Timestamp("2026-04-10")

    def test_format_week_range(self):
        result = format_week_range(pd.Timestamp("2026-04-04"), pd.Timestamp("2026-04-10"))
        assert result == "2026-04-04-2026-04-10"

    def test_week_start_dt_valid(self):
        assert week_start_dt("2026-04-04-2026-04-10") == pd.Timestamp("2026-04-04")

    def test_week_start_dt_invalid_returns_min(self):
        assert week_start_dt("garbage") == pd.Timestamp.min


class TestNormalizeWeekLabel:
    def test_sat_fri_returned_as_is(self):
        # 2026-04-04 是周六，2026-04-10 是周五
        result = normalize_week_label("2026-04-04-2026-04-10")
        assert result == "2026-04-04-2026-04-10"

    def test_sun_sat_shifted_back_one_day(self):
        # 2026-04-05 是周日，2026-04-11 是周六 → 平移到 04-04~04-10
        warnings: set[str] = set()
        result = normalize_week_label("2026-04-05-2026-04-11", warnings=warnings)
        assert result == "2026-04-04-2026-04-10"
        assert any("Sun-Sat -> Sat-Fri" in w for w in warnings)

    def test_unparseable_returns_str_with_warning(self):
        warnings: set[str] = set()
        result = normalize_week_label("garbage", warnings=warnings)
        assert result == "garbage"
        assert any("Unparseable" in w for w in warnings)

    def test_unparseable_silent_when_no_warnings_set(self):
        # 不传 warnings 不应抛异常
        result = normalize_week_label("garbage")
        assert result == "garbage"

    def test_unexpected_boundary_warns_but_formats(self):
        warnings: set[str] = set()
        # 2026-04-06 是周一
        result = normalize_week_label("2026-04-06-2026-04-12", warnings=warnings)
        assert result == "2026-04-06-2026-04-12"
        assert any("Unexpected week boundary" in w for w in warnings)


class TestWeekDisplayHelpers:
    def test_get_week_label_for_saturday(self):
        # 2026-04-04 是周六
        assert get_week_label(pd.Timestamp("2026-04-04")) == "2026-04-04-2026-04-10"

    def test_get_week_label_for_wednesday(self):
        # 2026-04-08 (周三) 所属周仍是 04-04 ~ 04-10
        assert get_week_label(pd.Timestamp("2026-04-08")) == "2026-04-04-2026-04-10"

    def test_week_str_to_display(self):
        assert week_str_to_display("2026-04-04-2026-04-10") == "04/04 - 04/10"

    def test_week_str_to_display_invalid(self):
        assert week_str_to_display("garbage") == "garbage"


# ----------------------------------------------------------------------------
# 模块键
# ----------------------------------------------------------------------------
class TestExtractModuleKey:
    def test_large_tier(self):
        assert extract_module_key("S1-Large A") == "S1-Large"

    def test_small_tier(self):
        assert extract_module_key("S1-Small B") == "S1-Small"

    def test_s0_bucket_returns_base(self):
        assert extract_module_key("S0-A Bucket") == "S0"

    def test_no_tier_keyword(self):
        assert extract_module_key("M1 Foo Bar") == "M1 Foo Bar"

    def test_strips_whitespace(self):
        assert extract_module_key("  S1-Large A  ") == "S1-Large"


class TestSortModuleKeys:
    def test_canonical_order(self):
        result = sort_module_keys(["M1", "S2", "S0", "S1-Large", "S1-Small"])
        assert result == ["S0", "S1-Large", "S1-Small", "S2", "M1"]

    def test_unknown_module_goes_last(self):
        result = sort_module_keys(["UNKNOWN", "S0"])
        assert result == ["S0", "UNKNOWN"]

    def test_large_before_small_within_module(self):
        result = sort_module_keys(["S1-Small", "S1-Large"])
        assert result == ["S1-Large", "S1-Small"]


class TestMapGroupToDtr:
    def test_s0_prefix_normalized(self):
        assert map_group_to_dtr("S0-A Foo") == "S0-A Bucket"

    def test_non_s0_unchanged(self):
        assert map_group_to_dtr("S1-Large A") == "S1-Large A"


class TestNorm:
    def test_strips_spaces_and_dashes(self):
        assert norm("S1-Large A") == "S1LargeA"

    def test_nan_returns_empty(self):
        assert norm(float("nan")) == ""
        assert norm(pd.NA) == ""

    def test_int_or_other_types(self):
        assert norm(123) == "123"


# ----------------------------------------------------------------------------
# resolve_canonical_group_for_breakdown
# ----------------------------------------------------------------------------
class TestResolveCanonicalGroup:
    def setup_method(self):
        self.norm_to_group = {"S1LargeA": "S1-Large A"}
        self.all_groups = ["S1-Large A", "S1-Large B"]
        self.group_agent_name_map: dict[str, set[str]] = {
            "S1-Large A": {"alice"},
            "S1-Large B": {"bob"},
        }

    def test_exact_match(self):
        result = resolve_canonical_group_for_breakdown(
            "S1-Large A",
            None,
            self.norm_to_group,
            self.all_groups,
            self.group_agent_name_map,
        )
        assert result == "S1-Large A"

    def test_module_only_disambiguates_by_agent(self):
        result = resolve_canonical_group_for_breakdown(
            "S1-Large",
            "Bob",
            self.norm_to_group,
            self.all_groups,
            self.group_agent_name_map,
        )
        assert result == "S1-Large B"

    def test_module_only_no_agent_returns_none(self):
        # 多候选 + 无法消歧
        result = resolve_canonical_group_for_breakdown(
            "S1-Large",
            None,
            self.norm_to_group,
            self.all_groups,
            self.group_agent_name_map,
        )
        assert result is None

    def test_single_candidate_returns_directly(self):
        result = resolve_canonical_group_for_breakdown(
            "S1-Large",
            None,
            {},
            ["S1-Large A"],
            {"S1-Large A": set()},
        )
        assert result == "S1-Large A"

    def test_nan_returns_none(self):
        assert (
            resolve_canonical_group_for_breakdown(
                None, None, {}, [], {}
            )
            is None
        )
        assert (
            resolve_canonical_group_for_breakdown(
                float("nan"), None, {}, [], {}
            )
            is None
        )


# ----------------------------------------------------------------------------
# module_key_to_bucket
# ----------------------------------------------------------------------------
class TestModuleKeyToBucket:
    def test_split_module_direct(self):
        nat_buckets = {"S1_Large", "S1_Small"}
        assert module_key_to_bucket("S1-Large", nat_buckets) == "S1_Large"

    def test_non_split_uses_other(self):
        nat_buckets = {"S0_Other", "M2_Other"}
        assert module_key_to_bucket("S0", nat_buckets) == "S0_Other"
        assert module_key_to_bucket("M2", nat_buckets) == "M2_Other"

    def test_fallback_to_other_when_direct_missing(self):
        nat_buckets = {"S1-Large_Other"}
        # direct_bucket "S1_Large" 不在；fallback 到 "S1-Large_Other"
        # 注意：fallback 使用 mk + "_Other" 即 "S1-Large_Other"
        assert module_key_to_bucket("S1-Large", nat_buckets) == "S1-Large_Other"

    def test_returns_direct_when_nothing_matches(self):
        # 都不匹配时返回 direct_bucket（非 fallback）
        assert module_key_to_bucket("S1-Large", set()) == "S1_Large"


# ----------------------------------------------------------------------------
# normalize_attd_rate_pct
# ----------------------------------------------------------------------------
class TestNormalizeAttdRatePct:
    def test_decimal_form_scaled(self):
        assert normalize_attd_rate_pct(0.95) == 95.0

    def test_already_pct_unchanged(self):
        assert normalize_attd_rate_pct(95.5) == 95.5

    def test_boundary_one_scaled(self):
        # ≤1 都按小数处理
        assert normalize_attd_rate_pct(1.0) == 100.0

    def test_just_above_one_unchanged(self):
        assert normalize_attd_rate_pct(1.5) == 1.5

    def test_nan_returns_none(self):
        assert normalize_attd_rate_pct(float("nan")) is None

    def test_rounded_to_one_decimal(self):
        assert normalize_attd_rate_pct(0.9567) == 95.7


# ----------------------------------------------------------------------------
# 连续未达标
# ----------------------------------------------------------------------------
class TestComputeConsecutiveDays:
    def test_streak_counts_recent_failures(self):
        df = pd.DataFrame(
            {
                "dt": pd.to_datetime(
                    ["2026-04-08", "2026-04-09", "2026-04-10"]
                ),
                "achieve_rate": [0.5, 0.8, 0.7],
            }
        )
        cutoff = pd.Timestamp("2026-04-10")
        assert compute_consecutive_days(df, cutoff) == 3

    def test_streak_breaks_on_met(self):
        df = pd.DataFrame(
            {
                "dt": pd.to_datetime(
                    ["2026-04-08", "2026-04-09", "2026-04-10"]
                ),
                "achieve_rate": [0.5, 1.2, 0.7],
            }
        )
        # 倒序：04-10=0.7(streak=1) → 04-09=1.2(break) → stop
        assert compute_consecutive_days(df, pd.Timestamp("2026-04-10")) == 1

    def test_cutoff_filters_future(self):
        df = pd.DataFrame(
            {
                "dt": pd.to_datetime(["2026-04-08", "2026-04-09", "2026-04-10"]),
                "achieve_rate": [0.5, 0.5, 0.5],
            }
        )
        # cutoff=04-09 时只看 04-08 和 04-09
        assert compute_consecutive_days(df, pd.Timestamp("2026-04-09")) == 2

    def test_nan_treated_as_zero(self):
        df = pd.DataFrame(
            {
                "dt": pd.to_datetime(["2026-04-09", "2026-04-10"]),
                "achieve_rate": [float("nan"), 0.5],
            }
        )
        assert compute_consecutive_days(df, pd.Timestamp("2026-04-10")) == 2


class TestBuildConsecutiveWeeksMap:
    def test_basic_streak(self):
        week_map = {
            "2026-03-28-2026-04-03": {"achievement": 80},
            "2026-04-04-2026-04-10": {"achievement": 90},
            "2026-04-11-2026-04-17": {"achievement": 70},
        }
        result = build_consecutive_weeks_map(week_map)
        # 第1周 streak=1; 第2周 streak=2; 第3周 streak=3
        assert result == {
            "2026-03-28-2026-04-03": 1,
            "2026-04-04-2026-04-10": 2,
            "2026-04-11-2026-04-17": 3,
        }

    def test_streak_breaks_on_met(self):
        week_map = {
            "2026-03-28-2026-04-03": {"achievement": 80},
            "2026-04-04-2026-04-10": {"achievement": 105},  # 达标
            "2026-04-11-2026-04-17": {"achievement": 90},
        }
        result = build_consecutive_weeks_map(week_map)
        # 第3周向前看：04-11 streak=1，再前一周已达标 → stop
        assert result["2026-04-11-2026-04-17"] == 1
        assert result["2026-04-04-2026-04-10"] == 0

    def test_empty_returns_empty(self):
        assert build_consecutive_weeks_map({}) == {}

    def test_missing_achievement_defaults_zero(self):
        week_map = {"2026-04-04-2026-04-10": {}}
        result = build_consecutive_weeks_map(week_map)
        assert result["2026-04-04-2026-04-10"] == 1

    def test_streak_resets_after_first_week_met(self):
        # H3 (code-reviewer):若首周达标后续未达标，streak 须从 0 干净重置
        week_map = {
            "2026-03-21-2026-03-27": {"achievement": 110},  # 达标
            "2026-03-28-2026-04-03": {"achievement": 80},   # 未达
            "2026-04-04-2026-04-10": {"achievement": 70},   # 未达
        }
        result = build_consecutive_weeks_map(week_map)
        assert result["2026-03-21-2026-03-27"] == 0
        assert result["2026-03-28-2026-04-03"] == 1
        assert result["2026-04-04-2026-04-10"] == 2

    def test_single_week_smoke(self):
        # M2 (code-reviewer):单周冒烟
        assert build_consecutive_weeks_map({"2026-04-04-2026-04-10": {"achievement": 50}}) == {
            "2026-04-04-2026-04-10": 1
        }


# ----------------------------------------------------------------------------
# Reviewer-driven 补测：边界值 & 字符串 & 中文 tier
# ----------------------------------------------------------------------------
class TestExtractModuleKeyEdgeCases:
    def test_empty_string(self):
        # M2 (code-reviewer):"" → "" (parity-preserving)
        assert extract_module_key("") == ""

    def test_trailing_dash(self):
        # M2 (code-reviewer):"S1-" → "S1"（tier 为空）
        assert extract_module_key("S1-") == "S1"

    def test_uppercase_large_normalized_to_capitalize(self):
        # M2 (code-reviewer):"S1-LARGE A" → "S1-Large"（lowercased 比较 + capitalize 输出）
        assert extract_module_key("S1-LARGE A") == "S1-Large"

    def test_mixed_case_small(self):
        assert extract_module_key("S2-sMaLL B") == "S2-Small"


class TestSortModuleKeysChineseTier:
    def test_chinese_large_tier_recognized(self):
        # M2 (code-reviewer):'大额'/'小额' 中文 tier 分支零覆盖 → 高 parity 风险
        # 验证 Chinese tier 与英文 tier 同等排序：large 优先于 small
        result = sort_module_keys(["S1-小额 A", "S1-大额 B"])
        # 注意：extract_module_key 不会处理中文 tier（只 capitalize 英文 large/small），
        # 所以这里测试的是 sort_module_keys 的 _parse_module_parts_for_sort 中文分支
        # 实际输入到 sort_module_keys 的是 module_key（已被 extract_module_key 处理过）
        # 中文 tier 通常作为 raw group_id 出现，先经 extract_module_key 提取
        # 这里直接给 sort_module_keys 传含中文的 key，验证排序稳定性
        assert result[0] == "S1-大额 B"  # large tier 优先
        assert result[1] == "S1-小额 A"


class TestNormalizeAttdRatePctBoundary:
    def test_zero_returns_zero(self):
        # M2 (code-reviewer):0.0 在 <=1.0 分支 × 100 = 0.0
        assert normalize_attd_rate_pct(0.0) == 0.0

    def test_negative_passes_through(self):
        # 负值通过 <=1.0 分支 × 100，parity-preserving
        assert normalize_attd_rate_pct(-0.05) == -5.0


class TestComputeConsecutiveDaysEmptyDF:
    def test_empty_dataframe_returns_zero(self):
        # M2 (code-reviewer):空 DataFrame 应返回 0
        df = pd.DataFrame({"dt": pd.to_datetime([]), "achieve_rate": []})
        assert compute_consecutive_days(df, pd.Timestamp("2026-04-10")) == 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
