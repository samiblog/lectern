"""0.99.0 — 실제 창(WebView2)에서: 슬라이드의 넘침 맞춤(D188) — 넘친 두 카드를 같은 배율로 줄이고 넘침 표시 없이 알림만,
글 아래 차트는 그림을 줄이지 않고 그 높이로 다시 그려 범례가 14pt 이상, 긴 코드는 줄을 접는다, 칸에 줄을 더하면 줄이고
파일이 바깥에서 줄면 원래 크기로, 슬라이드 창(새 창에서 열기)·발표·인쇄 모양에서도 같은 크기.
  python tools/real/real099.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real099-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
proj = base / '연구'
proj.mkdir(parents=True)
F = '```'
bul = lambda n, w: '\n'.join(f'- {w} ({i + 1})' for i in range(n))  # noqa: E731
VL = ('{"width": 600, "height": 360, "data": {"values": [{"m": "7월", "k": "LME", "v": 9100}, {"m": "8월", "k": "LME", "v": 9350}, '
      '{"m": "7월", "k": "SHFE", "v": 9000}, {"m": "8월", "k": "SHFE", "v": 9200}]}, "mark": "line", '
      '"encoding": {"x": {"field": "m", "type": "ordinal", "title": "월"}, "y": {"field": "v", "type": "quantitative", "title": "USD/t", "scale": {"zero": false}}, '
      '"color": {"field": "k", "type": "nominal", "title": "거래소"}}}')


def deck(n_a):
    return f"""---
marp: true
---

## 표지

글

---

<!-- layout: two -->

## 판단

::: a card
### 성과
{bul(n_a, '시장 점유율이 전년 대비 늘었고 신규 고객 유입이 이어졌다')}
:::

::: b card
### 과제
{bul(6, '원가 상승 압력이 커서 하반기 수익성 관리가 필요하다')}
:::

---

## 가격

{bul(5, '설명 글이 위에 있고 차트가 아래에 이어지는 흔한 모양의 장이다')}

{F}vega-lite
{VL}
{F}

---

<!-- layout: two -->

## 코드

::: a
글
:::

