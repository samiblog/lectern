// 사용설명서(F1)와 단축키 표(툴바 '?' 버튼, Ctrl+/) — D45.
// 설명서는 web/help/manual.md 를 처음 열 때 받아 문서처럼 그린다 (지금 문서 스타일·글자 크기). 터미널 모음처럼 사이드바와 문서 화면 위를
// 덮고, 왼쪽에 장 목록(읽는 곳 표시), Ctrl+F 는 설명서 안에서 찾는다. 다른 화면으로 가면(문서 열기·프로젝트 탭·터미널) 닫힌다.
// 단축키 표와 설명서의 '단축키' 장은 같은 SHORTCUTS 로 만든다 — 단축키를 더하면 여기에 넣는다.

import { on } from './store.js';
import { renderMarkdown } from './markdown.js';
import { decorateBlocks } from './doc.js';
import { setFindTarget } from './find.js';
import { $, $$, esc, findAnchor } from './util.js';
import { LANG, t } from './i18n.js';

/** [묶음, [[키, 하는 일]]]. 키: 'Ctrl+Shift+F' 처럼 + 로 잇고, 같은 일을 하는 다른 키는 ' / ' 로 나눈다 */
export const SHORTCUTS = [
  [t('열기·찾기'), [
    ['Ctrl+P', t('문서·코드 빠르게 열기 (이름·제목·경로로)')],
    ['Ctrl+F', t('지금 화면에서 찾기 — 문서·코드·사용설명서 (폴더 개요에서는 트리 거르기)')],
    ['Ctrl+Shift+F', t('모든 문서·코드에서 찾기 (사이드바 \'검색\')')],
    ['Ctrl+O', t('폴더 열기 — 새 탭으로')],
  ]],
  [t('프로젝트 탭'), [
    ['Ctrl+1~8', t('그 순번의 탭')],
    ['Ctrl+9', t('마지막 탭')],
    ['Ctrl+Tab / Ctrl+Shift+Tab', t('다음 / 이전 탭 (Ctrl+PageDown / Ctrl+PageUp 도 됨)')],
    ['Ctrl+W', t('탭 닫기 (탭을 마우스 가운데 버튼으로 눌러도)')],
  ]],
  [t('화면'), [
    ['Alt+← / Alt+→', t('뒤로 / 앞으로 (마우스의 뒤로·앞으로 버튼도)')],
    ['Ctrl+B', t('사이드바 보이기·숨기기')],
    ['F5', t('다시 불러오기 (지금 탭의 트리와 화면)')],
    [t('Ctrl+휠'), t('앱 화면 전체 확대·축소 (문서 글자만은 툴바의 − +)')],
    ['Esc', t('팝업·메뉴·찾기·사용설명서 닫기, 그다음 장 하이라이트 끄기')],
  ]],
  [t('장 하이라이트 (켜져 있을 때)'), [
    ['↑ / ↓', t('앞 장 / 다음 장')],
    ['PageUp / PageDown', t('앞 장 / 다음 장')],
  ]],
  [t('찾기 막대'), [
    ['Enter / Shift+Enter', t('다음 / 이전 결과')],
    ['Esc', t('찾기 닫기')],
  ]],
  [t('사이드바 \'코드\'·\'자료\' 목록'), [
    ['↑ / ↓', t('위 / 아래 항목')],
    ['→ / ←', t('폴더 펼치기 / 접기')],
    ['Enter', t('열기 (코드는 읽기 화면으로)')],
    [t('글자'), t('그 글자로 시작하는 항목으로 (같은 글자를 거듭 치면 다음 항목)')],
  ]],
  [t('편집 모드'), [
    ['Ctrl+E', t('보고 있는 문서·코드를 편집 모드로 열기·닫기')],
    ['Ctrl+S', t('저장 (편집 모드 안)')],
    ['Ctrl+F / Ctrl+H', t('찾기 / 바꾸기 (편집 모드 안)')],
    ['Alt+G', t('줄로 가기 (편집 모드 안)')],
    ['Esc', t('편집 닫기 (저장하지 않은 것이 있으면 물음)')],
  ]],
  [t('터미널'), [
    ['Ctrl+`', t('오른쪽 터미널 열기·닫기 (닫아도 셸은 계속 돎)')],
    ['Ctrl+Shift+`', t('터미널 모음 열기·닫기 (모음 안에서 Ctrl+Tab 은 다음 칸)')],
    ['Ctrl+C', t('고른 글 복사 (고른 글이 없으면 실행 중인 명령 멈춤)')],
    ['Ctrl+V', t('붙여 넣기')],
  ]],
  [t('도움말·설정'), [
    ['F1', t('사용설명서 열기·닫기')],
    ['Ctrl+/', t('단축키 표 열기·닫기')],
    ['Ctrl+,', t('설정 창')],
  ]],
];

