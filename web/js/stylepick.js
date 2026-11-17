// 글쓰기 스타일 고르기 (D161): 설정 창 '글쓰기 스타일'의 '스타일 고르기…'. Lectern 에 든 스타일 넷(web/help/writing-styles.json — 이런 글에·바뀌는 것·견본),
// Claude Code 기본, 개인 폴더의 내 스타일, 새 스타일 만들기. 고르면 설정 ai_style(기본은 ai_style_where 'off')을 바꾸고 설정 창으로 돌아간다 —
// 켤 곳·바뀌는 파일·요청 글은 설정 창의 그 칸(aisetup.js)이 만든다. 견본은 같은 요청을 Claude Code 에 스타일 없이와 그 스타일로 실제로 시킨
// 결과의 앞부분이다 (tools/make_style_samples.py) — 이 창이 AI 를 부르지 않는다.

import { S, emit } from './store.js';
import { getJSON, saveConfig } from './api.js';
import { $, $$, toast, copyText } from './util.js';
import { html, setHtml } from './html.js';
import { t, LANG } from './i18n.js';
import { aiTool, aiCli } from './aitool.js';
import { aiStatus, chosenStyle, scope, canFolder } from './aisetup.js';
import { openRaw } from './rawview.js';

const box = () => $('#lec-stylepick');
let meta = null;      // writing-styles.json
let current = '';     // 보이는 것: 스타일 id | 'default' | 'mine:<파일>' | 'new'

const claude = () => aiTool() === 'claude';
const pick = (v) => (v && typeof v === 'object' ? (v[LANG] ?? v.ko) : v);

/** Lectern 에 든 스타일 — 이름·경로는 서버의 것(화면 언어의 판), 이런 글에·바뀌는 것·견본은 writing-styles.json */
function lecternStyles() {
  return (S.writingStyles || []).map((s) => ({ ...s, ...(meta?.styles?.find((m) => m.id === s.id) || {}) }));
}

const mineStyles = () => (claude() ? aiStatus()?.claude?.other_styles || [] : []);

function renderList() {
  const row = (id, name, sub, on) => html`<button type="button" class="raw-item${on ? ' on' : ''}" data-id="${id}"><span>${name}</span>${sub ? html`<small>${sub}</small>` : ''}</button>`;
  const chosen = chosenStyle().id;
  const off = claude() && scope('wstyle') === 'off';
  setHtml($('#lec-stylepick-list'), [
    html`<div class="raw-group">${t('Lectern 에 든 스타일')}</div>`,
    ...lecternStyles().map((s) => row(s.id, s.name, !off && s.id === chosen ? t('고른 것') : '', current === s.id)),
    claude() ? html`<div class="raw-group">${t('스타일 없이')}</div>${row('default', t('Claude Code 기본'), off ? t('고른 것') : '', current === 'default')}` : '',
    mineStyles().length ? html`<div class="raw-group">${t('내 글쓰기 스타일')}</div>` : '',
    ...mineStyles().map((m) => row(`mine:${m.file}`, m.name, !off && `mine:${m.file}` === chosen ? t('고른 것') : '', current === `mine:${m.file}`)),
    html`<div class="raw-group">${t('새로')}</div>${row('new', t('새 스타일 만들기…'), '', current === 'new')}`,
  ]);
}

/** 지금 이 폴더에서 듣는 스타일 (aisetup 의 지금 상태 — 폴더의 값이 개인 값보다 앞선다) */
function hearing() {
  const now = aiStatus();
  if (!claude() || !now?.claude) return '';
  const v = now.project?.settings?.local?.value || now.project?.settings?.shared?.value || now.claude.settings.user.value || t('Claude Code 기본');
  return now.project ? t('지금 {folder} 폴더에서 듣는 스타일: {value}', { folder: now.project.name, value: v }) : t('모든 폴더의 기본 스타일: {value}', { value: v });
}

const STATE = () => ({ same: t('개인 폴더에 설치됨 — Lectern 의 것과 같음'), differs: t('개인 폴더에 설치됨 — Lectern 의 것과 다름 (다시 설치하면 새 판으로)'), missing: t('아직 설치하지 않음') });

