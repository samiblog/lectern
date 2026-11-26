// 담기함 펼쳐 보기 (D197): 담기함 하나를 문서 탭에 — 담은 것을 차례대로 실제 모습(표·그림·차트·글)으로, 조각마다 제목과 메모를 적는다.
// 화면 종류 'clips' (path = 담기함의 파일 이름) — main.js 가 nav.js 에 등록한 렌더러 showClips 가 칸에 그린다 (doctabs.js: 담기함마다 탭 하나).
//
// - 머리(담기함의 제목·설명), 붙어 있는 줄(문서로 보내기·AI 에 맡기기·되돌리기·개수), 조각 카드.
// - 카드: 차례, 제목 칸(비우면 캡션이 흐리게), 출처 줄(담은 곳·날짜·원래 문서가 바뀌었는지 — 누르면 그 자리로, Alt+← 로 돌아온다), 담은 내용, 메모 칸.
// - 내용은 담은 순간의 것이다 — 담은 글을 본문과 같은 규칙으로 그린다 (markdown.js → 정화 → doc.js 의 finishPart, 상대경로는 원래 문서 기준).
//   카드가 화면에 가까워질 때 그리고, 다이어그램·차트는 따로 줄을 서서. 다시 그려도 그린 카드와 쓰던 칸은 그대로 둔다 (제자리 고치기 — reconcile).
// - 원래 문서와의 대조: 담은 글이 그 문서에 그대로 있는지 줄로 본다 (clipdata.js 의 findPiece) — 그대로·옮겨짐은 말없이, 바뀌었거나 없어졌으면 알린다.
// - 글은 쓰는 대로 저장한다 (clipstore.js). 담은 내용은 여기서 고치지 않는다 — 원래 문서나 보낸 문서에서 고친다.

import { html, raw, setHtml } from './html.js';
import { S, on, emit } from './store.js';
import { showMenu } from './ui.js';
import { paneOf, paneShown } from './panes.js';
import { setToc, PARTS } from './toc.js';
import { goToSource, clipMenu, boxActions, sendBox, claudeMenu } from './basket.js';
import { clipsOf, boxOf, boxName, loadClips, setCur, editClip, editBox, moveClip, removeClips, undoRemove, flushClips, checkBox, stateOf } from './clipstore.js';
import { renderMarkdown } from './markdown.js';
import { sanitizeHtml, prepareParts, resolveRef, finishPart, settlePart } from './doc.js';
import { linkPaths } from './pathlink.js';
import { renderCharts } from './charts.js';
import { renderMermaid } from './mermaid.js';
import { fitTables } from './tablefit.js';
import { setStatus } from './status.js';
import { clearChanges } from './diffmark.js';
import { setDocSource } from './docmenu.js';
import { aiCli } from './aitool.js';
import { $, $$, linkHow, spotText, middleClickOpens, repeatClick, copyText, toast } from './util.js';
import { t } from './i18n.js';

const isClips = (pane) => !!pane?.clipv && !!pane.view?.classList.contains('clips-view');
const viewsOf = (tab) => (tab?.panes || []).filter(isClips);
const q = (pane, sel) => /** @type {any} */ (pane.view.querySelector(sel));
const themeNow = () => document.documentElement.dataset.theme || '';
const boxAt = (pane) => boxOf(pane.tab, pane.clipv.file);

const STATE_NAMES = { changed: t('원래 문서가 바뀌었습니다'), gone: t('원래 문서가 없습니다') };

/** 사이드바가 고른 조각으로 — 그 카드를 보이고 초점을 (id 가 없으면 담기함), title 이면 제목 칸에 */
function goClip({ file, id, title }) {
  const pane = S.pane;
  if (!isClips(pane) || pane.clipv.file !== file) return;
  const card = id ? cardOf(pane, id) : null;
  if (id && !card) return;
  card?.scrollIntoView({ block: 'start' });
  const target = /** @type {HTMLInputElement} */ (title ? (card ? card.querySelector('.cb-name') : q(pane, '.cb-title')) : card);
  target?.focus({ preventScroll: !!card });
  if (title) target?.select();
}

/** 글 칸의 높이를 글에 맞춘다 */
function grow(area) {
  area.style.height = 'auto';
  area.style.height = `${area.scrollHeight + 2}px`;
}

