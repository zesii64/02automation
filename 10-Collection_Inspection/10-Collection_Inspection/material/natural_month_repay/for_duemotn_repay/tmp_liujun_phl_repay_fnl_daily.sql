--@exclude_input=phl_anls.tmp_liujun_phl_repay_04_target_daily
--@exclude_input=phl_anls.tmp_liujun_phl_repay_05_target_daily
--odps sql 
--********************************************************************--
--author:刘军
--create time:2022-12-09 14:15:43
-- 20240125: 新增biz_line字段
-- 20240202：仅看cashloan的回款，新增product_name的限制条件
-- 20250908 wangyukun 回款逻辑与账龄表统一，取零点时刻的数据；新增dpd=dt-duedate维度
--********************************************************************--
-- step01-取出所有到期的债务并计算未入催的本金
DROP TABLE IF EXISTS phl_anls.tmp_liujun_phl_repay_01_daily
;

CREATE TABLE IF NOT EXISTS phl_anls.tmp_liujun_phl_repay_01_daily AS
SELECT  a.user_id
        ,a.debt_id
        ,a.principal
        ,a.due_mth
        ,a.due_day
        ,a.overdue_day
        ,TO_DATE(a.due_date) AS due_date -- 应还日期
        ,TO_DATE(DATE_ADD(TO_DATE(a.due_date),30)) AS end_due_date --应还日期+30天
        ,(
                    CASE   WHEN a.user_type IN ('新客') THEN '新客'
                            WHEN a.user_type IN ('新转化老客','存量老客') THEN '老客'
                    END
        ) AS user_type
        ,a.term_fnl
        ,a.total_not_overdue_amount
        ,a.biz_line
        ,d.d_code_min -- due_mth新入催的第一天
        ,d.d_code_max -- due_mth新入催的最后一天
FROM    (
            SELECT  *
                    ,SUBSTR(TRANSLATE(CAST(TO_DATE(due_date) AS VARCHAR(10)),'-',''),1,6) AS due_mth
                    ,SUBSTR(TRANSLATE(CAST(TO_DATE(due_date) AS VARCHAR(10)),'-',''),7,2) AS due_day
            FROM    phl_anls.tmp_liujun_phl_ana_01_eoc_debt_daily
            WHERE   TO_DATE(due_date) > '2022-01-01'
            -- AND     MONTHS_BETWEEN(now(),TO_DATE(due_date)) BETWEEN 0 AND 7
            AND     TO_DATE(due_date) >= CONCAT(SUBSTR((DATEADD(TO_DATE(now()),-6,'mm')),1,7),'-01')
            AND     flag_dq = 1
            AND     is_first_col = 1
            AND     overdue_day >= 1
            AND     DATEDIFF(due_date,now()) <= 0
            AND     product_name IN ('installment loan 001','pay day loan 001','Lazada PDL','Lazada Ins','ppl-free','ppl-ins')
        ) a
LEFT JOIN   (
                -- due_mth新入催的第一天和最后一天
                SELECT  SUBSTR(TRANSLATE(CAST(TO_DATE(d_code) AS VARCHAR(10)),'-',''),1,6) AS due_mth
                        ,MIN(d_code) AS d_code_min
                        ,MAX(d_code) AS d_code_max
                FROM    phl_data.dim_date
                GROUP BY SUBSTR(TRANSLATE(CAST(TO_DATE(d_code) AS VARCHAR(10)),'-',''),1,6)
            ) d
ON      a.due_mth = d.due_mth
;

-- 取每日回款的观察切片数据
-- DROP TABLE IF EXISTS phl_anls.tmp_liujun_phl_repay_02_daily_v2
-- ;

