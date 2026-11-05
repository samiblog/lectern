// 프로젝트 메모 (D92): 탭 막대의 '메모'·Alt+M 로 오른쪽 패널을 열고 닫는다. 카드는 Keep 처럼 — 제목·본문·할 일·색·고정.
// 글은 프로젝트의 .lectern/notes.md 하나 (notesdata.js 가 읽고 쓰고, 서버는 lectern/notes.py). 메모를 쓸 때만 파일이 생긴다.
// 프로젝트 탭마다 tab.notes. 저장은 쓰는 대로 조금 뒤에, 칸을 떠날 때와 패널을 닫을 때는 바로.
// 그사이 파일이 바뀌었으면(Claude Code·다른 창) 다시 읽어 합친다 — 고치던 메모는 남고 지운 메모는 되살리지 않는다.
// 다른 모듈은 'new-note' 로 메모를 더한다 (우클릭 '새 메모로 보내기' — 이 모듈을 부르면 import 순환이 생긴다).

import { S, on, emit } from './store.js';
import { getJSON, postJSON } from './api.js';
import { openTarget } from './doctabs.js';
import { html, setHtml } from './html.js';
import { $, toast, copyText, rangeText, isMd, isHtml } from './util.js';
import { t } from './i18n.js';
import {
  parseNotes, writeNotes, shownOrder, filterNotes, isTaskList, bodyLines, switchList, toggleTask, setTask, addTask, noteText, fromText, newId, COLORS,
} from './notesdata.js';

const SAVE_MS = 600;
const UNDO_MS = 8000;

const panel = () => $('#lec-notes');
const list = () => $('#lec-notes-list');
const filter = () => $('#lec-notes-filter');

let undo = null;       // 마지막에 지운 메모 {tab, note, at}
let undoTimer = 0;

/** 탭의 메모 상태. touched·removed 는 다음 저장까지 고치거나 지운 메모의 id — 합칠 때 쓴다 */
const stateOf = (tab) => (tab.notes ??= { items: [], hash: null, loaded: false, error: '', touched: new Set(), removed: new Set(), timer: 0, saving: null, again: false });
const noteOf = (st, id) => st.items.find((n) => n.id === id);
const hasWords = (st) => st.items.some((n) => n.title.trim() || n.body.trim());
export const notesOpen = () => !panel().hidden;

function readFrom(st, data) {
  st.hash = data.hash;
  st.items = parseNotes(data.text);
  st.loaded = true;
  st.error = '';
}

async function load(tab) {
  const st = stateOf(tab);
  try {
    readFrom(st, await getJSON(`/api/notes?p=${encodeURIComponent(tab.id)}`));
  } catch (e) {
    st.error = e.message;
  }
  if (tab === S.tab && notesOpen()) render();
}

/** 저장이 409 일 때: 파일을 다시 읽고 고친 메모·새 메모를 얹는다 */
async function merge(tab) {
  const st = stateOf(tab);
  const mine = st.items.filter((n) => st.touched.has(n.id));
  readFrom(st, await getJSON(`/api/notes?p=${encodeURIComponent(tab.id)}`));
  st.items = st.items.filter((n) => !st.removed.has(n.id));
  for (const n of mine) {
    const i = st.items.findIndex((x) => x.id === n.id);
    if (i >= 0) st.items[i] = n;
    else st.items.push(n);
  }
  toast(t('메모 파일이 밖에서 바뀌어 다시 읽고 합쳤습니다'));
}

