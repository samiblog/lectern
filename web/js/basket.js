// 담기·보내기 (D63·D65): 문서의 조각(장·절·블록·표·그림·차트·수식·코드·강조글, 고른 글)을 모아 두었다가 열린 문서나 새 문서로 보낸다.
//
// - 담는 곳: 본문 우클릭 '담기'(docmenu.js)와 Alt+C, 모아 보기 항목 우클릭 '담기'·'보이는 것 모두 담기'(parts.js). 담는 순간의 원문을 남긴다
//   (그 뒤에 원래 문서가 바뀌어도 담은 것은 그대로). 각주는 그 조각이 쓰는 정의를 함께 담는다. '지금 담기함'에 들어가고, 다른 담기함은 메뉴에서 고른다.
// - 담기함 (D197): 프로젝트마다 여럿, .lectern/clips/ 의 파일로 남는다 (clipstore.js·clipdata.js). 하나도 없이 담으면 '담기함' 하나가 생긴다.
// - 사이드바 '담기' 탭: 담기함의 목록 — 문서 목록처럼 (D198). 누르면 문서 탭에 펼치고(clipview.js), ● 는 지금 담기함, 화살표로 조각을 한 줄씩 펼친다(처음은 접힘).
//   조각을 누르면 펼친 화면의 그 카드로. 편집 중인 md 문서가 있으면 조각 줄의 '보내기'가 커서 자리로. 나머지(문서로 보내기·맡기기·비우기·지우기)는 우클릭과 펼친 화면에서.
// - 바로 보내기: 우클릭 '…보내기…' — 그 조각 하나를.
// - 보낼 곳 고르기 창(#lec-insert): 받는 곳은 편집 중인 곳(커서)·새 문서·문서 탭에 열린 문서뿐 (D65) → 자리(맨 끝·맨 앞·절 끝).
//   새 문서는 경로를 적으면 바로 만든다 (newdoc.js — '# 제목' 한 줄). 보내는 것은 editor.js 의 insertIntoDoc — 그 문서를 편집 모드로 열어
//   넣고, 저장은 사용자가 한다(Ctrl+S). 다듬는 것(경로·각주·제목 수준·담은 곳 주석)은 snippet.js.

import { S, on, emit } from './store.js';
import { getText, saveConfig } from './api.js';
import { showMenu, menuGroups } from './ui.js';
import { openTarget, openDocs, docPaneOf, selectDocTab, openInNewTab } from './doctabs.js';
import { goToPart, PARTS } from './toc.js';
import { insertIntoDoc, editingDoc } from './editor.js';
import { insertLines } from './lineedit.js';
import { buildBody, headingsOf, levelAt, noteDefs, noteIds, placeLine, placeText } from './snippet.js';
import {
  clipsOf, boxOf, curBox, boxName, loadClips, setCur, newBox, ensureBox, addClips, removeClips, undoRemove, moveClip, toBox, deleteBox, flushClips, checkBox, stateOf,
} from './clipstore.js';
import { pickBox } from './boxpick.js';
import { newDocGuess, cleanPath, createDoc } from './newdoc.js';
import { html, setHtml } from './html.js';
import { $, $$, toast, copyText, docUrl, isMd, isHtml, basename, dirname, timeAgo, keepFocus, blockedReadOnly, rangeText, natCompare, openHow, repeatClick, middleClickOpens } from './util.js';
import { t } from './i18n.js';
import { aiCli, aiName } from './aitool.js';
import { sendRowKey } from './tree.js';

let seq = 0;

const clip = (s, n = 40) => { const text = String(s ?? '').replace(/\s+/g, ' ').trim(); return text.length > n ? `${text.slice(0, n - 1)}…` : text; };
const itemsOf = () => curBox(S.tab)?.items || [];
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

/** 담는다 (선택된 탭의 지금 담기함에 — box 를 주면 거기에). 알림에 무엇을 담았는지와 담기함·개수 (note: 덧붙일 말 — 담지 않은 것 등) */
export async function addSnippets(list, note = '', box = null) {
  const tab = S.tab;
  const items = list.filter(Boolean);
  if (!tab) return;
  if (!items.length) {
    if (note) toast(note);
    return;
  }
  const into = box || await ensureBox(tab);
  if (!into) return;
  addClips(tab, into, items);
  const what = items.length === 1 ? items[0].label || items[0].name : t('{n}개', { n: items.length });
  const msg = t("담았습니다: {what} — '{box}' ({n}개)", { what: clip(what, 30), box: clip(boxName(into), 24), n: into.items.length });
  toast(note ? `${msg}. ${note}` : msg, '', note ? 4000 : undefined);
}

