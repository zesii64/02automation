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
  owner_bucket,
  substr(dt,1,7) as month,
  CONCAT(
    CASE 
        WHEN WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')) = 0 THEN  
          TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), -1, 'dd'), 'yyyy-MM-dd')
        ELSE  
          TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), - (WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')) + 1), 'dd'), 'yyyy-MM-dd')
    END 
    ,'-'
    ,CASE 
        WHEN WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')) = 0 THEN  
          TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), 5, 'dd'), 'yyyy-MM-dd')
        ELSE 
          TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), 5 - WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')), 'dd'), 'yyyy-MM-dd')
      END
    ) AS week,
  dt,
  GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1) AS headcount,
  GREATEST(COUNT(DISTINCT owner_name), 1) AS ownercount,
  SUM(owing_case_cnt) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour > 0 THEN owner_name END), 1)
                         * COUNT(DISTINCT dt)) AS owing_case_cnt_avg,
  CASE WHEN SUM(owing_case_cnt) > 0
       THEN SUM(comm_times) / (SUM(owing_case_cnt) - SUM(own_uncomm_case_cnt)) END AS cover_times,
  CASE WHEN SUM(owing_case_cnt) > 0
       THEN 1 - SUM(own_uncomm_case_cnt) / SUM(owing_case_cnt) END AS cover_rate,
  CASE WHEN SUM(owing_case_cnt) > 0
       THEN SUM(art_comm_times) / (SUM(owing_case_cnt) - SUM(own_uncomm_case_cnt)) END AS art_cover_times,
  CASE WHEN SUM(owing_case_cnt) > 0
       THEN SUM(batch_comm_times) / (SUM(owing_case_cnt) - SUM(own_uncomm_case_cnt)) END AS batch_cover_times,
  SUM(call_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                     * COUNT(DISTINCT dt)) AS call_times_avg,
  SUM(art_call_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                         * COUNT(DISTINCT dt)) AS art_call_times_avg,
  SUM(batch_call_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                           * COUNT(DISTINCT dt)) AS batch_call_times_avg,
  SUM(call_user_mobile_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                                 * COUNT(DISTINCT dt)) AS call_user_mobile_times_avg,
  SUM(call_contact_mobile_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                                    * COUNT(DISTINCT dt)) AS call_contact_mobile_times_avg,
  CASE WHEN SUM(owing_case_cnt) > 0
       THEN SUM(call_connect_mobile_cnt) / SUM(call_mobile_cnt) END AS mobile_number_connect_rate,
  SUM(call_connect_mobile_cnt) AS call_connect_mobile_cnt,
  SUM(call_billsec / 60) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                            * COUNT(DISTINCT dt)) AS call_billhr_avg,
  SUM(call_connect_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                              * COUNT(DISTINCT dt)) AS call_connect_times_avg,
  (SUM(call_billsec / 60) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                             * COUNT(DISTINCT dt)))
    / (SUM(call_connect_times) / (GREATEST(COUNT(DISTINCT CASE WHEN last_call_hour - first_call_hour >= 8 THEN owner_name END), 1)
                                  * COUNT(DISTINCT dt))) AS single_call_duration,
  CASE WHEN SUM(owing_case_cnt) > 0
       THEN SUM(comm_connect_own_case_cnt) / (SUM(owing_case_cnt) - SUM(own_uncomm_case_cnt)) END AS case_connect_rate,
  CASE WHEN SUM(owing_case_cnt) > 0
       THEN SUM(call_connect_times) / SUM(call_times) END AS call_connect_rate
FROM phl_anls.tmp_liujun_ana_11_agent_process_daily
WHERE dt >= '2026-01-19'
  AND (DAYOFWEEK(dt) + 12) % 7 + 1 != 7
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
  owner_bucket,
  CONCAT(
    CASE 
        WHEN WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')) = 0 THEN  
          TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), -1, 'dd'), 'yyyy-MM-dd')
        ELSE  
          TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), - (WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')) + 1), 'dd'), 'yyyy-MM-dd')
    END 
    ,'-'
    ,CASE 
        WHEN WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')) = 0 THEN  
          TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), 5, 'dd'), 'yyyy-MM-dd')
        ELSE 
          TO_CHAR(DATEADD(TO_DATE(dt, 'yyyy-MM-dd'), 5 - WEEKDAY(TO_DATE(dt, 'yyyy-MM-dd')), 'dd'), 'yyyy-MM-dd')
      END
    )
  ,substr(dt,1,7)
ORDER BY week DESC, product DESC
;