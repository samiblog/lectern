// 설정 창 (툴바 톱니 버튼, Ctrl+,): 화면에서 바꿀 수 있는 설정과 '설정 파일 열기'.
// 편집기 경로·제외 폴더처럼 API로 못 바꾸는 값은 설정 파일을 편집기로 열어 고친다 (서버가 저장된 파일을 다시 읽는다).

import { S, emit } from './store.js';
import { saveConfig, postJSON } from './api.js';
import { $, $$, toast } from './util.js';

const box = () => $('#lec-settings');

export function openSettings() {
  for (const input of $$('#lec-settings input[data-key]')) input.checked = S.config[input.dataset.key] !== false;
  box().hidden = false;
  $('#lec-settings input')?.focus();
}

export function closeSettings() {
  if (box().hidden) return false;
  box().hidden = true;
  return true;
}

async function onChange(e) {
  const key = e.target.dataset.key;
  if (!key) return;
  await saveConfig({ [key]: e.target.checked });
  if (key === 'external_images') location.reload();   // 그림 출처를 막는 CSP(img-src)가 바뀌므로 페이지를 다시 불러온다
  else if (key === 'math') emit('refresh-view');
}

const OPENED = {
  editor: '편집기에서 설정 파일을 열었습니다. 저장하면 반영됩니다',
  default: '설정 파일을 열었습니다',
  reveal: '편집기를 찾지 못해 탐색기에서 설정 파일을 보여 줍니다',
};

async function openConfigFile() {
  try {
    const r = await postJSON('/api/open-config', {});
    toast(OPENED[r.action] || `열었습니다: ${r.path}`);
  } catch (e) {
    toast(`설정 파일을 열지 못했습니다: ${e.message}`, 'error');
  }
}

export function initSettings() {
  $('#lec-settings-ver').textContent = `Lectern ${document.querySelector('meta[name="lec-version"]')?.content || ''}`;
  box().addEventListener('change', onChange);
  box().addEventListener('click', (e) => { if (e.target === box()) closeSettings(); });   // 바깥을 누르면 닫기
  $('#lec-settings-close').addEventListener('click', closeSettings);
  $('#lec-settings-file').addEventListener('click', openConfigFile);
  $('#lec-btn-settings').addEventListener('click', openSettings);
}
