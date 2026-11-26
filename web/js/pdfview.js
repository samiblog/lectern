// PDF 보기 (D201): pdf.js(web/vendor/pdfjs — 처음 열 때 불러온다)로 문서 칸에 그린다. 보기만 한다 (파일을 고치지 않는다).
//
// - 쪽을 세로로 잇고, 화면 가까이의 쪽만 그린다 (멀어지면 비운다 — 300쪽도 그려 둔 쪽은 몇 개뿐). 쪽마다 캔버스 + 글 층(고르기·복사·찾기) + 링크.
// - 지금 쪽을 안다: 막대의 쪽 칸, 상태줄, Shift+→ 로 '@경로 12쪽' 을 터미널에, 고른 글을 담으면 그 쪽이 담은 곳 (기록은 조각의 page 값).
// - 책갈피(outline)는 목차 패널에. 없으면 목차가 비어 있다.
// - 찾기(Ctrl+F — find.js)는 모든 쪽의 글에서 찾는다 (pane.findProvider). 처음 찾을 때 쪽마다 글을 받아 둔다.
// - PDF 안의 스크립트는 돌리지 않는다 (pdf.js 의 스크립트 기능을 켜지 않는다). 링크는 앱이 받는다 — 인터넷 주소는 기본 브라우저로, 문서 안이면 그 쪽으로.
// - 확대는 막대의 −·+·폭 맞춤과 Ctrl+= · Ctrl+- · Ctrl+0, Ctrl+휠. 폭 맞춤이면 칸 폭이 바뀔 때 다시 맞춘다.
// - 밖에서 파일이 바뀌면(watch.js 의 refresh-auto) 같은 자리에서 다시 읽는다. 암호가 걸렸거나 깨진 PDF 는 까닭과 '기본 앱으로 열기'.

import { S, on, emit } from './store.js';
import { openExternal } from './api.js';
import { html, setHtml } from './html.js';
import { setToc } from './toc.js';
import { setStatus } from './status.js';
import { clearChanges } from './diffmark.js';
import { $, toast, copyText, docUrl, basename, formatDateTime } from './util.js';
import { t } from './i18n.js';

const BASE = '/static/vendor/pdfjs/';
const ZOOMS = [0.5, 0.67, 0.8, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2, 2.5, 3];
const MAX_SIZES = 2000;   // 이만큼까지는 열 때 쪽마다 크기를 재 둔다 (넘으면 첫 쪽 크기로 — 그릴 때 맞춘다)
const MAX_HITS = 2000;
let lib = null;

/** pdf.js (처음 한 번 — ES 모듈). 일꾼은 같은 출처의 파일 (CSP 의 script-src 'self') */
function pdfjs() {
  lib ??= import(`${BASE}pdf.min.mjs`).then((m) => {
    m.GlobalWorkerOptions.workerSrc = `${BASE}pdf.worker.min.mjs`;
    return m;
  });
  return lib;
}

/** 읽은 PDF 를 놓는다 (일꾼과 함께) — 판에 따라 문서나 불러오기 작업이 destroy 를 가진다 */
function release(doc) {
  try {
    const task = doc?.loadingTask;
    (typeof task?.destroy === 'function' ? task : doc)?.destroy?.();
  } catch {
    // 이미 놓았다
  }
}

export const isPdfView = (pane = S.pane) => !!pane?.pdf && !!pane.view?.classList.contains('pdf-view');
export const pageRef = (st, n = st.cur) => `@${st.path} ${t('{n}쪽', { n })}`;

function skeleton(path) {
  return [html`<div class="pdf-bar" role="toolbar" aria-label="${t('PDF')}">`,
    html`<label class="pdf-pageno">${t('쪽')} <input class="pdf-page" type="text" inputmode="numeric" spellcheck="false" autocomplete="off" aria-label="${t('쪽 번호 — Enter 로 그 쪽으로')}"><span class="pdf-total"></span></label>`,
    html`<span class="pdf-zoom"><button type="button" class="icon-btn small" data-act="out" title="${t('작게 (Ctrl+-)')}" aria-label="${t('작게')}"><svg><use href="#i-minus"/></svg></button>`,
    html`<button type="button" class="text-btn pdf-fit" data-act="fit" title="${t('폭 맞춤 (Ctrl+0)')}"></button>`,
    html`<button type="button" class="icon-btn small" data-act="in" title="${t('크게 (Ctrl+=)')}" aria-label="${t('크게')}"><svg><use href="#i-plus"/></svg></button></span>`,
    html`<span class="pdf-note" role="status"></span>`,
    html`<button type="button" class="text-btn" data-act="external" title="${t('{name} 을(를) 기본 앱으로 엽니다 — 인쇄·주석은 그 앱에서', { name: basename(path) })}">${t('기본 앱으로 열기')}</button></div>`,
    html`<div class="pdf-pages"></div>`];
}

