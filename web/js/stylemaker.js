// 내 스타일 만들기 (D211): 지금 스타일을 바탕으로 글꼴·크기·색·목록 칸 몇 개를 고르고, 설정 폴더 styles 에 CSS 파일 하나로 저장한다.
//
// - 고르는 대로 문서에 입혀 본다 — :root 에 얹는 미리보기 <style>(#lec-stylemaker-preview, 내 스타일 css 보다 뒤). 닫거나 저장하면 뗀다.
// - 칸은 각 스타일이 이미 쓰는 변수 열하나 (--md-* 와 목록 수준 강조 D210 의 두 값). 바꾼 칸만 저장한다 — 나머지는 바탕 스타일을 따른다.
// - 저장은 서버가 값만 받아 CSS 를 짓는다 (styles.save_made — 글꼴 이름·#색·범위 안의 숫자만). 새 파일 하나, 같은 이름이 있으면 만들지 않는다.
// - 이 창이 만든 스타일(maker)을 고른 채 열면 그 값을 불러와 고친다 — 저장할 때 물은 뒤 그 파일을, 그사이 바뀌었으면 쓰지 않는다.
//   손이나 AI 로 쓴 내 스타일은 고치지 않는다: 그 규칙을 새 파일에 옮겨 담고 그 위에 값을 얹어 새 이름으로 (copy).
// - 글꼴은 PC 에 있는 것만 (D26): 흔한 글꼴 가운데 이 PC 에 있는 것을 캔버스로 재어 보이고, 직접 적을 수도 있다.

import { on } from './store.js';
import { getJSON, postJSON } from './api.js';
import { $, toast } from './util.js';
import { html, setHtml } from './html.js';
import { t } from './i18n.js';
import { resolvedTheme, themeOf, userStyleOf, useStyle } from './theme.js';

const box = () => $('#lec-stylemaker');
const PREVIEW_ID = 'lec-stylemaker-preview';

/** 칸 — 각 스타일이 :root 에 정하는 변수 (서버 styles.MAKER_VARS 와 같은 열하나 — tests/test_styles_made.py) */
const FIELDS = [
  { key: '--md-font', group: 'font', label: t('본문'), kind: 'font' },
  { key: '--md-heading-font', group: 'font', label: t('제목'), kind: 'font' },
  { key: '--md-size', group: 'size', label: t('글자'), kind: 'px', min: 12, max: 24, step: 0.5 },
  { key: '--md-line', group: 'size', label: t('줄 간격'), kind: 'num', min: 1.2, max: 2.4, step: 0.05 },
  { key: '--md-width', group: 'size', label: t('폭'), kind: 'px', min: 560, max: 1400, step: 10 },
  { key: '--md-fg', group: 'color', label: t('글자'), kind: 'color' },
  { key: '--md-heading', group: 'color', label: t('제목'), kind: 'color' },
  { key: '--md-link', group: 'color', label: t('링크·강조'), kind: 'color' },
  { key: '--md-th-bg', group: 'color', label: t('표 머리'), kind: 'color' },
  { key: '--lec-list-top-weight', group: 'list', label: t('맨 위 항목'), kind: 'weight' },
  { key: '--lec-list-top-scale', group: 'list', label: t('크기'), kind: 'percent', min: 100, max: 120, step: 1 },
];
const GROUPS = [['font', t('글꼴')], ['size', t('크기')], ['color', t('색')], ['list', t('목록')]];
const WEIGHTS = [[400, t('보통')], [650, t('조금 진하게')], [700, t('진하게')]];
/** 흔한 글꼴 [CSS 이름, 보이는 이름] — 이 PC 에 있는 것만 목록에 (installed) */
const FONTS = [
  ['Malgun Gothic', t('맑은 고딕')], ['Batang', t('바탕')], ['Dotum', t('돋움')], ['Gulim', t('굴림')], ['Gungsuh', t('궁서')],
  ['NanumGothic', t('나눔고딕')], ['NanumMyeongjo', t('나눔명조')], ['NanumBarunGothic', t('나눔바른고딕')], ['NanumSquare', t('나눔스퀘어')],
  ['Noto Sans KR', 'Noto Sans KR'], ['Noto Serif KR', 'Noto Serif KR'], ['Pretendard', 'Pretendard'], ['Spoqa Han Sans Neo', 'Spoqa Han Sans Neo'],
  ['HCR Batang', t('함초롬바탕')], ['HCR Dotum', t('함초롬돋움')], ['KoPubBatang', t('KoPub 바탕')], ['KoPubDotum', t('KoPub 돋움')], ['MaruBuri', t('마루 부리')],
  ['Segoe UI', 'Segoe UI'], ['Arial', 'Arial'], ['Calibri', 'Calibri'], ['Cambria', 'Cambria'], ['Georgia', 'Georgia'], ['Times New Roman', 'Times New Roman'],
];
const OWN = '__own';   // 글꼴 목록의 '직접 적기…'

