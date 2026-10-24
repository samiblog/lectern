// 담기·보내기 (D63·D65): 문서의 조각(장·절·블록·표·그림·차트·수식·코드·박스글, 고른 글)을 모아 두었다가 열린 문서나 새 문서로 보낸다.
//
// - 담는 곳: 본문 우클릭 '담기'(docmenu.js), 모아 보기 항목 우클릭 '담기'·'보이는 것 모두 담기'(parts.js). 담는 순간의 원문을 남긴다
//   (그 뒤에 원래 문서가 바뀌어도 담은 것은 그대로). 각주는 그 조각이 쓰는 정의를 함께 담는다.
// - 사이드바 '담기' 탭: 담은 것을 차례대로 — 위로·아래로·빼기, 누르면 원래 자리로, '문서로 보내기…', 'Claude 에 맡기기'(요청 글 복사·터미널).
//   편집 중인 md 문서가 있으면 항목의 '보내기'가 커서 자리로 보낸다. 프로젝트 탭마다 따로(경로를 그 프로젝트 기준으로 옮기므로),
//   앱을 끄면 비운다 (config.json 에 글을 쌓지 않는다).
// - 바로 보내기: 우클릭 '…보내기…' — 그 조각 하나를.
// - 보낼 곳 고르기 창(#lec-insert): 받는 곳은 편집 중인 곳(커서)·새 문서·문서 탭에 열린 문서뿐 (D65) → 자리(맨 끝·맨 앞·절 끝).
//   새 문서는 경로를 적으면 바로 만든다 (newdoc.js — '# 제목' 한 줄). 보내는 것은 editor.js 의 insertIntoDoc — 그 문서를 편집 모드로 열어
//   넣고, 저장은 사용자가 한다(Ctrl+S). 다듬는 것(경로·각주·제목 수준·담은 곳 주석)은 snippet.js.
// - 새로 만들기(askNewDoc — 문서 탭 줄의 +·Ctrl+N·폴더 우클릭)도 이 창의 '새 문서' 단계를 쓴다.

import { S, on } from './store.js';
import { getText } from './api.js';
import { showMenu } from './ui.js';
import { openTarget, openDocs } from './doctabs.js';
import { goToPart, PARTS } from './toc.js';
import { rangeText } from './docmenu.js';
import { insertIntoDoc, editingDoc } from './editor.js';
import { buildBody, headingsOf, levelAt, noteDefs, noteIds, placeLine, placeText } from './snippet.js';
import { newDocGuess, cleanPath, createDoc, openCreated } from './newdoc.js';
import { $, esc, toast, copyText, docUrl, isMd, basename, timeAgo, keepFocus } from './util.js';
import { t } from './i18n.js';

let seq = 0;

const clip = (s, n = 40) => { const text = String(s ?? '').replace(/\s+/g, ' ').trim(); return text.length > n ? `${text.slice(0, n - 1)}…` : text; };
const basketOf = (tab = S.tab) => (tab ? (tab.basket ||= []) : []);
const iconOf = (sn) => PARTS[sn.kind]?.icon || (sn.kind === 'section' ? 'i-toc' : 'i-text');

// ---- 조각 만들기 ----------------------------------------------------------------

/**
 * 원래 문서(doc — {path, lines})의 줄 범위(range [a, b], 1부터)를 조각으로: {id, path, lines, kind, name, label, text, notes}.
 * 들여 쓴 목록 항목 등은 공통 들여쓰기를 걷는다. plain: 원문이 아닌 글(고른 글 — 경로·제목을 건드리지 않는다)
 */
export function snippetOf(doc, range, { kind = 'block', name = '', label = '', text = null, plain = false } = {}) {
  let body = text;
  if (body == null) {
    const lines = doc.lines.slice(range[0] - 1, range[1]);
    const indent = Math.min(...lines.filter((l) => l.trim()).map((l) => /^[ \t]*/.exec(l)[0].length), 99);
    body = lines.map((l) => (indent && indent < 99 ? l.slice(Math.min(indent, /^[ \t]*/.exec(l)[0].length)) : l)).join('\n').replace(/\s+$/, '');
  }
  const notes = plain ? '' : noteDefs(doc.lines, noteIds(body), range);
  seq += 1;
  return { id: seq, path: doc.path, lines: range, kind, name, label, text: body, notes, plain };
}

