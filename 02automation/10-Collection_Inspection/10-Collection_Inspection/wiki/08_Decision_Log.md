# 08_Decision_Log (决策日志)

> 记录项目关键技术决策与业务逻辑变更。

## v4.25 线上/943 用 — 时间范围 2024-12 起

- **来源**: v4.24 的完整拷贝，不覆盖 v4.24。
- **变更**: 取数 SQL 时间范围扩至 2024-12：`SQL_REPAY` / `SQL_REPAY_DAILY` 中 `>= '202512'` / `>= '202511'` 改为 `>= '202412'`。
- **产出**: `CashLoan_Inspection_Report_*_v4_25.html`。
- **943 用法**: 平台上无法 `--mode all` 时，可只跑 **`--mode download`** 取数；出报告在本机跑 **`--mode report --excel <下载的 Excel 路径>`**，或把 Excel 拷到本机后执行 report。

---

## v4.24 Run 副本 (当前执行用)

- **来源**: v4.23 的完整拷贝，仅改 import 与输出文件名为 v4_24。
- **用途**: 在本机执行出报时不覆盖 v4.23；产出 `CashLoan_Inspection_Report_*_v4_24.html`。

---

## v4.23 Smart Diagnostics — 智能诊断 (2026-02) ✅

- **基线**: v4.22。
- **新增**: 智能诊断模块 — 多月模式识别、持续低效检测、提升量化、自然语言叙事生成。
- **新增函数**: `compute_smart_diagnostics(df_daily, df_process)`
  - 3-4 月观察窗口：组级多月指标矩阵（按 day 对齐）
  - 持续低效检测（连续 miss + 低催收力度、加速下降趋势）
  - Uplift 量化："若该组提升至模块均值，整体增益 X bp"
  - 自然语言诊断叙事
- **新增 UI**: 诊断摘要卡片（严重度分级：critical/high/medium/low）、多月趋势热力表、Uplift 柱状图

---

## v4.22 Part 3 大重构 — 运营效能升级 (2026-02) ✅

- **基线**: v4.21。
- **核心变更**: Part 3 完全重构，移除非核心面板，新增 4 个模块。
- **移除**: Repay Summary、Collection Performance、Process Summary、Anomalies（被更智能的替代方案取代）
- **新增**:
  - **Target Dashboard**: 目标达成 KPI 头部（实际率/目标/缺口/上月同日/MoM变化）
  - **Agent Leaderboard**: 模块-组排名表，按达成率排序
  - **Efficiency Analysis**: 2x2 象限散点图（努力度 vs 达成率）— "全面优秀/策略优秀/策略问题/管理问题"
  - **Action Items**: 5 类规则引擎自动生成行动建议卡片
- **调整**: Contactability 从 Part 3 迁移到 Part 2
- **Part 3 子标签**: 回收进度 / 运营归因 / 效率与行动

---

## v4.21 运营归因 Treemap + CDN 内联 (2026-02) ✅

- **基线**: v4.19/v4.20。
- **新增函数**: `compute_ops_attribution(df_daily, df_process)`
  - 3 层 Treemap 下钻：Module → Group → Agent
  - 目标缺口 + 环比双视角，带量权重
- **CDN 内联**: 下载 ECharts/TailwindCSS 并缓存本地，内联到 HTML，实现**完全离线可用**

---

## v4.19 归因中心重构 — Shift-Share (2026-02) ✅

- **基线**: v4.18。
- **核心变更**: 全新归因中心（Attribution Center），增强版 Shift-Share 分析
  - 时间窗口选择器 + 客群维度切换 + 自动生成摘要
  - 替代/合并旧版 Risk Attribution
- **新增函数**: `compute_shift_share(df_vintage)` — 预聚合所有月份 × 6 维度 × 5 指标
- **前端**: JS 实时计算结构效应 vs 风险效应

---

## v4.18 安全分母 + 页面重组 (2026-02) ✅

- **基线**: v4.17。
- **确认**: Safe Denominator 逻辑。
- **页面重组**: Part1=核心监控, Part2=归因与结构, Part3=运营效能

---

## v4.17 Shift-Share 结构归因 (2026-02) ✅

- **基线**: v4.16。
- **新增**: Shift-Share 结构归因分析 — DPD 变化 = 结构效应 + 风险效应
- **新增 UI**: 紫色主题归因面板 + 瀑布图可视化

---

## v4.16 Lift 修复 + NM 概览层 (2026-02) ✅

- **基线**: v4.15。
- **修复**: Lift 值缺失问题（方案B）
- **新增**: 自然月序时概览层（Small Multiples）、Tab 分页、Bucket 排序、当月过滤

---

## v4.15 基线验证 (2026-02) ✅

- **基线**: v4.14 纯拷贝，验证输出正确性。

---

## v4.14 方案C — 报告整体布局优化 (2026-02-06) ✅

- **基线 (Baseline)**: v4.13。
- **决策 (Decision)**: 顶部固定横栏导航 + 3 Part 分组 + ScrollSpy + 模块重排。
- **状态 (Status)**: ✅ 已实现。

### 核心变更

1. **顶部固定导航栏**: 参照内部 QuickBI 报表样式，固定在页面顶部
   - 样式: `催收智检_CashLoan | 01 回收监控 ··· 02 资产质量 & 归因 ··· 03 运营效能`
   - 点击跳转 (smooth scroll) + 滚动时自动高亮当前 Part (ScrollSpy)
   - `@media print` 隐藏导航栏

2. **3 Part 分组**:
   | Part | 标题 | 包含模块 |
   |---|---|---|
   | 01 回收监控 | 到期月回收曲线、期限监控矩阵 |
   | 02 资产质量 & 归因 | KPI卡片、Vintage矩阵、MTD Lift、资产质量趋势、金额段热力图、维度拆解、归因分析 |
   | 03 运营效能 | 自然月回收序时（含下钻）、自然月回收概览、催收团队效能、可联性分析、过程指标、异常诊断 |