function placeholder(n, w, h) {
  const el = document.createElement('section');
  el.className = 'pdf-pg';
  el.dataset.n = String(n);
  el.style.width = `${w}px`;
  el.style.height = `${h}px`;
  el.setAttribute('aria-label', t('{n}쪽', { n }));
  return el;
}

/** 폭 맞춤의 배율 — 보통 쪽(쪽 폭의 가운뎃값)이 칸에 들어가게. 아주 큰 쪽이 하나 섞여도 다른 쪽이 작아지지 않는다 (그 쪽은 옆으로 넘겨 본다) */
function fitScale(pane, st) {
  const w = Math.max(200, pane.view.clientWidth - 40);
  const widths = st.sizes.map((s) => s[0]).sort((a, b) => a - b);
  return Math.min(3, Math.max(0.4, w / widths[widths.length >> 1]));
}

/** 쪽 자리를 지금 배율로 다시 놓는다 — 그린 쪽은 비우고 보이는 것부터 다시 그린다. 지금 쪽의 자리를 지킨다 */
function layout(pane, st, keep = true) {
  const box = pane.view.querySelector('.pdf-pages');
  const at = keep ? pageAtTop(pane) : 1;
  const within = keep ? offsetIn(pane, at) : 0;
  st.scale = st.fit ? fitScale(pane, st) : st.zoom;
  for (const job of st.drawn.values()) cancel(job);
  st.drawn.clear();
  st.io?.disconnect();
  st.here?.disconnect();
  box.replaceChildren(...st.sizes.map(([w, h], i) => placeholder(i + 1, w * st.scale, h * st.scale)));
  st.io = new IntersectionObserver((es) => { for (const e of es) (e.isIntersecting ? draw(pane, st, e.target) : undraw(st, e.target)); }, { root: pane.scroller, rootMargin: '120% 0px' });
  // 지금 쪽 = 칸 맨 위에 걸친 쪽 (쪽 칸으로 간 쪽과 같게 — 아주 작은 쪽도). 스크롤할 때 한 화면에 한 번
  let frame = 0;
  const onScroll = () => {
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      if (pane.pdf === st) setCur(pane, st, pageAtTop(pane));
    });
  };
  pane.scroller.addEventListener('scroll', onScroll, { passive: true });
  st.here = { disconnect: () => pane.scroller.removeEventListener('scroll', onScroll) };
  for (const el of box.children) st.io.observe(el);
  showZoom(pane, st);
  if (st.marks) applyToc(pane, st);
  if (keep) goPage(pane, st, at, within);
}

/** 칸 맨 위에 걸친 쪽 — 지켜보기(IntersectionObserver)가 알려 주기 전에도 (다시 켤 때·폭이 바뀔 때) */
function pageAtTop(pane) {
  const pages = /** @type {HTMLElement[]} */ ([...pane.view.querySelectorAll('.pdf-pg')]);
  const top = pane.scroller.getBoundingClientRect().top + 50;
  let lo = 0;
  let hi = pages.length - 1;
  while (lo < hi) {   // 맨 위 아래로 끝나는 첫 쪽
    const mid = (lo + hi) >> 1;
    if (pages[mid].getBoundingClientRect().bottom < top) lo = mid + 1;
    else hi = mid;
  }
  return pages.length ? Number(pages[lo].dataset.n) : 1;
}

/** 그 쪽 안에서 화면 맨 위가 어디쯤인지 (0~1) — 배율을 바꿔도 같은 곳을 보게 */
function offsetIn(pane, n) {
  const el = pane.view.querySelector(`.pdf-pg[data-n="${n}"]`);
  if (!el) return 0;
  const top = pane.scroller.getBoundingClientRect().top;
  const r = el.getBoundingClientRect();
  return Math.min(1, Math.max(0, (top - r.top) / r.height));
}

function setCur(pane, st, n) {
  if (st.cur === n) return;
  st.cur = n;
  showPage(pane, st);
}

function showPage(pane, st) {
  const input = /** @type {HTMLInputElement} */ (pane.view.querySelector('.pdf-page'));
  if (input && document.activeElement !== input) input.value = String(st.cur);
  const file = pane.tab.fileMap.get(st.path);
  setStatus({ path: st.path, info: [`PDF · ${t('{n}쪽', { n: `${st.cur}/${st.doc.numPages}` })}`, file && t('수정 {when}', { when: formatDateTime(file.mtime) })].filter(Boolean).join(' · ') }, pane);
}

