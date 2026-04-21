# Data Pipeline (Local/Online switch)

This folder provides one entry script for two pipeline modes:

- `notebook` (default): execute `01_Data_Extraction_v3.ipynb` code cells via API-backed `run_sql`, then generate the same xlsx used by report script.
- `single`: run one SQL request for debugging and save raw/normalized artifacts.

Both source types are supported in each mode:

- `local`: call local curl-compatible endpoint directly.
- `online`: call online endpoint with the same request contract.

## Files

- `run_data_pipeline.ps1`: single entry, switch by `-Source local|online`.
- `fetch_local.ps1`: local mode implementation.
- `fetch_online.ps1`: online mode implementation.
- `common.ps1`: shared SQL loading, endpoint call, artifact output.
- `execute_notebook_sql.py`: executes notebook code cells and replaces `run_sql` with HTTP API implementation.
- `sql/default.sql`: default SQL when no `-SqlFile` / `-Sql` is passed.

## Quick Start

From this folder:

```powershell
pwsh .\run_data_pipeline.ps1 -Source local -Mode notebook
```

Notebook with explicit date overrides:

```powershell
pwsh .\run_data_pipeline.ps1 -Source local -Mode notebook -DtStart "2026-03-01" -DtEnd "2026-04-30"
```

Switch notebook mode to online endpoint:

```powershell
pwsh .\run_data_pipeline.ps1 -Source online -Mode notebook -OnlineEndpoint "https://your-online-endpoint"
```

Single SQL debug mode:

```powershell
pwsh .\run_data_pipeline.ps1 -Source local -Mode single -Sql "select 1 as ok;"
```

Or set env vars:

```powershell
$env:ONLINE_SQL_API_URL="https://your-online-endpoint"
$env:ONLINE_SQL_API_TOKEN="your_token_if_needed"
pwsh .\run_data_pipeline.ps1 -Source online
```

## Output

Notebook mode output xlsx:

- `data/260318_output_automation_v3.xlsx` (default, compatible with `generate_v2_7.py`)

Single mode writes artifacts to:

- `result/data_pipeline/<timestamp>_<source>/raw/response.json`
- `result/data_pipeline/<timestamp>_<source>/normalized/rows.csv` (when response can be normalized to rows)
- `result/data_pipeline/<timestamp>_<source>/meta.json`

## Sync rule for future changes

To keep local/online paths aligned:

1. Prefer changing shared logic in `common.ps1`.
2. Keep only endpoint/auth differences in `fetch_local.ps1` and `fetch_online.ps1`.
3. Notebook business logic should be changed in `01_Data_Extraction_v3.ipynb`; both sources then follow automatically in notebook mode.
