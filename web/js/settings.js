// 설정 창 (툴바 톱니 버튼, Ctrl+,): 화면에서 바꿀 수 있는 설정과 '설정 파일 열기'.
// 편집기 경로·제외 폴더처럼 API로 못 바꾸는 값은 설정 파일을 편집기로 열어 고친다 (서버가 저장된 파일을 다시 읽는다).

import { S, emit, on } from './store.js';
import { saveConfig, postJSON } from './api.js';
import { fillPicker, grouping, userStyleInfo } from './theme.js';
import { confirmReload } from './editor.js';
import { openSamples } from './tabs.js';
import { $, $$, toast, copyText } from './util.js';
import { t } from './i18n.js';
import { aiTool, aiInfo, aiName, aiCli } from './aitool.js';

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

export function openSettings() {
  for (const input of $$('#lec-settings input[data-key]')) input.checked = S.config[input.dataset.key] !== false;
  for (const radio of $$('#lec-settings input[name="theme_groups"]')) radio.checked = radio.value === grouping();
  for (const radio of $$('#lec-settings input[name="language"]')) radio.checked = radio.value === (S.config.language || 'auto');
  for (const radio of $$('#lec-settings input[name="terminal_position"]')) radio.checked = radio.value === (S.config.terminal_position || 'auto');
  for (const radio of $$('#lec-settings input[name="editor_keys"]')) radio.checked = radio.value === (S.config.editor_keys === 'vim' ? 'vim' : 'default');
  for (const radio of $$('#lec-settings input[name="print_font"]')) radio.checked = radio.value === (S.config.print_font === 'sans' ? 'sans' : 'serif');
  for (const radio of $$('#lec-settings input[name="ai_tool"]')) radio.checked = radio.value === aiTool();
  $('#lec-termfont').value = String(S.config.terminal_font_size || TERM_FONT_BASE);
  renderMyStyles();
  emit('settings-open');   // 업무 관리 칸 (work.js, D124)
  $('#lec-aiguide-samples').hidden = !S.samples;
  box().hidden = false;
  $('#lec-settings input')?.focus();
}

// ---- 쓰는 AI 도구 (D138) ------------------------------------------------------------
// 화면의 이름과 요청 글이 고른 도구(aitool.js)를 따른다. index.html 의 그 글자들은 비워 두고 여기서 채운다 (도구를 바꾸면 다시).

/** 프로젝트의 지시 파일 이름 — 여럿이면 둘을 함께 */
const ruleFile = () => aiInfo()?.file ?? t('지시 파일(CLAUDE.md·AGENTS.md)');