function showZoom(pane, st) {
  const btn = pane.view.querySelector('.pdf-fit');
  if (!btn) return;
  btn.textContent = `${Math.round(st.scale * 100)}%`;
  btn.setAttribute('aria-pressed', String(st.fit));
  btn.title = st.fit ? t('폭 맞춤 (Ctrl+0)') : t('누르면 폭 맞춤 (Ctrl+0)');
}

/** n 쪽으로 — within: 그 쪽 안의 위치 (0~1) */
export function goPage(pane, st, n, within = 0) {
  const el = pane.view.querySelector(`.pdf-pg[data-n="${Math.min(Math.max(1, n), st.doc.numPages)}"]`);
  if (!el) return;
  pane.scroller.scrollTop += el.getBoundingClientRect().top - pane.scroller.getBoundingClientRect().top - 44 + within * el.offsetHeight;
  setCur(pane, st, Number(el.dataset.n));
}

function cancel(job) {
  job.cancelled = true;
  try {
    job.task?.cancel();
  } catch {
    // 이미 끝났다
  }
}

async function draw(pane, st, el) {
  const n = Number(el.dataset.n);
  if (st.drawn.has(n) || pane.pdf !== st) return;   // 이 칸이 다른 PDF 로 바뀌었으면 (전에는 마지막에 연 PDF 만 그려, 다른 탭에서 돌아오면 비어 있었다)
  const job = { cancelled: false, task: null, at: Date.now() };
  st.drawn.set(n, job);
  try {
    const page = await st.doc.getPage(n);
    if (job.cancelled) return;
    const vp = page.getViewport({ scale: st.scale });
    const ratio = window.devicePixelRatio || 1;
    const canvas = document.createElement('canvas');
    canvas.width = Math.floor(vp.width * ratio);
    canvas.height = Math.floor(vp.height * ratio);
    canvas.style.width = `${vp.width}px`;
    canvas.style.height = `${vp.height}px`;
    el.style.width = `${vp.width}px`;
    el.style.height = `${vp.height}px`;
    job.task = page.render({ canvas, viewport: vp, transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : null });
    await job.task.promise;
    if (job.cancelled) return;
    el.replaceChildren(canvas);
    const layer = document.createElement('div');
    layer.className = 'textLayer';
    layer.style.setProperty('--total-scale-factor', String(st.scale));
    el.append(layer);
    const { TextLayer } = await pdfjs();
    await new TextLayer({ textContentSource: page.streamTextContent(), container: layer, viewport: vp }).render();
    if (job.cancelled) return;
    for (const a of await page.getAnnotations({ intent: 'display' })) {
      if (a.subtype !== 'Link' || (!a.url && !a.unsafeUrl && !a.dest && !NAMED.has(a.action))) continue;
      const [p, q, r, s, x, y] = vp.transform;
      const pt = (u, v) => [p * u + r * v + x, q * u + s * v + y];
      const [x1, y1] = pt(a.rect[0], a.rect[1]);
      const [x2, y2] = pt(a.rect[2], a.rect[3]);
      const link = document.createElement('a');
      link.className = 'pdf-link';
      link.href = '#';
      if (a.url || a.unsafeUrl) link.dataset.url = a.url || a.unsafeUrl;
      if (a.dest) link.dataset.dest = JSON.stringify(a.dest);
      else if (NAMED.has(a.action)) link.dataset.action = a.action;
      link.title = a.url || a.unsafeUrl || t('이 문서 안의 다른 곳');
      Object.assign(link.style, { left: `${Math.min(x1, x2)}px`, top: `${Math.min(y1, y2)}px`, width: `${Math.abs(x2 - x1)}px`, height: `${Math.abs(y2 - y1)}px` });
      el.append(link);
    }
    el.classList.add('drawn');
    noteScanned(pane, st, n, layer);
  } catch (e) {
    if (job.cancelled) return;
    st.drawn.delete(n);   // 남겨 두면 '그리는 중' 으로 남아 다시 그리지 않는다 (빈 쪽)
    if (e?.name === 'RenderingCancelledException') return;   // pdf.js 가 스스로 취소했다 — 보이면 heal 이 다시 그린다
    el.textContent = t('이 쪽을 그리지 못했습니다: {error}', { error: e?.message || String(e) });
  }
}

/**
 * 안전망: 보이는데 비어 있는 쪽을 다시 그린다 (1초마다, 이 칸이 보일 때). 그리던 쪽이 크기가 바뀌는 사이 취소되거나 숨었다 나타나며
 * 지켜보기가 알리지 않으면 빈 흰 쪽으로 남았다 — 5초 넘게 '그리는 중' 인 쪽도 다시
 */
