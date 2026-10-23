// 사이드바 '모아 보기' 탭 (D41): 프로젝트(또는 고른 폴더와 그 하위)의 표·그림·박스글·다이어그램·코드·수식을 종류마다 모아 보인다.
//
// - 문서마다 본문과 같은 해석기로 화면 밖에서 그려(md: markdown-it + 정화, html: DOMParser — 스크립트·그림을 부르지 않는다)
//   목차와 같은 규칙(toc.js 의 readParts)으로 센다. 그래서 번호·이름이 그 문서의 목차와 같다.
//   읽은 결과는 탭마다 문서의 수정 시각과 함께 기억해 두고(tab.partsCache), 바뀐 문서만 다시 읽는다.
// - 문서별로 묶어 트리 순서(또는 최근 수정 순)로. 그림은 작은 그림 격자 — 같은 그림을 여러 문서가 쓰면 처음 것 하나에 '+N곳'.
//   그림은 목록에서 보일 때 불러온다 (본문과 같은 규칙 — 프로젝트 밖은 막고 인터넷 그림은 설정 external_images).
// - 누르면 그 문서를 열고 목차와 같은 방법으로 그 자리로 간다 (접힌 절은 펴고 잠깐 테두리).
// - 여는 곳: 이 탭, 폴더 개요의 '모아 보기' 버튼, 트리의 폴더 우클릭 ('parts' 이벤트 {path, kind}).
// - 종류·범위·거르기·순서·스크롤은 프로젝트 탭마다 남긴다 (tab.side.parts).

import { S, on, emit } from './store.js';
import { getText } from './api.js';
import { navigate } from './nav.js';
import { switchPanel } from './tree.js';
import { readParts, goToPart, PARTS } from './toc.js';
import { renderMarkdown } from './markdown.js';
import { sanitizeHtml, prepareParts, loadImage, imageKey } from './doc.js';
import {
  $, $$, esc, docUrl, isHtml, basename, dirname, debounce, keepFocus, docRoot,
} from './util.js';

const KINDS = Object.keys(PARTS);
const MAX_SHOWN = 800;     // 목록에 그리는 항목 수 (넘으면 거르기로 좁히라고 알린다)
const PARALLEL = 4;        // 문서를 함께 읽는 수

const DEFAULT = { kind: 'table', scope: '', filter: '', order: 'tree', scroll: 0 };
let state = { ...DEFAULT };
let scanning = null;       // 지금 읽는 중인 {tab, scope, done, total}
let thumbs = null;         // 그림 칸이 보일 때 그림을 불러오는 IntersectionObserver

const panelShown = () => !$('#lec-parts').hidden;
const inScope = (path, scope) => !scope || path === scope || path.startsWith(`${scope}/`);

// ---- 읽기 ---------------------------------------------------------------------

/** 문서 하나를 화면 밖에서 읽어 구성 요소 목록으로: [{kind, n, name, label, section, src, alt}] (src·alt 는 그림) */
async function readDoc(tab, path) {
  const text = await getText(docUrl(tab, path));
  let root;
  if (isHtml(path)) {
    root = new DOMParser().parseFromString(text, 'text/html').body;   // 스크립트는 돌지 않고 그림도 부르지 않는다
  } else {
    const tpl = document.createElement('template');   // template 안은 그림을 부르지 않는다 (정화가 src 도 data-src 로 뗀다)
    tpl.innerHTML = sanitizeHtml(renderMarkdown(text, { math: S.config.math !== false }).html);
    root = tpl.content;
    prepareParts(root);
  }
  return readParts(root).rows.filter((r) => r.kind).map((r) => {
    const item = { kind: r.kind, n: r.n, name: r.name, label: r.label, section: r.section };
    if (r.kind === 'figure') {
      const img = r.el.tagName === 'IMG' ? r.el : r.el.querySelector('img');
      item.src = img?.getAttribute('data-src') || img?.getAttribute('src') || '';
      item.alt = img?.getAttribute('alt') || '';
    }
    return item;
  });
}