/** 담는다 (선택된 탭에). 알림에 무엇을 담았는지와 모두 몇 개인지 (note: 덧붙일 말 — 담지 않은 것 등) */
export function addSnippets(list, note = '') {
  const items = list.filter(Boolean);
  if (!S.tab) return;
  if (!items.length) {
    if (note) toast(note);
    return;
  }
  basketOf().push(...items);
  render();
  const what = items.length === 1 ? items[0].label || items[0].name : t('{n}개', { n: items.length });
  const msg = t("담았습니다: {what} — 사이드바 '담기' 탭 ({n}개)", { what: clip(what, 30), n: basketOf().length });
  toast(note ? `${msg}. ${note}` : msg, '', note ? 4000 : undefined);
}

// ---- 사이드바 '담기' 탭 ----------------------------------------------------------

function row(sn, i, n, put) {
  const where = `${sn.path}${sn.lines ? ` · ${rangeText(sn.lines)}` : ''}`;
  const tip = [sn.label, `${sn.name}`, where].filter(Boolean).join('\n');
  return `<div class="pt-item bk-item has-cap" tabindex="0" data-id="${sn.id}" title="${esc(tip)}">`
    + `<svg class="tp-icon" aria-hidden="true"><use href="#${iconOf(sn)}"/></svg>`
    + `<span class="pt-text"><span class="pt-name">${esc(sn.label || sn.name)}</span>`
    + `<span class="pt-label">${esc([sn.label && sn.name, where].filter(Boolean).join(' · '))}</span></span>`
    + `<span class="bk-btns">${put ? `<button type="button" class="text-btn bk-put" title="${esc(t('편집 중인 문서의 커서 자리로 보내기'))}">${t('보내기')}</button>` : ''}`
    + `<button type="button" class="icon-btn small bk-up" title="${esc(t('위로 (Alt+↑)'))}"${i === 0 ? ' disabled' : ''}><svg><use href="#i-up"/></svg></button>`
    + `<button type="button" class="icon-btn small bk-down" title="${esc(t('아래로 (Alt+↓)'))}"${i === n - 1 ? ' disabled' : ''}><svg><use href="#i-down"/></svg></button>`
    + `<button type="button" class="icon-btn small bk-del" title="${esc(t('빼기 (Delete)'))}"><svg><use href="#i-close"/></svg></button></span></div>`;
}

/** 탭의 개수 표시와 (보이면) 목록 */
function render() {
  const items = basketOf();
  const count = $('#lec-basket-count');
  count.hidden = !items.length;
  count.textContent = String(items.length);
  if ($('#lec-basket').hidden) return;
  const editing = editingDoc();
  const list = $('#lec-basket-list');
  keepFocus(list, () => {
    list.innerHTML = items.map((sn, i) => row(sn, i, items.length, !!editing)).join('');
  });
  for (const id of ['#lec-basket-insert', '#lec-basket-claude', '#lec-basket-clear']) $(id).disabled = !items.length;
  let info;
  if (!S.tab) info = t('먼저 폴더를 여세요');
  else if (!items.length) info = t("담은 것이 없습니다. 문서의 절·표·그림·차트 등을 우클릭해 '담기'를 고르세요 — 모아서 열린 문서나 새 문서로 한 번에 보냅니다");
  else if (editing) info = t("편집 중: {path} — 항목의 '보내기'를 누르면 커서 자리로 보냅니다", { path: editing.path });
  else info = t("{n}개 — '문서로 보내기'로 차례대로 한 번에 보냅니다", { n: items.length });
  $('#lec-basket-info').textContent = info;
}

const byId = (id) => basketOf().find((sn) => sn.id === Number(id));

function move(sn, step) {
  const items = basketOf();
  const i = items.indexOf(sn);
  const j = i + step;
  if (i < 0 || j < 0 || j >= items.length) return;
  [items[i], items[j]] = [items[j], items[i]];
  render();
  $(`#lec-basket-list .bk-item[data-id="${sn.id}"]`)?.focus();
}

function remove(sn) {
  const items = basketOf();
  const i = items.indexOf(sn);
  if (i < 0) return;
  items.splice(i, 1);
  render();
  const next = items[Math.min(i, items.length - 1)];
  if (next) $(`#lec-basket-list .bk-item[data-id="${next.id}"]`)?.focus();
}

