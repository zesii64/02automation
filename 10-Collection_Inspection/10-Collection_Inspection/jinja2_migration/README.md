# Jinja2 模板迁移工作目录

并行实验目录，**不影响生产管线**。当前生产仍由 `05-scripts/generate_v2_7.py` 跑。

## 目标

用 Jinja2 模板渲染替代 ~210 个字符串 `.replace()` 补丁；数据预处理阶段直接产出 JS 期望的最终字段名。

## 阶段进度

- [x] Phase 1：搭骨架（目录、`requirements.txt`、`data_contract.py`、`check_anchors.py`、`renderer.py`）
- [ ] Phase 2：抽取 `data_prep_helpers.py` + 编写 `data_prep.py`
- [ ] Phase 2.5：Pilot — Data View Under-performing 卡片最小闭环
- [ ] Phase 3-8：见 `.claude/plans/robust-inventing-hearth.md`

## 目录布局

```
jinja2_migration/
├── data_contract.py          # 契约校验 + head comment 注入
├── check_anchors.py          # 锚点检查
├── renderer.py               # Jinja2 Environment + render_report()
├── requirements.txt
├── README.md
├── data_prep_helpers.py      # [Phase 2] 周/模块/连续未达标工具函数
├── data_prep.py              # [Phase 2] 加载 Excel → 构建 context dict
├── run_pipeline.py           # [Phase 5] 入口：取数 → 渲染 → 校验 → 写产物
├── templates/
│   ├── base.j2               # [Phase 4] 主骨架
│   ├── tl_agent.j2           # [Phase 4] TL Agent Tab
│   ├── stl_group.j2          # [Phase 4] STL Group Tab
│   └── data_view.j2          # [Phase 4] Data View Tab
├── tests/
│   ├── test_data_prep.py     # [Phase 3] 数据预处理单元测试
│   ├── test_renderer.py      # [Phase 6] 渲染器单元测试
│   └── test_snapshot.py      # [Phase 3] 与当前管线产物逐字段对比
└── reports/                  # 产物目录（gitignore）
```

## 运行（Phase 1 仅自检）

```bash
cd jinja2_migration
pip install -r requirements.txt
python -c "from renderer import _build_environment; print(_build_environment())"
python check_anchors.py  # 无路径，仅模块自检
```

## 与生产管线的关系

| 项目 | 生产 (`05-scripts/`) | 实验 (`jinja2_migration/`) |
|------|----------------------|-----------------------------|
| 入口脚本 | `generate_v2_7.py` | `run_pipeline.py`（Phase 5） |
| 模板 | `templates/Collection_Operations_Report_base.html` | `templates/*.j2` |
| 数据契约 | `real_data_contract.py` | `data_contract.py`（增强） |
| 锚点检查 | `check_report_anchors.py` | `check_anchors.py` |

## 回退原则

任何阶段发现不可逾越的阻碍 → 保留本目录作参考，生产管线继续运行。详见 `.claude/plans/robust-inventing-hearth.md` 回退计划。
