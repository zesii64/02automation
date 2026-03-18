select due_date
         ,mob
         ,user_type
         ,period_no
         ,period_seq
         ,model_bin
         ,predue_bin
         ,collect_bin
         ,is_touch
         ,flag_principal
        ,province
        ,conntact_carrier
,sum(overdue_principal) AS overdue_principal
,sum(owing_principal) AS owing_principal
,sum(case when datediff(now(),to_date(due_date))>=31 then d31_principal end) AS d31_principal
,sum(case when datediff(now(),to_date(due_date))>=31 then owing_principal end) AS owing_principal_d31
from tmp_liujun_phl_ana_09_eoc_sum_daily_temp
where flag_dq = 1
and due_date >= '2025-12-01'
group by due_date
         ,mob
         ,user_type
         ,period_no
         ,period_seq
         ,model_bin
         ,predue_bin
         ,collect_bin
         ,is_touch
         ,flag_principal
        ,province
        ,conntact_carrier
;