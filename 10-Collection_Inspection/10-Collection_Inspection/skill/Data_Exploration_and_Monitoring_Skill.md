# 数据探查与监控归因方法论 (Data Exploration & Attribution Skill)

> **目标**：从源数据中提取业务价值，不仅仅是下载数据，而是理解结构、定义指标、监控异常、自动归因。

## 1. 数据维度探查 (Dimension Exploration)
在接入新数据（如 `natural_month_repay`）前，必须通过 SQL `GROUP BY` 摸清业务结构：
- **组织结构**：`SELECT group_name, count(*) FROM table GROUP BY group_name` —— 看看有哪些催收组（如 "M1组", "S1组"）。
- **资产分层**：`SELECT case_bucket, count(*) ...` —— 看看资产分布（M1, M2, S1...）。
- **作业层级**：`SELECT agent_bucket, count(*) ...` —— 看看是内催还是委外，或者是不同能力的坐席。

**产出**：确定监控的“颗粒度”（Granularity）。例如：我们不仅要看全盘回收率，还要看 **"分客群(bucket) + 分组(group)"** 的回收率。

## 2. 指标定义 (Metric Definition)
明确 SQL 中的计算逻辑：
- **Vintage 逾期率**：`sum(overdue_principal) / sum(principal)`
- **自然月回收率**：`sum(repay_principal) / sum(start_owing_principal)`
- **过程指标**：`案均负荷`、`通时`、`覆盖率`

## 3. 监控逻辑 (Monitoring Logic)
设定阈值与规则：
- **绝对阈值**：如 `回收率 < 0.5%`（按日）。
- **波动监控**：`今日 vs 昨日` 下跌超过 10%。
- **横向对比**：`A组` vs `B组` 差异超过 20%。

## 4. 归因逻辑 (Attribution Logic) - **核心价值**
当总指标异常时，自动下钻（Drill-down）找原因：
- **维度下钻**：总回收率低 -> 拆解看是哪个 `case_bucket` 低？ -> 再拆解看该 Bucket 下哪个 `group_name` 低？
- **量价分析**：是 `案量(load)` 变了，还是 `效能(rate)` 变了？

---
**应用**：本 Skill 已应用于 `run_daily_report.py`，自动对 `natural_month_repay` 数据执行维度拆解。
