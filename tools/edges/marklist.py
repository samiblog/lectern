"""글머리 글자 목록 (D192): 줄 맨 앞의 □·ㅁ, ○·ㅇ, -, · 를 목록으로 읽고 하위 수준은 상위 수준보다 들여 쓴다 — 원문은 그대로.
수준과 들여쓰기, 꺾인 줄·이어 쓴 줄, 문서 전체의 차례, Markdown 목록·인용·목록 항목 안, 한 줄 편집('- ' 도 글), 새 항목(같은 머리 글자·하위 항목 뒤·Tab),
머리 글자만 두고 끝내기, 지우기(그 줄만), 문서 점검, 종이, Lectern 슬라이드. 블록 규칙의 계산은 rules_check 의 marklist_cases.js 가 본다."""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

L = '인공지능 확산은 산업 전반의 생산성을 끌어올리지만 그 효과는 업종과 기업 규모에 따라 크게 다르게 나타나며 정책 대응도 달라져야 한다.'
DOC = f"""# 개조식 보고서

ㅁ 추진 배경
 ㅇ 생산성이 늘었다 {L}
  - 제조업 {L}
   · 반도체 {L}
  - 서비스업
  이어 쓴 줄 {L}
ㅁ 정책 과제

ㅇ 떨어진 문단의 항목

- 보통 목록
- 둘째

사이 문단

- 목록 항목
  ㅇ 항목 안의 줄

> ㅇ 인용 안의 항목
> - 인용 안의 세부
"""
DECK = '---\nmarp: true\n---\n\n# 표지\n\n---\n\n## 장\n\nㅁ 슬라이드의 줄\nㅇ 하위\n'

base = Path(tempfile.mkdtemp(prefix='lec-marklist-'))
proj = base / 'proj'
proj.mkdir(parents=True)
doc = proj / '개조.md'
doc.write_text(DOC, encoding='utf-8')
(proj / '발표.md').write_text(DECK, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)


def text():
    for _ in range(40):
        try:
            return doc.read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.02)
    return doc.read_text(encoding='utf-8')


