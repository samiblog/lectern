// 설정 창 (툴바 톱니 버튼, Ctrl+,): 화면에서 바꿀 수 있는 설정과 '설정 파일 열기'.
// 편집기 경로·제외 폴더처럼 API로 못 바꾸는 값은 설정 파일을 편집기로 열어 고친다 (서버가 저장된 파일을 다시 읽는다).

import { S, emit, on } from './store.js';
import { saveConfig, postJSON, getJSON } from './api.js';
import { fillPicker, grouping, userStyleInfo } from './theme.js';
import { confirmReload, hasUnsavedEdits } from './editor.js';
import { openSamples } from './tabs.js';
import { $, $$, toast, copyText } from './util.js';
import { html, setHtml } from './html.js';
import { t } from './i18n.js';
import { aiTool, aiInfo, aiName, aiCli, voicePrompt } from './aitool.js';
import { initAiSetup, refreshAiSetup, redrawAiSetup, guidePrompt, skillsPrompt, writingStylePrompt, chosenStyle } from './aisetup.js';
import { openStylePick } from './stylepick.js';
import { openRaw } from './rawview.js';

const box = () => $('#lec-settings');
const TERM_FONT_BASE = 14;   // 터미널 글자 크기의 기본 (D130 — terminal.js 의 TERM_FONT.base, config.py 의 기본값과 같게. 범위는 입력 칸의 min·max)

/** 터미널 글자 크기를 정해 저장하고 열린 터미널에 입힌다. 범위 밖이나 숫자가 아니면 가까운 값·지금 값으로 */
async function setTermFont(value) {
  const input = $('#lec-termfont');
  const [min, max] = [Number(input.min), Number(input.max)];
  const size = Number.isFinite(value) ? Math.min(max, Math.max(min, Math.round(value))) : (S.config.terminal_font_size || TERM_FONT_BASE);
  input.value = String(size);
  if (size === S.config.terminal_font_size) return;
  await saveConfig({ terminal_font_size: size });
  emit('term-font');
}

/** 고르는 칸들을 지금 설정에 맞춘다 (창을 열 때, 다른 창에서 설정이 바뀌었을 때 — D159) */
function fillControls() {
  for (const input of $$('#lec-settings input[data-key]')) input.checked = S.config[input.dataset.key] !== false;
  for (const radio of $$('#lec-settings input[name="theme_groups"]')) radio.checked = radio.value === grouping();
  for (const radio of $$('#lec-settings input[name="language"]')) radio.checked = radio.value === (S.config.language || 'auto');
  for (const radio of $$('#lec-settings input[name="terminal_position"]')) radio.checked = radio.value === (S.config.terminal_position || 'auto');
  for (const radio of $$('#lec-settings input[name="editor_keys"]')) radio.checked = radio.value === (S.config.editor_keys === 'vim' ? 'vim' : 'default');
  for (const radio of $$('#lec-settings input[name="print_font"]')) radio.checked = radio.value === (S.config.print_font === 'sans' ? 'sans' : 'serif');
  for (const radio of $$('#lec-settings input[name="table_align"]')) radio.checked = radio.value === (S.config.table_align === 'report' ? 'report' : 'auto');
  for (const radio of $$('#lec-settings input[name="ai_tool"]')) radio.checked = radio.value === aiTool();
  $('#lec-termfont').value = String(S.config.terminal_font_size || TERM_FONT_BASE);
}

/** 설정 창 (D154 — 왼쪽 분류, 오른쪽 절). section: 그 분류의 절에서 연다 — 없으면 마지막에 고른 분류 */
export function openSettings(section) {
  fillControls();
  renderMyStyles();
  emit('settings-open');   // 업무 관리 칸 (work.js, D124)
  $('#lec-aiguide-samples').hidden = !S.samples;
  renderValues();
  refreshAiSetup();   // AI 도구에 건네는 것의 넣을 곳·바뀌는 파일 (D159 — 지금 상태는 받는 대로 다시 그린다)
  segDescs();
  box().hidden = false;
  const sec = typeof section === 'string' && SECTIONS.includes(section) ? section : SECTIONS.includes(S.config.settings_section) ? S.config.settings_section : SECTIONS[0];
  goSection(sec, false);
  $(`#lec-settings .set-nav button[data-set="${sec}"]`)?.focus();
}

