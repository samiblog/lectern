"""그림 보기 (D209) — 그림 파일을 한 번 누르면 Lectern 의 문서 탭에서 본다 (보기만).
- '자료 → 그림' · '자료 → 전체' · '폴더' 묶음 · 문서 속 링크에서 누르면 그림 보기 — 칸 폭에 맞춤, 그림·단추를 누르면 실제 크기 ↔ 맞춤.
- 머리줄·상태줄에 해상도·크기. 두 번 누르면 기본 앱 (/api/open-external). SVG 도 (그 안의 스크립트는 돌지 않는다).
- 깨진 그림은 알림과 '기본 앱으로 열기'. 편집 키는 막는다. 밖에서 바뀌면 다시 그린다. 숨긴 그림('폴더' 묶음)도 본다."""
import base64
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

# 3×2 빨강 PNG, 5×4 파랑 PNG (작은 그림을 바이트로)
RED = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAMAAAACCAIAAAASFvFNAAAAEElEQVR4nGO4IycHQQxwFgBGKAaROP7e7QAAAABJRU5ErkJggg==')
BLUE = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAUAAAAECAIAAADJUWIXAAAAEUlEQVR4nGOQs7mDjBhI5AMA+IYYOV6hXqoAAAAASUVORK5CYII=')
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60"><rect width="120" height="60" fill="#2a6"/>'
       '<script>window.parent.__svgRan = 1</script><text x="10" y="35">도표</text></svg>')

