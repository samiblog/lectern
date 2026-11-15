// 인쇄와 'PDF로 저장' (D131·D134): 종이에는 화면 스타일과 상관없이 보고서 양식(web/themes/print.css)으로 나간다.
// - 'PDF로 저장…'·'인쇄…' 는 내보내기 창을 연다 (D134): 왼쪽은 옵션(글꼴·여백·쪽 머리·쪽 번호 — 설정에 남는다), 오른쪽은 실제로
//   만들어질 PDF 의 미리보기. 미리보기는 창의 WebView2 가 인쇄 창 없이 만든 PDF(native.pdf_preview — 메모리에만)를 서버가
//   /pdf-preview/<토큰>.pdf 로 내주고 iframe 의 PDF 보기로 띄운다. 저장은 미리 본 그 바이트를 그대로 (native.save_pdf — 저장
//   대화상자에서 고른 경로 하나에만), 인쇄는 미리 본 PDF 를 인쇄한다 — 브라우저 인쇄 창이 붙이는 날짜·주소 머리글이 없다.
// - 내보내기 창 (D144): 같은 창에서 형식을 고른다 — PDF·인쇄, html 한 파일. html 은 화면이 지은 파일(mdhtml.js)을 서버 메모리에 두고
//   (/api/export/keep) /export-preview/<토큰>.html 로 미리 보이며, 저장은 그 바이트를 저장 대화상자에서 고른 곳에 (native.save_export).
//   브라우저 개발 모드는 PDF 를 만들 수 없어 html 만 — 저장은 내려받기로.
// - Word (D146): 서버가 스킬의 build_docx 로 docx 를 만들어 메모리에 둔다 (/api/export/docx). 미리보기는 없고 만든 결과(그림 수·알림)를
//   알린다. 양식은 설정 폴더 docx-styles 의 .dotx·.docx — 맨 앞 설정 docxStyle, 없으면 layout 과 같은 이름의 양식이 처음 값.
// - 브라우저 개발 모드와 html 문서에는 PDF 창이 없고 '인쇄 / PDF로 저장…' 하나 — 브라우저 인쇄 창 (html 문서는 그 문서 자체를,
//   iframe 에 allow-modals 가 있어야 한다).
// - 쪽 머리의 문서 제목·날짜는 CSS 만으로 머리로 옮길 수 없어(string-set 은 Chrome 에 없다) 인쇄 직전에 #lec-print-page 에 적는다.
//   여백·여백 상자의 글꼴도 여기서 — 여백 상자는 문서의 CSS 변수를 물려받지 않는다.
// - 늦게 불러오는 그림(loading=lazy)은 PDF 에 빈칸으로 남을 수 있어 인쇄 전에 모두 불러 둔다.

import { S, on, emit } from './store.js';
import { native, saveConfig, postJSON, getJSON } from './api.js';
import { $, $$, toast, isMd, basename, debounce, copyText } from './util.js';
import { html, setHtml } from './html.js';
import { buildMdHtml } from './mdhtml.js';
import { listLayouts, buildLayoutHtml, fieldsOf, fieldSample, ALIAS } from './layout.js';
import { t, LANG } from './i18n.js';

const PAGE_FONT = {
  ko: { serif: '"HCR Dotum", "함초롬돋움", "Malgun Gothic", "맑은 고딕", sans-serif', sans: '"Malgun Gothic", "맑은 고딕", sans-serif' },   // i18n-ok (글꼴 이름)
  en: { serif: '"Calibri", "Segoe UI", "Malgun Gothic", sans-serif', sans: '"Calibri", "Segoe UI", "Malgun Gothic", sans-serif' },
};
/** 여백 (위 오른쪽 아래 왼쪽) — 보통은 보고서 시안, 좁게는 사방 15mm, 넓게는 한글 문서의 넉넉한 좌우 */
export const MARGINS = { normal: '25mm 22mm 22mm 22mm', narrow: '15mm 15mm 15mm 15mm', wide: '30mm 30mm 25mm 30mm' };
const TITLE_MAX = 60;
const box = () => $('#lec-print');
/** @type {{ tab: Tab, pane: Pane, path: string, deck: boolean, format: 'pdf' | 'html' | 'docx', layout: string, layouts: any[], docx: string, token: string, seq: number, busy: boolean } | null} */
let dlg = null;
/** 미리보기를 만들 때마다 하나씩 — 창을 닫았다 다시 열어도 이어서 센다. 창마다 0부터 세면 닫은 창의 늦은 결과가 새 창의
    같은 번호로 통과해, 다른 문서의 파일이 저장 단추에 들어간다 */
