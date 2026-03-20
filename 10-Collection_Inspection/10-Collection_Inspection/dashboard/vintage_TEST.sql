set
  odps.idata.system.id = quickbi_query;
set
  odps.sql.submit.mode = script;
set
  odps.task.sql.realtime = all;
set
  odps.sql.type.system.odps2 = true;
-- SQL From QuickBI, traceId: 095baf33-48ab-4066-ac62-1311d28ff64d
SELECT
  TO_CHAR(A78_T_1_.`due_date`, 'yyyyMMdd') AS T_AAD_2_,
  sum(A78_T_1_.`overdue_principal`) / sum(A78_T_1_.`owing_principal`) AS T_AC6_3_,
  sum(A78_T_1_.`overdue_cnt`) / sum(A78_T_1_.`owing_cnt`) AS T_A4D_4_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 2 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 2 then A78_T_1_.`d2_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 2 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_A7D_5_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 3 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 3 then A78_T_1_.`d3_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 3 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_A7A_6_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 4 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 4 then A78_T_1_.`d4_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 4 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_A3A_7_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 5 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 5 then A78_T_1_.`d5_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 5 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_AC1_8_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 6 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 6 then A78_T_1_.`d6_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 6 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_A51_9_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 7 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 7 then A78_T_1_.`d7_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 7 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_A40_10_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 8 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 8 then A78_T_1_.`d8_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 8 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_AAB_11_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 9 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 9 then A78_T_1_.`d9_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 9 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_AA3_12_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 10 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 10 then A78_T_1_.`d10_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 10 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_A66_13_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 11 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 11 then A78_T_1_.`d11_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 11 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_A40_14_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 12 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 12 then A78_T_1_.`d12_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 12 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_A43_15_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 13 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 13 then A78_T_1_.`d13_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 13 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_A7A_16_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 14 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 14 then A78_T_1_.`d14_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 14 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_AF1_17_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 15 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 15 then A78_T_1_.`d15_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 15 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_AC1_18_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 16 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 16 then A78_T_1_.`d16_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 16 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_A2C_19_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 17 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 17 then A78_T_1_.`d17_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 17 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_A31_20_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 18 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 18 then A78_T_1_.`d18_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 18 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_A20_21_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 19 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 19 then A78_T_1_.`d19_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 19 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_ABC_22_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 20 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 20 then A78_T_1_.`d20_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 20 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_A39_23_,
  case
    when SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 21 THEN A78_T_1_.`overdue_principal`
      END
    ) = 0 then NULL
    else 1 - SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 21 then A78_T_1_.`d21_principal`
      END
    ) / SUM(
      case
        when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 21 THEN A78_T_1_.`overdue_principal`
      END
    )
  end AS T_AE3_24_,
  1 - SUM(
    case
      when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 31 then A78_T_1_.`d31_principal`
    END
  ) / SUM(
    case
      when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 31 THEN A78_T_1_.`overdue_principal`
    END
  ) AS T_AF8_25_,
  SUM(A78_T_1_.`overdue_cnt`) AS T_AFD_26_
FROM
  (
    select
      *
    from
      phl_anls.tmp_liujun_phl_ana_09_eoc_sum_daily_temp
  ) A78_T_1_
WHERE
  A78_T_1_.`flag_dq` = 1
  AND A78_T_1_.`user_type` IN (
    '新转化老客',
    '存量老客'
  )
  AND TO_CHAR(A78_T_1_.`due_date`, 'yyyyMM') >= '202511'
  AND TO_CHAR(A78_T_1_.`due_date`, 'yyyyMM') <= '202602'
GROUP BY
  TO_CHAR(A78_T_1_.`due_date`, 'yyyyMMdd')
ORDER BY
  T_AAD_2_ DESC
LIMIT
  10000

set
  odps.idata.system.id = quickbi_query;
set
  odps.sql.submit.mode = script;
set
  odps.task.sql.realtime = all;
set
  odps.sql.type.system.odps2 = true;
-- SQL From QuickBI, traceId: 095baf33-48ab-4066-ac62-1311d28ff64d
SELECT
  COUNT(1) AS query_count
FROM
  (
    SELECT
      TO_CHAR(A78_T_1_.`due_date`, 'yyyyMMdd') AS T_AAD_2_,
      sum(A78_T_1_.`overdue_principal`) / sum(A78_T_1_.`owing_principal`) AS T_AC6_3_,
      sum(A78_T_1_.`overdue_cnt`) / sum(A78_T_1_.`owing_cnt`) AS T_A4D_4_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 2 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 2 then A78_T_1_.`d2_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 2 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_A7D_5_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 3 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 3 then A78_T_1_.`d3_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 3 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_A7A_6_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 4 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 4 then A78_T_1_.`d4_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 4 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_A3A_7_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 5 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 5 then A78_T_1_.`d5_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 5 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_AC1_8_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 6 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 6 then A78_T_1_.`d6_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 6 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_A51_9_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 7 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 7 then A78_T_1_.`d7_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 7 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_A40_10_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 8 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 8 then A78_T_1_.`d8_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 8 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_AAB_11_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 9 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 9 then A78_T_1_.`d9_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 9 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_AA3_12_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 10 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 10 then A78_T_1_.`d10_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 10 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_A66_13_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 11 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 11 then A78_T_1_.`d11_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 11 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_A40_14_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 12 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 12 then A78_T_1_.`d12_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 12 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_A43_15_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 13 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 13 then A78_T_1_.`d13_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 13 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_A7A_16_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 14 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 14 then A78_T_1_.`d14_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 14 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_AF1_17_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 15 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 15 then A78_T_1_.`d15_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 15 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_AC1_18_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 16 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 16 then A78_T_1_.`d16_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 16 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_A2C_19_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 17 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 17 then A78_T_1_.`d17_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 17 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_A31_20_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 18 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 18 then A78_T_1_.`d18_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 18 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_A20_21_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 19 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 19 then A78_T_1_.`d19_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 19 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_ABC_22_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 20 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 20 then A78_T_1_.`d20_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 20 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_A39_23_,
      case
        when SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 21 THEN A78_T_1_.`overdue_principal`
          END
        ) = 0 then NULL
        else 1 - SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 21 then A78_T_1_.`d21_principal`
          END
        ) / SUM(
          case
            when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 21 THEN A78_T_1_.`overdue_principal`
          END
        )
      end AS T_AE3_24_,
      1 - SUM(
        case
          when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 31 then A78_T_1_.`d31_principal`
        END
      ) / SUM(
        case
          when datediff(to_date(now()), to_date(A78_T_1_.`due_date`)) >= 31 THEN A78_T_1_.`overdue_principal`
        END
      ) AS T_AF8_25_,
      SUM(A78_T_1_.`overdue_cnt`) AS T_AFD_26_
    FROM
      (
        select
          *
        from
          phl_anls.tmp_liujun_phl_ana_09_eoc_sum_daily_temp
      ) A78_T_1_
    WHERE
      A78_T_1_.`flag_dq` = 1
      AND A78_T_1_.`user_type` IN (
        '新转化老客',
        '存量老客'
      )
      AND TO_CHAR(A78_T_1_.`due_date`, 'yyyyMM') >= '202511'
      AND TO_CHAR(A78_T_1_.`due_date`, 'yyyyMM') <= '202602'
    GROUP BY
      TO_CHAR(A78_T_1_.`due_date`, 'yyyyMMdd')
  ) TMP_QUERY