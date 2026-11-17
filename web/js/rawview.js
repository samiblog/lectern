// 설정 원문 보기 (D160): Lectern 설정(config.json)과 AI 도구에 건네는 것(작성 안내 요약·내 문체·글쓰기 스타일·스킬·Claude Code 설정)을
// 원문 그대로 읽기만 한다. 줄마다의 뜻은 서버가 설명 줄로 끼워 준다 — 번호 없는 흐린 '//' 줄이고 파일에는 없다 (파일 줄의 번호는 그대로).
// 목록과 경로는 서버가 정한다 (GET /api/raw/list·/api/raw — rawfiles.py). 고치는 길은 없다 — Lectern 설정은 '설정 파일 열기'.

import { S } from './store.js';
import { getJSON } from './api.js';
import { $, $$, toast, copyText } from './util.js';
import { html, setHtml } from './html.js';
import { t } from './i18n.js';

const box = () => $('#lec-raw');
let groups = [];
let current = { id: '', sub: '' };
let asking = 0;

const query = (params) => new URLSearchParams({ ...params, ...(S.tab ? { p: S.tab.id } : {}) }).toString();
const items = () => groups.flatMap((g) => g.items);

function sizeOf(n) {
  return n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : n >= 1024 ? `${Math.round(n / 1024)} KB` : `${n} B`;
}

function renderList() {
  setHtml($('#lec-raw-list'), groups.map((g) => html`<div class="raw-group">${g.group}</div>${g.items.map((it) => html`<button type="button" class="raw-item${it.exists ? '' : ' missing'}${it.id === current.id ? ' on' : ''}" data-id="${it.id}" title="${it.path}">${it.label}${it.exists ? '' : html`<small>${t('파일 없음')}</small>`}</button>`)}`));
}

/** 한 파일: 경로, (스킬이면) 폴더의 파일들, 원문 줄과 설명 줄 */
function renderFile(got) {
  $('#lec-raw-path').textContent = got.path;
  const files = $('#lec-raw-files');
  files.hidden = !got.files;
  if (got.files) {
    setHtml(files, got.files.map((f) => html`<button type="button" class="raw-file${f.rel === got.sub ? ' on' : ''}" data-f="${f.rel}" title="${sizeOf(f.size)}">${f.rel}</button>`));
  }
  const text = $('#lec-raw-text');
  if (!got.rows.length) {
    const why = { missing: t('파일이 없습니다 — 아직 설치하거나 저장하지 않았습니다'), binary: t('글 파일이 아닙니다 ({size}) — 읽기만 하는 목록에 둡니다', { size: sizeOf(got.size || 0) }),
      big: t('1 MB 가 넘어 보이지 않습니다 ({size})', { size: sizeOf(got.size || 0) }) }[got.reason] || '';
    setHtml(text, html`<div class="raw-empty">${why}</div>`);
    return;
  }
  setHtml(text, got.rows.map((r) => (r.note !== undefined
    ? html`<div class="raw-line raw-note"><span class="raw-n"></span><span class="raw-t">// ${r.note}</span></div>`
    : html`<div class="raw-line"><span class="raw-n">${r.n}</span><span class="raw-t">${r.text}</span></div>`)));
  text.scrollTop = 0;
}

async function show(id, sub = '') {
  const me = ++asking;
  current = { id, sub };
  renderList();
  try {
    const got = await getJSON(`/api/raw?${query({ id, ...(sub ? { f: sub } : {}) })}`);
    if (me !== asking) return;
    current.sub = got.sub || '';
    renderFile(got);
  } catch (e) {
    if (me !== asking) return;
    $('#lec-raw-path').textContent = '';
    setHtml($('#lec-raw-text'), html`<div class="raw-empty">${t('읽지 못했습니다: {error}', { error: e.message })}</div>`);
  }
}

/**
 * 원문 보기를 연다. ids: 목록의 id 하나나 여럿 — 여럿이면 있는 파일 가운데 앞의 것 (설치한 것 → Lectern 에 든 것).
 * 'config', 'rules', 'voice', 'csettings', 'csettings-local', 'style:…', 'skill:…', 'lstyle', 'lskill:…' 등. 없으면 처음 것
 * @param {string | string[]} [ids]
 */
export async function openRaw(ids = 'config') {
  try {
    groups = (await getJSON(`/api/raw/list?${query({})}`)).groups;
  } catch (e) {
    toast(t('원문 목록을 읽지 못했습니다: {error}', { error: e.message }), 'error');
    return;
  }
  box().hidden = false;
  const all = items();
  const want = [ids].flat();
  const pick = want.map((id) => all.find((it) => it.id === id && it.exists)).find(Boolean) || all.find((it) => it.id === want.at(-1)) || all[0];
  await show(pick.id);
  $(`#lec-raw-list .raw-item[data-id="${CSS.escape(pick.id)}"]`)?.focus();
}

export function closeRaw() {
  if (box().hidden) return false;
  box().hidden = true;
  return true;
}

export function initRaw() {
  $('#lec-raw-list').addEventListener('click', (e) => {
    const b = e.target.closest('.raw-item');
    if (b) show(b.dataset.id);
  });
  $('#lec-raw-list').addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const all = $$('#lec-raw-list .raw-item');
    const next = all[(all.indexOf(document.activeElement) + (e.key === 'ArrowDown' ? 1 : -1) + all.length) % all.length];
    next.focus();
    show(next.dataset.id);
  });
  $('#lec-raw-files').addEventListener('click', (e) => {
    const b = e.target.closest('.raw-file');
    if (b) show(current.id, b.dataset.f);
  });
  $('#lec-raw-copy').addEventListener('click', async () => {
    const path = $('#lec-raw-path').textContent;
    if (path) toast(await copyText(path) ? t('경로를 복사했습니다') : t('복사하지 못했습니다'));
  });
  $('#lec-raw-close').addEventListener('click', closeRaw);
  box().addEventListener('click', (e) => { if (e.target === box()) closeRaw(); });   // 바깥을 누르면 닫기
}