function skeleton() {
  return [html`<header class="cb-head">
    <p class="cb-kind">${t('담기함')}</p>
    <input class="cb-title" type="text" placeholder="${t('담기함의 제목')}" aria-label="${t('담기함의 제목')}" spellcheck="false" autocomplete="off">
    <textarea class="cb-note" rows="1" placeholder="${t('질문이나 설명 — 비워 두어도 됩니다')}" aria-label="${t('담기함의 설명')}" spellcheck="false"></textarea>
  </header>`, html`<div class="cb-bar">
    <button type="button" class="parts-send cb-here" data-act="here" aria-pressed="false"></button>
    <button type="button" class="parts-send" data-act="send" title="${t('담은 것을 차례대로 열린 문서 탭이나 새 문서로 — 제목과 메모도 함께')}">${t('문서로 보내기…')}</button>
    <button type="button" class="parts-send" data-act="ai" title="${t('담은 것의 위치로 새 문서를 만들어 달라는 요청 글 — 복사·터미널')}">${t('{cli} 에', { cli: aiCli() })}</button>
    <button type="button" class="icon-btn small toggle" data-act="menu" title="${t('담기함의 메뉴')}">${t('더 보기')}</button>
    <span class="tb-spacer"></span>
    <span class="cb-undo" hidden><span></span> <button type="button" class="text-btn" data-act="undo">${t('되돌리기')}</button></span>
    <span class="cb-info"></span>
  </div>`, html`<div class="cb-list" role="list" aria-label="${t('담은 것')}"></div>`];
}

const nameOf = (c) => c.label || c.name || t('조각');

function cardHtml(c) {
  const where = spotText(c);
  return [html`<div class="cb-row"><span class="cb-n"></span><input class="cb-name" type="text" aria-label="${t('조각의 제목')}" spellcheck="false" autocomplete="off">
    <span class="cb-btns"><button type="button" class="icon-btn small" data-act="up" title="${t('위로 (Alt+↑)')}"><svg><use href="#i-up"/></svg></button><button type="button" class="icon-btn small" data-act="down" title="${t('아래로 (Alt+↓)')}"><svg><use href="#i-down"/></svg></button><button type="button" class="icon-btn small" data-act="del" title="${t('빼기 (Delete)')}"><svg><use href="#i-close"/></svg></button></span></div>`,
  html`<div class="cb-src">${c.path ? html`<button type="button" class="cb-go" title="${t('문서에서 보기 — 그 자리로 갑니다 (Alt+← 로 돌아옵니다)')}">${where}</button>` : html`<span>${t('담은 곳 없음')}</span>`}${c.at ? html`<span class="cb-at">${t('{date} 담음', { date: c.at })}</span>` : ''}<span class="cb-state" hidden></span></div>`,
  html`<div class="pv-body pv-wait"><p class="pv-hold">${nameOf(c)}</p></div>`,
  html`<textarea class="cb-memo" rows="1" placeholder="${t('메모 — 왜 담았는지')}" aria-label="${t('메모')}" spellcheck="false"></textarea>`];
}

/** 카드의 칸에 조각의 값을 — 쓰고 있는 칸은 건드리지 않는다 */
function fillCard(card, c, i, n) {
  card.querySelector('.cb-n').textContent = String(i + 1);
  const name = card.querySelector('.cb-name');
  name.placeholder = nameOf(c);
  if (document.activeElement !== name && name.value !== c.title) name.value = c.title;
  const memo = card.querySelector('.cb-memo');
  if (document.activeElement !== memo && memo.value !== c.memo) {
    memo.value = c.memo;
    if (card.isConnected) grow(memo);
  }
  card.querySelector('[data-act="up"]').disabled = i === 0;
  card.querySelector('[data-act="down"]').disabled = i === n - 1;
}

/** 카드를 새로 만들어야 하는 까닭이 되는 것 — 담은 내용은 바뀌지 않으므로 출처(이름 바꾸기)와 글, 스타일뿐 */
const keyOf = (c) => `${themeNow()}|${c.path}|${c.lines || ''}|${c.at}|${c.plain}|${c.text.length}|${c.text.slice(0, 80)}`;

