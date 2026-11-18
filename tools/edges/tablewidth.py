"""표 열 너비 자동 맞추기 (D173): 글이 적은 열이 한두 글자 폭으로 좁아져 행이 길어지지 않음(열마다 가장 긴 낱말 폭 이상),
남는 폭은 글이 긴 열로, 한 줄로 다 들어가는 표·합친 칸이 있는 표는 그대로, 열이 많아도 좁혀 넣을 수 있으면 스크롤하지 않음,
좁혀 넣으면 글이 세로로 감기는 표만 마지막 수단으로 6em 씩 두고 옆으로 스크롤,
문서 폭을 바꾸면 다시 맞춤, 인쇄(print)에서는 쪽 폭에 브라우저대로, html 로 저장하면 앱 폭으로 잰 class 를 뗌, 첫 열 때문에 높은 행은 여전히 없앰"""
import json
import re
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-tablewidth-'))
proj = base / 'proj'
proj.mkdir(parents=True)
LONG = ('공급 충격은 가격에 바로 반영되므로 소식이 나오면 그날 안에 추정치를 고친다. 추정 근거는 출처와 함께 남기고 같은 소식이 여러 곳에서 다르게 나오면 가장 이른 원문을 기준으로 삼는다. ' * 4).strip()   # 아주 긴 칸 — 브라우저대로면 다른 열이 좁아진다
MID = '수요 전망의 바탕이 되는 각국 전력망 투자 계획'
rows = ''.join(f'| 항목 {i} | {MID} | {LONG} | 담당 부서와 검토 일정 정리 | 2026년 {i}월 |\n' for i in range(1, 7))
doc = ('# 표 너비\n\n## 다섯 열\n\n| 항목 | 요약 | 설명 | 담당 | 시점 |\n|---|---|---|---|---|\n' + rows
       + '\n## 한 줄 표\n\n| 이름 | 값 |\n|---|---|\n| 구리 | 9400 |\n| 니켈 | 16500 |\n'
       + '\n## 열 많은 표\n\n| ' + ' | '.join(f'열{i}' for i in range(1, 13)) + ' |\n|' + '---|' * 12 + '\n'
       + ''.join('| ' + ' | '.join(f'값 {r}-{i} 설명 글이 조금 깁니다' for i in range(1, 13)) + ' |\n' for r in range(1, 5))
       + '\n## 짧은 열 많은 표\n\n| ' + ' | '.join(f'항목{i}' for i in range(1, 11)) + ' |\n|' + '---|' * 10 + '\n'
       + ''.join('| ' + ' | '.join('가나 다라' for i in range(1, 11)) + ' |\n' for r in range(1, 4))
       + '\n## 숫자 열 많은 표\n\n| 지표 | ' + ' | '.join(f'{y}년' for y in range(2011, 2027)) + ' |\n|---|' + '---:|' * 16 + '\n'
       + ''.join(f'| 지표 {r} | ' + ' | '.join(f'{(r * 7919 + y * 104729) % 9000000 / 10:,.1f}' for y in range(16)) + ' |\n' for r in range(1, 5))
       + '\n## 합친 칸\n\n<table><tr><th colspan="2">머리</th></tr><tr><td>가</td><td>' + LONG + '</td></tr></table>\n'
       + '\n## 첫 열 표\n\n| 할 일 | 까닭 |\n|---|---|\n' + ''.join(f'| 재고 집계와 월말 대조, 기준일 맞추기 {i} | 짧다 |\n' for i in range(4)) + f'| 광산 소식 | {LONG} |\n')
