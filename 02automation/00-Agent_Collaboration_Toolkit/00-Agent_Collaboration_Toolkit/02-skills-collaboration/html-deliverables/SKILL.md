---
name: html-deliverables
description: 制作 HTML 类产出物（演示、述职、报告、落地页等）。触发词：制作 HTML、HTML 演示、HTML Slides、述职 HTML、结项报告风格、infront、前端展示、单页演示。说明 WHAT（技术约定、风格选项、导航引擎、存放位置）与 WHEN（用户要求做 HTML 演示/报告/述职材料时使用）。
---

# html-deliverables

本 Skill 在用户要求**制作 HTML 类产出物**（如演示 Slides、述职报告、结项风格报告、落地页、数据看板等）时启用，为 Agent 提供技术约定、风格选项、导航与结构规范、以及与其他项目/ Skill 的衔接。

---

## 1. 何时启用

- 用户提到「制作 HTML」「HTML 演示」「HTML Slides」「述职 HTML」「结项报告风格」「infront」「前端展示」「单页演示」时。
- 用户要求做**可离线打开的演示/汇报/报告**且指定或默认输出为 HTML 时。
- 与 [ai-sharing-context](.cursor/skills/ai-sharing-context/SKILL.md) 区分：本 Skill 管**通用 HTML 产出规范**；ai-sharing-context 管**AI 分享项目**内的具体演示文件与便携包。

---

## 2. 技术约定

### 2.1 单文件优先

- **默认**：单文件 HTML，内联 CSS + JS，**不依赖外部 CDN 或本地库**，便于离线、拷贝、投屏。
- 若需图表：可预留 `<div class="chart-placeholder">` 或占位图，后续替换为截图或内嵌 ECharts 等（再视情况引入单文件脚本）。
- 字体：优先系统字体栈（如 `'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif`），避免外链字体以保证离线可用。

### 2.2 导航引擎（Slides 类）

- **必备**：页码展示（当前页 / 总页数）、进度条、上一页/下一页按钮。
- **键盘**：左/上 = 上一页，右/下/空格 = 下一页，Home/End = 首/末页。
- **滚轮**：当前页可滚动时优先滚动，到底/到顶后再滚轮翻页。
- **触摸**：左右滑动翻页（可选）。
- 实现可参考：`12-agent_finalize/11-AI_Sharing/Annual_Review_2025/Annual_Review_2025.html` 或 `AI_Share_HarryPotter_V4.html` 中的导航脚本。

### 2.3 风格选项

| 风格 | 主色 | 背景 | 适用场景 |
|------|------|------|----------|
| **商务蓝白** | `#0052cc`、`#172b4d` | 白/浅灰 | 述职、结项报告、QBR/MBR 风格 |
| **暗色/魔法** | `#d4af37`(金)、`#740001`(深红) | 深色渐变 | AI 分享、主题演讲 |
| **现代深色** | 渐变蓝/紫 | 深色底 | 科技感汇报、产品发布 |

- 设计 token：用 CSS 变量（如 `--primary`、`--bg`、`--text`）集中管理颜色与间距，便于换肤。

### 2.4 响应式与投屏

- 使用 `max-width`、`flex`/`grid` 控制内容宽度，避免大屏上过宽。
- 字体与间距使用 `rem` 或相对单位，保证缩放可读。
- 投屏时以 16:9 或 4:3 为常见比例，可设 `min-height: 100vh` 保证一屏一页感（Slides 类）。

---

## 3. 存放位置

- **产出路径**：一律落在 **12-agent_finalize** 下对应业务目录（见 [workspace-structure](.cursor/rules/workspace-structure.mdc)）。
- **示例**：
  - 述职/年度汇报 → `12-agent_finalize/11-AI_Sharing/Annual_Review_2025/`
  - AI 分享演示 → `12-agent_finalize/11-AI_Sharing/` 或便携包子目录
  - 其他汇报/报告 → `12-agent_finalize/` 下对应主题文件夹（如 `04-Data_Analysis`、`11-AI_Sharing`）
- **素材**：图片等放该 HTML 同目录下的 `assets/` 或 `img/`，在 HTML 中用相对路径引用。

---

## 4. 数据与素材来源

- **MBR/QBR 数据**：数值类内容优先从 `04-report material/MBR/`、`04-report material/MBR/QBR/02-Materials` 与 `03-Output` 中已有 Markdown/文本/HTML 提取；需具体指标时注明来源（如 MBR数据源.xlsx、QBR催收_25XX.pptx），便于用户本机或 943 取数后填充。
- **占位符**：暂无数值时使用 `[待填充]` 或 `[待填充: 说明]`，并在页脚或注释中注明**数据来源路径**。
- **个人站/简历**：若需引用个人站内容，见 [personal-site-context](.cursor/skills/personal-site-context/SKILL.md)；URL：`https://jerr-yuan.github.io/-risk-digital-assets/`。

---

## 5. 与相关 Skill 的关系

| Skill | 关系 |
|-------|------|
| **ai-sharing-context** | 管 AI 分享项目的演示文件、便携包、Harry Potter 版 Slides；做「AI 分享」相关 HTML 时两 Skill 可同时参考。 |
| **personal-site-context** | 管个人站 URL、业务场景与 8/9 类；做对外展示或需从个人站提炼内容时参考。 |
| **yuan-digital-assets-convention** | 产出按 11 类落位；HTML 报告/演示通常归入 `products` 或 `report`。 |

---

## 6. 协作规则（必守）

- 遵守《AI Agent 协作工作流规则手册》；**先讨论再执行**（复杂结构或风格先确认）。
- **版本只增不改**：同一用途多版时用 V1/V2 或日期后缀区分，不覆盖旧版。
- **落款**：生成的 HTML 若含页脚/结尾，可加「维护者：Mr. Yuan」或等效；每次回答末尾签名 **Mr. Yuan**。

---

## 7. 参考实现

- **商务蓝白 Slides**：`12-agent_finalize/11-AI_Sharing/Annual_Review_2025/Annual_Review_2025.html`（13 页、KPI 卡片、时间线、导航栏）。
- **暗金主题 Slides**：`12-agent_finalize/11-AI_Sharing/AI_Share_Portable_20260209/AI_Share_HarryPotter_V4.html`（12 页 + Overlay、BGM、粒子效果）。
- **QBR 核心一页（单页 HTML）**：`04-report material/MBR/QBR/03-Output/QBR_Core_One_Page_Visual_Reference.html`。

---

**维护者**：Mr. Yuan
