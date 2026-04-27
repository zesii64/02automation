# 任务：v3.3 逻辑与 Data View 收口

task_id: task_2026-04-13_v3_3_logic_and_data_view_alignment
status: in_progress
owner: 未分配
created_at: 2026-04-13
updated_at: 2026-04-24

## 目标
- 收口 `Collection_Operations_Report_v3_3.html` 的判定口径、drilldown 展示与关键字段映射一致性。

## 约束
- 只维护 `v3_3` 主产物，不恢复 reference/bauhaus 产物输出。
- 遵守 `v2_7` 拆分边界：`generate_v2_7.py` 负责编排，view 文件负责 patch。
- 每次改动后必须执行最小编译/生成回归校验。

## 预检清单
- [x] 历史对话已提取关键结论（A/B/C 并行改造、二次修正、组维度 badge）。
- [x] 当前活跃脚本为 `05-scripts/generate_v2_7.py`。
- [x] 主产物路径确认：`reports/Collection_Operations_Report_v3_3.html`。
- [x] 现存风险已定位：TL 连接率字段映射仍存在旧字段优先问题。

## 状态
- 已完成 TL/STL selector 全联动的主逻辑修复（顶层 KPI、结论、表格、趋势图）。
- 人工交互抽检已通过，当前进入提交阶段。

## 证据
- 已落地：TL/STL drilldown 按 `achievement` 升序。
- 已落地：连续未达标文案中英文同步。
- 已落地：Data View 连续未达标按模块分段、催员 Recent 3 Days、组 Recent 2 Weeks。
- 已落地：TL badge 改为按“选中组 + 选中日期”判定。
- 已落地：仅保留 `v3_3` 主产物输出。
- 已落地：`agent_performance` 的 `connectRate` 映射改为优先 `connect_rate`，兼容 `call_connect_times/connect_times/call_billhr`。
- 已验证：`2026-04-09`、`2026-04-12` 在产物中 `agentPerformanceByDate.*.connectRate` 与源表 `connect_rate` 一致（归一化键后 0 mismatch）。
- 已验证：重新生成 `reports/Collection_Operations_Report_v3_3.html`，生成脚本 `Hard checks passed`。
- 已落地：TL 顶部 3 卡改为按 `tl-date-select` 的所选日期取值（不再固定默认日）。
- 已落地：TL recovery trend 按所选日期作为 cutoff（同月切换日期，曲线与数值同步变化）。
- 已落地：STL trend 文案改为按所选周动态计算；STL group 表在周切换时强制刷新。
- 已落地：STL recovery trend cutoff 改为 `min(所选周周末, dataDate)`，图表随周选择联动。
- 已验证：人工交互抽检通过（TL 日期切换、STL 周切换下 KPI/表格/图表联动一致）。

## 下一步动作
- 【P0/主回归】`python generate_v2_7.py` 用当前 `v3_5` 生成 `v3_6_*.html` 后做 TL/拆解/角色联动回归（见 `progress.json` 的 `next_actions`）。
- 按仓库习惯整理：代码与模板进版控、大报告与数据可忽略；清 `__tmp_*`；提交与推送策略自定。

## 交接说明
本卡功能与联动抽检已完成；接手时可直接执行提交/推送流程。

## 会话快照（2026-04-20）
- status: in_progress
- evidence:
  - 已并回 `v3_5` 关键能力到 `generate_v2_7.py`：today target / breakdown / 新 conclusion 格式。
  - 已修复 `v3_6` 页面点击异常（重复声明导致初始化中断）；自动化检查无 page error。
  - 已重生报告：`reports/Collection_Operations_Report_v3_6_2026-04-18.html`，人工检查通过。
- next_actions:
  - 业务侧再做 1 轮 TL/STL 关键路径抽检（角色切换、日期/周切换、结论联动）。
  - 确认稳定后更新 `release_gate` 并决定提交范围。
- handoff_note:
  - 当前主产物以 `v3_6` 为准；后续再改结论或 breakdown，必须做“页面可点击性回归 + 控制台无报错”检查。

## 会话快照（2026-04-22）
- status: completed
- evidence:
  - 模板 `generate_v2_7`：`REAL_DATA` 与 `// ROLE SWITCHING` 锚点改为正则可匹配；`v3_5` 自完整 v3_6 重建，可稳定全量生成。
  - 拆解：维度按钮 `onclick` 去掉错误 `\'`，补 `type="button"`；`tlBreakdownByDate` 全组键与模块级 `owner_group` 解析已落地；调试 `fetch` 埋点已清。
- next_actions: 以 `progress.json` 的 `next_actions` 为准（首条为【P0/主回归】，次条为 git/产物边界整理）。
- handoff_note: 新会话优先跑主回归与提交范围整理；`onclick` 勿再使用属性内 `\'`。

## 会话快照（2026-04-24）
- status: in_progress
- evidence:
  - 修复 HTML line 6857 toggleAgentOverviewModule SyntaxError：\\''' -> \\''
  - 修复 view_data.py line 686 锚点：'' -> \\''（避免下次生成复现）
  - 修复 HTML line 3763 重复代码（v3_6_2026-04-21.html base）
  - coarseModule 归一化（S1-Large -> S1）注入，doc-link 对 S1-Large A/S2-Small 等子模块生效
  - Jinja2 模板迁移已创建 scaffolding：tl_conclusions_renderer.py、templates/*.j2、data_contract.py（未接入 pipeline）
- next_actions:
  - 【P0】回归验证：打开 04-23 HTML，控制台确认无 JS 语法错误
  - 【P1】执行 python generate_v2_7.py 重新生成报告
  - 【P2】Git 提交
- blockers: []
- handoff_note: 04-23 HTML 已直接修复，view_data.py 锚点已修复，下次生成不会再出现同一问题。