let builds = 0;

/** CSS content 의 글자 하나로: 따옴표·역슬래시를 막고 줄바꿈·제어 문자는 빈칸으로 */
export const cssString = (s) => `"${String(s).replace(/[\u0000-\u001f\u007f]+/g, ' ').replace(/[\\"]/g, '\\$&')}"`;

/** 인쇄·PDF 글꼴 (설정 print_font — 설정 창과 내보내기 창) */
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
  style.textContent = pageCss(view);
}

/**
 * 쪽을 정하는 CSS: 보통 문서는 여백과 머리의 제목·날짜·쪽 번호(설정을 따라), Lectern 슬라이드는 쪽 크기를 슬라이드 크기로.
 * 'html 로 저장' 한 파일에도 같은 글을 넣는다 — 받은 사람이 브라우저에서 인쇄해도 보고서 양식 (D144). 30줄이 넘는 코드에 표시를 단다
 */
export function pageCss(view) {
  if (view?.classList.contains('lec-deck')) {
    const size = view.querySelector('.lec-slide-wrap.lec-43') ? '960px 720px' : '1280px 720px';   // slides.js 의 lec-43 (base.css 의 쪽 이름과 같게)
    return `@page { size: ${size}; margin: 0; @top-left { content: none; } @top-right { content: none; } @bottom-center { content: none; } }`;
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
  return [
    `@page { margin: ${MARGINS[printMargin()]}; @top-left { content: ${head ? cssString(title) : 'none'}; font-family: ${font}; } `
    + `@top-right { content: ${head ? cssString(date) : 'none'}; font-family: ${font}; } @bottom-center { ${pages ? '' : 'content: none; '}font-family: ${font}; } }`,
    `@page :first { ${none} }`,
    `@page lec-slide { ${none} @bottom-center { content: none; } }`,
    `@page lec-slide-43 { ${none} @bottom-center { content: none; } }`,
  ].join('\n');
}

/** 늦게 불러오는 그림을 지금 불러 둔다 (한 장에 10초까지) */
export async function loadImages() {
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

/** 내보내기 창을 쓸 수 있는 화면 — 창 모드의 md 문서(Lectern 슬라이드 포함). html 문서·코드·자료·폴더 개요는 아니다 */
export function canSavePdf(path = S.pane?.view?.dataset.docPath) {
  // 칸이 html 문서를 보여도 dataset.docPath 에는 앞의 md 문서가 남아 있다 (doc.js 만 적는다) — 메뉴의 문서와 같을 때만
  // 폴더 개요·코드 화면에서도 남아 있다 — 칸이 지금 보이는 것(pane.current)이 그 md 문서일 때만
  return native.has('pdf_preview') && !!path && isMd(path) && S.pane?.view?.dataset.docPath === path && !S.pane.view.querySelector(':scope > iframe.lec-html')
    && S.pane.current?.type === 'doc' && S.pane.current.path === path;
}

/** 'html 로 저장' 을 쓸 수 있는 화면 — 칸이 보이는 md 문서 (Lectern 슬라이드는 'html 로 전환'). 브라우저 개발 모드에서도 (D144) */
export function canExportHtml(path = S.pane?.view?.dataset.docPath) {
  return !!path && isMd(path) && S.pane?.view?.dataset.docPath === path && !S.pane.view.querySelector(':scope > iframe.lec-html')
    && !S.pane.view.classList.contains('lec-deck') && S.pane.current?.type === 'doc' && S.pane.current.path === path;
}

// ---- 내보내기 창 — PDF·인쇄 (D134), html (D144) ------------------------------------------------

/** 창을 연다 — kind 는 처음 누를 단추 ('pdf' 는 PDF로 저장, 'print' 는 인쇄, 'html' 은 html 로 저장, 'docx' 는 Word로 저장) */
export function openPrint(kind = 'pdf') {
  const format = kind === 'html' ? 'html' : kind === 'docx' ? 'docx' : 'pdf';
  if (format === 'pdf' ? !canSavePdf() : !canExportHtml()) return;
  const view = S.pane.view;
  dlg = { tab: S.tab, pane: S.pane, path: view.dataset.docPath, deck: view.classList.contains('lec-deck'), format, layout: '', layouts: [], docx: '', token: '', seq: ++builds, busy: false };
  for (const r of $$('#lec-print input[name="pp_font"]')) r.checked = r.value === printFont();
  for (const r of $$('#lec-print input[name="pp_margin"]')) r.checked = r.value === printMargin();
  $('#lec-pp-header').checked = S.config?.print_header !== false;
  $('#lec-pp-pages').checked = S.config?.print_page_numbers !== false;
  $('#lec-print-layout').disabled = dlg.deck;
  $('#lec-print-title').textContent = t('내보내기 — {name}', { name: basename(dlg.path) });
  $('#lec-print-save').classList.toggle('primary', kind !== 'print');
  $('#lec-print-paper').classList.toggle('primary', kind === 'print');
  const pdf = $('#lec-print input[name="pp_format"][value="pdf"]');
  pdf.disabled = !canSavePdf();
  pdf.closest('label').title = pdf.disabled ? t('PDF 는 Lectern 창에서 만듭니다 — 브라우저 개발 모드에는 없습니다') : '';
  $('#lec-print input[name="pp_format"][value="html"]').disabled = dlg.deck;
  $('#lec-print input[name="pp_format"][value="docx"]').disabled = dlg.deck;
  box().hidden = false;
  showFormat();
  $('#lec-print-docx-info').textContent = '';   // 앞에 연 문서의 결과가 남지 않게
  $('#lec-print-info').textContent = '';
  setBusy(t('미리보기를 만드는 중입니다…'));   // 만들기 전에는 단추를 끈다 (앞에 연 창의 것이 켜진 채 남지 않게)
  (format === 'html' ? $('#lec-print-html') : format === 'docx' ? $('#lec-print-docx') : kind === 'print' ? $('#lec-print-paper') : $('#lec-print-save')).focus();
  Promise.all([fillLayouts(), fillDocx()]).then(refresh);
}

/** Word 양식 목록을 채운다 — 맨 앞 설정 docxStyle(양식 이름)이 있으면 그것, 없으면 layout(틀)과 같은 이름의 양식 (D146) */
async function fillDocx() {
  const d = dlg;
  let list = [];
  try {
    list = d.deck ? [] : (await getJSON('/api/docx-styles')).styles || [];
  } catch { /* 목록을 못 읽으면 기본 양식만 */ }
  if (dlg !== d) return;
  const sel = $('#lec-pp-docx');
  setHtml(sel, [html`<option value="">${t('Lectern 기본 양식')}</option>`, ...list.map((s) => html`<option value="${s.name}">${s.name}</option>`)]);
  const fields = fieldsOf(d.pane);
  const named = String(fields.docxStyle ?? fields['Word 양식'] ?? '').trim();   // i18n-ok (맨 앞 설정의 한국어 키)
  const layout = String(fields.layout ?? fields['틀'] ?? '').trim().replace(/^user\//, '');   // i18n-ok (맨 앞 설정의 한국어 키)
  const hit = list.find((s) => s.name === named || s.file === named) || list.find((s) => s.name === layout);
  d.docx = hit ? hit.name : '';
  sel.value = d.docx;
}

/** 틀 목록을 채운다 — 맨 앞 설정의 layout(틀 id·이름)이 있으면 그것을 고른다. 슬라이드는 틀이 없다 */
async function fillLayouts() {
  const d = dlg;
  const sel = $('#lec-pp-layout');
  let list = [];
  try {
    list = d.deck ? [] : await listLayouts(true);
  } catch { /* 목록을 못 읽으면 기본 양식만 */ }
  if (dlg !== d) return;
  d.layouts = list;
  const en = LANG === 'en';
  const groups = new Map();
  for (const l of list) {
    const g = l.user ? t('내 틀') : (en ? l.group_en : l.group) || t('그 밖');
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(l);
  }
  setHtml(sel, [html`<option value="">${t('보고서 (기본 양식)')}</option>`,
    ...[...groups].map(([g, ls]) => html`<optgroup label="${g}">${ls.map((l) => html`<option value="${l.id}">${en ? l.name_en : l.name}</option>`)}</optgroup>`)]);
  const want = String(fieldsOf(d.pane).layout ?? fieldsOf(d.pane)['틀'] ?? '').trim();   // i18n-ok (맨 앞 설정의 한국어 키)
  const hit = want && list.find((l) => l.id === want || l.name === want || l.name_en === want || l.id === `user/${want}`);
  d.layout = hit ? hit.id : '';
  sel.value = d.layout;
  sel.disabled = d.deck;
  showLayout();
}

/** 고른 틀의 설명과 비어 있는 맨 앞 설정 — 기본 양식이면 PDF 옵션(글꼴·여백·쪽 머리·쪽 번호)을 보인다 */
function showLayout() {
  const info = dlg.layouts.find((l) => l.id === dlg.layout);
  const en = LANG === 'en';
  $('#lec-print-layout').hidden = dlg.format !== 'pdf' || !!info;
  const fields = fieldsOf(dlg.pane);
  const empty = (info?.fields || []).filter((k) => !['title', 'date'].includes(k) && fields[k] == null && fields[ALIAS[k]] == null);
  const slots = (info?.slots || []).map((n) => `<!-- box: ${n} -->`).join(' ');
  const lines = info ? [en ? info.description_en : info.description, info.flow ? t('쪽 없이 길게') : t('쪽: {size}', { size: info.pages })] : [];
  if (empty.length) lines.push(t('이 틀이 쓰는 맨 앞 설정 중 비어 있는 것: {keys}', { keys: empty.join(', ') }));
  if (slots) lines.push(t('박스글 자리: {slots}', { slots }));
  $('#lec-pp-layout-info').textContent = lines.join('\n');
  $('#lec-pp-layout-sample').hidden = !empty.length;
  showNote();
}

/** 고른 형식에 맞춰 옵션·단추·알림을 보인다 */
function showFormat() {
  const html = dlg.format === 'html';
  const docx = dlg.format === 'docx';
  for (const r of $$('#lec-print input[name="pp_format"]')) r.checked = r.value === dlg.format;
  $('#lec-print-layout').hidden = dlg.format !== 'pdf';
  $('#lec-print .print-layouts').hidden = docx;
  $('#lec-print .print-docx').hidden = !docx;
  $('#lec-print-paper').hidden = dlg.format !== 'pdf';
  $('#lec-print-save').hidden = dlg.format !== 'pdf';
  $('#lec-print-html').hidden = !html;
  $('#lec-print-docx').hidden = !docx;
  $('#lec-print-frame').hidden = docx;
  $('#lec-print-docx-info').hidden = !docx;
  $('#lec-print-same').hidden = docx;
  showNote();
  $('#lec-print-html-note').textContent = dlg.deck ? t("Lectern 슬라이드의 html 은 상태줄의 'html 로 전환'으로 만듭니다") : '';
}

/** 형식과 틀에 맞는 알림 — html 은 틀을 고르면 그 틀의 모양, 아니면 지금 화면 스타일 */
function showNote() {
  const html = dlg.format === 'html';
  $('#lec-print-note').textContent = html && dlg.layout ? t('고른 틀의 모양으로 담습니다. 그림·차트·수식이 파일 안에 들어가 파일 하나만 보내면 됩니다 — 받은 사람이 인쇄하면 PDF 와 같은 꼴입니다')
    : html ? t('지금 화면 스타일 그대로 한 쪽에 길게 담습니다. 그림·차트·수식이 파일 안에 들어가 파일 하나만 보내면 됩니다 — 받은 사람이 인쇄하면 PDF 와 같은 보고서 양식입니다')
    : dlg.format === 'docx' ? t('Word 에서 고쳐 쓸 수 있는 파일입니다. 글·표·각주·캡션 번호는 Word 의 것으로, 차트·다이어그램·블록 수식은 그림으로 들어갑니다. 쪽은 Word 가 나눕니다')
    : dlg.deck ? t('Lectern 슬라이드는 슬라이드 크기의 쪽에 한 장씩, 화면 색 그대로 나옵니다 — 글꼴·여백·쪽 머리·쪽 번호는 쓰지 않습니다') : '';
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
  $('#lec-print-html').disabled = !ready;
  $('#lec-print-docx').disabled = !ready;
}

/** 지금 옵션으로 미리보기 PDF 를 만들어 띄운다. 그사이 옵션이 또 바뀌면 앞의 결과는 버린다 */
async function refresh() {
  if (!dlg) return;
  const seq = dlg.seq = ++builds;
  dlg.token = '';
  if (dlg.format === 'docx') {
    await refreshDocx(seq);
    return;
  }
  setBusy(t('미리보기를 만드는 중입니다…'));
  if (dlg.format === 'html' || dlg.layout) {
    await refreshHtml(seq);
    return;
  }
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

/**
 * 형식·옵션·틀·양식을 바꿨거나 문서가 바뀌었다 — 앞의 결과는 바로 버리고 잠깐 뒤에 다시 만든다. 다시 만들기 전의 틈에
 * 앞 형식의 결과가 저장 단추에 남아 있으면 html 을 Word 로 받는 일이 생긴다 (그사이 늦게 온 앞의 결과도 seq 로 버린다)
 */
function remake() {
  if (!dlg) return;
  dlg.seq = ++builds;
  dlg.token = '';
  $('#lec-print-info').textContent = '';
  $('#lec-print-docx-info').textContent = '';
  setBusy(dlg.format === 'docx' ? t('Word 파일을 만드는 중입니다. 차트가 많으면 조금 걸립니다…') : t('미리보기를 만드는 중입니다…'));
  refreshSoon();
}

/**
 * html 한 파일을 지어 서버 메모리에 두고 미리 보인다 (D144). 틀을 골랐으면 틀로 짓고 (D145), PDF 형식이면 그 html 을
 * 숨은 창이 PDF 로 찍어(native.layout_pdf) PDF 를 미리 보인다 — 저장·인쇄는 그 PDF
 */
async function refreshHtml(seq) {
  try {
    const printCss = pageCss(dlg.pane.view);
    await loadImages();
    const info = dlg.layouts.find((l) => l.id === dlg.layout);
    const built = info ? await buildLayoutHtml(dlg.pane, dlg.path, info) : await buildMdHtml(dlg.pane, dlg.path, { printCss });
    if (!dlg || seq !== dlg.seq) return;
    const r = await postJSON('/api/export/keep', { text: built.text });
    if (!dlg || seq !== dlg.seq) return;
    $('#lec-print-html-note').textContent = built.notes.join('\n');
    if (dlg.format === 'pdf') {
      const pdf = await window.pywebview.api.layout_pdf(r.token);
      if (!dlg || seq !== dlg.seq) return;
      if (pdf?.error) {
        setBusy(pdf.error, true);
        return;
      }
      dlg.token = pdf.token;
      $('#lec-print-frame').src = `/pdf-preview/${pdf.token}.pdf#view=Fit`;
      $('#lec-print-info').textContent = t('{n}쪽 · {kb}KB', { n: pdf.pages, kb: Math.max(1, Math.round(pdf.size / 1024)) });
      setBusy('');
      return;
    }
    dlg.token = r.token;
    $('#lec-print-frame').src = `/export-preview/${r.token}.html`;
    $('#lec-print-info').textContent = t('html 한 파일 · {kb}KB', { kb: Math.max(1, Math.round(r.size / 1024)) });
    setBusy('');
  } catch (e) {
    if (dlg && seq === dlg.seq) setBusy(t('html 을 만들지 못했습니다: {error}', { error: e?.message || String(e) }), true);
  }
}

/** Word 파일을 만들어 서버 메모리에 둔다 (D146). 미리보기는 없고 만든 결과 — 크기·그림 수·스킬의 알림 — 를 보인다 */
async function refreshDocx(seq) {
  const info = $('#lec-print-docx-info');
  info.textContent = '';
  setBusy(t('Word 파일을 만드는 중입니다. 차트가 많으면 조금 걸립니다…'));
  try {
    const r = await postJSON('/api/export/docx', { p: dlg.tab.id, path: dlg.path, style: dlg.docx });
    if (!dlg || seq !== dlg.seq) return;
    dlg.token = r.token;
    const kb = Math.max(1, Math.round(r.size / 1024));
    const lines = [t('Word 파일을 만들었습니다 — 그림 {n}개 · {kb}KB', { n: r.figures || 0, kb }), dlg.docx ? t('양식: {name}', { name: dlg.docx }) : t('양식: Lectern 기본 양식 (A4, 명조 본문, 2쪽부터 머리에 제목, 바닥에 쪽 번호)')];
    if (r.notes?.length) lines.push('', ...r.notes.slice(0, 8));
    lines.push('', t("미리보기는 없습니다 — 저장한 뒤 Word 에서 엽니다. 목차·캡션 번호가 있으면 Word 가 열 때 필드를 업데이트할지 묻습니다 — '예'를 누르면 채워집니다"));
    info.textContent = lines.join('\n');
    $('#lec-print-info').textContent = t('Word · {kb}KB', { kb });
    setBusy('');
  } catch (e) {
    if (dlg && seq === dlg.seq) setBusy(t('Word 파일을 만들지 못했습니다: {why}', { why: e?.message || String(e) }), true);
  }
}

/** 옵션을 바꿨다 — 설정에 남기고 미리보기를 다시 만든다 */
async function onOption(e) {
  const el = e.target;
  if (!dlg || !(el instanceof HTMLInputElement)) return;
  if (el.name === 'pp_format') {   // 형식은 설정에 남기지 않는다 — 여는 길(메뉴의 PDF·html)이 정한다
    dlg.format = el.value === 'html' ? 'html' : el.value === 'docx' ? 'docx' : 'pdf';
    showFormat();
    showLayout();
    remake();
    return;
  }
  const patch = el.name === 'pp_font' ? { print_font: el.value } : el.name === 'pp_margin' ? { print_margin: el.value }
    : el.id === 'lec-pp-header' ? { print_header: el.checked } : el.id === 'lec-pp-pages' ? { print_page_numbers: el.checked } : null;
  if (!patch) return;
  setBusy(t('미리보기를 만드는 중입니다…'));
  await saveConfig(patch);
  if (patch.print_font) emit('print-font');
  remake();
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

/** 'html 로 저장…': 미리 본 html 을 저장 대화상자에서 고른 곳에 그대로 (D144). 브라우저 개발 모드는 내려받기 */
async function saveHtml() {
  if (!dlg?.token || dlg.busy || dlg.format !== 'html') return;
  dlg.busy = true;
  try {
    if (!native.has('save_export')) {
      const a = document.createElement('a');
      a.href = `/export-preview/${dlg.token}.html`;
      a.download = basename(dlg.path).replace(/\.[^.]+$/, '') + '.html';
      document.body.append(a);
      a.click();
      a.remove();
      closePrint();
      return;
    }
    const r = await window.pywebview.api.save_export(dlg.tab.id, dlg.path, dlg.token, 'html');
    if (r?.error) setBusy(r.error, true);
    else if (r?.path) {
      closePrint();
      toast(t('html 로 저장했습니다: {path}', { path: r.path }), '', 5000);
    }
  } catch (e) {
    setBusy(t('html 을 만들지 못했습니다: {error}', { error: e?.message || String(e) }), true);
  } finally {
    if (dlg) dlg.busy = false;
  }
}

/** 'Word로 저장…': 만든 docx 를 저장 대화상자에서 고른 곳에 그대로 (D146). 브라우저 개발 모드는 내려받기 */
async function saveDocx() {
  if (!dlg?.token || dlg.busy || dlg.format !== 'docx') return;
  dlg.busy = true;
  try {
    if (!native.has('save_export')) {
      const a = document.createElement('a');
      a.href = `/export-file/${dlg.token}.docx`;
      a.download = basename(dlg.path).replace(/\.[^.]+$/, '') + '.docx';
      document.body.append(a);
      a.click();
      a.remove();
      closePrint();
      return;
    }
    const r = await window.pywebview.api.save_export(dlg.tab.id, dlg.path, dlg.token, 'docx');
    if (r?.error) setBusy(r.error, true);
    else if (r?.path) {
      closePrint();
      toast(t('Word 로 저장했습니다: {path}', { path: r.path }), '', 5000);
    }
  } catch (e) {
    setBusy(t('Word 파일을 만들지 못했습니다: {why}', { why: e?.message || String(e) }), true);
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

/**
 * 탭 막대의 [인쇄] (D135): 창 모드의 md 문서(Lectern 슬라이드 포함)면 내보내기 창을 인쇄가 기본 단추로 연다.
 * html 문서·브라우저 개발 모드는 인쇄 창, 문서가 아니면(폴더 개요·코드·자료) 까닭을 알린다
 */
export function printButton() {
  if (canSavePdf()) {
    openPrint('print');
    return;
  }
  const cur = S.pane?.current;
  if (cur?.type === 'doc') {   // html 문서·브라우저 개발 모드의 md 문서 — 인쇄 창
    printDoc();
    return;
  }
  toast(t('문서를 볼 때 인쇄할 수 있습니다 — 왼쪽에서 문서를 여세요'));
}

/** 인쇄·PDF 글꼴을 문서 루트에 (print.css 가 :root[data-print-font] 로 고른다) */
export function applyPrintFont() {
  document.documentElement.dataset.printFont = printFont();
}

export function initPrint() {
  applyPrintFont();
  on('print-font', applyPrintFont);   // 설정 창·내보내기 창에서 바꿀 때
  addEventListener('beforeprint', () => { if (!dlg) preparePage(); });   // 다른 길로 연 인쇄 창도 같은 머리로 (창에서는 이미 적었다)
  box().addEventListener('change', onOption);
  box().addEventListener('click', (e) => { if (e.target === box()) closePrint(); });   // 바깥을 누르면 닫기
  $('#lec-print-close').addEventListener('click', closePrint);
  $('#lec-print-save').addEventListener('click', save);
  $('#lec-print-paper').addEventListener('click', paper);
  $('#lec-print-html').addEventListener('click', saveHtml);
  $('#lec-print-docx').addEventListener('click', saveDocx);
  $('#lec-pp-docx').addEventListener('change', (e) => {   // 양식은 문서에 적지 않는다 — 문서의 맨 앞 설정 docxStyle 이 처음 값
    if (!dlg) return;
    dlg.docx = /** @type {HTMLSelectElement} */ (e.target).value;
    remake();
  });
  $('#lec-pp-docx-folder').addEventListener('click', async () => {   // Word 양식 보관소 (없으면 빈 폴더를 만든다)
    try {
      await postJSON('/api/docx-styles/folder', {});
    } catch (e) {
      toast(e.message);
    }
  });
  $('#lec-pp-layout').addEventListener('change', (e) => {   // 틀은 문서에 적지 않는다 — 문서의 맨 앞 설정 layout 이 처음 값
    if (!dlg) return;
    dlg.layout = /** @type {HTMLSelectElement} */ (e.target).value;
    showLayout();
    remake();
  });
  $('#lec-pp-layout-sample').addEventListener('click', async () => {   // 비어 있는 맨 앞 설정의 견본 — 문서 맨 앞에 붙여 채운다
    const info = dlg?.layouts.find((l) => l.id === dlg.layout);
    if (!info) return;
    toast(await copyText(fieldSample(info, fieldsOf(dlg.pane))) ? t('맨 앞 설정 견본을 복사했습니다 — 문서 맨 앞에 붙여 값을 채우세요') : t('복사하지 못했습니다'));
  });
  $('#lec-btn-print').addEventListener('click', printButton);   // 탭 막대의 [인쇄] (D135)
  // 미리보기(PDF 보기)를 누르면 초점이 그 안으로 들어가 Esc 가 오지 않는다 — 마우스가 나가면 창으로 되돌린다
  $('#lec-print .print-preview').addEventListener('mouseleave', () => {
    if (dlg && document.activeElement === $('#lec-print-frame')) $('#lec-print .print-box').focus();
  });
  on('tab', () => closePrint());
  // 창을 연 사이 문서가 다시 그려지면(Claude 가 고침) 미리보기도 다시 — 옛 미리보기를 저장하지 않게
  on('rendered', (pane) => { if (dlg && pane === dlg.pane) remake(); });
}