function heal(pane, st) {
  if (pane.pdf !== st || !pane.view.isConnected) {   // 탭을 닫았거나 다른 화면으로
    if (pane.pdf !== st || !pane.tab?.panes?.includes(pane)) clearInterval(st.heal);
    return;
  }
  if (pane.pdf !== st || !st.doc || !pane.view.clientWidth || !pane.view.classList.contains('pdf-view')) return;
  const box = pane.scroller.getBoundingClientRect();
  if (!box.height) return;
  const now = Date.now();
  for (const el of /** @type {HTMLElement[]} */ ([...pane.view.querySelectorAll('.pdf-pg:not(.drawn)')])) {
    const r = el.getBoundingClientRect();
    if (r.bottom < box.top || r.top > box.bottom) continue;
    const n = Number(el.dataset.n);
    const job = st.drawn.get(n);
    if (job && now - job.at < 5000) continue;
    if (job) {
      cancel(job);
      st.drawn.delete(n);
    }
    draw(pane, st, el);
  }
}

function undraw(st, el) {
  const n = Number(el.dataset.n);
  const job = st.drawn.get(n);
  if (!job) return;
  cancel(job);
  st.drawn.delete(n);
  el.replaceChildren();
  el.classList.remove('drawn');
}

/** 앞의 몇 쪽에 글이 하나도 없으면 스캔한 그림으로 본다 — 글을 고르거나 찾을 수 없다고 알린다 */
function noteScanned(pane, st, n, layer) {
  if (n > 3 || st.scanned === false) return;
  if (layer.textContent.trim()) st.scanned = false;
  else if (n === Math.min(3, st.doc.numPages)) st.scanned = true;
  const note = pane.view.querySelector('.pdf-note');
  if (note) note.textContent = st.scanned ? t('글자가 없는 PDF 입니다 (스캔한 그림) — 글을 고르거나 찾을 수 없습니다') : '';
}

const NAMED = new Set(['FirstPage', 'LastPage', 'NextPage', 'PrevPage']);
/** PDF 의 이름 있는 동작(Named action)이 가리키는 쪽 — from 은 지금 쪽 (0 이면 앞·뒤 쪽은 쪽이 없다) */
function namedPage(action, st, from) {
  if (action === 'FirstPage') return 1;
  if (action === 'LastPage') return st.doc.numPages;
  if (from && action === 'NextPage') return Math.min(st.doc.numPages, from + 1);
  if (from && action === 'PrevPage') return Math.max(1, from - 1);
  return 0;
}

/** 책갈피 → 목차 패널 (두 단계까지). 쪽 번호로 기억해 두고(st.marks) 자리를 다시 놓을 때마다 잇는다 */
async function outline(pane, st) {
  let marks = [];
  try {
    const tree = (await st.doc.getOutline()) || [];
    const flat = [];
    const walk = (list, level) => {
      for (const o of list) {
        if (flat.length >= 500) return;
        flat.push({ o, level });
        if (level < 1 && o.items?.length) walk(o.items, level + 1);
      }
    };
    walk(tree, 0);
    marks = await Promise.all(flat.map(async ({ o, level }) => {
      let dest = o.dest;
      if (typeof dest === 'string') dest = await st.doc.getDestination(dest).catch(() => null);
      const page = Array.isArray(dest) && dest[0] ? await st.doc.getPageIndex(dest[0]).then((i) => i + 1).catch(() => 0)
        : namedPage(o.action, st, 0);   // '첫 쪽·마지막 쪽' 같은 이름 있는 동작 (앞·뒤 쪽은 책갈피에서 뜻이 없어 뺀다)
      return { level, name: (o.title || '').trim() || t('{n}쪽', { n: page }), page };
    }));
  } catch {
    marks = [];
  }
  if (pane.pdf !== st) return;
  st.marks = marks.filter((m) => m.page);
  applyToc(pane, st);
}

function applyToc(pane, st) {
  if (!st.marks?.length) {
    setToc(pane, null);
    return;
  }
  setToc(pane, pane.view, { title: t('책갈피'), items: st.marks.map((m) => ({ level: 1, name: `${m.level ? '· ' : ''}${m.name}`, label: t('{n}쪽', { n: m.page }), tip: `${m.name} · ${t('{n}쪽', { n: m.page })}`, icon: 'i-toc',
    el: pane.view.querySelector(`.pdf-pg[data-n="${m.page}"]`) })) });
}

