// 차트·도해 (D56): ```vega-lite·```vega·```echarts·```dot(```graphviz) 코드 블록을 그림(SVG)으로 — Mermaid(mermaid.js)와 같은 자리.
//
// - 라이브러리는 그 블록이 있는 문서를 처음 그릴 때 불러온다 (web/vendor 의 vega·echarts·viz). 전역(vega·vegaLite·echarts·Viz)은
//   문서 속 id 가 가릴 수 있으므로 진짜 라이브러리인지 본다 (mermaid.js 처럼).
// - 모두 움직이지 않는 SVG 로 그린다 — 인쇄·우클릭 복사(PNG)·눌러서 크게 보기가 Mermaid 와 같다. 마우스를 올려 값 보기·확대 같은
//   움직임은 없다. 그린 SVG 는 문서처럼 DOMPurify 로 거른다 (doc.js 의 sanitizeHtml — 인터넷 그림을 부르는 길), 링크는 푼다.
// - 색은 Mermaid 와 같은 스타일 색표(theme.js 의 mermaidTheme), 글꼴은 앱 글꼴. 스타일을 바꾸면 문서를 다시 그리므로 따라온다.
// - 설정은 JSON. ECharts 예제처럼 따옴표 없는 키·작은따옴표·주석·끝 쉼표·'option =' 도 읽는다 (parseSpec). 함수는 안 된다 —
//   문서가 스크립트를 돌리지 않는 것과 같은 까닭 (D27).
// - 데이터는 문서 안에 적는다. Vega(-Lite) 의 data.url 은 이 프로젝트 안의 파일(문서 기준 상대경로)만 — 인터넷 주소는 막는다.
// - 그리지 못하면 Mermaid 처럼 원문과 까닭을 보인다 (.diagram-error).

import { esc, docUrl } from './util.js';
import { mermaidTheme } from './theme.js';
import { openLightbox } from './ui.js';
import { t } from './i18n.js';

const LIB = '/static/vendor';
const FONT = '"Segoe UI", "Malgun Gothic", "Noto Sans KR", sans-serif';   // mermaid.js 와 같은 글꼴
// Graphviz 는 글꼴 없이 글자 폭을 어림한다. 한글을 Times(기본)로 어림하면 상자보다 넓어지므로 Verdana 로 어림해 배치하고,
// 화면에는 앱 글꼴로 그린다 (사용자가 fontname 을 정했으면 그대로)
const DOT_FONT = 'Verdana';

// 종류 (markdown.js 의 CHART_LANGS 가 코드 블록의 언어 이름으로 정해 pre.lec-chart 의 data-chart 에 단다)
export const CHART_NAMES = { 'vega-lite': 'Vega-Lite', vega: 'Vega', echarts: 'ECharts', dot: 'Graphviz' };

// ---- 라이브러리 ------------------------------------------------------------------

const loading = new Map();   // 주소 → Promise (한 번만)

function load(src) {
  if (!loading.has(src)) {
    loading.set(src, new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = () => {
        loading.delete(src);
        reject(new Error(t('차트 라이브러리를 불러오지 못했습니다. Lectern 을 다시 설치하면 고쳐집니다')));
      };
      document.head.append(s);
    }));
  }
  return loading.get(src);
}

/** 불러온 뒤 진짜 라이브러리인지 (문서 속 id="vega" 같은 요소가 window.vega 로 잡혀 있을 수 있다) */
async function library(files, test) {
  for (const f of files) await load(`${LIB}/${f}`);
  const lib = test();
  if (!lib) throw new Error(t('차트 라이브러리를 불러오지 못했습니다. Lectern 을 다시 설치하면 고쳐집니다'));
  return lib;
}

