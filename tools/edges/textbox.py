"""박스글 (D126): <!-- box --> … <!-- /box --> 를 본문과 따로 읽는 글 상자로 — 그리기, 닫지 않은 것, 목차·모아 보기, 접기, 넣기·묶기·풀기·지우기, 줄 편집.

기다릴 때는 고정 시간이 아니라 조건을 본다 (until) — 느린 PC 에서 흔들리지 않게.
"""
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-textbox-'))
proj = base / 'proj'
proj.mkdir(parents=True)
OPEN, CLOSE = '<!-- box -->', '<!-- /box -->'
DOC = f"""# 보고서

본문 첫 문단. [박스 1](#박스-1) 을 보라.

표 1. 본문의 표

| 가 | 나 |
|---|---|
| 1 | 2 |

{OPEN}
**박스 1. 재고 통계는 왜 다른가**

박스 안의 문단.

| 기관 | 세는 것 |
|---|---|
| 거래소 | 등록 물량 |

자료: 예시

> [!NOTE]
> 박스 안의 강조글.
{CLOSE}

본문이 이어진다.

{OPEN}
여러 줄로 쓴 첫 문단은
제목이 아니다.

둘째 문단.
{CLOSE}

{CLOSE}

```md
{OPEN}
코드 안의 글
{CLOSE}
```

{OPEN}
박스 2. 닫지 않은 박스글

닫는 줄이 없다.

## 다음 절

다음 절의 본문.
"""
doc = proj / '보고서.md'
doc.write_text(DOC, encoding='utf-8')
edit = proj / '편집.md'
EDIT = '# 편집\n\n가 문단\n\n나 문단\n\n다 문단\n'
edit.write_text(EDIT, encoding='utf-8')
(proj / '슬라이드.md').write_text(f'---\nmarp: true\n---\n\n# 표지\n\n{OPEN}\n장 안의 글\n{CLOSE}\n', encoding='utf-8')

server, url, port = serve(proj, base / 'config')
errors = []