// ---- 분류 (D154) — 왼쪽 분류를 누르면 그 절로, 내리면 지금 절을 강조. 고르는 칸은 숨기지 않는다 -----------------

const SECTIONS = ['general', 'view', 'edit', 'print', 'term', 'ai', 'work', 'more'];
const content = () => $('#lec-set-content');

function setActive(sec) {
  for (const b of $$('#lec-settings .set-nav button')) b.classList.toggle('on', b.dataset.set === sec);
}

function goSection(sec, smooth = true) {
  const el = $(`#lec-settings .set-sec[data-set="${sec}"]`);
  if (!el) return;
  content().scrollTo({ top: el.offsetTop, behavior: smooth ? 'smooth' : 'auto' });
  setActive(sec);
}

/** 내린 자리의 절을 강조 — 맨 끝까지 내렸으면 마지막 절 */
function onScroll() {
  const c = content();
  let cur = SECTIONS[0];
  for (const el of $$('#lec-settings .set-sec')) if (el.offsetTop <= c.scrollTop + 24) cur = el.dataset.set;
  if (c.scrollTop + c.clientHeight >= c.scrollHeight - 2) cur = SECTIONS.at(-1);
  setActive(cur);
}

/** 고르기 묶음: 고른 것의 설명만 묶음 아래에 한 줄 (한 줄 단추 — 단추 안의 설명은 감춘다) */
function segDescs() {
  for (const group of $$('#lec-settings .opt-choice')) {
    let d = group.querySelector(':scope > .seg-desc');
    if (!d) {
      d = document.createElement('small');
      d.className = 'seg-desc';
      group.append(d);
    }
    d.textContent = group.querySelector('label:has(input:checked) small')?.textContent || '';
  }
}

/** 고급: 파일에서만 고치는 설정의 지금 값 (보기만) */
function renderValues() {
  const dl = $('#lec-set-values');
  if (!dl) return;
  const row = (name, value) => [html`<dt>${name}</dt>`, html`<dd>${value}</dd>`];
  setHtml(dl, [
    ...row(t('편집기 경로 (editor)'), S.config.editor || t('기본 — VS Code')),
    ...row(t('제외 폴더 (exclude_dirs)'), (S.config.exclude_dirs || []).join(', ') || t('없음')),
    ...row(t('터미널 셸 (terminal_shell)'), S.config.terminal_shell || t('기본 — Windows PowerShell')),
  ]);
}

// ---- 쓰는 AI 도구 (D138) ------------------------------------------------------------
// 화면의 이름과 요청 글이 고른 도구(aitool.js)를 따른다. index.html 의 그 글자들은 비워 두고 여기서 채운다 (도구를 바꾸면 다시).

/** 프로젝트의 지시 파일 이름 — 여럿이면 둘을 함께 */
const ruleFile = () => aiInfo()?.file ?? t('지시 파일(CLAUDE.md·AGENTS.md)');

// 다른 창이나 설정 파일에서 바뀐 설정 (D159 — api.js 의 followConfig). 이 창에도 입힌다 — 다시 불러와야 하는 것은 편집 중이면 알리기만
on('config-follow', (keys) => {
  if (keys.has('language') || keys.has('external_images')) {
    if (hasUnsavedEdits()) toast(t('다른 창에서 다시 불러와야 하는 설정을 바꿨습니다 — 편집을 저장한 뒤 F5 를 누르면 다시 불러옵니다'), '', 8000);
    else location.reload();
    return;
  }
  if (keys.has('math') || keys.has('md_breaks') || keys.has('table_align')) emit('refresh-view');
  if (keys.has('vi_keys')) emit('vi-keys');
  if (keys.has('editor_keys')) emit('editor-keys');
  if (keys.has('print_font')) emit('print-font');
  if (keys.has('terminal_follow_style')) emit('term-colors');
  if (keys.has('terminal_font_size')) emit('term-font');
  if (keys.has('terminal_position')) emit('term-place');
  if (keys.has('ai_tool')) {
    applyAiNames();
    emit('ai-tool');
  }
  if (box().hidden) return;
  fillControls();
  if (keys.has('ai_tool')) refreshAiSetup();
  else if (['ai_scope_guide', 'ai_scope_skills', 'ai_style_where', 'ai_style'].some((k) => keys.has(k))) redrawAiSetup();
  segDescs();
});

