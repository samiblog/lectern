"""글쓰기 스타일 고르기 (D161 — stylepick.js): 목록(Lectern 에 든 넷·Claude Code 기본·내 스타일·새로), 이런 글에·바뀌는 것·견본·설치 상태,
'이 스타일로'가 설정 ai_style 을 바꾸고 설정 창의 바뀌는 파일·요청 글이 그 스타일을 따른다, Claude Code 기본(끄기), 내 스타일(켜기만),
원문 보기, 새 스타일 만들기 요청, Codex 에서는 '글쓰기' 절, 영어 화면"""
import json
import shutil
import tempfile
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-stylepick-'))
proj = base / '보고서'
config = base / 'config'
home = base / 'home'
(proj / 'docs').mkdir(parents=True)
(proj / 'docs' / 'a.md').write_text('# 글\n\n첫째 문단입니다.\n', encoding='utf-8')
styles = home / '.claude' / 'output-styles'
styles.mkdir(parents=True)
shutil.copy(ROOT / 'web' / 'help' / 'research-writing.md', styles / 'research-writing.md')
(styles / 'terse.md').write_text('---\nname: 짧게\ndescription: 짧은 답만\n---\n\n짧게 답한다.\n', encoding='utf-8')
META = json.loads((ROOT / 'web' / 'help' / 'writing-styles.json').read_text(encoding='utf-8'))

TEXT = "(sel) => document.querySelector(sel)?.textContent.trim() || ''"
ROWS = "(id) => [...document.querySelectorAll(id + ' li')].map((li) => [li.querySelector('.ai-act').textContent, li.querySelector('.ai-path').textContent, li.querySelector('small')?.textContent || ''])"


def text(page, sel):
    return page.evaluate(TEXT, sel)


