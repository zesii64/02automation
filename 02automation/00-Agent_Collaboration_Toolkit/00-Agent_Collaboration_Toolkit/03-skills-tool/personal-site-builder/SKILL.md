---
name: personal-site-builder
description: Build and maintain Yuan Peng's personal GitHub Pages site with Apple-minimalist design. Use when creating or editing HTML pages for the personal site, redesigning pages, adding new case studies, or updating site content. Triggers on keywords like personal site, GitHub Pages, homepage, inspector, case study, achievements page.
---

# Personal Site Builder

## Site Overview

Owner: 袁鹏 — 贷后策略负责人 · 资深策略专家
Core narrative: "将策略经验编码为系统能力，让 AI Agent 不只自动化，更能自主判断与决策。"
Repo: `https://github.com/jerr-yuan/-risk-digital-assets`
Live: `https://jerr-yuan.github.io/-risk-digital-assets/`

## Design System

Read the Cursor Rule at `e:/.cursor/rules/personal-site-design.mdc` for complete CSS variables, typography, spacing, and animation specs.

Key principles:
- Apple minimalist white background, Inter + Noto Sans SC fonts
- 8px grid, `clamp()` fluid typography, scroll-reveal via IntersectionObserver
- All styles inline (no external CSS files), each HTML page is self-contained
- Responsive breakpoints: 900px (tablet), 500px (mobile)

## Page Architecture

```
index.html                        # Homepage — hero + metrics + case cards
achievements.html                 # Key results with data visualization
cases/
  collection-inspection.html      # Smart Inspector deep-dive (primary case)
  risk-prediction.html            # Risk prediction & resource planning
  ofw-strategy.html               # OFW piece-rate incentive pricing
  reports/                        # Actual report outputs (linked from case pages)
methodology/index.html            # Methodology frameworks (4 frameworks)
1.resume/resume-v4.16.html        # Standalone resume (own design, do not restyle)
```

Navigation (5 items): 首页 | 业绩成就 | 实战案例 | 方法论 | 简历 (target="_blank")

## Content Strategy

### Homepage

- Hero: name + title + 4 personality tags (结果导向 | 好奇心驱动 | AI 风险策略落地 | 业务赋能)
- Subtitle: strategy-sense-into-agent narrative (NOT generic "X years experience")
- Metrics: 6-column grid with actual business results (M2+ recovery +104%, rate +55%, etc.)
- Case cards: link to detailed case study pages

### Inspector Page (Primary Case Study)

Structure follows "show, then explain":

**Part A — 这是什么 (What)**
1. Hero (light gradient, no abstract numbers — use navigation hint instead)
2. Interactive Demo (macOS frame, 3 clickable tabs):
   - Part 1: KPIs + Vintage Matrix (color-coded DPD table)
   - Part 2: KPIs + Shift-Share Waterfall Bridge (M-1 → Mix → Rate → Current)
   - Part 3: KPIs + Efficiency Quadrant (2x2: effort x achievement)
3. 系统的灵魂 (The Soul): 6 cards — Data Dictionary, Attribution Checklist, Diagnostic Business Sense, System Prompt Design, Wiki Knowledge System, Replicability
4. Module overview, Before/After, Business Value

**Part B — 怎么构建的 (How)**
5. Pain points, Vision (6-step chain), 3 monitoring lines
6. Architecture, Technical depth, Build log
7. Next steps: Dynamic Case Routing & Incentive/Punishment Closed Loop

### Key Content Principles

- Lead with OUTCOMES, not process
- The "soul" is domain expertise encoded into the system — not years of experience
- Avoid hollow metrics; every number should tell a story
- Interactive demos over static screenshots
- "查看实际报告产出" links to real output when available

## Workflow

### Adding a New Case Study

1. Create `cases/<slug>.html`
2. Copy header/footer/CSS-variables from an existing case page
3. Follow Part A (what) → Part B (how) structure
4. Add a card on the homepage linking to the new case
5. Update navigation if needed

### Iterating on Design

1. Always create in `e:/site-redesign/preview/` first
2. Never overwrite live files directly
3. Get user confirmation on preview
4. Assemble final folder at `e:/site-redesign/final/`
5. User pushes to GitHub manually

### Reskinning Old Pages

When updating old-style pages to the new design:
1. Keep all original content/data
2. Replace header with new sticky glassmorphism header
3. Add `:root` CSS variables and Google Fonts
4. Add scroll-reveal animations
5. Update navigation links to the 4-item structure
6. Add responsive `@media` queries

## Anti-Patterns

- Do NOT use "X年经验" as a selling point — use concrete results instead
- Do NOT use dark blue hero backgrounds — use white/light gradient
- Do NOT show abstract standalone numbers without context
- Do NOT modify `1.resume/` files during site redesign — resume has its own design
- Do NOT use external CSS/JS files — keep everything inline for GitHub Pages simplicity
