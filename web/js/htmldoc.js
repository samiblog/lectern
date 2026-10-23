// html 문서 보기 (D27): <iframe sandbox="allow-same-origin"> 에 /doc/<탭 id>/<경로> 를 띄운다.
//
// - 문서 자신의 스크립트·인라인 이벤트·폼은 돌지 않는다 (iframe sandbox 에 allow-scripts 가 없고, 서버 CSP 도 막는다).
//   같은 출처라서 앱(부모)이 iframe 안을 읽고 이벤트를 붙여 목차·찾기·링크·우클릭 메뉴·바뀐 부분 강조를 다룬다.
// - iframe 높이를 문서 높이에 맞춰 칸의 스크롤 상자(.lec-scroll)가 스크롤한다 (md 와 같게 스크롤 위치·마지막 위치가 동작).
// - 문서에 스타일(CSS)이 있으면 그대로, 없으면 지금 고른 Lectern 스타일을 입힌다 (사용자가 고름).
// - 자동 새로고침 때는 새 iframe 을 보이지 않게 겹쳐 불러온 뒤 바꿔 끼운다 (깜박임과 스크롤 튐 방지).

import { S, emit, on } from './store.js';
import { bindLink, showMissing, scrollToAnchor } from './doc.js';
import { setToc } from './toc.js';
import { setStatus } from './status.js';
import { setDocSource, frameContextMenu } from './docmenu.js';
import { hideMenu } from './ui.js';
import { snapshot, markChanges, clearChanges } from './diffmark.js';
import { textScale } from './textsize.js';
import { $, docUrl, formatDateTime } from './util.js';

const LOAD_TIMEOUT_MS = 20000;
const MAX_HEIGHT = 200000;
const XLINK = 'http://www.w3.org/1999/xlink';

/** 칸 화면(view)의 html 문서 iframe (없으면 null) */
const frameIn = (view) => view.querySelector(':scope > iframe.lec-html:not(.lec-loading)');

function load(frame) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(false), LOAD_TIMEOUT_MS);
    frame.addEventListener('load', () => { clearTimeout(timer); resolve(true); }, { once: true });
  });
}

function link(doc, href) {
  const el = doc.createElement('link');
  el.rel = 'stylesheet';
  el.href = href;
  return el;
}

/** 문서가 실제로 불러온 스타일이 있는지 (CSP로 막힌 인터넷 CSS는 없는 것과 같다) */
function hasOwnStyle(doc) {
  return [...doc.styleSheets].some((sheet) => {
    try {
      return sheet.cssRules.length > 0;
    } catch {
      return true;
    }
  });
}

/**
 * 문서 내용의 높이. scrollHeight 는 iframe 자신의 높이보다 작아지지 않아(접은 <details>, 창을 넓힘) 줄어들 때를 놓친다.
 * 그래서 html 상자의 높이와 body 자식들의 아래 끝을 잰다. 호환 모드(doctype 없음)는 html·body 가 창 높이를 채우므로 자식만.
 */
function contentHeight(doc) {
  const win = doc.defaultView;
  const root = doc.documentElement;
  let h = doc.compatMode === 'CSS1Compat' ? root.getBoundingClientRect().height : 0;
  const body = doc.body;
  if (body) {
    let bottom = 0;
    for (const el of body.children) bottom = Math.max(bottom, el.getBoundingClientRect().bottom);
    const s = win.getComputedStyle(body);
    h = Math.max(h, bottom + win.scrollY + parseFloat(s.paddingBottom) + parseFloat(s.borderBottomWidth) + parseFloat(s.marginBottom));
  }
  return Math.ceil(h);
}

/** iframe 높이를 문서 높이에 맞춘다. 100vh 를 쓰는 문서가 끝없이 커지지 않게, 같은 만큼 계속 커지면 멈춘다 */
function fitHeight(frame) {
  const doc = frame.contentDocument;
  let last = 0;
  let lastGrow = 0;
  let repeats = 0;
  const fit = () => {
    const h = contentHeight(doc);
    const grow = h - last;
    if (Math.abs(grow) < 2) return;
    repeats = grow > 0 && grow === lastGrow ? repeats + 1 : 0;
    if (repeats > 3) return;
    lastGrow = grow;
    last = h;
    frame.style.height = `${Math.min(h, MAX_HEIGHT)}px`;
  };
  fit();
  const watch = new ResizeObserver(fit);
  watch.observe(doc.documentElement);
  if (doc.body) watch.observe(doc.body);
  doc.addEventListener('toggle', fit, true);   // <details> 열고 닫기 (호환 모드에서는 상자 크기가 그대로라 관찰자가 모른다)
}

// ---- 읽을 수 있는 바탕 ------------------------------------------------------
// iframe 의 '다크 선호(prefers-color-scheme)'는 Lectern 스타일이 아니라 Windows 설정을 따르고, 색 모드(color-scheme)가
// 앱과 다르면 Chromium 이 iframe 바탕을 흰색으로 칠한다. 그래서 밝은 글자가 흰 바탕에 묻히는 일이 생긴다.
// 문서가 쪽 바탕을 직접 칠하지 않으면, 그 위에 바로 놓인 글자의 밝기를 보고 바탕을 정해 준다.

