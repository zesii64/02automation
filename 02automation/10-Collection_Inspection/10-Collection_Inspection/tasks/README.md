# 任务卡使用说明

## 命名规范
- `task_YYYY-MM-DD_short_topic.md`

## 生命周期
- `todo` -> `in_progress` -> `done` or `blocked`

## 必填模块
- 目标
- 约束
- 预检清单
- 状态
- 证据
- 下一步动作
- 交接说明

## 保存规则
- 每次执行 `/save` 时，至少更新：
  - 当前 `status`
  - 最新 `evidence`
  - 最优先的 `next_actions`
