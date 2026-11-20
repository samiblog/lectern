"""시나리오 — 슬라이드의 넘침 맞춤 (D188)을 사람이 쓰는 길로: 칸에 줄을 더하다 넘치고, AI 가 파일을 고쳐 줄고,
발표·인쇄·html 로 전환·스타일·창 크기·점검 목록·구조 보기·문서로 보기를 거쳐도 줄인 크기가 그대로이거나 제대로 풀린다"""
import re
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-scen-fit-'))
proj = base / 'proj'
proj.mkdir(parents=True)
F = '```'
bul = lambda n, w: '\n'.join(f'- {w} ({i + 1})' for i in range(n))
GOOD = bul(6, '시장 점유율이 전년 대비 늘었고 신규 고객 유입이 이어졌다')
VL = ('{"width": 600, "height": 360, "data": {"values": [{"m": "7월", "k": "LME", "v": 9100}, {"m": "8월", "k": "LME", "v": 9350}, '
      '{"m": "9월", "k": "LME", "v": 9620}, {"m": "7월", "k": "SHFE", "v": 9000}, {"m": "8월", "k": "SHFE", "v": 9200}, {"m": "9월", "k": "SHFE", "v": 9480}]}, '
      '"mark": "line", "encoding": {"x": {"field": "m", "type": "ordinal", "title": "월"}, "y": {"field": "v", "type": "quantitative", "title": "USD/t", "scale": {"zero": false}}, '
      '"color": {"field": "k", "type": "nominal", "title": "거래소"}}}')


def deck(cards_a=GOOD):
    return f"""---
marp: true
paginate: true
---

## 3분기 구리 구매 보고

구매 담당자용 요약

---

<!-- layout: two -->

## 하반기 구매 판단

::: a card
### 성과
{cards_a}
:::

::: b card
### 과제
{bul(3, '원가 상승 압력이 커서 하반기 수익성 관리가 필요하다')}
:::

---

## 가격 흐름

{bul(5, '설명 글이 위에 있고 차트가 아래에 이어지는 흔한 모양의 장이다')}

{F}vega-lite
{VL}
{F}

---

<!-- layout: two -->

## 표와 코드

::: a
| 항목 | 7월 | 8월 | 9월 |
|---|--:|--:|--:|
| 매출액 | 120 | 131 | 140 |
:::

::: b
{F}python
result = model.fit(train_features_with_lagged_variables, train_target_quarterly_growth, epochs=200, verbose=0)
{F}
:::
"""


DOC = proj / '보고.md'
DOC.write_text(deck(), encoding='utf-8', newline='\n')
# 성능: 40장 가운데 20장이 넘친다
big = ['---\nmarp: true\n---\n\n## 표지\n\n글\n']
for i in range(40):
    n = 9 if i % 2 else 4
    big.append(f'<!-- layout: two -->\n\n## {i + 1}장\n\n::: a card\n{bul(n, "보고서의 문장을 그대로 옮겨 와서 길어진 줄")}\n:::\n\n::: b card\n{bul(3, "짧은 글")}\n:::\n')
