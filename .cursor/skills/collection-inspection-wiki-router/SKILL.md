---
name: collection-inspection-wiki-router
description: 按问题类型把催收巡检问题路由到正确文档，再输出带范围约束的结论与行动建议。
---

# 催收巡检 Wiki 路由器

## 目标

先路由、后回答。  
避免无目标地读取大量文档。

## 知识源

主索引：

- `02automation/10-Collection_Inspection/10-Collection_Inspection/wiki/14_Knowledge_Library_Index.md`

项目 wiki：

- `02automation/10-Collection_Inspection/10-Collection_Inspection/wiki/`

跨项目权威根目录：

- `D:/09wiki/wiki/collection_inspection/`

## 路由规则

1. 先把请求分类为以下之一：
   - `definition`：指标定义、分子分母、口径一致性
   - `business`：趋势解释、风险原因、业务决策语境
   - `implementation`：脚本/SQL/报表改造、运行与排障
   - `coverage_gap`：覆盖缺口、待补项、路线图
2. 每次只取 1-3 篇最相关文档。
3. 若文档冲突，优先级为：
   - 最新 PRD/报表规范
   - 数据字典/数据模型
   - 决策日志（解释为什么）
4. 输出前显式声明答案范围：
   - 模块范围
   - 指标单位（件数/金额）
   - 时间与维度假设

## 排斥条件（必须停止猜测）

当满足任一条时，不允许“硬路由 + 直接回答”：

- 问题需要外部事实（例如线上配置、最新数据）但当前无法访问/核验
- 文档映射命中的 1-3 篇无法提供明确证据（只给观点，没有口径/公式/实现）
- 用户要求“最终结论/最终口径”，但项目内代码与文档冲突且无法判断哪个更新

此时必须输出：

1) 我不知道的部分（明确说出来）  
2) 需要的最小证据（表名/SQL 片段/报表截图/commit）  
3) 下一步验证路径（读哪份文档或改哪段代码来消除不确定性）

## 成功标准（路由完成的定义）

满足以下条件才算“路由成功”：

1. 明确问题类型（四选一）
2. 选中的文档不超过 3 篇
3. 回答中至少引用 1 条“可核验的证据”（公式/字段/脚本路径/表名）

## 文档映射

- `definition`:
  - `13_PRD_Collection_Report.md`
  - `10_Data_Dictionary.md`
  - `12_Data_Schema_Collection_Report.md`
  - `11_SQL_Templates.md`（需要校验 SQL/公式时）
- `business`:
  - `01_Business_Design.md`
  - `07_Business_Sense.md`
  - `08_Decision_Log.md`
- `implementation`:
  - `04_Technical_Arch.md`
  - `03_Operations_Manual.md`
  - `02_Report_Spec.md`
- `coverage_gap`:
  - `09_Metrics_Coverage.md`
  - `05_Roadmap.md`
  - `08_Decision_Log.md`

## 回答模板

按以下顺序输出：

1. 问题类型与选中文档
2. 直接结论
3. 证据摘要（公式/规则/路径）
4. 下一步动作（验证/改造/监控）

## 维护行为

若某问题无法清晰路由，必须：

1. 记录为路由缺口；
2. 在 `14_Knowledge_Library_Index.md` 增加映射条目；
3. 在同一会话更新本 skill 的“文档映射”。