/**
 * 지금 연 창의 상태
 * @type {{ base: string, dark: boolean, file?: string, stamp?: string, copy?: string, name: string,
 *   start: Record<string, any>, values: Record<string, any>, touched: Set<string>, loaded?: Set<string>, ask: boolean } | null}
 */
let made = null;
let fontList = null;   // 이 PC 에 있는 FONTS (처음 열 때 한 번 잰다)

/** 이 PC 에 그 글꼴이 있는지 — 없으면 대신 쓰는 글꼴과 폭이 같다 (세 바탕 글꼴 중 하나라도 다르면 있다) */
function installed(family) {
  const ctx = document.createElement('canvas').getContext('2d');
  if (!ctx) return true;
  const text = 'mmmwwwlli 가나다라 한글 ABC 123';   // i18n-ok (글꼴을 재는 글)
  return ['monospace', 'serif', 'sans-serif'].some((generic) => {
    ctx.font = `40px ${generic}`;
    const plain = ctx.measureText(text).width;
    ctx.font = `40px "${family}", ${generic}`;
    return ctx.measureText(text).width !== plain;
  });
}

/** 글꼴 목록의 첫 이름 — 따옴표를 뗀 */
const firstFamily = (stack) => (stack.split(',')[0] || '').trim().replace(/^["']|["']$/g, '');
/** 첫 이름을 바꾼 글꼴 목록 — 뒤의 대신 쓸 글꼴은 그대로 (그 글꼴이 없는 PC 에서도 한글이 보이게 — D26) */
function withFirst(stack, family) {
  const rest = stack.split(',').slice(1).join(',').trim();
  return `"${family.replace(/["\\]/g, '')}"${rest ? `, ${rest}` : ', sans-serif'}`;
}

/** 색 글을 #rrggbb 로 (캔버스가 풀어 준다) */
function hexColor(value) {
  const ctx = document.createElement('canvas').getContext('2d');
  if (!ctx) return '#000000';
  ctx.fillStyle = '#000000';
  ctx.fillStyle = value || '#000000';
  const got = String(ctx.fillStyle);
  return /^#[0-9a-f]{6}$/i.test(got) ? got.toLowerCase() : '#000000';
}

/** 바탕 스타일(과 지금 입힌 내 스타일)의 값 — 미리보기를 떼고 읽는다 */
function currentValues() {
  document.getElementById(PREVIEW_ID)?.remove();
  const css = getComputedStyle(document.documentElement);
  const got = {};
  for (const f of FIELDS) {
    const raw = css.getPropertyValue(f.key).trim();
    if (f.kind === 'font') got[f.key] = raw;
    else if (f.kind === 'color') got[f.key] = hexColor(raw);
    else if (f.kind === 'weight') {
      const n = raw === 'normal' ? 400 : raw === 'bold' ? 700 : Number(raw) || 650;
      got[f.key] = WEIGHTS.map(([w]) => w).reduce((a, w) => (Math.abs(w - n) < Math.abs(a - n) ? w : a));
    }
    else got[f.key] = parseFloat(raw) || (f.kind === 'percent' ? 1.05 : f.min);
  }
  return got;
}

/** 저장할 값 (바꾼 칸만) */
const chosen = () => Object.fromEntries(FIELDS.filter((f) => made.touched.has(f.key)).map((f) => [f.key, made.values[f.key]]));

/** CSS 의 값 글 — 서버(styles._value)와 같은 모양 */
function cssValue(f, v) {
  if (f.kind === 'px') return `${v}px`;
  return String(v);
}

/** 고른 값을 문서에 입혀 본다 */
function preview() {
  let style = document.getElementById(PREVIEW_ID);
  if (!style) {
    style = document.createElement('style');
    style.id = PREVIEW_ID;
    document.head.appendChild(style);   // 맨 뒤 — 바탕·내 스타일보다 늦게 읽혀 이긴다
  }
  const lines = FIELDS.filter((f) => made.touched.has(f.key)).map((f) => `  ${f.key}: ${cssValue(f, made.values[f.key])};`);
  style.textContent = `:root {\n${lines.join('\n')}\n}`;
  contrastNote();
}

/** 상대 밝기 (WCAG) */
function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** 고른 글자색이 바탕과 대비가 낮으면 알린다 — 4.5:1 (WCAG, 작성 안내 web/help/styles.md 와 같은 기준). 저장은 막지 않는다 */
function contrastNote() {
  const bg = hexColor(getComputedStyle(document.documentElement).getPropertyValue('--md-bg').trim());
  const low = FIELDS.filter((f) => f.kind === 'color' && f.key !== '--md-th-bg' && made.touched.has(f.key)).map((f) => {
    const [a, b] = [luminance(made.values[f.key]), luminance(bg)].sort((x, y) => y - x);
    return [f.label, (a + 0.05) / (b + 0.05)];
  }).filter(([, r]) => r < 4.5);
  message(low.length ? t('{what} 색은 바탕과의 대비가 {r}:1 입니다 — 4.5:1 이상이어야 읽기 좋습니다', { what: low[0][0], r: low[0][1].toFixed(1) }) : '');
}

function fontField(f) {
  const stack = made.values[f.key] || '';
  const first = firstFamily(stack);
  const known = fontList.find(([css]) => css.toLowerCase() === first.toLowerCase());
  const cur = made.touched.has(f.key) ? (known ? known[0] : OWN) : '';
  return html`<label class="sm-field"><span>${f.label}</span><select data-key="${f.key}">
    <option value="" ${cur === '' ? 'selected' : ''}>${t('지금 글꼴')} (${first || '—'})</option>
    ${fontList.map(([css, name]) => html`<option value="${css}" ${cur === css ? 'selected' : ''} style="font-family: &quot;${css}&quot;">${name}</option>`)}
    <option value="${OWN}" ${cur === OWN ? 'selected' : ''}>${t('직접 적기…')}</option></select>
    <input type="text" class="sm-own" data-own="${f.key}" spellcheck="false" autocomplete="off" placeholder="${t('글꼴 이름')}" value="${cur === OWN ? first : ''}" ${cur === OWN ? '' : 'hidden'}></label>`;
}

function field(f) {
  const v = made.values[f.key];
  if (f.kind === 'font') return fontField(f);
  if (f.kind === 'color') return html`<label class="sm-field sm-color"><span>${f.label}</span><input type="color" data-key="${f.key}" value="${v}"></label>`;
  if (f.kind === 'weight') {
    return html`<label class="sm-field"><span>${f.label}</span><select data-key="${f.key}">${WEIGHTS.map(([w, name]) => html`<option value="${w}" ${w === v ? 'selected' : ''}>${name}</option>`)}</select></label>`;
  }
  const shown = f.kind === 'percent' ? Math.round(v * 100) : v;
  const unit = f.kind === 'px' ? 'px' : f.kind === 'percent' ? '%' : '';
  return html`<label class="sm-field"><span>${f.label}</span><input type="number" data-key="${f.key}" min="${f.min}" max="${f.max}" step="${f.step}" value="${shown}">${unit ? html`<i>${unit}</i>` : ''}</label>`;
}

function render() {
  const user = made.file ? t("'{name}' 고치기", { name: made.name }) : t('바탕: {name}', { name: themeOf(made.base)?.name || made.base });
  setHtml($('#lec-stylemaker-sub'), [user, made.copy ? html` <small>${t('(직접 쓴 스타일 — 그 규칙을 새 파일에 옮겨 담습니다)')}</small>` : '']);
  setHtml($('#lec-stylemaker-fields'), GROUPS.map(([g, name]) => html`<fieldset class="sm-group"><legend>${name}</legend>${FIELDS.filter((f) => f.group === g).map(field)}</fieldset>`));
  $('#lec-stylemaker-name').value = made.name;
  $('#lec-stylemaker-ask').hidden = true;
  $('#lec-stylemaker-form').hidden = false;
  message('');
}

function message(text) {
  const msg = $('#lec-stylemaker-msg');
  msg.textContent = text;
  msg.hidden = !text;
}

/** 칸을 바꾸면 값에 담고 미리 본다 */
function onInput(e) {
  const el = /** @type {HTMLInputElement | HTMLSelectElement} */ (e.target);
  const key = el.dataset.key || el.dataset.own;
  const f = FIELDS.find((x) => x.key === key);
  if (!f || !made) return;
  if (f.kind === 'font') {
    const sel = /** @type {HTMLSelectElement} */ (box().querySelector(`select[data-key="${key}"]`));
    const own = /** @type {HTMLInputElement} */ (box().querySelector(`input[data-own="${key}"]`));
    own.hidden = sel.value !== OWN;
    const family = sel.value === OWN ? own.value.trim() : sel.value;
    if (e.target === sel && sel.value === OWN) own.focus();
    if (!family || /[;{}()\\<>@/*:!]/.test(family)) {   // 비었거나 쓸 수 없는 글자 — 지금 글꼴로
      made.values[key] = made.start[key];
      if (made.loaded?.has(key)) made.touched.add(key);
      else made.touched.delete(key);
    } else {
      made.values[key] = withFirst(made.start[key], family);
      made.touched.add(key);
    }
  } else if (f.kind === 'color') {
    made.values[key] = el.value.toLowerCase();
    made.touched.add(key);
  } else {
    const n = Number(el.value);
    if (!Number.isFinite(n)) return;
    const v = f.kind === 'percent' ? Math.round(n) / 100 : n;
    const [lo, hi] = f.kind === 'percent' ? [f.min / 100, f.max / 100] : f.kind === 'weight' ? [400, 800] : [f.min, f.max];
    if (v < lo || v > hi) return;   // 범위 밖은 칸만 (저장하지 않는다)
    made.values[key] = v;
    made.touched.add(key);
  }
  preview();
}

/** 열기 — 지금 스타일이 이 창이 만든 내 스타일이면 그 값을 불러온다 */
export async function openStyleMaker() {
  if (!fontList) fontList = FONTS.filter(([css]) => installed(css));
  const id = resolvedTheme();
  const user = userStyleOf(id);
  const start = currentValues();
  made = { base: id, dark: !!themeOf(id)?.dark, name: '', start, values: { ...start }, touched: new Set(), ask: false };
  if (user) {
    made.base = user.base;
    made.dark = !!user.dark;
    let got = null;
    if (user.maker) {
      try {
        got = await getJSON(`/api/styles/made?file=${encodeURIComponent(user.file)}`);
      } catch { /* 그사이 손으로 고쳐 머리가 바뀌었으면 — 손으로 쓴 스타일처럼 */ }
    }
    if (got) {
      Object.assign(made, { file: got.file, stamp: got.stamp, name: got.name, base: got.base, dark: !!got.dark });
      made.loaded = new Set(Object.keys(got.values));
      for (const [k, v] of Object.entries(got.values)) {
        made.values[k] = FIELDS.find((f) => f.key === k)?.kind === 'color' ? hexColor(v) : v;
        made.touched.add(k);
      }
    } else {
      made.copy = user.file;
    }
  }
  render();
  box().hidden = false;
  /** @type {HTMLElement} */ (box().querySelector('select, input')).focus();
}

export function closeStyleMaker() {
  if (box().hidden) return false;
  box().hidden = true;
  document.getElementById(PREVIEW_ID)?.remove();
  made = null;
  return true;
}

/** 저장 — 고칠 때는 먼저 묻는다 (asked = 물은 뒤 '바꾸기') */
async function save(replace) {
  if (!made) return;
  const name = $('#lec-stylemaker-name').value.trim();
  if (!name) {
    message(t('스타일 이름을 적으세요'));
    $('#lec-stylemaker-name').focus();
    return;
  }
  if (made.file && replace === undefined) {   // 이 창이 만든 파일 — 바꿀지, 새 스타일로 둘지 묻는다
    $('#lec-stylemaker-question').textContent = t("'{name}' 스타일 파일을 이 값으로 바꿀까요?", { name: made.name });
    $('#lec-stylemaker-form').hidden = true;
    $('#lec-stylemaker-ask').hidden = false;
    $('#lec-stylemaker-replace').focus();
    return;
  }
  const req = { name, base: made.base, dark: made.dark, values: chosen() };
  if (replace) Object.assign(req, { file: made.file, stamp: made.stamp });
  else if (made.copy) req.copy = made.copy;
  let got;
  try {
    got = await postJSON('/api/styles/made', req);
  } catch (err) {
    $('#lec-stylemaker-ask').hidden = true;
    $('#lec-stylemaker-form').hidden = false;
    message(err.message || String(err));
    return;
  }
  closeStyleMaker();
  await useStyle(got.id);
  toast(t("내 스타일 '{name}' 을 저장했습니다 — 스타일 목록 맨 아래 '내 스타일'에 있습니다", { name }));
}

export function initStyleMaker() {
  on('open-style-maker', () => openStyleMaker());
  on('theme-chosen', () => closeStyleMaker());   // 다른 스타일을 고르면 미리보기를 걷는다
  const el = box();
  el.addEventListener('input', onInput);
  el.addEventListener('change', onInput);
  el.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      closeStyleMaker();
    } else if (e.key === 'Enter' && e.target === $('#lec-stylemaker-name')) {
      e.preventDefault();
      save();
    }
  });
  $('#lec-stylemaker-save').addEventListener('click', () => save());
  $('#lec-stylemaker-cancel').addEventListener('click', closeStyleMaker);
  $('#lec-stylemaker-close').addEventListener('click', closeStyleMaker);
  $('#lec-stylemaker-replace').addEventListener('click', () => save(true));
  $('#lec-stylemaker-new').addEventListener('click', () => {   // 새 스타일로 — 이름을 바꿔 저장 (같은 이름이면 서버가 거절한다)
    $('#lec-stylemaker-ask').hidden = true;
    $('#lec-stylemaker-form').hidden = false;
    made.copy = made.file;   // 그 파일의 옮겨 담은 규칙은 새 파일에도 (서버가 그 파일의 값 칸은 빼고 옮긴다)
    made.file = undefined;
    $('#lec-stylemaker-name').select();
    message(t('새 이름을 적고 저장을 누르세요'));
  });
  $('#lec-stylemaker-back').addEventListener('click', () => {
    $('#lec-stylemaker-ask').hidden = true;
    $('#lec-stylemaker-form').hidden = false;
  });
}