/**
 * '다른 담기함에 담기…' — 담기함들과 '새 담기함…' 의 메뉴를 (x, y)에. 고른 담기함이 지금 담기함이 되지는 않는다 (하나만 다른 곳에 넣는 일이 잦다).
 * 새 담기함은 사이드바에서 이름을 받아 만들고 담는다. make: 조각들을 주는 함수
 */
export async function boxMenu(x, y, pick_, { except = null, header = t('담을 곳') } = {}) {
  const tab = S.tab;
  if (!tab) return;
  await loadClips(tab);
  if (tab === S.tab) pickBox(tab, { x, y, header, except, pick: pick_ });
}

/** 우클릭 메뉴의 '담기' 에 — 담기함이 여럿이면 어디에 담기는지 이름을 붙인다 (하나뿐이면 그대로) */
export function clipLabel(label) {
  const st = S.tab ? clipsOf(S.tab) : null;
  const cur = st && st.boxes.length > 1 ? curBox(S.tab) : null;
  return cur ? t("{label} — '{box}'", { label, box: clip(boxName(cur), 16) }) : label;
}

// ---- 사이드바 '담기' 탭 ----------------------------------------------------------

let asking = false;   // 새 담기함의 이름을 묻는 중

/** 사이드바에서 새 담기함의 이름을 묻는다 (이름을 적고 Enter — 그때 만든다) */
function askBox() {
  if (!S.tab) return;
  asking = true;
  render();
  const el = /** @type {HTMLInputElement} */ ($('#lec-basket-name'));
  el.value = '';
  el.focus();
}

function stopAsking() {
  asking = false;
  render();
}

/** 조각 한 줄 — 이름, 메모가 있으면 ✎, 원래 문서가 바뀌었거나 없으면 ⚠. 자세한 것은 마우스를 올리면 */
function row(box, sn, put) {
  const { state } = stateOf(S.tab, sn);
  const main = sn.title || sn.label || sn.name || clip(sn.text, 40);
  const tip = [main, sn.title && sn.label, sn.name !== main && sn.name, sn.path && `${sn.path}${sn.lines ? ` · ${rangeText(sn.lines)}` : ''}`, sn.at && t('{date} 담음', { date: sn.at }),
    state && (state === 'gone' ? t('원래 문서가 없습니다') : t('원래 문서가 바뀌었습니다')), sn.memo && `✎ ${sn.memo}`].filter(Boolean).join('\n');
  return html`<div class="row bk-item" tabindex="-1" data-file="${box.file}" data-id="${sn.id}" style="--d:1" title="${tip}"><span class="caret-space"></span><svg class="ficon" aria-hidden="true"><use href="#${iconOf(sn)}"/></svg><span class="label">${main}</span>${sn.memo ? html`<span class="bk-mark" aria-label="${t('메모')}">✎</span>` : ''}${state ? html`<span class="bk-mark warn">⚠</span>` : ''}${put ? html`<button type="button" class="text-btn bk-put" tabindex="-1" title="${t('편집 중인 문서의 커서 자리로 보내기')}">${t('보내기')}</button>` : ''}</div>`;
}

/** 담기함 한 줄 — 문서 행처럼. 화살표는 조각을 펼치고, ● 는 지금 담기함(다른 것은 마우스를 올리면 ○) */
function boxRow(box, cur, open) {
  const active = S.view?.type === 'clips' && S.view.path === box.file;
  const here = cur ? t('지금 담기함 — 담는 것이 여기에 들어갑니다 (Alt+C)') : t('여기에 담기 — 누르면 지금 담기함으로');
  return html`<div class="row bk-box${cur ? ' cur' : ''}${active ? ' active' : ''}${box.error ? ' bad' : ''}" tabindex="-1" data-file="${box.file}" aria-expanded="${open}" title="${[boxName(box), box.note, box.error].filter(Boolean).join('\n')}"><span class="caret${open ? ' open' : ''}${box.items.length ? '' : ' none'}" data-toggle aria-hidden="true"></span><svg class="ficon" aria-hidden="true"><use href="#i-clip"/></svg><span class="label">${boxName(box)}</span>${box.error ? html`<span class="pt-bad">${t('읽지 못함')}</span>` : html`<button type="button" class="bk-here" tabindex="-1" title="${here}" aria-label="${here}" aria-pressed="${cur}"></button><span class="n">${box.items.length}</span>`}</div>`;
}

