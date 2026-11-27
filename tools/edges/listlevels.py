"""목록의 수준 (D210) — 하위 항목이 있는 목록의 맨 위 항목은 진하게·조금 크게, 묶음 사이를 띄우고, 셋째 수준부터 조금 작게.
- 글머리 글자 목록(□ ○ - ·, D192)과 Markdown 목록(- · 1.) 모두. 한 목록 안에서는 하위가 없는 맨 위 항목도 같게.
- 그대로인 것: 하위가 없는 목록·□ 만 있는 묶음, 할 일 목록, 인용·강조글 안, 표 칸, Lectern 슬라이드, GitHub 스타일 두 가지.
- 인쇄(PDF)도 진하게 — 묶음 사이는 조금 좁게. 'html로 저장' 의 글에도 같은 규칙. 내어쓰기(D191)는 굵어진 글자에 맞는다."""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

DOC = """# 구리 시장 점검

## 수요

□ 전기차·전력망 투자로 2026년 구리 수요는 3.1% 늘 전망이며 이 줄은 일부러 길게 써서 칸 폭을 넘겨 꺾이게 한다 — 꺾인 줄이 글머리 글자 뒤에 맞는지 본다
○ 전기차 한 대에 구리 83kg
- 충전 설비 포함
· 국제구리협회 추정
□ 공급은 빠듯
○ 칠레 생산 감소

## □ 만

□ 첫째 요점
□ 둘째 요점

## 가격

- LME 구리 가격은 톤당 9,350달러
  - 재고가 줄었다
    - 상하이 포함
      - 넷째 수준
        - 다섯째 수준
- 4분기는 범위 전망

## 나열

- 재고 자료의 출처를 맞춘다
- 다음 보고는 12월

## 할 일

- [ ] 자료 모으기
  - [ ] 기관별
- [ ] 정리

## 인용

> - 인용 속 맨 위
>   - 인용 속 둘째

> [!NOTE]
> - 강조글 속 맨 위
>   - 강조글 속 둘째
"""
SLIDES = """---
marp: true
---

# 슬라이드

- 맨 위
  - 둘째
"""

STYLE = """(sel) => { const e = document.querySelector('#lec-view ' + sel); if (!e) return null; const c = getComputedStyle(e);
  const body = parseFloat(getComputedStyle(document.querySelector('#lec-view')).fontSize);
  return { w: Number(c.fontWeight), r: Math.round(parseFloat(c.fontSize) / body * 1000) / 1000, gap: Math.round(parseFloat(c.marginTop) / parseFloat(c.fontSize) * 100) / 100 }; }"""
MARK = "(text) => { const e = [...document.querySelectorAll('#lec-view .lec-mark')].find((p) => p.textContent.includes(text)); if (!e) return null; const c = getComputedStyle(e); const body = parseFloat(getComputedStyle(document.querySelector('#lec-view')).fontSize); return { w: Number(c.fontWeight), r: Math.round(parseFloat(c.fontSize) / body * 1000) / 1000, gap: Math.round(parseFloat(c.marginTop) / parseFloat(c.fontSize) * 100) / 100 }; }"
LI = "(text) => { const e = [...document.querySelectorAll('#lec-view li')].find((li) => (li.firstChild?.textContent || '').trim().startsWith(text) || li.childNodes[0]?.nodeValue?.trim().startsWith(text) || [...li.childNodes].filter((n) => n.nodeType === 3 || n.nodeName === 'P' || n.nodeName === 'INPUT').map((n) => n.textContent).join('').trim().startsWith(text)); if (!e) return null; const c = getComputedStyle(e); const body = parseFloat(getComputedStyle(document.querySelector('#lec-view')).fontSize); return { w: Number(c.fontWeight), r: Math.round(parseFloat(c.fontSize) / body * 1000) / 1000, gap: Math.round(parseFloat(c.marginTop) / parseFloat(c.fontSize) * 100) / 100 }; }"

