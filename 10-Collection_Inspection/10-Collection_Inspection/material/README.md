# material — 归因与业务看数材料

本文件夹存放**业务管理、归因分析、看数做分析**相关文件（如 checklist、归因模板、历史看板截图等），与 [WIKI/01_Business_Design.md](../WIKI/01_Business_Design.md) 中「业务归因逻辑」保持一致，便于对照与迭代。

## 读 Excel 约定

- 分析类 xlsx（如 `risk_management/250512_risk_analysis.xlsx`）：优先用 **`risk_management/read_risk_analysis_excel.py`** 查看 sheet 与表头；或在代码中 `pd.read_excel(..., engine="openpyxl")`，文件名建议英文。

**维护者**: Mr. Yuan
