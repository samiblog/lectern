// html 로 전환 (D129): 상태줄의 'html 로 전환' — 슬라이드 창이 그린 장을 모아 impress.js 발표 html 하나를 짓고, 서버가 문서 옆에 새 파일로 쓴다.
//
// - 담는 것: 장(section)의 복제(앱 표시를 뗀다), 문서 폴더의 그림(data URI), 스타일(base·고른 스타일·내 스타일·코드 색·문서 style:·장별 CSS,
//   수식이 있으면 KaTeX 와 그 글꼴), 발표자 노트(.notes — impress 의 발표자 콘솔 P 가 읽는다), impress.js 본문. 숨긴 장은 넣지 않는다 (발표와 같다).
// - 자리: impresslayout.js — 격자·가로 한 줄과 장 주석의 impress:. 맨 끝에 전체 보기 장.
// - 안전: 받은 사람의 브라우저에서 스크립트가 도는 파일이다. 파일의 CSP 가 impress.js 와 시작 줄의 해시만 허용하고 연결·바깥 글꼴을 막는다.
//   그린 화면은 이미 DOMPurify 를 거쳤지만 스크립트·이벤트 속성·앱 안 링크를 여기서 한 번 더 걸러 낸다.
// - Lectern 에서 열면 스크립트가 돌지 않으므로(D27) impress-not-supported 그대로 — 장이 위에서 아래로 놓인 문서로 보인다 (폭에 맞춰 zoom).
// - 파일의 글은 esc 로 짓는다 — 화면에 넣는 것이 아니라 파일로 쓰는 글이다 (html.js).

import { S, emit } from './store.js';
import { getJSON, getText, postJSON } from './api.js';
import { $, $$, toast, dirname, basename, blockedReadOnly } from './util.js';
import { esc, html, setHtml } from './html.js';
import { t } from './i18n.js';
import { DECK_SCOPE, readYaml } from './slides.js';
import { splitFrontMatter } from './markdown.js';
import { layoutSteps, overviewOf, readMode, readSpot } from './impresslayout.js';

const IMPRESS = '/static/vendor/impress/impress.js';
// 시작 줄. impress 의 extras 플러그인은 window.markdown·hljs·mermaid 가 있으면 부른다 — 그 id 의 제목(## Mermaid)이 전역으로 잡히지 않게 비운다.
// Home·End 는 Lectern 발표 모드와 같게 첫 장·마지막(전체 보기) 장으로 (impress 의 기본 키에는 없다)
const INIT = [
  'window.markdown = window.hljs = window.mermaid = undefined;',
  'var lecImpress = impress(); lecImpress.init();',
  "document.addEventListener('keydown', function (e) {",
  "  if (e.ctrlKey || e.altKey || e.metaKey || (e.key !== 'Home' && e.key !== 'End')) return;",
  "  e.preventDefault(); lecImpress.goto(e.key === 'Home' ? 0 : document.querySelectorAll('#impress .step').length - 1);",
  '});',
].join('\n');
const DROP = 'script, iframe, object, embed, base, meta, link, form, button, video, audio, .lec-tag, .lec-slide-tags, .lec-slide-play';
const DROP_ATTRS = new Set(['data-lines', 'data-key', 'data-warn', 'data-issues', 'data-src', 'data-lec-href', 'data-lec-open', 'data-impress', 'contenteditable']);
const MARKS = ['lec-target', 'lec-changed', 'lec-picked', 'lec-cell-over', 'lec-cell-bad'];

const box = () => $('#lec-html');
let asked = null;   // {tab, pane, path, mode, items, hidden, w, h, busy, result}

function setMsg(text, bad = false) {
  const p = $('#lec-html-msg');
  p.hidden = !text;
  p.textContent = text;
  p.classList.toggle('bad', bad);
}

/** 칸에 그려진 장들 (숨긴 장은 뺀다): [{wrap, section, page, lead, spot}], 숨긴 장 수 */
function slidesOf(pane) {
  const wraps = $$(':scope > .lec-slide-wrap', pane.view);
  const shown = wraps.filter((w) => !w.classList.contains('lec-hidden') && w.querySelector('.lec-slide'));
  const items = shown.map((wrap) => {
    const section = wrap.querySelector('.lec-slide');
    return { wrap, section, page: Number(wrap.dataset.slide) || 0, lead: section.classList.contains('lead'), spot: readSpot(section.dataset.impress).spot };
  });
  return { items, hidden: wraps.length - shown.length };
}

