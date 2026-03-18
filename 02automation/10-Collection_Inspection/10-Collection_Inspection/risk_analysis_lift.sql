--odps sql 
--********************************************************************--
--author:张昀天
--create time:2025-09-17 14:00:23
--dt                          owner             paones         desc
--2025-09-17 14:00:23	张昀天
--********************************************************************--
INSERT OVERWRITE phl_anls.tmp_zyt_same_period_risk
--=====================================去年同期======================================================
--去年同期
SELECT  'Cashloan' AS product
        ,CONCAT(TO_DATE(DATEADD(DATEADD(now(),-12,'month'),1 - DAYOFMONTH(now()),'day')),' -- ',TO_DATE(DATEADD(now(),-12,'month'))) AS due_period
        ,CASE   WHEN user_type = '新客' THEN '新客'
                ELSE '老客'
        END AS user_type2
        ,SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 1 THEN overdue_principal END
        ) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 1 THEN owing_principal END
        ) AS overdue_rate
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 2 THEN overdue_principal END
        ) AS dpd1_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 2 THEN owing_principal END
        ) AS dpd1
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 6 THEN overdue_principal END
        ) AS dpd5_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 6 THEN owing_principal END
        ) AS dpd5
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 11 THEN d11_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 11 THEN overdue_principal END
        ) AS dpd10_repay
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 31 THEN overdue_principal END
        ) AS dpd30_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) >= 31 THEN owing_principal END
        ) AS dpd30
FROM    phl_anls.tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE   due_date BETWEEN TO_DATE(DATEADD(DATEADD(now(),-12,'month'),1 - DAYOFMONTH(now()),'day')) AND TO_DATE(DATEADD(now(),-12,'month')) 
AND     flag_dq = 1
GROUP BY CONCAT(TO_DATE(DATEADD(DATEADD(now(),-12,'month'),1 - DAYOFMONTH(now()),'day')),' -- ',TO_DATE(DATEADD(now(),-12,'month')))
         ,CASE   WHEN user_type = '新客' THEN '新客'
                 ELSE '老客'
         END
         ,due_period
UNION ALL -- 去年同月剩余
SELECT  'Cashloan' AS product
        ,CONCAT(TO_CHAR(TO_DATE(DATEADD(now(),-12,'month')),'yyyy-mm'),'剩余') AS due_period
        ,CASE   WHEN user_type = '新客' THEN '新客'
                ELSE '老客'
        END AS user_type2
        ,SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 1 THEN overdue_principal END
        ) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 1 THEN owing_principal END
        ) AS overdue_rate
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 2 THEN d2_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 2 THEN overdue_principal END
        ) AS dpd1_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 2 THEN d2_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 2 THEN owing_principal END
        ) AS dpd1
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 6 THEN d6_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 6 THEN overdue_principal END
        ) AS dpd5_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 6 THEN d6_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 6 THEN owing_principal END
        ) AS dpd5
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 11 THEN d11_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 11 THEN overdue_principal END
        ) AS dpd10_repay
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 31 THEN d31_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 31 THEN overdue_principal END
        ) AS dpd30_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 31 THEN d31_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-12,'month'),TO_DATE(due_date)) < 31 THEN owing_principal END
        ) AS dpd30
FROM    phl_anls.tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE   TO_CHAR(due_date,'yyyy-mm') = TO_CHAR(TO_DATE(DATEADD(now(),-12,'month')),'yyyy-mm')
AND     flag_dq = 1
GROUP BY CONCAT(TO_CHAR(TO_DATE(DATEADD(now(),-12,'month')),'yyyy-mm'),'剩余')
         ,CASE   WHEN user_type = '新客' THEN '新客'
                 ELSE '老客'
         END
         ,due_period
