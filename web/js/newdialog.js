// 새 문서 만들기 (D105): 제목과 스타일을 정해 선택된 폴더에 새 문서를 만들고, md 문서 화면에서 바로 쓰게 한다 (편집 모드로 가지 않는다).
// 여는 곳: 사이드바 '문서' 머리줄의 만들기, Ctrl+N, 문서 탭 줄의 +, 우클릭 '새 문서 만들기…'(폴더·문서·트리의 빈 곳).
// 제목의 처음 값은 '새 문서'(있으면 번호를 붙여), 스타일의 처음 값은 가장 최근에 쓴 것이다. 제목이 파일 이름이 된다.
// 번호가 있는 스타일은 보기 머리글 두 줄을 넣는다 — 번호가 문서에 있어야 뒤에 더한 제목의 번호를 맞출 수 있다 (D107).
// Lectern 슬라이드를 고르면 만들기 다음에 첫 장의 템플릿 갤러리가 뜬다 (D101).

import { S, on, emit } from './store.js';
import { getJSON, saveConfig } from './api.js';
import { $, toast, basename, blockedReadOnly } from './util.js';
import { html, setHtml } from './html.js';
import { t } from './i18n.js';
import { preview, setOwnStyles } from './headstyle.js';
import { styleGroups } from './mdstyle.js';
import { newDocGuess, cleanPath, createDoc, openCreated } from './newdoc.js';

let asked = null;   // {tab, dir, deck, mine, items, sel}

const box = () => $('#lec-newdoc');
const title = () => $('#lec-newdoc-title');
const list = () => $('#lec-newdoc-list');

/** 제목 → 파일 이름 (확장자 없이). Windows 가 받지 않는 글자는 빈칸으로 */
export function fileName(text) {
  return String(text).replace(/\.(md|markdown)$/i, '').replace(/[\\/:*?"<>|]/g, ' ').replace(/\s+/g, ' ').trim().replace(/[. ]+$/, '');
}

function setMsg(text) {
  const p = $('#lec-newdoc-msg');
  p.hidden = !text;
  p.textContent = text;
}

function draw() {
  const { deck } = asked;
  $('#lec-newdoc-md').classList.toggle('on', !deck);
  $('#lec-newdoc-deck').classList.toggle('on', deck);
  $('#lec-newdoc-md').setAttribute('aria-pressed', String(!deck));
  $('#lec-newdoc-deck').setAttribute('aria-pressed', String(deck));
  $('#lec-newdoc-styles').hidden = deck;
  $('#lec-newdoc-note').hidden = !deck;
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

/** 새 문서 창을 연다. dir: 만들 폴더 (null 이면 지금 보는 문서·폴더 개요의 폴더) */
export async function askNewDocument(dir = null) {
  if (!S.tab) {
    toast(t('먼저 폴더를 여세요'));
    return;
  }
  const tab = S.tab;
  if (blockedReadOnly(tab) || asked) return;
  const guess = newDocGuess(dir);
  const folder = guess.includes('/') ? guess.slice(0, guess.lastIndexOf('/')) : '';
  let mine = [];
  try {
    mine = (await getJSON('/api/md-styles')).styles;
    setOwnStyles(mine);
  } catch { /* 내 스타일 없이 — 기본 스타일로 만들 수 있다 */ }
  if (S.tab !== tab || asked) return;
  asked = { tab, dir: folder, deck: false, mine, items: [], sel: 0 };
  $('#lec-newdoc-where').textContent = t('위치: {where}', { where: folder ? `${folder}/` : t('프로젝트 맨 위') });
  title().value = basename(guess).replace(/\.md$/, '');
  setMsg('');
  draw();
  const first = (S.config.recent_md_styles || []).map((id) => asked.items.findIndex((r) => r.id === id)).find((n) => n >= 0);
  asked.sel = first ?? Math.max(0, asked.items.findIndex((r) => r.id === 'plain'));
  draw();
  box().hidden = false;
  title().focus();
  title().select();
}

export function closeNewDocument() {
  if (box().hidden) return false;
  box().hidden = true;
  asked = null;
  return true;
}

async function submit() {
  if (!asked) return;
  const { dir, deck } = asked;
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

function onKey(e) {
  if (e.isComposing || e.keyCode === 229) return;   // 한글 조합 중
  if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && !asked.deck) {
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

/** 종류를 바꾼다 — 초점은 제목에 둔다 */
function setDeck(deck) {
  asked.deck = deck;
  draw();
  title().focus();
}

export function initNewDialog() {
  on('new-doc', ({ dir = null }) => askNewDocument(dir));   // 우클릭·문서 탭 줄의 + (tree·others·tabs·palette)
  on('tab', closeNewDocument);   // 다른 프로젝트 탭으로 — 만들 폴더는 그 탭의 것
  box().addEventListener('keydown', onKey);
  box().addEventListener('mousedown', (e) => { if (e.target === box()) closeNewDocument(); });
  title().addEventListener('input', () => { setMsg(''); draw(); });
  list().addEventListener('click', (e) => {
    const li = e.target.closest('li[data-i]');
    if (li) pick(Number(li.dataset.i));
    title().focus();
  });
  list().addEventListener('dblclick', (e) => { if (e.target.closest('li[data-i]')) submit(); });
  $('#lec-newdoc-md').addEventListener('click', () => setDeck(false));
  $('#lec-newdoc-deck').addEventListener('click', () => setDeck(true));
  $('#lec-newdoc-go').addEventListener('click', submit);
  $('#lec-newdoc-no').addEventListener('click', closeNewDocument);
  $('#lec-docs-new').addEventListener('click', () => askNewDocument());
}
