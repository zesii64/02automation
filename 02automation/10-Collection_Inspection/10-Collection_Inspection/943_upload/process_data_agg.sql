-- 过程表聚合版：不在最小颗粒度，按 月 + owner_bucket + owner_group 聚合（去掉 owing_amount_alloc_bin）。
-- 指标仍按“有效催员·天”平均，仅减少维度以减行数。
SELECT TO_CHAR(TO_DATE(dt), 'yyyymm') AS natural_month
     , owner_bucket
     , owner_group
     , SUM(call_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS call_times_avg
     , SUM(art_call_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS art_call_times_avg
     , SUM(batch_call_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS batch_call_times_avg
     , SUM(call_user_mobile_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS call_user_mobile_times_avg
     , SUM(call_contact_mobile_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS call_contact_mobile_times_avg
     , SUM(art_call_connect_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS art_call_connect_times_avg
     , SUM(call_billsec / 60) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * 60 * COUNT(DISTINCT dt)) AS call_billhr_avg
     , 60 * (SUM(call_billsec / 60) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * 60 * COUNT(DISTINCT dt)))
         / (SUM(call_connect_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) * COUNT(DISTINCT dt))) AS single_call_duration
     , CASE WHEN SUM(owing_case_cnt) > 0 THEN SUM(comm_times) / (SUM(owing_case_cnt) - SUM(own_uncomm_case_cnt)) END AS cover_times
     , CASE WHEN SUM(owing_case_cnt) > 0 THEN 1 - SUM(own_uncomm_case_cnt) / SUM(owing_case_cnt) END AS cover_rate
     , SUM(owing_case_cnt) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour > 0 THEN owner_name END), 1) * COUNT(DISTINCT dt)) AS caseload
     , SUM(call_mobile_cnt) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour > 0 THEN owner_name END), 1) * COUNT(DISTINCT dt)
         * GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
         / GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour > 0 THEN owner_name END), 1)) AS penetration_rate
     , SUM(comm_connect_own_case_cnt) / (SUM(owing_case_cnt) - SUM(own_uncomm_case_cnt)) AS case_connect_rate
     , SUM(call_connect_times) / SUM(call_times) AS call_connect_rate
     , SUM(call_times) AS raw_call_times
     , SUM(call_connect_times) AS raw_call_connect_times
     , SUM(owing_case_cnt) AS raw_owing_case_cnt
     , SUM(own_uncomm_case_cnt) AS raw_uncomm_case_cnt
FROM phl_anls.tmp_liujun_ana_11_agent_process_daily
WHERE CAST(call_8h_flag AS STRING) = '1'
  AND dt >= '2025-12-01'
  AND owner_bucket IN ('M1','M2','M2+','S0','S1','S2')
  AND is_outs_owner = 0
GROUP BY TO_CHAR(TO_DATE(dt), 'yyyymm'), owner_bucket, owner_group
;
