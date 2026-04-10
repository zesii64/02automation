# Collection Operations Report - PRD

> **Version**: 1.3
> **Status**: In Progress (v2_0 implementation pending)
> **Last Updated**: 2026-03-19
> **Style**: McKinsey (Clean, Professional, Minimal)
> **Changelog**: v1.3 — Gap analysis against v1_0; requirements updated with implementation status; data schema bumped to v1.2

---

## 1. Project Overview

### 1.1 Purpose

The Collection Operations Report is a standalone HTML report serving the collection operations team (TL, STL, and data analysts). It provides daily/weekly performance monitoring, anomaly detection, and automated insights to help collection staff focus on analysis and execution rather than data preparation.

### 1.2 Target Users

| Role | Description | Primary View |
|------|-------------|--------------|
| **TL (Team Leader)** | Group supervisors | Daily review of their group's performance |
| **STL (Section/Module Team Leader)** | Module responsible | Weekly review of module performance |
| **Data Analyst** | Full data monitoring | Anomaly detection and trend analysis |

### 1.3 Scope

- **In-house collection only** (non-outsourced)
- **Philippines market** (Cashloan, TTbnpl, Lazada, etc.)
- **English UI** for broader accessibility

---

## 2. User Stories

| # | User | Story | Priority |
|---|------|-------|----------|
| US-001 | TL | As a TL, I want to see my group's daily performance vs target so I can identify underperformers | P0 |
| US-002 | TL | As a TL, I want to drill down to agent level to see individual performance when target is not met | P0 |
| US-003 | TL | As a TL, I want automated conclusions about why we missed target so I know what to improve | P1 |
| US-004 | STL | As an STL, I want to see my module's weekly performance so I can track progress | P0 |
| US-005 | STL | As an STL, I want to drill down to group level to identify struggling groups | P0 |
| US-006 | Analyst | As an analyst, I want to see all agents/groups with 3+ consecutive unmet days so I can flag high-risk cases | P0 |
| US-007 | Analyst | As an analyst, I want to see recovery trends by module so I can identify at-risk modules | P0 |
| US-008 | All | As a user, I want date selection controls so I can review historical data | P1 |

---

## 3. Functional Requirements

### 3.1 Three-Tab Architecture

