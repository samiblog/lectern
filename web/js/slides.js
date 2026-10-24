// 발표 문서 (D59): 맨 앞 설정에 marp: true 가 있는 md 를 16:9 슬라이드로 그린다 — Marp(VS Code 확장·marp-cli)의 문서 형식.
//
// - 그리는 것은 문서 화면과 같은 렌더러다 (markdown.js·doc.js) — Mermaid·차트·수식·코드 색·표·박스글이 그대로 된다.
//   markdown-it 의 줄(---)마다 나눈다 (slideRule — headingDivider 면 그 수준까지의 제목 앞에서도). 슬라이드 하나 =
//   .lec-slide-wrap[data-lines] > .lec-slide-frame(화면 폭의 16:9 틀) > section.lec-slide(1280×720 을 transform 으로 줄임).
//   발표자 노트(지시어가 아닌 HTML 주석)는 틀 아래 .lec-slide-notes 에.
// - Marp 지시어: 맨 앞 설정과 HTML 주석의 paginate·header·footer·class(lead·invert)·backgroundColor·color·backgroundImage,
//   _ 를 앞에 붙이면 그 장만. size(16:9·4:3), headingDivider, style(이 문서의 슬라이드 안에만 입힌다 — 인터넷 주소는 지운다).
//   그림 문법 ![bg](…)(left·right[:N%]·contain·cover·auto·N%·vertical), ![w:300 h:200](…). theme 은 읽지 않는다 — 색·글꼴은 Lectern 스타일.
// - 넘치면: 그림·다이어그램·차트를 남은 높이에 맞춰 줄이고(fitSlide), 그래도 넘치면 글은 Marp 처럼 잘리고 틀에 '넘침' 표시.
// - 상태줄의 '문서로 보기'로 보통 문서처럼, '발표'(Shift+F5)는 present.js. 인쇄하면 한 장에 한 쪽 (base.css 의 @page lec-slide).

import { S, on, emit } from './store.js';
import { $, $$ } from './util.js';
import { marksOf, lineOfY, yOfLine } from './editsync.js';
import { t } from './i18n.js';

const SIZES = { '16:9': [1280, 720], '4:3': [960, 720] };
const GLOBAL = new Set(['theme', 'style', 'headingDivider', 'size', 'math', 'title', 'description', 'author', 'image', 'keywords',
  'url', 'marp', 'lang', 'transition']);
const LOCAL = ['paginate', 'header', 'footer', 'class', 'backgroundColor', 'backgroundImage', 'backgroundPosition',
  'backgroundRepeat', 'backgroundSize', 'color'];