const clipWords = (sn) => [sn.title, sn.label, sn.name, sn.memo, sn.path].join(' ').toLowerCase();

/** 목록에 보일 담기함들 [{box, open(펼쳤는지), items(보일 조각)}] — 차례(이름·최근)와 거르기. 거르는 동안 조각이 맞으면 그 조각만 펼쳐 보인다 */
function shownBoxes(st) {
  const words = $('#lec-basket-filter').value.toLowerCase().split(/\s+/).filter(Boolean);
  const has = (hay) => words.every((w) => hay.includes(w));
  const boxes = [...st.boxes].sort((a, b) => (S.config.clip_sort === 'time' ? b.mtime - a.mtime : 0) || natCompare(boxName(a), boxName(b)));
  if (!words.length) return boxes.map((box) => ({ box, open: st.open.has(box.file) && box.items.length > 0, items: box.items }));
  return boxes.map((box) => {
    const named = has(`${boxName(box)} ${box.note}`.toLowerCase());
    const items = box.items.filter((sn) => has(clipWords(sn)));
    return { box, open: items.length > 0, items, hit: named || items.length > 0 };
  }).filter((x) => x.hit);
}

/** Tab 으로 들어올 행 하나 — 초점이 있던 것, 보고 있는 담기함, 지금 담기함, 첫 줄 */
function rove(row_ = null) {
  const list = $('#lec-basket-list');
  for (const r of $$('.row[tabindex="0"]', list)) r.tabIndex = -1;
  const pick_ = row_ || list.querySelector('.row:focus') || list.querySelector('.bk-box.active') || list.querySelector('.bk-box.cur') || list.querySelector('.row');
  if (pick_) pick_.tabIndex = 0;
}

/** 탭의 개수 표시와 (보이면) 목록 */
function render() {
  const tab = S.tab;
  const items = itemsOf();
  const count = $('#lec-basket-count');
  count.hidden = !items.length;
  count.textContent = String(items.length);
  if ($('#lec-basket').hidden) return;
  const editing = editingDoc();
  const list = $('#lec-basket-list');
  const st = tab ? clipsOf(tab) : null;
  const shown = st ? shownBoxes(st) : [];
  keepFocus(list, () => {
    setHtml(list, shown.map(({ box, open, items: mine }) => [boxRow(box, box.file === st.cur, open), open && !box.error ? mine.map((sn) => row(box, sn, !!editing)) : '']));
  });
  rove();
  for (const { box, open } of shown) if (open) checkBox(tab, box);   // 보이는 조각만 원래 문서와 대조 (바뀐 것이 없으면 묻지 않는다)
  $('#lec-basket-ask').hidden = !asking;
  $('#lec-basket-new').disabled = !tab;
  const sort = $('#lec-basket-sort');
  sort.textContent = S.config.clip_sort === 'time' ? t('최근 순') : t('이름순');
  sort.title = S.config.clip_sort === 'time' ? t('누르면 이름순으로') : t('누르면 마지막에 고친 담기함부터');
  const undo = st?.undo && boxOf(tab, st.undo.file);
  $('#lec-basket-undo').hidden = !undo;
  if (undo) $('#lec-basket-undo span').textContent = t('{n}개를 뺐습니다', { n: st.undo.entries.length });
  let info = '';
  if (!tab) info = t('먼저 폴더를 여세요');
  else if (st.error) info = t('담기함을 읽지 못했습니다: {error}', { error: st.error });
  else if (!st.boxes.length) info = t("담은 것이 없습니다. 문서의 절·표·그림·차트 등을 우클릭해 '담기'를 고르거나 Alt+C 를 누르세요");
  else if (!shown.length) info = t('맞는 담기함이 없습니다');
  else if (st.memory) info = t('보기만 하는 프로젝트라 담은 것을 저장하지 않습니다 — 앱을 끄면 비워집니다');
  else if (editing) info = t("편집 중: {path} — 담기함을 펼쳐 조각의 '보내기'를 누르면 커서 자리로", { path: editing.path });
  $('#lec-basket-info').textContent = info;
  $('#lec-basket-info').hidden = !info;
}

function setOpen(box, open) {
  const st = clipsOf(S.tab);
  if (open) st.open.add(box.file);
  else st.open.delete(box.file);
  render();
}

