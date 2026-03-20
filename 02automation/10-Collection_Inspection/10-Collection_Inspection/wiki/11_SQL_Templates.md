# SQL 模板（可复制运行）

> **用途**：当需要编写本项目相关取数 SQL 时，优先参考/复制本文件中的模板，再按需求替换参数与颗粒度。

---

## 统一参数约定

- `dt_start`：开始日期（含），格式 `yyyy-MM-dd`
- `dt_end`：结束日期（含），格式 `yyyy-MM-dd`
- **本项目范围**：仅 review **内催**（inhouse / 非外包）

建议在 DataWorks/MaxCompute 脚本里用你习惯的参数注入方式替换占位符：
- `${dt_start}`、`${dt_end}`

---

## 1）Process Data（模块维度：周粒度 + 月字段）

**输出粒度**：每行唯一键 `product + agent_bucket + week + month`  
**内催限制**：`is_outs_owner = 0`  
**大小额分层**：通过 `owner_group` 手动制作 `agent_bucket`（Large/Small/Other）。若不需要分层，可把 `agent_bucket` 替换为 `case_bucket`。

```sql
-- Process Data（模块维度）：周粒度 + month（便于与月度结果对齐）
SELECT
  CASE
    WHEN CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END
         IN ('M1','M2','M2+','S0','S1','S2') THEN 'Cashloan'
    WHEN CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END
         IN ('T2','T3','T4+','T4','T5','T5+','TT') THEN 'TTbnpl'
    WHEN CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END
         IN ('L0','L1','L1&L2','L2','L2&3','L2&L3','L3','L3+','L4+') THEN 'Lazada'
    WHEN CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END
         IN ('TC0','TC1','TC2','TC3') THEN 'TTcl'
    WHEN CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END = 'Smart' THEN 'Smart'
    WHEN CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END = 'W0' THEN 'OFW'
    ELSE 'other'
  END AS product,

  -- 归一模块（用于映射/分层）
  CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END AS case_bucket,

  -- 分析用模块分层（大小额/其他）
  CASE
    WHEN owner_group LIKE '%Large%' THEN CONCAT(CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END, '_Large')
    WHEN owner_group LIKE '%Small%' THEN CONCAT(CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END, '_Small')
    ELSE CONCAT(CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END, '_Other')
  END AS agent_bucket,

  SUBSTR(dt, 1, 7) AS month,

  -- 周区间：周起始为周六（与现网脚本一致）
  CONCAT(
    CASE
      WHEN WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')) = 0 THEN
        TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), -1, 'dd'), 'yyyy-MM-dd')
      ELSE
        TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), - (WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')) + 1), 'dd'), 'yyyy-MM-dd')
    END,
    '-',
    CASE
      WHEN WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')) = 0 THEN
        TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), 5, 'dd'), 'yyyy-MM-dd')
      ELSE
        TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), 5 - WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')), 'dd'), 'yyyy-MM-dd')
    END
  ) AS week,

  -- 人力规模
  GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) AS headcount,
  GREATEST(COUNT(DISTINCT owner_name), 1) AS ownercount,

  -- 人均在手案量：分母为 >0h 出勤的人（允许早退/缺勤仍被分案）
  SUM(owing_case_cnt) / (
    GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour > 0 THEN owner_name END), 1)
    * COUNT(DISTINCT dt)
  ) AS owing_case_cnt_avg,

  -- 覆盖
  CASE WHEN SUM(owing_case_cnt) > 0
       THEN SUM(comm_times) / (SUM(owing_case_cnt) - SUM(own_uncomm_case_cnt)) END AS cover_times,
  CASE WHEN SUM(owing_case_cnt) > 0
       THEN 1 - SUM(own_uncomm_case_cnt) / SUM(owing_case_cnt) END AS cover_rate,
  CASE WHEN SUM(owing_case_cnt) > 0
       THEN SUM(art_comm_times) / (SUM(owing_case_cnt) - SUM(own_uncomm_case_cnt)) END AS art_cover_times,
  CASE WHEN SUM(owing_case_cnt) > 0
       THEN SUM(batch_comm_times) / (SUM(owing_case_cnt) - SUM(own_uncomm_case_cnt)) END AS batch_cover_times,

  -- 拨打相关人均：分母为 >=8h 的有效出勤人（反映正常工作强度）
  SUM(call_times) / (
    GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
    * COUNT(DISTINCT dt)
  ) AS call_times_avg,
  SUM(art_call_times) / (
    GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
    * COUNT(DISTINCT dt)
  ) AS art_call_times_avg,
  SUM(batch_call_times) / (
    GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
    * COUNT(DISTINCT dt)
  ) AS batch_call_times_avg,
  SUM(call_user_mobile_times) / (
    GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
    * COUNT(DISTINCT dt)
  ) AS call_user_mobile_times_avg,
  SUM(call_contact_mobile_times) / (
    GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
    * COUNT(DISTINCT dt)
  ) AS call_contact_mobile_times_avg,

  CASE WHEN SUM(owing_case_cnt) > 0
       THEN SUM(call_connect_mobile_cnt) / SUM(call_mobile_cnt) END AS mobile_number_connect_rate,
  SUM(call_connect_mobile_cnt) AS call_connect_mobile_cnt,

  SUM(call_billsec / 60) / (
    GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
    * COUNT(DISTINCT dt)
  ) AS call_billhr_avg,
  SUM(call_connect_times) / (
    GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
    * COUNT(DISTINCT dt)
  ) AS call_connect_times_avg,
  (SUM(call_billsec / 60) / (
    GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
    * COUNT(DISTINCT dt)
  )) / (
    SUM(call_connect_times) / (
      GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
      * COUNT(DISTINCT dt)
    )
  ) AS single_call_duration,
  CASE WHEN SUM(owing_case_cnt) > 0
       THEN SUM(comm_connect_own_case_cnt) / (SUM(owing_case_cnt) - SUM(own_uncomm_case_cnt)) END AS case_connect_rate,
  CASE WHEN SUM(owing_case_cnt) > 0
       THEN SUM(call_connect_times) / SUM(call_times) END AS call_connect_rate

FROM phl_anls.tmp_liujun_ana_11_agent_process_daily
WHERE dt >= '${dt_start}'
  AND dt <= '${dt_end}'
  AND (DAYOFWEEK(dt) + 12) % 7 + 1 != 7
  AND is_outs_owner = 0  -- 仅内催
GROUP BY
  CASE
    WHEN CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END
         IN ('M1','M2','M2+','S0','S1','S2') THEN 'Cashloan'
    WHEN CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END
         IN ('T2','T3','T4+','T4','T5','T5+','TT') THEN 'TTbnpl'
    WHEN CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END
         IN ('L0','L1','L1&L2','L2','L2&3','L2&L3','L3','L3+','L4+') THEN 'Lazada'
    WHEN CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END
         IN ('TC0','TC1','TC2','TC3') THEN 'TTcl'
    WHEN CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END = 'Smart' THEN 'Smart'
    WHEN CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END = 'W0' THEN 'OFW'
    ELSE 'other'
  END,
  CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END,
  CASE
    WHEN owner_group LIKE '%Large%' THEN CONCAT(CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END, '_Large')
    WHEN owner_group LIKE '%Small%' THEN CONCAT(CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END, '_Small')
    ELSE CONCAT(CASE WHEN owner_bucket LIKE '%S1%' THEN 'S1' ELSE owner_bucket END, '_Other')
  END,
  CONCAT(
    CASE
      WHEN WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')) = 0 THEN
        TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), -1, 'dd'), 'yyyy-MM-dd')
      ELSE
        TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), - (WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')) + 1), 'dd'), 'yyyy-MM-dd')
    END,
    '-',
    CASE
      WHEN WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')) = 0 THEN
        TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), 5, 'dd'), 'yyyy-MM-dd')
      ELSE
        TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), 5 - WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')), 'dd'), 'yyyy-MM-dd')
    END
  ),
  SUBSTR(dt, 1, 7)
;
```