async function saveNow(tab) {
  const st = stateOf(tab);
  clearTimeout(st.timer);
  st.timer = 0;
  if (st.saving) {
    st.again = true;
    return st.saving;
  }
  if (!st.touched.size && !st.removed.size) return null;
  if (st.hash == null && !hasWords(st)) return null;   // 쓴 것이 없으면 파일을 만들지 않는다
  let failed = false;
  st.saving = (async () => {
    for (let attempt = 0; attempt < 2; attempt += 1) {
      // 보내는 동안 고친 것은 다음 저장에 남긴다 — 보낸 글에 들어 있는 것만 지운다
      const sent = { touched: [...st.touched], removed: [...st.removed] };
      st.touched.clear();
      st.removed.clear();
      try {
        const r = await postJSON('/api/notes', { p: tab.id, text: writeNotes(st.items), hash: st.hash });
        st.hash = r.hash;
        return;
      } catch (e) {
        for (const id of sent.touched) st.touched.add(id);
        for (const id of sent.removed) st.removed.add(id);
        if (e.status !== 409 || attempt) {
          toast(t('메모를 저장하지 못했습니다: {error}', { error: e.message }), 'error', 6000);
          failed = true;   // 다시 시도하지 않는다 — 다음에 고치거나 패널을 닫을 때 저장한다
          return;
        }
        await merge(tab);
        if (tab === S.tab && notesOpen()) render();
      }
    }
  })();
  await st.saving;
  st.saving = null;
  if (failed) st.again = false;
  if (!failed && (st.again || st.touched.size || st.removed.size)) {
    st.again = false;
    return saveNow(tab);
  }
  return null;
}

function touched(tab, note) {
  const st = stateOf(tab);
  st.touched.add(note.id);
  clearTimeout(st.timer);
  st.timer = setTimeout(() => saveNow(tab), SAVE_MS);
}

// ---- 화면 ------------------------------------------------------------------------

const tools = (n) => html`<div class="note-tools">
    <span class="note-colors" role="group" aria-label="${t('색')}">${COLORS.map((c) => html`<button type="button" class="note-dot${c ? ` note-${c}` : ''}${c === n.color ? ' on' : ''}" data-act="color" data-color="${c}" title="${t('색')}" aria-label="${t('색')}"></button>`)}</span>
    <span class="note-acts">
      <button type="button" class="text-btn" data-act="pin" aria-pressed="${n.pinned}">${n.pinned ? t('고정 풀기') : t('고정')}</button>
      <button type="button" class="text-btn" data-act="list" title="${t('글과 할 일 목록을 바꿉니다')}">${isTaskList(n.body) ? t('글로') : t('할 일로')}</button>
      <button type="button" class="text-btn" data-act="copy">${t('복사')}</button>
      <button type="button" class="text-btn" data-act="term" title="${t('터미널에 붙여 넣기 (Enter 는 누르지 않음)')}">${t('터미널')}</button>
      <button type="button" class="text-btn" data-act="send" title="${t('열린 문서 탭이나 새 문서로 바로')}">${t('문서로')}</button>
      <button type="button" class="text-btn note-del" data-act="delete">${t('지우기')}</button>
    </span>
  </div>`;

function tasks(n) {
  const rows = bodyLines(n.body).filter((l) => l.task);
  return html`<ul class="note-tasks">${rows.map((l, i) => html`<li class="${l.done ? 'done' : ''}" data-i="${i}">
      <input type="checkbox"${l.done ? html` checked` : ''} aria-label="${t('끝냄')}"><input type="text" class="note-task" value="${l.text}" aria-label="${t('할 일')}" spellcheck="false">
    </li>`)}</ul><input type="text" class="note-add" placeholder="${t('항목 추가 — Enter')}" aria-label="${t('항목 추가 — Enter')}" spellcheck="false">`;
}

function card(n) {
  const from = fromText(n, rangeText);
  return html`<article class="note-card${n.color ? ` note-${n.color}` : ''}${n.pinned ? ' pinned' : ''}" data-id="${n.id}">
    <input type="text" class="note-title" value="${n.title}" placeholder="${t('제목')}" aria-label="${t('제목')}" spellcheck="false">
    ${isTaskList(n.body) ? tasks(n) : html`<textarea class="note-body" rows="2" placeholder="${t('메모')}" aria-label="${t('메모')}" spellcheck="false">${n.body}</textarea>`}
    ${from ? html`<button type="button" class="note-from" data-act="from" title="${t('그 자리로 가기')}">${from}</button>` : ''}
    ${tools(n)}
  </article>`;
}

