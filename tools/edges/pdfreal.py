"""실제 PDF 로 PDF 보기 (D201) — 인터넷의 라이선스 걱정 없는 PDF 를 받아 Lectern 에서 열고, 그린 모습을 다른 엔진(MuPDF)의 그림과 화소로 견준다.

- 받는 곳: 저장소 밖 임시 폴더(%TEMP%\\lectern-real-pdfs) — 한 번 받으면 다시 쓰고, 저장소에는 넣지 않는다 (다시 배포하지 않게). 인터넷이 없으면 건너뛴다.
- 출처와 라이선스 (아래 SOURCES): 미국 정부 저작물(공유 — USGS·NIST·IRS, IRS 안내서의 한국어·중국어·러시아어·베트남어판),
  한국 정부 보도자료(공공저작물 — 저작권법 제24조의2), 공유 저작물 스캔 책(인터넷 아카이브 — 1859년), PDF 협회 PDF 2.0 예제(CC BY-SA 4.0),
  veraPDF 검사 모음(CC BY 4.0 — 폴더마다 골고루, 표준의 경계를 찌르는 파일들).
- 파일마다: 열기(30초 안), 쪽 수가 MuPDF 와 같다, 첫·가운데·마지막 쪽을 그려 MuPDF 그림과의 차이(작게 줄인 회색조, 0~255)가 작다,
  글 층의 글자가 MuPDF 가 뽑은 글자와 맞는다, 책갈피 수, 찾기, 화면 오류 없음. 차이가 큰 쪽은 두 그림을 ui-shots/edges/pdfreal 에 남긴다.
  python pdfreal.py                 — 실제 문서 모두 + veraPDF 는 여덟 개마다 하나 (전체 점검 ui_edges 가 이것으로 — 10분 안팎이 아니게)
  LECTERN_REAL_PDFS=all python pdfreal.py — veraPDF 까지 모두 (328개)
  python pdfreal.py 20 · python pdfreal.py A019 — 앞의 20개만 · 이름에 그 글이 든 것만"""
import base64
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness import ROOT, check, fails, report, serve, stop

try:
    import pymupdf
except ImportError:
    pymupdf = None

CACHE = Path(tempfile.gettempdir()) / 'lectern-real-pdfs'
SHOTS = ROOT / 'ui-shots' / 'edges' / 'pdfreal'
LIMIT = next((int(a) for a in sys.argv[1:] if a.isdigit()), 0)
DIFF_MAX = 14       # 그림 차이의 허용 (0~255 평균) — 글꼴 대체·안티에일리어싱만큼은 다르다
TEXT_MIN = 0.85     # 글자 두 개씩의 겹침 (MuPDF 글자 중 Lectern 글 층에도 있는 비율)
# 알려진 차이 — 파일 이름: 까닭 (그 항목만 느슨하게)
KNOWN = {
    'PDF협회 pdf20-utf8-test.pdf': ('text', '그림의 대체 글(ActualText) 을 MuPDF 는 글로 뽑고 pdf.js 의 글 층에는 넣지 않는다 — 본문 글은 같다'),
    'vera PDF_UA-1 — 7.2 Text — 7.2-t25-pass-a.pdf': ('text', '서식 칸에 적힌 값을 MuPDF 는 글로 뽑고 pdf.js 의 글 층에는 넣지 않는다 — 그림으로는 맞게 그린다'),
    'vera TWG test files — TWG test suite A019-pdfa2-pass-b.pdf': ('diff', '사각형을 x = -3.4×10^38 로 옮겨 화면 밖에 두는 검사 — pdf.js 는 그대로 그리지 않고(맞음) MuPDF 는 값을 잘라 그린다'),
}

