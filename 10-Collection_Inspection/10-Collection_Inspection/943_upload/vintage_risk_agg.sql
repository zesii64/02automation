-- 09 表聚合版：不下明细，按常用维度 group by，行数大幅减少。
-- 维度：due_date + mob + user_type（到期日+账龄+新老客）；报表只需总入催率/dpd30，本地再 sum 即可。
-- 若需更粗：可改为仅 due_date,mob 或仅 due_date。
SELECT due_date
     , mob
     , user_type
     , model_bin
     , SUM(overdue_principal)   AS overdue_principal
     , SUM(owing_principal)    AS owing_principal
     , SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= 31 THEN d31_principal END)     AS d31_principal
     , SUM(CASE WHEN DATEDIFF(now(), TO_DATE(due_date)) >= 31 THEN owing_principal END) AS owing_principal_d31
FROM tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE flag_dq = 1
  AND due_date >= '2025-12-01'
GROUP BY due_date, mob, user_type, model_bin
;