/** 쪽마다 크기 (배율 1) — 많으면 첫 쪽 크기로 채우고 그릴 때 맞춘다 */
async function sizesOf(doc) {
  const first = (await doc.getPage(1)).getViewport({ scale: 1 });
  if (doc.numPages > MAX_SIZES) return Array.from({ length: doc.numPages }, () => [first.width, first.height]);
  // 한꺼번에 묻는다 — 하나씩 기다리면 쪽마다 일꾼과 한 번씩 오가 수백 쪽이면 늦다
  const rest = await Promise.all(Array.from({ length: doc.numPages - 1 }, (_, i) => doc.getPage(i + 2).then((pg) => {
    const vp = pg.getViewport({ scale: 1 });
    return [vp.width, vp.height];
  })));
  return [[first.width, first.height], ...rest];
}

function failed(pane, path, why, st = null) {
  pane.view.className = 'pdf-view pdf-failed';
  setHtml(pane.view, html`<div class="doc-missing"><h1>${path}</h1><p>${why}</p><p><button type="button" class="primary" data-act="external">${t('기본 앱으로 열기')}</button></p></div>`);
  pane.pdf = st;
  setToc(pane, null);
  setStatus({ path, info: 'PDF' }, pane);
  emit('rendered', pane);
  return true;
}

/**
 * PDF 를 칸에 그린다 (nav.js — 문서 화면에서 경로가 .pdf 일 때). hash 'page=N' 이면 그 쪽으로, scrollTop 이 있으면 그 자리로
 * (함수면 다시 그리기 직전의 자리 — 밖에서 바뀌어 다시 읽을 때)
 * @param {Pane} pane
 * @param {string} path
 * @param {{ hash?: string, scrollTop?: number | (() => number) }} [opts]
 */
