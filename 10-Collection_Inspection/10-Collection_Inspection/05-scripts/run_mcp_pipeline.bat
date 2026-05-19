@echo off
REM ==============================================================
REM MCP Pipeline scheduled run - Windows Task Scheduler entry
REM Date range: auto 1st of month ~ yesterday
REM Chunk: 2 days per query (MCP LIMIT 1000 protection)
REM Credentials: read ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET from env
REM Schedule: daily 08:45 (Windows Task Scheduler)
REM Log: append to reports\pipeline.log
REM ==============================================================

set PYTHON=C:\Users\zhangyuntian\AppData\Local\Programs\Python\Python313\python.exe
set SCRIPT=D:\11automation\02automation\10-Collection_Inspection\10-Collection_Inspection\05-scripts\run_mcp_pipeline.py
set LOG=D:\11automation\02automation\10-Collection_Inspection\10-Collection_Inspection\reports\pipeline.log

echo ===== MCP Pipeline Started: %DATE% %TIME% ===== > "%LOG%"

REM Env vars checked by Python script (with fallback to accesskey.txt)
if "%ALIYUN_ACCESS_KEY_ID%"=="" (
    echo [WARN] ALIYUN_ACCESS_KEY_ID not in env, will try accesskey.txt fallback >> "%LOG%"
)
if "%ALIYUN_ACCESS_KEY_SECRET%"=="" (
    echo [WARN] ALIYUN_ACCESS_KEY_SECRET not in env, will try accesskey.txt fallback >> "%LOG%"
)

"%PYTHON%" "%SCRIPT%" >> "%LOG%" 2>&1
set EC=%errorlevel%

echo ===== MCP Pipeline Finished (code=%EC%): %DATE% %TIME% ===== >> "%LOG%"
exit /b %EC%
