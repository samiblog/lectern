// 만들기 (D105·D177): 고른 폴더에 새 md 문서·Lectern 슬라이드·코드 파일·자료 파일·폴더를 만든다.
// 종류는 연 곳에 따라 — 사이드바 '문서' 묶음은 md 문서·슬라이드·폴더, '코드'는 코드 파일·폴더, '자료'는 자료 파일·폴더, '폴더'와 Ctrl+N·명령 찾기는 모두.
// md 문서는 제목과 스타일을 정해 만들고 md 문서 화면에서 바로 쓴다 (편집 모드로 가지 않는다). 제목의 처음 값은 '새 문서'(있으면 번호를 붙여),
// 스타일의 처음 값은 가장 최근에 쓴 것이다. 제목이 파일 이름이 된다. 번호가 있는 스타일은 보기 머리글 두 줄을 넣는다 (D107).
// Lectern 슬라이드를 고르면 만들기 다음에 첫 장의 템플릿 갤러리가 뜬다 (D101).
// 코드·자료 파일은 이름(확장자까지)을 정해 빈 파일을 만들고 편집 모드로 연다 (POST /api/new-file — 서버가 확장자를 거른다). 코드의 확장자는 처음에
// 그 프로젝트에 가장 많은 것. CSV 는 서버가 UTF-8 BOM 을 붙이고, CSV·TSV 는 '머리행'을 적으면 첫 줄로 넣는다.
// 폴더는 만든 뒤 창을 닫지 않고 그 폴더 안에 만들 것을 정하게 한다 — 빈 폴더는 트리에 나오지 않는다 (D114).
// 위치는 고를 수 있다 — 프로젝트 맨 위, 비어 있는 폴더도. 비어 있는 폴더는 트리에 나오지 않으므로 서버에서 받는다.
// 여는 곳: 사이드바 묶음 머리줄의 만들기, Ctrl+N, 문서 탭 줄의 +, 우클릭 '새 문서 만들기…'·'새 코드 파일 만들기…' 등, 명령 찾기.

import { S, on, emit } from './store.js';
import { getJSON, postJSON, saveConfig } from './api.js';
import { $, $$, toast, basename, blockedReadOnly } from './util.js';
import { html, setHtml } from './html.js';
import { t } from './i18n.js';
import { preview, setOwnStyles } from './headstyle.js';
import { styleGroups } from './mdstyle.js';
import { newDocGuess, cleanPath, createDoc, openCreated } from './newdoc.js';
import { openInNewTab } from './doctabs.js';
import { isCode, DATA_EDIT_EXT } from './icons.js';
import { askText } from './putmenu.js';

export const KINDS = ['md', 'deck', 'code', 'data', 'folder'];
/** 사이드바 묶음마다 만드는 것 (D177) */
export const SECTION_KINDS = { docs: ['md', 'deck', 'folder'], code: ['code', 'folder'], others: ['data', 'folder'], folder: KINDS };
// 서버 editing.NEW_CODE_SKIP — 문서로 보는 html, 빈 파일로는 열리지 않는 ipynb, 도구가 만드는 lock
const CODE_SKIP = new Set(['html', 'htm', 'ipynb', 'lock']);

/** @type {{tab: any, kind: string, kinds: string[], main: string, mine: any[], items: any[], sel: number, folders: string[], touched: boolean, ext: string} | null} */
let asked = null;

const box = () => $('#lec-newdoc');
const title = () => $('#lec-newdoc-title');
const list = () => $('#lec-newdoc-list');
const where = () => $('#lec-newdoc-folder');
const header = () => $('#lec-newdoc-header');
const isDoc = (kind) => kind === 'md' || kind === 'deck';
const extOf = (name) => (name.lastIndexOf('.') > 0 ? name.slice(name.lastIndexOf('.') + 1).toLowerCase() : '');
const codeExt = (ext) => !!ext && isCode(`x.${ext}`) && !CODE_SKIP.has(ext);
const dataExt = (ext) => DATA_EDIT_EXT.has(ext);
const fileExt = (kind, ext) => (kind === 'code' ? codeExt(ext) : kind === 'data' ? dataExt(ext) : false);

/** 위치 목록을 채운다 — 맨 앞은 프로젝트 맨 위 */
function drawFolders(folders, chosen) {
  setHtml(where(), ['', ...folders].map((f) => html`<option value="${f}">${f ? `${f}/` : t('프로젝트 맨 위')}</option>`));
  where().value = chosen;
}

/** 다음 '새 문서' 이름 — 고른 폴더 기준 */
const guessTitle = (dir) => basename(newDocGuess(dir)).replace(/\.md$/, '');

