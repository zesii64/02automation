# 任务：v3.3 逻辑与 Data View 收口

task_id: task_2026-04-13_v3_3_logic_and_data_view_alignment
status: in_progress
owner: 未分配
created_at: 2026-04-13
updated_at: 2026-04-27

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

## 基线模板剥离计划（2026-04-29 新增）

**目标**：从 `reports/Collection_Operations_Report_v3_6_2026-04-21.html` 逆向剥离所有补丁产物，生成 `templates/Collection_Operations_Report_base.html`，作为 `generate_v2_7.py` 的纯净输入。

**根因**：脚本补丁逻辑不具备幂等性。`HTML_IN` 使用旧报告作为模板，旧报告已包含上轮补丁产物，导致每次运行重复叠加。

**剥离清单**（保留 `old` 锚点，删除 `new` 追加部分）：

| # | 位置 | 补丁来源 | 需剥离内容 | 保留的锚点 |
|---|------|---------|-----------|-----------|
| 1 | Data View subtab | `view_data.py` | `subtab-agent-overview` 按钮 ×1 | `subtab-trend` 按钮 |
| 2 | Data View 内容块 | `view_data.py` | `<div id="data-agent-overview">` 整个块 ×1 | `<!-- Recovery Trend Sub-tab -->` |
| 3 | TL View unmet | `generate_v2_7.py` | `tl-gap-meta`、`tl-call-gap-meta`、`tl-connect-gap-meta` 子行 ×3 | `tl-gap-amount` + `Gap to Target` |
| 4 | TL View unmet | `generate_v2_7.py` | `tl-unmet-attendance` 行 ×1 | `Unmet Target — Detail Review` heading |
| 5 | STL View unmet | `generate_v2_7.py` | 3-card grid（Gap/Call/Billmin）×1 | heading + legend |

**验证标准**：
- 剥离后 `grep` 确认：模板中无 `subtab-agent-overview`、`data-agent-overview`、`tl-gap-meta`、`stl-gap-meta`
- 脚本重新运行后：上述元素恰好各出现1次，无重复

**关联修改**：
- `05-scripts/generate_v2_7.py` line 80：`HTML_IN = BASE + r'/templates/Collection_Operations_Report_base.html'`

## 交接说明
本卡功能与联动抽检已完成；接手时可直接执行提交/推送流程。
当前新增基线模板剥离任务，见上方计划。

## 会话快照（2026-04-29）
- status: in_progress
- current_focus: 报告模板重复模块清理与基线模板制作（方案A）
- recent_completed: 阶段一（4-21模板去重）、根因定位、方案评估
- next_actions: 执行剥离计划 → 修改 HTML_IN → 重新生成验证
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

## 会话快照（2026-04-27）
- status: in_progress
- evidence:
  - force push 完成（c727f32 优化html生成逻辑，目前以v3_6-4-21为模板）
  - force push 后发现 generate_v2_7.py、patch_utils.py、view_tl_stl.py、tl_conclusions_renderer.py、templates/、data_contract.py 等核心文件全部失踪
  - 这些文件在 git 中显示为 untracked，从未提交过，不受 git 保护
- next_actions:
  - 【P0】确认 HTML 报告文件是否仍存在（reports/Collection_Operations_Report_v3_6_2026-04-23.html）
  - 【P1】从 HTML 报告反推并重建 generate_v2_7.py
  - 【P2】重建 patch_utils.py、tl_conclusions_renderer.py、view_tl_stl.py 等辅助文件
- blockers:
  - 核心生成脚本失踪，无法重新生成报告
- handoff_note: 项目处于损坏状态，需先确认 HTML 报告资产完整性，再重建生成脚本。

## 会话快照（2026-04-27 晚）
- status: in_progress
- evidence:
  - 修复 tl_conclusion_fn 中 `\${improvementPlanBlock}` → `${improvementPlanBlock}`（Python普通字符串中 `\$` 不转义，导致字面量残留）
  - 确认 STL re.sub 锚点 `// ===================== DATA VIEW` 正确匹配，`${improvementPlanBlock}` 在 STL 中已正确渲染为 HTML
  - 确认模板 hotfix（lines 3845-3846）已注释，无重复 var MODULE_IMPROVEMENT_PLAN_URL