::: b
{F}python
result = model.fit(train_features_with_lagged_variables, train_target_quarterly_growth, epochs=200, verbose=0)
{F}
:::
"""


DOC = proj / '발표.md'
DOC.write_text(deck(8), encoding='utf-8', newline='\n')
INFO = """(n) => { const w = document.querySelectorAll('#lec-view > .lec-slide-wrap')[n]; const s = w.querySelector('.lec-slide');
  const px = (q) => { const e = s.querySelector(q); return e ? parseFloat(getComputedStyle(e).fontSize) : 0; };
  return { fitted: JSON.parse(w.dataset.fitted || '[]').map((x) => x.text), issues: JSON.parse(w.dataset.issues || '[]').map((x) => x.text),
    a: px('.lec-cell[data-cell=a] li'), b: px('.lec-cell[data-cell=b] li'), badge: !!w.querySelector('.lec-slide-frame').dataset.over }; }"""
CHART = """() => { const svg = document.querySelectorAll('#lec-view .lec-slide')[2]?.querySelector('pre.lec-chart > svg'); if (!svg) return 0;
  const s = svg.closest('.lec-slide'); const scale = s.getBoundingClientRect().width / s.offsetWidth || 1;
  const vb = svg.getAttribute('viewBox').split(/[\\s,]+/).map(Number); const r = svg.getBoundingClientRect();
  const k = Math.min(r.width / scale / vb[2], r.height / scale / vb[3]);
  return Math.round(Math.min(...[...svg.querySelectorAll('text')].filter((t) => t.textContent.trim()).map((t) => parseFloat(getComputedStyle(t).fontSize))) * k * 0.75 * 10) / 10; }"""


def connect(p, cdp):
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
    return b, page


proc = None
try:
    with sync_playwright() as p:
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b, page = connect(p, cdp)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        version = page.evaluate("() => document.querySelector('meta[name=lec-version]')?.content || ''")
        R.check(f'판 {R.VERSION}', version == R.VERSION or not version, version)

        print('[넘친 두 카드 (D188)]')
        R.check('발표를 연다', R.open_doc(page, '발표.md'))
        got = R.wait(lambda: (lambda x: x if x['fitted'] else None)(page.evaluate(INFO, 1)), 15) or page.evaluate(INFO, 1)
        R.check('두 카드를 같은 배율로 줄여 맞춘다 — 알림만, 넘침 없음', any('칸 a·b' in x for x in got['fitted']) and not got['issues'] and not got['badge'] and got['a'] == got['b'], got)
        R.check('— 바닥(14pt) 위', got['a'] * 0.75 >= 13.95, got)
        shrunk = got['a']
        pt = R.wait(lambda: (lambda v: v if v >= 14 else None)(page.evaluate(CHART)), 15) or page.evaluate(CHART)
        R.check('글 아래 차트는 그 높이로 다시 그려 글자 14pt 이상', pt >= 14, pt)
        code = page.evaluate(INFO, 3)
        R.check('긴 코드는 줄을 접는다', any('코드 줄을 접었습니다' in x for x in code['fitted']) and not code['issues'], code)
        R.check("상태줄 — '줄인 글 2장' (차트 장은 글을 줄이지 않았다)", page.locator('#lec-st-check').inner_text().strip() == '줄인 글 2장', page.locator('#lec-st-check').inner_text())

        print('[바깥에서 파일이 바뀐다 — AI 가 줄을 줄인다]')
        DOC.write_text(deck(4), encoding='utf-8', newline='\n')
        back = R.wait(lambda: (lambda x: x if not x['fitted'] and page.locator('#lec-view .lec-slide').nth(1).locator('.lec-cell[data-cell=a] li').count() == 4 else None)(page.evaluate(INFO, 1)), 20)
        R.check('다시 그려 원래 크기 (18pt)', bool(back) and abs(back['a'] * 0.75 - 18) < 0.1 and back['a'] == back['b'], back or page.evaluate(INFO, 1))

        print('[사람이 줄을 더한다]')
        for k in range(4):
            page.locator('#lec-view .lec-cell[data-cell=a] li').last.click()
            page.wait_for_timeout(300)
            page.keyboard.press('Shift+Enter')
            page.wait_for_timeout(500)
            page.keyboard.type(f'회의에서 덧붙인 판단 근거로 재고와 가격의 관계를 한 줄 더 적는다 {k + 1}')
            page.keyboard.press('Enter')
            page.wait_for_timeout(800)
            page.keyboard.press('Escape')
            page.wait_for_timeout(600)
        R.check('원문에 네 줄이 더해졌다', DOC.read_text(encoding='utf-8').count('- 회의에서 덧붙인 판단 근거로') == 4, DOC.read_text(encoding='utf-8')[100:700])
        got = R.wait(lambda: (lambda x: x if x['fitted'] else None)(page.evaluate(INFO, 1)), 15) or page.evaluate(INFO, 1)
        R.check('넘치자 줄여 맞춘다', bool(got['fitted']) and not got['issues'], got)
        shrunk = got['a']

        print('[발표·인쇄 모양]')
        page.evaluate("() => import('/static/js/present.js').then(({ startPresent }) => startPresent(undefined, 1))")
        page.wait_for_timeout(600)
        shown = page.evaluate("() => { const e = document.querySelector('.pr-stage .lec-cell[data-cell=a] li'); return e ? parseFloat(getComputedStyle(e).fontSize) : 0; }")
        R.check('발표에서도 같은 크기', shown == shrunk, (shown, shrunk))
        page.keyboard.press('Escape')
        page.wait_for_timeout(400)
        try:
            page.emulate_media(media='print')
            page.wait_for_timeout(400)
            printed = page.evaluate(INFO, 1)['a']
            R.check('인쇄 모양에서도 같은 크기', printed == shrunk, (printed, shrunk))
        finally:
            page.emulate_media(media='screen')

        print('[슬라이드 창 (새 창에서 열기)]')
        page.locator('#lec-tree .row.file[data-doc="발표.md"]').click(button='right')
        page.wait_for_selector('#lec-menu button', timeout=5000)
        page.locator('#lec-menu button', has_text='새 창에서 열기').first.click()
        win = R.new_window(b, None, 30)
        R.check('슬라이드 창이 뜬다', win is not None)
        if win:
            R.wait(lambda: win.evaluate("() => document.querySelectorAll('#lec-view .lec-slide').length === 4"), 30)
            solo = R.wait(lambda: (lambda x: x if x['fitted'] else None)(win.evaluate(INFO, 1)), 20) or win.evaluate(INFO, 1)
            R.check('슬라이드 창에서도 같은 크기·알림', solo['a'] == shrunk and bool(solo['fitted']) and not solo['issues'], (solo, shrunk))
            R.wait(lambda: win.evaluate(CHART) >= 14, 15)
            R.check('슬라이드 창의 차트도 14pt 이상', win.evaluate(CHART) >= 14, win.evaluate(CHART))
            try:
                win.keyboard.press('Control+w')
            except Exception:   # noqa: BLE001
                pass
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
