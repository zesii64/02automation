# Agent Collaboration Toolkit

> **用途**：汇总 Cursor 与 Claude Code 两个 AI Agent 工具的所有 **合作相关** Rules & Skills，作为统一参考。  
> **性质**：参考副本。原文件保持在各工具的配置目录中不动，此处仅供浏览与对照。  
> **创建日期**：2026-03-11  
> **维护者**：Mr. Yuan

---

## 目录结构

```
00-Agent_Collaboration_Toolkit/
├── README.md                           ← 本文件
├── 01-rules/                           ← 合作规则
│   ├── cursor/                         ← Cursor 工作区规则
│   │   ├── collaboration-constitution.mdc
│   │   ├── agent-reminder.mdc
│   │   ├── workspace-structure.mdc
│   │   ├── digital-asset-standards.mdc
│   │   └── archive/
│   │       └── collaboration-constitution_V3.2_snapshot_20260217.mdc
│   └── claude-code/                    ← Claude Code 全局配置
│       ├── CLAUDE.md
│       └── settings.json
├── 02-skills-collaboration/            ← 合作流程 / 文件组织技能
│   ├── yuan-digital-assets-convention/
│   ├── repo-content-structure/
│   └── html-deliverables/
├── 03-skills-tool/                     ← 通用工具能力技能
│   ├── ui-ux-pro-max/
│   ├── frontend-design-ui-ux-pro-max/
│   ├── personal-site-builder/
│   └── resume-pdf-and-github-deploy/
└── 04-skills-meta/                     ← Cursor/Claude 元技能
    ├── create-rule/
    ├── create-skill/
    ├── create-subagent/
    ├── migrate-to-skills/
    └── update-cursor-settings/
```

---

## 文件清单与来源对照表

### 01-rules/ — 合作规则

| 文件 | 版本 | 用途 | 原始路径 |
|------|------|------|----------|
| `cursor/collaboration-constitution.mdc` | **V4.0** | 协作宪法主文件（含规则 0-16） | `e:\.cursor\rules\collaboration-constitution.mdc` |
| `cursor/agent-reminder.mdc` | — | Agent 必守两条：签名 + 不确定则确认 | `e:\.cursor\rules\agent-reminder.mdc` |
| `cursor/workspace-structure.mdc` | — | 规则 5.5：仓库结构约定（方案 A） | `e:\.cursor\rules\workspace-structure.mdc` |
| `cursor/digital-asset-standards.mdc` | — | 规则 5.6：数字资产 11 类结构 + 呈现标准 | `e:\.cursor\rules\digital-asset-standards.mdc` |
| `cursor/archive/...V3.2_snapshot...` | V3.2 | 协作宪法历史快照（2026-02-17） | `e:\.cursor\rules\archive\...` |
| `claude-code/CLAUDE.md` | **V3.4** | Claude Code 版协作规则（含规则 1.8/1.9） | `C:\Users\yuanpeng03\.claude\CLAUDE.md` |
| `claude-code/settings.json` | — | Claude Code 全局配置（模型、权限、插件） | `C:\Users\yuanpeng03\.claude\settings.json` |

### 02-skills-collaboration/ — 合作流程技能

