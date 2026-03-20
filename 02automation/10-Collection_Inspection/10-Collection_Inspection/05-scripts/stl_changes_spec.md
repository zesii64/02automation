# STL Tab Change Spec

> **Source**: Research Agent output — 2026-03-19
> **Scope**: STL Tab fixes against PRD v1.3 requirements (STL-02, STL-03, STL-08, STL-09, STL-11)
> **Target Version**: v2_0

---

## Summary of Changes

1. **Week Selector (STL-02/03)**: Add HTML dropdown for last 12 weeks; default to most recent complete week (Mon–Sun); update `loadSTLData()` accordingly.
2. **Group Table `consecutiveWeeks` Column (STL-08)**: Insert new column after "Group" header; pull data from `MOCK_DATA.groupPerformance[moduleId]`.
3. **Consecutive Weeks Highlight Logic (STL-09)**: Replace hardcoded row-index logic with data-driven: red if ≥3, yellow if 1-2, none if 0.
4. **Empty State (STL-11)**: Add message prompt when no module selected.
5. **Group Performance Data Wiring**: Replace `loadSTLGroupTable()` random data with real `groupPerformance` schema lookup.
6. **CSS Addition**: Add `.yellow-row` class.

---

## Change 1: Week Selector (STL-02/03)

### DOM Location

**Parent element**: The right-side flex container holding the module selector (lines 161-165)

**Current code**:
```html
<div style="display: flex; gap: 12px; align-items: center;">
    <label style="font-size: 14px; color: #64748b;">Select Module:</label>
    <select id="stl-module-select" onchange="loadSTLData()">
        <option value="all">All Modules</option>
    </select>
</div>
```

**Insert after module `</select>`**:
```html
<label style="font-size: 14px; color: #64748b;">Select Week:</label>
<select id="stl-week-select" onchange="loadSTLData()">
    <option value="">-- Select Week --</option>
</select>
```

### Week Calculation Logic

**Function to modify**: `initSTLView()` (lines 557-564)

- Generate last 12 complete weeks (Mon–Sun cycle)
- Display format: `"MM/DD-MM/DD"` (e.g., `"03/09-03/15"`)
- Value: `"W1"` (most recent) to `"W12"` (oldest)
- Default: auto-select W1 (most recently completed week)
  - Last complete Sunday = last week's end
  - If today is Monday, last complete week ended yesterday (Sunday)

### `loadSTLData()` Behavior on Week Change

**Function**: `loadSTLData()` (lines 566-590)

- Read `module` and `week` from both selectors
- Use `MOCK_DATA.stlData[module].weeks[weekIndex]` to get per-week metrics
- Recalculate `target`, `actual`, `achievement`, `isMet` from selected week data
- Fall back to summary-level data if week not specified

---

## Change 2: Group Table `consecutiveWeeks` Column (STL-08)

### Current Table Columns (lines 202-211)

1. Group
2. Target
3. Actual
4. Achievement
5. Calls/Agent
6. Conn. Rate
7. PTP Rate
8. Attendance

### New Column Position

**Insert as column 2** (between Group and Target):

1. Group
2. **Consec. Weeks** ← NEW
3. Target
4. Actual
5. Achievement
6. Calls/Agent
7. Conn. Rate
8. PTP Rate
9. Attendance

**Header to insert**:
```html
<th style="padding: 12px; text-align: center; font-size: 12px; color: #64748b;">Consec. Weeks</th>
```

### Data Source

Use: `MOCK_DATA.groupPerformance[moduleId]` array

**All fields per group object** (schema section 6):
- `name` (String) — Group ID
- `consecutiveWeeks` (Number) — **Primary field for column + highlighting**
- `target` (Number) — Weekly target (PHP)
- `actual` (Number) — Actual weekly recovery (PHP)
- `achievement` (Number) — Achievement rate (%)
- `calls` (Number) — Avg calls per agent
- `connectRate` (Number) — Connection rate (%)
- `ptpRate` (Number) — PTP rate (%)
- `attendance` (Number) — Attendance rate (%)

---

## Change 3: Consecutive Weeks Highlight Logic (STL-09)

### Current (Wrong) Implementation

**Function**: `loadSTLGroupTable()` (lines 592-619)