/** 그 칸이 그린 문서의 맨 앞 설정 */
const frontOf = (pane) => readYaml(splitFrontMatter((pane.source?.lines || []).join('\n')).frontMatter || '');

const sizeOf = (section) => ({ w: parseFloat(section.style.width) || 1280, h: parseFloat(section.style.height) || 720 });

// ---- 창 ------------------------------------------------------------------------------------------

/** 배치 지도: 장 번호 상자를 고른 배치대로 — impress 를 돌리지 않고 앱이 그린다 */
function drawMap() {
  const { items, w, h, mode } = asked;
  const places = layoutSteps(items, { mode, w, h });
  const ov = overviewOf(places, { w, h });
  if (!ov) return setHtml($('#lec-html-map'), '');
  const [vw, vh] = [w * ov.scale, h * ov.scale];
  const view = [ov.x - vw / 2, ov.y - vh / 2, vw, vh].map((n) => Math.round(n)).join(' ');
  const boxes = places.map((p, i) => {
    const [bw, bh] = [w * p.scale, h * p.scale];
    const kind = Object.keys(items[i].spot).length ? 'placed' : items[i].lead ? 'lead' : '';
    return html`<g transform="rotate(${p.rotate} ${p.x} ${p.y})"><rect class="${kind}" x="${p.x - bw / 2}" y="${p.y - bh / 2}" width="${bw}" height="${bh}" rx="${h * 0.05}"></rect><text x="${p.x}" y="${p.y}" font-size="${bh * 0.42}">${i + 1}</text></g>`;
  });
  const path = places.map((p) => `${p.x},${p.y}`).join(' ');
  setHtml($('#lec-html-map'), html`<svg viewBox="${view}" preserveAspectRatio="xMidYMid meet"><polyline points="${path}"></polyline>${boxes}</svg>`);
}

function drawInfo() {
  const { items, hidden } = asked;
  const placed = items.filter((it) => Object.keys(it.spot).length).length;
  const parts = [t('{n}장', { n: items.length })];
  if (hidden) parts.push(t('숨긴 장 {n}개는 넣지 않습니다', { n: hidden }));
  if (placed) parts.push(t('자리를 적은 장 {n}개 (impress: 주석)', { n: placed }));
  $('#lec-html-info').textContent = parts.join(' · ');
}

function setMode(mode) {
  asked.mode = mode;
  for (const input of $$('input[name="lec-html-mode"]', box())) input.checked = input.value === mode;
  drawMap();
}

export function closeHtmlExport() {
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
  const { items, hidden } = slidesOf(pane);
  if (!items.length) {
    toast(t('넣을 장이 없습니다 — 숨기지 않은 장이 하나는 있어야 합니다'));
    return;
  }
  let info;
  try {
    info = await getJSON(`/api/html-export?p=${encodeURIComponent(S.tab.id)}&path=${encodeURIComponent(path)}`);
  } catch (e) {
    toast(e.message);
    return;
  }
  asked = { tab: S.tab, pane, path, items, hidden, ...sizeOf(items[0].section), mode: readMode(frontOf(pane).impress).mode, busy: false };
  $('#lec-html-title').textContent = t('html 로 전환 — {name}', { name: info.out });
  $('#lec-html-form').hidden = false;
  $('#lec-html-done').hidden = true;
  $('#lec-html-overview').checked = true;
  setMsg('');
  setMode(asked.mode);
  drawInfo();
  box().hidden = false;
  $('#lec-html-go').focus();
}

async function run() {
  if (!asked || asked.busy) return;
  const { tab, pane, path } = asked;
  if (pane.current?.path !== path || !pane.view.classList.contains('lec-deck')) {
    setMsg(t('그사이 칸의 문서가 바뀌었습니다 — 창을 닫고 다시 여세요'), true);
    return;
  }
  asked.busy = true;
  $('#lec-html-go').disabled = true;
  setMsg(t('만드는 중입니다…'));
  try {
    const built = await build(pane, path, { mode: asked.mode, overview: $('#lec-html-overview').checked });
    const r = await postJSON('/api/html-export', { p: tab.id, path, html: built.text });
    asked.result = `${dirname(path) ? `${dirname(path)}/` : ''}${r.path}`;
    $('#lec-html-form').hidden = true;
    $('#lec-html-done').hidden = false;
    $('#lec-html-summary').textContent = t('{name} 을 만들었습니다 — {n}장', { name: r.path, n: built.count });
    setMsg(built.notes.join('\n'));
    $('#lec-html-open').focus();
  } catch (e) {
    setMsg(e.message, true);
  } finally {
    if (asked) asked.busy = false;
    $('#lec-html-go').disabled = false;
  }
}

