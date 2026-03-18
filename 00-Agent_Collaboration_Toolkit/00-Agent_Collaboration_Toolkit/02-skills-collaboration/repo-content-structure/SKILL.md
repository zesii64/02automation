---
name: repo-content-structure
description: 仓库入口与内容分类。触发词：jerygithub、内容分类、8 类目录、wiki、blog、products、prompt、脚本、sql、readme、深度思考。说明 WHAT（jerygithub.txt 入口、8 类目录、Skill 汇总、落款）与 WHEN（在本仓库或提到上述词时使用）。
---

# repo-content-structure

本 Skill 在用户于本仓库下提问，或提到「jerygithub」「内容分类」「8 类目录」「wiki、blog、products、prompt、脚本、sql、readme、深度思考」时启用，为 Agent 提供仓库入口、8 类目录约定、Skill 汇总与落款约定。

---

## 1. 入口索引

- **路径**：仓库根 `jerygithub.txt`
- **内容**：GitHub Pages URL、Skills 索引、8 类目录说明；维护者落款 Mr. Yuan。
- **用途**：入口索引，不贴 Skill 全文；全文汇总见根下 `Skills_汇总.md`。

---

## 2. 8 类目录（仓库根）

| 目录 | 用途 |
|------|------|
| wiki/ | 知识库、概念与术语说明、长期可复用文档 |
| blog/ | 随笔、过程记录、非正式总结 |
| products/ | 产品说明、交付物清单、产品化产出 |
| prompt/ | 各类 Prompt 模板、Agent 启动指令 |
| 脚本/ | 独立脚本或脚本索引 |
| sql/ | 独立 SQL 或 SQL 索引 |
| readme/ | 根级 README 或全库 README 索引 |
| 深度思考/ | 深度思考、复盘、策略与决策记录 |

- **规则**：新内容按类放入对应目录；既有内容保留原路径（方案 A）。

---

## 3. 贷后巡检项目内 8 类

- **路径**：`12-agent_finalize/10-Collection_Inspection` 下同名子目录（wiki、blog、products、prompt、脚本、sql、readme、深度思考）。
- **用途**：贷后巡检产出只在该项目内按类存放；既有文件保留原路径（方案 A）。

---

## 4. Skill 汇总

- **路径**：根下 `Skills_汇总.md`
- **用途**：可导出全文汇总；新增/修改 Skill 后需更新此文件。

---

## 5. 合作宪法

- 所有产出带落款 Mr. Yuan；回答末尾签名 Mr. Yuan。

---

**维护者**：Mr. Yuan