-- CREATE TABLE phl_anls.tmp_liujun_phl_repay_02_daily_v2 AS
insert overwrite table phl_anls.tmp_liujun_phl_repay_02_daily_v2
select a.* 
from (
select * 
from phl_anls.tmp_liujun_phl_repay_02_daily_v2
where dt < '${BATCH_DATE}'
union all 
SELECT  dt,debt_id,listing_id,due_date
,amount - repay_amount as owing_amount
,principal - repay_principal as owing_principal
-- FROM    phl_data.dwd_fact_debt_detail_info_snp
from  phl_data.dwb_coll_fact_debt_list_info_snp
WHERE   dt >= '2022-01-01'
AND dt >= '${BATCH_DATE}'
-- and     app = 'juanhand'
AND     MONTHS_BETWEEN(now(),dt) BETWEEN 0 AND 8
) a
INNER JOIN phl_anls.tmp_liujun_phl_repay_01_daily b
ON      a.debt_id = b.debt_id
;

-- All
DROP TABLE IF EXISTS phl_anls.tmp_liujun_phl_repay_03_all_daily
;
CREATE TABLE IF NOT EXISTS phl_anls.tmp_liujun_phl_repay_03_all_daily AS
-- DROP TABLE IF EXISTS phl_anls.test_wyk_phl_repay_03_all_daily
-- ;
-- CREATE TABLE IF NOT EXISTS phl_anls.test_wyk_phl_repay_03_all_daily AS
SELECT  due_mth
        ,due_day
        ,user_type
        ,term_fnl
        ,biz_line
        ,days_from_duedate
        ,dpd
        ,'ALL' AS flag_bucket
        ,SUM(CASE WHEN re = 1 THEN 1 ELSE 0 END) AS overdue_act
        ,SUM(CASE WHEN re = 1 THEN overdue_principal ELSE 0 END) overdue_principal
        ,SUM(overdue_principal) AS overdue_principal_boc
        ,SUM(owing_principal) AS owing_principal_eoc
FROM    (
            SELECT  *
                    ,ROW_NUMBER() OVER (PARTITION BY debt_id ORDER BY days_from_duedate ) AS re
            FROM    (
                        SELECT  p.user_id
                                ,p.debt_id
                                ,p.due_mth
                                ,p.due_day
                                ,p.user_type
                                ,p.term_fnl
                                ,p.biz_line
                                ,r.dt AS obs_dt -- 观察每日剩余应还本金
                                ,DATEDIFF(r.dt,p.d_code_min) + 1 AS days_from_duedate
                                ,DATEDIFF(r.dt,p.due_date) as dpd
                                ,r.owing_principal AS owing_principal_intl --每个观察日的剩余应还本金，即使已经30及以上了
                                ,p.principal -- 应还本金
                                ,(
                                            CASE   WHEN p.overdue_day > 0 THEN p.principal - p.total_not_overdue_amount
                                                    ELSE 0
                                            END
                                ) AS overdue_principal -- 期初本金,不同阶段不同计算方式
                                ,(
                                            CASE   WHEN r.dt <= TO_DATE(DATE_ADD(TO_DATE(p.due_date),31)) THEN r.owing_principal
                                                    ELSE s.owing_principal
                                            END
                                ) AS owing_principal -- 期末本金
                        FROM    (
                                    SELECT  *
                                    FROM    phl_anls.tmp_liujun_phl_repay_01_daily
                                    WHERE   overdue_day > 0
                                ) p
                        LEFT JOIN phl_anls.tmp_liujun_phl_repay_02_daily_v2 r
                        ON      p.debt_id = r.debt_id
                        AND     r.dt >= TO_DATE(DATE_ADD(TO_DATE(p.due_date),1))
                        AND     r.dt <= TO_DATE(DATE_ADD(d_code_max,31))
                        LEFT JOIN phl_anls.tmp_liujun_phl_repay_02_daily_v2 s
                        ON      p.debt_id = s.debt_id
                        AND     TO_DATE(DATE_ADD(TO_DATE(p.due_date),31)) = s.dt
                        WHERE   DATEDIFF(r.dt,p.d_code_min) > 0
                        ORDER BY p.user_id,DATEDIFF(r.dt,p.d_code_min) + 1
                    ) tmp0
        ) tmp1
