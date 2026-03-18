set
  odps.idata.system.id = quickbi_query;
set
  odps.sql.submit.mode = script;
set
  odps.task.sql.realtime = all;
set
  odps.sql.type.system.odps2 = true;
-- SQL From QuickBI, traceId: 73bc0838-5bb8-4636-89e3-6caa9612dc3d
SELECT
  A13_T_1_.`day` AS T_A92_2_,
  TO_CHAR(A13_T_1_.`dt_biz`, 'yyyyMM') AS T_ACA_3_,
  sum(A13_T_1_.`repay_principal`) / sum(A13_T_1_.`start_owing_principal`) AS T_A91_4_
FROM
  (
    select
      *
    from
      phl_anls.tmp_maoruochen_phl_repay_natural_day_daily
  ) A13_T_1_
WHERE
  A13_T_1_.`case_bucket` = 'S1_Large'
  AND A13_T_1_.`data_level` = '1.5.大小模块层级'
  AND TO_CHAR(A13_T_1_.`dt_biz`, 'yyyyMM') >= '202511'
GROUP BY
  A13_T_1_.`day`,
  TO_CHAR(A13_T_1_.`dt_biz`, 'yyyyMM')
LIMIT
  1000