---

## 2）Natural Month Repay（月末状态，模块维度：月粒度）

**核心逻辑**：`dt` 为业务后一天，因此 `substr(dt,9,2)='01'` 表示“上月月末累计状态”。  
**内催限制**：`in_or_out='inhouse'`  
**颗粒度选择**：`data_level` 取值含义如下（按粗到细）：
- `3.公司层级`
- `1.模块层级`
- `1.5.大小模块层级`
- `2.5内外层级`
- `4.组别层级`
- `5.经办层级`

> 说明：本项目即使最终要模块维度，也可能取 `data_level='4.组别层级'` 的数据源再汇总到 `agent_bucket`（以适配大小额/内外等组合维度）。按你实际表结构选择即可。

```sql
-- Natural Month Repay（月末状态）：模块维度（月粒度）
SELECT
  SUBSTR(dt_biz, 1, 7) AS month,
  agent_bucket,
  SUM(repay_principal) AS repay_principal,
  SUM(start_owing_principal) AS start_owing_principal
FROM tmp_maoruochen_phl_repay_natural_day_daily
WHERE dt_biz >= '${dt_start}'
  AND dt_biz <= '${dt_end}'
  AND substr(dt,9,2) = '01'             -- 月初 => 上月月末累计状态
  AND in_or_out = 'inhouse'             -- 仅内催
  AND data_level = '4.组别层级'         -- 按需替换（见 data_level 说明）
  AND owner_name <> 'Target'
  AND group_name <> 'Target'            -- 排除目标行（若存在）
GROUP BY
  SUBSTR(dt_biz, 1, 7),
  agent_bucket
;
```

