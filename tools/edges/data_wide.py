"""표와 데이터 보기를 여러 상황으로 (D86): 실제 자료의 모양(ECOS·KOSIS·FRED·World Bank·Bloomberg·보고서 표), 망가진 입력, 끼어든 글, 큰 파일, 다른 기능과 겹치는 곳"""
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop

sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_sheet import make_xlsx  # noqa: E402



def xml_row(n, cells):
    """시험용 시트의 한 행: {열 글자: 값 | (값, 형식 차례)}"""
    out = []
    for c, v in cells.items():
        style = ''
        if isinstance(v, tuple):
            v, s = v
            style = f' s="{s}"'
        if isinstance(v, (int, float)):
            out.append(f'<c r="{c}{n}"{style}><v>{v}</v></c>')
        else:
            text = str(v).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            out.append(f'<c r="{c}{n}" t="inlineStr"{style}><is><t>{text}</t></is></c>')
    return f'<row r="{n}">{"".join(out)}</row>'


def merged(refs):
    return f'</sheetData><mergeCells count="{len(refs)}">{"".join(f"<mergeCell ref={chr(34)}{r}{chr(34)}/>" for r in refs)}</mergeCells><sheetData>'


base = Path(tempfile.mkdtemp(prefix='lec-wide-'))
proj = base / 'proj'
proj.mkdir()
W = lambda name, text, enc='utf-8': (proj / name).write_bytes(text.encode(enc))
months = [f'2024/{m:02d}' for m in range(1, 13)]

# 실제 자료의 모양
W('ecos.csv', '통계표,계정항목,단위,변환,' + ','.join(months) + '\n'
  + '8.1.1 생산자물가지수,총지수,2020=100,원자료,' + ','.join(str(110 + i) for i in range(12)) + '\n'
  + '8.1.1 생산자물가지수,공산품,2020=100,원자료,' + ','.join(str(120 + i) for i in range(12)) + '\n')
W('kosis.csv', '"통계표명: 광업제조업동향조사",,,\n"단위: 2020=100",,,\n"시점","2024.01","2024.02","2024.03"\n"광공업생산지수","100.1","101.2","99.8"\n"제조업","99.5","100.2","98.9"\n')
W('fred.csv', 'observation_date,CPIAUCSL\n2024-01-01,308.417\n2024-02-01,310.326\n2024-03-01,.\n2024-04-01,313.207\n')
W('bloomberg.csv', 'Date,LMCADY Comdty,LMAHDY Comdty\n' + ''.join(f'{m:02d}/15/2024,{9000 - m},{2200 + m}\n' for m in range(12, 0, -1)))
W('dayfirst.csv', 'Date,Price\n31/01/2024,100\n01/02/2024,101\n02/02/2024,102\n')
W('cp949.csv', '날짜,가격\n2024-01,100\n2024-02,110\n', 'cp949')
W('semi.csv', 'date;price\n2024-01;1\n2024-02;2\n')
W('tabs.tsv', 'date\tprice\n2024-01\t1\n2024-02\t2\n')
W('negative.csv', '연도,손익,증감\n2022,"1,200",3.0%\n2023,"(300)",(1.5%)\n2024,△50,△2.5%\n')
W('flags.csv', '분기,생산\n2024년 1/4분기,100\n2024년 2/4분기,101p\n2024년 3/4분기,102r\n2024년 4/4분기,x\n')
W('header-year.csv', '항목,2023,2024,2025\n구리,1,2,3\n니켈,4,5,6\n')
W('corner.csv', ',2023,2024,2025\n구리,1,2,3\n니켈,4,5,6\n')
W('totals.csv', '품목,수입\n구리,10\n니켈,20\n합계,30\n')
W('empty.csv', '')
W('blank.csv', '\n\n\n')
W('oneline.csv', 'a,b,c\n')
W('onecol.csv', '가격\n1\n2\n3\n')
W('ragged.csv', 'a,b\n1,2,3,4\n5\n6,7\n')
W('quoted.csv', '연도,메모,값\n2023,"첫째 줄\n둘째 줄",1\n2024,"쉼표, 있음",2\n')
W('dupes.csv', '연도,값,값\n2023,1,2\n2024,3,4\n')
W('script.csv', '연도,<img src=x onerror=window.__xss=1>,"<script>window.__xss=2</script>"\n2023,1,2\n<img src=http://example.invalid/a.png>,3,4\n2024,5,6\n')
W('wide.csv', 'date,' + ','.join(f's{i}' for i in range(300)) + '\n' + ''.join(f'2024-{m:02d},' + ','.join(str(i + m) for i in range(300)) + '\n' for m in range(1, 13)))

# 상태가 바뀌는 곳
W('state.csv', '제목 줄\n\n연도,값\n2023,1\n2024,2\n\n품목,수량,금액\n구리,1,2\n니켈,3,4\n아연,5,6\n')
W('mixed.csv', '구분,값\n2023,1\n2024Q1,2\n2024Q2,3\n')
W('single.csv', '연도,값\n2024,1\n')
W('long-format.csv', '품목,연도,값\n구리,2023,1\n구리,2024,2\n니켈,2023,3\n니켈,2024,4\n')
W('units3.csv', '연도,가격 (USD/t),수량 (천톤),증가율\n2023,1,2,3%\n2024,4,5,6%\n')
W('sparse.csv', ''.join(f'a{i},b{i}\n\n' for i in range(3000)))
W('sort.csv', '품목,값\n구리,3\n니켈,1\n아연,2\n')

