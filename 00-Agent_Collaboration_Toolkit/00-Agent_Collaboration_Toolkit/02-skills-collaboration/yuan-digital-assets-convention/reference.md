# 约定版参考 — 9 类与业务场景映射

> 与 `12-agent_finalize/build_convention.py` 一致；供 Agent 按需查阅。

---

## 11 类目录名（按顺序）

| 序号 | 目录名   | 用途简述 |
|------|----------|----------|
| 1    | wiki     | 知识库、概念与术语、长期可复用文档 |
| 2    | blog     | 随笔、过程记录、非正式总结 |
| 3    | products | 产品说明、交付物、产品化产出 |
| 4    | report   | 周期性报告、复盘报告 |
| 5    | prompt   | Prompt 模板、Agent 启动指令 |
| 6    | 脚本     | 独立脚本或脚本索引 |
| 7    | sql      | 独立 SQL 或 SQL 索引 |
| 8    | data     | 数据源、数据准备、ETL 中间件 |
| 9    | readme   | 根级 README 或全库 README 索引 |
| 10   | 深度思考 | 深度思考、复盘、策略与决策记录 |
| 11   | skill    | Cursor/Agent Skill 等可复用能力 |

---

## 业务场景 → 12-agent_finalize 目录

| 业务场景 | 12-agent_finalize 下目录（相对路径） |
|----------|--------------------------------------|
| 策略构建 | 03-Strategy_Development, 02-Strategy_Planning, 10-Collection_Inspection |
| 数据分析 | 04-Data_Analysis, 07-Daily_Operations |
| 指标预测 | 05-Data_Prediction |
| 团队管理 | 01-Team_Management, 06-PMO_Cockpit |
| 知识库   | 08-Knowledge_Base, 09-Personal_Growth |

---

## 关键路径

- **做项目**：`12-agent_finalize/<业务场景目录>/<子项目>/<9类之一>/`
- **约定版文档**：`数字资产_约定版/文件结构_按9类.md`、`数字资产_约定版/待确认清单.md`
- **生成约定版**：运行 `12-agent_finalize/build_convention.py`（不修改源文件）

---

**维护者**：Mr. Yuan
