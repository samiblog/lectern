"""내 스타일 만들기 (D211) — 지금 스타일을 바탕으로 칸을 골라 설정 폴더 styles 에 CSS 하나로 저장한다.
- 여는 곳: 툴바 스타일 목록의 '내 스타일 만들기…'(고른 스타일은 그대로), 설정 창 '화면에서 만들기…', 명령 찾기.
- 고르는 대로 문서에 입혀 본다 (미리보기). 닫거나 다른 스타일을 고르면 걷는다. 위·아래 단추는 이 줄로 가지 않는다.
- 저장: 새 파일 하나 (바꾼 칸만), 그 스타일로 바뀐다. 같은 이름은 만들지 않는다.
- 이 창이 만든 스타일은 다시 열면 값을 불러오고, 물은 뒤 그 파일을 고친다 — 그사이 바뀌었으면 쓰지 않는다.
- 손으로 쓴 스타일은 고치지 않는다: 그 규칙을 새 파일에 옮겨 담아 새 이름으로."""
import json
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-stylemaker-'))
proj = base / '과제'
proj.mkdir()
(proj / '보고서.md').write_text('# 보고서\n\n## 수요\n\n- 맨 위\n  - 둘째\n- 맨 위 둘\n\n본문 [링크](https://example.com).\n', encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report'}), encoding='utf-8')
styles = config / 'styles'

BOX = '#lec-stylemaker'
VAR = "(k) => getComputedStyle(document.documentElement).getPropertyValue(k).trim()"
SIZE = "() => { const v = document.querySelector('#lec-view'); return Math.round(parseFloat(getComputedStyle(v).fontSize) / (parseFloat(getComputedStyle(v).getPropertyValue('--md-scale')) || 1) * 10) / 10; }"   # --md-size (글자 크기 배율을 뺀)
TOP_W = "() => Number(getComputedStyle([...document.querySelectorAll('#lec-view li')].find((li) => li.textContent.startsWith('맨 위'))).fontWeight)"
THEME = "() => document.documentElement.dataset.theme"
TOAST = "() => { const e = document.querySelector('#lec-toast'); return e && !e.hidden ? e.textContent : ''; }"


def field(page, key):
    return page.locator(f'{BOX} [data-key="{key}"]')


def set_number(page, key, value):
    f = field(page, key)
    f.fill(str(value))
    f.dispatch_event('input')


def open_from_picker(page):
    page.select_option('#lec-theme', '__make')
    page.wait_for_selector(f'{BOX}:not([hidden])', timeout=8000)


server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.click('#lec-tree .row[data-doc="보고서.md"]')
        page.wait_for_selector('#lec-view li', timeout=10000)

        print("[툴바에서 열기 · 미리보기]")
        open_from_picker(page)
        check("목록의 '내 스타일 만들기…' 로 열리고 고른 스타일은 그대로", page.eval_on_selector('#lec-theme', 'e => e.value') == 'report' and page.evaluate(THEME) == 'report')
        check("바탕: 보고서", '보고서' in page.inner_text('#lec-stylemaker-sub'), page.inner_text('#lec-stylemaker-sub'))
        check('칸은 지금 스타일의 값 — 글자 16px · 글자색', field(page, '--md-size').input_value() == '16' and field(page, '--md-fg').input_value() == '#22262b',
              (field(page, '--md-size').input_value(), field(page, '--md-fg').input_value()))
        check('글꼴 목록은 이 PC 에 있는 것만 — Arial 이 있다', page.locator(f'{BOX} select[data-key="--md-font"] option[value="Arial"]').count() == 1)
        set_number(page, '--md-size', 18)
        check('글자 크기를 바꾸면 문서에 바로', until(page, lambda: page.evaluate(SIZE) == 18), page.evaluate(SIZE))
        page.select_option(f'{BOX} select[data-key="--lec-list-top-weight"]', '700')
        check('목록 맨 위 항목 — 진하게(700)', until(page, lambda: page.evaluate(TOP_W) == 700), page.evaluate(TOP_W))
        page.select_option(f'{BOX} select[data-key="--md-font"]', 'Arial')
        check('본문 글꼴 — 고른 글꼴을 앞에, 원래 목록을 뒤에', page.evaluate(VAR, '--md-font').startswith('"Arial", "KoPubBatang"') or page.evaluate(VAR, '--md-font').startswith('"Arial",'),
              page.evaluate(VAR, '--md-font')[:80])
        page.select_option(f'{BOX} select[data-key="--md-heading-font"]', '__own')
        own = page.locator(f'{BOX} input[data-own="--md-heading-font"]')
        own.fill('x;} body{display:none')
        own.dispatch_event('input')
        check('직접 적은 글꼴에 쓸 수 없는 글자가 있으면 입히지 않는다', 'display' not in page.evaluate(VAR, '--md-heading-font'), page.evaluate(VAR, '--md-heading-font')[:60])
        page.keyboard.press('Escape')
        check('Esc — 닫고 미리보기를 걷는다', until(page, lambda: page.locator(BOX).is_hidden() and page.evaluate(SIZE) == 16), page.evaluate(SIZE))

        print('[저장]')
        open_from_picker(page)
        set_number(page, '--md-size', 18)
        field(page, '--md-link').evaluate("(e) => { e.value = '#aa2200'; e.dispatchEvent(new Event('input', { bubbles: true })); }")
        field(page, '--md-fg').evaluate("(e) => { e.value = '#dddddd'; e.dispatchEvent(new Event('input', { bubbles: true })); }")
        check('바탕과 대비가 낮은 글자색은 알린다 (저장은 막지 않음)', until(page, lambda: '대비' in page.inner_text('#lec-stylemaker-msg')), page.inner_text('#lec-stylemaker-msg'))
        field(page, '--md-fg').evaluate("(e) => { e.value = '#222222'; e.dispatchEvent(new Event('input', { bubbles: true })); }")
        check('— 대비가 충분하면 알림을 걷는다', until(page, lambda: page.locator('#lec-stylemaker-msg').is_hidden()))
        page.fill('#lec-stylemaker-name', '우리 보고서')
        page.click('#lec-stylemaker-save')
        until(page, lambda: page.evaluate(THEME) == 'user:우리 보고서')
        check('알림', until(page, lambda: '우리 보고서' in page.evaluate(TOAST), ms=3000), page.evaluate(TOAST))
        made = styles / '우리 보고서.css'
        text = made.read_text(encoding='utf-8') if made.exists() else ''
        check('새 파일 하나 — 머리 주석(바탕 report · maker) 과 바꾼 칸만', 'base: report' in text and 'maker: lectern' in text and '--md-size: 18px;' in text
              and '--md-link: #aa2200;' in text and '--md-heading' not in text, text[-200:])
        check('저장하면 그 스타일로 — 목록에도', page.eval_on_selector('#lec-theme', 'e => e.value') == 'user:우리 보고서' and until(page, lambda: page.evaluate(SIZE) == 18))
        check('미리보기는 걷었다 (내 스타일 css 가 입힌다)', page.locator('#lec-stylemaker-preview').count() == 0 and page.evaluate(VAR, '--md-link') == '#aa2200')

        print('[다시 열어 고치기]')
        open_from_picker(page)
        check("'우리 보고서' 고치기 — 저장한 값을 불러온다", '우리 보고서' in page.inner_text('#lec-stylemaker-sub') and field(page, '--md-size').input_value() == '18'
              and page.input_value('#lec-stylemaker-name') == '우리 보고서', page.inner_text('#lec-stylemaker-sub'))
        set_number(page, '--md-size', 15)
        page.click('#lec-stylemaker-save')
        check('저장하면 먼저 묻는다', page.locator('#lec-stylemaker-ask').is_visible() and '우리 보고서' in page.inner_text('#lec-stylemaker-question'))
        page.click('#lec-stylemaker-replace')
        check('바꾸기 — 그 파일을 고쳐 쓴다', until(page, lambda: '--md-size: 15px;' in made.read_text(encoding='utf-8')) and len(list(styles.glob('*.css'))) == 1,
              [x.name for x in styles.iterdir()])
        check('— 화면도 15px', until(page, lambda: page.evaluate(SIZE) == 15, ms=8000), page.evaluate(SIZE))

        print('[그사이 바뀌었으면 · 같은 이름]')
        open_from_picker(page)
        time.sleep(0.05)
        made.write_text(made.read_text(encoding='utf-8') + '/* 손으로 덧붙임 */\n', encoding='utf-8')
        set_number(page, '--md-size', 20)
        page.click('#lec-stylemaker-save')
        page.click('#lec-stylemaker-replace')
        check('그사이 바뀌었으면 쓰지 않고 까닭을 알린다', until(page, lambda: '바뀌었습니다' in page.inner_text('#lec-stylemaker-msg'))
              and '20px' not in made.read_text(encoding='utf-8'), page.inner_text('#lec-stylemaker-msg'))
        page.click('#lec-stylemaker-cancel')
        page.select_option('#lec-theme', 'default')
        until(page, lambda: page.evaluate(THEME) == 'default')
        open_from_picker(page)
        page.fill('#lec-stylemaker-name', '우리 보고서')
        page.click('#lec-stylemaker-save')
        check('같은 이름이 있으면 만들지 않는다', until(page, lambda: '같은 이름' in page.inner_text('#lec-stylemaker-msg')), page.inner_text('#lec-stylemaker-msg'))
        page.select_option('#lec-theme', 'report')
        check('다른 스타일을 고르면 창을 닫고 미리보기를 걷는다', until(page, lambda: page.locator(BOX).is_hidden()) and page.locator('#lec-stylemaker-preview').count() == 0)

        print('[손으로 쓴 스타일을 바탕으로]')
        hand = '/* lectern-style\n   name: 손\n   base: office\n*/\n.md-body h1 { border-bottom: 5px solid rgb(255, 0, 0); }\n'
        (styles / '손.css').write_text(hand, encoding='utf-8')
        page.wait_for_selector('#lec-theme option[value="user:손"]', state='attached', timeout=10000)
        page.select_option('#lec-theme', 'user:손')
        until(page, lambda: page.evaluate(THEME) == 'user:손')
        open_from_picker(page)
        check('직접 쓴 스타일이라고 알린다', '직접 쓴' in page.inner_text('#lec-stylemaker-sub'), page.inner_text('#lec-stylemaker-sub'))
        set_number(page, '--md-size', 17)
        page.fill('#lec-stylemaker-name', '손 2')
        page.click('#lec-stylemaker-save')
        until(page, lambda: page.evaluate(THEME) == 'user:손 2')
        new = (styles / '손 2.css').read_text(encoding='utf-8') if (styles / '손 2.css').exists() else ''
        check('그 규칙을 옮겨 담고 값을 얹은 새 파일 — 원래 파일은 그대로', 'border-bottom: 5px solid' in new and '--md-size: 17px;' in new and 'base: office' in new
              and (styles / '손.css').read_text(encoding='utf-8') == hand, new[-240:])
        bb = page.evaluate("() => getComputedStyle(document.querySelector('#lec-view h1')).borderBottomColor")
        check('— 새 스타일에도 그 규칙이 듣는다', bb == 'rgb(255, 0, 0)' and until(page, lambda: page.evaluate(SIZE) == 17), bb)

        print('[다른 여는 곳 · 위아래 단추]')
        page.click('#lec-btn-settings')
        page.wait_for_selector('#lec-mystyles-make', state='visible', timeout=8000) if page.locator('#lec-mystyles-make').is_visible() else page.evaluate("() => document.querySelector('#lec-mystyles-make').scrollIntoView()")
        page.click('#lec-mystyles-make')
        check("설정 창 '화면에서 만들기…' — 설정 창을 닫고 연다", until(page, lambda: page.locator(BOX).is_visible() and page.locator('#lec-settings').is_hidden()))
        page.keyboard.press('Escape')
        page.keyboard.press('Control+Shift+P')
        page.keyboard.type('내 스타일 만들기')
        page.wait_for_timeout(300)
        page.keyboard.press('Enter')
        check('명령 찾기에서도', until(page, lambda: page.locator(BOX).is_visible()))
        page.keyboard.press('Escape')
        last = page.evaluate("() => { const s = document.querySelector('#lec-theme'); return s.options[s.options.length - 3].value; }")
        page.select_option('#lec-theme', last)
        page.wait_for_timeout(300)
        check("위·아래 단추는 '내 스타일 만들기…' 줄로 가지 않는다", page.is_disabled('#lec-theme-next'), last)
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
report()