async function send(url) {
  try {
    await postJSON(url, { p: asked.tab.id, path: asked.result });
  } catch (e) {
    toast(e.message);
  }
  closeHtmlExport();
}

// ---- 짓기 ----------------------------------------------------------------------------------------

async function dataUrl(url) {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(String(res.status));
  const blob = await res.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

async function sha256(text) {
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)));
  return `'sha256-${btoa(String.fromCharCode(...digest))}'`;
}

/** KaTeX CSS — 글꼴(woff2)을 파일 안에. woff·ttf 대체는 지운다 (바깥에 묻지 않게) */
async function katexCss() {
  const href = $('link[href*="katex"]')?.getAttribute('href') || '/static/vendor/katex/katex.min.css';
  const css = await getText(href);
  const base = new URL('.', new URL(href, location.href)).href;
  const fonts = new Map();
  for (const m of css.matchAll(/url\((fonts\/[\w-]+\.woff2)\)/g)) fonts.set(m[1], '');
  for (const name of fonts.keys()) fonts.set(name, await dataUrl(base + name));
  return css.replace(/url\((fonts\/[\w-]+\.woff2)\) format\("woff2"\)(?:,url\(fonts\/[\w-]+\.(?:woff|ttf)\) format\("(?:woff|truetype)"\))*/g,
    (_, name) => `url(${fonts.get(name)}) format("woff2")`);
}

/** 이 파일만의 CSS: impress 의 장 크기·흐린 장·진행 막대, 스크립트 없이 열 때(Lectern) 위에서 아래로 놓는 모양 */
function frameCss(w, h) {
  const fits = [];
  for (let z = 95; z >= 20; z -= 5) fits.push(`@media (max-width: ${Math.ceil((w * (z + 5)) / 100 + 40)}px) { .impress-not-supported .lec-step { zoom: ${z / 100}; } }`);
  return `
html, body { margin: 0; padding: 0; }
body { background: color-mix(in srgb, var(--md-bg, #ffffff) 70%, #000000); }
#impress.md-body { max-width: none; margin: 0; padding: 0; --slide-scale: 1; }
#impress .lec-step { width: ${w}px; height: ${h}px; }
.notes { display: none; }
.impress-enabled .lec-step { opacity: .3; transition: opacity .8s; }
.impress-enabled .lec-step.active, .impress-on-overview .lec-step { opacity: 1; }
.impress-enabled .lec-step:not(.active) { cursor: pointer; }
.impress-progressbar { position: fixed; left: 0; right: 0; bottom: 0; height: 3px; pointer-events: none; }
.impress-progressbar div { width: 0; height: 100%; background: var(--md-link, #c2410c); transition: width .6s; }
.impress-not-supported { background: var(--md-bg, #ffffff); }
.impress-not-supported .impress-progressbar, .impress-not-supported .lec-overview { display: none; }
.impress-not-supported #impress { display: flex; flex-direction: column; align-items: center; gap: 28px; padding: 24px 16px 48px; }
.impress-not-supported .lec-step { flex: none; height: auto; }
.impress-not-supported #impress .lec-slide { position: relative; box-shadow: 0 1px 4px rgb(0 0 0 / .22); }
.impress-not-supported .notes { display: block; margin-top: 10px; padding: 8px 14px; border-left: 3px solid var(--md-border, #cccccc); color: var(--md-muted, #555555); font: 18px/1.5 var(--md-font, sans-serif); }
.impress-not-supported .notes p { margin: 0 0 .4em; }
${fits.join('\n')}`;
}

/** 스타일: 앱 화면과 같은 차례 (KaTeX, 코드 색, base, 스타일, 내 스타일) + 문서의 style:·장별 CSS + 이 파일의 CSS */
async function gatherCss(pane, math, w, h) {
  const hrefs = [
    $('#lec-hljs-css')?.getAttribute('href'),
    $('link[href$="/themes/base.css"]')?.getAttribute('href'),
    $('#lec-theme-css')?.getAttribute('href'),
    $('#lec-user-css')?.getAttribute('href'),
  ].filter(Boolean);
  const texts = math ? [await katexCss()] : [];
  for (const href of hrefs) texts.push(await getText(href));
  for (const st of $$('style.lec-deck-style', pane.view)) texts.push(st.textContent.split(DECK_SCOPE).join('#impress'));
  texts.push(frameCss(w, h));
  return texts.join('\n').replace(/<\/(style)/gi, '<\\/$1');   // 글 안의 </style> 이 틀을 닫지 않게
}