/** @returns {Markup[]} */
function renderStyle(s) {
  const st = aiStatus()?.claude?.styles?.[s.id];
  const sample = s.sample;
  return [
    html`<h3 class="pick-name">${s.name}</h3><p class="pick-desc">${s.description}</p>`,
    html`<div class="pick-sub">${t('이런 글에')}</div><p class="pick-use">${pick(s.use)}</p>`,
    html`<div class="pick-sub">${t('바뀌는 것')}</div><ul class="pick-changes">${(pick(s.changes) || []).map((c) => html`<li>${c}</li>`)}</ul>`,
    sample ? html`<div class="pick-sub">${t('견본 — 같은 요청을 Claude Code 에 시킨 결과의 앞부분')}</div>
      <p class="pick-request">«${sample.request}»${LANG === 'en' ? html` <small>${t('(견본은 한국어로 시킨 것입니다)')}</small>` : ''}</p>
      <div class="pick-samples">
        <div><div class="pick-cap">${t('Claude Code 기본')}</div><div class="pick-text">${sample.default}</div></div>
        <div><div class="pick-cap">${t('이 스타일')}</div><div class="pick-text">${sample.style}</div></div>
      </div>` : '',
    html`<p class="pick-now">${[st ? STATE()[st.state] : '', hearing()].filter(Boolean).join(' · ')}</p>`,
    html`<div class="opt-btns"><button type="button" class="text-btn" data-act="choose">${t('이 스타일로')}</button><button type="button" class="text-btn" data-act="raw">${t('원문 보기')}</button></div>`,
  ];
}

/** @returns {Markup[]} */
function renderMine(m) {
  return [
    html`<h3 class="pick-name">${m.name}</h3><p class="pick-desc">${m.description || t('설명 없음')}</p>`,
    html`<p class="pick-use">${t('개인 폴더의 내 글쓰기 스타일 — {path}', { path: m.path })}</p>`,
    html`<p class="pick-now">${hearing()}</p>`,
    html`<div class="opt-btns"><button type="button" class="text-btn" data-act="choose">${t('이 스타일로')}</button><button type="button" class="text-btn" data-act="raw">${t('원문 보기')}</button></div>`,
  ];
}

/** @returns {Markup[]} */
function renderDefault() {
  return [
    html`<h3 class="pick-name">${t('Claude Code 기본')}</h3>`,
    html`<p class="pick-desc">${t('스타일을 켜지 않습니다. Claude Code 의 개발 지침(고칠 범위 지키기, 고친 뒤 확인하기)이 그대로 듣습니다 — 코드를 쓰는 폴더는 이것으로 둡니다')}</p>`,
    html`<p class="pick-now">${hearing()}</p>`,
    html`<div class="opt-btns"><button type="button" class="text-btn" data-act="default"${canFolder() ? '' : html` disabled title="${t('열린 폴더가 없습니다 — 폴더를 열고 고릅니다')}"`}>${t('이 폴더는 Claude Code 기본으로')}</button></div>`,
  ];
}

/** 새 스타일 만들기 요청 (D161) — 안내(web/help/new-style.md)가 가장 가까운 Lectern 스타일을 바탕으로 짓고, 보이고 물은 뒤 저장하게 한다 */
export const newStylePrompt = () => t('Lectern 의 글쓰기 스타일 만들기 안내({guide})를 읽고, 내 글에 맞는 글쓰기 스타일을 하나 만들어 줘. 저장하기 전에 초안을 먼저 보여 줘. 원하는 글: ', { guide: S.styleGuide });

/** @returns {Markup[]} */
function renderNew() {
  return [
    html`<h3 class="pick-name">${t('새 스타일 만들기')}</h3>`,
    html`<p class="pick-desc">${t('{cli} 가 Lectern 에 든 스타일 가운데 가장 가까운 것을 바탕으로 새 스타일을 짓고, 초안을 보인 뒤 물어서 개인 폴더(~/.claude/output-styles)에 저장합니다. 요청 글 끝에 원하는 글을 이어서 적습니다 — 예: 주간 회의록, 결정 사항과 할 일만, 표 하나', { cli: aiCli() })}</p>`,
    html`<p class="pick-use">${t("저장한 뒤 설정 창을 다시 열면 이 목록의 '내 글쓰기 스타일'에 나옵니다. Claude Code 가 그 스타일을 쓰려면 다시 시작합니다")}</p>`,
    html`<div class="opt-btns"><button type="button" class="text-btn" data-act="new-copy">${t('{cli}용 요청 복사', { cli: aiCli() })}</button><button type="button" class="icon-btn small" data-act="new-term" title="${t('그 요청 글을 터미널에 붙여 넣기 (Enter 는 누르지 않음)')}" aria-label="${t('그 요청 글을 터미널에 붙여 넣기 (Enter 는 누르지 않음)')}"><svg><use href="#i-term"/></svg></button></div>`,
  ];
}

