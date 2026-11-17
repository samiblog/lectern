"""설정의 범위 (D159)·설정 원문 보기 (D160): Lectern 설정은 전체에 하나 — 설정 창 머리의 한 줄, 다른 창·설정 파일에서 바뀐 값을 열린 창이 따른다
(독립창에서만 바꾼 화면 설정은 남는다). AI 도구에 건네는 것 — 넣을 곳 고르기(기본은 개인 폴더), 바뀌는 파일(전체 경로와 할 일),
지금 상태(시험용 개인 폴더의 정해진 파일만 — 설정 파일의 다른 값은 화면에 나오지 않는다), 요청 글이 고른 곳을 말한다."""
import json
import shutil
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, expect, fails, report, serve, stop, until

base = Path(tempfile.mkdtemp(prefix='lec-aiscope-'))
proj = base / '보고서'
config = base / 'config'
home = base / 'home'
(proj / 'docs').mkdir(parents=True)
(proj / 'docs' / 'a.md').write_text('# 글\n\n첫째 문단입니다.\n\n## 둘째\n\n둘째 문단입니다.\n', encoding='utf-8')
(proj / '.claude').mkdir()
(proj / '.claude' / 'settings.local.json').write_text(json.dumps({'outputStyle': '리서치 글쓰기', 'permissions': {'allow': ['Bash(SECRET_RULE:*)']}}), encoding='utf-8')
c = home / '.claude'
(c / 'rules').mkdir(parents=True)
(c / 'rules' / 'lectern.md').write_text('## 문서 (Lectern 으로 읽음)\n', encoding='utf-8')
(c / 'settings.json').write_text(json.dumps({'outputStyle': 'Explanatory', 'env': {'SECRET_TOKEN': 'abc'}}, indent=2), encoding='utf-8')   # Claude Code 처럼 줄을 나눠
(c / 'output-styles').mkdir()
style = (ROOT / 'web' / 'help' / 'research-writing.md').read_text(encoding='utf-8')
(c / 'output-styles' / 'research-writing.md').write_text(style.rstrip('\n') + '\n\n## 내 문체\n\n- 공통: 합니다체\n', encoding='utf-8')
for name in ('pptx-to-lectern', 'lectern-to-pptx'):
    shutil.copytree(ROOT / 'skills' / name, c / 'skills' / name, ignore=shutil.ignore_patterns('__pycache__'))
(c / 'skills' / 'lectern-to-pptx' / 'SKILL.md').write_text('옛 판\n', encoding='utf-8')

ROWS = "(id) => [...document.querySelectorAll(id + ' li')].map((li) => [li.querySelector('.ai-act').textContent, li.querySelector('.ai-path').textContent, li.querySelector('small')?.textContent || ''])"
TEXT = "(sel) => document.querySelector(sel)?.textContent.trim() || ''"


def rows(page, item):
    return page.evaluate(ROWS, f'#lec-{item}-files')


def text(page, sel):
    return page.evaluate(TEXT, sel)


