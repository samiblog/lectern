; Lectern 설치 파일 (Inno Setup 6). build.bat 이 만든다:
;   ISCC /DAppVersion=0.2.0 installer\lectern.iss   →   dist\Lectern-0.2.0-setup.exe
;
; - 현재 사용자 설치, 관리자 권한 불필요: %LOCALAPPDATA%\Programs\Lectern (D25)
; - 시작 메뉴 바로가기, 선택: 바탕화면 바로가기, 탐색기 폴더 우클릭 'Lectern으로 열기' (tools\context_menu.py 와 같은 키)
; - 제거해도 설정(%APPDATA%\Lectern\config.json)은 지우지 않는다 — 다시 설치하면 최근 폴더·스타일을 이어 쓴다
; - 이 파일은 UTF-8(BOM)이어야 한다. BOM이 없으면 ISCC가 한글을 시스템 코드 페이지로 읽는다

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; AppId 는 바꾸지 않는다 — 같은 값이어야 새 버전이 같은 자리에 덮어 설치된다
AppId={{2A366656-824B-4170-AE7B-982785216D59}
AppName=Lectern
AppVersion={#AppVersion}
AppVerName=Lectern {#AppVersion}
AppPublisher=Lectern
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Lectern 설치
DefaultDirName={autopf}\Lectern
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Lectern-{#AppVersion}-setup
SetupIconFile=..\assets\lectern.ico
UninstallDisplayIcon={app}\Lectern.exe
UninstallDisplayName=Lectern
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; 설치·제거 중에 Lectern이 실행 중이면 닫도록 안내한다
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=no

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "contextmenu"; Description: "탐색기 폴더 우클릭에 'Lectern으로 열기' 추가"; GroupDescription: "추가 작업:"
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 작업:"; Flags: unchecked

[InstallDelete]
; 새 버전으로 덮어 설치할 때, 이전 버전에만 있던 파일이 남지 않게 한다
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\Lectern\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Lectern"; Filename: "{app}\Lectern.exe"; Comment: "프로젝트 문서 뷰어 (Markdown·HTML)"
Name: "{autodesktop}\Lectern"; Filename: "{app}\Lectern.exe"; Comment: "프로젝트 문서 뷰어 (Markdown·HTML)"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\Directory\shell\Lectern"; ValueType: string; ValueName: ""; ValueData: "Lectern으로 열기"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\Lectern"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\Lectern.exe"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\shell\Lectern\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Lectern.exe"" ""%1"""; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\Lectern"; ValueType: string; ValueName: ""; ValueData: "Lectern으로 열기"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\Lectern"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\Lectern.exe"; Tasks: contextmenu
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\Lectern\command"; ValueType: string; ValueName: ""; ValueData: """{app}\Lectern.exe"" ""%V"""; Tasks: contextmenu

[Run]
Filename: "{app}\Lectern.exe"; Description: "Lectern 실행"; Flags: nowait postinstall skipifsilent

[Code]
const
  WebView2Key = '\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasVersion(Root: Integer; Key: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

{ Lectern 창은 Microsoft Edge WebView2 런타임으로 그린다. Windows 11 에는 기본으로 있고 Windows 10 도 대부분 있다 }
function WebView2Installed(): Boolean;
begin
  Result := HasVersion(HKLM, 'SOFTWARE\WOW6432Node' + WebView2Key) or HasVersion(HKLM, 'SOFTWARE' + WebView2Key)
    or HasVersion(HKCU, 'Software' + WebView2Key);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not WebView2Installed() then
    SuppressibleMsgBox('이 PC에 Microsoft Edge WebView2 런타임이 없습니다. Lectern 창을 띄우려면 필요합니다.' + #13#10#13#10 +
      '설치는 계속할 수 있습니다. 설치를 마친 뒤 Microsoft 사이트에서 "WebView2 Runtime"을 받아 설치해 주세요.',
      mbInformation, MB_OK, IDOK);
end;