/** 원래 문서의 그 자리로 (그 줄이 든 가장 안쪽 블록). 그 문서가 다른 문서 탭에 열려 있으면 그 탭, 지금 칸에서 편집 중이거나
 * newTab(Ctrl+누르기)이면 새 문서 탭에서 (D64 — 넣는 문서의 편집을 떠나지 않게) */
async function goToSource(sn, newTab = false) {
  if (!(await openTarget({ type: 'doc', path: sn.path, newTab: newTab || !!S.pane?.editor }))) return;
  if (!sn.lines) return;
  let found = null;
  for (const el of S.pane.view.querySelectorAll('[data-lines]')) {
    const [a, b] = el.dataset.lines.split('-').map(Number);
    if (a > sn.lines[0]) break;
    if (sn.lines[0] <= (b || a)) found = el;
  }
  if (found) goToPart(found);
  else toast(t('원래 문서에서 그 자리를 찾지 못했습니다 — 그사이 문서가 바뀌었을 수 있습니다'));
}

// ---- 보내기 (D63·D65) -------------------------------------------------------------

/**
 * 조각들을 보낸다. target: {path, place: {at, head?, line?}}. 받는 문서의 글에 맞춰 자리·제목 수준·각주 이름을 정하고
 * editor.js 가 편집 모드로 연 그 문서에 넣는다. 저장은 사용자가
 */
async function perform(snips, target) {
  const ok = await insertIntoDoc(target.path, (text) => {
    const at = placeLine(text, target.place);
    const body = buildBody(snips, target.path, { top: levelAt(text, target.place, at), taken: noteIds(text) });
    return placeText(text.split('\n'), at, body);
  });
  if (!ok) return;
  const what = snips.length === 1 ? clip(snips[0].label || snips[0].name, 30) : t('{n}개', { n: snips.length });
  toast(t('{path} 로 {what} 을(를) 보냈습니다 — 확인하고 저장(Ctrl+S)하세요', { path: target.path, what }), '', 4000);
}

/** 편집 중인 문서의 커서 자리로 바로 보낸다 */
function putAtCursor(snips) {
  const ed = editingDoc();
  if (!ed) {
    toast(t('편집 중인 문서가 없습니다 — 받을 문서를 편집 모드(Ctrl+E)로 열거나 문서로 보내기를 쓰세요'));
    return;
  }
  perform(snips, { path: ed.path, place: { at: 'cursor', line: ed.line } });
}

// 보낼 곳 고르기 창: step 'target'(받는 문서) → 'place'(자리) / 'new'(새 문서 경로 — 새로 만들기도 이 단계로 연다)
const pick = { snips: [], step: 'target', items: [], sel: 0, doc: null, heads: [] };
const box = () => $('#lec-insert');
const input = () => $('#lec-insert-input');

/** 조각들을 보낼 곳을 고르는 창을 연다 */
export function sendSnippets(snips) {
  if (!snips.length || !S.tab) return;
  Object.assign(pick, { snips, step: 'target', doc: null });
  box().hidden = false;
  showStep();
}

/** 새로 만들기 (D65 — 문서 탭 줄의 +·Ctrl+N·폴더 우클릭): 경로를 묻고 바로 만들어 새 문서 탭에서 편집 모드로. dir: 처음 값의 폴더 (없으면 지금 문서의) */
export function askNewDoc(dir = null) {
  if (!S.tab) {
    toast(t('먼저 폴더를 여세요'));
    return;
  }
  Object.assign(pick, { snips: [], step: 'new', doc: null });
  box().hidden = false;
  showStep(newDocGuess(dir));
}

function closePick() {
  if (box().hidden) return false;
  box().hidden = true;
  pick.snips = [];
  return true;
}