GROUP BY due_mth
         ,due_day
         ,user_type
         ,term_fnl
         ,biz_line
         ,days_from_duedate
         ,dpd
         ,'ALL'
;

-- S1
DROP TABLE IF EXISTS phl_anls.tmp_liujun_phl_repay_03_S1_daily
;

CREATE TABLE IF NOT EXISTS phl_anls.tmp_liujun_phl_repay_03_S1_daily AS
SELECT  due_mth
        ,due_day
        ,user_type
        ,term_fnl
        ,biz_line
        ,days_from_duedate
        ,dpd
        ,'S1' AS flag_bucket
        ,SUM(CASE WHEN re = 1 THEN 1 ELSE 0 END) AS overdue_act
        ,SUM(CASE WHEN re = 1 THEN overdue_principal ELSE 0 END) overdue_principal
        ,SUM(overdue_principal) AS overdue_principal_boc
        ,SUM(owing_principal) AS owing_principal_eoc
FROM    (
            SELECT  *
                    ,ROW_NUMBER() OVER (PARTITION BY debt_id ORDER BY days_from_duedate ) AS re
            FROM    (
                        SELECT  p.user_id
                                ,p.debt_id
                                ,p.due_mth
                                ,p.due_day
                                ,p.user_type
                                ,p.term_fnl
                                ,p.biz_line -- 观察每日剩余应还本金
                                ,r.dt AS obs_dt
                                ,DATEDIFF(r.dt,p.d_code_min) + 1 AS days_from_duedate
                                ,DATEDIFF(r.dt,p.due_date) as dpd
                                ,r.owing_principal AS owing_principal_intl --每个观察日的剩余应还本金，即使已经30及以上了                              
                                ,p.principal -- 应还本金
                                ,(
                                            CASE   WHEN p.overdue_day > 0 THEN p.principal - p.total_not_overdue_amount
                                                    ELSE 0
                                            END
                                ) AS overdue_principal -- 期初本金,不同阶段不同计算方式
                                ,(
                                            CASE   WHEN r.dt <= TO_DATE(DATE_ADD(TO_DATE(p.due_date),8)) THEN r.owing_principal
                                                    ELSE s.owing_principal
                                            END
                                ) AS owing_principal -- 期末本金
                        FROM    (
                                    SELECT  *
                                    FROM    phl_anls.tmp_liujun_phl_repay_01_daily
                                    WHERE   overdue_day > 0
                                ) p
                        LEFT JOIN phl_anls.tmp_liujun_phl_repay_02_daily_v2 r
                        ON      p.debt_id = r.debt_id
                        AND     r.dt >= TO_DATE(DATE_ADD(TO_DATE(p.due_date),1))
                        AND     r.dt <= TO_DATE(DATE_ADD(d_code_max,8))
                        LEFT JOIN phl_anls.tmp_liujun_phl_repay_02_daily_v2 s
                        ON      p.debt_id = s.debt_id
                        AND     TO_DATE(DATE_ADD(TO_DATE(p.due_date),8)) = s.dt
                        WHERE   DATEDIFF(r.dt,p.d_code_min) > 0
                        ORDER BY 1,9
                    ) tmp0
        ) tmp1
GROUP BY due_mth
         ,due_day
         ,user_type
         ,term_fnl
         ,biz_line
         ,days_from_duedate
         ,dpd
         ,'S1'
;

-- S2
DROP TABLE IF EXISTS phl_anls.tmp_liujun_phl_repay_03_S2_daily
;

CREATE TABLE IF NOT EXISTS phl_anls.tmp_liujun_phl_repay_03_S2_daily AS
SELECT  due_mth
        ,due_day
        ,user_type
        ,term_fnl
        ,biz_line
        ,days_from_duedate
        ,dpd
        ,'S2' AS flag_bucket
        ,SUM(CASE WHEN re = 1 THEN 1 ELSE 0 END) AS overdue_act
        ,SUM(CASE WHEN re = 1 THEN overdue_principal ELSE 0 END) overdue_principal
        ,SUM(overdue_principal) AS overdue_principal_boc
        ,SUM(owing_principal) AS owing_principal_eoc
