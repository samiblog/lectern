// html 문서 보기 (D27): <iframe sandbox="allow-same-origin"> 에 /doc/<경로> 를 띄운다.
//
// - 문서 자신의 스크립트·인라인 이벤트·폼은 돌지 않는다 (iframe sandbox 에 allow-scripts 가 없고, 서버 CSP 도 막는다).
//   같은 출처라서 앱(부모)이 iframe 안을 읽고 이벤트를 붙여 목차·찾기·링크·우클릭 메뉴·바뀐 부분 강조를 다룬다.
// - iframe 높이를 문서 높이에 맞춰 #lec-content 가 스크롤한다 (md 와 같게 스크롤 위치·마지막 위치가 동작).
// - 문서에 스타일(CSS)이 있으면 그대로, 없으면 지금 고른 Lectern 스타일을 입힌다 (사용자가 고름).
// - 자동 새로고침 때는 새 iframe 을 보이지 않게 겹쳐 불러온 뒤 바꿔 끼운다 (깜박임과 스크롤 튐 방지).

import { S, emit } from './store.js';
import { bindLink, showMissing, scrollToAnchor } from './doc.js';
import { buildToc, clearToc } from './toc.js';
import { setStatus } from './status.js';
import { setDocSource, frameContextMenu } from './docmenu.js';
import { hideMenu } from './ui.js';
import { snapshot, markChanges, clearChanges } from './diffmark.js';
import { $, encodePath, formatDateTime } from './util.js';

const LOAD_TIMEOUT_MS = 20000;
const MAX_HEIGHT = 200000;

/** 지금 화면의 html 문서 iframe (없으면 null) */
export const currentFrame = () => $('#lec-view > iframe.lec-html:not(.lec-loading)');

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

/** iframe 높이를 문서 높이에 맞춘다. 100vh 를 쓰는 문서가 끝없이 커지지 않게, 같은 만큼 계속 커지면 멈춘다 */
function fitHeight(frame) {
  const doc = frame.contentDocument;
  let last = 0;
  let lastGrow = 0;
  let repeats = 0;
  const fit = () => {
    const h = Math.ceil(Math.max(doc.documentElement.scrollHeight, doc.body?.scrollHeight || 0));
    const grow = h - last;
    if (Math.abs(grow) < 2) return;
    repeats = grow > 0 && grow === lastGrow ? repeats + 1 : 0;
    if (repeats > 3) return;
    lastGrow = grow;
    last = h;
    frame.style.height = `${Math.min(h, MAX_HEIGHT)}px`;
  };
  fit();
  new ResizeObserver(fit).observe(doc.documentElement);
}

function prepare(frame, path) {
  const doc = frame.contentDocument;
  const own = hasOwnStyle(doc);
  doc.head.append(link(doc, '/static/css/frame.css'));   // 찾기 표시·바뀐 곳·우클릭 테두리
  if (own) {
    frame.classList.add('own-style');   // 바탕색을 정하지 않은 문서가 다크 스타일 위에서 안 보이지 않게 흰 바탕
  } else {
    doc.head.append(link(doc, '/static/themes/base.css'), link(doc, $('#lec-theme-css').href));
    doc.body.classList.add('md-body');
  }
  let n = 0;
  for (const h of doc.querySelectorAll('h1, h2, h3, h4')) if (!h.id) h.id = `lec-h${++n}`;   // 목차용
  const baseUrl = new URL(`/doc/${encodePath(path)}`, location.origin);
  for (const a of doc.querySelectorAll('a[href], area[href]')) bindLink(a, baseUrl, path, doc);
  doc.addEventListener('contextmenu', (e) => frameContextMenu(e, frame));
  // iframe 안의 키·마우스는 앱 문서로 올라오지 않는다. 단축키(Ctrl+F, Esc, Alt+← …)와 마우스 뒤로 버튼, 메뉴 닫기를 위해 넘겨 준다
  doc.addEventListener('keydown', (e) => {
    if (!document.dispatchEvent(new KeyboardEvent('keydown', e))) e.preventDefault();
  });
  doc.addEventListener('mousedown', () => hideMenu());
  doc.addEventListener('mouseup', (e) => {
    if (e.button === 3 || e.button === 4) window.dispatchEvent(new MouseEvent('mouseup', { button: e.button }));
  });
  fitHeight(frame);
}

/**
 * html 문서를 그린다 (nav.js 가 확장자로 고른다). 더 나중에 시작한 렌더링이 있으면 결과를 버린다(false).
 */
export async function showHtml(path, { hash = '', scrollTop } = {}) {
  const id = ++S.renderId;
  const view = $('#lec-view');
  const content = $('#lec-content');
  const src = `/doc/${encodePath(path)}`;
  const head = await fetch(src, { method: 'HEAD', cache: 'no-store' }).catch((e) => ({ ok: false, status: 0, statusText: e.message }));
  if (id !== S.renderId) return false;
  if (!head.ok) {
    showMissing(view, path, { status: head.status, message: head.statusText });
    setDocSource(null);
    clearChanges();
    clearToc();
    setStatus({ path, info: '' });
    emit('rendered');
    return true;
  }

  const old = currentFrame();
  const sameDoc = old && S.view?.type === 'doc' && S.view.path === path;
  const before = sameDoc && old.contentDocument?.body ? snapshot(old.contentDocument.body) : null;
  const frame = document.createElement('iframe');
  frame.className = 'lec-html';
  frame.setAttribute('sandbox', 'allow-same-origin');   // allow-scripts 를 주지 않는다 (D27)
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
  if (id !== S.renderId) {
    if (sameDoc) frame.remove();
    return false;
  }
  if (!ok || !frame.contentDocument?.body) {
    showMissing(view, path, { status: 0, message: '문서를 불러오는 데 시간이 너무 오래 걸립니다' });
    emit('rendered');
    return true;
  }
  prepare(frame, path);
  if (sameDoc) {
    old.remove();
    frame.classList.remove('lec-loading');
  }
  const doc = frame.contentDocument;
  buildToc(doc.body);
  if (scrollTop != null) content.scrollTop = scrollTop;
  else if (!hash || !scrollToAnchor(doc, hash)) content.scrollTop = 0;
  setDocSource(path, '');
  markChanges(doc.body, path, before);

  if (S.changed.delete(path)) emit('changed');
  const file = S.fileMap.get(path);
  setStatus({ path, info: file ? `HTML · 수정 ${formatDateTime(file.mtime)}` : 'HTML' });
  emit('rendered');
  return true;
}
