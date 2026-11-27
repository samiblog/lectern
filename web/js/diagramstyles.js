// 도해 스타일 (D212) — Mermaid·Graphviz 그림의 모양을 번호로 고른다. "Mermaid 3번 스타일로" 처럼 Claude 에게 말할 수 있게.
//
// - 색은 지금 문서 스타일에서 (theme.js 의 mermaidTheme — 내 스타일이면 그 CSS 변수). 번호는 모양만 정한다: 상자·선·간격·굵기와
//   강조 표시를 칠하는 법. 그래서 어두운 스타일·인쇄에서도 어울린다.
// - 고르는 곳: 그림 블록 안의 줄 '%% 스타일: 3'(Mermaid)·'// 스타일: 3'(Graphviz — '#' 도) > 설정 diagram_style (기본 1 — 0.111 까지와 같은 모양).
//   번호 대신 이름('카드')도, 'style' 도 같다. 주석이라 다른 곳(GitHub 등)에서는 그 줄 없이 기본 모양으로 그린다.
// - 강조 표시 셋 — key(핵심)·warn(주의)·muted(보조): Mermaid 'A:::key'·'class A key', Graphviz 'A [class="key"]'. 색은 번호가 정한다.
// - 제목 상자(8~10): 줄을 바꾼 상자는 첫 줄이 제목, 나머지가 내용 — Mermaid '<br>', Graphviz '\n'. 한 줄짜리 상자는 제목만.
// - 문서는 번호와 표시 이름만 고른다. CSS·설정은 이 표에서만 나온다 (D56 — 문서가 할 수 있는 것을 늘리지 않는다).
// - 번호는 바꾸지 않는다 — 새 스타일은 뒤에 붙인다 (lectern/config.py 의 DIAGRAM_STYLES 가 수를 안다).
// - 색 조합 (D213): 모양과 따로 고르는 둘째 번호 1~8 — 차트의 계열 색과 도해의 상자·강조·단계 색. 글자·바탕·선은 문서 스타일 그대로.
//   그림·차트 블록의 '%% 색: 2'·'// 색: 2' (한 줄에 '%% 스타일: 8 · 색: 2' 도) > 문서의 '<!-- 도해: 스타일 8 · 색 2 -->' > 설정 diagram_colors.
// - 방향(가로·세로)은 원문의 것(flowchart LR·TD, rankdir) — 번호에 넣지 않는다. 우클릭 '방향 바꾸기' 가 그 글자만 바꾼다 (flipDirection).

import { S } from './store.js';
import { mermaidTheme } from './theme.js';
import { t } from './i18n.js';

// ---- 색 -------------------------------------------------------------------------

