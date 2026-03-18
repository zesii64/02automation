-- 自然月回收聚合到催员维度：去掉 day，按 自然月 + case_bucket + agent_bucket + group_name + owner_id 聚合。
-- 报表需要：整体回收率 + 按 case_bucket/group_name 最差 3 段，列名与明细版一致便于复用。
SELECT TO_CHAR(dt_biz, 'yyyyMM') AS natural_month
     , case_bucket
     , agent_bucket
     , group_name
     , owner_id
     , SUM(repay_principal)         AS repay_principal
     , SUM(start_owing_principal)   AS start_owing_principal
FROM phl_anls.tmp_maoruochen_phl_repay_natural_day_daily
WHERE 1 = 1
  AND case_bucket IN ('S0','S1','S2','M1','M2')
  AND TO_CHAR(dt_biz, 'yyyyMM') >= '202512'
GROUP BY TO_CHAR(dt_biz, 'yyyyMM')
       , case_bucket
       , agent_bucket
       , group_name
       , owner_id
;