const appIsDark = () => document.documentElement.dataset.ui === 'dark';
const appBg = () => getComputedStyle(document.documentElement).getPropertyValue('--md-bg').trim() || '#ffffff';

/** 계산된 색 → {rgb: 0~255, a}. color-mix() 등은 'color(srgb 0.9 0.9 0.9 / a)' 처럼 0~1 로 나온다 */
function rgba(color) {
  const n = (color.match(/[\d.]+/g) || []).map(Number);
  const unit = color.startsWith('color(') ? 255 : 1;
  return { rgb: n.slice(0, 3).map((x) => x * unit), a: n.length > 3 ? n[3] : 1 };
}

const luminance = ([r, g, b]) => [r, g, b].map((x) => {
  const c = x / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}).reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);

/**
 * 문서가 쪽 바탕을 직접 칠하지 않을 때 깔아 줄 바탕 'dark' | 'light'. 칠하면 null.
 * 바탕을 칠한 상자(카드 등) 안의 글자는 빼고, 쪽 바탕 위에 바로 놓인 글자의 밝기를 글자 수로 따진다.
 */
function backdropFor(doc) {
  const win = doc.defaultView;
  const painted = (el) => {
    const s = win.getComputedStyle(el);
    return s.backgroundImage !== 'none' || rgba(s.backgroundColor).a > 0.5;
  };
  if (painted(doc.documentElement) || painted(doc.body)) return null;
  let light = 0;
  let dark = 0;
  const els = [...doc.body.querySelectorAll('p, li, td, th, dt, dd, h1, h2, h3, h4, h5, h6, blockquote, figcaption, a, span, div')];
  for (const el of els.slice(0, 600)) {
    const text = [...el.childNodes].filter((n) => n.nodeType === Node.TEXT_NODE).map((n) => n.nodeValue.trim()).join('');
    if (!text) continue;
    let onBox = false;
    for (let a = el; a && a !== doc.body; a = a.parentElement) if (painted(a)) { onBox = true; break; }
    if (onBox) continue;
    if (luminance(rgba(win.getComputedStyle(el).color).rgb) > 0.4) light += text.length;
    else dark += text.length;
  }
  return light > dark ? 'dark' : 'light';
}

/** 쪽 바탕을 칠한다. 앱 스타일과 밝기가 같으면 그 스타일의 바탕색, 다르면 무난한 흰색·짙은 회색 */
function paintBackdrop(doc, scheme) {
  const root = doc.documentElement;
  root.style.colorScheme = scheme;
  root.style.backgroundColor = (scheme === 'dark') === appIsDark() ? appBg() : (scheme === 'dark' ? '#1e2227' : '#ffffff');
  root.dataset.lecBackdrop = scheme;
}

/** 툴바의 글자 크기: 스타일 없는 문서는 Lectern 스타일의 --md-scale, 스타일 있는 문서는 문서 전체 zoom (높이는 fitHeight 가 다시 맞춘다) */
function applyScale(frame) {
  const doc = frame.contentDocument;
  if (!doc) return;
  const s = textScale();
  if (frame.classList.contains('own-style')) doc.documentElement.style.zoom = s === 1 ? '' : String(s);
  else doc.documentElement.style.setProperty('--md-scale', String(s));
}
on('text-size', () => {
  for (const pane of S.panes) {
    const frame = frameIn(pane.view);
    if (frame) applyScale(frame);
  }
});

function prepare(frame, path, tab) {
  const doc = frame.contentDocument;
  const own = hasOwnStyle(doc);
  doc.head.append(link(doc, '/static/css/frame.css'));   // 찾기 표시·바뀐 곳·우클릭 테두리
  if (own) {
    frame.classList.add('own-style');
    const scheme = backdropFor(doc);
    if (scheme) paintBackdrop(doc, scheme);
  } else {
    // 스타일이 없는 문서: 지금 고른 Lectern 스타일을 입히고, 바탕과 색 모드도 앱과 맞춘다
    doc.head.append(link(doc, '/static/themes/base.css'), link(doc, $('#lec-theme-css').href));
    doc.body.classList.add('md-body');
    paintBackdrop(doc, appIsDark() ? 'dark' : 'light');
  }
  applyScale(frame);
  let n = 0;
  for (const h of doc.querySelectorAll('h1, h2, h3, h4')) if (!h.id) h.id = `lec-h${++n}`;   // 목차용
  const baseUrl = new URL(docUrl(tab, path), location.origin);
  // SVG 의 옛 링크(xlink:href)도 bindLink 가 다루게 한다 — 아니면 누를 때 iframe 이 그 주소로 떠나 문서를 잃는다
  for (const a of doc.querySelectorAll('a')) {
    if (!a.hasAttribute('href') && a.hasAttributeNS(XLINK, 'href')) a.setAttribute('href', a.getAttributeNS(XLINK, 'href'));
  }
  for (const a of doc.querySelectorAll('a[href], area[href]')) bindLink(a, baseUrl, path, tab, doc);
  doc.addEventListener('contextmenu', (e) => frameContextMenu(e, frame));
  // iframe 안의 키·마우스는 앱 문서로 올라오지 않는다. 단축키(Ctrl+F, Esc, Alt+← …)와 마우스 뒤로 버튼, 메뉴 닫기를 위해 넘겨 준다
  doc.addEventListener('keydown', (e) => {
    if (!document.dispatchEvent(new KeyboardEvent('keydown', e))) e.preventDefault();
  });
  doc.addEventListener('mousedown', hideMenu);   // 앱의 메뉴는 바깥을 누르면 닫힌다 — iframe 안의 누름은 앱 문서에 오지 않는다
  doc.addEventListener('mouseup', (e) => {
    if (e.button === 3 || e.button === 4) window.dispatchEvent(new MouseEvent('mouseup', { button: e.button }));
  });
  fitHeight(frame);
}

