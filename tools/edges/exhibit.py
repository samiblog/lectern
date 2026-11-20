"""전시물 — 캡션과 주·자료 (2026-11-20 사용자 요청: '그림, 표, 플로우차트, 차트에 상단 제목(캡션), 하단 주/출처(자료)를 넣을 공간 —
제목은 가운데 정렬이고 일반 글자보다 크게, 하단 주/출처는 왼쪽 정렬'):
캡션이 있는 표·그림·다이어그램·차트는 캡션·몸체·주·자료째 한 상자(div.lec-exhibit) — 캡션은 몸체의 가운데에 본문보다 크고 굵게, 주·자료는 몸체의 왼쪽 끝에서 왼쪽 정렬.
캡션이 없는 표는 그대로, 그림 캡션을 아래에 쓴 예전 문서와 두 그림 사이의 캡션, 빈 줄 없이 이어 쓴 '주:'·'자료:' 두 줄, 넓은 표의 열 너비(D173)와 옆 스크롤,
줄 편집·목차, 인쇄, Lectern 슬라이드의 칸"""
import json
import struct
import tempfile
import traceback
import zlib
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import check, expect, fails, report, serve, stop


def png(w, h):
    raw = b''.join(b'\x00' + bytes([90, 140, 200]) * w for _ in range(h))
    chunk = lambda kind, data: struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)  # noqa: E731
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


base = Path(tempfile.mkdtemp(prefix='lec-exhibit-'))
proj = base / 'proj'
proj.mkdir(parents=True)
(proj / '공장.png').write_bytes(png(480, 160))
(proj / '작은.png').write_bytes(png(120, 60))
FENCE = '```'
DOC = f"""# 전시물

본문 문단 하나 — 글자 크기를 견준다.

표 1. 분기별 금속 가격과 재고

| 분기 | 구리 (USD/t) | 알루미늄 (USD/t) | 니켈 (USD/t) | 재고 설명 |
|---|---:|---:|---:|---|
| 2026 2분기 | 9,410 | 2,480 | 16,200 | 거래소 재고가 줄었다 |
| 2026 3분기 | 9,820 | 2,530 | 15,900 | 창고 재고가 늘었다 |

주: 2026년 3분기는 잠정치다.
자료: LME (2026)

그림 1. 공장 사진

![공장](공장.png)

자료: 회사 자료

그림 2. 흐름

{FENCE}mermaid
flowchart LR
  A["원료"] --> B["가공"] --> C["출하"]
{FENCE}

출처: 사내 자료

그림 3. 월별 매출

{FENCE}vega-lite
{{"width": "container", "data": {{"values": [{{"월": "1월", "값": 3}}, {{"월": "2월", "값": 5}}]}}, "mark": "bar",
 "encoding": {{"x": {{"field": "월", "type": "nominal"}}, "y": {{"field": "값", "type": "quantitative"}}}}}}
{FENCE}

자료: 예시

**지역별 매출**

| 지역 | 매출 |
|---|---:|
| 서울 | 10 |

표 2. 좁은 표

| 가 | 나 |
|---|---|
| 1 | 2 |

자료: 좁은 표의 자료

캡션 없는 표 앞 문단.

| 다 | 라 |
|---|---|
| 3 | 4 |

자료: 캡션 없는 표의 자료
"""
(proj / '전시물.md').write_text(DOC, encoding='utf-8')
(proj / '예전.md').write_text('# 예전\n\n![a](공장.png)\n\n그림 1. 첫째\n\n![b](공장.png)\n\n그림 2. 둘째\n\n자료: 둘째의 자료\n', encoding='utf-8')
(proj / '새것.md').write_text('# 새것\n\n그림 1. 첫째\n\n![a](공장.png)\n\n그림 2. 둘째\n\n![b](작은.png)\n', encoding='utf-8')
LONG = ' '.join(['전력망 투자 계획이 늘어 수요가 커진다는 전망이 이어진다'] * 3)
wide = '| 항목 | 설명 | 비고 |\n|---|---|---|\n' + ''.join(f'| 항목{i} | {LONG} | 참고 {i} |\n' for i in range(3))
(proj / '넓은표.md').write_text(f'# 넓은 표\n\n표 1. 캡션이 있는 넓은 표\n\n{wide}\n자료: 예시\n\n문단\n\n{wide}', encoding='utf-8')
(proj / '슬라이드.md').write_text(f"""---
marp: true
---

# 표지

---

## 매출

::: a
**10월 매출 (억 원)**

| 부문 | 매출 |
|---|---:|
| 택배 | 12,600 |
| 창고 | 3,100 |

자료: 가상 협회 (2026)
:::
""", encoding='utf-8')
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False}), encoding='utf-8')
server, url, port = serve(proj, config)