function draw(pane) {
  if (!isClips(pane)) return;
  const st = pane.clipv;
  const tab = pane.tab;
  const box = boxAt(pane);
  const list = q(pane, '.cb-list');
  const miss = !box || box.error;
  q(pane, '.cb-head').hidden = !box;
  q(pane, '.cb-bar').hidden = !!miss;
  if (miss) {
    const state = clipsOf(tab);
    setHtml(list, html`<p class="cb-empty">${!state.loaded && !state.error ? t('담기함을 읽는 중…') : box?.error || state.error ? t('담기함을 읽지 못했습니다: {error}', { error: box?.error || state.error }) : t('이 담기함이 없습니다 — 지워졌거나 이름이 바뀌었습니다')}</p>`);
    setToc(pane, null);
    return;
  }
  const title = q(pane, '.cb-title');
  if (document.activeElement !== title && title.value !== box.title) title.value = box.title;
  const note = q(pane, '.cb-note');
  if (document.activeElement !== note && note.value !== box.note) note.value = box.note;
  grow(note);
  list.querySelector('.cb-empty')?.remove();
  // 제자리 고치기: 있는 카드는 두고(쓰던 칸의 초점과 그린 내용), 차례가 다른 것만 옮긴다
  const have = new Map(/** @type {HTMLElement[]} */ ([...list.children]).map((el) => [el.dataset.id, el]));
  let at = /** @type {any} */ (list.firstElementChild);
  box.items.forEach((c, i) => {
    let card = have.get(c.id);
    have.delete(c.id);
    if (!card || card.dataset.key !== keyOf(c)) {
      const made = document.createElement('article');
      made.className = 'cb-card';
      made.tabIndex = 0;
      made.dataset.id = c.id;
      made.dataset.key = keyOf(c);
      setHtml(made, cardHtml(c));
      const tall = st.heights.get(c.id);
      if (tall) /** @type {HTMLElement} */ (made.querySelector('.pv-body')).style.minHeight = `${tall}px`;
      if (card) {
        if (at === card) at = made;
        card.replaceWith(made);
      }
      card = made;
    }
    if (card === at) at = at.nextElementSibling;
    else list.insertBefore(card, at);
    fillCard(card, c, i, box.items.length);
  });
  for (const el of have.values()) el.remove();
  for (const memo of $$('.cb-memo', list)) if (memo.value && !memo.style.height) grow(memo);
  if (!box.items.length) setHtml(list, html`<p class="cb-empty">${t("아직 담은 것이 없습니다. 문서의 절·표·그림·차트 등을 우클릭해 '담기'를 고르거나 Alt+C 를 누르세요")}</p>`);
  const state = clipsOf(tab);
  const undo = q(pane, '.cb-undo');
  undo.hidden = state.undo?.file !== box.file;
  if (!undo.hidden) undo.querySelector('span').textContent = t('{n}개를 뺐습니다', { n: state.undo.entries.length });
  q(pane, '.cb-info').textContent = t('{n}개', { n: box.items.length });
  for (const b of $$('.cb-bar .parts-send:not(.cb-here)', pane.view)) b.disabled = !box.items.length;
  const here = q(pane, '.cb-here');
  const cur = box.file === state.cur;
  here.textContent = cur ? `● ${t('지금 담기함')}` : t('여기에 담기');
  here.title = cur ? t('담는 것이 여기에 들어갑니다 (Alt+C)') : t('누르면 지금 담기함으로 — 담는 것이 여기에 들어갑니다 (Alt+C)');
  here.setAttribute('aria-pressed', String(cur));
  showStates(pane);
  setStatus({ path: t('담기함 — {name}', { name: boxName(box) }), info: t('{n}개', { n: box.items.length }) }, pane);
  watch(pane);
  checkSources(pane);   // 바뀐 것이 없으면 서버에 묻지 않는다
}

// ---- 내용 그리기 -----------------------------------------------------------------