export function applyAiNames() {
  const ai = aiName();
  const cli = aiCli();
  const claude = aiTool() === 'claude';
  const text = (id, value) => { const el = $(id); if (el) el.textContent = value; };
  const tip = (id, value) => $(id)?.setAttribute('title', value);
  text('#lec-aiguide-title', t('{cli} 에 Lectern 알려 주기', { cli }));
  text('#lec-aiguide-desc', t('Lectern 에서 잘 보이는 문서를 쓰는 규칙을 적은 작성 안내가 있습니다. 요청 글을 {cli} 에 붙이면 안내를 읽고 고른 곳에 규칙을 정리합니다 — 모든 폴더면 개인 폴더에, 한 폴더면 그 폴더의 {file} 에 그 폴더의 읽는 사람·목적을', { cli, file: ruleFile() }));
  text('#lec-skills-desc', t("pptx 와 Lectern 슬라이드를 오가는 스킬 둘과 md 문서를 Word 로 만드는 스킬 하나가 들어 있습니다 (Claude Code·Codex·Antigravity·OpenCode 가 함께 쓰는 SKILL.md 형식). 요청 글을 {cli} 에 붙이면 설치할지 먼저 묻습니다. 쓰는 말은 사용설명서 'Lectern 슬라이드' 장의 'Claude 에게 시키기'와 예제 가이드 13 에 있습니다", { cli }));
  text('#lec-wstyle-desc', claude
    ? t("Claude Code 가 개발자가 아니라 그 글을 쓰는 실무자처럼 쓰게 하는 출력 스타일이 넷 들어 있습니다 — 리서치 글쓰기·업무 보고·학술 글·쉬운 설명. 모두 개발자·AI 글버릇을 빼고 다 쓴 뒤 다시 읽어 고칩니다. '스타일 고르기…'에서 견본을 보고 고르고, 고른 스타일의 파일을 개인 폴더에 두고 켜는 곳을 고릅니다. 요청 글을 Claude Code 에 붙이면 지금 상태를 알리고 물은 뒤 설치하고 켭니다")
    : t("개발자가 아니라 그 글을 쓰는 실무자처럼 쓰게 하는 글쓰기 규칙이 넷 들어 있습니다 — 리서치 글쓰기·업무 보고·학술 글·쉬운 설명. '스타일 고르기…'에서 견본을 보고 고르고, 요청 글을 {cli} 에 붙이면 고른 곳(개인 지시 파일이나 그 폴더의 AGENTS.md)에 넣을지 먼저 묻습니다 (Claude Code 는 출력 스타일로 설치합니다)", { cli }));
  text('#lec-voice-desc', t("내가 직접 쓴 글을 견본으로 {cli} 가 내 문체 노트를 만듭니다 — 용어·말투처럼 지킬 것, 즐겨 쓰는 방식, 따라 하지 않을 버릇(겹말·번역투 같은)을 나눠 적고, 글을 쓰거나 다듬을 때 참고합니다. 노트는 개인 폴더에 하나 두어 어느 폴더·스타일에서나 같은 노트를 씁니다. 요청 글 끝에 견본을 @경로로 이어 붙이거나, 문서 여백을 우클릭해 '내 문체 견본으로 보내기'를 고릅니다. 저장하기 전에 무엇을 찾았는지 먼저 보여 줍니다", { cli }));
  for (const id of ['#lec-aiguide-prompt', '#lec-skills-prompt', '#lec-wstyle-prompt', '#lec-voice-prompt', '#lec-mystyles-prompt', '#lec-layouts-prompt']) text(id, t('{cli}용 요청 복사', { cli }));
  tip('#lec-layouts-prompt', t('틀 작성 안내의 위치와 저장할 폴더를 적은 요청 글 — {cli} 에 붙여 넣고 원하는 양식을 이어서 적습니다', { cli }));
  tip('#lec-aiguide-prompt', t('작성 안내의 위치를 적은 요청 글 — 작업할 프로젝트의 {cli} 에 붙여 넣습니다', { cli }));
  tip('#lec-skills-prompt', t('스킬의 위치를 적은 요청 글 — {cli} 에 붙여 넣습니다', { cli }));
  tip('#lec-wstyle-prompt', t('글쓰기 스타일 파일의 위치를 적은 요청 글 — {cli} 에 붙여 넣습니다', { cli }));
  tip('#lec-voice-prompt', t('내 문체 안내의 위치를 적은 요청 글 — {cli} 에 붙여 넣고 견본을 @경로로 이어서 적습니다', { cli }));
  tip('#lec-mystyles-prompt', t('스타일 설명서의 위치와 저장할 폴더를 적은 요청 글 — {cli} 에 붙여 넣고 원하는 모양을 이어서 적습니다', { cli }));
  // 설정 창 밖의 단추들 (담기·템플릿·md 문서 스타일·pptx·html)
  text('#lec-basket-claude', t('{ai} 에 맡기기', { ai }));
  tip('#lec-basket-claude', t('담은 것의 위치로 새 문서를 만들어 달라는 {cli} 요청 글 — 복사·터미널', { cli }));
  text('#lec-gallery-ask', t('{ai} 에게 템플릿 요청', { ai }));
  text('#lec-mdstyle-request', t('{ai} 에게 스타일 요청', { ai }));
  text('#lec-pptx-ask', t('{ai} 에게 스타일 요청', { ai }));
  text('#lec-mdstyle-claude', t('머리글을 바꾸고 본문은 {ai} 에게 요청', { ai }));
  text('#lec-html-ask', t('{ai} 에게 배치 요청', { ai }));
}

