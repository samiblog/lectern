// 템플릿 갤러리 (D101): Lectern 슬라이드의 장 뼈대를 미리 보고 고른다. 새로 만들기·새 장·템플릿 바꾸기가 같은 창을 쓴다.
// 왼쪽에 묶음 목록(최근 쓴 것, 기본, 사용자의 묶음), 위에 찾기. 번호는 묶음 안의 장 차례다.
// 미리보기는 그림 파일이 아니라 템플릿을 실제 렌더러로 그린 것이다 — 템플릿을 고치면 미리보기도 바뀐다. 무대에서 그리고 칸으로 옮긴다.
// 부르는 쪽은 lineedit·basket 이고 이 모듈은 doc.js 를 쓰므로 import 순환을 피해 이벤트로 받는다: emit('pick-template', {title, resolve, group, start})
// 이름 묻기: emit('ask-template-name', {resolve})
// Claude 가 할 일은 요청 글을 터미널에 넣는 데까지다 (Enter 는 사용자가 — D51).

import { S, on, emit } from './store.js';
import { getJSON, postJSON, saveConfig } from './api.js';
import { renderMarkdown, splitFrontMatter } from './markdown.js';
import { sanitizeHtml, resolveRef } from './doc.js';
import { renderCharts } from './charts.js';
import { readDeck, prepareDeck, fitDeck } from './slides.js';
import { $, $$, toast } from './util.js';
import { html, raw, setHtml } from './html.js';
import { t } from './i18n.js';

const box = () => $('#lec-gallery');
const list = () => $('#lec-gallery-list');
const find = () => $('#lec-gallery-find');
const THUMB_W = 232;      // 미리보기 폭 (px) — app.css 의 .lec-tpl-view 와 같게
const RECENT = 6;
const RECENT_VIEW = '\n최근';   // i18n-ok (묶음 이름과 겹치지 않는 표시)

let waiting = null;       // 고르기를 기다리는 resolve
let groups = [];          // [{name, own, templates:[{number, name, text}]}]
let folder = '';
let view = '';            // 지금 보는 묶음 이름, RECENT_VIEW
let items = [];           // 보이는 템플릿 [{group, own, number, name, text, label}]
let sel = 0;
let typed = '';           // 번호를 친 글자 (두 자리 번호)
let typedAt = 0;
const drawn = new Map();  // 템플릿 글 → 그린 미리보기 (DOM) — 같은 글이면 다시 그리지 않는다

const flat = (g) => g.templates.map((x) => ({ ...x, group: g.name, own: g.own, label: x.number }));

function recentItems() {
  const all = groups.flatMap(flat);
  return (S.config.recent_templates || [])
    .map((key) => all.find((x) => `${x.group}\t${x.name}` === key))
    .filter(Boolean).map((x, i) => ({ ...x, label: i + 1 }));
}

/** 템플릿 글을 Lectern 슬라이드 한 장으로 그려 미리보기를 만든다 */
async function draw(text) {
  const source = `---\nmarp: true\n---\n\n${text.replace(/\{\{(제목|title)\}\}/g, t('제목'))}`;
  const deck = readDeck(splitFrontMatter(source).frontMatter);
  const { html: markup } = renderMarkdown(source, { math: S.config.math !== false, deck, cells: true });
  const stage = document.createElement('article');
  stage.className = 'md-body lec-marp lec-deck lec-stage';
  stage.style.width = `${THUMB_W}px`;
  stage.style.setProperty('--slide-scale', '1');
  setHtml(stage, raw(sanitizeHtml(markup)));
  document.body.append(stage);
  try {
    prepareDeck(stage, deck, source);
    await renderCharts(stage, { tab: S.tab, path: '', sanitize: sanitizeHtml, resolveRef });
    fitDeck(stage);
  } finally {
    stage.remove();
  }
  const out = document.createElement('article');
  out.className = 'md-body lec-marp lec-deck lec-tpl-view';
  out.setAttribute('aria-hidden', 'true');
  out.replaceChildren(...stage.childNodes);
  for (const el of $$('.lec-slide-notes, .lec-slide-play, .lec-tag, .lec-slide-tags', out)) el.remove();
  return out;
}