BOXES = """() => [...document.querySelectorAll('#lec-view .lec-exhibit')].map((box) => {
  const r = (el) => el && el.getBoundingClientRect();
  const cap = box.querySelector(':scope > .lec-caption');
  const body = box.querySelector(':scope > .table-wrap, :scope > p:not(.lec-caption, .lec-source) > img, :scope > pre svg');
  const srcs = [...box.querySelectorAll(':scope > .lec-source')];
  const cs = cap && getComputedStyle(cap);
  const b = r(body); const c = r(cap);
  return { kind: [...box.classList].find((x) => x.startsWith('lec-ex-')).slice(7), cap: cap?.textContent.trim() ?? '', capLast: box.lastElementChild === cap,
    capMid: c ? Math.round(c.left + c.width / 2) : 0, bodyMid: b ? Math.round(b.left + b.width / 2) : 0, bodyLeft: b ? Math.round(b.left) : 0, bodyW: b ? Math.round(b.width) : 0,
    capAlign: cs?.textAlign, capSize: cs ? parseFloat(cs.fontSize) : 0, capWeight: cs ? +cs.fontWeight : 0, boxW: Math.round(r(box).width), boxLeft: Math.round(r(box).left),
    srcs: srcs.map((s) => ({ text: s.textContent.trim(), left: Math.round(s.getBoundingClientRect().left), align: getComputedStyle(s).textAlign,
      lines: Math.round(s.getBoundingClientRect().height / parseFloat(getComputedStyle(s).lineHeight || '20')) })) }; })"""
BODY_SIZE = "() => parseFloat(getComputedStyle(document.querySelector('#lec-view > p')).fontSize)"
VIEW_LEFT = "() => { const v = document.querySelector('#lec-view'); return Math.round(v.getBoundingClientRect().left + parseFloat(getComputedStyle(v).paddingLeft)); }"

