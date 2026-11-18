// md 문서를 html 한 파일로 (D144): 내보내기 창의 'html 로 저장' — 화면이 그린 문서를 복제해 지금 화면 스타일 그대로 담는다.
//
// - 렌더러를 두 벌 두지 않는다 (D129): Mermaid·차트 SVG, canvas 는 그림, 수식(KaTeX 와 글꼴), 표·각주·박스글이 화면에서 그린 그대로다.
// - 걷어 내는 것은 종이에 나가지 않는 것과 같다 (base.css 의 @media print): 복사·차트 단추, 접기 화살표, 줄 번호, 현재 줄 표시,
//   맨 앞 설정 표. 접어 둔 절과 박스글은 펴서 담는다. 같은 파일 안의 #절 링크(목차·각주·상호 참조)는 그대로 둔다.
// - 스크립트는 하나도 없다 — 파일의 CSP 가 스크립트·연결·바깥 글꼴을 막는다. 인터넷 그림은 설정(external_images)이 켜져 있을 때만 주소로 남긴다.
// - 받은 사람이 브라우저에서 인쇄하면 'PDF로 저장'과 같은 보고서 양식이다 — print.css 와 쪽 머리 CSS(printdoc.pageCss)를 media="print" 로 넣는다.
// - 이 모듈은 짓기만 한다. 창(미리보기·저장)은 printdoc.js, 서버에 두고 쓰는 일은 lectern/pdfexport.py·native.save_export.

import { S } from './store.js';
import { getText } from './api.js';
import { basename } from './util.js';
import { esc } from './html.js';
import { t } from './i18n.js';
import { appCss, styleText, packClone } from './htmlpack.js';

/** 뗄 것: 앱의 단추·표시와 파일에서 쓸 데 없는 요소 */
const DROP = [
  'script', 'iframe', 'object', 'embed', 'base', 'meta', 'link', 'form', 'button', 'video', 'audio', 'template',
  '.code-tools', '.table-copy', '.lec-chart-tools', '.lec-chart-data', '.lec-unfold', '.lec-gutter', '.lec-here', '.lec-spot',
  '.lec-textbox-fold', '.front-matter', '.lec-new-line',
].join(', ');
const DROP_ATTRS = new Set(['data-lines', 'data-key', 'data-warn', 'data-issues', 'data-src', 'data-source', 'data-lec-href', 'data-lec-open',
  'data-chart', 'data-act', 'data-path', 'data-tex', 'data-notex', 'data-doc-path', 'contenteditable', 'spellcheck', 'tabindex']);
/** 지울 class — 접기·바뀐 곳·고른 곳 같은 화면의 상태 (접은 절·박스글은 이것을 떼면 펴진다) */
const MARKS = ['lec-fold', 'lec-folded', 'lec-fold-hidden', 'lec-textbox-folded', 'lec-changed', 'lec-picked', 'lec-target',
  'lec-cell-over', 'lec-cell-bad', 'lec-lit', 'lec-armed',
  'lec-fit'];   // 표의 열 폭(D173)은 앱 칸의 폭으로 잰 것 — 받은 쪽에서는 브라우저대로

/** 지울 CSS 변수 — 모든 열 맞추기(D173)의 열 폭·표 폭 (lec-fit 과 같이 앱 칸의 폭으로 잰 것) */
const DROP_VARS = ['--lec-w', '--lec-tw'];

/** 화면이 그린 문서를 담을 때 걸러 낼 것 — 지면 틀(layout.js)도 같은 것으로 */
export const MD_PACK = { drop: DROP, dropAttrs: DROP_ATTRS, marks: MARKS, dropVars: DROP_VARS };

/** 이 파일만의 CSS: 바탕과 가운데 단 — 화면에서는 앱의 문서 칸이 하던 일 */
const FRAME_CSS = `
html, body { margin: 0; padding: 0; }
body { background: var(--md-bg, #ffffff); color: var(--md-fg, #111111); }
article.md-body { box-sizing: border-box; }
@media print { body { background: #ffffff; } }`;