/** 카드의 내용을 그린다 — 담은 글을 본문과 같은 규칙으로. 문서가 쓴 글이라 정화를 거치고, 이 안의 단추·행을 앱의 것으로 읽지 않는다 */
async function fillBody(pane, card) {
  const box = boxAt(pane);
  const c = box?.items.find((x) => x.id === card.dataset.id);
  if (!c || !card.isConnected || card.classList.contains('cb-filled')) return;
  card.classList.add('cb-filled');
  const hold = card.querySelector('.pv-body');
  const body = document.createElement('div');
  if (c.plain) {   // 고른 글 — 보이는 글 그대로
    body.className = 'pv-body md-body cb-plain';
    body.textContent = c.text;
  } else {
    body.className = 'pv-body md-body';
    const { html: markup } = renderMarkdown(c.notes ? `${c.text}\n\n${c.notes}` : c.text, { math: S.config.math !== false });
    setHtml(body, raw(sanitizeHtml(markup)));
    prepareParts(body);
    finishPart(body, c.path, pane.tab);
  }
  hold.replaceWith(body);
  fitTables(body);
  if (!c.plain && c.path) linkPaths(body, c.path, pane.tab).catch(() => {});
  if (body.querySelector('pre.mermaid, pre.lec-chart')) {
    const st = pane.clipv;
    st.drawing = (st.drawing || Promise.resolve()).then(async () => {
      if (!body.isConnected) return;
      await renderMermaid(body);
      await renderCharts(body, { tab: pane.tab, path: c.path, sanitize: sanitizeHtml, resolveRef });
      settlePart(body);
      keepHeight(pane, card);
    }).catch(() => {});
  } else keepHeight(pane, card);
}

/** 그린 높이를 적어 둔다 — 돌아와 다시 그릴 때 그 자리를 잡아 스크롤 위치가 맞게 */
function keepHeight(pane, card) {
  requestAnimationFrame(() => {
    const h = card.querySelector('.pv-body')?.offsetHeight;
    if (h) pane.clipv.heights.set(card.dataset.id, h);
  });
}

function watch(pane) {
  const st = pane.clipv;
  st.io?.disconnect();
  st.io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      st.io.unobserve(e.target);
      fillBody(pane, /** @type {HTMLElement} */ (e.target)).catch(() => {});
    }
  }, { root: pane.scroller, rootMargin: '700px 0px' });
  for (const card of $$('.cb-card:not(.cb-filled)', pane.view)) st.io.observe(card);
}

/** 조각마다 원래 문서가 바뀌었는지(clipstore.js 의 checkBox)를 출처 줄과 목차에 */
function showStates(pane) {
  const box = boxAt(pane);
  for (const c of box?.items || []) {
    const el = /** @type {HTMLElement | null} */ (cardOf(pane, c.id)?.querySelector('.cb-state'));
    if (!el) continue;
    const { state } = stateOf(pane.tab, c);
    el.hidden = !state;
    el.textContent = state ? STATE_NAMES[state] : '';
    el.title = state === 'changed' ? t('담은 글이 그 문서에 그대로 있지 않습니다 — 여기 보이는 것은 담은 때의 내용입니다') : '';
  }
  outline(pane);
}

/** 목차 패널: 담은 것의 차례 — 메모가 있으면 ✎, 원래 문서가 바뀌었거나 없으면 ⚠ */
function outline(pane) {
  const box = boxAt(pane);
  if (!box || box.error) return;
  setToc(pane, pane.view, { title: boxName(box), items: box.items.map((c) => {
    const { state } = stateOf(pane.tab, c);
    return { level: 1, name: c.title || nameOf(c), tip: [c.title || nameOf(c), c.title && nameOf(c), c.path, c.memo, state && STATE_NAMES[state]].filter(Boolean).join('\n'),
      mark: `${c.memo ? '✎' : ''}${state ? '⚠' : ''}`, icon: PARTS[c.kind]?.icon || (c.kind === 'section' ? 'i-toc' : 'i-text'), el: cardOf(pane, c.id) };
  }) });
}

const checkSources = (pane) => checkBox(pane.tab, boxAt(pane));

// ---- 화면 (nav.js 의 렌더러) -----------------------------------------------------

/**
 * 담기함을 칸(pane)에 그린다 (화면 종류 'clips' — path 는 담기함의 파일 이름)
 * @param {Pane} pane
 * @param {string} path
 * @param {ShowOptions} [options]
 */
export async function showClips(pane, path, { scrollTop } = {}) {
  pane.renderId += 1;   // 이 칸에서 그리던 다른 화면은 버려진다
  const { view, tab } = pane;
  const st = (pane.clipv ??= { file: path, heights: new Map(), io: null, drawing: null });
  const kept = view.classList.contains('clips-view') && st.file === path && !!view.querySelector(':scope > .cb-list');
  st.file = path;
  const top = typeof scrollTop === 'function' ? scrollTop() : scrollTop;
  if (!kept) {
    view.className = 'clips-view';
    delete view.dataset.docPath;   // 앞에 보던 md 문서의 경로 — 남아 있으면 그 문서의 기능이 이 화면에서 켜진다
    setHtml(view, skeleton());
    setDocSource(pane, null);
    clearChanges(pane);
  }
  draw(pane);
  if (!kept) pane.scroller.scrollTop = top ?? 0;
  emit('rendered', pane);
  const was = clipsOf(tab).loaded;
  loadClips(tab, { force: true }).then(() => {
    if (!isClips(pane) || pane.clipv.file !== path) return;   // 읽는 사이에 다른 화면으로
    draw(pane);
    if (!was && !kept && top) pane.scroller.scrollTop = top;
  });
  return true;
}

