# 任务：v3.3 逻辑与 Data View 收口

task_id: task_2026-04-13_v3_3_logic_and_data_view_alignment
status: done
owner: 未分配
created_at: 2026-04-13
updated_at: 2026-04-13

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
- 已完成 `connectRate` 映射收口与关键日期回归。
- `v3_3` 主产物已重新生成并通过内置校验。

## 证据
- 已落地：TL/STL drilldown 按 `achievement` 升序。
- 已落地：连续未达标文案中英文同步。
- 已落地：Data View 连续未达标按模块分段、催员 Recent 3 Days、组 Recent 2 Weeks。
- 已落地：TL badge 改为按“选中组 + 选中日期”判定。
- 已落地：仅保留 `v3_3` 主产物输出。
- 已落地：`agent_performance` 的 `connectRate` 映射改为优先 `connect_rate`，兼容 `call_connect_times/connect_times/call_billhr`。
- 已验证：`2026-04-09`、`2026-04-12` 在产物中 `agentPerformanceByDate.*.connectRate` 与源表 `connect_rate` 一致（归一化键后 0 mismatch）。
- 已验证：重新生成 `reports/Collection_Operations_Report_v3_3.html`，生成脚本 `Hard checks passed`。

## 下一步动作
- 人工点开 `reports/Collection_Operations_Report_v3_3.html`，进行页面交互抽检（TL 日期切换、STL 周切换、Data View drilldown）。
- 若抽检通过，进入提交阶段（按仓库规范整理 commit message）。

## 交接说明
本卡技术收口已完成；如继续推进，优先执行人工交互抽检，再进行提交。
