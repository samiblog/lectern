"""0.91.0 — 빌드본·설치본 실제 창(WebView2)에서: 글쓰기 스타일 고르기 창(넷·견본·설치 상태), 업무 보고로 고르기 → 바뀌는 파일,
Claude Code 기본, 내 글쓰기 스타일, 원문 보기, Esc 차례, 새 스타일 만들기 요청 (시험용 개인 폴더 — 실제 ~/.claude 는 읽지 않는다).
  python real091.py --exe <Lectern.exe>"""
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

base = Path(tempfile.mkdtemp(prefix='lec-real091-'))
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'language': 'ko', 'work_alerts': False}), encoding='utf-8')
home = base / 'home'
styles = home / '.claude' / 'output-styles'
styles.mkdir(parents=True)
(styles / 'weekly-brief.md').write_text('---\nname: 주간 요약\ndescription: 주간 회의 요약을 짧게\n---\n\n결정 사항과 할 일만 쓴다.\n', encoding='utf-8')
os.environ['LECTERN_HOME'] = str(home)
proj = base / '보고서'
proj.mkdir()
(proj / 'a.md').write_text('# 가 문서\n\n첫째 문단.\n', encoding='utf-8')


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
        text = lambda sel: page.evaluate('(s) => document.querySelector(s)?.textContent.trim() || ""', sel)  # noqa: E731
        items = lambda: page.evaluate("() => [...document.querySelectorAll('#lec-stylepick-list .raw-group, #lec-stylepick-list .raw-item')].map((x) => x.classList.contains('raw-group') ? '# ' + x.textContent : x.querySelector('span').textContent)")  # noqa: E731

        print('[설정 창]')
        page.keyboard.press('Control+,')
        page.wait_for_selector('#lec-settings:not([hidden])')
        page.click('#lec-settings .set-nav button[data-set="ai"]')
        R.wait(lambda: '확인 중…' not in page.inner_text('#lec-set-content'), 8)
        R.check('고른 스타일: 리서치 글쓰기 (기본)', text('#lec-wstyle-chosen') == '고른 스타일: 리서치 글쓰기', text('#lec-wstyle-chosen'))

        print('[고르기 창]')
        page.click('#lec-wstyle-pick')
        R.check('고르기 창이 열린다', R.wait(lambda: page.locator('#lec-stylepick:not([hidden]) .raw-item').count() > 0, 8))
        got = items()
        R.check('목록 — 넷·Claude Code 기본·내 글쓰기 스타일·새로',
                got == ['# Lectern 에 든 스타일', '리서치 글쓰기', '업무 보고', '학술 글', '쉬운 설명', '# 스타일 없이', 'Claude Code 기본', '# 내 글쓰기 스타일', '주간 요약', '# 새로', '새 스타일 만들기…'], got)
        box = page.evaluate("() => { const r = document.querySelector('#lec-stylepick .dialog-box').getBoundingClientRect(); return [r.width, r.height, innerWidth, innerHeight]; }")
        R.check('창이 넉넉하다 (화면 너비의 반 넘게)', box[0] > box[2] * 0.5, box)
        for sid in ('research', 'brief', 'academic', 'plain'):
            page.click(f'#lec-stylepick-list .raw-item[data-id="{sid}"]')
            n = page.locator('#lec-stylepick-main .pick-text').count()
            lens = page.evaluate("() => [...document.querySelectorAll('#lec-stylepick-main .pick-text')].map((x) => x.textContent.length)")
            R.check(f'{sid}: 견본 둘이 보인다', n == 2 and min(lens) > 200, lens)
            if sid == 'brief':
                page.screenshot(path=str(R.HERE / 'real091.png'))
        page.click('#lec-stylepick-list .raw-item[data-id="brief"]')
        R.check('업무 보고 — 아직 설치하지 않음', '아직 설치하지 않음' in page.inner_text('#lec-stylepick-main'))
        page.click('#lec-stylepick-main [data-act="choose"]')
        R.check('이 스타일로 — 설정 창으로, 고른 스타일이 업무 보고', R.wait(lambda: page.locator('#lec-stylepick').is_hidden() and text('#lec-wstyle-chosen') == '고른 스타일: 업무 보고', 6))
        R.check('— config.json 에 저장', R.wait(lambda: saved().get('ai_style') == 'brief', 6), saved().get('ai_style'))
        files = page.evaluate("() => [...document.querySelectorAll('#lec-wstyle-files li')].map((li) => li.textContent)")
        R.check('바뀌는 파일 — 시험용 개인 폴더의 business-report.md 를 새로, 폴더에 업무 보고',
                any(f.startswith('새로 만듦') and str(styles / 'business-report.md') in f for f in files) and any('"outputStyle": "업무 보고"' in f for f in files), files)

        print('[Claude Code 기본 · 내 글쓰기 스타일]')
        page.click('#lec-wstyle-pick')
        page.wait_for_selector('#lec-stylepick:not([hidden]) .raw-item')
        page.click('#lec-stylepick-list .raw-item[data-id="default"]')
        R.check('열린 폴더가 있으니 Claude Code 기본 단추를 누를 수 있다', page.is_enabled('#lec-stylepick-main [data-act="default"]'))
        page.click('#lec-stylepick-main [data-act="default"]')
        R.check('켤 곳이 끄기로, 고른 스타일 줄도', R.wait(lambda: saved().get('ai_style_where') == 'off' and text('#lec-wstyle-chosen') == '고른 스타일: Claude Code 기본', 6), (saved().get('ai_style_where'), text('#lec-wstyle-chosen')))
        page.click('#lec-wstyle-pick')
        page.wait_for_selector('#lec-stylepick:not([hidden]) .raw-item')
        page.click('#lec-stylepick-list .raw-item[data-id="mine:weekly-brief.md"]')
        page.click('#lec-stylepick-main [data-act="choose"]')
        R.check('내 글쓰기 스타일 — 다시 켜기로, 고른 스타일: 주간 요약', R.wait(lambda: saved().get('ai_style') == 'mine:weekly-brief.md' and saved().get('ai_style_where') == 'folder' and text('#lec-wstyle-chosen') == '고른 스타일: 주간 요약', 6))
        files = page.evaluate("() => [...document.querySelectorAll('#lec-wstyle-files li')].map((li) => li.textContent)")
        R.check('— 설치 없이 켜기만', any(f.startswith('그대로') and 'weekly-brief.md' in f for f in files) and any('"outputStyle": "주간 요약"' in f for f in files), files)

        print('[원문 보기 · Esc]')
        page.click('#lec-wstyle-pick')
        page.wait_for_selector('#lec-stylepick:not([hidden]) .raw-item')
        page.click('#lec-stylepick-list .raw-item[data-id="plain"]')
        page.click('#lec-stylepick-main [data-act="raw"]')
        R.check('원문 보기 — 설치 폴더에 든 쉬운 설명', R.wait(lambda: 'name: 쉬운 설명' in page.inner_text('#lec-raw-text'), 8))
        page.keyboard.press('Escape')
        R.check('Esc — 원문 보기만 닫힌다', page.locator('#lec-raw').is_hidden() and page.locator('#lec-stylepick').is_visible())
        page.keyboard.press('Escape')
        R.check('Esc — 고르기 창만 닫힌다', page.locator('#lec-stylepick').is_hidden() and page.locator('#lec-settings').is_visible())
        page.keyboard.press('Escape')
        R.check('Esc — 설정 창도', page.locator('#lec-settings').is_hidden())
        R.check('실제 ~/.claude 를 읽지 않았다 (시험용 폴더에 새 파일 없음)', sorted(x.name for x in styles.iterdir()) == ['weekly-brief.md'])
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