```
┌─────────────────────────────────────────────────────┐
│  Role Selector: [TL] [STL] [Data]                  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Tab 1: TL View (Daily Group Review)               │
│  Tab 2: STL View (Weekly Module Review)             │
│  Tab 3: Data View (Anomaly + Trend)                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 3.2 TL Tab Requirements

| Req ID | Requirement | Description | v1_0 Status |
|--------|-------------|-------------|-------------|
| TL-01 | Group Selector | Dropdown to select group | ✅ Done |
| TL-02 | Date Selector | Date picker (last 30 days) | ❌ Missing |
| TL-03 | Default Date Logic | Show yesterday; if Monday, show Saturday | ❌ Missing |
| TL-04 | Summary Metrics | Target, Actual, Achievement Rate, vs Module Avg | ✅ Done |
| TL-05 | Status Badge | Show "Target Met" or "Target Not Met" | ✅ Done |
| TL-06 | Daily Trend Chart | Line chart with actual vs dashed red target line | ✅ Done |
| TL-07 | Unmet Detail Section | Show only when target not met | ✅ Done |
| TL-08 | Agent Drill-down Table | Agent-level metrics with `consecutiveDays` column | ❌ Missing column; uses random data not `agentPerformance` schema |
| TL-09 | Consecutive Days Highlight | Red for 3+ days, yellow for 1-2 days | ❌ Hardcoded row index; not driven by data |
| TL-10 | Automated Conclusions | Rule-based insights (1-3 bullet points) | ✅ Done |
| TL-11 | Empty State | Prompt to select group when none selected | ❌ Missing |

### 3.3 STL Tab Requirements

| Req ID | Requirement | Description | v1_0 Status |
|--------|-------------|-------------|-------------|
| STL-01 | Module Selector | Dropdown to select module | ✅ Done |
| STL-02 | Week Selector | Dropdown to select week (last 12 weeks) | ❌ Missing |
| STL-03 | Default Week Logic | Show last complete week | ❌ Missing |
| STL-04 | Summary Metrics | Target, Actual, Achievement Rate, vs Last Week | ✅ Done |
| STL-05 | Status Badge | Show "Weekly Target Met/Not Met" | ✅ Done |
| STL-06 | Weekly Trend Chart | Bar chart with actual vs dashed target line | ✅ Done |
| STL-07 | Unmet Detail Section | Show only when target not met | ✅ Done |
| STL-08 | Group Drill-down Table | Group-level metrics with `consecutiveWeeks` column | ❌ Missing column; uses random data not `groupPerformance` schema |
| STL-09 | Consecutive Weeks Highlight | Red for 3+ weeks, yellow for 1-2 weeks | ❌ Hardcoded row index; not driven by data |
| STL-10 | Automated Conclusions | Rule-based insights (1-3 bullet points) | ✅ Done |
| STL-11 | Empty State | Prompt to select module when none selected | ❌ Missing |

### 3.4 Data Tab Requirements

| Req ID | Requirement | Description | v1_0 Status |
|--------|-------------|-------------|-------------|
| DATA-01 | Sub-tabs | Three sub-tabs: Under-performing, Recovery Trend, Agent Overview | ✅ Done |
| DATA-02 | Anomaly Table | Agents/Groups with 3+ consecutive unmet days | ✅ Done |
| DATA-03 | Anomaly Highlight | Red background for 3+ days | ✅ Done |
| DATA-04 | Module Trend Charts | One chart card per module (2-column grid) | ❌ Wrong: single combined chart, not per-module cards |
| DATA-05 | Risk Badge | "At Risk" (red) or "On Track" (green) per module | ❌ Missing |
| DATA-06 | Risk Module Review | Show unmet groups for at-risk modules | ✅ Done (but tied to wrong chart layout) |
| DATA-07 | Recovery Trend Target Line | Green dashed line showing daily target | ❌ Missing (no target line in trend chart) |
| DATA-08 | Agent Overview | Date selector + per-module agent detail table; sort by selected-date actual repay (desc) within module | ✅ Done |

---

## 4. Data Model

### 4.1 Core Dimensions

| Dimension | Description | Example |
|-----------|-------------|---------|
| **Module** | Collection stage by overdue days | S0, S1, S2, M1, M2, T2, T4, T5 |
| **Group** | Collection team under a module | G-S1-01, G-M1-02 |
| **Agent** | Individual collector | A001, A002 |
| **TL** | Team Leader (group supervisor) | - |
| **STL** | Section/Module Team Leader | - |

### 4.2 Key Metrics

| Metric | Description | Calculation |
|--------|-------------|-------------|
| **Achievement Rate** | % of target achieved | Actual / Target * 100 |
| **Gap** | Shortfall vs target | Target - Actual |
| **Consecutive Days/Weeks** | Days/weeks below target | Count of consecutive unmet |
| **Call Volume** | Number of calls made | Sum of calls |
| **Connect Rate** | % of calls connected | Connected / Total * 100 |
| **PTP Rate** | % of Promise to Pay | PTP cases / Contacted * 100 |
| **Attendance** | % of agents present | Present / Scheduled * 100 |

### 4.3 Data Schema

See [12_Data_Schema_Collection_Report.md](wiki/12_Data_Schema_Collection_Report.md) for detailed JSON schema.

---

## 5. UI/UX Specification

### 5.1 Layout

- **Header**: Solid navy blue background, role selector, report title
- **Main Content**: White cards on light gray background
- **Cards**: 4px border-radius, 1px border (minimal style)
- **Max Width**: 1200px, centered

### 5.2 Color Palette (McKinsey Style)

| Purpose | Color | Hex |
|---------|-------|-----|
| Primary | Navy Blue | #1e3a5f |
| Success | Green | #059669 |
| Danger | Red | #dc2626 |
| Warning | Amber | #d97706 |
| Background | Gray 50 | #fafafa |
| Text Primary | Dark Gray | #1a1a1a |
| Text Secondary | Gray | #6b7280 |
| Border | Light Gray | #e5e7eb |

### 5.3 Typography

- **Font Family**: 'Helvetica Neue', Arial, sans-serif
- **Headings**: 16-20px, font-weight 600
- **Body**: 13-14px, font-weight 400-500
- **Labels**: 10-11px, uppercase, muted color, letter-spacing

### 5.4 Charts

| Chart Type | Use Case | Style |
|------------|----------|-------|
| Line | TL daily trend | Navy blue line, dashed red target |
| Bar | STL weekly trend | Navy blue bars, dashed red target |
| Multi-line | Module trends | Per-module lines, green dashed target |

### 5.5 Component Style Guide

| Component | Style |
|-----------|-------|
| Cards | White background, 1px border, no shadow |
| Metrics Grid | Horizontal layout with vertical dividers |
| Status Badge | Colored background with border |
| Tables | Light gray header, bottom borders only |
| Buttons | Underline style for active, text only for inactive |

---

## 6. Non-Functional Requirements

### 6.1 Performance

- Page load: < 2 seconds
- Chart render: < 500ms
- Data switch: < 200ms

### 6.2 Compatibility

- Chrome, Edge, Firefox (latest 2 versions)
- Desktop-first (responsive for tablet)

### 6.3 Distribution

- **Single HTML file** for easy distribution
- **CDN dependencies**: Tailwind CSS, ECharts
- **Offline mode**: CDN resources can be inlined for offline use

---

## 7. Future Enhancements

| # | Enhancement | Description | Priority |
|---|-------------|-------------|----------|
| FE-001 | Real Data Integration | Connect to SQL/Excel data source | P0 |
| FE-002 | Export to PDF | Add PDF export functionality | P2 |
| FE-003 | Email Distribution | Scheduled email with report | P2 |
| FE-004 | Comments/Notes | Allow users to add notes (localStorage) | P3 |
| FE-005 | Comparison View | Compare vs previous period | P3 |

---

## 8. Acceptance Criteria

### 8.1 TL Tab

- [ ] Can select a group from dropdown
- [ ] Default date is yesterday (or Saturday if Monday)
- [ ] Date selector shows only last 30 days
- [ ] Summary metrics display correctly
- [ ] Chart shows actual vs target line
- [ ] Unmet section shows when achievement < 100%
- [ ] Agent table shows consecutive days column
- [ ] 3+ consecutive days row highlighted red
- [ ] Automated conclusions generated
- [ ] Empty state shown when no group selected

### 8.2 STL Tab

- [ ] Can select a module from dropdown
- [ ] Default week is last complete week
- [ ] Week selector shows last 12 weeks
- [ ] Summary metrics display correctly
- [ ] Chart shows actual bars vs target line
- [ ] Unmet section shows when achievement < 100%
- [ ] Group table shows consecutive weeks column
- [ ] 3+ consecutive weeks row highlighted red
- [ ] Automated conclusions generated
- [ ] Empty state shown when no module selected

### 8.3 Data Tab

- [ ] Can switch between Under-performing, Trend, and Agent Overview sub-tabs
- [ ] Anomaly table shows all 3+ consecutive unmet cases
- [ ] High-risk rows (3+ days) highlighted red
- [ ] Each module has its own trend chart card
- [ ] Charts in 2-column grid layout
- [ ] Risk modules marked with "At Risk" badge
- [ ] Risk module review section shows unmet groups
- [ ] Agent Overview has its own date selector
- [ ] Agent Overview displays agent details grouped by module
- [ ] Within each module, agents are sorted by selected-date actual repay amount (high to low)

---

## 9. Technical Implementation

### 9.1 File Structure

```
reports/
  └── Collection_Operations_Report_v1_1.html  (Main report)

wiki/
  └── 12_Data_Schema_Collection_Report.md     (Data schema)
```

### 9.2 Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| Tailwind CSS | 3.x | Styling |
| ECharts | 5.4.3 | Charts |
| Lucide Icons | 0.321.0 | Icons |

### 9.3 Browser Support

- Chrome 90+
- Edge 90+
- Firefox 88+
- Safari 14+

---

**Document Version**: 1.3
**Last Updated**: 2026-03-19
**Author**: Claude Code
