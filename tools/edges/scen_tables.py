"""시나리오 — 표를 실제로 쓰는 흐름 (D173·D174):
1 Claude Code 가 보고서에 표를 쓴다 (열린 문서가 바뀜) → 글이 적은 열도 낱말이 끊기지 않고, 표는 문서 폭 안
2 연구자가 칸 하나를 길게 고친다 (F2 → 저장) → 다시 맞춰도 좁게 감긴 칸 없음
3 표 칸 우클릭으로 열을 더한다 → 일곱 열이어도 스크롤 없이 맞춤
4 글자 크기·문서 폭·줄 번호·창 크기를 바꾼다 → 그때마다 다시 맞춤
5 보고서식으로 바꿔 인쇄·html 로 저장 → 머리행·짧은 열 가운데, 원문의 맞춤 표시는 그대로, 앱 폭으로 잰 열 폭은 담지 않음
6 강조글·박스글 안의 표 → 그 상자 폭 안
7 표 마흔 개인 긴 문서 → 다시 맞추는 데 오래 걸리지 않고 좁게 감긴 칸 없음
8 CSV 표는 문서 표의 설정과 상관없음
9 영어 화면 — 설정과 우클릭 문구"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-scentables-'))
proj = base / 'proj'
(proj / 'data').mkdir(parents=True)
(proj / '보고서.md').write_text('# 공급망 점검 보고\n\n표를 채우는 중입니다.\n', encoding='utf-8')
(proj / 'data' / '목록.csv').write_text('구분,상태\n구리,진행\n니켈,보류\n', encoding='utf-8')
REPORT = '''# 공급망 점검 보고

## 점검 결과

표 1. 품목별 점검 결과

| 구분 | 상태 | 현황 | 문제 | 대응 방안 | 담당 |
|---|---|---|---|---|---|
| 구리 | 진행 | 전력망 투자 계획이 늘어 수요가 커진다는 전망이 이어지고 재고는 평년보다 낮다 | 칠레 광산의 파업 소식이 잦아 공급 일정이 흔들린다 | 분기마다 공급처별 계약 물량을 다시 확인하고 대체 공급처 두 곳과 조건을 미리 맞춘다 | 수급팀 |
| 니켈 | 보류 | 인도네시아 공급이 늘어 가격이 눌린다 | 품질 기준이 달라 바로 쓰기 어렵다 | 시험 물량을 들여와 품질을 확인한다 | 품질팀 |
| 아연 | 완료 | 건설 경기가 더디다 | 없음 | 지금 계약을 유지한다 | 수급팀 |

자료: 사내 점검 (2026)

## 기준

| 항목 | 기준 | 비고 |
|---|:---:|---|
| 재고 | 30일 | 평년 기준 |
| 계약 | 분기 | 공급처별 |

> [!NOTE]
> 참고 표
>
> | 구분 | 설명 | 비고 |
> |---|---|---|
> | 가 | 강조글 안의 표도 상자 폭 안에서 맞춘다 — 설명이 길어도 다른 열이 좁아지지 않아야 한다 | 짧음 |

<!-- box -->
**박스 1. 함께 볼 것**

| 구분 | 설명 |
|---|---|
| 나 | 박스글 안의 표 역시 상자 폭에 맞춰 그린다 — 긴 설명이 있어도 첫 열은 한두 글자 폭으로 좁아지지 않는다 |
<!-- /box -->
'''
LONGTXT = '공급 충격은 가격에 바로 반영되므로 소식이 나오면 그날 안에 추정치를 고친다'
many = '# 표 많은 문서\n\n' + ''.join(
    f'## 절 {k}\n\n| 구분 | 상태 | 설명 | 담당 |\n|---|---|---|---|\n' + ''.join(f'| 항목 {k}-{r} | 진행 | {LONGTXT} {r} | 수급팀 |\n' for r in range(6)) + '\n'
    for k in range(40))
(proj / '표많은.md').write_text(many, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

base2 = Path(tempfile.mkdtemp(prefix='lec-scentables-en-'))
proj2 = base2 / 'proj'
proj2.mkdir(parents=True)
(proj2 / 'a.md').write_text('# a\n\n| k | v |\n|---|:---:|\n| x | y |\n', encoding='utf-8')
config2 = base2 / 'config'
config2.mkdir()
(config2 / 'config.json').write_text(json.dumps({'work_alerts': False, 'language': 'en'}), encoding='utf-8')
server2, url2, port2 = serve(proj2, config2)

# 문서의 표마다: class, 열 폭(em), 좁게 감긴 칸, 가장 많은 줄, 넘침, 상자(부모 블록) 밖으로 나감
TABLES = """() => [...document.querySelectorAll('#lec-view .table-wrap > table')].map((t) => {
  const em = parseFloat(getComputedStyle(t).fontSize);
  const lines = (c) => { const lh = parseFloat(getComputedStyle(c).lineHeight) || em * 1.5; const r = document.createRange(); r.selectNodeContents(c); return Math.round(r.getBoundingClientRect().height / lh); };
  const cells = [...t.rows].flatMap((r) => [...r.cells]);
  const wrap = t.parentElement; const host = wrap.parentElement.getBoundingClientRect();
  return { cls: t.className, cols: t.rows[0].cells.length, widths: [...t.rows[0].cells].map((c) => Math.round(c.getBoundingClientRect().width / em * 10) / 10),
    narrow: cells.filter((c) => lines(c) >= 3 && c.getBoundingClientRect().width < em * 4).length, maxLines: Math.max(...cells.map(lines)),
    over: wrap.scrollWidth > wrap.clientWidth + 1, out: wrap.getBoundingClientRect().right > host.right + 1 };
})"""
SRC = lambda: (proj / '보고서.md').read_text(encoding='utf-8')


def healthy(ts):
    return all(t['narrow'] == 0 and not t['over'] and not t['out'] for t in ts)


try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1400, 'height': 900}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.locator('#lec-tree .row.file[data-doc="보고서.md"]').click()
        page.wait_for_selector('#lec-view h1', timeout=15000)
        tables = lambda: page.evaluate(TABLES)

        print('[1 Claude Code 가 표를 쓴다]')
        (proj / '보고서.md').write_text(REPORT, encoding='utf-8')
        expect(page, '열린 문서가 바뀌면 표 넷을 그린다', lambda: len(tables()) == 4, ms=10000)
        ts = until(page, lambda: tables() if healthy(tables()) else None, ms=4000) or tables()
        main = ts[0]
        check('본문 표: 좁게 감긴 칸·넘침 없음, 6줄을 넘는 칸 없음 (브라우저대로가 좋으면 그대로)', main['narrow'] == 0 and not main['over'] and main['maxLines'] <= 6
              and ('lec-fit' in main['cls'] or 'lec-words' in main['cls']), main)
        check('— 짧은 열(구분·상태·담당)도 낱말 폭은 지킨다 (3em 넘게)', min(main['widths']) > 3, main['widths'])
        check('— 긴 글 세 열이 짧은 열보다 넓다', min(main['widths'][2:5]) > max(main['widths'][0], main['widths'][1], main['widths'][5]), main['widths'])
        check('강조글·박스글 안의 표는 상자 폭 안', all(not t['out'] and not t['over'] and t['narrow'] == 0 for t in ts[2:]), ts[2:])

        print('[2 연구자가 칸 하나를 고친다]')
        page.locator('#lec-view tbody tr:nth-child(3) td:nth-child(6)').first.click()   # 아연의 담당
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=5000)
        for _ in range(5):   # F2 는 행의 첫 칸에서 연다 — Tab 으로 담당 칸까지
            page.keyboard.press('Tab')
        page.keyboard.press('End')
        page.keyboard.type(' and the review team for every contract in the next quarter')
        page.keyboard.press('Enter')   # 칸의 Enter 는 저장하고 다음 줄로 (D168)
        expect(page, '원문의 그 줄 담당 칸만 바뀐다', lambda: '| 수급팀 and the review team for every contract in the next quarter |' in SRC()
               and SRC().count('\n') == REPORT.count('\n'), lambda: [l for l in SRC().split('\n') if 'review' in l], ms=6000)
        expect(page, '다시 그려도 좁게 감긴 칸·넘침 없음', lambda: 'review team' in page.inner_text('#lec-view table') and healthy(tables()[:1]), lambda: tables()[0])

        print('[3 표 칸 우클릭 — 열 더하기]')
        page.locator('#lec-view tbody tr:first-child td:nth-child(2)').first.click(button='right')
        page.wait_for_selector('#lec-menu button', timeout=3000)
        page.locator('#lec-menu button', has_text='오른쪽에 열 더하기').click()
        expect(page, '일곱 열 — 원문 표의 줄마다 칸이 하나 늘었다', lambda: tables()[0]['cols'] == 7, ms=6000)
        expect(page, '— 스크롤 없이 맞춤, 좁게 감긴 칸 없음', lambda: healthy(tables()[:1]), lambda: tables()[0])

        print('[4 글자 크기·문서 폭·줄 번호·창 크기]')
        before = tables()[0]['widths']
        for _ in range(3):
            page.click('#lec-text-bigger')
        expect(page, '글자를 키우면 다시 맞춘다 — 넘침·좁게 감긴 칸 없음', lambda: tables()[0]['widths'] != before and healthy(tables()), lambda: tables()[0], ms=5000)
        page.click('#lec-text-reset')
        page.click('#lec-width-narrower')
        page.click('#lec-width-narrower')
        expect(page, '문서 폭을 좁히면 다시 맞춘다', lambda: healthy(tables()), lambda: tables()[0], ms=5000)
        page.click('#lec-width-reset')
        page.keyboard.press('Alt+L')
        expect(page, '줄 번호를 켜도 (본문이 좁아짐) 넘치지 않는다', lambda: healthy(tables()), lambda: tables()[0], ms=5000)
        page.keyboard.press('Alt+L')
        page.set_viewport_size({'width': 1000, 'height': 900})
        expect(page, '창을 줄여도 넘치거나 좁게 감기지 않는다', lambda: healthy(tables()), lambda: tables()[0], ms=5000)
        page.set_viewport_size({'width': 1400, 'height': 900})
        page.wait_for_timeout(400)

        print('[5 보고서식으로 인쇄·html 로 저장]')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        page.locator('#lec-settings .set-nav button[data-set="view"]').click()
        page.locator('#lec-settings label:has(input[name="table_align"][value="report"])').click()
        page.keyboard.press('Escape')
        align = lambda i: page.evaluate("(i) => { const t = document.querySelectorAll('#lec-view .table-wrap > table')[i]; return [...t.rows[0].cells].map((h, c) => [getComputedStyle(h).textAlign, getComputedStyle(t.rows[1].cells[c]).textAlign]); }", i)
        expect(page, '보고서식: 구분·상태 열은 가운데, 현황(긴 글)은 왼쪽', lambda: align(0)[0] == ['center', 'center'] and align(0)[1][1] == 'center' and align(0)[3][1] == 'left',
               lambda: (align(0), page.evaluate("() => [...document.querySelector('#lec-view .table-wrap > table').rows[1].cells].map((c) => [c.className, c.getAttribute('style'), c.textContent.slice(0, 12)])"), SRC().split(chr(10))[6:12]))
        check("원문의 맞춤 표시(기준 열 ':---:')는 그대로 가운데, 비고(짧은 글)도 가운데", align(1)[1][1] == 'center', align(1))
        check('열 너비는 그대로 맞춤 (보고서식은 맞춤만 바꾼다)', healthy(tables()), tables()[0])
        page.emulate_media(media='print')
        check('인쇄에서도 보고서식', align(0)[0] == ['center', 'center'] and align(0)[3][1] == 'left', align(0))
        page.emulate_media(media='screen')
        html = page.evaluate("() => import('/static/js/store.js').then(({ S }) => import('/static/js/mdhtml.js').then((m) => m.buildMdHtml(S.pane, '보고서.md', { printCss: '' }))).then((r) => r.text)") or ''
        check('html 로 저장 — 보고서식은 담고, 앱 폭으로 잰 열 폭(lec-fit·--lec-w)은 담지 않는다',
              'lec-report' in html and 'class="lec-fit' not in html and 'lec-fit"' not in html and '--lec-w:' not in html, ('lec-report' in html, html.count('--lec-w')))

        print('[7 표 마흔 개인 문서]')
        page.locator('#lec-tree .row.file[data-doc="표많은.md"]').click()
        expect(page, '표 마흔 개를 그린다', lambda: len(tables()) == 40, ms=15000)
        ms = page.evaluate("() => import('/static/js/tablefit.js').then((m) => { const t0 = performance.now(); m.fitTables(document.querySelector('#lec-view')); return performance.now() - t0; })")
        print(f'     다시 맞추기 {ms:.0f}ms')
        check('다시 맞추는 데 1.5초 안', ms < 1500, ms)
        ts = tables()
        check('모든 표에 좁게 감긴 칸·넘침 없음', healthy(ts), [t for t in ts if not healthy([t])][:2])

        print('[8 CSV 표]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'code', path: 'data/목록.csv' }))")
        expect(page, 'CSV 표는 문서 표의 보고서식과 상관없다', lambda: page.locator('#lec-view.csv-view table.csv-table').count() == 1
               and page.locator('#lec-view table.lec-report, #lec-view td.short').count() == 0, ms=8000)

        check('화면 스크립트 오류 없음', not errors, errors[:3])

        print('[9 영어 화면]')
        page2 = browser.new_context(viewport={'width': 1400, 'height': 900}).new_page()
        page2.goto(url2)
        page2.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page2.locator('#lec-tree .row.file[data-doc="a.md"]').click()
        page2.wait_for_selector('#lec-view table', timeout=15000)
        page2.keyboard.press('Control+,')
        page2.wait_for_selector('#lec-settings:not([hidden])')
        page2.locator('#lec-settings .set-nav button[data-set="view"]').click()
        text = page2.inner_text('#lec-settings')
        check("설정 — 'Table cell alignment'·'Report style'", 'Table cell alignment' in text and 'Report style' in text, text[:200])
        page2.keyboard.press('Escape')
        page2.locator('#lec-view tbody td:nth-child(2)').first.click(button='right')
        page2.wait_for_selector('#lec-menu button', timeout=3000)
        labels = page2.locator('#lec-menu button').all_inner_texts()
        check("우클릭 — 'Clear this column's alignment mark'", "Clear this column's alignment mark" in labels, labels)
        page2.keyboard.press('Escape')
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
    stop(server2, base2)
report()
