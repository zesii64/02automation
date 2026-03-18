# 项目规划 (Roadmap)

> **定位**: 项目进度追踪与未来规划；**完整计划**由本页总览 + 下列各文档共同构成。  
> **维护者**: Mr. Yuan

---

## 〇、完整计划总览 (Full Plan Index)

| 文档 | 内容 |
|------|------|
| [01_Business_Design.md](01_Business_Design.md) | 业务设计：监控维度（风险/回收/过程三条线）、**完整归因逻辑 checklist**、异常规则。 |
| [02_Report_Spec.md](02_Report_Spec.md) | 报表规范：日报/周报章节结构、KPI 定义、HTML 样式。 |
| [04_Technical_Arch.md](04_Technical_Arch.md) | 技术架构：数据流、取数/计算/展示层、脚本与 SQL 依赖。 |
| [06_Data_Dictionary.md](06_Data_Dictionary.md) | 数据字典：Vintage / Process / Repay 表结构与字段说明。 |
| [09_Metrics_Coverage.md](09_Metrics_Coverage.md) | 指标覆盖与待补：当前能看什么数、缺什么维度、补全计划。 |
| [03_Operations_Manual.md](03_Operations_Manual.md) | 操作手册：943 取数、本地出报、故障排查。 |
| [08_Decision_Log.md](08_Decision_Log.md) | 决策与迭代日志：各版本变更记录（v4.14～v4.25）。 |
| [07_Business_Sense.md](07_Business_Sense.md) | 业务 sense：扩展顺序、话术与结论模板、数据与报表现状。 |

*入口首页*：[00_Home.md](00_Home.md)

---

## 一、当前状态 (Current Status)

✅ **v4.25 线上/943 与数据质量** - *2026-01*
- [x] 取数时间范围 2024-12 起；vintage 支持 Y-1 对比。
- [x] 覆盖率改为日维度单日触达率平均；组过滤（Nocall/月初取消/agent_count=0）。
- [x] `--mode online`：先出报告再写 Excel，适配 943 内存约束。

✅ **v4.22～v4.24 运营效能与智能诊断**
- [x] Part 3 重构：Target Dashboard、Agent Leaderboard、Efficiency Analysis、Action Items。
- [x] 智能诊断：多月模式、持续低效、Uplift 叙事。
- [x] 归因中心 Shift-Share、运营归因 Treemap、CDN 内联离线可用。

✅ **v2.0 战略监控与文档**
- [x] 4 大维度 (资产/执行/回收/客群)、Model Bin、Process Raw；Wiki 与 Dashboard。

---

## 二、待办事项 (To-Do)

### v2.1 报表与资产
- [ ] **日报 + 周报**: 同一套归因逻辑，日报按日、周报按周聚合，结构一致。
- [ ] **核心数字资产**: 将业务设计/归因逻辑同步至 `11-Agent/Core_Digital_Assets` 作为贷后分析管理方法论。
- [ ] **贷后数据分析管理 Skill**: 已创建 `skill/Post_Loan_Data_Analysis_Management_Skill.md`，与 01_Business_Design 对齐；新增维度统一在 01_Business_Design 中新增。

### v2.2 报表增强与异常
- [ ] **due 趋势一节**: 聚合表已有 due_date；报表增加「按 due_date / due_week 的入催率与体量趋势」表或图，落实「先 due 再拆解」。
- [ ] **波动类异常**: 实现日/周环比计算（如 10% 示例阈值），在报表中标红并写入异常区；详见 01_Business_Design 与 07_Business_Sense。

### v2.3 体验与扩展
- [ ] **自动化邮件**: 本地生成 HTML 后调用 Outlook/SMTP 发送。
- [ ] **历史趋势**: 记录每日/周指标，生成 Trend Chart (需要本地轻量数据库或追加 Excel)。
- [ ] **多产品支持**: 目前仅 CashLoan，需扩展至其他产品线；复用 07_Business_Sense 中「扩展时的复用点」。
- [ ] **更深度的归因**: 结合 IVR/短信 具体触达数据进行分析。

---

## 三、长期规划 (Long-term)

- **AI 智能分析**: 引入 LLM 对 HTML 报表进行自动解读和摘要。
- **Web 平台化**: 将本地 Python 脚本升级为 Streamlit/Web 应用 (视需求而定)。

---

**Last Updated**: 2026-02-03  
**维护者**：Mr. Yuan