def saved():
    try:
        return json.loads((config / 'config.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def settled(page):
    until(page, lambda: '확인 중…' not in page.inner_text('#lec-set-content'))


def open_ai(page):
    if page.locator('#lec-settings').is_hidden():
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
    page.click('#lec-settings .set-nav button[data-set="ai"]')
    settled(page)


def open_pick(page):
    page.click('#lec-wstyle-pick')
    page.wait_for_selector('#lec-stylepick:not([hidden]) .raw-item')


def items(page):
    return page.evaluate("() => [...document.querySelectorAll('#lec-stylepick-list .raw-group, #lec-stylepick-list .raw-item')].map((x) => x.classList.contains('raw-group') ? '# ' + x.textContent : x.querySelector('span').textContent)")


def prompt(page):
    page.click('#lec-wstyle-prompt')
    page.wait_for_timeout(250)
    return page.evaluate('() => navigator.clipboard.readText()')


def P(*parts):
    return str(Path(*parts))


server, url, port = serve(proj, config, env={'LECTERN_HOME': str(home)})
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1400, 'height': 950})
        ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=url.rstrip('/'))
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)

        print('[설정 창의 글쓰기 스타일]')
        open_ai(page)
        check('고른 스타일은 리서치 글쓰기 (기본)', text(page, '#lec-wstyle-chosen') == '고른 스타일: 리서치 글쓰기', text(page, '#lec-wstyle-chosen'))
        check('스타일 고르기 단추', page.is_visible('#lec-wstyle-pick'))

        print('[고르기 창 — 목록]')
        open_pick(page)
        got = items(page)
        check('목록: Lectern 에 든 넷·Claude Code 기본·내 글쓰기 스타일·새로',
              got == ['# Lectern 에 든 스타일', '리서치 글쓰기', '업무 보고', '학술 글', '쉬운 설명', '# 스타일 없이', 'Claude Code 기본', '# 내 글쓰기 스타일', '짧게', '# 새로', '새 스타일 만들기…'], got)
        check('처음은 지금 고른 것 — 리서치 글쓰기, 고른 것 표시', page.evaluate("() => document.querySelector('#lec-stylepick-list .raw-item.on')?.dataset.id") == 'research'
              and '고른 것' in page.inner_text('#lec-stylepick-list .raw-item[data-id="research"]'))
        check('설치 상태 — 개인 폴더에 Lectern 의 것과 같음', '개인 폴더에 설치됨 — Lectern 의 것과 같음' in page.inner_text('#lec-stylepick-main'))

        print('[업무 보고]')
        page.click('#lec-stylepick-list .raw-item[data-id="brief"]')
        main = page.inner_text('#lec-stylepick-main')
        brief = next(s for s in META['styles'] if s['id'] == 'brief')
        check('이름·설명·이런 글에·바뀌는 것', main.startswith('업무 보고') and brief['use']['ko'] in main and page.locator('#lec-stylepick-main .pick-changes li').count() == len(brief['changes']['ko']), main[:200])
        if brief.get('sample'):
            check('견본 둘 — Claude Code 기본과 이 스타일', page.locator('#lec-stylepick-main .pick-text').count() == 2 and brief['sample']['request'] in main)
        check('아직 설치하지 않음', '아직 설치하지 않음' in main)
        page.click('#lec-stylepick-main [data-act="choose"]')
        check('이 스타일로 — 창이 닫히고 설정 창에 고른 스타일', page.locator('#lec-stylepick').is_hidden() and text(page, '#lec-wstyle-chosen') == '고른 스타일: 업무 보고')
        until(page, lambda: saved().get('ai_style') == 'brief')
        rows = page.evaluate(ROWS, '#lec-wstyle-files')
        check('바뀌는 파일: business-report.md 를 새로, 폴더에 업무 보고', rows[0][:2] == ['새로 만듦', P(home, '.claude', 'output-styles', 'business-report.md')]
              and rows[-1][2] == '"outputStyle": "업무 보고"', rows)
        w = prompt(page)
        check('요청 글: 업무 보고 파일과 그 이름', 'business-report.md' in w and '"outputStyle": "업무 보고"' in w and 'research-writing' not in w, w[:200])

        print('[Claude Code 기본 — 이 폴더에서 끄기]')
        open_pick(page)
        page.click('#lec-stylepick-list .raw-item[data-id="default"]')
        page.click('#lec-stylepick-main [data-act="default"]')
        until(page, lambda: saved().get('ai_style_where') == 'off')
        check('켤 곳이 이 폴더에서 끄기로', page.is_checked('#lec-settings input[name="ai_style_where"][value="off"]'))
        check('고른 스타일 줄도 Claude Code 기본', text(page, '#lec-wstyle-chosen') == '고른 스타일: Claude Code 기본', text(page, '#lec-wstyle-chosen'))
        open_pick(page)
        check('다시 열면 Claude Code 기본에 고른 것 표시', page.evaluate("() => document.querySelector('#lec-stylepick-list .raw-item.on')?.dataset.id") == 'default'
              and '고른 것' in page.inner_text('#lec-stylepick-list .raw-item[data-id="default"]'))

        print('[내 글쓰기 스타일]')
        page.click('#lec-stylepick-list .raw-item[data-id="mine:terse.md"]')
        check('내 스타일의 설명과 자리', '짧은 답만' in page.inner_text('#lec-stylepick-main') and P(home, '.claude', 'output-styles', 'terse.md') in page.inner_text('#lec-stylepick-main'))
        page.click('#lec-stylepick-main [data-act="choose"]')
        until(page, lambda: saved().get('ai_style') == 'mine:terse.md' and saved().get('ai_style_where') == 'folder')
        rows = page.evaluate(ROWS, '#lec-wstyle-files')
        check('내 글쓰기 스타일: 설치 없이 켜기만', rows[0] == ['그대로', P(home, '.claude', 'output-styles', 'terse.md'), '내 글쓰기 스타일'] and rows[-1][2] == '"outputStyle": "짧게"', rows)
        w = prompt(page)
        check('요청 글: 내 출력 스타일 짧게를 켜기', w.startswith('내 출력 스타일 짧게') and '"outputStyle": "짧게"' in w and '복사하기' not in w, w[:160])

        print('[원문 보기·새 스타일]')
        open_pick(page)
        page.click('#lec-stylepick-list .raw-item[data-id="academic"]')
        page.click('#lec-stylepick-main [data-act="raw"]')
        page.wait_for_selector('#lec-raw:not([hidden]) .raw-line')
        check('원문 보기 — 설치하지 않은 학술 글은 Lectern 에 든 것', text(page, '#lec-raw-path').endswith('academic-writing.md') and 'name: 학술 글' in page.inner_text('#lec-raw-text'))
        page.keyboard.press('Escape')
        check('Esc — 원문 보기만 닫힌다', page.locator('#lec-raw').is_hidden() and page.locator('#lec-stylepick').is_visible())
        page.click('#lec-stylepick-list .raw-item[data-id="new"]')
        page.click('#lec-stylepick-main [data-act="new-copy"]')
        page.wait_for_timeout(250)
        n = page.evaluate('() => navigator.clipboard.readText()')
        check('새 스타일 만들기 요청 — 안내의 경로', 'new-style.md' in n and n.endswith('원하는 글: '), n)
        check('— 저장한 뒤 설정 창을 다시 열면 나온다고', '설정 창을 다시 열면' in page.inner_text('#lec-stylepick-main'))
        page.keyboard.press('Escape')
        check('Esc — 고르기 창이 닫히고 설정 창은 남는다', page.locator('#lec-stylepick').is_hidden() and page.locator('#lec-settings').is_visible())

        print('[Codex — 글쓰기 절]')
        page.check('#lec-settings input[name="ai_tool"][value="codex"]')
        until(page, lambda: saved().get('ai_tool') == 'codex')
        settled(page)
        check('Codex: 내 글쓰기 스타일을 골라 두었어도 리서치 글쓰기로', text(page, '#lec-wstyle-chosen') == '고른 스타일: 리서치 글쓰기', text(page, '#lec-wstyle-chosen'))
        w = prompt(page)
        check('— 요청 글도 리서치 글쓰기의 글쓰기 절', 'research-writing.md' in w and 'terse' not in w, w[:200])
        open_pick(page)
        got = items(page)
        check('Codex: Claude Code 기본·내 글쓰기 스타일은 없다', got == ['# Lectern 에 든 스타일', '리서치 글쓰기', '업무 보고', '학술 글', '쉬운 설명', '# 새로', '새 스타일 만들기…'], got)
        page.click('#lec-stylepick-list .raw-item[data-id="plain"]')
        page.click('#lec-stylepick-main [data-act="choose"]')
        until(page, lambda: saved().get('ai_style') == 'plain')
        w = prompt(page)
        check("Codex 요청 글: 쉬운 설명을 AGENTS.md 의 '글쓰기' 절로", 'plain-explainer.md' in w and "'글쓰기' 절" in w and 'output-styles' not in w, w[:200])
        page.check('#lec-settings input[name="ai_tool"][value="claude"]')
        until(page, lambda: saved().get('ai_tool') == 'claude')
        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()

    print('[영어 화면]')
    server.terminate()
    server.wait(10)
    cfg = saved()
    cfg.update(language='en')
    (config / 'config.json').write_text(json.dumps(cfg), encoding='utf-8')
    server, url, port = serve(proj, config, env={'LECTERN_HOME': str(home)})
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1400, 'height': 950})
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        open_ai(page)
        open_pick(page)
        got = items(page)
        check('영어 목록', got[:5] == ['# Included in Lectern', 'Research writing', 'Business report', 'Academic writing', 'Plain explanation'], got)
        page.click('#lec-stylepick-list .raw-item[data-id="academic"]')
        main = page.inner_text('#lec-stylepick-main')
        academic = next(s for s in META['styles'] if s['id'] == 'academic')
        check('영어 설명', academic['use']['en'] in main and 'What changes' in main, main[:200])
        hangul = [x for x in page.evaluate("() => [...document.querySelectorAll('#lec-stylepick-main > :not(.pick-samples):not(.pick-request), #lec-stylepick-list')].map((x) => x.textContent)") if any('가' <= ch <= '힣' for ch in x.replace('짧게', '').replace('보고서', ''))]
        check('견본·사용자의 이름(내 스타일·폴더) 밖에는 한국어가 없다', not hangul, hangul[:2])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
