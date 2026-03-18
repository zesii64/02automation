# 监控指标覆盖度与待补清单 (Metrics Coverage & Gaps)

> **定位**: 盘点“当前能看什么数”，记录“还缺什么数”，作为后续补全的路线图。  
> **维护者**: Mr. Yuan

---

## 一、当前已覆盖 (What We Have)

基于 `run_inspection_all_in_one.py` 及现有聚合表，我们目前能监控：

### 1. 资产质量 (Asset Quality)
| 指标 | 维度 | 业务含义 |
|------|------|----------|
| **入催率 (Overdue Rate)** | Due Date, User Type, Model Bin | 进件质量、客群风险 |
| **DPD30+** | Due Date, Model Bin | 严重逾期风险 |
| **案量 (Volume)** | Due Date | 每日到期案件规模 |

### 2. 策略执行 (Strategy Execution)
| 指标 | 维度 | 业务含义 |
|------|------|----------|
| **覆盖率 (Coverage)** | Month, Bucket, Group | 案子是否被触达（防漏案） |
| **接通率 (Connect Rate)** | Month, Bucket, Group | 线路/号码健康度、接通情况 |
| **执行强度 (Intensity)** | Month, Bucket, Group | 人均/案均拨打次数（勤奋度） |

### 3. 回收结果 (Outcome)
| 指标 | 维度 | 业务含义 |
|------|------|----------|
| **回收率 (Repay Rate)** | Month, Bucket, Group | 最终回款结果 |
| **最差归因** | Bucket, Group | 找出拖后腿的组/阶段 |

---

## 二、欠缺清单 (Gaps / What's Missing)

**核心欠缺：业务归因维度的落地（支撑「先 due 再拆解」流程）**

目前主要缺的是**归因维度**，导致报表无法按设计思路（新老客、期限、金额段）进行拆解。

| 优先级 | 模块 | 缺失维度/功能 | 业务价值 | 补全计划 |
|--------|------|---------------|----------|----------|
| **P0** | **风险** | **期限 (Term)** | 区分长短标风险（如 7 天 vs 30 天）。 | SQL 增加 `term` 字段。 |
| **P0** | **风险** | **金额段 (Amount Bin)** | 大额案往往风险更高，需独立监控。 | SQL 增加 `amount_bin` 字段。 |
| **P0** | **风险** | **报表拆解增强** | 目前报表只拆了 Model，缺**新老客、期数、期限、金额段**的拆解表格。 | 修改 `run_cashloan_report.py`，增加这些维度的 Breakdown Table。 |
| **P1** | **过程** | **PTP / RPC** | 辅助判断通话质量（承诺率、有效联络）。 | 待 SQL 增加字段。 |
| **P1** | **风险** | **迁徙率 (Flow Rate)** | 补充 Vintage 之外的短期视角。 | 待设计逻辑。 |

---

## 三、补全验证记录 (Step-by-Step Verification)

*在此记录每一步的确认与补全动作*

- [x] **2026-02-03**：盘点当前覆盖度，确认**缺期限、金额段维度**及**报表拆解逻辑**。
- [ ] **待办**：修改 `vintage_risk_agg.sql`，增加 `term` 和 `amount_bin`。
- [ ] **待办**：修改 `run_daily_report.py`，支持按新维度聚合计算。
- [ ] **待办**：修改 `run_cashloan_report.py`，在 Asset Quality 节下增加多维拆解表。

---

**Last Updated**: 2026-02-03  
**维护者**：Mr. Yuan