3. **模块重排**:
   - **到期月回收**从原 Part 2 移到 Part 1 第一位（用户优先关注的核心指标）
   - **自然月回收序时**从原 Part 2 移到 Part 3（运营效能角度，含组织架构下钻）
   - **可联性分析**从原 Part 1 移到 Part 3（更偏运营过程指标）

---

## v4.13 方案A — 自然月序时下钻（组织架构维度） (2026-02-06) ✅

- **基线 (Baseline)**: v4.12。
- **决策 (Decision)**: 实现 4 层下钻：模块级 → 大小额 → 组级 → 经办级。
- **状态 (Status)**: ✅ 已实现，报告已生成 (`CashLoan_Inspection_Report_2026-02-06_v4_13.html`)。
- **文件大小**: 2.78 MB（含所有层级数据 JSON）。

### 核心设计

1. **4 层下钻路径**:
   - **L1 模块级**: `data_level='1.模块层级'`, `case_bucket` = S0/S1/S2/M1/M2/M3/M4
   - **L2 大小额**: `data_level='1.5.大小模块层级'`, `case_bucket` = S1_Large/S1_Small/S1_Other
   - **L3 组级**: `data_level='4.组别层级'`, `group_name`, 按 `agent_bucket` 归属到父级
   - **L4 经办级**: `data_level='5.经办层级'`, `owner_id`, 按 `group_name` 归属到父级

2. **Outsource 合并规则**: `*_Outsource` 统一合并到 `*_Other`（非大小额组）。

3. **SQL 计算口径** (用户确认):
   ```sql
   sum(repay_principal) / sum(start_owing_principal)
   -- GROUP BY day, natural_month
   -- WHERE data_level='1.模块层级' AND case_bucket='S1'
   ```

4. **图表模式**:
   - **L1/L2 多月模式**: 每条线 = 一个月份 + 目标虚线（查看某个 bucket 的跨月趋势）
   - **L3/L4 对比模式**: 每条线 = 一个组/经办（查看同级实体的当月对比）

5. **UI 交互**:
   - **面包屑导航**: `模块级 › S1 › S1_Large › S1-Large A`，点击任意节点回退
   - **动态按钮**: 根据当前层级和上级选择，自动展示对应实体按钮
   - **下钻/返回按钮**: 一键进入下级或返回上级

6. **Python 数据结构**:
   - L1/L2: `{buckets, months, data, summary}` 扁平结构
   - L3/L4: `{by_parent: {parent_key: {entities, months, data, summary}}}` 按父级分组
   - `parent_map`: L2 子模块→L1 模块映射 (S1_Large→S1)

7. **关键数据映射** (来自 `_check_hierarchy.py` 分析):
   - 4.组别层级: `case_bucket` 统一为模块级 (S1)，`agent_bucket` 区分子模块 (S1_Large)
   - 跨模块组 (如 M2+-A-AJCAI 同时处理 M2/M3/M4): 按 `agent_bucket` 过滤后数据正确隔离

---

## v4.12 UI 优化 — tooltip 降序 + 自然月大小额层级 (2026-02-06) ✅

- **基线 (Baseline)**: v4.11。
- **决策 (Decision)**: 优化图表交互体验和数据维度。
- **状态 (Status)**: ✅ 已实现。需重新下载数据（SQL 已更新含 `1.5.大小模块层级`）。

### 变更内容

1. **tooltip 降序排列 — 全局规则**:
   - 所有多 series 图表的 tooltip 均按值降序排列，高值在上方
   - 适用于: 到期月回收曲线、自然月回收序时

2. **自然月回收序时 — 新增大小额层级切换**:
   - **旧设计**: 仅显示 `data_level='1.模块层级'`，按 `case_bucket` (M1/M2/S0/S1/S2) 分组
   - **新设计**: 增加层级切换按钮 (`模块级` / `大小额`)
   - **大小额层级**: 使用 `data_level='1.5.大小模块层级'`，按 `case_bucket` 分组 (S1_Large/S1_Small 等)
   - **过滤规则**: 大小额层级只保留含 Large/Small 的 bucket，不展示 S1、S1_Other 等不可比项
   - **UI 交互**: 切换层级时，动态更新 bucket 按钮列表和目标达成汇总表

3. **SQL 更新**:
   - `SQL_REPAY_DAILY` 去掉 `case_bucket IN ('S0','S1','S2','M1','M2')` 硬编码限制
   - **根因**: 该过滤条件把 `1.5.大小模块层级` 下的 `S1_Large` 等 case_bucket 值全部挡掉了
   - 保留全部 `data_level`（不做 data_level 过滤），以支持未来 group/agent 级别下钻
   - 仅保留时间过滤 `TO_CHAR(dt_biz, 'yyyyMM') >= '202511'`
   - **需重新下载数据** 以获取 `1.5.大小模块层级` 数据

### 待设计 — 组织架构维度

> 用户提出: agent 层、group 层、module 层、bucket 层各自如何查看？
> 这涉及更复杂的组织架构设计，后续版本考虑。

---

## v4.11 计算逻辑修正 — 自然月序时 + 到期月去掉 bucket (2026-02-06) ✅

- **基线 (Baseline)**: v4.10。
- **决策 (Decision)**: 修正两个回收监控维度的计算逻辑和筛选维度。
- **状态 (Status)**: ✅ 已实现，报告已生成 (`CashLoan_Inspection_Report_2026-02-06_v4_11.html`)。

### 修正内容

1. **自然月回收序时 — 计算逻辑修正**:
   - **旧逻辑 (错误)**: `cumsum(repay_principal) / start_owing_principal[day=1]`（对已是累计值的数据再做 cumsum，导致数值异常偏高）
   - **新逻辑 (正确)**: `repay_principal[day_N] / start_owing_principal[day_N]`
   - **关键理解**: 数据本身已是累计值 — `start_owing_principal` 是截至当日累计委案本金（只增不减，因每天有新案进入），`repay_principal` 是截至当日累计回收本金
   - **公式**: 每天的回收率 = 当日累计回收 / 当日累计委案