/** 범위 안의 문서를 읽는다 (바뀐 것만). 읽는 동안 조금씩 다시 그린다. 다른 탭·범위로 새로 읽기 시작하면 멈춘다 */
async function scan(tab, scope) {
  tab.partsCache ??= new Map();
  const files = tab.files.filter((f) => inScope(f.path, scope));
  const todo = files.filter((f) => tab.partsCache.get(f.path)?.mtime !== f.mtime);
  for (const path of tab.partsCache.keys()) if (!tab.fileMap.has(path)) tab.partsCache.delete(path);   // 지워진 문서
  if (!todo.length) return;
  const job = { tab, scope, done: 0, total: todo.length };
  scanning = job;
  const redraw = debounce(() => { if (scanning === job) render(); }, 250);
  let next = 0;
  const worker = async () => {
    while (next < todo.length && scanning === job) {
      const f = todo[next++];
      let items;
      try {
        items = await readDoc(tab, f.path);
      } catch {
        items = [];   // 읽는 사이 지워진 문서 등 — 다음 변경 때 다시 읽는다
      }
      tab.partsCache.set(f.path, { mtime: f.mtime, items });
      job.done += 1;
      redraw();
    }
  };
  await Promise.all(Array.from({ length: PARALLEL }, worker));
  if (scanning === job) scanning = null;
}

// ---- 그리기 ---------------------------------------------------------------------

/** 범위 안 문서들의 항목: [{file, items}] (순서: 트리 또는 최근 수정) */
function collected(tab) {
  const files = tab.files.filter((f) => inScope(f.path, state.scope) && tab.partsCache?.has(f.path));
  if (state.order === 'recent') files.sort((a, b) => b.mtime - a.mtime);
  return files.map((file) => ({ file, items: tab.partsCache.get(file.path).items }));
}

function matcher(text) {
  const words = text.toLowerCase().split(/\s+/).filter(Boolean);
  return (...fields) => {
    const hay = fields.join(' ').toLowerCase();
    return words.every((w) => hay.includes(w));
  };
}

function itemRow(file, item, extra = '') {
  const tip = [`${item.name}${item.label ? ` · ${item.label}` : ''}`, item.section && `절: ${item.section}`, file.path].filter(Boolean).join('\n');
  return `<div class="pt-item" tabindex="0" data-doc="${esc(file.path)}" data-kind="${item.kind}" data-n="${item.n}" title="${esc(tip)}">`
    + `<svg class="tp-icon" aria-hidden="true"><use href="#${PARTS[item.kind].icon}"/></svg>`
    + `<span class="pt-text"><span class="pt-name">${esc(item.name)}</span>${item.label ? `<span class="pt-label">${esc(item.label)}</span>` : ''}`
    + `${item.section ? `<span class="pt-sec">${esc(item.section)}</span>` : ''}</span>${extra}</div>`;
}

function thumb(file, item, others) {
  const more = others.length ? `<span class="pt-more" title="${esc(`같은 그림을 쓰는 다른 문서:\n${others.join('\n')}`)}">+${others.length}곳</span>` : '';
  const tip = [`${item.name}${item.label ? ` · ${item.label}` : ''}`, item.section && `절: ${item.section}`, file.path].filter(Boolean).join('\n');
  return `<div class="pt-thumb" tabindex="0" data-doc="${esc(file.path)}" data-kind="figure" data-n="${item.n}" title="${esc(tip)}">`
    + `<div class="pt-pic" data-src="${esc(item.src)}" data-alt="${esc(item.alt)}"></div>`
    + `<span class="pt-cap">${esc(item.label || item.name)}</span>${more}</div>`;
}

