"""0.94.0 — 빌드본·설치본 실제 창(WebView2)에서 표: 열 너비 자동(좁게 감긴 칸·넘침 없음), 창 크기를 바꾸면 다시,
설정 '표 칸 맞춤' 보고서식(머리행·짧은 열 가운데)이 다시 실행해도 그대로, 우클릭 '이 열 맞춤 표시 지우기'는 구분 줄의 그 칸만.
시험용 설정 폴더·개인 폴더 — 실제 설정과 ~/.claude 는 건드리지 않는다.
  python real094t.py --exe <Lectern.exe>"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real094t-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
os.environ['LECTERN_HOME'] = str(base / 'home')
proj = base / '보고서'
proj.mkdir(parents=True)
DOC = '''# 점검 보고

| 구분 | 상태 | 근거 자료 | 설명 | 담당 | 주기 |
|---|---|---|---|---|---|
| 구리 | 진행 | 전력망 투자 계획 | 공급 충격은 가격에 바로 반영되므로 소식이 나오면 그날 안에 추정치를 고친다. 추정 근거는 출처와 함께 남기고 같은 소식이 여러 곳에서 다르게 나오면 가장 이른 원문을 기준으로 삼는다 | 수급팀 검토 | 매월 말 |
| 니켈 | 보류 | 배터리 수요 전망 | 인도네시아 공급이 늘어 가격이 눌린다 | 리서치 정리 | 분기마다 |

| 항목 | 기준 | 비고 |
|---|:---:|---|
| 재고 | 30일 | 평년 기준 |
'''
(proj / '표.md').write_text(DOC, encoding='utf-8')
STORE = "import('/static/js/store.js')"
TABLES = """() => [...document.querySelectorAll('#lec-view .table-wrap > table')].map((t) => {
  const em = parseFloat(getComputedStyle(t).fontSize);
  const lines = (c) => { const lh = parseFloat(getComputedStyle(c).lineHeight) || em * 1.5; const r = document.createRange(); r.selectNodeContents(c); return Math.round(r.getBoundingClientRect().height / lh); };
  const pad = (c) => { const s = getComputedStyle(c); return parseFloat(s.paddingLeft) + parseFloat(s.paddingRight); };
  const cells = [...t.rows].flatMap((r) => [...r.cells]);
  const wrap = t.parentElement;
  return { cls: t.className, widths: [...t.rows[0].cells].map((c) => Math.round(c.getBoundingClientRect().width)), narrow: cells.filter((c) => lines(c) >= 3 && c.getBoundingClientRect().width - pad(c) < em * 2.5).length,
    over: wrap.scrollWidth > wrap.clientWidth + 1, maxLines: Math.max(...cells.map(lines)),
    align: [...t.rows[0].cells].map((h, i) => [getComputedStyle(h).textAlign, getComputedStyle(t.rows[1].cells[i]).textAlign]) };
})"""


def connect(p, cdp):
    b = None
    for _ in range(120):
        try:
            b = p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp}')
            break
        except Exception:
            time.sleep(0.5)
    page = R.wait(lambda: R.app_page(b), 60)
    page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=40000)
    page.wait_for_timeout(1500)
    return b, page


def open_doc(page):
    page.evaluate(f"() => {STORE}.then((m) => m.emit('open', {{ type: 'doc', path: '표.md' }}))")
    page.wait_for_selector('#lec-view h1', timeout=15000)
    page.wait_for_timeout(900)


proc = None
try:
    with sync_playwright() as p:
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b, page = connect(p, cdp)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('dialog', lambda d: d.accept())
        version = page.evaluate("() => document.querySelector('meta[name=lec-version]')?.content || ''")
        R.check(f'판 — {version}', version == R.REPO.joinpath('lectern/__init__.py').read_text(encoding='utf-8').split("__version__ = '")[1].split("'")[0], version)
        open_doc(page)
        tables = lambda: page.evaluate(TABLES)  # noqa: E731

        print('[열 너비 자동]')
        t = tables()[0]
        R.check('본문 표 — 세로로 감긴 칸·옆 넘침 없음, 긴 설명(120자)이 가장 넓은 열에서 8줄 안', t['narrow'] == 0 and not t['over'] and t['maxLines'] <= 8
                and t['widths'][3] == max(t['widths']), t)
        R.check('— 모든 열 맞추기나 낱말 지키기', 'lec-fit' in t['cls'] or 'lec-words' in t['cls'], t['cls'])
        page.keyboard.press('Control+b')   # 사이드바 감추기 — 본문이 넓어진다
        R.check('사이드바를 감추면 다시 맞춘다 — 여전히 감긴 칸·넘침 없음', R.wait(lambda: tables()[0]['narrow'] == 0 and not tables()[0]['over'], 5), tables()[0])
        page.keyboard.press('Control+b')
        page.wait_for_timeout(600)

        print('[표 칸 맞춤 — 보고서식]')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        page.locator('#lec-settings .set-nav button[data-set="view"]').click()
        page.locator('#lec-settings label:has(input[name="table_align"][value="report"])').click()
        page.keyboard.press('Escape')
        R.check('보고서식 — 머리행 가운데, 구분·상태 가운데, 설명은 왼쪽', R.wait(lambda: 'lec-report' in tables()[0]['cls'], 5)
                and tables()[0]['align'][0] == ['center', 'center'] and tables()[0]['align'][1][1] == 'center' and tables()[0]['align'][3][1] == 'left', tables()[0]['align'])
        R.check("원문 맞춤 표시(':---:')는 그대로", tables()[1]['align'][1][1] == 'center', tables()[1]['align'])
        R.check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
        time.sleep(2)

        print('[다시 실행]')
        proc, cdp = R.launch(proj, config)
        R.CONN.update(cdp=cdp)
        b, page = connect(p, cdp)
        tables = lambda: page.evaluate(TABLES)  # noqa: E731
        open_doc(page)
        R.check('다시 실행해도 보고서식', 'lec-report' in tables()[0]['cls'] and tables()[0]['align'][0] == ['center', 'center'], tables()[0])

        print('[우클릭 — 이 열 맞춤 표시 지우기]')
        page.locator('#lec-view .table-wrap').nth(1).locator('tbody td').nth(1).click(button='right')
        page.wait_for_selector('#lec-menu button', timeout=4000)
        page.locator('#lec-menu button', has_text='이 열 맞춤 표시 지우기').click()
        sep = lambda: (proj / '표.md').read_text(encoding='utf-8').split('\n')[8]  # noqa: E731
        R.check('구분 줄의 그 칸만 — 나머지 줄은 그대로', R.wait(lambda: [x.strip() for x in sep().strip('|').split('|')] == ['---'] * 3, 6)
                and (proj / '표.md').read_text(encoding='utf-8').replace(sep(), '|---|:---:|---|') == DOC, sep())
        R.check('— 짧은 열이라 보고서식대로 가운데', R.wait(lambda: tables()[1]['align'][1][1] == 'center', 5), tables()[1]['align'])
        b.close()
except Exception:
    traceback.print_exc()
    R.fails.append('예외')
finally:
    if proc:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
    time.sleep(1)
    shutil.rmtree(base, ignore_errors=True)
print(f'\n{R.count}개 중 실패 {len(R.fails)}개', R.fails)
