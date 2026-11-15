"""내보내기 두 번째 시나리오 (D144~D146) — 첫 묶음(export_scenarios)에서 다루지 않은 것 (브라우저 개발 모드).

1 편집 중 — 저장하지 않은 글은 내보낸 파일에 들어가지 않는다 (편집 중에는 메뉴에 없거나, 저장한 뒤에)
2 양식을 빠르게 바꾸기 — 마지막에 고른 양식의 결과만 남는다
3 모두 펼치기 — 우클릭한 칸의 문서를 내보낸다
4 이름에 띄어쓰기·#·% 가 든 문서 — 내려받는 이름, 서버 경로
5 틀의 가장자리 — 모르는 틀·양식 이름은 기본으로, 같은 이름 박스글 둘·틀에 없는 이름, 닫지 않은 박스글
6 만드는 중에 창을 닫고 다른 문서로 — 앞의 결과가 섞이지 않는다
7 독립창 — 메뉴에 'Word로 저장…', 그 문서를 내보낸다
8 차트가 많은 문서 — 만드는 동안의 알림, 그림 수
9 Lectern Word 양식 18가지(D147) — 하나씩 골라 내려받기, 설명·비어 있는 맨 앞 설정·견본 복사"""
import io
import re
import tempfile
import time
import traceback
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-export-more-'))
proj = base / 'proj'
config = base / 'config'
(proj / '문서').mkdir(parents=True)


def w(rel, text):
    (proj / rel).write_text(text.lstrip('\n'), encoding='utf-8')


w('문서/편집.md', '# 편집 중인 문서\n\n저장한 글이다.\n')
w('문서/가.md', '# 가 문서\n\n가의 글.\n')
w('문서/양식시험.md', '---\ntitle: 양식 시험 보고서\norg: 예제연구원\nauthor: 김연구\n결재: [담당, 팀장]\n---\n\n# 양식 시험 보고서\n\n<!-- box: 요약 -->\n요약의 글.\n<!-- /box -->\n\n## 1. 절\n\n본문의 글.\n')
w('문서/나.md', '# 나 문서\n\n나의 글.\n')
w('문서/영문 보고서 #1 (100%).md', '---\nlang: en\n---\n\n# Quarterly Note\n\nSee [Table 1](#table-1).\n\nTable 1. Prices\n\n| Month | Price |\n|---|---:|\n| Oct | 11,220 |\n')
w('문서/틀-가장자리.md', """
---
title: 틀의 가장자리
layout: 없는틀
docxStyle: 없는양식
---

# 틀의 가장자리

<!-- box: 요약 -->
첫 번째 요약.
<!-- /box -->

<!-- box: 요약 -->
두 번째 요약.
<!-- /box -->

<!-- box: 틀에없는이름 -->
틀에 없는 이름의 글.
<!-- /box -->

<!-- box -->
**박스 1. 닫지 않은 박스글**

다음 제목에서 끝난다.

## 다음 절

본문.
""")
charts = '\n'.join('```vega-lite\n{"data": {"values": [{"a": "x", "b": %d}, {"a": "y", "b": %d}]}, "mark": "bar", "encoding": {"x": {"field": "a", "type": "nominal"}, "y": {"field": "b", "type": "quantitative"}}}\n```\n\n그림 %d. 막대 %d\n' % (k, k + 3, k, k) for k in range(1, 9))
w('문서/차트-여럿.md', '# 차트 여럿\n\n' + charts)

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def dotx(path, width, header):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"/>'
                   '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/></Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/_rels/document.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/></Relationships>')
        z.writestr('word/header1.xml', f'<?xml version="1.0" encoding="UTF-8"?><w:hdr {W}><w:p><w:r><w:t>{header}</w:t></w:r></w:p></w:hdr>')
        z.writestr('word/document.xml', f'<?xml version="1.0" encoding="UTF-8"?><w:document {W}><w:body><w:p/><w:sectPr><w:headerReference w:type="default" r:id="rId9"/>'
                   f'<w:pgSz w:w="{width}" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>')


(config / 'docx-styles').mkdir(parents=True)
dotx(config / 'docx-styles' / '가양식.dotx', 12240, '가 양식')
dotx(config / 'docx-styles' / '나양식.dotx', 11000, '나 양식')
server, url, port = serve(proj, config)
OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))"
OPEN_NEW = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p, newTab: true }))"
LABELS = "[...document.querySelectorAll('#lec-menu button[data-i] > span')].map((e) => e.textContent)"


