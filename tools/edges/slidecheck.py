"""슬라이드 점검 (D96): 사람이 손으로 쓸 때 나는 실수가 말없이 지나가지 않는지, 어두운 장의 글이 모든 스타일에서 보이는지, 문서의 태그가 틀을 벗어나지 않는지"""
import json
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-slidecheck-'))
proj = base / 'proj'
(proj / 'images').mkdir(parents=True)
(proj / 'images' / '있는 그림 (1).svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100"><rect width="300" height="100" fill="#ccd"/></svg>', encoding='utf-8')
B = '본문글'
FENCE = '```'
HEAD = '---\nmarp: true\n---\n\n## 앞장\n\n앞장글\n\n---\n\n'
TAIL = '\n---\n\n## 뒷장\n\n뒷장글\n'
# 이름: (원문, 점검에 나와야 할 글)
MISTAKES = {
    '붙여쓴칸': (f'## 제목\n\n:::a\n{B}\n:::\n', '칸 표시로 읽지 못했습니다'),
    '전각콜론': (f'## 제목\n\n：：： a\n{B}\n：：：\n', '칸 표시로 읽지 못했습니다'),
    '콜론넷': (f'## 제목\n\n:::: a\n{B}\n::::\n', '칸 표시로 읽지 못했습니다'),
    '닫는줄만': (f'## 제목\n\n{B}\n:::\n', '짝이 맞지 않는 :::'),
    '같은이름칸': (f'<!-- layout: two -->\n\n## 제목\n\n::: a\n{B}\n:::\n\n::: a\n둘째\n:::\n', '두 번 나옵니다'),
    '지시어오타': (f'<!-- layot: two -->\n\n## 제목\n\n::: a\n{B}\n:::\n', 'layout 인가요'),
    '콜론없음': (f'<!-- layout two -->\n\n## 제목\n\n::: a\n{B}\n:::\n', '콜론이 없어'),
    '주석안닫음': (f'<!-- layout: two\n\n## 제목\n\n{B}\n', '주석이 닫히지 않아'),
    '스타일안닫음': (f'<style scoped>\nsection {{ color: red; }}\n\n## 제목\n\n{B}\n', '<style> 이 닫히지 않아'),
    '코드안닫음': (f'## 제목\n\n{FENCE}py\nprint(1)\n\n{B}\n', '코드 블록이 닫히지 않아'),
    '글상자안닫음': (f'## 제목\n\n<textarea>\n\n{B}\n', '<textarea> 이 닫히지 않아'),
    '구분선앞빈줄없음': (f'## 제목\n\n{B}\n---\n\n둘째\n', '위에 빈 줄을'),
    '전각구분선': (f'## 제목\n\n{B}\n\n－－－\n\n둘째\n', '구분 줄로 읽지 못했습니다'),
    '글자낱말오타': (f'<!-- text: 표표 14 -->\n\n## 제목\n\n{B}\n', "글자 크기 '표표 14'"),
    '낱말오타': (f'## 제목\n\n::: a crad\n{B}\n:::\n', "낱말 'crad'"),
    '크기꼬리': (f'## 제목\n\n::: a 16pt\n{B}\n:::\n', "'16pt'"),
    '자리모자람': (f'## 제목\n\n::: a at 10 20 300\n{B}\n:::\n', "'at 10 20 300'"),
    '격자길이다름': (f'<!-- grid: t t / a b / c -->\n\n## 제목\n\n::: a\n{B}\n:::\n', '줄마다 칸 수'),
    '격자이상한글자': (f'<!-- grid: t t / a <b> -->\n\n## 제목\n\n::: a\n{B}\n:::\n', '격자를 읽지 못했습니다'),
    '열폭합이넘침': (f'<!-- grid: t t / a b -->\n<!-- cols: 900px 900px -->\n\n## 제목\n\n::: a\n{B}\n:::\n\n::: b\n글\n:::\n', '칸 b 이(가) 슬라이드 밖으로'),
    '자기로가는선': (f'<!-- links: a>a -->\n\n## 제목\n\n::: a card at 100 200 300 120\n{B}\n:::\n', '선의 양쪽이 같은 칸입니다'),
    '칸이많이넘침': ('## 제목\n\n' + ''.join(f'::: k{i} at {56 + i % 40 * 29} {110 + i // 40 * 22} 26 20\n{i % 10}\n:::\n\n' for i in range(100)), '이 장에'),
    '격자네모아님': (f'<!-- grid: t t / a b / b a -->\n\n## 제목\n\n::: a\n{B}\n:::\n\n::: b\n글\n:::\n', '네모가 아닙니다'),
    '열수다름': (f'<!-- grid: t t t / a b c -->\n<!-- cols: 1fr -->\n\n## 제목\n\n::: a\n{B}\n:::\n', '3개를 씁니다'),
    '열값글': (f'<!-- grid: t t / a b -->\n<!-- cols: 넓게 좁게 -->\n\n## 제목\n\n::: a\n{B}\n:::\n', "cols 값 '넓게 좁게'"),
    '없는그림': (f'## 제목\n\n![그림](images/없는.png)\n\n{B}\n', '그림을 찾을 수 없습니다'),
    '없는배경': (f'![bg](images/없는배경.png)\n\n## 제목\n\n{B}\n', '그림을 찾을 수 없습니다'),
    '긴코드': (f'## 제목\n\n{FENCE}sh\n{"curl --header value " * 12}\n{FENCE}\n\n{B}\n', '코드가 옆으로'),
    '별표남음': (f'## 제목\n\n값이 **8.0%**로 올랐다\n\n{B}\n', '굵게로 읽지 못한 별표'),
    '틀린차트': (f'<!-- layout: two -->\n\n## 제목\n\n::: a\n{FENCE}vega-lite\n{{"mark": "bar",\n{FENCE}\n:::\n\n::: b\n{B}\n:::\n', '그림을 그리지 못했습니다'),
    '틀린다이어그램': (f'## 제목\n\n{FENCE}mermaid\nflowchart TD\n  A --> \n  (((\n{FENCE}\n\n{B}\n', '그림을 그리지 못했습니다'),
    '없는자료': (f'## 제목\n\n{FENCE}vega-lite\n{{"data":{{"url":"없음.csv"}},"mark":"bar","encoding":{{"x":{{"field":"a"}}}}}}\n{FENCE}\n', '그림을 그리지 못했습니다'),
    '안보이는글': (f'<style scoped>\np {{ color: #123456; background: #123457; }}\n</style>\n\n## 제목\n\n{B}\n', '글자가 바탕과 비슷해'),
}
# 틀이 벗어나면 안 되는 것 — 앞뒤 장이 그대로이고 슬라이드 수가 맞아야 한다
TAGS = {
    '남은닫기': f'## 제목\n\n</div></div></section></div>\n\n{B}\n',
    '글속닫기': f'## 제목\n\n{B} </section></div> 이어진 글\n',
    '열린태그': f'## 제목\n\n<div><section><table><tr><td>\n\n{B}\n',
    '칸속닫기': f'## 제목\n\n::: a\n</div></section>\n{B}\n:::\n',
    '묶음': f'## 제목\n\n<div class="columns">\n<div>\n\n{B}\n\n</div>\n</div>\n',
}
# 틀리지 않은 것 — 점검이 말이 많으면 쓰지 않게 된다
QUIET = {
    '출처노트': f'## 제목\n\n{B}\n\n<!-- 출처: 통계청 -->\n<!-- note: 천천히 말한다 -->\n<!-- TODO: 수치 확인 -->\n',
    '코드속칸': f'## 제목\n\n{FENCE}md\n::: a\n:::a\n<!-- layot: two -->\n{FENCE}\n\n{B}\n',
    '글속콜론': f'## 제목\n\n{B} `:::` 와 a::b 는 글이다\n',
    '두배경이어쓰기': f'![bg](<images/있는 그림 (1).svg>)\n![bg](<images/있는 그림 (1).svg>)\n\n## 제목\n\n{B}\n',
    '가운데칸의긴그림': f'<!-- layout: two -->\n\n## 제목\n\n::: a card center\n{FENCE}mermaid\nsequenceDiagram\n' + ''.join(f'  A->>B: 단계 {i}\n  B-->>A: 응답 {i}\n' for i in range(1, 9)) + f'{FENCE}\n:::\n\n::: b\n{B}\n:::\n',
    '격자의빈자리': f'<!-- grid: t t t / a . b / . c . -->\n\n## 제목\n\n::: a\n{B}\n:::\n\n::: b\n글\n:::\n\n::: c\n글\n:::\n',
    '큰격자': '<!-- grid: ' + ' / '.join([' '.join(['t'] * 13)] + [' '.join(f'c{r}x{c}' for c in range(13)) for r in range(8)]) + ' -->\n<!-- cols: 120px repeat(12, 1fr) -->\n<!-- text: 본문 14 -->\n\n## 제목\n\n' + ''.join(f'::: c{r}x{c}\n{r}\n:::\n\n' for r in range(8) for c in range(13)),
    '칸색굵은글': f'<style scoped>\n.deep {{ background: #1f5a8c; color: #fff; }}\n</style>\n\n## 제목\n\n::: a deep\n**굵은 글** {B}\n:::\n',
    '사용자낱말': f'<style>\n.mine {{ color: rgb(1, 2, 3); }}\n</style>\n\n## 제목\n\n::: a mine\n{B}\n:::\n',
    '빈칸이름그림': f'## 제목\n\n![그림](<images/있는 그림 (1).svg>)\n\n{B}\n',
}
for name, (body, _) in MISTAKES.items():
    (proj / f'{name}.md').write_text(HEAD + body + TAIL, encoding='utf-8', newline='\n')
