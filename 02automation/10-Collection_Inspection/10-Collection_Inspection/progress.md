# 进度看板

last_updated: 2026-04-13
active_task: none
owner: 未分配
status: done

## 当前焦点
- TL/STL selector 全联动修复已完成并通过人工抽检，进入提交流程。

## 本次保存已完成
- 已完成 `v2_7` 拆分协作落地（`generate_v2_7.py` / `view_tl_stl.py` / `view_data.py`）。
- 已实现 TL/STL drilldown 按 `achievement` 升序展示。
- 已完成连续未达标文案中英文同步（含中文映射）。
- 已完成 Data View 连续未达标重构（按模块分段 + 催员 Recent 3 Days）。
- 已完成 Data View 组维度 Recent 2 Weeks drilldown。
- 已切换 TL badge 为组维度判定（按选中组 + 选中日期）。
- 已修复 TL `connectRate` 字段映射（优先 `connect_rate`，兼容 `call_connect_times/connect_times/call_billhr`）。
- 已完成关键日期点验（`2026-04-09`、`2026-04-12`）并确认产物与源表一致。
- 已重新生成唯一产物 `reports/Collection_Operations_Report_v3_3.html`，脚本硬校验通过。
- 已完成 TL 顶部 3 卡按 `selectedDate` 联动改造（target/actual/achievement）。
- 已完成 TL 趋势图 cutoff 按所选日期联动（不再固定 `dataDate`）。
- 已完成 STL trend 文案按所选周动态计算，并确保 group 表在周切换时刷新。
- 已完成 STL 趋势图 cutoff 改为 `min(week_end, dataDate)`。
- 已完成人工交互抽检：TL 日期与 STL 周切换下，KPI/表格/图表联动一致。

## 下一步动作
- 提交本轮增量修复并更新分支状态。
- 视需要推送远端并发起评审。

## 阻塞项
- 无（当前为逻辑收口阶段）。

## 待确认问题
- 无（等待人工交互抽检结论）。

## 交接提示词
先阅读 `code/agent_handoff_v2_7.md` 与 `tasks/task_2026-04-13_v3_3_logic_and_data_view_alignment.md`，优先执行 `next_actions[0]`。改动后必须进行 `py_compile` 与 `v3_3` 产物回归核验。

## 当前任务
- [completed] `tasks/task_2026-04-13_v3_3_logic_and_data_view_alignment.md`