function showStep(value = '') {
  const what = pick.snips.length === 1 ? clip(pick.snips[0].label || pick.snips[0].name, 36) : t('담은 것 {n}개', { n: pick.snips.length });
  const title = {
    target: t('{what} — 보낼 곳', { what }),
    place: t('{what} — {doc} 의 받을 자리', { what, doc: pick.doc?.title || pick.doc?.path || '' }),
    new: pick.snips.length ? t('{what} — 새 문서로', { what }) : t('새 문서 만들기'),
  }[pick.step];
  $('#lec-insert-title').textContent = title;
  input().placeholder = {
    target: t('문서 이름·제목·경로로 거르기'),
    place: t('절 제목으로 거르기'),
    new: t('새 문서의 경로 (프로젝트 기준, .md) — Enter'),
  }[pick.step];
  input().value = value;
  setMsg('');
  update();
  input().focus();
  if (pick.step === 'new') {   // 파일 이름 부분을 골라 두어 바로 고쳐 쓰게
    const slash = value.lastIndexOf('/') + 1;
    input().setSelectionRange(slash, value.toLowerCase().endsWith('.md') ? value.length - 3 : value.length);
  }
}

function setMsg(text, bad = false) {
  const p = $('#lec-insert-msg');
  p.hidden = !text;
  p.textContent = text;
  p.classList.toggle('bad', bad);
}

/** 받는 곳: 편집 중인 곳(커서)·새 문서·이 프로젝트의 문서 탭에 열린 md 문서 (D65 — 그 밖의 문서는 먼저 탭으로 연다) */
function targetItems(query) {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  const tab = S.tab;
  const docs = openDocs(tab).filter((path) => isMd(path)).map((path) => tab.fileMap.get(path) || { path, name: basename(path) })
    .filter((f) => terms.every((w) => `${(f.title || '').toLowerCase()} ${f.path.toLowerCase()}`.includes(w)));
  const out = [];
  if (!terms.length) {
    const ed = editingDoc();
    if (ed) out.push({ type: 'cursor', label: t('편집 중인 곳 — 커서 자리'), sub: ed.path });
    out.push({ type: 'new', label: t('새 문서…'), sub: t('경로를 정하면 바로 만들고 그 문서로 보냅니다') });
  }
  return out.concat(docs.map((f) => ({ type: 'doc', file: f, label: f.title || f.name, sub: f.path, when: f.mtime ? timeAgo(f.mtime) : '' })));
}

function placeItems(query) {
  const q = query.toLowerCase().trim();
  const out = q ? [] : [{ type: 'back', label: t('← 다른 곳 고르기') },
    { type: 'place', place: { at: 'end' }, label: t('맨 끝'), sub: t('끝의 각주 앞에') },
    { type: 'place', place: { at: 'start' }, label: t('맨 앞'), sub: t('문서 제목 아래에') }];
  for (const h of pick.heads) {
    if (q && !h.text.toLowerCase().includes(q)) continue;
    out.push({ type: 'place', place: { at: 'section', head: h }, label: t("'{name}' 절 끝", { name: h.text }), level: h.level, sub: t('{n}행 · 그 절 아래 수준으로', { n: h.i + 1 }) });
  }
  return out;
}

function update() {
  const query = input().value;
  if (pick.step === 'target') pick.items = targetItems(query);
  else if (pick.step === 'place') pick.items = placeItems(query);
  else pick.items = [{ type: 'create', label: t('Enter — 이 경로로 새 문서'), sub: t('바로 만듭니다 — 이미 있는 폴더에만, 같은 이름이 있으면 만들지 않습니다') }];
  pick.sel = 0;
  renderPick();
}

function renderPick() {
  const ul = $('#lec-insert-list');
  // 받는 곳은 열린 문서뿐이다 — 다른 문서로 보내는 길을 알린다 (고를 수 없는 줄)
  const note = pick.step === 'target' ? `<li class="note">${esc(t('다른 문서로 보내려면 먼저 그 문서를 문서 탭으로 여세요 — 트리에서 Ctrl+클릭'))}</li>` : '';
  if (!pick.items.length) {
    ul.innerHTML = `<li class="empty">${esc(pick.step === 'place' ? t('맞는 절이 없습니다') : t('맞는 문서가 없습니다'))}</li>${note}`;
    return;
  }
  ul.innerHTML = pick.items.map((it, i) => `<li role="option" data-i="${i}" class="${i === pick.sel ? 'sel' : ''} ins-${it.type}" aria-selected="${i === pick.sel}"`
    + `${it.level ? ` style="padding-left:${10 + (it.level - 1) * 14}px"` : ''}>`
    + `<span class="t">${esc(it.label)}</span><span class="when">${esc(it.when || '')}</span>${it.sub ? `<span class="p">${esc(it.sub)}</span>` : ''}</li>`).join('') + note;
  ul.querySelector('.sel')?.scrollIntoView({ block: 'nearest' });
}