2. **到期月回收曲线 — 去掉 bucket 筛选**:
   - **旧设计**: 按 `flag_bucket × user_type` 双维度筛选
   - **新设计**: 只按 `user_type`（新客/老客）筛选，取 `flag_bucket='ALL'` 汇总层级
   - **原因**: 到期月回收不区分 bucket，只关注客群差异
   - **JS 修复**: `switchDMUserType(this)` 直接传递按钮元素，解决 `event.target` 作用域问题

---

## v4.10 目标达成 — 自然月回收序时 + 到期月回收曲线 (2026-01-28) ✅

- **基线 (Baseline)**: v4.9（已验证通过）。
- **决策 (Decision)**: 新增两个核心回收监控维度，支持目标达成跟踪与历史同期对比。
- **状态 (Status)**: ✅ 已实现，报告已生成 (`CashLoan_Inspection_Report_2026-02-06_v4_10.html`)。已由 v4.11 修正。

### 两大监控维度

#### 维度1: 自然月回收序时 (Natural Month Recovery Progress) — 按模块

| 属性 | 说明 |
|------|------|
| **源表** | `phl_anls.tmp_maoruochen_phl_repay_natural_day_daily` |
| **X轴** | `day` (自然日 1-31) |
| **Y轴** | `sum(repay_principal) / sum(start_owing_principal)` — 累计回收率 |
| **线条** | 不同自然月 (202511/202512/202601/202602…) + **目标线 250003** |
| **筛选** | `case_bucket` (S1_Large 等) + `data_level` (如 "1.5.大小模块层级") |
| **核心问题** | "S1_Large 模块截止今天回收进度如何？跟目标差多少？" |
| **图表** | 序时进度曲线 + 目标虚线 (ECharts 折线图) |

**UI 设计**:
- 顶部模块筛选按钮: [S1_Large] [S1_Small] [S1_Other] [S2_Large] [M1] …
- ECharts 折线图: X轴=自然日(1-31), 多条月份线 + 目标虚线(250003)
- 底部汇总表: 模块 | 目标 | 当前 | 达成率 | 进度条

#### 维度2: 到期月回收曲线 (Due Month Recovery Curve) — 按 Bucket

| 属性 | 说明 |
|------|------|
| **源表** | `phl_anls.tmp_liujun_phl_repay_fnl_daily` |
| **X轴** | `days_from_duedate` (距到期日天数) |
| **Y轴** | `1 - sum(owing_principal_eoc) / sum(overdue_principal_boc)` — 回收率 |
| **线条** | 不同到期月 (202501-202602) |
| **筛选** | `user_type` (新客/老客) + `flag_bucket` (ALL/S1/S2/M1/M2) |
| **核心问题** | "这批到期月的资产，DPD+N 天后回收了多少？跟历史同期比如何？" |
| **图表** | 新客/老客分列回收曲线 (ECharts 折线图) |

**UI 设计**:
- 筛选区: 客群 [新客] [老客] + Bucket [ALL] [S1] [S2] [M1] [M2]
- ECharts 折线图: X轴=days_from_duedate, 多条到期月线

#### 两维度对比

| 对比项 | 自然月回收 (模块) | 到期月回收 (Due Month) |
|--------|-------------------|------------------------|
| 时间轴 | 自然日 1-31 (业务月内进度) | 距到期日天数 (资产生命周期) |
| 分组 | 按模块 (S1_Large 等) | 按 Bucket (ALL/S1/S2/M1/M2) |
| 客群拆分 | 不拆分 (模块维度已足够) | 新客/老客 |
| 目标线 | 有 — 250003 = 月度目标序时轨迹 | 无 — 通过历史同期曲线对标 |
| 数据源 | `tmp_maoruochen_phl_repay_natural_day_daily` | `tmp_liujun_phl_repay_fnl_daily` |

### 数据层改造

#### 现有 Excel Sheet 结构变更

```
现有 Excel 结构 (3 sheets):
  ├─ vintage_risk           ← 不变
  ├─ natural_month_repay    ← 需改造 SQL，保留 day + data_level 字段
  └─ process_data           ← 不变

新增 1 sheet:
  └─ due_month_repay        ← 新增，来自 tmp_liujun_phl_repay_fnl_daily
```

#### natural_month_repay SQL 改造（保留 day 粒度）

```sql
-- 现有 SQL: GROUP BY TO_CHAR(dt_biz, 'yyyyMM') 丢失了 day
-- 改造后: 保留 day 字段用于序时进度
SELECT
    day,                                    -- [新增] 自然日 1-31
    TO_CHAR(dt_biz, 'yyyyMM') AS natural_month,
    case_bucket,
    agent_bucket,
    data_level,                             -- [新增] 层级筛选
    group_name,
    owner_id,
    SUM(repay_principal)       AS repay_principal,
    SUM(start_owing_principal) AS start_owing_principal
FROM phl_anls.tmp_maoruochen_phl_repay_natural_day_daily
WHERE case_bucket IN ('S0','S1','S2','M1','M2')
  AND TO_CHAR(dt_biz, 'yyyyMM') >= '202511'
GROUP BY day, TO_CHAR(dt_biz, 'yyyyMM'),
         case_bucket, agent_bucket, data_level,
         group_name, owner_id
```

#### due_month_repay 新增取数 SQL

```sql
SELECT
    days_from_duedate,
    due_mth,
    user_type,
    flag_bucket,
    SUM(overdue_principal_boc) AS overdue_principal_boc,
    SUM(owing_principal_eoc)   AS owing_principal_eoc
FROM phl_anls.tmp_liujun_phl_repay_fnl_daily
WHERE due_mth >= '202501'
GROUP BY days_from_duedate, due_mth, user_type, flag_bucket
```

### 源表 DDL 与字段说明

#### tmp_maoruochen_phl_repay_natural_day_daily (自然月回收日度表)

