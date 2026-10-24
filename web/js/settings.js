// 설정 창 (툴바 톱니 버튼, Ctrl+,): 화면에서 바꿀 수 있는 설정과 '설정 파일 열기'.
// 편집기 경로·제외 폴더처럼 API로 못 바꾸는 값은 설정 파일을 편집기로 열어 고친다 (서버가 저장된 파일을 다시 읽는다).

import { S, emit, on } from './store.js';
import { saveConfig, postJSON } from './api.js';
import { fillPicker, grouping, userStyleInfo } from './theme.js';
import { confirmReload } from './editor.js';
import { $, $$, toast, copyText } from './util.js';
import { t } from './i18n.js';

const box = () => $('#lec-settings');

export function openSettings() {
  for (const input of $$('#lec-settings input[data-key]')) input.checked = S.config[input.dataset.key] !== false;
  for (const radio of $$('#lec-settings input[name="theme_groups"]')) radio.checked = radio.value === grouping();
  for (const radio of $$('#lec-settings input[name="language"]')) radio.checked = radio.value === (S.config.language || 'auto');
  for (const radio of $$('#lec-settings input[name="terminal_position"]')) radio.checked = radio.value === (S.config.terminal_position || 'auto');
  renderMyStyles();
  box().hidden = false;
  $('#lec-settings input')?.focus();
}

// ---- 내 스타일 (D53) --------------------------------------------------------------

function renderMyStyles() {
  const { count } = userStyleInfo();
  $('#lec-mystyles-info').textContent = count
    ? t("내 스타일 {n}개 — 툴바 스타일 목록 맨 아래 '내 스타일'에 있습니다. 파일을 고치면 바로 반영됩니다", { n: count })
    : t("CSS 파일 하나가 스타일 하나입니다. 스타일 폴더에 저장하면 툴바 스타일 목록 맨 아래 '내 스타일'에 나오고, 고치면 바로 반영됩니다");
}

/** Claude Code 에 줄 요청 글: 설명서 위치와 저장할 폴더 (원하는 모양은 사용자가 이어서 적는다) */
function stylePrompt() {
  const { dir, guide } = userStyleInfo();
  return t('Lectern 문서 뷰어의 내 스타일(CSS)을 만들어 줘. 먼저 설명서 {guide} 를 읽고, 그 규칙대로 {dir} 폴더에 CSS 파일 하나로 저장해. 원하는 모양: ',
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
  if (e.target.name === 'terminal_position') {   // 터미널 자리 (D52 — terminal.js)
    await saveConfig({ terminal_position: e.target.value });
    emit('term-place');
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
  $('#lec-mystyles-folder').addEventListener('click', openStylesFolder);
  $('#lec-mystyles-prompt').addEventListener('click', async () => {
    toast(await copyText(stylePrompt()) ? t('요청 글을 복사했습니다 — Claude Code 에 붙여 넣고 원하는 모양을 이어서 적으세요') : t('복사하지 못했습니다'));
  });
  $('#lec-mystyles-term').addEventListener('click', () => {
    closeSettings();
    emit('term-paste', stylePrompt());   // 터미널에 붙여 넣기 (D51 — Enter 없이)
  });
  on('user-styles', () => { if (!box().hidden) renderMyStyles(); });
  $('#lec-settings-ver').textContent = `Lectern ${document.querySelector('meta[name="lec-version"]')?.content || ''}`;
  box().addEventListener('change', onChange);
  box().addEventListener('click', (e) => { if (e.target === box()) closeSettings(); });   // 바깥을 누르면 닫기
  $('#lec-settings-close').addEventListener('click', closeSettings);
  $('#lec-settings-file').addEventListener('click', openConfigFile);
  $('#lec-btn-settings').addEventListener('click', openSettings);
}