base = Path(tempfile.mkdtemp(prefix='lec-listlevels-'))
proj = base / '과제'
proj.mkdir()
(proj / '보고서.md').write_text(DOC, encoding='utf-8', newline='\n')
(proj / '발표.md').write_text(SLIDES, encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report'}), encoding='utf-8')


def bold(x):
    return bool(x) and x['w'] >= 600


def plain(x):
    return bool(x) and x['w'] < 600


server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 900, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.click('#lec-tree .row[data-doc="보고서.md"]')
        page.wait_for_selector('#lec-view .lec-marklist', timeout=10000)
        page.wait_for_timeout(500)
        mk = lambda s: page.evaluate(MARK, s)   # noqa: E731
        li = lambda s: page.evaluate(LI, s)   # noqa: E731

        print('[글머리 글자 목록 (□ ○ - ·)]')
        top, second = mk('전기차·전력망'), mk('전기차 한 대')
        check('□ — 진하게·1.05배', bold(top) and top['r'] == 1.05, top)
        check('○ — 본문 그대로', plain(second) and second['r'] == 1, second)
        check('- — .96배', plain(mk('충전 설비')) and mk('충전 설비')['r'] == 0.96, mk('충전 설비'))
        check('· — .92배', mk('국제구리협회')['r'] == 0.92, mk('국제구리협회'))
        check('둘째 □ 앞은 띄운다 (.6em)', mk('공급은 빠듯')['gap'] == 0.6, mk('공급은 빠듯'))
        check('묶음의 첫 □ 앞은 그대로 (0)', top['gap'] == 0, top)
        check('□ 만 있는 묶음은 그대로', plain(mk('첫째 요점')) and mk('첫째 요점')['r'] == 1, mk('첫째 요점'))
        hang = page.evaluate("""() => { const e = [...document.querySelectorAll('#lec-view .lec-mark')].find((p) => p.textContent.includes('전기차·전력망'));
          const r = document.createRange(); const n = e.firstChild; const text = n.nodeValue; r.setStart(n, 2); r.setEnd(n, 3); const first = r.getClientRects()[0];
          const rects = []; for (let i = 3; i < text.length; i++) { r.setStart(n, i); r.setEnd(n, i + 1); const b = r.getClientRects()[0]; if (b && b.top > first.top + 5) { rects.push(b); break; } }
          return rects.length ? Math.round(Math.abs(rects[0].left - first.left)) : -1; }""")
        check('꺾인 줄은 글머리 글자 뒤에 맞는다 (굵은 글자로 잰 폭)', 0 <= hang <= 2, hang)

        print('[Markdown 목록]')
        check('맨 위 — 진하게·1.05배', bold(li('LME')) and li('LME')['r'] == 1.05, li('LME'))
        check('하위가 없는 맨 위 형제도 같게', bold(li('4분기')) and li('4분기')['gap'] == 0.6, li('4분기'))
        check('둘째 — 본문 그대로', plain(li('재고가')) and li('재고가')['r'] == 1, li('재고가'))
        check('셋째 .96 · 넷째 .92 · 다섯째 .92', (li('상하이')['r'], li('넷째')['r'], li('다섯째')['r']) == (0.96, 0.922, 0.922), (li('상하이'), li('넷째'), li('다섯째')))
        check('하위가 없는 목록은 그대로', plain(li('재고 자료')) and li('재고 자료')['r'] == 1, li('재고 자료'))
        check('할 일 목록은 그대로', plain(li('자료 모으기')), li('자료 모으기'))
        check('인용·강조글 속은 그대로', plain(li('인용 속 맨 위')) and plain(li('강조글 속 맨 위')), (li('인용 속 맨 위'), li('강조글 속 맨 위')))

        print('[인쇄 · html로 저장]')
        page.emulate_media(media='print')
        check('인쇄도 진하게 — 묶음 사이는 .4em', bold(li('LME')) and li('4분기')['gap'] == 0.4 and bold(mk('전기차·전력망')), (li('LME'), li('4분기')))
        page.emulate_media(media='screen')
        got = page.evaluate("""() => Promise.all([import('/static/js/mdhtml.js'), import('/static/js/store.js')]).then(([m, { S }]) => m.buildMdHtml(S.pane, '보고서.md', { printCss: '' })).then((r) => typeof r === 'string' ? r : (r.html || JSON.stringify(r)))""")
        check("'html로 저장' 의 글에도 같은 규칙", '--lec-list-top-scale' in got and 'lec-lv0' in got, len(got))

        print('[GitHub · 슬라이드]')
        page.evaluate("() => import('/static/js/api.js').then((m) => m.saveConfig({ theme: 'github' }))")
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.click('#lec-tree .row[data-doc="보고서.md"]')
        page.wait_for_selector('#lec-view .lec-marklist', timeout=10000)
        until(page, lambda: page.evaluate("() => document.documentElement.dataset.theme") == 'github')
        check('GitHub 스타일은 끈다 (GitHub 화면 그대로)', plain(li('LME')) and li('LME')['r'] == 1 and plain(mk('전기차·전력망')), (li('LME'), mk('전기차·전력망')))
        page.click('#lec-tree .row[data-doc="발표.md"]')
        page.wait_for_selector('#lec-view .lec-slide li', timeout=15000)
        w = page.evaluate("() => Number(getComputedStyle([...document.querySelectorAll('#lec-view .lec-slide li')][0]).fontWeight)")
        check('Lectern 슬라이드는 그대로', w < 600, w)
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