async function preview(item, slot) {
  try {
    if (!drawn.has(item.text)) drawn.set(item.text, await draw(item.text));
    const shown = drawn.get(item.text).cloneNode(true);
    const width = parseFloat(shown.querySelector('.lec-slide-wrap')?.style.getPropertyValue('--slide-w')) || 1280;
    shown.style.setProperty('--slide-scale', String(THUMB_W / width));
    slot.replaceChildren(shown);
  } catch (e) {
    console.warn('템플릿 미리보기 실패', item.name, e);   // i18n-ok (개발자 도구에만)
  }
}

function showGroups() {
  const rows = [...(recentItems().length ? [[RECENT_VIEW, t('최근 쓴 것')]] : []), ...groups.map((g) => [g.name, g.name])];
  setHtml($('#lec-gallery-groups'), rows.map(([id, name]) => html`<li data-g="${id}" class="${id === view && !find().value ? 'sel' : ''}">${name}</li>`));
}

function showItems() {
  const other = view === RECENT_VIEW || !!find().value;   // 여러 묶음이 섞이면 묶음 이름도 보인다
  setHtml(list(), items.length ? items.map((item, i) => html`<li role="option" data-i="${i}" class="lec-tpl${i === sel ? ' sel' : ''}" aria-selected="${i === sel}">
    <div class="lec-tpl-thumb"></div>
    <span class="lec-tpl-name"><b>${item.label}</b> ${item.name}${other ? html` <i>${item.group}</i>` : ''}</span>
  </li>`) : html`<li class="lec-tpl-none">${t('맞는 템플릿이 없습니다')}</li>`);
  $$('.lec-tpl', list()).forEach((li, i) => preview(items[i], li.querySelector('.lec-tpl-thumb')));
}

function showView(id, start = 0) {
  view = id;
  find().value = '';
  items = id === RECENT_VIEW ? recentItems() : flat(groups.find((g) => g.name === id) || groups[0]);
  sel = Math.max(0, Math.min(start, items.length - 1));
  showGroups();
  showItems();
}

function search() {
  const q = find().value.trim().toLowerCase();
  if (!q) {
    showView(view);
    return;
  }
  items = groups.flatMap(flat).filter((x) => `${x.name}\n${x.text}`.toLowerCase().includes(q)).map((x, i) => ({ ...x, label: i + 1 }));
  sel = 0;
  showGroups();
  showItems();
}

function mark(i) {
  sel = i;
  $$('.lec-tpl', list()).forEach((li, n) => {
    li.classList.toggle('sel', n === i);
    li.setAttribute('aria-selected', String(n === i));
    if (n === i) li.scrollIntoView({ block: 'nearest' });
  });
}

function finish(item) {
  const done = waiting;
  waiting = null;
  box().hidden = true;
  if (item) {
    const key = `${item.group}\t${item.name}`;
    saveConfig({ recent_templates: [key, ...(S.config.recent_templates || []).filter((x) => x !== key)].slice(0, RECENT) });
  }
  done?.(item);
}

/** 창이 열려 있으면 닫는다 (main.js 의 Esc) */
export function closeGallery() {
  if (box().hidden) return false;
  finish(null);
  return true;
}

async function open({ title, resolve, group = '', start = 0 }) {
  if (waiting) waiting(null);
  waiting = resolve;
  try {
    ({ groups, dir: folder } = await getJSON('/api/slide-templates'));
  } catch (e) {
    toast(t('템플릿을 읽지 못했습니다 — F5 를 누르면 다시 불러옵니다'));
    finish(null);
    return;
  }
  $('#lec-gallery-title').textContent = title;
  box().hidden = false;
  const wanted = groups.some((g) => g.name === group) ? group : groups[0]?.name;
  showView(wanted, wanted === groups[0]?.name ? start : 0);
  find().focus();   // 초점은 찾기 칸에 둔다 — 한글은 조합 중이라 키로 옮길 수 없다. 빈 칸일 때의 숫자는 번호다
}

