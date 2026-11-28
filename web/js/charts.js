// 차트·도해 (D56): ```vega-lite·```vega·```echarts·```plotly·```dot(```graphviz) 코드 블록을 그림(SVG)으로 — Mermaid(mermaid.js)와 같은 자리.
//
// - 라이브러리는 그 블록이 있는 문서를 처음 그릴 때 불러온다 (web/vendor 의 vega·echarts·plotly·viz). 전역(vega·vegaLite·echarts·Plotly·Viz)은
//   문서 속 id 가 가릴 수 있으므로 진짜 라이브러리인지 본다 (mermaid.js 처럼).
// - 모두 움직이지 않는 SVG 로 그린다 — 인쇄·우클릭 복사(PNG)·눌러서 크게 보기가 Mermaid 와 같다. 마우스를 올려 값 보기·확대 같은
//   움직임은 없다. 그린 SVG 는 문서처럼 DOMPurify 로 거른다 (doc.js 의 sanitizeHtml — 인터넷 그림을 부르는 길), 링크는 푼다.
// - 색은 Mermaid 와 같은 스타일 색표(theme.js 의 mermaidTheme), 글꼴은 앱 글꼴. 스타일을 바꾸면 문서를 다시 그리므로 따라온다.
// - 설정은 JSON. ECharts 예제처럼 따옴표 없는 키·작은따옴표·주석·끝 쉼표·'option =' 도 읽는다 (parseSpec). 함수는 안 된다 —
//   문서가 스크립트를 돌리지 않는 것과 같은 까닭 (D27).
// - 데이터는 문서 안에 적는다. Vega(-Lite) 의 data.url 은 이 프로젝트 안의 파일(문서 기준 상대경로)만 — 인터넷 주소는 막는다.
//   Plotly 의 지도(인터넷의 지도 자료가 있어야 한다)는 그리지 않고, 배경 그림은 data: 주소만 둔다.
// - 그리지 못하면 Mermaid 처럼 원문과 까닭을 보인다 (.diagram-error).

import { html, raw, setHtml } from './html.js';
import { docUrl } from './util.js';
import { mermaidTheme } from './theme.js';
import { styleOf, colorsOf, dotAttributes, decorateDot, chartPalette, defaultColors, palette } from './diagramstyles.js';
import { openLightbox } from './ui.js';
import { SLIDE_ZOOM } from './slides.js';
import { t } from './i18n.js';
import { addChartTools } from './chartdata.js';

const LIB = '/static/vendor';
const FONT = '"Segoe UI", "Malgun Gothic", "Noto Sans KR", sans-serif';   // mermaid.js 와 같은 글꼴
// Graphviz 는 글꼴 없이 글자 폭을 어림한다. 한글을 Times(기본)로 어림하면 상자보다 넓어지므로 Verdana 로 어림해 배치하고,
// 화면에는 앱 글꼴로 그린다 (사용자가 fontname 을 정했으면 그대로)
const DOT_FONT = 'Verdana';

// 종류 (markdown.js 의 CHART_LANGS 가 코드 블록의 언어 이름으로 정해 pre.lec-chart 의 data-chart 에 단다)
export const CHART_NAMES = { 'vega-lite': 'Vega-Lite', vega: 'Vega', echarts: 'ECharts', dot: 'Graphviz', plotly: 'Plotly' };

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
  plotly: () => library(['plotly/plotly.min.js'], () => typeof window.Plotly?.toImage === 'function' && window.Plotly),
};

/** 빠른 차트(quickchart.js)가 쓴다 — ECharts 와 지금 스타일의 색 */
export async function chartLib() {
  return { echarts: await LIBS.echarts(), theme: echartsTheme(colors(), chartPalette(defaultColors())) };   // 색 조합은 설정의 기본 (D213)
}

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
      const raw = kind === 'plotly' ? spec?.layout?.title : spec?.title;   // Plotly 는 layout.title
      const tt = Array.isArray(raw) ? raw[0] : raw;
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

