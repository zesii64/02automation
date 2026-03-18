# 报表规范 (Report Spec) - 贷后数据巡检

> **原则**: 先呈现数据概览与基础分析，再基于分析结果做异常判定。维度与归因以 [01_Business_Design](01_Business_Design.md) 为准。  
> **维护者**: Mr. Yuan

---

## 一、日报与周报

- **日报**：按日产出，文件名如 `CashLoan_Inspection_Report_YYYY-MM-DD.html`。
- **周报**：同一套章节结构与归因逻辑，按周聚合（如按自然周/due week），文件名如 `CashLoan_Inspection_Report_Weekly_YYYY-Www.html`。
- 章节与三条线（风险口径、回收口径、过程口径）一致，见下表。

---

## 二、标准章节结构（与三条线对应）

| 顺序 | 章节 | 口径 | 内容 | 说明 |
|------|------|------|------|------|
| 1 | **KPI Cards** | — | 关键指标卡片 (Rows, Overdue%, Repay%, Coverage%) | 顶部概览 |
| 2 | **数据概览** | — | 数据源、报告日期、各表记录数 | 基础信息核对 |
| 3 | **一、风险口径** | 风险 | **先 due 趋势**（due 日/周/月尽量全），再拆解：整体 + 新老客 + 期数/期限（发标月） + 分模型分箱 (Model Bin) | 资产质量与客群 |
| 4 | **二、回收口径** | 回收 | 序时/自然月回收率 + 归因最差 N 段 (Bucket/Group) | 回收结果 |
| 5 | **三、过程口径** | 过程 | 分 Bucket/Group：覆盖率、接通率、强度；S0/S1/S2/M1 阶段表现 | 策略执行 |
| 6 | **四、异常数据检查** | — | 以**波动**为主（日/周环比相对变化，阈值见 01_Business_Design）+ 倒挂等 | 综合预警 |
| 7 | **落款** | — | 报告生成时间、数据源、**维护者：Mr. Yuan** | 必带 |

*异常规则（相对变化、示例 10%、后续按方差定）以 [01_Business_Design](01_Business_Design.md) 第三节为准。*

---

## 三、指标定义 (Metrics Definition)

### 1. 风险口径
- **入催率 (Overdue Rate)** = `overdue_principal` / `owing_principal`
- **dpd30** = `d31_principal` / `owing_principal_d31`

### 2. 策略执行
- **覆盖率 (Coverage)** = 1 - (`raw_uncomm_case_cnt` / `raw_owing_case_cnt`)
    - *含义*: 有多少案子被触达过（拨打或短信）。
- **接通率 (Connect Rate)** = `raw_call_connect_times` / `raw_call_times`
    - *含义*: 拨出的电话有多少被接听。
- **强度 (Intensity)** = `raw_call_times` / `raw_owing_case_cnt`
    - *含义*: 平均每个案子被拨打多少次。

### 3. 回收口径
- **回收率 (Repay Rate)** = `repay_principal` / `start_owing_principal`

---

## 三、样式规范

- **CSS 框架**: Tailwind CSS (通过 CDN 引入)。
- **配色**:
    - 主色 (Brand): Blue `#2563EB`
    - 强调 (Accent): Orange `#EA580C`
    - 警告 (Danger): Red `#DC2626`
    - 成功 (Success): Green `#059669`
- **落款**: 必须包含在 `<div class="footer-block">` 中，样式与正文区分。

---

**Last Updated**: 2026-01-28（与 01_Business_Design 三条线、日报/周报、波动规则对齐）  
**维护者**：Mr. Yuan
