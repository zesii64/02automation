# Agent Split Prompt (v2.7)

## 0) Shared Prompt (send to all A/B/C)

```text
You are continuing split-based development on generate_v2_7.

Read and strictly follow:
code/agent_handoff_v2_7.md

Execution rules:
1) Respect file ownership boundaries strictly.
2) Only modify your owned files.
3) Do NOT modify any data-source/aggregation logic in generate_v2_7.py before HTML template patching.
4) If there is ownership ambiguity, stop and report one-sentence ownership proposal.
5) If A/B conflict on the same lines in generate_v2_7.py, leave integrator-apply TODO for C.
6) For high-risk cross-view UI/layout/chart-lifecycle changes (especially Data/Recovery Trend DOM structure changes), explicitly decide whether Agent C integration is required BEFORE implementation; if yes, stop and ask user to redirect to Agent C first.

Before finalizing, run:
python -m py_compile 05-scripts/generate_v2_7.py 05-scripts/view_tl_stl.py 05-scripts/view_data.py

Output format:
- Migrated sections:
- Files touched:
- Behavior changed intentionally? (Yes/No)
- Risks:
```

## 1) Agent A Prompt (TL/STL stream)

```text
Role: Agent A (TL/STL stream)

Allowed edits:
- 05-scripts/view_tl_stl.py
- 05-scripts/generate_v2_7.py (only wiring/removal of already-migrated TL/STL blocks)

Not allowed:
- 05-scripts/view_data.py
- Any data ingestion/aggregation logic before HTML patching in generate_v2_7.py

Migrate these sections from generate_v2_7.py into view_tl_stl.py:
- #5b #6 #7 #8 #9 #10 #10b #10c #11 #12
- #17 #18 #19
- #20 #21
- #23 #23.1 #23.2
- #24 #24.1
- #25
- TL table/group sorting + selected line highlight
- TL repay/process badge patch block
- STL full-month recovery trend replacement block
- #26b M2 hide logic related to TL/STL only

Goal:
- Keep behavior unchanged.
- Keep generate_v2_7.py as orchestrator for TL/STL patch invocation only.
```

## 2) Agent B Prompt (Data stream)

```text
Role: Agent B (Data stream)

Allowed edits:
- 05-scripts/view_data.py
- 05-scripts/generate_v2_7.py (only wiring/removal of already-migrated Data blocks)

Not allowed:
- 05-scripts/view_tl_stl.py
- Any data ingestion/aggregation logic before HTML patching in generate_v2_7.py

Migrate these sections from generate_v2_7.py into view_data.py:
- #13 #14 #15 #16 #16.1 (loadTrendChart related)
- #22 (riskModuleGroups table patch)
- Data modularized block after #2328:
  - loadAnomalyData rewrite
  - Agent Overview subtab + renderer/functions
  - initDataView update
  - under-performing group header weekly schema update
- #26 (Data date)
- #26b M2 hide logic related to Data view only

Goal:
- Keep behavior unchanged.
- Keep generate_v2_7.py as orchestrator for Data patch invocation only.
```

## 3) Agent C Prompt (Integrator/QA stream)

```text
Role: Agent C (Integrator/QA stream)

Allowed edits:
- 05-scripts/generate_v2_7.py (orchestration only)
- Minimal non-functional cleanup in view_tl_stl.py and view_data.py

Responsibilities:
1) Resolve merge conflicts between A/B outputs.
2) Enforce stable call order:
   - REAL_DATA injection first
   - apply_tl_stl_view_patches(html)
   - apply_data_view_patches(html)
   - final write
3) Ensure no duplicate inline patch logic remains in generate_v2_7.py.
4) Finalize #26b cross-boundary M2 hide integration without duplicate replacement.
5) Run py_compile + one smoke generation.

Goal:
- generate_v2_7.py is orchestrator-only.
- Split ownership is clean and conflict-free.
```