// ---- 누르기·키 (칸의 id 가 옮겨 다니므로 #lec-panes 에서 받는다) ---------------------------

function paneAt(e) {
  const pane = paneOf(e.target);
  return isClips(pane) && pane.view.contains(e.target) ? pane : null;
}

const clipAt = (pane, el) => boxAt(pane)?.items.find((c) => c.id === el?.closest('.cb-card')?.dataset.id) || null;
const cardOf = (pane, id) => /** @type {HTMLElement | null} */ (pane.view.querySelector(`.cb-card[data-id="${CSS.escape(id)}"]`));

/** 그 문서의 그 자리로 — 담은 글이 옮겨졌으면 지금 있는 줄로 */
const go = (pane, c, how = {}) => goToSource({ ...c, lines: stateOf(pane.tab, c).lines || c.lines }, false, how);

function remove(pane, c) {
  const box = boxAt(pane);
  const i = box.items.indexOf(c);
  removeClips(pane.tab, box, new Set([c.id]));
  const next = box.items[Math.min(i, box.items.length - 1)];
  if (next) cardOf(pane, next.id)?.focus({ preventScroll: true });
}

function step(pane, c, dir) {
  if (!moveClip(pane.tab, boxAt(pane), c, dir)) return;
  const card = cardOf(pane, c.id);
  card?.focus({ preventScroll: true });
  card?.scrollIntoView({ block: 'nearest' });
}

function onClick(e) {
  const pane = paneAt(e);
  if (!pane) return;
  const at = /** @type {HTMLElement} */ (e.target);
  if (at.closest('.pv-body')) {   // 담은 글 — 문서가 심은 단추·행을 앱의 것으로 읽지 않는다. 코드의 [복사]만 여기서
    const btn = at.closest('.code-copy');
    const code = btn?.closest('.code-block')?.querySelector('pre > code');
    if (code) copyText(code.textContent).then((ok) => toast(ok ? t('복사했습니다: {what}', { what: t('코드') }) : t('복사하지 못했습니다')));
    return;
  }
  const box = boxAt(pane);
  if (!box) return;
  const act = /** @type {HTMLElement | null} */ (at.closest('[data-act]'))?.dataset.act;
  const c = clipAt(pane, at);
  if (act === 'send') sendBox(box);
  else if (act === 'here') setCur(pane.tab, box.file);
  else if (act === 'ai') {
    const r = at.closest('button').getBoundingClientRect();
    claudeMenu(r.left, r.bottom + 4, box);
  }
  else if (act === 'undo') undoRemove(pane.tab);
  else if (act === 'menu') {
    const r = at.closest('button').getBoundingClientRect();
    showMenu(r.left, r.bottom + 4, boxActions(box, r.left, r.bottom + 4));
  } else if (c && act === 'up') step(pane, c, -1);
  else if (c && act === 'down') step(pane, c, 1);
  else if (c && act === 'del') remove(pane, c);
  else if (c && at.closest('.cb-go') && !repeatClick(e)) go(pane, c, linkHow(e));
}

/** 담은 글 안의 #절 링크는 이 화면에 그 절이 없을 수 있다 — 원래 문서의 그 절로 연다 (doc.js 의 bindLink 보다 먼저) */
function onAnchor(e) {
  const pane = paneAt(e);
  const a = pane && /** @type {HTMLElement} */ (e.target).closest?.('.pv-body a[href^="#"]');
  const c = a && clipAt(pane, a);
  if (!c) return;
  e.preventDefault();
  e.stopPropagation();
  if (c.path) emit('open', { type: 'doc', path: c.path, hash: a.getAttribute('href'), ...linkHow(e) });
}

