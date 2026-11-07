// md 문서 스타일 (D103): 문서 방식(서술식·개조식)과 머리글 모양을 고른다. 머리글은 md 원문에서 바뀐다 — html 틀이 아니다 (계산은 headstyle.js, 저장은 lineedit.js).
// 같은 방식 안의 머리글 모양은 바로 바꾸고, 방식을 바꿀 때는 꼭 묻는다. 본문을 바꾸는 일은 판단이 들어서 Claude 에게 요청 글만 넣는다 (Enter 는 사용자가 — D51).
// 스타일이 많아져도 찾기 쉽게: 찾기 칸(초점은 여기 — 한글은 조합 중이라 키로 옮길 수 없다), 최근 쓴 것, 내 스타일을 묶어 보인다.
// '이 문서를 스타일로 만들기' 는 머리글의 번호 모양을 뽑아 Lectern 전체의 내 스타일로 저장한다.

import { S, on, emit } from './store.js';
import { getJSON, postJSON, saveConfig } from './api.js';
import { $, toast, isMd } from './util.js';
import { html, setHtml } from './html.js';
import { t } from './i18n.js';
import { STYLES, detect, kindOf, marksFrom, preview, sample, setOwnStyles } from './headstyle.js';
import { sourceLines } from './spotlight.js';
import { linesEditable } from './lineedit.js';

const box = () => $('#lec-mdstyle');
const list = () => $('#lec-mdstyle-list');
const find = () => $('#lec-mdstyle-find');
const RECENT = 4;
const BASE_NAMES = () => ({ plain: t('번호 없음'), paper: t('논문형'), chapter: t('장·절형'), rule: t('규정형'), number: t('숫자형'), report: t('보고서형'), symbol: t('기호형') });
const USES = () => ({
  prose: { plain: t('기고문·칼럼'), paper: t('인문·사회 논문'), number: t('이공계 논문·기술 문서'), chapter: t('학위 논문·단행본'), rule: t('규정·지침') },
  outline: { report: t('보고서'), number: t('기획안·계획서'), symbol: t('공문·요약'), plain: t('회의록·메모') },
});
const KINDS = () => ({ prose: t('서술식'), outline: t('개조식') });

let asked = null;   // {path, lines, scheme(지금 모양), kind(지금 방식), shown(고르는 방식), mine(내 스타일들), dir, items(고를 줄들), sel}

/** 지금 화면이 머리글을 고칠 수 있는 md 문서인지 — Lectern 슬라이드·보기만 하는 프로젝트·편집 중은 뺀다 */
export function canStyle() {
  const view = S.pane?.view;
  const path = view?.dataset.docPath;
  return !!path && isMd(path) && !view.classList.contains('lec-marp') && linesEditable();
}

const row = (id, kind, name) => ({ id, kind, name, use: USES()[kind][id] || '', sub: id === 'plain' ? t('개요 · 시장 현황') : sample(id) });

/** 고를 수 있는 모든 줄. 찾을 때는 두 방식을 함께 본다 */
function rowsOf(kind) {
  const names = BASE_NAMES();
  return [
    ...STYLES[kind].map((id) => row(id, kind, names[id])),
    ...asked.mine.filter((x) => x.kind === kind).map((x) => ({ ...row(`own:${x.name}`, kind, x.name), own: true })),
  ];
}

/** 보이는 묶음: [[머리말, 줄들]] */
function sections() {
  const q = find().value.trim().toLowerCase();
  if (q) {
    const hits = ['prose', 'outline'].flatMap((kind) => rowsOf(kind).map((r) => ({ ...r, tag: KINDS()[kind] })))
      .filter((r) => `${r.name} ${r.use} ${r.sub}`.toLowerCase().includes(q));
    return [[t('찾은 스타일'), hits]];
  }
  const all = rowsOf(asked.shown);
  const recent = (S.config.recent_md_styles || []).map((id) => all.find((r) => r.id === id)).filter(Boolean).slice(0, RECENT);
  const mine = all.filter((r) => r.own);
  const base = all.filter((r) => !r.own);
  return [[recent.length && all.length > 6 ? t('최근 쓴 것') : '', all.length > 6 ? recent : []], [mine.length ? t('기본') : '', base], [mine.length ? t('내 스타일') : '', mine]];
}