// ---- 내 스타일 (D53) --------------------------------------------------------------

function renderMyStyles() {
  const { count } = userStyleInfo();
  $('#lec-mystyles-info').textContent = count
    ? t("내 스타일 {n}개 — 툴바 스타일 목록 맨 아래 '내 스타일'에 있습니다. 파일을 고치면 바로 반영됩니다", { n: count })
    : t("CSS 파일 하나가 스타일 하나입니다. 스타일 폴더에 저장하면 툴바 스타일 목록 맨 아래 '내 스타일'에 나오고, 고치면 바로 반영됩니다");
}

/** AI 도구에 줄 요청 글: 설명서 위치와 저장할 폴더 (원하는 모양은 사용자가 이어서 적는다) */
function stylePrompt() {
  const { dir, guide } = userStyleInfo();
  return t('Lectern 의 내 스타일(CSS)을 만들어 줘. 먼저 설명서 {guide} 를 읽고, 그 규칙대로 {dir} 폴더에 CSS 파일 하나로 저장해. 원하는 모양: ',
    { guide, dir });
}

// ---- 지면 틀 (D145) --------------------------------------------------------------

/** AI 도구에 줄 요청 글: 틀 작성 안내·앱의 틀·저장할 폴더 (원하는 양식은 사용자가 이어서 적는다) */
async function layoutPrompt() {
  const r = await getJSON('/api/layouts');
  return t('Lectern 의 지면 틀(PDF·html 내보내기 양식)을 만들어 줘. 먼저 작성 안내 {guide} 를 읽고, 그 규칙대로 {dir} 폴더에 html 파일 하나로 저장해. 앱에 든 틀은 {builtin} 에 있으니 비슷한 것을 참고해. 원하는 양식: ',
    { guide: r.guide, dir: r.dir, builtin: r.builtin });
}

async function openLayoutsFolder() {
  try {
    const r = await postJSON('/api/layouts/folder', {});
    toast(t('틀 폴더를 열었습니다: {path}', { path: r.path }));
  } catch (e) {
    toast(t('틀 폴더를 열지 못했습니다: {error}', { error: e.message }), 'error');
  }
}

