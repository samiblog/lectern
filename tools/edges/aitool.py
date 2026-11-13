"""쓰는 AI 도구 (D138): 설정에서 Claude Code·Codex·Antigravity·OpenCode·여럿을 고르면 화면의 이름과 요청 글(지시 파일·스킬 폴더·글쓰기 규칙)이
따라 바뀐다, 다시 불러와도 남는다, 영어 화면, 멈춘 프로그램의 이어 가기 명령.
터미널 붙여 넣기: 붙여넣기 모드를 켠 프로그램에는 표시 사이에 LF 줄바꿈으로 (Codex 가 CR 을 Enter 로 받아 보내 버리지 않게 —
실제 도구 대신 받은 바이트를 그대로 찍는 작은 프로그램으로 본다), 셸 프롬프트에는 지금처럼 묻고 CR 로"""
import json
import sys
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-aitool-'))
proj = base / 'proj'
config = base / 'config'
(proj / 'docs').mkdir(parents=True)
(proj / 'docs' / 'a.md').write_text('# 글\n\n첫째 문단입니다.\n\n둘째 문단입니다.\n', encoding='utf-8')
# 붙여넣기 모드를 켜고 받은 바이트를 그대로 찍는 프로그램 (Claude Code·Codex·Antigravity 자리)
ECHO = base / 'echo_tui.py'
ECHO.write_text(r'''
import ctypes, os, sys
k = ctypes.windll.kernel32
h = k.GetStdHandle(-10)
old = ctypes.c_uint32()
k.GetConsoleMode(h, ctypes.byref(old))
k.SetConsoleMode(h, 0x0200)   # ENABLE_VIRTUAL_TERMINAL_INPUT 만 — 줄 입력·에코 없이 받은 그대로
sys.stdout.write('\x1b[?2004hREADY\r\n')
sys.stdout.flush()
try:
    while True:
        b = os.read(0, 65536)
        sys.stdout.write('GOT ' + repr(b) + '\r\n')
        sys.stdout.flush()
        if b.strip() == b'q':
            break
finally:
    sys.stdout.write('\x1b[?2004lBYE\r\n')
    sys.stdout.flush()
    k.SetConsoleMode(h, old.value)
'''.lstrip(), encoding='utf-8')

SCREEN = "() => [...document.querySelectorAll('#lec-term .term-box:not([hidden]) .xterm-rows > div')].map((r) => r.textContent).join('')"
TEXT = "(sel) => document.querySelector(sel)?.textContent.trim() || ''"
TITLE = "(sel) => document.querySelector(sel)?.getAttribute('title') || ''"
EMIT = "(d) => import('/static/js/store.js').then((m) => m.emit('term-paste', d))"


def screen(page):
    # 받은 바이트는 여러 번에 나뉘어 오기도 한다 (표시와 글이 따로) — 이어 붙여 본다
    return ''.join(page.evaluate(SCREEN).split()).replace("'GOTb'", '')


def text(page, sel):
    return page.evaluate(TEXT, sel)


def clip(page):
    return page.evaluate('() => navigator.clipboard.readText()')


def open_settings(page):
    if page.evaluate("() => document.querySelector('#lec-settings').hidden"):
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')