SOURCES = [
    ('USGS 구리 2024.pdf', 'https://pubs.usgs.gov/periodicals/mcs2024/mcs2024-copper.pdf', '미국 정부 저작물 (USGS)', 'copper'),
    ('USGS 광물 연보 2024.pdf', 'https://pubs.usgs.gov/periodicals/mcs2024/mcs2024.pdf', '미국 정부 저작물 (USGS)', 'lithium'),
    ('NIST IR 8286C.pdf', 'https://nvlpubs.nist.gov/nistpubs/ir/2022/NIST.IR.8286C.pdf', '미국 정부 저작물 (NIST)', 'risk'),
    ('IRS W-9 서식.pdf', 'https://www.irs.gov/pub/irs-pdf/fw9.pdf', '미국 정부 저작물 (IRS) — 채우는 서식', 'Taxpayer'),
    ('IRS 1040 서식.pdf', 'https://www.irs.gov/pub/irs-pdf/f1040.pdf', '미국 정부 저작물 (IRS) — 채우는 서식', 'Income'),
    ('IRS 안내서 17 한국어.pdf', 'https://www.irs.gov/pub/irs-pdf/p17ko.pdf', '미국 정부 저작물 (IRS)', '세금'),
    ('IRS 안내서 17 중국어.pdf', 'https://www.irs.gov/pub/irs-pdf/p17zht.pdf', '미국 정부 저작물 (IRS)', ''),
    ('IRS 안내서 17 러시아어.pdf', 'https://www.irs.gov/pub/irs-pdf/p17ru.pdf', '미국 정부 저작물 (IRS)', ''),
    ('IRS 안내서 17 베트남어.pdf', 'https://www.irs.gov/pub/irs-pdf/p17vie.pdf', '미국 정부 저작물 (IRS)', ''),
    ('문체부 보도자료 2025-10-15.pdf', 'https://www.mcst.go.kr/servlets/eduport/front/upload/UplDownloadFile?pFileName=%5B1015%5D%EB%AC%B8%EC%B2%B4%EB%B6%80%EB%B3%B4%EB%8F%84%EC%9E%90%EB%A3%8C-%EB%8C%80%ED%95%9C%EB%AF%BC%EA%B5%AD+%EC%A0%95%EC%B1%85%EB%B8%8C%EB%A6%AC%ED%95%91+%EC%84%9C%EB%B9%84%EC%8A%A4+%EC%9E%AC%EA%B0%9C.pdf&pRealName=20251015161356665012236549_PRESS20251015041356490793.pdf&pPath=0302000000', '한국 정부 보도자료 (공공저작물 — 저작권법 제24조의2)', '정책'),
    ('종의 기원 1859 스캔.pdf', 'https://archive.org/download/originofspecies00darwuoft/originofspecies00darwuoft.pdf', '공유 저작물 (1859) — 인터넷 아카이브 스캔', ''),
]
PDF20 = ['PDF 2.0 UTF-8 string and annotation.pdf', 'PDF 2.0 image with BPC.pdf', 'PDF 2.0 via incremental save.pdf', 'PDF 2.0 with offset start.pdf',
         'PDF 2.0 with page level output intent.pdf', 'Simple PDF 2.0 file.pdf', 'pdf20-utf8-test.pdf']
for n in PDF20:
    SOURCES.append((f'PDF협회 {n}', 'https://raw.githubusercontent.com/pdf-association/pdf20examples/master/' + urllib.parse.quote(n), 'PDF 협회 예제 (CC BY-SA 4.0)', ''))
VERA_ALL = ('ISO 32000-1', 'ISO 32000-2', 'Undefined', 'TWG test files', 'PDF_A-1a', 'PDF_A-2a', 'PDF_A-2u', 'PDF_A-3b', 'PDF_A-4e', 'PDF_A-4f')
VERA_EVERY = 30   # 큰 폴더는 30개마다 하나


def vera_list():
    """veraPDF 검사 모음의 PDF 목록 (GitHub 의 트리 — 한 번 받아 둔다)"""
    listed = CACHE / 'vera.json'
    if not listed.exists():
        req = urllib.request.Request('https://api.github.com/repos/veraPDF/veraPDF-corpus/git/trees/master?recursive=1', headers={'User-Agent': 'lectern-test'})
        tree = json.loads(urllib.request.urlopen(req, timeout=60).read())['tree']
        listed.write_text(json.dumps([t['path'] for t in tree if t['path'].endswith('.pdf')], ensure_ascii=False), encoding='utf-8')
    paths = json.loads(listed.read_text(encoding='utf-8'))
    out = []
    by_folder = {}
    for path in sorted(paths):
        by_folder.setdefault(path.split('/')[0], []).append(path)
    for folder, items in by_folder.items():
        out += items if folder in VERA_ALL else items[::VERA_EVERY]
    return [(f"vera {p.replace('/', ' — ')}"[:120], 'https://raw.githubusercontent.com/veraPDF/veraPDF-corpus/master/' + urllib.parse.quote(p), 'veraPDF 검사 모음 (CC BY 4.0)', '') for p in out]


def fetch(name, url):
    path = CACHE / re.sub(r'[\\/:*?"<>|]', '_', name)
    if path.exists() and path.stat().st_size:
        return path
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (lectern test)'})
    data = urllib.request.urlopen(req, timeout=180).read()
    path.write_bytes(data)
    return path


