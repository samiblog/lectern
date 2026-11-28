// 도해 고르기 창 (D214): 그림 우클릭 '도해 스타일…'·'색 조합…'. 이름만 보고는 번호가 어떤 모양인지 모른다 — 그 그림을 번호마다 작게 그려
// 나란히 보인다 (견본이 아니라 그 그림 그대로). 고르면 그 블록의 표시 줄 하나를 쓴다 — 쓰는 일은 docmenu 가 넘긴 save 가 한다
// (원문이 메뉴를 연 뒤 바뀌었으면 쓰지 않는다). docmenu 는 이 창을 부르지 않고 'diagram-pick' 을 알린다 — doc.js 가 docmenu 를 불러서,
// 여기서 doc.js(정화·링크)를 부르면 import 가 돈다.

import { on, emit } from './store.js';
import { getJSON } from './api.js';
import { renderMermaid } from './mermaid.js';
import { renderCharts } from './charts.js';
import { sanitizeHtml, resolveRef } from './doc.js';
import { diagramStyles, diagramColors, setMark, setMyDiagrams, myDiagrams, makePrompt, DIAGRAM_SAMPLES } from './diagramstyles.js';
import { $, $$, lineRef } from './util.js';
import { uncolorPrompt } from './aitool.js';
import { html, setHtml } from './html.js';
import { t } from './i18n.js';

const box = () => $('#lec-dpick');
const grid = () => $('#lec-dpick-grid');
/** @type {any} 지금 연 것 — 'diagram-pick' 의 값 */
let cur = null;
let seq = 0;

const listOf = (key) => (key === 'style' ? diagramStyles() : diagramColors());
const named = (key, n) => {
  const s = listOf(key).find((x) => x.n === n);
  return s ? `${n} ${s.name}` : String(n || '');
};

/** 견본 문서를 예제 가이드 창에서 연다 */
const openSamples = (key) => emit('open-sample', DIAGRAM_SAMPLES[key === 'colors' ? 'colors' : 'style']);

// ---- 내 도해 스타일·내 색 조합 (D215) — 설정 폴더 diagram-styles 의 파일. 처음(main.js)과 3초마다 바뀌었는지 --------------------
const MY_POLL_MS = 3000;
let mySig = '';

/** 받는다. 바뀌었으면 true (처음 받은 것도) */
export async function loadMyDiagrams() {
  try {
    const d = await getJSON('/api/diagram-styles');
    const sig = JSON.stringify(d);
    if (sig === mySig) return false;
    mySig = sig;
    setMyDiagrams(d);
    return true;
  } catch {
    return false;
  }
}

/** 파일이 생기거나 고쳐지거나 지워졌으면 — 문서를 다시 그리고(그 번호를 쓰는 그림) 설정 창의 목록을 고친다 */
async function syncMyDiagrams() {
  if (document.hidden) return;
  if (!(await loadMyDiagrams())) return;
  emit('my-diagrams');
  emit('refresh-view');
}

/**
 * 연다. p: {key: 'style' | 'colors', kind: 'mermaid' | 'dot' | 'chart', chart (pre.lec-chart 의 data-chart), body (여는·닫는 줄을 뺀 블록의 줄),
 * now (지금 그린 번호), own (블록에 적힌 번호, 없으면 0), base (줄을 지우면 따를 번호), fromDoc (문서의 기본 줄 — 그릴 때 함께), save(nextBody, done), tab, path,
 * lines ([여는 줄, 닫는 줄] — 내 것 만들기 요청의 자리), ai (쓰는 AI 도구의 이름)}
 */