UNION ALL --去年同月整月
SELECT  'Cashloan' AS product
        ,CONCAT(TO_CHAR(TO_DATE(DATEADD(now(),-12,'month')),'yyyy-mm'),'整月') AS due_period
        ,CASE   WHEN user_type = '新客' THEN '新客'
                ELSE '老客'
        END AS user_type2
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 1 THEN overdue_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 1 THEN owing_principal END) AS overdue_rate
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN overdue_principal END) AS dpd1_repay
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN owing_principal END) AS dpd1
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN overdue_principal END) AS dpd5_repay
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN owing_principal END) AS dpd5
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 11 THEN d11_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 11 THEN overdue_principal END) AS dpd10_repay
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN overdue_principal END) AS dpd30_repay
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN owing_principal END) AS dpd30
FROM    phl_anls.tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE   TO_CHAR(due_date,'yyyy-mm') = TO_CHAR(TO_DATE(DATEADD(now(),-12,'month')),'yyyy-mm')
AND     flag_dq = 1
GROUP BY CONCAT(TO_CHAR(TO_DATE(DATEADD(now(),-12,'month')),'yyyy-mm'),'整月')
         ,CASE   WHEN user_type = '新客' THEN '新客'
                 ELSE '老客'
         END
         ,due_period
UNION ALL
--=====================================M-2======================================================
-- M-2同期
SELECT  'Cashloan' AS product
        ,CONCAT(TO_DATE(DATEADD(DATEADD(now(),-2,'month'),1 - DAYOFMONTH(now()),'day')),' -- ',TO_DATE(DATEADD(now(),-2,'month'))) AS due_period
        ,CASE   WHEN user_type = '新客' THEN '新客'
                ELSE '老客'
        END AS user_type2
        ,SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 1 THEN overdue_principal END
        ) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 1 THEN owing_principal END
        ) AS overdue_rate
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 2 THEN overdue_principal END
        ) AS dpd1_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 2 THEN owing_principal END
        ) AS dpd1
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 6 THEN overdue_principal END
        ) AS dpd5_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 6 THEN owing_principal END
        ) AS dpd5
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 11 THEN d11_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 11 THEN overdue_principal END
        ) AS dpd10_repay
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 31 THEN overdue_principal END
        ) AS dpd30_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) >= 31 THEN owing_principal END
        ) AS dpd30
FROM    phl_anls.tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE   due_date BETWEEN TO_DATE(DATEADD(DATEADD(now(),-2,'month'),1 - DAYOFMONTH(now()),'day')) AND TO_DATE(DATEADD(now(),-2,'month')) --上上月同期
AND     flag_dq = 1
GROUP BY CONCAT(TO_DATE(DATEADD(DATEADD(now(),-2,'month'),1 - DAYOFMONTH(now()),'day')),' -- ',TO_DATE(DATEADD(now(),-2,'month')))
         ,CASE   WHEN user_type = '新客' THEN '新客'
                 ELSE '老客'
         END
         ,due_period
UNION ALL -- M-2剩余
SELECT  'Cashloan' AS product
        ,CONCAT(TO_CHAR(TO_DATE(DATEADD(now(),-2,'month')),'yyyy-mm'),'剩余') AS due_period
        ,CASE   WHEN user_type = '新客' THEN '新客'
                ELSE '老客'
        END AS user_type2
        ,SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 1 THEN overdue_principal END
        ) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 1 THEN owing_principal END
        ) AS overdue_rate
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 2 THEN d2_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 2 THEN overdue_principal END
        ) AS dpd1_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 2 THEN d2_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 2 THEN owing_principal END
        ) AS dpd1
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 6 THEN d6_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 6 THEN overdue_principal END
        ) AS dpd5_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 6 THEN d6_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 6 THEN owing_principal END
        ) AS dpd5
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 11 THEN d11_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 11 THEN overdue_principal END
        ) AS dpd10_repay
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 31 THEN d31_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 31 THEN overdue_principal END
        ) AS dpd30_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 31 THEN d31_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-2,'month'),TO_DATE(due_date)) < 31 THEN owing_principal END
        ) AS dpd30
