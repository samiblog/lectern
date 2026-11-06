// 발표 문서 (D59·D96): 맨 앞 설정에 marp: true 가 있는 md 를 16:9 슬라이드로 그린다 — Marp 에서 출발한 Lectern 의 발표 형식.
//
// - 그리는 것은 문서 화면과 같은 렌더러다 (markdown.js·doc.js) — Mermaid·차트·수식·코드 색·표·박스글이 그대로 된다.
//   markdown-it 의 줄(---)마다 나눈다 (slideRule — headingDivider 면 그 수준까지의 제목 앞에서도). 슬라이드 하나 =
//   .lec-slide-wrap[data-lines] > .lec-slide-frame(화면 폭의 16:9 틀) > section.lec-slide(1280×720 을 transform 으로 줄임).
//   발표자 노트(지시어가 아닌 HTML 주석)는 틀 아래 .lec-slide-notes 에.
// - Marp 지시어: 맨 앞 설정과 HTML 주석의 paginate·header·footer·class(lead·invert)·backgroundColor·color·backgroundImage,
//   _ 를 앞에 붙이면 그 장만. size(16:9·4:3), headingDivider, style(이 문서의 슬라이드 안에만 입힌다 — 인터넷 주소는 지운다).
//   그림 문법 ![bg](…)(left·right[:N%]·contain·cover·auto·N%·vertical), ![w:300 h:200](…). theme 은 읽지 않는다 — 색·글꼴은 Lectern 스타일.
// - Lectern 이 더한 것 (D96): 칸 ::: 이름 낱말…  … :::(cellRule), 배치 layout·grid·cols·rows, 글자 크기 text, 작은 머리글 eyebrow, 장별 CSS <style scoped>.
//   글자 크기는 스타일과 상관없이 pt 로 정해져 있다 (base.css 의 --t-*) — 1280px 슬라이드는 PowerPoint 와이드 화면과 같은 크기다.
// - 넘치면: 그림·다이어그램·차트를 남은 높이에 맞춰 줄이고(fitSlide), 그래도 넘치면 글은 Marp 처럼 잘리고 틀에 '넘침' 표시.
//   넘침과 잘못 쓴 칸(checkSlide)은 장마다 wrap.dataset.issues 에 모은다 — 상태줄의 '점검'(slidetools.js)이 읽는다.
// - 상태줄의 '문서로 보기'로 보통 문서처럼, '발표'(Shift+F5)는 present.js. 인쇄하면 한 장에 한 쪽 (base.css 의 @page lec-slide).

import { S, on, emit } from './store.js';
import { $, $$ } from './util.js';
import { marksOf, lineOfY, yOfLine } from './editsync.js';
import { t } from './i18n.js';
import { textSizes, readCellHead } from './slideops.js';

const SIZES = { '16:9': [1280, 720], '4:3': [960, 720] };
const GLOBAL = new Set(['theme', 'style', 'headingDivider', 'size', 'math', 'title', 'description', 'author', 'image', 'keywords',
  'url', 'marp', 'lang', 'transition']);
const LOCAL = ['paginate', 'header', 'footer', 'class', 'backgroundColor', 'backgroundImage', 'backgroundPosition',
  'backgroundRepeat', 'backgroundSize', 'color', 'layout', 'grid', 'cols', 'rows', 'text', 'eyebrow'];