FROM    (
            SELECT  *
                    ,ROW_NUMBER() OVER (PARTITION BY debt_id ORDER BY days_from_duedate ) AS re
            FROM    (
                        SELECT  p.user_id
                                ,p.debt_id
                                ,p.due_mth
                                ,p.due_day
                                ,p.user_type
                                ,p.term_fnl
                                ,p.biz_line -- 观察每日剩余应还本金
                                ,r.dt AS obs_dt
                                ,DATEDIFF(r.dt,p.d_code_min) + 1 AS days_from_duedate
                                ,DATEDIFF(r.dt,p.due_date) as dpd
                                ,r.owing_principal AS owing_principal_intl --每个观察日的剩余应还本金，即使已经30及以上了
                                ,p.principal -- 应还本金
                                ,(
                                            CASE   WHEN p.overdue_day > 7 THEN q.owing_principal
                                                    ELSE 0
                                            END
                                ) AS overdue_principal -- 期初本金,不同阶段不同计算方式
                                ,(
                                            CASE   WHEN r.dt <= TO_DATE(DATE_ADD(TO_DATE(p.due_date),16)) THEN r.owing_principal
                                                    ELSE s.owing_principal
                                            END
                                ) AS owing_principal -- 期末本金
                        FROM    (
                                    SELECT  *
                                    FROM    phl_anls.tmp_liujun_phl_repay_01_daily
                                    WHERE   overdue_day > 7
                                ) p
                        LEFT JOIN phl_anls.tmp_liujun_phl_repay_02_daily_v2 q
                        ON      p.debt_id = q.debt_id
                        AND     TO_DATE(DATE_ADD(TO_DATE(p.due_date),8)) = q.dt
                        LEFT JOIN phl_anls.tmp_liujun_phl_repay_02_daily_v2 r
                        ON      p.debt_id = r.debt_id
                        AND     r.dt >= TO_DATE(DATE_ADD(TO_DATE(p.due_date),8))
                        AND     r.dt <= TO_DATE(DATE_ADD(d_code_max,16))
                        LEFT JOIN phl_anls.tmp_liujun_phl_repay_02_daily_v2 s
                        ON      p.debt_id = s.debt_id
                        AND     TO_DATE(DATE_ADD(TO_DATE(p.due_date),16)) = s.dt
                        ORDER BY 1,9
                    ) tmp0
        ) tmp1
GROUP BY due_mth
         ,due_day
         ,user_type
         ,term_fnl
         ,biz_line
         ,days_from_duedate
         ,dpd
         ,'S2'
;

-- M1
DROP TABLE IF EXISTS phl_anls.tmp_liujun_phl_repay_03_M1_daily
;

CREATE TABLE IF NOT EXISTS phl_anls.tmp_liujun_phl_repay_03_M1_daily AS
SELECT  due_mth
        ,due_day
        ,user_type
        ,term_fnl
        ,biz_line
        ,days_from_duedate
        ,dpd
        ,'M1' AS flag_bucket
        ,SUM(CASE WHEN re = 1 THEN 1 ELSE 0 END) AS overdue_act
        ,SUM(CASE WHEN re = 1 THEN overdue_principal ELSE 0 END) overdue_principal
        ,SUM(overdue_principal) AS overdue_principal_boc
        ,SUM(owing_principal) AS owing_principal_eoc
