---
name: collection-staffing-analysis
description: 催收人力-负荷-勤奋度-回款表现的分析边界与最小指标集，用于人力规划、产能诊断与效率对标（非因果结论）。
---

# 催收人力与回款分析（边界版）

## 触发条件（必须调用）

当请求满足任一条时必须调用本 skill：

- 人力配置/调配建议
- 负荷压力（`case_load`）与人力是否不足
- 勤奋度强度（`call_times`、`cover_rate`、接通时长等）与回款关系
- 组别/阶段回款变化的解释（以诊断为主）
- 是否存在“冗余/可压缩空间”的初筛判断

## 排斥条件（必须停止并提示人工介入）

出现以下情况，不要给“确定性结论”：

- 用户要做“裁员/降编”的最终决策，但缺少：案件结构、目标、策略差异、质量指标（只能输出风险提示与需要补的证据）
- 缺少关键分母（例如 `owing_principal` 或 `case_load`）导致无法归一化
- 指标存在明显数据质量问题（缺失、重复、口径不一）但尚未修复

此时必须输出：缺失证据清单 + 最小可行验证方案。

## 成功标准（做到这里才算完成）

1. 指标都被归一化到“人均/案均/本金口径”至少一种
2. 对比在“同 bucket/同客群结构”前提下完成（或明确声明无法满足）
3. 输出为“诊断 + 可验证建议”，不输出因果承诺

## 最小完备工具集（只用这些）

- **字段映射**：把现有表映射到 Staffing/Workload/Diligence/Outcome 四类
- **归一化指标**：人均、案均、单位投入产出
- **对标方法**：同 bucket 同结构下对比；找效率前沿与落后单元

## 概念映射（先做这个）

如果 schema 不同，先映射等价字段：

- Staffing:
  - Agent id: `owner_name` (or equivalent)
  - `headcount = distinct count(owner_name)`
- Workload:
  - `case_load`
  - `cover_times`
  - `cover_rate`
- Diligence:
  - `call_times`
  - `call_billmin`
  - `single_call_duration`
- Outcome:
  - `owing_principal`
  - `repay_principal`
  - `target_repay_principal`

## 核心派生指标（只保留最少集合）

- `avg_case_load_per_agent = sum(case_load) / headcount`
- `avg_calls_per_agent = sum(call_times) / headcount`
- `avg_connect_minutes_per_agent = sum(call_billmin) / headcount`
- `avg_connect_minutes_per_case = sum(call_billmin) / sum(case_load)`
- `repay_rate = sum(repay_principal) / sum(owing_principal)`
- `repay_principal_per_agent = sum(repay_principal) / headcount`
- `achieve_rate = sum(repay_principal) / sum(target_repay_principal)`
- `repay_per_connect_minute = sum(repay_principal) / sum(call_billmin)`
- `repay_per_call = sum(repay_principal) / sum(call_times)`

## 解释边界（默认规则）

1. More staffing usually lowers per-agent load, but excessive staffing can dilute output per agent.
2. Increasing calls helps first at low coverage; marginal return drops at high coverage.
3. Coverage and valid contact quality should be analyzed together, not separately.
4. Long call duration without repayment improvement indicates strategy or execution inefficiency.
5. Compare peers under similar bucket and portfolio structure before claiming under/over staffing.

## 输出格式（固定）

1. **现象**（人力/负荷/勤奋/回款）
2. **诊断**（瓶颈在覆盖、接通质量、策略差异还是数据口径）
3. **建议**（只给可验证的动作，不给因果承诺）
4. **验证**（下一周期观察哪些指标来确认建议有效）

## Source note

Canonical reference document:

- `skills/skill_hc_repay_process.md`
