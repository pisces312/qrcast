@echo off
chcp 65001 >nul
cd /d "%~dp0"
"D:\dev\miniconda3\python.exe" -m qrcast.bw.gen_and_display_individual "%~1"
pause
