-- =============================================================================
-- 贷后数据巡检 - 全表结构探查 (Full Table Structure Exploration)
-- 目的：全面看齐每张底表的字段结构与关键维度取值，便于对齐维度图与监控口径。
-- 用法：在 943 平台 SQL 编辑器中分段执行；执行前可先运行 DESC 表名 查看元数据。
-- 维护者：Mr. Yuan
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 表一：09 表（Vintage 风险）tmp_liujun_phl_ana_09_eoc_sum_daily_temp
-- 说明：核心风险表，可关联多维度。建议在 943 控制台先执行：
--   DESC tmp_liujun_phl_ana_09_eoc_sum_daily_temp;
-- 查看完整字段名、类型、注释。
-- -----------------------------------------------------------------------------

-- 1.1 维度取值抽样（09 表）- 看有哪些业务分类（去重样例）
SELECT DISTINCT predue_bin, collect_bin, user_type, model_bin
FROM tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE flag_dq = 1 AND due_date >= '2025-10-01'
LIMIT 100;

-- 1.1b 地区、运营商样例
SELECT DISTINCT province, conntact_carrier
FROM tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE flag_dq = 1 AND due_date >= '2025-10-01'
LIMIT 50;

-- 1.2 各维度基数（09 表）
SELECT
    COUNT(DISTINCT due_date)   AS cnt_due_date,
    COUNT(DISTINCT mob)       AS cnt_mob,
    COUNT(DISTINCT user_type) AS cnt_user_type,
    COUNT(DISTINCT model_bin) AS cnt_model_bin,
    COUNT(DISTINCT predue_bin) AS cnt_predue_bin,
    COUNT(DISTINCT collect_bin) AS cnt_collect_bin,
    COUNT(DISTINCT province)  AS cnt_province,
    COUNT(DISTINCT conntact_carrier) AS cnt_conntact_carrier
FROM tmp_liujun_phl_ana_09_eoc_sum_daily_temp
WHERE flag_dq = 1 AND due_date >= '2025-10-01';


-- -----------------------------------------------------------------------------
-- 表二：回收表 phl_anls.tmp_maoruochen_phl_repay_natural_day_daily
-- 说明：建议先执行 DESC phl_anls.tmp_maoruochen_phl_repay_natural_day_daily; 看全表结构。
-- -----------------------------------------------------------------------------

-- 2.1 维度取值抽样（回收表）- 看有哪些 group、bucket、data_level
SELECT DISTINCT data_level, case_bucket, agent_bucket, group_name
FROM phl_anls.tmp_maoruochen_phl_repay_natural_day_daily
WHERE TO_CHAR(dt_biz,'yyyyMM') >= '202501'
  AND case_bucket IN ('S0','S1','S2','M1','M2')
LIMIT 50;

-- 2.2 data_level 全量枚举（不限制 data_level 时有哪些层级）
SELECT data_level, COUNT(*) AS cnt
FROM phl_anls.tmp_maoruochen_phl_repay_natural_day_daily
WHERE TO_CHAR(dt_biz,'yyyyMM') >= '202501'
  AND case_bucket IN ('S0','S1','S2','M1','M2')
GROUP BY data_level
ORDER BY cnt DESC;


-- -----------------------------------------------------------------------------
-- 表三：过程表 phl_anls.tmp_liujun_ana_11_agent_process_daily
-- 说明：建议先执行 DESC phl_anls.tmp_liujun_ana_11_agent_process_daily; 看全表结构。
-- -----------------------------------------------------------------------------

-- 3.1 维度取值抽样（过程表）- 看有哪些 owner_bucket、owner_group
SELECT DISTINCT owner_bucket, owner_group, owing_amount_alloc_bin
FROM phl_anls.tmp_liujun_ana_11_agent_process_daily
WHERE dt >= '2025-12-01'
  AND CAST(call_8h_flag AS string) = '1'
  AND owner_bucket IN ('M1','M2','M2+','S0','S1','S2')
  AND is_outs_owner = 0
LIMIT 50;

-- 3.2 过程表关键字段基数
SELECT
    COUNT(DISTINCT dt) AS cnt_dt,
    COUNT(DISTINCT owner_bucket) AS cnt_owner_bucket,
    COUNT(DISTINCT owner_group) AS cnt_owner_group,
    COUNT(DISTINCT owing_amount_alloc_bin) AS cnt_owing_amount_alloc_bin
FROM phl_anls.tmp_liujun_ana_11_agent_process_daily
WHERE dt >= '2025-12-01'
  AND CAST(call_8h_flag AS string) = '1'
  AND owner_bucket IN ('M1','M2','M2+','S0','S1','S2')
  AND is_outs_owner = 0;


-- =============================================================================
-- 以上为三张底表的结构与维度探查；运行结果可整理为《数据结构与内容》供维度图映射表更新。
-- 维护者：Mr. Yuan
-- =============================================================================