/** 파일의 제목: 맨 앞 # 제목, 없으면 맨 앞 설정의 title, 파일 이름 */
function titleOf(view, path) {
  const h1 = view.querySelector(':scope > h1')?.textContent.replace(/\s+/g, ' ').trim();
  const fm = [...view.querySelectorAll(':scope > .front-matter tr')].find((r) => r.querySelector('th')?.textContent.trim().toLowerCase() === 'title');
  return h1 || fm?.querySelector('td')?.textContent.trim() || basename(path).replace(/\.[^.]+$/, '');
}

/**
 * 칸이 그린 md 문서를 html 한 파일의 글로 짓는다: {text, title, notes(알릴 것)}.
 * @param {Pane} pane 문서를 그린 칸 (Lectern 슬라이드는 아니다 — 슬라이드는 'html 로 전환')
 * @param {string} path 프로젝트 안 경로
 * @param {{ printCss: string }} opt printCss: 받은 사람이 인쇄할 때의 쪽 머리 (printdoc.pageCss — 순환을 피해 부르는 쪽이 준다)
 */
export async function buildMdHtml(pane, path, { printCss }) {
  const view = pane.view;
  const images = new Map();
  const found = { external: 0, missing: 0, media: 0 };
  const article = await packClone(view, { ...MD_PACK, keepAnchors: true, images, found });
  const external = S.config?.external_images !== false;
  if (!external) {
    for (const img of article.querySelectorAll('img[src^="http"]')) img.removeAttribute('src');
    found.external = 0;
  }
  const math = !!view.querySelector('.katex');
  const css = styleText([...await appCss({ math }), FRAME_CSS]);
  const paper = styleText([await getText('/static/themes/print.css'), printCss]);
  const policy = [
    "default-src 'none'",
    "style-src 'self' 'unsafe-inline'",   // 'self': Lectern 이 이 파일을 html 문서로 보일 때 넣는 frame.css (htmldoc.js)
    `img-src data:${found.external ? ' https: http:' : ''}`,
    'font-src data:',
    "base-uri 'none'",
    "form-action 'none'",
  ].join('; ');
  const title = titleOf(view, path);
  const root = document.documentElement;
  const text = [
    '<!doctype html>',
    `<html lang="${esc(root.lang || 'ko')}" data-ui="${esc(root.dataset.ui || '')}" data-theme="${esc(root.dataset.theme || '')}" data-print-font="${esc(root.dataset.printFont || 'serif')}">`,
    '<head>',
    '<meta charset="utf-8">',
    '<meta name="generator" content="Lectern">',
    `<meta http-equiv="Content-Security-Policy" content="${esc(policy)}">`,
    '<meta name="referrer" content="no-referrer">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    `<meta name="lectern-source" content="${esc(basename(path))}">`,
    `<title>${esc(title)}</title>`,
    `<style>${css}</style>`,
    `<style media="print">${paper}</style>`,
    '</head>',
    '<body>',
    `<article class="md-body">${article.innerHTML}</article>`,
    '</body>',
    '</html>',
    '',
  ].join('\n').replace(/\r\n?/g, '\n');   // 줄바꿈은 LF 하나로 — 이 PC 의 CRLF 사본(스타일 css 등)이 섞이지 않게
  return { text, title, notes: foundNotes(found) };
}

/** 담으며 센 것을 알릴 글로 */
export function foundNotes(found) {
  const notes = [];
  if (found.external) notes.push(t('인터넷 그림 {n}개는 주소로 남았습니다 — 받은 사람의 브라우저가 불러옵니다', { n: found.external }));
  if (found.missing) notes.push(t('불러오지 못한 그림 {n}개는 빠졌습니다', { n: found.missing }));
  if (found.media) notes.push(t('동영상·소리 {n}개는 넣지 않았습니다', { n: found.media }));
  return notes;
}