OPEN = "(p) => import('/static/js/store.js').then((m) => m.emit('open', { type: 'doc', path: p }))"
ST = "() => import('/static/js/store.js').then(({ S }) => S.pane.pdf?.doc ? { path: S.pane.pdf.path, cur: S.pane.pdf.cur, pages: S.pane.pdf.doc.numPages, marks: (S.pane.pdf.marks || []).length } : null)"
# 그린 쪽(캔버스)과 MuPDF 의 그림을 같은 방법으로 줄여 회색조로 견준다 — 평균 차이, 잉크(어두운 점)의 비율
COMPARE = """async ([n, png]) => {
  const c = document.querySelector(`#lec-view .pdf-pg[data-n="${n}"].drawn canvas`);
  if (!c) return null;
  const img = new Image();
  img.src = 'data:image/png;base64,' + png;
  await img.decode();
  const W = 120, H = Math.max(1, Math.round(W * c.height / c.width));
  const gray = (src) => { const k = document.createElement('canvas'); k.width = W; k.height = H; const x = k.getContext('2d');
    x.fillStyle = '#fff'; x.fillRect(0, 0, W, H); x.imageSmoothingQuality = 'high'; x.drawImage(src, 0, 0, W, H);
    const d = x.getImageData(0, 0, W, H).data; const out = new Float32Array(W * H); for (let i = 0; i < out.length; i++) out[i] = 0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2]; return out; };
  const a = gray(c), b = gray(img);
  let diff = 0, inkA = 0, inkB = 0;
  for (let i = 0; i < a.length; i++) { diff += Math.abs(a[i] - b[i]); if (a[i] < 200) inkA++; if (b[i] < 200) inkB++; }
  return { diff: diff / a.length, inkA: inkA / a.length, inkB: inkB / a.length, w: c.width, h: c.height, mine: c.toDataURL('image/png').split(',')[1] };
}"""
TEXT = """(n) => import('/static/js/store.js').then(async ({ S }) => { const pg = await S.pane.pdf.doc.getPage(n); return (await pg.getTextContent()).items.map((x) => x.str).join(''); })"""


def norm(s):
    return re.sub(r'\s+', '', s or '')


def overlap(ref, got):
    """MuPDF 글자의 두 글자 묶음 가운데 Lectern 글 층에도 있는 비율"""
    a, b = norm(ref), norm(got)
    if len(a) < 20:
        return 1.0
    grams = {a[i:i + 2] for i in range(len(a) - 1)}
    have = {b[i:i + 2] for i in range(len(b) - 1)}
    return len(grams & have) / len(grams)


if pymupdf is None:
    print('PyMuPDF 가 없어 건너뜁니다')
    report()
    raise SystemExit(0)
CACHE.mkdir(exist_ok=True)
items = list(SOURCES)
try:
    import os
    vera = vera_list()
    items += vera if os.environ.get('LECTERN_REAL_PDFS') == 'all' or len(sys.argv) > 1 else vera[::8]
except Exception as e:   # noqa: BLE001 — GitHub 에 닿지 않으면 그것만 뺀다
    print('veraPDF 목록을 받지 못함:', str(e)[:120])
ONLY = [a for a in sys.argv[1:] if not a.isdigit()]   # 이름의 일부로 고르기
if ONLY:
    items = [x for x in items if any(o in x[0] for o in ONLY)]
if LIMIT:
    items = items[:LIMIT]
base = Path(tempfile.mkdtemp(prefix='lec-pdfreal-'))
proj = base / '실제 PDF'
proj.mkdir()
got = []
print(f'[받기 — {len(items)}개, {CACHE}]')
for name, url, lic, word in items:
    try:
        src = fetch(name, url)
        dest = proj / (name if name.lower().endswith('.pdf') else name + '.pdf')
        shutil.copy(src, dest)
        got.append((dest.name, lic, word))
    except Exception as e:   # noqa: BLE001
        print(f'  받지 못함: {name} — {str(e)[:100]}')
check(f'받은 PDF {len(got)}/{len(items)}개', len(got) >= max(1, len(items) * 0.8), len(got))
SHOTS.mkdir(parents=True, exist_ok=True)
for old in SHOTS.glob('*.png'):
    old.unlink()