/** 프로젝트에 이미 있는 경로인지 — 문서·코드·자료·폴더 */
function known(path) {
  const index = S.tab?.others?.index;
  return S.fileMap.has(path) || S.dirs.has(path) || !!asked?.folders.includes(path) || !!index?.code?.has(path) || !!index?.files?.has(path);
}

/** 이 프로젝트에 가장 많은 코드 확장자 — 없으면 py */
function usualCodeExt() {
  const count = new Map();
  for (const path of S.tab?.others?.index?.code?.keys() || []) {
    const ext = extOf(basename(path));
    if (codeExt(ext)) count.set(ext, (count.get(ext) || 0) + 1);
  }
  return [...count].sort((a, b) => b[1] - a[1])[0]?.[0] || 'py';
}

/** 종류마다 이름의 처음 값 — 고른 폴더에 없는 이름 ('새 파일.py', '새 자료.csv', '새 폴더' — 있으면 번호를 붙여) */
function guessName(kind, dir) {
  if (isDoc(kind)) return guessTitle(dir);
  const base = kind === 'folder' ? t('새 폴더') : kind === 'data' ? t('새 자료') : t('새 파일');
  const ext = kind === 'code' ? `.${asked.ext}` : kind === 'data' ? '.csv' : '';
  for (let n = 1; ; n += 1) {
    const name = `${base}${n > 1 ? ` ${n}` : ''}${ext}`;
    if (!known(`${dir ? `${dir}/` : ''}${name}`)) return name;
  }
}

/** 이름 칸에 초점 — 파일이면 확장자 앞까지 골라 둔다 (치면 이름만 바뀐다) */
function focusName() {
  const el = title();
  el.focus();
  const ext = asked && !isDoc(asked.kind) && asked.kind !== 'folder' ? extOf(el.value) : '';
  el.setSelectionRange(0, ext ? el.value.length - ext.length - 1 : el.value.length);
}

/** 폴더들을 받는다. 못 받으면 트리가 아는 폴더로 */
async function foldersOf(tab) {
  try {
    return (await getJSON(`/api/folders?p=${encodeURIComponent(tab.id)}`)).folders;
  } catch {
    return [...S.dirs].filter(Boolean);
  }
}

/** 폴더 하나를 만든다 — 이름을 묻는다. 만든 경로, 그만두면 null */
async function makeFolder(tab, parent, at) {
  const name = await askText({ title: t('새 폴더 — {where}', { where: parent ? `${parent}/` : t('프로젝트 맨 위') }), at, placeholder: t('폴더 이름') });
  if (!name?.trim()) return null;
  try {
    return (await postJSON('/api/new-folder', { p: tab.id, parent, name })).path;
  } catch (e) {
    toast(e.message, 'error');
    return null;
  }
}