| 字段 | 含义 | 用途 |
|------|------|------|
| `day` | 自然日 (1-31) | X轴 |
| `dt_biz` | 业务日期 | 聚合为 YYYYMM → 线条维度 |
| `case_bucket` | 案件阶段 (S1_Large 等) | 模块筛选 |
| `data_level` | 层级 (如 "1.5.大小模块层级") | 层级筛选 |
| `repay_principal` | 回收本金 | 分子 |
| `start_owing_principal` | 期初在贷本金 | 分母 |
| `group_name` / `owner_id` | 组/经办 | 下钻维度 |

- **目标行**: `natural_month = '250003'` 代表目标值，其 `repay_principal / start_owing_principal` = 当天序时目标回收率。

#### tmp_liujun_phl_repay_fnl_daily (到期月回收日度表)

| 字段 | 含义 | 用途 |
|------|------|------|
| `days_from_duedate` | 距到期日天数 (DATEDIFF(dt, d_code_min)+1) | X轴 |
| `due_mth` | 到期月 (YYYYMM) | 线条维度 |
| `user_type` | 客群 (新客/老客) | 筛选 |
| `flag_bucket` | Bucket (ALL/S1/S2/M1/M2) | 筛选 |
| `overdue_principal_boc` | 期初逾期本金 (BOC) | 分母 |
| `owing_principal_eoc` | 期末在贷本金 (EOC) | 分子 |
| 回收率公式 | `1 - sum(owing_principal_eoc) / sum(overdue_principal_boc)` | |

- **新老客定义** (SQL 中已固化):
  - 新客: `user_type IN ('新客')` → '新客'
  - 老客: `user_type IN ('新转化老客','存量老客')` → '老客'
- **Bucket 拆分逻辑**:
  - ALL: `overdue_day > 0` (所有逾期)
  - S1: `overdue_day > 0`, 观测窗口 due_date+1 ~ d_code_max+8
  - S2: `overdue_day > 7`, 观测窗口 due_date+8 ~ d_code_max+16
  - M1: `overdue_day > 15`, 观测窗口 due_date+16 ~ d_code_max+31
  - M2: `overdue_day > 30`, 观测窗口 due_date+31 ~ d_code_max+61

### 实现计划

**Mr. Yuan 负责**:
1. 按改造后的 SQL 重新导出 `natural_month_repay` 数据（含 `day` 和 `data_level` 字段）
2. 新增导出 `due_month_repay` 数据（来自 `tmp_liujun_phl_repay_fnl_daily`）
3. 放到 `data/collection_inspection_data_local.xlsx` 对应 sheet 中

**Agent 负责**:
1. 创建 v4.10 文件（不覆盖 v4.9）
2. 新增 `compute_natural_month_progress()` — 解析自然月序时数据 + 目标线
3. 新增 `compute_due_month_recovery()` — 解析到期月回收曲线
4. 新增 ECharts 折线图模块 × 2 (自然月序时 + 到期月回收)
5. 整合目标达成率汇总表（从 250003 行提取）
6. 更新决策日志

---

## v4.9 期限监控矩阵 + Lift 按钮 (2026-02-06 ~ 2026-02-28) ✅

- **基线 (Baseline)**: v4.8（= v4.2 纯净副本，数据验证通过）。
- **决策 (Decision)**: 基于 v4.8 稳定代码，增量实现期限监控矩阵、Lift 按钮、回收归因兜底。
- **增量功能**:
  1. **期限监控矩阵 (Term × MOB)**: 纵轴到期月 × 横轴所有 MOB（动态取值），三维筛选：客群 × 产品期数 × 指标。
  2. **Lift 按钮 (Show Lift Toggle)**: Vintage Matrix 增加 Show Lift 开关，Daily 默认关闭 Lift。
  3. **回收归因兜底展示**: `perf_data.buckets` 为空时展示"暂无数据"，避免板块消失。
  4. **SQL 变更**: vintage SQL 增加 `period_seq` 字段（SELECT + GROUP BY）。
- **迭代细节 (Iteration Notes)**:
  - **Lift 数值展示**: 箭头后附 delta 绝对值（如 ↑0.53%），而非仅箭头。
  - **多指标切换**: 新增 OVERDUE_RATE / DPD5 / DPD7 / DPD15 / DPD30 指标按钮，仅数据中存在对应列时显示。
  - **组内比热力**: 热力着色按每列 MOB 独立计算 min/max（组内比），而非全局比。
  - **新老客二元分类**: 与主报告一致 — 入催率最高的 user_type 为「新客」，其余合并为「老客 (含转化)」。
  - **MOB 动态范围**: 从硬编码 1-4 改为取数据中所有可用 period_no。
  - **Show Lift (MoM)**: 期限矩阵独立的 Lift 开关，公式 = (本月-上月)/上月。
  - **Bug 修复**: 删除重复的 `compute_term_monitoring_matrix` 函数（旧版覆盖新版导致数据为空）。
- **数据源**: `data/collection_inspection_data_local.xlsx`（35MB 真实数据）。
- **状态 (Status)**: ✅ 已实现，报告已生成。

---

## v4.8 基线验证 (2026-02-06) ✅

- **目的**: 纯净复制 v4.2，用真实源数据验证计算逻辑与 v4.2 一致。
- **结论**: 数据一致，确认 v4.2 代码逻辑可靠。
- **修正**: 报告保存路径修正为 `Path(__file__).parent / "reports"`，数据源指向 `data/` 目录。

---

## v4.7 期限监控矩阵与放款账龄归因 (2026-02-06) - ❌ 数据不一致

- **基线 (Baseline)**: v4.2（最后验证通过的稳定版本）。
- **决策 (Decision)**: 基于 v4.2 稳定代码，增量实现 v4.3 原定需求。版本号使用 v4.7（不复用失败版本号）。
- **增量功能**:
  1. **回收归因兜底展示**: `perf_data.buckets` 为空时展示"暂无数据"，避免板块消失。
  2. **期限监控矩阵 (Term Monitoring Matrix)**: 纵轴到期月 × 横轴 MOB1~4，支持 All/新客/老客 + All/1期/3期/6期 筛选。
  3. **放款账龄归因**: Risk Attribution 增加到期月 × MOB 维度。
  4. **SQL 变更**: vintage SQL 增加 `period_seq` 字段。
