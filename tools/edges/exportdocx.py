"""내보내기 창의 'Word로 저장' (D146) — 브라우저 개발 모드에서: 메뉴, 창(형식·옵션·단추·미리보기 대신 알림), 스킬이 만든 docx
(글·캡션 번호 필드·각주·그림), 양식 보관소(맨 앞 설정 docxStyle 이 처음 값, 양식의 쪽 설정·머리글), 형식 바꾸기, 슬라이드에는 없음.

창 모드의 저장 대화상자(native.save_export)는 여기서 돌지 않는다 — 쓰는 길은 tests/test_docxexport.py 가 본다.
그림은 Edge 가 그린다 (Windows). Edge 가 없으면 그림 수 점검만 건너뛴다."""
import re
import tempfile
import traceback
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-exportdocx-'))
proj = base / 'proj'
config = base / 'config'
(proj / 'docs').mkdir(parents=True)
DOC = """# 내보낼 보고서

첫 문단이다. <mark>칠한 글</mark>과 각주[^1].

## 1. 값

표 1. 값

| 항목 | 값 |
|---|---|
| 가 | 10 |

[표 1](#표-1) 을 본다.

```mermaid
flowchart LR
  A --> B
```

그림 1. 흐름

[^1]: 각주의 글.
"""
(proj / 'docs' / '보고서.md').write_text(DOC, encoding='utf-8')
(proj / 'docs' / '양식.md').write_text('---\ndocxStyle: 회사\n---\n\n# 양식 문서\n\n본문.\n', encoding='utf-8')
(proj / 'docs' / '발표.md').write_text('---\nmarp: true\n---\n\n# 발표\n', encoding='utf-8')