def part(data, name='word/document.xml'):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read(name).decode('utf-8') if name in z.namelist() else ''


def text_of(xml):
    return ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', xml))


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1300, 'height': 900}, accept_downloads=True)
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)

        def open_doc(path, pg=page, new=False):
            pg.evaluate(OPEN_NEW if new else OPEN, path)
            pg.wait_for_function("(p) => document.querySelector('#lec-view')?.dataset.docPath === p", arg=path)
            pg.wait_for_timeout(400)

        def menu_at(locator, pg=page, pos=None):
            pg.keyboard.press('Escape')
            locator.click(button='right', position=pos or {'x': 6, 'y': 6})
            try:
                pg.wait_for_selector('#lec-menu:not([hidden])', timeout=4000)
            except Exception:   # noqa: BLE001 — 메뉴가 뜨지 않는 자리
                return []
            return pg.evaluate(LABELS)

        def word_ready(pg=page, ms=90000):
            return until(pg, lambda: pg.is_enabled('#lec-print-docx') and pg.is_hidden('#lec-print-wait'), ms)

        def download(pg=page):
            with pg.expect_download() as dl:
                pg.click('#lec-print-docx')
            return dl.value.suggested_filename, Path(dl.value.path()).read_bytes()

        print('[1. 편집 중]')
        open_doc('문서/편집.md')
        page.locator('#lec-view p', has_text='저장한 글이다').click()
        page.keyboard.press('Control+e')
        page.wait_for_selector('.CodeMirror, #lec-editor:not([hidden]), .lec-editor', timeout=15000)
        page.wait_for_timeout(600)
        page.keyboard.press('Control+End')
        page.keyboard.type('\n\n저장하지 않은 글이다.')
        page.wait_for_timeout(300)
        editing = page.evaluate("() => !!document.querySelector('.CodeMirror')")
        labels = menu_at(page.locator('.lec-editor .CodeMirror'), pos={'x': 200, 'y': 120})
        offered = 'Word로 저장…' in labels
        if offered:
            page.locator('#lec-menu button', has_text='Word로 저장…').click()
            page.wait_for_selector('#lec-print:not([hidden])')
            word_ready()
            _, data = download()
            check('편집 중에 내보내면 저장한 글만 (저장하지 않은 글은 없다)', '저장한 글이다' in text_of(part(data)) and '저장하지 않은 글' not in text_of(part(data)))
        else:
            check('편집 중에는 메뉴에 Word로 저장이 없다', editing and not offered, labels)
        page.keyboard.press('Escape')
        page.keyboard.press('Control+s')
        page.wait_for_timeout(800)
        page.keyboard.press('Escape')
        until(page, lambda: page.evaluate("() => !document.querySelector('.CodeMirror')"), 8000)
        page.wait_for_timeout(600)
        menu_at(page.locator('#lec-view'))
        page.locator('#lec-menu button', has_text='Word로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        word_ready()
        _, data = download()
        check('저장하고 편집을 닫은 뒤에는 그 글까지', '저장하지 않은 글이다' in text_of(part(data)), text_of(part(data))[:120])

        print('[2. 양식을 빠르게 바꾸기]')
        open_doc('문서/가.md')
        menu_at(page.locator('#lec-view'))
        page.locator('#lec-menu button', has_text='Word로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        word_ready()
        for name in ('가양식', '나양식', '가양식', '나양식'):
            page.select_option('#lec-pp-docx', name)
            page.wait_for_timeout(90)
        check('바꾸는 동안 저장 단추가 꺼진다', page.is_disabled('#lec-print-docx'))
        word_ready()
        info = page.inner_text('#lec-print-docx-info')
        _, data = download()
        check('마지막에 고른 양식(나양식)의 결과만', '양식: 나양식' in info and '나 양식' in part(data, 'word/header1.xml') and '<w:pgSz w:w="11000"' in part(data), info)

        print('[3. 모두 펼치기]')
        open_doc('문서/가.md')
        open_doc('문서/나.md', new=True)
        page.click('#lec-doctab-spread')
        until(page, "document.documentElement.classList.contains('spread-on')")
        page.wait_for_timeout(600)
        panes = page.locator('#lec-panes .lec-pane')
        target = None
        for k in range(panes.count()):
            if panes.nth(k).locator('h1', has_text='가 문서').count():
                target = panes.nth(k)
        check('모두 펼치기에 두 문서 칸', target is not None, panes.count())
        if target is not None:
            labels = menu_at(target.locator('.md-body, article').first)
            check('펼친 칸의 우클릭에 Word로 저장…', 'Word로 저장…' in labels, labels)
            if 'Word로 저장…' in labels:
                page.locator('#lec-menu button', has_text='Word로 저장…').click()
                page.wait_for_selector('#lec-print:not([hidden])')
                check('창 제목은 우클릭한 칸의 문서', page.inner_text('#lec-print-title') == '내보내기 — 가.md', page.inner_text('#lec-print-title'))
                word_ready()
                name, data = download()
                check('그 문서를 내보낸다', name == '가.docx' and '가의 글' in text_of(part(data)) and '나의 글' not in text_of(part(data)), name)
        page.keyboard.press('Escape')
        page.click('#lec-doctab-spread')
        until(page, "!document.documentElement.classList.contains('spread-on')")
        page.wait_for_timeout(400)

        print('[4. 이름에 띄어쓰기·#·%]')
        open_doc('문서/영문 보고서 #1 (100%).md')
        menu_at(page.locator('#lec-view'))
        page.locator('#lec-menu button', has_text='Word로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        check('만든다', word_ready())
        name, data = download()
        check('내려받는 이름 그대로', name == '영문 보고서 #1 (100%).docx', name)
        check('영어 문서 — 캡션 필드·링크', ' SEQ Table ' in part(data) and 'w:anchor="lec_tbl_1"' in part(data))
        menu_at(page.locator('#lec-view'))
        page.locator('#lec-menu button', has_text='html로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        check('html 도 된다', until(page, lambda: (page.get_attribute('#lec-print-frame', 'src') or '').startswith('/export-preview/'), 30000))
        with page.expect_download() as dl:
            page.click('#lec-print-html')
        check('html 내려받는 이름', dl.value.suggested_filename == '영문 보고서 #1 (100%).html', dl.value.suggested_filename)

        print('[5. 틀의 가장자리]')
        open_doc('문서/틀-가장자리.md')
        menu_at(page.locator('#lec-view'))
        page.locator('#lec-menu button', has_text='html로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        check('모르는 틀 이름이면 기본 양식', until(page, lambda: (page.get_attribute('#lec-print-frame', 'src') or '').startswith('/export-preview/')) and page.input_value('#lec-pp-layout') == '')
        page.select_option('#lec-pp-layout', 'research-report')
        until(page, lambda: page.is_enabled('#lec-print-html') and page.is_hidden('#lec-print-wait'), 30000)
        h = page.evaluate('(u) => fetch(u).then((r) => r.text())', page.get_attribute('#lec-print-frame', 'src'))
        first, second, other = h.find('첫 번째 요약'), h.find('두 번째 요약'), h.find('틀에 없는 이름의 글')
        check('같은 이름 박스글 둘 — 첫째는 요약 자리, 둘째와 틀에 없는 이름은 본문에 남는다', min(first, second, other) > 0 and first < h.find('다음 절') and second > 0, (first, second, other))
        check('닫지 않은 박스글도 글이 남는다', '다음 제목에서 끝난다' in h and '본문.' in h)
        page.click('#lec-print input[name="pp_format"][value="docx"]')
        check('모르는 양식 이름이면 기본 양식', word_ready() and page.input_value('#lec-pp-docx') == '')
        _, data = download()
        t = text_of(part(data))
        check('Word: 박스글 넷의 글이 모두 있다', all(s in t for s in ('첫 번째 요약', '두 번째 요약', '틀에 없는 이름의 글', '다음 제목에서 끝난다')), t[:200])

        print('[6. 만드는 중에 닫기]')
        open_doc('문서/차트-여럿.md')
        until(page, lambda: page.locator('#lec-view .lec-chart svg, #lec-view .lec-chart canvas').count() >= 8, 30000)
        menu_at(page.locator('#lec-view'))
        page.locator('#lec-menu button', has_text='Word로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        page.wait_for_timeout(300)
        busy = page.inner_text('#lec-print-wait')
        check('만드는 동안 알림', 'Word 파일을 만드는 중입니다' in busy, busy)
        page.click('#lec-print-close')
        open_doc('문서/가.md')
        menu_at(page.locator('#lec-view'))
        page.locator('#lec-menu button', has_text='Word로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        word_ready()
        page.wait_for_timeout(8000)   # 닫은 창의 차트 문서가 그사이 끝나도
        info = page.inner_text('#lec-print-docx-info')
        _, data = download()
        check('앞의 결과가 섞이지 않는다 — 가 문서, 그림 0개', '그림 0개' in info and '가의 글' in text_of(part(data)), info)

        print('[7. 독립창]')
        page.locator('#lec-doctab-list .doc-tab', has_text='가').first.click(button='right')
        page.wait_for_selector('#lec-menu:not([hidden])')
        with page.expect_popup() as pop:
            page.locator('#lec-menu button', has_text='새 창으로 옮기기').click()
        solo = pop.value
        solo.wait_for_selector('#lec-view h1:has-text("가 문서")', timeout=15000)
        solo.wait_for_timeout(600)
        labels = menu_at(solo.locator('#lec-view'), solo)
        check('독립창의 우클릭에도 Word로 저장…', 'Word로 저장…' in labels, labels)
        if 'Word로 저장…' in labels:
            solo.locator('#lec-menu button', has_text='Word로 저장…').click()
            solo.wait_for_selector('#lec-print:not([hidden])')
            check('독립창에서 만든다', word_ready(solo))
            name, data = download(solo)
            check('그 문서', name == '가.docx' and '가의 글' in text_of(part(data)), name)
        solo.close()

        print('[9. Lectern Word 양식 18가지]')
        open_doc('문서/양식시험.md')
        menu_at(page.locator('#lec-view'))
        page.locator('#lec-menu button', has_text='Word로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        word_ready()
        ids = page.evaluate("() => [...document.querySelectorAll('#lec-pp-docx option')].map((o) => o.value).filter((v) => v.startsWith('lectern:'))")
        check('Lectern 양식 18가지', len(ids) == 18, ids)
        page.select_option('#lec-pp-docx', 'lectern:research-report')
        info = page.inner_text('#lec-pp-docx-info')
        check('고른 양식의 설명·쪽·비어 있는 맨 앞 설정·박스글 자리', '연구기관 보고서' in info and '쪽: A4' in info and 'number' in info and '<!-- box: 요약 -->' in info, info)
        page.context.grant_permissions(['clipboard-read', 'clipboard-write'])
        page.click('#lec-pp-docx-sample')
        clip = page.evaluate('navigator.clipboard.readText()').replace('\r\n', '\n')
        check('견본 복사 — 비어 있는 키만', clip.startswith('---\n') and 'number: ' in clip and '\norg: ' not in clip and '\ntitle: ' not in clip, clip)
        bad = []
        for tid in ids:
            if page.is_hidden('#lec-print'):
                menu_at(page.locator('#lec-view'))
                page.locator('#lec-menu button', has_text='Word로 저장…').click()
                page.wait_for_selector('#lec-print:not([hidden])')
                word_ready()
            page.select_option('#lec-pp-docx', tid)
            if not word_ready():
                bad.append((tid, '만들지 못함', page.inner_text('#lec-print-wait')))
                continue
            _, data = download()
            parts = []
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                parts = [z.read(n).decode('utf-8') for n in z.namelist() if re.match(r'word/(document|header\d*|footer\d*)\.xml$', n)]
            t = ''.join(text_of(x) for x in parts)
            if '{{' in t or '양식 시험 보고서' not in t or '본문의 글' not in t:
                bad.append((tid, t[:120]))
        check('18가지 모두 만들어지고 자리 표시가 남지 않는다 — 제목·본문이 들어간다', not bad, bad)

        print('[8. 차트가 많은 문서]')
        open_doc('문서/차트-여럿.md')
        menu_at(page.locator('#lec-view'))
        page.locator('#lec-menu button', has_text='Word로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        t0 = time.monotonic()
        ok = word_ready(page, 120000)
        sec = time.monotonic() - t0
        info = page.inner_text('#lec-print-docx-info')
        check(f'차트 8개 ({sec:.0f}초)', ok and '그림 8개' in info, info)
        page.click('#lec-print-close')
        check('페이지 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
