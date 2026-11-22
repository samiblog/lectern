"""0.100.0 사람 시나리오 — 연구원이 Claude 가 쓴 보고서 초안을 Lectern 에서 다듬는 하루 (D189·D190).

1. 초안을 열고 문서 점검을 따라 고친다 — 고치기를 차례로, 한 번 되돌리고, 고칠 수 없는 것은 목록을 복사해 Claude 에 맡긴다 (바깥에서 파일이 바뀐다)
2. 긴 문단을 칸에서 고친다 — 화살표로 화면 줄을 오르내리며 글을 넣고, 둘째 화면 줄 맨 앞의 ↑, 빠르게 누른 ↑
3. 목록을 다듬는다 — 하위 항목이 있는 항목·둘째 문단이 있는 항목 지우기, 새 하위 항목의 Tab, 되돌리기
4. 여러 문단을 끌어 지우고 옮긴다 — 문단 셋, 코드 블록을 지나는 끌기, Alt+↓
5. 머리 설정을 본다 — 접혀 있고, 연 문서는 다른 문서에 다녀와도 연 채, 문서 정보 고치기
6. Claude 가 바깥에서 고치는 동안 — 칸을 연 채 파일이 바뀌고, 점검이 따라 바뀐다
7. 여러 문서를 오간다 — 슬라이드·업무 카드·깨끗한 문서, 모두 펼치기에서 고른 칸의 점검
8. 큰 보고서 — 점검할 곳이 많으면 '그 밖에 N곳', 복사한 목록에는 모두"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

F = '```'
REPORT = f"""---
title: AI 확산에 따른 세계 경제 영향
status: 초안
---

# AI 확산에 따른 세계 경제 영향

## 1. 요약

AI 확산은 생산성을 높이지만 고용의 재배치를 부른다.
2. 서비스업의 변화가 가장 크다.

## 2. 생산성

- 제조업
- 서비스업
* 공공 부문

표 1. 산업별 생산성 증가율

| 산업 | 증가율 |
|---|---|
| 제조업 | 1.2 |
| 서비스업 |

자료: OECD

표 3. 나라별 도입률

| 나라 | 도입률 |
|---|---|
| 한국 | 34 |

자료: IMF

| 구분 | 값 |
|---|---|
| 기타 | 1 |

> [!NOTES]
> 수치는 잠정치다.

## 3. 고용

고용은 직무 단위로 재편된다.

## 4. 부록

