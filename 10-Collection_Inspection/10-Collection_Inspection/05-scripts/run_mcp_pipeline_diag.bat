@echo off
REM ==============================================================
REM MCP Pipeline 诊断版 — 用于定位 Task Scheduler 环境问题
REM ==============================================================

set PYTHON=C:\Users\zhangyuntian\AppData\Local\Programs\Python\Python313\python.exe
set SCRIPT=D:\11automation\02automation\10-Collection_Inspection\10-Collection_Inspection\05-scripts\run_mcp_pipeline.py
set LOG=D:\11automation\02automation\10-Collection_Inspection\10-Collection_Inspection\generate_v2_7_package\reports\pipeline_diag.log

REM 先写日志头（证明 bat 本身被执行到了）
echo ===== DIAG START: %DATE% %TIME% ===== > "%LOG%"
echo [DIAG] Running as user: %USERNAME% >> "%LOG%"
echo [DIAG] Computer name: %COMPUTERNAME% >> "%LOG%"
echo [DIAG] Current directory: %CD% >> "%LOG%"

REM 检查 env var 是否可见（脱敏输出长度）
if defined ALIYUN_ACCESS_KEY_ID (
    echo [DIAG] ALIYUN_ACCESS_KEY_ID is DEFINED, length: %ALIYUN_ACCESS_KEY_ID:~0,1%... >> "%LOG%"
) else (
    echo [DIAG] ALIYUN_ACCESS_KEY_ID is NOT DEFINED >> "%LOG%"
)

if defined ALIYUN_ACCESS_KEY_SECRET (
    echo [DIAG] ALIYUN_ACCESS_KEY_SECRET is DEFINED, length: %ALIYUN_ACCESS_KEY_SECRET:~0,1%... >> "%LOG%"
) else (
    echo [DIAG] ALIYUN_ACCESS_KEY_SECRET is NOT DEFINED >> "%LOG%"
)

REM 检查 python 是否存在
echo [DIAG] Checking python path... >> "%LOG%"
if exist "%PYTHON%" (
    echo [DIAG] Python found at: %PYTHON% >> "%LOG%"
) else (
    echo [DIAG] Python NOT found at: %PYTHON% >> "%LOG%"
    exit /b 1
)

REM 检查脚本是否存在
if exist "%SCRIPT%" (
    echo [DIAG] Script found at: %SCRIPT% >> "%LOG%"
) else (
    echo [DIAG] Script NOT found at: %SCRIPT% >> "%LOG%"
    exit /b 1
)

REM 尝试运行 Python（无论 env var 是否存在都试一次，让 Python 自己报错）
echo [DIAG] Launching Python script... >> "%LOG%"
"%PYTHON%" "%SCRIPT%" >> "%LOG%" 2>&1
set EC=%errorlevel%

echo ===== DIAG END (code=%EC%): %DATE% %TIME% ===== >> "%LOG%"
exit /b %EC%
