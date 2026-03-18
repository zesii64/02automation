# 数据字典 (Data Dictionary)

> **定位**: 关键表结构与字段定义。  

---

## 1. Vintage Risk (`vintage_risk`)
*源表: `tmp_liujun_phl_ana_09_eoc_sum_daily_temp`*

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| `due_date` | Date | 到期日 | |
| `mob` | Int | 账龄 | |
| `user_type` | String | 新老客 | |
| `model_bin` | String | **模型分箱** | *v2.0 新增*，用于分层监控 |
| `overdue_principal` | Decimal | 逾期本金 | 分子 |
| `owing_principal` | Decimal | 应还本金 | 分母 |
| `d31_principal` | Decimal | DPD30+ 本金 | 分子 |
| `owing_principal_d31` | Decimal | DPD30+ 应还 | 分母 |

## 2. Process Data (`process_data`)
*源表: `phl_anls.tmp_liujun_ana_11_agent_process_daily`*

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| `product` | String | 产品线 | 由 `owner_bucket` 映射得到：Cashloan/TTbnpl/Lazada/TTcl/Smart/OFW/other |
| `owner_bucket` | String | 逾期阶段/模块 | 例：M1, M2, S0, S1, T2...（`S1%` 归一为 `S1` 用于映射，但输出仍为原 `owner_bucket`） |
| `week` | String | 周区间 | 格式：`yyyy-MM-dd-yyyy-MM-dd`，周起始为周六（脚本中对周六做了特殊处理） |
| `dt` | String | 天 | 格式：`yyyy-MM-dd`|
| `headcount` | Decimal | 满足出勤条件（工作8h）的催员数 | `COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END)` |
| `ownercount` | Decimal | 催员数 | `COUNT(DISTINCT owner_name END)` |
| `owing_case_cnt_avg` | Decimal | 人均在手案量 | `SUM(owing_case_cnt)` /（满足出勤条件的催员数 × 统计天数） |
| `cover_times` | Decimal | 覆盖次数 | `SUM(comm_times)` /（`SUM(owing_case_cnt)`-`SUM(own_uncomm_case_cnt)`） |
| `cover_rate` | Decimal | 覆盖率 | \(1 - SUM(own_uncomm_case_cnt) / SUM(owing_case_cnt)\) |
| `art_cover_times` | Decimal | 人工覆盖次数 | `SUM(art_comm_times)` /（`SUM(owing_case_cnt)`-`SUM(own_uncomm_case_cnt)`） |
| `batch_cover_times` | Decimal | 批量覆盖次数 | `SUM(batch_comm_times)` /（`SUM(owing_case_cnt)`-`SUM(own_uncomm_case_cnt)`） |
| `call_times_avg` | Decimal | 人均拨打次数 | `SUM(call_times)` /（满足出勤条件的催员数 × 统计天数） |
| `art_call_times_avg` | Decimal | 人均人工拨打次数 | `SUM(art_call_times)` /（满足出勤条件的催员数 × 统计天数） |
| `batch_call_times_avg` | Decimal | 人均批量拨打次数 | `SUM(batch_call_times)` /（满足出勤条件的催员数 × 统计天数） |
| `call_user_mobile_times_avg` | Decimal | 人均拨打本人号码次数 | `SUM(call_user_mobile_times)` /（满足出勤条件的催员数 × 统计天数） |
| `call_contact_mobile_times_avg` | Decimal | 人均拨打联系人号码次数 | `SUM(call_contact_mobile_times)` /（满足出勤条件的催员数 × 统计天数） |
| `mobile_number_connect_rate` | Decimal | 号码接通率 | `SUM(call_connect_mobile_cnt)` / `SUM(call_mobile_cnt)` |
| `call_connect_mobile_cnt` | Int | 接通过的号码数 | `SUM(call_connect_mobile_cnt)` |
| `call_billhr_avg` | Decimal | 人均通话时长（小时） | `SUM(call_billsec/60)` /（满足出勤条件的催员数 × 统计天数）；脚本中为分钟口径命名 hr |
| `call_connect_times_avg` | Decimal | 人均接通次数 | `SUM(call_connect_times)` /（满足出勤条件的催员数 × 统计天数） |
| `single_call_duration` | Decimal | 单通接通时长（分钟/通） | （人均通话时长分钟）/（人均接通次数） |
| `case_connect_rate` | Decimal | 案件接通率 | `SUM(comm_connect_own_case_cnt)` /（`SUM(owing_case_cnt)`-`SUM(own_uncomm_case_cnt)`） |
| `call_connect_rate` | Decimal | 拨打接通率 | `SUM(call_connect_times)` / `SUM(call_times)` |

## 3. Natural Month Repay (`natural_month_repay`)
*源表: `tmp_maoruochen_phl_repay_natural_day_daily`*

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| `natural_month` | String | 自然月 | |
| `case_bucket` | String | 案件阶段 | |
| `group_name` | String | 组别 | |
| `repay_principal` | Decimal | 回收本金 | 分子 |
| `start_owing_principal` | Decimal | 期初应还本金 | 分母 |

## 4. EOM Target Data (`eom_target_data`)
*源表: `module_eom_repay_target`*
*源文件: `d:\97data\eom_target_data_202501_202602.csv`*

| 字段名 | 类型 | 说明 | 备注 |
|--------|------|------|------|
| `product` | String | 产品线 | 例：cashloan、ttbnpl |
| `module` | String | 模块/阶段 | 例：S0、S1、S2、M1、T2、T4、T5；也可能包含分层（如 `S1_Large`） |
| `target_repayment_rate` | Decimal | 目标回款率 | 月度目标值 |
| `month` | String | 月份 | 格式：`yyyy-MM` |

---

**Last Updated**: 2026-03-17  
