"""0.90.0 — 빌드본·설치본 실제 창(WebView2)에서: 메인 창에서 바꾼 설정을 열린 독립창이 따른다, 고친 설정 파일도,
독립창에서만 바꾼 글자 크기는 남는다, 설정 원문 보기, 설정 창 머리의 한 줄과 'AI 도구에 건네는 것'(시험용 개인 폴더 — 바뀌는 파일·지금 상태).
  python real090.py --exe <Lectern.exe>"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from playwright.sync_api import sync_playwright

import realwin as R

base = Path(tempfile.mkdtemp(prefix='lec-real090-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
home = base / 'home'
(home / '.claude' / 'rules').mkdir(parents=True)
(home / '.claude' / 'rules' / 'lectern.md').write_text('## 문서 (Lectern 으로 읽음)\n', encoding='utf-8')
(home / '.claude' / 'settings.json').write_text(json.dumps({'outputStyle': 'Explanatory', 'env': {'SECRET_TOKEN': 'abc'}}), encoding='utf-8')
os.environ['LECTERN_HOME'] = str(home)   # launch 가 os.environ 을 넘긴다 — 이 PC 의 실제 ~/.claude 를 읽지 않게
proj = base / '보고서'
proj.mkdir()
(proj / 'a.md').write_text('# 가 문서\n\n첫째 문단.\n\n## 둘째\n\n둘째 문단.\n', encoding='utf-8')
(proj / 'b.md').write_text('# 나 문서\n\n다른 글.\n', encoding='utf-8')


def saved():
    for _ in range(40):
        try:
            return json.loads((config / 'config.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            time.sleep(0.05)
    return {}


proc, cdp = R.launch(proj, config)
try:
    with sync_playwright() as p:
        R.CONN.update(pw=p, cdp=cdp)
        b = None
        for _ in range(120):
            try:
                b = p.chromium.connect_over_cdp(f'http://127.0.0.1:{cdp}')
                break
            except Exception:
                time.sleep(0.5)
        page = R.wait(lambda: R.app_page(b), 60)
        page.wait_for_selector('#lec-tree .row.file', timeout=40000)
        page.wait_for_timeout(1500)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        version = page.evaluate("() => document.querySelector('meta[name=lec-version]')?.content || ''")
        R.check(f'판 — {version}', version == R.VERSION, version)
        text = lambda pg, sel: pg.evaluate('(s) => document.querySelector(s)?.textContent.trim() || ""', sel)  # noqa: E731
        R.open_doc(page, 'b.md')
        R.open_doc(page, 'a.md')

        print('[독립창]')
        page.evaluate("() => import('/static/js/doctabs.js').then((m) => m.moveToWindow())")
        solo = R.new_window(b, None)
        R.check('독립창이 떴다', solo is not None)
        solo.wait_for_selector('#lec-view h1', timeout=20000)
        solo.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.bring_to_front()
        page.click('#lec-text-bigger')
        R.check('메인 창의 글자 크기를 독립창이 따른다', R.wait(lambda: text(solo, '#lec-text-reset') == '110%', 6), text(solo, '#lec-text-reset'))
        page.select_option('#lec-theme', 'paper')
        R.check('스타일도', R.wait(lambda: solo.evaluate('() => document.documentElement.dataset.theme') == 'paper', 6))
        solo.click('#lec-text-bigger')
        R.check('독립창에서만 키운 글자 크기는 그 창에서만 (저장하지 않는다)', text(solo, '#lec-text-reset') == '120%' and saved().get('font_scale') == 1.1, (text(solo, '#lec-text-reset'), saved().get('font_scale')))
        page.select_option('#lec-theme', 'default')
        R.wait(lambda: solo.evaluate('() => document.documentElement.dataset.theme') == 'default', 6)
        time.sleep(1.5)
        R.check('— 메인 창이 다른 설정을 바꿔도 남는다', text(solo, '#lec-text-reset') == '120%', text(solo, '#lec-text-reset'))

        print('[설정 파일을 고쳐도]')
        data = saved()
        data['doc_width'] = 1.5
        (config / 'config.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        R.check('두 창이 고친 문서 폭으로', R.wait(lambda: text(page, '#lec-width-reset') == '폭 150%' and text(solo, '#lec-width-reset') == '폭 150%', 8),
                (text(page, '#lec-width-reset'), text(solo, '#lec-width-reset')))

        print('[설정 창]')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        R.check('머리의 한 줄', text(page, '#lec-settings .set-scope') == '여기의 설정은 Lectern 전체에 듣습니다 — 모든 폴더와 창')
        page.click('#lec-settings .set-nav button[data-set="ai"]')
        R.wait(lambda: '확인 중…' not in page.inner_text('#lec-set-content'), 8)
        guide = page.evaluate("() => [...document.querySelectorAll('#lec-aiguide-files li')].map((li) => li.textContent)")
        R.check('알려 주기: 시험용 개인 폴더의 규칙 파일을 바꿈', len(guide) == 1 and guide[0].startswith('바꿈') and str(home / '.claude' / 'rules' / 'lectern.md') in guide[0], guide)
        now = text(page, '#lec-wstyle-now')
        R.check('지금 듣는 스타일', 'Explanatory (개인 설정)' in now, now)
        R.check('설정 파일의 다른 값은 보이지 않는다', 'SECRET' not in page.inner_text('#lec-settings'))
        print('[설정 원문 보기]')
        page.click('#lec-settings .set-nav button[data-set="more"]')
        page.click('#lec-settings-raw')
        R.check('원문 보기가 열린다', R.wait(lambda: page.locator('#lec-raw:not([hidden]) .raw-line').count() > 0, 8))
        lines = page.evaluate("() => [...document.querySelectorAll('#lec-raw-text .raw-line:not(.raw-note) .raw-t')].map((x) => x.textContent)")
        R.check('원문 줄은 config.json 그대로', lines == (config / 'config.json').read_text(encoding='utf-8').split('\n'), len(lines))
        R.check('설명 줄이 있다 (번호 없이)', page.locator('#lec-raw-text .raw-note').count() > 50 and page.evaluate("() => document.querySelector('#lec-raw-text .raw-note .raw-n').textContent") == '')
        page.click('#lec-raw-list .raw-item[data-id="lskill:lectern-to-docx"]')
        R.check('설치 폴더에 든 스킬도', R.wait(lambda: page.locator('#lec-raw-files .raw-file').count() > 3, 8))
        page.screenshot(path=str(R.HERE / 'real090.png'))
        page.keyboard.press('Escape')
        R.check('Esc 로 원문 보기만 닫힌다', page.locator('#lec-raw').is_hidden() and page.locator('#lec-settings').is_visible())
        page.keyboard.press('Escape')
        R.check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    R.fails.append('예외')
finally:
    subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True)
    time.sleep(1)
    shutil.rmtree(base, ignore_errors=True)
print(f'\n{R.count}개 중 실패 {len(R.fails)}개', R.fails)