// 칸 배치: 이름 → [칸 자리(줄은 /), 열, 행]. t 는 제목 자리
const LAYOUTS = {
  two: ['t t / a b', '1fr 1fr', 'auto 1fr'],
  'two-left': ['t t / a b', '2fr 1fr', 'auto 1fr'],
  'two-right': ['t t / a b', '1fr 2fr', 'auto 1fr'],
  three: ['t t t / a b c', '1fr 1fr 1fr', 'auto 1fr'],
  quad: ['t t / a b / c d', '1fr 1fr', 'auto 1fr 1fr'],
  'left-stack': ['t t / a b / a c', '3fr 2fr', 'auto 1fr 1fr'],
  'right-stack': ['t t / a b / c b', '2fr 3fr', 'auto 1fr 1fr'],
  kpi: ['t t t t / a b c d / e e e e', '1fr 1fr 1fr 1fr', 'auto auto 1fr'],
  'kpi-two': ['t t t / a b c / d d e', '1fr 1fr 1fr', 'auto auto 1fr'],
  stack: ['t / a / b', '1fr', 'auto 1fr 1fr'],
};
const SAFE_AREA = /^[\p{L}\p{N}_\s/-]{1,200}$/u;
const SAFE_TRACK = /^[\w\s.%()-]{1,120}$/;
const LOCAL_SET = new Set(LOCAL);
const PER_SLIDE = ['layout', 'grid', 'cols', 'rows', 'text', 'eyebrow'];   // 칸 배치는 그 장에만 — 장마다 다른 것이 보통이라 Marp 처럼 뒤로 물려주지 않는다
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
 * key: 값 줄들을 읽는다 (발표 문서의 설정, 모아 보기의 문서 정보 D62). 키는 한글도 된다.
 * 값: 따옴표 글, true/false, 숫자, `|`·`>` 블록 글, 목록(`[a, b]` 또는 아래 줄의 `- a`). 아래에 들여 쓴 `키: 값` 은
 * 점으로 이은 키로 (`author:` 아래의 `name: 김` → `author.name`). 그 밖의 들여 쓴 줄(목록 항목의 이어진 줄 등)은 건너뛴다.
 * 읽을 수 없는 줄이 있으면 strict 일 때 null (주석이 지시어인지 노트인지 가를 때)
 */
