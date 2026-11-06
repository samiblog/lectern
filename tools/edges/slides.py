"""슬라이드 (D96): 칸·배치·글자 크기·장별 CSS, 잘못 쓴 칸의 점검, 칸 안 한 줄 편집, 구조 보기, 장 다루기, 슬라이드 창"""
import json
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-slides-'))
proj = base / 'proj'
(proj / 'data').mkdir(parents=True)
(proj / 'images').mkdir()
(proj / 'data' / '월별.csv').write_text('월,값\n1월,10\n2월,20\n3월,15\n', encoding='utf-8')
(proj / 'images' / '큰그림.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1400"><rect width="900" height="1400" fill="#7a5a3a"/></svg>', encoding='utf-8')
DECK = """---
marp: true
title: 시험 발표
paginate: true
---

<!-- _class: lead -->

# 표지

부제

---

<!-- layout: kpi -->

## 숫자 장

::: a kpi
**9,120**
가격
:::

::: b kpi
**+5.4%**
증감
:::

::: c kpi
**19.2**
재고
:::

::: d kpi
**-10%**
변화
:::

::: e
```vega-lite
{"width": "container", "data": {"url": "data/월별.csv"}, "mark": "line", "encoding": {"x": {"field": "월", "type": "ordinal", "sort": null}, "y": {"field": "값", "type": "quantitative"}}}
```
:::

---

<!-- layout: quad -->

## 네 칸 장

::: a card
### 첫째

- 왼쪽 위 항목
:::

::: b card
### 둘째

- 오른쪽 위 항목
:::

::: c card
### 셋째

- 왼쪽 아래 항목
:::

::: d card
### 넷째

- 오른쪽 아래 항목
- 끝 항목
:::

---

<!-- layout: two -->

## 표 장

::: a
| 이름 | 값 |
|---|---:|
| 가 | 1,080 |
| 나 | 530 |
:::

::: b accent
한 문단뿐인 칸이다.
:::

---

<!-- layout: two -->
<!-- text: 표 12, 제목 26 -->

## 크기 장

::: a
| 이름 | 값 |
|---|---:|
| 다 | 1 |
:::

::: b card 22
> 박스 글이다.

크기 있는 칸의 글이다.
:::

---

<style scoped>
section { background-color: rgb(1, 2, 3); }
@import url("https://example.com/x.css");
h2 { background-image: url("https://example.com/y.png"); }
</style>

## 장별 CSS 장

::: hub note at 100 200 300 120
자리 칸의 글이다.
:::

---

<!-- eyebrow: 머리글 -->

![bg right:30% sepia](images/큰그림.svg)

## 마지막 장

- 끝 글
"""
deck = proj / '발표.md'
deck.write_text(DECK, encoding='utf-8')
(proj / '잘못.md').write_text("""---
marp: true
---

<!-- layout: two -->

## 넘친 칸 이름

::: a
가
:::

::: b
나
:::

::: c
셋째
:::

---

<!-- layout: 없는배치 -->

## 없는 배치

::: a
가
:::

---

<!-- layout: two -->

## 칸 이름 오타

::: a
가
:::

::: z
나
:::

---

<!-- layout: two -->

## 닫는 줄 빠짐

::: a
가

::: b
나
:::

---

<!-- layout: two -->

## 칸 밖 글

사이 글

::: a
가
:::

::: b
나
:::

---

<!-- layout: three -->

## 빈 칸

::: a
가
:::

::: b
나
:::

---

<!-- layout: stack -->

## 넘침

::: a
""" + '\n'.join(f'- 항목 {i}' for i in range(40)) + """
:::

::: b
글
:::

---

## 짝 없는 줄

:::
""", encoding='utf-8')
(proj / '겹침.md').write_text("""---
marp: true
---

## 자리 칸만 있는 장

::: a at 100 40 300 120
제목과 겹친다
:::

::: b at 500 200 300 200
가
:::

::: c at 520 220 300 200
나
:::

::: d at 1100 600 300 200
밖으로 나간다
:::

---

<!-- grid: t t / a b / c c -->

## 열을 적지 않은 격자

::: a
가
:::

::: b
나
:::

::: c
| 아주아주긴열이름하나 | 아주아주긴열이름둘 | 아주아주긴열이름셋 | 아주아주긴열이름넷 | 아주아주긴열이름다섯 | 아주아주긴열이름여섯 | 아주아주긴열이름일곱 |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000,000,000,000 | 1,000,000,000,000 | 1,000,000,000,000 | 1,000,000,000,000 | 1,000,000,000,000 | 1,000,000,000,000 | 1,000,000,000,000 |
:::
""", encoding='utf-8')
(proj / '악성.md').write_text("""---
marp: true
---

<style scoped>
} #lec-status { display: none; } body { background: red; } section {
</style>

<!-- layout: x"><img src=x onerror=alert(1)> -->
<!-- grid: a"><script>alert(2)</script> -->
<!-- eyebrow: <img src=x onerror=alert(3)> -->
<!-- text: 표 12; color: red -->

## 악성 장

::: a" onclick="alert(4) card<script>
글
:::

::: b at 1 2 3 4" style="position:fixed
글
:::

---

<style>
@import url("https://example.com/a.css");
#lec-status { display: none; }
</style>

## 둘째
""", encoding='utf-8')
(proj / '보통.md').write_text('# 보통\n\n첫 문단이다.\n\n::: a\n이것은 글이다.\n:::\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
server, url, port = serve(proj, config)
extra = []
TEXT = lambda: deck.read_text(encoding='utf-8')


def run():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1500, 'height': 950})
        page.on('pageerror', lambda e: extra.append(str(e)[:200]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        page.locator('#lec-tree .row.file[data-doc="발표.md"]').click()
        page.wait_for_selector('#lec-view.lec-deck', timeout=30000)
        page.wait_for_selector('#lec-view .lec-chart svg', timeout=30000)
        page.wait_for_timeout(600)
        slide = lambda n: page.locator('#lec-view .lec-slide').nth(n - 1)
        cell_edit = '#lec-view .lec-line-edit'
        toast = lambda: page.text_content('#lec-toast') or ''
        pts = lambda loc: loc.evaluate("(e) => Math.round(parseFloat(getComputedStyle(e).fontSize) * 7.5) / 10")
        open_text = lambda: page.evaluate("[...document.querySelectorAll('.lec-line-edit')].map((e) => e.textContent)")

        def edit(loc):
            loc.scroll_into_view_if_needed()
            loc.click()
            page.keyboard.press('F2')
            page.wait_for_selector(cell_edit, timeout=3000)

        def reset():
            if page.locator(cell_edit).count():
                page.keyboard.press('Escape')
            deck.write_text(DECK, encoding='utf-8')
            page.wait_for_function("document.querySelectorAll('#lec-view .lec-slide').length === 7 && !document.querySelector('.lec-line-edit')", timeout=8000)
            page.wait_for_timeout(1900)

        print('[그리기]')
        check('장 일곱', slide(1).count() and page.locator('#lec-view .lec-slide').count() == 7)
        check('칸', page.locator('#lec-view .lec-cell').count() == 14, page.locator('#lec-view .lec-cell').count())
        check('깨끗한 문서에는 점검이 없다', page.locator('#lec-st-check').is_hidden(), page.text_content('#lec-st-check'))
        check('기본 글자 크기', [pts(slide(3).locator('h2')), pts(slide(3).locator('h3').first), pts(slide(3).locator('li').first), pts(slide(4).locator('table'))] == [30, 20, 18, 14],
              [pts(slide(3).locator('h2')), pts(slide(3).locator('h3').first), pts(slide(3).locator('li').first), pts(slide(4).locator('table'))])
        check('그 장의 글자 크기', [pts(slide(5).locator('table')), pts(slide(5).locator('h2'))] == [12, 26], [pts(slide(5).locator('table')), pts(slide(5).locator('h2'))])
        check('다음 장으로 번지지 않는다', pts(slide(6).locator('h2')) == 30)
        check('칸의 글자 크기', [pts(slide(5).locator('.lec-cell').nth(1).locator('p').last), pts(slide(5).locator('blockquote'))] == [22, 22])
        check('배치는 그 장에만', 'lec-grid' not in (slide(6).get_attribute('class') or ''))
        ss = page.evaluate("""() => { const s = document.querySelectorAll('#lec-view .lec-slide'); const at = s[5].querySelector('.lec-cell'); const css = [...document.querySelectorAll('#lec-view .lec-deck-style')].map((x) => x.textContent).join('');
          return { bg: getComputedStyle(s[5]).backgroundColor, other: getComputedStyle(s[4]).backgroundColor, pos: getComputedStyle(at).position, left: at.style.left, width: at.style.width, css, h2: getComputedStyle(s[5].querySelector('h2')).backgroundImage }; }""")
        check('장별 CSS 는 그 장에만', ss['bg'] == 'rgb(1, 2, 3)' and ss['other'] != ss['bg'], ss)
        check('장별 CSS 의 인터넷 길은 지운다', 'example.com' not in ss['css'] and ss['h2'] == 'none', ss['css'][:200])
        check('자리 칸', ss['pos'] == 'absolute' and ss['left'] == '100px' and ss['width'] == '300px', ss)
        check('머리글', slide(7).locator('.lec-eyebrow').text_content() == '머리글')
        check('배경 필터', 'sepia' in (slide(7).locator('.lec-slide-bg img').evaluate('(e) => e.style.filter')))

        for name in ('book', 'dracula'):
            page.select_option('#lec-theme', name)
            page.wait_for_timeout(1800)
            check(f'{name} 스타일에서도 글자 크기가 같다', [pts(slide(3).locator('h2')), pts(slide(3).locator('li').first), pts(slide(4).locator('table'))] == [30, 18, 14])
        page.select_option('#lec-theme', 'default')
        page.wait_for_timeout(1500)

        print('[한 줄 편집]')
        edit(slide(2).locator('.lec-cell.kpi').first.locator('p'))
        check('KPI 숫자 줄', open_text() == ['**9,120**'], open_text())
        page.keyboard.press('Escape')
        edit(slide(3).locator('.lec-cell').nth(3).locator('li').first)
        check('나란한 칸: 누른 칸이 열린다', open_text() == ['오른쪽 아래 항목'], open_text())
        page.keyboard.press('Escape')
        edit(slide(3).locator('.lec-cell').nth(3).locator('li').last)
        page.keyboard.press('Control+Enter')
        page.wait_for_timeout(300)
        page.keyboard.type('새 항목')
        page.keyboard.press('Enter')
        page.wait_for_timeout(900)
        check('칸 끝의 새 줄은 칸 안에', '- 끝 항목\n- 새 항목\n:::' in TEXT(), TEXT()[TEXT().find('끝 항목') - 10:TEXT().find('끝 항목') + 40])
        reset()
        edit(slide(4).locator('.lec-cell').nth(1).locator('p'))
        page.keyboard.press('Alt+ArrowDown')
        page.wait_for_timeout(500)
        check('하나뿐인 문단을 옮겨도 그대로', TEXT() == DECK, toast())
        page.keyboard.press('Home')
        page.keyboard.press('Backspace')
        page.wait_for_timeout(500)
        check('맨 앞 Backspace 는 칸 머리 줄과 잇지 않는다', TEXT() == DECK, toast())
        reset()
        t = slide(3).locator('.lec-cell').first.locator('li')
        t.scroll_into_view_if_needed()
        t.click()
        page.keyboard.press('Shift+Enter')
        page.wait_for_timeout(200)
        page.keyboard.press('Delete')
        page.wait_for_timeout(900)
        check('칸의 줄을 지워도 칸 표시는 남는다', '::: a card\n### 첫째\n\n:::' in TEXT(), TEXT()[TEXT().find('### 첫째') - 14:TEXT().find('### 첫째') + 30])
        page.keyboard.press('Control+z')
        page.wait_for_timeout(900)
        check('Ctrl+Z 로 돌아온다', TEXT() == DECK)
        page.keyboard.press('Escape')
        reset()

        print('[글자 크기]')
        t = slide(4).locator('.lec-cell').first.locator('td').first
        t.scroll_into_view_if_needed()
        t.click()
        for _ in range(2):
            page.keyboard.press('Control+Shift+Comma')
            page.wait_for_timeout(800)
        check('표에서 두 번 줄이기', '<!-- text: 표 12 -->' in TEXT() and pts(slide(4).locator('table')) == 12, [x for x in TEXT().split('\n') if 'text:' in x])
        check('구조는 그대로', TEXT().count('\n:::\n') == DECK.count('\n:::\n'))
        for _ in range(2):
            page.keyboard.press('Control+z')
            page.wait_for_timeout(700)
        check('Ctrl+Z 로 지시어가 사라진다', TEXT() == DECK, toast())
        t = slide(5).locator('.lec-cell').nth(1).locator('p').last
        t.scroll_into_view_if_needed()
        t.click()
        page.keyboard.press('Control+Shift+Period')
        page.wait_for_timeout(900)
        check('크기 있는 칸은 머리 줄의 수를 고친다', '::: b card 23' in TEXT(), toast())
        reset()
        edit(slide(3).locator('h2'))
        page.keyboard.press('Control+Shift+Comma')
        page.wait_for_timeout(1200)
        check('F2 칸이 열린 채로 눌러도 된다', '<!-- text: 제목 29 -->' in TEXT(), [x for x in TEXT().split('\n') if 'text:' in x])
        reset()
        page.evaluate("import('/static/js/store.js').then((m) => { m.S.pane.here = { ...m.S.pane.here, line: 42 }; })")
        page.keyboard.press('Control+Shift+Period')
        page.wait_for_timeout(500)
        check('차트 줄은 바꾸지 않는다', TEXT() == DECK and '글자 크기' in toast(), toast())

        print('[표 점검]')
        cases = (Path(__file__).parent / 'slideops_cases.js').read_text(encoding='utf-8')
        r = page.evaluate("async (src) => { const m = await import('/static/js/slideops.js'); const lo = await import('/static/js/lineops.js'); return new Function('m', 'lo', src)(m, lo); }", cases)
        check(f"슬라이드 계산 {r['n']}건", not r['fails'], r['fails'][:4])

        print('[구조 보기]')
        check('꺼 둔 동안 꼬리표는 줄 단위가 아니다', page.locator('#lec-view .lec-tag[data-lines]').count() == 0)
        page.locator('#lec-st-structure').click()
        page.wait_for_timeout(300)
        tag = slide(3).locator('.lec-cell').nth(1).locator('.lec-tag')
        check('칸 꼬리표', tag.text_content() == '::: b card', tag.text_content())
        check('장 꼬리표', '<!-- layout: quad -->' in page.locator('#lec-view .lec-slide-wrap').nth(2).locator('.lec-slide-tags').text_content())
        tag.scroll_into_view_if_needed()
        tag.dblclick()
        page.wait_for_selector(cell_edit, timeout=3000)
        check('꼬리표에서 그 줄을 연다', open_text() == ['::: b card'], open_text())
        page.keyboard.press('End')
        page.keyboard.type(' center')
        page.keyboard.press('Enter')
        page.wait_for_timeout(1000)
        check('칸 꾸밈을 고쳤다', '::: b card center' in TEXT() and 'center' in (slide(3).locator('.lec-cell').nth(1).get_attribute('class') or ''))
        check('다시 그려도 구조 보기가 켜져 있다', page.locator('#lec-view .lec-tag[data-lines]').count() > 0)
        tag = page.locator('#lec-view .lec-slide-wrap').nth(2).locator('.lec-slide-tags .lec-tag')
        tag.dblclick()
        page.wait_for_selector(cell_edit, timeout=3000)
        page.keyboard.press('Control+a')
        page.keyboard.type('<!-- layout: two -->')
        page.keyboard.press('Enter')
        page.wait_for_timeout(1000)
        check('배치를 고치면 칸 경고가 나온다', page.locator('#lec-st-check').is_visible() and '1' in page.text_content('#lec-st-check'), page.text_content('#lec-st-check'))
        reset()
        page.locator('#lec-st-structure').click()
        page.wait_for_timeout(200)
        check('끄면 꼬리표가 빠진다', page.locator('#lec-view .lec-tag[data-lines]').count() == 0 and not page.locator('#lec-view.lec-structure').count())

        print('[장 다루기]')
        t = slide(4).locator('h2')
        t.scroll_into_view_if_needed()
        t.click()
        page.keyboard.press('Control+m')
        page.wait_for_selector(cell_edit, timeout=4000)
        check('새 장 제목이 바로 열린다', page.locator('#lec-view .lec-slide').count() == 8 and open_text() == ['새 장'], open_text())
        page.keyboard.press('Control+a')
        page.keyboard.type('더한 장')
        page.keyboard.press('Enter')
        page.wait_for_timeout(900)
        check('그 장 뒤에 들어갔다', slide(5).locator('h2').text_content() == '더한 장' and '---\n\n## 더한 장\n' in TEXT())
        page.keyboard.press('Control+z')
        page.wait_for_timeout(800)
        page.keyboard.press('Control+z')
        page.wait_for_timeout(800)
        check('Ctrl+Z 두 번이면 처음으로', TEXT() == DECK, toast())
        t = slide(2).locator('h2')
        t.scroll_into_view_if_needed()
        t.click()
        page.keyboard.press('Control+d')
        page.wait_for_timeout(1000)
        check('복제', page.locator('#lec-view .lec-slide').count() == 8 and TEXT().count('## 숫자 장') == 2)
        reset()
        t = slide(3).locator('h2')
        t.scroll_into_view_if_needed()
        t.click()
        page.keyboard.press('Control+Shift+PageUp')
        page.wait_for_timeout(1000)
        check('앞으로 옮기기', slide(2).locator('h2').text_content() == '네 칸 장' and slide(3).locator('h2').text_content() == '숫자 장')
        check('옮겨도 칸 수는 그대로', page.locator('#lec-view .lec-cell').count() == 14)
        page.keyboard.press('Control+Shift+PageDown')
        page.wait_for_timeout(1000)
        check('뒤로 옮기면 원문이 처음과 같다', TEXT() == DECK, TEXT()[:80])
        t = slide(7).locator('h2')
        t.scroll_into_view_if_needed()
        t.click()
        page.keyboard.press('Control+Shift+PageDown')
        page.wait_for_timeout(500)
        check('맨 끝이면 알린다', TEXT() == DECK and '더 옮길' in toast(), toast())
        answers = []
        page.on('dialog', lambda d: (answers.append(d.message), d.accept()))
        t = slide(4).locator('h2')
        t.scroll_into_view_if_needed()
        t.click(button='right')
        page.wait_for_timeout(200)
        menu = page.locator('#lec-menu').inner_text()
        check('우클릭 메뉴', all(x in menu for x in ('장 더하기', '장 복제', '장 앞으로 옮기기', '장 뒤로 옮기기', '장 지우기')), menu[:200])
        page.locator('#lec-menu').get_by_text('장 지우기').click()
        page.wait_for_timeout(1000)
        check('장 지우기는 묻고 지운다', answers == ['4장을 지울까요?'] and page.locator('#lec-view .lec-slide').count() == 6 and '## 표 장' not in TEXT(), answers)
        page.keyboard.press('Control+z')
        page.wait_for_timeout(900)
        check('지운 장도 Ctrl+Z 로', TEXT() == DECK)
        reset()

        print('[목차]')
        toc = page.locator('#lec-toc .toc-slides a')
        check('슬라이드 목록', toc.count() == 7 and '3. 네 칸 장' in toc.nth(2).text_content(), toc.count())
        check('카드 소제목은 없다', '첫째' not in page.locator('#lec-toc').text_content())
        toc.nth(5).click()
        page.wait_for_timeout(500)
        top = page.evaluate("(() => { const w = document.querySelectorAll('#lec-view .lec-slide-wrap')[5]; const s = document.querySelector('#lec-content'); return w.getBoundingClientRect().top - s.getBoundingClientRect().top; })()")
        check('누르면 그 장으로', abs(top) < 200, top)

        print('[문서로 보기]')
        page.locator('#lec-st-slides').click()
        page.wait_for_function("!document.querySelector('#lec-view').classList.contains('lec-deck')", timeout=8000)
        page.wait_for_timeout(600)
        check('칸 표시가 글자로 나오지 않는다', ':::' not in page.locator('#lec-view').text_content())
        check('칸의 글은 보인다', '오른쪽 위 항목' in page.locator('#lec-view').text_content())
        page.locator('#lec-st-slides').click()
        page.wait_for_selector('#lec-view.lec-deck', timeout=8000)
        page.wait_for_timeout(1200)

        print('[발표·인쇄]')
        slide(1).scroll_into_view_if_needed()
        page.locator('#lec-st-structure').click()
        page.keyboard.press('Shift+F5')
        page.wait_for_selector('#lec-present', state='visible', timeout=5000)
        for _ in range(5):
            page.keyboard.press('ArrowRight')
            page.wait_for_timeout(120)
        pr = page.evaluate("""() => { const h = document.querySelector('#lec-present .pr-deck'); const s = h.querySelector('.lec-slide'); return { bg: getComputedStyle(s).backgroundColor, tag: [...s.querySelectorAll('.lec-tag')].filter((e) => getComputedStyle(e).display !== 'none').length, at: !!s.querySelector('.lec-at') }; }""")
        check('발표에서도 장별 CSS 가 먹고 꼬리표는 없다', pr == {'bg': 'rgb(1, 2, 3)', 'tag': 0, 'at': True}, pr)
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)
        page.emulate_media(media='print')
        check('인쇄에는 꼬리표가 없다', page.evaluate("[...document.querySelectorAll('#lec-view .lec-tag, #lec-view .lec-slide-tags')].every((e) => getComputedStyle(e).display === 'none')"))
        page.emulate_media(media='screen')
        page.locator('#lec-st-structure').click()

        print('[점검]')
        page.locator('#lec-tree .row.file[data-doc="잘못.md"]').click()
        page.wait_for_function("document.querySelector('#lec-view .lec-slide h2')?.textContent === '넘친 칸 이름'", timeout=10000)
        page.wait_for_timeout(1000)
        label = page.text_content('#lec-st-check')
        check('점검 장 수', '8장' in label, label)
        page.locator('#lec-st-check').click()
        page.wait_for_timeout(200)
        menu = page.locator('#lec-menu').inner_text()
        for want in ('칸 c 이(가) 배치에 없습니다', "배치 '없는배치' 이(가) 없습니다", '칸 z 이(가) 배치에 없습니다', '칸 b 이(가) 비어 있습니다', '칸 a 의 닫는 ::: 가 빠졌습니다', '칸 밖에 글이 있습니다', '칸 c 이(가) 비어 있습니다', 'px 넘칩니다', '짝이 맞지 않는 :::', '목록을 터미널에 붙여 넣기'):
            check(f'목록: {want}', want in menu, menu[:400])
        page.locator('#lec-menu').get_by_text('칸 z 이(가) 배치에 없습니다').click()
        page.wait_for_timeout(500)
        here = page.evaluate("import('/static/js/store.js').then((m) => m.S.pane.here.line)")
        check('고르면 그 줄로 간다', here == (proj / '잘못.md').read_text(encoding='utf-8').split('\n').index('::: z') + 1 or here > 0, here)

        print('[겹침]')
        page.locator('#lec-tree .row.file[data-doc="겹침.md"]').click()
        page.wait_for_function("document.querySelector('#lec-view .lec-slide h2')?.textContent === '자리 칸만 있는 장'", timeout=10000)
        page.wait_for_timeout(800)
        page.locator('#lec-st-check').click()
        page.wait_for_timeout(200)
        menu = page.locator('#lec-menu').inner_text()
        for want in ('칸 a 이(가) 제목과 겹칩니다', '칸 b 과(와) 칸 c 이(가) 겹칩니다', '칸 d 이(가) 슬라이드 밖으로 나갑니다', '칸 c 이(가) 옆으로'):
            check(f'목록: {want}', want in menu, menu[:300])
        page.keyboard.press('Escape')
        box = page.evaluate("""() => { const s = document.querySelectorAll('#lec-view .lec-slide'); const k = s[0].offsetWidth / s[0].getBoundingClientRect().width; const h = s[0].querySelector('h2').getBoundingClientRect(); const c = [...s[1].querySelectorAll('.lec-cell')].map((e) => e.getBoundingClientRect().width * k);
          return { top: (h.top - s[0].getBoundingClientRect().top) * k, a: c[0], b: c[1], c: c[2] }; }""")
        check('자리 칸만 있는 장의 제목은 위에', box['top'] < 80, box)
        check('열을 적지 않아도 온 폭', abs(box['a'] - box['b']) < 2 and box['c'] > 1100, box)

        print('[악성 문서]')
        page.locator('#lec-tree .row.file[data-doc="악성.md"]').click()
        page.wait_for_function("document.querySelector('#lec-view .lec-slide h2')?.textContent === '악성 장'", timeout=10000)
        page.wait_for_timeout(700)
        bad = page.evaluate("""() => { const v = document.querySelector('#lec-view'); const css = [...v.querySelectorAll('.lec-deck-style')].map((s) => s.textContent).join('');
          return { status: getComputedStyle(document.querySelector('#lec-status')).display, body: getComputedStyle(document.body).backgroundColor, scripts: v.querySelectorAll('script').length, onerr: v.querySelectorAll('[onerror], [onclick]').length, imported: css.includes('example.com') }; }""")
        check('장별 CSS 가 앱을 건드리지 못한다', bad['status'] != 'none' and bad['body'] != 'rgb(255, 0, 0)', bad)
        check('스크립트·이벤트 속성이 없다', bad['scripts'] == 0 and bad['onerr'] == 0, bad)
        check('인터넷 CSS 를 부르지 않는다', not bad['imported'], bad)

        print('[보통 문서]')
        page.locator('#lec-tree .row.file[data-doc="보통.md"]').click()
        page.wait_for_selector('#lec-view h1', timeout=8000)
        page.wait_for_timeout(500)
        check('보통 문서의 ::: 는 글이다', ':::' in page.locator('#lec-view').text_content())
        check('슬라이드 도구가 없다', page.locator('#lec-st-structure').is_hidden() and page.locator('#lec-st-check').is_hidden())
        page.locator('#lec-view p').first.click()
        page.keyboard.press('Control+Shift+Period')
        page.keyboard.press('Control+m')
        page.wait_for_timeout(400)
        check('슬라이드 키가 듣지 않는다', '<!--' not in (proj / '보통.md').read_text(encoding='utf-8') and '---' not in (proj / '보통.md').read_text(encoding='utf-8'))

        print('[슬라이드 창]')
        pid = page.evaluate("import('/static/js/store.js').then((m) => m.S.tab.id)")
        win = b.new_page(viewport={'width': 1200, 'height': 800})
        win.on('pageerror', lambda e: extra.append('창 ' + str(e)[:200]))
        win.goto(f"{url}?solo={quote(pid)}&w=abcdef0123&type=doc&path={quote('발표.md')}&deck=1")
        win.wait_for_selector('#lec-view.lec-deck', timeout=20000)
        win.wait_for_timeout(1200)
        check('슬라이드 창의 기본 스타일', win.evaluate('document.documentElement.dataset.theme') == 'deck', win.evaluate('document.documentElement.dataset.theme'))
        check('메인 스타일은 그대로', page.evaluate('document.documentElement.dataset.theme') != 'deck')
        check('스타일을 고를 수 있다', win.locator('#lec-theme').is_visible() and win.locator('#lec-theme').input_value() == 'deck', win.locator('#lec-theme').input_value())
        win.select_option('#lec-theme', 'nord')
        win.wait_for_timeout(1500)
        saved = json.loads((config / 'config.json').read_text(encoding='utf-8'))
        check('슬라이드 창의 스타일만 저장한다', saved.get('slide_theme') == 'nord' and saved.get('theme') != 'nord', [saved.get('slide_theme'), saved.get('theme')])
        check('메인 화면은 그대로', page.evaluate('document.documentElement.dataset.theme') != 'nord')
        plain = b.new_page(viewport={'width': 1000, 'height': 700})
        plain.goto(f"{url}?solo={quote(pid)}&w=abcdef0124&type=doc&path={quote('보통.md')}")
        plain.wait_for_selector('#lec-view h1', timeout=15000)
        check('보통 독립창은 스타일을 고르지 않는다', plain.locator('#lec-theme').is_hidden())
        plain.close()
        win.close()

        print('[새 발표 문서]')
        page.keyboard.press('Control+n')
        page.wait_for_selector('#lec-insert-list li', timeout=4000)
        page.fill('#lec-insert-input' if page.locator('#lec-insert-input').count() else '#lec-insert input', '새발표.md')
        page.wait_for_timeout(200)
        page.locator('#lec-insert-list li', has_text='새 발표 문서').click()
        page.wait_for_selector('#lec-view.lec-deck', timeout=8000)
        made = (proj / '새발표.md').read_text(encoding='utf-8')
        check('머리 설정과 표지로 만든다', made.startswith('---\nmarp: true\n') and '# 새발표' in made, made[:80])
        check('슬라이드로 열린다', page.locator('#lec-view .lec-slide').count() == 1)
        page.wait_for_timeout(600)
        row = page.locator('#lec-tree .row.file[data-doc="보통.md"]')
        row.click(button='right')
        page.wait_for_timeout(200)
        check('문서 메뉴의 발표로 바꾸기 요청', '발표로 바꾸기 요청' in page.locator('#lec-menu').inner_text())
        page.keyboard.press('Escape')
        page.locator('#lec-tree .row.file[data-doc="발표.md"]').click(button='right')
        page.wait_for_timeout(200)
        check('발표 문서에는 없다', '발표로 바꾸기 요청' not in page.locator('#lec-menu').inner_text())
        page.keyboard.press('Escape')
        check('화면 오류 없음', not extra, extra[:3])
        b.close()


try:
    run()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
