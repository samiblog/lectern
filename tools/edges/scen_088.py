"""시나리오 — 0.88.0 을 실제로 쓰는 흐름 (D155·D156·D157):
1 AI 초안을 보고서 모양으로 (문단 셋 → 번호 목록, 한 항목을 문단으로 빼기, 목록 → 표 → 목록, Ctrl+Z 로 처음까지)
2 회의 메모의 강조글 (안에서 목록으로, 안팎을 섞어 고르면 하지 않음, 강조글 풀기)
3 받아 적기 (번호를 이어 쓰기, 제목 위에 넣으면 목록을 잇기, 제목 아래는 문단 — 그동안 알림 없음, 지우기는 알림)
4 긴 문서의 화면 밖 되돌리기는 알림
5 단축키 표에서 찾아 바로 써 보기 (. → 목록 전체를 할 일로)
6 Lectern 슬라이드의 칸 안에서 바꾸기 (칸 표시는 그대로)"""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-scen088-'))
proj = base / 'proj'
proj.mkdir(parents=True)
DRAFT = ('# 3분기 구리 시장\n\n## 요약\n\n가격은 9,400달러까지 올랐다.\n\n수요는 중국 전력망이 이끌었다.\n\n재고는 2주치로 줄었다.\n\n'
         '## 가격\n\n- 구리: 9,400달러\n- 니켈: 16,500달러\n- 아연: 2,700달러\n\n## 다음 할 일\n\n조달 일정을 정한다.\n')
MEET = '# 회의\n\n> [!NOTE]\n> 결정: 9월 발주\n> 담당: 구매팀\n> 마감: 10월\n\n- 후속 하나\n- 후속 둘\n'
NOTE = '# 받아 적기\n\n## 할 일\n\n1. 첫째\n\n## 메모\n\n메모 문단.\n'
LONG = '# 긴 문서\n\n첫 문단.\n\n' + '\n\n'.join(f'문단 {i:03d} 이다.' for i in range(1, 161)) + '\n'
DECK = '---\nmarp: true\n---\n\n# 장 하나\n\n::: a card\n- 가\n- 나\n:::\n'
PRACTICE = (Path(__file__).resolve().parents[2] / 'samples' / 'guide' / '단축키-연습' / '연습-문서.md').read_text(encoding='utf-8')
docs = {'초안.md': DRAFT, '회의.md': MEET, '적기.md': NOTE, '긴.md': LONG, '발표.md': DECK, '연습-문서.md': PRACTICE}
for name, text in docs.items():
    (proj / name).write_text(text, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)


def read(name):
    for _ in range(40):
        try:
            return (proj / name).read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.05)
    return ''