// 백틱은 문자 참조로 — 설명서(Markdown) 표 안에서 코드 표시로 읽히지 않게
const cap = (k) => `<kbd>${esc(k).replace(/`/g, '&#96;')}</kbd>`;
/** 'Ctrl+Tab / Ctrl+Shift+Tab' → <kbd>Ctrl</kbd>+<kbd>Tab</kbd> / … (조합마다 줄바꿈하지 않는 묶음) */
const keysHtml = (keys) => keys.split(' / ').map((combo) => `<span class="combo">${combo.split('+').map(cap).join('+')}</span>`).join(' / ');

/** 설명서의 '단축키' 장에 넣을 Markdown (묶음마다 표 하나) */
function shortcutsMarkdown() {
  return SHORTCUTS.map(([group, rows]) => `### ${group}\n\n| ${t('키')} | ${t('하는 일')} |\n|---|---|\n`
    + rows.map(([keys, what]) => `| ${keysHtml(keys)} | ${esc(what)} |`).join('\n')).join('\n\n');
}

// ---- 단축키 표 ------------------------------------------------------------------

const keysBox = () => $('#lec-keys');

export function openShortcuts() {
  keysBox().hidden = false;
  $('#lec-keys-close').focus();
}

export function closeShortcuts() {
  if (keysBox().hidden) return false;
  keysBox().hidden = true;
  return true;
}

export const toggleShortcuts = () => (closeShortcuts() || openShortcuts());

function renderShortcuts() {
  $('#lec-keys-list').innerHTML = SHORTCUTS.map(([group, rows]) => `<section class="keys-group"><h3>${esc(group)}</h3>
    <table>${rows.map(([keys, what]) => `<tr><th scope="row">${keysHtml(keys)}</th><td>${esc(what)}</td></tr>`).join('')}</table></section>`).join('');
}

// ---- 사용설명서 -----------------------------------------------------------------

const helpBox = () => $('#lec-help');
const scroller = () => $('#lec-help-scroll');
const view = () => $('#lec-help-view');
let loaded = null;    // 설명서를 받아 그리는 중·그린 것 (Promise) — 처음 열 때 한 번
let heads = [];       // 장 목록의 제목 (h2·h3)

export const manualOpen = () => !helpBox().hidden;

async function loadManual() {
  const r = await fetch(LANG === 'en' ? '/static/help/manual.en.md' : '/static/help/manual.md');   // 영어판 (D46)
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const text = (await r.text()).replace('<!-- 단축키 표 -->', shortcutsMarkdown());   // i18n-ok (두 설명서에 같은 자리 표시)
  const { html } = renderMarkdown(text, { math: false });
  view().innerHTML = window.DOMPurify.sanitize(html);
  decorateBlocks(view());
  heads = $$('h2, h3', view());
  $('#lec-help-toc').innerHTML = heads.map((h, i) => `<li class="${h.tagName === 'H3' ? 'sub' : ''}">`
    + `<a href="#" data-i="${i}">${esc(h.textContent)}</a></li>`).join('');
  markCurrent();
}

