# Agent Handoff Contract (v2.7 baseline)

## 1) Goal

Continue feature development on top of `generate_v2_7.py` split architecture, while keeping module boundaries clear and minimizing merge conflicts.

This handoff is for multi-agent parallel work, not for rollback verification against old versions.

## 2) Current split architecture

- Entry/orchestrator: `05-scripts/generate_v2_7.py`
- TL/STL view patches: `05-scripts/view_tl_stl.py`
- Data view patches: `05-scripts/view_data.py`

Current contract:

- `apply_tl_stl_view_patches(html: str) -> str`
- `apply_data_view_patches(html: str) -> str`
- Each view module is pure patch logic over `html` string only.
- Data ingestion / pandas aggregation / `REAL_DATA` assembly remain in `generate_v2_7.py`.

## 3) Ownership and edit boundaries

### Agent A (TL/STL stream)

Allowed edits:

- `05-scripts/view_tl_stl.py`
- `05-scripts/generate_v2_7.py` (only to wire or remove already-migrated TL/STL patch blocks)

Not allowed:

- `05-scripts/view_data.py`
- Any data-source/aggregation logic in `generate_v2_7.py` before HTML template patching

### Agent B (Data stream)

Allowed edits:

- `05-scripts/view_data.py`
- `05-scripts/generate_v2_7.py` (only to wire or remove already-migrated Data patch blocks)

Not allowed:

- `05-scripts/view_tl_stl.py`
- Any data-source/aggregation logic in `generate_v2_7.py` before HTML template patching

### Agent C (Integrator/QA stream)

Allowed edits:

- `05-scripts/generate_v2_7.py` (orchestration only)
- Minimal non-functional cleanup in both view files

Responsibilities:

- Resolve merge conflicts
- Ensure call order is stable
- Run syntax + smoke checks

## 4) Development rules (must follow)

1. Keep functions pure:
   - No file IO in `view_tl_stl.py` / `view_data.py`
   - No Excel reads, no writes, no environment changes
2. Keep behavior-preserving migration:
   - Move existing `html.replace(...)` / block-replacement logic mechanically
   - Do not change KPI semantics unless task explicitly requests feature changes
3. Keep deterministic order:
   - In `generate_v2_7.py`: `REAL_DATA` injection first, then TL/STL patches, then Data patches, then final write
4. Avoid broad edits:
   - One concern per PR/commit
   - No opportunistic refactor outside owned stream

## 5) Suggested task slicing for parallel agents

Use section comments in `generate_v2_7.py` (`# ---- N...`) as migration units.

- TL/STL stream scope:
  - Primary: section groups around TL/STL chart/render/drilldown logic
  - Migrate into `view_tl_stl.py`
- Data stream scope:
  - Primary: section groups around Data subtab/anomaly/trend/overview logic
  - Migrate into `view_data.py`

Rule of thumb:

- If a patch references `tl`, `stl`, `group/module repay chart`, assign TL/STL stream.
- If a patch references `Data View`, `anomaly`, `agent overview`, assign Data stream.

## 6) Integration protocol

When a stream agent finishes:

1. Keep changes localized to owned files.
2. In `generate_v2_7.py`, remove only the exact migrated inline block and replace with module call if needed.
3. Run:
   - `python -m py_compile 05-scripts/generate_v2_7.py 05-scripts/view_tl_stl.py 05-scripts/view_data.py`
4. Report in fixed format:
   - Migrated sections:
   - Files touched:
   - Behavior changed intentionally? (Yes/No)
   - Risks:

## 7) Conflict handling

If two agents need the same lines in `generate_v2_7.py`:

- Do not both modify the same block.
- One agent owns migration; the other leaves TODO marker in its own report.
- Integrator applies final orchestration update.

If boundaries are unclear:

- Stop before editing
- Propose ownership decision in one sentence
- Continue only after ownership is confirmed

## 8) Definition of done

A task is done when:

- Target patch blocks are migrated to the correct view module
- Entry script still compiles
- No edits outside ownership boundary
- Handoff report is complete and unambiguous

## 9) Quick starter prompt for any new agent

Use this prompt to onboard a new agent quickly:

```
You are continuing split-based development on generate_v2_7.
Read and follow: code/agent_handoff_v2_7.md.
Respect file ownership boundaries strictly.
Only modify your owned files.
Before finalizing, run py_compile on generate_v2_7.py, view_tl_stl.py, view_data.py.
Output: migrated sections, files touched, intentional behavior changes (if any), risks.
```
