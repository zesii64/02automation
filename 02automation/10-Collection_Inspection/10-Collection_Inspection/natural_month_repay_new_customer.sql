SELECT
  days_from_duedate,
  due_mth,
  1 - SUM(owing_principal_eoc) / SUM(overdue_principal_boc)
FROM phl_anls.tmp_liujun_phl_repay_fnl_daily
WHERE user_type = '新客'
  AND flag_bucket = 'ALL'
  AND due_mth IN (
    '202508','202509','202510','202511','202512','202601','202602'
  )
GROUP BY days_from_duedate, due_mth
ORDER BY days_from_duedate ASC, due_mth ASC;