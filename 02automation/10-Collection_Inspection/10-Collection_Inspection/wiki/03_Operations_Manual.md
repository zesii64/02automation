# 03_Operations_Manual (操作手册)

> **文档说明**：本手册指导用户如何在 943 环境取数、在本地环境生成巡检日报，以及如何排查常见问题。  
> **维护者**：Mr. Yuan

---

## 一、系统架构简述

本巡检系统采用 **"云端取数 + 本地分析"** 的架构，核心是一个 Python 脚本 `run_inspection_all_in_one.py`：

1.  **取数 (943 Server)**：连接 ODPS 计算引擎，执行 SQL (Vintage/Repay/Process)，将结果下载为 Excel。
2.  **分析 (Local PC)**：读取 Excel，进行指标计算、同环比分析、异常检测，生成 HTML 报告。

---

## 二、运行步骤 (SOP)

### 第一步：在 943 环境取数 (Download)

**适用场景**：每天早上，需要获取最新 T-1 数据。

1.  **登录 Jupyter/Terminal**：进入 943 数据平台。
2.  **上传/定位脚本**：确保 `run_inspection_all_in_one.py` 在你的目录下。
3.  **运行脚本**：
    ```bash
    # 方式 A：命令行运行
    python run_inspection_all_in_one.py --mode download
    
    # 方式 B：Jupyter Notebook 中运行
    # 新建一个 Cell，输入以下代码并运行：
    %run run_inspection_all_in_one.py --mode download
    ```
4.  **获取结果**：
    脚本运行成功后，会生成 `collection_inspection_data_local.xlsx`。
    请将此文件**下载**到你本地电脑的 `10-Collection_Inspection/data/` 目录下。

### 第二步：在本地生成报告 (Report)

**适用场景**：拿到数据后，生成可视化 HTML 报告。

1.  **准备数据**：确保 `collection_inspection_data_local.xlsx` 已放入 `data/` 文件夹（或脚本同级目录）。
2.  **运行脚本**：
    打开 CMD 或 PowerShell，进入项目目录：
    ```powershell
    cd d:\0_phirisk\12-agent_finalize\10-Collection_Inspection
    python run_inspection_all_in_one.py --mode report --no-pause
    ```
3.  **查看报告**：
    报告会自动生成在 `reports/` 目录下，文件名格式为 `CashLoan_Inspection_Report_YYYY-MM-DD.html`。
    **双击直接用浏览器打开即可。**

---

## 三、如何解读报告 (核心业务逻辑)

### 1. 警惕“表现期滞后” (Maturity Lag)
**这是解读报告最大的坑！** 请务必注意：

*   **DPD 指标看账龄**：
    *   **DPD5** 需要逾期 5 天才能看到。
    *   如果 Due Date 是昨天或前天，DPD5 **必然是 0**。这不代表质量好，只是**还没熟**。
    *   **原则**：最近 3-5 天的数据，只看 **入催率 (Overdue Rate)**；不要看 DPD5/DPD30。

*   **同环比 (WoW) 的假象**：
    *   报告中如果显示 DPD5 <span style="color:green">↓ 75%</span>（绿色下降），往往是因为“本周数据没熟” vs “上周数据熟了”。
    *   **判读标准**：重点关注 **入催率 (Overdue Rate)** 的红色箭头 <span style="color:red">↑</span>。入催率是一天就能看出的，最准。

### 2. 归因顺序
报告设计遵循 **"先看趋势，再看拆解"**：
1.  先看 **Due Trend**：哪天开始恶化？是突然跳变还是缓慢爬坡？
2.  再看 **Breakdown**：
    *   **新老客**：通常新客风险 > 老客。如果老客突然飙升，可能是存量清洗出问题。
    *   **模型分箱**：A -> H 逾期率应递增。如果 **H < G** (倒挂)，说明模型或策略有大问题。

---

## 四、常见问题排查 (Troubleshooting)

### Q1: 运行 --mode download 报错 "ODPS object not found"
*   **原因**：脚本没找到 ODPS 入口。
*   **解法**：
    *   如果是 Notebook，确保你已经运行了 ODPS 初始化代码（通常平台会自动注入 `o` 对象）。
    *   如果是本地/纯脚本，需要配置 `ODPS_ACCESS_ID` 等环境变量（见脚本头部注释）。

### Q2: 运行 --mode report 报错 "File not found"
*   **原因**：脚本找不到 Excel 数据文件。
*   **解法**：
    *   确保文件名完全一致：`collection_inspection_data_local.xlsx`。
    *   确保文件放在 `data/` 目录下，或者和脚本在同一级目录。

### Q3: 报告里的中文是乱码
*   **原因**：Windows PowerShell 编码问题。
*   **解法**：
    *   脚本已内置 `sys.stdout.reconfigure(encoding='utf-8')` 处理。
    *   如果仍有乱码，尝试在运行前执行 `chcp 65001`。
    *   **注意**：这只影响控制台打印，**不影响 HTML 报告内容**（HTML 强制 UTF-8）。

---

**Last Updated**: 2026-02-04
