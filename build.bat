@echo off
chcp 65001 >nul
rem 실행 파일 만들기: dist\Lectern\Lectern.exe, Inno Setup 이 있으면 설치 파일 dist\Lectern-버전-setup.exe 도
cd /d "%~dp0"
set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe
%PY% -m pytest -q || goto :fail
%PY% -m PyInstaller --noconfirm lectern.spec || goto :fail
echo.
echo 완료: dist\Lectern\Lectern.exe

set "ISCC="
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC goto :no_installer
for /f %%v in ('%PY% -c "import lectern; print(lectern.__version__)"') do set "VER=%%v"
"%ISCC%" /Q /DAppVersion=%VER% installer\lectern.iss || goto :fail
echo 완료: dist\Lectern-%VER%-setup.exe
exit /b 0

:no_installer
echo 설치 파일은 건너뜁니다: Inno Setup 6 이 없습니다. winget install JRSoftware.InnoSetup 으로 설치할 수 있습니다.
echo 설치 파일 없이 탐색기 우클릭 메뉴를 등록하려면: %PY% tools\context_menu.py
exit /b 0

:fail
echo 빌드 실패
exit /b 1