FROM    phl_anls.tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE   TO_CHAR(due_date,'yyyy-mm') = TO_CHAR(TO_DATE(DATEADD(now(),-2,'month')),'yyyy-mm') --M-2月
AND     flag_dq = 1
GROUP BY CONCAT(TO_CHAR(TO_DATE(DATEADD(now(),-2,'month')),'yyyy-mm'),'剩余')
         ,CASE   WHEN user_type = '新客' THEN '新客'
                 ELSE '老客'
         END
         ,due_period
UNION ALL --M-2整月
SELECT  'Cashloan' AS product
        ,CONCAT(TO_CHAR(TO_DATE(DATEADD(now(),-2,'month')),'yyyy-mm'),'整月') AS due_period
        ,CASE   WHEN user_type = '新客' THEN '新客'
                ELSE '老客'
        END AS user_type2
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 1 THEN overdue_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 1 THEN owing_principal END) AS overdue_rate
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN overdue_principal END) AS dpd1_repay
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN owing_principal END) AS dpd1
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN overdue_principal END) AS dpd5_repay
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN owing_principal END) AS dpd5
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 11 THEN d11_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 11 THEN overdue_principal END) AS dpd10_repay
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN overdue_principal END) AS dpd30_repay
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN owing_principal END) AS dpd30
FROM    phl_anls.tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE   TO_CHAR(due_date,'yyyy-mm') = TO_CHAR(TO_DATE(DATEADD(now(),-2,'month')),'yyyy-mm')
AND     flag_dq = 1
GROUP BY CONCAT(TO_CHAR(TO_DATE(DATEADD(now(),-2,'month')),'yyyy-mm'),'整月')
         ,CASE   WHEN user_type = '新客' THEN '新客'
                 ELSE '老客'
         END
         ,due_period
--========================================M-1=========================================================
UNION ALL --M-1同期
SELECT  'Cashloan' AS product
        ,CONCAT(TO_DATE(DATEADD(DATEADD(now(),-1,'month'),1 - DAYOFMONTH(now()),'day')),' -- ',TO_DATE(DATEADD(now(),-1,'month'))) AS due_period
        ,CASE   WHEN user_type = '新客' THEN '新客'
                ELSE '老客'
        END AS user_type2
        ,SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 1 THEN overdue_principal END
        ) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 1 THEN owing_principal END
        ) AS overdue_rate
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 2 THEN overdue_principal END
        ) AS dpd1_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 2 THEN owing_principal END
        ) AS dpd1
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 6 THEN overdue_principal END
        ) AS dpd5_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 6 THEN owing_principal END
        ) AS dpd5
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 11 THEN d11_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 11 THEN overdue_principal END
        ) AS dpd10_repay
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 31 THEN overdue_principal END
        ) AS dpd30_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) >= 31 THEN owing_principal END
        ) AS dpd30
FROM    phl_anls.tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE   due_date BETWEEN TO_DATE(DATEADD(DATEADD(now(),-1,'month'),1 - DAYOFMONTH(now()),'day')) AND TO_DATE(DATEADD(now(),-1,'month')) --上月同期
AND     flag_dq = 1
GROUP BY CONCAT(TO_DATE(DATEADD(DATEADD(now(),-1,'month'),1 - DAYOFMONTH(now()),'day')),' -- ',TO_DATE(DATEADD(now(),-1,'month')))
         ,CASE   WHEN user_type = '新客' THEN '新客'
                 ELSE '老客'
         END
         ,due_period