function draw() {
  for (const kind of ['prose', 'outline']) {
    const btn = $(`#lec-mdstyle-${kind}`);
    btn.classList.toggle('on', kind === asked.shown && !find().value);
    btn.setAttribute('aria-pressed', String(kind === asked.shown));
    btn.textContent = `${KINDS()[kind]}${kind === asked.kind ? ` · ${t('지금')}` : ''}`;
  }
  const groups = sections().filter(([, rows]) => rows.length);
  asked.items = groups.flatMap(([, rows]) => rows);
  asked.sel = Math.min(asked.sel, Math.max(0, asked.items.length - 1));
  let i = -1;
  setHtml(list(), groups.length ? groups.flatMap(([head, rows]) => [
    head ? html`<li class="head">${head}</li>` : '',
    ...rows.map((r) => {
      i += 1;
      return html`<li role="option" data-i="${i}" class="${i === asked.sel ? 'sel' : ''}" aria-selected="${i === asked.sel}">
        <span class="t">${r.name}${r.use ? html` <em>${r.use}</em>` : ''}${r.tag ? html` <i>${r.tag}</i>` : ''}${r.id === asked.scheme ? html` <i>${t('지금')}</i>` : ''}</span><span class="p">${r.sub}</span>
      </li>`;
    }),
  ]) : html`<li class="none">${t('맞는 스타일이 없습니다')}</li>`);
  const item = asked.items[asked.sel];
  const shown = item ? preview(asked.lines, item.id) : [];
  setHtml($('#lec-mdstyle-preview'), shown.length
    ? shown.map((h) => html`<li style="--d:${h.depth - 1}">${h.text}</li>`)
    : html`<li class="none">${t('이 문서에는 머리글이 없습니다')}</li>`);
  $('#lec-mdstyle-go').disabled = !item;
  list().querySelector('li.sel')?.scrollIntoView({ block: 'nearest' });
}

export function closeMdStyle() {
  if (box().hidden) return false;
  box().hidden = true;
  asked = null;
  return true;
}

let folder = '';   // 내 스타일 폴더

async function loadMine() {
  try {
    const { styles, dir } = await getJSON('/api/md-styles');
    setOwnStyles(styles);
    folder = dir;
    return styles;
  } catch (e) {
    toast(e.message);
    return [];
  }
}

async function open() {
  if (!canStyle()) return;
  const mine = await loadMine();
  if (!canStyle()) return;
  const lines = sourceLines();
  const kind = kindOf(lines);
  const found = detect(lines, kind);
  const scheme = found === 'plain' && marksFrom(lines).length ? '' : found;   // 번호가 있는데 아는 모양이 아니면 '지금' 표시를 달지 않는다
  asked = { path: S.pane.view.dataset.docPath, lines, scheme, kind, shown: kind, mine, items: [], sel: 0 };
  find().value = '';
  $('#lec-mdstyle-form').hidden = false;
  $('#lec-mdstyle-ask').hidden = true;
  draw();
  asked.sel = Math.max(0, asked.items.findIndex((r) => r.id === scheme));
  draw();
  box().hidden = false;
  find().focus();
}

/** 고르는 방식을 바꾼다. 같은 모양이 있으면 그대로 둔다 */
function showKind(kind) {
  const id = asked.items[asked.sel]?.id;
  asked.shown = kind;
  find().value = '';
  asked.sel = 0;
  draw();
  asked.sel = Math.max(0, asked.items.findIndex((r) => r.id === id));
  draw();
}

/** 머리글을 바꾼다. then: 저장한 뒤 터미널에 넣을 요청 글 */
function run(then = '') {
  const { id } = asked.items[asked.sel];
  saveConfig({ recent_md_styles: [id, ...(S.config.recent_md_styles || []).filter((x) => x !== id)].slice(0, 8) });
  closeMdStyle();
  emit('md-headings', { scheme: id, then });
}

/** 고른 것을 적용한다. 문서 방식을 바꾸면 먼저 묻는다 */
function choose() {
  const item = asked.items[asked.sel];
  if (!item) return;
  if (item.kind === asked.kind) {
    if (item.id === asked.scheme) closeMdStyle();
    else run();
    return;
  }
  const names = KINDS();
  $('#lec-mdstyle-question').textContent = t('{from} 문서를 {to} 으로 바꿀까요? 머리글은 바로 바뀌지만 본문은 Claude 가 고쳐야 합니다.', { from: names[asked.kind], to: names[item.kind] });
  $('#lec-mdstyle-form').hidden = true;
  $('#lec-mdstyle-ask').hidden = false;
  $('#lec-mdstyle-claude').focus();
}

