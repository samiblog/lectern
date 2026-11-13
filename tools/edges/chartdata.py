"""차트의 데이터 (D136): 차트의 [표]·[복사], 긴 표 줄이기·모두 보기, 변환 알림, CSV 차트의 '데이터를 문서 안으로 넣기'(같은 그림·되돌리기·
묻기·프로젝트 밖 막기), ECharts·Plotly, Graphviz·슬라이드에는 없음, 표의 [복사], 데이터 표 칸에는 표 메뉴 없음, 인쇄에는 없음"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-chartdata-'))
proj = base / 'proj'
config = base / 'config'
(proj / 'docs').mkdir(parents=True)
(proj / 'data').mkdir()


def fence(lang, spec):
    return f'```{lang}\n{json.dumps(spec, ensure_ascii=False, indent=2)}\n```\n'


small = [{'월': f'2026-0{i}', '가격': 9000 + i * 37} for i in range(1, 6)]
many = [{'n': i, 'v': i * i} for i in range(100)]
(proj / 'data' / '가격.csv').write_bytes('\ufeff월,가격,비고\r\n2026-01,9120,\r\n2026-02,9340,추정\r\n2026-03,9285,\r\n'.encode('utf-8'))   # 엑셀처럼 BOM·CRLF
(proj / 'data' / 'big.csv').write_text('n,v\n' + ''.join(f'{i},{i * 2}\n' for i in range(600)), encoding='utf-8')
DOC = '\n'.join([
    '# 차트 데이터',
    '',
    '첫 문단.',
    '',
    fence('vega-lite', {'title': '작은 차트', 'width': 'container', 'height': 160, 'data': {'values': small}, 'mark': 'bar',
                        'encoding': {'x': {'field': '월', 'type': 'nominal'}, 'y': {'field': '가격', 'type': 'quantitative'}}}),
    '그림 1. 작은 차트',
    '',
    fence('vega-lite', {'title': '긴 차트', 'width': 'container', 'height': 160, 'data': {'values': many}, 'mark': 'line',
                        'encoding': {'x': {'field': 'n', 'type': 'quantitative'}, 'y': {'field': 'v', 'type': 'quantitative'}}}),
    fence('vega-lite', {'title': '거른 차트', 'width': 'container', 'height': 160, 'data': {'values': small}, 'transform': [{'filter': 'datum.가격 > 9100'}],
                        'mark': 'bar', 'encoding': {'x': {'field': '월', 'type': 'nominal'}, 'y': {'field': '가격', 'type': 'quantitative'}}}),
    fence('vega-lite', {'title': '파일 차트', 'width': 'container', 'height': 160, 'data': {'url': '../data/가격.csv'}, 'mark': {'type': 'line', 'point': True},
                        'encoding': {'x': {'field': '월', 'type': 'temporal'}, 'y': {'field': '가격', 'type': 'quantitative', 'scale': {'zero': False}}}}),
    fence('echarts', {'height': 220, 'xAxis': {'type': 'category', 'data': ['월', '화', '수']}, 'yAxis': {'type': 'value'},
                      'series': [{'name': '방문', 'type': 'bar', 'data': [3, 5, 4]}, {'name': '가입', 'type': 'line', 'data': [1, 2, 2]}]}),
    fence('plotly', {'data': [{'type': 'scatter', 'x': ['A', 'B'], 'y': [1, 4], 'name': '올해'}], 'layout': {'height': 260}}),
    '```dot\ndigraph g { a -> b }\n```\n',
    '| 품목 | 값 |',
    '|---|---:|',
    '| 구리 | 1,200 |',
    '| 알루미늄 | 800 |',
    '',
    '끝 문단.',
    '',
])
(proj / 'docs' / 'a.md').write_text(DOC, encoding='utf-8')
(proj / 'docs' / 'big.md').write_text('# 큰 파일\n\n' + fence('vega-lite', {'data': {'url': '../data/big.csv'}, 'mark': 'point',
                                       'encoding': {'x': {'field': 'n', 'type': 'quantitative'}, 'y': {'field': 'v', 'type': 'quantitative'}}}), encoding='utf-8')
(proj / 'docs' / 'out.md').write_text('# 밖\n\n' + fence('vega-lite', {'data': {'url': '../../밖.csv'}, 'mark': 'point'}), encoding='utf-8')
(base / '밖.csv').write_text('a\n1\n', encoding='utf-8')
(proj / 'docs' / 'deck.md').write_text('---\nmarp: true\n---\n\n# 장\n\n' + fence('vega-lite', {'data': {'values': small}, 'mark': 'bar',
                                        'encoding': {'x': {'field': '월', 'type': 'nominal'}, 'y': {'field': '가격', 'type': 'quantitative'}}})
                                        + '\n| a | b |\n|---|---|\n| 1 | 2 |\n', encoding='utf-8')

OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))"
CHART = "#lec-view pre.lec-chart >> nth={}"


def chart(page, n):
    return page.locator(f'#lec-view pre.lec-chart >> nth={n}')


def info(page, n):
    return page.evaluate("""(n) => {
      const node = document.querySelectorAll('#lec-view pre.lec-chart')[n];
      const panel = node?.querySelector(':scope > .lec-chart-data');
      return { tools: !!node?.querySelector(':scope > .lec-chart-tools'), open: !!panel,
        heads: panel ? [...panel.querySelectorAll('thead th')].map((x) => x.textContent) : [],
        rows: panel ? [...panel.querySelectorAll('tbody tr:not(.skip)')].map((r) => [...r.cells].map((c) => c.textContent)) : [],
        skips: panel ? panel.querySelectorAll('tbody tr.skip').length : 0,
        head: panel?.querySelector('.cd-head')?.textContent || '', notes: panel ? [...panel.querySelectorAll('.cd-note')].map((x) => x.textContent.trim()) : [] };
    }""", n)


def press(page, n, act):
    chart(page, n).hover()
    page.locator(f'#lec-view pre.lec-chart >> nth={n}').locator(f'[data-act="{act}"]').first.click()


def clip(page):
    return page.evaluate('() => navigator.clipboard.readText()').replace('\r\n', '\n')   # Windows 의 클립보드는 줄바꿈을 CRLF 로


server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1300, 'height': 900})
        ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=url.rstrip('/'))
        page = ctx.new_page()
        dialogs = []
        answer = {'accept': False}

        def on_dialog(d):
            dialogs.append(d.message)
            d.accept() if answer['accept'] else d.dismiss()
        page.on('dialog', on_dialog)
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.evaluate(OPEN, 'docs/a.md')
        until(page, "() => document.querySelectorAll('#lec-view pre.lec-chart.chart-ok').length === 7", ms=30000)

        print('[단추 — 데이터 차트만]')
        tools = page.evaluate("() => [...document.querySelectorAll('#lec-view pre.lec-chart')].map((n) => n.dataset.chart + ':' + !!n.querySelector(':scope > .lec-chart-tools'))")
        check('Vega-Lite·ECharts·Plotly 에 단추, Graphviz 에는 없음', tools == ['vega-lite:true'] * 4 + ['echarts:true', 'plotly:true', 'dot:false'], tools)
        hidden = page.evaluate("() => getComputedStyle(document.querySelector('#lec-view .lec-chart-tools')).opacity")
        check('마우스를 올리기 전에는 보이지 않는다', hidden == '0', hidden)
        chart(page, 0).hover()
        expect(page, '올리면 보인다', "() => getComputedStyle(document.querySelector('#lec-view .lec-chart-tools')).opacity === '1'")

        print('[작은 차트 — 표와 복사]')
        press(page, 0, 'table')
        i = info(page, 0)
        check('표: 머리행과 값 (수는 자리 쉼표)', i['heads'] == ['월', '가격'] and i['rows'][0] == ['2026-01', '9,037'] and len(i['rows']) == 5, i)
        check('머리: 5행 2열', '5행 2열' in i['head'], i['head'])
        check('[표]를 눌러도 크게 보기가 뜨지 않는다', page.evaluate("() => !document.querySelector('#lec-lightbox') || document.querySelector('#lec-lightbox').hidden"))
        check('캡션은 그대로 차트 다음 단락 (자료 줄이 아님)', page.evaluate("() => { const n = document.querySelector('#lec-view pre.lec-chart'); return n.nextElementSibling?.textContent.startsWith('그림 1.'); }"))
        page.locator('#lec-view pre.lec-chart >> nth=0').locator('.lec-chart-data td').first.click()
        check('표 안을 눌러도 크게 보기가 뜨지 않는다', page.evaluate("() => !document.querySelector('#lec-lightbox') || document.querySelector('#lec-lightbox').hidden"))
        press(page, 0, 'copy')
        check('복사: 탭으로 나눈 전부, 수는 쉼표 없이', until(page, lambda: clip(page) == '월\t가격\n' + '\n'.join(f"{r['월']}\t{r['가격']}" for r in small)), clip(page))
        press(page, 0, 'table')
        check('다시 누르면 접힌다', not info(page, 0)['open'])

        print('[긴 차트 — 30행으로 줄이고 모두 보기]')
        press(page, 1, 'table')
        i = info(page, 1)
        check('30행과 건너뛴 줄', len(i['rows']) == 30 and i['skips'] > 0 and i['rows'][0] == ['0', '0'] and i['rows'][-1] == ['99', '9,801'], (len(i['rows']), i['skips'], i['rows'][:1], i['rows'][-1:]))
        check("머리: '30행 보임 — 약 3행마다'", '100행 2열' in i['head'] and '30행 보임' in i['head'] and '3행마다' in i['head'], i['head'])
        page.locator('#lec-view pre.lec-chart >> nth=1').locator('[data-act="all"]').click()
        i = info(page, 1)
        check('모두 보기 → 100행', len(i['rows']) == 100 and i['skips'] == 0, len(i['rows']))
        press(page, 1, 'copy')
        check('복사는 늘 100행 전부', until(page, lambda: clip(page).count('\n') == 100), clip(page).count('\n'))

        print('[변환이 있는 차트]')
        press(page, 2, 'table')
        i = info(page, 2)
        check('변환 전 값이라고 알린다 (값은 5행 모두)', len(i['rows']) == 5 and any('변환 전 값' in x for x in i['notes']), i['notes'])

        print('[ECharts·Plotly]')
        press(page, 4, 'table')
        i = info(page, 4)
        check('ECharts: 축과 계열의 넓은 표', i['heads'] == ['', '방문', '가입'] and i['rows'] == [['월', '3', '1'], ['화', '5', '2'], ['수', '4', '2']], i)
        press(page, 5, 'table')
        i = info(page, 5)
        check('Plotly: x 와 계열', i['heads'] == ['x', '올해'] and i['rows'] == [['A', '1'], ['B', '4']], i)

        print('[문서를 다시 그려도 펼친 표가 남는다]')
        page.evaluate("() => import('/static/js/nav.js').then((m) => m.refreshView())")
        page.wait_for_timeout(800)
        expect(page, '다시 그린 뒤에도 ECharts 표가 펼쳐져 있다', "() => !!document.querySelectorAll('#lec-view pre.lec-chart')[4]?.querySelector('.lec-chart-data')", ms=10000)

        print('[데이터 표의 칸에는 표 메뉴가 없다]')
        page.locator('#lec-view pre.lec-chart >> nth=4').locator('.lec-chart-data td').first.click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])', timeout=5000)
        items = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.textContent.trim())")
        check("'아래에 행 더하기'가 없다", not any('행 더하기' in x for x in items), items)
        page.keyboard.press('Escape')

        print('[인쇄에는 없다]')
        page.emulate_media(media='print')
        shown = page.evaluate("() => [...document.querySelectorAll('#lec-view .lec-chart-tools, #lec-view .lec-chart-data, #lec-view .table-copy')].filter((x) => getComputedStyle(x).display !== 'none').length")
        check('단추·펼친 표·표의 복사가 인쇄에 없다', shown == 0, shown)
        page.emulate_media(media='screen')

        print('[표의 [복사]]')
        wrap = page.locator('#lec-view .table-wrap').last
        wrap.hover()
        wrap.locator('.table-copy').click()
        check('표 복사: 보이는 그대로 탭으로', until(page, lambda: clip(page) == '품목\t값\n구리\t1,200\n알루미늄\t800'), clip(page))
        check('표의 단추는 한 표에 하나', page.evaluate("() => [...document.querySelectorAll('#lec-view .table-wrap')].filter((w) => !w.closest('.lec-chart-data')).every((w) => w.querySelectorAll(':scope > .table-copy').length === 1)"))

        print('[CSV 차트 — 문서 안으로 넣기]')
        press(page, 3, 'table')
        i = info(page, 3)
        check('표 없이 파일 이름과 단추', not i['heads'] and any('../data/가격.csv' in x for x in i['notes']), i)
        press(page, 3, 'copy')
        expect(page, '복사는 까닭을 알린다', "() => document.querySelector('#lec-toast')?.textContent.includes('복사할 값이 없습니다')")
        before_svg = page.evaluate("() => document.querySelectorAll('#lec-view pre.lec-chart')[3].querySelector(':scope > svg').outerHTML")
        before = (proj / 'docs' / 'a.md').read_text(encoding='utf-8')
        page.locator('#lec-view pre.lec-chart >> nth=3').locator('[data-act="inline"]').click()
        check('파일에 values 로 들어갔다', until(page, lambda: '"values"' in (proj / 'docs' / 'a.md').read_text(encoding='utf-8').split('파일 차트')[1].split('```')[0], ms=10000))
        after = (proj / 'docs' / 'a.md').read_text(encoding='utf-8')
        part = after.split('"title": "파일 차트"')[1].split('```')[0]
        check('url 은 빠지고 빈 칸은 null, 수는 수로', '"url"' not in part and '{"월":"2026-02","가격":9340,"비고":"추정"}' in part and '"비고":null' in part, part[:400])
        check('다른 줄은 그대로', after.split('"title": "파일 차트"')[0] == before.split('"title": "파일 차트"')[0]
              and after.split('"title": "파일 차트"')[1].split('```', 1)[1] == before.split('"title": "파일 차트"')[1].split('```', 1)[1])
        until(page, "() => !!document.querySelectorAll('#lec-view pre.lec-chart')[3]?.querySelector('.lec-chart-data table')", ms=10000)
        i = info(page, 3)
        check('다시 그린 차트의 표에 값', i['heads'] == ['월', '가격', '비고'] and len(i['rows']) == 3, i)
        after_svg = page.evaluate("() => document.querySelectorAll('#lec-view pre.lec-chart')[3].querySelector(':scope > svg').outerHTML")
        check('같은 그림 (SVG 가 같다)', after_svg == before_svg, (len(before_svg), len(after_svg)))
        page.locator('#lec-view p').first.click()
        page.keyboard.press('Control+z')
        check('Ctrl+Z 로 되돌린다', until(page, lambda: (proj / 'docs' / 'a.md').read_text(encoding='utf-8') == before, ms=10000))

        print('[큰 CSV — 묻는다]')
        page.evaluate(OPEN, 'docs/big.md')
        until(page, "() => document.querySelector('#lec-view pre.lec-chart.chart-ok')", ms=20000)
        big_before = (proj / 'docs' / 'big.md').read_text(encoding='utf-8')
        press(page, 0, 'table')
        page.locator('#lec-view pre.lec-chart >> nth=0').locator('[data-act="inline"]').click()
        expect(page, '600행이면 묻는다', lambda: any('600' in d for d in dialogs), dialogs)
        page.wait_for_timeout(500)
        check('그만두면 그대로', (proj / 'docs' / 'big.md').read_text(encoding='utf-8') == big_before)
        answer['accept'] = True
        page.locator('#lec-view pre.lec-chart >> nth=0').locator('[data-act="inline"]').click()
        check('넣으면 600행', until(page, lambda: (proj / 'docs' / 'big.md').read_text(encoding='utf-8').count('{"n":') == 600, ms=10000))
        answer['accept'] = False

        print('[프로젝트 밖의 파일]')
        page.evaluate(OPEN, 'docs/out.md')
        until(page, "() => document.querySelector('#lec-view h1')?.textContent === '밖'")
        page.wait_for_timeout(1500)
        drawn = page.evaluate("() => !!document.querySelector('#lec-view pre.lec-chart.chart-ok')")
        if drawn:
            press(page, 0, 'table')
            page.locator('#lec-view pre.lec-chart >> nth=0').locator('[data-act="inline"]').click()
            expect(page, '프로젝트 밖은 읽지 않는다고 알린다', "() => document.querySelector('#lec-toast')?.textContent.includes('이 프로젝트 안의 파일만')")
        else:
            check('프로젝트 밖 파일의 차트는 그려지지 않는다 (단추도 없다)', not page.evaluate("() => !!document.querySelector('#lec-view .lec-chart-tools')"))
        check('파일은 그대로', '"url"' in (proj / 'docs' / 'out.md').read_text(encoding='utf-8'))

        print('[Lectern 슬라이드에는 없다]')
        page.evaluate(OPEN, 'docs/deck.md')
        until(page, "() => document.querySelector('#lec-view.lec-deck pre.lec-chart.chart-ok')", ms=20000)
        check('슬라이드의 차트·표에 단추가 없다', page.evaluate("() => !document.querySelector('#lec-view .lec-chart-tools, #lec-view .table-copy')"))
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
