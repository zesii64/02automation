@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   CashLoan 巡检日报 - 执行中（有进度）
echo ========================================
echo.
python run_cashloan_report.py --no-pause
echo.
echo ========================================
echo   执行结束，请查看上方进度与 reports 目录
echo ========================================
pause