try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1400, 'height': 900}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        # 화면 아래 알림을 모두 적어 둔다 — 글을 쓰는 동안 몇 번 떴는지
        page.evaluate("""() => { window.__toasts = []; const t = document.querySelector('#lec-toast');
          new MutationObserver(() => { if (!t.hidden && t.textContent) window.__toasts.push(t.textContent); }).observe(t, { childList: true, characterData: true, subtree: true, attributes: true }); }""")
        toasts = lambda: page.evaluate('() => window.__toasts.slice()')
        clear = lambda: page.evaluate('() => { window.__toasts = []; }')
        LIT = "() => import('/static/js/spotlight.js').then((m) => m.litSpan())"
        line_of = lambda name, text: read(name).split('\n').index(text) + 1
        option = lambda name: page.locator('#lec-put-list li[role=option]', has_text=name).first

        def open_doc(name, sel='#lec-view h1'):
            page.keyboard.press('Escape')
            page.keyboard.press('Escape')
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click()
            page.wait_for_function("(n) => document.querySelector('#lec-st-path')?.textContent.includes(n)", arg=name, timeout=8000)
            page.wait_for_selector(sel)
            page.wait_for_timeout(600)

        def go(n):
            page.locator('#lec-view h1').first.click()
            page.evaluate("(n) => import('/static/js/spotlight.js').then((m) => m.followLine(n))", n)
            page.wait_for_timeout(200)

        def pick(a, b):
            go(a)
            for _ in range(b - a):
                span = page.evaluate(LIT)
                if span and span[1] >= b:
                    break
                page.keyboard.press('Shift+ArrowDown')
            page.wait_for_timeout(150)

        def change(n, name):
            go(n)
            page.keyboard.press('.')
            page.wait_for_selector('#lec-put:not([hidden])', timeout=4000)
            option(name).click()

        def undo_to(name, want, label, times=8):
            page.keyboard.press('Escape')
            for _ in range(times):
                if read(name) == want:
                    break
                page.keyboard.press('Control+z')
                page.wait_for_timeout(700)
            check(label, read(name) == want, read(name)[:200])

        print('[1 AI 초안을 보고서 모양으로]')
        open_doc('초안.md')
        pick(line_of('초안.md', '가격은 9,400달러까지 올랐다.'), line_of('초안.md', '재고는 2주치로 줄었다.'))
        page.keyboard.press('n')
        expect(page, '문단 셋을 골라 N — 번호 목록 하나 (빈 줄 없이)', lambda: '## 요약\n\n1. 가격은 9,400달러까지 올랐다.\n2. 수요는 중국 전력망이 이끌었다.\n3. 재고는 2주치로 줄었다.\n\n## 가격' in read('초안.md'), lambda: read('초안.md')[:200])
        page.keyboard.press('Escape')
        clear()
        change(line_of('초안.md', '2. 수요는 중국 전력망이 이끌었다.'), '문단')
        expect(page, '가운데 항목을 바꾸기 창에서 문단으로 — 뒤 항목은 2 로', lambda: '1. 가격은 9,400달러까지 올랐다.\n\n수요는 중국 전력망이 이끌었다.\n\n2. 재고는 2주치로 줄었다.' in read('초안.md'), lambda: read('초안.md')[:220])
        expect(page, '— 알림은 고른 줄 밖의 번호 변경 하나', lambda: toasts() == ['뒤 항목 1개의 번호를 다시 매겼습니다'], toasts)
        change(line_of('초안.md', '- 구리: 9,400달러'), '목록을 표로')
        expect(page, '가격 목록을 표로 — 이름과 값으로 나뉜다', lambda: '| 항목 | 값 |\n| --- | --- |\n| 구리 | 9,400달러 |\n| 니켈 | 16,500달러 |\n| 아연 | 2,700달러 |' in read('초안.md'), lambda: read('초안.md')[200:420])
        change(line_of('초안.md', '| 니켈 | 16,500달러 |'), '표를 목록으로')
        expect(page, '표를 다시 목록으로 (캡션이 없으니 묻지 않는다)', lambda: '- 구리 — 9,400달러\n- 니켈 — 16,500달러\n- 아연 — 2,700달러' in read('초안.md'), lambda: read('초안.md')[200:420])
        undo_to('초안.md', DRAFT, 'Ctrl+Z 를 이어 누르면 처음 초안 그대로')
        check('화면 안의 되돌리기는 알리지 않는다', not [x for x in toasts() if '되돌렸습니다' in x], toasts())

        print('[2 회의 메모의 강조글]')
        open_doc('회의.md')
        pick(line_of('회의.md', '> 결정: 9월 발주'), line_of('회의.md', '> 마감: 10월'))
        page.keyboard.press('l')
        expect(page, '강조글 본문 셋을 골라 L — 강조글 안의 목록', lambda: '> [!NOTE]\n> - 결정: 9월 발주\n> - 담당: 구매팀\n> - 마감: 10월\n\n- 후속 하나' in read('회의.md'), lambda: read('회의.md'))
        page.keyboard.press('Escape')
        clear()
        after_l = read('회의.md')
        pick(line_of('회의.md', '> - 마감: 10월'), line_of('회의.md', '- 후속 하나'))
        page.keyboard.press('n')
        page.wait_for_timeout(500)
        check('강조글 안과 밖을 함께 골라 N — 하지 않고 까닭을 알림', read('회의.md') == after_l and any('나눠서 고르세요' in x for x in toasts()), (toasts(), read('회의.md')[-80:]))
        page.keyboard.press('Escape')
        change(line_of('회의.md', '> - 담당: 구매팀'), '강조글 풀기')
        expect(page, '바꾸기 창의 강조글 풀기 — 목록만 남는다', lambda: '[!NOTE]' not in read('회의.md') and '- 결정: 9월 발주\n- 담당: 구매팀\n- 마감: 10월' in read('회의.md'), lambda: read('회의.md'))
        undo_to('회의.md', MEET, 'Ctrl+Z 로 회의 메모 처음 그대로')

        print('[3 받아 적기 — 그동안 알림 없음]')
        open_doc('적기.md')
        clear()
        go(line_of('적기.md', '1. 첫째'))
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.press('End')
        page.keyboard.press('Control+Enter')
        page.wait_for_timeout(400)
        page.keyboard.type('둘째')
        page.keyboard.press('Shift+Enter')   # 저장하고 아래에 새 줄 (D158)
        until(page, lambda: '둘째' in read('적기.md'), 6000)
        page.wait_for_timeout(350)
        page.keyboard.type('셋째')
        page.keyboard.press('Enter')   # 저장하고 닫기 (D158)
        until(page, lambda: '셋째' in read('적기.md'), 6000)
        page.wait_for_timeout(400)
        check('번호를 이어 쓴다 — 2. 3.', '1. 첫째\n2. 둘째\n3. 셋째\n' in read('적기.md'), read('적기.md'))
        go(line_of('적기.md', '## 메모'))
        page.keyboard.press('Control+Shift+Enter')
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.type('넷째')
        page.keyboard.press('Enter')
        until(page, lambda: '넷째' in read('적기.md'), 6000)
        page.wait_for_timeout(350)
        page.keyboard.press('Escape')
        check('제목 위에 넣으면 위 목록을 잇는다 — 4.', '3. 셋째\n4. 넷째\n\n## 메모' in read('적기.md'), read('적기.md'))
        go(line_of('적기.md', '## 메모'))
        page.keyboard.press('Control+Enter')
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.type('메모 앞 문단')
        page.keyboard.press('Enter')
        until(page, lambda: '메모 앞 문단' in read('적기.md'), 6000)
        page.wait_for_timeout(350)
        page.keyboard.press('Escape')
        check('제목 아래는 문단', '## 메모\n\n메모 앞 문단\n\n메모 문단.' in read('적기.md'), read('적기.md'))
        check('여섯 줄을 쓰는 동안 알림 0번', toasts() == [], toasts())
        go(line_of('적기.md', '메모 문단.'))
        page.keyboard.press('Delete')
        page.wait_for_timeout(150)
        page.keyboard.press('Delete')
        expect(page, '지우기는 알린다 — 되돌리는 키와 함께', lambda: any('지웠습니다 — Ctrl+Z' in x for x in toasts()), toasts)

        print('[4 긴 문서의 화면 밖 되돌리기]')
        open_doc('긴.md')
        go(3)
        page.keyboard.press('2')
        page.wait_for_timeout(150)
        page.keyboard.press('2')
        expect(page, '첫 문단을 제목 2 로', lambda: '\n## 첫 문단.\n' in read('긴.md'))
        page.keyboard.press('Escape')
        go(line_of('긴.md', '문단 160 이다.'))
        clear()
        page.keyboard.press('Control+z')
        expect(page, '화면 밖에서 되돌리면 알린다 — 몇 행인지', lambda: any(x.startswith('되돌렸습니다') and '3' in x for x in toasts()), toasts)
        check('— 파일은 처음 그대로', read('긴.md') == LONG)

        print('[5 단축키 표에서 찾아 바로 써 보기]')
        open_doc('초안.md')
        page.keyboard.press('Control+/')
        page.wait_for_selector('#lec-keys:not([hidden])')
        page.keyboard.type('바꾸기 창')
        page.wait_for_timeout(200)
        keys = page.evaluate("[...document.querySelectorAll('#lec-keys-list tr')].filter((tr) => tr.offsetParent).map((tr) => tr.querySelector('th').textContent.replace(/\\s/g, ''))")
        check("찾기 칸에 '바꾸기 창' — . 이 나온다", '.' in keys, keys)
        page.keyboard.press('Escape')
        change(line_of('초안.md', '- 니켈: 16,500달러'), '이 목록 전체를 할 일로')
        expect(page, '배운 . 으로 — 목록 전체를 할 일로', lambda: '- [ ] 구리: 9,400달러\n- [ ] 니켈: 16,500달러\n- [ ] 아연: 2,700달러' in read('초안.md'), lambda: read('초안.md')[200:360])
        undo_to('초안.md', DRAFT, 'Ctrl+Z 로 처음 그대로')

        print('[6 Lectern 슬라이드의 칸 안]')
        open_doc('발표.md', '#lec-view .lec-slide')
        page.wait_for_timeout(500)
        change(line_of('발표.md', '- 가'), '이 목록 전체를 번호 목록으로')
        expect(page, '칸 안의 목록 전체를 번호로 — 칸 표시는 그대로', lambda: '::: a card\n1. 가\n2. 나\n:::\n' in read('발표.md'), lambda: read('발표.md'))
        undo_to('발표.md', DECK, 'Ctrl+Z 로 처음 그대로')

        print('[7 가이드 15 의 7단계 그대로 — 연습 문서]')
        open_doc('연습-문서.md')
        change(line_of('연습-문서.md', '- 칠레'), '이 목록 전체를 번호 목록으로')
        expect(page, "'칠레' 에서 . → 목록 전체를 번호로 — 네 항목, 아래 번호 목록과는 따로",
               lambda: '1. 칠레\n2. 페루\n3. 중국\n4. 콩고\n\n순서가 있는 일:\n\n1. 자료 모으기' in read('연습-문서.md'), lambda: read('연습-문서.md')[600:900])
        undo_to('연습-문서.md', PRACTICE, 'Ctrl+Z 로 되돌린다')
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
