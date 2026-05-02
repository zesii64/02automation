@echo off
chcp 65001 >nul
echo ========================================
echo  自动下载邮件附件并生成报告
echo  %date% %time%
echo ========================================

REM 激活你的虚拟环境（如果有的话，没有就删掉下面这行）
REM call D:\your_env\Scripts\activate.bat

cd /d "D:\11automation\02automation\10-Collection_Inspection\10-Collection_Inspection\05-scripts"

python 01-email_attachment_downloader.py

echo ========================================
echo 执行完毕
echo ========================================
pause