const LIBS = {
  vega: () => library(['vega/vega.min.js'], () => typeof window.vega?.View === 'function' && window.vega),
  'vega-lite': () => library(['vega/vega.min.js', 'vega/vega-lite.min.js'], () => typeof window.vegaLite?.compile === 'function' && window.vegaLite),
  echarts: () => library(['echarts/echarts.min.js'], () => typeof window.echarts?.init === 'function' && window.echarts),
  dot: () => library(['viz/viz-global.js'], () => typeof window.Viz?.instance === 'function' && window.Viz),
};

let viz = null;   // Graphviz (WebAssembly) — 한 번 만들어 둔다
const graphviz = async () => {
  const Viz = await LIBS.dot();
  viz ||= Viz.instance().catch((e) => {
    viz = null;
    throw e;
  });
  return viz;
};

// ---- 설정 읽기 ------------------------------------------------------------------

class SpecError extends Error {}

/**
 * JSON 설정을 읽는다. JSON 이 아니면 JS 객체 글처럼 — 주석(// /* *\/), 따옴표 없는 키, 작은따옴표, 끝 쉼표, 16진수,
 * 맨 앞의 'option =' (const·let·var) 과 끝의 ';'. 함수·식은 안 된다 (돌리지 않는다).
 */
export function parseSpec(text) {
  try {
    return JSON.parse(text);
  } catch { /* 아래에서 너그럽게 */ }
  const src = text;
  let i = 0;
  const fail = (fn = false) => {
    const line = src.slice(0, i).split('\n').length;
    throw new SpecError(fn ? t('함수는 쓸 수 없습니다 — 값만 적습니다 (블록 {line}행)', { line })
      : t('설정을 읽지 못했습니다 — JSON 형식을 확인하세요 (블록 {line}행)', { line }));
  };
  const at = (re) => {
    re.lastIndex = i;
    const m = re.exec(src);
    return m ? m[0] : null;
  };
  const skip = () => {
    for (;;) {
      while (i < src.length && /\s/.test(src[i])) i++;
      if (src.startsWith('//', i)) {
        while (i < src.length && src[i] !== '\n') i++;
      } else if (src.startsWith('/*', i)) {
        const end = src.indexOf('*/', i + 2);
        if (end < 0) fail();
        i = end + 2;
      } else {
        return;
      }
    }
  };
  const ESC = { n: '\n', t: '\t', r: '\r', b: '\b', f: '\f', v: '\v', 0: '\0' };
  const string = () => {
    const quote = src[i++];
    let out = '';
    while (i < src.length && src[i] !== quote) {
      const c = src[i++];
      if (c === '\n') fail();
      if (c !== '\\') {
        out += c;
        continue;
      }
      const e = src[i++];
      if (e === 'u') {
        out += String.fromCharCode(parseInt(src.slice(i, i + 4), 16));
        i += 4;
      } else if (e !== '\n') {
        out += ESC[e] ?? e;
      }
    }
    if (src[i++] !== quote) fail();
    return out;
  };
  const NAME = /[A-Za-z_$][\w$]*/y;
  const NUMBER = /[-+]?(?:0[xX][\da-fA-F]+|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|Infinity)|NaN/y;
  const value = () => {
    skip();
    const c = src[i];
    if (c === '{' || c === '[') {
      const isObj = c === '{';
      const close = isObj ? '}' : ']';
      const out = isObj ? {} : [];
      i++;
      for (;;) {
        skip();
        if (src[i] === close) {
          i++;
          return out;
        }
        if (isObj) {
          let key;
          if (src[i] === '"' || src[i] === "'") key = string();
          else if ((key = at(NAME) ?? at(NUMBER)) != null) i += key.length;
          else fail();
          skip();
          if (src[i] === '(') fail(true);   // 메서드 (formatter() { … })
          if (src[i++] !== ':') fail();
          // __proto__ 같은 키도 그 이름의 값으로 (프로토타입을 바꾸지 않게)
          Object.defineProperty(out, key, { value: value(), enumerable: true, writable: true, configurable: true });
        } else {
          out.push(value());
        }
        skip();
        if (src[i] === ',') i++;
        else if (src[i] !== close) fail();
      }
    }
    if (c === '"' || c === "'") return string();
    const num = at(NUMBER);
    if (num != null) {
      i += num.length;
      return Number(num);
    }
    const word = at(NAME);
    if (word === 'true' || word === 'false' || word === 'null') {
      i += word.length;
      return word === 'true' ? true : word === 'false' ? false : null;
    }
    if (word === 'function' || c === '(' || c === '`') fail(true);
    return fail();
  };
  skip();   // 앞의 주석
  const head = at(/(?:(?:const|let|var)\s+)?[A-Za-z_$][\w$]*\s*=(?!=)/y);   // option =
  if (head) i += head.length;
  const out = value();
  skip();
  if (src[i] === ';') i++;
  skip();
  if (i < src.length) fail();
  return out;
}