base = Path(tempfile.mkdtemp(prefix='lec-imageview-'))
proj = base / '과제'
(proj / '그림').mkdir(parents=True)
(proj / '그림' / '빨강.png').write_bytes(RED)
(proj / '그림' / '도표.svg').write_text(SVG, encoding='utf-8')
(proj / '그림' / '깨짐.png').write_bytes(b'not a png at all')
(proj / '그림' / '스캔.tif').write_bytes(bytes([73, 73, 42, 0]) + bytes(60))   # 화면이 그리지 못하는 그림 (TIFF) — 기본 앱으로
(proj / '메모.txt').write_text('그림이 아닌 자료\n', encoding='utf-8')   # '그림' 하위 묶음이 '전체' 와 같지 않게
(proj / '.숨김').mkdir()
(proj / '.숨김' / '몰래.png').write_bytes(BLUE)
(proj / '보고서.md').write_text('# 보고서\n\n[빨강 그림](그림/빨강.png)\n', encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')

VIEW = "() => import('/static/js/store.js').then(({ S }) => S.view && S.view.type + ':' + S.view.path)"
IMG = """() => { const i = document.querySelector('#lec-view.image-view .iv-img'); return i && i.complete ? { w: i.naturalWidth, h: i.naturalHeight, shown: Math.round(i.getBoundingClientRect().width), actual: document.querySelector('#lec-view').classList.contains('actual') } : null; }"""
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"

server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1300, 'height': 850})
        errors, opened = [], []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.on('request', lambda r: opened.append(json.loads(r.post_data or '{}').get('path')) if r.url.endswith('/api/open-external') else None)
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)

        print("['자료 → 그림' 에서 누르기]")
        page.click('#lec-others-head')
        page.wait_for_selector('#lec-others .kind-head[data-kind="image"]', timeout=10000)
        page.click('#lec-others .kind-head[data-kind="image"]')
        page.click('#lec-others-list .row[data-path="그림/빨강.png"]')
        got = until(page, lambda: page.evaluate(IMG))
        check('한 번 누르면 그림 보기 — 3×2', page.evaluate(VIEW) == 'code:그림/빨강.png' and got and (got['w'], got['h']) == (3, 2), (page.evaluate(VIEW), got))
        check('머리줄에 해상도', '3×2' in page.inner_text('#lec-view .cv-sub'), page.inner_text('#lec-view .cv-sub'))
        check('상태줄에 해상도·크기', until(page, lambda: '3×2' in page.inner_text('#lec-status')), page.inner_text('#lec-status')[:120])
        check('처음은 칸 폭에 맞춤 (작은 그림은 그대로 3px)', got and not got['actual'] and got['shown'] <= 5, got)
        page.click('#lec-view .iv-img')
        check('그림을 누르면 실제 크기 표시', until(page, lambda: (page.evaluate(IMG) or {}).get('actual')), page.evaluate(IMG))
        check("단추 글은 '창에 맞춤'", page.inner_text('#lec-view .iv-fit') == '창에 맞춤')
        page.click('#lec-view .iv-fit')
        check('단추로 다시 맞춤', until(page, lambda: not (page.evaluate(IMG) or {}).get('actual')))
        page.dblclick('#lec-others-list .row[data-path="그림/빨강.png"]')
        check('두 번 누르면 기본 앱으로', until(page, lambda: '그림/빨강.png' in opened), opened)
        page.click('#lec-view h1, #lec-view .cv-title')
        page.keyboard.press('Control+e')
        check('편집 키는 막는다', until(page, lambda: '그림은 보기만' in page.evaluate(TOAST)), page.evaluate(TOAST))

        before = page.evaluate(VIEW)
        page.click('#lec-others-list .row[data-path="그림/스캔.tif"]')
        page.wait_for_timeout(500)
        check('tif 는 한 번 눌러도 Lectern 에서 그리지 않는다 (화면이 못 그리는 형식)', page.evaluate(VIEW) == before, page.evaluate(VIEW))
        page.dblclick('#lec-others-list .row[data-path="그림/스캔.tif"]')
        check('— 두 번 누르면 기본 앱으로', until(page, lambda: '그림/스캔.tif' in opened), opened)
        print('[SVG · 깨진 그림]')
        page.evaluate("() => { window.__svgRan = 0; }")
        page.click('#lec-others-list .row[data-path="그림/도표.svg"]')
        got = until(page, lambda: (x := page.evaluate(IMG)) and x['w'] == 120 and x)
        check('SVG — 120×60 으로 그린다', got and (got['w'], got['h']) == (120, 60), got)
        check('SVG 안의 스크립트는 돌지 않는다', page.evaluate('() => window.__svgRan') == 0)
        page.click('#lec-others-list .row[data-path="그림/깨짐.png"]')
        check('깨진 그림 — 알림과 기본 앱으로 열기', until(page, lambda: '그림을 그리지 못했습니다' in page.inner_text('#lec-view') and page.locator('#lec-view .cv-editor').count() == 1),
              page.inner_text('#lec-view')[:120])

        print('[밖에서 바뀌면]')
        page.click('#lec-others-list .row[data-path="그림/빨강.png"]')
        until(page, lambda: (page.evaluate(IMG) or {}).get('w') == 3)
        (proj / '그림' / '빨강.png').write_bytes(BLUE)
        check('다시 그린다 — 5×4', until(page, lambda: (page.evaluate(IMG) or {}).get('w') == 5, ms=12000), page.evaluate(IMG))

        print('[문서 속 링크 · 폴더 묶음 · 숨긴 그림]')
        page.click('#lec-docs-head')
        page.click('#lec-tree .row[data-doc="보고서.md"]')
        page.wait_for_selector('#lec-view a', timeout=10000)
        page.locator('#lec-view a', has_text='빨강 그림').click()
        check('문서 속 그림 링크를 누르면 그림 보기', until(page, lambda: page.evaluate(VIEW) == 'code:그림/빨강.png' and page.evaluate(IMG)), page.evaluate(VIEW))
        page.click('#lec-folder-head')
        page.wait_for_selector('#lec-folder-list .row[data-path=".숨김"]', timeout=10000)
        page.click('#lec-folder-list .row[data-path=".숨김"] [data-toggle]')
        page.wait_for_selector('#lec-folder-list .row[data-path=".숨김/몰래.png"]', timeout=10000)
        page.click('#lec-folder-list .row[data-path=".숨김/몰래.png"]')
        check("'폴더' 묶음의 숨긴 그림도 본다 (토큰을 붙인 주소)", until(page, lambda: (page.evaluate(IMG) or {}).get('w') == 5), page.evaluate(IMG))
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
