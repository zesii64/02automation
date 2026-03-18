# 09 表研究：tmp_liujun_phl_ana_09_eoc_sum_daily_temp

> 基于本地 CSV 导出与现有 SQL 用法整理，用于取数口径对齐与维度映射。

## 表用途

- **模块**：Vintage 风险（入催率、dpd30 等）
- **取数脚本**：`vintage_risk.sql` → Sheet `vintage_risk`
- **指标**：入催率 = overdue_principal / owing_principal；dpd30 = d31_principal / owing_principal（到期 31+ 天口径）

## 字段结构（基于 CSV 表头）

### 维度类（用于 GROUP BY / 监控切分）

| 字段 | 说明 | 维度图映射 |
|------|------|------------|
| due_date | 到期日 | 到期月/到期时间 |
| due_day | 到期日（日） | - |
| mob | 账龄月 | 用户 mob |
| user_type | 用户类型 | 新老客 |
| prod_type | 产品类型 | 产品（部分） |
| period_no, period_seq | 期序 | 产品总期数相关 |
| model_bin | 模型分箱 | C卡/模型 |
| predue_bin | 提醒阶段分箱 | 提醒阶段C卡/早期 |
| collect_bin | 到期阶段分箱 | 到期阶段C卡/晚期 |
| predue_bin_old, collect_bin_old | 旧版分箱 | - |
| channel | 渠道 | - |
| is_touch | 是否触达/可联 | 可联 |
| flag_principal | 本金口径标识 | - |
| province | 省份 | 地区 |
| conntact_carrier | 运营商 | 运营商 |
| biz_line, biz_line_new | 业务线 | - |
| amt_seg | 金额段 | 金额段（可对照） |
| s1_test_group, s2m1_test_group, flag_smstest | 策略/灰度 | 策略灰度 |

### 指标类（用于聚合）

| 字段 | 说明 | 用途 |
|------|------|------|
| **owing_principal** | 应还/在贷本金 | 入催率、dpd30 分母（表内无 principal / principal_balance，以此为准） |
| **overdue_principal** | 逾期本金 | 入催率分子 |
| **d31_principal** | 31+ 天逾期本金 | dpd30 分子 |
| d2_principal … d30_principal | 各 DPD 本金 | 可做更细 DPD 分布 |
| overdue_amount | 逾期金额 | - |
| owing_user_cnt, overdue_user_cnt, owing_cnt, overdue_cnt | 户数/笔数 | 可选 |

### 过滤与质量

- **flag_dq = 1**：数据质量通过，取数时必须带 `WHERE flag_dq = 1`。

## 与 vintage_risk.sql 的对应关系

- **分母**：表内为 **owing_principal**（不是 `principal` 或 `principal_balance`），SQL 中入催率、dpd30 分母均应以 `owing_principal` 聚合。
- **取数逻辑**：按维度 GROUP BY，输出原始 sum（overdue_principal, owing_principal, d31_principal, owing_principal_d31），比率在分析阶段计算。

## 注意

- CSV 中部分维度值为乱码（如 `ÐÂ×ª»¯ÀÏ¿Í`）多为编码问题，ODPS 内为正常中文。
- 若后续 ODPS 上表新增或重命名列，以 `DESC tmp_liujun_phl_ana_09_eoc_sum_daily_temp` 为准，本文档可同步更新。

---

**最后更新**：2026-02-03（基于 tmp_liujun_phl_ana_09_eoc_sum_daily_temp.csv 与现有 SQL）  
**维护者**：Mr. Yuan
