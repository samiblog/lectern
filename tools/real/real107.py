"""0.107.0 — 실제 창(WebView2)에서: '폴더' 묶음의 모든 것과 탐색기와의 복사·붙여 넣기 (D203).
숨긴 파일·폴더가 보이고 숨긴 파일은 보기만, Ctrl+C 한 것을 Windows 가 읽는다(PowerShell Get-Clipboard -Format FileDropList — 탐색기와 같은 클립보드),
Windows 가 놓은 파일 목록(Set-Clipboard -Path — 탐색기의 복사와 같은 모양)을 Ctrl+V 로 붙인다, 겹치면 '- 복사본'.
  python tools/real/real107.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real107-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False, 'files_open': 'folder'}), encoding='utf-8')
proj = base / '사업'
(proj / '자료').mkdir(parents=True)
(proj / '.git').mkdir()
(proj / '보고서.md').write_text('# 보고서\n\n글\n', encoding='utf-8', newline='\n')
(proj / '.env').write_text('KEY=real-test\n', encoding='utf-8')
(proj / '.git' / 'HEAD').write_text('ref\n', encoding='utf-8')
outside = base / '받은 자료'
outside.mkdir()
(outside / '계획서.docx').write_bytes(b'PK\x03\x04 docx')
(outside / '보고서.md').write_text('# 밖\n', encoding='utf-8')

ROWS = "() => [...document.querySelectorAll('#lec-folder-list .row')].map((r) => r.dataset.path)"
VIEW = "() => import('/static/js/store.js').then(({ S }) => S.view && S.view.type + ':' + S.view.path)"


def ps(cmd):
    full = '[Console]::OutputEncoding = [Text.Encoding]::UTF8; ' + cmd   # 한국어 Windows 의 기본은 CP949
    return (subprocess.run(['powershell', '-NoProfile', '-Command', full], capture_output=True, text=True, encoding='utf-8', errors='replace').stdout or '').strip()


proc = None
try:
    with sync_playwright() as p:
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b = None
        for _ in range(120):
            try:
                b = p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp}')
                break
            except Exception:   # noqa: BLE001
                time.sleep(0.5)
        page = R.wait(lambda: R.app_page(b), 60)
        page.wait_for_selector('#lec-folder-list .row', state='attached', timeout=40000)
        page.wait_for_timeout(1500)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))

        print("['폴더' 묶음 — 숨긴 것]")
        R.wait(lambda: '.env' in page.evaluate(ROWS), 15)
        R.check('.env · .git 이 보인다', {'.env', '.git'} <= set(page.evaluate(ROWS)), page.evaluate(ROWS))
        page.click('#lec-folder-list .row[data-path=".env"]')
        R.wait(lambda: page.evaluate(VIEW) == 'code:.env' and 'real-test' in page.inner_text('#lec-view'), 15)
        R.check('숨긴 파일을 코드 화면에서 본다 (창 모드의 토큰으로)', 'real-test' in page.inner_text('#lec-view'), page.evaluate(VIEW))

        print('[Lectern → Windows 클립보드]')
        page.click('#lec-folder-list .row[data-path="보고서.md"]')
        page.click('#lec-folder-list .row[data-path=".env"]', modifiers=['Control'])
        page.focus('#lec-folder-list .row[data-path=".env"]')
        page.keyboard.press('Control+c')
        R.wait(lambda: '.env' in ps('Get-Clipboard -Format FileDropList | ForEach-Object { $_.Name }'), 10)
        got = ps('Get-Clipboard -Format FileDropList | ForEach-Object { $_.FullName }').splitlines()
        R.check('Windows 가 읽는 파일 목록 — 보고서.md · .env 의 전체 경로', sorted(Path(x).name for x in got) == ['.env', '보고서.md'] and all(str(proj) in x for x in got), got)

        print('[Windows 클립보드 → Lectern]')
        ps(f"Set-Clipboard -Path '{outside / '계획서.docx'}','{outside / '보고서.md'}'")
        page.click('#lec-folder-list .row[data-path="자료"]')
        page.keyboard.press('Control+v')
        R.wait(lambda: (proj / '자료' / '계획서.docx').exists() and (proj / '자료' / '보고서.md').exists(), 20)
        R.check('Set-Clipboard -Path 로 놓은 두 파일이 자료 폴더에', (proj / '자료' / '계획서.docx').exists() and (proj / '자료' / '보고서.md').exists(), sorted(x.name for x in (proj / '자료').iterdir()))
        page.click('#lec-folder-list .row[data-path="보고서.md"]')
        page.keyboard.press('Control+v')
        R.wait(lambda: len(list(proj.glob('보고서 - *.md'))) == 1, 20)
        R.check("맨 위에 다시 붙이면 '보고서 - 복사본.md' — 원래 것은 그대로", len(list(proj.glob('보고서 - *.md'))) == 1 and (proj / '보고서.md').read_text(encoding='utf-8') == '# 보고서\n\n글\n',
                sorted(x.name for x in proj.iterdir()))
        R.check('원본은 그대로', (outside / '계획서.docx').exists())
        R.check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    R.fails.append('예외')
finally:
    if proc:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
    time.sleep(1)
    shutil.rmtree(base, ignore_errors=True)
print(f'\n{R.count}개 중 실패 {len(R.fails)}개', R.fails)
