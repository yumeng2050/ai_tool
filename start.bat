@echo off
chcp 65001 >nul
cd /d %~dp0

REM 优先使用本机 D 盘 Python，避免 PATH 中残留旧盘符或商店版 python 干扰
if exist "D:\Python_3_12_10\python.exe" set "PATH=D:\Python_3_12_10;D:\Python_3_12_10\Scripts;%PATH%"

echo Starting AI info collector at http://127.0.0.1:8000 ...
start "" /min cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8000"
python -m src.web.server
pause
