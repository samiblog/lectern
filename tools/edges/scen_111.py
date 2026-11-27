"""0.111 사람 시나리오 — 목록의 수준 (D210) 과 내 스타일 만들기 (D211) 를 실제 일하는 차례대로.

1 개조식 보고서를 쓰는 동안 목록이 자란다: □ 만 있던 묶음에 ○ 줄을 더하면 □ 가 진해지고, 지우면 돌아간다. 한 줄 편집·긴 줄의 꺾임·Markdown 목록의 레벨.
2 AI(Claude)가 파일을 고쳐 ○ 줄을 더한다 — 저절로 다시 그려 □ 가 진해진다.
3 팀 보고서 스타일을 만든다 — 칸 고르기, 대비 알림, 이름 칸의 Enter 로 저장, 다시 켜도 그 스타일, 다시 열어 고쳐 쓰기.
  그사이 Claude 가 그 파일에 규칙을 더해도 다시 저장할 때 남는다.
4 GitHub 스타일로 바꾸면 목록 강조는 꺼지고 창은 닫힌다. 종이(인쇄)에는 진하게.
5 Word 로 보내기 — 같은 위계 (□ 진하게, 항목마다 단락).
6 영어 화면에서도 창이 영어로.
7 스타일 파일을 탐색기에서 지우면 목록에서 빠지고 기본 스타일로, 창의 바탕도 기본."""
import importlib
import json
import re
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, expect, fails, report, serve, stop, until

DOC = """# AI 확산과 세계 경제 — 주간 점검

## 1. 핵심

□ 생산성 효과는 서비스업에서 먼저 나타난다
□ 고용 충격은 직무 단위로 온다

## 2. 지표

- 데이터센터 투자
- 전력 수요
- 반도체 수출

## 3. 할 일

- [ ] 자료 모으기
  - [ ] IMF 보고서

> [!NOTE]
> - 참고 속 목록
>   - 참고 속 하위
"""

base = Path(tempfile.mkdtemp(prefix='lec-scen111-'))
proj = base / 'AI 확산 보고서'
(proj / 'reports').mkdir(parents=True)
(proj / 'reports' / '주간.md').write_text(DOC, encoding='utf-8', newline='\n')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'theme': 'report'}), encoding='utf-8')
styles = config / 'styles'
SRC = lambda: (proj / 'reports' / '주간.md').read_text(encoding='utf-8').replace('\r\n', '\n')  # noqa: E731
THEME = "() => document.documentElement.dataset.theme"
SIZE = "() => { const v = document.querySelector('#lec-view'); return Math.round(parseFloat(getComputedStyle(v).fontSize) / (parseFloat(getComputedStyle(v).getPropertyValue('--md-scale')) || 1) * 10) / 10; }"
WEIGHT = """(t) => { const e = [...document.querySelectorAll('#lec-view .lec-mark, #lec-view li')].find((x) => (x.firstChild?.textContent || x.textContent).trim().startsWith(t));
  return e ? Number(getComputedStyle(e).fontWeight) : -1; }"""
BOX = '#lec-stylemaker'


def write(text):
    time.sleep(1.1)   # 수정 시각이 바뀌게
    (proj / 'reports' / '주간.md').write_text(text, encoding='utf-8', newline='\n')


