# 贷后数据巡检 (Collection Inspection)

> **Strategic Monitoring System v2.0**

This project has been upgraded to a comprehensive strategic monitoring system.

## 📚 Documentation

All project documentation, including Business Design, Architecture, and Operations Manual, has been moved to the **Wiki**.

- **[Project Dashboard (HTML)](WIKI/index.html)** - Recommended Entry Point
- **[Wiki Home (Markdown)](WIKI/00_Home.md)**

## 🚀 Quick Start

1.  **Download Data**: See [Operations Manual](WIKI/03_Operations_Manual.md).
2.  **Run Report**:
    ```bash
    python run_cashloan_report.py
    ```

---

## 读 Excel 约定 (Reading Excel in This Project)

- **数据源 Excel**（如 `collection_inspection_data_local.xlsx`）：用 **pandas** 读取，`pd.read_excel(path, sheet_name=..., engine="openpyxl")`；多 sheet 或分片见 `run_cashloan_report.py` / `run_daily_report.py` 中的 `read_sheet`、`read_sheet_maybe_chunked`。
- **分析材料 Excel**（如 `material/risk_management/250512_risk_analysis.xlsx`）：用同目录脚本 **`material/risk_management/read_risk_analysis_excel.py`** 查看 sheet 名与表头；或在代码中 `pd.read_excel(..., engine="openpyxl")`，文件名建议英文避免路径问题。

**读 Excel 对本项目的帮助**：  
- 数据源 Excel：直接驱动日报/周报（vintage_risk、natural_month_repay、process_data），无则无法出报。  
- 分析材料 Excel：对齐「先 due 趋势再拆解」、各业务线结论与维度，用于校准报表结构、异常规则和归因表述，避免巡检与业务分析脱节。

---

*Maintainer: Mr. Yuan*