(proj / '표.md').write_text(doc, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

STATE = """() => [...document.querySelectorAll('#lec-view .table-wrap > table')].map((t) => {
  const em = parseFloat(getComputedStyle(t).fontSize);
  const lines = (c) => { const lh = parseFloat(getComputedStyle(c).lineHeight) || em * 1.5; const r = document.createRange(); r.selectNodeContents(c); return Math.round(r.getBoundingClientRect().height / lh); };
  const cells = [...t.rows].flatMap((r) => [...r.cells]);
  const wrap = t.parentElement;
  return { cls: t.className, layout: getComputedStyle(t).tableLayout, widths: [...t.rows[0].cells].map((c) => Math.round(c.getBoundingClientRect().width / em * 10) / 10),
    narrow: cells.filter((c) => lines(c) >= 3 && c.getBoundingClientRect().width < em * 4).length, maxLines: Math.max(...cells.map(lines)),
    spill: cells.filter((c) => c.scrollWidth > c.clientWidth + 1).length,
    h: Math.round(t.getBoundingClientRect().height), over: wrap.scrollWidth > wrap.clientWidth + 1, firstTall: [...t.rows].slice(1).filter((r) => r.cells.length > 1
      && lines(r.cells[0]) >= 3 && lines(r.cells[0]) > Math.max(...[...r.cells].slice(1).map(lines))).length };
})"""

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: '표.md' }))")
        page.wait_for_selector('#lec-view h1:has-text("표 너비")', timeout=15000)
        page.wait_for_timeout(800)
        st = page.evaluate(STATE)
        five, one, many, shorts, nums, span, first = st

        print('[다섯 열 — 글이 적은 열·많은 열]')
        check('모든 열 맞추기(lec-fit, 고정 배치)', 'lec-fit' in five['cls'] and five['layout'] == 'fixed', five['cls'])
        check('좁은 열에 3줄 넘게 감긴 칸이 없다 (열마다 4em 이상)', five['narrow'] == 0 and min(five['widths']) >= 4, five['widths'])
        check('남는 폭은 글이 가장 긴 열(설명)로', five['widths'][2] == max(five['widths']), five['widths'])
        check('— 표는 문서 폭을 넘지 않는다', not five['over'])

        print('[그대로 두는 표]')
        check('한 줄로 다 들어가는 표는 그대로', 'lec-fit' not in one['cls'] and one['maxLines'] == 1, one)
        check('합친 칸이 있는 표는 그대로', 'lec-fit' not in span['cls'], span['cls'])

        print('[열이 많은 표 — 옆 스크롤은 마지막 수단]')
        check('짧은 열이 많으면 좁혀 넣는다 — 스크롤하지 않고 칸은 두 줄까지', not shorts['over'] and shorts['maxLines'] <= 2 and shorts['narrow'] == 0,
              (shorts['widths'][:4], shorts['over'], shorts['maxLines']))
        check('좁혀 넣으면 글이 세로로 감기는 표만 — 열마다 6em 쯤 두고 옆으로 스크롤', many['over'] and min(many['widths']) >= 5.9 and many['narrow'] == 0,
              (many['widths'][:4], many['over']))

        check('숫자 열이 많아 들어가지 않으면 — 숫자를 옆 칸에 겹치지 않고 옆으로 스크롤 (숫자는 끊지 않는다)', nums['spill'] == 0 and nums['over'],
              (nums['spill'], nums['over'], nums['widths'][:4]))
        check('— 다른 표의 칸도 글이 칸 밖으로 넘치지 않는다', all(t['spill'] == 0 for t in st), [t['spill'] for t in st])

        print('[첫 열 때문에 높은 행]')
        check('첫 열 때문에 높은 행이 없다 (D68 이나 D173)', first['firstTall'] == 0 and ('lec-fit' in first['cls'] or 'lec-wide1' in first['cls']), first)

        print('[칸 폭이 바뀌면 다시 맞춘다]')
        before = five['widths'][:]
        page.set_viewport_size({'width': 1000, 'height': 900})   # 창을 줄이면 문서 칸이 좁아진다
        expect(page, '창을 줄이면 열 폭을 다시 정한다 — 좁은 열은 여전히 없다', lambda: page.evaluate(STATE)[0]['widths'] != before and page.evaluate(STATE)[0]['narrow'] == 0
               and not page.evaluate(STATE)[0]['over'], lambda: page.evaluate(STATE)[0]['widths'])
        page.set_viewport_size({'width': 1280, 'height': 900})
        page.wait_for_timeout(500)

        print('[인쇄·html 로 저장]')
        page.emulate_media(media='print')
        layout = page.evaluate("getComputedStyle(document.querySelector('#lec-view .table-wrap > table.lec-fit')).tableLayout")
        check('인쇄에서는 쪽 폭에 브라우저대로 (고정 배치 아님)', layout == 'auto', layout)
        page.emulate_media(media='screen')
        html = page.evaluate("() => import('/static/js/store.js').then(({ S }) => import('/static/js/mdhtml.js').then((m) => m.buildMdHtml(S.pane, '표.md', { printCss: '' }))).then((r) => r.text)")
        tagged = re.findall(r'<table[^>]*class="[^"]*lec-fit', html or '')
        check("html 로 저장하면 앱 폭으로 잰 'lec-fit' 을 표에서 뗀다", not tagged and '<table' in (html or ''), (len(html or ''), tagged[:2]))

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
