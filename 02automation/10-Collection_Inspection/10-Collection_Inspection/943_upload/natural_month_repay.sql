SELECT
  case_bucket
  ,day
  ,TO_CHAR(dt_biz, 'yyyyMM')
  ,agent_bucket
  ,group_name
  ,owner_id
  ,data_level
  ,SUM(repay_principal) AS repay_principal
  ,SUM(start_owing_principal) AS start_owing_principal
FROM phl_anls.tmp_maoruochen_phl_repay_natural_day_daily
WHERE 1=1
  -- 不限制 data_level；若需只看经办层级可改为: AND data_level = '5.经办层级'
  AND case_bucket IN ('S0','S1','S2','M1','M2')
  AND TO_CHAR(dt_biz, 'yyyyMM') >= '202512'
GROUP BY case_bucket
,day
,TO_CHAR(dt_biz, 'yyyyMM')
,data_level
,agent_bucket
,group_name
,owner_id
;
