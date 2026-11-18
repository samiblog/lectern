"""시나리오 — 레벨 키를 실제 문서처럼 (D152): 항목 200개의 목록, 글머리·번호·할 일이 섞인 세 단계, 목록 둘과 그 사이 문단을 함께 고름,
인용 속 목록, 빈 줄로 띄운 목록, 제목 둘을 골라 Alt+Shift, 번호를 단 제목 문서, 칸 안의 Tab, vi 의 V·j·>·3>>·u, 그리고 되돌리기는 늘 한 번."""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-scenlevels-'))
proj = base / 'proj'
proj.mkdir(parents=True)
BIG = '# 큰 목록\n\n' + '\n'.join(f'{i}. 항목 {i:03d}' for i in range(1, 201)) + '\n'
MIX = ('# 섞인 목록\n\n- 원자재\n  1. 구리\n     - [ ] 재고 확인\n     - [x] 가격 표\n  2. 니켈\n- 환율\n\n사이 문단이다.\n\n1. 첫째\n2. 둘째\n3. 셋째\n\n'
       '> - 인용 가\n> - 인용 나\n\n- 띄운 가\n\n- 띄운 나\n\n- 띄운 다\n')
HEADS = '# 문서\n\n## 가 장\n\n### 가 절\n\n## 나 장\n\n### 나 절\n\n#### 나 항\n\n## 다 장\n'
NUMBERED = '# 보고서\n\n## 1. 서론\n\n- 배경\n- 목적\n\n## 2. 본론\n\n### 2.1 현황\n\n## 3. 결론\n'
files = {'큰.md': BIG, '섞인.md': MIX, '제목.md': HEADS, '번호.md': NUMBERED}
for name, text in files.items():
    (proj / name).write_text(text, encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)
errors = []


def read(name):
    for _ in range(40):
        try:
            return (proj / name).read_text(encoding='utf-8')
        except OSError:
            time.sleep(0.05)
    return ''