UNION ALL -- M-1剩余
SELECT  'Cashloan' AS product
        ,CONCAT(TO_CHAR(TO_DATE(DATEADD(now(),-1,'month')),'yyyy-mm'),'剩余') AS due_period
        ,CASE   WHEN user_type = '新客' THEN '新客'
                ELSE '老客'
        END AS user_type2
        ,SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 1 THEN overdue_principal END
        ) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 1 THEN owing_principal END
        ) AS overdue_rate
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 2 THEN d2_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 2 THEN overdue_principal END
        ) AS dpd1_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 2 THEN d2_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 2 THEN owing_principal END
        ) AS dpd1
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 6 and DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 6 and DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN overdue_principal END
        ) AS dpd5_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 6 and DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 6 and DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN owing_principal END
        ) AS dpd5
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 11 and DATEDIFF(now(),TO_DATE(due_date)) >= 11 THEN d11_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 11 and DATEDIFF(now(),TO_DATE(due_date)) >= 11 THEN overdue_principal END
        ) AS dpd10_repay
        ,1 - SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 31 and DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 31 and DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN overdue_principal END
        ) AS dpd30_repay
        ,SUM(CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 31 and DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(
            CASE    WHEN DATEDIFF(DATEADD(now(),-1,'month'),TO_DATE(due_date)) < 31 and DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN owing_principal END
        ) AS dpd30
FROM    phl_anls.tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE   TO_CHAR(due_date,'yyyy-mm') = TO_CHAR(TO_DATE(DATEADD(now(),-1,'month')),'yyyy-mm') --M-1月
AND     flag_dq = 1
GROUP BY CONCAT(TO_CHAR(TO_DATE(DATEADD(now(),-1,'month')),'yyyy-mm'),'剩余')
         ,CASE   WHEN user_type = '新客' THEN '新客'
                 ELSE '老客'
         END
         ,due_period
UNION ALL -- M-1整月
SELECT  'Cashloan' AS product
        ,CONCAT(TO_CHAR(TO_DATE(DATEADD(now(),-1,'month')),'yyyy-mm'),'整月') AS due_period
        ,CASE   WHEN user_type = '新客' THEN '新客'
                ELSE '老客'
        END AS user_type2
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 1 THEN overdue_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 1 THEN owing_principal END) AS overdue_rate
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN overdue_principal END) AS dpd1_repay
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN owing_principal END) AS dpd1
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN overdue_principal END) AS dpd5_repay
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN owing_principal END) AS dpd5
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 11 THEN d11_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 11 THEN overdue_principal END) AS dpd10_repay
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN overdue_principal END) AS dpd30_repay
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN owing_principal END) AS dpd30
FROM    phl_anls.tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE   TO_CHAR(due_date,'yyyy-mm') = TO_CHAR(TO_DATE(DATEADD(now(),-1,'month')),'yyyy-mm')
AND     flag_dq = 1
GROUP BY CONCAT(TO_CHAR(TO_DATE(DATEADD(now(),-1,'month')),'yyyy-mm'),'整月')
         ,CASE   WHEN user_type = '新客' THEN '新客'
                 ELSE '老客'
         END
         ,due_period
--=========================================本月========================================
UNION ALL  --本月
SELECT  'Cashloan' AS product
        ,CONCAT(TO_DATE(DATEADD(now(),1 - DAYOFMONTH(now()),'day')),' -- ',TO_DATE(now())) AS due_period
        ,CASE   WHEN user_type = '新客' THEN '新客'
                ELSE '老客'
        END AS user_type2
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 1 THEN overdue_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 1 THEN owing_principal END) AS overdue_rate
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN overdue_principal END) AS dpd1_repay
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN d2_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 2 THEN owing_principal END) AS dpd1
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN overdue_principal END) AS dpd5_repay
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN d6_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 6 THEN owing_principal END) AS dpd5
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 11 THEN d11_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 11 THEN overdue_principal END) AS dpd10_repay
        ,1 - SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN overdue_principal END) AS dpd30_repay
        ,SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN d31_principal END) / SUM(CASE    WHEN DATEDIFF(now(),TO_DATE(due_date)) >= 31 THEN owing_principal END) AS dpd30
FROM    phl_anls.tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE   due_date BETWEEN TO_DATE(DATEADD(now(),1 - DAYOFMONTH(now()),'day')) AND TO_DATE(now()) --本月
AND     flag_dq = 1
GROUP BY CONCAT(TO_DATE(DATEADD(now(),1 - DAYOFMONTH(now()),'day')),' -- ',TO_DATE(now()))
         ,CASE   WHEN user_type = '新客' THEN '新客'
                 ELSE '老客'
         END
         ,due_period

;
