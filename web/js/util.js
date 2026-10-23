// 공용 도우미 함수

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);

/** 'docs/한글 문서.md' → URL 경로 조각마다 인코딩 */
export const encodePath = (p) => p.split('/').map(encodeURIComponent).join('/');

/** 탭(프로젝트) 안 파일의 주소: /doc/<탭 id>/<경로>. 상대경로 링크·그림은 이 주소를 기준으로 푼다 (doc.js 의 resolveRef) */
export const docUrl = (tab, p) => `/doc/${tab.id}/${encodePath(p)}`;

export const basename = (p) => p.slice(p.lastIndexOf('/') + 1);
export const dirname = (p) => (p.includes('/') ? p.slice(0, p.lastIndexOf('/')) : '');
export const isMd = (p) => /\.(md|markdown)$/i.test(p);
export const isHtml = (p) => /\.html?$/i.test(p);

/** 지금 화면의 문서 내용 뿌리: md 는 #lec-view, html 문서는 iframe 의 body (htmldoc.js) */
export function docRoot() {
  const frame = document.querySelector('#lec-view > iframe.lec-html:not(.lec-loading)');
  return frame?.contentDocument?.body || document.querySelector('#lec-view');
}

/** 요소·Range 의 화면 좌표. html 문서(iframe) 안의 것은 iframe 위치만큼 더한다 */
export function screenRect(node) {
  const r = node.getBoundingClientRect();
  const doc = node.ownerDocument || node.startContainer?.ownerDocument;
  const frame = doc?.defaultView?.frameElement;
  if (!frame) return r;
  const f = frame.getBoundingClientRect();
  return { top: r.top + f.top, bottom: r.bottom + f.top, left: r.left + f.left, right: r.right + f.left, width: r.width, height: r.height };
}

const pad = (n) => String(n).padStart(2, '0');
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

/** 유닉스 초 → 'YYYY-MM-DD HH:MM' */
export function formatDateTime(sec) {
  const d = new Date(sec * 1000);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export const formatClock = (d) => `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

/** 유닉스 초 → '방금', '5분 전', '어제', '10월 3일' */
export function timeAgo(sec) {
  if (!sec) return '';
  const diff = Date.now() / 1000 - sec;
  if (diff < 45) return '방금';
  if (diff < 3600) return `${Math.max(1, Math.round(diff / 60))}분 전`;
  const d = new Date(sec * 1000);
  const now = new Date();
  const days = Math.round((startOfDay(now) - startOfDay(d)) / 86400000);
  if (days === 0) return `${Math.round(diff / 3600)}시간 전`;
  if (days === 1) return '어제';
  if (days < 7) return `${days}일 전`;
  if (d.getFullYear() === now.getFullYear()) return `${d.getMonth() + 1}월 ${d.getDate()}일`;
  return `${d.getFullYear()}.${d.getMonth() + 1}.${d.getDate()}`;
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px;top:0';
    document.body.append(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch { ok = false; }
    ta.remove();
    return ok;
  }
}

let toastTimer = 0;
export function toast(message, kind = '', ms = kind === 'error' ? 4000 : 2200) {
  const el = $('#lec-toast');
  el.textContent = message;
  el.className = kind;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, ms);
}

export function debounce(fn, ms) {
  let t = 0;
  const call = (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
  call.cancel = () => clearTimeout(t);
  return call;
}

/**
 * 목록을 다시 그려도 키보드 초점을 지킨다 (파일이 바뀌면 트리·검색 결과를 새로 그린다).
 * 초점이 area 안 목록의 행에 있었으면, 다시 그린 뒤 같은 목록에서 같은 data-* 를 가진 행으로 돌려준다.
 */
export function keepFocus(area, draw) {
  const el = document.activeElement;
  const list = el && el !== area && area.contains(el) ? el.parentElement?.closest('[id]') : null;
  const sel = list ? Object.entries(el.dataset)
    .map(([k, v]) => `[data-${k.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}="${CSS.escape(v)}"]`).join('') : '';
  draw();
  if (sel && document.activeElement !== el) document.getElementById(list.id)?.querySelector(`${el.localName}${sel}`)?.focus({ preventScroll: true });
}

/** 문서 안의 앵커(#id) 요소. root 범위 안에서만 찾는다 (앱 UI의 id와 겹치지 않도록). */
export function findAnchor(root, hash) {
  if (!hash || hash === '#') return null;
  let id = hash.replace(/^#/, '');
  try { id = decodeURIComponent(id); } catch { /* 그대로 사용 */ }
  return root.querySelector(`#${CSS.escape(id)}`) || root.querySelector(`[name="${CSS.escape(id)}"]`);
}
