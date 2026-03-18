---
name: yuan-digital-assets-convention
description: Organizes and creates files under 业务场景→子项目→11类 (wiki, blog, products, report, prompt, 脚本, sql, data, readme, 深度思考, skill). Use when creating or moving files in 12-agent_finalize, when asked about 数字资产/约定版/文件结构/11类, or when generating docs for Mr. Yuan. Enforces 维护者 Mr. Yuan and reply sign-off — Mr. Yuan.
---

# 数字资产约定版 — 标准化执行

本 Skill 在用户于本仓库下**新建/移动文件、询问数字资产/约定版/文件结构/11 类**时启用，确保按「业务场景 → 子项目 → 11 类」标准化落位，并遵守署名约定。

---

## 1. 路径与结构

- **做项目**：新建/修改产出一律落在 **12-agent_finalize** 下对应业务场景目录，再落到**子项目**下的 **11 类**之一。
- **11 类目录名**（按顺序）：`wiki`, `blog`, `products`, `report`, `prompt`, `脚本`, `sql`, `data`, `readme`, `深度思考`, `skill`。
- **查阅约定/清单**：`数字资产_约定版/文件结构_按9类.md`、`数字资产_约定版/待确认清单.md`；方法论/规范参考 `11-Agent/Core_Digital_Assets`。
- **约定版产出**：仅文档在 `数字资产_约定版/`，由 `12-agent_finalize/build_convention.py` 生成；不修改源文件。

详见 [reference.md](reference.md) 中的业务场景与 11 类映射。

---

## 2. 署名与落款

- **生成文档**：文末或文首须含 **维护者：Mr. Yuan**。
- **每次回答**：末尾须带 **— Mr. Yuan**（或等效署名）。

---

## 3. 与仓库规则的关系

- 做项目唯一在 **12-agent_finalize**，查规范在 **11-Agent/Core_Digital_Assets**，见 `.cursor/rules/workspace-structure.mdc`。
- 先讨论再执行、回答末尾 Mr. Yuan，见 `.cursor/rules/collaboration-constitution.mdc`。

---

**维护者**：Mr. Yuan