try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', timeout=20000)

        def open_doc(name, ready):
            page.evaluate("(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))", name)
            expect(page, f'{name} 을 연다', lambda: page.evaluate(ready), ms=15000)
            page.wait_for_timeout(400)

        print('[문서 — 표·그림·다이어그램·차트]')
        open_doc('전시물.md', "() => document.querySelectorAll('#lec-view .lec-exhibit').length >= 5 && !!document.querySelector('#lec-view pre.mermaid svg') && !!document.querySelector('#lec-view pre.lec-chart svg')")
        boxes = page.evaluate(BOXES)
        body = page.evaluate(BODY_SIZE)
        kinds = [(x['kind'], x['cap']) for x in boxes]
        check('캡션이 있는 넷 — 표·그림·다이어그램·차트, 굵게 쓴 한 줄 캡션의 표, 좁은 표가 묶인다',
              kinds == [('table', '표 1. 분기별 금속 가격과 재고'), ('figure', '그림 1. 공장 사진'), ('diagram', '그림 2. 흐름'), ('chart', '그림 3. 월별 매출'),
                        ('table', '지역별 매출'), ('table', '표 2. 좁은 표')], kinds)
        check('캡션 없는 표는 묶지 않는다 — 왼쪽 그대로', page.evaluate("() => { const t = [...document.querySelectorAll('#lec-view > .table-wrap')]; return t.length === 1 && t[0].textContent.includes('다'); }")
              and abs(page.evaluate("document.querySelector('#lec-view > .table-wrap').getBoundingClientRect().left") - page.evaluate(VIEW_LEFT)) <= 2)
        check('— 그 자료 줄도 작은 글 그대로 (묶지 않은 자리)', page.evaluate("() => { const s = document.querySelector('#lec-view > .table-wrap + p'); return s.classList.contains('lec-source') && !s.closest('.lec-exhibit'); }"))
        for x in boxes:
            check(f"{x['kind']} '{x['cap']}' — 캡션은 몸체의 가운데에 가운데 정렬", x['capAlign'] == 'center' and abs(x['capMid'] - x['bodyMid']) <= 2, (x['capMid'], x['bodyMid']))
            check('— 본문보다 크고 굵게', x['capSize'] > body * 1.04 and x['capWeight'] >= 600, (x['capSize'], body, x['capWeight']))
        t1, fig, dia, chart, bold, narrow = boxes
        check('표 — 주·자료 줄은 몸체 왼쪽 끝에서 왼쪽 정렬', [s['text'][:3] for s in t1['srcs']] == ['주: '] and all(abs(s['left'] - t1['bodyLeft']) <= 2 and s['align'] == 'left' for s in t1['srcs']), t1['srcs'])
        check("— 빈 줄 없이 이어 쓴 '주:'·'자료:' 는 두 줄로", t1['srcs'][0]['lines'] == 2 and '자료: LME' in t1['srcs'][0]['text'], t1['srcs'])
        check('— 상자는 표의 폭, 가운데', abs(t1['boxW'] - t1['bodyW']) <= 2 and abs(t1['bodyMid'] - (page.evaluate(VIEW_LEFT) + page.evaluate("document.querySelector('#lec-view').clientWidth - parseFloat(getComputedStyle(document.querySelector('#lec-view')).paddingLeft) - parseFloat(getComputedStyle(document.querySelector('#lec-view')).paddingRight)") / 2)) <= 3, t1)
        check('그림 — 자료 줄이 그림의 왼쪽 끝에서', len(fig['srcs']) == 1 and abs(fig['srcs'][0]['left'] - fig['bodyLeft']) <= 2 and fig['bodyW'] == 480, fig)
        check('다이어그램 — 상자는 그림의 본래 폭, 출처 줄은 그림의 왼쪽 끝에서', abs(dia['boxW'] - dia['bodyW']) <= 3 and abs(dia['srcs'][0]['left'] - dia['bodyLeft']) <= 3 and dia['srcs'][0]['text'].startswith('출처'), dia)
        check('차트 — 칸 폭으로 그리고 자료 줄은 왼쪽', chart['bodyW'] > 500 and chart['srcs'] and chart['srcs'][0]['align'] == 'left', chart)
        check('좁은 표 — 상자는 22em 까지 넓히고 표는 그 가운데, 자료는 상자의 왼쪽 끝', narrow['boxW'] > narrow['bodyW'] + 40 and abs(narrow['bodyMid'] - narrow['capMid']) <= 2
              and abs(narrow['srcs'][0]['left'] - narrow['boxLeft']) <= 2, narrow)
        check('굵게 쓴 한 줄도 표의 캡션 (D61) — 자료 줄이 없으면 캡션과 표만', bold['srcs'] == [] and bold['cap'] == '지역별 매출', bold)

        print('[목차·줄 편집은 그대로]')
        toc = page.evaluate("() => [...document.querySelectorAll('#lec-toc li.part a')].map((a) => a.textContent.trim())")
        check('목차의 구성 요소는 캡션을 이름으로', any('분기별 금속 가격' in x for x in toc) and any('공장 사진' in x for x in toc) and any('흐름' in x for x in toc), toc)
        page.locator('#lec-view .lec-caption', has_text='공장 사진').click()
        page.wait_for_timeout(200)
        page.keyboard.press('F2')
        expect(page, '캡션 줄을 누르고 F2 — 그 줄을 고친다', lambda: page.evaluate("[...document.querySelectorAll('#lec-view .lec-line-edit')].map((e) => e.textContent)") == ['그림 1. 공장 사진'])
        page.keyboard.press('End')
        page.keyboard.type(' 고침')
        page.keyboard.press('Enter')
        expect(page, '— 그 줄만 바뀐다', lambda: (proj / '전시물.md').read_text(encoding='utf-8') == DOC.replace('그림 1. 공장 사진', '그림 1. 공장 사진 고침'))
        page.keyboard.press('Escape')
        page.keyboard.press('Escape')
        expect(page, '— 다시 그려도 묶인다', lambda: '그림 1. 공장 사진 고침' in [x['cap'] for x in page.evaluate(BOXES)])

        print('[인쇄]')
        page.emulate_media(media='print')
        page.wait_for_timeout(300)
        pr = page.evaluate(BOXES)[0]
        check('인쇄 — 캡션 11pt 가운데, 자료 줄은 왼쪽', abs(pr['capSize'] - 11 * 4 / 3) < 0.6 and pr['capAlign'] == 'center' and pr['srcs'][0]['align'] == 'left', pr)
        page.emulate_media(media='screen')

        print('[그림 캡션의 위·아래 — 문서마다]')
        open_doc('예전.md', "() => document.querySelectorAll('#lec-view .lec-exhibit').length === 2")
        old = page.evaluate(BOXES)
        check('그림 아래에 캡션을 쓴 예전 문서 — 그림마다 아래 캡션, 같은 모양', [(x['cap'], x['capLast'] or bool(x['srcs'])) for x in old] == [('그림 1. 첫째', True), ('그림 2. 둘째', True)]
              and all(x['capAlign'] == 'center' for x in old), old)
        check('— 아래 캡션 뒤의 자료 줄도 함께', [s['text'] for s in old[1]['srcs']] == ['자료: 둘째의 자료'], old[1]['srcs'])
        open_doc('새것.md', "() => document.querySelectorAll('#lec-view .lec-exhibit').length === 2")
        new = page.evaluate(BOXES)
        check('위에 쓴 문서 — 두 그림 사이의 캡션은 뒤 그림의 것', [x['cap'] for x in new] == ['그림 1. 첫째', '그림 2. 둘째'] and not any(x['capLast'] for x in new), new)
        check('— 작은 그림은 22em 상자의 가운데', new[1]['bodyW'] == 120 and abs(new[1]['bodyMid'] - new[1]['capMid']) <= 2, new[1])

        print('[넓은 표 — 열 너비(D173)는 캡션이 있어도 같다]')
        open_doc('넓은표.md', "() => document.querySelectorAll('#lec-view table').length === 2 && document.querySelectorAll('#lec-view .lec-exhibit').length === 1")
        page.wait_for_timeout(500)
        ws = page.evaluate("() => [...document.querySelectorAll('#lec-view .table-wrap')].map((w) => [Math.round(w.getBoundingClientRect().width), w.scrollWidth > w.clientWidth + 1, Math.round(w.getBoundingClientRect().height)])")
        check('캡션이 있는 표와 없는 표의 폭·높이가 같다', abs(ws[0][0] - ws[1][0]) <= 2 and abs(ws[0][2] - ws[1][2]) <= 2, ws)
        check('— 옆으로 넘치지 않는다', not ws[0][1], ws)

        print('[Lectern 슬라이드의 칸]')
        open_doc('슬라이드.md', "() => !!document.querySelector('#lec-view .lec-cell .lec-exhibit')")
        sl = page.evaluate("""() => { const box = document.querySelector('#lec-view .lec-cell .lec-exhibit'); const cell = box.closest('.lec-cell');
          const cap = box.querySelector('.lec-caption'); const src = box.querySelector('.lec-source'); const t = box.querySelector('table');
          const pt = (el) => Math.round(parseFloat(getComputedStyle(el).fontSize) * 0.75 * 10) / 10;
          return { cap: cap?.textContent.trim(), capAlign: getComputedStyle(cap).textAlign, capPt: pt(cap), srcPt: src && pt(src), tablePt: pt(t),
            srcAlign: src && getComputedStyle(src).textAlign, full: Math.abs(t.getBoundingClientRect().width - cell.getBoundingClientRect().width) < 3,
            warn: document.querySelector('#lec-view .lec-slide-wrap:nth-of-type(2) .lec-slide')?.dataset.issues || '' }; }""")
        check('칸 안의 굵은 한 줄 + 표 + 자료 — 캡션은 가운데, 본문(18pt)의 1.1배', sl['cap'] == '10월 매출 (억 원)' and sl['capAlign'] == 'center' and abs(sl['capPt'] - 19.8) < 0.3, sl)
        check('— 자료 줄은 왼쪽, 표 글 크기', sl['srcAlign'] == 'left' and sl['srcPt'] == sl['tablePt'], sl)
        check('— 표는 칸 폭 그대로', sl['full'], sl)
        check("— '본문이 작습니다' 점검에 걸리지 않는다", '작습니다' not in sl['warn'], sl['warn'])

        check('화면 스크립트 오류 없음', not errors, errors[:3])
        b.close()
except Exception:
    traceback.print_exc()
    fails.append('예외')
finally:
    stop(server, base)
report()
