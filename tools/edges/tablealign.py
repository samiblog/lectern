"""표 칸 맞춤 (D174): 설정 '표 칸 맞춤'의 기본(글 왼쪽·숫자 오른쪽·위)과 보고서식(머리행·짧은 열 가운데, 숫자 오른쪽, 긴 글 왼쪽,
세로 가운데), 원문의 맞춤 표시(:---)가 앞섬, 우클릭 '이 열 맞춤 표시 지우기'(표시가 있는 열에만 — 원문의 구분 줄만 고침),
인쇄·html 로 저장에도 그대로, 설정 파일에 남음"""
import json
import re
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-tablealign-'))
proj = base / 'proj'
proj.mkdir(parents=True)
doc = ('# 표 맞춤\n\n'
       '| 구분 | 상태 | 금액 (억원) | 설명 | 표시 |\n'
       '|---|---|---|---|:---|\n'
       '| 구리 | 진행 | 1,234 | 전력망 투자 계획이 늘어 수요가 커진다는 전망이 이어진다 | 가 |\n'
       '| 니켈 | 보류 | 567 | 인도네시아 공급이 늘어 가격이 눌린다는 소식이 많다 | 나 |\n')
(proj / '맞춤.md').write_text(doc, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

# 열마다 [머리행 맞춤, 첫 몸통 칸 맞춤, 세로 맞춤]
ALIGN = """() => { const t = document.querySelector('#lec-view .table-wrap > table'); const head = [...t.rows[0].cells]; const body = [...t.rows[1].cells];
  return { report: t.classList.contains('lec-report'), cols: head.map((h, i) => [getComputedStyle(h).textAlign, getComputedStyle(body[i]).textAlign, getComputedStyle(body[i]).verticalAlign]) }; }"""
SEP = lambda: (proj / '맞춤.md').read_text(encoding='utf-8').split('\n')[3]

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: '맞춤.md' }))")
        page.wait_for_selector('#lec-view h1:has-text("표 맞춤")', timeout=15000)
        page.wait_for_timeout(500)

        print('[기본 — 글 왼쪽·숫자 오른쪽·위]')
        a = page.evaluate(ALIGN)
        c = a['cols']
        check('보고서식 표시 없음', not a['report'])
        check('짧은 열·긴 글은 왼쪽, 위에 맞춤', c[0][:2] == ['left', 'left'] and c[1][1] == 'left' and c[3][1] == 'left' and c[0][2] == 'top', c)
        check('숫자 열은 머리행까지 오른쪽', c[2][:2] == ['right', 'right'], c[2])

        print('[설정 창 — 보고서식]')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        page.locator('#lec-settings .set-nav button[data-set="view"]').click()
        check("보기 분류에 '표 칸 맞춤' — 기본이 골라져 있다", page.locator('#lec-settings input[name="table_align"][value="auto"]').is_checked())
        page.locator('#lec-settings label:has(input[name="table_align"][value="report"])').click()
        expect(page, '고르면 문서를 다시 그린다 — 표에 보고서식', lambda: page.evaluate(ALIGN)['report'])
        page.keyboard.press('Escape')
        a = page.evaluate(ALIGN)
        c = a['cols']
        check('머리행은 모두 가운데 (숫자 열도)', [x[0] for x in c[:4]] == ['center'] * 4, [x[0] for x in c])
        check('짧은 열(구분·상태)은 가운데', c[0][1] == 'center' and c[1][1] == 'center', c[:2])
        check('숫자는 오른쪽, 긴 글은 왼쪽', c[2][1] == 'right' and c[3][1] == 'left', c[2:4])
        check('칸은 세로 가운데', all(x[2] == 'middle' for x in c), [x[2] for x in c])
        check('원문의 맞춤 표시(:---)가 앞선다 — 짧아도 왼쪽', c[4][:2] == ['left', 'left'], c[4])
        saved = json.loads((config / 'config.json').read_text(encoding='utf-8'))
        check('설정 파일에 남는다 (table_align: report)', saved.get('table_align') == 'report', saved.get('table_align'))

        print('[인쇄·html 로 저장]')
        page.emulate_media(media='print')
        pc = page.evaluate(ALIGN)['cols']
        check('인쇄에서도 보고서식 (머리행·짧은 열 가운데, 세로 가운데)', pc[0][:2] == ['center', 'center'] and pc[3][1] == 'left' and pc[0][2] == 'middle', pc)
        page.emulate_media(media='screen')
        html = page.evaluate("() => import('/static/js/store.js').then(({ S }) => import('/static/js/mdhtml.js').then((m) => m.buildMdHtml(S.pane, '맞춤.md', { printCss: '' }))).then((r) => r.text)") or ''
        check('html 로 저장에도 표의 보고서식과 짧은 열 표시, 그 CSS', bool(re.search(r'<table[^>]*class="[^"]*lec-report', html)) and 'class="short"' in html and 'table.lec-report' in html,
              (len(html), 'lec-report' in html))

        print('[우클릭 — 이 열 맞춤 표시 지우기]')
        def menu_at(selector):
            page.locator(selector).first.click(button='right')
            page.wait_for_selector('#lec-menu button', timeout=3000)
            return page.locator('#lec-menu button').all_inner_texts()
        labels = menu_at('#lec-view tbody tr:first-child td:nth-child(4)')
        check("표시가 없는 열에는 '맞춤 표시 지우기'가 없다 (왼쪽·가운데·오른쪽 맞춤은 있다)",
              '이 열 맞춤 표시 지우기' not in labels and '이 열 가운데 맞춤' in labels, labels)
        page.keyboard.press('Escape')
        labels = menu_at('#lec-view tbody tr:first-child td:nth-child(5)')
        check("표시가 있는 열에는 있다", '이 열 맞춤 표시 지우기' in labels, labels)
        page.locator('#lec-menu button', has_text='이 열 맞춤 표시 지우기').click()
        expect(page, '원문의 구분 줄에서 그 열의 표시만 지운다', lambda: [x.strip() for x in SEP().strip('|').split('|')] == ['---'] * 5, SEP)
        expect(page, '— 다시 그리면 짧은 열이라 가운데 (보고서식)', lambda: page.evaluate(ALIGN)['cols'][4][1] == 'center', lambda: page.evaluate(ALIGN)['cols'][4])
        rest = (proj / '맞춤.md').read_text(encoding='utf-8').split('\n')
        check('다른 줄은 그대로', rest[:3] + rest[4:] == doc.split('\n')[:3] + doc.split('\n')[4:])

        print('[기본으로 되돌리기]')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        page.locator('#lec-settings label:has(input[name="table_align"][value="auto"])').click()
        expect(page, '기본을 고르면 보고서식을 뗀다 — 머리행·짧은 열은 다시 왼쪽',
               lambda: not page.evaluate(ALIGN)['report'] and page.evaluate(ALIGN)['cols'][0][:2] == ['left', 'left'])
        page.keyboard.press('Escape')

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