async function openPick(p) {
  cur = p;
  const my = ++seq;
  if (await loadMyDiagrams()) {   // Claude 가 방금 저장한 내 것도 — 3초마다 보기를 기다리지 않고 (D215, 시나리오가 찾은 것)
    emit('my-diagrams');
    emit('refresh-view');
  }
  if (my !== seq) return;
  const isStyle = p.key === 'style';
  $('#lec-dpick-same').hidden = true;
  $('#lec-dpick-uncolor').hidden = true;
  $('#lec-dpick-title').textContent = isStyle ? t('도해 스타일 — 이 그림') : t('색 조합 — 이 그림');
  const follow = $('#lec-dpick-follow');
  follow.hidden = !p.own;
  follow.title = t('이 그림의 표시 줄에서 지웁니다');
  follow.textContent = p.fromDoc?.[p.key] ? t('문서의 기본 따르기 (지금 {n})', { n: named(p.key, p.base) }) : t('설정 따르기 (지금 {n})', { n: named(p.key, p.base) });
  $('#lec-dpick-default').textContent = isStyle ? t('기본 도해 스타일 바꾸기…') : t('기본 색 조합 바꾸기…');
  $('#lec-dpick-default').title = t('설정 창 — 표시 줄이 없는 그림 모두');
  $('#lec-dpick-samples').textContent = isStyle ? t('모양 견본 모두 보기') : t('색 조합 견본 모두 보기');
  const make = $('#lec-dpick-make');
  make.hidden = !p.lines;
  make.textContent = isStyle ? t('이 모양으로 내 도해 스타일 만들기…') : t('이 색으로 내 색 조합 만들기…');
  make.title = t('{ai} 에게 이 그림으로 내 것을 만들어 달라는 요청 — 터미널에 (Enter 는 누르지 않음). 만들면 이 창에 {n}번으로 나옵니다',
    { ai: p.ai || 'Claude', n: isStyle ? myDiagrams().next.style : myDiagrams().next.colors });
  const list = listOf(p.key);
  setHtml(grid(), list.map((s) => {
    const here = s.n === p.now;
    return html`<div class="dpick-card${here ? ' on' : ''}" role="option" tabindex="${here ? '0' : '-1'}" aria-selected="${here ? 'true' : 'false'}" data-n="${s.n}" title="${s.tip}">
      <div class="dpick-stage"></div><div class="dpick-name"><b>${s.n}</b> ${s.name}${here ? html`<i>${t('지금')}</i>` : ''}${s.mine ? html`<em>${t('내 것')}</em>` : ''}</div></div>`;
  }));
  if (!$('.dpick-card.on', grid())) $('.dpick-card', grid())?.setAttribute('tabindex', '0');
  for (const card of /** @type {HTMLElement[]} */ ($$('.dpick-card', grid()))) {
    const pre = document.createElement('pre');
    if (p.kind === 'mermaid') pre.className = 'mermaid';
    else {
      pre.className = 'lec-chart';
      pre.dataset.chart = p.chart;
    }
    pre.textContent = setMark(p.body, p.kind, p.key, Number(card.dataset.n)).join('\n');   // 그 번호의 표시 줄을 적은 원문 — 문서 파일은 그대로
    card.querySelector('.dpick-stage').append(pre);
  }
  box().hidden = false;
  tip(/** @type {HTMLElement} */ ($('.dpick-card.on', grid()) || $('.dpick-card', grid())));
  /** @type {HTMLElement} */ ($('.dpick-card[tabindex="0"]', grid()))?.focus();
  try {
    if (p.kind === 'mermaid') await renderMermaid(grid(), p.fromDoc);
    else await renderCharts(grid(), { tab: p.tab, path: p.path, sanitize: sanitizeHtml, resolveRef, marks: p.fromDoc });
  } catch { /* 그리지 못한 칸은 각자 까닭을 보인다 */ }
  if (my !== seq) return;
  sameNote(p);
  for (const svg of /** @type {SVGSVGElement[]} */ ($$('.dpick-stage svg:not(svg svg)', grid()))) fit(svg);
  layout();
  grid().classList.add('dpick-done');
}