# 회사 양식 — Letter 쪽, 머리글 '회사 양식' (Word 없이 짠 가장 작은 .dotx)
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
(config / 'docx-styles').mkdir(parents=True)
with zipfile.ZipFile(config / 'docx-styles' / '회사.dotx', 'w') as z:
    z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
               '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
               '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"/>'
               '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/></Types>')
    z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    z.writestr('word/_rels/document.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               '<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/></Relationships>')
    z.writestr('word/header1.xml', f'<?xml version="1.0" encoding="UTF-8"?><w:hdr {W}><w:p><w:r><w:t>회사 양식</w:t></w:r></w:p></w:hdr>')
    z.writestr('word/document.xml', f'<?xml version="1.0" encoding="UTF-8"?><w:document {W}><w:body><w:p/><w:sectPr><w:headerReference w:type="default" r:id="rId9"/>'
               '<w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>')
(config / 'docx-styles' / '~$회사.dotx').write_bytes(b'lock')   # Word 가 열어 둔 잠금 파일 — 목록에 없다

server, url, port = serve(proj, config)
LABELS = "[...document.querySelectorAll('#lec-menu button[data-i] > span')].map((e) => e.textContent)"


def docx_xml(data, name='word/document.xml'):
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read(name).decode('utf-8') if name in z.namelist() else ''


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1300, 'height': 900}, accept_downloads=True)
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)

        def open_doc(path):
            page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", path)
            page.wait_for_function("(p) => document.querySelector('#lec-view')?.dataset.docPath === p", arg=path)
            page.wait_for_timeout(300)

        def menu():
            page.keyboard.press('Escape')
            page.locator('#lec-view').click(button='right', position={'x': 6, 'y': 6})
            page.wait_for_selector('#lec-menu:not([hidden])')
            return page.evaluate(LABELS)

        def ready():
            return until(page, lambda: page.is_enabled('#lec-print-docx') and page.is_hidden('#lec-print-wait'), 60000)

        def download():
            with page.expect_download() as dl:
                page.click('#lec-print-docx')
            return dl.value.suggested_filename, Path(dl.value.path()).read_bytes()

        print('[메뉴와 창]')
        open_doc('docs/보고서.md')
        labels = menu()
        check("문서 여백의 우클릭에 'Word로 저장…'", 'Word로 저장…' in labels, labels)
        page.locator('#lec-menu button', has_text='Word로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        check('Word 형식이 골라져 있고 PDF 는 막혀 있다 (브라우저 개발 모드)',
              page.is_checked('#lec-print input[name="pp_format"][value="docx"]') and page.is_disabled('#lec-print input[name="pp_format"][value="pdf"]'))
        check('틀·PDF 옵션은 감추고 Word 양식을 보인다', page.is_hidden('#lec-print .print-layouts') and page.is_hidden('#lec-print-layout') and page.is_visible('#lec-print .print-docx'))
        check('단추는 Word로 저장 하나', page.is_visible('#lec-print-docx') and page.is_hidden('#lec-print-save') and page.is_hidden('#lec-print-paper') and page.is_hidden('#lec-print-html'))
        check('미리보기 대신 알림 칸', page.is_hidden('#lec-print-frame') and page.is_visible('#lec-print-docx-info'))
        opts = page.evaluate("() => [...document.querySelectorAll('#lec-pp-docx option')].map((o) => [o.value, o.textContent])")
        groups = page.evaluate("() => [...document.querySelectorAll('#lec-pp-docx optgroup')].map((g) => g.label)")
        check('양식 목록 — 기본 양식, Lectern 양식 18가지(묶음별), 맨 아래 내 양식 (잠금 파일은 빼고)',
              opts[0] == ['', 'Lectern 기본 양식'] and len([o for o in opts if o[0].startswith('lectern:')]) == 18 and opts[-1] == ['회사', '회사']
              and groups == ['업무·공공', '연구', '금융·컨설팅', '매체·출판', '안내', '내 양식'], (opts[:3], groups))
        check('맨 앞 설정이 없으면 기본 양식', page.input_value('#lec-pp-docx') == '')
        check('만들기를 마친다', ready())
        info = page.inner_text('#lec-print-docx-info')
        check('만든 결과를 알린다 — 그림 수·양식·필드 안내', 'Word 파일을 만들었습니다' in info and '양식: Lectern 기본 양식' in info and '필드를 업데이트' in info, info)
        check('그림 1개 (Mermaid — Edge 로 그린다)', '그림 1개' in info or 'mermaid' in info, info)
        check('크기를 알린다', re.fullmatch(r'Word · \d+KB', page.inner_text('#lec-print-info')) is not None, page.inner_text('#lec-print-info'))
        name, data = download()
        doc = docx_xml(data)
        check("'Word로 저장…' — 문서 이름.docx", name == '보고서.docx' and data[:2] == b'PK', name)
        check('글·형광펜·캡션 번호 필드·표 링크·각주', '칠한 글' in doc and 'w:fill="FFF1A6"' in doc and ' SEQ 표 ' in doc and 'w:anchor="lec_tbl_1"' in doc
              and '<w:footnoteReference' in doc and '각주의 글' in docx_xml(data, 'word/footnotes.xml'))
        check('기본 양식은 A4', '<w:pgSz w:w="11906" w:h="16838"/>' in doc)
        check('저장하면 창이 닫힌다', until(page, lambda: page.is_hidden('#lec-print')))
        check('프로젝트에는 아무것도 쓰지 않는다', not list(proj.rglob('*.docx')))

        print('[양식]')
        open_doc('docs/양식.md')
        menu()
        page.locator('#lec-menu button', has_text='Word로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        check('맨 앞 설정 docxStyle 의 양식이 골라져 있다', until(page, lambda: page.input_value('#lec-pp-docx') == '회사'), page.input_value('#lec-pp-docx'))
        ready()
        check('알림에 양식 이름', '양식: 회사' in page.inner_text('#lec-print-docx-info'), page.inner_text('#lec-print-docx-info'))
        name, data = download()
        doc = docx_xml(data)
        check('양식의 쪽 크기·머리글', '<w:pgSz w:w="12240" w:h="15840"/>' in doc and '회사 양식' in docx_xml(data, 'word/header1.xml'), name)
        check('양식(.dotx)이 아니라 문서로', 'template.main+xml' not in docx_xml(data, '[Content_Types].xml'))
        menu()
        page.locator('#lec-menu button', has_text='Word로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        ready()
        page.select_option('#lec-pp-docx', label='Lectern 기본 양식')
        check('양식을 바꾸면 다시 만든다', until(page, lambda: '양식: Lectern 기본 양식' in page.inner_text('#lec-print-docx-info') and page.is_enabled('#lec-print-docx'), 60000))
        _, data = download()
        check('기본 양식으로 — A4', '<w:pgSz w:w="11906" w:h="16838"/>' in docx_xml(data))

        print('[형식 바꾸기]')
        menu()
        page.locator('#lec-menu button', has_text='Word로 저장…').click()
        page.wait_for_selector('#lec-print:not([hidden])')
        ready()
        page.click('#lec-print input[name="pp_format"][value="html"]')
        check('html 로 — 미리보기가 다시 보이고 Word 칸은 숨는다', until(page, lambda: (page.get_attribute('#lec-print-frame', 'src') or '').startswith('/export-preview/'), 20000)
              and page.is_visible('#lec-print-frame') and page.is_hidden('#lec-print-docx-info') and page.is_hidden('#lec-print .print-docx') and page.is_visible('#lec-print .print-layouts'))
        check('html 단추만', page.is_visible('#lec-print-html') and page.is_hidden('#lec-print-docx'))
        page.click('#lec-print input[name="pp_format"][value="docx"]')
        check('Word 로 돌아오면 다시 만든다', ready() and page.is_visible('#lec-print-docx-info'))
        asked = []
        page.on('request', lambda r: asked.append(r.url) if '/api/docx-styles/folder' in r.url else None)
        page.click('#lec-pp-docx-folder')
        check("'양식 폴더 열기' — 보관소를 만들고 연다", until(page, lambda: bool(asked)) and (config / 'docx-styles').is_dir())
        page.click('#lec-print-close')

        print('[슬라이드]')
        open_doc('docs/발표.md')
        page.wait_for_timeout(600)
        labels = menu()
        check("Lectern 슬라이드에는 'Word로 저장…' 이 없다 (슬라이드는 pptx 로 전환)", 'Word로 저장…' not in labels, labels)
        page.keyboard.press('Escape')
        check('페이지 오류 없음', not errors, errors)
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