---

## 3）日目标回款 + Achievement（日粒度）

**源表**: `phl_anls.rpt_coll_repay_target_dly4`

> **重要**：此表已包含日粒度的目标回款数据，可直接计算 achievement

**输出粒度**: `month + dt + owner_bucket + owner_group`

```sql
-- 日目标回款 + Achievement
-- 源表: phl_anls.rpt_coll_repay_target_dly4
SELECT
  TO_CHAR(dt, 'yyyyMM') AS month,
  TO_CHAR(dt, 'yyyy-MM-dd') AS dt,
  owner_bucket,
  owner_group,
  SUM(owing_principal) AS daily_owing_principal,
  SUM(repay_principal) / SUM(owing_principal) AS daily_repay_rate,
  SUM(target_repay_principal) AS target_repay_principal,
  SUM(repay_principal) AS actual_repay_principal,
  CASE WHEN SUM(target_repay_principal) <= 0 THEN 0
       ELSE SUM(repay_principal) / SUM(target_repay_principal)
  END AS achieve_rate
FROM (
  SELECT
    *,
    CASE
      WHEN owner_bucket = 'S0' AND case_overdue_days = -3 THEN 'H3'
      WHEN owner_bucket = 'S0' AND case_overdue_days = -2 THEN 'H2'
      WHEN owner_bucket = 'S0' AND case_overdue_days = -1 THEN 'H1'
      WHEN owner_bucket = 'S0' AND case_overdue_days >= 0 THEN 'H0'
      WHEN owner_bucket = 'S1' AND case_overdue_days <= 1 THEN '<=1'
      WHEN owner_bucket = 'S1' AND case_overdue_days <= 5 THEN '2-5'
      WHEN owner_bucket = 'S1' AND case_overdue_days >= 6 THEN '6-7'
      WHEN owner_bucket = 'S2' AND case_overdue_days <= 8 THEN '<=8'
      WHEN owner_bucket = 'S2' AND case_overdue_days <= 12 THEN '9-12'
      WHEN owner_bucket = 'S2' AND case_overdue_days >= 13 THEN '13-15'
      WHEN owner_bucket = 'M1' AND case_overdue_days <= 16 THEN '<=16'
      WHEN owner_bucket = 'M1' AND case_overdue_days >= 17 THEN '17-25'
      WHEN owner_bucket = 'M1' THEN '26-30'
      ELSE case_overdue_days
    END AS case_stage,
    CASE
      WHEN case_owing_principal <= 1000 THEN '<=1000'
      WHEN case_owing_principal <= 2000 THEN '1000-2000'
      WHEN case_owing_principal <= 5000 THEN '2000-5000'
      WHEN case_owing_principal > 5000 THEN '>5000'
    END AS principal_stage
  FROM phl_anls.rpt_coll_repay_target_dly4
  WHERE dt >= '${dt_start}'
    AND case_overdue_days > -99
    AND owner_bucket IN ('S0', 'S1', 'S2', 'M1')
) t
WHERE owner_bucket IN ('M1', 'S1', 'S2', 'S0')
  AND TO_CHAR(dt, 'yyyyMMdd') BETWEEN REPLACE('${dt_start}', '-', '') AND REPLACE('${dt_end}', '-', '')
GROUP BY
  TO_CHAR(dt, 'yyyyMM'),
  TO_CHAR(dt, 'yyyy-MM-dd'),
  owner_bucket,
  owner_group
HAVING SUM(owing_principal) > 0
ORDER BY month DESC, dt DESC, owner_bucket DESC, owner_group ASC;
```