/** 한 줄에 몇 개 있는지 — 위아래 키 */
function perRow() {
  const cells = $$('.lec-tpl', list());
  const top = cells[0]?.offsetTop;
  const n = cells.findIndex((li) => li.offsetTop !== top);
  return n > 0 ? n : Math.max(1, cells.length);
}

function nextView(dir) {
  const ids = $$('#lec-gallery-groups li').map((li) => li.dataset.g);
  showView(ids[(ids.indexOf(view) + dir + ids.length) % ids.length]);
}

function onKey(e) {
  const go = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: perRow(), ArrowUp: -perRow() }[e.key];
  if (go) {
    e.preventDefault();
    if (items.length) mark(Math.min(items.length - 1, Math.max(0, sel + go)));
  } else if (e.key === 'PageDown' || e.key === 'PageUp') {
    e.preventDefault();
    nextView(e.key === 'PageDown' ? 1 : -1);
  } else if (e.key === 'Enter') {
    e.preventDefault();
    if (items[sel]) finish(items[sel]);
  } else if (e.key === 'Escape') {
    e.preventDefault();
    e.stopPropagation();
    if (find().value) {
      find().value = '';
      search();
    } else finish(null);
  } else if (/^\d$/.test(e.key) && !find().value) {   // 번호로 고르기: 1 뒤에 2 를 치면 12 다
    e.preventDefault();
    typed = Date.now() - typedAt < 900 ? typed + e.key : e.key;
    typedAt = Date.now();
    const i = items.findIndex((x) => String(x.label) === typed);
    if (i >= 0) mark(i);
  }
}

/** 이름을 묻는다 (이 장을 템플릿으로 저장) */
function askName({ resolve, title = '' }) {
  const dialog = $('#lec-tplname');
  const input = $('#lec-tplname-input');
  const done = (name) => {
    dialog.hidden = true;
    input.onkeydown = null;
    dialog.onmousedown = null;
    resolve(name);
  };
  input.value = '';
  $('#lec-tplname-title').textContent = title || t('이 장을 템플릿으로 저장');
  dialog.hidden = false;
  input.focus();
  input.onkeydown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      done(input.value.trim());
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      done('');
    }
  };
  dialog.onmousedown = (e) => { if (e.target === dialog) done(''); };
}

export function initGallery() {
  on('pick-template', open);
  on('ask-template-name', askName);
  find().addEventListener('keydown', onKey);
  list().addEventListener('click', (e) => {
    const li = e.target.closest('.lec-tpl');
    if (li) finish(items[+li.dataset.i]);
  });
  find().addEventListener('input', search);
  $('#lec-gallery-groups').addEventListener('click', (e) => {
    const li = e.target.closest('li[data-g]');
    if (li) {
      showView(li.dataset.g);
      find().focus();
    }
  });
  box().addEventListener('mousedown', (e) => { if (e.target === box()) finish(null); });
  $('#lec-gallery-cancel').addEventListener('click', () => finish(null));
  $('#lec-gallery-folder').addEventListener('click', async () => {
    finish(null);
    try {
      await postJSON('/api/slide-templates/folder', {});   // Lectern 탭으로 — 묶음을 평소처럼 고친다
    } catch (e) {
      toast(e.message);
    }
  });
  $('#lec-gallery-ask').addEventListener('click', () => {
    const text = t("Lectern 슬라이드 템플릿을 만들어 줘. {guide} 의 '템플릿' 장을 읽고 {dir} 에 묶음 파일로 써. 원하는 모양: ", { guide: S.slidesGuide, dir: folder });
    finish(null);
    emit('term-paste', text);   // 터미널에 붙여 넣기 (D51 — Enter 는 사용자가)
  });
}
