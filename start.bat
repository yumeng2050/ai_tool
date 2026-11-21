@echo off
chcp 65001 >nul
cd /d %~dp0
echo Starting AI info collector at http://127.0.0.1:8000 ...
start "" /min cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8000"
python -m src.web.server
pause