// ---- 원문이 정한 색·모양 — 고른 번호보다 먼저라 그대로 남는다 (0.113.2: 몇째 줄의 무엇인지 알리고, AI 에 빼 달라는 요청을 넣는다) ----
const HEX = /#(?:[\da-f]{3}|[\da-f]{6}|[\da-f]{8})\b/i;   // '#2024년' 같은 네 자리는 색이 아니다
const FUNC = /\b(?:rgba?|hsla?)\s*\(/i;
const SCHEME = /["']?(?:scheme|colorscale|colorway)["']?\s*:\s*["']?[a-z]/i;   // 이름 붙은 색표 (Vega 의 scheme, Plotly 의 colorscale)
const NAMED = /["']?([a-z_-]*(?:colou?r|fill|stroke)|value)["']?\s*[:=]\s*["']?([a-z]+)\b/gi;   // "color": "red", fillcolor=red, fill:red
const NOT_COLOR = /^(transparent|currentcolor|inherit|initial|unset|none|auto)$/i;
const MERMAID_THEME = /%%\{.*\b(?:theme|themeVariables)\b/;   // init 의 sequence·flowchart 같은 배치 설정은 색이 아니다
const MERMAID_LOOK = /^\s*(?:classDef|style|linkStyle)\s|%%\{.*\b(?:theme|themeVariables|themeCSS|look)\b|^\s*(?:theme|look|themeVariables)\s*:/;
const DOT_LOOK = /\b(?:node|edge)\s*\[[^\]]*\b(?:style|penwidth|fontname)\s*=/;   // node [shape=box] 는 도해 스타일과 같은 모양이다

/** 색 이름인지 — 'toself'(Plotly 의 채우기 방법) 같은 것은 아니다 */
const isColorWord = (w) => !NOT_COLOR.test(w) && typeof CSS !== 'undefined' && CSS.supports('color', w);

/** 그 줄에서 원문이 색을 정한 자리 — 없으면 -1 */
function colorAt(line, kind) {
  const at = [];
  for (const re of [HEX, FUNC, ...(kind === 'chart' ? [SCHEME] : []), ...(kind === 'mermaid' ? [MERMAID_THEME] : [])]) {
    const m = re.exec(line);
    if (m) at.push(m.index);
  }
  for (const m of line.matchAll(NAMED)) {
    if (m[1].toLowerCase() === 'value' && kind !== 'chart') continue;
    if (isColorWord(m[2])) {
      at.push(m.index);
      break;
    }
  }
  return at.length ? Math.min(...at) : -1;
}

const CLIP = 64;

/** 알림에 보일 그 줄 — 길면 그 자리(at)를 가운데에 두고 자른다 */
function clipAt(line, at) {
  const s = line.trim();
  if (s.length <= CLIP) return s;
  const i = Math.max(0, Math.min(at - (line.length - line.trimStart().length) - 24, s.length - CLIP));
  return `${i > 0 ? '…' : ''}${s.slice(i, i + CLIP)}${i + CLIP < s.length ? '…' : ''}`;
}

/**
 * 원문이 정한 것 — 처음 찾은 줄 {i: body 의 몇째(0부터), text}. key 가 'style' 이면 모양을 정한 줄(classDef·style·init 의 theme·look, Graphviz 의 node [style=…])도.
 * 표시 줄(// 색: 2 …)은 색 글자를 쓰지 않는다
 */
function ownLook(body, kind, key) {
  for (let i = 0; i < body.length; i++) {
    const line = body[i];
    const at = colorAt(line, kind);
    const look = key === 'style' && ((kind === 'mermaid' && MERMAID_LOOK.exec(line)) || (kind === 'dot' && DOT_LOOK.exec(line)));
    if (at >= 0 || look) return { i, text: clipAt(line, at >= 0 ? at : look.index) };
  }
  return null;
}

/**
 * 칸에 그린 모양 — 색·선·모서리·그림자, 도해는 크기(간격)도. 칸마다 같으면 이 그림은 그 번호들을 따르지 않는다.
 * 차트는 칸 폭에 맞춰 그려 칸마다 1px 씩 다를 수 있어 크기를 보지 않는다
 */
function lookOf(card, kind) {
  const svg = card.querySelector('.dpick-stage svg');
  if (!svg) return null;
  const parts = [kind === 'chart' ? '' : svg.getAttribute('viewBox') || ''];
  let k = 0;
  for (const el of svg.querySelectorAll('path, rect, circle, ellipse, polygon, polyline, line, image, stop')) {
    if (++k > 1500) break;
    if (el.tagName === 'image') {   // Plotly 의 열지도는 PNG 로 들어온다
      parts.push(el.getAttribute('href') || el.getAttribute('xlink:href') || '');
      continue;
    }
    const st = getComputedStyle(el);
    if (el.tagName === 'stop') {   // 그러데이션(색 막대·범례)의 색
      parts.push(st.stopColor);
      continue;
    }
    // url(#칸마다-다른-id) 는 이름만 — 가리키는 그러데이션의 색은 stop 이 본다
    parts.push([st.fill, st.stroke, st.strokeWidth, st.strokeDasharray, st.filter, st.getPropertyValue('rx')].join(',').replace(/url\([^)]*\)/g, 'url'));
  }
  return parts.join(';');
}

/**
 * 칸이 모두 같게 그려졌으면 까닭을 창 위에 — 원문이 색을 정한 차트, 오름·내림 색이 정해진 차트(캔들·폭포) 등.
 * 고를 수는 있다 (표시 줄은 남고, 원문의 색을 지우면 그 번호를 따른다). 0.113.1 — 말없이 여덟 칸이 같아 '바뀌지 않는다'로 보였다
 */
function sameNote(p) {
  const note = $('#lec-dpick-same');
  const ask = $('#lec-dpick-uncolor');
  const looks = /** @type {HTMLElement[]} */ ($$('.dpick-card', grid())).map((card) => lookOf(card, p.kind));
  const same = looks.length > 1 && looks.every((x) => x != null && x === looks[0]);
  const own = ownLook(p.body, p.kind, p.key);
  note.hidden = !same && !own;
  ask.hidden = !own || !p.lines;
  if (note.hidden) return;
  const style = p.key === 'style';
  note.classList.toggle('soft', !same);   // 칸은 갈리지만 원문이 정한 것은 남는다
  const where = own ? { line: p.lines ? p.lines[0] + 1 + own.i : own.i + 1, text: own.text } : null;
  $('#lec-dpick-same-text').textContent = !same
    ? (style ? t('원문이 정한 모양·색은 그대로 남습니다 — {line}째 줄 {text}', where) : t('원문이 정한 색은 그대로 남습니다 — {line}째 줄 {text}', where))
    : where
      ? (style ? t('칸이 모두 같습니다 — 원문이 모양·색을 정해 두어({line}째 줄 {text}) 도해 스타일을 따르지 않습니다', where)
        : t('칸이 모두 같습니다 — 원문이 색을 정해 두어({line}째 줄 {text}) 색 조합을 따르지 않습니다', where))
      : style ? t('칸이 모두 같습니다 — 이 종류의 그림은 도해 스타일을 따르지 않습니다')
        : p.kind !== 'chart' ? t('칸이 모두 같습니다 — 이 종류의 그림은 색 조합을 따르지 않습니다')
          : t('칸이 모두 같습니다 — 이 종류의 차트는 정해진 색을 써서(캔들·폭포의 오름·내림 색 등) 색 조합을 따르지 않습니다');
  ask.textContent = style ? t('{ai} 에 모양·색 지정 빼기 요청', { ai: p.ai || 'Claude' }) : t('{ai} 에 색 지정 빼기 요청', { ai: p.ai || 'Claude' });
  ask.title = t('원문이 정한 것을 빼 달라는 요청 — 터미널에 (Enter 는 누르지 않음). 빼면 고른 번호를 따릅니다');
}

/**
 * 열 수와 칸 높이 — 그림이 가장 크게 보이게. 가로로 긴 그림(flowchart LR)은 넓은 칸 몇 줄, 세로로 긴 그림은 좁고 높은 칸.
 * 한 화면에 다 들어가는 쪽을 앞세운다 (견주어 보려고 여는 창이다)
 */
function layout() {
  const g = grid();
  const sizes = /** @type {SVGSVGElement[]} */ ($$('.dpick-stage svg:not(svg svg)', g))
    .map((svg) => (svg.getAttribute('viewBox') || '').split(/[\s,]+/).map(Number).slice(2)).filter((v) => v[0] > 0 && v[1] > 0);
  if (!sizes.length) return;
  const w = Math.max(...sizes.map((v) => v[0]));
  const h = Math.max(...sizes.map((v) => v[1]));
  const n = $$('.dpick-card', g).length;
  const GAP = 10;
  const PAD = 16;   // 칸 안의 여백 (위아래·좌우)
  const LABEL = /** @type {HTMLElement} */ ($('.dpick-name', g))?.offsetHeight || 31;
  const width = g.clientWidth - 4;
  const room = window.innerHeight * 0.94 - 24 - (/** @type {HTMLElement} */ (g.closest('.dialog-box')).offsetHeight - g.offsetHeight) - 4;   // 창의 머리·설명·단추를 뺀 높이
  let best = null;
  for (let cols = 2; cols <= 6; cols++) {
    const cw = (width - GAP * (cols - 1)) / cols - PAD;
    if (cw < 140 && best) break;
    const rows = Math.ceil(n / cols);
    const sh = Math.min(260, Math.max(80, (room - rows * (LABEL + GAP + 2)) / rows - PAD));
    const all = rows * (sh + PAD + LABEL + GAP + 2) <= room + 1;
    const score = Math.min(cw / w, sh / h, 1) * (all ? 1 : 0.6);
    if (!best || score > best.score + 1e-6) best = { cols, sh, score };
  }
  g.style.gridTemplateColumns = `repeat(${best.cols}, minmax(0, 1fr))`;
  g.style.setProperty('--dpick-h', `${Math.round(best.sh + PAD)}px`);
}

/** 칸에 맞게 — 크게는 늘리지 않고 줄이기만 (viewBox 가 있어야 비율을 지킨다) */
function fit(svg) {
  if (!svg.getAttribute('viewBox')) {
    const w = parseFloat(svg.getAttribute('width'));
    const h = parseFloat(svg.getAttribute('height'));
    if (w && h) svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  }
  const vb = (svg.getAttribute('viewBox') || '').split(/[\s,]+/).map(Number);
  svg.style.width = '100%';
  svg.style.height = '100%';
  svg.style.maxWidth = vb[2] ? `${vb[2]}px` : '';
  svg.style.maxHeight = vb[3] ? `${vb[3]}px` : '';
}

/** 아래 줄의 설명 — 마우스를 올리거나 키로 옮긴 칸 */
function tip(card) {
  if (!card || !cur) return;
  const s = listOf(cur.key).find((x) => x.n === Number(card.dataset.n));
  $('#lec-dpick-tip').textContent = s ? `${s.n} ${s.name} — ${s.tip}` : '';
}

export function closeDiagramPick() {
  if (!box() || box().hidden) return false;
  box().hidden = true;
  seq += 1;
  $('#lec-dpick-same').hidden = true;
  $('#lec-dpick-uncolor').hidden = true;
  grid().replaceChildren();   // 닫힌 창에 그때 스타일의 그림을 남기지 않는다
  grid().classList.remove('dpick-done');
  grid().style.gridTemplateColumns = '';
  grid().style.removeProperty('--dpick-h');
  cur = null;
  return true;
}

function choose(n) {
  const p = cur;
  if (!p) return;
  closeDiagramPick();
  if (n === p.own) return;   // 이미 그 번호가 적혀 있다
  const name = listOf(p.key).find((x) => x.n === n)?.name || '';
  p.save(setMark(p.body, p.kind, p.key, n), p.key === 'style' ? t('도해 스타일 {n} — {name}. Ctrl+Z 로 되돌립니다', { n, name })
    : t('색 조합 {n} — {name}. Ctrl+Z 로 되돌립니다', { n, name }));
}

/** 칸 사이를 키로 — ← → 하나씩, ↑ ↓ 한 줄씩 (격자의 열 수), Home·End */
function move(card, key) {
  const all = /** @type {HTMLElement[]} */ ($$('.dpick-card', grid()));
  const cols = getComputedStyle(grid()).gridTemplateColumns.split(' ').filter(Boolean).length || 1;
  const i = all.indexOf(card);
  const step = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: cols, ArrowUp: -cols }[key];
  const j = key === 'Home' ? 0 : key === 'End' ? all.length - 1 : Math.max(0, Math.min(all.length - 1, i + step));
  for (const c of all) c.setAttribute('tabindex', c === all[j] ? '0' : '-1');
  all[j].focus();
  tip(all[j]);
}

export function initDiagramPick() {
  on('diagram-pick', (p) => openPick(p));
  setInterval(syncMyDiagrams, MY_POLL_MS);
  grid().addEventListener('click', (e) => {
    const card = /** @type {HTMLElement} */ (e.target).closest?.('.dpick-card');
    if (card) choose(Number(card.dataset.n));
  });
  grid().addEventListener('mouseover', (e) => tip(/** @type {HTMLElement} */ (e.target).closest?.('.dpick-card')));
  grid().addEventListener('focusin', (e) => tip(/** @type {HTMLElement} */ (e.target).closest?.('.dpick-card')));
  grid().addEventListener('keydown', (e) => {
    const card = /** @type {HTMLElement} */ (e.target).closest?.('.dpick-card');
    if (!card) return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      choose(Number(card.dataset.n));
    } else if (['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) {
      e.preventDefault();
      move(card, e.key);
    }
  });
  $('#lec-dpick-follow').addEventListener('click', () => {
    const p = cur;
    if (!p) return;
    closeDiagramPick();
    p.save(setMark(p.body, p.kind, p.key, null), t('표시를 지웠습니다 — 기본으로 그립니다'));
  });
  $('#lec-dpick-samples').addEventListener('click', () => {
    const key = cur?.key;
    closeDiagramPick();
    openSamples(key);
  });
  $('#lec-dpick-make').addEventListener('click', () => {
    const p = cur;
    if (!p?.lines) return;
    closeDiagramPick();
    emit('term-paste', makePrompt(p.key, lineRef(p.path, p.lines)));   // 터미널에 붙여 넣기 (D51 — Enter 없이)
  });
  $('#lec-dpick-uncolor').addEventListener('click', () => {
    const p = cur;
    if (!p?.lines) return;
    closeDiagramPick();
    emit('term-paste', uncolorPrompt(lineRef(p.path, p.lines), p.key));   // 터미널에 붙여 넣기 (D51 — Enter 없이)
  });
  $('#lec-dpick-default').addEventListener('click', () => {
    closeDiagramPick();
    emit('open-settings', 'view');
  });
  $('#lec-dpick-close').addEventListener('click', closeDiagramPick);
  window.addEventListener('resize', () => { if (!box().hidden && grid().classList.contains('dpick-done')) layout(); });
  box().addEventListener('click', (e) => { if (e.target === box()) closeDiagramPick(); });   // 바깥을 누르면 닫기
}