# 큰 파일
W('big.csv', 'date,item,value\n' + ''.join(f'2024-01-01,x,{i}\n' for i in range(180_000)))
W('long-series.csv', 'date,price\n' + ''.join(f'{1990 + i // 365}-{(i // 30) % 12 + 1:02d}-{i % 28 + 1:02d},{100 + i % 50}\n' for i in range(20_000)))

# 문서
(proj / 'doc.md').write_text("""# 표 문서

표 1. 연간 실적 (단위: 억원)

| 구분 | 2023 | 2024 | 2025(E) |
|---|---:|---:|---:|
| 매출 | **1,200** | 1,300 | 1,450 |
| 영업이익 | [150](#x) | (20) | 180 |
| 증가율 | 3.0% | 8.3% | 11.5% |

> | 연도 | 값 |
> |---|---:|
> | 2023 | 1 |
> | 2024 | 2 |

- 목록 속 표

  | 연도 | 값 |
  |---|---:|
  | 2023 | 5 |
  | 2024 | 6 |

| 헤더만 | 값 |
|---|---|

| 2023 | 2024 |
|---:|---:|
| 1 | 2 |
| 3 | 4 |
""", encoding='utf-8')
(proj / 'span.html').write_text('<!doctype html><html><body><h1>병합 표</h1><table><tr><th rowspan=2>구분</th><th colspan=2>수입</th></tr><tr><th>구리</th><th>니켈</th></tr><tr><td>2023</td><td>1</td><td>2</td></tr></table></body></html>', encoding='utf-8')
(proj / 'page.html').write_text('<!doctype html><html><head><title>웹 표</title></head><body><h1>웹 표</h1><table><tr><th>연도</th><th>값</th></tr><tr><td>2023</td><td>1</td></tr><tr><td>2024</td><td>2</td></tr></table></body></html>', encoding='utf-8')
(proj / 'deck.md').write_text('---\nmarp: true\n---\n\n# 표지\n\n| 연도 | 값 |\n|---|---:|\n| 2023 | 1 |\n| 2024 | 2 |\n', encoding='utf-8')

# 엑셀
pink = ''.join([
    xml_row(1, {'A': 'World Bank Commodity Price Data'}), xml_row(2, {'A': 'updated 2 November 2026'}),
    xml_row(5, {'B': 'Crude oil, average', 'C': 'Copper', 'D': 'Nickel'}), xml_row(6, {'B': '($/bbl)', 'C': '($/mt)', 'D': '($/mt)'}), xml_row(7, {'B': 'CRUDE_PETRO', 'C': 'COPPER', 'D': 'NICKEL'}),
    *[xml_row(8 + i, {'A': f'2024M{i + 1:02d}', 'B': 80 + i, 'C': 8000 + i * 10, 'D': '…' if i == 2 else 16000 + i}) for i in range(12)],
])
make_xlsx(proj / 'pink.xlsx', sheets=[('Monthly Prices', pink, None)])
report_rows = ''.join([
    xml_row(2, {'B': '주요 지표 현황', 'F': '(단위: 조원, %)'}),
    xml_row(4, {'B': '구분', 'C': '2023', 'E': '2024'}), xml_row(5, {'C': '상반기', 'D': '하반기', 'E': '상반기', 'F': '하반기'}),
    xml_row(6, {'B': '[실물]'}),
    xml_row(7, {'B': '생산', 'C': 1, 'D': 2, 'E': 3, 'F': 4}), xml_row(8, {'B': '소비', 'C': 5, 'D': 6, 'E': 7, 'F': 8}),
    xml_row(9, {'B': '[대외]'}),
    xml_row(10, {'B': '수출', 'C': 9, 'D': 10, 'E': 11, 'F': 12}),
    xml_row(11, {'B': '* 잠정치'}), xml_row(12, {'B': '자료: 통계청'}),
]) + merged(['C4:D4', 'E4:F4', 'B4:B5'])
make_xlsx(proj / 'report.xlsx', sheets=[('요약', report_rows, None)])
side = ''.join([
    xml_row(3, {'B': '연도', 'C': '수입', 'E': '연도', 'F': '수출', 'H': '메모'}),
    xml_row(4, {'B': 2023, 'C': 1, 'E': 2023, 'F': 10, 'H': '비고입니다'}), xml_row(5, {'B': 2024, 'C': 2, 'E': 2024, 'F': 20}), xml_row(6, {'B': 2025, 'C': 3, 'E': 2025, 'F': 30}),
])
make_xlsx(proj / 'side.xlsx', sheets=[('옆', side, None)])
styled = ''.join([
    xml_row(1, {'A': '날짜', 'B': '월', 'C': '값', 'D': '비율', 'E': '오류', 'F': '지수'}),
    *[xml_row(2 + i, {'A': (45292 + i * 31, 1), 'B': (45292 + i * 31, 2), 'C': (1234.5 + i, 3), 'D': (0.053 + i / 100, 4), 'E': '#DIV/0!' if i == 1 else i, 'F': (1500.0 * (i + 1), 5)}) for i in range(4)],
])
make_xlsx(proj / 'styled.xlsx', sheets=[('형식', styled, None)], formats=[(164, 'yyyy-mm-dd'), (165, 'yyyy&quot;년&quot; m&quot;월&quot;'), (166, '#,##0.00;(#,##0.00)'), (167, '0.0%'), (168, '0.00E+00')], xfs=(0, 164, 165, 166, 167, 168))
make_xlsx(proj / 'hidden.xlsx', sheets=[('보임', xml_row(1, {'A': '연도', 'B': '값'}) + xml_row(2, {'A': 2024, 'B': 1}), None), ('숨김', xml_row(1, {'A': '비밀'}), 'hidden'), ('빈 시트', '', None)])
heavy = ''.join(xml_row(i + 1, {'A': f'품목{i // 2}', 'B': i, 'C': i * 2}) for i in range(30_000)) + merged([f'A{i * 2 + 1}:A{i * 2 + 2}' for i in range(5000)])
make_xlsx(proj / 'heavy.xlsx', sheets=[('큰 시트', heavy, None)])