FROM    (
            SELECT  *
                    ,ROW_NUMBER() OVER (PARTITION BY debt_id ORDER BY days_from_duedate ) AS re
            FROM    (
                        SELECT  p.user_id
                                ,p.debt_id
                                ,p.due_mth
                                ,p.due_day
                                ,p.user_type
                                ,p.term_fnl
                                ,p.biz_line -- 观察每日剩余应还本金
                                ,r.dt AS obs_dt
                                ,DATEDIFF(r.dt,p.d_code_min) + 1 AS days_from_duedate
                                ,DATEDIFF(r.dt,p.due_date) as dpd
                                ,r.owing_principal AS owing_principal_intl --每个观察日的剩余应还本金，即使已经30及以上了
                                ,p.principal -- 应还本金
                                ,(
                                            CASE   WHEN p.overdue_day > 15 THEN q.owing_principal
                                                    ELSE 0
                                            END
                                ) AS overdue_principal -- 期初本金,不同阶段不同计算方式
                                ,(
                                            CASE   WHEN r.dt <= TO_DATE(DATE_ADD(TO_DATE(p.due_date),31)) THEN r.owing_principal
                                                    ELSE s.owing_principal
                                            END
                                ) AS owing_principal -- 期末本金
                        FROM    (
                                    SELECT  *
                                    FROM    phl_anls.tmp_liujun_phl_repay_01_daily
                                    WHERE   overdue_day > 15
                                ) p
                        LEFT JOIN phl_anls.tmp_liujun_phl_repay_02_daily_v2 q
                        ON      p.debt_id = q.debt_id
                        AND     TO_DATE(DATE_ADD(TO_DATE(p.due_date),16)) = q.dt
                        LEFT JOIN phl_anls.tmp_liujun_phl_repay_02_daily_v2 r
                        ON      p.debt_id = r.debt_id
                        AND     r.dt >= TO_DATE(DATE_ADD(TO_DATE(p.due_date),16))
                        AND     r.dt <= TO_DATE(DATE_ADD(d_code_max,31))
                        LEFT JOIN phl_anls.tmp_liujun_phl_repay_02_daily_v2 s
                        ON      p.debt_id = s.debt_id
                        AND     TO_DATE(DATE_ADD(TO_DATE(p.due_date),31)) = s.dt
                        WHERE   DATEDIFF(r.dt,p.d_code_min) > 0
                        ORDER BY 1,9
                    ) tmp0
        ) tmp1
GROUP BY due_mth
         ,due_day
         ,user_type
         ,term_fnl
         ,biz_line
         ,days_from_duedate
         ,dpd
         ,'M1'
;

-- M2
DROP TABLE IF EXISTS phl_anls.tmp_liujun_phl_repay_03_M2_daily
;

CREATE TABLE IF NOT EXISTS phl_anls.tmp_liujun_phl_repay_03_M2_daily AS
SELECT  due_mth
        ,due_day
        ,user_type
        ,term_fnl
        ,biz_line
        ,days_from_duedate
        ,dpd
        ,'M2' AS flag_bucket
        ,SUM(CASE WHEN re = 1 THEN 1 ELSE 0 END) AS overdue_act
        ,SUM(CASE WHEN re = 1 THEN overdue_principal ELSE 0 END) overdue_principal
        ,SUM(overdue_principal) AS overdue_principal_boc
        ,SUM(owing_principal) AS owing_principal_eoc
