@echo off
chcp 65001 >nul
rem 브라우저 개발 모드: 서버만 띄우고 일반 브라우저에서 확인. 사용: dev.bat [폴더]
cd /d "%~dp0"
set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
if "%~1"=="" (
  %PY% app.py --browser samples
) else (
  %PY% app.py --browser %*
)