/** 받는 문서의 글 — 편집 중이면 편집기의 글(저장하지 않은 것까지) */
async function textOf(path) {
  const ed = S.tab.panes.find((p) => p.editor?.path === path)?.editor;
  if (ed) return ed.cm.getValue();
  return getText(docUrl(S.tab, path));
}

async function choose(i) {
  const it = pick.items[i];
  if (!it) return;
  const snips = pick.snips;
  if (it.type === 'cursor') {
    closePick();
    putAtCursor(snips);
  } else if (it.type === 'new') {
    pick.step = 'new';
    showStep(newDocGuess());
  } else if (it.type === 'doc') {
    pick.doc = { path: it.file.path, title: it.file.title || it.file.name };
    try {
      pick.heads = headingsOf(await textOf(it.file.path));
    } catch {
      setMsg(t('문서를 읽지 못했습니다 — 그사이 지워졌을 수 있습니다'), true);
      return;
    }
    pick.step = 'place';
    showStep();
  } else if (it.type === 'back') {
    pick.step = 'target';
    showStep();
  } else if (it.type === 'place') {
    closePick();
    perform(snips, { path: pick.doc.path, place: it.place });
  } else if (it.type === 'create') {
    const path = cleanPath(input().value);
    if (!path) return;
    let made;
    try {
      made = await createDoc(path);
    } catch (e) {   // 없는 폴더·같은 이름·쓸 수 없는 이름 — 고쳐서 다시 Enter
      if (!box().hidden && pick.step === 'new') setMsg(e.message, true);
      return;
    }
    closePick();
    if (snips.length) {   // 새 문서로 보내기 — 제목 아래에 (## 로)
      perform(snips, { path: made, place: { at: 'end' } });
    } else {
      toast(t('새 문서를 만들었습니다: {path}', { path: made }));
      openCreated(made);
    }
  }
}

// ---- Claude 에 맡기기 ------------------------------------------------------------

/** 담은 것들을 Claude Code 가 모아 새 문서로 만들게 하는 요청 글 (한 줄 — 여러 줄이면 터미널이 묻는다) */
function claudeRequest(snips) {
  const refs = snips.map((sn) => `@${sn.path}${sn.lines ? ` ${rangeText(sn.lines)}` : ''}${sn.label || sn.name ? ` ('${clip(sn.label || sn.name, 30).replace(/'/g, '’')}')` : ''}`).join(', ');
  const ask = t('다음 조각을 이 차례로 모아 새 Markdown 문서를 만들어 주세요. 파일 이름과 폴더는 내용에 맞게 정하고, 그림·링크·데이터의 상대경로는 새 문서 기준으로 고치고, 조각마다 담은 곳을 <!-- 담은 곳: 경로 줄 --> 주석으로 남겨 주세요: {refs}', { refs });
  return S.writingGuide ? `${ask} ${t('문서는 Lectern 작성 안내({path})를 따라 주세요.', { path: S.writingGuide })}` : ask;
}

function claudeMenu(btn) {
  const snips = basketOf();
  if (!snips.length) return;
  const text = claudeRequest(snips);
  const r = btn.getBoundingClientRect();
  showMenu(r.left, r.bottom + 4, [{ header: t('Claude Code 에 맡기기 — 담은 것 {n}개로 새 문서', { n: snips.length }) },
    { label: t('요청 글 복사'), hint: t('Claude Code 에 붙여 넣습니다'), action: async () => toast(await copyText(text) ? t('복사했습니다: {what}', { what: t('요청 글') }) : t('복사하지 못했습니다')), term: text }]);
}

// ---- 시작 -----------------------------------------------------------------------