FROM    (
            SELECT  *
                    ,ROW_NUMBER() OVER (PARTITION BY debt_id ORDER BY days_from_duedate ) AS re
            FROM    (
                        SELECT  p.user_id
                                ,p.debt_id
                                ,p.due_mth
                                ,p.due_day
                                ,p.user_type
                                ,p.term_fnl
                                ,p.biz_line -- 观察每日剩余应还本金
                                ,r.dt AS obs_dt
                                ,DATEDIFF(r.dt,p.d_code_min) + 1 AS days_from_duedate
                                ,DATEDIFF(r.dt,p.due_date) as dpd
                                ,r.owing_principal AS owing_principal_intl --每个观察日的剩余应还本金，即使已经30及以上了
                                ,p.principal -- 应还本金
                                ,(
                                            CASE   WHEN p.overdue_day > 30 THEN q.owing_principal
                                                    ELSE 0
                                            END
                                ) AS overdue_principal -- 期初本金,不同阶段不同计算方式
                                ,(
                                            CASE   WHEN r.dt <= TO_DATE(DATE_ADD(TO_DATE(p.due_date),61)) THEN r.owing_principal
                                                    ELSE s.owing_principal
                                            END
                                ) AS owing_principal -- 期末本金
                        FROM    (
                                    SELECT  *
                                    FROM    phl_anls.tmp_liujun_phl_repay_01_daily
                                    WHERE   overdue_day > 30
                                ) p
                        LEFT JOIN phl_anls.tmp_liujun_phl_repay_02_daily_v2 q
                        ON      p.debt_id = q.debt_id
                        AND     TO_DATE(DATE_ADD(TO_DATE(p.due_date),31)) = q.dt
                        LEFT JOIN phl_anls.tmp_liujun_phl_repay_02_daily_v2 r
                        ON      p.debt_id = r.debt_id
                        AND     r.dt >= TO_DATE(DATE_ADD(TO_DATE(p.due_date),31))
                        AND     r.dt <= TO_DATE(DATE_ADD(d_code_max,61))
                        LEFT JOIN phl_anls.tmp_liujun_phl_repay_02_daily_v2 s
                        ON      p.debt_id = s.debt_id
                        AND     TO_DATE(DATE_ADD(TO_DATE(p.due_date),61)) = s.dt
                        WHERE   DATEDIFF(r.dt,p.d_code_min) > 0
                        ORDER BY 1,9
                    ) tmp0
        ) tmp1
GROUP BY due_mth
         ,due_day
         ,user_type
         ,term_fnl
         ,biz_line
         ,days_from_duedate
         ,dpd
         ,'M2'
;

DROP TABLE IF EXISTS phl_anls.tmp_liujun_phl_repay_fnl_daily
;

CREATE TABLE IF NOT EXISTS phl_anls.tmp_liujun_phl_repay_fnl_daily AS
SELECT  *
FROM    phl_anls.tmp_liujun_phl_repay_03_all_daily
UNION ALL
SELECT  *
FROM    phl_anls.tmp_liujun_phl_repay_03_S1_daily
UNION ALL
SELECT  *
FROM    phl_anls.tmp_liujun_phl_repay_03_S2_daily
UNION ALL
SELECT  *
FROM    phl_anls.tmp_liujun_phl_repay_03_M1_daily
UNION ALL
SELECT  *
FROM    phl_anls.tmp_liujun_phl_repay_03_M2_daily
-- UNION ALL
-- SELECT  *
-- FROM    phl_anls.tmp_liujun_phl_repay_04_target_daily
;

-- SHOW CREATE TABLE phl_anls.tmp_liujun_phl_repay_fnl_daily
-- ;
-- TRUNCATE TABLE phl_anls.tmp_liujun_phl_repay_04_target_daily
-- ;
DROP TABLE IF EXISTS phl_anls.tmp_liujun_phl_repay_fnl_will_daily
;

CREATE TABLE IF NOT EXISTS phl_anls.tmp_liujun_phl_repay_fnl_will_daily AS
SELECT  *
FROM    phl_anls.tmp_liujun_phl_repay_03_all_daily
UNION ALL
SELECT  *
FROM    phl_anls.tmp_liujun_phl_repay_03_S1_daily
UNION ALL
SELECT  *
FROM    phl_anls.tmp_liujun_phl_repay_03_S2_daily
UNION ALL
SELECT  *
FROM    phl_anls.tmp_liujun_phl_repay_03_M1_daily
UNION ALL
SELECT  *
FROM    phl_anls.tmp_liujun_phl_repay_03_M2_daily
-- UNION ALL
-- SELECT  *
-- FROM    phl_anls.tmp_liujun_phl_repay_05_target_daily
;

-- TRUNCATE TABLE phl_anls.tmp_liujun_phl_repay_05_target_daily
-- ;
-- SELECT  due_mth
--         ,user_type
--         ,days_from_duedate
--         ,SUM(overdue_principal_boc) AS overdue_principal_boc
--         ,SUM(owing_principal_eoc) AS owing_principal_eoc
-- FROM    phl_anls.tmp_liujun_phl_repay_03_all_daily
-- GROUP BY due_mth
--          ,user_type
--          ,days_from_duedate