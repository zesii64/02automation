# 菲律宾催收指标数据提取与CSV生成

## 任务描述

从菲律宾催收指标邮件中提取"各模块指标"数据，生成标准格式的CSV数据。

## 数据格式规范

### CSV列结构


| 列名                    | 说明             | 示例                                               |
| --------------------- | -------------- | ------------------------------------------------ |
| product               | 产品类型           | cashloan, ttbnpl, lzd                                |
| module                | 模块名称           | S0, S1, S2, M1, S1_Large, S1_Small, T2, T4, T5 等 |
| target_repayment_rate | 目标回款率（小数，保留3位） | 0.505, 0.127                                     |
| month                 | 月份（yyyy-mm格式）  | 2025-01, 2026-02                                 |


### 产品映射规则


| 邮件中的产品   | CSV中的product |
| -------- | ------------ |
| Cashloan | cashloan     |
| TikTok   | ttbnpl       |
| Lazada   | lzd       |


### 模块命名规则

#### 1. 2025-01 至 2025-11（早期格式）

- Cashloan模块直接使用：`S0`, `S1`, `S2`, `M1`
- 不区分In-house/Outsourcing，不区分Large/Small
- TikTok模块使用：`T2`, `T4`, `T5`

#### 2. 2025-12 及之后（新格式）

**Cashloan模块：**

- **Outsourcing数据**（外包）：如果只有整个模块的目标，则生成两行
  - 第一行：不带后缀 `S0`, `S1`, `S2`, `M1`
  - 第二行：带`_Other`后缀 `S0_Other`, `S1_Other`, `S2_Other`, `M1_Other`
  - 两行数值相同
- **In-house数据**（内催）：
  - Large客户：`S1_Large`, `S2_Large`, `M1_Large`
  - Small客户：`S1_Small`, `S2_Small`, `M1_Small`
  - S0回款率：使用 `S0`（已在Outsourcing部分生成，In-house部分如单独出现则使用`S0`）

**TikTok模块（不变）：**

- 始终使用：`T2`, `T4`, `T5`

### 月份格式规则

1. 从邮件中的"By natural month"或"By due month"提取年月
2. 格式为：`YYYY-MM`（纯文本，**不带单引号**）
3. 月份映射：
  - 202501 → 2025-01

### 数值转换规则

1. 百分比转换为小数（如 50.5% → 0.505）
2. 保留3位小数
3. 不需要提取M2+后端催回金额（纯金额数据，非回款率）

## 数据提取步骤

### Step 1: 识别月份

- 查找邮件中的"By natural month"
- 提取格式如：202601
- 转换为：2026-01

### Step 2: 识别产品类型

- 查找"Cashloan各模块指标" → cashloan
- 查找"TikTok各模块指标" → ttbnpl
- 查找"Lazada各模块指标" → lzd
- 额外操作说明：如果出现之前没有的产品类型，询问我是否需要添加新产品。如果添加，则在此skill中更新指示。

### Step 3: 提取Cashloan模块数据

#### 判断时间格式：
- **2025-11及之前**：提取 S0, S1, S2, M1 四个模块，不区分Large/Small，每模块一行
- **2025-12及之后**：
  - Outsourcing部分：每个模块生成两行（带`_Other`后缀和不带后缀的），共8行
    - `S0` 和 `S0_Other`
    - `S1` 和 `S1_Other`
    - `S2` 和 `S2_Other`
    - `M1` 和 `M1_Other`
  - In-house部分：S1_Large, S1_Small, S2_Large, S2_Small, M1_Large, M1_Small


### Step 4: 提取TikTok模块数据
- 始终提取：T2, T4, T5
- 转换为小数，保留3位
- 每模块只生成一行

### Step 5: 生成CSV行
按以下顺序组织（2025-12及之后）：
1. Cashloan S0
2. Cashloan S0_Other
3. Cashloan S1
4. Cashloan S1_Other
5. Cashloan S2
6. Cashloan S2_Other
7. Cashloan M1
8. Cashloan M1_Other
9. Cashloan S1_Large
10. Cashloan S1_Small
11. Cashloan S2_Large
12. Cashloan S2_Small
13. Cashloan M1_Large
14. Cashloan M1_Small
15. ttbnpl T2
16. ttbnpl T4
17. ttbnpl T5