/** 목록의 행이 가리키는 담기함과 조각 (담기함 행이면 조각은 null) */
function rowOf(el) {
  const line = el?.closest?.('#lec-basket-list .row');
  const box = line && boxOf(S.tab, line.dataset.file);
  if (!box) return null;
  const sn = line.dataset.id ? box.items.find((c) => c.id === line.dataset.id) : null;
  return line.dataset.id && !sn ? null : { line, box, sn };
}

const focusRow = (sel) => {
  const el = /** @type {HTMLElement | null} */ ($(`#lec-basket-list ${sel}`));
  if (!el) return;
  rove(el);
  el.focus({ preventScroll: true });
  el.scrollIntoView({ block: 'nearest' });
};
const focusItem = (sn) => focusRow(`.bk-item[data-id="${CSS.escape(sn.id)}"]`);

function remove(box, sn) {
  const i = box.items.indexOf(sn);
  removeClips(S.tab, box, new Set([sn.id]));
  const next = box.items[Math.min(i, box.items.length - 1)];
  if (next) focusItem(next);
  else focusRow(`.bk-box[data-file="${CSS.escape(box.file)}"]`);
}

/** 담기함을 문서 탭에 펼친다 (clipview.js). how: 열 곳 (util.openHow — 문서 목록과 같다) */
export const openBox = (box, how = {}) => emit('open', { type: 'clips', path: box.file, ...how });

/** 펼친 담기함의 그 조각으로 (title: 제목 칸에 초점 — 조각이 없으면 담기함의 제목) */
async function openClip(box, sn = null, title = false) {
  await openTarget({ type: 'clips', path: box.file });   // 열기가 초점을 본문에 두고 나서
  emit('clips-goto', { file: box.file, id: sn?.id || '', title });
}

/** 담기함을 휴지통으로 — 담은 것이 있으면 묻는다 */
async function dropBox(box) {
  if (!window.confirm(t("담기함 '{box}' 를 지울까요? 담은 것 {n}개와 메모가 함께 휴지통으로 갑니다 (문서는 그대로입니다)", { box: boxName(box), n: box.items.length }))) return;
  if (await deleteBox(S.tab, box)) toast(t('휴지통으로 보냈습니다: {what}', { what: boxName(box) }));
}

/** 담기함의 메뉴 — 사이드바의 우클릭과 펼친 화면의 '더 보기'. (x, y): 이어지는 메뉴의 자리 */
export function boxActions(box, x = 0, y = 0) {
  const tab = S.tab;
  /** @type {MenuItem[]} */
  const acts = [{ label: t('펼쳐 보기'), hint: 'Enter', action: () => openBox(box) }];
  if (box.file !== clipsOf(tab).cur) acts.push({ label: t('여기에 담기'), tip: t('지금 담기함으로 — 담는 것이 여기에 들어갑니다 (Alt+C)'), action: () => setCur(tab, box.file) });
  acts.push({ label: t('제목과 설명 고치기'), hint: 'F2', action: () => openClip(box, null, true) });
  /** @type {MenuItem[]} */
  const sends = box.items.length ? [{ label: t('{ai} 에 맡기기', { ai: aiName() }), tip: t('담은 것의 위치로 새 문서를 만들어 달라는 요청 글 — 복사·터미널'), action: () => claudeMenu(x, y, box) },
    { label: t('문서로 보내기…'), tip: t('담은 것을 차례대로 열린 문서 탭이나 새 문서로 — 제목과 메모도 함께'), action: () => sendBox(box) }] : [];
  /** @type {MenuItem[]} */
  const copies = clipsOf(tab).memory ? [] : [{ label: t('@{path} 복사', { path: `.lectern/clips/${box.file}` }), tip: t('{cli} 프롬프트에 붙여 넣기', { cli: aiCli() }),
    action: async () => toast(await copyText(`@.lectern/clips/${box.file}`) ? t('복사했습니다: {what}', { what: `@.lectern/clips/${box.file}` }) : t('복사하지 못했습니다')), term: `@.lectern/clips/${box.file} ` }];
  /** @type {MenuItem[]} */
  const danger = [];
  if (box.items.length) danger.push({ label: t('비우기'), tip: t('담은 것을 모두 뺍니다 — 되돌릴 수 있습니다 (문서는 그대로)'), action: () => removeClips(tab, box, new Set(box.items.map((c) => c.id))) });
  danger.push({ label: t('담기함 지우기…'), tip: t('휴지통으로 보냅니다'), action: () => dropBox(box) });
  return menuGroups([{ header: boxName(box) }], box.error ? [] : acts, box.error ? [] : sends, copies, box.error ? [] : danger);
}