/** 장 하나의 복제: 앱 표시·스크립트·이벤트 속성을 떼고, 그림은 파일 안으로, 앱 안 링크는 글로 */
async function cleanSlide(section, images, found) {
  const clone = /** @type {HTMLElement} */ (section.cloneNode(true));
  const canvases = $$('canvas', section);
  $$('canvas', clone).forEach((c, i) => {   // 복제한 canvas 는 비어 있다 — 그림으로
    const img = document.createElement('img');
    try {
      img.src = canvases[i].toDataURL('image/png');
      img.style.cssText = c.style.cssText;
      img.width = canvases[i].width;
      img.height = canvases[i].height;
    } catch { /* 바깥 그림이 그려진 canvas */ }
    c.replaceWith(img);
  });
  for (const el of $$(DROP, clone)) {
    if (el.matches('video, audio')) found.media += 1;
    el.remove();
  }
  for (const el of [clone, ...$$('*', clone)]) {
    el.classList.remove(...MARKS);
    for (const at of [...el.attributes]) {
      const name = at.name.toLowerCase();
      const js = /^(href|xlink:href|src|action|formaction)$/.test(name) && /^\s*javascript:/i.test(at.value);
      if (name.startsWith('on') || js || DROP_ATTRS.has(name)) el.removeAttribute(at.name);
    }
  }
  for (const a of $$('a', clone)) {
    const href = a.getAttribute('href') || '';
    a.removeAttribute('xlink:href');
    if (/^https?:\/\//i.test(href)) {
      a.setAttribute('target', '_blank');
      a.setAttribute('rel', 'noopener noreferrer');
    } else if (!/^mailto:/i.test(href)) a.removeAttribute('href');   // 프로젝트 안 문서·절 링크는 이 파일에서 갈 곳이 없다
  }
  for (const input of $$('input', clone)) input.setAttribute('disabled', '');
  for (const img of $$('img', clone)) {
    img.removeAttribute('srcset');
    img.removeAttribute('loading');
    const src = img.getAttribute('src') || '';
    if (!src || src.startsWith('data:')) continue;
    const url = new URL(src, location.href);
    if (url.origin === location.origin) {
      try {
        if (!images.has(url.href)) images.set(url.href, await dataUrl(url.href));
        img.setAttribute('src', images.get(url.href));
      } catch {
        img.removeAttribute('src');
        found.missing += 1;
      }
    } else if (/^https?:$/.test(url.protocol)) {
      img.setAttribute('referrerpolicy', 'no-referrer');
      found.external += 1;
    } else img.removeAttribute('src');
  }
  return clone;
}

/** 노트 글 → 문단 (빈 줄로 나눈 것) */
const notesHtml = (text) => text.trim().split(/\n\s*\n/).map((p) => `<p>${esc(p).replace(/\n/g, '<br>')}</p>`).join('');

