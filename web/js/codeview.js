// 코드 화면 (D43): 사이드바 '코드' 목록이나 문서 속 코드 경로·링크를 누르면 코드 파일을 본문 자리에 읽기 전용으로 보인다.
// 줄 번호, 언어별 색(highlight.js — 이미 들여온 것), 긴 줄은 접어서(pre-wrap). 오른쪽 목차는 outline.js 가 찾은 클래스·함수·구분 주석.
// - 화면(#lec-view)의 최상위 자식이 머리줄과 줄들이라, 바뀐 곳 강조(diffmark)·문서 안 찾기(find.js)가 문서처럼 된다.
// - 코드 파일의 내용 수정은 서버의 변경 기록에 오지 않는다 (소스를 고칠 때마다 문서 트리를 다시 읽지 않게 — D36).
//   그래서 보고 있는 동안 2초마다 그 파일의 수정 시각(HEAD /doc/…, Last-Modified)을 보고, 바뀌었으면 다시 그린다.
// - 실행하지 않는다: 글자로만 보인다 (highlight.js 가 이스케이프한다). 너무 큰 파일·바이너리는 편집기로 열라고 알린다.
// - 자료 파일도 여기서 본다 (D60): txt·log 는 글자 그대로, csv·tsv 는 표(csvview.js). 이것들은 UTF-8 이 아니면 UTF-16(BOM)·CP949 로 읽는다
//   (엑셀이 저장한 CSV·유니코드 텍스트 — 보기만, 편집 모드는 UTF-8 만). Windows 인코딩으로 쓰는 코드(EViews 의 prg — D85)도 같다.
// - 엑셀(xlsx·xlsm — D77)은 서버가 읽은 값(GET /api/sheet)을 csv 와 같은 표로, 머리줄 아래 시트 탭. 행은 엑셀의 행 번호이고
//   view.codeText 는 행 번호 자리마다 그 행의 칸을 탭으로 이은 글 (우클릭 '이 줄 복사'·하이라이트의 Ctrl+C 가 엑셀에 붙는 글), view.dataset.sheet 는 시트 이름.

import { S, emit, on } from './store.js';
import { openExternal, getJSON } from './api.js';
import { setToc } from './toc.js';
import { setStatus } from './status.js';
import { snapshot, markChanges, clearChanges } from './diffmark.js';
import { showMissing } from './doc.js';
import { languageOf, outlineOf } from './outline.js';
import { isTableFile, renderCsv, renderRows, colName, initCsv } from './csvview.js';
import { DATA_VIEW_EXT, WINDOWS_TEXT_EXT, isSheet, isCode } from './icons.js';
import { paneShown } from './panes.js';
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

const extOf = (path) => path.split('.').pop().toLowerCase();
const isDataFile = (path) => DATA_VIEW_EXT.has(extOf(path));

/** 받은 바이트를 글로. 자료 파일과 Windows 인코딩으로 쓰는 코드는 UTF-16(BOM) → UTF-8 → CP949 순서로 — {text, encoding('' 이면 UTF-8)} */
function decode(buf, path) {
  const bytes = new Uint8Array(buf);
  if (!isDataFile(path) && !WINDOWS_TEXT_EXT.has(extOf(path))) return { text: new TextDecoder('utf-8').decode(bytes), encoding: '' };
  if (bytes[0] === 0xff && bytes[1] === 0xfe) return { text: new TextDecoder('utf-16le').decode(bytes), encoding: 'UTF-16' };
  if (bytes[0] === 0xfe && bytes[1] === 0xff) return { text: new TextDecoder('utf-16be').decode(bytes), encoding: 'UTF-16' };
  try {
    return { text: new TextDecoder('utf-8', { fatal: true }).decode(bytes), encoding: '' };
  } catch {
    return { text: new TextDecoder('euc-kr').decode(bytes), encoding: 'CP949' };   // WHATWG 의 euc-kr 은 CP949(확장 완성형)이다
  }
}

/** 보이지 않는 경우(너무 큼·바이너리·읽지 못한 엑셀)의 안내 */
function notice(view, path, message) {
  view.className = 'md-body code-view';
  delete view.dataset.docPath;
  delete view.dataset.sheet;
  delete view.dataset.encoding;
  view.dataset.codePath = path;
  const label = isSheet(path) ? t('기본 앱으로 열기') : t('편집기로 열기');
  view.innerHTML = `<div class="doc-missing"><h1>${esc(path)}</h1><p>${esc(message)}</p>
    <p><button type="button" class="primary cv-editor">${label}</button></p></div>`;
}

/**
 * 코드 파일을 칸(pane)에 그린다. 프로젝트는 칸의 탭(pane.tab). line: 그 줄로 가서 잠깐 표시. scrollTop: 이 위치로 (함수면 바꿔 끼우기 직전에 읽는다).
 * 그 칸에서 더 나중에 시작한 렌더링이 있으면 결과를 버린다(false).
 * @param {Pane} pane
 * @param {string} path
 * @param {ShowOptions} [options]
 */
