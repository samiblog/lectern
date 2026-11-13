// 인쇄와 'PDF로 저장' (D131): 종이에는 화면 스타일과 상관없이 보고서 양식(web/themes/print.css)으로 나간다.
// - 'PDF로 저장…' 은 창의 WebView2 가 인쇄 창 없이 만든다 (native.py 의 save_pdf → pdfexport.py). 저장 대화상자에서 사용자가
//   고른 경로 하나에만 쓴다. 브라우저 인쇄 창이 붙이는 날짜·창 제목·주소 머리글이 없다. 브라우저 개발 모드와 html 문서에는 없다.
// - '인쇄…' 는 브라우저 인쇄 창이다. html 문서는 그 문서 자체(자기 스타일)를 인쇄한다 — iframe 에 allow-modals 가 있어야 한다.
// - 쪽 머리의 문서 제목·날짜는 CSS 만으로 머리로 옮길 수 없어(string-set 은 Chrome 에 없다) 인쇄 직전에 #lec-print-page 에 적는다.
//   여백 상자의 글꼴도 여기서 — 여백 상자는 문서의 CSS 변수를 물려받지 않는다.
// - 늦게 불러오는 그림(loading=lazy)은 PDF 에 빈칸으로 남을 수 있어 인쇄 전에 모두 불러 둔다.

import { S, on } from './store.js';
import { native } from './api.js';
import { $, toast, isMd, basename } from './util.js';
import { t, LANG } from './i18n.js';

const PAGE_FONT = {
  ko: { serif: '"HCR Dotum", "함초롬돋움", "Malgun Gothic", "맑은 고딕", sans-serif', sans: '"Malgun Gothic", "맑은 고딕", sans-serif' },   // i18n-ok (글꼴 이름)
  en: { serif: '"Calibri", "Segoe UI", "Malgun Gothic", sans-serif', sans: '"Calibri", "Segoe UI", "Malgun Gothic", sans-serif' },
};
const TITLE_MAX = 60;
let busy = false;

/** CSS content 의 글자 하나로: 따옴표·역슬래시를 막고 줄바꿈·제어 문자는 빈칸으로 */
export const cssString = (s) => `"${String(s).replace(/[\u0000-\u001f\u007f]+/g, ' ').replace(/[\\"]/g, '\\$&')}"`;

/** 인쇄·PDF 글꼴 (설정 창의 '인쇄·PDF 글꼴', config print_font) */
export const printFont = () => (S.config?.print_font === 'sans' ? 'sans' : 'serif');

/** 화면의 맨 앞 설정 표에서 한 값 (doc.js 의 frontMatterHtml — 열쇠는 영문) */
function frontValue(view, key) {
  for (const row of view.querySelectorAll(':scope > .front-matter tr')) {
    if (row.querySelector('th')?.textContent.trim().toLowerCase() === key) return row.querySelector('td')?.textContent.trim() || '';
  }
  return '';
}

/** 쪽 머리에 쓸 문서 제목과 날짜 — 제목은 맨 앞 # 제목(없으면 맨 앞 설정의 title, 파일 이름), 날짜는 맨 앞 설정의 date(없으면 오늘) */
export function pageHead(view, path, today = new Date()) {
  const h1 = view?.querySelector(':scope > h1')?.textContent.replace(/\s+/g, ' ').trim();
  let title = h1 || (view && frontValue(view, 'title')) || basename(path || '').replace(/\.[^.]+$/, '');
  if (title.length > TITLE_MAX) title = `${title.slice(0, TITLE_MAX - 1)}…`;
  const date = (view && frontValue(view, 'date')) || new Intl.DateTimeFormat(LANG === 'en' ? 'en-US' : 'ko-KR', { dateStyle: 'long' }).format(today);
  return { title, date };
}

/**
 * 지금 칸의 문서로 쪽을 정한다: 보통 문서는 머리의 제목·날짜, Lectern 슬라이드는 쪽 크기를 슬라이드 크기로 (머리·쪽 번호 없이).
 * 슬라이드의 쪽 크기를 쪽 이름(base.css 의 @page lec-slide)에만 두면 WebView2 의 PDF 는 기본 @page 크기(print.css 의 A4,
 * 없으면 Letter)로 만든다 — 기본 쪽 크기를 슬라이드 크기로 적어야 한다 (2026-11-13 시험)
 */
