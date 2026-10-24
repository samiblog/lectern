// 문서 화면: md 원문을 받아 렌더링하고, 링크·이미지·표·코드 블록·콜아웃을 다듬는다.

import { S, emit } from './store.js';
import { getText, openExternal } from './api.js';
import { renderMarkdown, splitFrontMatter } from './markdown.js';
import { renderMermaid } from './mermaid.js';
import { renderCharts } from './charts.js';
import { readDeck, slidesWanted, prepareDeck, fitDeck, showDeck } from './slides.js';
import { setToc } from './toc.js';
import { setupFolds, unfoldTo } from './fold.js';
import { setDocSource } from './docmenu.js';
import { snapshot, markChanges, clearChanges } from './diffmark.js';
import { linkPaths } from './pathlink.js';
import { setStatus } from './status.js';
import { paneOf } from './panes.js';
import { openLightbox } from './ui.js';
import { isViewable } from './icons.js';
import {
  $, $$, esc, docUrl, isMd, isHtml, toast, copyText, formatDateTime, findAnchor, dirname, newTabWanted,
} from './util.js';
import { t } from './i18n.js';

const PURIFY = {
  SANITIZE_DOM: false,          // 제목 id(예: 'title', 'images')가 지워지지 않도록. document 를 가리는 img 의 name 은 훅에서 지운다 (D15)
  FORBID_TAGS: ['style', 'form'],
  // DOMPurify 기본 허용 URL 에 file: 과 드라이브 경로(c:/, c:%5C — markdown-it 이 \ 를 %5C 로 바꾼다)를 더한다.
  // 이런 링크·그림은 resolveRef 가 프로젝트 안이면 상대경로로 바꾸고 밖이면 막는다 (ROADMAP 2-2)
  ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|matrix|file):|[a-z]:(?:[\\/]|%5c)|[^a-z]|[a-z+.-]+(?:[^a-z+.\-:]|$))/i,
};

const ALERTS = { NOTE: t('참고'), TIP: t('팁'), IMPORTANT: t('중요'), WARNING: t('경고'), CAUTION: t('주의') };