function render() {
  const tab = S.tab;
  const list = $('#lec-parts-list');
  if (!tab) {
    $('#lec-parts-kinds').innerHTML = '';
    $('#lec-parts-info').textContent = '열린 프로젝트가 없습니다';
    list.innerHTML = '';
    return;
  }
  const groups = collected(tab);
  // 종류 버튼: 범위 안의 개수
  const counts = Object.fromEntries(KINDS.map((k) => [k, 0]));
  for (const g of groups) for (const it of g.items) counts[it.kind] += 1;
  const reading = scanning?.tab === tab ? `문서 읽는 중 ${scanning.done}/${scanning.total}` : '';
  if (state.autoKind && !reading) {   // 종류를 정하지 않고 열었는데 그 범위에 없으면, 있는 첫 종류로
    if (!counts[state.kind]) state.kind = KINDS.find((k) => counts[k]) || state.kind;
    state.autoKind = false;
  }
  $('#lec-parts-kinds').innerHTML = KINDS.map((k) => `<button type="button" role="tab" data-kind="${k}" aria-selected="${k === state.kind}"`
    + ` class="${k === state.kind ? 'active' : ''}${counts[k] ? '' : ' zero'}"><svg aria-hidden="true"><use href="#${PARTS[k].icon}"/></svg>${esc(PARTS[k].name)}`
    + `<span class="n">${counts[k]}</span></button>`).join('');
  // 범위
  $('#lec-parts-scope').textContent = state.scope ? `${state.scope}/` : `${tab.name} 전체`;
  $('#lec-parts-scope').title = state.scope ? `${state.scope} 폴더와 그 하위` : '프로젝트 전체';
  $('#lec-parts-all').hidden = !state.scope;
  const order = $('#lec-parts-order');
  order.textContent = state.order === 'recent' ? '최근 수정 순' : '트리 순서';
  order.title = state.order === 'recent' ? '누르면 트리 순서로' : '누르면 최근 수정한 문서부터';
  // 목록
  const match = matcher(state.filter);
  const seen = new Map();   // 그림 → 처음 보인 칸의 '다른 문서' 목록 (같은 그림을 한 번만)
  let shown = 0;
  let docs = 0;
  const html = [];
  for (const { file, items } of groups) {
    const title = file.title || basename(file.path);
    let mine = items.filter((it) => it.kind === state.kind
      && match(it.name, it.label, it.section, title, file.path));
    if (!mine.length) continue;
    let body;
    if (state.kind === 'figure') {
      const cells = [];
      mine = mine.filter((it) => {
        const key = it.src ? imageKey(it.src, file.path, tab) : `${file.path}#${it.n}`;
        if (seen.has(key)) {
          seen.get(key).push(file.path);
          return false;
        }
        const others = [];
        seen.set(key, others);
        cells.push([it, others]);
        return true;
      });
      if (!mine.length) continue;
      body = { cells };
    }
    if (shown >= MAX_SHOWN) break;   // 같은 그림의 '+N곳'은 여기까지 읽은 문서로 센다
    shown += mine.length;
    docs += 1;
    const head = `<div class="pt-doc" tabindex="0" data-doc="${esc(file.path)}" title="${esc(file.path)}">`
      + `<span class="label">${esc(title)}</span>${dirname(file.path) ? `<span class="sub">${esc(dirname(file.path))}</span>` : ''}</div>`;
    html.push({ head, file, mine, body });
  }
  keepFocus(list, () => {
    list.innerHTML = html.map(({ head, file, mine, body }) => (body
      ? `${head}<div class="pt-grid">${body.cells.map(([it, others]) => thumb(file, it, others)).join('')}</div>`
      : head + mine.map((it) => itemRow(file, it)).join(''))).join('');
  });
  watchThumbs(tab);
  // 알림: 개수, 거른 결과, 읽는 중
  const name = PARTS[state.kind].name;
  const total = counts[state.kind];
  let info;
  if (!total) info = reading || `이 범위에는 ${name}${josa(name, '이', '가')} 없습니다`;
  else {
    info = state.filter ? `거른 결과 ${shown}개 (모두 ${total}개)` : `문서 ${docs}개, ${name} ${total}개`;
    if (shown >= MAX_SHOWN) info += ` — 처음 ${MAX_SHOWN}개만, 거르기로 좁히세요`;
    if (reading) info += ` · ${reading}`;
  }
  $('#lec-parts-info').textContent = info;
}

/** 받침이 있으면 a, 없으면 b (표가 / 그림이) */
function josa(word, a, b) {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  return code >= 0 && code < 11172 && code % 28 ? a : b;
}

/** 그림 칸이 목록에서 보일 때 그림을 불러온다 */
function watchThumbs(tab) {
  thumbs?.disconnect();
  thumbs = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      thumbs.unobserve(e.target);
      const pic = e.target;
      const docPath = pic.closest('.pt-thumb')?.dataset.doc;
      if (!pic.dataset.src || !docPath || tab !== S.tab) continue;
      const img = document.createElement('img');
      img.alt = pic.dataset.alt || '';
      img.setAttribute('data-src', pic.dataset.src);
      img.loading = 'lazy';
      pic.append(img);
      loadImage(img, docPath, tab);   // 본문과 같은 규칙. 불러오지 못하면 글로 바뀐다
    }
  }, { root: $('#lec-parts-list'), rootMargin: '200px 0px' });
  for (const pic of $$('#lec-parts-list .pt-pic:empty')) thumbs.observe(pic);
}