| Skill | 用途 | 原始路径 |
|-------|------|----------|
| `yuan-digital-assets-convention/` | 数字资产 11 类约定：业务场景 → 子项目 → 11 类文件夹 | `e:\.cursor\skills\yuan-digital-assets-convention\` |
| `repo-content-structure/` | 仓库入口与 8 类内容目录约定 | `e:\.cursor\skills\repo-content-structure\` |
| `html-deliverables/` | HTML 产出物约定：单文件、离线优先、导航引擎 | `e:\.cursor\skills\html-deliverables\` |

### 03-skills-tool/ — 通用工具能力

| Skill | 用途 | 原始路径 |
|-------|------|----------|
| `ui-ux-pro-max/` | UI/UX 设计系统（67 种风格、96 调色板、13 技术栈，含 data/ + scripts/） | `e:\.cursor\skills\ui-ux-pro-max\` |
| `frontend-design-ui-ux-pro-max/` | 前端设计（Claude 插件版，生产级 HTML/CSS/JS） | `C:\Users\yuanpeng03\.cursor\skills\frontend-design-ui-ux-pro-max\` |
| `personal-site-builder/` | 个人 GitHub Pages 站构建与维护（Apple 极简风格） | `C:\Users\yuanpeng03\.cursor\skills\personal-site-builder\` |
| `resume-pdf-and-github-deploy/` | 简历 HTML 转 PDF（Playwright）+ 个人站推 GitHub | `C:\Users\yuanpeng03\.cursor\skills\resume-pdf-and-github-deploy\` |

### 04-skills-meta/ — Cursor/Claude 元技能

| Skill | 用途 | 原始路径 |
|-------|------|----------|
| `create-rule/` | 创建 Cursor 规则（.cursor/rules/、AGENTS.md） | `C:\Users\yuanpeng03\.cursor\skills-cursor\create-rule\` |
| `create-skill/` | 创建 Cursor Agent Skills（SKILL.md 格式与最佳实践） | `C:\Users\yuanpeng03\.cursor\skills-cursor\create-skill\` |
| `create-subagent/` | 创建自定义子 Agent（代码 reviewer、调试器等） | `C:\Users\yuanpeng03\.cursor\skills-cursor\create-subagent\` |
| `migrate-to-skills/` | 将 .mdc 规则和 slash 命令迁移到 Skills | `C:\Users\yuanpeng03\.cursor\skills-cursor\migrate-to-skills\` |
| `update-cursor-settings/` | 修改 Cursor/VSCode settings.json | `C:\Users\yuanpeng03\.cursor\skills-cursor\update-cursor-settings\` |

---

## Cursor 版 vs Claude Code 版协作宪法：版本差异对比

两个版本同源但独立演进，以下是关键差异：

| 规则 | Cursor V4.0 | Claude Code V3.4 | 说明 |
|------|:-----------:|:-----------------:|------|
| 规则 0：先讨论再执行 | ✅ | ✅ | 两版一致 |
| 规则 1：签名确认 | ✅ | ✅ 精简版 | Claude Code 版明确"短回答不需签名" |
| 规则 1.5：长任务进度同步 | ✅ | ✅ | Claude Code 版增加"优先使用 TodoWrite" |
| 规则 1.6：本地脚本暂停 | ✅ | ✅ | 两版一致 |
| 规则 1.7：943 平台取数 | ✅ | ✅ | 两版一致 |
| **规则 1.8：Skills 自动持久化** | ❌ | ✅ | **仅 Claude Code**：触发条件 → 写入 memory |
| **规则 1.9：对话结束 Memory 检查** | ❌ | ✅ | **仅 Claude Code**：自问两个问题 |
| 规则 2-5：版本控制/文件修改/验证/错误 | ✅ | ✅ | 两版一致 |
| 规则 5.5：仓库结构约定 | ✅ | ✅ | 两版一致 |
| 规则 5.6：数字资产 11 类 | ✅ | ✅ | 两版一致 |
| 规则 8：人机边界 | ✅ | ✅ | 两版一致 |
| 规则 9：不确定则确认 | ✅ | ✅ | 两版一致 |
| **规则 11：专业评估维度** | ❌ | ✅ | **仅 Claude Code**：5 维度检查清单 |
| **规则 11-16：Agent 工作流规则** | ✅ | ❌ | **仅 Cursor**：状态管理、权限边界、日志、版本管理、回滚、命名规范 |

### 差异总结

- **Claude Code 独有**：规则 1.8（Skills 自动持久化）、规则 1.9（Memory 检查）、规则 11（专业评估 5 维度）
- **Cursor 独有**：规则 11-16（Agent 工作流状态管理、权限边界、日志标准化、Skill/Rule 版本管理、回滚机制、命名规范）
- **建议**：下次统一版本时，将两边独有的规则合并为 **V5.0**

---

## 排除的业务知识文件

以下文件属于具体业务项目知识，不纳入本合作工具包：

| 文件 | 类型 | 所属项目 |
|------|------|----------|
| `collection-inspection-excel.mdc` | Rule | 贷后巡检 |
| `personal-site-design.mdc` | Rule | 个人站 |
| `slide-modification-isolation.mdc` | Rule | 年度汇报 |
| `ai-sharing-context/` | Skill | AI 分享 |
| `annual-review-methodology/` | Skill | 年终总结 |
| `collection-inspection-context/` | Skill | 贷后巡检 |
| `data-inspection-workflow/` | Skill | 贷后巡检 |
| `inspector-intelligent/` | Skill | 智能巡检 |
| `personal-site-context/` | Skill | 个人站 |
| `weekly-report/` | Skill | 双周报 |
| `risk-prediction-validation.mdc` | Skill | 风险预测 |

---

## 维护说明

1. **此处为参考副本**：实际生效的规则仍在各工具原始路径中（Cursor 读 `.cursor/rules/` 和 `.cursor/skills/`，Claude Code 读 `~/.claude/CLAUDE.md`）
2. **更新流程**：修改原始文件 → 同步复制到此处 → 更新本 README 中的版本号
3. **版本对齐**：建议定期检查 Cursor 版与 Claude Code 版的差异，逐步合并为统一版本
4. **Archive 策略**：大版本更新前，将旧版复制到 `01-rules/cursor/archive/` 归档

---

**维护者**：Mr. Yuan  
**最后更新**：2026-03-11
