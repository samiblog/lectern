// 인쇄와 'PDF로 저장' (D131·D134): 종이에는 화면 스타일과 상관없이 보고서 양식(web/themes/print.css)으로 나간다.
// - 'PDF로 저장…'·'인쇄…' 는 'PDF·인쇄' 창을 연다 (D134): 왼쪽은 옵션(글꼴·여백·쪽 머리·쪽 번호 — 설정에 남는다), 오른쪽은 실제로
//   만들어질 PDF 의 미리보기. 미리보기는 창의 WebView2 가 인쇄 창 없이 만든 PDF(native.pdf_preview — 메모리에만)를 서버가
//   /pdf-preview/<토큰>.pdf 로 내주고 iframe 의 PDF 보기로 띄운다. 저장은 미리 본 그 바이트를 그대로 (native.save_pdf — 저장
//   대화상자에서 고른 경로 하나에만), 인쇄는 미리 본 PDF 를 인쇄한다 — 브라우저 인쇄 창이 붙이는 날짜·주소 머리글이 없다.
// - 브라우저 개발 모드와 html 문서에는 이 창이 없고 '인쇄 / PDF로 저장…' 하나 — 브라우저 인쇄 창 (html 문서는 그 문서 자체를,
//   iframe 에 allow-modals 가 있어야 한다).
// - 쪽 머리의 문서 제목·날짜는 CSS 만으로 머리로 옮길 수 없어(string-set 은 Chrome 에 없다) 인쇄 직전에 #lec-print-page 에 적는다.
//   여백·여백 상자의 글꼴도 여기서 — 여백 상자는 문서의 CSS 변수를 물려받지 않는다.
// - 늦게 불러오는 그림(loading=lazy)은 PDF 에 빈칸으로 남을 수 있어 인쇄 전에 모두 불러 둔다.

import { S, on, emit } from './store.js';
import { native, saveConfig } from './api.js';
import { $, $$, toast, isMd, basename, debounce } from './util.js';
import { t, LANG } from './i18n.js';

const PAGE_FONT = {
  ko: { serif: '"HCR Dotum", "함초롬돋움", "Malgun Gothic", "맑은 고딕", sans-serif', sans: '"Malgun Gothic", "맑은 고딕", sans-serif' },   // i18n-ok (글꼴 이름)
  en: { serif: '"Calibri", "Segoe UI", "Malgun Gothic", sans-serif', sans: '"Calibri", "Segoe UI", "Malgun Gothic", sans-serif' },
};
/** 여백 (위 오른쪽 아래 왼쪽) — 보통은 보고서 시안, 좁게는 사방 15mm, 넓게는 한글 문서의 넉넉한 좌우 */
export const MARGINS = { normal: '25mm 22mm 22mm 22mm', narrow: '15mm 15mm 15mm 15mm', wide: '30mm 30mm 25mm 30mm' };
const TITLE_MAX = 60;
const box = () => $('#lec-print');
/** @type {{ tab: Tab, pane: Pane, path: string, deck: boolean, token: string, seq: number, busy: boolean } | null} */
let dlg = null;

/** CSS content 의 글자 하나로: 따옴표·역슬래시를 막고 줄바꿈·제어 문자는 빈칸으로 */
export const cssString = (s) => `"${String(s).replace(/[\u0000-\u001f\u007f]+/g, ' ').replace(/[\\"]/g, '\\$&')}"`;