(proj / '큰발표.md').write_text('\n---\n\n'.join(big), encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
server, url, port = serve(proj, config)
extra = []
OPEN = "(path) => import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'doc', path, force: true }))"
S = lambda n: f"document.querySelectorAll('#lec-view .lec-slide')[{n}]"
W = lambda n: f"document.querySelectorAll('#lec-view > .lec-slide-wrap')[{n}]"
FITTED = lambda n: f"JSON.parse({W(n)}?.dataset.fitted || '[]').map((x) => x.text)"
ISSUES = lambda n: f"JSON.parse({W(n)}?.dataset.issues || '[]').map((x) => x.text)"
PX = lambda sel: f"(() => {{ const e = {sel}; return e ? parseFloat(getComputedStyle(e).fontSize) : 0; }})()"
CHART_PT = """(svg) => { if (!svg) return 0; const s = svg.closest('.lec-slide'); const scale = s.getBoundingClientRect().width / s.offsetWidth || 1;
  const vb = svg.getAttribute('viewBox').split(/[\\s,]+/).map(Number); const r = svg.getBoundingClientRect();
  const k = Math.min(r.width / scale / vb[2], r.height / scale / vb[3]);
  return Math.round(Math.min(...[...svg.querySelectorAll('text')].filter((t) => t.textContent.trim()).map((t) => parseFloat(getComputedStyle(t).fontSize))) * k * 0.75 * 10) / 10; }"""


def run():
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1400, 'height': 900})
        page = ctx.new_page()
        page.on('pageerror', lambda e: extra.append(str(e)[:200]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row')
        page.evaluate("() => { window.__drawn = 0; document.addEventListener('lec-chart-drawn', () => { window.__drawn += 1; }, true); }")

        def show(name):
            page.evaluate(OPEN, name)
            page.wait_for_function("(n) => document.querySelector('#lec-st-path')?.textContent.includes(n) && document.querySelector('#lec-view .lec-slide')", arg=name, timeout=20000)
            until(page, "() => [...document.querySelectorAll('#lec-view pre.lec-chart')].every((p) => p.querySelector(':scope > svg'))", 20000)
            page.wait_for_timeout(800)

        src = lambda: DOC.read_text(encoding='utf-8')
        print('[S1 사람: 카드에 줄을 더하다 넘친다]')
        show('보고.md')
        check('처음에는 줄인 곳·넘침이 없다', not page.evaluate(FITTED(1)) and not page.evaluate(ISSUES(1)), [page.evaluate(FITTED(1)), page.evaluate(ISSUES(1))])
        full = page.evaluate(PX(f"{S(1)}.querySelector('.lec-cell li')"))
        for k in range(3):
            page.locator('#lec-view .lec-cell[data-cell=a] li').last.click()
            page.wait_for_timeout(250)
            page.keyboard.press('Shift+Enter')
            page.wait_for_timeout(450)
            page.keyboard.type(f'담당자가 회의에서 덧붙인 판단 근거 문장 {k + 1}')
            page.keyboard.press('Enter')
            page.wait_for_timeout(700)
            page.keyboard.press('Escape')
            page.wait_for_timeout(500)
        check('원문에 세 줄이 목록으로 더해졌다', len(re.findall(r'^- 담당자가 회의에서 덧붙인', src(), re.M)) == 3, src()[200:900])
        expect(page, '넘친 칸을 줄여 맞춘다 — 넘침 없이 알림만', f"() => {FITTED(1)}.some((x) => x.includes('칸 a·b')) && !{ISSUES(1)}.length",
               lambda: [page.evaluate(FITTED(1)), page.evaluate(ISSUES(1))], ms=8000)
        small = page.evaluate(PX(f"{S(1)}.querySelector('.lec-cell li')"))
        check('글자가 작아졌지만 바닥 위', 14 / 0.75 - 0.1 <= small < full, (small, full))
        check('상태줄 — 줄인 글', '줄인 글' in page.locator('#lec-st-check').inner_text(), page.locator('#lec-st-check').inner_text())

        print('[S2 AI 가 파일을 고친다 (바깥에서 바뀜) — 줄인 것이 풀린다]')
        DOC.write_text(deck(), encoding='utf-8', newline='\n')
        expect(page, '다시 그려 원래 크기로', f"() => {S(1)}.querySelectorAll('.lec-cell[data-cell=a] li').length === 6 && !{FITTED(1)}.length && !{S(1)}.querySelector('.lec-shrunk')",
               lambda: page.evaluate(FITTED(1)), ms=15000)
        check('글자 크기도 처음과 같다', page.evaluate(PX(f"{S(1)}.querySelector('.lec-cell li')")) == full)
        check('상태줄은 코드를 접은 장 하나만 센다', page.locator('#lec-st-check').inner_text().strip() == '줄인 글 1장', page.locator('#lec-st-check').inner_text())
        DOC.write_text(deck(GOOD + '\n' + bul(3, '담당자가 회의에서 덧붙인 판단 근거 문장')), encoding='utf-8', newline='\n')
        expect(page, '다시 넘치게 고치면 다시 줄인다', f"() => {FITTED(1)}.length > 0", ms=15000)
        small = page.evaluate(PX(f"{S(1)}.querySelector('.lec-cell li')"))

        print('[S3 사람: 발표]')
        page.evaluate("() => import('/static/js/present.js').then(({ startPresent }) => startPresent(undefined, 1))")
        page.wait_for_timeout(400)
        shown = page.evaluate(PX("document.querySelector('.pr-stage .lec-cell li')"))
        check('발표에서도 줄인 크기 그대로', shown == small, (shown, small))
        check('발표 화면에 넘침 표시가 없다', not page.evaluate("!!document.querySelector('.pr-stage .lec-cell-over')"))
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

        print('[S4 사람: 인쇄 모양]')
        page.emulate_media(media='print')
        page.wait_for_timeout(300)
        printed = page.evaluate(PX(f"{S(1)}.querySelector('.lec-cell li')"))
        check('인쇄에서도 줄인 크기 그대로', printed == small, (printed, small))
        page.emulate_media(media='screen')
        page.wait_for_timeout(300)

        print('[S5 사람: 차트가 있는 장 — 줄이지 않고 다시 그린다]')
        expect(page, '글 아래 차트를 그 자리 높이로 다시 그렸다 — 14pt 이상', f"() => ({CHART_PT})({S(2)}.querySelector('pre.lec-chart > svg')) >= 14 && !!{S(2)}.querySelector('pre.lec-chart[data-fit-height]')",
               lambda: page.evaluate(f"({CHART_PT})({S(2)}.querySelector('pre.lec-chart > svg'))"), ms=10000)
        check('차트 장에 점검이 남지 않는다', not page.evaluate(ISSUES(2)), page.evaluate(ISSUES(2)))
        check('코드 장은 줄을 접었다고 알린다', any('코드 줄을 접었습니다' in x for x in page.evaluate(FITTED(3))), page.evaluate(FITTED(3)))

        print('[S6 사람: html 로 전환]')
        page.click('#lec-st-html')
        page.wait_for_selector('#lec-html:not([hidden])', timeout=5000)
        page.click('#lec-html-go')
        expect(page, '만든다', "!document.querySelector('#lec-html-done').hidden", ms=20000)
        page.click('#lec-html-close')
        out = proj / '보고.html'
        text = out.read_text(encoding='utf-8')
        check('결과 파일에 앱 표시(data-fitted·data-fit-height)가 없다', 'data-fitted' not in text and 'data-fit-height' not in text)
        view = ctx.new_page()
        view.goto(out.as_uri())
        view.wait_for_timeout(800)
        got = view.evaluate("""() => { const s = document.querySelector('#lec-slide-2 .lec-slide'); const li = s.querySelector('.lec-cell li');
          const pre = document.querySelector('#lec-slide-4 pre.lec-wrap'); return [parseFloat(getComputedStyle(li).fontSize), pre ? getComputedStyle(pre).whiteSpace : '']; }""")
        check('html 발표에서도 줄인 크기 그대로', got[0] == small, (got, small))
        check('html 발표에서도 코드 줄이 접힌다', got[1] == 'pre-wrap', got)
        view.close()

        print('[S7 사람: 스타일·창 크기·구조 보기]')
        before = page.evaluate(FITTED(1))
        dark = page.evaluate("[...document.querySelectorAll('#lec-theme option')].map((o) => o.value).find((v) => /dark|night|어두/i.test(v))") or 'dark'
        page.evaluate("(v) => { const s = document.querySelector('#lec-theme'); s.value = v; s.dispatchEvent(new Event('change', { bubbles: true })); }", dark)
        expect(page, f'스타일({dark})을 바꿔도 같은 비율', f"() => JSON.stringify({FITTED(1)}) === JSON.stringify({before!r})", lambda: page.evaluate(FITTED(1)), ms=10000)
        page.evaluate("() => { window.__drawn = 0; }")
        page.set_viewport_size({'width': 1000, 'height': 760})
        page.wait_for_timeout(1500)
        check('창 크기를 바꿔도 같은 비율', page.evaluate(FITTED(1)) == before, page.evaluate(FITTED(1)))
        drawn = page.evaluate('window.__drawn')
        check('창 크기를 바꿔도 차트를 몇 번만 다시 그린다 (되풀이 없음)', drawn <= 4, drawn)
        page.set_viewport_size({'width': 1400, 'height': 900})
        page.wait_for_timeout(800)
        page.click('#lec-st-structure')
        page.wait_for_timeout(600)
        check('구조 보기에서도 같은 비율·넘침 없음', page.evaluate(FITTED(1)) == before and not page.evaluate(ISSUES(1)), [page.evaluate(FITTED(1)), page.evaluate(ISSUES(1))])
        page.click('#lec-st-structure')
        page.wait_for_timeout(400)

        print('[S8 사람: 점검 목록에서 줄인 곳으로]')
        page.evaluate(f"{W(3)}.scrollIntoView()")
        page.wait_for_timeout(300)
        page.click('#lec-st-check')
        page.wait_for_timeout(250)
        menu = page.locator('#lec-menu').inner_text()
        check('목록에 줄인 곳이 장 번호와 함께', '넘쳐서 글을 줄인 곳' in menu and '2장' in menu and '4장' in menu, menu[:300])
        check('상태줄 단추의 풀이도 줄인 글', '줄인' in (page.get_attribute('#lec-st-check', 'title') or ''), page.get_attribute('#lec-st-check', 'title'))
        page.locator('#lec-menu .item, #lec-menu button, #lec-menu [role=menuitem]').filter(has_text='2장 —').first.click()
        page.wait_for_timeout(600)
        top = page.evaluate(f"{W(1)}.getBoundingClientRect().top")
        check('고르면 그 장으로 간다', -50 < top < 500, top)

        print('[S9 사람: 문서로 보기]')
        page.click('#lec-st-slides')
        page.wait_for_timeout(800)
        check('문서로 보면 줄인 표시가 없다', page.evaluate("!document.querySelector('#lec-view .lec-shrunk, #lec-view .lec-wrap, #lec-view [data-fit-height]')"))
        page.click('#lec-st-slides')
        page.wait_for_timeout(1200)
        expect(page, '슬라이드로 돌아오면 다시 줄인다', f"() => {FITTED(1)}.length > 0", ms=8000)

        print('[S10 큰 발표 — 40장 중 20장이 넘친다]')
        t0 = time.monotonic()
        page.evaluate(OPEN, '큰발표.md')
        page.wait_for_function("() => document.querySelector('#lec-st-path')?.textContent.includes('큰발표') && document.querySelectorAll('#lec-view .lec-slide').length === 41", timeout=30000)
        n = until(page, "() => [...document.querySelectorAll('#lec-view > .lec-slide-wrap')].filter((w) => w.dataset.fitted).length", 10000)
        took = time.monotonic() - t0
        check('넘친 20장을 모두 줄여 맞춘다', n == 20, n)
        check(f'40장을 그리고 맞추는 데 6초 안 ({took:.1f}초)', took < 6, took)
        left = page.evaluate("[...document.querySelectorAll('#lec-view > .lec-slide-wrap')].filter((w) => w.dataset.issues).length")
        check('줄여서 맞는 장은 점검에 남지 않는다', left == 0, left)

        check('화면 오류 없음', not extra, extra[:3])
        b.close()


try:
    run()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