function onInput(e) {
  const pane = paneAt(e);
  const at = /** @type {any} */ (e.target);
  const box = pane && boxAt(pane);
  if (!box || at.closest('.pv-body')) return;
  if (at.matches('.cb-title')) editBox(pane.tab, box, { title: at.value });
  else if (at.matches('.cb-note')) {
    grow(at);
    editBox(pane.tab, box, { note: at.value });
  } else {
    const c = clipAt(pane, at);
    if (!c) return;
    if (at.matches('.cb-name')) editClip(pane.tab, box, c, { title: at.value });
    else if (at.matches('.cb-memo')) {
      grow(at);
      editClip(pane.tab, box, c, { memo: at.value });
    }
  }
}

function onKey(e) {
  const pane = paneAt(e);
  const at = /** @type {HTMLElement} */ (e.target);
  if (!pane || at.closest('.pv-body')) return;
  const c = clipAt(pane, at);
  const vertical = e.key === 'ArrowUp' || e.key === 'ArrowDown';
  if (at.matches('.cb-name, .cb-title, .cb-memo, .cb-note')) {
    if (e.key === 'Enter' && !e.isComposing && at.matches('.cb-name, .cb-title')) {   // 제목에서 Enter 는 메모(설명)로
      e.preventDefault();
      (at.matches('.cb-title') ? q(pane, '.cb-note') : at.closest('.cb-card').querySelector('.cb-memo')).focus();
    } else if (e.key === 'Escape' && !e.isComposing) {   // 쓰던 것은 저장되어 있다 — 카드로 초점만
      e.preventDefault();
      e.stopPropagation();
      (at.closest('.cb-card') || pane.scroller).focus({ preventScroll: true });
    } else if (c && e.altKey && vertical) {
      e.preventDefault();
      e.stopPropagation();
      step(pane, c, e.key === 'ArrowUp' ? -1 : 1);
    }
    return;
  }
  if (!c || !at.matches('.cb-card') || e.ctrlKey || e.metaKey) return;
  if (vertical && e.altKey) step(pane, c, e.key === 'ArrowUp' ? -1 : 1);
  else if (vertical && !e.shiftKey) {
    const next = /** @type {HTMLElement | null} */ (e.key === 'ArrowUp' ? at.previousElementSibling : at.nextElementSibling);
    next?.focus({ preventScroll: true });
    next?.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Delete' && !e.altKey) remove(pane, c);
  else if (e.key === 'Enter' && !e.altKey) go(pane, c);
  else if (e.key === 'F2') /** @type {HTMLElement} */ (at.querySelector('.cb-name')).focus();
  else return;
  e.preventDefault();
  e.stopPropagation();   // 현재 줄의 키로 가지 않게
}

function onMenu(e) {
  const pane = paneAt(e);
  const at = /** @type {HTMLElement} */ (e.target);
  if (!pane || (at.closest('input, textarea') && !at.closest('.pv-body'))) return;   // 글 칸은 기본 메뉴
  const c = clipAt(pane, at);
  if (!c) return;
  e.preventDefault();
  clipMenu(boxAt(pane), c, at.closest('.cb-card'), e.clientX, e.clientY);
}

export function initClipView() {
  const panes = $('#lec-panes');
  panes.addEventListener('click', onAnchor, true);
  panes.addEventListener('click', onClick);
  panes.addEventListener('input', onInput);
  panes.addEventListener('keydown', onKey);
  panes.addEventListener('contextmenu', onMenu);
  panes.addEventListener('focusout', (e) => {
    const pane = paneAt(e);
    if (pane && /** @type {HTMLElement} */ (e.target).matches('.cb-title, .cb-note, .cb-name, .cb-memo')) flushClips(pane.tab);
  });
  middleClickOpens(panes, '.clips-view .cb-go');
  on('clips', (tab) => { for (const pane of viewsOf(tab)) if (paneShown(pane)) draw(pane); else pane.stale = true; });
  on('clips-goto', goClip);
  on('clips-state', (tab) => { for (const pane of viewsOf(tab)) if (paneShown(pane)) showStates(pane); });
  on('clips-sources', (pane) => { if (isClips(pane) && paneShown(pane)) checkSources(pane); });   // 밖에서 문서가 바뀜 (watch.js)
  on('tree', () => { for (const pane of viewsOf(S.tab)) if (paneShown(pane)) checkSources(pane); });   // 원래 문서가 생기거나 지워짐
  on('rendered', (pane) => { if (pane.clipv && !pane.view.classList.contains('clips-view')) pane.clipv.io?.disconnect(); });   // 이 칸이 다른 화면으로
}
