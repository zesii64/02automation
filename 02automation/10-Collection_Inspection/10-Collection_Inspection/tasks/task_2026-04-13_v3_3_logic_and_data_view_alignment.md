# 任务：v3.3 逻辑与 Data View 收口

task_id: task_2026-04-13_v3_3_logic_and_data_view_alignment
status: in_progress
owner: 未分配
created_at: 2026-04-13
updated_at: 2026-04-20

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
- 提交本轮增量修复（`generate_v2_7.py` + `Collection_Operations_Report_v3_3.html` + 状态文档）。
- 视需要推送到远端分支并发起后续评审。

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