export function applyAiNames() {
  const ai = aiName();
  const cli = aiCli();
  const claude = aiTool() === 'claude';
  const text = (id, value) => { const el = $(id); if (el) el.textContent = value; };
  const tip = (id, value) => $(id)?.setAttribute('title', value);
  text('#lec-aiguide-title', t('{cli} 에 Lectern 알려 주기', { cli }));
  text('#lec-aiguide-desc', t('Lectern 에서 잘 보이는 문서를 쓰는 규칙을 적은 작성 안내가 있습니다. 요청 글을 {cli} 에 붙이면 안내를 읽고 그 프로젝트의 {file} 에 규칙을 정리합니다', { cli, file: ruleFile() }));
  text('#lec-skills-desc', t("pptx 와 Lectern 슬라이드를 오가는 스킬이 들어 있습니다 (Claude Code·Codex·Antigravity·OpenCode 가 함께 쓰는 SKILL.md 형식). 요청 글을 {cli} 에 붙이면 설치할지 먼저 묻습니다. 쓰는 말은 사용설명서 'Lectern 슬라이드' 장의 'Claude 에게 시키기'에 있습니다", { cli }));
  text('#lec-wstyle-desc', claude
    ? t('Claude Code 를 개발자가 아닌 리서치 동료·편집자로 바꾸는 출력 스타일이 들어 있습니다 — 읽는 사람을 먼저 정하고, 폴더 밖 자료와 웹으로 넓히고, 문단으로 쓰고 다시 읽어 고칩니다. 요청 글을 Claude Code 에 붙이면 설치할지 먼저 묻습니다. 설치한 뒤 보고서를 쓰는 폴더에서 /output-style 로 고르면 그 폴더에서만 씁니다')
    : t('개발자가 아닌 리서치 동료·편집자처럼 쓰게 하는 글쓰기 규칙이 들어 있습니다 — 읽는 사람을 먼저 정하고, 폴더 밖 자료와 웹으로 넓히고, 문단으로 쓰고 다시 읽어 고칩니다. 요청 글을 {cli} 에 붙이면 그 프로젝트의 AGENTS.md 에 넣을지 먼저 묻습니다 (Claude Code 는 출력 스타일로 설치합니다)', { cli }));
  for (const id of ['#lec-aiguide-prompt', '#lec-skills-prompt', '#lec-wstyle-prompt', '#lec-mystyles-prompt']) text(id, t('{cli}용 요청 복사', { cli }));
  tip('#lec-aiguide-prompt', t('작성 안내의 위치를 적은 요청 글 — 작업할 프로젝트의 {cli} 에 붙여 넣습니다', { cli }));
  tip('#lec-skills-prompt', t('스킬의 위치를 적은 요청 글 — {cli} 에 붙여 넣습니다', { cli }));
  tip('#lec-wstyle-prompt', t('글쓰기 스타일 파일의 위치를 적은 요청 글 — {cli} 에 붙여 넣습니다', { cli }));
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

// ---- AI 도구에 Lectern 알려 주기 (D57·D138) ----------------------------------------------

/** AI 도구에 줄 요청 글: 작성 안내(web/help/writing.md)를 읽고 그 프로젝트의 지시 파일(CLAUDE.md·AGENTS.md)에 규칙을 정리하게 */
function guidePrompt() {
  const one = aiInfo();
  const where = one
    ? t('이 프로젝트의 {file} 에 넣어 줘', { file: one.file })
    : t('이 프로젝트의 지시 파일에 넣어 줘 (Claude Code 는 CLAUDE.md, Codex·Antigravity·OpenCode 는 AGENTS.md — 둘 다 쓰는 프로젝트면 AGENTS.md 에 넣고 CLAUDE.md 에는 @AGENTS.md 한 줄만 둬)');
  return t("이 프로젝트의 문서는 사람이 Lectern(Markdown을 중심으로 AI와 함께 작업하는 통합 리서치 작업 환경)으로 읽고 그 자리에서 고쳐. 먼저 작성 안내 {guide} 를 읽고, 안내 끝의 '지시 파일에 넣을 요약'을 이 프로젝트에 맞게 다듬어 {where}. 이 프로젝트의 글을 누가 읽고 무엇에 쓰는지 모르면 나에게 물어서 형식 규칙보다 앞에 적어 줘. 앞으로 문서는 그 규칙대로 써.",
    { guide: S.writingGuide, where });
}

// ---- PowerPoint 스킬 (D98) -------------------------------------------------------

/** AI 도구에 줄 요청 글: 앱이 설치하지 않는다. 도구가 설명하고 물은 뒤 사용자가 허락하면 제 개인 스킬 폴더로 복사한다 (도구들이 같은 SKILL.md 형식) */
function skillsPrompt() {
  const one = aiInfo();
  const to = one
    ? t('두 폴더를 {dir}/ 로 복사해', { dir: one.skills })
    : t('두 폴더를 네 개인 스킬 폴더로 복사해 (Claude Code 는 ~/.claude/skills, Codex 는 ~/.codex/skills, Antigravity 는 ~/.gemini/config/skills, OpenCode 는 ~/.config/opencode/skills)');
  return t('Lectern 에 {cli} 스킬 두 개가 들어 있어: {dir} 의 pptx-to-lectern, lectern-to-pptx. 먼저 그 폴더의 README.md 를 읽고 무엇을 하는지 짧게 알려 준 뒤, 내 개인 스킬로 설치할지 나에게 물어봐. 내가 그렇다고 하면 {to}. 이미 있으면 바꿀지 다시 물어봐.',
    { cli: aiCli(), dir: S.skillsDir, to });
}

// ---- 글쓰기 스타일 (D132) -------------------------------------------------------

/** AI 도구에 줄 요청 글: 글쓰기 규칙(web/help/research-writing.md). 앱이 설치하지 않는다 — 도구가 설명하고 물은 뒤 사용자가 허락하면.
    Claude Code 는 출력 스타일로 ~/.claude/output-styles 에 (고르는 것은 사용자가 보고서 폴더에서 /output-style 로),
    출력 스타일이 없는 Codex·Antigravity·OpenCode 는 그 프로젝트의 AGENTS.md 에 '글쓰기' 절로 (D138) */
function writingStylePrompt() {
  const file = S.writingStyle;
  if (aiTool() === 'claude') {
    return t('Lectern 에 Claude Code 의 글쓰기용 출력 스타일이 들어 있어: {file}. 먼저 그 파일을 읽고 무엇이 바뀌는지 짧게 알려 준 뒤, 내 개인 출력 스타일로 설치할지 나에게 물어봐. 내가 그렇다고 하면 ~/.claude/output-styles/ 폴더에 같은 파일 이름으로 복사해 (폴더가 없으면 만들고, 같은 이름이 있으면 바꿀지 다시 물어봐). 설치한 뒤에는 Claude Code 를 다시 시작해야 읽는다는 것과, 보고서를 쓰는 폴더에서 /output-style 로 그 스타일을 고르면 그 폴더에서만 쓴다는 것을 알려 줘.', { file });
  }
  if (aiInfo()) {
    return t("Lectern 에 글쓰기 규칙이 들어 있어: {file} (Claude Code 의 출력 스타일 형식으로 쓴 파일이야). 먼저 그 파일을 읽고 무엇이 바뀌는지 짧게 알려 준 뒤, 이 프로젝트의 AGENTS.md 에 넣을지 나에게 물어봐. 내가 그렇다고 하면 맨 앞 설정(--- 사이)은 빼고 본문을 AGENTS.md 의 '글쓰기' 절로 넣어 (그 절이 이미 있으면 바꿀지 다시 물어봐). 그 뒤로 이 프로젝트의 글은 그 규칙대로 써.", { file });
  }
  return t("Lectern 에 글쓰기 규칙이 들어 있어: {file} (Claude Code 의 출력 스타일 형식으로 쓴 파일이야). 먼저 그 파일을 읽고 무엇이 바뀌는지 짧게 알려 줘. 네가 Claude Code 면 내 개인 출력 스타일로 설치할지 물어보고, 내가 그렇다고 하면 ~/.claude/output-styles/ 폴더에 같은 파일 이름으로 복사한 뒤 다시 시작해서 보고서를 쓰는 폴더에서 /output-style 로 고르라고 알려 줘. 다른 도구면 이 프로젝트의 AGENTS.md 에 넣을지 물어보고, 내가 그렇다고 하면 맨 앞 설정(--- 사이)은 빼고 본문을 AGENTS.md 의 '글쓰기' 절로 넣어 (그 절이 이미 있으면 바꿀지 다시 물어봐).", { file });
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
    emit('ai-tool');
    await saving;
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

export function initSettings() {
  applyAiNames();   // 고른 AI 도구의 이름으로 (D138)
  $('#lec-mystyles-folder').addEventListener('click', openStylesFolder);
  $('#lec-termfont-down').addEventListener('click', () => setTermFont(Number($('#lec-termfont').value) - 1));
  $('#lec-termfont-up').addEventListener('click', () => setTermFont(Number($('#lec-termfont').value) + 1));
  $('#lec-termfont-reset').addEventListener('click', () => setTermFont(TERM_FONT_BASE));
  $('#lec-mystyles-prompt').addEventListener('click', async () => {
    toast(await copyText(stylePrompt()) ? t('요청 글을 복사했습니다 — {cli} 에 붙여 넣고 원하는 모양을 이어서 적으세요', { cli: aiCli() }) : t('복사하지 못했습니다'));
  });
  $('#lec-mystyles-term').addEventListener('click', () => {
    closeSettings();
    emit('term-paste', stylePrompt());   // 터미널에 붙여 넣기 (D51 — Enter 없이)
  });
  $('#lec-aiguide-prompt').addEventListener('click', async () => {
    toast(await copyText(guidePrompt()) ? t('요청 글을 복사했습니다 — 작업할 프로젝트의 {cli} 에 붙여 넣으세요', { cli: aiCli() }) : t('복사하지 못했습니다'));
  });
  $('#lec-aiguide-term').addEventListener('click', () => {
    closeSettings();
    emit('term-paste', guidePrompt());   // 지금 탭의 터미널에 붙여 넣기 (D51 — Enter 없이)
  });
  $('#lec-skills-prompt').addEventListener('click', async () => {
    toast(await copyText(skillsPrompt()) ? t('요청 글을 복사했습니다 — {cli} 에 붙여 넣으세요', { cli: aiCli() }) : t('복사하지 못했습니다'));
  });
  $('#lec-skills-term').addEventListener('click', () => {
    closeSettings();
    emit('term-paste', skillsPrompt());   // 터미널에 붙여 넣기 (D51 — Enter 없이)
  });
  $('#lec-wstyle-prompt').addEventListener('click', async () => {
    toast(await copyText(writingStylePrompt()) ? t('요청 글을 복사했습니다 — {cli} 에 붙여 넣으세요', { cli: aiCli() }) : t('복사하지 못했습니다'));
  });
  $('#lec-wstyle-term').addEventListener('click', () => {
    closeSettings();
    emit('term-paste', writingStylePrompt());   // 터미널에 붙여 넣기 (D51 — Enter 없이)
  });
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
  $('#lec-btn-settings').addEventListener('click', openSettings);
}