server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={'width': 1300, 'height': 900}).new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        weight = lambda t: page.evaluate(WEIGHT, t)  # noqa: E731

        def open_doc(path):
            page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", path)
            page.wait_for_selector('#lec-view h1', timeout=10000)

        def pick_line(text):
            page.locator('#lec-view .lec-mark, #lec-view li, #lec-view p', has_text=text).first.click()
            page.wait_for_timeout(250)

        def maker_field(key):
            return page.locator(f'{BOX} [data-key="{key}"]')

        def set_number(key, value):
            f = maker_field(key)
            f.fill(str(value))
            f.dispatch_event('input')

        def set_color(key, value):
            maker_field(key).evaluate("(e, v) => { e.value = v; e.dispatchEvent(new Event('input', { bubbles: true })); }", value)

        print('[1 개조식 보고서를 쓰는 동안 목록이 자란다]')
        open_doc('reports/주간.md')
        check('□ 만 있는 묶음은 보통 굵기', weight('□ 생산성') < 600, weight('□ 생산성'))
        pick_line('생산성 효과는')
        page.keyboard.press('Shift+Enter')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=5000)
        check('Shift+Enter — 새 줄은 같은 글머리 글자(□ )로 시작한다', page.inner_text('#lec-view .lec-line-edit').startswith('□'), page.inner_text('#lec-view .lec-line-edit'))
        page.keyboard.press('Control+a')   # 사람은 □ 를 지우고 ○ 로 쓴다
        page.keyboard.type('○ 3분기 서비스업 생산성 1.8% 상승')
        page.keyboard.press('Enter')
        expect(page, 'Shift+Enter 로 ○ 줄을 더하면 원문에 그 줄', lambda: '□ 생산성 효과는 서비스업에서 먼저 나타난다\n○ 3분기 서비스업 생산성 1.8% 상승\n' in SRC(), SRC)
        expect(page, '— 묶음에 ○ 가 생겨 □ 가 진해진다 (둘째 □ 도)', lambda: weight('□ 생산성') >= 600 and weight('□ 고용') >= 600 and weight('○ 3분기') < 600,
               lambda: (weight('□ 생산성'), weight('□ 고용'), weight('○ 3분기')))
        pick_line('고용 충격은')
        page.keyboard.press('F2')
        page.wait_for_selector('#lec-view .lec-line-edit', timeout=5000)
        page.keyboard.press('End')
        page.keyboard.type(' — 사무·상담·번역 직무가 먼저이고 제조 현장은 늦게 온다는 것이 여러 기관의 공통된 판단이다')
        page.keyboard.press('Enter')
        expect(page, 'F2 로 □ 줄을 길게 고친다 — 저장되고 진한 채', lambda: '번역 직무가 먼저' in SRC() and weight('□ 고용') >= 600, SRC)
        gap = page.evaluate("""() => { const e = [...document.querySelectorAll('#lec-view .lec-mark')].find((x) => x.textContent.startsWith('□ 고용'));
          const n = e.firstChild; const r = document.createRange(); r.setStart(n, 2); r.setEnd(n, 3); const first = r.getClientRects()[0];
          for (let i = 3; i < n.nodeValue.length; i++) { r.setStart(n, i); r.setEnd(n, i + 1); const b = r.getClientRects()[0]; if (b && b.top > first.top + 5) return Math.round(Math.abs(b.left - first.left)); }
          return -1; }""")
        check('— 긴 □ 줄이 꺾이면 둘째 줄은 글머리 글자 뒤에 (굵은 글자로 잰 폭)', 0 <= gap <= 2, gap)
        pick_line('3분기 서비스업')
        page.keyboard.press('Delete')
        page.keyboard.press('Delete')
        expect(page, 'Delete 두 번으로 ○ 줄을 지우면 □ 는 다시 보통', lambda: '○ 3분기' not in SRC() and weight('□ 생산성') < 600, lambda: (weight('□ 생산성'), SRC()[:200]))
        check('Markdown 목록 — 하위가 없으면 보통', weight('데이터센터') < 600, weight('데이터센터'))
        pick_line('전력 수요')
        page.keyboard.press('Alt+Shift+ArrowRight')
        page.keyboard.press('Alt+Shift+ArrowRight')
        expect(page, "'전력 수요' 를 한 단계 안으로 — 하위가 생겨 맨 위 둘이 진해진다", lambda: '- 데이터센터 투자\n  - 전력 수요' in SRC()
               and weight('데이터센터') >= 600 and weight('반도체') >= 600 and weight('전력 수요') < 600, lambda: (SRC()[200:330], weight('데이터센터'), weight('반도체')))
        check('할 일 목록 · 강조글 속 목록은 그대로', weight('자료 모으기') < 600 and weight('참고 속 목록') < 600, (weight('자료 모으기'), weight('참고 속 목록')))

        print('[2 AI 가 파일을 고친다]')
        write(SRC().replace('□ 고용 충격은', '○ 콜센터 자동화율 40%\n□ 고용 충격은'))
        expect(page, 'Claude 가 ○ 줄을 더하면 저절로 다시 그려 □ 가 진해진다', lambda: weight('□ 생산성') >= 600 and weight('○ 콜센터') < 600, ms=12000)

        print('[3 팀 보고서 스타일을 만든다]')
        page.select_option('#lec-theme', '__make')
        page.wait_for_selector(f'{BOX}:not([hidden])', timeout=8000)
        page.select_option(f'{BOX} select[data-key="--md-font"]', 'Malgun Gothic')
        set_number('--md-size', 17)
        set_number('--md-line', 1.9)
        set_color('--md-heading', '#cfd8e3')
        expect(page, '제목색을 옅게 고르면 대비가 낮다고 알린다', lambda: '대비' in page.inner_text('#lec-stylemaker-msg'), lambda: page.inner_text('#lec-stylemaker-msg'))
        set_color('--md-heading', '#0f2a4a')
        page.select_option(f'{BOX} select[data-key="--lec-list-top-weight"]', '700')
        set_number('--lec-list-top-scale', 108)
        expect(page, '고르는 대로 문서에 — 글자 17px, □ 700', lambda: page.evaluate(SIZE) == 17 and weight('□ 생산성') == 700, lambda: (page.evaluate(SIZE), weight('□ 생산성')))
        page.fill('#lec-stylemaker-name', '팀 보고서')
        page.keyboard.press('Enter')
        made = styles / '팀 보고서.css'
        expect(page, '이름 칸에서 Enter — 저장하고 그 스타일로', lambda: page.evaluate(THEME) == 'user:팀 보고서' and made.exists())
        text = made.read_text(encoding='utf-8')
        check('— 바꾼 칸만: 글꼴 · 17px · 1.9 · 제목색 · 목록 700 · 1.08', all(s in text for s in ('"Malgun Gothic"', '--md-size: 17px;', '--md-line: 1.9;', '#0f2a4a', 'weight: 700;', 'scale: 1.08;'))
              and '--md-fg' not in text and '--md-width' not in text, text[-300:])
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        open_doc('reports/주간.md')
        expect(page, '다시 켜도 그 스타일 — 글자 17px, □ 700', lambda: page.evaluate(THEME) == 'user:팀 보고서' and page.evaluate(SIZE) == 17 and weight('□ 생산성') == 700, ms=10000)
        page.select_option('#lec-theme', '__make')
        page.wait_for_selector(f'{BOX}:not([hidden])', timeout=8000)
        check('다시 열면 그 값 — 글꼴 칸은 맑은 고딕, 목록 108%', page.input_value(f'{BOX} select[data-key="--md-font"]') == 'Malgun Gothic' and maker_field('--lec-list-top-scale').input_value() == '108',
              (page.input_value(f'{BOX} select[data-key="--md-font"]'), maker_field('--lec-list-top-scale').input_value()))
        set_number('--lec-list-top-scale', 110)
        page.click('#lec-stylemaker-save')
        page.click('#lec-stylemaker-replace')
        expect(page, '고쳐 쓰기 — 물은 뒤 그 파일을 (스타일은 하나)', lambda: 'scale: 1.1;' in made.read_text(encoding='utf-8') and len(list(styles.glob('*.css'))) == 1)
        time.sleep(1.1)
        t2 = made.read_text(encoding='utf-8')
        made.write_text(t2.replace('/* lectern-maker */', '.md-body h2 { letter-spacing: .03em; }\n\n/* lectern-maker */'), encoding='utf-8')
        expect(page, 'Claude 가 그 파일에 규칙을 더하면 몇 초 안에 다시 입혀진다', lambda: page.evaluate("() => getComputedStyle(document.querySelector('#lec-view h2')).letterSpacing") != 'normal', ms=10000)
        page.select_option('#lec-theme', '__make')
        page.wait_for_selector(f'{BOX}:not([hidden])', timeout=8000)
        set_number('--md-size', 16)
        page.click('#lec-stylemaker-save')
        page.click('#lec-stylemaker-replace')
        expect(page, '— 다시 저장해도 그 규칙은 남고 값 칸은 하나', lambda: '--md-size: 16px;' in made.read_text(encoding='utf-8'))
        t3 = made.read_text(encoding='utf-8')
        check('— (파일 확인)', 'letter-spacing: .03em' in t3 and t3.count('/* lectern-maker */') == 1 and t3.count(':root') == 1, t3[-260:])

        print('[4 GitHub 스타일 · 종이]')
        page.emulate_media(media='print')
        check('종이(인쇄)에도 □ 진하게', weight('□ 생산성') >= 600, weight('□ 생산성'))
        page.emulate_media(media='screen')
        page.select_option('#lec-theme', '__make')
        page.wait_for_selector(f'{BOX}:not([hidden])', timeout=8000)
        page.select_option('#lec-theme', 'github')
        expect(page, 'GitHub 스타일로 바꾸면 창은 닫히고 목록 강조는 꺼진다', lambda: page.locator(BOX).is_hidden() and page.evaluate(THEME) == 'github' and weight('□ 생산성') < 600
               and weight('데이터센터') < 600)
        page.select_option('#lec-theme', 'user:팀 보고서')

        print('[5 Word 로 보내기]')
        sys.path.insert(0, str(ROOT / 'skills' / 'lectern-to-docx' / 'scripts'))
        bd = importlib.import_module('build_docx')
        bd.figure_png.draw = lambda *a, **k: False
        out = base / '주간.docx'
        bd.build(proj / 'reports' / '주간.md', out)
        with zipfile.ZipFile(out) as z:
            xml = z.read('word/document.xml').decode('utf-8')
        paras = {(''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', q))): q for q in re.findall(r'<w:p>.*?</w:p>', xml)}
        top = next((q for k, q in paras.items() if k.startswith('□ 생산성')), '')
        sub = next((q for k, q in paras.items() if k.startswith('○ 콜센터')), '')
        md_top = next((q for k, q in paras.items() if k.startswith('데이터센터')), '')
        check('Word — □ 는 진한 단락, ○ 는 들여 쓴 보통 단락, 맨 위 Markdown 항목도 진하게', '<w:b/>' in top and '<w:b/>' not in sub and 'w:left=' in sub and '<w:b/>' in md_top,
              (top[:160], sub[:160]))

        print('[7 스타일 파일을 지우면]')
        made.unlink()
        expect(page, '탐색기에서 지우면 목록에서 빠지고 기본 스타일로', lambda: page.locator('#lec-theme option[value="user:팀 보고서"]').count() == 0 and page.evaluate(THEME) == 'default', ms=10000)
        page.select_option('#lec-theme', '__make')
        page.wait_for_selector(f'{BOX}:not([hidden])', timeout=8000)
        check('— 창의 바탕도 기본', '기본' in page.inner_text('#lec-stylemaker-sub'), page.inner_text('#lec-stylemaker-sub'))
        page.keyboard.press('Escape')
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        browser.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)

print('[6 영어 화면]')
base2 = Path(tempfile.mkdtemp(prefix='lec-scen111en-'))
proj2 = base2 / 'p'
proj2.mkdir()
(proj2 / 'a.md').write_text('# A\n\n- top\n  - sub\n', encoding='utf-8')
config2 = base2 / 'config'
config2.mkdir()
(config2 / 'config.json').write_text(json.dumps({'work_alerts': False, 'language': 'en', 'theme': 'report'}), encoding='utf-8')
server2, url2, port2 = serve(proj2, config2)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 900, 'height': 800})
        page.goto(url2)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=30000)
        page.select_option('#lec-theme', '__make')
        page.wait_for_selector(f'{BOX}:not([hidden])', timeout=8000)
        txt = page.inner_text(BOX)
        check("영어 화면 — 'Make my style', 칸 이름도 영어", 'Make my style' in txt and 'Line spacing' in txt and 'Based on' in txt and not re.search('[가-힣]', txt), txt[:300])
        box = page.locator(BOX).bounding_box()
        check('좁은 창(900px)에서도 창 안에', box and box['x'] >= 0 and box['x'] + box['width'] <= 900, box)
        browser.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤 (영어)')
finally:
    stop(server2, base2)
report()