/** 본문 칸의 높이를 글에 맞춘다 */
function grow(area) {
  area.style.height = 'auto';
  area.style.height = `${area.scrollHeight + 2}px`;
}

function render() {
  const tab = S.tab;
  const box = list();
  $('#lec-notes-new').disabled = !tab || tab.readonly;
  if (!tab) {
    setHtml(box, html`<p class="side-empty">${t('먼저 폴더를 여세요')}</p>`);
    return;
  }
  if (tab.readonly) {
    setHtml(box, html`<p class="side-empty">${t('보기만 하는 프로젝트라 메모를 쓰지 않습니다 — 고쳐 보려면 그 폴더를 복사해 여세요')}</p>`);
    return;
  }
  const st = stateOf(tab);
  if (st.error) {
    setHtml(box, html`<p class="side-empty">${t('메모를 읽지 못했습니다: {error}', { error: st.error })}</p>`);
    return;
  }
  const query = filter().value;
  const shown = shownOrder(filterNotes(st.items, query));
  if (!shown.length) {
    setHtml(box, html`<p class="side-empty">${query.trim() ? t('맞는 메모가 없습니다') : t('메모가 없습니다 — 새 메모를 누르세요')}</p>`);
    return;
  }
  setHtml(box, shown.map(card));
  for (const area of box.querySelectorAll('.note-body')) grow(area);
}

function hideUndo() {
  clearTimeout(undoTimer);
  undo = null;
  $('#lec-notes-undo').hidden = true;
}

function focusCard(id, selector) {
  list().querySelector(`[data-id="${CSS.escape(id)}"] ${selector}`)?.focus();
}

function newNote(fields = {}) {
  const tab = S.tab;
  if (!tab || tab.readonly) return null;
  const st = stateOf(tab);
  const note = { id: newId(), title: '', body: '', color: '', pinned: false, path: '', line: 0, end: 0, extra: {}, ...fields };
  st.items.unshift(note);
  filter().value = '';
  render();
  if (note.title || note.body) touched(tab, note);
  return note;
}

function removeNote(tab, note) {
  const st = stateOf(tab);
  const at = st.items.indexOf(note);
  st.items.splice(at, 1);
  st.touched.delete(note.id);
  st.removed.add(note.id);
  render();
  clearTimeout(st.timer);
  st.timer = setTimeout(() => saveNow(tab), SAVE_MS);
  if (!note.title.trim() && !note.body.trim()) return;   // 빈 카드는 되돌릴 것이 없다
  undo = { tab, note, at };
  $('#lec-notes-undo').hidden = false;
  clearTimeout(undoTimer);
  undoTimer = setTimeout(hideUndo, UNDO_MS);
}

function restoreNote() {
  if (!undo) return;
  const { tab, note, at } = undo;
  const st = stateOf(tab);
  st.items.splice(Math.min(at, st.items.length), 0, note);
  st.removed.delete(note.id);
  hideUndo();
  render();
  touched(tab, note);
}

async function goToSource(note) {
  const type = isMd(note.path) || isHtml(note.path) ? 'doc' : 'code';
  if (!(await openTarget({ type, path: note.path, newTab: true }))) return;
  if (note.line) emit('go-line', { line: note.line });
}

async function act(name, note, button) {
  const tab = S.tab;
  const text = noteText(note, rangeText);
  if (name === 'color') note.color = button.dataset.color;
  else if (name === 'pin') note.pinned = !note.pinned;
  else if (name === 'list') note.body = switchList(note.body);
  else if (name === 'delete') {
    removeNote(tab, note);
    return;
  } else if (name === 'copy') {
    toast(await copyText(text) ? t('복사했습니다: {what}', { what: note.title.trim() || t('메모') }) : t('복사하지 못했습니다'));
    return;
  } else if (name === 'term') {
    emit('term-paste', text);
    return;
  } else if (name === 'send') {
    emit('note-send', { text, label: note.title.trim() || t('메모') });
    return;
  } else if (name === 'from') {
    goToSource(note);
    return;
  }
  render();
  touched(tab, note);
}

