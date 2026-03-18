set
  odps.idata.system.id = quickbi_query;
set
  odps.sql.submit.mode = script;
set
  odps.task.sql.realtime = all;
set
  odps.sql.type.system.odps2 = true;
-- SQL From QuickBI, traceId: d5458ad0-5202-48a0-8dd9-fc6f26e8cdd4
SELECT
  A96_T_1_.`days_from_duedate` AS T_A31_2_,
  A96_T_1_.`due_mth` AS T_AE1_3_,
  1 - sum(A96_T_1_.`owing_principal_eoc`) / sum(A96_T_1_.`overdue_principal_boc`) AS T_A4F_4_
FROM
  (
    SELECT
      *
    FROM
      phl_anls.tmp_liujun_phl_repay_fnl_daily
  ) A96_T_1_
WHERE
  A96_T_1_.`user_type` = '老客'
  AND A96_T_1_.`flag_bucket` = 'ALL'
  AND A96_T_1_.`due_mth` IN (
    '202501',
    '202502',
    '202503',
    '202504',
    '202505',
    '202506',
    '202507',
    '202508',
    '202509',
    '202510',
    '202511',
    '202512',
    '202601',
    '202602'
  )
GROUP BY
  A96_T_1_.`days_from_duedate`,
  A96_T_1_.`due_mth`
ORDER BY
  T_A31_2_ ASC,
  T_AE1_3_ ASC
LIMIT
  1000