- next_actions:
  - 重新生成报告后验证 TL conclusions 中 `${improvementPlanBlock}` 无字面量残留
  - 浏览器抽检文档链接可点击性
  - 清理 DEBUG 代码（generate_v2_7.py 第 2189-2207 行）
- blockers: []
- handoff_note: TL conclusion 的 `\${improvementPlanBlock}` 是 Python 普通字符串中 `\$` 不转义导致的，已修复。STL 无此问题。重新生成后需验证。

## 会话快照（2026-04-27 下午）
- status: in_progress
- evidence:
  - 已从 commit 435ff104 恢复全部失踪文件：generate_v2_7.py、patch_utils.py、view_tl_stl.py、tl_conclusions_renderer.py、templates/*.j2、data_contract.py 等
  - 已恢复 v3_6_2026-04-21.html（模板，5754行）和 v3_6_2026-04-23.html（HTML产物）
  - 本次会话确认：re.sub 补丁链静默失效——29个 post_* + 9个 gen_* 锚点未找到
  - 生成的 HTML v3_6_2026-04-25.html 有 2份 var MODULE_IMPROVEMENT_PLAN_URL（旧版未删除），导致 JS SyntaxError
  - tl_conclusion_fn（含 const MODULE_IMPROVEMENT_PLAN_URL）未被 re.sub 插入到生成 HTML
  - 模板 v3_6_2026-04-21.html 中 generateTLConclusions 函数使用 var，未被 tl_conclusion_fn（const）版本替换
  - 文档链接问题根本原因：子模块（S1-Large/S2-Small 等）对应的 coarseModule 归一化已存在于模板中，但补丁机制失效
- next_actions:
  - 【P0】调试 tl_conclusion_fn re.sub：模板函数未被替换的根本原因
  - 【P1】验证生成 HTML 无 JS 语法错误 + 文档链接可点击
  - 【P2】执行 Jinja2 模板迁移（plan 文件已存在于 .claude/plans/radiant-watching-perlis.md）
- blockers:
  - re.sub 锚点失效导致生成的 HTML JS 语法错误，文档链接不可点击
- handoff_note:
  - 核心问题：字符串锚点脆弱性——HTML 模板与补丁锚点不匹配时静默失效
  - generate_v2_7.py 已恢复，但补丁机制本身有根本性缺陷，需要 Jinja2 迁移
  - Plan 文件已存在：.claude/plans/radiant-watching-perlis.md

## 会话快照（2026-04-28 下午）
- status: in_progress
- evidence:
  - view_data.py line 686 修复：8-pair \' → '' + module + ''
  - 模板 v3_6_2026-04-21.html 修复 3 处 onclick：\'\'\'\'\'\'\'\' → '' + module + ''
  - 04-25.html 生成后全部 16 个 toggleAgentOverviewModule onclick 无 0x5c (backslash)
  - 仍报 JS SyntaxError: Unexpected string at line 6218
  - line 6218 位于 <script> 块内（66668-14047872），内容是 Python source 字符串（section += '<button onclick=...>）但出现在 JS 上下文中，浏览器当作 JS 执行导致语法错误
  - cross-validation 确认：'' + module + '' 在 JS 中合法（empty string concat），8 quotes 也合法
- next_actions:
  - 【P0】定位 line 6218 根因：Python source 字符串为何出现在 JS <script> 块内被当作 JS 执行
  - 【P0】确认 '' 在 JS 单引号字符串中的语义
  - 【P2】浏览器抽检
- blockers:
  - JS SyntaxError: Unexpected string at line 6218
  - toggleAgentOverviewModule('' + module + '') 是否合法 JS？
- handoff_note: backslash 问题已解决（模板+view_data.py 均已干净），但 line 6218 的 Python source 为何出现在 JS <script> 块内仍待定位。

## 会话快照（2026-04-28 傍晚）
- status: in_progress
- evidence:
  - view_data.py line 686: "..." 双引号字符串，\' 解析为两个单引号 ''，result = '' + module + ''（合法 JS）
  - 模板 04-21.html 修复 3 处 onclick：已替换 \\'\\'\\'\\'\\'\\'\\'\\' 为 '' + module + ''
  - 04-25.html 全部 16 个 onclick 无 backslash (0x5c) — 已验证 clean
  - 但 line 6218 (HTML) 内容：section += '<button onclick="toggleAgentOverviewModule('' + module + '')"...>' （Python source），位于 <script> 块内，被浏览器当作 JS 解析
  - 模板中相同 section += 写法也存在，浏览器均当作 JS 执行
- next_actions:
  - 【P0】定位 line 6218 根因：模板的 Python source 字符串为何保留在 HTML 中而非被生成脚本求值
  - 【P0】修复 toggleAgentOverviewModule('' + module + '') 在 JS 单引号字符串中的引号问题
  - 【P2】浏览器抽检验证
- blockers:
  - line 6218 报 SyntaxError: Unexpected string — Python source 字符串被当作 JS 执行
  - 模板中 section += '<button onclick="...">' 是 Python 代码还是 JS？为何保留原样？
- handoff_note: backslash 问题已彻底解决，但 JS 语法错误的根因已转变为"模板中的 Python source 字符串为何保留在 HTML 中未被求值"。

## 会话快照（2026-04-28 晚间）
- status: in_progress
- evidence:
  - 根因定位完成：跨层转义语义不一致——Python 三引号字符串中 `\'` 被解析为 `'`（裸单引号），而非 `\'`（JS 转义）
  - 修复模板 `v3_6_2026-04-21.html` 3处：JS 单引号字符串内 `''` → `\'`
  - 修复 `view_data.py` 3处（line 355/451/686）：三引号字符串中 `\'` → `\\'`（输出 `\'` 到 JS）
  - 重新生成 `v3_6_2026-04-25.html`，全部 6 处 toggle 调用均正确输出 `\'`，Hard checks passed
  - 遗留 SOFT_WARN: onclick no JS escape quotes，待排查
- next_actions:
  - 【P1】排查 SOFT_WARN 来源
  - 【P2】浏览器抽检验证
  - 【P2】Git 提交推送
- blockers: []
- handoff_note: 核心 SyntaxError 已解决。跨层转义规则：Python 三引号字符串 → 要输出 `\'`（JS 转义单引号），必须写 `\\\\'`（四个反斜杠）。

## 会话快照（2026-04-28 保存）
- status: in_progress
- evidence:
  - 修复 `generate_v2_7.py`：`stlChart` 声明缺失 + `renderSTLChart` 正则 `\n\s*\n\s*` 过于严格导致 re.sub 静默失效
  - 重新生成 `v3_6_2026-04-27.html`，`var stlChart = null;` 已正确注入，resize handler 无 ReferenceError
  - 用户人工检验通过，浏览器控制台已干净
- next_actions:
  - 【P0】Git 提交并推送当前修复
  - 【P2/长期】Jinja2 模板迁移（替换 fragile string-replacement 为结构化模板渲染）
- blockers: []
- handoff_note: 核心 JS 语法错误（toggleAgentOverviewModule 引号、stlChart 未定义）已全部解决，产物可正常使用。re.sub 锚点脆弱性已短期修复（放宽正则），长期需 Jinja2 迁移根治。

## 会话快照（2026-04-28 当前）
- status: in_progress
- evidence:
  - Conclusion 增加第三列 Suggested Action（TL 修复了之前 tableHtml 替换未命中导致的 action 缺失）
  - Action 文案全改为英文（People/Strategy/Tool/Environment/Lagging）
  - Lagging Action 带具体名单：TL 展示 agent 姓名，STL 展示 group 名
  - 阈值动态化：attendance/connectRate/callLossRate/dial 从硬编码（95%/22%/20%）改为同模块/全模块均值 + 容忍带
  - 容忍带配置：ATTENDANCE_TOLERANCE=2pp, CONNECT_TOLERANCE=5pp, LOSS_TOLERANCE=5pp, DIAL_TOLERANCE=10%
- next_actions:
  - 【P0】Git 提交并推送
  - 【P1】重新生成报告验证 conclusion 渲染
- blockers: []
- handoff_note:
  - generate_v2_7.py 中 TL 和 STL 的 conclusion 函数已完成重构
  - Jinja2 模板（tl_conclusions.html.j2 / stl_conclusions.html.j2）已同步更新
  - 动态判断逻辑已落地，容忍带为集中常量，便于后续微调

## 会话快照（2026-04-29 自动化Pipeline方案确定）
- status: in_progress
- evidence:
  - 自动化方案已确定：方案A（本地Windows定时任务 + 线上取数）
  - Function Compute HTTP API 端点已确认：`https://fc-maxcte-query-azbabkaceu.ap-southeast-1.fcapp.run`
  - 测试脚本 test_api.py 已准备，等待 AccessKey 配置后验证返回格式
  - Notebook 01_Data_Extraction_v3.ipynb 的16个SQL查询和sheet结构已完整梳理
- next_actions:
  - 【P0/阻塞】跑通 test_api.py，确认 API 返回数据格式（JSON Array/ODPS格式）
  - 【P1】基于 API 返回格式实现 get_write_data_from_dataworks.py（本地run_sql替换）
  - 【P2】编写 run_pipeline.py（取数→生成HTML→分发）
  - 【P3】Windows Task Scheduler 定时配置
- blockers:
  - Function Compute HTTP API 认证方式未确认（当前返回 403，需要正确 Bearer Token 或 AK）
- handoff_note:
  - 方案A已选定，待 API 调通后可立即恢复推进
  - test_api.py 在根目录，填入 AK 后即可运行测试
  - 所有历史版本脚本已清理，仓库清爽

## 长期规划：Agent 级 Conclusion 诊断（方案三）
- 目标：从 group/module 级结论下沉到 agent 级精准诊断
- 具体需求：
  - 每个 lagging agent 的短板归因到 People/Strategy/Tool 具体维度
  - 例如：Agent A — attendance OK, connect rate low → Tool issue → 建议切换线路测试
  - Action 不再统一，而是根据 agent 个人指标组合生成个性化建议
- 依赖：
  - 当前方案一（规则映射）已跑稳
  - 需要业务方确认归因逻辑（避免误判）
- 优先级：P2（等方案一稳定后启动）
- 状态：backlog

## 会话快照（2026-04-28 晚）
- status: in_progress
- evidence:
  - 修复 TL view 改进文档链接：恢复按模块区分 S0/S1/S2/M1，子模块粗略匹配（S1-Large/S1-Small → S1）
  - STL 保持统一链接不变
  - TL 和 STL view：process target met 时隐藏改进方案链接
  - 人工抽检通过，已合并 hotfix/2026-04-28-tl-module-links → master 并 push
- next_actions:
  - 【P0】重新生成最终报告验证所有修复点
  - 【P1】清理临时 debug/test 脚本
  - 【P2/长期】Jinja2 模板迁移
- blockers: []
- handoff_note:
  - master 已包含最新修复；下次生成报告前确保 generate_v2_7.py 和模板 v3_6_2026-04-21.html 一致

## 会话快照（2026-04-29 P1清理 + Bug修复）
- status: completed
- evidence:
  - 修复 `generate_v2_7.py` line 675：`g_dtr.index.day == day` → `g_dtr.index == pd.Timestamp(date_str)`
  - 根因：跨月日期匹配导致4月28被3月28覆盖（S1-Large A target错误显示644000 → 修正为485642）
  - 重新生成 `v3_6_2026-04-28.html`，Hard checks passed，人工抽检通过
- next_actions:
  - 【P2/长期】Jinja2 模板迁移
  - 【P3/长期】Agent 级精准诊断
- blockers: []
- handoff_note: 数据视图精确性修复，不涉及UI或结论文案变更

## 会话快照（2026-04-29 基线模板剥离完成）
- status: in_progress
- evidence:
  - 执行基线模板剥离计划，从 `v3_6_2026-04-21.html` 剥离5类补丁产物
  - 生成 `templates/Collection_Operations_Report_base.html`（纯净基线模板）
  - 修改 `generate_v2_7.py` line 80：`HTML_IN` 指向 `templates/Collection_Operations_Report_base.html`
  - 修复 `generate_v2_7.py` line 1791：old_string `Connect Rate Gap` → `Call Billmin Gap`（基线模板标签已变更导致替换失效）
  - 重新生成 `v3_6_2026-04-28.html`，Hard checks passed
  - 验证产物：9个补丁元素（subtab-agent-overview、data-agent-overview、tl-gap-meta×3、tl-unmet-attendance、stl-gap-meta×3）各恰好出现1次，无重复
  - 人工抽检通过（用户确认）
- next_actions:
  - 以 `progress.json` 的 `next_actions` 为准
- blockers: []
- handoff_note: 基线模板机制已生效，后续生成报告前确保 `generate_v2_7.py` 和 `templates/Collection_Operations_Report_base.html` 一致；`HTML_IN` 不再指向 reports 目录下的历史产物

## 会话快照（2026-05-06 Jinja2迁移计划评审）
- status: in_progress
- evidence:
  - Jinja2迁移计划（.claude/plans/robust-inventing-hearth.md）已完成全面评审
  - 补丁数量修正：约175 → 约210（经generate_v2_7.py/view_data.py/view_tl_stl.py/view_tl_stl_post_patches.py 4文件统计）
  - 补丁类型细分：JS逻辑块替换~50、字段重映射~40、文本copy~30、数据筛选~30、HTML结构~25、I18N~15、其他~20
  - 计划v2更新：单模板→4子模板拆分、新增Phase 2.5 Pilot gate（GO/NO-GO决策点）、3个Checkpoint、回退计划、时间重估11-15天
  - 关键设计决策：先跑Data View一个卡片的最小闭环验证，再决定是否全面推进
- next_actions:
  - 【P0】执行Phase 1-2.5：搭建jinja2_migration/骨架 + data_prep数据准备 + Pilot最小.j2验证
  - 【P1】Pilot GO之后：推进Phase 3-4（snapshot基建 + 完整模板转换）
  - 【P2】实现 get_write_data_from_dataworks.py（自动化pipeline取数）
- blockers: []
- handoff_note:
  - 迁移计划已就绪（.claude/plans/robust-inventing-hearth.md），评审通过
  - Pilot范围：Data View Tab → Under-performing卡片（补丁最少、逻辑最简单）
  - 验证标准：JSON等价 + 卡片HTML结构一致 + 浏览器无console error
  - 当前管线（generate_v2_7.py）继续正常运行，jinja2_migration/为并行实验

## 会话快照（2026-05-06 Phase 1+2 helpers完成）
- status: in_progress
- evidence:
  - 创建 jinja2_migration/ 目录及子目录（templates/, tests/, reports/）
  - 8 个文件落盘：.gitignore、README.md、requirements.txt、data_contract.py（增强 contract_id=v3_5+jinja2@2026-05-06）、check_anchors.py、renderer.py（StrictUndefined+autoescape）、data_prep_helpers.py（16 个纯函数）、tests/test_data_prep_helpers.py
  - 16 个纯函数（13 计划列出 + 3 私有/依赖）：parse_week_str/format_week_range/normalize_week_label/week_start_dt/get_week_label/week_str_to_display/extract_module_key/sort_module_keys/map_group_to_dtr/norm/resolve_canonical_group_for_breakdown/module_key_to_bucket/normalize_attd_rate_pct/compute_consecutive_days/build_consecutive_weeks_map + _parse_module_parts_for_sort/_MODULE_SORT_PRIORITY/_MODULE_SORT_RANK
  - 关键架构改动：state→显式参数（data_warning_set→warnings 形参；nat_buckets→形参）；regex 预编译；Iterable 走 collections.abc
  - 61 个单测全通过（1.7s）；含 reviewer-driven 补测 10 个（中文 tier、空串、S1- 边界、大写 LARGE、空 DataFrame、boundary 0.0、负值、首周达标后 streak 重置等）
  - 多模型审计（python-reviewer + code-reviewer 并行）：0 CRITICAL，2 HIGH 已修复（H4 module_key_to_bucket docstring 误导；H3 build_consecutive_weeks_map 缺测试），5 MEDIUM 部分修复，1 LOW 采纳（typing.Iterable→collections.abc）
  - codex/gemini wrapper 未安装（~/.claude/bin/codeagent-wrapper 缺失），已用 Claude Code 内置 agent 替代审计环节
- next_actions:
  - 【P0】Phase 2 主逻辑：实现 jinja2_migration/data_prep.py 的 build_context()，加载 Excel → 处理 → 构建 real_data dict（字段名 camelCase 与 JS 期望对齐：repayRate、ptpRate、callLossRate）
  - 【P0】Phase 2.5：Pilot — Data View Under-performing 卡片最小闭环（含 snapshot 对比 + 浏览器 console 检查）
  - 【P1】Phase 2 主逻辑前先跑一次 generate_v2_7.py 确认生产管线仍正常
- blockers: []
- handoff_note:
  - jinja2_migration/ 与生产管线**完全隔离**，互不影响。下一会话执行 Phase 2 主逻辑前可直接 import data_prep_helpers
  - normalize_week_label 用 functools.partial 配合 Series.apply 注入 warnings 集合（已写入 docstring 示例）
  - module_key_to_bucket、resolve_canonical_group_for_breakdown 的 nat_buckets/norm_to_group 由调用方装配，建议在 build_context 入口集中构造一次
  - 当前 dual_review_gate=passed_warning，可继续推进 Phase 2；如 Phase 2.5 Pilot NO-GO，可保留本目录作参考，生产管线 generate_v2_7.py 继续运行

## 会话快照（2026-05-06 Phase 2 主逻辑完成）
- status: in_progress
- evidence:
  - 实现 jinja2_migration/data_prep.py（1290行）：load_excel_sheets() / determine_key_dates() / build_derived_structures() / preprocess_natural_month() / build_tl_data() / build_agent_performance() / build_group_performance() / build_stl_data() / build_context()
  - 实现 jinja2_migration/data_prep_payloads.py（290行）：build_anomaly_groups() / build_anomaly_agents() / build_module_daily_trends() / build_module_monthly() / build_risk_module_groups() / build_today_agent_targets() / build_tl_breakdown_by_date() / build_stl_breakdown_by_week()
  - data_prep_helpers.py 新增 2 个函数：detect_day_only_cross_month_risk() / filter_report_month()（18 个纯函数总计）
  - build_context() 烟雾测试通过：加载真实 Excel 数据 → 27 个 real_data 键全部正确产出
  - 结构交叉验证通过：tlData/agentPerformance/stlData/groupPerformance/moduleDailyTrends/anomalyGroups/anomalyAgents 等所有嵌套结构键名正确
  - 现有 61 个单测全部继续通过
  - 生产管线 generate_v2_7.py 未触碰（git status 确认）
  - templateContractId: v3_5+jinja2@2026-05-06
- next_actions:
  - 【P0】Phase 2.5 Pilot：Data View Under-performing 卡片最小闭环（JSON等价 + 卡片HTML结构一致 + 浏览器无console error）
  - 【P1】实现 get_write_data_from_dataworks.py（自动化pipeline取数）
  - 【P2】编写 run_pipeline.py（取数→生成HTML→分发）
- blockers: []
- handoff_note:
  - build_context() 已可独立运行，输出与 generate_v2_7.py real_data 结构完全一致
  - from data_prep import build_context 即可使用（需在 jinja2_migration/ 目录下运行）
  - 下一会话：执行 Phase 2.5 Pilot，用 build_context 的输出渲染 Data View Under-performing 卡片 .j2 模板，与当前 HTML 产物 snapshot 对比

## 会话快照（2026-05-07 Phase 3 Snapshot 基建完成）
- status: in_progress
- evidence:
  - Phase 2.5 Pilot 全部完成：Jinja2 渲染与 JSON 等价（16 groups / 55 agents, row count/name/streak 全部 PASS），用户 GO 确认
  - Phase 3 Snapshot 基建完成：6 个步骤全部通过
  - 新建文件: tests/helpers/html_table.py, tests/conftest.py, dump_full_snapshot.py, test_data_prep_build_context.py, test_renderer_smoke.py, test_pilot_snapshot.py
  - 修改文件: compare_pilot.py (refactored import), data_contract.py (_REQUIRED_TOP_LEVEL_KEYS 8→29)
  - 85 tests 全绿（1.88s），含 11 个 build_context 集成测试 + 5 个 renderer smoke + 8 个 pilot snapshot
  - 生产管线 generate_v2_7.py 未触碰（git status 确认）
- next_actions:
  - 【P0】Phase 4a Data View Tab 模板转换（24 补丁/4 卡片/1380 行 JS，约 14h）
  - 【P1】用户浏览器抽检 Phase 4a 输出
  - 【P2】实现 get_write_data_from_dataworks.py（自动化 pipeline 取数）
- blockers: []
- handoff_note:
  - Phase 3 全部完成，Phase 4a 计划已发布（~/.claude/plans/robust-sprouting-stearns.md）
  - data_prep.build_context() 30 个 key 已锁定在 tests/fixtures/real_data_baseline.json（本地生成，gitignore 不入库）
  - 下一会话优先动作：等待用户启动 Phase 4a，或继续 Phase 4a 中 4a.1 子模板骨架（data_view/_index.html.j2）
