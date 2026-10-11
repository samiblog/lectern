@echo off
setlocal
chcp 65001 >nul
rem Lectern 실행 (개발 중). 사용: run.bat [폴더]
rem 폴더는 지금 있는 곳 기준이다 (run.bat . = 현재 폴더). 그래서 스크립트 폴더로 cd 하지 않는다
set "HERE=%~dp0"
if exist "%HERE%.venv\Scripts\pythonw.exe" (
  start "" "%HERE%.venv\Scripts\pythonw.exe" "%HERE%app.py" %*
) else (
  start "" pythonw "%HERE%app.py" %*
)
