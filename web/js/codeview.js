// 코드 화면 (D43): 사이드바 '코드' 목록이나 문서 속 코드 경로·링크를 누르면 코드 파일을 본문 자리에 읽기 전용으로 보인다.
// 줄 번호, 언어별 색(highlight.js — 이미 들여온 것), 긴 줄은 접어서(pre-wrap). 오른쪽 목차는 outline.js 가 찾은 클래스·함수·구분 주석.
// - 화면(#lec-view)의 최상위 자식이 머리줄과 줄들이라, 바뀐 곳 강조(diffmark)·문서 안 찾기(find.js)가 문서처럼 된다.
// - 코드 파일의 내용 수정은 서버의 변경 기록에 오지 않는다 (소스를 고칠 때마다 문서 트리를 다시 읽지 않게 — D36).
//   그래서 보고 있는 동안 2초마다 그 파일의 수정 시각(HEAD /doc/…, Last-Modified)을 보고, 바뀌었으면 다시 그린다.
// - 실행하지 않는다: 글자로만 보인다 (highlight.js 가 이스케이프한다). 너무 큰 파일·바이너리는 편집기로 열라고 알린다.
// - 자료 파일도 여기서 본다 (D60): txt·log 는 글자 그대로, csv·tsv 는 표(csvview.js). 이것들은 UTF-8 이 아니면 UTF-16(BOM)·CP949 로 읽는다
//   (엑셀이 저장한 CSV·유니코드 텍스트 — 보기만, 편집 모드는 UTF-8 만).

import { S, emit, on } from './store.js';
import { openExternal } from './api.js';
import { setToc } from './toc.js';
import { setStatus } from './status.js';
import { snapshot, markChanges, clearChanges } from './diffmark.js';
import { showMissing } from './doc.js';
import { languageOf, outlineOf } from './outline.js';
import { isTableFile, renderCsv, initCsv } from './csvview.js';
import { DATA_VIEW_EXT } from './icons.js';
import { $, esc, docUrl, basename, dirname, formatSize, formatDateTime, copyText, toast } from './util.js';
import { t } from './i18n.js';

const MAX_BYTES = 4 * 1024 * 1024;        // 이보다 크면 보이지 않고 편집기로
const MAX_HIGHLIGHT = 1024 * 1024;        // 이보다 크면 색 없이 (빨리 보이게)
const CHECK_MS = 2000;                    // 보고 있는 파일의 수정 시각을 보는 주기

/** highlight.js 결과를 줄로 나눈다. 여러 줄에 걸친 <span>(주석·문자열)은 줄마다 닫고 다음 줄에서 다시 연다 */
function splitLines(html) {
  const out = [];
  const open = [];
  for (const raw of html.split('\n')) {
    const head = open.join('');
    for (const m of raw.matchAll(/<span[^>]*>|<\/span>/g)) {
      if (m[0] === '</span>') open.pop();
      else open.push(m[0]);
    }
    out.push(head + raw + '</span>'.repeat(open.length));
  }
  return out;
}

function highlighted(text, lang) {
  const hljs = window.hljs;
  if (text.length <= MAX_HIGHLIGHT && hljs?.getLanguage(lang.hljs)) {
    try {
      return hljs.highlight(text, { language: lang.hljs, ignoreIllegals: true }).value;
    } catch { /* 글자로 */ }
  }
  return esc(text);
}

const isDataFile = (path) => DATA_VIEW_EXT.has(path.split('.').pop().toLowerCase());

/** 받은 바이트를 글로. 자료 파일은 UTF-16(BOM) → UTF-8 → CP949 순서로 — {text, encoding('' 이면 UTF-8)} */
function decode(buf, path) {
  const bytes = new Uint8Array(buf);
  if (!isDataFile(path)) return { text: new TextDecoder('utf-8').decode(bytes), encoding: '' };
  if (bytes[0] === 0xff && bytes[1] === 0xfe) return { text: new TextDecoder('utf-16le').decode(bytes), encoding: 'UTF-16' };
  if (bytes[0] === 0xfe && bytes[1] === 0xff) return { text: new TextDecoder('utf-16be').decode(bytes), encoding: 'UTF-16' };
  try {
    return { text: new TextDecoder('utf-8', { fatal: true }).decode(bytes), encoding: '' };
  } catch {
    return { text: new TextDecoder('euc-kr').decode(bytes), encoding: 'CP949' };   // WHATWG 의 euc-kr 은 CP949(확장 완성형)이다
  }
}