- **状态 (Status)**: ✅ 已实现，报告已生成 (`CashLoan_Inspection_Report_2026-02-06_v4_7.html`, 397KB)。

---

## v4.2 ✅ 最后成功版本 (Last Verified Build) (2026-02-05)

- **状态 (Status)**: **成功 (SUCCESS)** — 数据逻辑、MTD、趋势、归因等所有板块验证通过。
- **核心脚本**: `run_inspection_all_in_one_v4_2.py` / `run_daily_report_v4_2.py` / `run_cashloan_report_v4_2.py`。
- **功能集**: Vintage Matrix + MTD Lift + Risk Attribution + Amount Heatmap + Contactability + Collection Performance + Breakdown + Process Summary。
- **备注**: 后续所有新版本必须以 v4.2 为基线，确保数据一致性。

---

## v4.3 ~ v4.6 ❌ 失败版本记录 (Failed Iterations)

| 版本 | 目标 | 失败原因 |
|------|------|----------|
| v4.3 | 期限监控矩阵 + 放款账龄归因 | 脚本重写导致核心计算逻辑被篡改，MTD/趋势数据与 v4.2 不一致 |
| v4.4 | 性能优化 (Daily 跳过 Lift) | 基于 v4.3 错误代码，数据继承了 v4.3 的问题 |
| v4.5 | 瀑布图归因 (Waterfall) | 视觉效果差，且原有功能丢失 |
| v4.6 | 侧边栏导航 + 命名标准化 | 改动范围过大，功能回归问题 |

- **教训**: 增量开发必须基于已验证的稳定版本，不可在未验证的中间版本上叠加。

---

## v4.6 侧边栏导航与功能回滚 (Cancelled/Failed)

### 1. UI 交互升级 (Sidebar Layout)
- **痛点**: 报告越来越长，单页滚动难以快速定位核心板块（如 Risk vs Operations）。
- **决策**: 引入 **左侧固定导航栏 (Sidebar Navigation)**。
- **实现**:
  - 左侧常驻菜单，包含 Risk / Operations / Deep Dive 三大类。
  - **滚动监听 (Scroll Spy)**: 自动高亮当前阅读区域对应的菜单项。
  - **样式升级**: 采用 Inter 字体与更现代的卡片阴影设计。

### 2. 功能回滚与标准化 (Revert & Standardize)
- **回滚 (Revert)**: 撤销 v4.5 的瀑布图 (Waterfall Chart)，恢复 v4.4 的表格化归因分析。
  - 原因：瀑布图在多维度下视觉杂乱，不如表格直观。
- **标准化 (Naming)**: 全局统一将 `entrant_rate` 替换为 **`overdue_rate`** (入催率)，消除歧义。

---

## v4.5 资产质量归因 (Waterfall Attribution) - 已尝试但回滚
- **尝试**: 实现 ECharts 瀑布图以展示 Mix Effect vs Rate Effect。
- **结果**: 虽然逻辑跑通，但视觉效果不佳（"Ugly"），且挤占了原有表格的信息密度。
- **状态**: 代码保留在 v4.5 历史文件中，但 v4.6 版本回退至 v4.4 的展示逻辑。

---

## v4.4 性能优化与版本正式化 (2026-02-05)

### 1. 归因逻辑 (Logic)
- **目标**: 解释风险指标（如 DPD5, Entrant Rate）的环比变化 ($\Delta R$)。
- **框架**: **结构效应 (Mix Effect)** vs **表现效应 (Rate Effect)**。
- **公式**:
  - **Mix Effect (结构影响)**: $\sum (w_{i, curr} - w_{i, prev}) \times (r_{i, prev} - R_{total, prev})$
    - 含义：如果某组不仅风险高于大盘，且占比还在提升，则产生正向（恶化）的结构影响。
  - **Rate Effect (表现影响)**: $\sum w_{i, curr} \times (r_{i, curr} - r_{i, prev})$
    - 含义：该组自身风险变差带来的直接影响（加权后）。
- **维度**: 优先支持 **User Type (新老客)** 和 **Model Bin (模型分)**。

### 2. 可视化 (Visualization)
- **组件**: **瀑布图 (Waterfall Chart)**。
- **流向**: 
  - 起点：上月指标 (Prev Rate)。
  - 中间：各组的 Mix 贡献柱（红/绿） + 各组的 Rate 贡献柱（红/绿）。
  - 终点：本月指标 (Curr Rate)。
- **价值**: 直观回答“是客群变差了，还是同类客户表现变差了”。

### 3. 实现路径
- **版本**: v4.5 (集成在现有 HTML 报告中)。
- **位置**: 放置在 `Risk Attribution` 板块，替代或增强现有的表格视图。

---

## v4.4 性能优化与版本正式化 (2026-02-05)

### 1. 性能优化 (Performance)
- **痛点**: `Vintage Matrix` 在 Daily 维度下计算 Lift (环比) 非常耗时且视觉噪点多。
- **决策**: **Daily 维度跳过 Lift 计算**。
- **实现**: 
  - Python 端 `make_vintage_matrix_table` 增加 `show_lift` 参数。
  - 仅 Weekly/Monthly 默认计算 Lift，Daily 强制关闭。
  - 前端 Daily Tab 自动隐藏 "Show Lift" 开关。

### 2. 版本正式化 (Versioning)
- **动作**: 
  - `_v4_3.py` 系列脚本正式重命名为 `_v4_4.py`。
  - 内部 import 引用同步更新。
  - 报告标题更新为 `v4.4`。

---

## v4.3 讨论：期限监控矩阵 + 回收归因修复（已确认口径与顺序）

### 问题 1：回收归因 (Contribution + Process Drivers) 未展示
- **现象**: 08_Decision_Log v4.1 中描述的「贡献度拆解 + 过程驱动」在报告里看不到。
- **原因排查**: 前端逻辑存在；若板块为空，多为 `perf_data.buckets` 为空。
- **修复方向**: v4.3 中当 `buckets` 为空时展示「暂无数据」+ 当前月份说明，避免整块消失。

