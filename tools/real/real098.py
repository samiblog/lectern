"""0.98.0 — 실제 창(WebView2)에서: 전시물(D184 — 캡션은 몸체의 가운데에 본문보다 크게, 주·자료는 몸체의 왼쪽 끝에서, 슬라이드 칸도),
사용설명서 창의 Ctrl+B 는 설명서의 차례(D186 — 메인 창의 사이드바 설정은 그대로), 강조글 ↔ 박스글 바꾸기(D185 — 우클릭).
  python tools/real/real098.py [--exe <Lectern.exe>]   (없으면 소스의 app.py)"""
import json
import re
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

VERSION = re.search(r"__version__ = '([^']+)'", (R.REPO / 'lectern' / '__init__.py').read_text(encoding='utf-8'))[1]
base = Path(tempfile.mkdtemp(prefix='lec-real098-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
proj = base / '연구'
proj.mkdir(parents=True)
FENCE = '```'
(proj / '보고서.md').write_text(f"""# 시장 점검

본문 문단 — 글자 크기를 견준다.

표 1. 분기별 금속 가격과 재고

| 분기 | 구리 (USD/t) | 알루미늄 (USD/t) | 니켈 (USD/t) | 재고 설명 |
|---|---:|---:|---:|---|
| 2026 2분기 | 9,410 | 2,480 | 16,200 | 거래소 재고가 줄었다 |
| 2026 3분기 | 9,820 | 2,530 | 15,900 | 창고 재고가 늘었다 |

주: 2026년 3분기는 잠정치다.
자료: LME (2026)

그림 1. 흐름

{FENCE}mermaid
flowchart LR
  A["원료"] --> B["가공"] --> C["출하"]
{FENCE}

출처: 사내 자료

> [!TIP]
> 강조글의 글
""", encoding='utf-8')
(proj / '발표.md').write_text("""---
marp: true
---

# 표지

---

## 매출

::: a
**10월 매출 (억 원)**

| 부문 | 매출 |
|---|---:|
| 택배 | 12,600 |
| 창고 | 3,100 |

자료: 가상 협회 (2026)
:::
""", encoding='utf-8')

BOXES = """() => [...document.querySelectorAll('#lec-view .lec-exhibit')].map((box) => {
  const r = (el) => el.getBoundingClientRect();
  const cap = box.querySelector(':scope > .lec-caption');
  const body = box.querySelector(':scope > .table-wrap, :scope > pre svg');
  const src = box.querySelector(':scope > .lec-source');
  return { cap: cap?.textContent.trim(), capMid: Math.round(r(cap).left + r(cap).width / 2), bodyMid: Math.round(r(body).left + r(body).width / 2),
    bodyLeft: Math.round(r(body).left), srcLeft: src ? Math.round(r(src).left) : null, srcLines: src ? Math.round(r(src).height / parseFloat(getComputedStyle(src).lineHeight)) : 0,
    capPx: parseFloat(getComputedStyle(cap).fontSize), align: [getComputedStyle(cap).textAlign, src && getComputedStyle(src).textAlign] }; })"""
NAV = "() => [!document.querySelector('#lec-help').hidden, getComputedStyle(document.querySelector('#lec-help .help-nav')).display !== 'none', !document.querySelector('#lec-help-navon').hidden]"


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


def side_saved():
    return json.loads((config / 'config.json').read_text(encoding='utf-8')).get('sidebar_visible', True)


proc = None
try:
    with sync_playwright() as p:
        proc, cdp = R.launch(proj, config)
        R.CONN.update(pw=p, cdp=cdp)
        b, page = connect(p, cdp)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        version = page.evaluate("() => document.querySelector('meta[name=lec-version]')?.content || ''")
        R.check(f'판 {VERSION}', version == VERSION or not version, version)

        print('[전시물 — 문서 (D184)]')
        R.check('보고서를 연다', R.open_doc(page, '보고서.md'))
        boxes = R.wait(lambda: page.evaluate(BOXES) if page.locator('#lec-view .lec-exhibit pre svg').count() else None, 20) or page.evaluate(BOXES)
        body = page.evaluate("parseFloat(getComputedStyle(document.querySelector('#lec-view > p')).fontSize)")
        R.check('표·다이어그램이 캡션째 묶인다', [x['cap'] for x in boxes] == ['표 1. 분기별 금속 가격과 재고', '그림 1. 흐름'], boxes)
        for x in boxes:
            R.check(f"— '{x['cap']}': 캡션은 몸체의 가운데에 본문보다 크게", x['align'][0] == 'center' and abs(x['capMid'] - x['bodyMid']) <= 2 and x['capPx'] > body * 1.04, (x, body))
            R.check('— 주·자료 줄은 몸체의 왼쪽 끝에서 왼쪽 정렬', x['align'][1] == 'left' and abs(x['srcLeft'] - x['bodyLeft']) <= 3, x)
        R.check("— 이어 쓴 '주:'·'자료:' 는 두 줄", boxes[0]['srcLines'] == 2, boxes[0])

        print('[강조글 ↔ 박스글 (D185)]')
        page.locator('#lec-view .markdown-alert p, #lec-view blockquote p').last.click(button='right')
        page.wait_for_selector('#lec-menu button', timeout=5000)
        page.locator('#lec-menu button', has_text='박스글로 바꾸기').first.click()
        doc = lambda: (proj / '보고서.md').read_text(encoding='utf-8')  # noqa: E731
        R.check('강조글의 우클릭 — 박스글로 바꾸기', R.wait(lambda: '<!-- box -->\n**박스 1. 제목**\n\n강조글의 글\n<!-- /box -->' in doc(), 10), doc()[-120:])
        R.wait(lambda: page.locator('#lec-view aside.lec-textbox').count() == 1, 10)
        page.wait_for_timeout(500)
        page.locator('#lec-view aside.lec-textbox p').last.click(button='right')
        page.wait_for_selector('#lec-menu button', timeout=5000)
        page.locator('#lec-menu button', has_text='강조글로 바꾸기').first.click()
        R.check('박스글의 우클릭 — 강조글로 바꾸기 (자리 글 제목은 뺀다)', R.wait(lambda: doc().rstrip().endswith('> [!NOTE]\n> 강조글의 글'), 10), doc()[-120:])

        print('[전시물 — 슬라이드의 칸]')
        R.check('발표를 연다', R.open_doc(page, '발표.md'))
        sl = R.wait(lambda: page.evaluate("""() => { const box = document.querySelector('#lec-view .lec-cell .lec-exhibit'); if (!box) return null;
          const cap = box.querySelector('.lec-caption'), src = box.querySelector('.lec-source'), t = box.querySelector('table');
          const pt = (el) => Math.round(parseFloat(getComputedStyle(el).fontSize) * 0.75 * 10) / 10;
          return { cap: cap.textContent.trim(), align: [getComputedStyle(cap).textAlign, getComputedStyle(src).textAlign], capPt: pt(cap), srcPt: pt(src), tablePt: pt(t) }; }"""), 15)
        R.check('칸 안의 굵은 한 줄·표·자료 — 캡션은 가운데 본문의 1.1배, 자료는 왼쪽 표 글 크기',
                bool(sl) and sl['cap'] == '10월 매출 (억 원)' and sl['align'] == ['center', 'left'] and abs(sl['capPt'] - 19.8) < .3 and sl['srcPt'] == sl['tablePt'], sl)

        print('[사용설명서 창의 Ctrl+B (D186)]')
        side0 = side_saved()
        page.locator('#lec-content').focus()
        page.keyboard.press('F1')
        win = R.new_window(b, None, 30, key='help=1')
        R.check('F1 — 사용설명서 창', win is not None and R.wait(lambda: win.evaluate(NAV)[0], 30))
        if win:
            R.wait(lambda: win.locator('#lec-help-toc li.doc a').count() >= 50, 20)
            win.locator('#lec-help-scroll').focus()
            win.keyboard.press('Control+b')
            R.check('Ctrl+B — 차례를 감추고 왼쪽 위에 다시 보이는 단추', R.wait(lambda: win.evaluate(NAV) == [True, False, True], 5), win.evaluate(NAV))
            win.keyboard.press('Control+b')
            R.check('— 다시 Ctrl+B 면 차례가 보인다', R.wait(lambda: win.evaluate(NAV) == [True, True, False], 5), win.evaluate(NAV))
            win.locator('#lec-help-navoff').click()
            R.check('— 머리줄 단추로 감추고', R.wait(lambda: win.evaluate(NAV)[1] is False, 5))
            win.locator('#lec-help-navon').click()
            R.check('— 본문 왼쪽 위 단추로 다시', R.wait(lambda: win.evaluate(NAV)[1] is True, 5))
            R.check('메인 창의 사이드바 설정은 그대로', side_saved() == side0 and page.evaluate("import('/static/js/store.js').then((m) => m.S.config.sidebar_visible !== false)") == side0, (side0, side_saved()))
            win.locator('#lec-help-scroll').focus()
            try:
                win.keyboard.press('F1')
            except Exception:   # noqa: BLE001 — 키를 떼기 전에 창이 닫힌다
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