def saved():
    try:   # 서버가 바꿔 끼우는 순간이면 잠깐 읽지 못한다
        return json.loads((config / 'config.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def choose(page, tool):
    open_settings(page)
    page.check(f'#lec-settings input[name="ai_tool"][value="{tool}"]')
    until(page, lambda: saved().get('ai_tool') == tool)


def prompts(page):
    """설정 창의 요청 글 셋 (복사 단추 → 클립보드)"""
    open_settings(page)
    out = {}
    for name in ('aiguide', 'skills', 'wstyle'):
        page.click(f'#lec-{name}-prompt')
        page.wait_for_timeout(250)
        out[name] = clip(page)
    return out


def lit_menu(page):
    """고른 줄의 우클릭 메뉴 글자들"""
    page.keyboard.press('Escape')
    page.locator('#lec-view p').nth(0).click()
    page.keyboard.press('Insert')
    box = page.locator('#lec-view p').nth(0).bounding_box()
    page.mouse.click(box['x'] + 20, box['y'] + box['height'] / 2, button='right')
    page.wait_for_selector('#lec-menu:not([hidden])')
    items = page.evaluate("() => [...document.querySelectorAll('#lec-menu button')].map((b) => b.querySelector('span')?.textContent || b.textContent)")
    page.keyboard.press('Escape')
    page.keyboard.press('Escape')
    return items


server, url, port = serve(proj, config)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1400, 'height': 900})
        ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=url.rstrip('/'))
        page = ctx.new_page()
        dialogs = []
        answer = {'ok': True}
        page.on('dialog', lambda d: (dialogs.append(d.message), d.accept() if answer['ok'] else d.dismiss()))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: 'docs/a.md' }))")
        page.wait_for_selector('#lec-view h1')
        guide_text = (ROOT / 'web' / 'help' / 'writing.md').read_text(encoding='utf-8')

        print('[기본은 Claude Code]')
        open_settings(page)
        check('고른 것은 Claude Code', page.is_checked('#lec-settings input[name="ai_tool"][value="claude"]'))
        check('알려 주기 칸의 이름', text(page, '#lec-aiguide-title') == 'Claude Code 에 Lectern 알려 주기', text(page, '#lec-aiguide-title'))
        check('설명에 CLAUDE.md', 'CLAUDE.md 에 규칙을 정리' in text(page, '#lec-aiguide-desc'), text(page, '#lec-aiguide-desc'))
        check('요청 단추', [text(page, f'#lec-{x}-prompt') for x in ('aiguide', 'skills', 'wstyle', 'mystyles')] == ['Claude Code용 요청 복사'] * 4)
        check('단추의 설명', 'Claude Code 에 붙여 넣습니다' in page.evaluate(TITLE, '#lec-skills-prompt'), page.evaluate(TITLE, '#lec-skills-prompt'))
        pr = prompts(page)
        check('알려 주기 요청: CLAUDE.md 에', '이 프로젝트의 CLAUDE.md 에 넣어 줘' in pr['aiguide'] and 'AGENTS.md' not in pr['aiguide'], pr['aiguide'][-200:])
        quoted = pr['aiguide'].split("안내 끝의 '")[1].split("'")[0]
        check('요청 글이 말하는 절이 작성 안내에 있다', f'## {quoted}' in guide_text, quoted)
        check('스킬 요청: ~/.claude/skills', '~/.claude/skills/ 로 복사해' in pr['skills'] and 'Claude Code 스킬 두 개' in pr['skills'], pr['skills'])
        check('글쓰기 요청: 출력 스타일', '~/.claude/output-styles/' in pr['wstyle'] and '/output-style' in pr['wstyle'], pr['wstyle'][:120])
        page.keyboard.press('Escape')
        check('담기의 단추', text(page, '#lec-basket-claude') == 'Claude 에 맡기기', text(page, '#lec-basket-claude'))
        items = lit_menu(page)
        check("고른 줄 메뉴: 'Claude로 보내기'", 'Claude로 보내기' in items, items)

        print('[Codex]')
        choose(page, 'codex')
        check('고르자마자 이름이 바뀐다', text(page, '#lec-aiguide-title') == 'Codex 에 Lectern 알려 주기' and text(page, '#lec-skills-prompt') == 'Codex용 요청 복사',
              [text(page, '#lec-aiguide-title'), text(page, '#lec-skills-prompt')])
        check('설명에 AGENTS.md', 'AGENTS.md 에 규칙을 정리' in text(page, '#lec-aiguide-desc'))
        check('글쓰기 칸의 설명: AGENTS.md 에', 'AGENTS.md 에 넣을지' in text(page, '#lec-wstyle-desc') and '/output-style' not in text(page, '#lec-wstyle-desc'), text(page, '#lec-wstyle-desc'))
        pr = prompts(page)
        check('알려 주기 요청: AGENTS.md 에', '이 프로젝트의 AGENTS.md 에 넣어 줘' in pr['aiguide'] and 'CLAUDE.md' not in pr['aiguide'], pr['aiguide'][-200:])
        check('스킬 요청: ~/.codex/skills', '~/.codex/skills/ 로 복사해' in pr['skills'] and 'Codex 스킬 두 개' in pr['skills'] and '.claude' not in pr['skills'], pr['skills'])
        check("글쓰기 요청: AGENTS.md 의 '글쓰기' 절", "AGENTS.md 의 '글쓰기' 절" in pr['wstyle'] and 'output-styles' not in pr['wstyle'], pr['wstyle'][:160])
        check('요청 글은 한 줄 (터미널에 여러 줄로 가지 않게)', all('\n' not in v for v in pr.values()))
        page.keyboard.press('Escape')
        check('담기의 단추', text(page, '#lec-basket-claude') == 'Codex 에 맡기기')
        check("고른 줄 메뉴: 'Codex로 보내기'", 'Codex로 보내기' in lit_menu(page))
        check('창 밖의 단추들', [text(page, x) for x in ('#lec-gallery-ask', '#lec-mdstyle-request', '#lec-pptx-ask', '#lec-html-ask')]
              == ['Codex 에게 템플릿 요청', 'Codex 에게 스타일 요청', 'Codex 에게 스타일 요청', 'Codex 에게 배치 요청'])
        stuck = page.evaluate("() => import('/static/js/terminal.js').then((m) => m.stuckMessage([{ name: 'git.exe', pid: 1 }]))")
        check('멈춘 프로그램 안내: codex resume --last', 'Codex 는 codex resume --last 로 이어 갑니다' in stuck and 'claude --continue' not in stuck, stuck[-80:])

        print('[Antigravity]')
        choose(page, 'antigravity')
        pr = prompts(page)
        check('스킬 요청: ~/.gemini/config/skills', '~/.gemini/config/skills/ 로 복사해' in pr['skills'] and 'Antigravity 스킬 두 개' in pr['skills'], pr['skills'])
        check('알려 주기 요청: AGENTS.md 에', '이 프로젝트의 AGENTS.md 에 넣어 줘' in pr['aiguide'])
        stuck = page.evaluate("() => import('/static/js/terminal.js').then((m) => m.stuckMessage([{ name: 'git.exe', pid: 1 }]))")
        check('멈춘 프로그램 안내: agy --continue', 'Antigravity 는 agy --continue 로 이어 갑니다' in stuck, stuck[-80:])
        page.keyboard.press('Escape')
        check("고른 줄 메뉴: 'Antigravity로 보내기'", 'Antigravity로 보내기' in lit_menu(page))

        print('[OpenCode]')
        choose(page, 'opencode')
        check('이름', text(page, '#lec-aiguide-title') == 'OpenCode 에 Lectern 알려 주기' and text(page, '#lec-wstyle-prompt') == 'OpenCode용 요청 복사',
              [text(page, '#lec-aiguide-title'), text(page, '#lec-wstyle-prompt')])
        pr = prompts(page)
        check('스킬 요청: ~/.config/opencode/skills', '~/.config/opencode/skills/ 로 복사해' in pr['skills'] and 'OpenCode 스킬 두 개' in pr['skills'], pr['skills'])
        check('알려 주기 요청: AGENTS.md 에', '이 프로젝트의 AGENTS.md 에 넣어 줘' in pr['aiguide'] and 'CLAUDE.md' not in pr['aiguide'])
        check("글쓰기 요청: AGENTS.md 의 '글쓰기' 절", "AGENTS.md 의 '글쓰기' 절" in pr['wstyle'] and 'output-styles' not in pr['wstyle'])
        stuck = page.evaluate("() => import('/static/js/terminal.js').then((m) => m.stuckMessage([{ name: 'git.exe', pid: 1 }]))")
        check('멈춘 프로그램 안내: opencode --continue', 'OpenCode 는 opencode --continue 로 이어 갑니다' in stuck, stuck[-80:])
        page.keyboard.press('Escape')
        check("고른 줄 메뉴: 'OpenCode로 보내기'", 'OpenCode로 보내기' in lit_menu(page))
        check('담기의 단추', text(page, '#lec-basket-claude') == 'OpenCode 에 맡기기')

        print('[여럿]')
        choose(page, 'any')
        check("이름은 'AI 도구'", text(page, '#lec-aiguide-title') == 'AI 도구 에 Lectern 알려 주기' and text(page, '#lec-skills-prompt') == 'AI 도구용 요청 복사',
              [text(page, '#lec-aiguide-title'), text(page, '#lec-skills-prompt')])
        pr = prompts(page)
        check('알려 주기 요청: 두 파일과 @AGENTS.md', all(x in pr['aiguide'] for x in ('CLAUDE.md', 'AGENTS.md', '@AGENTS.md 한 줄')), pr['aiguide'][-260:])
        check('스킬 요청: 네 폴더', all(x in pr['skills'] for x in ('~/.claude/skills', '~/.codex/skills', '~/.gemini/config/skills', '~/.config/opencode/skills')), pr['skills'])
        check('글쓰기 요청: 도구에 따라', 'Claude Code 면' in pr['wstyle'] and "AGENTS.md 의 '글쓰기' 절" in pr['wstyle'], pr['wstyle'][:200])
        page.keyboard.press('Escape')
        check('담기의 단추', text(page, '#lec-basket-claude') == 'AI 에 맡기기')
        check("고른 줄 메뉴: 'AI로 보내기'", 'AI로 보내기' in lit_menu(page))
        stuck = page.evaluate("() => import('/static/js/terminal.js').then((m) => m.stuckMessage([{ name: 'git.exe', pid: 1 }]))")
        check('멈춘 프로그램 안내: 네 도구', all(x in stuck for x in ('claude --continue', 'codex resume --last', 'agy --continue', 'opencode --continue')), stuck[-200:])

        print('[다시 불러와도 남는다]')
        choose(page, 'codex')
        page.keyboard.press('Escape')
        page.reload()
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        expect(page, '담기의 단추가 Codex', lambda: text(page, '#lec-basket-claude') == 'Codex 에 맡기기')
        open_settings(page)
        check('고른 것은 Codex', page.is_checked('#lec-settings input[name="ai_tool"][value="codex"]'))
        page.keyboard.press('Escape')

        print('[터미널 붙여 넣기 — 붙여넣기 모드를 켠 프로그램에는 LF 로]')
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: 'docs/a.md' }))")
        page.wait_for_selector('#lec-view h1')
        page.keyboard.press('Control+`')
        until(page, lambda: 'PS' in screen(page), ms=20000)
        page.keyboard.type(f'& "{sys.executable}" "{ECHO}"')
        page.keyboard.press('Enter')
        expect(page, '프로그램이 붙여넣기 모드를 켠다', lambda: 'READY' in screen(page) and page.evaluate(
            "() => import('/static/js/store.js').then((m) => m.S.tab.term.xterm.modes.bracketedPasteMode)"), ms=15000)
        dialogs.clear()
        page.evaluate(EMIT, 'first line\nsecond line\r\nthird')
        want = "GOTb'\\x1b[200~firstline\\nsecondline\\nthird\\x1b[201~"
        expect(page, '표시 사이에 LF 줄바꿈으로 (CR 없음)', lambda: want in screen(page), lambda: screen(page)[-300:])
        check('묻지 않는다 (붙여넣기 모드)', not dialogs, dialogs)
        check('Enter(CR)가 따로 가지 않았다', "\\r" not in screen(page).split('READY')[1], screen(page).split('READY')[1][-200:])
        page.evaluate("() => navigator.clipboard.writeText('clip one\\nclip two')")
        page.locator('#lec-term .term-box:not([hidden]) .xterm').click()
        page.keyboard.press('Control+v')
        expect(page, 'Ctrl+V 도 같은 길', lambda: "\\x1b[200~clipone\\ncliptwo\\x1b[201~" in screen(page), lambda: screen(page)[-300:])
        page.evaluate(EMIT, '@docs/a.md 3 ')
        expect(page, '한 줄은 그대로 (끝 공백까지)', lambda: "\\x1b[200~@docs/a.md3\\x1b[201~" in screen(page), lambda: screen(page)[-200:])
        page.locator('#lec-term .term-box:not([hidden]) .xterm').click()
        page.keyboard.type('q')
        expect(page, '프로그램이 끝나고 프롬프트로', lambda: 'BYE' in screen(page), ms=8000)

        print('[셸 프롬프트 — 지금처럼 묻고 줄마다]')
        until(page, lambda: not page.evaluate("() => import('/static/js/store.js').then((m) => m.S.tab.term.xterm.modes.bracketedPasteMode)"), ms=5000)
        dialogs.clear()
        answer['ok'] = False
        page.evaluate(EMIT, 'Write-Output aaa\nWrite-Output bbb')
        expect(page, '여러 줄이면 묻는다', lambda: any('2줄' in d for d in dialogs), lambda: dialogs)
        page.wait_for_timeout(500)
        check('그만두면 넣지 않는다', 'Write-Outputaaa' not in screen(page).split('BYE')[1], screen(page)[-200:])
        b.close()

    print('[영어 화면]')
    server.terminate()   # 설정을 바꿔 다시 띄운다 (임시 폴더는 그대로)
    server.wait(10)
    cfg = json.loads((config / 'config.json').read_text(encoding='utf-8'))
    cfg.update(language='en', ai_tool='codex')
    (config / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
    server, url, port = serve(proj, config)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 900})
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: 'docs/a.md' }))")
        page.wait_for_selector('#lec-view h1')
        check('Ask Codex', text(page, '#lec-basket-claude') == 'Ask Codex', text(page, '#lec-basket-claude'))
        check('Send to Codex', 'Send to Codex' in lit_menu(page))
        open_settings(page)
        check('Teach Codex about Lectern', text(page, '#lec-aiguide-title') == 'Teach Codex about Lectern' and text(page, '#lec-skills-prompt') == 'Copy request for Codex',
              [text(page, '#lec-aiguide-title'), text(page, '#lec-skills-prompt')])
        check('도구 고르기 칸의 영어', text(page, '#lec-aitool-title') == 'AI tool' and 'Several' in page.evaluate("() => document.querySelector('#lec-settings input[name=\"ai_tool\"][value=\"any\"]').parentElement.textContent"))
        hangul = page.evaluate("() => [...document.querySelectorAll('#lec-settings .opt-block, #lec-settings .opt-choice')].filter((x) => /[가-힣]/.test(x.textContent) && !x.querySelector('[translate=\"no\"]:not(span)')).map((x) => x.textContent.trim().slice(0, 60))")
        check('설정 창에 한국어가 남지 않는다', not [h for h in hangul if '한국어' not in h], hangul)
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