for name, body in TAGS.items():
    (proj / f'{name}.md').write_text(HEAD + body + TAIL, encoding='utf-8', newline='\n')
for name, body in QUIET.items():
    (proj / f'{name}.md').write_text(HEAD + body + TAIL, encoding='utf-8', newline='\n')
DARK = f"""---
marp: true
footer: 꼬리말
paginate: true
---

<!-- _class: invert -->
<!-- layout: quad -->

## 어두운 장

::: a card
### 카드 소제목

- 카드 글 **굵게** `코드`
:::

::: b accent
강조 칸의 글 [링크](a.md)
:::

::: c dark
어두운 칸의 글 **굵게**
:::

::: d kpi
**90%**
숫자 칸의 글
:::

---

<!-- _class: invert -->
<!-- layout: two -->

## 어두운 장의 표

::: a
| 항목 | 값 |
|---|---:|
| 첫째 | 1 |
| 둘째 | 2 |
| 셋째 | 3 |
:::

::: b
> 인용 글

> [!WARNING]
> 박스글

{FENCE}py
print(1)
{FENCE}
:::

---

<!-- _class: lead -->
<!-- layout: two -->

## 표지 장의 칸

::: a card
표지의 카드 글
:::

::: b dark
표지의 어두운 칸 글

| 항목 |
|---|
| 표 글 |
:::

---

<!-- _class: invert -->
<!-- layout: stack -->

## 어두운 장의 메모

::: a note
### 메모 소제목

메모 글 **굵게** [링크](a.md)
:::

::: b
{FENCE}py
def 함수(값):
    return "글자"  # 주석
{FENCE}
:::

---

<!-- layout: quad -->

## 밝은 장

::: a card
### 카드 소제목

- 카드 글 **굵게** `코드`
:::

::: b accent
강조 칸의 글 [링크](a.md)
:::

::: c dark
어두운 칸의 글 **굵게**
:::

::: d note
### 메모 소제목

메모 글
:::
"""
(proj / '어두운장.md').write_text(DARK, encoding='utf-8', newline='\n')
(proj / '꼬리표.md').write_text('---\nmarp: true\n---\n\n<!-- grid: t t / a b -->\n<!-- cols: 1fr 2fr -->\n<!-- rows: auto 1fr -->\n\n## 제목\n\n::: a\n글\n:::\n\n::: b\n글\n:::\n\n<!-- 노트 -->\n', encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
server, url, port = serve(proj, config)
extra = []
OPEN = "(path) => import('/static/js/store.js').then(({ emit }) => emit('open', { type: 'doc', path, force: true }))"
ISSUES = "[...document.querySelectorAll('#lec-view > .lec-slide-wrap')].flatMap((w) => JSON.parse(w.dataset.issues || '[]'))"


def run():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        page.on('pageerror', lambda e: extra.append(str(e)[:200]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row')

        def show(name):
            page.evaluate(OPEN, f'{name}.md')
            page.wait_for_function("(n) => document.querySelector('#lec-st-path')?.textContent.includes(n) && document.querySelector('#lec-view .lec-slide')", arg=f'{name}.md', timeout=8000)
            page.wait_for_timeout(350)

        print('[실수가 점검에 나온다]')
        for name, (_, want) in MISTAKES.items():
            show(name)
            got = page.evaluate(ISSUES)
            check(name, any(want in x['text'] for x in got), [x['text'] for x in got])
            check(f'{name}: 줄 번호가 있다', all(x['line'] > 0 for x in got), got)

        print('[문서의 태그가 틀을 벗어나지 않는다]')
        for name in TAGS:
            show(name)
            r = page.evaluate("""() => { const v = document.querySelector('#lec-view'); return {
              wraps: v.querySelectorAll(':scope > .lec-slide-wrap').length, slides: v.querySelectorAll(':scope > .lec-slide-wrap > .lec-slide-frame > .lec-slide').length,
              stray: [...v.children].filter((x) => !x.matches('.lec-slide-wrap, .lec-slide-notes, style, .lec-spot, .lec-now')).map((x) => x.tagName + '.' + x.className).slice(0, 4),
              text: v.textContent }; }""")
            check(f'{name}: 장이 그대로', r['wraps'] == 3 and r['slides'] == 3, r['wraps'])
            check(f'{name}: 틀 밖에 아무것도 없다', not r['stray'], r['stray'])
            check(f'{name}: 앞뒤 장의 글', '앞장글' in r['text'] and '뒷장글' in r['text'])
        show('두배경이어쓰기')
        check('이어 쓴 배경이 빈 문단을 남기지 않는다', page.locator('#lec-view .lec-slide').nth(1).locator(':scope > p').count() == 1, page.locator('#lec-view .lec-slide').nth(1).locator(':scope > p').count())
        show('격자의빈자리')
        place = page.evaluate("""() => { const s = document.querySelectorAll('#lec-view .lec-slide')[1]; return [...s.querySelectorAll('.lec-cell')].map((c) => [c.dataset.cell, c.offsetLeft, c.offsetTop]); }""")
        check('빈 자리가 있는 격자가 듣는다', place[0][1] < place[2][1] < place[1][1] and place[0][2] < place[2][2], place)
        show('큰격자')
        wide = page.evaluate("""() => { const s = document.querySelectorAll('#lec-view .lec-slide')[1]; const c = [...s.querySelectorAll('.lec-cell')]; return [s.classList.contains('lec-grid'), c.length, new Set(c.map((x) => x.offsetLeft)).size, new Set(c.map((x) => x.offsetTop)).size]; }""")
        check('13열 8줄 격자가 듣는다', wide == [True, 104, 13, 8], wide)
        show('칸색굵은글')
        check('칸의 글자색을 굵은 글이 따른다', page.locator('#lec-view .lec-cell.deep strong').evaluate('(e) => getComputedStyle(e).color') == 'rgb(255, 255, 255)')
        show('묶음')
        check('여러 블록에 걸친 묶음은 그대로다', page.locator('#lec-view .columns > div').count() == 1, page.locator('#lec-view .columns').count())

        print('[틀리지 않은 것은 조용하다]')
        for name in QUIET:
            show(name)
            got = page.evaluate(ISSUES)
            check(name, not got, [x['text'] for x in got])

        print('[나란한 꼬리표]')
        show('꼬리표')
        page.locator('#lec-st-structure').click()
        page.wait_for_timeout(400)
        tags = page.locator('#lec-view .lec-slide-tags .lec-tag')
        for i, want in enumerate(('grid', 'cols', 'rows', '노트')):
            tags.nth(i).dblclick()
            page.wait_for_selector('#lec-view .lec-line-edit', timeout=3000)
            got = page.locator('#lec-view .lec-line-edit').first.text_content()
            check(f'{want} 꼬리표를 누르면 그 줄이 열린다', want in got, got)
            page.keyboard.press('Escape')
            page.wait_for_timeout(200)
        page.locator('#lec-st-structure').click()
        page.wait_for_timeout(200)

        print('[키보드 메뉴]')
        show('꼬리표')
        page.locator('#lec-view .lec-cell p').last.click()
        page.wait_for_timeout(200)
        page.keyboard.press('Shift+F10')
        page.wait_for_timeout(250)
        check('Shift+F10 메뉴에 장 다루기가 있다', '배치 넣기' in page.locator('#lec-menu').inner_text(), page.locator('#lec-menu').inner_text()[:160])
        page.keyboard.press('Escape')
        page.wait_for_timeout(150)

        print('[어두운 장의 글이 모든 스타일에서 보인다]')
        themes = page.evaluate("[...document.querySelectorAll('#lec-theme option')].map((o) => o.value).filter((v) => v && !v.startsWith('user:'))")
        check('스타일 목록', len(themes) >= 20, len(themes))
        show('어두운장')
        bad = {}
        for theme in themes:
            page.evaluate("(v) => { const s = document.querySelector('#lec-theme'); s.value = v; s.dispatchEvent(new Event('change', { bubbles: true })); }", theme)
            page.wait_for_timeout(700)
            got = [x['text'] for x in page.evaluate(ISSUES) if '바탕과 비슷해' in x['text']]
            if got:
                bad[theme] = got
        check('어느 스타일에서도 글이 묻히지 않는다', not bad, json.dumps(bad, ensure_ascii=False)[:500])
        page.evaluate("(v) => { const s = document.querySelector('#lec-theme'); s.value = v; s.dispatchEvent(new Event('change', { bubbles: true })); }", 'deck')
        page.wait_for_timeout(700)
        left = page.evaluate("""() => { const s = document.querySelector('#lec-view .lec-slide'); const k = s.getBoundingClientRect().width / s.offsetWidth;
          const x = (el) => (el.getBoundingClientRect().left - s.getBoundingClientRect().left) / k;
          return [x(s.querySelector(':scope > h2')), x(s.querySelector(':scope > footer'))]; }""")
        check('꼬리말이 본문과 같은 왼쪽 줄에', abs(left[0] - left[1]) < 3, left)
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
