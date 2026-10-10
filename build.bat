@echo off
chcp 65001 >nul
rem 실행 파일 만들기: dist\Lectern\Lectern.exe
cd /d "%~dp0"
set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
%PY% -m pytest -q || goto :fail
%PY% -m PyInstaller --noconfirm lectern.spec || goto :fail
echo.
echo 완료: dist\Lectern\Lectern.exe
echo 탐색기 우클릭 메뉴 등록: %PY% tools\context_menu.py
exit /b 0
:fail
echo 빌드 실패
exit /b 1
