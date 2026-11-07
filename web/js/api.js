// 서버 API 호출과 네이티브(pywebview) 기능 연결

import { S } from './store.js';
import { solo } from './solo.js';
import { toast } from './util.js';
import { t } from './i18n.js';

function headers(extra = {}) {
  const h = { ...extra };
  const token = window.pywebview?.token;
  if (token) h['X-Token'] = token;
  return h;
}

async function check(res) {
  if (res.ok) return res;
  let message = `HTTP ${res.status}`;
  try {
    const body = await res.json();
    if (body?.error) message = body.error;
  } catch { /* 본문이 JSON이 아님 */ }
  const err = /** @type {any} */ (new Error(message));
  err.status = res.status;
  throw err;
}

/** 받기만 하는 요청 — 연결이 잠깐 실패한 것이면 한 번 더 (D81. 다시 보내도 되는 요청에만 쓴다) */
async function fetchRetry(path, options) {
  try {
    return await fetch(path, options);
  } catch {
    await new Promise((r) => setTimeout(r, 200));
    return fetch(path, options);
  }
}

/** extra: 더 붙일 헤더 (터미널 API 의 X-Term — terminal.js) */
export async function getJSON(path, extra = {}) {
  const res = await fetchRetry(path, { headers: headers(extra), cache: 'no-store' });
  return (await check(res)).json();
}

/**
 * signal: 기다리는 요청을 그만둘 때 (터미널 출력의 긴 폴링 — terminal.js)
 * @param {string} path
 * @param {any} [body]
 * @param {Record<string, any>} [extra]
 * @param {{ signal?: AbortSignal }} [options]
 */
export async function postJSON(path, body, extra = {}, { signal } = {}) {
  const res = await fetch(path, {
    method: 'POST',
    headers: headers({ ...extra, 'Content-Type': 'application/json' }),
    body: JSON.stringify(body ?? {}),
    signal,
  });
  return (await check(res)).json();
}

export async function getText(path) {
  const res = await fetchRetry(path, { cache: 'no-store' });
  return (await check(res)).text();
}

/** 설정 일부를 저장한다. 실패해도 화면 동작에는 영향이 없다. */
export async function saveConfig(patch) {
  Object.assign(S.config, patch);
  if (solo && !(solo.deck && ('slide_theme' in patch || 'pptx_style' in patch))) return;   // 독립창의 화면 설정은 그 창에서만 (D95 — 설정은 메인 창의 것이다). 슬라이드 창의 스타일만 저장한다 (D96)
  try {
    await postJSON('/api/config', patch);
  } catch (e) {
    console.warn('설정 저장 실패', e);   // i18n-ok (개발자 도구에만)
  }
}

const OPEN_RESULT = {
  editor: t('편집기로 열었습니다'),
  default: t('기본 앱으로 열었습니다'),
  reveal: t('탐색기에서 파일을 표시했습니다'),
  folder: t('폴더를 열었습니다'),
};

/**
 * 선택된 탭의 프로젝트 안 파일을 OS에 넘겨 연다 (md가 아닌 링크, 트리의 '편집기로 열기', 문서 외 파일).
 * how: 'editor' 면 기본 앱으로 여는 형식(csv 등)도 편집기로. 어떻게 열지는 서버가 정한다 (실행하지 않는다 — osutil.open_path)
 */
export async function openExternal(path, line, how) {
  try {
    const r = await postJSON('/api/open-external', { p: S.tab?.id, path, line, how });
    toast(OPEN_RESULT[r.action] || t('열었습니다'));
  } catch (e) {
    toast(e.status === 404 ? t('파일을 찾을 수 없습니다: {path}', { path }) : t('열지 못했습니다: {error}', { error: e.message }), 'error');
  }
}

/** 탐색기에서 보기. path 가 '' 면 프로젝트 폴더 (탭 우클릭) */
export async function revealInExplorer(path, tab = S.tab) {
  try {
    await postJSON('/api/reveal', { p: tab?.id, path });
  } catch (e) {
    toast(t('탐색기에서 열지 못했습니다: {error}', { error: e.message }), 'error');
  }
}

export const native = {
  has: (name) => typeof window.pywebview?.api?.[name] === 'function',

  async chooseFolder() {
    if (native.has('choose_folder')) return window.pywebview.api.choose_folder();
    const p = window.prompt(t('열 폴더의 전체 경로를 입력하세요 (브라우저 개발 모드)'));
    return p ? p.trim() : null;
  },

  setTitle(title) {
    document.title = title;
    if (native.has('set_title')) window.pywebview.api.set_title(title)?.catch?.(() => {});
  },

  /** 독립창을 띄운다 (D95 — query 는 solo.soloQuery). 띄웠으면 true */
  async openWindow(query) {
    if (native.has('open_window')) return window.pywebview.api.open_window(query);
    return !!window.open(`/${query}`, '_blank', 'popup,width=1000,height=760');   // 브라우저 개발 모드
  },

  closeWindow() {
    if (native.has('close_window')) window.pywebview.api.close_window();
    else window.close();
  },

  /** 이 독립창이 닫힌다 — 다른 창의 보낼 곳에서 빠지게. 닫히는 중에도 닿도록 keepalive */
  tellGone(id) {
    fetch('/api/window-gone', { method: 'POST', keepalive: true, headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ w: id }) }).catch(() => {});
  },
};
