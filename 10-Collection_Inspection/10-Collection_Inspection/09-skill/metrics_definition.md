# TL/STL View Drill Down 指标说明 / Metrics Definition

> 用于报告 drill down 表格表头悬浮 tooltip

| # | 指标名（EN） | 指标名（CN） | 计算公式 / Formula | 说明 / Notes |
|---|-------------|-------------|-------------------|-------------|
| 1 | Weekly Target | 周目标 | — | 当周设定目标值 / Target set for the week |
| 2 | Weekly Actual | 周实际 | — | 当周实际完成值 / Actual achieved in the week |
| 3 | Weekly Achievement | 周达成率 | `Weekly Actual / Weekly Target × 100%` | 达成比例，≥100% 为达标 / Achievement ratio, ≥100% = on track |
| 4 | Conn. Rate (Connect Rate) | 接通率 | `成功接通数 / 拨打数 × 100%` | 电话接通率 / Call connect rate |
| 5 | Cover Times | 案均覆盖次数 | — | 每案件平均覆盖次数 / Cover times per case |
| 6 | Call Times | 催员日均拨打次数 | — | 催员平均每天拨打电话次数 / Agent's avg. daily dial count |
| 7 | Art Call Times | 催员日均点呼次数 | — | 催员平均每天人工拨号次数 / Agent's avg. daily manual dial count |
| 8 | Single Call Duration | 单通电话时长 | `总通话分钟数 / 通话次数` | 平均单通接通时长（分钟）/ Avg. connected time per call (minutes) |
| 9 | Call Billmin | 催员日均接通时长 | — | 催员平均每天接通时长（分钟）/ Agent's avg. daily connected time (minutes) |
| 10 | Call Loss | 呼损率 | `成功接通数 / 用户接听数 × 100%` | — |
| 11 | PTP | 承诺还款率 | — | 承诺还款用户数 / 应还款用户数 × 100% / Users who promised to pay / Users who should repay × 100% |
| 12 | Attendance | 出勤率 | — | 实际出勤天数 / 应出勤天数 × 100% / Actual attendance days / Required attendance days × 100% |

---

## 日粒度指标（Agent Drilldown 3 Days）/ Daily Metrics

| # | 指标名（EN） | 指标名（CN） | 计算公式 / Formula | 说明 / Notes |
|---|-------------|-------------|-------------------|-------------|
| 1 | Target | 日目标 | — | 当日设定目标值 / Target set for the day |
| 2 | Actual | 日实际 | — | 当日实际完成值 / Actual achieved in the day |
| 3 | Achievement | 日达成率 | `Daily Actual / Daily Target × 100%` | 达成比例，≥100% 为达标 / Achievement ratio, ≥100% = on track |
| 4–12 | （其余指标同上） | — | — | — |
