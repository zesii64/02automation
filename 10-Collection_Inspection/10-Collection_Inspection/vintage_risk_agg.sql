-- 09 表聚合版 (v2.0 升级)：全链路风险口径
-- 新增维度：period_no (期数), flag_principal (金额段)
-- 新增指标：DPD5/15, 接通转化率分子分母 (Conversion)
SELECT due_date
     , mob
     , user_type
     , model_bin
     , period_no
     , flag_principal
     -- 基础资产 (Basic Asset)
     , SUM(owing_principal)     AS owing_principal
     , SUM(overdue_principal)   AS overdue_principal
     -- DPD 风险 (Risk Buckets)
     , SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= 6 THEN d6_principal END)   AS d6_principal   -- DPD5+
     , SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= 16 THEN d16_principal END) AS d16_principal  -- DPD15+
     , SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= 31 THEN d31_principal END) AS d31_principal  -- DPD30+
     , SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= 31 THEN owing_principal END) AS owing_principal_d31
     -- 转化率相关 (Conversion Metrics)
     -- 接通转化率 (Connect Conversion): 接通且未还清者，后续还回了多少
     -- 分子: 接通(is_touch=2)且D2未清(d2_payoff_flag=0)的 (逾期本金 - D16本金 = 回收本金)
     , SUM(CASE WHEN is_touch=2 AND d2_payoff_flag=0 THEN overdue_principal - d16_principal END) AS conn_conv_repay
     -- 分母: 接通且D2未清的 逾期本金
     , SUM(CASE WHEN is_touch=2 AND d2_payoff_flag=0 THEN overdue_principal END) AS conn_conv_base
     -- PTP 转化率 (PTP Conversion)
     -- 分子: 承诺(action_code like %PTP%)且D2未清的 (逾期本金 - D16本金)
     , SUM(CASE WHEN action_code LIKE '%PTP%' AND d2_payoff_flag=0 THEN overdue_principal - d16_principal END) AS ptp_conv_repay
     -- 分母: 承诺且D2未清的 逾期本金
     , SUM(CASE WHEN action_code LIKE '%PTP%' AND d2_payoff_flag=0 THEN overdue_principal END) AS ptp_conv_base
FROM tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE flag_dq = 1
  AND due_date >= '2025-12-01'
GROUP BY due_date
       , mob
       , user_type
       , model_bin
       , period_no
       , flag_principal
;
