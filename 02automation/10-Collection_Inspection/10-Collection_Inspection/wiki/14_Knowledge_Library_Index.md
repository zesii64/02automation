# 知识库索引（Collection Inspection）

> 目的：把项目 wiki 组织成可复用知识库，提升检索效率并保证口径一致。

---

## A. 指标定义与口径标准（优先级 P0）

用于指标定义、分子分母校验、跨报表一致性核对。

- `13_PRD_Collection_Report.md`
  - 产品级需求与报表目标。
- `10_Data_Dictionary.md`
  - 字段定义与表级语义。
- `12_Data_Schema_Collection_Report.md`
  - 数据模型结构与口径承载层。
- `11_SQL_Templates.md`
  - 指标生成 SQL 模板。
- `09_Metrics_Coverage.md`
  - 当前覆盖与缺口路线图。

典型触发问题：

- “这个 KPI 的精确定义是什么？”
- “为什么两个报表数不一致？”
- “这个指标分母应该用什么？”

---

## B. 业务解释与决策语境（优先级 P1）

用于趋势解释、策略判断与决策追溯。

- `01_Business_Design.md`
- `07_Business_Sense.md`
- `08_Decision_Log.md`
- `05_Roadmap.md`

典型触发问题：

- “为什么采用这套监控框架？”
- “当前趋势的业务逻辑是什么？”
- “哪些已决策、哪些还待定？”

---

## C. 技术实现与操作手册（优先级 P1）

用于脚本实现细节、运行流程与排障。

- `04_Technical_Arch.md`
- `03_Operations_Manual.md`
- `02_Report_Spec.md`

典型触发问题：

- “这个模块在 pipeline 里怎么计算？”
- “该改哪个脚本/SQL？”
- “本地如何跑通并验证？”

---

## D. Agent 检索策略

推荐顺序：

1. 先判断请求类型：
   - 口径定义
   - 业务解释
   - 技术实现
2. 在本索引定位对应分区。
3. 只读取 1-3 篇最相关 wiki 文档。
4. 输出必须包含：
   - 精确定义/公式
   - 适用范围与维度
   - 验证步骤或改造路径

禁止：

- 未声明范围就混用“定义文档”和“解释文档”。
- 未核对架构/操作文档就给改造建议。

---

## E. 建议绑定的全局 Skill

若用于跨项目复用，优先绑定：

1. `postloan-kpi-definitions`（口径定义与一致性校验）
2. `collection-staffing-analysis`（人力-负荷-回款关系分析）
3. `collection-inspection-wiki-router`（按问题类型路由文档）
4. `knowledge-library-maintainer`（跨项目维护与同步治理）

---

## F. 维护规则

- 出现以下任一变更时，必须更新本索引：
  - 新增/修改 KPI 口径
  - 表结构或字段语义变化
  - 监控范围变化
  - 关键决策改变了解释逻辑

- 文件命名按序号递增维护：
  - 当前文件：`14_Knowledge_Library_Index.md`

---

## G. 跨项目存放建议

建议在 D 盘设置统一权威目录：

- `D:/09wiki/wiki/collection_inspection/`

执行规则：

- 项目 wiki：承载项目上下文与执行细节
- `D:/09wiki`：承载跨项目复用的权威知识

当口径或映射变化时，至少同步更新：

1. 项目 wiki 文档
2. `D:/09wiki` 下对应权威文档
3. 相关路由/定义 skill