function preparePage() {
  const view = S.pane?.view;
  let style = $('#lec-print-page');
  if (!style) {
    style = document.createElement('style');
    style.id = 'lec-print-page';
    document.head.append(style);
  }
  if (view?.classList.contains('lec-deck')) {
    const size = view.querySelector('.lec-slide-wrap.lec-43') ? '960px 720px' : '1280px 720px';   // slides.js 의 lec-43 (base.css 의 쪽 이름과 같게)
    style.textContent = `@page { size: ${size}; margin: 0; @top-left { content: none; } @top-right { content: none; } @bottom-center { content: none; } }`;
    return;
  }
  const { title, date } = pageHead(view, view?.dataset.docPath);
  const font = PAGE_FONT[LANG === 'en' ? 'en' : 'ko'][printFont()];
  // 첫 쪽과 슬라이드 쪽의 '머리 없음'을 뒤에 다시 적는다 — Chrome 은 여백 상자 규칙을 :first·쪽 이름의 무게가 아니라 나중 것으로 고른다
  const none = '@top-left { content: none; } @top-right { content: none; }';
  style.textContent = [
    `@page { @top-left { content: ${cssString(title)}; font-family: ${font}; } @top-right { content: ${cssString(date)}; font-family: ${font}; } @bottom-center { font-family: ${font}; } }`,
    `@page :first { ${none} }`,
    `@page lec-slide { ${none} @bottom-center { content: none; } }`,
    `@page lec-slide-43 { ${none} @bottom-center { content: none; } }`,
  ].join('\n');
}

/** 늦게 불러오는 그림을 지금 불러 둔다 (한 장에 10초까지) */
async function loadImages() {
  const imgs = [...(S.pane?.view?.querySelectorAll('img') || [])];
  for (const img of imgs) if (img.loading === 'lazy') img.loading = 'eager';
  await Promise.all(imgs.filter((img) => img.src && !img.complete).map((img) => new Promise((resolve) => {
    img.addEventListener('load', resolve, { once: true });
    img.addEventListener('error', resolve, { once: true });
    setTimeout(resolve, 10000);
  })));
}

/** 인쇄 대화상자. html 문서는 그 문서 자체(자기 스타일)를 인쇄한다 */
export async function printDoc() {
  const frame = $('#lec-view > iframe.lec-html:not(.lec-loading)');
  if (frame) {
    frame.contentWindow.print();
    return;
  }
  preparePage();
  await loadImages();
  window.print();
}

/** 'PDF로 저장…' 을 쓸 수 있는 화면 — 창 모드의 md 문서(Lectern 슬라이드 포함). html 문서·코드·자료·폴더 개요는 아니다 */
export function canSavePdf(path = S.pane?.view?.dataset.docPath) {
  // 칸이 html 문서를 보여도 dataset.docPath 에는 앞의 md 문서가 남아 있다 (doc.js 만 적는다) — 메뉴의 문서와 같을 때만
  return native.has('save_pdf') && !!path && isMd(path) && S.pane?.view?.dataset.docPath === path && !S.pane.view.querySelector(':scope > iframe.lec-html');
}

/** 'PDF로 저장…': 저장 대화상자는 창(native.py)이 띄우고, 고른 경로에 지금 칸의 문서를 PDF 하나로 쓴다 */
export async function savePdf() {
  if (busy || !canSavePdf()) return;
  busy = true;
  try {
    preparePage();
    await loadImages();
    const r = await window.pywebview.api.save_pdf(S.tab?.id || '', S.pane.view.dataset.docPath);
    if (r?.error) toast(r.error, 'error', 6000);
    else if (r?.path) toast(t('PDF 로 저장했습니다: {path}', { path: r.path }), '', 5000);
  } catch (e) {
    toast(t('PDF 를 만들지 못했습니다: {error}', { error: e?.message || String(e) }), 'error', 6000);
  } finally {
    busy = false;
  }
}

/** 인쇄·PDF 글꼴을 문서 루트에 (print.css 가 :root[data-print-font] 로 고른다) */
export function applyPrintFont() {
  document.documentElement.dataset.printFont = printFont();
}

export function initPrint() {
  applyPrintFont();
  on('print-font', applyPrintFont);   // 설정 창에서 바꿀 때
  addEventListener('beforeprint', preparePage);   // 다른 길로 연 인쇄 창도 같은 머리로
}
