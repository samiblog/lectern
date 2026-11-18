"""Tab 이 문서 밖으로 나가지 않는다 — 무작위 시험 (D167, 2026-11-18 사용자 요청 '다른 각도에서'): 터미널을 연 채 여러 문서(링크·표·각주·접힌 절·코드 블록이 든 md,
링크 없는 md, Lectern 슬라이드, 입력 칸이 든 html, 누를 것 없는 html, csv, 코드, 폴더 개요)를 무작위로 열고, 아무 곳이나 누르고, 접기·찾기 막대·칸 열고 닫기·
모두 펼치기를 섞어 가며 Tab·Shift+Tab 을 거듭 누른다. 문서 안에서 누른 Tab 뒤의 초점이 한 번이라도 문서 칸 밖(터미널·사이드바·툴바·탭 줄·상태줄·바닥)이면 실패.
    python tab_fuzz.py [씨앗 …]   (기본 씨앗 셋, 씨앗마다 걸음 120)"""
import json
import random
import sys
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

SEEDS = [int(x) for x in sys.argv[1:] if x.isdigit()] or [11, 23, 47]
STEPS = 120

base = Path(tempfile.mkdtemp(prefix='lec-tabfuzz-'))
proj = base / 'proj'
(proj / 'sub').mkdir(parents=True)
(proj / 'mixed.md').write_text("""# 섞인 문서

첫 문단에 [링크 하나](plain.md) 가 있다.

## 표와 목록

| 항목 | 링크 |
|---|---|
| 가 | [표 안 링크](#표와-목록) |

- 목록 [안 링크](plain.md)
- [ ] 할 일 체크 칸

> [!NOTE]
> 강조글 안 [링크](#섞인-문서).

## 접히는 절

절 안 [숨을 링크](plain.md) 이다.

```python
print('코드 블록 — 복사 단추')
```

각주가 있는 글이다[^1].

[^1]: 각주의 [링크](plain.md).
""", encoding='utf-8')
(proj / 'plain.md').write_text('# 링크 없는 문서\n\n' + '\n\n'.join(f'{i}번째 문단.' for i in range(1, 30)) + '\n', encoding='utf-8')
(proj / 'deck.md').write_text('---\nmarp: true\n---\n\n# 첫 장\n\n[링크](plain.md) 가 있는 장\n\n---\n\n# 둘째 장\n\n- 항목\n', encoding='utf-8')
(proj / 'form.html').write_text('<title>폼</title><p><a href="#x">하나</a></p><p><input value="입력 칸"> <button>단추</button></p><p><a href="#y">끝 링크</a></p>', encoding='utf-8')
(proj / 'bare.html').write_text('<title>빈 쪽</title><p>누를 것이 없는 쪽.</p>', encoding='utf-8')
(proj / 'data.csv').write_text('지역,값\n가,1\n나,2\n다,3\n', encoding='utf-8')
(proj / 'tool.py').write_text('\n'.join(f'x{i} = {i}' for i in range(40)) + '\n', encoding='utf-8')
(proj / 'sub' / 'note.md').write_text('# 하위 문서\n\n글.\n', encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

TARGETS = [('doc', 'mixed.md'), ('doc', 'plain.md'), ('doc', 'deck.md'), ('doc', 'form.html'), ('doc', 'bare.html'),
           ('code', 'data.csv'), ('code', 'tool.py'), ('overview', ''), ('overview', 'sub')]
WHERE = """() => { const a = document.activeElement;
  if (!a || a === document.body || a === document.documentElement) return 'body';
  if (a.closest('#lec-term')) return 'term';
  if (a.closest('#lec-sidebar')) return 'side';
  if (a.closest('#lec-toolbar, #lec-tabbar, #lec-status')) return 'chrome';
  if (a.closest('#lec-doctabs')) return 'doctabs';
  if (a.closest('.lec-pane, #lec-panes')) return a.tagName === 'IFRAME' ? 'frame' : 'doc';
  return 'other:' + (a.id || a.className || a.tagName); }"""

try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1400, 'height': 860}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file')
        page.keyboard.press('Control+`')   # 터미널을 열어 둔다
        page.wait_for_selector('#lec-term .term-box:not([hidden]) .xterm', timeout=15000)
        page.wait_for_timeout(800)
        where = lambda: page.evaluate(WHERE)  # noqa: E731

        def open_target(kind, path):
            page.evaluate("([k, p]) => import('/static/js/store.js').then((m) => m.emit('open', { type: k, path: p }))", [kind, path])
            until(page, lambda: page.evaluate("() => import('/static/js/store.js').then(({ S }) => !!S.pane?.current && !S.pane.pending)"), 8000)
            page.wait_for_timeout(350)

        def click_inside(rng):
            """문서 칸 안의 아무 곳 — 보이는 요소 하나를 골라 그 가운데를 누른다 (html 이면 iframe 안). 누를 것이 없으면 칸 빈 곳"""
            boxes = page.evaluate("""() => { const v = document.querySelector('#lec-view'); if (!v) return [];
              return [...v.querySelectorAll('p, li, td, h1, h2, pre, .cv-line, iframe, button.overview-doc, .ov-card, [data-doc], tr')]
                .map((e) => e.getBoundingClientRect()).filter((r) => r.width > 4 && r.height > 4 && r.top > 40 && r.bottom < innerHeight - 30)
                .slice(0, 60).map((r) => [r.left + Math.min(r.width / 2, 30), r.top + r.height / 2]); }""")
            if boxes:
                x, y = rng.choice(boxes)
                page.mouse.click(x, y)
            else:
                page.locator('#lec-content').focus()
            page.wait_for_timeout(120)

        total = 0
        bad = []
        for seed in SEEDS:
            rng = random.Random(seed)
            log = []
            open_target(*rng.choice(TARGETS))
            click_inside(rng)
            for step in range(STEPS):
                act = rng.choices(['open', 'click', 'tab', 'esc', 'cell', 'find', 'fold', 'spread', 'scroll'], [8, 14, 40, 6, 6, 5, 5, 3, 4])[0]
                log.append(act)
                if act == 'open':
                    open_target(*rng.choice(TARGETS))
                    click_inside(rng)
                elif act == 'click':
                    click_inside(rng)
                elif act == 'esc':
                    page.keyboard.press('Escape')
                elif act == 'cell':   # 칸을 열고 닫는다 (Enter — D166, 바꾸지 않으니 파일은 그대로)
                    page.keyboard.press('Enter')
                    page.wait_for_timeout(250)
                    page.keyboard.press('Escape')
                elif act == 'find':
                    page.keyboard.press('Control+f')
                    page.wait_for_timeout(120)
                elif act == 'fold':
                    page.keyboard.press('Alt+Enter')   # 제목이면 접기, 링크 줄이면 열기 — 문서가 바뀌어도 된다
                    page.wait_for_timeout(300)
                elif act == 'spread':
                    page.click('#lec-doctab-spread')
                    page.wait_for_timeout(400)
                    click_inside(rng)
                elif act == 'scroll':
                    page.mouse.wheel(0, rng.choice([-600, 600]))
                    page.wait_for_timeout(150)
                if act != 'tab':
                    continue
                before = where()
                if before not in ('doc', 'frame'):   # 문서 밖에서 누른 Tab 은 이 시험의 몫이 아니다 — 문서 안으로 돌아와서
                    click_inside(rng)
                    before = where()
                    if before not in ('doc', 'frame'):
                        continue
                key = rng.choice(['Tab', 'Tab', 'Shift+Tab'])
                for _ in range(rng.randint(1, 9)):
                    page.keyboard.press(key)
                    page.wait_for_timeout(90)
                    total += 1
                    now = where()
                    if now not in ('doc', 'frame'):
                        view = page.evaluate("() => import('/static/js/store.js').then(({ S }) => JSON.stringify(S.pane?.current || null))")
                        bad.append(f'씨앗 {seed} 걸음 {step} {key} → {now} (보던 것 {view}, 앞의 일 {log[-6:]})')
                        page.locator('#lec-content').focus()
                        break
            if page.evaluate("document.documentElement.classList.contains('spread-on')"):
                page.click('#lec-doctab-spread')
        print(f'  Tab·Shift+Tab {total}번을 눌렀다 (씨앗 {SEEDS}, 씨앗마다 걸음 {STEPS})')
        check(f'Tab {total}번 — 한 번도 문서 칸 밖으로 나가지 않았다', not bad, bad[:5])
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        browser.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