const MEDIA_TAGS = /^(IMG|SOURCE|VIDEO|AUDIO|TRACK|EMBED|INPUT)$/;
const SVG_NS = 'http://www.w3.org/2000/svg';
const SVG_IMAGE_TAGS = /^(image|feImage)$/;
// url(#id) 같은 문서 안 참조는 두고, 그 밖의 url()·image-set() 은 외부 요청이 될 수 있다
const URL_REF = /url\s*\(\s*['"]?\s*(?!#)|image-set\s*\(/i;
let purifyHookInstalled = false;

/**
 * HTML을 DOM에 넣는 순간 브라우저는 이미지를 내려받기 시작한다 (외부 주소 포함).
 * 그래서 정화 단계에서 src 를 data-src 로 옮겨 두고, fixImage 가 허용된 이미지에만 주소를 다시 준다.
 * (로컬 이미지는 항상, 외부 이미지는 설정 external_images 가 켜져 있을 때만)
 * 그 밖에 그림을 불러오는 길은 모두 지운다 — srcset·poster, 표의 background,
 * SVG image·feImage 의 href, style 과 SVG 속성(fill·mask·clip-path·marker 등)의 url()·image-set().
 * 여기서 놓친 길은 서버가 / 에 붙이는 CSP(img-src)가 막는다 (server.py content_security_policy).
 *
 * 앱 화면을 망가뜨리는 것도 지운다. <img name="querySelector"> 는 document.querySelector 를 가리고 (D15),
 * SVG 링크의 xlink:href 는 bindLink 가 보지 못해 누르면 앱 창이 그 주소로 떠나므로 href 로 옮긴다.
 */
function installPurifyHook() {
  if (purifyHookInstalled) return;
  purifyHookInstalled = true;
  window.DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    if (MEDIA_TAGS.test(node.nodeName) && node.hasAttribute('src')) {
      node.setAttribute('data-src', node.getAttribute('src'));
      node.removeAttribute('src');
    }
    if (node.nodeName === 'IMG') node.removeAttribute('name');
    node.removeAttribute('srcset');
    node.removeAttribute('poster');
    node.removeAttribute('background');
    const isSvg = node.namespaceURI === SVG_NS;
    if (isSvg && node.nodeName === 'a' && node.hasAttribute('xlink:href')) {
      if (!node.hasAttribute('href')) node.setAttribute('href', node.getAttribute('xlink:href'));
      node.removeAttribute('xlink:href');
    }
    if (isSvg && SVG_IMAGE_TAGS.test(node.nodeName)) {
      for (const name of ['href', 'xlink:href']) {
        const value = node.getAttribute(name);
        if (value && !/^\s*(#|data:)/i.test(value)) node.removeAttribute(name);
      }
    }
    for (const { name, value } of [...node.attributes]) {
      if ((name === 'style' || isSvg) && URL_REF.test(value)) node.removeAttribute(name);
    }
  });
}

// 숫자 열 판정: 1,234 / -3.5% / $105 / 105.2달러 / 12억 / 1.2x / 30bp / '-'
const NUM_CELL = /^(?:[-+−]?(?:[$₩€¥£]\s?)?[-+−]?\d[\d,]*(?:\.\d+)?\s?(?:%p?|bp|원|달러|억|만|조|배|x|[kKmMbB])?|[-–—])$/;

// ---------------------------------------------------------------------------
// 경로 해석

/**
 * 절대경로(C:\proj\a.md, C:/proj/a.md, \\server\share\a.md, file:///C:/proj/a.md)가 문서가 든 탭의 프로젝트 안이면 상대경로로 (ROADMAP 2-2).
 * 절대경로가 아니면 null, 프로젝트 밖이면 outside (다른 탭에 열린 프로젝트도 밖이다). markdown-it 이 \ 를 %5C 로 바꿔 주므로 풀어서 본다.
 * 경로 비교는 Windows처럼 대소문자를 가리지 않는다. 실제로 열 수 있는지는 서버의 resolve_inside 가 다시 본다.
 */
function absoluteRef(href, tab) {
  let raw = href;
  try { raw = decodeURIComponent(href); } catch { /* 그대로 */ }
  const unc = raw.startsWith('\\\\');
  let s = raw.replace(/\\/g, '/');
  if (/^file:/i.test(s)) {
    s = s.replace(/^file:\/*/i, '');
    if (!/^[a-z]:\//i.test(s)) s = `//${s}`;   // file://server/share → //server/share
  } else if (!/^[a-z]:\//i.test(s) && !unc) {
    return null;
  }
  const at = s.indexOf('#');
  const hash = at >= 0 ? s.slice(at) : '';
  const full = (at >= 0 ? s.slice(0, at) : s).replace(/\?.*$/, '');
  const root = (tab.root || '').replace(/\\/g, '/').replace(/\/+$/, '');
  const low = full.toLowerCase();
  if (!root || (low !== root.toLowerCase() && !low.startsWith(`${root.toLowerCase()}/`))) return { kind: 'outside' };
  const path = full.slice(root.length + 1).replace(/\/+$/, '');
  return { kind: 'local', path, hash, isDir: full.endsWith('/') || path === '' || tab.dirs.has(path) };
}

/**
 * 문서 속 href/src 를 해석한다. tab: 문서가 든 탭 — 그 프로젝트 안(/doc/<탭 id>/…)만 local 이다.
 * '../<다른 id>/x' 처럼 다른 탭 프로젝트로 넘어가는 상대경로는 밖으로 본다.
 */
export function resolveRef(href, baseUrl, tab) {
  if (!href) return { kind: 'none' };
  if (href.startsWith('#')) return { kind: 'anchor', hash: href };
  if (/^data:/i.test(href)) return { kind: 'data' };
  const abs = absoluteRef(href, tab);
  if (abs) return abs;
  if (/^(https?:|mailto:)/i.test(href) || href.startsWith('//')) return { kind: 'external', url: href };
  if (/^[a-z][a-z0-9+.-]*:/i.test(href)) return { kind: 'blocked' };
  const base = `/doc/${tab.id}/`;
  let url;
  try {
    url = new URL(href.startsWith('/') ? `${base}${href.slice(1)}` : href, baseUrl);   // '/docs/a.md' = 프로젝트 루트 기준
  } catch {
    return { kind: 'blocked' };
  }
  if (url.origin !== location.origin || !url.pathname.startsWith(base)) return { kind: 'outside' };
  let path;
  try {
    path = url.pathname.slice(base.length).split('/').map(decodeURIComponent).join('/');
  } catch {
    return { kind: 'blocked' };
  }
  const isDir = path.endsWith('/') || path === '';
  return { kind: 'local', path: path.replace(/\/+$/, ''), hash: url.hash, isDir };
}

/** 문서 안의 앵커로 스크롤. 접힌 절 안이면 펴서 보여 준다. root 는 #lec-view 또는 html 문서(iframe)의 document */
export function scrollToAnchor(root, hash) {
  const el = findAnchor(root, hash);
  if (!el) return false;
  unfoldTo(el);
  el.scrollIntoView({ block: 'start' });
  return true;
}

const lineFromHash = (hash) => {
  const m = /^#L(\d+)/i.exec(hash || '');
  return m ? +m[1] : undefined;
};

// ---------------------------------------------------------------------------
// 렌더링 후 다듬기

/**
 * 문서 속 링크를 앱 안의 동작으로 바꾼다. tab: 문서가 든 탭. root 는 앵커(#id)를 찾을 곳 — html 문서면 iframe 의 document (htmldoc.js).
 * 링크는 보이는 칸(선택된 탭)에서만 누를 수 있으므로, 여는 동작은 선택된 탭에서 한다 ('open' → nav.js).
 */
export function bindLink(a, baseUrl, docPath, tab, root = null) {
  const r = resolveRef(a.getAttribute('href'), baseUrl, tab);
  const where = () => root || paneOf(a)?.view;
  // 우클릭 메뉴의 '링크 주소 복사'가 쓸 값: 인터넷 주소, 또는 프로젝트 기준 경로(#앵커 포함)
  const target = { external: r.url, local: `${r.path || ''}${r.hash || ''}`, anchor: `${docPath}${r.hash}` }[r.kind];
  a.dataset.lecHref = target || a.getAttribute('href');
  switch (r.kind) {
    case 'anchor':
      a.addEventListener('click', (e) => {
        e.preventDefault();
        if (!scrollToAnchor(where(), r.hash)) toast(t('문서에서 해당 위치를 찾지 못했습니다'));
      });
      break;
    case 'external':
      // SVG <a> 의 target 은 읽기 전용 속성이라 대입하면 오류가 난다
      a.setAttribute('target', '_blank');
      a.setAttribute('rel', 'noopener noreferrer');
      a.classList.add('ext');
      a.title = r.url;
      if (a.ownerDocument !== document) {
        // html 문서(iframe sandbox)는 새 창을 열 수 없으므로 앱이 연다 (창 모드에서는 기본 브라우저로)
        a.addEventListener('click', (e) => {
          e.preventDefault();
          window.open(r.url, '_blank', 'noopener');
        });
      }
      break;
    case 'local':
      a.title = r.path || t('프로젝트 루트');
      if (r.isDir || tab.dirs.has(r.path)) {
        a.addEventListener('click', (e) => {
          e.preventDefault();
          emit('open', { type: 'overview', path: r.path });
        });
      } else if (isMd(r.path) || (isHtml(r.path) && tab.fileMap.has(r.path))) {
        // html 은 트리에 보이는 문서일 때만 뷰어로 연다 (src 등 소스 폴더의 html 은 편집기로)
        a.addEventListener('click', (e) => {
          e.preventDefault();
          if (r.path === docPath && r.hash && !newTabWanted(e)) {
            if (!scrollToAnchor(where(), r.hash)) toast(t('문서에서 해당 위치를 찾지 못했습니다'));
          } else {
            emit('open', { type: 'doc', path: r.path, hash: r.hash, newTab: newTabWanted(e) });   // Ctrl+누르기·가운데 버튼: 새 문서 탭 (D64)
          }
        });
      } else if (isViewable(r.path.split('/').pop())) {
        // 코드 파일·csv·txt: 읽기 화면의 그 줄로 (#L42) — 편집기는 우클릭 메뉴 (D43·D60)
        a.classList.add('file-link');
        a.addEventListener('click', (e) => {
          e.preventDefault();
          emit('open', { type: 'code', path: r.path, line: lineFromHash(r.hash), newTab: newTabWanted(e) });
        });
      } else {
        a.classList.add('file-link');
        a.addEventListener('click', (e) => {
          e.preventDefault();
          openExternal(r.path, lineFromHash(r.hash));
        });
      }
      break;
    default:
      a.classList.add('link-off');
      a.title = t('프로젝트 폴더 밖이거나 열 수 없는 경로');
      a.addEventListener('click', (e) => {
        e.preventDefault();
        toast(t('프로젝트 폴더 밖의 경로는 열지 않습니다'));
      });
  }
}

const EXTERNAL_IMAGE_TIMEOUT_MS = 15000;   // 사내망에서 막힌 주소는 응답 없이 오래 걸릴 수 있다
// 불러오지 못한 외부 이미지. 자동 새로고침마다 다시 15초를 기다리거나 '바뀐 곳'으로 잡히지 않게 바로 링크로 둔다 (F5 로 다시 시도)
const failedImages = new Set();
export const forgetFailedImages = () => failedImages.clear();

/** 이미지 자리에 넣을 대체 표시. url 이 있으면 브라우저로 여는 링크가 된다. */
function imageStandIn(label, alt, url) {
  const el = document.createElement(url ? 'a' : 'span');
  el.className = 'image-off';
  el.textContent = `${label}${alt ? `: ${alt}` : ''}`;
  if (url) {
    el.href = url;
    el.target = '_blank';
    el.rel = 'noopener noreferrer';
    el.title = url;
  }
  return el;
}

function makeZoomable(img) {
  img.classList.add('zoomable');
  img.addEventListener('click', () => openLightbox(img.cloneNode()));
}

function fixImage(img, baseUrl, stamp, tab, zoom = true) {
  const src = img.getAttribute('data-src');
  img.removeAttribute('data-src');
  const r = resolveRef(src, baseUrl, tab);
  if (r.kind === 'data') {
    img.src = src;
    return;
  }
  if (r.kind === 'local') {
    img.src = `${docUrl(tab, r.path)}?v=${stamp}`;   // 다시 그릴 때 바뀐 이미지가 보이도록
    img.loading = 'lazy';
    if (zoom) makeZoomable(img);
    return;
  }
  const isWebImage = r.kind === 'external' && /^(https?:)?\/\//i.test(r.url);
  if (!isWebImage) {
    img.replaceWith(imageStandIn(t('표시할 수 없는 그림'), img.alt));
    return;
  }
  if (S.config.external_images === false) {
    img.replaceWith(imageStandIn(t('인터넷 그림 (설정에서 꺼 둠)'), img.alt, r.url));
    return;
  }
  if (failedImages.has(r.url)) {
    img.replaceWith(imageStandIn(t('인터넷 그림을 불러오지 못했습니다'), img.alt, r.url));
    return;
  }
  // 외부 이미지: 문서 주소가 전달되지 않게 referrer 를 숨기고, 실패·시간 초과면 링크로 바꾼다
  img.referrerPolicy = 'no-referrer';
  img.classList.add('external');
  img.title = img.title || r.url;
  let settled = false;
  const fail = () => {
    if (settled) return;
    settled = true;
    failedImages.add(r.url);
    img.replaceWith(imageStandIn(t('인터넷 그림을 불러오지 못했습니다'), img.alt, r.url));
  };
  img.addEventListener('load', () => { settled = true; }, { once: true });
  img.addEventListener('error', fail, { once: true });
  setTimeout(() => { if (!settled && !(img.complete && img.naturalWidth)) fail(); }, EXTERNAL_IMAGE_TIMEOUT_MS);
  if (zoom) makeZoomable(img);
  img.src = r.url;
}

// ---- 모아 보기(parts.js)가 쓰는 것: 문서를 화면 밖에서 본문과 같은 규칙으로 읽고, 그림을 본문과 같은 규칙으로 불러온다 ----

/** md 렌더링 결과를 본문과 같은 규칙으로 정화한다 (그림 주소는 data-src 로 떼어 둔다 — 넣어도 내려받지 않는다) */
export function sanitizeHtml(html) {
  installPurifyHook();
  return window.DOMPurify.sanitize(html, PURIFY);
}

/** 화면 밖 조각의 콜아웃·표·코드 블록을 본문처럼 꾸민다 (목차·모아 보기가 같은 규칙으로 세게) */
export function prepareParts(root) {
  decorateAlerts(root);
  decorateTables(root);
  decorateCode(root);
}

/** 그림(img, data-src 에 문서 속 주소)을 docPath 문서 기준으로 불러온다 — 프로젝트 밖은 막고, 인터넷 그림은 설정을 따른다 */
export function loadImage(img, docPath, tab, { zoom = false } = {}) {
  fixImage(img, new URL(docUrl(tab, docPath), location.origin), Date.now(), tab, zoom);
}

/** 문서 속 그림 주소가 가리키는 것 (같은 그림을 한 번만 보이려고): 프로젝트 안이면 경로, 인터넷이면 주소 */
export function imageKey(src, docPath, tab) {
  const r = resolveRef(src, new URL(docUrl(tab, docPath), location.origin), tab);
  return r.kind === 'local' ? r.path : r.kind === 'external' ? r.url : `${docPath}#${src}`;
}

function decorateAlerts(root) {
  for (const bq of $$('blockquote', root)) {
    const p = bq.firstElementChild;
    if (!p || p.tagName !== 'P') continue;
    const first = p.firstChild;
    if (!first || first.nodeType !== Node.TEXT_NODE) continue;
    const m = /^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*/i.exec(first.nodeValue);
    if (!m) continue;
    const kind = m[1].toUpperCase();
    first.nodeValue = first.nodeValue.slice(m[0].length);
    if (p.firstChild?.nodeName === 'BR') p.firstChild.remove();
    if (!p.textContent.trim() && !p.querySelector('img')) p.remove();
    bq.classList.add('alert', `alert-${kind.toLowerCase()}`);
    const title = document.createElement('p');
    title.className = 'alert-title';
    title.textContent = ALERTS[kind];
    bq.prepend(title);
  }
}

function markNumericColumns(table) {
  const rows = $$(':scope > tbody > tr', table);
  if (!rows.length) return;
  const cols = Math.max(...rows.map((r) => r.cells.length));
  for (let c = 0; c < cols; c++) {
    let filled = 0;
    let numeric = 0;
    for (const r of rows) {
      const text = r.cells[c]?.textContent.trim();
      if (!text) continue;
      filled += 1;
      if (NUM_CELL.test(text)) numeric += 1;
    }
    if (!filled || numeric / filled < 0.7) continue;
    for (const r of $$(':scope > thead > tr, :scope > tbody > tr', table)) {
      const cell = r.cells[c];
      if (cell && !cell.style.textAlign) cell.classList.add('num');
    }
  }
}

function decorateTables(root) {
  for (const table of $$('table', root)) {
    if (table.closest('.front-matter')) continue;
    const wrap = document.createElement('div');
    wrap.className = 'table-wrap';
    table.replaceWith(wrap);
    wrap.append(table);
    markNumericColumns(table);
  }
}

function decorateCode(root) {
  for (const pre of $$('pre', root)) {
    if (pre.matches('.mermaid, .lec-chart') || pre.closest('.front-matter')) continue;
    const code = pre.querySelector(':scope > code');
    if (!code) continue;
    code.classList.add('hljs');
    const lang = (/language-([\w+#.-]+)/.exec(code.className) || [])[1] || '';
    const box = document.createElement('div');
    box.className = 'code-block';
    pre.replaceWith(box);
    const tools = document.createElement('div');
    tools.className = 'code-tools';
    tools.innerHTML = `${lang ? `<span class="code-lang">${esc(lang)}</span>` : ''}<button type="button" class="code-copy">${t('복사')}</button>`;
    box.append(tools, pre);
    tools.querySelector('button').addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      const ok = await copyText(code.textContent);
      btn.textContent = ok ? t('복사됨') : t('복사 실패');
      setTimeout(() => { btn.textContent = t('복사'); }, 1400);
    });
  }
}

/** 박스글·표·코드 블록 꾸미기만 (사용설명서 — help.js. 링크·그림은 부르는 쪽이 다룬다) */
export function decorateBlocks(root) {
  decorateAlerts(root);
  decorateTables(root);
  decorateCode(root);
}

function frontMatterHtml(raw) {
  const entries = [];
  let simple = true;
  for (const line of raw.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const m = /^([A-Za-z0-9_.-]+)\s*:\s*(.*)$/.exec(line);
    if (m) entries.push([m[1], m[2]]);
    else if (entries.length && /^\s/.test(line)) entries[entries.length - 1][1] += `\n${line.trim()}`;
    else simple = false;
  }
  if (!simple || !entries.length) {
    return `<details class="front-matter" open><summary>${t('메타데이터')}</summary><pre>${esc(raw)}</pre></details>`;
  }
  const rows = entries.map(([k, v]) => {
    const value = v.replace(/^[|>]-?\s*\n?/, '').replace(/^(["'])(.*)\1$/s, '$2');
    return `<tr><th>${esc(k)}</th><td>${esc(value)}</td></tr>`;
  }).join('');
  return `<details class="front-matter" open><summary>${t('메타데이터')}</summary><table>${rows}</table></details>`;
}

function enhance(root, docPath, stamp, tab) {
  const baseUrl = new URL(docUrl(tab, docPath), location.origin);
  for (const img of $$('img[data-src]', root)) fixImage(img, baseUrl, stamp, tab);
  for (const a of $$('a[href], area[href]', root)) bindLink(a, baseUrl, docPath, tab);   // 이미지 맵의 area 도 링크
  decorateAlerts(root);
  decorateTables(root);
  decorateCode(root);
}

// ---------------------------------------------------------------------------

export function showMissing(view, path, err) {
  view.className = 'md-body';
  const parent = dirname(path);
  const reason = err?.status === 404 ? t('문서가 없거나(삭제·이동) 숨김 경로에 있습니다.') : t('문서를 읽지 못했습니다: {error}', { error: err?.message || '' });
  view.innerHTML = `<div class="doc-missing"><h1>${esc(path)}</h1><p>${esc(reason)}</p>
    <p><button type="button" class="primary" data-parent="${esc(parent)}">${parent ? esc(t('{folder} 폴더 개요 보기', { folder: parent })) : t('프로젝트 개요 보기')}</button></p></div>`;
  view.querySelector('button').addEventListener('click', () => emit('open', { type: 'overview', path: parent }));
}

/**
 * 문서를 칸(pane)에 그린다. 프로젝트는 칸의 탭(pane.tab)이다 — 그리는 중에 다른 탭을 골라도 이 탭에 그린다.
 * - 화면 밖 무대(stage)에서 먼저 그린 뒤 한 번에 바꿔 끼워, 자동 새로고침 때 깜박임과 스크롤 튐을 막는다.
 * - 그 칸에서 더 나중에 시작한 렌더링이 있으면 결과를 버린다(false 반환).
 */
export async function showDoc(pane, path, { hash = '', scrollTop, missing = false } = {}) {
  const id = ++pane.renderId;
  const { view, scroller: content, tab } = pane;

  let text;
  try {
    // missing: 아직 만들지 않은 새 문서 (D63 — 편집 상자가 위를 덮는다). 읽어 보지 않고 '문서 없음' 화면으로
    if (missing) throw Object.assign(new Error('missing'), { status: 404 });
    text = await getText(docUrl(tab, path));
  } catch (err) {
    if (id !== pane.renderId) return false;
    showMissing(view, path, err);
    setDocSource(pane, null);
    clearChanges(pane);
    setToc(pane, null);
    setStatus({ path, info: '' }, pane);
    emit('rendered', pane);
    return true;
  }
  if (id !== pane.renderId) return false;

  installPurifyHook();
  // 발표 문서(맨 앞 설정에 marp: true — D59)는 슬라이드로. 상태줄의 '문서로 보기'를 골랐으면 보통 문서처럼
  const marp = readDeck(splitFrontMatter(text).frontMatter);
  const deck = marp && slidesWanted(pane, path) ? marp : null;
  const { html, frontMatter } = renderMarkdown(text, { math: S.config.math !== false, deck });
  const viewClass = `md-body${marp ? ' lec-marp' : ''}${deck ? ' lec-deck' : ''}`;
  const stage = document.createElement('article');
  stage.className = `${viewClass} lec-stage`;
  stage.style.width = `${content.clientWidth}px`;
  if (deck) stage.style.setProperty('--slide-scale', '1');   // 무대에서는 줄이지 않는다 — Mermaid 가 글자 크기를 제대로 잰다
  stage.innerHTML = (frontMatter && !deck ? frontMatterHtml(frontMatter) : '') + window.DOMPurify.sanitize(html, PURIFY);
  document.body.append(stage);
  try {
    enhance(stage, path, Date.now(), tab);
    if (deck) prepareDeck(stage, deck);   // 배경 그림·그림 크기·style: CSS
    await renderMermaid(stage);
    await renderCharts(stage, { tab, path, sanitize: sanitizeHtml, resolveRef });   // ```vega-lite·```echarts·```dot (D56)
    await linkPaths(stage, path, tab);   // 본문 속 `src/app.py:42` 같은 경로 표기를 링크로 (서버에 있는지 묻는다)
    if (deck) fitDeck(stage);   // 넘치는 슬라이드의 그림을 줄인다 (그린 뒤에 잰다)
  } finally {
    stage.remove();
  }
  if (id !== pane.renderId) return false;

  // 같은 문서를 다시 그리면(자동 새로고침) 바뀐 블록을 강조하려고 이전 화면을 기록해 둔다
  // 슬라이드 ↔ 문서로 바꾼 것(D59)은 바뀐 곳이 아니다
  const sameDoc = pane.current?.type === 'doc' && pane.current.path === path && !$('.doc-missing', view)
    && view.classList.contains('lec-deck') === !!deck;
  const before = sameDoc ? snapshot(view) : null;
  const top = typeof scrollTop === 'function' ? scrollTop() : scrollTop;   // 함수면 바꿔 끼우기 직전의 위치 (refreshView)
  view.className = viewClass;
  view.dataset.docPath = path;   // 장 하이라이트(spotlight.js)·접기(fold.js)가 어느 문서를 그렸는지 본다
  view.replaceChildren(...stage.childNodes);
  if (deck) showDeck(pane);   // 슬라이드를 칸 폭에 맞춰 줄인다 (스크롤 위치를 정하기 전에 — 높이가 달라진다)
  else view.style.removeProperty('--slide-scale');
  setupFolds(view, path);   // 스크롤 위치를 정하기 전에: 접힌 절이 있으면 문서 높이가 다르다
  setDocSource(pane, path, text);
  setToc(pane, view);
  if (top != null) content.scrollTop = top;
  else if (!hash || !scrollToAnchor(view, hash)) content.scrollTop = 0;
  markChanges(view, before, pane);

  if (tab.changed.delete(path)) emit('changed');
  const file = tab.fileMap.get(path);
  setStatus({ path, info: file ? t('수정 {when}', { when: formatDateTime(file.mtime) }) : '' }, pane);
  emit('rendered', pane);
  return true;
}