/** 제목 → 파일 이름 (확장자 없이). Windows 가 받지 않는 글자는 빈칸으로 */
export function fileName(text) {
  return String(text).replace(/\.(md|markdown)$/i, '').replace(/[\\/:*?"<>|]/g, ' ').replace(/\s+/g, ' ').trim().replace(/[. ]+$/, '');
}

/** 창의 알림 줄 — ok 면 잘못이 아니라 안내 */
function setMsg(text, ok = false) {
  const p = $('#lec-newdoc-msg');
  p.hidden = !text;
  p.textContent = text;
  p.classList.toggle('bad', !ok);
}

function headOf(kind) {
  if (kind === 'code') return t('새 코드 파일 만들기');
  if (kind === 'data') return t('새 자료 파일 만들기');
  return kind === 'folder' ? t('새 폴더 만들기') : t('새 문서 만들기');
}

function hintOf(kind) {
  if (kind === 'code') return t('확장자로 형식을 정합니다 — .py · .js · .ts · .json · .yaml · .sql · .r 등. 빈 파일을 만들어 편집 모드로 엽니다');
  if (kind === 'data') return t('.csv · .tsv · .txt — 빈 파일을 만들어 편집 모드로 엽니다. CSV 는 한국어 엑셀이 바로 열 수 있게 UTF-8 BOM 을 붙입니다');
  if (kind === 'folder') return t('빈 폴더는 목록에 나오지 않습니다 — 만든 뒤 그 안에 만들 것을 정합니다');
  return '';
}

function draw() {
  const { kind } = asked;
  for (const b of $$('#lec-newdoc .mdstyle-kinds button')) {
    const on = b.dataset.kind === kind;
    b.hidden = !asked.kinds.includes(b.dataset.kind);
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', String(on));
  }
  $('#lec-newdoc-head').textContent = headOf(kind);
  $('#lec-newdoc-title-label').textContent = isDoc(kind) ? t('제목') : t('이름');
  $('#lec-newdoc-styles').hidden = kind !== 'md';
  $('#lec-newdoc-note').hidden = kind !== 'deck';
  const hint = hintOf(kind);
  $('#lec-newdoc-hint').hidden = !hint;
  $('#lec-newdoc-hint').textContent = hint;
  $('#lec-newdoc-header-row').hidden = !(kind === 'data' && ['csv', 'tsv'].includes(extOf(title().value.trim())));
  $('#lec-newdoc-mkdir').hidden = kind === 'folder';
  $('#lec-newdoc-keys').textContent = kind === 'md' ? t('↑·↓ 스타일 · Enter 만들기 · Esc 그만두기') : t('Enter 만들기 · Esc 그만두기');
  if (kind !== 'md') return;
  const groups = styleGroups(asked.mine, S.config.recent_md_styles || []);
  asked.items = groups.flatMap(([, rows]) => rows);
  let i = -1;
  setHtml(list(), groups.flatMap(([head, rows]) => [
    html`<li class="head">${head}</li>`,
    ...rows.map((r) => {
      i += 1;
      return html`<li role="option" data-i="${i}" class="${i === asked.sel ? 'sel' : ''}" aria-selected="${i === asked.sel}">
        <span class="t">${r.name}${r.use ? html` <em>${r.use}</em>` : ''}</span><span class="p">${r.sub}</span>
      </li>`;
    }),
  ]));
  const item = asked.items[asked.sel];
  const sample = [`# ${title().value.trim() || t('제목')}`, '', `## ${t('첫째 절')}`, '', `### ${t('세부 절')}`, '', `#### ${t('작은 절')}`, ''];
  setHtml($('#lec-newdoc-preview'), [html`<li class="doc">${sample[0].slice(2)}</li>`,
    ...(item ? preview(sample, item.id) : []).map((h) => html`<li style="--d:${h.depth - 1}">${h.text}</li>`)]);
  list().querySelector('li.sel')?.scrollIntoView({ block: 'nearest' });
}

/** 스타일을 고른다 */
function pick(i) {
  asked.sel = i;
  draw();
}

/**
 * 만들기 창을 연다. dir: 만들 폴더 (null 이면 지금 보는 문서·폴더 개요의 폴더).
 * kinds: 고를 수 있는 종류 (사이드바 묶음마다 — SECTION_KINDS), kind: 처음 고른 종류
 */
export async function askNewDocument(dir = null, { kinds = KINDS, kind = '' } = {}) {
  if (!S.tab) {
    toast(t('먼저 폴더를 여세요'));
    return;
  }
  const tab = S.tab;
  if (blockedReadOnly(tab) || asked) return;
  const guess = newDocGuess(dir);
  const folder = guess.includes('/') ? guess.slice(0, guess.lastIndexOf('/')) : '';
  const folders = await foldersOf(tab);
  let mine = [];
  try {
    mine = (await getJSON('/api/md-styles')).styles;
    setOwnStyles(mine);
  } catch { /* 내 스타일 없이 — 기본 스타일로 만들 수 있다 */ }
  if (S.tab !== tab || asked) return;
  const first = kinds.includes(kind) ? kind : kinds[0];
  asked = { tab, kind: first, kinds, main: first === 'folder' ? kinds.find((k) => k !== 'folder') || 'md' : first, mine, items: [], sel: 0, folders, touched: false, ext: usualCodeExt() };
  drawFolders(folders.includes(folder) || !folder ? folders : [...folders, folder], folder);
  title().value = guessName(first, folder);
  header().value = '';
  setMsg('');
  // 스타일의 처음 값 — 가장 최근에 쓴 것, 없으면 번호 없음 (목록은 draw 가 같은 차례로 다시 만든다)
  asked.items = styleGroups(mine, S.config.recent_md_styles || []).flatMap(([, rows]) => rows);
  const recent = (S.config.recent_md_styles || []).map((id) => asked.items.findIndex((r) => r.id === id)).find((n) => n >= 0);
  asked.sel = recent ?? Math.max(0, asked.items.findIndex((r) => r.id === 'plain'));
  draw();
  box().hidden = false;
  focusName();
}

export function closeNewDocument() {
  if (box().hidden) return false;
  box().hidden = true;
  asked = null;
  return true;
}

function submit() {
  if (!asked) return;
  if (isDoc(asked.kind)) submitDoc();
  else if (asked.kind === 'folder') submitFolder();
  else submitFile();
}

async function submitDoc() {
  const deck = asked.kind === 'deck';
  const dir = where().value;
  const text = title().value.trim();
  const name = fileName(text);
  if (!name) {
    setMsg(t('제목을 쓰세요 — 제목이 파일 이름이 됩니다'));
    title().focus();
    return;
  }
  const path = cleanPath(`${dir ? `${dir}/` : ''}${name}`);
  const scheme = deck ? '' : asked.items[asked.sel]?.id || '';
  const template = deck ? await new Promise((resolve) => { emit('pick-template', { title: t('첫 장의 템플릿을 고르세요'), resolve }); }) : null;
  if (!asked) return;
  if (deck && !template) {   // 취소 — 제목을 고쳐 다시 고를 수 있게
    title().focus();
    return;
  }
  let made;
  try {
    made = await createDoc(path, { deck, template, title: text.replace(/\.(md|markdown)$/i, ''), scheme });
  } catch (e) {   // 같은 이름·쓸 수 없는 이름 — 고쳐서 다시 Enter
    if (asked) setMsg(e.message);
    title().focus();
    return;
  }
  closeNewDocument();
  if (scheme) saveConfig({ recent_md_styles: [scheme, ...(S.config.recent_md_styles || []).filter((x) => x !== scheme)].slice(0, 8) });
  toast(t('새 문서를 만들었습니다: {path}', { path: made }));
  openCreated(made, { deck, scheme });
}

/** 머리행 칸 → 열 이름들 (쉼표·탭으로 나눔). 모두 비면 [] */
function columns(raw) {
  const cols = String(raw).split(/[,\t]/).map((c) => c.trim());
  return cols.some(Boolean) ? cols : [];
}

/** 코드·자료 파일 — 빈 파일(CSV 는 BOM·머리행)을 만들고 새 문서 탭에서 편집 모드로 연다 */
async function submitFile() {
  const { kind, tab } = asked;
  const dir = where().value;
  let name = title().value.trim();
  if (!name) {
    setMsg(t('이름을 쓰세요'));
    title().focus();
    return;
  }
  if (!name.includes('.')) name += kind === 'code' ? `.${asked.ext}` : '.csv';   // 확장자를 빼먹으면 처음 값의 것으로
  const ext = extOf(name);
  if (!fileExt(kind, ext)) {
    setMsg(kind === 'code' ? t('코드 파일의 확장자를 쓰세요 — 예: 정리.py · 도구.js · 설정.json')
      : t('자료 파일은 .csv · .tsv · .txt 로 끝나는 이름이어야 합니다'));
    focusName();
    return;
  }
  const cols = kind === 'data' && (ext === 'csv' || ext === 'tsv') ? columns(header().value) : [];
  let made;
  try {
    made = (await postJSON('/api/new-file', { p: tab.id, path: `${dir ? `${dir}/` : ''}${name}`, header: cols })).path;
  } catch (e) {   // 같은 이름·쓸 수 없는 이름 — 고쳐서 다시 Enter
    if (asked) setMsg(e.message);
    focusName();
    return;
  }
  closeNewDocument();
  toast(t('새 파일을 만들었습니다: {path}', { path: made }));
  if (S.tab !== tab) return;
  const pane = await openInNewTab({ type: 'code', path: made });
  if (pane && S.pane === pane) emit('edit');
}

/** 폴더 — 만든 뒤 창을 닫지 않고 그 폴더 안에 만들 것을 정하게 한다 (빈 폴더는 트리에 나오지 않는다) */
async function submitFolder() {
  const { tab } = asked;
  const parent = where().value;
  const name = title().value.trim();
  if (!name) {
    setMsg(t('이름을 쓰세요'));
    title().focus();
    return;
  }
  let made;
  try {
    made = (await postJSON('/api/new-folder', { p: tab.id, parent, name })).path;
  } catch (e) {
    if (asked) setMsg(e.message);
    focusName();
    return;
  }
  toast(t('폴더를 만들었습니다: {path}', { path: made }));
  if (!asked) return;
  asked.folders = await foldersOf(tab);
  if (!asked) return;
  drawFolders(asked.folders.includes(made) ? asked.folders : [...asked.folders, made], made);
  setKind(asked.main, { fresh: true });
  setMsg(t('폴더를 만들었습니다 — 그 안에 만들 것을 정하세요 (그만두려면 Esc)'), true);
}

function onKey(e) {
  if (e.isComposing || e.keyCode === 229 || !asked) return;   // 한글 조합 중
  if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && asked.kind === 'md' && e.target !== where()) {
    e.preventDefault();
    const n = asked.items.length;
    if (n) pick((asked.sel + (e.key === 'ArrowDown' ? 1 : -1) + n) % n);
  } else if (e.key === 'Enter' && e.target.tagName !== 'BUTTON') {
    e.preventDefault();
    submit();
  } else if (e.key === 'Escape') {
    e.preventDefault();
    e.stopPropagation();
    closeNewDocument();
  }
}

/**
 * 종류를 바꾼다 — 초점은 이름에 둔다. 쓴 이름은 이어 쓴다 (md 문서 ↔ 슬라이드는 그대로, 파일이면 확장자만 그 종류의 것으로).
 * 아직 고치지 않은 이름이거나 fresh 면 그 종류의 처음 값으로
 */
function setKind(kind, { fresh = false } = {}) {
  const prev = asked.kind;
  asked.kind = kind;
  const now = title().value.trim();
  if (fresh || !asked.touched || !now) {
    title().value = guessName(kind, where().value);
    asked.touched = false;
  } else if (!(isDoc(prev) && isDoc(kind))) {
    const ext = extOf(now);
    const stem = ext && (fileExt('code', ext) || fileExt('data', ext) || ext === 'md') ? now.slice(0, -ext.length - 1) : now;
    const keep = fileExt(kind, ext) ? ext : '';
    title().value = kind === 'code' || kind === 'data' ? `${stem}.${keep || (kind === 'code' ? asked.ext : 'csv')}` : stem;
  }
  setMsg('');
  draw();
  focusName();
}

/** 우클릭 '새 폴더 만들기…': 폴더를 만들고 그 폴더의 새 문서 창을 연다 — 빈 폴더는 트리에 나오지 않는다 */
async function newFolderAt(dir) {
  const tab = S.tab;
  if (!tab || blockedReadOnly(tab)) return;
  const made = await makeFolder(tab, dir, { x: Math.max(8, innerWidth / 2 - 150), y: 140 });
  if (!made || S.tab !== tab) return;
  toast(t('폴더를 만들었습니다: {path}', { path: made }));
  askNewDocument(made);
}

/** 창의 새 폴더: 고른 위치 안에 만들고 그 폴더를 고른다 */
async function folderInDialog() {
  const { tab } = asked;
  const parent = where().value;
  const made = await makeFolder(tab, parent, $('#lec-newdoc-mkdir'));
  if (!asked) return;
  if (made) {
    asked.folders = await foldersOf(tab);
    drawFolders(asked.folders, made);
    if (where().value !== made) drawFolders([...[...where().options].map((o) => o.value).filter(Boolean), made], made);
    title().value = guessName(asked.kind, made);
    asked.touched = false;
  }
  focusName();
}

export function initNewDialog() {
  // 우클릭·문서 탭 줄의 +·묶음의 만들기 (tree·others·tabs·palette). section: 사이드바 묶음 이름 — 그 묶음의 종류만
  on('new-doc', ({ dir = null, section = '', kind = '' } = {}) => askNewDocument(dir, { kinds: SECTION_KINDS[section] || KINDS, kind }));
  on('new-folder', ({ dir = '' }) => newFolderAt(dir));   // 우클릭 '새 폴더 만들기…' (tree·others·tabs)
  where().addEventListener('change', () => {
    title().value = guessName(asked.kind, where().value);
    asked.touched = false;
    draw();
    focusName();
  });
  $('#lec-newdoc-mkdir').addEventListener('click', folderInDialog);
  on('tab', closeNewDocument);   // 다른 프로젝트 탭으로 — 만들 폴더는 그 탭의 것
  box().addEventListener('keydown', onKey);
  box().addEventListener('mousedown', (e) => { if (e.target === box()) closeNewDocument(); });
  title().addEventListener('input', () => {
    if (!asked) return;
    asked.touched = true;
    setMsg('');
    draw();
  });
  list().addEventListener('click', (e) => {
    const li = e.target.closest('li[data-i]');
    if (li) pick(Number(li.dataset.i));
    title().focus();
  });
  list().addEventListener('dblclick', (e) => { if (e.target.closest('li[data-i]')) submit(); });
  for (const b of $$('#lec-newdoc .mdstyle-kinds button')) b.addEventListener('click', () => { if (asked) setKind(b.dataset.kind); });
  $('#lec-newdoc-go').addEventListener('click', submit);
  $('#lec-newdoc-no').addEventListener('click', closeNewDocument);
  $('#lec-docs-new').addEventListener('click', () => askNewDocument(null, { kinds: SECTION_KINDS.docs }));
}
