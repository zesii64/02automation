# 全链路风险材料拆解与巡检落地建议

> 基于 `material/risk_management` 下 **脚本（含 SQL）+ output + 分析** 全链路的拆解：收获、疑问、可纳入巡检的内容及脚本更新建议。  
> **维护者**: Mr. Yuan

---

## 一、全链路结构（当前理解）

| 环节 | 文件/形式 | 作用 |
|------|------------|------|
| **脚本** | `250508_全链路风险.ipynb` | 在 DataWorks/ODPS 上跑 SQL，用 GROUPING SETS 一次取多维度汇总；Python 做透视与拆分。 |
| **output** | `output.xlsx` | 脚本产出的中间或最终表格（供下游使用）。 |
| **分析** | `250512_risk_analysis.xlsx`（原各业务线分析_v3） | 各业务线分析结果（总览结论 + 分业务线问题与结论）。 |

---

## 二、收获（从 notebook 学到的）

### 1. 风险口径的「正确顺序」：先 due 趋势，再拆解

- SQL 用 `TO_CHAR(due_date,'yyyymm') AS due_mon` 做**发标月/到期月**维度，并用 GROUPING SETS 同时产出：总览、按新老客、按 due_mon、按 flag_principal（金额段）、按 mob、按 period_no（期数）、按 model_bin。
- 脚本把结果拆成多张表：**df_duemon**（按 due_mon 的时序视图）、df_principal、df_mob、df_modelbina、df_period；以及 **金额段×due_mon**、**model_bin×due_mon**、**期数×due_mon** 的透视表。
- **结论**：due_mon 是时间轴，先看 due 趋势（df_duemon 及带 due_mon 的透视），再按金额段、期数、模型等拆解，这与您定的「先看 due 趋势再拆解」完全一致，已写入 [01_Business_Design](../WIKI/01_Business_Design.md) 与 [02_Report_Spec](../WIKI/02_Report_Spec.md)。

### 2. 一次取数、多维度复用（GROUPING SETS）

- 一条 SQL 通过 GROUPING SETS 同时得到：总览、新老客、due_mon、金额段、mob、期数、model_bin，以及（新老客+due_mon）、（新老客+金额段+due_mon）、（新老客+model_bin+due_mon）、（新老客+期数+due_mon）等组合。
- 对巡检的启示：若 943 支持，可考虑在聚合 SQL 里用 GROUPING SETS 产出「due 趋势 + 常用拆解」的中间表，再在本地做日报/周报的筛选与展示，减少多次查库。

### 3. 指标与 09 表字段的对应关系

- 入催率、dpd5、dpd30、dpd1/dpd5/dpd7/dpd15/dpd30_repay（各账龄回收率）、connect_rate、ptp_rate、disconnect/connect/ptp_conversion 等，均来自 09 表或与 09 表一致口径；提醒阶段转化用 owing_principal_h3。
- 巡检侧：vintage_risk 的指标定义可与该 notebook 对齐（overdue_rate、dpd30 等），避免口径不一致。

### 4. 多产品（CashLoan / TT 等）与 owner_bucket

- Notebook 内除 CashLoan 外还有 TT 等业务线，以及按 owner_bucket（S0/S1/M1…）的下钻。
- 巡检可逐步支持：先 CashLoan + 风险口径 due 趋势与拆解，再扩展 TT、再扩展过程口径的 owner_bucket 表现。

---

## 三、疑问与确认（已更新）

1. **output.xlsx 与 各业务线分析 的生成方式** — **已确认**  
   - **output.xlsx**：由 notebook 内 `pd.ExcelWriter('output.xlsx')` 写出。  
   - **写出逻辑**（从 notebook 代码可见）：  
     - **Cashloan** 表：先有注释掉的完整版（df_duemon、df_duemon_process、df_principal、df_principal_process、df_principal_duemon_result、df_mob、df_mob_process、df_modelbina、df_modelbina_process、df_modelbina_duemon_result、df_modelbinc、df_modelbinc_process、df_modelbinc_duemon_result、df_period、df_period_process、df_period_duemon_result），当前有 cell 只写入了 modelbinc 相关三张；  
     - **Tiktok / Lazada**：与 Cashloan 同结构（df_duemon、df_principal、df_principal_duemon_result、df_mob、df_modelbina、df_modelbinc 及 _process、_duemon_result）；  
     - **Total**：df_total_cl、df_total_tt、df_total_lzd。  
   - **250512_risk_analysis.xlsx**：已用本目录 `read_risk_analysis_excel.py` 读取。Sheet：**00.总览结论**（各业务线结论）、**01.CashLoan**（使用场景/问题/结论）、**02. Tiktok.new**、**03.TikTok**、**03. Lazada.new**、**04.Lazada**。内容为基于 output 或同口径的解读与结论（如 CashLoan 新客占比约 6.7%、老客风险相对可控；TikTok/Lazada 新客占比与风险结论等），与巡检「先 due 趋势再拆解」及多业务线可对齐。

---

## 3.2 读该 Excel 后的新收获 & 对项目的帮助

