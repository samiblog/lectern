// 서버 API 호출과 네이티브(pywebview) 기능 연결

import { S, emit } from './store.js';
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
  let code = '';
  try {
    const body = await res.json();
    if (body?.error) message = body.error;
    if (body?.code) code = body.code;
  } catch { /* 본문이 JSON이 아님 */ }
  const err = /** @type {any} */ (new Error(message));
  err.status = res.status;
  if (code) err.code = code;   // 서버가 붙인 까닭의 이름 (예: /api/work/folders 의 no-card)
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

const saving = new Map();   // 저장하러 보낸 설정 열쇠와 그 수 (D159 — 다른 창의 변경을 받을 때 이 창이 막 바꾼 값을 덮지 않게)

/** 설정 일부를 저장한다. 실패해도 화면 동작에는 영향이 없다. */
export async function saveConfig(patch) {
  Object.assign(S.config, patch);
  if (solo && !(solo.deck && ['slide_theme', 'pptx_style', 'recent_templates'].some((k) => k in patch))) return;   // 독립창의 화면 설정은 그 창에서만 (D95 — 설정은 메인 창의 것이다). 슬라이드 창의 스타일만 저장한다 (D96)
  const keys = Object.keys(patch);
  for (const k of keys) saving.set(k, (saving.get(k) || 0) + 1);
  try {
    await postJSON('/api/config', patch);
  } catch (e) {
    console.warn('설정 저장 실패', e);   // i18n-ok (개발자 도구에만)
  } finally {
    for (const k of keys) saving.set(k, saving.get(k) - 1);
  }
}

// ---- 설정 따르기 (D159) — 설정은 Lectern 전체에 하나다. 다른 창(독립창·슬라이드 창·메인 창)이나 설정 파일에서 바뀐 값을 이 창에도 입힌다 ----
// 변경 확인(watch.js)의 대답에 설정의 판 번호가 오고, 이 창이 아는 번호와 다르면 설정을 다시 받는다. 이 창이 마지막으로 받은 서버의 값과
// 달라진 열쇠만 고른다 — 독립창에서만 바꾼 화면 설정(D95)은 다른 창이 그 열쇠를 바꿀 때까지 그대로 둔다.
// 사이드바·목차·터미널의 폭과 보임, 검색·최근 변경의 단추, 사이드바의 펼친 묶음처럼 창마다의 화면 상태는 따르지 않는다.
const FOLLOW = ['language', 'theme', 'slide_theme', 'theme_groups', 'diagram_style', 'diagram_colors', 'pptx_style', 'font_scale', 'doc_width', 'line_numbers', 'show_titles', 'doc_kinds', 'side_sort', 'clip_sort',
  'toc_hidden_parts', 'math', 'md_breaks', 'external_images', 'vi_keys', 'editor_keys', 'restore_last', 'expand_first_level', 'terminal_position',
  'terminal_follow_style', 'terminal_font_size', 'csv_stats', 'table_align', 'work_alerts', 'print_font', 'print_margin', 'print_margin_mm', 'print_header', 'print_page_numbers',
  'ai_tool', 'ai_scope_guide', 'ai_scope_skills', 'ai_style_where', 'ai_style', 'recent_md_styles', 'recent_templates', 'recent_puts', 'recent_chars'];
let served = null;   // 이 창이 마지막으로 받은 서버의 설정

/** 처음 설정을 받는다 (main.js) — 따르기의 기준도 이것 */
export async function loadConfig() {
  const config = await getJSON('/api/config');
  served = structuredClone(config);
  return config;
}

/** 변경 확인이 알려 준 판 번호 rev 가 이 창의 것과 다르면 설정을 다시 받아, 달라진 열쇠를 입히고 'config-follow' (열쇠의 Set) 를 알린다 */
export async function followConfig(rev) {
  if (rev === S.config._rev) return;
  const fresh = await getJSON('/api/config');
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const keys = FOLLOW.filter((k) => !same(fresh[k], served?.[k]) && !same(fresh[k], S.config[k]) && !(saving.get(k) > 0));
  served = fresh;
  S.config._rev = fresh._rev;
  if (!keys.length) return;
  for (const k of keys) S.config[k] = fresh[k];
  emit('config-follow', new Set(keys));
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
/** '폴더' 묶음의 숨긴 파일인지 (D203 — 보기만, 서버에 hidden 을 함께 보낸다) */
export const hiddenFile = (tab, path) => !!tab?.others?.hiddenSet?.has(path);

export async function openExternal(path, line, how) {
  try {
    const r = await postJSON('/api/open-external', { p: S.tab?.id, path, line, how, ...(hiddenFile(S.tab, path) ? { hidden: true } : {}) });
    toast(OPEN_RESULT[r.action] || t('열었습니다'));
  } catch (e) {
    toast(e.status === 404 ? t('파일을 찾을 수 없습니다: {path}', { path }) : t('열지 못했습니다: {error}', { error: e.message }), 'error');
  }
}

/** 탐색기에서 보기. path 가 '' 면 프로젝트 폴더 (탭 우클릭) */
export async function revealInExplorer(path, tab = S.tab) {
  try {
    await postJSON('/api/reveal', { p: tab?.id, path, ...(hiddenFile(tab, path) ? { hidden: true } : {}) });
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