// 글자 크기는 본문에 맞게 라이브러리 기본보다 조금 크게 (Vega 는 10~11px, ECharts 제목은 18px 굵게).
// pal: 색 조합(D213 — chartPalette)의 계열 색 — 없으면 라이브러리의 기본색. 차트가 색을 정했으면 그것이 먼저다.
// 색으로 나누지 않은 차트(막대 하나·선 하나)는 계열 색 목록이 아니라 mark.color 를 쓴다 — 그 색도 색 조합의 첫 색으로 (0.113.1 — 없으면 어느 번호든 같았다)
function vegaConfig(c, pal = null) {
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
    ...(pal ? { range: { category: pal.series, ramp: pal.ramp, heatmap: pal.ramp }, mark: { color: pal.series[0] } } : {}),
  };
}

function echartsTheme(c, pal = null) {
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
    // 열지도 등 연속 값의 색(visualMap)도 색 조합의 두 끝으로 — 설정에 inRange 를 적었으면 그것 (0.113.1)
    ...(pal ? { color: pal.series, visualMap: { inRange: { color: pal.ramp } } } : {}),
  };
}

let paint = null;   // 색 글자를 읽는 캔버스

/** Plotly 의 기본 모양 (설정에 layout.template 가 없을 때만 — Python 의 fig.to_json() 처럼 자기 template 이 있으면 그것) */
function plotlyTemplate(c) {
  const axis = { gridcolor: fade(c.line, 0.22), linecolor: c.line, zerolinecolor: fade(c.line, 0.45), tickcolor: c.line, tickfont: { color: c.line } };
  const clear = 'rgba(0,0,0,0)';
  return {
    layout: {
      font: { family: FONT.replace(/"/g, "'"), color: c.text, size: 12 }, title: { font: { size: 15 } },
      paper_bgcolor: clear, plot_bgcolor: clear, xaxis: axis, yaxis: axis, legend: { font: { color: c.text } },
      polar: { bgcolor: clear, angularaxis: axis, radialaxis: axis }, ternary: { bgcolor: clear, aaxis: axis, baxis: axis, caxis: axis },
    },
  };
}

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

// Lectern 슬라이드에서 (D188): 그리는 폭의 하한 (좁은 칸에서도 글자를 SLIDE_ZOOM 배로 키울 수 있게), 범례를 아래로 옮기는 폭 (슬라이드 450px)
const MIN_W = 200;
const SLIDE_MIN_W = 120;
const NARROW = 265;

/** 슬라이드에서 숫자로 적은 폭·높이는 비율로만 — 폭은 칸에 맞춘다. 높이/폭 (둘 다 숫자가 아니면 0) */
const ratioOf = (w, h) => (Number.isFinite(w) && Number.isFinite(h) && w > 0 && h > 0 ? h / w : 0);

async function drawVega(kind, src, width, ctx, fit = 0, slide = false, pal = null) {
  const spec = parseSpec(src);
  const config = vegaConfig(colors(), pal);
  let fluid = false;
  if (spec && typeof spec === 'object') {
    const single = !['facet', 'repeat', 'concat', 'hconcat', 'vconcat'].some((k) => k in spec);
    if (slide && kind === 'vega-lite' && single && !spec.autosize) {
      const ratio = ratioOf(spec.width, spec.height);
      if (Number.isFinite(spec.width)) spec.width = 'container';
      if (spec.width === 'container' && Number.isFinite(spec.height) && (fit || ratio)) delete spec.height;
      if (!fit && ratio) fit = Math.round(Math.max(SLIDE_MIN_W, width) * ratio);
      if (width < NARROW) config.legend = { ...config.legend, orient: 'bottom' };   // 좁은 칸: 오른쪽 범례가 그래프 폭을 먹는다 (설정에 적었으면 그것)
    }
    // 슬라이드의 칸: 축·범례까지 칸 크기에 맞춰 그린다. 크게 그려 통째로 줄이면 글자까지 작아져 뭉개진다
    if (fit && kind === 'vega-lite' && single && spec.width === 'container' && spec.height == null && !spec.autosize) {
      spec.width = Math.max(slide ? SLIDE_MIN_W : MIN_W, width);
      spec.height = Math.max(80, fit);
      spec.autosize = { type: 'fit', contains: 'padding' };
      fluid = true;
    }
    // 'container' 크기는 문서 폭에 맞춘다 (그릴 틀이 따로 없다). 축·범례 자리를 뺀 그림 폭이다
    if (spec.width === 'container') {
      spec.width = Math.max(slide ? SLIDE_MIN_W : MIN_W, width - 110);
      fluid = true;
    }
    if (spec.height === 'container' || (fit && spec.height == null)) spec.height = fit ? Math.max(80, fit - 50) : 300;
    if (fit) spec.config = { axisX: { labelAngle: 0, labelOverlap: true }, ...spec.config };   // 칸은 좁아 눕히면 읽기 어렵다 — 겹치는 글자는 건너뛴다
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
    // 칸 크기에 맞춰 그릴 때 범례가 더 길면 그림 밖으로 잘린다 — 끝까지 보이게 키를 알린다 (draw 가 늘린다)
    const bottom = spec?.autosize?.type === 'fit' ? (view.scenegraph().root.bounds?.y2 ?? 0) + view.origin()[1] : 0;
    return { svg, fluid, bottom };
  } finally {
    view.finalize();
  }
}

/**
 * ECharts 설정에서 그림 주소를 지운다 — 그리는 동안 ECharts 가 그림을 불러오므로 (graphic 의 image, 배경·무늬의 image,
 * 'image://주소' 기호). data: 주소만 둔다. 글자 단계까지 내려가며 본다
 */
function dropImages(node, depth = 0) {
  if (!node || typeof node !== 'object' || depth > 40) return;
  for (const key of Object.keys(node)) {
    const v = node[key];
    if (typeof v === 'string') {
      if (key === 'image' && !/^data:/i.test(v)) delete node[key];
      else if (/^image:\/\//i.test(v) && !/^image:\/\/data:/i.test(v)) node[key] = 'emptyCircle';
    } else {
      dropImages(v, depth + 1);
    }
  }
}

async function drawECharts(src, width, fit = 0, slide = false, pal = null) {
  const option = parseSpec(src);
  if (!option || typeof option !== 'object' || Array.isArray(option)) throw new SpecError(t('설정을 읽지 못했습니다 — JSON 형식을 확인하세요 (블록 {line}행)', { line: 1 }));
  // 크기: 폭은 문서 폭(설정의 width 가 숫자면 그것), 높이는 설정의 height 아니면 360 — ECharts 에는 없는 키라 여기서만 쓴다.
  // 슬라이드에서는 폭은 칸에 맞추고 높이는 남은 높이, 없으면 적은 크기의 비율로 (D188)
  let height = Number.isFinite(option.height) ? option.height : fit || 360;
  let fluid = !Number.isFinite(option.width);
  if (slide) {
    const ratio = ratioOf(option.width, option.height);
    height = fit || (ratio ? Math.max(SLIDE_MIN_W, width) * ratio : height);
    fluid = true;
  }
  const w = fluid ? width : option.width;
  delete option.height;
  delete option.width;
  dropImages(option);
  const echarts = await LIBS.echarts();
  const chart = echarts.init(null, echartsTheme(colors(), pal), { renderer: 'svg', ssr: true, width: Math.max(slide ? SLIDE_MIN_W : MIN_W, w), height: Math.max(120, height) });
  try {
    chart.setOption({ ...option, animation: false, ...(fit ? { backgroundColor: 'transparent' } : {}) });   // 칸의 바탕이 보이게
    return { svg: chart.renderToSVGString(), fluid };
  } finally {
    chart.dispose();
  }
}

// 인터넷의 지도 자료(나라 경계·지도 타일)가 있어야 하는 Plotly 종류 — 받지 않으므로 그리지 않는다
const PLOTLY_MAPS = /^(scattergeo|choropleth|scattermapbox|choroplethmapbox|densitymapbox|scattermap|choroplethmap|densitymap)$/;
// 연속 값을 색으로 칠하는 Plotly 종류 — colorscale 을 쓴다
const PLOTLY_RAMP = /^(heatmap|contour|histogram2d|histogram2dcontour)$/;

async function drawPlotly(src, width, fit = 0, slide = false, pal = null) {
  let fig = parseSpec(src);
  if (Array.isArray(fig)) fig = { data: fig };   // 그래프 목록만 적어도 된다
  if (!fig || typeof fig !== 'object' || !Array.isArray(fig.data)) throw new SpecError(t('Plotly 설정은 data(그래프 목록)와 layout 을 가진 JSON 입니다'));
  const map = fig.data.find((tr) => PLOTLY_MAPS.test(String(tr?.type)));
  if (map) throw new SpecError(t('지도 차트({type})는 인터넷의 지도 자료가 있어야 해서 그리지 않습니다', { type: map.type }));
  const layout = fig.layout && typeof fig.layout === 'object' ? fig.layout : {};
  // 그리는 동안 Plotly 가 그림을 불러오므로 미리 지운다 — 배경 그림(layout.images)·image 종류의 주소는 data: 만
  if (Array.isArray(layout.images)) layout.images = layout.images.filter((im) => /^data:/i.test(String(im?.source || '')));
  for (const tr of fig.data) if (tr?.type === 'image' && tr.source && !/^data:/i.test(String(tr.source))) delete tr.source;
  if (!layout.template) layout.template = plotlyTemplate(colors());
  if (pal && !layout.colorway) layout.colorway = pal.series;   // 색 조합 (D213) — 계열 색만, 자기 template 의 글자·바탕은 그대로
  if (pal) {
    // 연속 값의 색(열지도·등고선)은 colorway 를 쓰지 않는다 — 색을 적지 않은 그래프만 색 조합의 두 끝으로 (0.113.1). 그리는 동안만, 원문은 그대로
    for (const tr of fig.data) {
      if (!tr || !PLOTLY_RAMP.test(String(tr.type)) || tr.colorscale != null || layout.template?.data?.[tr.type]?.[0]?.colorscale != null) continue;
      tr.colorscale = [[0, pal.ramp[0]], [1, pal.ramp[1]]];
    }
  }
  // 크기: 폭은 문서 폭(layout.width 가 숫자면 그것), 높이는 layout.height 아니면 400.
  // 슬라이드에서는 폭은 칸에 맞추고 높이는 남은 높이, 없으면 적은 크기의 비율로. 좁은 칸은 범례를 아래로 (설정에 적었으면 그것) (D188)
  let fluid = !Number.isFinite(layout.width);
  let h = Number.isFinite(layout.height) ? layout.height : fit || 400;
  if (slide) {
    const ratio = ratioOf(layout.width, layout.height);
    h = fit || (ratio ? Math.max(SLIDE_MIN_W, width) * ratio : h);
    fluid = true;
    delete layout.width;
    delete layout.height;
    // 기본 여백(좌우 80px)은 웹 쪽의 것이라 칸에서는 그래프가 쪼그라든다 — 좁게 두고 축 글자만큼만 늘게 (설정에 적었으면 그것)
    if (layout.margin == null) {
      layout.margin = { l: 10, r: 10, t: layout.title ? 40 : 10, b: 10 };
      for (const key of new Set(['xaxis', 'yaxis', ...Object.keys(layout).filter((k) => /^[xy]axis\d+$/.test(k))])) {
        const axis = layout[key] && typeof layout[key] === 'object' ? layout[key] : {};
        layout[key] = { automargin: true, ...axis };
      }
    }
    const legend = layout.legend && typeof layout.legend === 'object' ? layout.legend : {};
    if (width < NARROW && legend.orientation == null && legend.x == null && legend.y == null) {
      layout.legend = { ...legend, orientation: 'h', x: 0, xanchor: 'left', yref: 'container', y: 0, yanchor: 'bottom' };
    }
  }
  const w = fluid ? width : layout.width;
  const Plotly = await LIBS.plotly();
  const url = await Plotly.toImage({ data: fig.data, layout }, { format: 'svg', width: Math.max(slide ? SLIDE_MIN_W : MIN_W, w), height: Math.max(120, h) });
  return { svg: decodeURIComponent(url.slice(url.indexOf(',') + 1)), fluid };
}

async function drawDot(src, marks) {
  const v = await graphviz();
  const font = { fontname: DOT_FONT };
  const a = dotAttributes(styleOf(src, 'dot', marks), colorsOf(src, 'dot', marks));   // 도해 스타일(D212)의 모양 — 원문이 정한 속성이 먼저다
  return { svg: v.renderString(src, { format: 'svg', graphAttributes: { ...a.graph, ...font }, nodeAttributes: { ...a.node, ...font }, edgeAttributes: { ...a.edge, ...font } }), fluid: false };
}

function showSource(node, message) {
  const box = document.createElement('div');
  box.className = 'diagram-error';
  box.dataset.chart = node.dataset.chart;
  if (node.dataset.lines) box.dataset.lines = node.dataset.lines;   // 본문 우클릭 메뉴의 원문 복사용
  setHtml(box, html`<p>${message}</p><pre><code>${node.dataset.source ?? node.textContent}</code></pre>`);
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
  // 색 조합 (D213): 블록의 '// 색: 2' > 문서의 '<!-- 도해: 색 2 -->'(ctx.marks) > 설정
  const colorsNo = colorsOf(src, kind === 'dot' ? 'dot' : 'chart', ctx.marks);
  const pal = kind === 'dot' ? null : chartPalette(colorsNo);
  node.dataset.diagramColors = String(colorsNo);
  const width = node.clientWidth || 640;
  // Lectern 슬라이드의 슬라이드(D59)에서는 좁게 그려 키운다 — 차트 글자가 슬라이드 글자와 어울리게 (slides.js 의 SLIDE_ZOOM)
  const slide = !!node.closest('.lec-slide');
  const zoom = slide ? SLIDE_ZOOM : 1;
  // 높이가 정해진 칸(배치·자리 칸) 안이면 차트를 칸의 남은 높이에 맞춘다 (남은 것이 없어도 120px — 넘치면 slides.js 가 글을 줄인다).
  // 장이 넘쳐 slides.js 가 높이를 청했으면(data-fit-height) 그 높이로 — 그림을 줄이면 글자까지 작아진다 (D188)
  const cell = node.closest('.lec-slide.lec-grid > .lec-cell, .lec-cell.lec-at');
  const px = (st, ...keys) => keys.reduce((sum, k) => sum + (parseFloat(st[k]) || 0), 0);
  const box = (el) => el.offsetHeight + px(getComputedStyle(el), 'marginTop', 'marginBottom');
  // 칸의 다른 것이 쓴 높이 = 칸 안 전체에서 차트 자신을 뺀 것. 캡션·자료가 있으면 차트는 칸의 바로 아래가 아니라 전시물(D184) 안에 있다 —
  // 칸의 자식만 빼면 차트가 든 전시물을 통째로 '다른 것'으로 세어 남은 높이가 0 이 됐다
  const used = cell ? [...cell.children].reduce((sum, el) => sum + box(el), px(getComputedStyle(cell), 'paddingTop', 'paddingBottom')) - box(node) : 0;
  const asked = slide ? Number(node.dataset.fitHeight) || 0 : 0;
  const fit = asked ? asked / zoom : cell ? Math.max(120, cell.clientHeight - used - 8) / zoom : 0;
  const info = drawn.get(node) || { ctx, seq: 0 };
  const seq = ++info.seq;
  let out;
  try {
    if (kind === 'echarts') out = await drawECharts(src, width / zoom, fit, slide, pal);
    else if (kind === 'plotly') out = await drawPlotly(src, width / zoom, fit, slide, pal);
    else if (kind === 'dot') out = await drawDot(src, ctx.marks);
    else out = await drawVega(kind, src, width / zoom, ctx, fit, slide, pal);
  } catch (e) {
    if (drawn.has(node)) return;
    const why = String(e?.message || e).split('\n')[0];
    showSource(node, e instanceof SpecError ? why : t('{kind} 그림을 그리지 못해 원문을 표시합니다: {error}', { kind: CHART_NAMES[kind], error: why }));
    return;
  }
  if (seq !== info.seq) return;   // 그사이 더 나중에 시작한 그리기가 있다
  const holder = document.createElement('div');
  setHtml(holder, raw(ctx.sanitize(out.svg)));
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
  if (out.bottom > parseFloat(el.getAttribute('height'))) {
    const h = Math.ceil(out.bottom) + 2;
    el.setAttribute('height', String(h));
    el.setAttribute('viewBox', `0 0 ${el.getAttribute('width')} ${h}`);
  }
  if (zoom !== 1) {
    const w = parseFloat(el.getAttribute('width')) || parseFloat(el.getAttribute('viewBox')?.split(/[\s,]+/)[2]);
    if (w) el.style.width = `${Math.min(width, w * zoom)}px`;
    el.style.height = 'auto';
  }
  node.replaceChildren(el);
  addChartTools(node, ctx, parseSpec);   // [표]·[복사] (D136) — 칸의 안을 바꿔 끼웠으니 다시
  if (kind === 'dot') {
    paintGraph(el, { ...colors(), border: palette(colorsNo).border });   // 글자 폭을 재지 않으므로 붙인 뒤 어디서든 (테두리는 색 조합의 색 — D213)
    const style = styleOf(src, 'dot', ctx.marks);
    node.dataset.diagramStyle = String(style);
    try {
      decorateDot(el, style, colorsNo);   // 강조 표시·묶음·단계 색·제목 상자 (D212)
    } catch (e) {
      console.warn('diagram style', e);
    }
  }
  if (!drawn.has(node)) {
    node.classList.add('chart-ok');
    node.title = t('누르면 크게 봅니다');
    node.addEventListener('click', (e) => {
      if (e.target.closest?.('.lec-chart-tools, .lec-chart-data')) return;
      openLightbox(node.querySelector(':scope > svg').cloneNode(true));
    });
    if (out.fluid) watchWidth(node);
    // 슬라이드의 넘침 맞춤이 높이를 청하면 다시 그린다 — slides.js 는 이 모듈을 부르지 않는다 (차례가 돈다)
    node.addEventListener('lec-chart-refit', () => {
      const it = drawn.get(node);
      if (it && node.isConnected) draw(node, it.ctx);
    });
  }
  info.width = width;
  drawn.set(node, info);
  node.dispatchEvent(new Event('lec-chart-drawn'));
}

/**
 * root 안의 pre.lec-chart 를 그림으로 바꾼다. root 는 화면(문서 트리)에 붙어 있어야 폭을 잰다 (doc.js 의 무대).
 * ctx: {tab, path — 문서, sanitize — doc.js 의 sanitizeHtml, resolveRef — doc.js 의 것, marks — 문서의 기본 도해 스타일·색 조합 (D213, 없어도 된다)}
 */
export async function renderCharts(root, ctx) {
  for (const node of root.querySelectorAll('pre.lec-chart')) {
    node.dataset.source = node.textContent;
    await draw(node, ctx);
  }
}
