// 템플릿 갤러리 (D101): Lectern 슬라이드의 장 뼈대를 미리 보고 고른다. 새로 만들기·새 장·템플릿 바꾸기가 같은 창을 쓴다.
// 미리보기는 그림 파일이 아니라 템플릿을 실제 렌더러로 그린 것이다 — 템플릿을 고치면 미리보기도 바뀐다. 무대에서 그리고 칸으로 옮긴다.
// 부르는 쪽은 lineedit·basket 이고 이 모듈은 doc.js 를 쓰므로 import 순환을 피해 이벤트로 받는다: emit('pick-template', {title, resolve})
// 이름 묻기: emit('ask-template-name', {resolve})

import { S, on } from './store.js';
import { getJSON, postJSON } from './api.js';
import { renderMarkdown, splitFrontMatter } from './markdown.js';
import { sanitizeHtml, resolveRef } from './doc.js';
import { renderCharts } from './charts.js';
import { readDeck, prepareDeck, fitDeck } from './slides.js';
import { $, $$, toast } from './util.js';
import { html, raw, setHtml } from './html.js';
import { t } from './i18n.js';

const box = () => $('#lec-gallery');
const list = () => $('#lec-gallery-list');
const THUMB_W = 232;      // 미리보기 폭 (px) — app.css 의 .lec-tpl-view 와 같게

let waiting = null;       // 고르기를 기다리는 resolve
let items = [];           // 고를 수 있는 템플릿
let sel = 0;
let typed = '';           // 번호를 친 글자 (두 자리 번호)
let typedAt = 0;
const drawn = new Map();  // 템플릿 글 → 그린 미리보기 (DOM) — 같은 글이면 다시 그리지 않는다

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
  const view = document.createElement('article');
  view.className = 'md-body lec-marp lec-deck lec-tpl-view';
  view.setAttribute('aria-hidden', 'true');
  view.replaceChildren(...stage.childNodes);
  for (const el of $$('.lec-slide-notes, .lec-slide-play, .lec-tag, .lec-slide-tags', view)) el.remove();
  return view;
}

async function preview(item, slot) {
  try {
    if (!drawn.has(item.text)) drawn.set(item.text, await draw(item.text));
    const view = drawn.get(item.text).cloneNode(true);
    const width = parseFloat(view.querySelector('.lec-slide-wrap')?.style.getPropertyValue('--slide-w')) || 1280;
    view.style.setProperty('--slide-scale', String(THUMB_W / width));
    slot.replaceChildren(view);
  } catch (e) {
    console.warn('템플릿 미리보기 실패', item.name, e);   // i18n-ok (개발자 도구에만)
  }
}

function show() {
  setHtml(list(), items.map((item, i) => html`<li role="option" data-i="${i}" class="lec-tpl${i === sel ? ' sel' : ''}" aria-selected="${i === sel}">
    <div class="lec-tpl-thumb"></div>
    <span class="lec-tpl-name"><b>${item.number}</b> ${item.name}${item.own ? html` <i>${t('내 템플릿')}</i>` : ''}</span>
  </li>`));
  $$('.lec-tpl', list()).forEach((li, i) => preview(items[i], li.querySelector('.lec-tpl-thumb')));
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
  done?.(item);
}

/** 창이 열려 있으면 닫는다 (main.js 의 Esc) */
export function closeGallery() {
  if (box().hidden) return false;
  finish(null);
  return true;
}

async function open({ title, resolve, start = 0 }) {   // start: 먼저 골라 둘 차례
  if (waiting) waiting(null);
  waiting = resolve;
  try {
    items = (await getJSON('/api/slide-templates')).templates;
  } catch (e) {
    toast(t('템플릿을 읽지 못했습니다 — F5 를 누르면 다시 불러옵니다'));
    finish(null);
    return;
  }
  sel = Math.min(start, items.length - 1);
  $('#lec-gallery-title').textContent = title;
  box().hidden = false;
  show();
  list().focus();
}

/** 한 줄에 몇 개 있는지 — 위아래 키 */
function perRow() {
  const cells = $$('.lec-tpl', list());
  const top = cells[0]?.offsetTop;
  const n = cells.findIndex((li) => li.offsetTop !== top);
  return n > 0 ? n : Math.max(1, cells.length);
}

function onKey(e) {
  const go = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: perRow(), ArrowUp: -perRow() }[e.key];
  if (go) {
    e.preventDefault();
    mark(Math.min(items.length - 1, Math.max(0, sel + go)));
  } else if (e.key === 'Enter') {
    e.preventDefault();
    finish(items[sel]);
  } else if (e.key === 'Escape') {
    e.preventDefault();
    e.stopPropagation();
    finish(null);
  } else if (/^\d$/.test(e.key)) {   // 번호로 고르기: 3 은 바로 고르고, 1 은 10·11 이 될 수 있어 잠깐 기다린다
    e.preventDefault();
    typed = Date.now() - typedAt < 900 ? typed + e.key : e.key;
    typedAt = Date.now();
    const i = items.findIndex((x) => String(x.number) === typed);
    if (i >= 0) mark(i);
  }
}

/** 이름을 묻는다 (이 장을 템플릿으로 저장) */
function askName({ resolve }) {
  const dialog = $('#lec-tplname');
  const input = $('#lec-tplname-input');
  const done = (name) => {
    dialog.hidden = true;
    input.onkeydown = null;
    dialog.onmousedown = null;
    resolve(name);
  };
  input.value = '';
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
  list().addEventListener('keydown', onKey);
  list().addEventListener('click', (e) => {
    const li = e.target.closest('.lec-tpl');
    if (li) finish(items[+li.dataset.i]);
  });
  box().addEventListener('mousedown', (e) => { if (e.target === box()) finish(null); });
  $('#lec-gallery-cancel').addEventListener('click', () => finish(null));
  $('#lec-gallery-folder').addEventListener('click', async () => {
    try {
      await postJSON('/api/slide-templates/folder', {});
    } catch (e) {
      toast(e.message);
    }
  });
}
