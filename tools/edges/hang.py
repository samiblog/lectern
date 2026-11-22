"""번호·글머리 글자로 시작하는 블록의 내어쓰기 (D191): 제목·문단·목록 항목이 화면에서 꺾이면 둘째 줄부터 그 글자 뒤에.
머리 글자로 읽는 것과 읽지 않는 것, 화면에서의 맞춤(잰 폭 — 스타일 셋), 줄바꿈(<br>) 뒤의 줄, 하위 목록·문단으로 시작하는 항목, 가운데 맞춘 제목,
한 줄 편집 중, 글자 크기, 종이(어림값)·html 로 저장, Lectern 슬라이드, 큰 문서. 머리 글자의 계산은 rules_check 의 hang_cases.js 가 본다."""
import json
import re
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

L = '인공지능 확산은 산업 전반의 생산성을 끌어올리지만 그 효과는 업종과 기업 규모에 따라 크게 다르게 나타나며 정책 대응도 달라져야 한다.'
DOC = f"""# 내어쓰기 보고서

## 1. 추진 배경 — 생산성 증가와 고용 재편이 동시에 나타나는 전환기에 정부와 기업이 함께 풀어야 할 정책 과제를 정리한다

□ {L} {L}

① 추진 배경
※ {L} {L}
▶ 세부 사항

다음과 같다
① {L} {L}
② {L} {L}

※ 참고: {L} {L}

- ① {L} {L}
- (가) {L} {L}
  - 하위 항목 {L} {L}

- 견줄 항목
  - 하위 항목 {L} {L}

1. □ {L} {L}

- ② {L} {L}

- ③ 문단으로 시작하는 항목 {L}

> [!NOTE]
> (1) {L} {L}

3 가지 이유가 있다. {L} {L}

2024년 매출은 늘었다. {L} {L}

○○ 기관의 보고서는 {L} {L}

| 칸 |
|---|
| ① {L} |

- [ ] ① 할 일 {L} {L}
"""
DECK = f'---\nmarp: true\n---\n\n# 표지\n\n---\n\n## 장\n\n- ① {L}\n- ② {L}\n'
BIG = '# 큰 문서\n\n' + ''.join(f'## {i}. 절\n\n□ {L}\n○ {L}\n\n' for i in range(1, 501))

