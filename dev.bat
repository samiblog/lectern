@echo off
setlocal
chcp 65001 >nul
rem 브라우저 개발 모드: 서버만 띄우고 일반 브라우저에서 확인. 사용: dev.bat [폴더]
rem 폴더는 지금 있는 곳 기준이다 (dev.bat . = 현재 폴더). 생략하면 samples
set "HERE=%~dp0"
set "PY=python"
if exist "%HERE%.venv\Scripts\python.exe" set "PY=%HERE%.venv\Scripts\python.exe"
if "%~1"=="" (
  "%PY%" "%HERE%app.py" --browser "%HERE%samples"
) else (
  "%PY%" "%HERE%app.py" --browser %*
)