# 항목마다: 글 앞 6자, 수준 class, 머리 글자의 x, (꺾였으면) 다음 화면 줄의 x 와 머리 글자 뒤 글의 x 의 차이(em)
ITEMS = """() => [...document.querySelectorAll('#lec-view .lec-mark')].map((p) => {
  const fs = parseFloat(getComputedStyle(p).fontSize); const boxes = []; const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) for (let i = 0; i < n.length; i++) { if (/\\s/.test(n.data[i])) continue; const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1);
    const b = [...r.getClientRects()].find((x) => x.width); if (b) boxes.push({ c: n.data[i], left: b.left, top: b.top }); }
  const body = boxes[1]; const next = boxes.find((x) => x.top > boxes[0].top + fs / 2);
  return { t: p.textContent.slice(0, 6), lv: (/lec-lv(\\d)/.exec(p.className) || [])[1], x: Math.round(boxes[0].left), fs,
    gap: next ? Math.round(((next.left - body.left) / fs) * 100) / 100 : null };
})"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1100, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('dialog', lambda d: d.accept())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')

        def open_doc(name, sel='#lec-view h1'):
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click()
            page.wait_for_selector(sel)
            page.wait_for_timeout(400)

        def items():
            return {x['t']: x for x in page.evaluate(ITEMS)}

        def item(start):
            return page.locator('#lec-view .lec-mark', has_text=start).first

        def editing():
            return page.evaluate("document.activeElement?.classList?.contains('lec-line-edit') ? document.activeElement.textContent : null")

        print('[수준과 들여쓰기]')
        open_doc('개조.md')
        it = items()
        lv = {k[:3]: v['lv'] for k, v in it.items()}
        check('ㅁ·ㅇ·-·· 가 수준 0·1·2·3', lv.get('ㅁ 추') == '0' and lv.get('ㅇ 생') == '1' and lv.get('- 제') == '2' and lv.get('· 반') == '3', lv)
        xs = [it[k]['x'] for k in it if k.startswith(('ㅁ 추', 'ㅇ 생', '- 제', '· 반'))]
        step = (xs[1] - xs[0]) / it['ㅁ 추진 배']['fs'] if len(xs) == 4 else 0
        check('하위 수준은 상위 수준보다 들여 쓴다 — 한 수준에 1.25em', len(xs) == 4 and xs[0] < xs[1] < xs[2] < xs[3] and abs(step - 1.25) < 0.05, (xs, step))
        check('같은 수준은 같은 자리 (ㅁ 추진 배경 · ㅁ 정책 과제, - 제조업 · - 서비스업)', it['ㅁ 추진 배']['x'] == it['ㅁ 정책 과']['x'] and it['- 제조업 ']['x'] == it['- 서비스업']['x'])
        gaps = {k: v['gap'] for k, v in it.items() if v['gap'] is not None}
        check('꺾인 줄은 머리 글자 뒤에 (항목마다)', len(gaps) >= 3 and all(abs(g) < 0.05 for g in gaps.values()), gaps)
        check("'- 서비스업' 에 이어 쓴 줄도 글자 뒤에 (줄바꿈 뒤)", it['- 서비스업']['gap'] is not None and abs(it['- 서비스업']['gap']) < 0.05, it['- 서비스업'])
        check("빈 줄로 떨어진 'ㅇ' 문단도 문서의 차례대로 수준 1", lv.get('ㅇ 떨') == '1', lv)
        check("묶음 안의 '-' 줄은 Markdown 목록이 아니다", page.locator('#lec-view .lec-marklist ul').count() == 0 and page.locator('#lec-view li', has_text='제조업').count() == 0)
        check('보통 Markdown 목록은 그대로', page.locator('#lec-view ul > li', has_text='보통 목록').count() == 1)
        check('목록 항목 안의 ㅇ 줄은 그대로 (줄바꿈)', page.locator('#lec-view li', has_text='목록 항목').first.evaluate("(li) => !li.querySelector('.lec-mark') && !!li.querySelector('br')"))
        check('인용 안에서도 글머리 글자 목록', page.locator('#lec-view blockquote .lec-mark').count() == 2)

        print('[현재 줄]')
        here = "import('/static/js/store.js').then(({ S }) => S.pane.here?.line ?? null)"
        item('ㅁ 추진').click(position={'x': 60, 'y': 8})
        page.wait_for_timeout(150)
        seq = [page.evaluate(here)]
        for _ in range(4):
            page.keyboard.press('ArrowDown')
            page.wait_for_timeout(120)
            seq.append(page.evaluate(here))
        check('↓ 는 항목마다 한 줄씩 (묶음을 한 덩어리로 건너뛰지 않는다)', seq == [3, 4, 5, 6, 7], seq)
        page.keyboard.press('Escape')

        print('[한 줄 편집]')
        item('- 제조업').click(position={'x': 120, 'y': 8})
        page.keyboard.press('Enter')
        got = until(page, lambda: editing(), 4000)
        check("'- 제조업' 을 고칠 때 '- ' 도 칸에 (화면에 보이는 그대로)", (got or '').startswith('- 제조업'), got)
        page.keyboard.press('End')
        page.keyboard.type(' 끝')
        page.keyboard.press('Enter')
        expect(page, '저장 — 앞 빈칸과 머리 글자는 원문 그대로', lambda: f'\n  - 제조업 {L} 끝\n' in text(), lambda: text()[:200])
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')

        print('[새 항목]')
        page.wait_for_timeout(500)
        item('ㅇ 생산성').click(position={'x': 120, 'y': 8})
        page.keyboard.press('Shift+Enter')
        until(page, lambda: page.locator('#lec-view .lec-new-line .lec-line-edit').count() == 1, 4000)
        fresh = page.evaluate("""() => { const p = document.querySelector('#lec-view .lec-new-line'); return { text: p.textContent, cls: p.className,
          prev: p.previousElementSibling?.textContent.slice(0, 6), caret: getSelection().focusOffset }; }""")
        check("ㅇ 항목 아래에 새 줄 — 'ㅇ ' 가 미리 들고 같은 수준, 하위 항목(- · ·) 뒤에", fresh['text'] == 'ㅇ ' and 'lec-lv1' in fresh['cls'] and fresh['prev'].startswith('이어 쓴') is False and fresh['prev'].startswith('- 서비'), fresh)
        page.keyboard.press('Tab')
        fresh2 = page.evaluate("(() => { const p = document.querySelector('#lec-view .lec-new-line'); return [p.textContent, p.className]; })()")
        check("Tab — 'ㅇ ' 가 '- ' 로, 한 수준 아래", fresh2[0] == '- ' and 'lec-lv2' in fresh2[1], fresh2)
        page.keyboard.press('Shift+Tab')
        page.keyboard.type('새 항목')
        page.keyboard.press('Enter')
        expect(page, "Shift+Tab 으로 되돌려 쓰고 저장 — '이어 쓴 줄' 뒤, 'ㅁ 정책 과제' 앞에 ' ㅇ 새 항목'", lambda: f'이어 쓴 줄 {L}\n ㅇ 새 항목\nㅁ 정책 과제' in text(), lambda: text()[:600])
        expect(page, '— 화면에서도 수준 1 의 항목', lambda: items().get('ㅇ 새 항목', {}).get('lv') == '1', lambda: list(items()))
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        page.wait_for_timeout(400)
        before = text()
        item('ㅁ 정책').click(position={'x': 80, 'y': 8})
        page.keyboard.press('Shift+Enter')
        until(page, lambda: page.locator('#lec-view .lec-new-line .lec-line-edit').count() == 1, 4000)
        page.keyboard.press('Escape')
        page.wait_for_timeout(400)
        check('머리 글자만 둔 채 끝내면 넣지 않는다', text() == before and page.locator('#lec-view .lec-new-line').count() == 0)

        print('[지우기]')
        before = text()
        item('· 반도체').click(position={'x': 80, 'y': 8})
        page.keyboard.press('Delete')
        page.keyboard.press('Delete')
        expect(page, "'· 반도체' 줄만 지운다 — 위아래 줄은 그대로", lambda: text() == before.replace(f'   · 반도체 {L}\n', ''), lambda: text()[:400])
        before = text()
        item('- 제조업').click(position={'x': 80, 'y': 8})
        page.keyboard.press('Delete')
        page.keyboard.press('Delete')
        expect(page, "'- 제조업' 을 지워도 그 줄만 (Markdown 목록처럼 정리하지 않는다)", lambda: text() == before.replace(f'  - 제조업 {L} 끝\n', ''), lambda: text()[:400])
        page.keyboard.press('Control+z')
        expect(page, '— Ctrl+Z', lambda: text() == before)

        print('[문서 점검]')
        doc.write_text(DOC.replace('  - 서비스업\n', '  - 서비스업\n2. 붙은 번호\n'), encoding='utf-8')
        page.wait_for_timeout(1500)
        lint = page.evaluate("(() => { const b = document.querySelector('#lec-st-lint'); return b.hidden ? null : b.textContent.trim(); })()")
        check("묶음 안의 '2.' 줄은 '목록이 되지 않는 번호'가 아니다 (문서 점검도 같은 규칙으로 읽는다)", lint is None, lint)

        print('[종이]')
        page.emulate_media(media='print')
        ind = page.evaluate("getComputedStyle(document.querySelector('#lec-view .lec-mark.lec-hang')).textIndent")
        check('종이에도 내어쓰기 (어림값, 이어 쓴 줄까지)', 'hanging' in ind and 'each-line' not in ind, ind)
        page.emulate_media(media='screen')

        print('[Lectern 슬라이드]')
        open_doc('발표.md', '#lec-view .lec-slide')
        check('슬라이드에서는 하지 않는다', page.locator('#lec-view .lec-mark').count() == 0)

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
