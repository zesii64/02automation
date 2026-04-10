---

## name: collection-staffing-analysis
description: Summarizes domain knowledge about relationships between collection staffing, workload, diligence (calls, coverage, contact time), and repayment performance using Repay_* and Process_* style metrics. Use as background knowledge when analyzing collection manpower planning, staffing intensity, coverage, or their impact on repayment outcomes.

# 催收人力 / 负荷 / 勤奋度 关系（精简版）

本 Skill 提供一套 **稳定的认知框架**，说明在催收业务中：人力规模（staffing）、任务负荷（workload）、勤奋程度（diligence）与回款表现之间的典型关系。  
具体公式、字段口径与详细示例可参考项目内的 wiki 文档。

---

## 1. 概念与字段映射（只给最小集合）

在任意表结构下，只要能映射出这些含义，就可以使用本 Skill：

- **人力规模（Staffing）**
  - 催员唯一标识：`owner_name`（或等价字段）
  - 人力规模：`headcount = 去重催员数(owner_name distinct count)`
- **任务负荷（Workload）**
  - 案件量：`case_load`（按催员/组/时间聚合）
  - 案均拨打次数：`cover_times`（每案平均拨打次数）
  - 覆盖率：`cover_rate`（至少被成功触达一次的案件占比）
- **勤奋程度（Diligence）**
  - 拨打次数：`call_times`（可含点呼、一键外呼等）
  - 接通时长：`call_billmin`（总接通分钟数）
  - 单通接通时长：`single_call_duration = 接通时长 ÷ 接通次数`（仅接通）
  - 同时也把 `cover_times`、`cover_rate` 视为勤奋的一部分  
  - `penetration_rate` 暂不参与分析，可忽略。
- **回款结果（Repayment Performance）**
  - 本金基数：`owing_principal`
  - 实际回款本金：`repay_principal`
  - 本金回款率：`repay_rate = repay_principal ÷ owing_principal`
  - 目标回款本金：`target_repay_principal`
  - 目标达成率：`achieve_rate = repay_principal ÷ target_repay_principal`

---

## 2. 关键派生指标（只保留最核心几项）

在任意分析单元（如：某个阶段 + 某个组 + 某段时间）上，优先关注：

- **人均负荷**
  - `avg_case_load_per_agent = sum(case_load) ÷ headcount`
- **勤奋程度（综合）**
  - 人均拨打：`avg_calls_per_agent = sum(call_times) ÷ headcount`
  - 案均拨打：`avg_cover_times`
  - 覆盖率：`avg_cover_rate`
  - 人均接通时长：`avg_connect_minutes_per_agent = sum(call_billmin) ÷ headcount`
  - 每案接通时长：`avg_connect_minutes_per_case = sum(call_billmin) ÷ sum(case_load)`
  - 单通接通时长：`avg_single_call_duration`（由 `single_call_duration` 聚合）
- **产出与效率**
  - 人均回款：`repay_principal_per_agent = sum(repay_principal) ÷ headcount`
  - 回款率：`repay_rate`
  - 单位接通时长回款：`repay_per_connect_minute = sum(repay_principal) ÷ sum(call_billmin)`
  - 单位拨打回款：`repay_per_call = sum(repay_principal) ÷ sum(call_times)`

---

## 3. 解释性规则（用来“看懂”数据）

在做任何具体分析时，可将下面这些规则作为默认解读框架：

- **人力 vs 负荷**
  - 在案件量与结构大致稳定下：
    - 人力规模 `headcount` 越大，人均案件量 `avg_case_load_per_agent` 越低，单人压力下降；
    - 适度降低人均案件量有利于提升沟通质量，但人力并非越多越好，过多会稀释人均产出。
- **勤奋各指标对回款的综合影响**
  - 拨打次数 `call_times`：
    - 覆盖率低时，增加拨打有助于提升 `cover_rate`，进而提高 `repay_rate`；
    - 覆盖率已高且案均拨打多时，继续加拨的边际收益会减弱。
  - 案均覆盖 & 覆盖率（`cover_times`、`cover_rate`）：
    - 从“有无触达”视角看，这两项对回款率提升往往非常关键；
    - 在高覆盖前提下，进一步提高案均拨打是否有效，取决于话术与策略。
  - 接通时长与单通质量（`call_billmin`、`single_call_duration`）：
    - 过短通常意味着沟通不足，难以支撑稳定回款；
    - 过长但回款不佳，则提示沟通效率或策略存在问题。
  - **综合视角**：
    - 勤奋度应同时看：拨打次数 + 案均覆盖 + 覆盖率 + 有效接通时长，而不是单看其中一个数。
- **效率前沿与压缩空间（概念性）**
  - 在相似案件结构与逾期阶段下：
    - 那些在人均回款、人均接通时长回款等指标上表现更好的单元，构成“效率前沿”；
    - 若存在投入不低但明显低于前沿的单元，说明从历史表现看可能有人力或资源冗余；
    - 任何“可压缩空间”的判断，都应在具体分析中结合案件结构、策略、目标等进一步验证。

---

## 4. 使用方式

- 当你在分析中涉及“人力配置、任务负荷、勤奋程度与回款关系”时：
  - 使用本 Skill 统一这些概念与指标解释；
  - 将具体公式、字段口径和例子放在项目 wiki 中按需引用。
- 本 Skill 不提供具体 SQL、建模或结论模板，只提供 **稳定的概念框架和解释规则**，保证跨项目、跨时间的分析口径一致。

---

## 5. 相关背景文档

本 Skill 只保留最核心的概念与解释规则，以减少上下文占用。  
当需要更详细的字段口径说明、更多业务背景或案例时，可参考项目中的 wiki 文档，例如：

- `.cursor\wiki\wiki_hc_repay_process.md`：详细说明人力、负荷、勤奋与回款之间的关系，包含更多指标解释和业务语境，下次完成相关项目时，询问我是否要把其添加到案例中。