/** 원래 문서의 그 자리로 (그 줄이 든 가장 안쪽 블록). 그 문서가 다른 문서 탭에 열려 있으면 그 탭, 지금 칸에서 편집 중이거나
 * newTab(Ctrl+누르기)이면 새 문서 탭에서 (D64 — 넣는 문서의 편집을 떠나지 않게) */
export async function goToSource(sn, newTab = false, how = {}) {
  if (!sn.path) {
    toast(t('담은 곳이 적혀 있지 않은 조각입니다'));
    return;
  }
  const kind = isMd(sn.path) || isHtml(sn.path) ? 'doc' : 'code';
  if (!(await openTarget({ type: kind, path: sn.path, newTab: newTab || !!S.pane?.editor, deckLine: sn.lines?.[0], ...how })) || how.behind) return;
  if (!sn.lines || kind !== 'doc') return;
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
  const compute = (text) => {
    const at = placeLine(text, target.place);
    const body = buildBody(snips, target.path, { top: levelAt(text, target.place, at), taken: noteIds(text) });
    return placeText(text.split('\n'), at, body);
  };
  // 그 문서를 편집 모드로 고치고 있으면 편집기에 (저장은 사용자가), 아니면 바로 넣는다 — 되돌리기 한 걸음 (D113)
  const editing = S.tab?.panes.some((p) => p.editor?.path === target.path);
  const ok = editing ? await insertIntoDoc(target.path, compute) : await sendInto(target.path, compute);
  if (!ok) return;
  const what = snips.length === 1 ? clip(snips[0].label || snips[0].name, 30) : t('{n}개', { n: snips.length });
  toast(editing ? t('{path} 로 {what} 을(를) 보냈습니다 — 확인하고 저장(Ctrl+S)하세요', { path: target.path, what })
    : t('{path} 로 {what} 을(를) 보냈습니다 — Ctrl+Z 로 되돌립니다', { path: target.path, what }), '', 4000);
}

