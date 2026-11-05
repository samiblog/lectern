// 사용설명서(F1)와 단축키 표(툴바 '?' 버튼, Ctrl+/) — D45.
// 설명서는 web/help/manual.md 를 처음 열 때 받아 문서처럼 그린다 (지금 문서 스타일·글자 크기). 터미널 모음처럼 사이드바와 문서 화면 위를
// 덮고, 왼쪽에 장 목록(읽는 곳 표시), Ctrl+F 는 설명서 안에서 찾는다. 다른 화면으로 가면(문서 열기·프로젝트 탭·터미널) 닫힌다.
// 단축키 표와 설명서의 '단축키' 장은 같은 SHORTCUTS 로 만든다 — 단축키를 더하면 여기에 넣는다.

import { on } from './store.js';
import { renderMarkdown } from './markdown.js';
import { decorateBlocks } from './doc.js';
import { setFindTarget } from './find.js';
import { esc, html, raw, setHtml } from './html.js';
import { $, $$, findAnchor } from './util.js';
import { LANG, t } from './i18n.js';

/** [묶음, [[키, 하는 일]]]. 키: 'Ctrl+Shift+F' 처럼 + 로 잇고, 같은 일을 하는 다른 키는 ' / ' 로 나눈다 */
export const SHORTCUTS = [
  [t('열기·찾기'), [
    ['Ctrl+P', t('문서·코드 빠르게 열기 (이름·제목·경로로)')],
    ['Ctrl+F', t('지금 화면에서 찾기 — 문서·코드·사용설명서 (폴더 개요에서는 트리 거르기)')],
    ['Ctrl+Shift+F', t('모든 문서·코드에서 찾기 (사이드바 \'검색\')')],
    ['Ctrl+O', t('폴더 열기 — 새 탭으로')],
    ['Ctrl+N', t('새 문서 만들기 — 경로를 정하면 바로 만들어 새 문서 탭에서 편집')],
    ['Ctrl+G', t('줄로 가기 — 문서·코드 화면과 편집 모드')],
    ['F2', t('사이드바에서 고른 파일의 이름 바꾸기 (같은 폴더 안에서)')],
  ]],
  [t('프로젝트 탭'), [
    ['Ctrl+1~8', t('그 순번의 탭')],
    ['Ctrl+9', t('마지막 탭')],
    ['Alt+PageDown / Alt+PageUp', t('다음 / 이전 프로젝트 탭')],
    ['Ctrl+Shift+W', t('프로젝트 탭 닫기 (탭을 마우스 가운데 버튼으로 눌러도)')],
  ]],
  [t('문서 탭'), [
    [t('누르기'), t('사이드바 목록의 문서를 새 문서 탭에서 열기 — 이미 열려 있으면 그 탭으로')],
    [t('Ctrl+누르기 / 가운데 버튼'), t('보던 문서를 두고 뒤에서 새 문서 탭 — 트리·목록·링크·검색·모아 보기')],
    [t('Alt+누르기'), t('사이드바 목록의 문서를 지금 탭에서 열기')],
    ['Ctrl+T', t('새 문서 탭에 문서 열기')],
    ['Ctrl+Shift+T', t('닫은 문서 탭 다시 열기')],
    ['Ctrl+Tab / Ctrl+Shift+Tab', t('다음 / 이전 문서 탭 (Ctrl+PageDown / Ctrl+PageUp 도 됨)')],
    ['Alt+1~8', t('그 순번의 문서 탭')],
    ['Alt+9', t('마지막 문서 탭')],
    ['Ctrl+W', t('문서 탭 닫기 (Ctrl+F4, 탭을 마우스 가운데 버튼으로 눌러도)')],
  ]],
  [t('화면'), [
    ['Alt+← / Alt+→', t('뒤로 / 앞으로 — 같은 문서 안에서 뛴 자리도 (마우스의 뒤로·앞으로 버튼도)')],
    ['Ctrl+B', t('사이드바 보이기·숨기기')],
    ['Alt+L', t('Markdown 문서의 줄 번호 보이기·감추기')],
    ['Alt+H', t('장 하이라이트 켜기·끄기')],
    ['Alt+M', t('이 프로젝트의 메모 열기·닫기')],
    ['Ctrl+= / Ctrl+- / Ctrl+0', t('문서 글자 키우기 / 줄이기 / 100%')],
    ['F5', t('다시 불러오기 (지금 탭의 트리와 화면)')],
    [t('Ctrl+휠'), t('앱 화면 전체 확대·축소 (문서 글자만은 툴바의 − +)')],
    ['Shift+F10', t('초점이 있는 곳이나 현재 줄의 우클릭 메뉴')],
    ['Esc', t('팝업·메뉴·찾기·사용설명서 닫기, 그다음 하이라이트 끄기')],
  ]],
  [t('현재 위치·하이라이트 (문서·코드 화면)'), [
    ['↑ / ↓', t('현재 위치를 위 / 아래 줄로 — 화면이 따라감 (장 하이라이트 중에는 앞 장 / 다음 장)')],
    [t('Shift+누르기 / Shift+끌기'), t('그 줄들을 하이라이트 — 하이라이트가 있으면 거기까지 넓히기')],
    ['Shift+Enter', t('현재 줄 하이라이트 켜기·끄기')],
    ['Ctrl+L', t('현재 줄 하이라이트 — 거듭 누르면 아래로 넓힘')],
    ['F2', t('현재 줄을 한 줄 편집 (한 줄만 하이라이트했으면 그 줄)')],
    [t('두 번 누르기'), t('본문의 그 줄을 한 줄 편집 — 누른 자리에 커서')],
    ['Shift+↑ / Shift+↓', t('하이라이트의 끝 줄을 위 / 아래로 — 넓히거나 줄이기')],
    ['Shift+→', t('하이라이트한 곳을 맨 앞 터미널(Claude Code)에 \'@경로 a~b행\' 으로 (Enter 는 누르지 않음, 초점은 문서에)')],
    ['Ctrl+Shift+→', t('위치를 맨 앞 터미널에 넣고 초점도 터미널로 (하이라이트가 없으면 현재 줄)')],
    ['Shift+←', t('하이라이트한 곳의 위치(@경로 a~b행) 복사')],
    ['Ctrl+C', t('하이라이트한 곳의 원문 복사 (고른 글이 없을 때)')],
    ['Alt+↑ / Alt+↓', t('하이라이트한 줄을 위 / 아래로 옮기기 — 목록은 하위 항목과 함께')],
    ['Delete', t('하이라이트한 줄 지우기')],
    ['Ctrl+X', t('하이라이트한 줄의 원문을 복사하고 지우기 (고른 글이 없을 때)')],
    ['PageUp / PageDown', t('앞 장 / 다음 장 (장 하이라이트 중)')],
    ['Ctrl+Z', t('한 줄 편집으로 저장한 줄을 고치기 전으로 (거듭 누르면 그 앞 것도)')],
    ['Ctrl+Y', t('되돌린 것을 다시 (거듭 누르면 그 뒤 것도)')],
  ]],
  [t('한 줄 편집 (F2 · 본문 두 번 누르기)'), [
    ['Enter', t('저장 — 원문 파일에 바로')],
    ['Esc', t('그만두기')],
    ['↑ / ↓', t('저장하고 위 / 아래 줄을 이어서 편집 (표는 같은 칸) — 글이 화면에서 꺾이면 맨 윗줄·맨 아랫줄에서')],
    ['Ctrl+Enter', t('아래에 새 줄 — 글 가운데서는 그 자리에서 두 줄로 나눔')],
    ['Ctrl+Shift+Enter', t('위에 새 줄')],
    ['Backspace', t('줄 맨 앞에서: 같은 종류의 윗줄과 합침')],
    ['Tab / Shift+Tab', t('목록 항목을 한 단계 안 / 밖으로, 표는 옆 / 앞 칸')],
    ['Alt+↑ / Alt+↓', t('이 줄을 위 / 아래로 옮기기 — 목록은 하위 항목과 함께')],
    ['Ctrl+Shift+K', t('이 줄 지우기')],
    ['Ctrl+Shift+D', t('이 줄 복제')],
  ]],
  [t('발표 문서 (marp: true)'), [
    ['Shift+F5', t('발표 — 지금 보는 슬라이드부터 창 전체에 한 장씩')],
    ['→ / ←', t('다음 / 이전 슬라이드 (Space·PageDown·↓ / PageUp·↑ 도, 발표 중)')],
    ['Home / End', t('첫 / 마지막 슬라이드 (발표 중)')],
    ['N', t('발표자 노트 보이기·감추기 (발표 중)')],
    ['F', t('전체 화면 켜기·끄기 (발표 중)')],
    ['Esc', t('발표 끝내기')],
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
    ['F3 / Shift+F3', t('다음 / 이전 찾기 (편집 모드 안)')],
    ['Esc', t('편집 닫기 (저장하지 않은 것이 있으면 물음)')],
  ]],
  [t('터미널'), [
    ['Ctrl+`', t('오른쪽 터미널 열기·닫기 (닫아도 셸은 계속 돎)')],
    ['F6 / Shift+F6', t('문서 ↔ 터미널로 초점 옮기기 (터미널 안에서도, 닫혀 있으면 열면서)')],
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
  setHtml($('#lec-keys-list'), SHORTCUTS.map(([group, rows]) => html`<section class="keys-group"><h3>${group}</h3>
    <table>${rows.map(([keys, what]) => html`<tr><th scope="row">${raw(keysHtml(keys))}</th><td>${what}</td></tr>`)}</table></section>`));
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
  const { html: markup } = renderMarkdown(text, { math: false });
  setHtml(view(), raw(window.DOMPurify.sanitize(markup)));
  decorateBlocks(view());
  heads = $$('h2, h3', view());
  setHtml($('#lec-help-toc'), heads.map((h, i) => [html`<li class="${h.tagName === 'H3' ? 'sub' : ''}">`, html`<a href="#" data-i="${i}">${h.textContent}</a></li>`]));
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
    setHtml(view(), html`<p>${t('사용설명서를 읽지 못했습니다 ({error}). Lectern 을 다시 설치하면 고쳐집니다.', { error: e.message })}</p>`);
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
