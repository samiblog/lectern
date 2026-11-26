"""0.106.0 — 실제 창(WebView2)에서: 사이드바 '문서'의 하위 묶음 고르기와 오피스 묶음 (D202).
기본으로 Word·PowerPoint·Excel·CSV·한글(HWP) 이 보이고 업무·형광펜·할 일은 없다, csv·xlsx 는 한 번 누르면 표, 설정 창의 칸이 config.json 에 쓴다,
머리줄의 우클릭으로 켠다, 오피스 행의 Shift+→ 가 실제 셸에 '@경로' 를 넣는다 (Enter 없이), 목록의 md 문서는 파일 이름.
두 번 누르면 그 프로그램이 뜨는 것은 이 PC 의 Office·한글을 띄우므로 docs/TESTING.md 의 수동 점검이다.
  python tools/real/real106.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_sheet import make_xlsx  # noqa: E402

base = Path(tempfile.mkdtemp(prefix='lec-real106-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
proj = base / '사업'
(proj / '보고').mkdir(parents=True)
(proj / '자료').mkdir()
(proj / '보고서.md').write_text('# 2026년 사업 보고서\n\n- [ ] 표 고치기\n', encoding='utf-8', newline='\n')
(proj / '보고' / '계획서.docx').write_bytes(b'PK\x03\x04 word')
(proj / '보고' / '발표.pptx').write_bytes(b'PK\x03\x04 ppt')
(proj / '보고' / '공문.hwp').write_bytes(b'\xd0\xcf\x11\xe0 hwp')
(proj / '자료' / '표.csv').write_text('항목,금액\n인건비,100\n', encoding='utf-8')
make_xlsx(proj / '자료' / '예산.xlsx', sheets=[('값', '<row r="1"><c r="A1" t="s"><v>0</v></c></row><row r="2"><c r="A2"><v>2026</v></c></row>', None)], shared=('연도',))

KINDS = "() => [...document.querySelectorAll('#lec-docs .kind-head')].map((b) => b.dataset.kind)"
VIEW = "() => import('/static/js/store.js').then(({ S }) => S.view && S.view.type + ':' + S.view.path)"
TEXT = """(n) => import('/static/js/store.js').then((m) => { const term = (m.S.tab.terms || []).find((x) => x.n === n); if (!term?.xterm) return '';
  const b = term.xterm.buffer.active; const out = []; for (let i = 0; i < b.length; i++) out.push(b.getLine(i).translateToString(true)); return out.join(''); })"""

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
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=40000)
        page.wait_for_timeout(1500)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))

        print('[기본 하위 묶음]')
        R.wait(lambda: 'word' in page.evaluate(KINDS), 15)
        R.check('전체·Word·PowerPoint·Excel·CSV·한글(HWP) — 업무·형광펜·할 일은 없다', page.evaluate(KINDS) == ['all', 'word', 'ppt', 'excel', 'hwp'], page.evaluate(KINDS))
        R.check('목록의 md 문서는 파일 이름', page.locator('#lec-tree .row[data-doc="보고서.md"] .label').inner_text() == '보고서.md')

        print('[Excel·CSV — 한 번 누르면 표]')
        page.click('#lec-docs .kind-head[data-kind="excel"]')
        page.click('#lec-tree .row[data-file="자료/표.csv"]')
        R.wait(lambda: page.evaluate(VIEW) == 'code:자료/표.csv' and '인건비' in page.inner_text('#lec-view'), 15)
        R.check('csv 를 누르면 표', page.evaluate(VIEW) == 'code:자료/표.csv' and '인건비' in page.inner_text('#lec-view'), page.evaluate(VIEW))
        page.click('#lec-tree .row[data-file="자료/예산.xlsx"]')
        R.wait(lambda: page.evaluate(VIEW) == 'code:자료/예산.xlsx' and '2026' in page.inner_text('#lec-view'), 15)
        R.check('xlsx 를 누르면 엑셀 보기', page.evaluate(VIEW) == 'code:자료/예산.xlsx' and '2026' in page.inner_text('#lec-view'), page.evaluate(VIEW))

        print('[Shift+→ — 실제 셸]')
        page.click('#lec-docs .kind-head[data-kind="word"]')
        page.focus('#lec-tree .row[data-file="보고/계획서.docx"]')
        page.keyboard.press('Shift+ArrowRight')
        R.wait(lambda: '@보고/계획서.docx' in page.evaluate(TEXT, 0), 60)
        got = page.evaluate(TEXT, 0)
        R.check("Word 행의 Shift+→ — '@보고/계획서.docx' 가 실제 셸에, Enter 없이", '@보고/계획서.docx' in got and got.count('PS ') == 1, got[-160:])

        print('[설정 창 · 머리줄 우클릭]')
        page.click('#lec-btn-settings')   # 초점이 터미널에 있으면 Ctrl+, 는 셸로 간다
        page.wait_for_selector('#lec-set-kinds input', timeout=10000)
        page.click('#lec-set-kinds input[data-kind="tasks"]')
        R.wait(lambda: json.loads((config / 'config.json').read_text(encoding='utf-8')).get('doc_kinds') == ['word', 'ppt', 'excel', 'hwp', 'tasks'], 10)
        R.check('설정 창에서 할 일을 켜면 config.json 에', json.loads((config / 'config.json').read_text(encoding='utf-8')).get('doc_kinds') == ['word', 'ppt', 'excel', 'hwp', 'tasks'])
        page.click('#lec-settings button:has-text("닫기")')
        R.wait(lambda: 'tasks' in page.evaluate(KINDS), 10)
        R.check('사이드바에 할 일', 'tasks' in page.evaluate(KINDS), page.evaluate(KINDS))
        page.click('#lec-docs .kind-head[data-kind="all"]', button='right')
        page.locator('#lec-menu').get_by_text('형광펜').click()
        R.wait(lambda: 'marks' in page.evaluate(KINDS), 10)
        R.check('머리줄 우클릭으로 형광펜을 켠다', 'marks' in page.evaluate(KINDS), page.evaluate(KINDS))
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