/** 목차·모아 보기의 이름표: '종류 · 제목' (제목은 설정의 title, Graphviz 는 label) */
export function chartLabel(kind, src) {
  let title = '';
  if (kind === 'dot') {
    // 그래프 이름 (digraph 이름 {), 없으면 처음 나오는 label
    title = /^\s*(?:strict\s+)?(?:di)?graph\s+("?)([^"{\s]+)\1/im.exec(src)?.[2] || /\blabel\s*=\s*"([^"]*)"/.exec(src)?.[1] || '';
  } else {
    try {
      const spec = parseSpec(src);
      const tt = Array.isArray(spec?.title) ? spec.title[0] : spec?.title;
      title = typeof tt === 'string' ? tt : (typeof tt?.text === 'string' ? tt.text : '');
    } catch { /* 이름만 */ }
  }
  return [CHART_NAMES[kind], title.trim()].filter(Boolean).join(' · ');
}

// ---- 색 -------------------------------------------------------------------------

/** 스타일의 색 (Mermaid 색표와 같은 것): 글자·선·테두리·바탕, 어두운지 */
function colors() {
  const v = mermaidTheme().themeVariables;
  return { dark: !!v.darkMode, text: v.textColor, line: v.lineColor, border: v.primaryBorderColor, bg: v.background };
}

// 글자 크기는 본문에 맞게 라이브러리 기본보다 조금 크게 (Vega 는 10~11px, ECharts 제목은 18px 굵게)
function vegaConfig(c) {
  const axis = {
    labelColor: c.line, titleColor: c.text, domainColor: c.line, tickColor: c.line, gridColor: c.line, gridOpacity: 0.22,
    labelFont: FONT, titleFont: FONT, labelFontSize: 12, titleFontSize: 12, titleFontWeight: 600,
  };
  const legend = { labelColor: c.text, titleColor: c.text, labelFont: FONT, titleFont: FONT, labelFontSize: 12, titleFontSize: 12, titleFontWeight: 600 };
  return {
    background: null, font: FONT,
    title: { color: c.text, subtitleColor: c.line, font: FONT, fontSize: 15, fontWeight: 600, subtitleFontSize: 12 },
    axis, legend,
    header: { labelColor: c.text, titleColor: c.text, labelFont: FONT, titleFont: FONT, labelFontSize: 12, titleFontSize: 13 },
    view: { stroke: c.line, strokeOpacity: 0.3 },
    text: { color: c.text }, rule: { color: c.line },
  };
}