export function readYaml(raw, strict = false) {
  const out = {};
  let lines = String(raw).split(/\r?\n/);
  const margin = Math.min(...lines.filter((l) => l.trim()).map((l) => l.match(/^\s*/)[0].length), 99);
  if (margin && margin < 99) lines = lines.map((l) => l.slice(margin));   // 통째로 들여 쓴 것 (주석 속 지시어)
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.trim() || /^\s*#/.test(line)) continue;
    const m = /^\s/.test(line) ? null : /^([\p{L}_$][\p{L}\p{N}_$.-]*)\s*:(?:\s+(.*)|\s*)$/u.exec(line.trim());
    if (!m) {
      if (strict) return null;
      continue;
    }
    /** @type {any} */
    let value = m[2] ?? '';
    const flow = /^\[(.*)\]$/.exec(value.trim());
    const next = lines.slice(i + 1).find((l) => l.trim() && !/^\s*#/.test(l)) || '';
    if (!value.trim() && /^\s+[\p{L}_$][\p{L}\p{N}_$.-]*\s*:/u.test(next)) {   // 아래에 들여 쓴 키: 값 (한 단계 아래 표)
      const block = [];
      while (i + 1 < lines.length && (/^\s/.test(lines[i + 1]) || !lines[i + 1].trim())) block.push(lines[++i]);
      const sub = readYaml(block.join('\n'), strict);
      if (!sub) return null;
      for (const [k, v] of Object.entries(sub)) out[`${m[1]}.${k}`] = v;
      continue;
    }
    if (flow) {   // [a, b]
      value = flow[1].split(',').map((x) => scalar(x)).filter((x) => x !== '');
    } else if (!value.trim() && /^\s*-\s+/.test(lines[i + 1] || '')) {   // 아래 줄의 - a, - b
      value = [];
      const indent = (l) => l.match(/^\s*/)[0].length;
      const at = indent(lines[i + 1]);
      while (i + 1 < lines.length) {
        const l = lines[i + 1];
        if (/^\s*-\s+/.test(l) && indent(l) === at) value.push(scalar(l.replace(/^\s*-\s+/, '')));
        else if (l.trim() && indent(l) <= at) break;   // 빈 줄·더 들여 쓴 줄(항목의 이어진 줄)은 건너뛴다
        i += 1;
      }
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
  return { id: ++deckSeq, w, h, style: typeof fm.style === 'string' ? fm.style : '', slideCss: {}, divider, fm };
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
const STYLE_BLOCK = /^\s*<style(\s+scoped)?\s*>([\s\S]*?)<\/style>\s*$/i;
const BG_FILTERS = { blur: '10px', brightness: '1.5', contrast: '2', grayscale: '1', 'hue-rotate': '180deg', invert: '1', opacity: '.5', saturate: '2', sepia: '1' };

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
  for (const [kind, size] of Object.entries(textSizes(deck.fm.text, eff.text))) css.push(`--t-${kind}:${size}pt`);
  const grid = gridOf(eff);
  if (grid) {
    css.push(`grid-template-areas:${grid.areas}`);
    if (grid.cols) css.push(`grid-template-columns:${grid.cols}`);
    if (grid.rows) css.push(`grid-template-rows:${grid.rows}`);
  }
  return css.join(';');
}

/** 이 장의 칸 배치 {areas, cols, rows} — layout 이름이나 grid 글자에서. 없으면 null */
function gridOf(eff) {
  const preset = LAYOUTS[String(eff.layout || '').trim()];
  const areas = typeof eff.grid === 'string' && SAFE_AREA.test(eff.grid) ? eff.grid : preset?.[0];
  if (!areas) return null;
  const track = (value, fallback) => (typeof value === 'string' && SAFE_TRACK.test(value) ? value : fallback);
  const rows = areas.split('/').map((row) => row.trim());
  // 적지 않으면 열은 같은 폭, 줄은 제목 줄만 글 높이 — 그냥 두면 내용 폭으로 쪼그라든다
  const width = rows[0].split(/\s+/).length;
  return {
    areas: rows.map((row) => `'${row}'`).join(' '),
    cols: track(eff.cols, preset?.[1] || `repeat(${width}, minmax(0, 1fr))`),
    rows: track(eff.rows, preset?.[2] || rows.map((row) => (/^t(\s+t)*$/.test(row) ? 'auto' : 'minmax(0, 1fr)')).join(' ')),
  };
}

/** ::: 이름 낱말…  부터 ::: 까지가 슬라이드의 칸이다 (markdown-it 블록 규칙 — 발표 문서에서만). 이름은 칸 자리, 낱말은 꾸밈 (card·kpi·accent…) */
export function cellRule(state, startLine, endLine, silent) {
  if (!state.env.deck && !state.env.cells) return false;
  const line = (n) => state.src.slice(state.bMarks[n] + state.tShift[n], state.eMarks[n]).trim();
  const m = /^:::\s+(\S.*)$/.exec(line(startLine));
  if (!m) return false;
  let close = startLine + 1;
  while (close < endLine && line(close) !== ':::') close += 1;
  if (close >= endLine) return false;
  if (silent) return true;
  const { name, words, size, at } = readCellHead(m[1]);
  const safe = /^[\p{L}\p{N}_-]+$/u.test(name) ? name : '';
  const open = state.push('lec_cell_open', 'div', 1);
  open.map = [startLine, close + 1];
  open.attrSet('class', ['lec-cell', ...words, ...(at ? ['lec-at'] : [])].join(' '));
  open.attrSet('data-cell', safe);
  for (let n = startLine + 1; n < close; n++) {
    if (/^:::\s+\S/.test(line(n))) open.attrSet('data-unclosed', '1');   // 닫는 줄을 빠뜨리면 다음 칸의 머리 줄이 안에 든다
  }
  const css = [];
  if (at) css.push(`left:${at[0]}px`, `top:${at[1]}px`, `width:${at[2]}px`, `height:${at[3]}px`);
  else if (safe) css.push(`grid-area:${safe}`);
  if (size) css.push(`font-size:${size}pt`, `--t-sub:${size * 1.15}pt`, `--t-table:${size}pt`, `--t-box:${size}pt`, `--t-code:${size}pt`);   // 이 칸의 글자 크기 (pt)
  if (css.length) open.attrSet('style', css.join(';'));
  const max = state.lineMax;
  state.lineMax = close;
  state.md.block.tokenize(state, startLine + 1, close);
  state.lineMax = max;
  state.push('lec_cell_close', 'div', -1);
  state.line = close + 1;
  return true;
}

export function slideRule(state) {
  const deck = state.env.deck;
  if (!deck) return;
  const md = state.md;
  const offset = state.env.lineOffset || 0;
  const total = (state.src.match(/\n/g) || []).length + (state.src.endsWith('\n') ? 0 : 1);
  const slides = [];
  const fresh = (start) => ({ tokens: [], start, local: {}, spot: {}, notes: [], css: [] });
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
      const style = STYLE_BLOCK.exec(tok.content);
      if (style) {   // 장별 CSS — scoped 면 이 장만, 아니면 문서 전체 (Marp 와 같다)
        if (style[1]) cur.css.push(style[2]);
        else deck.style += `\n${style[2]}`;
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
    for (const key of PER_SLIDE) delete inherit[key];
    const classes = String(eff.class || '').split(/\s+/).filter((c) => /^[\w-]+$/.test(c));
    if (eff.paginate === true) classes.push('lec-paginate');
    const grid = gridOf(eff);
    if (grid) classes.push('lec-grid');
    const missing = eff.layout && !LAYOUTS[String(eff.layout).trim()] && typeof eff.grid !== 'string' ? ` data-layout-miss="${attr(eff.layout)}"` : '';
    const areas = grid ? ` data-areas="${attr([...new Set(grid.areas.replace(/'/g, ' ').trim().split(/\s+/))].filter((x) => x !== 't' && x !== '.').join(' '))}"` : '';
    if (s.css.length) deck.slideCss[i + 1] = s.css.join('\n');
    const a = s.start + 1 + offset;
    const b = Math.max(s.start + 1, s.end) + offset;
    const header = typeof eff.header === 'string' && eff.header.trim() ? `<header>${md.renderInline(eff.header)}</header>` : '';
    const footer = typeof eff.footer === 'string' && eff.footer.trim() ? `<footer>${md.renderInline(eff.footer)}</footer>` : '';
    const eyebrow = typeof eff.eyebrow === 'string' && eff.eyebrow.trim() ? `<div class="lec-eyebrow">${md.renderInline(eff.eyebrow)}</div>` : '';
    const bgUrl = /^\s*url\(\s*(['"]?)(.*?)\1\s*\)\s*$/i.exec(typeof eff.backgroundImage === 'string' ? eff.backgroundImage : '');
    const bgImg = bgUrl ? `<p><img src="${attr(bgUrl[2])}" alt="bg"></p>` : '';
    const wide = deck.w / deck.h > 1.5 ? '' : ' lec-43';   // 인쇄 쪽 크기 (base.css 의 @page)
    out.push(html(`<div class="lec-slide-wrap${wide}" data-deck="${deck.id}" data-slide="${i + 1}" data-lines="${a}-${b}"`
      + ` style="--slide-w:${deck.w}px;--slide-h:${deck.h}px">`
      + `<div class="lec-slide-frame" style="aspect-ratio:${deck.w} / ${deck.h}">`
      + `<section class="lec-slide ${classes.join(' ')}" data-page="${i + 1}"${missing}${areas} style="${attr(slideStyle(eff, deck))}">${header}${eyebrow}${bgImg}\n`));
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

/** 문서의 style: CSS 를 이 문서의 슬라이드 안에만 — 중첩 규칙으로 감싸고, 바깥에서 불러오는 길(@import·url()·@font-face)은 지운다. page: 그 장에만 (<style scoped>) */
function scopedCss(css, id, page = 0) {
  const clean = String(css)
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/@import[^;]*;?/gi, '')
    .replace(/@font-face\s*\{[^}]*\}/gi, '')
    .replace(/url\(\s*(?!['"]?data:)[^)]*\)/gi, 'none')
    .replace(/image-set\([^)]*\)/gi, 'none')
    .replace(/<\/?style/gi, '');
  return `:is(#lec-panes, #lec-present, .lec-stage) [data-deck="${id}"]${page ? `[data-slide="${page}"]` : ''} {\n${balanceBraces(clean)}\n}`;
}

/** ![bg …](…) 의 낱말 → 배경 자리 */
function bgOptions(words) {
  const o = { side: '', split: '50%', fit: 'cover', size: '', vertical: false, filter: '' };
  for (const w of words) {
    const m = /^(left|right)(?::(\d+(?:\.\d+)?%))?$/i.exec(w);
    const f = /^(blur|brightness|contrast|grayscale|hue-rotate|invert|opacity|saturate|sepia)(?::([\d.]+(?:px|deg|%)?))?$/i.exec(w);
    if (f) o.filter += ` ${f[1].toLowerCase()}(${f[2] || BG_FILTERS[f[1].toLowerCase()]})`;
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
    if (o.filter) img.style.filter = o.filter.trim();
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

/** 칸 안의 그림·다이어그램·차트를 남은 높이에 맞춰 줄이고, 그래도 넘치면 그 칸에 표시한다. 넘친 칸들 [{cell, over(px), height(px), wide(옆으로 px)}] */
function fitCells(section) {
  const overs = [];
  for (const cell of $$('.lec-cell', section)) {
    cell.classList.remove('lec-cell-over');
    for (const el of $$('.lec-fit', cell)) {
      el.style.maxHeight = '';
      el.classList.remove('lec-fit');
    }
    let over = cell.scrollHeight - cell.clientHeight;
    if (over > 1) {
      const scale = section.getBoundingClientRect().width / section.offsetWidth || 1;
      const height = (el) => el.getBoundingClientRect().height / scale;
      for (const el of $$(FIGS, cell).sort((x, y) => height(y) - height(x))) {
        const want = Math.max(48, height(el) - over - 2);
        el.style.maxHeight = `${Math.round(want)}px`;
        el.classList.add('lec-fit');
        over = cell.scrollHeight - cell.clientHeight;
        if (over <= 1) break;
      }
    }
    const wide = cell.scrollWidth - cell.clientWidth;
    if (over > 1 || wide > 1) {
      cell.classList.add('lec-cell-over');
      overs.push({ cell, over: over > 1 ? Math.round(over) : 0, height: cell.clientHeight, wide: wide > 1 ? Math.round(wide) : 0 });
    }
  }
  return overs;
}

const lineOf = (el) => parseInt(el.dataset.lines || '', 10) || 0;

/** 잘못 쓴 칸·배치를 찾는다 — 글이 말없이 사라지지 않게. 고칠 것들 [{text, line}] */
function checkSlide(section) {
  const out = [];
  const add = (text, el = section.closest('.lec-slide-wrap')) => out.push({ text, line: lineOf(el) });
  if (section.dataset.layoutMiss) add(t("배치 '{name}' 이(가) 없습니다", { name: section.dataset.layoutMiss }));
  const cells = $$('.lec-cell', section).filter((c) => !c.closest('.lec-cell .lec-cell') || c.parentElement === section);
  for (const cell of cells) {
    cell.classList.remove('lec-cell-bad');
    if (cell.dataset.unclosed) {
      cell.classList.add('lec-cell-bad');
      add(t("칸 {name} 의 닫는 ::: 가 빠졌습니다", { name: cell.dataset.cell }), cell);
    }
  }
  if (section.classList.contains('lec-grid')) {
    const areas = (section.dataset.areas || '').split(' ').filter(Boolean);
    const names = new Set();
    for (const cell of cells) {
      if (cell.classList.contains('lec-at')) continue;
      names.add(cell.dataset.cell);
      if (!areas.includes(cell.dataset.cell)) {
        cell.classList.add('lec-cell-bad');
        add(t('칸 {name} 이(가) 배치에 없습니다 — 배치의 칸: {areas}', { name: cell.dataset.cell || '?', areas: areas.join(' ') }), cell);
      }
    }
    for (const area of areas) if (!names.has(area)) add(t('칸 {name} 이(가) 비어 있습니다', { name: area }));
    const stray = [...section.children].filter((el) => !el.matches('.lec-cell, h1, h2, header, footer, .lec-slide-bg, .lec-eyebrow, style, script'));
    if (stray.length) add(t('칸 밖에 글이 있습니다 — 칸 안으로 옮기세요'), stray[0]);
    if ($$(':scope > :is(h1, h2)', section).length > 1) add(t('이 장에 제목이 둘입니다 — 제목은 하나만 씁니다'));
  }
  for (const p of $$('p', section)) {
    if (/^:::(\s|$)/.test(p.textContent.trim())) add(t('짝이 맞지 않는 ::: 가 있습니다'), p);
  }
  checkPlaced(section, cells.filter((c) => c.classList.contains('lec-at')), add);
  return out;
}

/** 두 상자가 겹친 넓이 ÷ 작은 상자의 넓이 */
function overlap(a, b) {
  const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
  const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
  return w > 0 && h > 0 ? (w * h) / Math.max(1, Math.min(a.width * a.height, b.width * b.height)) : 0;
}

/** 자리 칸(at)은 글이 넘쳐도 서로 가릴 뿐 넘침으로 잡히지 않는다 — 겹침과 슬라이드 밖을 따로 본다 */
function checkPlaced(section, placed, add) {
  if (!placed.length) return;
  const slide = section.getBoundingClientRect();
  const heads = $$(':scope > :is(h1, h2)', section).map((h) => {
    const r = document.createRange();
    r.selectNodeContents(h);
    return r.getBoundingClientRect();
  });
  const boxes = placed.map((c) => c.getBoundingClientRect());
  placed.forEach((cell, i) => {
    const box = boxes[i];
    if (box.right > slide.right + 1 || box.bottom > slide.bottom + 1) add(t('칸 {name} 이(가) 슬라이드 밖으로 나갑니다', { name: cell.dataset.cell }), cell);
    if (heads.some((h) => overlap(box, h) > 0)) add(t('칸 {name} 이(가) 제목과 겹칩니다', { name: cell.dataset.cell }), cell);
    for (let j = i + 1; j < placed.length; j++) {
      if (overlap(box, boxes[j]) > 0.1) add(t('칸 {a} 과(와) 칸 {b} 이(가) 겹칩니다', { a: cell.dataset.cell, b: placed[j].dataset.cell }), cell);
    }
  });
}

/** 넘치면 그림·다이어그램·차트부터 남은 높이에 맞춰 줄인다. 그래도 넘치면 틀에 '넘침' 표시 (글은 Marp 처럼 잘린다) */
export function fitSlide(section) {
  const wrap = section.closest('.lec-slide-wrap');
  if (!wrap) return;
  const cellsOver = fitCells(section);
  const issues = checkSlide(section);
  for (const el of $$(':scope > .lec-fit', section)) {
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
  for (const c of cellsOver) {
    if (c.over) issues.push({ text: t('칸 {name} 이(가) {over}px 넘칩니다 (칸 높이 {height}px)', { name: c.cell.dataset.cell, over: c.over, height: c.height }), line: lineOf(c.cell) });
    if (c.wide) issues.push({ text: t('칸 {name} 이(가) 옆으로 {over}px 넘칩니다', { name: c.cell.dataset.cell, over: c.wide }), line: lineOf(c.cell) });
  }
  if (over > 1) issues.push({ text: t('아래가 {over}px 잘렸습니다', { over: Math.round(over) }), line: lineOf(wrap) });
  const frame = wrap.querySelector('.lec-slide-frame');
  wrap.classList.toggle('lec-over', issues.length > 0);
  if (issues.length) {
    frame.dataset.over = issues.length > 1 ? t('{text} 외 {n}건', { text: issues[0].text, n: issues.length - 1 }) : issues[0].text;
    wrap.dataset.issues = JSON.stringify(issues);
  } else {
    delete frame.dataset.over;
    delete wrap.dataset.issues;
  }
  if (section.isConnected && !section.closest('.lec-stage')) emit('deck-checked');
}

/** 구조 보기(slidetools.js)의 꼬리표 자리: 칸 머리 줄과 장의 주석 줄 — 글은 켤 때 넣는다 (꺼 둔 동안은 찾기·줄 단위에 들지 않게) */
function addTags(root, text) {
  const lines = text.split(/\r?\n/);
  const tag = (n) => {
    const el = document.createElement('span');
    el.className = 'lec-tag';
    el.dataset.tagLine = String(n);
    el.dataset.tag = lines[n - 1] ?? '';
    return el;
  };
  for (const cell of $$('.lec-cell[data-lines]', root)) cell.prepend(tag(parseInt(cell.dataset.lines, 10)));
  for (const wrap of $$('.lec-slide-wrap', root)) {
    const [a, b] = wrap.dataset.lines.split('-').map(Number);
    const strip = document.createElement('div');
    strip.className = 'lec-slide-tags';
    let fence = '';
    for (let n = a; n <= b; n++) {
      const s = lines[n - 1] ?? '';
      const f = /^\s*(`{3,}|~{3,})/.exec(s);
      if (f && (!fence || f[1][0] === fence)) fence = fence ? '' : f[1][0];
      else if (!fence && /^\s*<!--.*-->\s*$/.test(s)) strip.append(tag(n));
    }
    if (strip.children.length) wrap.prepend(strip);
  }
}

/** 렌더링 뒤 다듬기 (그림은 enhance 가 불러오기 시작한 뒤): 배경 그림, 그림 크기, style: CSS, 구조 보기 꼬리표 자리, 이 장부터 발표 버튼 */
export function prepareDeck(root, deck, text = '') {
  const addCss = (css, page = 0) => {
    const st = document.createElement('style');
    st.className = 'lec-deck-style';
    st.textContent = scopedCss(css, deck.id, page);
    root.prepend(st);
  };
  if (deck.style) addCss(deck.style);
  for (const [page, css] of Object.entries(deck.slideCss)) addCss(css, Number(page));
  addTags(root, text);
  for (const section of $$('.lec-slide', root)) {
    if (!section.classList.contains('lec-grid') && section.querySelector(':scope > .lec-at')) section.classList.add('lec-free');   // 자리 칸만 있는 장: 제목은 위에
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
  emit('deck-shown', deck);
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