function show(id) {
  current = id;
  renderList();
  const main = $('#lec-stylepick-main');
  const s = lecternStyles().find((x) => x.id === id);
  const m = mineStyles().find((x) => `mine:${x.file}` === id);
  setHtml(main, s ? renderStyle(s) : m ? renderMine(m) : id === 'default' ? renderDefault() : renderNew());
  main.scrollTop = 0;
}

/** 고르기 창을 연다 — 처음은 지금 고른 스타일 */
export async function openStylePick() {
  if (!meta) {
    try {
      meta = await getJSON('/static/help/writing-styles.json');
    } catch {
      meta = { styles: [] };
    }
  }
  box().hidden = false;
  const off = claude() && scope('wstyle') === 'off';
  show(off ? 'default' : chosenStyle().id);
  $(`#lec-stylepick-list .raw-item[data-id="${CSS.escape(current)}"]`)?.focus();
}

export function closeStylePick() {
  if (box().hidden) return false;
  box().hidden = true;
  return true;
}

/** 고른 것을 설정에 — 설정 창의 '글쓰기 스타일' 칸이 그것으로 바뀐다 */
function choose(patch, name) {
  saveConfig(patch);
  closeStylePick();
  emit('settings-redraw');
  toast(t('고른 스타일: {name} — 켤 곳을 확인하고 요청 글을 보내세요', { name }));
}

async function act(what) {
  const s = lecternStyles().find((x) => x.id === current);
  const m = mineStyles().find((x) => `mine:${x.file}` === current);
  const where = scope('wstyle');
  if (what === 'choose' && (s || m)) {
    choose({ ai_style: s ? s.id : `mine:${m.file}`, ...(where === 'off' ? { ai_style_where: 'folder' } : {}) }, (s || m).name);
  } else if (what === 'default' && canFolder()) {
    choose({ ai_style_where: 'off' }, t('Claude Code 기본'));
  } else if (what === 'raw') {
    openRaw(s ? [`style:${s.file}.md`, `style:${s.file}.en.md`, `lstyle:${s.id}`] : [`style:${m.file}`]);
  } else if (what === 'new-copy') {
    toast(await copyText(newStylePrompt()) ? t('요청 글을 복사했습니다 — {cli} 에 붙여 넣고 원하는 글을 이어서 적으세요', { cli: aiCli() }) : t('복사하지 못했습니다'));
  } else if (what === 'new-term') {
    closeStylePick();
    emit('close-settings');
    emit('term-paste', newStylePrompt());   // 터미널에 붙여 넣기 (D51 — Enter 없이)
  }
}

export function initStylePick() {
  $('#lec-stylepick-list').addEventListener('click', (e) => {
    const b = e.target.closest('.raw-item');
    if (b) show(b.dataset.id);
  });
  $('#lec-stylepick-list').addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const all = $$('#lec-stylepick-list .raw-item');
    const next = all[(all.indexOf(document.activeElement) + (e.key === 'ArrowDown' ? 1 : -1) + all.length) % all.length];
    show(next.dataset.id);
    $(`#lec-stylepick-list .raw-item[data-id="${CSS.escape(next.dataset.id)}"]`)?.focus();
  });
  $('#lec-stylepick-main').addEventListener('click', (e) => {
    const b = e.target.closest('[data-act]');
    if (b) act(b.dataset.act);
  });
  $('#lec-stylepick-close').addEventListener('click', closeStylePick);
  box().addEventListener('click', (e) => { if (e.target === box()) closeStylePick(); });   // 바깥을 누르면 닫기
}