function askClaude() {
  run(t('@{path} 의 본문을 {to} 으로 바꿔 줘. 머리글은 그대로 두고 숫자와 표는 바꾸지 마. 고치기 전에 어떻게 바꿀지 먼저 보여 줘.', { path: asked.path, to: KINDS()[asked.items[asked.sel].kind] }));
}

/** 이 문서의 머리글 모양을 내 스타일로 저장한다 */
async function saveFromDoc() {
  const marks = marksFrom(asked.lines);
  if (!marks.length) {
    toast(t('번호나 기호가 달린 머리글이 없습니다 — 머리글에 번호를 단 문서에서 만드세요'));
    return;
  }
  const kind = asked.shown;   // 지금 고르고 있는 방식의 스타일로 저장한다
  const name = await new Promise((resolve) => { emit('ask-template-name', { resolve, title: t('이 문서의 머리글을 스타일로 저장 — {sample}', { sample: marks.filter(Boolean).slice(0, 4).join('  ') }) }); });
  if (!name || !asked) {
    find().focus();
    return;
  }
  try {
    const { style } = await postJSON('/api/md-styles', { name, kind, marks });
    asked.mine = await loadMine();
    asked.scheme = `own:${style.name}`;
    asked.shown = kind;
    find().value = '';
    draw();
    asked.sel = Math.max(0, asked.items.findIndex((r) => r.id === `own:${style.name}`));
    draw();
    toast(t('내 스타일 {name} 으로 저장했습니다', { name: style.name }));
  } catch (e) {
    toast(e.message);
  }
  find().focus();
}

/** 번호 모양이 복잡하면 Claude 에게 맡긴다 — 요청 글만 터미널에 넣는다 (Enter 는 사용자가) */
function askStyle() {
  const text = t("@{path} 의 머리글을 보고 md 문서 스타일을 만들어 줘. {guide} 의 'md 문서 스타일' 장대로 {dir} 에 파일 하나로 써. 스타일 이름: ", { path: asked.path, guide: S.writingGuide, dir: folder });
  closeMdStyle();
  emit('term-paste', text);
}

function pick(i) {
  asked.sel = i;
  draw();
}

function onKey(e) {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    if (asked.items.length) pick((asked.sel + (e.key === 'ArrowDown' ? 1 : -1) + asked.items.length) % asked.items.length);
  } else if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && !find().value) {
    e.preventDefault();
    showKind(e.key === 'ArrowLeft' ? 'prose' : 'outline');
  } else if (e.key === 'Enter') {
    e.preventDefault();
    choose();
  } else if (e.key === 'Escape') {
    e.preventDefault();
    e.stopPropagation();
    if (find().value) {
      find().value = '';
      asked.sel = 0;
      draw();
    } else closeMdStyle();
  }
}

const refresh = () => { $('#lec-st-mdstyle').hidden = !canStyle(); };

export function initMdStyle() {
  on('md-style', open);
  on('deck-shown', refresh);
  on('editor', refresh);
  $('#lec-st-mdstyle').addEventListener('click', open);
  $('#lec-mdstyle-go').addEventListener('click', choose);
  $('#lec-mdstyle-save').addEventListener('click', saveFromDoc);
  $('#lec-mdstyle-request').addEventListener('click', askStyle);
  $('#lec-mdstyle-prose').addEventListener('click', () => { showKind('prose'); find().focus(); });
  $('#lec-mdstyle-outline').addEventListener('click', () => { showKind('outline'); find().focus(); });
  $('#lec-mdstyle-cancel').addEventListener('click', closeMdStyle);
  $('#lec-mdstyle-heads').addEventListener('click', () => run());
  $('#lec-mdstyle-claude').addEventListener('click', askClaude);
  $('#lec-mdstyle-no').addEventListener('click', closeMdStyle);
  $('#lec-mdstyle-folder').addEventListener('click', async () => {
    try {
      await postJSON('/api/md-styles/folder', {});
    } catch (e) {
      toast(e.message);
    }
  });
  find().addEventListener('input', () => {
    asked.sel = 0;
    draw();
  });
  find().addEventListener('keydown', onKey);
  list().addEventListener('click', (e) => {
    const li = e.target.closest('li[data-i]');
    if (li) {
      pick(+li.dataset.i);
      find().focus();
    }
  });
  list().addEventListener('dblclick', (e) => { if (e.target.closest('li[data-i]')) choose(); });
  box().addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && e.target !== find()) {
      e.preventDefault();
      e.stopPropagation();
      closeMdStyle();
    }
  });
  box().addEventListener('mousedown', (e) => { if (e.target === box()) closeMdStyle(); });
}
