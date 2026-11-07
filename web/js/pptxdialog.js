// pptx 로 전환 (D102): 상태줄의 'pptx 로 전환' — pptx 스타일을 고르면 앱이 문서 옆에 새 pptx 를 만든다.
// 스타일은 Lectern 전체의 보관소(설정 폴더 pptx-styles)에 있고 문서에는 이름만 적는다 (맨 앞 설정의 pptxStyle — lineedit 의 'pptx-style').

// Claude 가 할 일(pptx 로 스타일과 템플릿 만들기)은 요청 글을 터미널에 넣는 데까지다 (Enter 는 사용자가 — D51).

import { S, emit } from './store.js';
import { getJSON, postJSON, saveConfig } from './api.js';
import { $, $$, toast, dirname, blockedReadOnly } from './util.js';
import { html, setHtml } from './html.js';
import { t } from './i18n.js';

const box = () => $('#lec-pptx');
const list = () => $('#lec-pptx-list');

let asked = null;   // {tab, path, rows, sel, busy, out}

function setMsg(text, bad = false) {
  const p = $('#lec-pptx-msg');
  p.hidden = !text;
  p.textContent = text;
  p.classList.toggle('bad', bad);
}

function rowsOf({ styles, default: chosen, memory }) {
  const names = new Set(styles.map((s) => s.name));
  const rows = [];
  const kept = names.has(memory.style) ? memory.style : names.has(memory.group) ? memory.group : '';   // 같은 이름의 템플릿 묶음이 짝이다
  const style = styles.find((s) => s.name === kept);
  if (style) rows.push({ ...style, value: '', label: kept, sub: kept === memory.style ? t('이 문서가 기억한 스타일') : t('템플릿 묶음과 짝인 스타일') });
  else if (memory.original) rows.push({ value: '', label: t('원본 pptx'), sub: t('고치지 않은 장은 원본 그대로 씁니다') });
  for (const s of styles) if (s.name !== kept) rows.push({ ...s, value: s.name, label: s.name, sub: s.name === chosen ? t('기본 스타일') : '' });
  if (!style && !memory.original && !names.has(chosen)) rows.push({ value: '', label: t('Lectern 스타일'), sub: t('슬라이드 창에서 고른 스타일로 만듭니다') });
  return rows;
}

function draw() {
  const { rows, sel } = asked;
  setHtml(list(), rows.map((r, i) => html`<li role="option" data-i="${i}" class="${i === sel ? 'sel' : ''}" aria-selected="${i === sel}">
    <span class="t">${r.label}</span>
    <span class="lec-pptx-colors">${(r.colors || []).map((c) => html`<i style="background:${c}"></i>`)}</span>
    ${r.sub ? html`<span class="p">${r.sub}</span>` : ''}
  </li>`));
}

/** 고른 스타일의 미리보기 (표지·본문). 그림은 Claude 가 스타일을 등록할 때 만든다 */
function showPreviews() {
  const shots = asked.rows[asked.sel]?.previews || [];
  const box2 = $('#lec-pptx-previews');
  box2.hidden = !shots.length;
  setHtml(box2, shots.map((f) => html`<img src="/pptxstyle/${encodeURIComponent(f)}" alt="">`));
}

function pick(i) {
  asked.sel = i;
  $$('li', list()).forEach((li, n) => {
    li.classList.toggle('sel', n === i);
    li.setAttribute('aria-selected', String(n === i));
  });
  showPreviews();
}

export function closePptx() {
  if (box().hidden) return false;
  if (asked?.busy) return true;
  box().hidden = true;
  asked = null;
  return true;
}