{F}python
print('계산')
"""
LONG = '인공지능의 확산은 노동 시장과 생산성에 동시에 영향을 미치며, 특히 서비스 산업에서는 업무 방식이 크게 바뀌고 있다. ' * 4
LONG = LONG.rstrip()
DRAFT = f'# 본문\n\n앞 문단이다.\n\n{LONG}\n\n뒤 문단이다.\n'
LIST = ('# 목차 짜기\n\n- 수요 측면\n  - 소비\n  - 투자\n- 공급 측면\n  - 노동\n    - 고숙련\n    - 저숙련\n  - 자본\n- 정책\n\n  재정·통화 정책의 대응을 본다\n- 전망\n')
PARAS = (f'# 정리\n\n가 문단은 그대로 둔다.\n\n나 문단은 지울 것이다.\n\n다 문단도 지울 것이다.\n\n라 문단까지 지운다.\n\n마 문단은 남는다.\n\n'
         f'{F}\n코드 한 줄\n{F}\n\n바 문단은 코드와 함께 지운다.\n\n사 문단은 마지막이다.\n')
FRONT = '---\ntitle: 머리 설정 시험\nowner: 연구원 A\n---\n\n# 머리 문서\n\n본문 글이다.\n'
CLEAN = '# 깨끗한 문서\n\n## 하나\n\n글이다.\n\n## 둘\n\n- 가\n- 나\n'
DECK = '---\nmarp: true\n---\n\n# 표지\n\n## 장\n\n## 장\n'
WORK = '---\nstatus: 진행\n---\n\n# 업무\n\n## 할 일\n\n## 일정\n'
BIG = '# 큰 보고서\n\n' + ''.join(f'## 절 {i}\n\n> [!NOTES]\n> 메모 {i}\n\n본문 {i} 이다.\n\n' for i in range(1, 61))
QUOTES = ('# 인용 다듬기\n\n> 인터뷰 첫 줄\n>\n> 인터뷰 끝 줄\n\n> [!TIP]\n> 팁의 첫 줄\n> 팁의 둘째 줄\n\n끝 문단\n')
NUMBERS = ('# 순서\n\n1. 자료 모으기\n   - 통계청\n   - 한국은행\n2. 정리하기\n3. 쓰기\n\n사이 설명 문단\n\n1. 검토\n2. 보내기\n')
SLIDES = ('---\nmarp: true\n---\n\n# 표지\n\n---\n\n<!-- layout: two -->\n\n## 두 칸\n\n::: a card\n- 가 항목\n- 나 항목\n  - 나의 하위\n- 다 항목\n:::\n\n::: b card\n오른쪽 글\n:::\n')

base = Path(tempfile.mkdtemp(prefix='lec-scen100-'))
proj = base / '연구'
proj.mkdir(parents=True)
files = {'보고서.md': REPORT, '초안.md': DRAFT, '목차.md': LIST, '정리.md': PARAS, '머리.md': FRONT, '깨끗.md': CLEAN, '발표.md': DECK, '큰.md': BIG,
         '인용.md': QUOTES, '순서.md': NUMBERS, '칸.md': SLIDES}
for name, text in files.items():
    (proj / name).write_text(text, encoding='utf-8')
(proj / '과제').mkdir()
(proj / '과제' / 'WORK.md').write_text(WORK, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'toc_visible': True}), encoding='utf-8')
server, url, port = serve(proj, config)


def text_of(name):
    for _ in range(40):
        try:
            return (proj / name).read_text(encoding='utf-8')
        except OSError:   # 앱이 파일을 바꿔 끼우는 순간
            time.sleep(0.02)
    return (proj / name).read_text(encoding='utf-8')


CARET = """() => { const sp = document.activeElement; if (!sp?.classList?.contains('lec-line-edit')) return null;
  const sel = getSelection(); const pre = document.createRange(); pre.selectNodeContents(sp); pre.setEnd(sel.focusNode, sel.focusOffset);
  const node = sp.firstChild; const text = sp.textContent; const starts = [0]; let prev = null;
  for (let i = 0; node && i < text.length; i++) { const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + 1);
    const b = [...r.getClientRects()].find((x) => x.width); if (!b) continue; if (prev != null && b.top - prev > b.height / 2) starts.push(i); prev = b.top; }
  return { text: text.slice(0, 12), offset: pre.toString().length, starts, len: text.length }; }"""
line_of = lambda c: max(i for i, s in enumerate(c['starts']) if s <= c['offset'])   # noqa: E731

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1300, 'height': 900}, locale='ko-KR', permissions=['clipboard-read', 'clipboard-write'])
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('dialog', lambda d: d.accept())
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        label = lambda: page.evaluate("(() => { const b = document.querySelector('#lec-st-lint'); return b.hidden ? null : b.textContent.trim(); })()")   # noqa: E731
        editing = lambda: page.evaluate("document.activeElement?.classList?.contains('lec-line-edit') ? document.activeElement.textContent : null")   # noqa: E731

        def open_doc(name, title):
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click()
            page.wait_for_selector(f'#lec-view h1:has-text("{title}")')
            page.wait_for_timeout(500)

        def open_list():
            page.locator('#lec-st-lint').click()
            page.wait_for_selector('#lec-menu:not([hidden]) .menu-head', timeout=3000)

        def fix(row_text):
            open_list()
            page.locator('#lec-menu .menu-row', has_text=row_text).locator('.menu-side').click()

        # ---- 1 ----------------------------------------------------------------------------------
        print('[1. 초안을 열고 문서 점검을 따라 고친다]')
        open_doc('보고서.md', 'AI 확산에 따른 세계 경제 영향')
        expect(page, "초안에 '점검 8곳' — 깨진 틀 다섯, 보고서의 틀 셋", lambda: label() == '점검 8곳', label)
        check('머리 설정은 접혀 있다', page.evaluate("document.querySelector('#lec-view details.front-matter')?.open") is False)
        open_list()
        heads = page.evaluate("[...document.querySelectorAll('#lec-menu .menu-head')].map((e) => e.textContent.trim())")
        check('목록의 묶음 — 깨진 틀·보고서의 틀', heads == ['깨진 틀', '보고서의 틀'], heads)
        page.keyboard.press('Escape')
        fix('강조글 종류')
        expect(page, '고치기: [!NOTES] → [!NOTE]', lambda: '> [!NOTE]\n> 수치는' in text_of('보고서.md'))
        expect(page, "— '점검 7곳'", lambda: label() == '점검 7곳', label)
        page.locator('#lec-view h2', has_text='고용').click()
        page.keyboard.press('Control+z')
        expect(page, '— 마음이 바뀌어 Ctrl+Z: 원래대로', lambda: '> [!NOTES]' in text_of('보고서.md') and label() == '점검 8곳', label)
        fix('강조글 종류')
        expect(page, '— 다시 고친다', lambda: label() == '점검 7곳', label)
        fix('글머리표가')
        expect(page, '글머리표를 맞춘다 — 목록 하나', lambda: '- 서비스업\n- 공공 부문' in text_of('보고서.md') and label() == '점검 6곳', label)
        fix('번호가 2.')
        expect(page, '문단에 붙은 번호를 띄운다', lambda: '부른다.\n\n2. 서비스업' in text_of('보고서.md') and label() == '점검 5곳', label)
        fix('캡션이 없습니다')
        expect(page, '빈 캡션을 넣으면 번호가 차례대로 — 건너뛴 표 3 도 표 2 로 (두 곳이 함께 풀린다)',
               lambda: '표 2. 나라별 도입률' in text_of('보고서.md') and '표 3.\n\n| 구분 | 값 |' in text_of('보고서.md') and label() == '점검 3곳', label)
        fix("'자료:' 줄이 없습니다")
        expect(page, "빈 '자료:' 줄", lambda: '| 기타 | 1 |\n\n자료: \n' in text_of('보고서.md') and label() == '점검 2곳', label)
        fix('닫지 않은 코드 블록')
        expect(page, '부록의 코드 블록을 닫는다', lambda: text_of('보고서.md').endswith("print('계산')\n```\n") and label() == '점검 1곳', label)
        warned = page.evaluate("[...document.querySelectorAll('#lec-toc .toc-list li.warn')].map((li) => li.textContent.trim())")
        check('목차에는 남은 한 곳(칸 수)이 든 절만 ●', warned == ['2. 생산성'], warned)
        open_list()
        rows = page.evaluate("[...document.querySelectorAll('#lec-menu button[data-i]')].map((e) => e.textContent.trim())")
        check('남은 것은 고치기가 없는 칸 수 — 그 줄로 가기만', page.locator('#lec-menu .menu-side').count() == 0 and any('칸이 1개' in r for r in rows), rows)
        page.locator('#lec-menu button[data-i]', has_text='목록 복사').click()
        clip = until(page, lambda: (lambda c: c if '문서 점검 결과' in c else '')(page.evaluate('navigator.clipboard.readText()')), 3000)
        check('목록 복사 — Claude 에 줄 요청 글', clip.startswith('@보고서.md 문서 점검 결과입니다. 고쳐 주세요:') and '행 이 행은 칸이 1개' in clip, clip)
        (proj / '보고서.md').write_text(text_of('보고서.md').replace('| 서비스업 |\n', '| 서비스업 | 0.8 |\n'), encoding='utf-8')
        expect(page, 'Claude 가 바깥에서 고치면 점검이 사라진다', lambda: label() is None, label, ms=8000)
        check('— 목차의 ● 도', page.locator('#lec-toc .toc-list li.warn').count() == 0)

        # ---- 2 ----------------------------------------------------------------------------------
        print('[2. 긴 문단을 칸에서 고친다]')
        open_doc('초안.md', '본문')
        page.locator('#lec-view p', has_text='인공지능').click(position={'x': 30, 'y': 8})
        page.keyboard.press('Enter')
        until(page, lambda: editing() is not None, 4000)
        c = page.evaluate(CARET)
        n = len(c['starts'])
        check('긴 문단이 화면에서 다섯 줄 넘게 꺾인다 (시험의 전제)', n >= 5, c)
        page.keyboard.press('ArrowUp')
        page.keyboard.press('ArrowUp')
        page.keyboard.press('Home')
        page.wait_for_timeout(150)
        at1 = page.evaluate(CARET)['offset']
        page.keyboard.type('[가]')
        page.keyboard.press('ArrowUp')
        page.wait_for_timeout(200)
        c = page.evaluate(CARET)
        check('넣은 뒤 ↑ — 칸 안에서 윗줄로', c is not None and c['text'].startswith('인공지능') and line_of(c) == n - 4, c)
        page.keyboard.press('Home')
        page.keyboard.press('ArrowUp')   # 화면 줄 맨 앞의 ↑ — 칸을 떠나지 않는다 (D189)
        page.wait_for_timeout(200)
        c = page.evaluate(CARET)
        check('화면 줄 맨 앞의 ↑ 도 칸 안에서', c is not None and c['text'].startswith('인공지능') and line_of(c) == n - 5, c)
        page.keyboard.press('Enter')   # 저장하고 다음 줄로
        expect(page, '저장 — 넣은 글이 그 화면 줄의 맨 앞에', lambda: f'{LONG[:at1]}[가]{LONG[at1:]}' in text_of('초안.md'), lambda: text_of('초안.md')[:200])
        page.locator('#lec-view p', has_text='뒤 문단').click()
        page.keyboard.press('Enter')
        until(page, lambda: (editing() or '').startswith('뒤 문단'), 4000)
        for _ in range(3):
            page.keyboard.press('ArrowUp')   # 빠르게 — 넘어가는 사이에 누른 것도 칸 안부터
        until(page, lambda: (editing() or '').startswith('인공지능'), 4000)
        page.wait_for_timeout(600)
        c = page.evaluate(CARET)
        n2 = len(c['starts']) if c else 0
        check('뒤 문단에서 ↑ 셋을 빠르게 — 긴 문단의 끝에서 둘째 위 화면 줄 (건너뛰지 않음)', c is not None and line_of(c) == n2 - 3, c)
        page.keyboard.press('End')
        page.keyboard.type('[나]')
        page.keyboard.press('Enter')
        expect(page, '— 그 줄 끝에 넣은 글이 저장', lambda: '[나]' in text_of('초안.md') and text_of('초안.md').count('인공지능의 확산은') == 4, lambda: text_of('초안.md')[:300])
        check('— 앞 문단·뒤 문단은 그대로', '\n\n앞 문단이다.\n\n' in text_of('초안.md') and '\n\n뒤 문단이다.\n' in text_of('초안.md'))

        # ---- 3 ----------------------------------------------------------------------------------
        print('[3. 목록을 다듬는다]')
        open_doc('목차.md', '목차 짜기')

        def delete_line(text):
            page.locator('#lec-view li', has_text=text).first.click(position={'x': 30, 'y': 8})
            page.keyboard.press('Delete')
            page.keyboard.press('Delete')

        delete_line('공급 측면')
        expect(page, "'공급 측면'을 지우면 하위 항목은 레벨 그대로 앞 항목 아래로", lambda: text_of('목차.md').startswith('# 목차 짜기\n\n- 수요 측면\n  - 소비\n  - 투자\n  - 노동\n    - 고숙련\n    - 저숙련\n  - 자본\n- 정책'), lambda: text_of('목차.md'))
        expect(page, '— 화면에서도 노동·자본이 둘째 레벨', lambda: page.locator('#lec-view li li', has_text='노동').count() >= 1 and page.locator('#lec-view > ul > li', has_text='노동').count() == 1)
        page.keyboard.press('Control+z')
        expect(page, '— Ctrl+Z 로 되돌림', lambda: '- 공급 측면\n  - 노동' in text_of('목차.md'))
        page.locator('#lec-view li li', has_text='투자').click(position={'x': 30, 'y': 8})
        page.keyboard.press('Shift+Enter')
        until(page, lambda: page.locator('#lec-view .lec-new-line .lec-line-edit').count() == 1, 4000)
        page.keyboard.press('Tab')
        page.wait_for_timeout(200)
        depth = page.evaluate("(() => { const li = document.querySelector('#lec-view .lec-new-line'); let d = 0; for (let e = li.parentElement; e.id !== 'lec-view'; e = e.parentElement) if (/^(UL|OL)$/.test(e.tagName)) d += 1; return [d, getComputedStyle(li).listStyleType]; })()")
        check('투자 아래 새 줄에서 Tab — 셋째 레벨의 글머리표가 바로', depth == [3, 'square'], depth)
        page.keyboard.type('설비 투자')
        page.keyboard.press('Enter')
        expect(page, '— 써서 저장하면 투자의 하위 항목', lambda: '  - 투자\n    - 설비 투자\n- 공급 측면' in text_of('목차.md'), lambda: text_of('목차.md'))
        delete_line('정책')
        expect(page, "둘째 문단이 있는 '정책'을 지우면 그 문단이 항목이 된다 — 전망은 목록에 남는다", lambda: '- 재정·통화 정책의 대응을 본다\n- 전망' in text_of('목차.md'), lambda: text_of('목차.md'))

        # ---- 4 ----------------------------------------------------------------------------------
        print('[4. 여러 문단을 끌어 지우고 옮긴다]')
        open_doc('정리.md', '정리')

        def drag(a_text, z_text, dx=40):
            a = page.locator('#lec-view p', has_text=a_text).bounding_box()
            z = page.locator('#lec-view p', has_text=z_text).bounding_box()
            page.mouse.move(a['x'] + 60, a['y'] + a['height'] / 2)
            page.mouse.down()
            page.mouse.move(z['x'] + dx, z['y'] + z['height'] / 2, steps=10)
            page.mouse.up()
            page.wait_for_timeout(200)

        drag('나 문단', '라 문단')
        page.keyboard.press('Delete')
        expect(page, '나·다·라 문단의 가운데부터 끌어 Delete 한 번 — 세 문단이 지워진다', lambda: '가 문단은 그대로 둔다.\n\n마 문단은 남는다.' in text_of('정리.md'), lambda: text_of('정리.md'))
        page.keyboard.press('Control+z')
        expect(page, '— Ctrl+Z', lambda: '라 문단까지 지운다' in text_of('정리.md'))
        drag('가 문단', '나 문단')
        page.keyboard.press('Alt+ArrowDown')
        expect(page, '가·나 문단을 끌어 Alt+↓ — 다 문단 아래로', lambda: '다 문단도 지울 것이다.\n\n가 문단은 그대로 둔다.\n\n나 문단은 지울 것이다.' in text_of('정리.md'), lambda: text_of('정리.md'))
        page.keyboard.press('Control+z')
        expect(page, '— Ctrl+Z', lambda: '# 정리\n\n가 문단은 그대로 둔다.\n\n나 문단은' in text_of('정리.md'))
        drag('마 문단', '바 문단')
        page.keyboard.press('Delete')
        expect(page, '문단에서 코드 블록을 지나 끌어 지우면 코드 블록째 (깨진다고 막지 않는다)', lambda: '라 문단까지 지운다.\n\n사 문단은 마지막이다.' in text_of('정리.md'), lambda: text_of('정리.md'))

        # ---- 5 ----------------------------------------------------------------------------------
        print('[5. 머리 설정을 본다]')
        open_doc('머리.md', '머리 문서')
        fm = "document.querySelector('#lec-view details.front-matter')?.open"
        check('머리 설정은 접혀 있다', page.evaluate(fm) is False)
        page.locator('#lec-view .front-matter summary').click()
        expect(page, '누르면 편다', fm)
        open_doc('깨끗.md', '깨끗한 문서')
        open_doc('머리.md', '머리 문서')
        expect(page, '다른 문서에 다녀와도 연 채', fm)
        page.locator('#lec-view .front-matter').click(button='right')
        page.wait_for_selector('#lec-menu button', timeout=3000)
        page.locator('#lec-menu button', has_text='문서 정보 고치기').click()
        page.wait_for_timeout(600)
        page.keyboard.press('Control+a')
        page.keyboard.type('바꾼 제목')
        page.keyboard.press('Enter')
        page.wait_for_timeout(300)
        page.keyboard.press('Escape')
        expect(page, '문서 정보 고치기로 값을 바꾼다', lambda: 'title: 바꾼 제목' in text_of('머리.md'), lambda: text_of('머리.md'))
        expect(page, '— 다시 그려도 연 채', fm)
        page.locator('#lec-view .front-matter summary').click()
        open_doc('깨끗.md', '깨끗한 문서')
        open_doc('머리.md', '머리 문서')
        expect(page, '접어 두면 다녀와도 접힌 채', lambda: page.evaluate(fm) is False)

        # ---- 6 ----------------------------------------------------------------------------------
        print('[6. Claude 가 바깥에서 고치는 동안]')
        open_doc('깨끗.md', '깨끗한 문서')
        check('깨끗한 문서는 점검이 없다', label() is None, label())
        page.locator('#lec-view p', has_text='글이다').click()
        page.keyboard.press('Enter')
        until(page, lambda: editing() is not None, 4000)
        page.keyboard.press('End')
        page.keyboard.type(' 사람이 쓰는 중')
        (proj / '깨끗.md').write_text(CLEAN + '\n> [!WARN]\n> Claude 가 더한 메모\n', encoding='utf-8')
        page.wait_for_timeout(1500)
        page.keyboard.press('Enter')
        expect(page, '칸을 연 채 바깥에서 파일이 바뀌어도 사람이 쓴 글과 Claude 의 글이 함께 남는다', lambda: '글이다. 사람이 쓰는 중' in text_of('깨끗.md') and '[!WARN]' in text_of('깨끗.md'), lambda: text_of('깨끗.md'))
        expect(page, "— 점검이 따라와 '점검 1곳' (모르는 강조글 종류)", lambda: label() == '점검 1곳', label, ms=8000)
        (proj / '깨끗.md').write_text(text_of('깨끗.md').replace('[!WARN]', '[!WARNING]'), encoding='utf-8')
        expect(page, 'Claude 가 고치면 사라진다', lambda: label() is None, label, ms=8000)

        # ---- 7 ----------------------------------------------------------------------------------
        print('[7. 여러 문서를 오간다]')
        (proj / '보고서.md').write_text(REPORT, encoding='utf-8')
        open_doc('보고서.md', 'AI 확산에 따른 세계 경제 영향')
        expect(page, '보고서 — 점검 8곳', lambda: label() == '점검 8곳', label)
        open_doc('발표.md', '표지')
        check('Lectern 슬라이드 — 문서 점검 없음', label() is None, label())
        page.locator('#lec-tree .row.dir', has_text='과제').first.click()
        page.locator('#lec-tree .row.file[data-doc="과제/WORK.md"]').click()
        page.wait_for_selector('#lec-view h1:has-text("업무")')
        page.wait_for_timeout(500)
        check('업무 카드의 빈 절 — 점검 없음', label() is None, label())
        open_doc('보고서.md', 'AI 확산에 따른 세계 경제 영향')
        expect(page, '보고서로 돌아오면 다시 점검 8곳', lambda: label() == '점검 8곳', label)
        open_doc('깨끗.md', '깨끗한 문서')
        page.evaluate("() => import('/static/js/spread.js').then((m) => m.toggleSpread())")
        page.wait_for_timeout(1000)
        tiles = page.locator('.lec-pane')
        picked = []
        for i in range(tiles.count()):
            t = tiles.nth(i)
            name = t.evaluate("(el) => el.querySelector('.md-body')?.dataset.docPath || ''")
            if name not in ('보고서.md', '깨끗.md'):
                continue
            t.locator('.md-body h1').click()
            page.wait_for_timeout(600)
            picked.append((name, label()))
        page.evaluate("() => import('/static/js/spread.js').then((m) => m.toggleSpread())")
        page.wait_for_timeout(500)
        check('모두 펼치기에서 고른 칸의 점검이 상태줄에', sorted(picked) == [('깨끗.md', None), ('보고서.md', '점검 8곳')], picked)

        # ---- 8 ----------------------------------------------------------------------------------
        print('[8. 큰 보고서]')
        open_doc('큰.md', '큰 보고서')
        expect(page, '강조글 종류 오타 60곳 — 점검 60곳', lambda: label() == '점검 60곳', label)
        open_list()
        rows = page.evaluate("[...document.querySelectorAll('#lec-menu button[data-i]')].length")
        more = page.evaluate("[...document.querySelectorAll('#lec-menu .menu-head')].map((e) => e.textContent.trim())")
        check("목록은 40곳까지 보이고 '그 밖에 20곳'", rows == 40 + 2 and any('그 밖에 20곳' in m for m in more), (rows, more))
        page.locator('#lec-menu button[data-i]', has_text='목록 복사').click()
        clip = until(page, lambda: (lambda c: c if '큰.md' in c else '')(page.evaluate('navigator.clipboard.readText()')), 3000)
        check('— 복사한 목록에는 60곳 모두', clip.count('강조글 종류') == 60, clip.count('강조글 종류'))
        page.keyboard.press('Escape')

        # ---- 9 ----------------------------------------------------------------------------------
        print('[9. 강조글·인용을 다듬는다]')
        open_doc('인용.md', '인용 다듬기')

        def delete_p(text):
            page.locator('#lec-view p', has_text=text).first.click(position={'x': 30, 'y': 8})
            page.keyboard.press('Delete')
            page.keyboard.press('Delete')

        delete_p('인터뷰 끝 줄')
        expect(page, '인용의 끝 줄을 지워도 아래 강조글은 따로 — 위 인용에 붙지 않는다',
               lambda: '인터뷰 끝 줄' not in text_of('인용.md') and page.locator('#lec-view p', has_text='인터뷰 끝 줄').count() == 0
               and page.locator('#lec-view blockquote.alert', has_text='팁의 첫 줄').count() == 1 and page.locator('#lec-view blockquote:not(.alert)', has_text='인터뷰 첫 줄').count() == 1,
               lambda: text_of('인용.md'))
        delete_p('팁의 첫 줄')
        expect(page, '강조글의 첫 줄을 지워도 강조글 그대로 (머리 줄이 남는다)',
               lambda: '> [!TIP]\n> 팁의 둘째 줄' in text_of('인용.md') and page.locator('#lec-view blockquote.alert', has_text='팁의 둘째 줄').count() == 1, lambda: text_of('인용.md'))

        # ---- 10 ---------------------------------------------------------------------------------
        print('[10. 번호 목록을 정리한다]')
        open_doc('순서.md', '순서')
        page.locator('#lec-view li', has_text='자료 모으기').first.click(position={'x': 30, 'y': 8})
        page.keyboard.press('Delete')
        page.keyboard.press('Delete')
        expect(page, "첫 항목 '자료 모으기'를 지우면 하위 항목이 올라오고 남은 번호는 1 부터 — 목록이 문단에 붙지 않는다",
               lambda: text_of('순서.md').startswith('# 순서\n\n- 통계청\n- 한국은행\n1. 정리하기\n2. 쓰기\n'), lambda: text_of('순서.md'))
        expect(page, '— 화면에서도 번호 목록 1·2', lambda: page.evaluate("[...document.querySelectorAll('#lec-view ol')].map((o) => o.start)")[:1] == [1])
        delete_p('사이 설명 문단')
        expect(page, '두 번호 목록 사이의 문단을 지우면 하나의 붙은 목록으로, 번호는 이어서',
               lambda: '1. 정리하기\n2. 쓰기\n3. 검토\n4. 보내기\n' in text_of('순서.md'), lambda: text_of('순서.md'))
        expect(page, '— 화면도 한 목록 (띄운 목록이 아님)', lambda: page.evaluate("(() => { const o = [...document.querySelectorAll('#lec-view ol')].find((x) => x.textContent.includes('보내기')); return !!o && o.children.length === 4 && !o.querySelector('li > p'); })()"))
        check('— 이 문서에는 점검할 곳이 없다', label() is None, label())

        # ---- 11 ---------------------------------------------------------------------------------
        print('[11. Lectern 슬라이드의 칸 안 목록]')
        open_doc('칸.md', '표지')
        page.locator('#lec-view .lec-cell[data-cell=a] li', has_text='나 항목').first.click(position={'x': 20, 'y': 8})
        page.keyboard.press('Delete')
        page.keyboard.press('Delete')
        expect(page, "칸 안의 '나 항목'을 지우면 하위 항목은 앞 항목 아래로 — 칸 표시(:::)는 그대로",
               lambda: '::: a card\n- 가 항목\n  - 나의 하위\n- 다 항목\n:::' in text_of('칸.md'), lambda: text_of('칸.md'))
        check('— 슬라이드는 문서 점검을 하지 않는다', label() is None, label())

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