// ---- 열고 닫기 -------------------------------------------------------------------

export async function openNotes() {
  panel().hidden = false;
  $('#lec-btn-notes').setAttribute('aria-pressed', 'true');
  render();
  const tab = S.tab;
  if (tab && !tab.readonly) {
    const st = stateOf(tab);
    if (!st.touched.size && !st.removed.size) await load(tab);   // 밖에서 고친 것을 보이게
  }
  if (notesOpen()) filter().focus();
}

export function closeNotes() {
  if (!notesOpen()) return false;
  panel().hidden = true;
  $('#lec-btn-notes').setAttribute('aria-pressed', 'false');
  hideUndo();
  if (S.tab) saveNow(S.tab);
  return true;
}

export function toggleNotes() {
  if (!closeNotes()) openNotes();
}

export function initNotes() {
  const box = list();
  const noteAt = (el) => noteOf(stateOf(S.tab), el.closest('.note-card')?.dataset.id);
  $('#lec-btn-notes').addEventListener('click', toggleNotes);
  $('#lec-notes-close').addEventListener('click', closeNotes);
  $('#lec-notes-new').addEventListener('click', () => {
    const note = newNote();
    if (note) focusCard(note.id, '.note-body');
  });
  $('#lec-notes-undo-btn').addEventListener('click', restoreNote);
  filter().addEventListener('input', render);
  box.addEventListener('input', (e) => {
    const note = noteAt(e.target);
    if (!note) return;
    if (e.target.matches('.note-title')) note.title = e.target.value;
    else if (e.target.matches('.note-body')) {
      note.body = e.target.value;
      grow(e.target);
    } else return;
    touched(S.tab, note);
  });
  box.addEventListener('change', (e) => {
    const note = noteAt(e.target);
    const i = Number(e.target.closest('li')?.dataset.i);
    if (!note || Number.isNaN(i)) return;
    if (e.target.matches('input[type="checkbox"]')) note.body = toggleTask(note.body, i);
    else if (e.target.matches('.note-task')) note.body = setTask(note.body, i, e.target.value);
    else return;
    render();
    touched(S.tab, note);
  });
  box.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' || !e.target.matches('.note-add') || !e.target.value.trim()) return;
    e.preventDefault();
    const note = noteAt(e.target);
    note.body = addTask(note.body, e.target.value.trim());
    render();
    touched(S.tab, note);
    focusCard(note.id, '.note-add');
  });
  box.addEventListener('click', (e) => {
    const button = e.target.closest('[data-act]');
    const note = button && noteAt(button);
    if (note) act(button.dataset.act, note, button);
  });
  box.addEventListener('focusout', () => { if (S.tab) saveNow(S.tab); });
  on('tab', (info) => {
    if (info?.prev) saveNow(info.prev);
    hideUndo();
    if (notesOpen()) openNotes();
  });
  on('new-note', async ({ title = '', body = '', path = '', line = 0, end = 0 }) => {
    const tab = S.tab;
    if (!tab) return;
    if (tab.readonly) {
      toast(t('보기만 하는 프로젝트라 메모를 쓰지 않습니다 — 고쳐 보려면 그 폴더를 복사해 여세요'));
      return;
    }
    const st = stateOf(tab);
    if (!st.loaded) await load(tab);
    if (!notesOpen()) await openNotes();
    const note = newNote({ title, body, path, line, end });
    if (note) focusCard(note.id, '.note-title');
    toast(t('새 메모로 보냈습니다'));
  });
}