def saved():
    try:
        return json.loads((config / 'config.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def open_settings(page):
    if page.evaluate("() => document.querySelector('#lec-settings').hidden"):
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
    until(page, lambda: '확인 중…' not in page.inner_text('#lec-set-content'))


def prompt(page, item):
    page.click(f'#lec-{item}-prompt')
    page.wait_for_timeout(250)
    return page.evaluate('() => navigator.clipboard.readText()')


def var(page, name):
    return page.evaluate(f"() => getComputedStyle(document.documentElement).getPropertyValue('{name}').trim()")


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
        page.evaluate("() => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: 'docs/a.md' }))")
        page.wait_for_selector('#lec-view h1')

        print('[설정 창 — 전체에 하나, AI 도구에 건네는 것]')
        open_settings(page)
        check('머리의 한 줄', text(page, '#lec-settings .set-scope') == '여기의 설정은 Lectern 전체에 듣습니다 — 모든 폴더와 창')
        page.click('#lec-settings .set-nav button[data-set="ai"]')
        subs = page.evaluate("() => [...document.querySelectorAll('#lec-settings .set-sub')].map((h) => h.textContent)")
        check('AI 도구 분류의 두 작은 제목', subs == ['Lectern 설정', 'AI 도구에 건네는 것'], subs)
        checked = lambda name: page.evaluate(f"() => document.querySelector('#lec-settings input[name=\"{name}\"]:checked')?.value")  # noqa: E731
        check('기본: 알려 주기·스킬은 모든 폴더, 글쓰기 스타일은 이 폴더에서', [checked('ai_scope_guide'), checked('ai_scope_skills'), checked('ai_style_where')] == ['all', 'all', 'folder'])
        labs = page.evaluate("() => [...document.querySelectorAll('#lec-settings .ai-where')].map((g) => [...g.querySelectorAll('label:not([hidden]) .ai-lab')].map((x) => x.textContent))")
        check('단추 이름에 폴더 이름', labs == [['모든 폴더 (개인)', '보고서 폴더만'], ['모든 폴더 (개인)', '보고서 폴더만'], ['보고서 폴더에서 켜기', '모든 폴더에서 켜기', '보고서 폴더에서 끄기']], labs)
        check('고른 것의 설명이 아래에', '이 PC 의 모든 폴더에서 읽힙니다' in page.inner_text('#lec-settings .ai-where >> nth=0 >> xpath=..'))

        print('[바뀌는 파일 — 지금 상태]')
        check('알려 주기: 개인 규칙 파일 — 있으니 바꿈', rows(page, 'aiguide') == [['바꿈', P(home, '.claude', 'rules', 'lectern.md'), '지금 것을 새 요약으로']], rows(page, 'aiguide'))
        sk = rows(page, 'skills')
        check('스킬: 같음·다름·없음', [r[0] for r in sk] == ['그대로', '바꿈', '새로 만듦'] and sk[1][1] == P(home, '.claude', 'skills', 'lectern-to-pptx') and sk[1][2] == 'Lectern 의 것과 다름', sk)
        ws = rows(page, 'wstyle')
        check('글쓰기 스타일: 파일 그대로, 끝의 내 문체는 옮김, 폴더 값은 이미 그대로',
              [r[0] for r in ws] == ['그대로', '옮김', '그대로'] and ws[0][1] == P(home, '.claude', 'output-styles', 'research-writing.md')
              and ws[2][1] == P(proj, '.claude', 'settings.local.json') and ws[2][2] == '"outputStyle": "리서치 글쓰기"', ws)
        now = text(page, '#lec-wstyle-now')
        check('지금 이 폴더에서 듣는 스타일과 모든 폴더의 기본', '리서치 글쓰기 (이 폴더의 settings.local.json)' in now and '모든 폴더의 기본: Explanatory' in now, now)
        vo = rows(page, 'voice')
        check('내 문체: 개인 규칙 파일을 새로, 스타일 끝의 절을 옮김', [r[0] for r in vo] == ['새로 만듦', '옮김'] and vo[0][1] == P(home, '.claude', 'rules', '내-문체.md'), vo)
        dom = page.inner_text('#lec-settings')
        check('설정 파일의 다른 값은 화면에 없다', 'SECRET' not in dom and 'permissions' not in dom and 'abc' not in dom)
        check('경고는 모든 폴더를 고를 때만', page.locator('#lec-wstyle-warn').is_hidden())

        print('[요청 글 — 고른 곳을 말한다]')
        g = prompt(page, 'aiguide')
        check('알려 주기 (모든 폴더): 개인 규칙 파일 하나, 내 CLAUDE.md 는 고치지 않게', '~/.claude/rules/lectern.md' in g and '~/.claude/CLAUDE.md 는 고치지 마' in g and '알려 주고' in g, g[:200])
        page.check('#lec-settings input[name="ai_scope_guide"][value="folder"]')
        until(page, lambda: saved().get('ai_scope_guide') == 'folder')
        check('이 폴더만: 그 폴더의 CLAUDE.md 를 새로 — 형식 규칙은 개인 폴더에 있어 빼고',
              rows(page, 'aiguide') == [['새로 만듦', P(proj, 'CLAUDE.md'), '이 폴더의 읽는 사람·목적']], rows(page, 'aiguide'))
        g = prompt(page, 'aiguide')
        check('요청: 이 프로젝트의 CLAUDE.md, 형식 규칙은 넣지 않게', '이 프로젝트의 CLAUDE.md' in g and '형식 규칙은 내 개인 폴더' in g and '넣지 마' in g, g[-260:])
        page.check('#lec-settings input[name="ai_scope_skills"][value="folder"]')
        sk = rows(page, 'skills')
        check('스킬 이 폴더만: 그 폴더의 .claude/skills — 개인 스킬이 먼저 쓰인다고 알림',
              [r[0] for r in sk] == ['새로 만듦'] * 3 + ['그대로'] and sk[0][1] == P(proj, '.claude', 'skills', 'pptx-to-lectern') and '먼저 쓰입니다' in sk[3][2], sk)
        s = prompt(page, 'skills')
        check('스킬 요청: 이 프로젝트의 .claude/skills, 없는 것과 다른 것만', '이 프로젝트의 .claude/skills' in s and '없는 것과 다른 것만' in s and '그쪽이 먼저 쓰인다' in s, s[-200:])
        w = prompt(page, 'wstyle')
        check('글쓰기 요청 (이 폴더): 설치하고 그 폴더의 settings.local.json 에 한 값', '~/.claude/output-styles/' in w and '.claude/settings.local.json 에 "outputStyle": "리서치 글쓰기" 한 값만' in w and P(home, '.claude', 'rules', '내-문체.md') in w, w[-300:])
        page.check('#lec-settings input[name="ai_style_where"][value="all"]')
        until(page, lambda: saved().get('ai_style_where') == 'all')
        check('모든 폴더에서 켜기: 경고', page.locator('#lec-wstyle-warn').is_visible())
        ws = rows(page, 'wstyle')
        check('바뀌는 파일: 개인 settings.json 에 한 값, 이 폴더의 값이 이긴다고 알림',
              ws[2][:2] == ['한 값 적기', P(home, '.claude', 'settings.json')] and ws[3][0] == '그대로' and '이 폴더에서는 그것이 듣습니다' in ws[3][2], ws)
        w = prompt(page, 'wstyle')
        check('글쓰기 요청 (모든 폴더): ~/.claude/settings.json, 코드 폴더는 Default 로', '~/.claude/settings.json 에 "outputStyle": "리서치 글쓰기" 한 값만' in w and '"outputStyle": "Default"' in w, w[-300:])
        page.check('#lec-settings input[name="ai_style_where"][value="off"]')
        ws = rows(page, 'wstyle')
        check('이 폴더에서 끄기: 스타일 파일은 건드리지 않고 폴더에 Default', ws == [['한 값 적기', P(proj, '.claude', 'settings.local.json'), '"outputStyle": "Default"']], ws)
        w = prompt(page, 'wstyle')
        check('끄기 요청', '기본 출력 스타일' in w and '"outputStyle": "Default" 한 값만' in w and 'output-styles' not in w, w)
        check('요청 글은 한 줄', all('\n' not in x for x in (g, s, w)))

        print('[Codex — 도구마다 자리]')
        page.check('#lec-settings input[name="ai_tool"][value="codex"]')
        until(page, lambda: saved().get('ai_tool') == 'codex')
        until(page, lambda: '확인 중…' not in page.inner_text('#lec-set-content'))
        check('끄기는 Claude Code 만 — 단추가 숨고 이 폴더로', page.locator('#lec-settings input[name="ai_style_where"][value="off"]').evaluate('(x) => x.closest("label").hidden') and checked('ai_style_where') == 'folder')
        sk = rows(page, 'skills')
        check('스킬 이 폴더만: .agents/skills', sk[0][1] == P(proj, '.agents', 'skills', 'pptx-to-lectern') and len(sk) == 3, sk)
        page.check('#lec-settings input[name="ai_scope_skills"][value="all"]')
        sk = rows(page, 'skills')
        check('스킬 모든 폴더: ~/.agents/skills', sk[0][1] == P(home, '.agents', 'skills', 'pptx-to-lectern'), sk)
        page.check('#lec-settings input[name="ai_scope_guide"][value="all"]')
        check('알려 주기 모든 폴더: ~/.codex/AGENTS.md 를 새로', rows(page, 'aiguide')[0][:2] == ['새로 만듦', P(home, '.codex', 'AGENTS.md')], rows(page, 'aiguide'))
        page.check('#lec-settings input[name="ai_tool"][value="claude"]')
        until(page, lambda: saved().get('ai_tool') == 'claude')
        until(page, lambda: '확인 중…' not in page.inner_text('#lec-set-content'))

        print('[설정 원문 보기 — 읽기만, 설명 줄은 번호 없이 (D160)]')
        page.click('#lec-settings .set-nav button[data-set="more"]')
        page.click('#lec-settings-raw')
        page.wait_for_selector('#lec-raw:not([hidden]) .raw-line')
        groups = page.evaluate("() => [...document.querySelectorAll('#lec-raw-list .raw-group')].map((g) => g.textContent)")
        check('목록의 묶음', groups == ['Lectern', 'Claude Code — 개인 폴더', '이 폴더 — 보고서', 'Lectern 에 든 것'], groups)
        check('처음은 Lectern 설정', page.evaluate("() => document.querySelector('#lec-raw-list .raw-item.on')?.dataset.id") == 'config' and text(page, '#lec-raw-path') == str(config / 'config.json'))
        nums = page.evaluate("() => [...document.querySelectorAll('#lec-raw-text .raw-line:not(.raw-note) .raw-t')].map((x) => x.textContent)")
        check('원문 줄은 파일 그대로', nums == (config / 'config.json').read_text(encoding='utf-8').split('\n'), len(nums))
        note = page.evaluate("""() => { const t = [...document.querySelectorAll('#lec-raw-text .raw-line')];
          const i = t.findIndex((x) => x.textContent.includes('"language"')); const n = t[i - 1];
          return [n.classList.contains('raw-note'), n.querySelector('.raw-n').textContent, n.querySelector('.raw-t').textContent]; }""")
        check('열쇠 앞의 설명 줄 — 번호 없이 // 로', note[0] and note[1] == '' and note[2].startswith('// 화면 언어') and "바꾸는 곳: 설정 창 '일반'" in note[2], note)
        page.click('#lec-raw-list .raw-item[data-id="csettings"]')
        until(page, lambda: text(page, '#lec-raw-path') == P(home, '.claude', 'settings.json'))
        raw = page.inner_text('#lec-raw-text')
        check('Claude Code 개인 설정: 원문 그대로, 비밀 값 조심 안내', 'SECRET_TOKEN' in raw and '비밀 값이 있을 수 있으니' in raw and '// 출력 스타일' in raw, raw[:300])
        page.click('#lec-raw-list .raw-item[data-id="skill:lectern-to-pptx"]')
        until(page, lambda: page.locator('#lec-raw-files .raw-file').count() > 0)
        check('스킬: SKILL.md 먼저, 폴더의 파일들', page.evaluate("() => document.querySelector('#lec-raw-files .raw-file.on')?.textContent") == 'SKILL.md'
              and page.locator('#lec-raw-text .raw-line:not(.raw-note)').first.inner_text().endswith('옛 판'))
        script = page.evaluate("() => [...document.querySelectorAll('#lec-raw-files .raw-file')].map((b) => b.textContent).find((x) => x.endsWith('.py'))")
        page.click(f'#lec-raw-files .raw-file[data-f="{script}"]')
        until(page, lambda: text(page, '#lec-raw-path').endswith(script.replace('/', '\\')))
        check('스킬의 프로그램도 읽는다 (설명 줄 없이)', page.locator('#lec-raw-text .raw-note').count() == 0 and page.locator('#lec-raw-text .raw-line').count() > 5)
        page.click('#lec-raw-list .raw-item[data-id="skill:lectern-to-docx"]')
        until(page, lambda: '파일이 없습니다' in page.inner_text('#lec-raw-text'))
        check('없는 것은 흐리게 — 없음', 'missing' in page.get_attribute('#lec-raw-list .raw-item[data-id="skill:lectern-to-docx"]', 'class'))
        page.keyboard.press('Escape')
        check('Esc — 원문 보기만 닫고 설정 창은 남는다', page.locator('#lec-raw').is_hidden() and page.locator('#lec-settings').is_visible())
        page.click('#lec-settings .set-nav button[data-set="ai"]')
        page.click('#lec-wstyle-raw')
        page.wait_for_selector('#lec-raw:not([hidden])')
        until(page, lambda: text(page, '#lec-raw-path') == P(home, '.claude', 'output-styles', 'research-writing.md'))
        check('글쓰기 스타일의 원문 보기 — 설치한 스타일을 먼저', page.evaluate("() => document.querySelector('#lec-raw-list .raw-item.on')?.dataset.id") == 'style:research-writing.md')
        page.keyboard.press('Escape')
        page.click('#lec-voice-raw')
        until(page, lambda: text(page, '#lec-raw-path') == P(home, '.claude', 'rules', '내-문체.md'))
        check('내 문체의 원문 보기 — 아직 없는 노트', '파일이 없습니다' in page.inner_text('#lec-raw-text'))
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')

        print('[다른 창이 설정을 따른다]')
        two = ctx.new_page()
        two.on('pageerror', lambda e: errors.append(str(e)[:300]))
        two.goto(url)
        two.wait_for_selector('#lec-view h1', timeout=20000)
        scale = var(two, '--md-scale')
        page.click('#lec-text-bigger')
        expect(two, '글자 크기를 키우면 다른 창도', lambda: text(two, '#lec-text-reset') == '110%' and var(two, '--md-scale') != scale, lambda: text(two, '#lec-text-reset'))
        page.select_option('#lec-theme', 'paper')
        expect(two, '스타일을 바꾸면 다른 창도', lambda: two.evaluate('() => document.documentElement.dataset.theme') == 'paper')
        page.keyboard.press('Alt+l')
        expect(two, '줄 번호도', lambda: two.evaluate("() => document.documentElement.classList.contains('line-numbers')"))
        page.keyboard.press('Alt+l')
        expect(two, '— 끄면 끈다', lambda: not two.evaluate("() => document.documentElement.classList.contains('line-numbers')"))
        page.click('#lec-text-bigger')
        page.click('#lec-text-bigger')
        page.click('#lec-text-smaller')
        page.wait_for_timeout(2500)
        check('빠르게 눌러도 이 창의 값이 되돌아가지 않는다', text(page, '#lec-text-reset') == '120%' and text(two, '#lec-text-reset') == '120%', [text(page, '#lec-text-reset'), text(two, '#lec-text-reset')])
        two.keyboard.press('Control+,')
        two.wait_for_selector('#lec-settings:not([hidden])')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        page.check('#lec-settings input[data-key="vi_keys"]')
        expect(two, '열린 설정 창의 칸도 따른다', lambda: two.is_checked('#lec-settings input[data-key="vi_keys"]'))
        page.uncheck('#lec-settings input[data-key="vi_keys"]')
        page.check('#lec-settings input[name="ai_scope_skills"][value="folder"]')
        expect(two, '— 넣을 곳도', lambda: two.is_checked('#lec-settings input[name="ai_scope_skills"][value="folder"]'))
        page.keyboard.press('Escape')
        two.keyboard.press('Escape')

        print('[설정 파일을 고쳐도]')
        data = saved()
        data['doc_width'] = 1.5
        (config / 'config.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        expect(page, '고친 문서 폭이 두 창에', lambda: text(page, '#lec-width-reset') == '폭 150%' and text(two, '#lec-width-reset') == '폭 150%', lambda: [text(page, '#lec-width-reset'), text(two, '#lec-width-reset')], ms=6000)

        print('[독립창에서만 바꾼 화면 설정은 남는다]')
        pid = page.evaluate("() => import('/static/js/store.js').then((m) => m.S.tab.id)")
        solo = ctx.new_page()
        solo.on('pageerror', lambda e: errors.append(str(e)[:300]))
        solo.goto(f'{url}?solo={pid}&w=edgesolo&type=doc&path=docs/a.md')
        solo.wait_for_selector('#lec-view h1', timeout=20000)
        check('독립창은 지금 설정으로 연다', text(solo, '#lec-text-reset') == '120%', text(solo, '#lec-text-reset'))
        solo.click('#lec-text-bigger')
        check('독립창의 글자 크기는 그 창에서만', text(solo, '#lec-text-reset') == '135%' and saved().get('font_scale') == 1.2)
        page.select_option('#lec-theme', 'default')
        expect(solo, '메인 창의 스타일은 독립창도 따른다', lambda: solo.evaluate('() => document.documentElement.dataset.theme') == 'default')
        page.wait_for_timeout(1500)
        check('— 독립창의 글자 크기는 남는다', text(solo, '#lec-text-reset') == '135%', text(solo, '#lec-text-reset'))
        page.click('#lec-text-smaller')
        expect(solo, '메인 창이 글자 크기를 바꾸면 그때 따른다', lambda: text(solo, '#lec-text-reset') == '110%', lambda: text(solo, '#lec-text-reset'))
        check('화면 스크립트 오류 없음', not errors, errors[:3])

        print('[열린 폴더가 없으면]')
        three = ctx.new_page()
        three.goto(url)
        three.wait_for_selector('#lec-tree .row.file', timeout=20000)
        three.evaluate("() => import('/static/js/store.js').then((m) => { m.S.config.ai_scope_guide = 'folder'; })")
        three.evaluate("() => import('/static/js/store.js').then((m) => { m.S.tab = null; })")
        three.keyboard.press('Control+,')
        three.wait_for_selector('#lec-settings:not([hidden])')
        until(three, lambda: '확인 중…' not in three.inner_text('#lec-set-content'))
        check('폴더 쪽 단추는 고를 수 없고 모든 폴더로', three.is_disabled('#lec-settings input[name="ai_scope_guide"][value="folder"]') and three.is_checked('#lec-settings input[name="ai_scope_guide"][value="all"]'))
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
