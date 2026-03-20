-- =============================================================================
-- 基于 phl_data.dwb_asset_overdue_debt_dtl_dly 按到期月计算两种 DPD30 逾期率
-- 观察日 = 每个 debt 取 dt >= due_date+31 的最小 dt 作为该笔观察日快照（保证有数据）
-- 1) 结清口径 DPD30 逾期率 = SUM(CASE WHEN overdue_principal_31>0 THEN 0 ELSE overdue_principal_31 END) / 对应分母
-- 2) 实际还钱 DPD30 逾期率 = overdue_principal_31 / principal
-- 依赖：phl_data.dwb_asset_overdue_debt_dtl_dly, phl_anls.tmp_liujun_phl_ana_01_eoc_debt_daily
-- =============================================================================
WITH debt_due AS (
    SELECT
        a.debt_id,
        TO_DATE(a.due_date) AS due_date,
        SUBSTR(TRANSLATE(CAST(TO_DATE(a.due_date) AS VARCHAR(10)), '-', ''), 1, 6) AS due_month
    FROM phl_anls.tmp_liujun_phl_ana_01_eoc_debt_daily a
    WHERE a.is_first_col = 1
      AND TO_DATE(a.due_date) >= '2022-03-01'
      AND a.product_name IN ('installment loan 001', 'pay day loan 001', 'Lazada PDL', 'Lazada Ins', 'ppl-free', 'ppl-ins')
),
dwb_snapshot AS (
    SELECT
        b.debt_id,
        b.dt,
        b.overdue_principal_31,
        b.principal
    FROM phl_data.dwb_asset_overdue_debt_dtl_dly b
    WHERE b.dt >= '2022-01-01'
),
-- 每个 debt 取「dt >= due_date+31」的第一天快照（最小 dt）
dwb_obs_dt AS (
    SELECT
        d.debt_id,
        d.due_month,
        MIN(w.dt) AS obs_dt
    FROM debt_due d
    INNER JOIN dwb_snapshot w
        ON d.debt_id = w.debt_id
        AND w.dt >= TO_DATE(DATE_ADD(TO_DATE(d.due_date), 31))
    GROUP BY d.debt_id, d.due_month
),
obs AS (
    SELECT
        t.debt_id,
        t.due_month,
        w.overdue_principal_31,
        w.principal
    FROM dwb_obs_dt t
    INNER JOIN dwb_snapshot w ON t.debt_id = w.debt_id AND w.dt = t.obs_dt
)
SELECT
    due_month,
    SUM(CASE WHEN overdue_principal_31 > 0 THEN 0 ELSE overdue_principal_31 END) * 1.0
        / NULLIF(SUM(CASE WHEN overdue_principal_31 > 0 THEN 0 ELSE principal END), 0) AS dpd30_rate_settled,
    SUM(overdue_principal_31) * 1.0 / NULLIF(SUM(principal), 0) AS dpd30_rate_actual
FROM obs
GROUP BY due_month
ORDER BY due_month DESC
;