/** 범위의 문서를 (바뀐 것만) 읽고 그린다 */
async function refresh() {
  const tab = S.tab;
  if (!tab || !panelShown()) {
    render();
    return;
  }
  const job = scan(tab, state.scope);   // 읽을 것이 있으면 여기서 바로 '읽는 중'이 된다 (첫 await 전까지는 이어서 돈다)
  render();
  await job;
  if (tab === S.tab && panelShown()) render();
}

// ---- 열기 ---------------------------------------------------------------------

/** 항목으로 간다: 그 문서를 열고, 목차와 같은 규칙으로 센 같은 종류·번호의 것으로 */
async function openItem(el) {
  const path = el.dataset.doc;
  const here = S.view?.type === 'doc' && S.view.path === path;
  if (!here && !(await navigate({ type: 'doc', path }))) return;
  if (!el.dataset.kind) return;   // 문서 머리줄
  const row = readParts(docRoot()).rows.find((r) => r.kind === el.dataset.kind && r.n === Number(el.dataset.n));
  if (row) goToPart(row.el);
}

/** 모아 보기를 연다 (폴더 개요의 버튼·트리 우클릭). path: 범위 폴더 ('' = 프로젝트 전체), kind: 종류 (없으면 그대로) */
export function openParts({ path = '', kind = null } = {}) {
  state.scope = path;
  if (kind && PARTS[kind]) state.kind = kind;
  state.autoKind = !kind;
  state.filter = '';
  $('#lec-parts-filter').value = '';
  $('#lec-parts-list').scrollTop = 0;
  emit('show-sidebar');
  if (panelShown()) refresh();
  else switchPanel('parts');   // 'panel' 이벤트가 refresh 한다
}

/** 프로젝트 탭을 바꾸면: 앞 탭의 상태를 남기고 새 탭의 것을 되살린다 */
function onTab({ tab, prev }) {
  if (prev && S.tabs.includes(prev)) prev.side.parts = { ...state, scroll: $('#lec-parts-list').scrollTop };
  state = { ...DEFAULT, ...(tab?.side.parts || {}) };
  $('#lec-parts-filter').value = state.filter;
  if (panelShown()) {
    refresh().then(() => { $('#lec-parts-list').scrollTop = state.scroll; });
  }
}

export function initParts() {
  $('#lec-parts-kinds').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-kind]');
    if (!b || b.dataset.kind === state.kind) return;
    state.kind = b.dataset.kind;
    state.autoKind = false;
    $('#lec-parts-list').scrollTop = 0;
    render();
  });
  $('#lec-parts-all').addEventListener('click', () => openParts({ path: '' }));
  $('#lec-parts-order').addEventListener('click', () => {
    state.order = state.order === 'recent' ? 'tree' : 'recent';
    render();
  });
  const filter = $('#lec-parts-filter');
  const later = debounce(render, 150);
  filter.addEventListener('input', () => {
    state.filter = filter.value.trim();
    later();
  });
  filter.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      state.filter = filter.value.trim();
      render();   // 거르기가 아직 반영되기 전이어도 지금 글자로 거른 첫 항목을 연다
      $('#lec-parts-list .pt-item, #lec-parts-list .pt-thumb')?.click();
    }
    else if (e.key === 'Escape' && filter.value) {
      e.stopPropagation();
      filter.value = '';
      filter.dispatchEvent(new Event('input'));
    }
  });
  const list = $('#lec-parts-list');
  list.addEventListener('click', (e) => {
    const el = e.target.closest('.pt-item, .pt-thumb, .pt-doc');
    if (el) openItem(el);
  });
  list.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.matches('.pt-item, .pt-thumb, .pt-doc')) openItem(e.target);
  });
  on('panel', (name) => { if (name === 'parts') refresh(); });
  on('parts', openParts);
  on('tab', onTab);
  on('tree', () => { if (panelShown()) refresh(); });   // 문서가 바뀌면 (트리를 새로 받으면) 바뀐 문서만 다시 읽는다
}
