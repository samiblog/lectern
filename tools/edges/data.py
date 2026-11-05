"""표와 데이터 보기 (D86): 표 읽기 규칙, 빠른 차트, 요약 줄, 계산 열, 복사·문서로 보내기. 프로젝트·설정은 임시 폴더"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_sheet import make_xlsx  # noqa: E402

fails: list[str] = []
count = 0


def check(name, cond, detail=''):
    global count
    count += 1
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else f' — {detail}'}", flush=True)
    if not cond:
        fails.append(name)


DOC = """# 표 문서

표 1. 구리 시세 (단위: USD/t)

| 연도 | 가격 | 증가율 |
|---|---:|---:|
| 2026 | 9,000 | 5.0% |
| 2025 | 8,600 | 3.0% |
| 2024 | 8,300 | n.a. |

| 항목 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|
| 구리 | 1 | 2 | 3 |
| 니켈 | 4 | 5 | 6 |

| 품목 | 메모 |
|---|---|
| 구리 | 좋음 |
"""
MONTHLY = 'date,price,volume\n' + ''.join(f'2024-{m:02d},{100 + m},{"" if m == 3 else m * 10}\n' for m in range(1, 13)) \
    + ''.join(f'2025-{m:02d},{120 + m},{m * 11}\n' for m in range(1, 13))
LONG = 'date,item,price\n' + ''.join(f'2025-{m:02d},copper,{100 + m}\n2025-{m:02d},nickel,{200 + m}\n' for m in range(1, 7))

base = Path(tempfile.mkdtemp(prefix='lec-data-'))
proj = base / 'proj'
proj.mkdir()
(proj / 'tables.md').write_text(DOC, encoding='utf-8')
(proj / 'monthly.csv').write_text(MONTHLY, encoding='utf-8')
(proj / 'long.csv').write_text(LONG, encoding='utf-8')
(proj / 'text.csv').write_text('a,b\nx,y\n', encoding='utf-8')
SHEET = ('<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row><row r="2"><c r="A2"><v>2024</v></c><c r="B2"><v>10</v></c></row>'
         '<row r="3"><c r="A3"><v>2025</v></c><c r="B3"><v>20</v></c></row>')
make_xlsx(proj / 'book.xlsx', sheets=[('값', SHEET, None)], shared=('연도', '가격'))


def xml_row(n, cells):
    """시험용 시트의 한 행: {열 글자: 값}"""
    out = ''.join(f'<c r="{c}{n}"><v>{v}</v></c>' if isinstance(v, (int, float)) else f'<c r="{c}{n}" t="inlineStr"><is><t>{v}</t></is></c>' for c, v in cells.items())
    return f'<row r="{n}">{out}</row>'


MESSY = ''.join([
    xml_row(1, {'A': '구리 수입 현황'}), xml_row(2, {'A': '(단위: 천톤)'}),
    xml_row(4, {'A': '구분', 'B': '수입', 'D': '수출'}), xml_row(5, {'B': '구리', 'C': '니켈', 'D': '구리', 'E': '니켈'}),
    *[xml_row(6 + i, {'A': 2023 + i, 'B': 10 + i, 'C': 20 + i, 'D': 30 + i, 'E': 40 + i}) for i in range(4)],
    xml_row(10, {'A': '자료: 무역협회'}), xml_row(12, {'A': '둘째 표'}), xml_row(13, {'A': '품목', 'B': '가격'}),
    xml_row(14, {'A': '구리', 'B': 9000}), xml_row(15, {'A': '니켈', 'B': 16000}),
]) + '</sheetData><mergeCells count="2"><mergeCell ref="B4:C4"/><mergeCell ref="D4:E4"/></mergeCells><sheetData>'
make_xlsx(proj / 'messy.xlsx', sheets=[('현황', MESSY, None)])
(proj / 'messy.csv').write_text('구리 시세 통계,,\n단위: USD/t,,\n,,\n연도,가격,재고\n2024,1,5\n2025,2,6\n자료: LME,,\n', encoding='utf-8')
with socket.socket() as s:
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
server = subprocess.Popen([sys.executable, str(ROOT / 'app.py'), '--browser', '--port', str(port), str(proj)], cwd=ROOT,
                          env=os.environ | {'LECTERN_CONFIG_DIR': str(base / 'config')}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
url = f'http://127.0.0.1:{port}/'
for _ in range(60):
    try:
        urllib.request.urlopen(url + 'api/state', timeout=1)
        break
    except Exception:
        time.sleep(0.3)

OPTION = """(() => { const o = window.echarts.getInstanceByDom(document.querySelector('#lec-chart-plot'))?.getOption(); if (!o) return null;
  return { x: o.xAxis[0].data, axes: o.yAxis.map((a) => a.name), series: o.series.map((s) => ({ name: s.name, type: s.type, axis: s.yAxisIndex, data: s.data })) }; })()"""

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1440, 'height': 900}, locale='ko-KR', permissions=['clipboard-read', 'clipboard-write']).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        settle = lambda ms=250: page.wait_for_timeout(ms)
        press = page.keyboard.press
        toast_has = lambda s: page.wait_for_function('(s) => document.querySelector("#lec-toast").textContent.includes(s)', arg=s, timeout=3000) and True
        option = lambda: page.evaluate(OPTION)

        def chart_open():
            page.wait_for_selector('#lec-chart:not([hidden])', timeout=4000)
            page.wait_for_function("!!window.echarts?.getInstanceByDom(document.querySelector('#lec-chart-plot'))", timeout=15000)
            settle(150)

        def menu(text):
            page.wait_for_selector('#lec-menu:not([hidden])')
            page.locator('#lec-menu button', has_text=text).first.click()

        def data(path):
            page.evaluate("(p) => import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'code', path: p }))", path)
            page.wait_for_function("(p) => document.querySelector('#lec-view')?.dataset.codePath === p && document.querySelector('.csv-table tbody.csv-rows tr')", arg=path, timeout=8000)
            settle(250)

        cells = lambda n: page.evaluate("(n) => [...document.querySelectorAll('.csv-rows tr.cv-line')].map((r) => r.cells[n]?.textContent)", n)

        print('[표 읽기]')
        cases = (Path(__file__).parent / 'tabledata_cases.js').read_text(encoding='utf-8')
        res = page.evaluate(f"(async () => {{ const m = await import('/static/js/tabledata.js');\n{cases}\n}})()")
        check(f'tabledata.js 표 점검 {res["n"]}개', not res['fails'], res['fails'][:6])

        print('[문서의 표]')
        page.locator('#lec-tree .row.file[data-doc="tables.md"]').click()
        page.wait_for_selector('#lec-view h1:has-text("표 문서")')
        settle()
        tables = page.locator('#lec-view table')
        tables.nth(0).locator('td').first.click(button='right')
        menu('차트로 보기')
        chart_open()
        o = option()
        check('표 우클릭 차트: 최근 것이 위인 표를 오래된 것부터', o['x'] == ['2024', '2025', '2026'], o)
        check('레벨은 막대·왼쪽 축, 증가율은 선·오른쪽 축', [(s['type'], s['axis']) for s in o['series']] == [('bar', 0), ('line', 1)] and o['axes'] == ['USD/t', '%'], o)
        check('n.a. 는 0 이 아니라 끊긴 곳', o['series'][1]['data'][0] in (None, '-') and o['series'][0]['data'] == [8300, 8600, 9000], o['series'])
        check('제목에 캡션', '구리 시세' in page.inner_text('#lec-chart-title'))
        page.screenshot(path=str(Path(os.environ.get('LEC_SHOTS', base)) / 'chart.png'))
        page.locator('#lec-chart-scale button[data-scale="rate"]').click()
        settle(150)
        o = option()
        check("'증가율'만", [s['name'] for s in o['series']] == ['증가율'], o)
        page.locator('#lec-chart-scale button[data-scale="both"]').click()
        page.locator('#lec-chart-kind button[data-kind="line"]').click()
        settle(150)
        check('종류: 선', {s['type'] for s in option()['series']} == {'line'})
        page.locator('#lec-chart-series input').first.uncheck()
        settle(150)
        check('계열을 끔', [s['name'] for s in option()['series']] == ['증가율'])
        page.locator('#lec-chart-kind button[data-kind="auto"]').click()
        press('Escape')
        page.wait_for_selector('#lec-chart', state='hidden')
        check('Esc 로 닫힘', page.locator('#lec-chart').is_hidden())
        tables.nth(1).locator('td').first.click(button='right')
        menu('차트로 보기')
        chart_open()
        o = option()
        check('머리행이 시점이면 저절로 행과 열을 바꿈', o['x'] == ['2024', '2025', '2026'] and [s['name'] for s in o['series']] == ['구리', '니켈'], o)
        page.click('#lec-chart-swap')
        settle(200)
        o = option()
        check('행↔열로 되돌림', o['x'] == ['구리', '니켈'] and [s['name'] for s in o['series']] == ['2024', '2025', '2026'], o)
        page.mouse.click(10, 10)
        page.wait_for_selector('#lec-chart', state='hidden')
        check('바깥을 누르면 닫힘', True)
        tables.nth(2).locator('td').first.click(button='right')
        menu('차트로 보기')
        check('숫자가 없으면 알리고 열지 않음', toast_has('차트로 볼 숫자가 없습니다') and page.locator('#lec-chart').is_hidden())
        tables.nth(0).locator('tbody tr').nth(0).locator('td').first.click()
        press('Shift+Enter')
        press('Shift+ArrowDown')
        settle(150)
        tables.nth(0).locator('tbody tr').nth(0).locator('td').first.click(button='right')
        menu('차트로 보기')
        chart_open()
        check('하이라이트한 행만 차트로', option()['x'] == ['2025', '2026'], option()['x'])
        press('Escape')
        press('Escape')
        settle(150)

        print('[데이터 보기 — 요약 줄]')
        data('monthly.csv')
        summary = page.inner_text('.csv-summary')
        check('요약 줄: 주기·기간·숫자 열·빈칸', summary == '월별 · 2024-01 ~ 2025-12 · 숫자 열 2 · 빈칸 1', summary)
        page.locator('.csv-filter input[data-col="0"]').fill('2025')
        page.wait_for_function("document.querySelector('.csv-summary').textContent.includes('2025-01 ~ 2025-12')", timeout=3000)
        check('거르면 남은 행으로', '빈칸' not in page.inner_text('.csv-summary'), page.inner_text('.csv-summary'))

        print('[데이터 보기 — 빠른 차트]')
        page.click('.csv-chart')
        chart_open()
        o = option()
        check('거른 행 그대로 차트로', len(o['x']) == 12 and o['x'][0] == '2025-01', o['x'])
        press('Escape')
        page.click('.csv-clear')
        settle(200)
        page.click('.csv-chart')
        chart_open()
        o = option()
        check('점이 많으면 자동은 레벨도 선이 아니라 막대가 뭉개지지 않게', len(o['x']) == 24, len(o['x']))
        press('Escape')
        page.locator('.csv-head th[data-col="1"]').click(button='right')
        menu('이 열을 차트로')
        chart_open()
        check('열 머리 우클릭: 그 열만 켬', [s['name'] for s in option()['series']] == ['price'], option()['series'])
        press('Escape')
        settle(150)

        print('[데이터 보기 — 계산 열]')
        page.locator('.csv-head th[data-col="1"]').click(button='right')
        items = page.evaluate("[...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent)")
        check('메뉴에 전기 대비·전년 동기·차분·누적·이동평균(월별 3·12)·지수', all(any(w in x for x in items) for w in ('전기 대비', '전년 동기', '차분', '누적', '이동평균 3', '이동평균 12', '지수')), items)
        menu('전년 동기 대비')
        page.wait_for_selector('.csv-head th.csv-calc')
        yoy = cells(4)
        check('전년 동기 대비: 월은 12 뺌', yoy[0] == '' and yoy[11] == '' and yoy[12] == '19.8', yoy[10:14])
        before = (proj / 'monthly.csv').read_text(encoding='utf-8')
        check('파일은 그대로', before == MONTHLY)
        page.locator('.csv-head th[data-col="1"]').click(button='right')
        menu('이동평균 3')
        page.wait_for_function("document.querySelectorAll('.csv-head th.csv-calc').length === 2")
        ma = cells(5)
        check('이동평균 3', ma[0] == '' and ma[2] == '102', ma[:4])
        page.locator('.csv-head th.csv-calc').first.click()
        settle(150)
        check('계산 열로 정렬', cells(4)[0] not in ('',), cells(4)[:3])
        page.locator('.csv-head th.csv-calc').first.click()
        page.locator('.csv-head th.csv-calc').first.click()
        settle(150)
        page.locator('.csv-filter input[data-col="3"]').fill('>19.8')
        page.wait_for_function("document.querySelector('.csv-count').textContent.includes('24행 중')", timeout=3000)
        count_text = page.inner_text('.csv-count')
        check('계산 열로 거르기', count_text.startswith('24행 중') and not count_text.endswith(' 24행'), count_text)
        page.click('.csv-clear')
        settle(200)
        check('통계 줄에 계산 열', page.locator('.csv-stats td').nth(3).inner_text() != '')
        page.click('.csv-chart')
        chart_open()
        names = page.evaluate("[...document.querySelectorAll('#lec-chart-series label span')].map((s) => s.textContent)")
        check('계산 열도 차트의 계열', any('전년 동기' in n for n in names), names)
        press('Escape')
        (proj / 'monthly.csv').write_text(MONTHLY + '2026-01,140,5\n', encoding='utf-8')
        page.wait_for_function("document.querySelector('.csv-count').textContent.includes('25행')", timeout=8000)
        settle(200)
        check('파일이 바뀌어 다시 그려도 계산 열은 남음', page.locator('.csv-head th.csv-calc').count() == 2)
        (proj / 'monthly.csv').write_text(MONTHLY, encoding='utf-8')
        page.wait_for_function("document.querySelector('.csv-count').textContent.includes('24행')", timeout=8000)
        settle(200)
        page.locator('.csv-calc-x').first.click()
        settle(150)
        check('× 로 뺌', page.locator('.csv-head th.csv-calc').count() == 1)
        page.locator('#lec-tree .row.file[data-doc="tables.md"]').click()
        page.wait_for_selector('#lec-view h1:has-text("표 문서")')
        data('monthly.csv')
        check('파일을 다시 열면 계산 열은 없음', page.locator('.csv-head th.csv-calc').count() == 0)
        data('long.csv')
        page.locator('.csv-head th[data-col="2"]').click(button='right')
        menu('전기 대비')
        page.wait_for_selector('.csv-blocked:not([hidden])', timeout=3000)
        check('품목별로 쌓은 표는 계산하지 않고 까닭을 보임', all(v == '' for v in cells(4)), cells(4)[:4])
        page.locator('.csv-filter input[data-col="1"]').fill('=copper')
        page.wait_for_selector('.csv-blocked', state='hidden', timeout=3000)
        settle(200)
        got = cells(4)
        check('품목으로 거르면 그 품목의 시계열로 계산', got[0] == '' and got[1] == '0.99', got[:3])
        page.click('.csv-clear')
        settle(200)

        print('[데이터 보기 — 내보내기]')
        data('monthly.csv')
        page.locator('.csv-head th[data-col="1"]').click(button='right')
        menu('차분')
        page.wait_for_selector('.csv-head th.csv-calc')
        page.locator('.csv-filter input[data-col="0"]').fill('2024-1')
        page.wait_for_function("document.querySelector('.csv-count').textContent.includes('24행 중 3행')", timeout=3000)
        page.click('.csv-copy-shown')
        toast_has('복사했습니다')
        clip = page.evaluate('navigator.clipboard.readText()')
        lines = clip.splitlines()   # Windows 클립보드는 줄바꿈을 CRLF 로 바꾼다
        check('보이는 표 복사: 머리행·거른 행·계산 열, 탭으로', len(lines) == 4 and lines[0].split('\t') == ['date', 'price', 'volume', 'price 차분'] and lines[1].split('\t')[0] == '2024-10', lines[:2])
        page.click('.csv-send')
        page.wait_for_selector('#lec-insert:not([hidden])')
        press('Escape')
        settle(150)
        check("'문서로 보내기'는 보낼 곳 고르기로", page.locator('#lec-insert').is_hidden())
        page.click('.csv-clear')

        print('[표 영역]')
        names = lambda: page.evaluate("[...document.querySelectorAll('.csv-head th[data-col]')].map((h) => { const c = h.cloneNode(true); c.querySelector('small')?.remove(); return c.textContent; })")
        chips = lambda: page.evaluate("[...document.querySelectorAll('.csv-region')].map((b) => [b.textContent, b.getAttribute('aria-pressed')])")
        data('messy.xlsx')
        got = chips()
        check('표마다 단추, 가장 큰 표를 고름, 시트 전체', len(got) == 3 and got[0] == ['표 1A4:E9', 'true'] and got[1][0] == '표 2A13:B15' and got[2][0] == '시트 전체', got)
        check('제목 줄은 제목으로', page.inner_text('.csv-title') == '구리 수입 현황 · (단위: 천톤)', page.inner_text('.csv-title'))
        check('두 줄 머리행을 병합 범위대로 합침', names() == ['구분', '수입 · 구리', '수입 · 니켈', '수출 · 구리', '수출 · 니켈'], names())
        check('자료 줄은 표에서 빠지고 행 번호는 엑셀 그대로', cells(0) == ['6', '7', '8', '9'], cells(0))
        check('요약 줄도 그 표로', page.inner_text('.csv-summary') == '연별 · 2023 ~ 2026 · 숫자 열 4', page.inner_text('.csv-summary'))
        check('시간 열에는 합계·평균을 내지 않음', '합계' not in page.locator('.csv-stats td').nth(0).inner_text())
        page.screenshot(path=str(Path(os.environ.get('LEC_SHOTS', base)) / 'region.png'))
        page.click('.csv-chart')
        chart_open()
        o = option()
        check('차트: 합친 열 이름, 제목의 단위', [s['name'] for s in o['series']][:2] == ['수입 · 구리', '수입 · 니켈'] and o['axes'] == ['천톤'] and o['x'] == ['2023', '2024', '2025', '2026'], o)
        press('Escape')
        page.locator('.csv-head th[data-col="1"]').click(button='right')
        menu('전기 대비')
        page.wait_for_selector('.csv-head th.csv-calc')
        check('계산 열도 그 표에', cells(6)[1] == '10', cells(6))
        page.locator('.csv-region[data-region="1"]').click()
        page.wait_for_function("document.querySelector('.csv-region[data-region=\"1\"]').getAttribute('aria-pressed') === 'true'")
        settle(150)
        check('둘째 표로 — 계산 열은 그 표의 것이라 빠짐', names() == ['품목', '가격'] and page.locator('th.csv-calc').count() == 0, names())
        page.locator('.csv-region[data-region="0"]').click()
        settle(200)
        page.locator('.csv-depth button[data-depth="1"]').click()
        settle(200)
        depth3 = names()
        check('머리행을 한 줄 늘림', page.inner_text('.csv-depth b') == '3줄' and depth3[0] == '구분 · 2023' and len(cells(0)) == 3, depth3)
        page.locator('.csv-depth button[data-depth="-1"]').click()
        settle(200)
        check('줄이면 돌아옴', names()[1] == '수입 · 구리')
        page.locator('.csv-region[data-region="all"]').click()
        settle(200)
        check('시트 전체는 받은 그대로', len(cells(0)) >= 11 and page.locator('.csv-depth').count() == 0 and page.locator('.csv-headrow').is_visible(), cells(0))
        press('F5')
        page.wait_for_selector('.csv-table tbody.csv-rows tr')
        settle(500)
        check('다시 그려도 고른 곳 그대로', page.get_attribute('.csv-region[data-region="all"]', 'aria-pressed') == 'true')
        page.locator('.csv-rows tr.cv-line[data-line="13"] td').nth(1).click()
        press('Shift+Enter')
        press('Shift+ArrowDown')
        press('Shift+ArrowDown')
        settle(150)
        page.locator('.csv-rows tr.cv-line[data-line="13"] td').nth(1).click(button='right')
        menu('이 범위를 표로')
        settle(250)
        press('Escape')
        got = chips()
        check('하이라이트한 범위를 표로', any(c[0].startswith('지정한 표') and c[1] == 'true' for c in got) and names() == ['품목', '가격'], (got, names()))
        data('messy.csv')
        got = chips()
        check('csv 도: 제목 줄·자료 줄, 파일 전체', got[-1][0] == '파일 전체' and page.inner_text('.csv-title').startswith('구리 시세 통계') and cells(1) == ['2024', '2025'], (got, cells(1)))
        page.click('.csv-chart')
        chart_open()
        check('csv 의 캡션 단위', option()['axes'] == ['USD/t'], option()['axes'])
        press('Escape')

        print('[엑셀]')
        data('book.xlsx')
        check('깔끔한 시트에는 표 단추가 없음', page.locator('.csv-regions').is_hidden() and page.locator('.csv-headrow').is_visible())
        check('엑셀에도 요약 줄', '연별' in page.inner_text('.csv-summary'), page.inner_text('.csv-summary'))
        page.click('.csv-chart')
        chart_open()
        check('엑셀 표도 차트로', option()['x'] == ['2024', '2025'], option())
        press('Escape')
        data('text.csv')
        page.click('.csv-chart')
        check('글뿐인 csv 는 알림', toast_has('차트로 볼 숫자가 없습니다'))

        real = [e for e in errors if 'addressunreachable' not in e]
        check('화면 스크립트 오류 없음', not real, real[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('점검이 중간에 멈춤')
finally:
    server.terminate()
    try:
        server.wait(10)
    except subprocess.TimeoutExpired:
        server.kill()
    time.sleep(0.5)
    shutil.rmtree(base, ignore_errors=True)
print(f'\n{count}개 중 실패 {len(fails)}개', fails)
sys.exit(1 if fails else 0)
