# 技术架构 (Technical Architecture)

> **定位**: 系统设计文档，供开发维护参考。  
> **维护者**: Mr. Yuan

---

## 一、数据流 (Data Flow)

```mermaid
graph LR
    ODPS[ODPS Data Warehouse] --SQL Extract--> Pandas[Python Pandas DataFrame]
    Pandas --To Excel--> Excel[Local Excel File]
    Excel --Read--> ReportScript[run_cashloan_report.py]
    ReportScript --Render--> HTML[HTML Report]
```

## 二、核心组件

### 1. 取数层 (Extraction)
- **策略**: 聚合取数 (Aggregation First)。
- **脚本**: `download_agg_only.py`
- **SQL**:
    - `vintage_risk_agg.sql`: 按 `due_date + mob + user_type + model_bin` 聚合。
    - `process_data_agg.sql`: 按 `month + bucket + group` 聚合，保留 `raw_*` 分子分母供计算。
    - `natural_month_repay_agg.sql`: 按 `month + bucket + group` 聚合。

### 2. 计算层 (Computation)
- **脚本**: `run_cashloan_report.py` (继承 `run_daily_report.py` 的部分逻辑)
- **核心逻辑**:
    - **Asset Quality**: 计算 GroupBy Model Bin 的 Overdue Rate。
    - **Strategy**: 计算 Coverage (1 - uncomm/total), Connect Rate, Intensity。
    - **Outcome**: 计算 Repay Rate 并提取 Bottom 3 Segments。

### 3. 展示层 (Presentation)
- **技术**: Python f-string 生成 HTML + Tailwind CSS (CDN)。
- **特点**: 响应式布局、KPI 卡片、颜色编码 (Brand/Accent/Danger)。

---

## 三、数据流与三条线 / 日报章节对应

| 三条线（业务口径） | 取数 SQL / Sheet | 计算逻辑（run_daily_report） | 日报章节（02_Report_Spec） |
|--------------------|------------------|------------------------------|---------------------------|
| **风险口径** | vintage_risk_agg.sql → Sheet `vintage_risk` | compute_vintage_summary, compute_due_trend | 一、资产质量（Due 趋势 + Overall + Model Bin） |
| **回收口径** | natural_month_repay_agg.sql → Sheet `natural_month_repay` | compute_repay_summary | 三、回收结果（回收率 + 归因最差段） |
| **过程口径** | process_data_agg.sql → Sheet `process_data` | compute_process_summary | 二、策略执行（覆盖率、接通率、强度） |
| **异常** | 由上三层结果派生 | vintage/repay 的 anomaly 列表 | 四、异常数据检查 |

---

## 四、脚本职责

| 脚本 / 模块 | 职责 |
|-------------|------|
| **download_agg_only.py** | 在 943 上执行三个 *_agg.sql，将结果写入 Excel 各 Sheet（vintage_risk / natural_month_repay / process_data），支持大表分 Sheet 写入。 |
| **run_daily_report.py** | 计算层核心：compute_vintage_summary（含 Overall/Model Bin）、compute_due_trend（按 due_date）、compute_repay_summary、compute_process_summary；产出 anomaly 列表；含通用 find_excel / read_sheet / read_sheet_maybe_chunked。 |
| **run_cashloan_report.py** | 读 Excel 三 Sheet，调用 run_daily_report 的 compute_* 与 _compute_* 封装；组装 KPI、四节内容与 Due 趋势表；build_cashloan_html 生成 HTML；main 中 find_excel → 读表 → 计算 → 写 reports/ 下 HTML。 |

---

## 五、文件依赖

- `collection_inspection_data_local.xlsx`: 必须包含 `vintage_risk`, `natural_month_repay`, `process_data` 三个 Sheet。
- `data/`: 默认数据存放目录。
- `reports/`: 默认报告输出目录。

---

## 六、支撑本项目的 SQL 与脚本清单（准备用）

为支撑当前巡检项目（聚合取数 → 本地 Excel → 日报 HTML），需要准备以下内容。**943 上传用**时，可将本目录下对应 SQL 与 `download_agg_only.py` 拷贝到 `943_upload/` 同目录后执行。

### 必须的 SQL（3 个，由 download_agg_only 按顺序执行）

| 文件名 | 用途 | 产出 Excel Sheet |
|--------|------|------------------|
| `vintage_risk_agg.sql` | 风险口径聚合：due_date + mob + user_type + model_bin + **period_no + flag_principal**，含 DPD5/15/30 及接通/PTP 转化率 | `vintage_risk` |
| `natural_month_repay_agg.sql` | 回收口径聚合：自然月 + bucket + group，回收分子分母 | `natural_month_repay` |
| `process_data_agg.sql` | 过程口径聚合：月 + bucket + group，raw_* 拨打/接通/案量供算覆盖率/接通率/强度 | `process_data` |

### 必须的脚本（2 个核心 + 1 个入口）

| 脚本 | 使用场景 | 作用 |
|------|----------|------|
| `download_agg_only.py` | **943 上** | 执行上述 3 个 SQL，写出 `collection_inspection_data_local.xlsx`（三 Sheet，大表自动分 Sheet） |
| `run_daily_report.py` | **本地**（被 run_cashloan_report 调用） | 计算层：vintage/repay/process 汇总与 due 趋势、异常列表 |
| `run_cashloan_report.py` | **本地** | 读 Excel → 调 run_daily_report 计算 → 生成 `reports/CashLoan_Inspection_Report_YYYY-MM-DD.html` |

### 可选

| 文件 | 说明 |
|------|------|
| `run_report.bat` | Windows 一键运行 run_cashloan_report.py（可指定 chcp 65001 防乱码） |
| `943_upload/` 下同名 SQL + download_agg_only.py | 与根目录保持一致，便于整包上传 943 后直接运行 |

### 小结

- **要跑的 SQL**：仅上述 **3 个 \*_agg.sql**（聚合版）；非 agg 的明细 SQL 不参与当前日报流水线。
- **要用的脚本**：**943 上**用 `download_agg_only.py` 取数；**本地**用 `run_cashloan_report.py` 出报（依赖同目录 `run_daily_report.py`）。

---

**Last Updated**: 2026-01-28  
**维护者**：Mr. Yuan