/** 보이지 않는 경우(너무 큼·바이너리)의 안내 */
function notice(view, path, message) {
  view.className = 'md-body code-view';
  delete view.dataset.docPath;
  view.dataset.codePath = path;
  view.innerHTML = `<div class="doc-missing"><h1>${esc(path)}</h1><p>${esc(message)}</p>
    <p><button type="button" class="primary cv-editor">${t('편집기로 열기')}</button></p></div>`;
}

/**
 * 코드 파일을 칸(pane)에 그린다. 프로젝트는 칸의 탭(pane.tab). line: 그 줄로 가서 잠깐 표시. scrollTop: 이 위치로 (함수면 바꿔 끼우기 직전에 읽는다).
 * 그 칸에서 더 나중에 시작한 렌더링이 있으면 결과를 버린다(false).
 */
export async function showCode(pane, path, { line, scrollTop } = {}) {
  const id = ++pane.renderId;
  const { view, scroller, tab } = pane;
  let text;
  let stamp;
  let size = 0;
  let modified = null;
  let encoding = '';
  try {
    const res = await fetch(docUrl(tab, path), { cache: 'no-store' });
    if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status}`), { status: res.status });
    size = Number(res.headers.get('Content-Length')) || 0;
    modified = res.headers.get('Last-Modified');
    stamp = `${modified}|${size}`;
    if (size <= MAX_BYTES) ({ text, encoding } = decode(await res.arrayBuffer(), path));
  } catch (err) {
    if (id !== pane.renderId) return false;
    showMissing(view, path, err);
    finish(pane, path, null, { path, info: '' });
    return true;
  }
  if (id !== pane.renderId) return false;
  pane.codeStamp = stamp;
  if (text == null || text.includes('\u0000')) {
    notice(view, path, text == null ? t('파일이 너무 큽니다 ({size}). 편집기로 여세요.', { size: formatSize(size) }) : t('글자로 된 파일이 아닙니다. 편집기로 여세요.'));
    finish(pane, path, null, { path, info: formatSize(size) });
    return true;
  }

  text = text.replace(/\r\n?/g, '\n');
  if (text.endsWith('\n')) text = text.slice(0, -1);
  if (isTableFile(path)) return showTable(pane, path, { text, size, modified, encoding, top: typeof scrollTop === 'function' ? scrollTop() : scrollTop, line });
  const lang = languageOf(path);
  const lines = splitLines(highlighted(text, lang));
  const same = pane.current?.type === 'code' && pane.current.path === path && view.classList.contains('code-view') && !view.querySelector('.doc-missing');
  const before = same ? snapshot(view) : null;
  const top = typeof scrollTop === 'function' ? scrollTop() : scrollTop;   // 함수면 바꿔 끼우기 직전의 위치 (refreshView)

  view.className = 'md-body code-view';
  delete view.dataset.docPath;   // 장 하이라이트·접기는 md 문서에서만
  view.style.setProperty('--cv-digits', String(String(lines.length).length));
  view.innerHTML = `<header class="cv-head"><div class="cv-title">${esc(basename(path))}</div>`
    + `<div class="cv-sub">${dirname(path) ? `${esc(dirname(path))} · ` : ''}${esc(lang.name)}</div>`
    + `<div class="cv-tools"><button type="button" class="text-btn cv-edit" title="${t('여기서 고치기 — 편집 모드 (Ctrl+E)')}">`
    + `<svg aria-hidden="true"><use href="#i-edit"/></svg>${t('편집')}</button>`
    + openButton(path)
    + `<button type="button" class="text-btn cv-copy">${t('전체 복사')}</button></div></header>`
    + lines.map((l, i) => `<div class="cv-line" data-line="${i + 1}"><span class="cv-text">${l}</span></div>`).join('');
  view.dataset.codePath = path;
  view.codeText = text;
  finish(pane, path, outlineOf(path, text), {
    path, info: `${lang.name} · ${t('{n}줄', { n: lines.length })} · ${formatSize(size)}${encoding ? ` · ${encoding}` : ''}${modifiedText(modified)}`,
  });
  if (top != null) scroller.scrollTop = top;
  else if (line) goToLine(view, line, { flash: true });
  else scroller.scrollTop = 0;
  markChanges(view, before, pane);
  return true;
}

/** 머리줄의 '편집기로 열기' — 자료 파일(csv·txt 등)은 기본 앱(엑셀·메모장)으로 */
function openButton(path) {
  return isDataFile(path)
    ? `<button type="button" class="text-btn cv-editor" title="${t('기본 앱으로 열기 (자료 목록에서 두 번 누르기)')}">${t('기본 앱으로 열기')}</button>`
    : `<button type="button" class="text-btn cv-editor" title="${t('편집기로 열기 (코드 목록에서 두 번 누르기)')}">${t('편집기로 열기')}</button>`;
}

function modifiedText(modified) {
  const when = modified ? new Date(modified) : null;
  return when && !Number.isNaN(when.getTime()) ? ` · ${t('수정 {when}', { when: formatDateTime(when.getTime() / 1000) })}` : '';
}

const DELIMS = { ',': t('쉼표'), ';': t('세미콜론'), '\t': t('탭') };

/** csv·tsv: 머리줄 + 표 (csvview.js). 바뀐 곳 강조는 하지 않는다 (표 전체가 한 블록이다) */
function showTable(pane, path, { text, size, modified, encoding, top, line }) {
  const { view, scroller, tab } = pane;
  view.className = 'md-body code-view';
  delete view.dataset.docPath;
  view.innerHTML = `<header class="cv-head"><div class="cv-title">${esc(basename(path))}</div>`
    + `<div class="cv-sub">${dirname(path) ? `${esc(dirname(path))} · ` : ''}${esc(languageOf(path).name)}</div>`
    + `<div class="cv-tools"><button type="button" class="text-btn cv-edit" title="${t('여기서 고치기 — 편집 모드 (Ctrl+E)')}">`
    + `<svg aria-hidden="true"><use href="#i-edit"/></svg>${t('편집')}</button>${openButton(path)}`
    + `<button type="button" class="text-btn cv-copy">${t('전체 복사')}</button></div></header>`;
  view.dataset.codePath = path;
  view.codeText = text;
  const info = renderCsv(view, path, text, `${tab.id}:${path}`);
  finish(pane, path, null, {
    path, info: `${languageOf(path).name} · ${t('{n}행', { n: info.rows.toLocaleString() })} · ${t('{n}열', { n: info.cols })}`
      + ` · ${DELIMS[info.delim] || info.delim} · ${formatSize(size)}${encoding ? ` · ${encoding}` : ''}${modifiedText(modified)}`,
  });
  if (top != null) scroller.scrollTop = top;
  else if (line) goToLine(view, line, { flash: true });
  else scroller.scrollTop = 0;
  return true;
}

function finish(pane, path, outline, status) {
  setToc(pane, outline ? pane.view : null, outline);
  if (!outline) clearChanges(pane);
  setStatus(status, pane);
  emit('rendered', pane);
}

/** 코드 화면에서 line 번째 줄로 (가운데), flash 면 잠깐 표시 */
export function goToLine(view, line, { flash = false } = {}) {
  const el = view.querySelector(`.cv-line[data-line="${Number(line)}"]`);
  if (!el) return null;
  el.scrollIntoView({ block: 'center' });
  if (flash) {
    el.classList.remove('lec-target');
    void el.offsetWidth;
    el.classList.add('lec-target');
    setTimeout(() => el.classList.remove('lec-target'), 1800);
  }
  return el;
}

/** 보고 있는 코드 파일의 수정 시각이 바뀌었으면 다시 그린다 */
async function check() {
  const pane = S.pane;
  const v = pane?.current;
  if (document.hidden || v?.type !== 'code' || pane.pending) return;
  try {
    const res = await fetch(docUrl(pane.tab, v.path), { method: 'HEAD', cache: 'no-store' });
    const stamp = res.ok ? `${res.headers.get('Last-Modified')}|${Number(res.headers.get('Content-Length')) || 0}` : 'gone';
    if (pane === S.pane && pane.current === v && stamp !== pane.codeStamp) emit('refresh-view', pane);
  } catch { /* 서버가 잠시 답하지 않음 */ }
}

export function initCodeView() {
  initCsv($('#lec-panes'));   // 표의 거르기·정렬·통계 (D60)
  $('#lec-panes').addEventListener('click', (e) => {
    const view = e.target.closest('.code-view');
    if (!view) return;
    const path = view.dataset.codePath || S.view?.path;
    if (e.target.closest('.cv-editor')) openExternal(path);
    else if (e.target.closest('.cv-copy')) {
      copyText(view.codeText || '').then((ok) => toast(ok ? t('복사했습니다: {what}', { what: t('{name} 전체', { name: basename(path) }) }) : t('복사하지 못했습니다')));
    }
  });
  setInterval(check, CHECK_MS);
  on('pane', () => check());   // 다른 탭을 고르면 그 탭의 코드가 그사이 바뀌었는지
}