base = Path(tempfile.mkdtemp(prefix='lec-hang-'))
proj = base / 'proj'
proj.mkdir(parents=True)
(proj / '보고서.md').write_text(DOC, encoding='utf-8')
(proj / '발표.md').write_text(DECK, encoding='utf-8')
(proj / '큰.md').write_text(BIG, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

# 블록 하나: 머리 글자가 시작하는 줄(at)의 첫 화면 줄에서 글이 시작하는 x 와 그 줄이 꺾인 다음 화면 줄의 x — em 으로 (글자 상자로 잰다)
GEOM = """(sel) => { const el = typeof sel === 'string' ? document.querySelector(sel) : sel; if (!el) return null;
  return import('/static/js/hang.js').then(({ blockHang }) => {
    const own = el.tagName === 'LI' ? [...el.childNodes].filter((n, i, a) => !a.slice(0, i + 1).some((x) => x.nodeType === 1 && /^(UL|OL|P|DIV|PRE|TABLE|BLOCKQUOTE)$/.test(x.tagName))).map((n) => n.textContent).join('') : el.textContent;
    const h = blockHang(own); if (!h) return { marked: el.classList.contains('lec-hang') };
    const boxes = []; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let at = 0;
    for (let n = w.nextNode(); n; n = w.nextNode()) { for (let i = 0; i < n.length; i++) { if (at + i >= h.at) { const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1);
      const b = [...r.getClientRects()].find((x) => x.width); if (b) boxes.push({ i: at + i, c: n.data[i], left: b.left, top: b.top }); } } at += n.length; if (boxes.length > 300) break; }
    const fs = parseFloat(getComputedStyle(el).fontSize); const start = boxes[0];
    const body = boxes.find((x) => x.i >= h.at + h.prefix.length);
    const next = boxes.find((x) => x.top > start.top + fs / 2);
    const nl = own.indexOf('\\n', h.at);
    const sameHard = next && (nl < 0 || next.i < nl);
    return { marked: el.classList.contains('lec-hang'), prefix: h.prefix, fs, wrapGap: sameHard ? (next.left - body.left) / fs : null,
      est: parseFloat(el.style.getPropertyValue('--lec-hang')), fit: parseFloat(el.style.getPropertyValue('--lec-hang-fit')), indent: getComputedStyle(el).textIndent };
  }); }"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1100, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')

        def open_doc(name, sel='#lec-view h1'):
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click()
            page.wait_for_selector(sel)
            page.wait_for_timeout(300)

        def geom(sel):
            return page.evaluate(GEOM, sel)

        def p_with(text):
            return page.locator('#lec-view p, #lec-view li, #lec-view h2', has_text=text).first.element_handle()

        def geo_of(text):
            return page.evaluate(GEOM, p_with(text))

        print('[머리 글자로 읽는 것]')
        open_doc('보고서.md')
        for name, text in [('번호 제목 (h2)', '1. 추진 배경'), ('□ 문단', '□ 인공지능'), ('※ 참고', '※ 참고'), ('목록 항목의 ①', '① 인공지능'),
                           ('목록 항목의 (가)', '(가) 인공지능'), ('번호 목록 항목의 □', '□ 인공지능 확산은 산업 전반의 생산성을 끌어올리지만 그 효과는 업종과 기업 규모에 따라 크게 다르게 나타나며 정책 대응도 달라져야 한다. 인공'),
                           ('강조글 안의 (1)', '(1) 인공지능')]:
            g = page.evaluate(GEOM, page.locator('#lec-view :is(p, li, h2)', has_text=text).last.element_handle())
            check(f'{name} — 꺾인 줄이 글자 뒤에 (차이 0.05em 아래)', bool(g and g['marked'] and g['wrapGap'] is not None and abs(g['wrapGap']) < 0.05), g)
        g = geo_of('① 추진 배경')
        check("'① 제목 / ※ 내용 / ▶ 세부' 문단 — 가장 긴 ※ 줄이 꺾이면 글자 뒤에", bool(g and g['marked'] and g['prefix'] == '※ ' and abs(g['wrapGap']) < 0.05), g)
        starts = page.evaluate("""(el) => { const r = document.createRange(); const out = [];
          const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); for (let n = w.nextNode(); n; n = w.nextNode()) { const i = n.data.search(/[①※▶]/); if (i < 0 || n.data[i + 1] !== ' ') continue;
            r.setStart(n, i); r.setEnd(n, i + 1); out.push(Math.round(r.getClientRects()[0].left)); } return out; }""", p_with('① 추진 배경'))
        check('— 줄바꿈 뒤의 ※·▶ 줄은 첫 줄과 같은 자리에서 시작 (들여 쓰지 않는다)', len(starts) == 3 and len(set(starts)) == 1, starts)
        g = geo_of('다음과 같다')
        check("'다음과 같다' 뒤의 ①·② 줄 — ① 이 꺾이면 글자 뒤에", bool(g and g['marked'] and g['prefix'] == '① ' and abs(g['wrapGap']) < 0.05), g)
        nested = page.evaluate("""() => { const items = [...document.querySelectorAll('#lec-view li li')].filter((li) => li.textContent.startsWith('하위 항목'));
          return items.map((li) => Math.round(li.getBoundingClientRect().left)); }""")
        check('하위 목록은 위 항목의 내어쓰기를 물려받지 않는다 (내어 쓴 항목 아래와 견줄 항목 아래가 같은 자리)', len(nested) == 2 and nested[0] == nested[1], nested)
        sub = page.evaluate("""() => { const li = [...document.querySelectorAll('#lec-view li li')].find((x) => x.textContent.startsWith('하위 항목')); return getComputedStyle(li).textIndent; }""")
        check('— 하위 항목의 text-indent 는 0', sub == '0px', sub)
        loose = page.evaluate("""() => { const li = [...document.querySelectorAll('#lec-view li')].find((x) => x.textContent.includes('③ 문단으로'));
          return [li.classList.contains('lec-hang'), li.querySelector(':scope > p')?.classList.contains('lec-hang')]; }""")
        check('문단으로 시작하는 항목은 그 문단이 내어 쓴다', loose == [False, True], loose)

        print('[읽지 않는 것]')
        for name, text in [("'3 가지'", '3 가지 이유'), ("'2024년'", '2024년 매출'), ("'○○ 기관'", '○○ 기관의')]:
            check(f'{name} 은 내어 쓰지 않는다', page.locator('#lec-view p', has_text=text).first.evaluate("(el) => !el.classList.contains('lec-hang')"))
        check('표의 칸은 내어 쓰지 않는다', page.locator('#lec-view table .lec-hang').count() == 0)
        check('할 일 항목은 내어 쓰지 않는다 (체크 칸이 이미 맞춘다)', page.locator('#lec-view .task-list-item.lec-hang, #lec-view .task-list-item .lec-hang').count() == 0)
        check('머리 글자가 없는 제목은 그대로', page.locator('#lec-view h1.lec-hang').count() == 0)

        print('[한 줄 편집 중]')
        target = page.locator('#lec-view p', has_text='※ 참고').first
        target.click(position={'x': 200, 'y': 8})
        page.keyboard.press('Enter')
        until(page, "document.activeElement?.classList?.contains('lec-line-edit')", 4000)
        g = page.evaluate("""() => { const sp = document.activeElement; const node = sp.firstChild; const r = document.createRange();
          const box = (i) => { r.setStart(node, i); r.setEnd(node, i + 1); return r.getClientRects()[0]; };
          const fs = parseFloat(getComputedStyle(sp).fontSize); const body = box(2); let next = null;
          for (let i = 3; i < node.length; i++) { const b = box(i); if (b && b.top > body.top + fs / 2) { next = b; break; } }
          return next ? (next.left - body.left) / fs : null; }""")
        check('고치는 동안에도 꺾인 줄이 글자 뒤에 (칸이 내어쓰기를 물려받는다)', g is not None and abs(g) < 0.05, g)
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)

        print('[글자 크기]')
        page.evaluate("document.documentElement.style.setProperty('--md-scale', '1.35')")
        page.wait_for_timeout(200)
        g = geo_of('□ 인공지능')
        check('글자를 키워도 맞다 (em 이라 따라간다)', bool(g and abs(g['wrapGap']) < 0.05), g)
        page.evaluate("document.documentElement.style.removeProperty('--md-scale')")

        print('[스타일]')
        for th in ['report', 'book', 'manuscript']:
            page.evaluate("window.__old = document.querySelector('#lec-view').firstElementChild")
            page.select_option('#lec-theme', th)
            page.wait_for_function(f"""document.documentElement.dataset.theme === '{th}' && document.querySelector('#lec-theme-css').sheet?.cssRules.length > 0
              && document.querySelector('#lec-view').firstElementChild !== window.__old""", timeout=10000)
            page.wait_for_timeout(300)
            gaps = page.evaluate(f"""async () => {{ const g = {GEOM}; const out = [];
              for (const el of document.querySelectorAll('#lec-view .lec-hang')) {{ const x = await g(el); if (x.wrapGap != null) out.push(Math.abs(x.wrapGap)); }} return out; }}""")
            check(f'{th} — 꺾인 줄이 모두 글자 뒤에 ({len(gaps)}곳, 가장 큰 차이 0.05em 아래)', len(gaps) >= 8 and max(gaps) < 0.05, gaps)
            if th == 'book':
                centered = page.evaluate("[...document.querySelectorAll('#lec-view h2')].map((h) => [getComputedStyle(h).textAlign, h.classList.contains('lec-hang')])")
                check("책 — 가운데 맞춘 제목 '1. 추진 배경' 은 내어 쓰지 않는다", centered and centered[0] == ['center', False], centered)
        page.select_option('#lec-theme', 'default')
        page.wait_for_function("document.documentElement.dataset.theme === 'default'")
        page.wait_for_timeout(600)

        print('[종이·html 로 저장]')
        page.emulate_media(media='print')
        g = geo_of('□ 인공지능')
        ind = float(g['indent'].split('px')[0]) if g else 0
        check('종이에는 어림값 (--lec-hang) — 글꼴이 다르다', bool(g and abs(ind - g['est'] * g['fs']) < 1 and 'hanging' in g['indent']), g)
        page.emulate_media(media='screen')
        g = geo_of('□ 인공지능')
        ind = float(g['indent'].split('px')[0]) if g else 0
        check('화면에는 잰 값 (--lec-hang-fit)', bool(g and abs(ind - g['fit'] * g['fs']) < 1), g)
        out = page.evaluate("""async () => { const { S } = await import('/static/js/store.js'); const m = await import('/static/js/mdhtml.js');
          return (await m.buildMdHtml(S.pane, '보고서.md', { printCss: '' })).text; }""")
        styles = re.findall(r'style="([^"]*--lec-hang[^"]*)"', out)
        check('html 로 저장 — 내어쓰기와 어림값은 남고 화면에서 잰 값은 뺀다 (화면 글꼴로 잰 것)',
              len(styles) >= 8 and all('--lec-hang:' in s and '--lec-hang-fit' not in s for s in styles) and 'hanging each-line' in out, styles[:3])

        print('[Lectern 슬라이드]')
        open_doc('발표.md', '#lec-view .lec-slide')
        check('슬라이드는 내어 쓰지 않는다', page.locator('#lec-view .lec-hang').count() == 0)

        print('[큰 문서]')
        open_doc('큰.md')
        n = page.locator('#lec-view .lec-hang').count()
        ms = page.evaluate("""async () => { const { fitHangs } = await import('/static/js/hang.js'); const view = document.querySelector('#lec-view');
          view.querySelectorAll('.lec-hang').forEach((el) => el.style.removeProperty('--lec-hang-fit'));
          const t0 = performance.now(); fitHangs(view); return performance.now() - t0; }""")
        check(f'제목 500·글머리 글자 목록 500 (항목 1000) — 모두 내어 쓰고 ({n}곳), 다시 재는 데 {ms:.0f}ms (300ms 아래)', n == 1500 and ms < 300, (n, ms))

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