const LOCAL_SET = new Set(LOCAL);
const SAFE_CSS = /^[#\w\s(),.%+-]{1,120}$/;   // 색·크기·그라데이션 — 따옴표·세미콜론·url() 은 받지 않는다
const FIGS = 'pre.mermaid > svg, .lec-chart svg:not(svg svg), img';
/** 슬라이드 안의 다이어그램·차트를 키우는 배율 — 그 글자(12~16px)가 슬라이드 글자(본문 × 1.8)와 어울리게. charts.js 도 쓴다 */
export const SLIDE_ZOOM = 1.7;

let deckSeq = 0;
const asDocument = new Set();   // '문서로 보기'를 고른 발표 문서 (탭 id + 경로) — 앱을 다시 켜면 다시 슬라이드

// ---- 맨 앞 설정·주석 지시어 읽기 (YAML 의 작은 부분: key: 값, 따옴표, true/false/숫자, | > 블록 글) ----------------

function scalar(value) {
  const v = value.trim();
  const q = /^(["'])([\s\S]*)\1$/.exec(v);
  if (q) return q[2];
  if (/^(true|yes|on)$/i.test(v)) return true;
  if (/^(false|no|off)$/i.test(v)) return false;
  if (/^-?\d+(\.\d+)?$/.test(v)) return Number(v);
  return v.replace(/\s+#\s.*$/, '');   // 끝 주석 (값이 #fff 처럼 # 로 시작하는 것은 색으로 둔다)
}

/**
 * key: 값 줄들을 읽는다 (맨 위 단계만 — 발표 문서의 설정, 모아 보기의 문서 정보 D62). 키는 한글도 된다.
 * 값: 따옴표 글, true/false, 숫자, `|`·`>` 블록 글, 목록(`[a, b]` 또는 아래 줄의 `- a`). 읽을 수 없는 줄이 있으면 strict 일 때 null
 * (주석이 지시어인지 노트인지 가를 때)
 */
export function readYaml(raw, strict = false) {
  const out = {};
  const lines = String(raw).split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim() || /^\s*#/.test(line)) continue;
    const m = /^([\p{L}_$][\p{L}\p{N}_$.-]*)\s*:(?:\s+(.*)|\s*)$/u.exec(line.trim());
    if (!m) {
      if (strict) return null;
      continue;
    }
    let value = m[2] ?? '';
    const flow = /^\[(.*)\]$/.exec(value.trim());
    if (flow) {   // [a, b]
      value = flow[1].split(',').map((x) => scalar(x)).filter((x) => x !== '');
    } else if (!value.trim() && /^\s*-\s+/.test(lines[i + 1] || '')) {   // 아래 줄의 - a, - b
      value = [];
      while (i + 1 < lines.length && /^\s*-\s+/.test(lines[i + 1])) value.push(scalar(lines[++i].replace(/^\s*-\s+/, '')));
    } else if (/^[|>][+-]?\s*$/.test(value.trim())) {   // 블록 글: 아래의 들여 쓴 줄들
      const fold = value.trim()[0] === '>';
      const block = [];
      while (i + 1 < lines.length && (/^\s/.test(lines[i + 1]) || !lines[i + 1].trim())) block.push(lines[++i]);
      const indent = Math.min(...block.filter((l) => l.trim()).map((l) => l.match(/^\s*/)[0].length), 99);
      const body = block.map((l) => l.slice(indent));
      value = (fold ? body.join(' ') : body.join('\n')).replace(/\s+$/, '');
    } else {
      value = scalar(value);
    }
    out[m[1]] = value;
  }
  return out;
}

/** 맨 앞 설정(frontmatter 원문)이 Marp 발표 문서면 그 설정, 아니면 null */
export function readDeck(frontMatter) {
  if (!frontMatter) return null;
  const fm = readYaml(frontMatter);
  if (fm.marp !== true) return null;
  const [w, h] = SIZES[String(fm.size || '16:9').trim()] || SIZES['16:9'];
  const divider = Array.isArray(fm.headingDivider) ? Math.max(...fm.headingDivider) : Number(fm.headingDivider) || 0;
  return { id: ++deckSeq, w, h, style: typeof fm.style === 'string' ? fm.style : '', divider, fm };
}

/** 칸(pane)의 이 문서를 슬라이드로 그릴지 — 발표 문서이고 '문서로 보기'를 고르지 않았으면 */
export const slidesWanted = (pane, path) => !asDocument.has(`${pane.tab.id}:${path}`);

/** 주석 하나: 모든 줄이 Marp 지시어면 {local, spot}, 아니면 null (발표자 노트) */
function directivesOf(text) {
  const map = readYaml(text, true);
  if (!map || !Object.keys(map).length) return null;
  const local = {};
  const spot = {};
  for (const [key, value] of Object.entries(map)) {
    const name = key.startsWith('_') ? key.slice(1) : key;
    if (!LOCAL_SET.has(name) && !GLOBAL.has(name)) return null;
    if (!LOCAL_SET.has(name)) continue;   // 주석 속 전역 지시어(theme 등)는 읽지 않는다
    (key.startsWith('_') ? spot : local)[name] = value;
  }
  return { local, spot };
}

const COMMENT = /<!--([\s\S]*?)-->/g;

/** html 블록이 주석만이면 그 글들, 아니면 null */
function commentsOnly(html) {
  const texts = [];
  const rest = html.replace(COMMENT, (_, body) => {
    texts.push(body);
    return '';
  });
  return texts.length && !rest.trim() ? texts : null;
}

// ---- markdown-it 규칙: 줄(---)마다 슬라이드로 감싼다 (markdown.js 가 등록 — env.deck 이 있을 때만) ----------------

const attr = (s) => String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
const cssValue = (v) => (typeof v === 'string' && SAFE_CSS.test(v) ? v.trim() : '');

function slideStyle(eff, deck) {
  const css = [`width:${deck.w}px`, `height:${deck.h}px`];
  const bg = cssValue(eff.backgroundColor);
  if (bg) css.push(`background-color:${bg}`);
  const fg = cssValue(eff.color);
  if (fg) css.push(`color:${fg}`, `--md-fg:${fg}`, `--md-heading:${fg}`);
  const image = typeof eff.backgroundImage === 'string' ? eff.backgroundImage.trim() : '';
  if (image && !/url\s*\(/i.test(image) && SAFE_CSS.test(image)) css.push(`background-image:${image}`);   // 그라데이션
  for (const [key, prop] of [['backgroundPosition', 'background-position'], ['backgroundRepeat', 'background-repeat'], ['backgroundSize', 'background-size']]) {
    const v = cssValue(eff[key]);
    if (v) css.push(`${prop}:${v}`);
  }
  return css.join(';');
}

export function slideRule(state) {
  const deck = state.env.deck;
  if (!deck) return;
  const md = state.md;
  const offset = state.env.lineOffset || 0;
  const total = (state.src.match(/\n/g) || []).length + (state.src.endsWith('\n') ? 0 : 1);
  const slides = [];
  const fresh = (start) => ({ tokens: [], start, local: {}, spot: {}, notes: [] });
  let cur = fresh(0);
  const split = (end, next) => {
    cur.end = end;
    slides.push(cur);
    cur = fresh(next);
  };
  for (const tok of state.tokens) {
    if (tok.level === 0 && tok.type === 'hr') {
      split(tok.map[0], tok.map[1]);
      continue;
    }
    if (tok.level === 0 && tok.type === 'heading_open' && deck.divider && +tok.tag[1] <= deck.divider && cur.tokens.length) {
      split(tok.map[0], tok.map[0]);
    }
    if (tok.level === 0 && tok.type === 'html_block') {
      const texts = commentsOnly(tok.content);
      if (texts) {
        for (const text of texts) {
          const dirs = directivesOf(text);
          if (dirs) {
            Object.assign(cur.local, dirs.local);
            Object.assign(cur.spot, dirs.spot);
          } else if (text.trim()) {
            cur.notes.push(text.trim());
          }
        }
        continue;
      }
    }
    cur.tokens.push(tok);
  }
  cur.end = total;
  slides.push(cur);

  const html = (content) => {
    const tok = new state.Token('html_block', '', 0);
    tok.content = content;
    tok.block = true;
    return tok;
  };
  const out = [];
  let inherit = Object.fromEntries(LOCAL.filter((k) => k in deck.fm).map((k) => [k, deck.fm[k]]));
  slides.forEach((s, i) => {
    inherit = { ...inherit, ...s.local };
    const eff = { ...inherit, ...s.spot };
    const classes = String(eff.class || '').split(/\s+/).filter((c) => /^[\w-]+$/.test(c));
    if (eff.paginate === true) classes.push('lec-paginate');
    const a = s.start + 1 + offset;
    const b = Math.max(s.start + 1, s.end) + offset;
    const header = typeof eff.header === 'string' && eff.header.trim() ? `<header>${md.renderInline(eff.header)}</header>` : '';
    const footer = typeof eff.footer === 'string' && eff.footer.trim() ? `<footer>${md.renderInline(eff.footer)}</footer>` : '';
    const bgUrl = /^\s*url\(\s*(['"]?)(.*?)\1\s*\)\s*$/i.exec(typeof eff.backgroundImage === 'string' ? eff.backgroundImage : '');
    const bgImg = bgUrl ? `<p><img src="${attr(bgUrl[2])}" alt="bg"></p>` : '';
    const wide = deck.w / deck.h > 1.5 ? '' : ' lec-43';   // 인쇄 쪽 크기 (base.css 의 @page)
    out.push(html(`<div class="lec-slide-wrap${wide}" data-deck="${deck.id}" data-slide="${i + 1}" data-lines="${a}-${b}"`
      + ` style="--slide-w:${deck.w}px;--slide-h:${deck.h}px">`
      + `<div class="lec-slide-frame" style="aspect-ratio:${deck.w} / ${deck.h}">`
      + `<section class="lec-slide ${classes.join(' ')}" data-page="${i + 1}" style="${attr(slideStyle(eff, deck))}">${header}${bgImg}\n`));
    out.push(...s.tokens);
    out.push(html(`${footer}</section></div>${s.notes.length ? `<div class="lec-slide-notes">${md.utils.escapeHtml(s.notes.join('\n\n'))}</div>` : ''}</div>\n`));
  });
  state.tokens = out;
}

// ---- 그린 뒤 다듬기 (doc.js 가 화면 밖 무대에서 부른다) ------------------------------------------------------

/** 짝이 맞지 않는 } 를 뺀다 — 감싼 중첩 규칙을 일찍 닫고 앱 전체에 규칙을 거는 길을 막는다 (따옴표 안의 괄호는 세지 않는다) */
function balanceBraces(css) {
  let out = '';
  let depth = 0;
  let quote = '';
  for (const ch of css) {
    if (quote) {
      if (ch === quote) quote = '';
    } else if (ch === '"' || ch === "'") {
      quote = ch;
    } else if (ch === '{') {
      depth += 1;
    } else if (ch === '}') {
      if (!depth) continue;
      depth -= 1;
    }
    out += ch;
  }
  return out + (quote || '') + '}'.repeat(depth);
}

/** 문서의 style: CSS 를 이 문서의 슬라이드 안에만 — 중첩 규칙으로 감싸고, 바깥에서 불러오는 길(@import·url()·@font-face)은 지운다 */
function scopedCss(css, id) {
  const clean = String(css)
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/@import[^;]*;?/gi, '')
    .replace(/@font-face\s*\{[^}]*\}/gi, '')
    .replace(/url\(\s*(?!['"]?data:)[^)]*\)/gi, 'none')
    .replace(/image-set\([^)]*\)/gi, 'none')
    .replace(/<\/?style/gi, '');
  return `:is(#lec-panes, #lec-present, .lec-stage) [data-deck="${id}"] {\n${balanceBraces(clean)}\n}`;
}

/** ![bg …](…) 의 낱말 → 배경 자리 */
function bgOptions(words) {
  const o = { side: '', split: '50%', fit: 'cover', size: '', vertical: false };
  for (const w of words) {
    const m = /^(left|right)(?::(\d+(?:\.\d+)?%))?$/i.exec(w);
    if (m) {
      o.side = m[1].toLowerCase();
      if (m[2]) o.split = m[2];
    } else if (/^(contain|fit)$/i.test(w)) o.fit = 'contain';
    else if (/^cover$/i.test(w)) o.fit = 'cover';
    else if (/^auto$/i.test(w)) o.fit = 'none';
    else if (/^\d+(\.\d+)?%$/.test(w)) o.size = w;
    else if (/^vertical$/i.test(w)) o.vertical = true;
  }
  return o;
}

function moveBackgrounds(section) {
  const imgs = $$('img', section).filter((img) => /^bg(\s|$)/i.test(img.alt.trim()));
  if (!imgs.length) return;
  const first = bgOptions(imgs[0].alt.trim().split(/\s+/).slice(1));
  const box = document.createElement('div');
  box.className = `lec-slide-bg${first.side ? ` ${first.side}` : ''}${first.vertical ? ' vertical' : ''}`;
  if (first.side) {
    box.style.setProperty('--bg-split', first.split);
    section.classList.add(`lec-bg-${first.side}`);
    section.style.setProperty('--bg-pad', `${Math.round((parseFloat(section.style.width) * parseFloat(first.split)) / 100)}px`);
  }
  for (const img of imgs) {
    const o = bgOptions(img.alt.trim().split(/\s+/).slice(1));
    const p = img.parentElement;
    img.classList.remove('zoomable');
    img.classList.add('lec-bg-img');
    img.style.objectFit = o.fit;
    if (o.size) {
      img.style.objectFit = 'contain';
      img.style.width = o.size;
      img.style.height = o.size;
    }
    box.append(img);
    if (p && p.tagName === 'P' && !p.textContent.trim() && !p.children.length) p.remove();
  }
  section.prepend(box);
}

/** ![w:300 h:200](…) — 그림 크기 낱말을 대체 글에서 떼어 크기로 */
function sizeImages(section) {
  for (const img of $$('img:not(.lec-bg-img)', section)) {
    const words = img.alt.trim().split(/\s+/);
    const rest = [];
    for (const w of words) {
      const m = /^(w|width|h|height):(\d+(?:\.\d+)?)(px)?$/i.exec(w);
      if (m) img.style[m[1][0].toLowerCase() === 'w' ? 'width' : 'height'] = `${m[2]}px`;
      else if (w) rest.push(w);
    }
    if (rest.length !== words.filter(Boolean).length) img.alt = rest.join(' ');
  }
}

/** 넘치면 그림·다이어그램·차트부터 남은 높이에 맞춰 줄인다. 그래도 넘치면 틀에 '넘침' 표시 (글은 Marp 처럼 잘린다) */
export function fitSlide(section) {
  const wrap = section.closest('.lec-slide-wrap');
  if (!wrap) return;
  for (const el of $$('.lec-fit', section)) {
    el.style.maxHeight = '';
    el.classList.remove('lec-fit');
  }
  let over = section.scrollHeight - section.clientHeight;
  if (over > 1) {
    const scale = section.getBoundingClientRect().width / section.offsetWidth || 1;   // 화면의 줄인 크기 → 슬라이드 크기
    const height = (el) => el.getBoundingClientRect().height / scale;
    const figs = $$(FIGS, section).filter((el) => !el.closest('.lec-slide-bg, header, footer') && height(el) > 40)
      .sort((x, y) => height(y) - height(x));
    const least = section.clientHeight * 0.3;
    for (const el of figs) {
      const h = height(el);
      const want = Math.max(least, h - over - 6);
      if (want >= h - 1) continue;
      el.style.maxHeight = `${Math.round(want)}px`;
      el.classList.add('lec-fit');
      over = section.scrollHeight - section.clientHeight;
      if (over <= 1) break;
    }
  }
  const frame = wrap.querySelector('.lec-slide-frame');
  wrap.classList.toggle('lec-over', over > 1);
  if (over > 1) frame.dataset.over = t('넘침 — 아래가 잘렸습니다');
}

/** 렌더링 뒤 다듬기 (그림은 enhance 가 불러오기 시작한 뒤): 배경 그림, 그림 크기, style: CSS, 이 장부터 발표 버튼 */
export function prepareDeck(root, deck) {
  if (deck.style) {
    const st = document.createElement('style');
    st.className = 'lec-deck-style';
    st.textContent = scopedCss(deck.style, deck.id);
    root.prepend(st);
  }
  for (const section of $$('.lec-slide', root)) {
    moveBackgrounds(section);
    sizeImages(section);
    for (const img of $$('img', section)) {
      img.loading = 'eager';   // 화면 밖 무대에서도 불러와야 넘침을 잴 수 있다
      if (!img.complete) img.addEventListener('load', () => fitSlide(section), { once: true });
    }
  }
  for (const notes of $$('.lec-slide-notes', root)) notes.dataset.label = t('발표자 노트');
  for (const wrap of $$('.lec-slide-wrap', root)) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'lec-slide-play';
    btn.title = t('이 장부터 발표');
    btn.setAttribute('aria-label', btn.title);
    btn.innerHTML = '<svg aria-hidden="true"><use href="#i-play"/></svg>';
    wrap.querySelector('.lec-slide-frame').append(btn);
  }
}

/** 다이어그램·차트를 그린 뒤 (무대에 붙어 있어 크기를 잴 수 있을 때): Mermaid 를 키우고(차트는 charts.js 가 키워 그린다) 넘침을 맞춘다 */
export function fitDeck(root) {
  for (const svg of $$('.lec-slide pre.mermaid > svg', root)) {
    const natural = parseFloat(svg.style.maxWidth);
    if (natural) svg.style.maxWidth = `${Math.round(natural * SLIDE_ZOOM)}px`;
  }
  for (const section of $$('.lec-slide', root)) fitSlide(section);
}

// ---- 화면 폭에 맞춰 줄이기 ----------------------------------------------------------------------------

/** 슬라이드(1280×720 등)를 틀 폭에 맞춰 줄이는 배율 — 칸의 본문에 --slide-scale 로 */
export function applyScale(view) {
  const frame = view.querySelector(':scope > .lec-slide-wrap .lec-slide-frame');
  const section = frame?.querySelector('.lec-slide');
  if (!frame || !section || !section.offsetWidth) {
    view.style.removeProperty('--slide-scale');
    return;
  }
  view.style.setProperty('--slide-scale', String(frame.clientWidth / section.offsetWidth));
}

let resizer = null;

/** 칸에 그린 뒤: 배율을 정하고 폭이 바뀔 때마다 다시 */
export function showDeck(pane) {
  applyScale(pane.view);
  resizer ||= new ResizeObserver((entries) => {
    for (const e of entries) if (e.target.classList.contains('lec-deck')) applyScale(e.target);
  });
  resizer.observe(pane.view);
}

// ---- 상태줄: 슬라이드 ↔ 문서, 발표 -------------------------------------------------------------------------

/** 지금 화면 위쪽의 슬라이드 번호 (0부터) */
export function slideAtTop(pane = S.pane) {
  const wraps = $$(':scope > .lec-slide-wrap', pane.view);
  const box = pane.scroller.getBoundingClientRect();
  let found = 0;
  wraps.forEach((w, i) => {
    if (w.getBoundingClientRect().top <= box.top + box.height * 0.4) found = i;
  });
  return found;
}

function updateButtons() {
  const view = S.pane?.view;
  const marp = !!view?.classList.contains('lec-marp');
  const deck = marp && view.classList.contains('lec-deck');
  const toggle = $('#lec-st-slides');
  toggle.hidden = !marp;
  toggle.querySelector('span').textContent = deck ? t('문서로 보기') : t('슬라이드로 보기');
  toggle.title = deck ? t('보통 문서처럼 이어서 보기') : t('슬라이드로 보기 — Marp 발표 문서 (marp: true)');
  $('#lec-st-present').hidden = !deck;
}

let keepLine = null;   // 슬라이드 ↔ 문서를 바꾼 뒤 같은 원문 줄을 화면 위에 두려고 {pane, line}

function toggleSlides() {
  const pane = S.pane;
  const path = pane?.current?.path;
  if (!pane?.view.classList.contains('lec-marp') || !path) return;
  const key = `${pane.tab.id}:${path}`;
  const top = pane.scroller.getBoundingClientRect().top;
  keepLine = { pane, line: lineOfY(marksOf(pane), top + 8, top) };
  if (asDocument.has(key)) asDocument.delete(key);
  else asDocument.add(key);
  emit('refresh-view', pane);
}

export function initSlides() {
  $('#lec-st-slides').addEventListener('click', toggleSlides);
  on('rendered', (pane) => {
    if (keepLine?.pane === pane) {
      const top = pane.scroller.getBoundingClientRect().top;
      const y = yOfLine(marksOf(pane), keepLine.line, top);
      if (y != null) pane.scroller.scrollTop += y - top - 8;
      keepLine = null;
    }
    if (pane === S.pane) updateButtons();
  });
  on('pane', updateButtons);
}