---

## 4）EOM Target（月度目标）

```sql
-- EOM Target（月度目标）
SELECT
  product,
  module,
  target_repayment_rate,
  month
FROM module_eom_repay_target
WHERE month >= SUBSTR('${dt_start}', 1, 7)
  AND month <= SUBSTR('${dt_end}', 1, 7)
;
```

---

## 5）PTP 承诺还款（催员日粒度）

**源表**: `phl_anls.tmp_zyt_agent_ptp`

**输出粒度**: `dt + owner_name + owner_group`

```sql
-- PTP 承诺还款数据
-- 源表: phl_anls.tmp_zyt_agent_ptp
SELECT
  dt,
  owner_name,
  owner_group,
  SUM(ptp_case) AS ptp_case_cnt,
  SUM(ptp_today_case) AS ptp_today_case,
  SUM(today_actual_repay_case) AS today_actual_repay_case,
  CASE WHEN SUM(ptp_today_case) > 0
       THEN SUM(today_actual_repay_case) / SUM(ptp_today_case)
       ELSE 0
  END AS today_ptp_repay_rate
FROM phl_anls.tmp_zyt_agent_ptp
WHERE dt >= '${dt_start}'
  AND dt <= '${dt_end}'
GROUP BY dt, owner_name, owner_group
ORDER BY dt DESC, owner_name ASC
;
```

**聚合到组维度（按需）**：

```sql
-- PTP 承诺还款 - 组维度聚合
SELECT
  dt,
  owner_group,
  SUM(ptp_case) AS ptp_case_cnt,
  SUM(ptp_today_case) AS ptp_today_case,
  SUM(today_actual_repay_case) AS today_actual_repay_case,
  CASE WHEN SUM(ptp_today_case) > 0
       THEN SUM(today_actual_repay_case) / SUM(ptp_today_case)
       ELSE 0
  END AS today_ptp_repay_rate
FROM phl_anls.tmp_zyt_agent_ptp
WHERE dt >= '${dt_start}'
  AND dt <= '${dt_end}'
GROUP BY dt, owner_group
ORDER BY dt DESC, owner_group ASC
;
```

---

## 6）呼损率（组粒度）

**源表**: `phl_anls.tmp_phl_zyt_20_lark_genesys_daily`

> **仅统计一键外呼**：筛选条件 `call_type = '3'`

**输出粒度**: `dt + group_name`

```sql
-- 呼损率数据
-- 源表: phl_anls.tmp_phl_zyt_20_lark_genesys_daily
-- 仅统计一键外呼 (call_type = '3')
SELECT
  dt,
  group_name,
  SUM(call_loss) / (SUM(call_loss) + SUM(connect_times)) AS call_loss_rate,
  SUM(call_loss) AS call_loss,
  SUM(connect_times) AS connect_times
FROM phl_anls.tmp_phl_zyt_20_lark_genesys_daily
WHERE dt >= '${dt_start}'
  AND dt <= '${dt_end}'
  AND CAST(call_type AS STRING) = '3'
GROUP BY dt, group_name
ORDER BY dt DESC, group_name ASC
;
```