/** 인쇄·PDF 글꼴 (설정 print_font — 설정 창과 'PDF·인쇄' 창) */
export const printFont = () => (S.config?.print_font === 'sans' ? 'sans' : 'serif');
/** 여백 (설정 print_margin) */
export const printMargin = () => (Object.hasOwn(MARGINS, S.config?.print_margin || '') ? S.config.print_margin : 'normal');

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
 * 지금 칸의 문서로 쪽을 정한다: 보통 문서는 여백과 머리의 제목·날짜·쪽 번호(설정을 따라), Lectern 슬라이드는 쪽 크기를 슬라이드 크기로
 * (머리·쪽 번호 없이). 슬라이드의 쪽 크기를 쪽 이름(base.css 의 @page lec-slide)에만 두면 WebView2 의 PDF 는 기본 @page 크기
 * (print.css 의 A4, 없으면 Letter)로 만든다 — 기본 쪽 크기를 슬라이드 크기로 적어야 한다 (2026-11-13 시험)
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
  // 30줄이 넘는 코드는 쪽을 나눠 싣는다 (print.css — 짧은 것은 한 덩어리로). CSS 로는 줄 수를 셀 수 없다
  for (const pre of view?.querySelectorAll('pre:not(.mermaid):not(.lec-chart)') || []) {
    pre.classList.toggle('lec-print-long', (pre.textContent.match(/\n/g) || []).length > 30);
  }
  const { title, date } = pageHead(view, view?.dataset.docPath);
  const font = PAGE_FONT[LANG === 'en' ? 'en' : 'ko'][printFont()];
  const head = S.config?.print_header !== false;
  const pages = S.config?.print_page_numbers !== false;
  // 첫 쪽과 슬라이드 쪽의 '머리 없음'을 뒤에 다시 적는다 — Chrome 은 여백 상자 규칙을 :first·쪽 이름의 무게가 아니라 나중 것으로 고른다
  const none = '@top-left { content: none; } @top-right { content: none; }';
  style.textContent = [
    `@page { margin: ${MARGINS[printMargin()]}; @top-left { content: ${head ? cssString(title) : 'none'}; font-family: ${font}; } `
    + `@top-right { content: ${head ? cssString(date) : 'none'}; font-family: ${font}; } @bottom-center { ${pages ? '' : 'content: none; '}font-family: ${font}; } }`,
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

/** 인쇄 대화상자 (브라우저 개발 모드·html 문서). html 문서는 그 문서 자체(자기 스타일)를 인쇄한다 */
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

/** 'PDF·인쇄' 창을 쓸 수 있는 화면 — 창 모드의 md 문서(Lectern 슬라이드 포함). html 문서·코드·자료·폴더 개요는 아니다 */
export function canSavePdf(path = S.pane?.view?.dataset.docPath) {
  // 칸이 html 문서를 보여도 dataset.docPath 에는 앞의 md 문서가 남아 있다 (doc.js 만 적는다) — 메뉴의 문서와 같을 때만
  return native.has('pdf_preview') && !!path && isMd(path) && S.pane?.view?.dataset.docPath === path && !S.pane.view.querySelector(':scope > iframe.lec-html');
}

// ---- 'PDF·인쇄' 창 (D134) ------------------------------------------------------------

/** 창을 연다 — kind 는 처음 누를 단추 ('pdf' 는 PDF로 저장, 'print' 는 인쇄) */
export function openPrint(kind = 'pdf') {
  if (!canSavePdf()) return;
  const view = S.pane.view;
  dlg = { tab: S.tab, pane: S.pane, path: view.dataset.docPath, deck: view.classList.contains('lec-deck'), token: '', seq: 0, busy: false };
  for (const r of $$('#lec-print input[name="pp_font"]')) r.checked = r.value === printFont();
  for (const r of $$('#lec-print input[name="pp_margin"]')) r.checked = r.value === printMargin();
  $('#lec-pp-header').checked = S.config?.print_header !== false;
  $('#lec-pp-pages').checked = S.config?.print_page_numbers !== false;
  $('#lec-print-layout').disabled = dlg.deck;
  $('#lec-print-note').textContent = dlg.deck ? t('Lectern 슬라이드는 슬라이드 크기의 쪽에 한 장씩, 화면 색 그대로 나옵니다 — 글꼴·여백·쪽 머리·쪽 번호는 쓰지 않습니다') : '';
  $('#lec-print-title').textContent = t('PDF·인쇄 — {name}', { name: basename(dlg.path) });
  $('#lec-print-save').classList.toggle('primary', kind !== 'print');
  $('#lec-print-paper').classList.toggle('primary', kind === 'print');
  box().hidden = false;
  (kind === 'print' ? $('#lec-print-paper') : $('#lec-print-save')).focus();
  refresh();
}

export function closePrint() {
  if (!dlg) return false;
  dlg = null;
  box().hidden = true;
  $('#lec-print-frame').removeAttribute('src');
  return true;
}

function setBusy(text, error = false) {
  const msg = $('#lec-print-wait');
  msg.textContent = text || '';
  msg.hidden = !text;
  msg.classList.toggle('error', error);
  const ready = !!dlg?.token && !text;
  $('#lec-print-save').disabled = !ready;
  $('#lec-print-paper').disabled = !ready;
}

/** 지금 옵션으로 미리보기 PDF 를 만들어 띄운다. 그사이 옵션이 또 바뀌면 앞의 결과는 버린다 */
async function refresh() {
  if (!dlg) return;
  const seq = ++dlg.seq;
  dlg.token = '';
  setBusy(t('미리보기를 만드는 중입니다…'));
  try {
    preparePage();
    await loadImages();
    const r = await window.pywebview.api.pdf_preview();
    if (!dlg || seq !== dlg.seq) return;
    if (r?.error) {
      setBusy(r.error, true);
      return;
    }
    dlg.token = r.token;
    $('#lec-print-frame').src = `/pdf-preview/${r.token}.pdf#view=Fit`;   // 쪽 전체 — Edge 의 PDF 보기는 FitH 를 따르지 않는다
    $('#lec-print-info').textContent = t('{n}쪽 · {kb}KB', { n: r.pages, kb: Math.max(1, Math.round(r.size / 1024)) });
    setBusy('');
  } catch (e) {
    if (dlg && seq === dlg.seq) setBusy(t('PDF 를 만들지 못했습니다: {error}', { error: e?.message || String(e) }), true);
  }
}
const refreshSoon = debounce(refresh, 250);

/** 옵션을 바꿨다 — 설정에 남기고 미리보기를 다시 만든다 */
async function onOption(e) {
  const el = e.target;
  if (!dlg || !(el instanceof HTMLInputElement)) return;
  const patch = el.name === 'pp_font' ? { print_font: el.value } : el.name === 'pp_margin' ? { print_margin: el.value }
    : el.id === 'lec-pp-header' ? { print_header: el.checked } : el.id === 'lec-pp-pages' ? { print_page_numbers: el.checked } : null;
  if (!patch) return;
  setBusy(t('미리보기를 만드는 중입니다…'));
  await saveConfig(patch);
  if (patch.print_font) emit('print-font');
  refreshSoon();
}

/** 'PDF로 저장…': 미리 본 PDF 를 저장 대화상자에서 고른 곳에 그대로 */
async function save() {
  if (!dlg?.token || dlg.busy) return;
  dlg.busy = true;
  try {
    const r = await window.pywebview.api.save_pdf(dlg.tab.id, dlg.path, dlg.token);
    if (r?.error) setBusy(r.error, true);
    else if (r?.path) {
      closePrint();
      toast(t('PDF 로 저장했습니다: {path}', { path: r.path }), '', 5000);
    }
  } catch (e) {
    setBusy(t('PDF 를 만들지 못했습니다: {error}', { error: e?.message || String(e) }), true);
  } finally {
    if (dlg) dlg.busy = false;
  }
}

/** '인쇄…': 미리 본 PDF 를 인쇄한다 (프린터·매수·쪽은 인쇄 창에서). 미리보기를 인쇄할 수 없으면 문서를 인쇄 창으로 */
function paper() {
  if (!dlg?.token) return;
  const win = $('#lec-print-frame').contentWindow;
  try {
    win.focus();
    win.print();   // PDF 보기의 인쇄 — 기다리지 않고 바로 돌아온다 (인쇄 창은 WebView2 가 따로 띄운다)
    $('#lec-print-paper').focus();   // 인쇄 창을 닫은 뒤 Esc 가 이 창으로 오게 (초점이 PDF 보기 안에 있으면 키가 오지 않는다)
  } catch {
    closePrint();
    printDoc();
  }
}

/** 인쇄·PDF 글꼴을 문서 루트에 (print.css 가 :root[data-print-font] 로 고른다) */
export function applyPrintFont() {
  document.documentElement.dataset.printFont = printFont();
}

export function initPrint() {
  applyPrintFont();
  on('print-font', applyPrintFont);   // 설정 창·'PDF·인쇄' 창에서 바꿀 때
  addEventListener('beforeprint', () => { if (!dlg) preparePage(); });   // 다른 길로 연 인쇄 창도 같은 머리로 (창에서는 이미 적었다)
  box().addEventListener('change', onOption);
  box().addEventListener('click', (e) => { if (e.target === box()) closePrint(); });   // 바깥을 누르면 닫기
  $('#lec-print-close').addEventListener('click', closePrint);
  $('#lec-print-save').addEventListener('click', save);
  $('#lec-print-paper').addEventListener('click', paper);
  // 미리보기(PDF 보기)를 누르면 초점이 그 안으로 들어가 Esc 가 오지 않는다 — 마우스가 나가면 창으로 되돌린다
  $('#lec-print .print-preview').addEventListener('mouseleave', () => {
    if (dlg && document.activeElement === $('#lec-print-frame')) $('#lec-print .print-box').focus();
  });
  on('tab', () => closePrint());
  // 창을 연 사이 문서가 다시 그려지면(Claude 가 고침) 미리보기도 다시 — 옛 미리보기를 저장하지 않게
  on('rendered', (pane) => { if (dlg && pane === dlg.pane) refreshSoon(); });
}
