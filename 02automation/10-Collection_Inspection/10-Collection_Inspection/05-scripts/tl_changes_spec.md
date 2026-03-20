# TL Tab Change Spec

> **Source**: Research Agent output — 2026-03-19
> **Scope**: TL Tab fixes against PRD v1.3 requirements (TL-02, TL-03, TL-08, TL-09, TL-11)
> **Target Version**: v2_0

---

## Summary of Changes

1. **Add date selector** (TL-02/03) — missing HTML element + date range generation + default logic
2. **Fix agent table data wiring** (TL-08) — replace hardcoded mock agents with `agentPerformance` schema
3. **Insert `consecutiveDays` column** (TL-08) — add between "Agent" and "Target" columns
4. **Implement row highlighting** (TL-09) — replace index-based logic with data-driven consecutive days highlighting (red if ≥3, yellow if 1-2)
5. **Add empty state** (TL-11) — show message when no group selected
6. **Add missing CSS class** — `yellow-row` for 1-2 consecutive days

---

## Change 1: Date Selector (TL-02/03)

### DOM Location
Insert new date selector element **after** the group selector, within the same right-side flex container.

**Parent Container**: `<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">` (HTML lines 74-82)

**Current HTML Structure**:
```html
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
    <h2 style="font-size: 18px; font-weight: 700; color: #1e293b;">TL Daily Review</h2>
    <div style="display: flex; gap: 12px; align-items: center;">
        <label style="font-size: 14px; color: #64748b;">Select Group:</label>
        <select id="tl-group-select" onchange="loadTLData()">
            <option value="all">All Groups</option>
        </select>
    </div>
</div>
```

**What to Add**: Insert date label + date input after the group `</select>`:
- Element ID: `tl-date-select`
- Type: HTML `<select>` (dropdown, not date input — for consistent styling)
- Trigger: `onchange="loadTLData()"`

### Date Population Logic

**Function to modify**: `initTLView()` (HTML lines 434-441)

- Generate date array: last 30 days from today → yesterday (or Saturday if Monday)
- Format: YYYY-MM-DD (display and value)
- Default value:
  - If today is NOT Monday → yesterday (today - 1 day)
  - If today IS Monday → Saturday (today - 2 days)
- Populate `tl-date-select` with `<option>` elements

### loadTLData() Modification

**Function**: `loadTLData()` (HTML line 443)

- Read selected date: `const selectedDate = document.getElementById('tl-date-select').value;`
- Pass `selectedDate` to `loadTLAgentTable(group, selectedDate)`
- Reserve for future date-based data filtering

---

## Change 2: Agent Table `consecutiveDays` Column (TL-08)

### Current Table Columns (lines 131-140)

Order:
1. Agent
2. Target
3. Actual
4. Achievement
5. Calls
6. Conn. Rate
7. PTP
8. Attendance

### New Column Position

**Insert `Consecutive Days` as column 2** (between Agent and Target):

1. Agent
2. **Consecutive Days** ← NEW
3. Target
4. Actual
5. Achievement
6. Calls
7. Conn. Rate
8. PTP
9. Attendance

**Header `<th>` to insert** (between Agent and Target headers):
```html
<th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Consec. Days</th>
```

### Data Source

Use: `MOCK_DATA.agentPerformance[groupId]` array

**All available fields per agent object** (schema section 5):
- `name` (String) — Agent ID
- `consecutiveDays` (Number) — **Primary field for column + highlighting**
- `target` (Number) — Daily target (PHP)
- `actual` (Number) — Actual recovery (PHP)
- `achievement` (Number) — Achievement rate (%)
- `calls` (Number) — Total calls made
- `connectRate` (Number) — Connection rate (%)
- `ptp` (Number) — PTP rate (%)
- `attendance` (Number) — Attendance rate (%)

---

## Change 3: Consecutive Days Highlight Logic (TL-09)

### Current (Wrong) Implementation

**Function**: `loadTLAgentTable(group)` (HTML lines 473-500)

**Problems**:
```javascript
const agents = MOCK_DATA.agents.slice(0, 5);  // WRONG: hardcoded agent list, ignores group
const isUnmet = i < 2;                         // WRONG: index-based, always first 2 rows = red
const target = 25000 + Math.random() * 10000; // WRONG: all metrics are random
// Row class:
<tr class="drilldown-row ${isUnmet ? 'red-row' : ''}">  // WRONG: no yellow, no data-driven logic
```