export async function showPdf(pane, path, { hash = '', scrollTop } = {}) {
  const id = ++pane.renderId;
  const { view, tab } = pane;
  const old = pane.pdf;
  const same = old?.path === path && view.classList.contains('pdf-view') && !view.classList.contains('pdf-failed');
  const top = typeof scrollTop === 'function' ? scrollTop() : scrollTop;
  let doc;
  try {
    const m = await pdfjs();
    const file = tab.fileMap.get(path);
    const task = m.getDocument({ url: `${docUrl(tab, path)}?v=${file ? file.mtime : Date.now()}`, cMapUrl: `${BASE}cmaps/`, cMapPacked: true, standardFontDataUrl: `${BASE}standard_fonts/`,
      wasmUrl: `${BASE}wasm/`, isEvalSupported: false, enableXfa: false, useSystemFonts: true, stopAtErrors: false });
    task.onPassword = () => {   // 암호를 묻지 않는다 — 기본 앱으로
      task.passwordAsked = true;
      task.destroy();
    };
    doc = await task.promise.catch((e) => {
      if (task.passwordAsked || e?.name === 'PasswordException') throw Object.assign(new Error('password'), { password: true });
      throw e;
    });
  } catch (e) {
    if (id !== pane.renderId) return false;
    release(old?.doc);
    const missing = e?.status === 404 || /Missing PDF|404/.test(e?.message || '');
    const broken = e?.name === 'InvalidPDFException' || /invalid pdf|empty|zero bytes/i.test(e?.message || '');   // pdf.js 의 영어 원문 대신
    return failed(pane, path, e?.password ? t('암호가 걸린 PDF 입니다 — 기본 앱으로 열어 보세요')
      : missing ? t('문서가 없거나(삭제·이동) 숨김 경로에 있습니다.')
        : broken ? t('PDF 를 읽지 못했습니다: {error}', { error: t('PDF 가 아니거나 깨진 파일입니다 — 다 받기 전에 저장했거나 다른 형식일 수 있습니다') })
          : t('PDF 를 읽지 못했습니다: {error}', { error: e?.message || String(e) }), { path, doc: null });
  }
  if (id !== pane.renderId) {   // 이 칸에서 그 사이 다른 것을 열었다 (다른 칸이 연 PDF 와는 상관없다)
    release(doc);
    return false;
  }
  const sizes = await sizesOf(doc).catch(() => null);
  if (!sizes || id !== pane.renderId) {
    release(doc);
    if (!sizes && id === pane.renderId) return failed(pane, path, t('PDF 를 읽지 못했습니다: {error}', { error: t('쪽이 없습니다') }));
    return false;
  }
  if (old && old.doc !== doc) {
    old.io?.disconnect();
    old.here?.disconnect();
    old.ro?.disconnect();
    clearInterval(old.heal);
    release(old.doc);
  }
  const st = { path, doc, sizes, fit: same ? old.fit : true, zoom: same ? old.zoom : 1, scale: 1, drawn: new Map(), cur: 1, texts: null, scanned: null, marks: null, io: null, here: null, ro: null };
  pane.pdf = st;
  if (!same) {
    view.className = 'pdf-view';
    delete view.dataset.docPath;   // 앞에 보던 md 문서의 경로 — 남아 있으면 그 문서의 기능이 이 화면에서 켜진다
    setHtml(view, skeleton(path));
  }
  pane.source = null;
  clearChanges(pane);
  view.querySelector('.pdf-total').textContent = `/ ${doc.numPages}`;
  layout(pane, st, false);
  await outline(pane, st);   // 책갈피가 있으면 목차 패널이 열려 칸 폭이 바뀐다 — 폭 맞춤 배율을 정한 뒤에 자리를 되살린다
  if (id !== pane.renderId || pane.pdf !== st) return false;
  if (st.fit && Math.abs(fitScale(pane, st) - st.scale) > 0.01) layout(pane, st, false);
  const page = /^page=(\d+)$/.exec(String(hash).replace(/^#/, ''));
  if (page) goPage(pane, st, Number(page[1]));
  else pane.scroller.scrollTop = top ?? 0;
  st.cur = pageAtTop(pane);
  st.ro = new ResizeObserver(() => {   // 폭 맞춤이면 칸 폭을 따라간다 (사이드바·목차를 열고 닫을 때)
    if (!st.fit || pane.pdf !== st) return;
    const next = fitScale(pane, st);
    if (Math.abs(next - st.scale) > 0.01) layout(pane, st);
  });
  st.ro.observe(view);
  st.heal = setInterval(() => heal(pane, st), 1000);
  pane.findProvider = finder(pane, st);
  showPage(pane, st);
  if (tab.changed.delete(path)) emit('changed');
  emit('rendered', pane);
  return true;
}

function zoom(pane, st, how) {
  if (how === 'fit') {
    st.fit = true;
  } else {
    const now = st.scale;
    const next = how > 0 ? ZOOMS.find((z) => z > now + 0.01) : [...ZOOMS].reverse().find((z) => z < now - 0.01);
    if (!next) return;
    st.fit = false;
    st.zoom = next;
  }
  layout(pane, st);
}

// ---- 찾기 (find.js 가 부른다) ----------------------------------------------------------

const norm = (s) => s.toLowerCase().replace(/\s/g, ' ');

/** 쪽의 글 — 글 층과 같게 이어 붙인다 (줄 끝은 빈칸 하나) */
async function textOf(st, n) {
  st.texts ??= [];
  if (st.texts[n - 1] == null) {
    const page = await st.doc.getPage(n);
    st.texts[n - 1] = norm((await page.getTextContent()).items.map((it) => (it.str ?? '') + (it.hasEOL ? ' ' : '')).join(''));
  }
  return st.texts[n - 1];
}

/** 그려진 쪽의 글 층에서 needle 의 k 번째 자리를 Range 로 */
function rangeIn(el, needle, k) {
  const layer = el.querySelector('.textLayer');
  if (!layer) return null;
  const parts = [];
  let text = '';
  const walker = document.createTreeWalker(layer, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node.nodeName === 'BR') text += ' ';
    if (node.nodeType !== Node.TEXT_NODE) continue;
    parts.push([text.length, node]);
    text += norm(node.nodeValue);
  }
  if (!parts.length) return null;
  let at = -1;
  for (let i = 0; i <= k; i += 1) {
    at = text.indexOf(needle, at + 1);
    if (at < 0) return null;
  }
  const find = (pos) => {
    let j = parts.length - 1;
    while (j > 0 && parts[j][0] > pos) j -= 1;
    return [parts[j][1], Math.min(pos - parts[j][0], parts[j][1].nodeValue.length)];
  };
  const [a, ao] = find(at);
  const [b, bo] = find(at + needle.length - 1);
  const r = document.createRange();
  r.setStart(a, ao);
  r.setEnd(b, Math.min(bo + 1, b.nodeValue.length));
  return r;
}

function finder(pane, st) {
  let hits = [];
  let needle = '';
  return {
    /** 모든 쪽에서 — 찾은 수 */
    async search(query) {
      needle = norm(query);
      hits = [];
      if (!needle.trim()) return 0;
      for (let n = 1; n <= st.doc.numPages && hits.length < MAX_HITS; n += 1) {
        const text = await textOf(st, n);
        if (pane.pdf !== st) return 0;
        for (let i = text.indexOf(needle), k = 0; i !== -1 && hits.length < MAX_HITS; i = text.indexOf(needle, i + needle.length), k += 1) hits.push({ page: n, k });
      }
      return hits.length;
    },
    /** i 번째로 가서 그 자리의 Range (그 쪽을 그린 뒤) */
    async go(i, scroll = true) {
      const h = hits[i];
      if (!h || pane.pdf !== st) return null;
      const el = pane.view.querySelector(`.pdf-pg[data-n="${h.page}"]`);
      if (scroll && Math.abs(h.page - st.cur) > 0) goPage(pane, st, h.page);
      for (let tries = 0; tries < 80 && !el.classList.contains('drawn'); tries += 1) await new Promise((r) => setTimeout(r, 50));
      const r = rangeIn(el, needle, h.k);
      if (r && scroll) {
        const box = pane.scroller.getBoundingClientRect();
        const rect = r.getBoundingClientRect();
        if (rect.top < box.top + 56 || rect.bottom > box.bottom - 24) pane.scroller.scrollTop += rect.top - box.top - box.height / 3;
      }
      return r;
    },
    /** 그려진 쪽에 있는 찾은 곳들 */
    visible() {
      const out = [];
      const per = new Map();
      for (const h of hits) {
        const el = st.drawn.has(h.page) && pane.view.querySelector(`.pdf-pg[data-n="${h.page}"].drawn`);
        if (!el) continue;
        per.set(h.page, (per.get(h.page) || 0) + 1);
        const r = rangeIn(el, needle, h.k);
        if (r) out.push(r);
        if (out.length > 300) break;
      }
      return out;
    },
    clear() {
      hits = [];
    },
  };
}

// ---- 고른 글·위치 (담기·보내기) ---------------------------------------------------------

/** 고른 글이 있는 쪽 */
export function pageOfSelection(pane) {
  const sel = getSelection();
  if (sel.isCollapsed || !pane.view.contains(sel.anchorNode)) return 0;
  const el = /** @type {Element} */ (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement)?.closest('.pdf-pg');
  return el ? Number(el.dataset.n) : 0;
}

/** Alt+C·Alt+Shift+C (docmenu.js): 고른 글을 조각으로 — 담은 곳은 그 쪽. 고른 글이 없으면 알리고 null */
export function pdfHere(pane = S.pane) {
  const st = pane?.pdf;
  if (!st?.doc) return null;
  const sel = getSelection();
  const text = !sel.isCollapsed && pane.view.contains(sel.anchorNode) ? sel.toString().replace(/[ \t]+\n/g, '\n').trim() : '';
  if (!text) {
    toast(st.scanned ? t('글자가 없는 PDF 라 담을 글이 없습니다 — 기본 앱이나 OCR 로 글을 만든 뒤에') : t('PDF 에서는 담을 글을 끌어 고른 뒤 Alt+C 를 누릅니다'));
    return null;
  }
  const page = pageOfSelection(pane) || st.cur;
  const one = text.replace(/\s+/g, ' ');
  return {
    snip: { path: st.path, lines: null, kind: 'text', name: t('고른 글'), label: one.length > 40 ? `${one.slice(0, 39)}…` : one, text, notes: '', plain: true, extra: { page: String(page) } },
    rect: sel.getRangeAt(0).getBoundingClientRect(),
  };
}

function sendRef(pane, st, e) {
  const text = `${pageRef(st)} `;
  if (e.key === 'ArrowLeft') {
    copyText(pageRef(st)).then((ok) => toast(ok ? t('복사했습니다: {what}', { what: pageRef(st) }) : t('복사하지 못했습니다')));
    return;
  }
  emit(e.ctrlKey ? 'term-paste-stay' : 'term-paste', { text, n: null, back: e.ctrlKey ? pane.scroller : null });
}

// ---- 키·누르기 ---------------------------------------------------------------------

function onKey(e) {
  const pane = S.pane;
  const inToc = !!e.target.closest?.('#lec-toc');   // 책갈피를 누른 뒤 — 초점이 목차에 남는다
  if (!isPdfView(pane) || (!inToc && !pane.scroller.contains(/** @type {Node} */ (e.target))) || e.isComposing) return;
  const st = pane.pdf;
  if (!st.doc) return;
  if (e.target.matches?.('.pdf-page')) {
    if (e.key === 'Enter') {
      e.preventDefault();
      goPage(pane, st, Number(e.target.value) || st.cur);
      pane.scroller.focus({ preventScroll: true });
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.target.value = String(st.cur);
      pane.scroller.focus({ preventScroll: true });
    }
    e.stopPropagation();
    return;
  }
  if (e.target.closest?.('input, textarea, #lec-findbar')) return;
  const mod = e.ctrlKey || e.metaKey;
  if (mod && !e.altKey && !e.shiftKey && ['=', '+', '-', '0'].includes(e.key)) {
    zoom(pane, st, e.key === '0' ? 'fit' : e.key === '-' ? -1 : 1);
  } else if (e.shiftKey && !e.altKey && !e.metaKey && (e.key === 'ArrowRight' || (e.key === 'ArrowLeft' && !e.ctrlKey))) {
    if (!e.repeat) sendRef(pane, st, e);
  } else if (!mod && !e.altKey && !e.shiftKey && (e.key === 'Home' || e.key === 'End')) {
    goPage(pane, st, e.key === 'Home' ? 1 : st.doc.numPages);
  } else if (inToc && !mod && !e.altKey && (e.key === 'PageDown' || e.key === 'PageUp' || e.key === ' ')) {
    pane.scroller.scrollTop += (e.key === 'PageUp' || (e.key === ' ' && e.shiftKey) ? -0.9 : 0.9) * pane.scroller.clientHeight;
  } else return;
  e.preventDefault();
  e.stopPropagation();   // 문서의 현재 줄 키로 가지 않게
}

function onClick(e) {
  const pane = S.pane;
  const view = /** @type {Element} */ (e.target).closest?.('.pdf-view');
  if (!view || pane?.view !== view) return;
  const st = pane.pdf;
  const act = /** @type {HTMLElement | null} */ (e.target.closest('[data-act]'))?.dataset.act;
  if (act === 'external') {
    openExternal(st?.path || pane.current?.path);
    return;
  }
  if (!st?.doc) return;
  if (act === 'in' || act === 'out') zoom(pane, st, act === 'in' ? 1 : -1);
  else if (act === 'fit') zoom(pane, st, 'fit');
  const link = /** @type {HTMLElement | null} */ (e.target.closest('a.pdf-link'));
  if (!link) return;
  e.preventDefault();
  if (link.dataset.url) {
    if (/^(https?:|mailto:)/i.test(link.dataset.url)) window.open(link.dataset.url, '_blank', 'noopener');
    else toast(t('이 링크는 열지 않습니다: {url}', { url: link.dataset.url }));
    return;
  }
  if (link.dataset.action) {   // 이름 있는 동작 — 첫 쪽·마지막 쪽·앞 쪽·뒤 쪽
    emit('jump');
    goPage(pane, st, namedPage(link.dataset.action, st, st.cur));
    return;
  }
  let dest = JSON.parse(link.dataset.dest || 'null');
  (async () => {
    if (typeof dest === 'string') dest = await st.doc.getDestination(dest);
    if (!Array.isArray(dest) || !dest[0]) return;
    emit('jump');
    goPage(pane, st, (await st.doc.getPageIndex(dest[0])) + 1);
  })().catch(() => toast(t('문서에서 해당 위치를 찾지 못했습니다')));
}

export function initPdf() {
  const panes = $('#lec-panes');
  panes.addEventListener('keydown', onKey);
  $('#lec-toc')?.addEventListener('keydown', onKey);
  panes.addEventListener('click', onClick);
  panes.addEventListener('wheel', (e) => {   // Ctrl+휠 — 확대 (창 전체 확대 대신)
    const pane = S.pane;
    if (!(e.ctrlKey || e.metaKey) || !isPdfView(pane) || !pane.scroller.contains(/** @type {Node} */ (e.target)) || !pane.pdf.doc) return;
    e.preventDefault();
    zoom(pane, pane.pdf, e.deltaY < 0 ? 1 : -1);
  }, { passive: false });
  on('rendered', (pane) => {   // 이 칸이 다른 화면으로 — 읽은 PDF 를 놓는다
    const st = pane.pdf;
    if (!st || pane.view.classList.contains('pdf-view')) return;
    st.io?.disconnect();
    st.here?.disconnect();
    st.ro?.disconnect();
    clearInterval(st.heal);
    release(st.doc);
    pane.pdf = null;
    pane.findProvider = null;
  });
  // 숨었던 칸이 다시 보일 때 (다른 문서 탭·프로젝트에서 돌아옴) — 지켜보기가 깨어나지 않을 때가 있어 다시 건다. 그 사이 폭이 바뀌었으면 맞춘다
  const wake = (pane) => {
    if (!isPdfView(pane) || !pane.pdf.doc) return;
    const st = pane.pdf;
    requestAnimationFrame(() => {
      if (pane.pdf !== st || !pane.view.clientWidth) return;
      if (st.fit && Math.abs(fitScale(pane, st) - st.scale) > 0.01) {
        layout(pane, st);
      } else {
        st.io?.disconnect();
        for (const el of pane.view.querySelectorAll('.pdf-pg')) st.io.observe(el);   // 다시 걸면 지금 보이는 쪽을 곧바로 알려 준다
      }
      showPage(pane, st);
    });
  };
  on('pane', wake);
  on('tab', () => wake(S.pane));
}

