SELECT
  to_char(to_date(dt),'yyyymm'),
  owner_bucket,
  owner_group,
  owing_amount_alloc_bin,
  SUM(call_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                     * COUNT(DISTINCT dt)) as call_times_avg,
  SUM(art_call_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                         * COUNT(DISTINCT dt)) art_call_times_avg,
  SUM(batch_call_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                           * COUNT(DISTINCT dt)) batch_call_times_avg,
  SUM(call_user_mobile_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                         * COUNT(DISTINCT dt)) call_user_mobile_times_avg,
  SUM(call_contact_mobile_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                           * COUNT(DISTINCT dt)) call_contact_mobile_times_avg,
  SUM(art_call_connect_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                                 * COUNT(DISTINCT dt)) art_call_connect_times_avg,
  SUM(call_billsec / 60) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                            * 60 * COUNT(DISTINCT dt)) call_billhr_avg,
  60 * (SUM(call_billsec / 60) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                                  * 60 * COUNT(DISTINCT dt)))
    / (SUM(call_connect_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                                  * COUNT(DISTINCT dt))) single_call_duration,
  CASE WHEN SUM(owing_case_cnt) > 0 THEN SUM(comm_times) / (SUM(owing_case_cnt) - SUM(own_uncomm_case_cnt)) END cover_times,
  CASE WHEN SUM(owing_case_cnt) > 0 THEN 1 - SUM(own_uncomm_case_cnt) / SUM(owing_case_cnt) END cover_rate,
  SUM(owing_case_cnt) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour > 0 THEN owner_name END), 1)
                        * COUNT(DISTINCT dt)) caseload,
  SUM(call_mobile_cnt) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour > 0 THEN owner_name END), 1)
                         * COUNT(DISTINCT dt)
                         * GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                         / GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour > 0 THEN owner_name END), 1)) penetration_rate,
  sum(comm_connect_own_case_cnt)/(sum(owing_case_cnt)-sum(own_uncomm_case_cnt)) as case_connect_rate,
  sum(call_connect_times)/sum(call_times) as call_connect_rate
FROM phl_anls.tmp_liujun_ana_11_agent_process_daily
WHERE CAST(call_8h_flag AS string) = '1'
  AND dt >= '2025-12-01'
  and owner_bucket IN ('M1','M2','M2+','S0','S1','S2')
  and is_outs_owner = 0
GROUP BY
  to_char(to_date(dt),'yyyymm'),
  owner_bucket,
  owner_group,
  owing_amount_alloc_bin;
