@echo off
chcp 65001 >nul
rem Lectern 실행 (개발 중). 사용: run.bat [폴더]
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" app.py %*
) else (
  start "" pythonw app.py %*
)