### 问题 2：数据口径（已确认 — Mr. Yuan）
- **标的维度字段**:
  - **period_no**: 当前期数（该笔标的当前在第几期）。
  - **period_seq**: 总期数（该笔标的总期数，即产品期数）。
  - 关系：`period_no <= period_seq`。
- **推导**:
  - **产品期数 (1期/3期/6期)** = `period_seq`（取值 1、3、6 等）。
  - **放款账龄 MOB** = `period_no`（MOB1 = 第 1 期，MOB2 = 第 2 期…）。
- 矩阵与归因均使用上述口径，不再使用原 `mob` 字段表示放款账龄。

### 需求与顺序（已确认 — Mr. Yuan）
- **顺序 1**: 先做 **期限监控矩阵**（含 Filter），再做「按到期月×放款账龄(MOB) 的归因」。
- **期限监控矩阵**:
  - 纵轴：到期月（由 `due_date` 聚合）。
  - 横轴：MOB1, MOB2, MOB3, MOB4（由 `period_no` 取 1~4）。
  - Filter：All / 新客 / 老客；All / 1期 / 3期 / 6期（由 `period_seq` 筛选）。

### 版本与实现
- 版本：**v4.3**，不覆盖 v4.2。
- 实现顺序：① 回收归因兜底展示；② 期限监控矩阵（period_no + period_seq + due_date）；③ 放款账龄归因（到期月×MOB）。
- **备注**: 若当前 vintage SQL 未产出 `period_seq`，需在 v4.3 的 SQL 中增加该字段（SELECT 与 GROUP BY），以支持 1期/3期/6期 筛选。

---

## v4.2 趋势可见性与 MOB 归因 (2026-02-05)

### 1. Vintage 矩阵趋势增强 (Matrix Trends)
- **痛点**: "Time Series Data" 移除后，Vintage 矩阵中看不出环比涨跌。
- **决策**: 在矩阵单元格中直接嵌入 **WoW/MoM 箭头**。
- **实现**: 对比当前行与下一行（上个周期）的数据，计算 Delta。若变化 > 0.1%，显示红/绿箭头。

### 2. MOB 归因 (MOB Attribution)
- **需求**: "本月风险上升是由哪个 MOB (账龄) 导致的？"
- **决策**: 在 `Risk Attribution` 板块中新增 `MOB (Month on Book)` 维度。
- **价值**: 识别是新资产崩盘还是老资产恶化。

### 3. 标题修复
- **Fix**: 报告标题更新为 `v4.2`，不再显示旧版本号。

### 4. 目标数据约定 (Target Data Convention)
- **约定**: `natural_month` 为 `250003` (或其他 25xx) 的数据行被视为 **目标值 (Target)**。
- **处理**: 脚本在计算 Trend/MoM 时会自动排除这些月份，避免将其误认为 Current Month。
- **未来**: 可用于计算达成率 (Actual / Target)。

---

## v4.1 回收深度归因与报表瘦身 (2026-02-05)

### 1. 报表结构简化 (Simplification)
- **痛点**: "Time Series Data" 板块与 "Vintage Matrix" 信息重叠，冗余。
- **决策**: 
    - **移除**: 删掉独立的 `Time Series Data` 分时明细板块。
    - **增强**: 保留并增强 `Vintage Matrix`，确保周/月视图能清晰体现趋势变化。
- **价值**: 报告更精炼，聚焦核心图表。

### 2. 回收归因体系 (Recovery Attribution)
- **痛点**: "回收率下降了，到底是哪个组的问题？是没打够还是接通率低？"
- **决策**: 在“回收结果”板块新增深度归因模块，包含两层逻辑：
    - **Level 1: 贡献度拆解 (Contribution)**: 计算每个组对整体回收率变化的贡献值 (Contribution to Delta)。回答 "谁是罪魁祸首"。
    - **Level 2: 过程驱动 (Process Drivers)**: 针对关键组，对比其过程指标 (Cov/Conn/Int) 的环比变化。回答 "为什么掉链子"。
- **实现**: 
    - 引入 `df_process` 的历史月份数据进行 MoM 对比。
    - 结合权重计算贡献度。

---

## v4.0 报告重构与可联性独立分析 (2026-02-05)

### 1. 报告结构重组 (Report Restructuring)
- **痛点**: 报告板块堆砌，缺乏叙事逻辑。
- **决策**: 按照“看数做分析”的思维流重组报告结构：
    1.  **风险态势 (Risk Profile)**: Vintage Matrix (提权) -> MTD Lift -> Trends -> Risk Attribution -> Deep Dive -> Contactability.
    2.  **回收结果 (Recovery Performance)**: Repay Summary -> Collection Performance.
    3.  **过程执行 (Process Execution)**: Process Summary -> Anomalies.
- **价值**: 逻辑闭环——先看底子(风险)，再看结果(回收)，最后看执行(过程)。

### 2. 可联性独立分析 (Contactability Analysis)
- **调整**: 从 **风险归因** 表中**剔除** `Connect Rate` (v3.8 加入的)。
- **新增**: 在风险/过程篇章中新增 **独立的可联性分析板块**。
    - **Trend**: Overall / New / Old 的可联率趋势。
    - **MTD**: 本月 vs 上月可联率对比。
- **价值**: 避免将“触达问题”与“资产结构问题”混淆，独立视角看可联率变化。

---

## v3.9 催收过程归因与效能对标 (2026-02-05)

### 1. 组维度过程归因 (Group Process Attribution)
- **痛点**: 知道 S1_large 组回收率低，但不知道是“打得不够”还是“接通率低”。
- **决策**: 将 **过程指标 (Process Metrics)** 与 **结果指标 (Performance)** 融合。
- **逻辑**:
    - 在“催收团队效能”表格中，为每个组增加过程指标列 (Cov %, Conn %, Int)。
    - 计算过程指标的 Delta (Group Value - Bucket Avg)。