export async function showCode(pane, path, { line, scrollTop } = {}) {
  if (isSheet(path)) return showSheet(pane, path, { line, scrollTop });
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
    + `<div class="cv-tools">${editButton(path)}${openButton(path)}`
    + `<button type="button" class="text-btn cv-copy">${t('전체 복사')}</button></div></header>`
    + lines.map((l, i) => `<div class="cv-line" data-line="${i + 1}"><span class="cv-text">${l}</span></div>`).join('');
  view.dataset.codePath = path;
  if (encoding) view.dataset.encoding = encoding;   // UTF-8 이 아니면 보기만 — 한 줄 편집이 본다 (lineedit.js, D85)
  else delete view.dataset.encoding;
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

// ---- 엑셀 보기 (D77) ----------------------------------------------------------------

const sheetChoice = new Map();   // 탭 id + 경로 → 고른 시트 차례 (자동 새로고침으로 다시 그려도 그 시트)

/**
 * 엑셀 파일을 칸에 그린다 — 시트 탭과 csv 같은 표 (GET /api/sheet 가 고른 시트 하나의 값을 준다). sheet: 이 시트로 (탭을 누름).
 * 수정 시각은 HEAD 로 받아 두고 코드 화면처럼 바뀌면 다시 그린다 (check)
 * @param {Pane} pane
 * @param {string} path
 * @param {ShowOptions} [options]
 */
async function showSheet(pane, path, { line, scrollTop, sheet } = {}) {
  const id = ++pane.renderId;
  const { view, tab } = pane;
  const key = `${tab.id}:${path}`;
  if (sheet != null) sheetChoice.set(key, sheet);
  let data;
  let size = 0;
  let modified = null;
  try {
    const head = await fetch(docUrl(tab, path), { method: 'HEAD', cache: 'no-store' });
    if (!head.ok) throw Object.assign(new Error(`HTTP ${head.status}`), { status: head.status });
    size = Number(head.headers.get('Content-Length')) || 0;
    modified = head.headers.get('Last-Modified');
    pane.codeStamp = `${modified}|${size}`;
    data = await getJSON(`/api/sheet?p=${encodeURIComponent(tab.id)}&path=${encodeURIComponent(path)}&sheet=${sheetChoice.get(key) ?? 0}`);
  } catch (err) {
    if (id !== pane.renderId) return false;
    if (err.status === 404) showMissing(view, path, err);
    else notice(view, path, err.message);
    finish(pane, path, null, { path, info: size ? formatSize(size) : '' });
    return true;
  }
  if (id !== pane.renderId) return false;
  sheetChoice.set(key, data.index);
  const top = typeof scrollTop === 'function' ? scrollTop() : scrollTop;
  const sh = data.sheet;
  const keep = view.classList.contains('csv-view') ? view.csv : null;
  view.className = 'md-body code-view';
  delete view.dataset.docPath;
  view.dataset.codePath = path;
  view.dataset.sheet = sh?.name ?? '';
  view.dataset.firstCol = String(sh?.first_col ?? 0);
  const tabs = data.sheets.map((s, i) => `<button type="button" class="xl-sheet${s.hidden ? ' xl-hidden' : ''}" data-sheet="${i}" aria-pressed="${i === data.index}"`
    + `${s.hidden ? ` title="${esc(t('숨긴 시트'))}"` : ''}>${esc(s.name)}</button>`).join('');
  view.innerHTML = `<header class="cv-head"><div class="cv-title">${esc(basename(path))}</div>`
    + `<div class="cv-sub">${dirname(path) ? `${esc(dirname(path))} · ` : ''}${esc(t('엑셀'))}</div>`
    + `<div class="cv-tools">${openButton(path)}<button type="button" class="text-btn cv-copy" title="${esc(t('지금 시트를 탭으로 나눈 글로 — 엑셀에 붙이면 칸이 나뉩니다'))}">${t('전체 복사')}</button></div>`
    + `<nav class="xl-sheets" aria-label="${esc(t('시트'))}">${tabs}</nav></header>`;
  if (!sh) {
    view.dataset.sheet = '';
    view.codeText = '';
    view.insertAdjacentHTML('beforeend', `<p class="xl-empty">${esc(t('시트가 없습니다'))}</p>`);
    finish(pane, path, null, { path, info: `${t('엑셀')} · ${formatSize(size)}${modifiedText(modified)}` });
    return true;
  }
  const first = sh.first_col;
  const rows = sh.rows.map(([, cells]) => cells.concat(Array(Math.max(0, sh.cols - cells.length)).fill('')));
  const lines = sh.rows.map(([r]) => [r, r]);
  // 행 번호 자리마다 그 행의 칸을 탭으로 이은 글 — '이 줄 복사'·Ctrl+C·'전체 복사'
  const text = Array(sh.rows.length ? sh.rows.at(-1)[0] : 0).fill('');
  for (const [r, cells] of sh.rows) text[r - 1] = cells.join('\t');
  view.codeText = text.join('\n');
  const letter = (c) => colName(first + c);
  const note = sh.truncated ? t('앞부분만 보입니다 (행 {rows}·칸 {cells}까지) — 전부 보려면 엑셀로 여세요', { rows: '50,000', cells: '1,000,000' }) : '';
  const shown = renderRows(view, rows, lines, `${key}:${data.index}`, { letter, titleOf: (r, c) => sh.formulas[`${letter(c)}${r}`] || '', note, keep, merges: sh.merges, line });
  if (!rows.length) view.insertAdjacentHTML('beforeend', `<p class="xl-empty">${esc(t('빈 시트입니다'))}</p>`);
  finish(pane, path, null, {
    path, info: `${t('엑셀')} · ${t("'{name}' 시트", { name: sh.name })} · ${t('{n}행', { n: shown.rows.toLocaleString() })} · ${t('{n}열', { n: shown.cols })}`
      + ` · ${formatSize(size)}${modifiedText(modified)}`,
  });
  if (top != null) pane.scroller.scrollTop = top;
  else if (line) goToLine(view, line, { flash: true });
  else pane.scroller.scrollTop = 0;
  return true;
}

/** 머리줄의 '편집' — 코드만 (자료 파일은 편집 모드가 열지 않는다) */
const editButton = (path) => (isCode(path) ? `<button type="button" class="text-btn cv-edit" title="${t('여기서 고치기 — 편집 모드 (Ctrl+E)')}">`
  + `<svg aria-hidden="true"><use href="#i-edit"/></svg>${t('편집')}</button>` : '');

/** 머리줄의 '편집기로 열기' — 자료 파일(csv·txt 등)·엑셀은 기본 앱(엑셀·메모장)으로 */
function openButton(path) {
  return isDataFile(path) || isSheet(path)
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
  const keep = view.classList.contains('csv-view') ? view.csv : null;   // 다시 그릴 때 계산 열은 그대로 (D86)
  view.className = 'md-body code-view';
  delete view.dataset.docPath;
  view.innerHTML = `<header class="cv-head"><div class="cv-title">${esc(basename(path))}</div>`
    + `<div class="cv-sub">${dirname(path) ? `${esc(dirname(path))} · ` : ''}${esc(languageOf(path).name)}</div>`
    + `<div class="cv-tools">${editButton(path)}${openButton(path)}`
    + `<button type="button" class="text-btn cv-copy">${t('전체 복사')}</button></div></header>`;
  view.dataset.codePath = path;
  view.codeText = text;
  const info = renderCsv(view, path, text, `${tab.id}:${path}`, keep, line);
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

/** 코드 화면에서 line 번째 줄로 (가운데), flash 면 잠깐 표시. 현재 위치도 그 줄로 (spotlight.js — 'reveal') */
export function goToLine(view, line, { flash = false } = {}) {
  const el = view.querySelector(`.cv-line[data-line="${Number(line)}"]`);
  if (!el) return null;
  emit('reveal', el);
  el.scrollIntoView({ block: 'center' });
  if (flash) {
    el.classList.remove('lec-target');
    void el.offsetWidth;
    el.classList.add('lec-target');
    setTimeout(() => el.classList.remove('lec-target'), 1800);
  }
  return el;
}

/** 보고 있는 코드 파일의 수정 시각이 바뀌었으면 다시 그린다 — 보이는 칸마다 (모두 펼치기 중이면 펼친 칸 모두, D73) */
async function check() {
  if (document.hidden || !S.tab) return;
  await Promise.all(S.tab.panes.filter(paneShown).map(checkPane));
}

async function checkPane(pane) {
  const v = pane.current;
  if (v?.type !== 'code' || pane.pending) return;
  try {
    const res = await fetch(docUrl(pane.tab, v.path), { method: 'HEAD', cache: 'no-store' });
    const stamp = res.ok ? `${res.headers.get('Last-Modified')}|${Number(res.headers.get('Content-Length')) || 0}` : 'gone';
    if (paneShown(pane) && pane.current === v && stamp !== pane.codeStamp) emit('refresh-view', pane);
  } catch { /* 서버가 잠시 답하지 않음 */ }
}

export function initCodeView() {
  initCsv($('#lec-panes'));   // 표의 거르기·정렬·통계 (D60)
  $('#lec-panes').addEventListener('click', (e) => {
    const view = e.target.closest('.code-view');
    if (!view) return;
    const path = view.dataset.codePath || S.view?.path;
    const sheetBtn = e.target.closest('.xl-sheet[data-sheet]');
    if (sheetBtn) {   // 엑셀의 시트 탭 (D77)
      const pane = S.panes.find((p) => p.view === view);
      if (pane && sheetBtn.getAttribute('aria-pressed') !== 'true') showSheet(pane, path, { sheet: Number(sheetBtn.dataset.sheet), scrollTop: 0 });
      return;
    }
    if (e.target.closest('.cv-editor')) openExternal(path);
    else if (e.target.closest('.cv-copy')) {
      copyText(view.codeText || '').then((ok) => toast(ok ? t('복사했습니다: {what}', { what: t('{name} 전체', { name: basename(path) }) }) : t('복사하지 못했습니다')));
    }
  });
  setInterval(check, CHECK_MS);
  on('pane', () => check());   // 다른 탭을 고르면 그 탭의 코드가 그사이 바뀌었는지
}
