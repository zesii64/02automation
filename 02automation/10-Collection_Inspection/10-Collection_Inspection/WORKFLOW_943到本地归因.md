# 943 → 本地归因：完整操作说明

> 目标：在 943 上取数 → 拿到 Excel → 本地跑脚本 → 自动出带归因的日报。

---

## 一、需要传到 943 上的文件

**只需上传一个文件夹**：`10-Collection_Inspection/943_upload/`

该文件夹内已包含取数用全部文件（缺一不可）：

| 文件名 | 用途 |
|--------|------|
| `vintage_risk.sql` | 取 vintage 风险数据 → 写入 Sheet `vintage_risk` |
| `natural_month_repay.sql` | 取自然月回收率（已去掉 data_level 限制）→ 写入 Sheet `natural_month_repay` |
| `process_data.sql` | 取过程数据 → 写入 Sheet `process_data` |
| `download_collection_inspection_data.py` | 依次执行上述 3 个 SQL，**只输出一个 Excel、多个 Sheet** |

**可选（仅探查用，不参与下载脚本）**：探查用 SQL 在上级目录 `10-Collection_Inspection` 下（如 `explore_business_structure.sql`），需单独跑时再拷贝到 943。

---

## 二、在 943 上执行什么

1. **把 `943_upload` 整个文件夹上传到 943**（保证 3 个 SQL 与下载脚本在同一目录）。
2. **在 943 上进入该文件夹并执行：**
   ```bash
   python download_collection_inspection_data.py
   ```
   （如需指定输出路径：`python download_collection_inspection_data.py --output collection_inspection_data_local.xlsx --dir /你的输出目录`）
3. **脚本会依次执行** `vintage_risk.sql`、`natural_month_repay.sql`、`process_data.sql`，把结果写入同一个 Excel 的 3 个 Sheet。

---

## 三、你需要“返回”什么

- **文件名**：`collection_inspection_data_local.xlsx`
- **内容**：同一 Excel 内包含  
  - **取数 3 Sheet**：`vintage_risk`、`natural_month_repay`、`process_data`  
  - **数据探查若干 Sheet**：`explore_09_dims`、`explore_09_region`、`explore_09_cnt`、`explore_repay_dims`、`explore_repay_datalvl`、`explore_process_dims`、`explore_process_cnt`（脚本自动执行探查 SQL 并写入，便于带回后 Agent 读取并做维度映射）
- 把该 Excel 拷到本地项目目录：  
  `d:\0_phirisk\12-agent_finalize\10-Collection_Inspection\`

---

## 四、本地如何开始自动归因

1. **确认 Excel 已放在** `10-Collection_Inspection` 目录下，且名为 `collection_inspection_data_local.xlsx`。
2. **在本机该目录下执行：**
   ```bash
   python run_daily_report.py
   ```
3. **产出**：  
   - 报告路径：`10-Collection_Inspection\reports\Inspection_Report_YYYY-MM-DD.html`  
   - 报告内容：风险概况 + 分产品 + **分批次回收（含自动归因：表现最差的 3 个 group/bucket）** + 异常与建议。

---

## 五、小结

| 步骤 | 在哪里做 | 做什么 | 得到什么 |
|------|----------|--------|----------|
| 1 | 943 | 上传 `943_upload` 文件夹 + 在该文件夹内运行 `download_collection_inspection_data.py` | 唯一 Excel：`collection_inspection_data_local.xlsx`（3 个 Sheet） |
| 2 | 本机 | 把该 Excel 放到 `10-Collection_Inspection` 下 | 数据就位 |
| 3 | 本机 | 运行 `python run_daily_report.py` | `reports/Inspection_Report_YYYY-MM-DD.html`（含自动归因） |

**SQL 变更说明**：  
- `natural_month_repay.sql` 与 `explore_business_structure.sql` 中已**不再限制** `data_level = '5.经办层级'`，如需限制可自行加回该条件。  
- Process 探查查询已改为用底表原始字段（如 `owing_case_cnt`、`call_times`）聚合，避免引用不存在的列，适配 ODPS 语法。

— Mr. Yuan