- **收获一（结构）**：分析表是「00 总览结论 → 01/02/03/04 分业务线」，每条线都是「使用场景 + 问题 + 结论」。巡检日报/周报可以沿用：先总览再分线，每条线有「问题聚焦 + 结论一句」，和业务看数习惯一致。
- **收获二（指标与话术）**：表里反复出现**新客占比、老客风险、高阶段接通率、承诺率/转化率（如 1–3%）**。这些可以固化为巡检的展示指标和异常规则表述（例如「老客大额案逾期率更高」「高阶段接通率更高」），报表和业务分析用同一套话术，便于对齐。
- **收获三（多业务线）**：CashLoan / TikTok / Lazada 并列，sheet 命名和顺序可直接作为巡检扩展多产品时的模板；先做 CashLoan 再扩 TT、Lazada 时，结构不用重设计。
- **收获四（due 与拆解）**：分析结论建立在「due 趋势 + 新老客/金额段/阶段」拆解之上，和我们在 01_Business_Design 里定的「先 due 趋势再拆解」一致，读这份 Excel 等于再次确认了巡检的展示顺序和维度优先级。

**对项目的帮助**：校准报表结构（总览+分线）、统一指标与异常表述话术、明确多产品扩展路径、确认「先 due 再拆解」与业务材料一致，避免巡检与业务分析脱节。

2. **get_write_data_from_dataworks.run_sql** — **已确认**  
   - 仅在 **943** 环境可用；未来「一键跑全链路 + 下载 + 出报」即用该能力在 943 跑 notebook 或等价 SQL，再下载 output/分析表。

3. **due 颗粒度** — **已确认**  
   - **日趋势**有时也很重要，需求是 **尽量全**：due_date（日）、due_week（周）、due_mon（月）在报表/取数中尽量都支持，先尽量全。

4. **flag_principal / period_no** — **已确认**  
   - **09 表有**：当前 `vintage_risk.sql`（明细）已含 `period_no`、`flag_principal` 等。  
   - **聚合**：`vintage_risk_agg.sql` 目前只按 due_date, mob, user_type, model_bin 聚合；**做不同分析需聚合不同维度**，后续可增写「按金额段聚合」「按期数聚合」等单独 SQL，或在一份聚合中增加 GROUPING SETS，按需选用。

---

## 四、可加入巡检 project 的内容

| 方向 | 建议 | 优先级 |
|------|------|--------|
| **1. 风险口径展示顺序** | 报表与 Wiki 已明确：**先 due 趋势，再拆解**（整体、新老客、期数/期限、分模型分箱）。 | 已落地 |
| **2. due 趋势的图表或表格** | 日报/周报中「风险口径」第一节：先出 **due 趋势**（due_date 日 / due_week 周 / due_mon 月 尽量全），再给拆解表。 | 高 |
| **3. 金额段、期数、model_bin 的拆解** | 与 material 一致：在风险口径下增加「按金额段」「按期数」「按 model_bin」的视图；数据来源可为现有 vintage_risk 聚合表扩展维度，或后续从 09 表 GROUPING SETS 产出。 | 高 |
| **4. 波动告警与 due 趋势结合** | 异常规则除「日环比」外，可加「同一 due_mon 内或跨 due_mon 的波动」检测（如某 due_mon 入催率较前月升幅 >10%）。 | 中 |
| **5. 与全链路脚本的衔接** | 若 943 能跑该 notebook 或等价 SQL：可把其 output 视为「风险口径的权威中间结果」，巡检日报/周报从 output 或同口径 Excel 读取，避免重复开发取数逻辑。 | 中 |

---

## 五、脚本更新建议（巡检侧）

1. **run_cashloan_report.py / 日报 HTML**  
   - 风险口径区块：**先渲染 due 趋势**（若有 due_mon/due_week 字段）：表格或简单折线（如用现有 HTML 表格按 due 排序展示入催率、dpd30）。  
   - 再渲染：整体、新老客、期数/期限、分模型分箱的拆解表（与 02_Report_Spec 一致）。

2. **vintage_risk 取数**  
   - **明细** `vintage_risk.sql` 已含 due_date、period_no、flag_principal、model_bin 等。  
   - **聚合**：当前 `vintage_risk_agg.sql` 仅 due_date, mob, user_type, model_bin；做不同分析需聚合不同维度，可增写「按 due_mon / due_week 聚合」「按 flag_principal / period_no 聚合」等 SQL，或在一份 SQL 中用 GROUPING SETS 产出多维度，供日报/周报选用。  
   - 保证 **due_date / due_week / due_mon** 在数据中都有或可派生，以便「先 due 趋势、再拆解」且**日/周/月尽量全**。

3. **数据流可选路径**  
   - **路径 A**：继续用现有 download 脚本拉取 vintage_risk / natural_month_repay / process_data，在 Python 中计算 due 趋势与拆解。  
   - **路径 B**：若全链路 notebook 产出稳定，可增加「从 material/risk_management/output.xlsx（或指定 sheet）读取风险口径汇总」，再与回收、过程口径合并出报，减少重复 SQL。

4. **Skill 与 Wiki**  
   - [Post_Loan_Data_Analysis_Management_Skill](../skill/Post_Loan_Data_Analysis_Management_Skill.md) 和 01_Business_Design 已强调「先 due 趋势再拆解」；后续若增加「金额段×due」「期数×due」等，在 01 中补一行归因问题即可。

---

**Last Updated**: 2026-01-28