async function openStylesFolder() {
  try {
    const r = await postJSON('/api/styles/folder', {});
    toast(t('스타일 폴더를 열었습니다: {path}', { path: r.path }));
  } catch (e) {
    toast(t('스타일 폴더를 열지 못했습니다: {error}', { error: e.message }), 'error');
  }
}

export function closeSettings() {
  if (box().hidden) return false;
  box().hidden = true;
  return true;
}

async function onChange(e) {
  if (e.target.name === 'language') {   // 화면 언어 (D46): 서버가 index.html 에 넣는 언어가 바뀌므로 다시 불러온다 (열린 탭·터미널 셸은 그대로)
    if (!confirmReload()) {   // 저장하지 않은 편집 (D54)
      openSettings();   // 고른 것을 되돌린다
      return;
    }
    await saveConfig({ language: e.target.value });
    location.reload();
    return;
  }
  if (e.target.name === 'editor_keys') {   // 전체 편집 방식 (D122 — editor.js 의 vim 키맵, 열린 편집기에도)
    await saveConfig({ editor_keys: e.target.value });
    emit('editor-keys');
    return;
  }
  if (e.target.name === 'ai_tool') {   // 쓰는 AI 도구 (D138 — aitool.js): 화면의 이름과 요청 글
    const saving = saveConfig({ ai_tool: e.target.value });   // S.config 는 바로 바뀐다 — 이름부터 고친다
    applyAiNames();
    refreshAiSetup();   // 도구마다 자리가 다르다 (D159)
    emit('ai-tool');
    await saving;
    return;
  }
  if (e.target.name === 'table_align') {   // 표 칸 맞춤 (D174 — doc.js 가 그릴 때 표에 단다) — 문서를 다시 그린다
    await saveConfig({ table_align: e.target.value });
    emit('refresh-view');
    return;
  }
  if (e.target.name === 'print_font') {   // 인쇄·PDF 글꼴 (D131 — printdoc.js, print.css)
    await saveConfig({ print_font: e.target.value });
    emit('print-font');
    return;
  }
  if (e.target.name === 'terminal_position') {   // 터미널 자리 (D52 — terminal.js)
    await saveConfig({ terminal_position: e.target.value });
    emit('term-place');
    return;
  }
  if (e.target.id === 'lec-termfont') {   // 터미널 글자 크기 (D130 — terminal.js, 열린 터미널에도)
    await setTermFont(parseFloat(e.target.value));
    return;
  }
  if (e.target.name === 'theme_groups') {   // 스타일 목록을 묶는 방식만 바뀐다 (고른 스타일은 그대로)
    await saveConfig({ theme_groups: e.target.value });
    fillPicker();
    return;
  }
  const key = e.target.dataset.key;
  if (!key) return;
  if (key === 'external_images' && !confirmReload()) {   // 다시 불러오는 설정 — 저장하지 않은 편집 (D54)
    e.target.checked = !e.target.checked;
    return;
  }
  await saveConfig({ [key]: e.target.checked });
  if (key === 'md_breaks') emit('refresh-view');   // 문서를 새 규칙으로 다시 그린다 (D93)
  if (key === 'vi_keys') emit('vi-keys');   // 상태줄의 vi 표시 (D122 — 읽는 화면만. 전체 편집기는 editor_keys)
  if (key === 'external_images') location.reload();   // 그림 출처를 막는 CSP(img-src)가 바뀌므로 페이지를 다시 불러온다
  else if (key === 'math') emit('refresh-view');
  else if (key === 'terminal_follow_style') emit('term-colors');
}

const OPENED = {
  editor: t('편집기에서 설정 파일을 열었습니다. 저장하면 반영됩니다'),
  default: t('설정 파일을 열었습니다'),
  reveal: t('편집기를 찾지 못해 탐색기에서 설정 파일을 보여 줍니다'),
};

async function openConfigFile() {
  try {
    const r = await postJSON('/api/open-config', {});
    toast(OPENED[r.action] || t('열었습니다: {path}', { path: r.path }));
  } catch (e) {
    toast(t('설정 파일을 열지 못했습니다: {error}', { error: e.message }), 'error');
  }
}