/** 문서를 보여 줄 수 없을 때: 안내 화면으로 바꾸고 옛 문서의 목차·원문·바뀐 곳도 지운다 */
function missing(pane, path, err) {
  showMissing(pane.view, path, err);
  setDocSource(pane, null);
  clearChanges(pane);
  setToc(pane, null);
  setStatus({ path, info: '' }, pane);
  emit('rendered', pane);
  return true;
}

/**
 * html 문서를 칸(pane)에 그린다 (nav.js 가 확장자로 고른다). 프로젝트는 칸의 탭(pane.tab)이다.
 * 그 칸에서 더 나중에 시작한 렌더링이 있으면 결과를 버린다(false).
 */
export async function showHtml(pane, path, { hash = '', scrollTop } = {}) {
  const id = ++pane.renderId;
  const { view, scroller: content, tab } = pane;
  const src = docUrl(tab, path);
  const head = await fetch(src, { method: 'HEAD', cache: 'no-store' }).catch((e) => ({ ok: false, status: 0, statusText: e.message }));
  if (id !== pane.renderId) return false;
  if (!head.ok) return missing(pane, path, { status: head.status, message: head.statusText });

  // 같은 문서를 다시 그리는지는 화면의 iframe 이 이 문서를 다 불러온 것인지로 본다. 다른 문서를 불러오는 중인
  // 빈 iframe 과 비교하면(A → B → 빠르게 A) A 의 모든 블록이 '바뀐 곳'이 된다
  const old = frameIn(view);
  const sameDoc = old?.dataset.ready === path && pane.current?.type === 'doc' && pane.current.path === path;
  const before = sameDoc && old.contentDocument?.body ? snapshot(old.contentDocument.body) : null;
  const frame = document.createElement('iframe');
  frame.className = 'lec-html';
  // allow-scripts 를 주지 않는다 (D27). allow-modals 는 앱이 이 문서를 인쇄(print)하려고 — 스크립트가 없으니 문서는 쓸 수 없다
  frame.setAttribute('sandbox', 'allow-same-origin allow-modals');
  frame.title = path;
  if (sameDoc) {
    frame.classList.add('lec-loading');   // 옛 문서 위에 보이지 않게 겹쳐 불러온다 (iframe 은 옮기면 다시 불러오므로 제자리에서)
    view.append(frame);
  } else {
    view.className = 'html-view';
    view.replaceChildren(frame);
  }
  frame.src = `${src}?v=${Date.now()}`;
  const ok = await load(frame);
  if (id !== pane.renderId) {
    if (sameDoc) frame.remove();
    return false;
  }
  if (!ok) return missing(pane, path, { status: 0, message: '시간이 너무 오래 걸립니다. F5 를 누르면 다시 불러옵니다' });
  // HEAD 뒤에 지워지면 404 응답(CSP sandbox)이 들어와 문서를 읽을 수 없다
  if (!frame.contentDocument?.body) return missing(pane, path, { status: 404 });
  const top = typeof scrollTop === 'function' ? scrollTop() : scrollTop;   // 함수면 바꿔 끼우기 직전의 위치 (refreshView)
  prepare(frame, path, tab);
  frame.dataset.ready = path;
  if (sameDoc) {
    old.remove();
    frame.classList.remove('lec-loading');
  }
  const doc = frame.contentDocument;
  setToc(pane, doc.body);
  if (top != null) content.scrollTop = top;
  else if (!hash || !scrollToAnchor(doc, hash)) content.scrollTop = 0;
  setDocSource(pane, path, '');
  markChanges(doc.body, before, pane);

  if (tab.changed.delete(path)) emit('changed');
  const file = tab.fileMap.get(path);
  setStatus({ path, info: file ? `HTML · 수정 ${formatDateTime(file.mtime)}` : 'HTML' }, pane);
  emit('rendered', pane);
  return true;
}
