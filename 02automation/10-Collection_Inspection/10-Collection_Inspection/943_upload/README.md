# 943 上传用 - 贷后数据巡检取数

本文件夹**整包上传到 943 平台**，在同一目录下执行下载脚本即可得到唯一 Excel（多 Sheet），方便您一次下载后做数据分析。

## 必传文件（取数用，缺一不可）

| 文件 | 用途 |
|------|------|
| vintage_risk.sql | 取 vintage 风险 → Sheet vintage_risk |
| natural_month_repay.sql | 取自然月回收率 → Sheet natural_month_repay |
| process_data.sql | 取过程数据 → Sheet process_data |
| download_collection_inspection_data.py | 依次执行上述 3 个 SQL，只输出一个 Excel、多 Sheet |

**聚合版（推荐，行数少、下载快）**：不下明细时使用 `--agg`，脚本会执行 `*_agg.sql`，产出同名 Sheet，报表无需改。

| 文件 | 用途 |
|------|------|
| vintage_risk_agg.sql | 09 表按 due_date+mob+user_type 聚合 |
| natural_month_repay_agg.sql | 自然月回收按 自然月+case_bucket+group_name+owner_id（催员维度）聚合 |
| process_data_agg.sql | 过程表按 月+owner_bucket+owner_group 聚合（去掉 owing_amount_alloc_bin） |

## 数据探查 SQL（可选，全面看每张表结构）

在 943 上**单独执行**（不参与下载脚本），用于看齐每张底表的字段与维度取值：

| 文件 | 用途 |
|------|------|
| **explore_all_tables_structure.sql** | **全表结构探查**：三张底表（09/vintage、回收、过程）的 DESC 说明 + 维度取值抽样 + 各维度基数，全面看齐每张表结构 |
| explore_data_profile.sql | 数据量级与行数估算，防下载卡死（上级目录另有副本） |
| explore_business_structure.sql | 组织与分层结构（group_name、case_bucket 等）（上级目录另有副本） |

建议先运行 **explore_all_tables_structure.sql** 各段（或先在控制台对三张表执行 `DESC 表名` 看元数据），再跑下载脚本。

## 在 943 上操作

1. 将本文件夹 `943_upload` 整个上传到 943。
2. 在该文件夹内执行（**建议加 `--agg` 下聚合数据，更快**）：
   ```bash
   python download_collection_inspection_data.py --agg
   ```
   不加 `--agg` 则下明细（行数多、易超 Excel 上限或卡顿）。
3. 得到 **collection_inspection_data_local.xlsx**（内含取数 3 Sheet + 数据探查若干 Sheet；探查结果便于带回后 Agent 读取）。
4. 将该 Excel 下载并放到本地项目目录 `10-Collection_Inspection` 下，然后运行 `run_daily_report.py` 生成带归因的日报。

— Mr. Yuan
