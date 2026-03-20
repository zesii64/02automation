# Collection Operations Report - Data Schema Specification

> **Version**: 1.2
> **Last Updated**: 2026-03-19
> **Purpose**: Define the JSON data format for the Collection Operations Report HTML
> **Changelog**: v1.2 — Added `days` array to `tlData` and `weeks` array to `stlData` for chart trend rendering

---

## Overview

The report uses a single JSON object (`REPORT_DATA`) that can be loaded from an external file or embedded directly. This schema defines all required data structures for the three main views: TL, STL, and Data.

---

## Data File Structure

```json
{
  "meta": { ... },
  "modules": [ ... ],
  "groups": [ ... ],
  "agents": [ ... ],
  "tlData": { ... },
  "stlData": { ... },
  "agentPerformance": { ... },
  "groupPerformance": { ... },
  "anomalyData": [ ... ],
  "riskModules": [ ... ],
  "riskModuleGroups": { ... },
  "moduleDailyTrends": { ... }
}
```

---

## 1. Meta Information

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `reportDate` | String | Yes | Report generation date (YYYY-MM-DD) |
| `dataDate` | String | Yes | Data snapshot date (YYYY-MM-DD) |
| `version` | String | Yes | Report version |

```json
"meta": {
  "reportDate": "2026-03-18",
  "dataDate": "2026-03-17",
  "version": "1.1"
}
```

---

## 2. Dimension Lists

### 2.1 Modules

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `modules` | Array[String] | Yes | List of all module codes (e.g., S0, S1, S2, M1, M2, T2, T4, T5) |

```json
"modules": ["S0", "S1", "S2", "M1", "M2", "T2", "T4", "T5"]
```

### 2.2 Groups

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `groups` | Array[String] | Yes | List of all group IDs |

```json
"groups": ["G-S1-01", "G-S1-02", "G-M1-01", "G-M2-01"]
```

