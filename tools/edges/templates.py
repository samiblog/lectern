"""Lectern 슬라이드 템플릿 (D101)·pptx 로 전환 (D102): 갤러리, 새로 만들기, 새 장, 템플릿 바꾸기, 저장, 전환"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop

base = Path(tempfile.mkdtemp(prefix='lec-templates-'))
proj = base / 'proj'
config = base / 'config'
proj.mkdir()
(config / 'pptx-styles').mkdir(parents=True)
(proj / '보통.md').write_text('# 보통\n\n글입니다.\n', encoding='utf-8')
style_md = base / 'style.md'
style_md.write_text('---\nmarp: true\n---\n\n# 표지\n\n---\n\n## 둘째\n\n글\n', encoding='utf-8')
subprocess.run([sys.executable, str(ROOT / 'skills' / 'lectern-to-pptx' / 'scripts' / 'build_pptx.py'), str(style_md), '--out', str(config / 'pptx-styles' / '회사양식.pptx'), '--style', 'deck'],
               check=True, capture_output=True, env=os.environ | {'LECTERN_CONFIG_DIR': str(config)})

server, url, port = serve(proj, config)
extra = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1320, 'height': 860})
        page.on('pageerror', lambda e: extra.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)
        doc = proj / '보고서.md'
        cell_edit = '#lec-view .lec-line-edit'
        gallery = '#lec-gallery-list .lec-tpl'
        open_text = lambda: page.evaluate("[...document.querySelectorAll('.lec-line-edit')].map((e) => e.textContent)")
        names = lambda: [x.strip() for x in page.locator('.lec-tpl-name').all_inner_texts()]
        text = lambda: doc.read_text(encoding='utf-8')
        slide = lambda n: page.locator('#lec-view .lec-slide-wrap').nth(n - 1)
        menu = lambda n, name: (slide(n).click(button='right', position={'x': 40, 'y': 40}), page.wait_for_timeout(200), page.locator('#lec-menu button', has_text=name).first.click())

        def pick(*keys):
            page.wait_for_selector(gallery, timeout=6000)
            for k in keys:
                page.keyboard.press(k)
            page.keyboard.press('Enter')
            page.wait_for_timeout(900)

        print('[새로 만들기 — 첫 장의 템플릿]')
        page.keyboard.press('Control+n')
        page.wait_for_selector('#lec-insert-list li', timeout=4000)
        page.fill('#lec-insert-input', '취소할문서.md')
        page.wait_for_timeout(200)
        page.locator('#lec-insert-list li').first.click()
        page.wait_for_selector(gallery, timeout=6000)
        check('Lectern 슬라이드를 새로 만들면 갤러리가 뜬다', page.locator('#lec-gallery').is_visible() and '첫 장' in page.text_content('#lec-gallery-title'))
        check('기본 템플릿 12개', page.locator(gallery).count() == 12, names())
        check('번호와 이름이 나온다', names()[0].startswith('1') and '표지' in names()[0] and names()[11].startswith('12'), names())
        page.wait_for_function("document.querySelectorAll('.lec-tpl-view .lec-slide').length === 12", timeout=15000)
        check('미리보기는 실제 슬라이드다', page.locator('.lec-tpl-view .lec-slide.lec-grid').count() >= 8)
        page.wait_for_timeout(1500)
        check('미리보기에 차트가 그려진다', page.locator('.lec-tpl-view svg').count() >= 2)
        fit = page.evaluate("[...document.querySelectorAll('.lec-tpl-thumb')].every((t) => { const s = t.querySelector('.lec-slide'); if (!s) return false; const a = t.getBoundingClientRect(), b = s.getBoundingClientRect(); return Math.abs(a.width - b.width) < 3 && b.height <= a.height + 3; })")
        check('미리보기가 칸에 맞는다', fit)
        check('첫 장은 표지를 먼저 고른다', page.locator('.lec-tpl.sel .lec-tpl-name').inner_text().strip().startswith('1 '))
        if os.environ.get('LEC_SHOTS'):
            page.screenshot(path=str(Path(os.environ['LEC_SHOTS']) / '템플릿-갤러리.png'))
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)
        check('취소하면 만들지 않고 경로로 돌아간다', page.locator('#lec-gallery').is_hidden() and page.locator('#lec-insert').is_visible() and not (proj / '취소할문서.md').exists())
        page.fill('#lec-insert-input', '보고서.md')
        page.wait_for_timeout(200)
        page.locator('#lec-insert-list li').first.click()
        pick('5')
        page.wait_for_selector('#lec-view.lec-deck', timeout=8000)
        check('고른 템플릿으로 첫 장이 된다', '<!-- layout: two -->' in text() and 'vega-lite' in text() and text().startswith('---\nmarp: true\ntitle: 보고서\n'), text()[:90])
        check('슬라이드로 열린다', page.locator('#lec-view .lec-slide').count() == 1)
        page.wait_for_timeout(1200)

        print('[새 장 — 템플릿을 골라 이어 간다]')
        slide(1).locator('h2').click()
        page.keyboard.press('Control+m')
        page.wait_for_selector(gallery, timeout=6000)
        check('새 장의 갤러리', '새 장' in page.text_content('#lec-gallery-title'))
        check('새 장은 제목과 본문을 먼저 고른다', page.locator('.lec-tpl.sel .lec-tpl-name').inner_text().strip().startswith('3 '))
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)
        check('취소하면 장이 늘지 않는다', page.locator('#lec-view .lec-slide').count() == 1 and text().count('\n---\n') == 1)
        page.keyboard.press('Control+m')
        pick('1', '1')
        page.wait_for_selector(cell_edit, timeout=4000)
        check('번호 두 자리로 고른다', '| 항목 | 값 | 비고 |' in text() and page.locator('#lec-view .lec-slide').count() == 2)
        check('제목이 바로 열린다', open_text() == ['표가 말하는 결론을 씁니다'], open_text())
        page.keyboard.press('Control+a')
        page.keyboard.type('매출이 늘었다')
        page.keyboard.press('Enter')
        page.wait_for_timeout(900)
        check('제목을 쓰며 이어 간다', '## 매출이 늘었다' in text())

        print('[템플릿 바꾸기 — 글은 옮겨 담는다]')
        doc.write_text(text().replace('| 가 | 0 | 내용 |', '| 가 | 12 | 매출 |'), encoding='utf-8')
        page.wait_for_timeout(1800)
        before = text()
        menu(2, '템플릿 바꾸기')
        pick('7')
        after = text()
        check('제목이 그대로다', '## 매출이 늘었다' in after, after[-300:])
        check('새 배치가 된다', '<!-- layout: two -->' in after.split('\n---\n')[-1] and '<!-- layout: two-left -->' not in after, after[-300:])
        check('표가 칸에 옮겨진다', after.count('| 항목 | 값 | 비고 |') == 1 and '::: a card\n| 항목' in after, after[-300:])
        check('고치지 않은 안내 글은 옮기지 않는다', '표에서 볼 곳을 씁니다' not in after, after[-300:])
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
        page.keyboard.press('Control+z')
        page.wait_for_timeout(900)
        check('Ctrl+Z 로 되돌린다', text() == before)

        print('[이 장을 템플릿으로 저장]')
        menu(2, '이 장을 템플릿으로 저장')
        page.wait_for_selector('#lec-tplname-input', state='visible', timeout=3000)
        page.keyboard.type('매출 보고')
        page.keyboard.press('Enter')
        page.wait_for_timeout(600)
        saved = config / 'templates' / '01-매출 보고.md'
        check('Lectern 전체의 템플릿 폴더에 파일 하나를 만든다', saved.exists() and '## 매출이 늘었다' in saved.read_text(encoding='utf-8'), list((config / 'templates').glob('*')) if (config / 'templates').exists() else '')
        slide(2).locator('h2').click()
        page.keyboard.press('Control+m')
        page.wait_for_selector(gallery, timeout=6000)
        check('13번으로 나온다', page.locator(gallery).count() == 13 and '내 템플릿' in names()[12] and names()[12].startswith('13'), names()[-1])
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)
        menu(2, '이 장을 템플릿으로 저장')
        page.wait_for_selector('#lec-tplname-input', state='visible', timeout=3000)
        page.keyboard.type('매출 보고')
        page.keyboard.press('Enter')
        page.wait_for_timeout(500)
        check('같은 이름은 덮어쓰지 않고 알린다', '같은 이름' in (page.text_content('#lec-toast') or '') and len(list((config / 'templates').glob('*.md'))) == 1, page.text_content('#lec-toast'))

        print('[pptx 로 전환]')
        check('상태줄에 전환 버튼', page.locator('#lec-st-pptx').is_visible())
        page.click('#lec-st-pptx')
        page.wait_for_selector('#lec-pptx-list li', timeout=4000)
        items = page.locator('#lec-pptx-list li').all_inner_texts()
        check('보관소의 스타일이 나온다', any('회사양식' in x for x in items), items)
        check('보관소의 대표색', page.locator('.lec-pptx-colors i').count() >= 3)
        check('Lectern 스타일도 고를 수 있다', any('Lectern 스타일' in x for x in items), items)
        if os.environ.get('LEC_SHOTS'):
            page.screenshot(path=str(Path(os.environ['LEC_SHOTS']) / 'pptx-전환.png'))
        page.keyboard.press('Enter')
        page.wait_for_selector('#lec-pptx-summary', state='visible', timeout=60000)
        out = proj / '보고서.pptx'
        check('문서 옆에 pptx 를 만든다', out.exists() and '2장' in page.text_content('#lec-pptx-summary'), page.text_content('#lec-pptx-summary'))
        z = zipfile.ZipFile(out)
        check('고른 스타일 위에 만든다', any('slideLayout' in n for n in z.namelist()) and any(n.startswith('ppt/charts/') for n in z.namelist()), [n for n in z.namelist() if 'chart' in n][:3])
        page.click('#lec-pptx-close')
        page.wait_for_timeout(1000)
        check('문서가 스타일 이름을 기억한다', 'pptxStyle: 회사양식\n' in text().split('\n---\n')[0] + '\n', text()[:120])
        page.click('#lec-st-pptx')
        page.wait_for_selector('#lec-pptx-list li', timeout=4000)
        first = page.locator('#lec-pptx-list li').first.inner_text()
        check('다음에는 기억한 스타일을 먼저 고른다', '회사양식' in first and '기억' in first, first)
        check('있는 파일은 덮어쓰지 않는다', '보고서 2.pptx' in page.text_content('#lec-pptx-title'), page.text_content('#lec-pptx-title'))
        made = out.stat().st_mtime
        page.keyboard.press('Enter')
        page.wait_for_selector('#lec-pptx-summary', state='visible', timeout=60000)
        check('새 이름으로 만들고 앞 파일은 그대로', (proj / '보고서 2.pptx').exists() and out.stat().st_mtime == made)
        page.click('#lec-pptx-close')
        (config / 'pptx-styles' / '회사양식.pptx').rename(config / 'pptx-styles' / '다른이름.pptx')
        page.wait_for_timeout(300)
        page.click('#lec-st-pptx')
        page.wait_for_selector('#lec-pptx-list li', timeout=4000)
        check('보관소에 없으면 알리고 다시 고르게 한다', '보관소에 없습니다' in page.text_content('#lec-pptx-msg'), page.text_content('#lec-pptx-msg'))
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
        check('Esc 로 닫는다', page.locator('#lec-pptx').is_hidden())
        check('화면 오류 없음', not extra, extra)
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