server, url, port = serve(proj, base / 'config')

OPTION = """(() => { const c = window.echarts.getInstanceByDom(document.querySelector('#lec-chart-plot')); const o = c?.getOption(); if (!o) return null;
  return { x: o.xAxis[0].data, axes: o.yAxis.map((a) => a.name), series: o.series.map((s) => ({ name: s.name, type: s.type, axis: s.yAxisIndex, data: s.data })) }; })()"""
HEADS = "[...document.querySelectorAll('#lec-view .csv-head th[data-col]')].map((h) => { const c = h.cloneNode(true); c.querySelector('small')?.remove(); c.querySelector('button')?.remove(); return c.textContent; })"

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900}, locale='ko-KR', permissions=['clipboard-read', 'clipboard-write'])
        page = ctx.new_page()
        errors = []
        outside = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: outside.append(r.url) if '127.0.0.1' not in r.url and not r.url.startswith(('data:', 'blob:')) else None)
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        settle = lambda ms=250: page.wait_for_timeout(ms)
        press = page.keyboard.press
        heads = lambda: page.evaluate(HEADS)
        cells = lambda n: page.evaluate("(n) => [...document.querySelectorAll('#lec-view .csv-rows tr.cv-line')].map((r) => r.cells[n]?.textContent)", n)
        summary = lambda: page.inner_text('#lec-view .csv-summary')
        toast_has = lambda s: page.wait_for_function('(s) => document.querySelector("#lec-toast").textContent.includes(s)', arg=s, timeout=4000) and True
        chips = lambda: page.evaluate("[...document.querySelectorAll('#lec-view .csv-region')].map((b) => b.textContent)")

        def data(path):
            page.evaluate("(p) => import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'code', path: p }))", path)
            page.wait_for_function("(p) => document.querySelector('#lec-view')?.dataset.codePath === p", arg=path, timeout=30000)
            page.wait_for_selector('#lec-view .csv-bar, #lec-view .cv-line, #lec-view .xl-empty', timeout=30000)
            settle(250)

        def chart(button='#lec-view .csv-chart'):
            page.click(button)
            page.wait_for_selector('#lec-chart:not([hidden])', timeout=8000)
            page.wait_for_function("!!window.echarts?.getInstanceByDom(document.querySelector('#lec-chart-plot'))", timeout=20000)
            settle(200)
            o = page.evaluate(OPTION)
            note = page.inner_text('#lec-chart-note')
            press('Escape')
            page.wait_for_selector('#lec-chart', state='hidden')
            return o, note

        def menu(text):
            page.wait_for_selector('#lec-menu:not([hidden])')
            page.locator('#lec-menu button', has_text=text).first.click()

        print('[실제 자료의 모양]')
        data('ecos.csv')
        o, _ = chart()
        check('ECOS: 머리행의 시점 — 앞의 글 열은 계열 이름으로, 단위 열은 단위로', len(o['x']) == 12 and o['x'][0] == '2024/01' and [s['name'] for s in o['series']] == ['총지수 (2020=100)', '공산품 (2020=100)'] and o['axes'] == ['2020=100'], o and ([s['name'] for s in o['series']], o['axes']))
        data('kosis.csv')
        o, _ = chart()
        check('KOSIS: 위의 제목·단위 줄, 머리행의 시점', o['x'] == ['2024.01', '2024.02', '2024.03'] and [s['name'] for s in o['series']] == ['광공업생산지수', '제조업'] and o['axes'] == ['2020=100'], (o['x'], o['axes']))
        data('fred.csv')
        o, _ = chart()
        check("FRED: 빈 값 '.' 은 끊긴 곳", o['series'][0]['data'][2] in (None, '-') and len(o['x']) == 4, o['series'])
        check('FRED: 요약 줄', summary().startswith('월별 · 2024-01 ~ 2024-04'), summary())
        data('bloomberg.csv')
        check('Bloomberg: 미국식 날짜, 최근 것이 위 — 요약', summary().startswith('월별 · 2024-01 ~ 2024-12') or '2024-01-15 ~ 2024-12-15' in summary(), summary())
        o, _ = chart()
        check('Bloomberg: 오래된 것부터', o['x'][0] == '01/15/2024' and o['x'][-1] == '12/15/2024', o['x'][:2])
        data('dayfirst.csv')
        o, _ = chart()
        check('일/월 표기: 31/01 이 있으면 01/02 는 2월 1일', o['x'] == ['31/01/2024', '01/02/2024', '02/02/2024'], o['x'])
        data('cp949.csv')
        check('CP949 csv', heads() == ['날짜', '가격'] and summary().startswith('월별'), heads())
        data('semi.csv')
        check('세미콜론', heads() == ['date', 'price'])
        data('tabs.tsv')
        check('tsv', heads() == ['date', 'price'] and summary().startswith('월별'), heads())
        data('negative.csv')
        o, _ = chart()
        check('괄호·△ 는 음수', o['series'][0]['data'] == [1200, -300, -50] and o['series'][1]['data'] == [3, -1.5, -2.5], o['series'])
        data('flags.csv')
        o, _ = chart()
        check('1/4분기 표기, p·r 표시, x 는 끊긴 곳', o['series'][0]['data'][:3] == [100, 101, 102] and o['series'][0]['data'][3] in (None, '-'), o['series'])
        check('분기 요약', summary().startswith('분기별 · 2024Q1 ~ 2024Q4'), summary())
        data('header-year.csv')
        check('머리행이 시점인 csv — 머리행으로', heads() == ['항목', '2023', '2024', '2025'], heads())
        o, _ = chart()
        check('머리행이 시점인 csv — 차트', o['x'] == ['2023', '2024', '2025'] and [s['name'] for s in o['series']] == ['구리', '니켈'], (o['x'], [s['name'] for s in o['series']]))
        data('corner.csv')
        o, _ = chart()
        check('왼쪽 위 칸이 빈 표', o['x'] == ['2023', '2024', '2025'], o['x'])
        data('totals.csv')
        o, note = chart()
        check('합계 행은 차트에서 뺌', o['x'] == ['구리', '니켈'] and '합계' in note, (o['x'], note))

        print('[지저분한 엑셀]')
        data('pink.xlsx')
        check('World Bank: 세 줄 머리행 (이름·단위·코드), 2024M01', heads()[1].startswith('Crude oil') and 'CRUDE_PETRO' in heads()[1] and summary().startswith('월별 · 2024-01 ~ 2024-12'), (heads(), summary()))
        o, _ = chart()
        check('World Bank: 단위별 양축', set(o['axes']) == {'$/bbl', '$/mt'} and o['series'][2]['data'][2] in (None, '-'), (o['axes'],))
        data('report.xlsx')
        check('보고서 표: 제목과 단위가 한 줄, 병합 머리행', heads()[:3] == ['구분', '2023 · 상반기', '2023 · 하반기'], heads())
        check('제목 줄을 표에 넣지 않음', '주요 지표 현황' in page.inner_text('.csv-title') and '단위' in page.inner_text('.csv-title'), page.inner_text('.csv-regions'))
        check('주·자료 줄은 뺌', '* 잠정치' not in cells(1) and '자료: 통계청' not in cells(1), cells(1))
        o, _ = chart()
        check('보고서 표: 두 줄 머리행의 시점으로 행과 열을 바꿈', o['x'] == ['2023 · 상반기', '2023 · 하반기', '2024 · 상반기', '2024 · 하반기'] and '생산' in [s['name'] for s in o['series']], (o['x'], [s['name'] for s in o['series']]))
        data('side.xlsx')
        check('옆으로 둔 표 둘 — 표 단추', len(chips()) == 3, chips())
        page.locator('.csv-region[data-region="1"]').click()
        settle(200)
        check('둘째 표', heads()[:2] == ['연도', '수출'], heads())
        page.locator('.csv-rows tr.cv-line').first.locator('td').nth(2).click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        hint = page.inner_text('#lec-menu')
        press('Escape')
        check('이 칸 복사의 이름은 엑셀의 칸', 'F4' in hint, hint[:200])
        page.locator('.csv-head th[data-col="1"]').click(button='right')
        menu('차분')
        page.wait_for_selector('th.csv-calc')
        tip = page.evaluate("[...document.querySelectorAll('td.csv-calc')].map((c) => c.title).join('')")
        check('계산 칸에 다른 칸의 수식 풍선이 뜨지 않음', tip == '', tip)
        data('styled.xlsx')
        check('엑셀 표시 형식: 날짜 열이 시간으로', summary().startswith('월별') or summary().startswith('일별'), summary())
        o, _ = chart()
        names = [s['name'] for s in o['series']]
        check('월 표시 열은 계열이 아니고 #DIV/0! 는 끊긴 곳', '월' not in names and o['series'][names.index('오류')]['data'][1] in (None, '-'), o['series'])
        check('백분율·지수 표기도 숫자', '비율' in names and '지수' in names, names)
        data('hidden.xlsx')
        check('숨긴 시트가 있어도', page.locator('.xl-sheet').count() == 3 and heads() == ['연도', '값'], heads())
        page.locator('.xl-sheet', has_text='빈 시트').click()
        page.wait_for_selector('.xl-empty', timeout=5000)
        check('빈 시트', page.locator('.xl-empty').count() == 1)

        print('[망가진 입력]')
        for name in ('empty.csv', 'blank.csv', 'oneline.csv', 'onecol.csv', 'ragged.csv', 'quoted.csv', 'dupes.csv'):
            before = len(errors)
            data(name)
            page.click('.csv-chart')
            settle(500)
            press('Escape')
            settle(100)
            check(f'{name}: 화면이 깨지지 않음', len(errors) == before and page.locator('#lec-chart').is_hidden(), errors[before:])
        data('quoted.csv')
        o, _ = chart()
        check('칸 안의 줄바꿈·쉼표', o['x'] == ['2023', '2024'] and o['series'][0]['data'] == [1, 2], o)
        data('dupes.csv')
        o, _ = chart()
        check('같은 이름의 열', len(o['series']) == 2, o['series'])

        print('[끼어든 글]')
        data('script.csv')
        page.click('.csv-chart')
        page.wait_for_selector('#lec-chart:not([hidden])')
        page.wait_for_function("!!window.echarts?.getInstanceByDom(document.querySelector('#lec-chart-plot'))", timeout=20000)
        settle(300)
        box = page.locator('#lec-chart-plot').bounding_box()
        page.mouse.move(box['x'] + box['width'] * 0.5, box['y'] + box['height'] * 0.5)
        settle(300)
        html = page.evaluate("document.querySelector('#lec-chart').innerHTML")
        press('Escape')
        settle(150)
        check('차트 창에 끼어든 태그가 되지 않음', '<img' not in html and page.evaluate('window.__xss') is None, html[:300] if '<img' in html else '')
        check('밖으로 나간 요청 없음', not outside, outside[:3])

        print('[큰 파일]')
        t0 = time.time()
        data('big.csv')
        opened = time.time() - t0
        check(f'18만 행 csv 를 엶 ({opened:.1f}초)', opened < 12 and page.locator('.csv-table').count() == 1, opened)
        t0 = time.time()
        page.locator('.csv-filter input[data-col="2"]').fill('>179990')
        page.wait_for_function("document.querySelector('.csv-count').textContent.includes('중 9행')", timeout=15000)
        check(f'거르기 ({time.time() - t0:.1f}초)', time.time() - t0 < 5)
        page.click('.csv-clear')
        settle(300)
        t0 = time.time()
        data('long-series.csv')
        page.locator('.csv-head th[data-col="1"]').click(button='right')
        menu('이동평균')
        page.wait_for_selector('th.csv-calc', timeout=15000)
        check(f'2만 행 계산 열 ({time.time() - t0:.1f}초)', time.time() - t0 < 8)
        t0 = time.time()
        o, _ = chart()
        check(f'2만 점 차트 ({time.time() - t0:.1f}초)', len(o['x']) == 20000 and time.time() - t0 < 10, len(o['x']))
        data('wide.csv')
        t0 = time.time()
        page.click('.csv-chart')
        page.wait_for_function("!!window.echarts?.getInstanceByDom(document.querySelector('#lec-chart-plot'))", timeout=20000)
        on = page.locator('#lec-chart-series input:checked').count()
        check(f'300열: 6개만 켜 둠 ({time.time() - t0:.1f}초)', on == 6, on)
        t0 = time.time()
        page.click('#lec-chart-swap')
        settle(300)
        check(f'300열 표의 행↔열 ({time.time() - t0:.1f}초)', page.locator('#lec-chart-series label').count() >= 1 and time.time() - t0 < 5)
        press('Escape')
        data('big.csv')
        t0 = time.time()
        page.click('.csv-chart')
        page.wait_for_function("!!window.echarts?.getInstanceByDom(document.querySelector('#lec-chart-plot'))", timeout=30000)
        settle(200)
        page.click('#lec-chart-swap')
        settle(800)
        rows_listed = page.locator('#lec-chart-series label').count()
        check(f'18만 행 표의 행↔열이 멈추지 않음 ({time.time() - t0:.1f}초, 목록 {rows_listed}개)', rows_listed <= 1000 and time.time() - t0 < 15, rows_listed)
        press('Escape')
        t0 = time.time()
        data('heavy.xlsx')
        check(f'3만 행·병합 5천 개 시트 ({time.time() - t0:.1f}초)', time.time() - t0 < 15 and page.locator('.csv-table').count() == 1, time.time() - t0)

        print('[다른 기능과 겹치는 곳]')
        page.click('.side-tabs button[data-tab="files"]')
        page.locator('#lec-tree .row.file[data-doc="doc.md"]').click()
        page.wait_for_selector('#lec-view h1:has-text("표 문서")')
        settle(300)
        tables = page.locator('#lec-view table')

        def doc_chart(i):
            tables.nth(i).locator('td, th').first.click(button='right')
            menu('차트로 보기')
            page.wait_for_function("!!window.echarts?.getInstanceByDom(document.querySelector('#lec-chart-plot'))", timeout=15000)
            settle(200)
            o = page.evaluate(OPTION)
            title = page.inner_text('#lec-chart-title')
            press('Escape')
            page.wait_for_selector('#lec-chart', state='hidden')
            return o, title

        o, title = doc_chart(0)
        names = [s['name'] for s in o['series']]
        check('문서 표: 굵게·링크 칸, (20) 음수, 2025(E)', o['x'] == ['2023', '2024', '2025(E)'] and o['series'][names.index('영업이익')]['data'] == [150, -20, 180], o['series'])
        check('문서 표: 증가율은 오른쪽 축, 캡션의 단위', '억원' in o['axes'] and '%' in o['axes'], o['axes'])
        o, _ = doc_chart(1)
        check('인용 속 표', o['x'] == ['2023', '2024'])
        o, _ = doc_chart(2)
        check('목록 속 표', o['series'][0]['data'] == [5, 6])
        tables.nth(3).locator('th').first.click(button='right')
        menu('차트로 보기')
        check('머리행뿐인 표는 알림', toast_has('차트로 볼 숫자가 없습니다'))
        o, _ = doc_chart(4)
        check('머리행이 연도뿐인 표', len(o['x']) >= 1, o)
        page.locator('#lec-tree .row.file[data-doc="page.html"]').click()
        frame = page.frame_locator('#lec-view iframe.lec-html')
        frame.locator('td').first.wait_for(timeout=8000)
        settle(300)
        frame.locator('td').first.click(button='right')
        menu('차트로 보기')
        page.wait_for_function("!!window.echarts?.getInstanceByDom(document.querySelector('#lec-chart-plot'))", timeout=15000)
        settle(200)
        check('html 문서의 표', page.evaluate(OPTION)['x'] == ['2023', '2024'])
        press('Escape')
        page.locator('#lec-tree .row.file[data-doc="deck.md"]').click()
        page.wait_for_selector('#lec-view .lec-slide', timeout=8000)
        settle(300)
        page.locator('#lec-view table td').first.click(button='right')
        menu('차트로 보기')
        page.wait_for_function("!!window.echarts?.getInstanceByDom(document.querySelector('#lec-chart-plot'))", timeout=15000)
        settle(200)
        check('발표 문서의 표', page.evaluate(OPTION)['x'] == ['2023', '2024'])
        press('Escape')

        data('report.xlsx')
        before_chip = page.get_attribute('.csv-region[data-region="0"]', 'aria-pressed')
        page.evaluate("import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'code', path: 'report.xlsx', line: 12 }))")
        settle(600)
        at = page.locator('.cv-line[data-line="12"]').count()
        check('표 밖의 줄로 가면 그 줄이 보임', at == 1, (before_chip, chips()))
        page.locator('.csv-region[data-region="0"]').click()
        settle(200)

        print('[차트 창의 조작]')
        data('units3.csv')
        page.click('.csv-chart')
        page.wait_for_function("!!window.echarts?.getInstanceByDom(document.querySelector('#lec-chart-plot'))", timeout=15000)
        settle(200)
        on = page.evaluate("[...document.querySelectorAll('#lec-chart-series input')].map((i) => i.checked)")
        check('단위가 셋이면 둘만 켜 둠', on == [True, True, False], on)
        page.locator('#lec-chart-series input').nth(2).click()
        check('셋째 단위를 켜면 알리고 켜지 않음', toast_has('축은 둘까지') and not page.locator('#lec-chart-series input').nth(2).is_checked())
        before = len(errors)
        for i in range(2):
            page.locator('#lec-chart-series input').nth(i).uncheck()
        settle(200)
        check('계열을 모두 꺼도 오류가 없음', len(errors) == before, errors[before:])
        page.locator('#lec-chart-series input').nth(2).check()
        settle(200)
        check('다시 켜면 그려짐', [s['name'] for s in page.evaluate(OPTION)['series']] == ['증가율'], page.evaluate(OPTION))
        page.locator('#lec-chart-scale button[data-scale="level"]').click()
        settle(200)
        check("켠 것이 없는 단위를 골라도 오류가 없음", len(errors) == before, errors[before:])
        page.locator('#lec-chart-kind button[data-kind="bar"]').click()
        page.locator('#lec-chart-scale button[data-scale="both"]').click()
        settle(200)
        page.set_viewport_size({'width': 700, 'height': 480})
        settle(400)
        size = page.evaluate("(() => { const c = document.querySelector('#lec-chart-plot canvas'); const b = document.querySelector('.chart-box').getBoundingClientRect(); return [c.getBoundingClientRect().width, b.right <= innerWidth + 1, b.bottom <= innerHeight + 1]; })()")
        check('작은 창: 차트가 따라 줄고 창 안에 있음', size[0] > 200 and size[1] and size[2], size)
        page.set_viewport_size({'width': 1440, 'height': 900})
        settle(300)
        press('Escape')
        for name in ('single.csv', 'mixed.csv'):
            data(name)
            before = len(errors)
            o, _ = chart()
            check(f'{name}: 그려짐', len(o['x']) >= 1 and len(errors) == before, o)
        data('long-format.csv')
        o, note = chart()
        check('품목별로 쌓은 표: 알림', '여러 행' in note, note)
        page.locator('.csv-filter input[data-col="0"]').fill('=구리')
        settle(300)
        o, note = chart()
        check('거르면 그 품목의 시계열', o['x'] == ['2023', '2024'] and '여러 행' not in note and [s['name'] for s in o['series']] == ['값'], (o['x'], note))
        page.click('.csv-clear')
        data('sort.csv')
        page.locator('.csv-head th[data-col="1"]').click()
        settle(150)
        o, _ = chart()
        check('시간이 없는 표는 정렬한 차례로 차트', o['x'] == ['니켈', '아연', '구리'], o['x'])
        page.locator('.csv-head th[data-col="1"]').click()
        page.locator('.csv-head th[data-col="1"]').click()

        print('[바뀌는 상태]')
        data('state.csv')
        got = chips()
        check('csv 의 표 둘', len(got) == 3, got)
        page.locator('.csv-region[data-region="1"]').click()
        settle(200)
        page.locator('.csv-head th[data-col="1"]').click(button='right')
        menu('누적')
        page.wait_for_selector('th.csv-calc')
        (proj / 'state.csv').write_text('제목 줄\n\n연도,값\n2023,1\n2024,2\n', encoding='utf-8')
        page.wait_for_function("document.querySelectorAll('.csv-region').length === 0 || document.querySelector('.csv-region[aria-pressed=\"true\"]')?.dataset.region !== '1'", timeout=8000)
        settle(300)
        check('표가 줄어 고른 표가 없어지면 있는 표로', heads()[:2] == ['연도', '값'] and page.locator('th.csv-calc').count() == 0, (heads(), chips()))
        (proj / 'state.csv').write_text('연도,값\n2023,1\n2024,2\n', encoding='utf-8')
        page.wait_for_function("document.querySelector('.csv-regions').hidden", timeout=8000)
        check('깔끔해지면 단추가 사라짐', heads() == ['연도', '값'])
        (proj / 'state.csv').unlink()
        page.wait_for_selector('#lec-view .doc-missing', timeout=8000)
        check('보던 파일을 지우면 없다고 알림', page.locator('#lec-view .csv-table').count() == 0)
        data('report.xlsx')
        before = len(errors)
        for _ in range(8):
            page.locator('.csv-depth button[data-depth="-1"]').click() if page.locator('.csv-depth button[data-depth="-1"]').count() else None
            settle(30)
        check('머리행 0줄: 열 글자로', len(errors) == before and page.inner_text('.csv-depth b').startswith('0'), page.inner_text('.csv-regions'))
        for _ in range(9):
            page.locator('.csv-depth button[data-depth="1"]').click()
            settle(30)
        check('머리행을 끝까지 늘려도 몸통이 남음', len(errors) == before and len(cells(0)) >= 1, cells(0))
        for _ in range(9):
            page.locator('.csv-depth button[data-depth="-1"]').click()
            settle(30)
        page.locator('.csv-depth button[data-depth="1"]').click()
        page.locator('.csv-depth button[data-depth="1"]').click()
        settle(150)
        page.locator('.csv-head th[data-col="1"]').click()
        page.locator('.csv-filter input[data-col="1"]').fill('>1')
        settle(200)
        page.locator('.csv-region[data-region="all"]').click()
        settle(200)
        page.locator('.csv-region[data-region="0"]').click()
        settle(200)
        check('표를 오가도 그 표의 거르기는 그대로', page.input_value('.csv-filter input[data-col="1"]') == '>1', page.input_value('.csv-filter input[data-col="1"]'))
        page.click('.csv-clear')
        page.locator('.csv-head th[data-col="1"]').click()
        page.locator('.csv-head th[data-col="1"]').click()
        data('sparse.csv')
        check('빈 줄로 띄운 글 3천 줄: 표 단추를 만들지 않음', page.locator('.csv-regions').is_hidden() and page.locator('.csv-region').count() == 0, page.locator('.csv-region').count())
        data('fred.csv')
        page.locator('.csv-head th[data-col="1"]').click(button='right')
        menu('차분')
        page.wait_for_selector('th.csv-calc')
        page.locator('.csv-headrow input').uncheck()
        settle(200)
        before = len(errors)
        page.locator('.csv-headrow input').check()
        settle(200)
        check('첫 줄은 머리행을 켜고 꺼도 오류가 없음', len(errors) == before, errors[before:])
        check('자료 파일에는 편집 단추가 없음', page.locator('.cv-edit').count() == 0 and page.locator('#lec-st-edit').is_hidden() and page.locator('#lec-btn-edit').is_disabled())
        page.locator('.csv-rows tr.cv-line').first.locator('td').nth(1).click()
        press('F2')
        check('자료 파일의 F2 는 까닭을 알림', toast_has('자료 파일은 볼 수만'))
        data('report.xlsx')
        page.locator('.csv-rows tr.cv-line').nth(1).locator('td').nth(1).click()
        press('Shift+Enter')
        settle(150)
        press('Shift+ArrowLeft')
        ref = toast_has('@report.xlsx')
        clip = page.evaluate('navigator.clipboard.readText()')
        check('표를 고른 채 위치 복사: 원래 행 번호', "'요약' 시트 8행" in clip or "'요약' 시트 7행" in clip, clip)
        press('Escape')
        page.keyboard.press('Control+f')
        page.wait_for_selector('#lec-find-input', timeout=3000)
        page.keyboard.type('수출')
        settle(400)
        found = page.inner_text('#lec-find-count')
        press('Escape')
        check('찾기가 고른 표 안에서', '1' in found, found)

        print('[문서로 보내기]')
        data('fred.csv')
        page.locator('.csv-filter input[data-col="1"]').fill('>309')
        page.wait_for_function("document.querySelector('.csv-count').textContent.includes('중')", timeout=3000)
        page.click('.csv-send')
        page.wait_for_selector('#lec-insert:not([hidden])')
        page.locator('#lec-insert-list li, #lec-insert button').filter(has_text='새 문서').first.click()
        page.wait_for_selector('#lec-insert-input:visible', timeout=4000)
        page.fill('#lec-insert-input', '보낸 표.md')
        press('Enter')
        page.wait_for_selector('.lec-editor .CodeMirror', timeout=8000)
        settle(400)
        press('Control+s')
        settle(600)
        sent = (proj / '보낸 표.md').read_text(encoding='utf-8')
        check('새 문서로 보낸 Markdown 표', '| observation_date | CPIAUCSL |' in sent and '| ---' in sent and '| 2024-02-01 | 310.326 |' in sent, sent[:300])
        press('Control+e')
        settle(400)

        print('[여러 칸·보기만]')
        page.click('.side-tabs button[data-tab="files"]')
        page.locator('#lec-tree .row.file[data-doc="span.html"]').click()
        frame = page.frame_locator('#lec-view iframe.lec-html')
        frame.locator('td').first.wait_for(timeout=8000)
        settle(300)
        before = len(errors)
        frame.locator('td').first.click(button='right')
        menu('차트로 보기')
        settle(800)
        press('Escape')
        settle(150)
        check('병합이 있는 html 표도 탈이 없음', len(errors) == before, errors[before:])
        data('fred.csv')
        page.evaluate("import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'code', path: 'pink.xlsx', newTab: true }))")
        page.wait_for_function("document.querySelector('#lec-view')?.dataset.codePath === 'pink.xlsx'", timeout=8000)
        page.wait_for_selector('#lec-view .csv-bar', timeout=8000)
        settle(300)
        page.click('#lec-doctab-spread')
        settle(600)
        cells_shown = page.locator('.csv-chart:visible').count()
        check('모두 펼치기: 칸마다 데이터 보기', cells_shown >= 2, cells_shown)
        page.locator('.csv-chart:visible').first.click()
        page.wait_for_function("!!window.echarts?.getInstanceByDom(document.querySelector('#lec-chart-plot'))", timeout=15000)
        settle(200)
        title = page.inner_text('#lec-chart-title')
        press('Escape')
        settle(200)
        check('모두 펼치기에서 누른 칸의 표로', 'fred' in title or 'pink' in title, title)
        page.click('#lec-doctab-spread')
        settle(400)

        print('[보기만 하는 프로젝트]')
        page.once('dialog', lambda d: d.accept(str(ROOT / 'samples')))
        page.click('#lec-btn-open')
        page.wait_for_function("document.querySelectorAll('#lec-tablist .lec-tab').length === 2", timeout=8000)
        settle(800)
        data('data/월별-가격.csv')
        o, _ = chart()
        check('예제에서도 차트', len(o['x']) >= 3 and len(o['series']) >= 1, o['x'][:3])
        page.locator('#lec-view .csv-head th.num').first.click(button='right')
        menu('차분')
        page.wait_for_selector('#lec-view th.csv-calc')
        check('예제에서도 계산 열', page.locator('#lec-view td.csv-calc').count() >= 3)
        page.locator('#lec-view .csv-send').click()
        told = toast_has('보기만')
        check('예제에서는 문서로 보내지 않고 까닭을 알림', told and page.locator('#lec-insert').is_hidden())
        page.locator('#lec-tablist .lec-tab.active .tab-close').click()
        settle(500)

        print('[스타일 24종]')
        data('report.xlsx')
        page.locator('#lec-view .csv-head th[data-col="1"]').click(button='right')
        menu('누적')
        page.wait_for_selector('#lec-view th.csv-calc')
        themes = page.evaluate("[...document.querySelectorAll('#lec-theme option')].map((o) => o.value).filter((v) => v && v !== 'auto')")
        CONTRAST = """(() => { const nums = (c) => { const m = c.match(/[\\d.]+/g).map(Number); return c.startsWith('color(') ? m.slice(0, 3).map((v) => v * 255) : m.slice(0, 3); };
          const alpha = (c) => { const a = /\\/\\s*([\\d.]+)\\)|rgba\\([^)]*,\\s*([\\d.]+)\\)/.exec(c); return a ? Number(a[1] ?? a[2]) : 1; };
          const back = (el) => { for (let e = el; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; if (alpha(c) > 0.99) return nums(c); } return [255, 255, 255]; };
          const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
          const ratio = (el) => { const [x, y] = [lum(nums(getComputedStyle(el).color)), lum(back(el))].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
          const q = (s) => document.querySelector(`#lec-view ${s}`);
          return { chip: ratio(q('.csv-region[aria-pressed="true"]')), other: ratio(q('.csv-region[aria-pressed="false"]')), calc: ratio(q('td.csv-calc')), title: ratio(q('.csv-title')), summary: ratio(q('.csv-summary')) }; })()"""
        low = {}
        for theme in themes:
            page.select_option('#lec-theme', theme)
            settle(120)
            got = page.evaluate(CONTRAST)
            worst = {k: round(v, 1) for k, v in got.items() if v < 4.5}
            if worst:
                low[theme] = worst
        check(f'스타일 {len(themes)}종: 표 단추·계산 칸·제목·요약의 글자 대비 4.5 이상', len(themes) >= 24 and not low, low)
        page.select_option('#lec-theme', 'auto')
        settle(150)

        print('[스타일과 언어]')
        data('fred.csv')
        page.evaluate("(async () => { const { saveConfig } = await import('/static/js/api.js'); await saveConfig({ theme: 'dark' }); })()")
        page.reload()
        page.wait_for_selector('#lec-tree .row.file')
        data('report.xlsx')
        page.click('.csv-chart')
        page.wait_for_function("!!window.echarts?.getInstanceByDom(document.querySelector('#lec-chart-plot'))", timeout=15000)
        settle(300)
        contrast = page.evaluate("""(() => { const nums = (c) => c.match(/[\\d.]+/g).map(Number).slice(0, 3);
          const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
          const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
          const b = document.querySelector('#lec-chart-kind button[aria-pressed="true"]'); return ratio(nums(getComputedStyle(b).color), nums(getComputedStyle(document.querySelector('.chart-box')).backgroundColor)); })()""")
        check(f'어두운 스타일: 고른 단추의 글자 대비 {contrast:.1f}', contrast >= 4.5, contrast)
        press('Escape')
        page.evaluate("(async () => { const { saveConfig } = await import('/static/js/api.js'); await saveConfig({ theme: 'auto', language: 'en' }); })()")
        page.reload()
        page.wait_for_selector('#lec-tree .row.file')
        data('report.xlsx')
        page.click('.csv-chart')
        page.wait_for_function("!!window.echarts?.getInstanceByDom(document.querySelector('#lec-chart-plot'))", timeout=15000)
        settle(300)
        tools = page.inner_text('.chart-tools')
        press('Escape')
        page.locator('.csv-head th[data-col="1"]').click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        items = page.inner_text('#lec-menu')
        press('Escape')
        bar = page.inner_text('.csv-regions') + page.inner_text('.csv-bar')
        import re
        hangul = lambda s: re.sub(r"[^가-힣]", '', re.sub(r'주요 지표 현황|\(단위: 조원, %\)|요약|구분|상반기|하반기|2023 · |2024 · ', '', s))
        check('영어 화면: 차트 창·열 머리 메뉴·표 단추에 한글이 남지 않음 (문서 내용 빼고)', not hangul(tools) and not hangul(bar) and not hangul(items.replace('2023 · 상반기', '')), (tools, bar[:200], items[:200]))
        page.evaluate("(async () => { const { saveConfig } = await import('/static/js/api.js'); await saveConfig({ language: 'ko' }); })()")

        real = [e for e in errors if 'addressunreachable' not in e]
        check('화면 스크립트 오류 없음', not real, real[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('점검이 중간에 멈춤')
finally:
    stop(server, base)
report()