/** 받을 문서를 문서 탭에 열고 글을 넣는다 */
async function sendInto(path, compute) {
  const target = { type: 'doc', path };
  const open = docPaneOf(S.tab, target);
  if (open) await selectDocTab(open);
  const pane = open ?? await openInNewTab(target);
  return pane ? insertLines(pane, path, compute) : false;
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
const pick = { snips: [], step: 'target', items: [], sel: 0, doc: null, heads: [], name: '' };
const box = () => $('#lec-insert');
const input = () => $('#lec-insert-input');

/** 조각들을 보낼 곳을 고르는 창을 연다. fresh: 새 문서의 경로를 묻는 단계부터 (모아 보기의 '새 문서로' — D196). name: 새 문서의 이름 (담기함의 제목 — D197) */
export function sendSnippets(snips, { fresh = false, name = '' } = {}) {
  if (!snips.length || !S.tab || blockedReadOnly(S.tab)) return;   // 받는 곳이 모두 이 프로젝트 안 (D71)
  Object.assign(pick, { snips, step: fresh ? 'new' : 'target', doc: null, name });
  box().hidden = false;
  showStep(fresh ? newGuess() : '');
}

/** 새 문서의 처음 경로 — 담기함을 보내면 그 제목으로 (같은 이름이 있으면 '새 문서') */
function newGuess() {
  const guess = newDocGuess();
  const name = pick.name.replace(/[<>:"/\\|?*\u0000-\u001f]/g, ' ').replace(/\s+/g, ' ').trim().replace(/[. ]+$/, '').slice(0, 60);
  const path = name ? `${dirname(guess) ? `${dirname(guess)}/` : ''}${name}.md` : guess;
  return S.fileMap.has(path) ? guess : path;
}

/** 담기함을 통째로 보낸다 — 담은 차례대로, 단 제목과 메모도 */
export const sendBox = (b) => sendSnippets([...b.items], { name: b.title });

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
  /** @type {any[]} */
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
  /** @type {any[]} */
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
  // 새로 만들기는 보통 문서가 Enter. 자리는 '맨 끝'이 Enter — 맨 위의 '다른 곳 고르기'로 돌아가지 않게
  pick.sel = pick.step === 'new' ? pick.items.length - 1 : pick.step === 'place' && pick.items[0]?.type === 'back' ? 1 : 0;
  renderPick();
}

function renderPick() {
  const ul = $('#lec-insert-list');
  // 받는 곳은 열린 문서뿐이다 — 다른 문서로 보내는 길을 알린다 (고를 수 없는 줄)
  const note = pick.step === 'target' ? html`<li class="note">${t('다른 문서로 보내려면 먼저 그 문서를 문서 탭으로 여세요 — 트리에서 Ctrl+클릭')}</li>` : '';
  if (!pick.items.length) {
    setHtml(ul, html`<li class="empty">${pick.step === 'place' ? t('맞는 절이 없습니다') : t('맞는 문서가 없습니다')}</li>${note}`);
    return;
  }
  setHtml(ul, [pick.items.map((it, i) => [html`<li role="option" data-i="${i}" class="${i === pick.sel ? 'sel' : ''} ins-${it.type}" aria-selected="${i === pick.sel}"`, html`${it.level ? html` style="padding-left:${10 + (it.level - 1) * 14}px"` : ''}>`, html`<span class="t">${it.label}</span><span class="when">${it.when || ''}</span>${it.sub ? html`<span class="p">${it.sub}</span>` : ''}</li>`]), note]);
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
    showStep(newGuess());
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
    perform(snips, { path: made, place: { at: 'end' } });   // 새 문서로 보내기 — 제목 아래에 (## 로)
  }
}

// ---- Claude 에 맡기기 ------------------------------------------------------------

/** 담은 것들을 Claude Code 가 모아 새 문서로 만들게 하는 요청 글 (한 줄 — 여러 줄이면 터미널이 묻는다) */
export function claudeRequest(snips, b = null) {
  const refs = snips.map((sn) => `@${sn.path}${sn.lines ? ` ${rangeText(sn.lines)}` : ''}${sn.title || sn.label || sn.name ? ` ('${clip(sn.title || sn.label || sn.name, 30).replace(/'/g, '’')}')` : ''}`).join(', ');
  const ask = t('다음 조각을 이 차례로 모아 새 Markdown 문서를 만들어 주세요. 파일 이름과 폴더는 내용에 맞게 정하고, 그림·링크·데이터의 상대경로는 새 문서 기준으로 고치고, 조각마다 담은 곳을 <!-- 담은 곳: 경로 줄 --> 주석으로 남겨 주세요: {refs}', { refs });
  const words = b && !clipsOf(S.tab).memory && (b.note || snips.some((sn) => sn.title || sn.memo)) ? ` ${t('담기함의 설명과 조각마다 단 제목·메모는 @.lectern/clips/{file} 에 있습니다.', { file: b.file })}` : '';
  return `${ask}${words}${S.writingGuide ? ` ${t('문서는 Lectern 작성 안내({path})를 따라 주세요.', { path: S.writingGuide })}` : ''}`;
}

export async function claudeMenu(x, y, b) {
  const snips = b?.items || [];
  if (!snips.length) return;
  await flushClips();   // 요청 글이 담기함 파일을 가리킨다 — 쓰던 메모까지 저장하고
  const known = snips.filter((sn) => sn.path);
  const text = claudeRequest(known.length ? known : [/** @type {any} */ ({ path: `.lectern/clips/${b.file}` })], b);
  showMenu(x, y, [{ header: t('{cli} 에 맡기기 — 담은 것 {n}개로 새 문서', { cli: aiCli(), n: snips.length }) },
    { label: t('요청 글 복사'), hint: t('{cli} 에 붙여 넣습니다', { cli: aiCli() }), action: async () => toast(await copyText(text) ? t('복사했습니다: {what}', { what: t('요청 글') }) : t('복사하지 못했습니다')), term: text }]);
}

// ---- 시작 -----------------------------------------------------------------------

/** 조각의 우클릭 메뉴 — 사이드바와 펼쳐 보기(clipview.js)가 함께 쓴다 */
export function clipMenu(b, sn, el, x, y, open = null) {
  const tab = S.tab;
  const items = b.items;
  const i = items.indexOf(sn);
  if (i < 0) return;
  /** @type {MenuItem[]} */
  const sends = [];
  if (editingDoc()) sends.push({ label: t('커서 자리로 보내기'), tip: editingDoc().path, action: () => putAtCursor([sn]) });
  sends.push({ label: t('문서로 보내기…'), tip: t('열린 문서 탭이나 새 문서로'), action: () => sendSnippets([sn]) },
    { label: t('새 메모로 보내기'), tip: t('이 프로젝트의 메모에 — 어디서 왔는지도 함께'), action: () => emit('new-note', { body: sn.text, path: sn.path, line: sn.lines?.[0] || 0, end: sn.lines?.[1] || 0 }) });
  /** @type {MenuItem[]} */
  const moves = [];
  if (i > 0) moves.push({ label: t('위로'), hint: 'Alt+↑', action: () => moveClip(tab, b, sn, -1) });
  if (i < items.length - 1) moves.push({ label: t('아래로'), hint: 'Alt+↓', action: () => moveClip(tab, b, sn, 1) });
  moves.push({ label: t('다른 담기함으로 옮기기…'), action: () => boxMenu(x, y, (to) => toBox(tab, b, [sn], to), { except: b, header: t('옮길 담기함') }) },
    { label: t('다른 담기함에 복사…'), action: () => boxMenu(x, y, (to) => toBox(tab, b, [sn], to, { copy: true }), { except: b, header: t('복사할 담기함') }) });
  const copyItem = { label: t('원문 복사'), tip: sn.lines ? `${sn.path} ${rangeText(sn.lines)}` : '', term: sn.text,
    action: async () => toast(await copyText(sn.text) ? t('복사했습니다: {what}', { what: clip(sn.label || sn.name, 30) }) : t('복사하지 못했습니다')) };
  const menu = menuGroups([{ header: `${clip(sn.title || sn.label || sn.name || sn.text, 40)}${sn.path ? ` · ${sn.path}` : ''}` }], [...(open ? [{ label: t('펼친 화면에서 보기'), hint: 'Enter', action: open }] : []), ...(sn.path ? [{ label: t('문서에서 보기'), hint: open ? '' : 'Enter', action: () => goToSource(sn) }] : [])],
    [copyItem], sends, moves, [{ label: t('빼기'), hint: 'Delete', action: () => removeClips(tab, b, new Set([sn.id])) }]);
  el.classList.add('lec-picked');
  showMenu(x, y, menu, () => el.classList.remove('lec-picked'));
}

let typed = '';
let typedAt = 0;

/** 목록의 키 — 문서 트리와 같게 (D169·D195): ↑·↓·Home·End, → 펼치기·← 접기(조각에서는 그 담기함으로), Enter 열기, F2 제목, Delete 빼기·지우기,
 * 조각은 Alt+↑·↓ 로 차례, Shift+→ 는 담기함 파일·담은 곳을 터미널로, 글자는 그 글자로 시작하는 줄 */
function onListKey(e) {
  const hit = rowOf(e.target);
  if (!hit || !e.target.matches('.row')) return;
  const { line, box, sn } = hit;
  const tab = S.tab;
  const rows = /** @type {HTMLElement[]} */ ($$('.row', $('#lec-basket-list')));
  const i = rows.indexOf(line);
  const go = (el) => {
    if (!el) return;
    rove(el);
    el.focus({ preventScroll: true });
    el.scrollIntoView({ block: 'nearest' });
  };
  const open = line.getAttribute('aria-expanded') === 'true';
  if (sn ? sendRowKey(e, sn.path || null, stateOf(tab, sn).lines || sn.lines || 0) : !clipsOf(tab).memory && sendRowKey(e, `.lectern/clips/${box.file}`)) return;
  if (e.altKey && sn && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
    if (moveClip(tab, box, sn, e.key === 'ArrowUp' ? -1 : 1)) focusItem(sn);
  } else if (e.ctrlKey || e.metaKey || e.altKey) return;
  else if (e.key === 'ArrowDown') go(rows[Math.min(rows.length - 1, i + 1)]);
  else if (e.key === 'ArrowUp') go(rows[Math.max(0, i - 1)]);
  else if (e.key === 'Home') go(rows[0]);
  else if (e.key === 'End') go(rows[rows.length - 1]);
  else if (e.key === 'ArrowRight') {
    if (!sn && !open && box.items.length) setOpen(box, true);
    else go(rows[i + 1]);
  } else if (e.key === 'ArrowLeft') {
    if (sn) focusRow(`.bk-box[data-file="${CSS.escape(box.file)}"]`);
    else if (open) setOpen(box, false);
  } else if (e.key === 'Enter') {
    if (sn) openClip(box, sn);
    else if (!box.error) openBox(box, openHow(e));
  } else if (e.key === 'F2') {
    if (!box.error) openClip(box, sn, true);
  } else if (e.key === 'Delete') {
    if (sn) remove(box, sn);
    else if (!box.error) dropBox(box);
  } else if (e.key.length === 1 && e.key !== ' ' && !e.isComposing) {
    const now = Date.now();
    typed = now - typedAt > 800 ? e.key.toLowerCase() : typed + e.key.toLowerCase();
    typedAt = now;
    const from = typed.length === 1 ? i + 1 : i;
    go([...rows.slice(from), ...rows.slice(0, from)].find((r) => (r.querySelector('.label')?.textContent || '').toLowerCase().startsWith(typed)));
  } else return;
  e.preventDefault();
  e.stopPropagation();   // 현재 줄의 키로 가지 않게
}

export function initBasket() {
  on('note-send', ({ text, label }) => sendSnippets([snippetOf({ path: '.lectern/notes.md', lines: [] }, null, { kind: 'text', name: t('메모'), label, text, plain: true })]));   // 메모를 문서로 (D92)
  const list = $('#lec-basket-list');
  list.addEventListener('click', (e) => {
    const hit = rowOf(e.target);
    if (!hit) return;
    const { box, sn } = hit;
    if (sn) {
      if (e.target.closest('.bk-put')) putAtCursor([sn]);
      else if (!repeatClick(e)) openClip(box, sn);
    } else if (e.target.closest('[data-toggle]')) setOpen(box, !clipsOf(S.tab).open.has(box.file));
    else if (e.target.closest('.bk-here')) setCur(S.tab, box.file);
    else if (!box.error && !repeatClick(e)) openBox(box, { ...openHow(e), here: e.altKey });
  });
  middleClickOpens(list, '.bk-box');
  list.addEventListener('focusin', (e) => { if (e.target.matches?.('.row')) rove(e.target); });
  list.addEventListener('keydown', onListKey);
  list.addEventListener('contextmenu', (e) => {
    const hit = rowOf(e.target);
    if (!hit) return;
    e.preventDefault();
    if (hit.sn) clipMenu(hit.box, hit.sn, hit.line, e.clientX, e.clientY, () => openClip(hit.box, hit.sn));
    else showMenu(e.clientX, e.clientY, boxActions(hit.box, e.clientX, e.clientY));
  });
  const filter = /** @type {HTMLInputElement} */ ($('#lec-basket-filter'));
  filter.addEventListener('input', render);
  filter.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === 'ArrowDown') {
      e.preventDefault();
      focusRow('.row');
    } else if (e.key === 'Escape' && filter.value) {
      e.stopPropagation();
      filter.value = '';
      render();
    }
  });
  $('#lec-basket-sort').addEventListener('click', async () => {
    await saveConfig({ clip_sort: S.config.clip_sort === 'time' ? 'name' : 'time' });
    render();
  });
  on('config-follow', (keys) => { if (keys.has('clip_sort')) render(); });
  on('clips-state', (tab) => { if (tab === S.tab) render(); });
  on('view', () => { if (!$('#lec-basket').hidden) render(); });   // 보고 있는 담기함
  on('tree', () => { if (!$('#lec-basket').hidden) render(); });   // 원래 문서가 바뀌었는지
  $('#lec-basket-undo button').addEventListener('click', () => undoRemove(S.tab));
  $('#lec-basket-new').addEventListener('click', () => askBox());
  const name = /** @type {HTMLInputElement} */ ($('#lec-basket-name'));
  name.addEventListener('keydown', async (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      stopAsking();
    } else if (e.key === 'Enter' && !e.isComposing) {
      e.preventDefault();
      if (!asking || !name.value.trim()) return;
      asking = false;   // 두 번 누른 Enter 로 둘을 만들지 않게
      if (!(await newBox(S.tab, name.value))) asking = true;
      render();
    }
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
  on('panel', (panel) => {
    if (panel !== 'basket') return;
    render();
    if (S.tab) loadClips(S.tab, { force: true });   // 밖에서(다른 창·Claude Code) 고친 것을 보이게
  });
  on('tab', ({ tab, prev }) => {
    closePick();   // 보낼 곳·새 문서 경로는 앞 탭의 것 (Ctrl+Tab 은 이 창에서도 탭을 바꾼다)
    asking = null;
    if (prev && S.tabs.includes(prev)) flushClips(prev);
    render();
    if (tab) loadClips(tab);
  });
  on('clips', (tab) => { if (tab === S.tab) render(); });
  addEventListener('focus', () => { if (S.tab?.clips?.loaded && (S.tab.clips.boxes.length || !$('#lec-basket').hidden)) loadClips(S.tab, { force: true }); });
  addEventListener('pagehide', () => { flushClips(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) flushClips(); });
  on('editor', render);   // 편집을 열고 닫으면 항목의 '보내기'
  render();
}

/** 보낼 곳 고르기 창이 열려 있으면 닫는다 (main.js 의 Esc) */
export const closeInsert = closePick;