async function open() {
  const pane = S.pane;
  const path = pane?.current?.path;
  if (!path || !pane.view.classList.contains('lec-deck') || blockedReadOnly(S.tab)) return;
  if (pane.editor?.dirty) {
    toast(t('저장하지 않은 편집이 있습니다 — 저장한 뒤 전환하세요'));
    return;
  }
  let info;
  try {
    info = await getJSON(`/api/pptx-styles?p=${encodeURIComponent(S.tab.id)}&path=${encodeURIComponent(path)}`);
  } catch (e) {
    toast(e.message);
    return;
  }
  const rows = rowsOf(info);
  const start = Math.max(0, rows.findIndex((r) => r.sub === t('기본 스타일')));
  const remembered = rows[0]?.value === '' && (rows[0].sub !== t('슬라이드 창에서 고른 스타일로 만듭니다'));
  asked = { tab: S.tab, pane, path, rows, sel: remembered ? 0 : start, busy: false };
  $('#lec-pptx-title').textContent = t('pptx 로 전환 — {name}', { name: info.out });
  $('#lec-pptx-default').checked = false;
  $('#lec-pptx-done').hidden = true;
  $('#lec-pptx-form').hidden = false;
  const lost = info.memory.style && !info.styles.some((s) => s.name === info.memory.style);
  setMsg(lost ? t("문서의 스타일 '{name}' 이 보관소에 없습니다 — 다른 스타일을 고르세요", { name: info.memory.style })
    : info.styles.length ? '' : t('보관소에 pptx 스타일이 없습니다 — 보관소 폴더에 pptx 파일을 넣으면 여기에 나옵니다'), !!lost);
  draw();
  showPreviews();
  box().hidden = false;
  list().focus();
}

async function run() {
  if (!asked || asked.busy) return;
  const { tab, path, rows, sel } = asked;
  const row = rows[sel];
  asked.busy = true;
  $('#lec-pptx-go').disabled = true;
  setMsg(t('만드는 중입니다. 차트가 많으면 조금 걸립니다…'));
  try {
    const r = await postJSON('/api/pptx-export', { p: tab.id, path, style: row.value });
    if (row.value && $('#lec-pptx-default').checked) saveConfig({ pptx_style: row.value });
    if (row.value) emit('slide-op', { op: 'pptx-style', style: row.value });   // 문서에 이름을 적어 다음에도 쓴다
    asked.result = `${dirname(path) ? `${dirname(path)}/` : ''}${r.path}`;
    $('#lec-pptx-form').hidden = true;
    $('#lec-pptx-done').hidden = false;
    $('#lec-pptx-summary').textContent = t('{name} 을 만들었습니다 — {n}장', { name: r.path, n: r.slides });
    setMsg((r.notes || []).slice(0, 6).join('\n'));
    $('#lec-pptx-show').focus();
  } catch (e) {
    setMsg(e.message, true);
  } finally {
    asked.busy = false;
    $('#lec-pptx-go').disabled = false;
  }
}

async function send(url) {
  try {
    await postJSON(url, { p: asked.tab.id, path: asked.result });
  } catch (e) {
    toast(e.message);
  }
  closePptx();
}

export function initPptx() {
  $('#lec-st-pptx').addEventListener('click', open);
  $('#lec-pptx-go').addEventListener('click', run);
  $('#lec-pptx-cancel').addEventListener('click', closePptx);
  $('#lec-pptx-close').addEventListener('click', closePptx);
  $('#lec-pptx-show').addEventListener('click', () => send('/api/reveal'));
  $('#lec-pptx-open').addEventListener('click', () => send('/api/open-external'));
  $('#lec-pptx-ask').addEventListener('click', () => {
    const text = t('pptx-to-lectern 스킬로 이 pptx 를 pptx 스타일과 같은 이름의 템플릿 묶음으로 등록해 줘. 스킬이 없으면 {dir} 의 README.md 를 읽고 나에게 물어봐. 스타일 이름과 pptx 경로: ', { dir: S.skillsDir });
    closePptx();
    emit('term-paste', text);   // 터미널에 붙여 넣기 (D51 — Enter 는 사용자가)
  });
  $('#lec-pptx-folder').addEventListener('click', async () => {
    try {
      await postJSON('/api/pptx-styles/folder', {});
    } catch (e) {
      toast(e.message);
    }
  });
  list().addEventListener('click', (e) => {
    const li = e.target.closest('li[data-i]');
    if (li) pick(+li.dataset.i);
  });
  list().addEventListener('dblclick', (e) => { if (e.target.closest('li[data-i]')) run(); });
  list().addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (asked?.rows.length) pick((asked.sel + (e.key === 'ArrowDown' ? 1 : -1) + asked.rows.length) % asked.rows.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      run();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      closePptx();
    }
  });
  box().addEventListener('mousedown', (e) => { if (e.target === box()) closePptx(); });
}