BOXES = """() => [...document.querySelectorAll('#lec-view aside.lec-textbox')].map((b) => ({
  lines: b.dataset.lines,
  title: b.querySelector(':scope > .lec-textbox-title')?.textContent.trim() ?? null,
  kids: [...b.children].filter((c) => !c.matches('.lec-textbox-fold')).map((c) => c.tagName + (c.className ? '.' + c.className.split(' ')[0] : '')),
  folded: b.classList.contains('lec-textbox-folded'),
  shown: [...b.children].filter((c) => !c.matches('.lec-textbox-fold') && c.getClientRects().length).length,
}))"""
PARTS = "() => [...document.querySelectorAll('#lec-toc li.part')].map((li) => [[...li.classList].find((c) => c.startsWith('part-')).slice(5), li.textContent.replace(/\\s+/g, ' ').trim()])"

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1360, 'height': 900}).new_page()
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        dialogs = []
        page.on('dialog', lambda d: (dialogs.append(d.message), d.accept()))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)

        def until(fn, ms=6000):
            """fn 이 참이 될 때까지 — 값을 돌려준다 (끝내 거짓이면 마지막 값)"""
            got = fn()
            for _ in range(ms // 50):
                if got:
                    break
                page.wait_for_timeout(50)
                got = fn()
            return got

        def open_doc(name, selector='#lec-view h1'):
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click()
            page.wait_for_function("(n) => document.querySelector('#lec-st-path')?.textContent.includes(n)", arg=name, timeout=8000)
            page.wait_for_selector(selector, timeout=8000)

        boxes = lambda: page.evaluate(BOXES)
        toast = lambda: page.text_content('#lec-toast') or ''

        print('[그리기]')
        open_doc('보고서.md')
        got = until(lambda: len(boxes()) == 3 and boxes())
        check('박스글 셋 (코드 안의 것과 남은 닫는 줄은 아니다)', got and len(got) == 3, boxes())
        got = got or [{}, {}, {}]
        check('첫 줄이 제목 띠', got[0].get('title') == '박스 1. 재고 통계는 왜 다른가', got[0])
        check('안에 문단·표·자료 줄·강조글', got[0].get('kids') == ['P.lec-textbox-title', 'P', 'DIV.table-wrap', 'P.lec-source', 'BLOCKQUOTE.alert'], got[0].get('kids'))
        check('줄 범위는 여는 줄부터 닫는 줄까지', got[0].get('lines') == '11-24', got[0].get('lines'))
        check('여러 줄 문단은 제목이 아니다', got[1].get('title') is None and got[1].get('kids') == ['P', 'P'], got[1])
        check('닫지 않은 박스글은 다음 제목 앞에서 끝난다', got[2].get('lines') == '43-46' and got[2].get('title') == '박스 2. 닫지 않은 박스글', got[2])
        outside = page.evaluate("() => ({ h2: !document.querySelector('#lec-view aside h2') && !!document.querySelector('#lec-view > h2'), after: document.querySelector('#lec-view > h2 + p')?.textContent })")
        check('다음 절은 박스글 밖', outside == {'h2': True, 'after': '다음 절의 본문.'}, outside)
        text = page.locator('#lec-view').inner_text()
        check('표시 줄은 화면에 없고 코드 안의 것은 글자 그대로', text.count('<!-- box -->') == 1 and text.count('<!-- /box -->') == 1 and '코드 안의 글' in text, (text.count('<!-- box -->'), text.count('<!-- /box -->')))
        look = page.evaluate("""() => { const b = document.querySelector('#lec-view aside.lec-textbox'); const s = getComputedStyle(b); const t = getComputedStyle(b.querySelector('.lec-textbox-title'));
          const quote = getComputedStyle(b.querySelector('blockquote'));
          return { border: s.borderLeftWidth, top: s.borderTopWidth, bg: s.backgroundColor, body: getComputedStyle(document.querySelector('#lec-view')).backgroundColor,
            titleBg: t.backgroundColor, weight: t.fontWeight, quoteBar: quote.borderLeftWidth, small: parseFloat(s.fontSize) < parseFloat(getComputedStyle(document.querySelector('#lec-view > p')).fontSize) }; }""")
        check('테두리·위쪽 굵은 줄·옅은 바탕·제목 띠 — 강조글(왼쪽 막대)과 다르게', look['border'] == '1px' and look['top'] == '3px' and look['bg'] != look['body'] and look['titleBg'] != look['bg']
              and int(look['weight']) >= 600 and look['quoteBar'] == '4px' and look['small'], look)
        contrast = page.evaluate("""() => { const lum = (c) => { const [r, g, b] = c.match(/[\\d.]+/g).slice(0, 3).map((v) => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }); return .2126 * r + .7152 * g + .0722 * b; };
          const flat = (el) => { const c = document.createElement('canvas').getContext('2d'); c.fillStyle = getComputedStyle(el).backgroundColor; c.fillRect(0, 0, 1, 1); const d = c.getImageData(0, 0, 1, 1).data; return `rgb(${d[0]}, ${d[1]}, ${d[2]})`; };
          const ratio = (fg, bg) => { const a = lum(fg), b = lum(bg); return (Math.max(a, b) + .05) / (Math.min(a, b) + .05); };
          const c = document.createElement('canvas').getContext('2d'); const rgb = (v) => { c.fillStyle = v; c.fillRect(0, 0, 1, 1); const d = c.getImageData(0, 0, 1, 1).data; return `rgb(${d[0]}, ${d[1]}, ${d[2]})`; };
          const box = document.querySelector('#lec-view aside.lec-textbox'); const title = box.querySelector('.lec-textbox-title'); const para = box.querySelector('p:not(.lec-textbox-title)');
          return [ratio(rgb(getComputedStyle(title).color), flat(title)), ratio(rgb(getComputedStyle(para).color), flat(box))]; }""")
        check('제목 띠와 안의 글의 대비 4.5 이상', min(contrast) >= 4.5, contrast)

        print('[목차]')
        parts = until(lambda: [x for x in page.evaluate(PARTS)] if page.locator('#lec-toc li.part-textbox').count() == 3 else None) or page.evaluate(PARTS)
        names = [x[1] for x in parts if x[0] == 'textbox']
        check('목차에 박스글 셋 — 번호와 제목 (캡션 머리는 뗀다)', len(names) == 3 and names[0].startswith('박스글 1') and '재고 통계는 왜 다른가' in names[0] and '박스 1.' not in names[0]
              and '여러 줄로 쓴 첫 문단' in names[1] and '닫지 않은 박스글' in names[2], names)
        tables = [x[1] for x in parts if x[0] == 'table']
        check('안의 표는 본문과 이어서 센다 — 박스글의 제목을 표의 캡션으로 가져가지 않는다', len(tables) == 2 and '본문의 표' in tables[0] and tables[1].startswith('표 2') and '재고 통계' not in tables[1], tables)
        check('안의 강조글도 센다', [x[1][:3] for x in parts if x[0] == 'box'] == ['강조글'], [x for x in parts if x[0] == 'box'])
        check('다음 절의 것이 아니다 — 박스글은 앞 절 아래', page.evaluate("() => { const li = [...document.querySelectorAll('#lec-toc li')]; return li.findIndex((x) => x.textContent.includes('다음 절')) > li.findIndex((x) => x.textContent.includes('닫지 않은')); }"))

        print('[가리키기]')
        page.evaluate("document.querySelector('#lec-view').parentElement.scrollTop = 99999")
        page.locator('#lec-toc li.part-textbox a').first.click()
        check('목차의 박스글을 누르면 그 자리로', until(lambda: page.evaluate("() => { const r = document.querySelector('#lec-view aside.lec-textbox').getBoundingClientRect(); return r.top >= 0 && r.top < innerHeight; }")))
        page.evaluate("document.querySelector('#lec-view').parentElement.scrollTop = 99999")
        page.locator('#lec-view > p a', has_text='박스 1').first.click()
        check("'[박스 1](#박스-1)' 링크를 누르면 그 박스글로", until(lambda: page.evaluate("() => { const r = document.querySelector('#lec-view aside.lec-textbox').getBoundingClientRect(); return r.top >= 0 && r.top < innerHeight; }")))
        check("'박스 1' 캡션에 가리킬 id", page.locator('#lec-view aside .lec-textbox-title').first.get_attribute('id') == '박스-1')

        print('[접기]')
        fold = page.locator('#lec-view aside.lec-textbox .lec-textbox-fold').first
        check('접는 버튼은 글이 없다 (찾기·복사에 들지 않는다)', fold.inner_text() == '' and fold.get_attribute('aria-expanded') == 'true')
        fold.click()
        got = until(lambda: boxes()[0]['folded'] and boxes())
        check('버튼을 누르면 접히고 제목만 남는다', bool(got) and got[0]['shown'] == 1 and fold.get_attribute('aria-expanded') == 'false', boxes()[0])
        page.locator('#lec-view aside .lec-textbox-title').first.click()
        page.wait_for_timeout(150)
        check('제목 글자를 눌러서는 펴지지 않는다', boxes()[0]['folded'])
        doc.write_text(DOC.replace('본문이 이어진다.', '본문이 이어지고 바뀌었다.'), encoding='utf-8')
        check('파일이 바뀌어 다시 그려도 접힌 채로', until(lambda: '바뀌었다' in page.locator('#lec-view').inner_text()) and boxes()[0]['folded'], boxes()[0])
        boxes2 = page.locator('#lec-view aside.lec-textbox').nth(1)
        boxes2.locator('.lec-textbox-fold').click()
        got = until(lambda: boxes()[1]['folded'] and boxes())
        check('제목이 없는 박스글은 첫 블록만 남는다', bool(got) and got[1]['shown'] == 1, boxes()[1])
        boxes2.locator('.lec-textbox-fold').click()
        check('다시 누르면 펴진다', until(lambda: not boxes()[1]['folded']) and boxes()[1]['shown'] == 2)
        page.locator('#lec-toc li.part-table a').nth(1).click()
        check('목차로 접힌 박스글 안의 표로 가면 펴진다', until(lambda: not boxes()[0]['folded']), boxes()[0])
        doc.write_text(DOC, encoding='utf-8')
        until(lambda: '바뀌었다' not in page.locator('#lec-view').inner_text())

        print('[슬라이드에는 없다]')
        open_doc('슬라이드.md', '#lec-view .lec-slide')
        check('Lectern 슬라이드에서는 박스글로 그리지 않는다', page.locator('#lec-view aside.lec-textbox').count() == 0 and '장 안의 글' in page.locator('#lec-view').inner_text())

        print('[넣기]')
        src = lambda: edit.read_text(encoding='utf-8')
        cells = lambda: page.evaluate("[...document.querySelectorAll('#lec-view .lec-line-edit')].map((e) => e.textContent)")

        def reset(text=EDIT):
            page.keyboard.press('Escape')
            page.keyboard.press('Escape')
            edit.write_text(text, encoding='utf-8')
            want = text.strip().split('\n')[-1].replace(OPEN, '').replace(CLOSE, '').strip('*# ')
            until(lambda: not page.locator('#lec-view .lec-line-edit').count() and (not want or want in page.locator('#lec-view').inner_text()))
            page.wait_for_timeout(250)   # 다시 그린 뒤 줄 단위가 놓일 때까지

        def menu(target, word):
            target.click(button='right')
            page.wait_for_selector('#lec-menu button', timeout=3000)
            labels = page.locator('#lec-menu button').all_inner_texts()
            if word is None or not any(word in x for x in labels):   # 없는 항목을 기다리며 멈추지 않는다 — 부른 쪽이 labels 로 판정한다
                page.keyboard.press('Escape')
                return labels
            page.locator('#lec-menu button', has_text=word).first.click()
            return labels

        open_doc('편집.md')
        reset()
        page.locator('#lec-view > p').last.click()
        page.wait_for_timeout(200)
        page.keyboard.press('ArrowDown')
        check('마지막 줄의 ↓ 로 새 줄', until(lambda: cells() == ['']), cells())
        page.keyboard.press('/')
        page.wait_for_selector('#lec-put:not([hidden])', timeout=3000)
        page.keyboard.type('박스글')
        check('넣기 창에 박스글', until(lambda: '박스글' in page.inner_text('#lec-put-list')) and '강조글' not in page.inner_text('#lec-put-list'), page.inner_text('#lec-put-list'))
        page.keyboard.press('Enter')
        want = EDIT + f'\n{OPEN}\n**박스 1. 제목**\n\n여기에 내용을 씁니다.\n{CLOSE}\n'
        check('여는 줄·제목·내용·닫는 줄을 넣는다', until(lambda: src() == want), src())
        check('제목 줄이 열린다', until(lambda: cells() and '박스 1. 제목' in cells()[0]), cells())
        page.keyboard.press('Escape')
        check('넣은 것이 박스글로 보인다', until(lambda: len(boxes()) == 1 and boxes()[0]['title'] == '박스 1. 제목'), boxes())

        print('[안의 줄 고치기]')
        page.locator('#lec-view aside p', has_text='여기에 내용을').click()
        page.wait_for_timeout(200)
        page.keyboard.press('F2')
        check('안의 줄이 F2 로 열린다', until(lambda: cells() == ['여기에 내용을 씁니다.']), cells())
        page.keyboard.press('End')
        page.keyboard.type(' 고침')
        page.keyboard.press('Enter')
        check('그 줄만 바뀌고 표시 줄은 그대로', until(lambda: src() == want.replace('씁니다.', '씁니다. 고침')), src())
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        until(lambda: not cells())

        print('[풀기·지우기]')
        labels = menu(page.locator('#lec-view aside p').last, None)
        check('박스글 안의 우클릭에 풀기·지우기', any('박스글 풀기' in x for x in labels) and any('박스글 지우기' in x for x in labels), labels)
        labels = menu(page.locator('#lec-view > p').first, None)
        check('박스글 밖에는 없다', not any('박스글 풀기' in x for x in labels), labels)
        menu(page.locator('#lec-view aside p').last, '박스글 풀기')
        check('풀면 표시 줄 둘만 빠진다', until(lambda: src() == EDIT + '\n**박스 1. 제목**\n\n여기에 내용을 씁니다. 고침\n'), src())
        check('보통 글로 보인다', until(lambda: not boxes()) and '여기에 내용을' in page.locator('#lec-view').inner_text())
        reset(EDIT + f'\n{OPEN}\n**박스 1. 지울 것**\n\n안의 글\n{CLOSE}\n\n뒤 문단\n')
        until(lambda: len(boxes()) == 1)
        menu(page.locator('#lec-view aside p').last, '박스글 지우기')
        check('지우기 전에 묻는다', until(lambda: any('박스글을 지울까요' in d for d in dialogs)), dialogs)
        check('안의 글까지 지운다', until(lambda: src() == EDIT + '\n뒤 문단\n'), src())

        print('[묶기]')
        reset()

        def pick_two():
            page.locator('#lec-view > p').first.click()
            page.wait_for_timeout(200)
            page.keyboard.press('Shift+ArrowDown')
            page.wait_for_timeout(300)

        pick_two()
        labels = menu(page.locator('#lec-view > p').first, '박스글로 묶기')   # Esc 는 고른 줄을 풀므로 메뉴를 한 번만 연다
        check('고른 줄의 우클릭에 박스글로 묶기', any('박스글로 묶기' in x for x in labels), labels)
        want = f'# 편집\n\n{OPEN}\n**박스 1. 제목**\n\n가 문단\n\n나 문단\n{CLOSE}\n\n다 문단\n'
        check('고른 줄을 묶고 제목 줄을 넣는다', until(lambda: src() == want), src())
        check('묶은 것이 박스글로 보인다', until(lambda: len(boxes()) == 1 and boxes()[0]['kids'] == ['P.lec-textbox-title', 'P', 'P']), boxes())
        reset('# 편집\n\n가 문단\n\n## 절\n\n나 문단\n')
        page.locator('#lec-view > p').first.click()
        page.wait_for_timeout(200)
        page.keyboard.press('Shift+ArrowDown')
        page.keyboard.press('Shift+ArrowDown')
        page.wait_for_timeout(200)
        before = src()
        menu(page.locator('#lec-view > p').first, '박스글로 묶기')
        check('제목 줄에 걸치면 묶지 않고 까닭을 알린다', until(lambda: '제목 줄은 박스글로 묶지 않습니다' in toast()) and src() == before, (toast(), src()))

        print('[번호]')
        reset(f'# 편집\n\n가 문단\n\n[박스 1](#박스-1) 을 보라.\n\n{OPEN}\n**박스 1. 먼저 있던 것**\n\n글\n{CLOSE}\n')
        until(lambda: len(boxes()) == 1)
        page.locator('#lec-view > p').first.click()
        page.wait_for_timeout(200)
        page.keyboard.press('Insert')   # 현재 줄 하나를 고른다
        page.wait_for_timeout(200)
        labels = menu(page.locator('#lec-view > p').first, '박스글로 묶기')
        if any('박스글로 묶기' in x for x in labels):
            want = f'# 편집\n\n{OPEN}\n**박스 1. 제목**\n\n가 문단\n{CLOSE}\n\n[박스 2](#박스-2) 을 보라.\n\n{OPEN}\n**박스 2. 먼저 있던 것**\n\n글\n{CLOSE}\n'
            check('앞에 박스글이 생기면 번호와 참조 링크가 밀린다', until(lambda: src() == want), src())
        else:
            check('한 줄을 고른 우클릭에 박스글로 묶기', False, labels)

        print('[Claude 에 박스글 요청]')
        # 요청 글만 본다 — 터미널은 띄우지 않는다 (셸을 쓸 수 없다고 답한다)
        page.route('**/api/term/**', lambda r: r.fulfill(status=501, content_type='application/json', body='{"error": "점검에서는 터미널을 띄우지 않습니다"}'))
        page.evaluate("import('/static/js/store.js').then(({ on }) => { window.__sent = []; on('term-paste', (text) => window.__sent.push(text)); })")
        reset(f'# 편집\n\n가 문단은\n두 줄이다\n\n나 문단\n\n{OPEN}\n**박스 1. 있던 것**\n\n안의 글\n{CLOSE}\n\n다 문단\n')
        until(lambda: len(boxes()) == 1)
        sent = lambda: page.evaluate('window.__sent')
        before = src()
        labels = menu(page.locator('#lec-view > p').first, 'Claude 에 박스글 요청')
        check('줄의 우클릭에 Claude 에 박스글 요청', any('Claude 에 박스글 요청' in x for x in labels), labels)
        got = until(lambda: sent() and sent()[-1]) or ''
        check('요청 글: 그 블록의 끝 줄 뒤, 다음 번호, 박스글 규칙, 한 줄', '@편집.md 4행 바로 뒤에 박스글로' in got and '**박스 2. 제목**' in got and '<!-- box -->' in got and '<!-- /box -->' in got and '\n' not in got, got)
        check('Lectern 은 파일을 고치지 않는다', src() == before)
        page.keyboard.press('Escape')
        menu(page.locator('#lec-view aside p').last, 'Claude 에 박스글 요청')
        got = until(lambda: len(sent()) >= 2 and sent()[-1]) or ''
        check('박스글 안에서 누르면 그 박스글 뒤에', '@편집.md 12행 바로 뒤에' in got, got)
        page.keyboard.press('Escape')
        page.locator('#lec-view > p').nth(1).click()
        page.wait_for_timeout(200)
        page.keyboard.press('Insert')
        page.wait_for_timeout(200)
        menu(page.locator('#lec-view > p').nth(1), 'Claude 에 박스글 요청')
        got = until(lambda: len(sent()) >= 3 and sent()[-1]) or ''
        check('고른 줄이면 끝 줄 뒤에', '@편집.md 6행 바로 뒤에' in got, got)
        labels = []
        page.keyboard.press('Escape')

        print('[모아 보기]')
        page.keyboard.press('Escape')
        page.locator('[role=tab][data-tab="parts"]').click()
        check("모아 보기에 '박스글' 종류", until(lambda: page.locator('#lec-parts-kinds button[data-kind="textbox"]:not(.zero)').count() == 1, 8000),
              page.locator('#lec-parts-kinds').inner_text() if page.locator('#lec-parts-kinds').count() else '')
        page.locator('#lec-parts-kinds button[data-kind="textbox"]').click()
        listed = until(lambda: page.locator('#lec-parts-list').inner_text() if '재고 통계' in page.locator('#lec-parts-list').inner_text() else '')
        check('박스글의 제목이 이름', '박스 1. 재고 통계는 왜 다른가' in listed and '닫지 않은 박스글' in listed, listed[:300])

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
