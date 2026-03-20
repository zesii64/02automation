-- =============================================================================
-- 贷后数据巡检 - 数据探查 (Data Profiling)
-- 用于分析底表数据量级、维度基数，以优化正式取数脚本，防止下载卡死。
-- 请在 943 平台 SQL 编辑器中依次执行各段。
-- =============================================================================

-- 1. [Vintage] 探查 tmp_liujun_phl_ana_09_eoc_sum_daily_temp
-- 目的：检查组合维度后的行数是否过大
SELECT
    COUNT(DISTINCT due_date) AS cnt_days,
    COUNT(DISTINCT model_bin) AS cnt_model,
    COUNT(DISTINCT predue_bin) AS cnt_predue,
    COUNT(DISTINCT collect_bin) AS cnt_collect,
    COUNT(*) AS total_rows_raw
FROM tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE flag_dq = 1
  AND due_date >= '2025-10-01';

-- 建议：如果组合维度多，检查是否有必要保留 province, conntact_carrier 等字段。


-- 2. [Repay] 探查 tmp_maoruochen_phl_repay_natural_day_daily
-- 目的：检查 owner_id（催收员）是否导致数据量爆炸
SELECT
    TO_CHAR(dt_biz, 'yyyyMM') AS biz_month,
    COUNT(DISTINCT day) AS cnt_days,
    COUNT(DISTINCT owner_id) AS cnt_agents, -- 重点关注：如果成百上千，乘以天数会导致结果集巨大
    COUNT(*) AS total_rows_if_no_agg,
    -- 估算按天+人聚合后的行数
    COUNT(DISTINCT day) * COUNT(DISTINCT owner_id) * COUNT(DISTINCT case_bucket) as est_result_rows
FROM phl_anls.tmp_maoruochen_phl_repay_natural_day_daily
WHERE data_level = '5.经办层级'
  AND case_bucket in ('S0','S1','S2','M1','M2')
  AND TO_CHAR(dt_biz, 'yyyyMM') >= '202501'
GROUP BY TO_CHAR(dt_biz, 'yyyyMM')
ORDER BY biz_month DESC;

-- 建议：如果 cnt_agents 很大且 est_result_rows > 10万，建议正式 SQL 中去掉 owner_id，只保留 group_name。


-- 3. [Process] 探查 tmp_liujun_ana_11_agent_process_daily
-- 目的：检查源表分区数，以及计算开销
SELECT
    TO_CHAR(TO_DATE(dt), 'yyyyMM') AS month,
    COUNT(DISTINCT dt) AS cnt_days,
    COUNT(DISTINCT owner_bucket) AS cnt_buckets,
    COUNT(*) AS raw_log_rows -- 如果这里是几亿行，大量 distinct count 计算会很慢
FROM phl_anls.tmp_liujun_ana_11_agent_process_daily
WHERE dt >= '2024-01-01'
  AND owner_bucket IN ('M1','M2','M2+','S0','S1','S2')
GROUP BY TO_CHAR(TO_DATE(dt), 'yyyyMM')
ORDER BY month DESC;

-- 建议：Process SQL 虽然结果行数少（按月聚合），但计算复杂。如果卡死，尝试缩小 dt 范围（如改为最近 3 个月）。
--
-- 维护者：Mr. Yuan