/** 제목으로 (위에 조금 띄워서) */
function scrollToHead(h) {
  const box = scroller();
  box.scrollTop += h.getBoundingClientRect().top - box.getBoundingClientRect().top - 16;
}

/** 장 목록에 지금 읽는 곳 표시 */
function markCurrent() {
  const top = scroller().getBoundingClientRect().top + 80;
  let cur = 0;
  heads.forEach((h, i) => { if (h.getBoundingClientRect().top <= top) cur = i; });
  for (const a of $$('#lec-help-toc a')) {
    const on = Number(a.dataset.i) === cur;
    a.classList.toggle('active', on);
    if (on) a.scrollIntoView({ block: 'nearest' });
  }
}

export async function openManual() {
  closeShortcuts();
  helpBox().hidden = false;
  setFindTarget({ root: view(), scroller: scroller() });   // Ctrl+F 는 설명서 안에서
  scroller().focus({ preventScroll: true });               // 화살표·PageDown 으로 설명서를 넘기게
  loaded ??= loadManual().catch((e) => {
    loaded = null;   // 다음에 다시 시도
    view().innerHTML = `<p>${t('사용설명서를 읽지 못했습니다 ({error}). Lectern 을 다시 설치하면 고쳐집니다.', { error: esc(e.message) })}</p>`;
  });
  await loaded;
}

export function closeManual() {
  if (!manualOpen()) return false;
  helpBox().hidden = true;
  setFindTarget(null);   // 찾기 막대를 문서 화면으로 되돌린다
  $('#lec-content')?.focus({ preventScroll: true });
  return true;
}

export const toggleManual = () => (closeManual() || openManual());

export function initHelp() {
  renderShortcuts();
  $('#lec-help-ver').textContent = document.querySelector('meta[name="lec-version"]')?.content || '';
  $('#lec-btn-help').addEventListener('click', toggleShortcuts);
  $('#lec-keys-close').addEventListener('click', closeShortcuts);
  $('#lec-keys-manual').addEventListener('click', openManual);
  keysBox().addEventListener('click', (e) => { if (e.target === keysBox()) closeShortcuts(); });   // 바깥을 누르면 닫기
  $('#lec-help-close').addEventListener('click', closeManual);
  $('#lec-help-keys').addEventListener('click', openShortcuts);
  $('#lec-help-toc').addEventListener('click', (e) => {
    const a = e.target.closest('a[data-i]');
    if (!a) return;
    e.preventDefault();
    scrollToHead(heads[Number(a.dataset.i)]);
  });
  // 설명서 속 링크: 설명서 안의 제목(#…)으로만 간다 — 다른 주소로 가면 앱 창이 떠난다
  view().addEventListener('click', (e) => {
    const a = e.target.closest('a[href]');
    if (!a) return;
    e.preventDefault();
    const href = a.getAttribute('href');
    const target = href.startsWith('#') && findAnchor(view(), href);
    if (target) scrollToHead(target);
  });
  let ticking = false;
  scroller().addEventListener('scroll', () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => { ticking = false; markCurrent(); });
  });
  // 시작 화면(폴더를 열기 전)의 '사용설명서' 버튼
  $('#lec-panes').addEventListener('click', (e) => { if (e.target.closest('.welcome [data-act="help"]')) openManual(); });
  // 다른 화면으로 가면 닫는다: 문서·개요·코드를 열거나 다른 탭을 고름(view), 프로젝트 탭·목차·터미널·터미널 모음 버튼
  on('view', closeManual);
  const away = (e) => { if (e.target.closest('.lec-tab, .tabbar-btn, #lec-btn-gather') && !e.target.closest('.tab-close')) closeManual(); };
  $('#lec-tabbar').addEventListener('click', away, true);
  $('#lec-btn-gather').addEventListener('click', away, true);
}