function echartsTheme(c) {
  const grid = fade(c.line, 0.25);
  const axis = {
    axisLine: { lineStyle: { color: c.line } }, axisTick: { lineStyle: { color: c.line } }, axisLabel: { color: c.line },
    splitLine: { lineStyle: { color: [grid] } }, nameTextStyle: { color: c.text },
  };
  return {
    // 바탕은 문서 바탕색 — 비워 두면 ECharts 가 밝은 바탕으로 보고 바깥 글자(원그래프 이름표 등)에 흰 테두리를 두른다.
    // 글꼴: ECharts 는 style="font-family:…" 에 그대로 넣으므로 큰따옴표가 있으면 속성이 깨진다 — 작은따옴표로
    backgroundColor: c.bg, textStyle: { fontFamily: FONT.replace(/"/g, "'"), color: c.text },
    title: { textStyle: { color: c.text, fontSize: 15, fontWeight: 600 }, subtextStyle: { color: c.line } },
    legend: { textStyle: { color: c.text } },
    categoryAxis: axis, valueAxis: axis, logAxis: axis, timeAxis: axis,
    radar: { axisName: { color: c.text }, axisLine: { lineStyle: { color: grid } }, splitLine: { lineStyle: { color: grid } } },
  };
}

let paint = null;   // 색 글자를 읽는 캔버스

/** 색 글자(이름·#hex·rgb) → [r, g, b] (모르면 null) */
function rgbOf(color) {
  paint ||= document.createElement('canvas').getContext('2d');
  paint.fillStyle = '#000';
  paint.fillStyle = color;
  const m = /^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(paint.fillStyle);
  return m ? m.slice(1).map((x) => parseInt(x, 16)) : null;
}

/** 밝기 0~1 (모르면 null) */
function luma(color) {
  const c = rgbOf(color);
  return c ? (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255 : null;
}

/** 그 색을 alpha 만큼 비치게 (ECharts 는 색을 스스로 읽으므로 color-mix 대신 rgba) */
function fade(color, alpha) {
  const c = rgbOf(color);
  return c ? `rgba(${c.join(', ')}, ${alpha})` : color;
}

/** Graphviz 그림을 스타일 색으로: 흰 바탕은 비우고, 기본 검정은 글자·선·테두리 색으로, 기본 글꼴(어림용 Verdana)은 앱 글꼴로 */
function paintGraph(svg, c) {
  svg.querySelector('g.graph > polygon[fill="white"]')?.setAttribute('fill', 'none');
  for (const el of svg.querySelectorAll('[stroke="black"]')) el.setAttribute('stroke', el.closest('g.edge') ? c.line : c.border);
  for (const el of svg.querySelectorAll('[fill="black"]')) el.setAttribute('fill', el.closest('g.edge') ? c.line : c.text);
  for (const text of svg.querySelectorAll('text')) {
    if (/^Verdana/i.test(text.getAttribute('font-family') || '')) text.setAttribute('font-family', FONT);
    if (text.hasAttribute('fill')) continue;
    // 채운 상자 안의 글자는 그 채움의 밝기에 맞춰 (어두운 스타일에서 밝은 상자에 밝은 글자가 되지 않게)
    const shape = text.closest('g.node, g.cluster')?.querySelector('polygon, ellipse, path');
    const fill = shape?.getAttribute('fill');
    const l = fill && fill !== 'none' ? luma(fill) : null;
    text.setAttribute('fill', l == null ? c.text : (l > 0.55 ? '#1f2933' : '#f5f7fa'));
  }
}

// ---- 그리기 ---------------------------------------------------------------------

/** Vega(-Lite) 의 데이터 주소: 이 문서 기준 상대경로로, 이 프로젝트 안의 파일만. 막은 것은 problems 에 (Vega 는 오류를 던지지 않고 적기만 한다) */
function vegaLoader(vega, ctx, problems) {
  const loader = vega.loader({ mode: 'http', http: { credentials: 'same-origin' } });
  const base = new URL(docUrl(ctx.tab, ctx.path), location.origin);
  loader.sanitize = async (uri, options) => {
    // 그림 속 링크(href)는 풀어 버리고 그림(image)은 그리지 않으므로 (문서 속 SVG 그림처럼 — D19) 빈 주소로 — 데이터만 읽는다
    if (options?.context === 'href' || options?.context === 'image') return { href: '' };
    const ref = ctx.resolveRef(String(uri), base, ctx.tab);
    if (ref.kind !== 'local' || ref.isDir) {
      const e = new SpecError(t('데이터는 이 프로젝트 안의 파일만 읽습니다 — 문서 기준 상대경로로 적으세요: {url}', { url: uri }));
      problems.unshift(e);
      throw e;
    }
    return { href: docUrl(ctx.tab, ref.path) };
  };
  return loader;
}

/** Vega 의 오류 기록: 데이터를 못 읽어도 빈 그림을 그리므로, 적힌 오류를 모아 두었다가 그림 대신 원문과 까닭을 보인다 */
function vegaLogger(vega, problems) {
  const log = vega.logger(vega.Error);
  log.error = (...args) => {
    problems.push(args.find((a) => a instanceof Error) || new Error(args.map(String).join(' ')));
    return log;
  };
  log.warn = (...args) => {   // 데이터를 못 읽은 것은 경고로 온다 ('Loading failed', 주소, 오류)
    if (/loading failed/i.test(String(args[0]))) problems.push(new SpecError(t('데이터 파일을 읽지 못했습니다 — 경로를 확인하세요: {url}', { url: args[1] })));
    return log;
  };
  return log;
}

// 그리는 함수: {svg, fluid} — fluid 면 문서 폭을 따른 것이라 폭이 바뀌면 다시 그린다 (renderCharts)

async function drawVega(kind, src, width, ctx) {
  const spec = parseSpec(src);
  const config = vegaConfig(colors());
  let fluid = false;
  if (spec && typeof spec === 'object') {
    // 'container' 크기는 문서 폭에 맞춘다 (그릴 틀이 따로 없다). 축·범례 자리를 뺀 그림 폭이다
    if (spec.width === 'container') {
      spec.width = Math.max(200, width - 110);
      fluid = true;
    }
    if (spec.height === 'container') spec.height = 300;
  }
  const vega = await LIBS.vega();
  let vgSpec = spec;
  if (kind === 'vega-lite') vgSpec = (await LIBS['vega-lite']()).compile(spec, { config }).spec;
  const problems = [];
  const view = new vega.View(vega.parse(vgSpec, kind === 'vega' ? config : undefined), {
    renderer: 'none', loader: vegaLoader(vega, ctx, problems), logger: vegaLogger(vega, problems),
  });
  try {
    const svg = await view.toSVG();
    if (problems.length) throw problems[0];
    return { svg, fluid };
  } finally {
    view.finalize();
  }
}

async function drawECharts(src, width) {
  const option = parseSpec(src);
  if (!option || typeof option !== 'object' || Array.isArray(option)) throw new SpecError(t('설정을 읽지 못했습니다 — JSON 형식을 확인하세요 (블록 {line}행)', { line: 1 }));
  // 크기: 폭은 문서 폭(설정의 width 가 숫자면 그것), 높이는 설정의 height 아니면 360 — ECharts 에는 없는 키라 여기서만 쓴다
  const height = Number.isFinite(option.height) ? option.height : 360;
  const fluid = !Number.isFinite(option.width);
  const w = fluid ? width : option.width;
  delete option.height;
  delete option.width;
  const echarts = await LIBS.echarts();
  const chart = echarts.init(null, echartsTheme(colors()), { renderer: 'svg', ssr: true, width: Math.max(200, w), height: Math.max(120, height) });
  try {
    chart.setOption({ ...option, animation: false });
    return { svg: chart.renderToSVGString(), fluid };
  } finally {
    chart.dispose();
  }
}

async function drawDot(src) {
  const v = await graphviz();
  const font = { fontname: DOT_FONT };
  return { svg: v.renderString(src, { format: 'svg', graphAttributes: font, nodeAttributes: font, edgeAttributes: font }), fluid: false };
}

function showSource(node, message) {
  const box = document.createElement('div');
  box.className = 'diagram-error';
  box.dataset.chart = node.dataset.chart;
  if (node.dataset.lines) box.dataset.lines = node.dataset.lines;   // 본문 우클릭 메뉴의 원문 복사용
  box.innerHTML = `<p>${esc(message)}</p><pre><code>${esc(node.dataset.source ?? node.textContent)}</code></pre>`;
  node.replaceWith(box);
}

// 문서 폭을 따르는 그림(fluid)은 폭이 바뀌면 다시 그린다 — 화면 밖 무대에서 그린 폭과 목차가 나온 뒤의 폭이 다르고,
// 사이드바·터미널·창 크기에 따라서도 바뀐다. 줄여서 보이면 글자가 작아지므로 그 폭으로 새로 그린다
const drawn = new WeakMap();   // pre.lec-chart → {ctx, width, seq, timer}
let resizer = null;

function watchWidth(node) {
  resizer ||= new ResizeObserver((entries) => {
    for (const { target } of entries) {
      const info = drawn.get(target);
      if (!target.isConnected || !info) {
        resizer.unobserve(target);
        continue;
      }
      const width = target.clientWidth;
      if (!width || Math.abs(width - info.width) < 16) continue;   // 접힌 절(폭 0)이거나 거의 그대로
      clearTimeout(info.timer);
      info.timer = setTimeout(() => draw(target, info.ctx), 150);
    }
  });
  resizer.observe(node);
}

/** 블록 하나를 그린다. 처음 그리다 실패하면 원문과 까닭으로 바꾼다 (다시 그리다 실패하면 그린 것을 둔다) */
async function draw(node, ctx) {
  const kind = node.dataset.chart;
  const src = node.dataset.source;
  const width = node.clientWidth || 640;
  const info = drawn.get(node) || { ctx, seq: 0 };
  const seq = ++info.seq;
  let out;
  try {
    if (kind === 'echarts') out = await drawECharts(src, width);
    else if (kind === 'dot') out = await drawDot(src);
    else out = await drawVega(kind, src, width, ctx);
  } catch (e) {
    if (drawn.has(node)) return;
    const why = String(e?.message || e).split('\n')[0];
    showSource(node, e instanceof SpecError ? why : t('{kind} 그림을 그리지 못해 원문을 표시합니다: {error}', { kind: CHART_NAMES[kind], error: why }));
    return;
  }
  if (seq !== info.seq) return;   // 그사이 더 나중에 시작한 그리기가 있다
  const holder = document.createElement('div');
  holder.innerHTML = ctx.sanitize(out.svg);
  const el = holder.querySelector('svg');
  if (!el) {
    if (!drawn.has(node)) showSource(node, t('{kind} 그림을 그리지 못해 원문을 표시합니다: {error}', { kind: CHART_NAMES[kind], error: 'SVG' }));
    return;
  }
  for (const a of el.querySelectorAll('a')) a.replaceWith(...a.childNodes);   // 그림 속 링크는 풀어 둔다 (누르면 앱 창이 떠나지 않게)
  if (!el.getAttribute('viewBox')) {   // 크게 보기는 크기 속성을 지우고 viewBox 로 늘린다
    const w = parseFloat(el.getAttribute('width'));
    const h = parseFloat(el.getAttribute('height'));
    if (w && h) el.setAttribute('viewBox', `0 0 ${w} ${h}`);
  }
  node.replaceChildren(el);
  if (kind === 'dot') paintGraph(el, colors());   // 글자 폭을 재지 않으므로 붙인 뒤 어디서든
  if (!drawn.has(node)) {
    node.classList.add('chart-ok');
    node.title = t('누르면 크게 봅니다');
    node.addEventListener('click', () => openLightbox(node.querySelector('svg').cloneNode(true)));
    if (out.fluid) watchWidth(node);
  }
  info.width = width;
  drawn.set(node, info);
}

/**
 * root 안의 pre.lec-chart 를 그림으로 바꾼다. root 는 화면(문서 트리)에 붙어 있어야 폭을 잰다 (doc.js 의 무대).
 * ctx: {tab, path — 문서, sanitize — doc.js 의 sanitizeHtml, resolveRef — doc.js 의 것}
 */
export async function renderCharts(root, ctx) {
  for (const node of root.querySelectorAll('pre.lec-chart')) {
    node.dataset.source = node.textContent;
    await draw(node, ctx);
  }
}