/** 파일 하나의 글을 짓는다: {text, count, notes(알릴 것)} */
async function build(pane, path, { mode, overview }) {
  const { items } = slidesOf(pane);
  if (!items.length) throw new Error(t('넣을 장이 없습니다 — 숨기지 않은 장이 하나는 있어야 합니다'));
  const { w, h } = sizeOf(items[0].section);
  const places = layoutSteps(items, { mode, w, h });
  const ov = overview ? overviewOf(places, { w, h }) : null;
  const images = new Map();
  const found = { external: 0, missing: 0, media: 0 };
  const steps = [];
  for (const [i, it] of items.entries()) {
    const clone = await cleanSlide(it.section, images, found);
    const p = places[i];
    const notes = it.wrap.querySelector('.lec-slide-notes')?.textContent || '';
    const data = Object.entries(p).map(([axis, v]) => `data-${axis}="${v}"`).join(' ');
    steps.push(`<div id="slide-${it.page}" class="step lec-step" data-deck="${esc(it.wrap.dataset.deck)}" data-slide="${it.page}" ${data}>${clone.outerHTML}${notes.trim() ? `<div class="notes">${notesHtml(notes)}</div>` : ''}</div>`);
  }
  if (ov) steps.push(`<div id="overview" class="step lec-overview" data-x="${ov.x}" data-y="${ov.y}" data-scale="${ov.scale}"></div>`);
  const math = items.some((it) => it.section.querySelector('.katex'));
  const css = await gatherCss(pane, math, w, h);
  const impress = await getText(IMPRESS);
  if (/<\/script/i.test(impress)) throw new Error('impress.js');   // 틀을 닫는 글이 있으면 해시가 맞지 않는다 (판을 올릴 때 보는 것)
  const policy = [
    "default-src 'none'",
    `script-src ${await sha256(impress)} ${await sha256(INIT)}`,
    "style-src 'self' 'unsafe-inline'",   // 'self': Lectern 이 이 파일을 보일 때 넣는 frame.css (찾기·바뀐 곳 표시 — htmldoc.js)
    `img-src data:${found.external ? ' https: http:' : ''}`,
    'font-src data:',
    "frame-src 'self'",   // 발표자 콘솔(P)이 같은 파일을 미리보기로 띄운다
    "base-uri 'none'",
    "form-action 'none'",
  ].join('; ');
  const fm = frontOf(pane);
  const heading = items[0].section.querySelector('h1, h2')?.textContent.trim();
  const title = (typeof fm.title === 'string' && fm.title.trim()) || heading || basename(path).replace(/\.md$/i, '');
  const root = document.documentElement;
  const text = [
    '<!doctype html>',
    `<html lang="${esc(root.lang || 'ko')}" data-ui="${esc(root.dataset.ui || '')}" data-theme="${esc(root.dataset.theme || '')}">`,
    '<head>',
    '<meta name="generator" content="Lectern (impress.js 2.0.0)">',
    '<meta charset="utf-8">',
    `<meta http-equiv="Content-Security-Policy" content="${esc(policy)}">`,
    '<meta name="referrer" content="no-referrer">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    `<meta name="lectern-source" content="${esc(basename(path))}">`,
    `<title>${esc(title)}</title>`,
    `<style>${css}</style>`,
    '</head>',
    '<body class="impress-not-supported">',
    `<div id="impress" class="md-body lec-deck" data-width="${w}" data-height="${h}" data-max-scale="3" data-min-scale="0" data-perspective="1000" data-transition-duration="1000">`,
    ...steps,
    '</div>',
    '<div class="impress-progressbar"><div></div></div>',
    `<script>${impress}</script>`,
    `<script>${INIT}</script>`,
    '</body>',
    '</html>',
    '',
  ].join('\n');
  const notes = [];
  if (found.external) notes.push(t('인터넷 그림 {n}개는 주소로 남았습니다 — 받은 사람의 브라우저가 불러옵니다', { n: found.external }));
  if (found.missing) notes.push(t('불러오지 못한 그림 {n}개는 빠졌습니다', { n: found.missing }));
  if (found.media) notes.push(t('동영상·소리 {n}개는 넣지 않았습니다', { n: found.media }));
  return { text, count: items.length, notes };
}

// ---- 시작 ----------------------------------------------------------------------------------------

export function initHtmlExport() {
  $('#lec-st-html').addEventListener('click', open);
  $('#lec-html-go').addEventListener('click', run);
  $('#lec-html-cancel').addEventListener('click', closeHtmlExport);
  $('#lec-html-close').addEventListener('click', closeHtmlExport);
  $('#lec-html-open').addEventListener('click', () => send('/api/html-export/open'));
  $('#lec-html-show').addEventListener('click', () => send('/api/reveal'));
  for (const input of $$('input[name="lec-html-mode"]', box())) input.addEventListener('change', () => setMode(input.value));
  $('#lec-html-ask').addEventListener('click', () => {
    const text = t("@{path} 이 Lectern 슬라이드를 impress.js html 로 전환하려고 해. 이야기 흐름에 맞게 장마다 자리를 정해 <!-- impress: x=… y=… --> 주석으로 적어 줘. 쓰는 법은 {guide} 의 'html 로 전환' 절에 있어.", { path: asked.path, guide: S.slidesGuide });
    closeHtmlExport();
    emit('term-paste', text);   // 터미널에 붙여 넣기 (D51 — Enter 는 사용자가)
  });
  box().addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      closeHtmlExport();
    } else if (e.key === 'Enter' && !e.target.closest('button') && !$('#lec-html-form').hidden) {
      e.preventDefault();
      run();
    }
  });
  box().addEventListener('mousedown', (e) => { if (e.target === box()) closeHtmlExport(); });
}