### 2.3 Agents

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agents` | Array[String] | Yes | List of all agent IDs |

```json
"agents": ["A001", "A002", "A003", "A004", "A005"]
```

---

## 3. TL Data (Daily Group Metrics)

**Key**: Group ID (e.g., "G-S1-01")

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | Number | Yes | Daily recovery target (PHP) for the selected date |
| `actual` | Number | Yes | Actual daily recovery (PHP) for the selected date |
| `achievement` | Number | Yes | Achievement rate (%) = actual/target * 100 |
| `moduleAvg` | Number | Yes | Module average achievement rate (%) |
| `gap` | Number | Yes | Gap to target (PHP) = target - actual |
| `callGap` | Number | Yes | Call volume gap vs target |
| `connectGap` | Number | Yes | Connect rate gap vs target (%) |
| `days` | Array | Yes | Daily trend data for chart (last 30 days) — see Daily Entry below |

### TL Daily Entry (inside `days` array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `date` | String | Yes | Date (YYYY-MM-DD) |
| `target` | Number | Yes | Daily target for that date (PHP) |
| `actual` | Number | Yes | Actual recovery for that date (PHP) |

```json
"tlData": {
  "G-S1-01": {
    "target": 125000,
    "actual": 118500,
    "achievement": 94.8,
    "moduleAvg": 96.2,
    "gap": 6500,
    "callGap": -12,
    "connectGap": -2.3,
    "days": [
      { "date": "2026-03-01", "target": 120000, "actual": 115000 },
      { "date": "2026-03-02", "target": 122000, "actual": 130000 }
    ]
  }
}
```

---

## 4. STL Data (Weekly Module Metrics)

**Key**: Module code (e.g., "S1", "M1")

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | Number | Yes | Weekly recovery target (PHP) for the selected week |
| `actual` | Number | Yes | Actual weekly recovery (PHP) for the selected week |
| `achievement` | Number | Yes | Achievement rate (%) |
| `lastWeek` | Number | Yes | Last week's actual (PHP) |
| `trend` | String | Yes | Week-over-week change (e.g., "+4.4%") |
| `gap` | Number | Yes | Gap to target (PHP) |
| `weeks` | Array | Yes | Weekly trend data for chart (last 12 weeks) — see Weekly Entry below |

### STL Weekly Entry (inside `weeks` array)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `week` | String | Yes | Week label (e.g., "W1", "W2") |
| `weekLabel` | String | Yes | Human-readable date range (e.g., "03/01-03/07") |
| `target` | Number | Yes | Weekly target for that week (PHP) |
| `actual` | Number | Yes | Actual recovery for that week (PHP) |

```json
"stlData": {
  "S1": {
    "target": 850000,
    "actual": 798500,
    "achievement": 93.9,
    "lastWeek": 765000,
    "trend": "+4.4%",
    "gap": 51500,
    "weeks": [
      { "week": "W1", "weekLabel": "02/09-02/15", "target": 850000, "actual": 780000 },
      { "week": "W2", "weekLabel": "02/16-02/22", "target": 850000, "actual": 798500 }
    ]
  }
}
```

---

## 5. Agent Performance (For TL Drill-down)

**Key**: Group ID → Array of Agent objects

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | String | Yes | Agent ID |
| `consecutiveDays` | Number | Yes | Consecutive days below target |
| `target` | Number | Yes | Daily target (PHP) |
| `actual` | Number | Yes | Actual recovery (PHP) |
| `achievement` | Number | Yes | Achievement rate (%) |
| `calls` | Number | Yes | Total calls made |
| `connectRate` | Number | Yes | Connection rate (%) |
| `ptp` | Number | Yes | PTP (Promise to Pay) rate (%) |
| `attendance` | Number | Yes | Attendance rate (%) |

```json
"agentPerformance": {
  "G-S1-01": [
    {
      "name": "A001",
      "consecutiveDays": 0,
      "target": 25000,
      "actual": 26500,
      "achievement": 106.0,
      "calls": 52,
      "connectRate": 22.5,
      "ptp": 8.2,
      "attendance": 95
    }
  ]
}
```

---

## 6. Group Performance (For STL Drill-down)

**Key**: Module code → Array of Group objects

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | String | Yes | Group ID |
| `consecutiveWeeks` | Number | Yes | Consecutive weeks below target |
| `target` | Number | Yes | Weekly target (PHP) |
| `actual` | Number | Yes | Actual weekly recovery (PHP) |
| `achievement` | Number | Yes | Achievement rate (%) |
| `calls` | Number | Yes | Average calls per agent |
| `connectRate` | Number | Yes | Connection rate (%) |
| `ptpRate` | Number | Yes | PTP rate (%) |
| `attendance` | Number | Yes | Attendance rate (%) |

```json
"groupPerformance": {
  "S1": [
    {
      "name": "G-S1-01",
      "consecutiveWeeks": 0,
      "target": 280000,
      "actual": 295000,
      "achievement": 105.4,
      "calls": 52,
      "connectRate": 21.2,
      "ptpRate": 8.5,
      "attendance": 94
    }
  ]
}
```

---

## 7. Anomaly Data (For Data Tab - Anomaly Detection)

Array of objects with:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | String | Yes | "Agent" or "Group" |
| `name` | String | Yes | Agent/Group ID |
| `module` | String | Yes | Associated module |
| `days` | Number | Yes | Consecutive days below target |
| `target` | Number | Yes | Target amount (PHP) |
| `actual` | Number | Yes | Actual amount (PHP) |
| `gap` | Number | Yes | Gap amount (PHP) |

```json
"anomalyData": [
  {
    "type": "Agent",
    "name": "A003",
    "module": "M1",
    "days": 5,
    "target": 8500,
    "actual": 6800,
    "gap": 1700
  }
]
```

---

## 8. Risk Modules

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `riskModules` | Array[String] | Yes | List of modules at risk of missing monthly target |

```json
"riskModules": ["M2", "T2"]
```

---

## 9. Risk Module Groups (For Data Tab - Risk Review)

**Key**: Module code → Array of Group objects (same structure as Group Performance)

```json
"riskModuleGroups": {
  "M2": [
    {
      "group": "G-M2-01",
      "target": 45000,
      "actual": 34200,
      "achievement": 76.0,
      "calls": 45,
      "connectRate": 18.5,
      "ptpRate": 8.2,
      "attendance": 88
    }
  ]
}
```

---

## 10. Module Daily Trends (For Data Tab - Recovery Trend)

**Key**: Module code → Object with daily trend data

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | Number | Yes | Daily target (PHP) |
| `daily` | Array | Yes | Array of daily actual values |

### Daily Data Structure

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `date` | String | Yes | Date (YYYY-MM-DD) |
| `actual` | Number | Yes | Actual recovery (PHP) |

```json
"moduleDailyTrends": {
  "S1": {
    "target": 100000,
    "daily": [
      { "date": "2026-03-01", "actual": 95000 },
      { "date": "2026-03-02", "actual": 102000 }
    ]
  }
}
```

---

## Complete Example

```json
{
  "meta": {
    "reportDate": "2026-03-18",
    "dataDate": "2026-03-17",
    "version": "1.1"
  },
  "modules": ["S0", "S1", "S2", "M1", "M2", "T2", "T4", "T5"],
  "groups": ["G-S1-01", "G-S1-02", "G-M1-01", "G-M2-01"],
  "agents": ["A001", "A002", "A003", "A004", "A005"],
  "tlData": {
    "G-S1-01": {
      "target": 125000,
      "actual": 118500,
      "achievement": 94.8,
      "moduleAvg": 96.2,
      "gap": 6500,
      "callGap": -12,
      "connectGap": -2.3,
      "days": [
        { "date": "2026-03-01", "target": 120000, "actual": 115000 },
        { "date": "2026-03-02", "target": 122000, "actual": 130000 }
      ]
    }
  },
  "stlData": {
    "S1": {
      "target": 850000,
      "actual": 798500,
      "achievement": 93.9,
      "lastWeek": 765000,
      "trend": "+4.4%",
      "gap": 51500,
      "weeks": [
        { "week": "W1", "weekLabel": "02/09-02/15", "target": 850000, "actual": 780000 },
        { "week": "W2", "weekLabel": "02/16-02/22", "target": 850000, "actual": 798500 }
      ]
    }
  },
  "agentPerformance": {
    "G-S1-01": [
      {
        "name": "A001",
        "consecutiveDays": 0,
        "target": 25000,
        "actual": 26500,
        "achievement": 106.0,
        "calls": 52,
        "connectRate": 22.5,
        "ptp": 8.2,
        "attendance": 95
      }
    ]
  },
  "groupPerformance": {
    "S1": [
      {
        "name": "G-S1-01",
        "consecutiveWeeks": 0,
        "target": 280000,
        "actual": 295000,
        "achievement": 105.4,
        "calls": 52,
        "connectRate": 21.2,
        "ptpRate": 8.5,
        "attendance": 94
      }
    ]
  },
  "anomalyData": [
    {
      "type": "Agent",
      "name": "A003",
      "module": "M1",
      "days": 5,
      "target": 8500,
      "actual": 6800,
      "gap": 1700
    }
  ],
  "riskModules": ["M2", "T2"],
  "riskModuleGroups": {
    "M2": [
      {
        "group": "G-M2-01",
        "target": 45000,
        "actual": 34200,
        "achievement": 76.0,
        "calls": 45,
        "connectRate": 18.5,
        "ptpRate": 8.2,
        "attendance": 88
      }
    ]
  },
  "moduleDailyTrends": {
    "S1": {
      "target": 100000,
      "daily": [
        { "date": "2026-03-01", "actual": 95000 }
      ]
    }
  }
}
```

---

## Integration Guide

### Option 1: Embedded Data

Replace the `MOCK_DATA` constant in the HTML with:

```javascript
const REPORT_DATA = { ... }; // Your data here
const MOCK_DATA = REPORT_DATA;
```

### Option 2: External JSON File

```javascript
fetch('data/collection_report_data.json')
  .then(res => res.json())
  .then(data => {
    window.REPORT_DATA = data;
    initReport();
  });
```

### Option 3: Excel/CSV Import

Convert Excel data to JSON using a separate script, then load into the report.

---

**Last Updated**: 2026-03-19