// ---- 요청 글의 ▣ (D180) --------------------------------------------------------------
// 요청 글을 터미널에 붙여 넣는다 (D51 — Enter 없이). 받는 터미널은 마지막에 쓴 것(탭의 고른 터미널 — 누르거나 초점이 간 것)이고,
// 숫자 키(1~5)를 누른 채 누르면 그 번호의 터미널 (D137 — 메뉴의 숫자+누르기와 같게). 고른 AI 도구가 1번이 아닌 터미널에 떠 있어도 그리로 간다.
// 글을 쓰는 칸에 초점이 있으면 숫자는 그 칸의 글이다.

let heldTerm = null;
const TERM_BUTTONS = '#lec-settings button[id$="-term"]';

function setHeldTerm(n) {
  heldTerm = n;
  for (const b of $$(TERM_BUTTONS)) {
    b.classList.toggle('term-held', n != null);
    if (n != null) b.dataset.held = String(n + 1);
    else delete b.dataset.held;
  }
}

const typing = (el) => !!el?.closest?.('input, textarea, select, [contenteditable="true"], [contenteditable="plaintext-only"]');
const digitOf = (e) => (/^(?:Digit|Numpad)[1-5]$/.test(e.code) ? Number(e.code.at(-1)) - 1 : null);

/** ▣ 단추 하나: make() 가 지은 요청 글을 받는 터미널에. 누를 때의 번호를 먼저 잡는다 (글을 짓는 사이에 키를 뗄 수 있다) */
function termButton(sel, make) {
  $(sel).addEventListener('click', async () => {
    const n = heldTerm ?? S.tab?.term?.n ?? null;
    const text = await make();
    closeSettings();
    emit('term-paste', n == null ? text : { text, n });
  });
}

function bindHeldTerm() {
  document.addEventListener('keydown', (e) => {
    if ($('#lec-settings').hidden || e.ctrlKey || e.altKey || e.metaKey || digitOf(e) == null || typing(e.target)) return;
    e.preventDefault();
    if (!e.repeat) setHeldTerm(digitOf(e));
  }, true);
  document.addEventListener('keyup', (e) => { if (heldTerm != null && digitOf(e) === heldTerm) setHeldTerm(null); }, true);
  window.addEventListener('blur', () => setHeldTerm(null));
}

