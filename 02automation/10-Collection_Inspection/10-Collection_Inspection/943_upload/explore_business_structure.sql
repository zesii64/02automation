-- =============================================================================
-- 贷后数据巡检 - 业务结构探查 (Business Structure Exploration)
-- 目的：看“有哪些业务维度”（组织、资产分层），不限制 data_level，便于做分层监控和归因。
-- 语法：ODPS/MaxCompute，可在 943 SQL 编辑器中直接运行。
-- 维护者：Mr. Yuan
-- =============================================================================

-- 1. [Repay] 探查组织与分层结构（不限制 data_level）
-- 问：我们到底在管哪些组？哪些资产？
SELECT
    TO_CHAR(dt_biz, 'yyyyMM') AS month,
    group_name,
    agent_bucket,
    case_bucket,
    COUNT(DISTINCT owner_id) AS agent_count,
    SUM(start_owing_principal) AS total_amount
FROM phl_anls.tmp_maoruochen_phl_repay_natural_day_daily
WHERE dt_biz >= '2025-12-01'
  -- 不限制 data_level，如需只看经办层级可取消下一行注释
  -- AND data_level = '5.经办层级'
  AND case_bucket IN ('S0','S1','S2','M1','M2')
GROUP BY
    TO_CHAR(dt_biz, 'yyyyMM'),
    group_name,
    agent_bucket,
    case_bucket
ORDER BY month DESC, total_amount DESC;


-- 2. [Process] 探查作业组（用底表原始字段，ODPS 语法）
-- 问：哪些组是核心作业组？用底表字段聚合，避免引用不存在的列。
SELECT
    TO_CHAR(TO_DATE(dt), 'yyyymm') AS month,
    owner_bucket,
    owner_group,
    COUNT(DISTINCT dt) AS days,
    SUM(owing_case_cnt) AS total_case_cnt,
    SUM(call_times) AS total_calls
FROM phl_anls.tmp_liujun_ana_11_agent_process_daily
WHERE dt >= '2025-12-01'
  AND CAST(call_8h_flag AS string) = '1'
  AND owner_bucket IN ('M1','M2','M2+','S0','S1','S2')
  AND is_outs_owner = 0
GROUP BY
    TO_CHAR(TO_DATE(dt), 'yyyymm'),
    owner_bucket,
    owner_group
ORDER BY month DESC, total_case_cnt DESC;
--
-- 维护者：Mr. Yuan