function rowMenu(el, x, y) {
  const sn = byId(el.dataset.id);
  if (!sn) return;
  const items = basketOf();
  const i = items.indexOf(sn);
  const menu = [{ header: `${sn.label || sn.name} · ${sn.path}` },
    { label: t('문서에서 보기'), hint: t('누르기·Enter'), action: () => goToSource(sn) }];
  if (editingDoc()) menu.push({ label: t('커서 자리로 보내기'), hint: editingDoc().path, action: () => putAtCursor([sn]) });
  menu.push({ label: t('문서로 보내기…'), hint: t('열린 문서 탭이나 새 문서로'), action: () => sendSnippets([sn]) },
    { label: t('원문 복사'), hint: sn.lines ? `${sn.path} ${rangeText(sn.lines)}` : '', action: async () => toast(await copyText(sn.text) ? t('복사했습니다: {what}', { what: clip(sn.label || sn.name, 30) }) : t('복사하지 못했습니다')), term: sn.text },
    '-');
  if (i > 0) menu.push({ label: t('위로'), hint: 'Alt+↑', action: () => move(sn, -1) });
  if (i < items.length - 1) menu.push({ label: t('아래로'), hint: 'Alt+↓', action: () => move(sn, 1) });
  menu.push({ label: t('빼기'), hint: 'Delete', action: () => remove(sn) });
  el.classList.add('lec-picked');
  showMenu(x, y, menu, () => el.classList.remove('lec-picked'));
}

export function initBasket() {
  const list = $('#lec-basket-list');
  list.addEventListener('click', (e) => {
    const el = e.target.closest('.bk-item');
    const sn = el && byId(el.dataset.id);
    if (!sn) return;
    if (e.target.closest('.bk-put')) putAtCursor([sn]);
    else if (e.target.closest('.bk-up')) move(sn, -1);
    else if (e.target.closest('.bk-down')) move(sn, 1);
    else if (e.target.closest('.bk-del')) remove(sn);
    else goToSource(sn, e.ctrlKey || e.metaKey);
  });
  list.addEventListener('keydown', (e) => {
    const el = e.target.closest?.('.bk-item');
    const sn = el && e.target === el && byId(el.dataset.id);
    if (!sn) return;
    if (e.key === 'Enter') goToSource(sn);
    else if (e.key === 'Delete') remove(sn);
    else if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) move(sn, e.key === 'ArrowUp' ? -1 : 1);
    else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') (e.key === 'ArrowUp' ? el.previousElementSibling : el.nextElementSibling)?.focus();
    else return;
    e.preventDefault();
  });
  list.addEventListener('contextmenu', (e) => {
    const el = e.target.closest('.bk-item');
    if (!el) return;
    e.preventDefault();
    rowMenu(el, e.clientX, e.clientY);
  });
  $('#lec-basket-insert').addEventListener('click', () => sendSnippets([...basketOf()]));
  $('#lec-basket-claude').addEventListener('click', (e) => claudeMenu(e.currentTarget));
  $('#lec-basket-clear').addEventListener('click', () => {
    const n = basketOf().length;
    if (!n || !window.confirm(t('담은 것 {n}개를 모두 뺄까요? (문서는 그대로입니다)', { n }))) return;
    basketOf().splice(0);
    render();
  });
  // 보낼 곳 고르기 창
  input().addEventListener('input', () => {
    setMsg('');
    if (pick.step !== 'new') update();
  });
  input().addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!pick.items.length) return;
      pick.sel = (pick.sel + (e.key === 'ArrowDown' ? 1 : -1) + pick.items.length) % pick.items.length;
      renderPick();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose(pick.sel);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      if (pick.step === 'target' || !pick.snips.length) closePick();   // 새로 만들기는 바로 닫는다
      else {   // 자리·새 문서에서는 보낼 곳 고르기로 돌아간다
        pick.step = 'target';
        showStep();
      }
    }
  });
  $('#lec-insert-list').addEventListener('click', (e) => {
    const li = e.target.closest('li[data-i]');
    if (li) choose(+li.dataset.i);
  });
  box().addEventListener('mousedown', (e) => { if (e.target === box()) closePick(); });
  on('panel', (name) => { if (name === 'basket') render(); });
  on('tab', () => {
    closePick();   // 보낼 곳·새 문서 경로는 앞 탭의 것 (Ctrl+Tab 은 이 창에서도 탭을 바꾼다)
    render();
  });
  on('editor', render);   // 편집을 열고 닫으면 항목의 '보내기'
  on('new-doc', ({ dir }) => askNewDoc(dir));   // 폴더 우클릭 '이 폴더에 새 문서…' (tree·others)
  render();
}

/** 보낼 곳 고르기 창이 열려 있으면 닫는다 (main.js 의 Esc) */
export const closeInsert = closePick;