config = base / 'config'
config.mkdir()
(config / 'config.json').write_text(json.dumps({'work_alerts': False, 'language': 'ko'}), encoding='utf-8')
server, url, port = serve(proj, config)
rows = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={'width': 1200, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)[:300]))
        page.goto(url)
        page.wait_for_selector('#lec-tree .row.file', state='attached', timeout=60000)
        page.wait_for_timeout(500)
        print('[열고 그리고 견주기]')
        for name, lic, word in got:
            path = name
            ref = pymupdf.open(str(proj / name))
            if ref.needs_pass:
                print(f'  {name}: 암호 — 건너뜀')
                continue
            row = {'name': name, 'lic': lic, 'pages': ref.page_count}
            t0 = time.monotonic()
            page.evaluate(OPEN, path)
            try:
                page.wait_for_function("""(p) => document.querySelector('#lec-st-path')?.textContent === p && (!!document.querySelector('#lec-view.pdf-failed')
                  || !!document.querySelector('#lec-view.pdf-view .pdf-pg[data-n="1"].drawn'))""", arg=path, timeout=30000, polling=50)
            except Exception:   # noqa: BLE001
                row['problem'] = '30초 안에 그리지 못함'
                rows.append(row)
                check(f'{name}: 30초 안에 연다', False, ref.page_count)
                continue
            row['open'] = round(time.monotonic() - t0, 2)
            if page.locator('#lec-view.pdf-failed').count():
                row['problem'] = page.inner_text('#lec-view')[:160]
                rows.append(row)
                check(f'{name}: 연다 (MuPDF 는 {ref.page_count}쪽을 읽는다)', ref.page_count == 0, row['problem'])
                continue
            st = page.evaluate(ST)
            row['ok_pages'] = st['pages'] == ref.page_count
            toc = len([x for x in ref.get_toc(simple=True) if x[0] <= 2 and x[2] > 0])
            row['marks'] = (st['marks'], min(toc, 500))
            picks = sorted({1, (ref.page_count + 1) // 2, ref.page_count})
            worst = 0.0
            texts = []
            for n in picks:
                page.fill('#lec-view .pdf-page', str(n))
                page.keyboard.press('Enter')
                try:
                    page.wait_for_selector(f'#lec-view .pdf-pg[data-n="{n}"].drawn canvas', timeout=20000)
                except Exception:   # noqa: BLE001
                    row.setdefault('problem', f'{n}쪽을 그리지 못함')
                    continue
                rp = ref[n - 1]
                cmp_ = pix = None
                for _ in range(20):   # 그 사이 다시 그려질 수 있다 (폭 맞춤·지켜보기) — 그려진 것을 잡을 때까지
                    page.wait_for_timeout(150)
                    w = page.evaluate(f"() => document.querySelector('#lec-view .pdf-pg[data-n=\"{n}\"].drawn canvas')?.width || 0")
                    if not w:
                        continue
                    pix = rp.get_pixmap(matrix=pymupdf.Matrix(w / rp.rect.width, w / rp.rect.width), alpha=False)
                    cmp_ = page.evaluate(COMPARE, [n, base64.b64encode(pix.tobytes('png')).decode()])
                    if cmp_ and cmp_['w'] == w:
                        break
                if not cmp_:
                    row.setdefault('problem', f'{n}쪽의 그림을 잡지 못함')
                    continue
                worst = max(worst, cmp_['diff'])
                if cmp_['diff'] > DIFF_MAX:
                    stem = re.sub(r'[^\w가-힣]+', '_', name)[:60]
                    (SHOTS / f'{stem}-{n}-lectern.png').write_bytes(base64.b64decode(cmp_['mine']))
                    (SHOTS / f'{stem}-{n}-mupdf.png').write_bytes(pix.tobytes('png'))
                ref_text = rp.get_text()
                if len(norm(ref_text)) >= 20:
                    texts.append(overlap(ref_text, page.evaluate(TEXT, n)))
            row['diff'] = round(worst, 1)
            row['text'] = round(min(texts), 2) if texts else None
            if word:
                page.keyboard.press('Control+f')
                page.fill('#lec-find-input', word)
                try:
                    page.wait_for_function("() => /^\\d+\\/\\d+$/.test(document.querySelector('#lec-find-count').textContent)", timeout=20000)
                    row['find'] = page.inner_text('#lec-find-count')
                except Exception:   # noqa: BLE001
                    row['find'] = page.inner_text('#lec-find-count') or '없음'
                page.keyboard.press('Escape')
            rows.append(row)
            row['ok_marks'] = st['marks'] == min(toc, 500)
            known = KNOWN.get(name, ('', ''))[0]
            if known == 'text':
                row['text'] = None
            if known == 'diff':
                worst = 0.0
            ok = row['ok_pages'] and row['ok_marks'] and worst <= DIFF_MAX and (row['text'] is None or row['text'] >= TEXT_MIN) and 'problem' not in row and (not word or '/' in row.get('find', ''))
            check(f"{name[:60]} — {ref.page_count}쪽, 열기 {row['open']}초, 그림 차이 {row['diff']}, 글자 {row['text']}" + (f", 찾기 '{word}' {row.get('find')}" if word else ''), ok, row)
        check('화면 스크립트 오류 없음', not errors, errors[:5])
        b.close()
except Exception:   # noqa: BLE001
    traceback.print_exc()
    fails.append('점검이 멈춤')
finally:
    stop(server, base)
    (SHOTS / 'results.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    if rows:
        opens = sorted(r.get('open', 0) for r in rows)
        print(f"\n파일 {len(rows)}개 · 열기 가운뎃값 {opens[len(opens) // 2]}초 · 가장 늦은 것 {opens[-1]}초 · 그림 차이 가장 큰 것 {max((r.get('diff') or 0) for r in rows)}")
report()