let paint = null;
/** 색 글자 → [r, g, b] (모르는 것·비침은 null). 캔버스가 '#rrggbb' 로 바꿔 준다 */
function rgbOf(color) {
  if (!color || /^transparent$/i.test(color)) return null;
  paint ||= document.createElement('canvas').getContext('2d');
  paint.fillStyle = '#000001';
  paint.fillStyle = color;
  const m = /^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(paint.fillStyle);
  return m ? m.slice(1).map((x) => parseInt(x, 16)) : null;
}
const hexOf = (c) => `#${c.map((x) => Math.round(Math.max(0, Math.min(255, x))).toString(16).padStart(2, '0')).join('')}`;
/** a 를 t 만큼, b 를 나머지만큼 섞은 색 */
function mix(a, b, k) {
  const x = rgbOf(a);
  const y = rgbOf(b);
  if (!x || !y) return a;
  return hexOf(x.map((v, i) => v * k + y[i] * (1 - k)));
}
const luma = (c) => (c ? (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255 : null);
/** 그 바탕에 읽히는 글자색 */
function ink(fill, p) {
  const l = luma(rgbOf(fill));
  return l == null ? p.text : (l > 0.55 ? '#1f2933' : '#f5f7fa');
}
/** 옅게 칠한 그 색 위의 글자 — 밝은 스타일은 진하게, 어두운 스타일은 밝게 */
const deep = (c, p) => (p.dark ? mix(c, '#ffffff', 0.55) : mix(c, '#000000', 0.55));
const shadow = (p) => (p.dark ? 'rgba(0, 0, 0, .55)' : 'rgba(23, 48, 79, .2)');

/** 어두운 바탕에서는 진한 색을 밝게 — 읽힐 만큼(밝기 0.45) 흰색을 섞는다 */
function onDark(c) {
  for (let k = 1; k > 0.25; k -= 0.05) {
    const x = mix(c, '#ffffff', k);
    if (luma(rgbOf(x)) >= 0.45) return x;
  }
  return mix(c, '#ffffff', 0.25);
}

// 단계 색(7)이 묶음마다 돌려 쓰는 색 (색 조합 1)
const ZONES = { light: ['#c2410c', '#15803d', '#7c3aed', '#0e7490', '#b45309'], dark: ['#f0883e', '#3fb950', '#a371f7', '#39c5cf', '#e3b341'] };

/**
 * 색 조합 (D213) — 번호는 바꾸지 않는다 (config.DIAGRAM_COLORS 가 수를 안다). series: 차트의 계열 색(차례대로),
 * strong: 도해의 기본 상자 색, accent: 핵심(key) 강조, zones: 단계 색의 묶음 색 (없으면 series). 어두운 스타일에서는 밝게 (onDark)
 */
const PALETTES = [
  { key: 'doc', name: t('문서 스타일'), words: ['문서스타일', '문서', 'doc', 'document', 'documentstyle'], tip: t('지금 그대로 — 차트는 라이브러리의 기본색, 도해는 문서 스타일의 색') },   // i18n-ok (찾는 말)
  { key: 'navy', name: t('보고서 남색'), words: ['보고서남색', '남색', 'navy', 'reportnavy'], tip: t('남색 농담 + 주황 강조 하나 — 보고서·흑백 인쇄에도'),   // i18n-ok (찾는 말)
    series: ['#17304f', '#2f5d8a', '#5b8db8', '#9dbcd8', '#c2410c', '#6b7280'], strong: '#17304f', accent: '#c2410c', zones: ['#17304f', '#2f5d8a', '#5b8db8'] },
  { key: 'gray', name: t('회색 + 강조'), words: ['회색+강조', '회색강조', '회색', 'gray', 'grey', 'grayaccent', 'gray+accent'], tip: t('첫 계열(핵심)만 색, 나머지는 회색 — "이것만 보세요"'),   // i18n-ok (찾는 말)
    series: ['#c2410c', '#6b7280', '#9ca3af', '#c4c9d0', '#4b5563', '#d1d5db'], strong: '#4b5563', accent: '#c2410c', zones: ['#6b7280', '#9ca3af', '#4b5563'] },
  { key: 'vivid', name: t('선명한 구분'), words: ['선명한구분', '선명한', 'vivid', 'distinct'], tip: t('계열이 많은 차트 — 서로 잘 갈리는 색'),   // i18n-ok (찾는 말)
    series: ['#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f', '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac'], strong: '#4e79a7', accent: '#e15759' },
  { key: 'safe', name: t('색약 친화'), words: ['색약친화', '색약', 'safe', 'colorblind', 'colorblindsafe', 'okabeito'], tip: t('Okabe-Ito — 색각 이상이 있어도 구분된다'),   // i18n-ok (찾는 말)
    series: ['#0072b2', '#e69f00', '#009e73', '#d55e00', '#cc79a7', '#56b4e9', '#f0e442', '#999999'], strong: '#0072b2', accent: '#d55e00' },
  { key: 'warm', name: t('따뜻한'), words: ['따뜻한', 'warm'], tip: t('주황·적갈 계열 — 비용·위험·수요'),   // i18n-ok (찾는 말)
    series: ['#7c2d12', '#c2410c', '#ea580c', '#f59e0b', '#b45309', '#fdba74'], strong: '#7c2d12', accent: '#ea580c', zones: ['#c2410c', '#b45309', '#7c2d12'] },
  { key: 'cool', name: t('차가운'), words: ['차가운', 'cool'], tip: t('남·청록·보라 계열 — 기술·공급·인프라'),   // i18n-ok (찾는 말)
    series: ['#1e3a8a', '#1d4ed8', '#0e7490', '#4f46e5', '#0891b2', '#93c5fd'], strong: '#1e3a8a', accent: '#0891b2', zones: ['#1d4ed8', '#0e7490', '#4f46e5'] },
  { key: 'pastel', name: t('파스텔'), words: ['파스텔', 'pastel'], tip: t('옅은 색 — 발표 화면, 상자가 큰 그림'),   // i18n-ok (찾는 말)
    series: ['#8fb8de', '#f5b994', '#a8d5a2', '#e4a5c4', '#c3b1e1', '#f3d98b'], strong: '#5b7fa6', accent: '#e07a3f', zones: ['#8fb8de', '#a8d5a2', '#f5b994'] },
];

/** 색 조합 목록 — 설정 창·우클릭 메뉴가 쓴다 [{n, key, name, tip, chips}] (chips: 지금 스타일에서 보이는 계열 색) */
export const diagramColors = () => {
  const dark = !!mermaidTheme().themeVariables.darkMode;
  return PALETTES.map((x, i) => ({ n: i + 1, key: x.key, name: x.name, tip: x.tip, chips: (x.series || ZONES.light).slice(0, 6).map((c) => (dark ? onDark(c) : c)) }));
};

/** 설정의 기본 색 조합 (1부터) */
export function defaultColors() {
  const n = Number(S.config.diagram_colors);
  return Number.isInteger(n) && n >= 1 && n <= PALETTES.length ? n : 1;
}

/** 문서 스타일의 색표(Mermaid themeVariables) → 도해 스타일이 쓰는 이름. c: 색 조합 (1 이면 문서 스타일 그대로) */
function paletteOf(v, c = 1) {
  const dark = !!v.darkMode;
  const pick = (x, fallback) => (rgbOf(x) ? hexOf(rgbOf(x)) : fallback);
  const bg = pick(v.background, dark ? '#1f242b' : '#ffffff');
  const p = {
    dark, bg,
    fill: pick(v.primaryColor, dark ? '#2a313a' : '#e8eff7'), border: pick(v.primaryBorderColor, dark ? '#6ea8e6' : '#2b5c8a'),
    title: pick(v.primaryTextColor, dark ? '#eef2f5' : '#1b3a5c'), soft: pick(v.secondaryColor, dark ? '#333b45' : '#f1f4f8'),
    line: pick(v.lineColor, dark ? '#9aa5b1' : '#5f6b78'), text: pick(v.textColor, dark ? '#d5dbe1' : '#1f2933'),
    accent: dark ? '#f0883e' : '#c2410c', warn: dark ? '#e3b341' : '#b45309', danger: dark ? '#f47067' : '#b42318',
    zones: dark ? ZONES.dark : ZONES.light, series: /** @type {string[] | null} */ (null),
  };
  const set = PALETTES[c - 1];
  if (!set?.series) return p;
  const adapt = (x) => (dark ? onDark(x) : x);
  const strong = adapt(set.strong);
  return {
    ...p, border: strong, fill: mix(strong, bg, dark ? 0.26 : 0.12), title: dark ? mix(strong, '#ffffff', 0.45) : strong, soft: mix(strong, bg, dark ? 0.14 : 0.06),
    accent: adapt(set.accent), zones: (set.zones || set.series).map(adapt), series: set.series.map(adapt),
  };
}
/** 지금 문서 스타일의 색표 (c: 색 조합) */
export const palette = (c = 1) => paletteOf(mermaidTheme().themeVariables, c);

/** 차트의 계열 색 — 색 조합 1 이면 null (라이브러리의 기본색). ramp: 연속 값(열지도)의 두 끝 */
export function chartPalette(c) {
  const p = palette(c);
  return p.series ? { series: p.series, ramp: [mix(p.border, p.bg, 0.12), p.border] } : null;
}

// ---- 스타일 표 ---------------------------------------------------------------------

const ROLES = ['key', 'warn', 'muted'];
/** @typedef {{fill: string, stroke: string, color?: string, width?: number, dash?: boolean, bold?: boolean}} Role */
/** 강조 표시의 기본 칠 — 핵심은 진하게 채우고, 주의는 주황, 보조는 흐린 점선 */
const baseRoles = (p) => ({
  key: { fill: p.border, stroke: p.border, color: ink(p.border, p), bold: true },
  warn: { fill: mix(p.warn, p.bg, 0.14), stroke: p.warn, color: deep(p.warn, p) },
  muted: { fill: p.bg, stroke: mix(p.line, p.bg, 0.6), color: p.line, dash: true },
});
/** 제목 상자의 강조 표시 — 상자는 바탕색, 띠(또는 테두리)의 색이 바뀐다. 글자색은 띠가 정한다 (classDef 의 color 는 Mermaid 가 !important 로 넣는다) */
const titleRoles = (p) => ({
  key: { fill: p.bg, stroke: p.accent, width: 1.8 },
  warn: { fill: p.bg, stroke: p.warn, width: 1.8 },
  muted: { fill: p.bg, stroke: mix(p.line, p.bg, 0.6), dash: true },
});
// 제목 상자의 글자: 제목은 첫 줄(::first-line — Mermaid 가 크기를 잴 때도 듣는다), 내용은 조금 작게 왼쪽 맞춤
const TITLE_CSS = '.node .nodeLabel p { font-size: 13.5px; line-height: 1.6; text-align: left; word-break: keep-all; padding-bottom: 6px; }'
  + ' .node .nodeLabel p::first-line { font-size: 15px; font-weight: 700; line-height: 2.3; }'
  + ' .node .nodeLabel .lec-dt { color: var(--lec-dt, inherit); } .node .nodeLabel p { color: var(--lec-dd, inherit); }';
const TITLE_WRAP = 220;   // 내용 글이 꺾이는 폭 (px — Mermaid 의 wrappingWidth)

/**
 * 도해 스타일 하나: mermaid(p) — initialize 에 더할 것 {look, vars(themeVariables), flowchart, css(themeCSS)},
 * dot(p) — renderString 의 기본 속성 {graph, node, edge} 과 묶음(cluster)의 칠 {cluster: {fill, stroke, dash}}·그림자 {shadow} (문자열이면 그 스타일의 것),
 * roles(p) — 강조 표시의 칠, title — 제목 상자의 방식(band·tint·rule), zones — 묶음마다 색을 돌려 쓰기
 */
const STYLES = [
  { key: 'basic', name: t('기본'), words: ['기본', 'basic', 'default'], tip: t('0.111 까지와 같은 모양 — 문서 스타일의 색'),   // i18n-ok (찾는 말)
    mermaid: () => ({}), dot: () => ({}), roles: baseRoles },
  { key: 'report', name: t('보고서 선'), words: ['보고서선', '보고서', 'report', 'reportline', 'reportlines'], tip: t('흰 상자·진한 테두리·직각으로 꺾는 선 — 흑백 인쇄에 강하다'),   // i18n-ok (찾는 말)
    mermaid: (p) => ({ look: 'classic', vars: { primaryColor: p.bg, clusterBkg: p.bg, clusterBorder: p.line }, flowchart: { curve: 'stepAfter', nodeSpacing: 40, rankSpacing: 42 },
      css: '.node rect, .node polygon, .node path { stroke-width: 1.6px; } .flowchart-link { stroke-width: 1.3px; } .cluster rect { stroke-dasharray: 5 3; }' }),
    dot: (p) => ({ graph: { splines: 'ortho', nodesep: 0.45, ranksep: 0.45 }, node: { shape: 'box', style: 'filled', fillcolor: p.bg, color: p.border, penwidth: 1.6, fontcolor: p.title },
      edge: { color: p.line, penwidth: 1.3, arrowsize: 0.8 }, cluster: { stroke: p.line, dash: true } }),
    roles: (p) => ({ ...baseRoles(p), warn: { fill: p.bg, stroke: p.border, color: p.title, width: 2.6, bold: true } }) },
  { key: 'card', name: t('카드'), words: ['카드', 'card'], tip: t('둥근 모서리·옅은 그림자·넉넉한 여백 — 화면·발표용'),   // i18n-ok (찾는 말)
    mermaid: (p) => ({ look: 'classic', vars: { primaryColor: p.bg, primaryBorderColor: mix(p.border, p.bg, 0.25), clusterBkg: p.soft, clusterBorder: p.soft },
      flowchart: { curve: 'basis', nodeSpacing: 44, rankSpacing: 46, padding: 16 },
      css: `.node rect { rx: 10px; ry: 10px; } .node rect, .node polygon, .node path { filter: drop-shadow(0 2px 3px ${shadow(p)}); } .cluster rect { rx: 14px; ry: 14px; } .flowchart-link { stroke-width: 1.6px; } .nodeLabel { font-weight: 600; }` }),
    dot: (p) => ({ graph: { nodesep: 0.5, ranksep: 0.5 }, node: { shape: 'box', style: 'rounded,filled', fillcolor: p.bg, color: mix(p.border, p.bg, 0.25), penwidth: 1.2, fontcolor: p.title, margin: '0.2,0.1' },
      edge: { color: p.line, penwidth: 1.5, arrowsize: 0.8 }, cluster: { fill: p.soft, stroke: p.soft }, shadow: true }),
    roles: (p) => ({ ...baseRoles(p), muted: { fill: p.soft, stroke: mix(p.line, p.bg, 0.25), color: p.line } }) },
  { key: 'solid', name: t('진한 채움'), words: ['진한채움', 'solid', 'filled'], tip: t('상자를 진하게 채우고 밝은 글자 — 단계가 적은 큰 그림에'),   // i18n-ok (찾는 말)
    mermaid: (p) => ({ look: 'classic', vars: { primaryColor: p.border, primaryTextColor: ink(p.border, p), primaryBorderColor: p.border, titleColor: p.title, clusterBkg: mix(p.border, p.bg, 0.08),
      clusterBorder: mix(p.border, p.bg, 0.08), edgeLabelBackground: p.bg }, flowchart: { curve: 'linear', nodeSpacing: 38, rankSpacing: 46 },
      css: `.node rect { rx: 4px; ry: 4px; } .node .nodeLabel { font-weight: 600; } .flowchart-link { stroke-width: 2px; } .edgeLabel, .edgeLabel p { color: ${p.text}; }` }),
    dot: (p) => ({ graph: { nodesep: 0.4, ranksep: 0.5 }, node: { shape: 'box', style: 'rounded,filled', fillcolor: p.border, color: p.border, fontcolor: ink(p.border, p) },
      edge: { color: p.line, penwidth: 2, arrowsize: 0.8 }, cluster: { fill: mix(p.border, p.bg, 0.08), stroke: mix(p.border, p.bg, 0.08) } }),
    roles: (p) => {
      const gray = mix(p.line, p.bg, 0.3);
      return { key: { fill: p.accent, stroke: p.accent, color: ink(p.accent, p), bold: true }, warn: { fill: p.danger, stroke: p.danger, color: ink(p.danger, p) },
        muted: { fill: gray, stroke: gray, color: ink(gray, p) } };
    } },
  { key: 'line', name: t('선만'), words: ['선만', 'line', 'outline', 'lineonly'], tip: t('채움 없이 가는 선, 글자만 또렷 — 논문·책'),   // i18n-ok (찾는 말)
    mermaid: (p) => ({ look: 'classic', vars: { primaryColor: p.bg, primaryBorderColor: p.text, primaryTextColor: p.text, lineColor: p.text, secondaryColor: p.bg, tertiaryColor: p.bg,
      clusterBkg: p.bg, clusterBorder: mix(p.text, p.bg, 0.45) }, flowchart: { curve: 'linear' },
      css: '.node rect, .node polygon, .node path { stroke-width: 1px; } .flowchart-link { stroke-width: 1px; }' }),
    dot: (p) => ({ node: { shape: 'box', color: p.text, penwidth: 1, fontcolor: p.text }, edge: { color: p.text, penwidth: 1, arrowsize: 0.7, fontcolor: p.text },
      cluster: { stroke: mix(p.text, p.bg, 0.45) } }),
    roles: (p) => ({ key: { fill: p.bg, stroke: p.text, color: p.text, width: 2.4, bold: true }, warn: { fill: p.bg, stroke: p.text, color: p.text, dash: true },
      muted: { fill: p.bg, stroke: mix(p.text, p.bg, 0.35), color: mix(p.text, p.bg, 0.6) } }) },
  { key: 'sketch', name: t('손그림'), words: ['손그림', 'sketch', 'handdrawn'], tip: t('손으로 그린 듯한 선 — 초안·구상임을 드러낼 때 (Graphviz 는 기본 모양)'),   // i18n-ok (찾는 말)
    mermaid: (p) => ({ look: 'handDrawn', vars: { primaryColor: mix('#e8b931', p.bg, 0.16) } }), dot: 'basic',
    roles: (p) => ({ key: { fill: mix(p.accent, p.bg, 0.3), stroke: p.accent, color: p.text, bold: true }, warn: { fill: mix(p.danger, p.bg, 0.14), stroke: p.danger, color: deep(p.danger, p) },
      muted: baseRoles(p).muted }) },
  { key: 'zones', name: t('단계 색'), words: ['단계색', 'zones', 'zone', 'stage'], tip: t('묶음(subgraph·cluster)마다 옅은 색을 돌려 쓴다 — 영역이 여럿인 구성도'),   // i18n-ok (찾는 말)
    mermaid: (p) => ({ look: 'classic', vars: { primaryColor: mix(p.border, p.bg, 0.1), primaryBorderColor: mix(p.border, p.bg, 0.7), clusterBkg: mix(p.border, p.bg, 0.05),
      clusterBorder: mix(p.border, p.bg, 0.3) }, flowchart: { curve: 'basis', nodeSpacing: 42 }, css: '.node rect { rx: 6px; ry: 6px; } .cluster rect { rx: 10px; ry: 10px; }' }),
    dot: (p) => ({ node: { shape: 'box', style: 'rounded,filled', fillcolor: mix(p.border, p.bg, 0.1), color: mix(p.border, p.bg, 0.7), fontcolor: p.title }, edge: { color: p.line } }),
    zones: true, roles: (p) => ({ ...baseRoles(p), key: { fill: p.accent, stroke: p.accent, color: ink(p.accent, p), bold: true } }) },
  { key: 'band', name: t('제목 띠'), words: ['제목띠', 'band', 'titleband'], tip: t('상자 위에 진한 제목 띠, 아래에 내용 — 줄을 바꾼 상자의 첫 줄이 제목'),   // i18n-ok (찾는 말)
    mermaid: (p) => ({ look: 'classic', vars: { primaryColor: p.bg, primaryBorderColor: p.border, primaryTextColor: p.text, clusterBkg: p.soft, clusterBorder: p.soft },
      flowchart: { curve: 'basis', nodeSpacing: 40, rankSpacing: 44, wrappingWidth: TITLE_WRAP, padding: 7 }, css: `${TITLE_CSS} .node rect { rx: 5px; ry: 5px; } .node rect, .node polygon { stroke-width: 1.4px; }` }),
    dot: (p) => ({ node: { shape: 'box', style: 'filled', fillcolor: p.bg, color: p.border, penwidth: 1.4, fontcolor: p.text, margin: '0.2,0.15' }, edge: { color: p.line },
      cluster: { fill: p.soft, stroke: p.soft } }),
    title: 'band', roles: titleRoles },
  { key: 'tint', name: t('옅은 제목 띠'), words: ['옅은제목띠', '옅은띠', 'tint', 'lightband', 'lighttitleband'], tip: t('옅은 제목 띠에 진한 제목 글자, 아래에 내용'),   // i18n-ok (찾는 말)
    mermaid: (p) => ({ look: 'classic', vars: { primaryColor: p.bg, primaryBorderColor: mix(p.border, p.bg, 0.45), primaryTextColor: p.text, clusterBkg: p.bg, clusterBorder: mix(p.line, p.bg, 0.45) },
      flowchart: { curve: 'basis', nodeSpacing: 40, rankSpacing: 44, wrappingWidth: TITLE_WRAP, padding: 7 }, css: `${TITLE_CSS} .node rect { rx: 5px; ry: 5px; } .cluster rect { stroke-dasharray: 5 3; }` }),
    dot: (p) => ({ node: { shape: 'box', style: 'filled', fillcolor: p.bg, color: mix(p.border, p.bg, 0.45), fontcolor: p.text, margin: '0.2,0.15' }, edge: { color: p.line },
      cluster: { stroke: mix(p.line, p.bg, 0.45), dash: true } }),
    title: 'tint', roles: titleRoles },
  { key: 'rule', name: t('제목 줄'), words: ['제목줄', 'rule', 'titlerule'], tip: t('굵은 제목 아래에 가는 줄, 그 아래 흐린 내용 — 칸을 나눈 표처럼'),   // i18n-ok (찾는 말)
    mermaid: (p) => ({ look: 'classic', vars: { primaryColor: p.bg, primaryBorderColor: mix(p.border, p.bg, 0.55), primaryTextColor: p.title, clusterBkg: p.bg, clusterBorder: mix(p.line, p.bg, 0.45) },
      flowchart: { curve: 'linear', nodeSpacing: 40, rankSpacing: 44, wrappingWidth: TITLE_WRAP, padding: 7 }, css: `${TITLE_CSS} .node rect { rx: 3px; ry: 3px; }` }),
    dot: (p) => ({ node: { shape: 'box', style: 'filled', fillcolor: p.bg, color: mix(p.border, p.bg, 0.55), fontcolor: p.title, margin: '0.2,0.15' }, edge: { color: p.line },
      cluster: { stroke: mix(p.line, p.bg, 0.45) } }),
    title: 'rule', roles: titleRoles },
];

/** 도해 스타일 목록 — 설정 창·우클릭 메뉴가 쓴다 [{n, key, name, tip}] */
export const diagramStyles = () => STYLES.map((s, i) => ({ n: i + 1, key: s.key, name: s.name, tip: s.tip }));

/** 설정의 기본 번호 (1부터) */
export function defaultStyle() {
  const n = Number(S.config.diagram_style);
  return Number.isInteger(n) && n >= 1 && n <= STYLES.length ? n : 1;
}

// ---- 그림이 고른 번호 -------------------------------------------------------------

// 그림·차트 블록 안의 표시 줄 — Mermaid '%% …', Graphviz '// …'('#' 도), 차트(JSON) '// …'. 한 줄에 '스타일: 8 · 색: 2' 처럼 둘 다 적어도 된다
const LEAD = { mermaid: /^(\s*)%%(?!\{)[ \t]*(.*)$/, dot: /^(\s*)(?:\/\/|#)[ \t]*(.*)$/, chart: /^(\s*)\/\/[ \t]*(.*)$/ };
const TOKEN = /^(스타일|style|색\s*조합|색|colou?rs?|palette)(?:\s*[:：=]\s*|\s+)(.+?)\s*$/i;   // i18n-ok — '색인' 처럼 붙은 글은 표시가 아니다
const keyOf = (word) => (/^(스타일|style)$/i.test(word) ? 'style' : 'colors');   // i18n-ok

/** 표시 줄이면 {indent, parts:[{key, word, value, raw}]} (key 가 없는 조각은 그 줄의 다른 글), 아니면 null */
function markLine(line, kind) {
  const m = (LEAD[kind] || LEAD.mermaid).exec(line);
  if (!m) return null;
  const parts = m[2].split(/\s*[·,;]\s*/).filter(Boolean).map((raw) => {
    const x = TOKEN.exec(raw);
    return x ? { key: keyOf(x[1]), word: x[1], value: x[2], raw } : { key: '', word: '', value: '', raw };
  });
  return parts.some((x) => x.key) ? { indent: m[1], parts } : null;
}

/** 블록 안의 표시 — {style, colors} (값 글자, 없으면 ''). 처음 나온 것 */
function marksIn(src, kind) {
  const out = { style: '', colors: '' };
  for (const line of String(src).split('\n')) {
    const m = markLine(line, kind);
    for (const x of m ? m.parts : []) if (x.key && !out[x.key]) out[x.key] = x.value;
  }
  return out;
}

/** 값 → 번호 (모르면 0). 번호·'3 카드'·이름('카드'·'card')·key */
function numberIn(list, value) {
  const v = String(value ?? '').trim();
  const num = /^(\d+)/.exec(v);
  if (num) {
    const n = Number(num[1]);
    return n >= 1 && n <= list.length ? n : 0;
  }
  const word = v.toLowerCase().replace(/[\s_-]+/g, '');
  return list.findIndex((s) => s.words.includes(word) || s.key === word || s.name.toLowerCase().replace(/\s+/g, '') === word) + 1;
}
/** 스타일 줄의 값 → 번호 (모르면 0) */
export const styleNumber = (value) => numberIn(STYLES, value);
/** 색 줄의 값 → 번호 (모르면 0) */
export const colorsNumber = (value) => numberIn(PALETTES, value);

/** 문서의 기본 줄 '<!-- 도해: 스타일 8 · 색 2 -->' → {style, colors} (번호, 없으면 0). 처음 나온 줄 */
export function docMarks(text) {
  const out = { style: 0, colors: 0 };
  let fence = '';   // 코드 블록 안의 예시 줄은 건너뛴다 (작성 안내처럼 그 줄을 보여 주는 문서)
  let m = null;
  for (const line of String(text || '').split('\n')) {
    const f = /^\s*(\x60{3,}|~{3,})/.exec(line);   // \x60 은 백틱 (글자로 적으면 시험의 원문 읽개가 템플릿으로 본다)
    if (f && (!fence || f[1][0] === fence[0])) {
      fence = fence ? '' : f[1];
      continue;
    }
    if (fence) continue;
    m = /^[ \t]*<!--[ \t]*(?:도해|diagrams?)[ \t]*[:：][ \t]*(.*?)[ \t]*-->[ \t]*$/i.exec(line);   // i18n-ok
    if (m) break;
  }
  if (!m) return out;
  for (const raw of m[1].split(/\s*[·,;]\s*/)) {
    const x = TOKEN.exec(raw);
    if (x) out[keyOf(x[1])] ||= keyOf(x[1]) === 'style' ? styleNumber(x[2]) : colorsNumber(x[2]);
  }
  return out;
}

/** 그 그림의 모양 번호 — 블록의 줄 > 문서의 줄(marks) > 설정. kind: 'mermaid' | 'dot' */
export function styleOf(src, kind, marks = null) {
  return styleNumber(marksIn(src, kind).style) || marks?.style || defaultStyle();
}

/** 그 그림·차트의 색 조합 — 블록의 줄 > 문서의 줄 > 설정. kind: 'mermaid' | 'dot' | 'chart' */
export function colorsOf(src, kind, marks = null) {
  return colorsNumber(marksIn(src, kind).colors) || marks?.colors || defaultColors();
}

/** 블록 안의 표시 — 메뉴가 지금 것을 보인다 {style, colors} (블록에 적힌 번호, 없으면 0) */
export function blockMarks(src, kind) {
  const m = marksIn(src, kind);
  return { style: styleNumber(m.style), colors: colorsNumber(m.colors) };
}

/**
 * 블록 안(body — 여는 줄·닫는 줄 뺀 줄들)의 표시를 고친 새 줄들. key: 'style' | 'colors', n: 번호 (null 이면 지운다).
 * 있는 표시 줄을 고친다 (다른 표시는 그대로, 아무것도 안 남으면 줄을 지운다). 없으면 — 차트는 맨 앞에, 그림은 첫 줄(flowchart LR·digraph 이름 {)
 * 아래에 다음 줄의 들여쓰기로 (Mermaid 의 머리 설정 '---' 은 맨 앞이어야 하므로 그 다음의 첫 줄 아래에)
 */
export function setMark(body, kind, key, n) {
  const lines = [...body];
  const lead = kind === 'mermaid' ? '%%' : '/'.repeat(2);
  const fallback = key === 'style' ? t('스타일') : t('색');
  const fmt = (x) => (x.key ? `${x.word}: ${x.value}` : x.raw);
  let at = -1;
  let first = -1;
  lines.forEach((l, i) => {
    const m = markLine(l, kind);
    if (!m) return;
    if (first < 0) first = i;
    if (at < 0 && m.parts.some((x) => x.key === key)) at = i;
  });
  if (at >= 0 || (first >= 0 && n != null)) {
    const i = at >= 0 ? at : first;
    const m = markLine(lines[i], kind);
    let parts = m.parts;
    if (at >= 0) parts = n == null ? parts.filter((x) => x.key !== key) : parts.map((x) => (x.key === key ? { ...x, value: String(n) } : x));
    else parts = [...parts, { key, word: fallback, value: String(n), raw: '' }];
    if (parts.length) lines[i] = `${m.indent}${lead} ${parts.map(fmt).join(' · ')}`;
    else lines.splice(i, 1);
    return lines;
  }
  if (n == null) return lines;
  const text = `${lead} ${fallback}: ${n}`;
  if (kind === 'chart') return [text, ...lines];
  let skip = 0;
  if (kind === 'mermaid' && lines[0]?.trim() === '---') skip = lines.findIndex((l, i) => i > 0 && l.trim() === '---') + 1;
  let head = skip;
  while (head < lines.length && !lines[head].trim()) head += 1;
  const pos = head < lines.length ? head + 1 : skip;
  const next = lines[pos];
  const pad = next != null && next.trim() ? /^\s*/.exec(next)[0] : '';
  lines.splice(pos, 0, pad + text);
  return lines;
}

// ---- 방향 (가로·세로) -----------------------------------------------------------

const MERMAID_HEAD = /^(\s*)(flowchart|graph)\b[ \t]*(LR|RL|TD|TB|BT)?(.*)$/i;
const RANKDIR = /\brankdir\s*=\s*"?(LR|RL|TB|BT)"?/i;

/** 그림의 방향 — {line(body 의 차례), dir: 'LR' | 'TD'} 또는 null (흐름도·Graphviz 가 아니면). Graphviz 에 rankdir 이 없으면 위아래(TD) */
export function directionOf(body, kind) {
  if (kind === 'mermaid') {
    let i = 0;
    if (body[0]?.trim() === '---') i = body.findIndex((l, j) => j > 0 && l.trim() === '---') + 1;
    for (; i < body.length; i++) {
      const l = body[i];
      if (!l.trim() || /^\s*%%/.test(l)) continue;
      const m = MERMAID_HEAD.exec(l);
      return m ? { line: i, dir: /^(LR|RL)$/i.test(m[3] || '') ? 'LR' : 'TD' } : null;
    }
    return null;
  }
  if (kind !== 'dot' || !body.some((l) => /\b(di)?graph\b/i.test(l))) return null;
  const i = body.findIndex((l) => RANKDIR.test(l));
  return i >= 0 ? { line: i, dir: /^(LR|RL)$/i.test(RANKDIR.exec(body[i])[1]) ? 'LR' : 'TD' } : { line: -1, dir: 'TD' };
}

/** 가로 ↔ 세로를 바꾼 새 줄들 (못 바꾸면 null). Mermaid 는 첫 줄의 방향 글자, Graphviz 는 rankdir (없으면 그래프 첫 줄 아래에 rankdir=LR) */
export function flipDirection(body, kind) {
  const d = directionOf(body, kind);
  if (!d) return null;
  const lines = [...body];
  const to = d.dir === 'LR' ? 'TD' : 'LR';
  if (kind === 'mermaid') {
    const m = MERMAID_HEAD.exec(lines[d.line]);
    lines[d.line] = `${m[1]}${m[2]} ${to}${m[4]}`;
    return lines;
  }
  if (d.line >= 0) {
    lines[d.line] = lines[d.line].replace(RANKDIR, `rankdir=${to === 'LR' ? 'LR' : 'TB'}`);
    return lines;
  }
  const open = lines.findIndex((l) => l.includes('{'));
  if (open < 0) return null;
  const next = lines[open + 1];
  const pad = next != null && next.trim() ? /^\s*/.exec(next)[0] : '  ';
  lines.splice(open + 1, 0, `${pad}rankdir=LR`);
  return lines;
}

const styleAt = (n) => STYLES[n - 1] || STYLES[0];

// ---- Mermaid ---------------------------------------------------------------------

/** mermaid.initialize 에 넘길 설정 — 문서 스타일의 색(mermaidTheme) 위에 그 색 조합(c)과 그 번호(n)의 모양 */
export function mermaidConfig(n, c = 1) {
  const base = mermaidTheme();
  const st = styleAt(n);
  const p = palette(c);
  const m = st.mermaid(p);
  /** @type {Record<string, any>} */
  const set = p.series ? {
    primaryColor: p.fill, primaryBorderColor: p.border, primaryTextColor: p.title, secondaryColor: p.soft,
    ...Object.fromEntries(Array.from({ length: 12 }, (_, i) => [`pie${i + 1}`, p.series[i % p.series.length]])),   // 원그래프
    xyChart: { plotColorPalette: p.series.join(', ') },   // xychart-beta
  } : {};
  /** @type {Record<string, any>} */
  const out = { ...base, themeVariables: { ...base.themeVariables, ...set, ...(m.vars || {}) } };
  if (m.look) out.look = m.look;
  if (m.look === 'handDrawn') out.handDrawnSeed = 7;   // 다시 그려도 같은 선 (0 이면 그릴 때마다 흔들린다)
  if (m.flowchart) out.flowchart = m.flowchart;
  if (m.css) out.themeCSS = m.css;
  return out;
}

const roleCss = (r) => [`fill:${r.fill}`, `stroke:${r.stroke}`, r.color ? `color:${r.color}` : '', r.width ? `stroke-width:${r.width}px` : '', r.dash ? 'stroke-dasharray:4 3' : '',
  r.bold ? 'font-weight:bold' : ''].filter(Boolean).join(',');

/**
 * 그릴 원문 — 흐름도가 강조 표시(key·warn·muted)를 쓰면 그 번호의 classDef 를 끝에 붙인다 (문서가 같은 이름을 정했으면 그것을 둔다).
 * 원문 파일은 바꾸지 않는다 — 그릴 때만
 */
export function mermaidSource(src, n, c = 1) {
  const body = String(src);
  const head = body.split('\n').find((l) => l.trim() && !/^\s*(%%|---)/.test(l) && !/^\s*\w+\s*:/.test(l)) || '';
  if (!/^\s*(flowchart|graph)\b/i.test(head)) return body;
  const used = ROLES.filter((r) => new RegExp(`:::${r}\\b|^\\s*class\\s+.+\\s${r}\\s*;?\\s*$`, 'm').test(body) && !new RegExp(`^\\s*classDef\\s+${r}\\b`, 'm').test(body));
  if (!used.length) return body;
  const roles = styleAt(n).roles(palette(c));
  return `${body.replace(/\s*$/, '')}\n${used.map((r) => `  classDef ${r} ${roleCss(roles[r])}`).join('\n')}\n`;
}

/** 그린 Mermaid 그림을 다듬는다 — 단계 색(묶음마다 색), 제목 상자(띠·줄). 그림이 화면(무대)에 붙어 있어야 잰다 */
export function decorateMermaid(svg, n, c = 1) {
  const st = styleAt(n);
  if (!st.zones && !st.title) return;
  const p = palette(c);
  if (st.zones) zones(svg, p, (g) => [...g.querySelectorAll(':scope > rect.label-container, :scope > polygon.label-container, :scope > rect.basic, :scope > path.label-container')],
    (g) => g.querySelector(':scope > rect'));
  if (st.title) {
    const roles = st.roles(p);
    for (const g of svg.querySelectorAll('g.node')) {
      const shape = g.querySelector(':scope > rect.label-container, :scope > rect.basic');
      const para = g.querySelector('.nodeLabel p') || g.querySelector('.nodeLabel');
      if (shape && para) titleMermaid(g, shape, para, st.title, roleColor(g, roles, p), p);
    }
  }
}

/** 강조 표시가 붙은 상자의 띠 색 (없으면 null — 스타일의 기본) */
function roleColor(g, roles, p) {
  const r = ROLES.find((x) => g.classList.contains(x));
  if (!r) return null;
  return r === 'muted' ? mix(p.line, p.bg, 0.55) : roles[r].stroke;
}

/** 띠의 색과 그 위 글자색 — band(진하게)·tint(옅게) */
function bandColors(kind, role, p) {
  if (kind === 'band') {
    const c = role || p.border;
    return { band: c, ink: ink(c, p) };
  }
  const c = role || p.border;
  return { band: mix(c, p.bg, p.dark ? 0.22 : 0.13), ink: p.dark ? mix(c, '#ffffff', 0.5) : mix(c, '#000000', 0.8) };
}

/** 띠의 칠 — 그림의 CSS(Mermaid 의 '.node path', 강조 표시)보다 먼저 */
function paintBand(band, color) {
  band.style.setProperty('fill', color, 'important');
  band.style.setProperty('stroke', 'none', 'important');
  band.style.setProperty('filter', 'none', 'important');
}

/** 위쪽 두 모서리만 둥근 띠 (x, y 에서 폭 w, 높이 h) */
function bandPath(x, y, w, h, r) {
  const k = Math.max(0, Math.min(r, h, w / 2));
  return `M${x},${y + h} V${y + k} Q${x},${y} ${x + k},${y} H${x + w - k} Q${x + w},${y} ${x + w},${y + k} V${y + h} Z`;
}

const SVGNS = 'http://www.w3.org/2000/svg';

function titleMermaid(g, shape, para, kind, role, p) {
  const br = para.querySelector('br');
  // 제목 글자를 묶는다 — 색만 바꾸므로 배치(Mermaid 가 잰 크기)는 그대로
  const range = document.createRange();
  range.setStart(para, 0);
  if (br) range.setEndBefore(br);
  else range.setEnd(para, para.childNodes.length);
  const dt = document.createElement('span');
  dt.className = 'lec-dt';
  dt.append(range.extractContents());
  para.prepend(dt);
  const box = { x: +shape.getAttribute('x'), y: +shape.getAttribute('y'), w: +shape.getAttribute('width'), h: +shape.getAttribute('height') };
  const css = getComputedStyle(shape);
  const radius = parseFloat(css.rx) || parseFloat(shape.getAttribute('rx')) || 0;
  const sw = parseFloat(css.strokeWidth) || 1;
  if (kind === 'rule') {
    g.style.setProperty('--lec-dt', role || p.title);
    if (br) g.style.setProperty('--lec-dd', p.line);
  } else {
    const c = bandColors(kind, role, p);
    g.style.setProperty('--lec-dt', c.ink);
    if (!br) {   // 제목만 — 상자 전체가 띠
      shape.style.setProperty('fill', c.band, 'important');
      return;
    }
    shape.dataset.band = c.band;
  }
  if (!br) return;
  // 제목과 내용의 경계 — 화면에서 잰 것을 상자의 좌표로 (상자의 화면 높이와 속성 높이의 비)
  const R = shape.getBoundingClientRect();
  if (!R.height || !box.h) return;
  const k = box.h / R.height;
  const titleBottom = Math.max(...[...dt.getClientRects()].map((r) => r.bottom));
  const rest = document.createRange();
  rest.setStartAfter(br);
  rest.setEnd(para, para.childNodes.length);
  const restTop = Math.min(...[...rest.getClientRects()].filter((r) => r.height).map((r) => r.top));
  if (!Number.isFinite(titleBottom)) return;
  const titleTop = Math.min(...[...dt.getClientRects()].map((r) => r.top));
  const gap = Math.max(2, titleTop - R.top);   // 띠 위 끝에서 제목 글자까지
  const cut = box.y + (Math.min(titleBottom + gap, Number.isFinite(restTop) ? restTop - 2 : R.bottom) - R.top) * k;
  if (kind === 'rule') {
    const line = document.createElementNS(SVGNS, 'line');
    line.setAttribute('class', 'lec-title-rule');
    line.setAttribute('x1', String(box.x));
    line.setAttribute('x2', String(box.x + box.w));
    line.setAttribute('y1', String(cut));
    line.setAttribute('y2', String(cut));
    line.setAttribute('stroke', role || mix(p.border, p.bg, 0.55));
    line.setAttribute('stroke-width', '1');
    shape.after(line);
    return;
  }
  const band = document.createElementNS(SVGNS, 'path');
  band.setAttribute('class', 'lec-title-band');
  band.setAttribute('d', bandPath(box.x + sw / 2, box.y + sw / 2, box.w - sw, cut - box.y - sw / 2, Math.max(0, radius - sw / 2)));
  paintBand(band, shape.dataset.band || p.border);
  delete shape.dataset.band;
  shape.after(band);
}

// ---- Graphviz --------------------------------------------------------------------

/** Graphviz 의 기본 속성 {graph, node, edge} — 원문이 정한 것이 먼저다 (renderString 의 기본값으로 넘긴다) */
export function dotAttributes(n, c = 1) {
  const p = palette(c);
  const d = dotOf(styleAt(n))(p);
  const node = { ...(d.node || {}) };
  if (p.series && !node.color) Object.assign(node, { color: p.border, fontcolor: p.title });   // 1 기본 · 손그림 — 색 조합의 상자 색
  return { graph: d.graph || {}, node, edge: d.edge || {} };
}

let dotSeq = 0;

/** 그 스타일의 Graphviz 모양 — 문자열이면 그 이름의 스타일 것 (손그림 → 기본) */
function dotOf(st) {
  const own = typeof st.dot === 'string' ? STYLES.find((s) => s.key === st.dot) || STYLES[0] : st;
  return /** @type {(p: any) => any} */ (own.dot);
}
/** Graphviz 를 다듬을 때 쓰는 스타일 — 손그림은 기본의 것으로 (강조 표시·제목 상자도) */
const dotStyle = (st) => (typeof st.dot === 'string' ? STYLES.find((s) => s.key === st.dot) || STYLES[0] : st);

/** 그린 Graphviz 그림을 다듬는다 — 강조 표시(class), 묶음의 칠, 그림자, 단계 색, 제목 상자. paintGraph(스타일 색) 다음에 */
export function decorateDot(svg, n, c = 1) {
  const st = dotStyle(styleAt(n));
  const p = palette(c);
  const d = dotOf(st)(p);
  svg.id ||= `lec-dot-${++dotSeq}`;
  const sc = `#${svg.id}`;
  const roles = st.roles(p);
  const rules = ROLES.map((r) => {
    const x = roles[r];
    return `${sc} .node.${r} :is(polygon, path, ellipse) { fill: ${x.fill}; stroke: ${x.stroke}; stroke-width: ${x.width || 1.4}; ${x.dash ? 'stroke-dasharray: 4 3;' : ''} }`
      + (x.color ? ` ${sc} .node.${r} text { fill: ${x.color}; ${x.bold ? 'font-weight: 700;' : ''} }` : '');
  });
  if (d.shadow) rules.push(`${sc} .node :is(polygon, path, ellipse) { filter: drop-shadow(0 2px 3px ${shadow(p)}); }`);
  const style = document.createElementNS(SVGNS, 'style');
  style.textContent = rules.join('\n');
  svg.prepend(style);
  // 묶음(cluster): 원문이 색을 정하지 않은 것(기본 검정 → paintGraph 가 테두리 색으로 바꾼 것)만
  if (d.cluster) {
    for (const poly of svg.querySelectorAll('g.cluster > polygon')) {
      if (poly.getAttribute('fill') && poly.getAttribute('fill') !== 'none') continue;
      if (d.cluster.fill) poly.setAttribute('fill', d.cluster.fill);
      if (d.cluster.stroke) poly.setAttribute('stroke', d.cluster.stroke);
      if (d.cluster.dash) poly.setAttribute('stroke-dasharray', '5,3');
    }
  }
  if (st.zones) zones(svg, p, (g) => [...g.querySelectorAll(':scope > polygon, :scope > path, :scope > ellipse')], (g) => g.querySelector(':scope > polygon, :scope > path'));
  if (st.title) for (const g of svg.querySelectorAll('g.node')) titleDot(g, st.title, roleColor(g, roles, p), p);
}

/** Graphviz 상자의 제목·내용 — 글자 줄(text)이 둘 이상이면 첫 줄이 제목 */
function titleDot(g, kind, role, p) {
  const shape = g.querySelector(':scope > polygon');
  const texts = [...g.querySelectorAll(':scope > text')];
  if (!shape || !texts.length) return;
  const pts = (shape.getAttribute('points') || '').trim().split(/\s+/).map((s) => s.split(',').map(Number));
  if (pts.length !== 5 || pts.some((q) => q.length !== 2 || q.some((v) => !Number.isFinite(v)))) return;   // 네모 상자만 (마름모·타원은 그대로)
  const xs = pts.map((q) => q[0]);
  const ys = pts.map((q) => q[1]);
  const box = { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
  texts.sort((a, b) => +a.getAttribute('y') - +b.getAttribute('y'));
  const [head, ...rest] = texts;
  const size = (el) => parseFloat(el.getAttribute('font-size')) || 14;
  head.setAttribute('font-weight', '700');
  if (rest.length) {   // 여러 줄 글은 줄 간격이 좁다 — 제목과 내용 사이를 벌린다
    const d = size(head) * 0.22;
    head.setAttribute('y', String(+head.getAttribute('y') - d));
    for (const el of rest) el.setAttribute('y', String(+el.getAttribute('y') + d));
  }
  for (const el of rest) {
    el.setAttribute('font-size', String(Math.round(size(el) * 0.92 * 100) / 100));
    el.style.fill = kind === 'rule' ? p.line : p.text;   // 인라인 — 강조 표시의 CSS 보다 먼저
  }
  if (kind === 'rule') {
    head.style.fill = role || p.title;
    if (!rest.length) return;
    const cut = (+head.getAttribute('y') + size(head) * 0.3 + +rest[0].getAttribute('y') - size(rest[0]) * 0.8) / 2;
    const line = document.createElementNS(SVGNS, 'line');
    line.setAttribute('class', 'lec-title-rule');
    line.setAttribute('x1', String(box.x));
    line.setAttribute('x2', String(box.x + box.w));
    line.setAttribute('y1', String(cut));
    line.setAttribute('y2', String(cut));
    line.setAttribute('stroke', role || mix(p.border, p.bg, 0.55));
    shape.after(line);
    return;
  }
  const c = bandColors(kind, role, p);
  head.style.fill = c.ink;
  if (!rest.length) {
    shape.style.fill = c.band;   // 인라인 — 강조 표시의 CSS 보다 먼저
    return;
  }
  const cut = (+head.getAttribute('y') + size(head) * 0.3 + +rest[0].getAttribute('y') - size(rest[0]) * 0.8) / 2;
  const sw = parseFloat(shape.getAttribute('stroke-width')) || 1;
  const band = document.createElementNS(SVGNS, 'path');
  band.setAttribute('class', 'lec-title-band');
  band.setAttribute('d', bandPath(box.x + sw / 2, box.y + sw / 2, box.w - sw, cut - box.y - sw / 2, 0));
  paintBand(band, c.band);
  shape.after(band);
}

// ---- 단계 색 (두 엔진이 같이) -------------------------------------------------------

/**
 * 묶음마다 색을 돌려 쓴다 — 묶음의 칠·테두리, 그 안(화면에서 잰 자리)의 상자. 강조 표시가 붙은 상자는 그대로.
 * shapesOf(g.node) → 칠할 도형들, frameOf(g.cluster) → 묶음의 테두리 도형
 */
function zones(svg, p, shapesOf, frameOf) {
  const colors = p.zones;
  const clusters = [...svg.querySelectorAll('g.cluster')].map((g) => ({ g, frame: frameOf(g), color: '' })).filter((c) => c.frame);
  const boxes = clusters.map((c) => c.frame.getBoundingClientRect());
  const area = (r) => r.width * r.height;
  clusters.forEach((c, i) => {
    const col = colors[i % colors.length];
    c.color = col;
    c.frame.style.setProperty('fill', mix(col, p.bg, p.dark ? 0.12 : 0.07), 'important');
    c.frame.style.setProperty('stroke', mix(col, p.bg, 0.45), 'important');
  });
  for (const g of svg.querySelectorAll('g.node')) {
    if (ROLES.some((r) => g.classList.contains(r))) continue;
    const r = g.getBoundingClientRect();
    if (!r.width) continue;
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    // 가장 안쪽(작은) 묶음
    let best = -1;
    boxes.forEach((b, i) => {
      if (cx >= b.left && cx <= b.right && cy >= b.top && cy <= b.bottom && (best < 0 || area(b) < area(boxes[best]))) best = i;
    });
    if (best < 0) continue;
    const col = clusters[best].color;
    for (const s of shapesOf(g)) {
      s.style.setProperty('fill', mix(col, p.bg, p.dark ? 0.24 : 0.13), 'important');
      s.style.setProperty('stroke', col, 'important');
    }
  }
}