- **价值**: 实现“一表看清”：回收率差是因为接通率低 (-5%)，还是覆盖率低 (-10%)。

---

## v3.8 归因增强与组织效能对标 (2026-02-05)

### 1. 归因分析：加入“可联率”维度 (Attribution with Contactability)
- **痛点**: 风险上升时，不知道是因为“客户变坏了”还是因为“没联系上”。
- **决策**: 在归因分析表格中增加 `Connect Rate` (可联率) 指标。
- **口径**: `Connect Rate` = `conn_conv_base` (Connected Balance) / `overdue_principal` (Overdue Balance)。即逾期金额中有多少是已接通的。
- **价值**: 辅助判断风险波动与触达质量的相关性。

### 2. 催收团队效能：M-1 对标 (Performance Benchmarking)
- **痛点**: 部分 Bucket (如 M1) 组很少，Top/Bottom 排名重复，且缺乏绝对标准。
- **决策**: 引入 **环比对标 (MoM Benchmark)**。
    - **Benchmark**: 计算上月 (M-1) 该 Bucket 的**整体回收率**。
    - **指标**: 每个组的 `Current Rate` vs `Benchmark` (M-1 Overall)。
    - **排序**: 按 `Rate Delta` (当前 - 基准) 排序，找出跑赢/跑输大盘的组。
- **价值**: 即使组很少，也能通过与历史基准对比，评价其表现好坏。

---

## v3.7 风险归因细分与组织效能 (2026-02-05)

### 1. 风险归因细分 (Segmented Risk Attribution)
- **需求**: "我觉得要拆解新老客...老客风险上升是由哪个批次导致的？"
- **决策**: 归因分析 (Risk Attribution) 板块必须支持 **Overall / New / Old** 三个维度的独立计算和展示。
- **价值**: 避免总体归因掩盖了新老客截然不同的风险驱动因素（如老客可能因存量恶化，新客可能因进件结构变化）。

### 2. 催收组织效能 (Collection Org Performance)
- **数据源**: `natural_month_repay` 表。
- **目标**: 分析 S1/S2 等各阶段（Bucket）内，不同组（Group）和催收员（Owner）的回收表现。
- **逻辑**:
    - **层级**: Bucket -> Group -> Owner。
    - **指标**: 回收率 (`repay_rate`)、案件量占比（Contribution）。
    - **可视化**: 
        - **Bucket 概览**: 展示各阶段整体回收率。
        - **Group 排名**: 每个 Bucket 下表现最好/最差的组。
        - **Agent 排名**: 重点关注组内的明星与后进员工。

---

## v3.6 风险归因与度量校准 (2026-02-05)

### 1. 风险归因体系 (Risk Attribution / Drivers)
- **痛点**: "风险上升是由哪个入催批次、哪个金额段导致的？" 用户需要直接的归因结论，而不是去查多张表。
- **决策**: 新增 **归因分析 (Risk Attribution)** 板块。
    - **对比逻辑**: 本月 MTD vs 上月同期 MTD。
    - **维度**: 
        - **结构维度 (Amount, Model)**: 计算 Volume Mix Effect (结构变化) 和 Rate Effect (本组恶化)。
        - **时间维度 (Batch)**: 筛选本月内 *风险贡献度 (Volume * Rate)* 最高的入催批次，回答 "是否由最新放款导致" 的问题。
    - **可视化**: Top Contributors 列表，红色高亮正向贡献（导致风险上升）的因子。

### 2. 核心度量修正 (Metric Calibration)
- **Rows -> Loan Cnt**: 
    - **问题**: 原 `Rows` 统计的是聚合数据的行数，无业务意义。
    - **修正**: 全局替换为 `SUM(loan_cnt)` (借据数)，反映真实业务单量。
- **Signature**: 页脚署名更新为 **Mr. Yuan**，强化合作契约。

---

## v3.5 可视化洞察增强 (2026-02-05)

### 1. 金额段热力图 (Amount x Month Heatmap)
- **需求**: "月环比视图...纵轴到期月，横轴金额段"。
- **实现**: 新增交互式热力图，支持切换 `Overdue Rate`, `DPD1`, `DPD5`, `DPD30`。
- **价值**: 一眼识别特定金额段在特定月份的风险聚集区。

### 2. 标准化命名与微小变化感知
- **Naming**: `Rows` -> `Loan Cnt`, `Entrant` -> `Overdue Rate`。
- **Sensitivity**: 环比箭头 (Change Arrow) 阈值从 1% 降至 **0.1%**，捕捉微小风险信号。

---

## v3.4 多维时序拆解 (2026-02-04)

### 1. 维度拆解多周期化 (Multi-Period Breakdown)
- **升级**: `维度拆解` 板块不再仅展示 Weekly，新增 `Daily` (DoD) 和 `Monthly` (MoM) 切换。
- **Daily 聚焦**: 金额段 (Amount) 维度的 Daily 视图被特别强化，用于监控每日入催批次的金额段风险。

### 2. 时序表环比 (Trend Table Change)
- **功能**: 在分时明细表中加入环比变化箭头，保持与维度拆解一致的体验。

---

## v3.3 深度对齐与口径修正 (2026-02-04)

### 1. 同观测期对齐 (Observability Alignment)
- **痛点**: 在 MTD 对比时，历史月份（M-1）数据已完全成熟，而本月（Current）进度刚开始（如 3天）。直接对比会导致历史数据的 DPD 指标虚高（因包含了本月看不到的后几天坏账）。
- **决策**: **严格回退历史进度**。计算 M-1 的 DPD 指标时，必须应用与本月完全相同的相对时间窗口。
    - **Entrant (T+1)**: 历史同期也只取前 X 天。
    - **DPD1 (T+2)**: 历史同期也只取前 X-1 天。
- **效果**: M-1 的 DPD1 从 6.10% (全量) 修正为 5.82% (截断后)，与 BI 系统完全一致。