lines = lambda name: read(name).split('\n')

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_context(viewport={'width': 1400, 'height': 900}).new_page()
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        toast = lambda: page.text_content('#lec-toast') or ''
        clear_toast = lambda: page.evaluate("() => { const t = document.querySelector('#lec-toast'); t.textContent = ''; t.hidden = true; }")
        vi = lambda on: page.evaluate("(on) => import('/static/js/api.js').then((m) => m.saveConfig({ vi_keys: on }))", on)
        SRC = "() => import('/static/js/store.js').then(({ S }) => S.pane?.source?.lines?.join('\\n'))"

        def open_doc(name):
            page.keyboard.press('Escape')
            page.locator(f'#lec-tree .row.file[data-doc="{name}"]').click()
            page.wait_for_function("(n) => document.querySelector('#lec-st-path')?.textContent.includes(n)", arg=name, timeout=8000)
            page.wait_for_timeout(700)

        def reset(name):
            page.keyboard.press('Escape')
            page.keyboard.press('Escape')
            if read(name) != files[name]:
                (proj / name).write_text(files[name], encoding='utf-8')
            until(page, lambda: (page.evaluate(SRC) or '').rstrip('\n') == files[name].rstrip('\n'), 10000)
            page.wait_for_timeout(300)

        def go(n):
            page.locator('#lec-view h1').first.click()
            page.evaluate("(n) => import('/static/js/spotlight.js').then((m) => m.followLine(n))", n)
            page.wait_for_timeout(200)

        LIT = "() => import('/static/js/spotlight.js').then((m) => m.litSpan())"

        def pick(a, b_):
            """a 행부터 b_ 행이 든 줄까지 고른다 — Shift+↓ 는 빈 줄을 건너뛰므로 고른 끝을 보며 누른다"""
            go(a)
            for _ in range(b_ - a):
                span = page.evaluate(LIT)
                if span and span[1] >= b_:
                    break
                page.keyboard.press('Shift+ArrowDown')
            page.wait_for_timeout(150)

        def back(name, label):
            page.keyboard.press('Escape')
            page.keyboard.press('Control+z')
            expect(page, f'{label} — Ctrl+Z 한 번으로 처음 그대로', lambda: read(name) == files[name], lambda: read(name)[:200])

        print('[항목 200개]')
        open_doc('큰.md')
        pick(52, 101)   # 항목 050 ~ 099
        began = time.time()
        page.keyboard.press('Tab')
        ok = until(page, lambda: lines('큰.md')[51] == '    1. 항목 050' and lines('큰.md')[100] == '    50. 항목 099', 15000)
        took = time.time() - began
        check(f'50줄을 골라 Tab — 앞 항목의 하위 50개로 ({took:.1f}초)', ok and took < 8, (lines('큰.md')[50:53], lines('큰.md')[99:102], took))
        check('— 뒤 항목은 50 부터 이어짐', lines('큰.md')[101] == '50. 항목 100' and lines('큰.md')[-2] == '150. 항목 200', lines('큰.md')[101:103])
        expect(page, '— 번호를 다시 매긴 뒤 항목 101개를 알림', lambda: '뒤 항목 101개의 번호를 다시 매겼습니다' in toast(), toast)   # 100 ~ 200번
        back('큰.md', '큰 목록')

        print('[섞인 세 단계]')
        open_doc('섞인.md')
        pick(4, 6)   # 구리와 그 할 일 둘
        page.keyboard.press('Shift+Tab')
        expect(page, '하위가 있는 번호 항목과 하위를 함께 골라 밖으로 — 한 단계만', lambda: lines('섞인.md')[3:7] == ['- 구리', '  - [ ] 재고 확인', '  - [x] 가격 표', '  1. 니켈'], lambda: lines('섞인.md')[2:8])
        back('섞인.md', '섞인 목록')
        reset('섞인.md')
        pick(7, 13)   # 니켈 · 환율 · (빈 줄) · 사이 문단 · (빈 줄) · 첫째 · 둘째
        page.keyboard.press('Tab')
        expect(page, '목록 둘과 사이 문단을 함께 — 옮길 수 있는 줄만', lambda: lines('섞인.md')[9] == '사이 문단이다.' and lines('섞인.md')[12] == '   1. 둘째' and lines('섞인.md')[13] == '2. 셋째',
               lambda: lines('섞인.md')[5:14])
        back('섞인.md', '목록 둘과 문단')
        reset('섞인.md')
        go(17)
        page.keyboard.press('Control+Enter')
        page.keyboard.press('Tab')
        expect(page, '인용 속 목록 — 인용 표시 뒤에서 들여쓴다', lambda: lines('섞인.md')[16] == '>   - 인용 나', lambda: lines('섞인.md')[15:17])
        back('섞인.md', '인용 속 목록')
        reset('섞인.md')
        pick(21, 23)   # 띄운 나 · (빈 줄) · 띄운 다
        page.keyboard.press('Tab')
        expect(page, '빈 줄로 띄운 목록 — 둘 다 앞 항목의 하위로', lambda: lines('섞인.md')[20] == '  - 띄운 나' and lines('섞인.md')[22] == '  - 띄운 다', lambda: lines('섞인.md')[18:23])
        back('섞인.md', '띄운 목록')
        reset('섞인.md')
        pick(5, 6)   # 하위 할 일 둘
        page.keyboard.press('n')
        expect(page, '하위 할 일 둘을 번호로 — 들여쓰기 그대로', lambda: lines('섞인.md')[4:6] == ['     1. 재고 확인', '     2. 가격 표'], lambda: lines('섞인.md')[3:7])
        back('섞인.md', '종류 바꾸기')

        print('[제목]')
        open_doc('제목.md')
        pick(7, 11)   # 나 장 ~ 나 항
        clear_toast()
        page.keyboard.press('Alt+Shift+ArrowRight')
        expect(page, '절 하나를 통째로 골라 Alt+Shift+→ — 모두 한 단계씩만', lambda: lines('제목.md')[6:11] == ['### 나 장', '', '#### 나 절', '', '##### 나 항'] and lines('제목.md')[12] == '## 다 장',
               lambda: lines('제목.md')[6:13])
        expect(page, '— 함께 옮긴 하위 절 제목 2개', lambda: '하위 절 제목 2개도' in toast(), toast)
        back('제목.md', '제목')
        reset('제목.md')
        pick(3, 7)   # 가 장 ~ 나 장 (제목 셋)
        page.keyboard.press('Tab')
        expect(page, '제목만 골라 Tab — 그대로이고 키를 알림', lambda: '제목 수준은 숫자 키' in toast() and read('제목.md') == HEADS, toast)
        page.keyboard.press('Escape')

        print('[번호를 단 제목 문서]')
        open_doc('번호.md')
        pick(5, 6)
        clear_toast()
        page.keyboard.press('Tab')
        page.wait_for_timeout(900)
        check('목록의 Tab 은 제목 번호를 건드리지 않음', read('번호.md') == NUMBERED.replace('- 배경\n- 목적', '- 배경\n  - 목적') and '제목 번호' not in toast(), (read('번호.md')[:80], toast()))
        back('번호.md', '번호 문서의 목록')
        reset('번호.md')
        go(11)   # ### 2.1 현황
        clear_toast()
        page.keyboard.press('2')
        page.wait_for_timeout(250)
        page.keyboard.press('2')
        expect(page, '2.1 현황을 제목 2 로 — 3. 현황, 결론은 4', lambda: '## 3. 현황' in read('번호.md') and '## 4. 결론' in read('번호.md'), lambda: read('번호.md'))
        expect(page, '— 다시 매긴 제목 번호를 알림', lambda: '제목 번호 1곳을 다시 매겼습니다' in toast(), toast)
        back('번호.md', '번호 제목')

        print('[칸 안]')
        open_doc('섞인.md')
        reset('섞인.md')
        go(4)   # 구리
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit')
        page.keyboard.press('Shift+Tab')
        expect(page, '칸 안의 Shift+Tab — 하위와 함께 밖으로, 칸은 이어짐', lambda: lines('섞인.md')[3:6] == ['- 구리', '  - [ ] 재고 확인', '  - [x] 가격 표'] and page.locator('#lec-view .lec-line-edit').count() == 1,
               lambda: lines('섞인.md')[2:7])
        page.keyboard.press('Escape')
        back('섞인.md', '칸 안의 레벨')

        print('[vi 키]')
        reset('섞인.md')
        vi(True)
        go(4)
        for k in ('Shift+V', 'j', 'j', '<'):
            page.keyboard.press(k)
        expect(page, 'V j j < — 구리와 하위를 한 단계만 밖으로', lambda: lines('섞인.md')[3:6] == ['- 구리', '  - [ ] 재고 확인', '  - [x] 가격 표'], lambda: lines('섞인.md')[2:7])
        page.keyboard.press('Escape')
        page.keyboard.press('u')
        expect(page, 'u 로 되돌림', lambda: read('섞인.md') == MIX, lambda: read('섞인.md')[:120])
        go(13)   # 2. 둘째
        for k in ('2', '>', '>'):
            page.keyboard.press(k)
        expect(page, '2>> — 둘째·셋째가 첫째의 하위로', lambda: lines('섞인.md')[11:14] == ['1. 첫째', '   1. 둘째', '   2. 셋째'], lambda: lines('섞인.md')[11:14])
        page.keyboard.press('u')
        expect(page, 'u 한 번으로 처음 그대로', lambda: read('섞인.md') == MIX, lambda: read('섞인.md')[:160])
        vi(False)
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