### Correct Logic

PRD TL-09: Red for 3+ days, yellow for 1-2 days.

```javascript
// Row class determination:
let rowClass = 'drilldown-row';
if (agent.consecutiveDays >= 3) {
    rowClass += ' red-row';
} else if (agent.consecutiveDays >= 1) {
    rowClass += ' yellow-row';
}
```

---

## Change 4: Empty State (TL-11)

### When to Show
Show when group selector value is `"all"` (default) or when `MOCK_DATA.agentPerformance[group]` is undefined.

### DOM Location
Add inside the TL Daily Review card, after the selectors row and **before** the metrics grid. Add `id="tl-metrics-container"` to the metrics flex div (line 83) to enable show/hide.

**HTML to add**:
```html
<div id="tl-empty-state" style="display: none; padding: 40px 20px; text-align: center; background: #f8fafc; border-radius: 4px;">
    <p style="font-size: 16px; color: #64748b; margin: 0;">Please select a specific group to view daily performance details.</p>
</div>
```

### Show/Hide Logic in `loadTLData()`

```javascript
if (group === 'all' || !MOCK_DATA.agentPerformance[group]) {
    document.getElementById('tl-empty-state').style.display = 'block';
    document.getElementById('tl-metrics-container').style.display = 'none';
    document.getElementById('tl-status-badge').innerHTML = '';
    document.getElementById('tl-unmet-section').style.display = 'none';
    return;
} else {
    document.getElementById('tl-empty-state').style.display = 'none';
    document.getElementById('tl-metrics-container').style.display = 'flex';
    // continue loading...
}
```

**Required DOM change**: Add `id="tl-metrics-container"` to the metrics flex div (line 83).

---

## Change 5: Agent Performance Data Wiring

### Lines to Remove/Replace

All in `loadTLAgentTable()` (lines 473-500):

```javascript
// REMOVE:
const agents = MOCK_DATA.agents.slice(0, 5);
const isUnmet = i < 2;
const target = 25000 + Math.random() * 10000;
const actual = isUnmet ? target * (0.7 + Math.random() * 0.2) : ...
const calls = Math.floor(30 + Math.random() * 40);
const connectRate = (15 + Math.random() * 15).toFixed(1);
const ptp = (5 + Math.random() * 10).toFixed(1);
const attendance = Math.floor(80 + Math.random() * 20);

// REPLACE WITH:
const agents = MOCK_DATA.agentPerformance[group] || [];
// then iterate: agents.forEach(agent => { ... use agent.target, agent.actual, etc. })
```

### MOCK_DATA Addition Needed

`agentPerformance` key must be added to MOCK_DATA with structure per schema section 5. Add entries for at minimum: `G-S1-01`, `G-S1-02`, `G-M1-01`.

Each agent entry:
```javascript
{ name: 'A001', consecutiveDays: 0, target: 25000, actual: 26500, achievement: 106.0, calls: 52, connectRate: 22.5, ptp: 8.2, attendance: 95 }
```

---

## CSS Additions Needed

Add after `.red-row:hover` rule (line 40 in `<style>`):

```css
.yellow-row { background: #fffbeb !important; }
.yellow-row:hover { background: #fef3c7 !important; }
```

---

## Implementation Checklist

- [ ] Add date selector HTML (`id="tl-date-select"`) after group selector
- [ ] `initTLView()`: populate date selector with last 30 days + default to yesterday/Saturday
- [ ] `loadTLData()`: read date from selector, pass to `loadTLAgentTable(group, date)`
- [ ] Add `id="tl-metrics-container"` to metrics flex div
- [ ] Add `<div id="tl-empty-state">` HTML
- [ ] `loadTLData()`: implement empty state show/hide logic
- [ ] Add `<th>Consec. Days</th>` header in agent table (position 2)
- [ ] Add `.yellow-row` CSS class
- [ ] Add `agentPerformance` to MOCK_DATA (all groups used)
- [ ] Rewrite `loadTLAgentTable()`:
  - Use `MOCK_DATA.agentPerformance[group]`
  - Remove all `Math.random()` calls
  - Add `consecutiveDays` `<td>` cell in correct column position
  - Implement data-driven row class logic
- [ ] Test: empty state when "All Groups" selected
- [ ] Test: red row when consecutiveDays >= 3
- [ ] Test: yellow row when consecutiveDays = 1 or 2
- [ ] Test: no highlight when consecutiveDays = 0