### 2. 动态新客识别 (Dynamic New Customer Detection)
- **痛点**: `user_type` 字段存在编码乱码问题，硬编码匹配 `"新客"` 导致筛选失效，老客数据混入了高风险新客。
- **决策**: **风险锚定识别**。
    - 自动计算所有类型的入催率。
    - 认定 **入催率最高** 的组为新客（New），将其剔除。
    - 剩余组自动合并为老客（Old）。
- **价值**: 彻底规避编码问题，确保分群准确。

### 3. DPD1 定义修正
- **口径**: 明确 DPD1 逾期率 = `d2_principal` / `owing_principal`。
    - 分子：`d2_principal` (T+1 也就是 Due+1 结束时的逾期余额)。
    - 分母：`owing_principal` (在贷本金)。
- **Vintage 矩阵**:
    - 表头 `D1` 对应 DPD1 (d2 数据)。
    - 表头 `Overdue Rate` 对应入催率 (d1 数据)。

---

## v3.2 深度拆解与可视化回调 (2026-02-04)

### 1. 老客定义聚合 (Old Customer Aggregation)
- **业务逻辑**: 明确“老客”包含 `存量老客` (Existing) 和 `新转化老客` (Converted)。
- **实现**: 代码逻辑从简单的 `!= "新客"` 升级为确保清洗逻辑能正确包含所有非新客类型，避免因精确匹配导致的“数据丢失”。

### 2. 环比涨跌回归 (MoM Lift Restored)
- **决策**: 在 v3.1 的多周期并列（M/M-1/M-2）基础上，**恢复** v3.0 的 `Lift (MoM)` 涨跌幅列。
- **价值**: 用户既需要看绝对值的历史对比（M-2, Y-1），也需要一眼看到相比上月的**变化幅度**（红涨绿跌）。

### 3. Vintage 矩阵双视图 (Split Matrix)
- **决策**: Vintage 矩阵不再只展示回收率，拆分为两张表：
    1.  **Recovery Rates** (回收率矩阵)
    2.  **DPD Overdue Rates** (逾期率矩阵)
- **实现**: `compute_aggregated_vintage` 同时计算两套指标，前端垂直堆叠展示。

### 4. 维度拆解回归 (Breakdown Restored)
- **修正**: v3.1 迁移时遗漏的 `Breakdown` 板块（按模型、金额、期数拆解）已在 v3.2 补全。

---

## v3.1 精细化拆解与体验优化 (2026-02-04)

### 1. 全局维度拆解 (Universal Segmentation)
- **决策**: 报告中 **所有** 核心模块（Trend, Lift, Matrix）必须支持 **Overall / New / Old** 三个维度的独立切换查看。
- **痛点解决**: 避免“平均数陷阱”，新老客风险表现差异巨大，混合看会掩盖真实问题。

### 2. MTD 环比增强 (Enhanced Lift Analysis)
- **时间窗扩展**: 
    - `Current` (本月 MTD)
    - `M-1` (上月同进度)
    - `M-2` (上上月同进度)
    - `Y-1` (去年同期同进度)
- **数据处理**: 遇到数据缺失（如去年同期）位保留占位符，确保指标体系完整性，待线上数据积累后自动生效。

### 3. 指标口径明确 (Metric Definitions)
- **Rows (记录数)**: 当前脚本中的 `Rows` 指的是 Excel 聚合数据的行数（组合数），非业务口径。
- **Loan Count (借据数)**: v3.1 SQL 中预埋 `COUNT(1) as loan_cnt`。未来报表将展示真实的进件/放款单量。
- **精度控制**: 
    - 率值 (Rate): 保留 2 位百分比小数 (xx.xx%)。
    - 浮点数: ECharts Tooltip 强制保留 2 位小数。

### 4. 版本控制策略
- **文件隔离**: 建立 `_v3_1.py` 系列文件，严格保留 `_v3.py` 作为稳定版，不覆盖。

---

## v3.0 深度归因与趋势分析 (2026-02-04)

### 1. 同观察日水平对比 (Lift Analysis)
- **核心逻辑**: MTD (Month-to-Date) 对比。
- **价值**: 只有在相同的“时间进度”下（如本月前4天 vs 上月前4天）对比，才能排除账龄成熟度带来的干扰，真正看出风险变化。
- **实现**: Python `compute_lift_analysis` 通过日期筛选模拟历史同期的观测状态。

### 2. 局部成熟趋势 (Partial Maturity Trend)
- **痛点**: 月度/周度趋势中，因周期末端几天未成熟，导致整个周期指标被 Global Constraint 屏蔽（显示为 0 或空）。
- **决策**: 启用 **Safe Denominator** 逻辑。在聚合周期内，只统计已满表现期的样本。
    - 例如：1月 DPD5 = (1月1日-29日 DPD5 分子之和) / (1月1日-29日 应还分母之和)。
    - **结果**: 能体现月初已暴露的风险，而非全零。

### 3. 智能热力图 (Scoped Heatmap)
- **痛点**: 全局上色导致老客全绿、新客全红，失去区分度。
- **决策**: **组内竞争 (Group Scoped)**。新客内部比，老客内部比。颜色深浅反映该群体内部的相对风险。

### 4. 多维 Vintage 矩阵
- **升级**: 新增 Weekly 和 Monthly 视图，消除单日波动，看清长周期走势。

---

## v2.3 核心指标口径精细化 (2026-02-04)
- **观测时点错位 (Lag 1)**: D1 回收率使用 T+2 的 `d2_principal` 计算。
- **分子分母同口径**: SQL 产出 `owing_principal_dX` 专用分母列。
- **可视化**: 未成熟数据强制断点 (Null)。

## v2.2 核心架构与逻辑升级 (2026-02-04)
- **动态 SQL**: `generate_vintage_sql` 自动生成 D1-D31。
- **趋势细分**: 新客/老客分页签。

## v2.1 归因与自动化 (2026-02-03)
- **归因分析**: 分批次回收率下钻。
- **全链路脚本**: `run_inspection_all_in_one.py`。

## v1.0 初始化 (2026-02-01)
- **基础框架**: Excel -> Python -> HTML。