**Problems**:
```javascript
const groups = Object.keys(MOCK_DATA.tlData);  // WRONG: uses TL data keys, not STL groups
const isUnmet = i < 2;                          // WRONG: hardcoded index, not data-driven
const target = 80000 + Math.random() * 40000;   // WRONG: random
// ... all other metrics random ...
<tr class="drilldown-row ${isUnmet ? 'red-row' : ''}">  // WRONG: no yellow, index-based
```

### Correct Logic

PRD STL-09: Red for 3+ weeks, yellow for 1-2 weeks.

```javascript
// Row class determination:
let rowClass = 'drilldown-row';
if (group.consecutiveWeeks >= 3) {
    rowClass += ' red-row';
} else if (group.consecutiveWeeks >= 1) {
    rowClass += ' yellow-row';
}
```

---

## Change 4: Empty State (STL-11)

### When to Show
Show when module selector value is `"all"` (default) or when `MOCK_DATA.groupPerformance[module]` is undefined.

### DOM Location
Insert inside `<div id="tab-STL">`, after the header card (after line ~187) and before the chart card.

**HTML to add**:
```html
<div id="stl-empty-state" class="card" style="display: none; text-align: center; padding: 40px;">
    <p style="font-size: 16px; color: #64748b; margin-bottom: 8px;">Please select a module to view weekly performance details.</p>
    <p style="font-size: 12px; color: #94a3b8;">Use the Module selector above to get started.</p>
</div>
```

### Show/Hide Logic in `loadSTLData()`

```javascript
if (module === 'all' || !MOCK_DATA.groupPerformance[module]) {
    document.getElementById('stl-empty-state').style.display = 'block';
    document.getElementById('stl-unmet-section').style.display = 'none';
    return;
} else {
    document.getElementById('stl-empty-state').style.display = 'none';
    // continue loading...
}
```

---

## Change 5: Group Performance Data Wiring

### Lines to Remove/Replace

All in `loadSTLGroupTable()` (lines 592-619):

```javascript
// REMOVE:
const groups = Object.keys(MOCK_DATA.tlData);  // wrong source
const isUnmet = i < 2;                          // wrong logic
const target = 80000 + Math.random() * 40000;   // random
const actual = isUnmet ? target * ...           // random
const calls = Math.floor(40 + Math.random() * 30);
const connectRate = (15 + Math.random() * 15).toFixed(1);
const ptpRate = (5 + Math.random() * 10).toFixed(1);
const attendance = Math.floor(80 + Math.random() * 20);

// REPLACE WITH:
const groups = MOCK_DATA.groupPerformance[module] || [];
// iterate: groups.forEach(group => { ... use group.target, group.actual, etc. })
```

### MOCK_DATA Addition Needed

`groupPerformance` key must be added to MOCK_DATA. Add entries for at minimum: `S1`, `M1`, `M2`.

Each group entry:
```javascript
{ name: 'G-S1-01', consecutiveWeeks: 0, target: 280000, actual: 295000, achievement: 105.4, calls: 52, connectRate: 21.2, ptpRate: 8.5, attendance: 94 }
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

- [ ] Add week selector HTML (`id="stl-week-select"`) after module selector
- [ ] `initSTLView()`: populate week selector with last 12 complete weeks + default to W1 (last complete week)
- [ ] `loadSTLData()`: read both module and week selectors; filter data by week
- [ ] Add `<div id="stl-empty-state">` HTML
- [ ] `loadSTLData()`: implement empty state show/hide logic
- [ ] Add `<th>Consec. Weeks</th>` header in group table (position 2)
- [ ] Add `.yellow-row` CSS class (if not already added by TL tab changes)
- [ ] Add `groupPerformance` to MOCK_DATA (all modules used)
- [ ] Rewrite `loadSTLGroupTable()`:
  - Use `MOCK_DATA.groupPerformance[module]`
  - Remove all `Math.random()` calls
  - Add `consecutiveWeeks` `<td>` cell in correct column position
  - Implement data-driven row class logic
- [ ] Test: empty state when "All Modules" selected
- [ ] Test: red row when consecutiveWeeks >= 3
- [ ] Test: yellow row when consecutiveWeeks = 1 or 2
- [ ] Test: no highlight when consecutiveWeeks = 0
- [ ] Test: week selector defaults to last complete week