export function initSettings() {
  bindHeldTerm();   // ▣ 에 숫자 키 (D180)
  $('#lec-settings .set-nav')?.addEventListener('click', (e) => {   // 분류 (D154)
    const b = e.target.closest('button[data-set]');
    if (!b) return;
    goSection(b.dataset.set);
    saveConfig({ settings_section: b.dataset.set });
  });
  $('#lec-settings .set-nav')?.addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const all = $$('#lec-settings .set-nav button');
    const next = all[(all.indexOf(document.activeElement) + (e.key === 'ArrowDown' ? 1 : -1) + all.length) % all.length];
    next.focus();
    next.click();
  });
  content()?.addEventListener('scroll', onScroll, { passive: true });
  box().addEventListener('change', segDescs);
  on('open-settings', (sec) => openSettings(sec));   // 관련 화면에서 그 분류로 (D154 — 터미널 머리줄·스타일 목록·업무 현황·vi 표시·내보내기 창)
  applyAiNames();   // 고른 AI 도구의 이름으로 (D138)
  initAiSetup();   // 넣을 곳 고르기 (D159)
  $('#lec-mystyles-folder').addEventListener('click', openStylesFolder);
  $('#lec-layouts-folder').addEventListener('click', openLayoutsFolder);
  $('#lec-layouts-prompt').addEventListener('click', async () => {
    toast(await copyText(await layoutPrompt()) ? t('요청 글을 복사했습니다 — {cli} 에 붙여 넣고 원하는 양식을 이어서 적으세요', { cli: aiCli() }) : t('복사하지 못했습니다'));
  });
  termButton('#lec-layouts-term', layoutPrompt);
  $('#lec-termfont-down').addEventListener('click', () => setTermFont(Number($('#lec-termfont').value) - 1));
  $('#lec-termfont-up').addEventListener('click', () => setTermFont(Number($('#lec-termfont').value) + 1));
  $('#lec-termfont-reset').addEventListener('click', () => setTermFont(TERM_FONT_BASE));
  $('#lec-mystyles-prompt').addEventListener('click', async () => {
    toast(await copyText(stylePrompt()) ? t('요청 글을 복사했습니다 — {cli} 에 붙여 넣고 원하는 모양을 이어서 적으세요', { cli: aiCli() }) : t('복사하지 못했습니다'));
  });
  termButton('#lec-mystyles-term', stylePrompt);
  $('#lec-aiguide-prompt').addEventListener('click', async () => {
    toast(await copyText(guidePrompt()) ? t('요청 글을 복사했습니다 — 작업할 프로젝트의 {cli} 에 붙여 넣으세요', { cli: aiCli() }) : t('복사하지 못했습니다'));
  });
  termButton('#lec-aiguide-term', guidePrompt);
  $('#lec-skills-prompt').addEventListener('click', async () => {
    toast(await copyText(skillsPrompt()) ? t('요청 글을 복사했습니다 — {cli} 에 붙여 넣으세요', { cli: aiCli() }) : t('복사하지 못했습니다'));
  });
  termButton('#lec-skills-term', skillsPrompt);
  $('#lec-wstyle-prompt').addEventListener('click', async () => {
    toast(await copyText(writingStylePrompt()) ? t('요청 글을 복사했습니다 — {cli} 에 붙여 넣으세요', { cli: aiCli() }) : t('복사하지 못했습니다'));
  });
  termButton('#lec-wstyle-term', writingStylePrompt);
  $('#lec-voice-prompt').addEventListener('click', async () => {
    toast(await copyText(voicePrompt()) ? t('요청 글을 복사했습니다 — {cli} 에 붙여 넣고 견본을 @경로로 이어서 적으세요', { cli: aiCli() }) : t('복사하지 못했습니다'));
  });
  termButton('#lec-voice-term', voicePrompt);   // 견본은 사람이 이어서 적는다
  $('#lec-aiguide-samples').addEventListener('click', () => {
    closeSettings();
    openSamples();
  });
  on('user-styles', () => { if (!box().hidden) renderMyStyles(); });
  $('#lec-settings-ver').textContent = `Lectern ${document.querySelector('meta[name="lec-version"]')?.content || ''}`;
  box().addEventListener('change', onChange);
  box().addEventListener('click', (e) => { if (e.target === box()) closeSettings(); });   // 바깥을 누르면 닫기
  $('#lec-settings-close').addEventListener('click', closeSettings);
  $('#lec-settings-file').addEventListener('click', openConfigFile);
  // 원문 보기 (D160 — rawview.js): 설정 창 위에 연다. 여럿을 주면 있는 파일 가운데 앞의 것 (설치한 것 → Lectern 에 든 것)
  $('#lec-settings-raw').addEventListener('click', () => openRaw('config'));
  $('#lec-aiguide-raw').addEventListener('click', () => openRaw(['rules']));
  $('#lec-skills-raw').addEventListener('click', () => openRaw(['skill:pptx-to-lectern', 'pskill:pptx-to-lectern', 'lskill:pptx-to-lectern']));
  $('#lec-wstyle-raw').addEventListener('click', () => {   // 고른 스타일 — 설치한 것 → Lectern 에 든 것 (D161)
    const s = chosenStyle();
    openRaw(s.mine ? [`style:${s.mine}`] : [`style:${s.file}.md`, `style:${s.file}.en.md`, `lstyle:${s.id}`]);
  });
  $('#lec-wstyle-pick').addEventListener('click', openStylePick);   // 글쓰기 스타일 고르기 (D161)
  on('settings-redraw', () => { if (!box().hidden) { redrawAiSetup(); segDescs(); } });   // 고르기 창에서 고른 뒤
  on('close-settings', closeSettings);
  $('#lec-voice-raw').addEventListener('click', () => openRaw(['voice']));
  $('#lec-btn-settings').addEventListener('click', openSettings);
}
