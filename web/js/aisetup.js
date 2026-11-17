// AI 도구에 건네는 것 (D159): 설정 창 'AI 도구' 분류의 아래쪽 — Lectern 작성 안내 요약, PowerPoint·Word 스킬, 글쓰기 스타일, 내 문체.
// 넣을 곳은 사람이 고른다 (설정 ai_scope_guide·ai_scope_skills·ai_style_where — 기본은 개인 폴더, 글쓰기 스타일을 켜는 곳은 그 폴더).
// 보내기 전에 '바뀌는 파일'(전체 경로와 무엇을 하는지)을 보이고, 같은 것을 요청 글에도 적는다. 지금 상태는 서버가 정해진 파일만 읽어 준다
// (/api/ai-status — aistatus.py). Lectern 은 이 파일들을 쓰지 않는다 — 요청 글을 받은 AI 도구가 지금 상태를 알리고 물은 뒤 쓴다 (D57·D98·D132·D148).

import { S } from './store.js';
import { getJSON, saveConfig } from './api.js';
import { $, $$ } from './util.js';
import { html, setHtml } from './html.js';
import { t } from './i18n.js';
import { AI_TOOLS, aiTool, aiInfo, aiCli } from './aitool.js';

/** 마지막으로 받은 지금 상태 — 받는 중이면 undefined, 받지 못했으면 null */
let now;
let asking = 0;

const KEYS = { guide: 'ai_scope_guide', skills: 'ai_scope_skills', wstyle: 'ai_style_where' };
const SKILLS = ['pptx-to-lectern', 'lectern-to-pptx', 'lectern-to-docx'];

/** '이 폴더'로 고를 수 있는지 — 프로젝트가 열려 있고, 보기만 하는 폴더(D71 — 프로그램 폴더 안의 예제)가 아닐 때 */
export const canFolder = () => !!S.tab && !S.tab.readonly;

/** 고른 넣을 곳: guide·skills 는 all|folder, wstyle 은 folder|all|off. 이 폴더를 고를 수 없으면 모든 폴더 (글쓰기 스타일의 끄기는 Claude Code 만) */
export function scope(item) {
  const v = S.config?.[KEYS[item]];
  if (item === 'wstyle') {
    const w = ['folder', 'all', 'off'].includes(v) ? v : 'folder';
    if (w === 'off' && aiTool() !== 'claude') return canFolder() ? 'folder' : 'all';
    return w !== 'all' && !canFolder() ? 'all' : w;
  }
  return v === 'folder' && canFolder() ? 'folder' : 'all';
}

const claude = () => aiTool() === 'claude';
const folderName = () => S.tab?.name || '';
const inFolder = (...parts) => [S.tab?.root || '', ...parts].join(S.sep || '\\');
/**
 * 고른 글쓰기 스타일 (D161 — 설정 ai_style, 고르기 창 stylepick.js): {id, name, path, file?, mine?}.
 * Lectern 에 든 것이면 file(web/help 의 이름)과 path(그 판), 내 스타일(mine:<파일>)이면 개인 폴더의 그 파일
 */
export function chosenStyle() {
  const v = S.config?.ai_style || 'research';
  if (v.startsWith('mine:') && claude()) {   // 내 글쓰기 스타일은 Claude Code 의 출력 스타일 — 다른 도구면 Lectern 의 처음 것
    const file = v.slice(5);
    const got = now?.claude?.other_styles?.find((x) => x.file === file);
    return { id: v, mine: file, name: got?.name || file.replace(/\.md$/, ''), path: got?.path || `~/.claude/output-styles/${file}` };
  }
  const s = (S.writingStyles || []).find((x) => x.id === v) || S.writingStyles?.[0];
  return s ? { id: s.id, name: s.name, path: s.path, file: s.file } : { id: 'research', name: t('리서치 글쓰기'), path: S.writingStyle };
}

/** 마지막으로 받은 지금 상태 (고르기 창이 함께 쓴다 — 받는 중이면 undefined) */
export const aiStatus = () => now;

const styleName = () => chosenStyle().name;
const voicePath = () => now?.claude?.voice || now?.claude?.voice_path || t('~/.claude/rules/내-문체.md');

// ---- 바뀌는 파일 --------------------------------------------------------------------------------------

const ACTS = () => ({
  new: t('새로 만듦'), change: t('바꿈'), keep: t('그대로'), add: t('절 넣기'), value: t('한 값 적기'), move: t('옮김'),
  tool: t('그 도구의 것'), wait: t('확인 중…'), unknown: t('확인하지 못함'),
});

/** 상태를 받기 전·받지 못했을 때의 표시 */
const pending = () => (now === undefined ? 'wait' : 'unknown');

function rows(id, list) {
  const acts = ACTS();
  setHtml($(id), list.map((r) => html`<li><span class="ai-act ai-act-${r.act}">${acts[r.act]}</span><code class="ai-path">${r.path}</code>${r.note ? html`<small>${r.note}</small>` : ''}</li>`));
}

/** 스킬 하나의 상태 → 바뀌는 것 */
const skillRow = (state) => ({ missing: ['new', ''], same: ['keep', t('Lectern 의 것과 같음')], differs: ['change', t('Lectern 의 것과 다름')] })[state] || [pending(), ''];

/** 도구가 여럿이면 도구마다의 자리를 그대로 보인다 (Lectern 이 어느 도구인지 모른다) */
const perTool = (pick) => Object.values(AI_TOOLS).map((x) => ({ act: 'tool', path: pick(x), note: x.cli }));

function guideRows() {
  const one = aiInfo();
  if (scope('guide') === 'all') {
    if (!one) return perTool((x) => x.rules);
    const r = now?.rules;
    if (!r) return [{ act: pending(), path: one.rules }];
    if (claude()) return [{ act: r.exists ? 'change' : 'new', path: r.path, note: r.exists ? t('지금 것을 새 요약으로') : t('모든 폴더에서 읽힙니다') }];
    const row = { act: !r.exists ? 'new' : r.lectern ? 'change' : 'add', path: r.path, note: r.lectern ? t('Lectern 절을 새 요약으로') : t('Lectern 절 하나만') };
    return r.override ? [row, { act: 'keep', path: r.override, note: t('이 파일이 있어 위 파일은 읽히지 않습니다') }] : [row];
  }
  const files = now?.project?.rules || (one ? [one.file] : ['CLAUDE.md', 'AGENTS.md']).map((f) => ({ path: inFolder(f) }));
  const formats = now?.rules?.lectern === false ? t(' — 형식 규칙도 (개인 폴더에 없어서)') : '';
  return files.map((f) => ({ act: f.exists === undefined ? pending() : !f.exists ? 'new' : f.lectern ? 'change' : 'add', path: f.path, note: t('이 폴더의 읽는 사람·목적{formats}', { formats }) }));
}

function skillRows() {
  const one = aiInfo();
  const all = scope('skills') === 'all';
  if (!one) return perTool((x) => (all ? x.skills : inFolder(...x.projectSkills.split('/'))));
  const box = all ? now?.skills : now?.project?.skills;
  const dir = box?.dir || (all ? one.skills : inFolder(...one.projectSkills.split('/')));
  const out = SKILLS.map((n) => {
    const [act, note] = skillRow(box?.items?.[n]);
    return { act, path: `${dir}${S.sep || '\\'}${n}`, note };
  });
  if (!all && claude() && SKILLS.some((n) => ['same', 'differs'].includes(now?.skills?.items?.[n]))) {
    out.push({ act: 'keep', path: now.skills.dir, note: t('개인 스킬 폴더에도 있어 그쪽이 먼저 쓰입니다') });
  }
  return out;
}

const jsonValue = (name) => `"outputStyle": "${name}"`;

function styleRows() {
  const one = aiInfo();
  const where = scope('wstyle');
  if (!claude()) {   // 출력 스타일이 없는 도구 — 개인 지시 파일이나 그 프로젝트의 AGENTS.md 의 '글쓰기' 절 (D138)
    if (!one) return where === 'all' ? perTool((x) => x.rules) : [{ act: 'tool', path: inFolder('AGENTS.md'), note: t('Claude Code 는 출력 스타일로') }];
    if (where === 'all') return [{ act: now?.rules ? (now.rules.exists ? 'add' : 'new') : pending(), path: now?.rules?.path || one.rules, note: t("'글쓰기' 절") }];
    const f = now?.project?.rules?.[0];
    return [{ act: f ? (f.exists ? 'add' : 'new') : pending(), path: f?.path || inFolder('AGENTS.md'), note: t("'글쓰기' 절") }];
  }
  const c = now?.claude;
  const out = [];
  const chosen = chosenStyle();
  if (where !== 'off' && chosen.mine) {
    out.push({ act: 'keep', path: chosen.path, note: t('내 글쓰기 스타일') });
  } else if (where !== 'off') {
    const st = c?.styles?.[chosen.id];
    const act = st ? ({ missing: 'new', same: 'keep', differs: 'change' })[st.state] : pending();
    out.push({ act, path: st?.path || `~/.claude/output-styles/${chosen.file}.md`, note: st?.state === 'same' ? t('Lectern 의 것과 같음') : st?.state === 'differs' ? t('Lectern 의 것과 다름') : '' });
    if (st?.voice) out.push({ act: 'move', path: voicePath(), note: t("스타일 파일 끝의 '내 문체' 절을 이 노트로") });
  }
  const local = now?.project?.settings?.local;
  if (where === 'all') {
    const user = c?.settings?.user;
    out.push({ act: user ? (user.value === styleName() ? 'keep' : 'value') : pending(), path: user?.path || '~/.claude/settings.json', note: jsonValue(styleName()) });
    if (local?.value) out.push({ act: 'keep', path: local.path, note: t('이 폴더에는 따로 고른 {value} 이 있어 이 폴더에서는 그것이 듣습니다', { value: jsonValue(local.value) }) });
  } else {
    const want = where === 'off' ? 'Default' : styleName();
    out.push({ act: local ? (local.value === want ? 'keep' : 'value') : pending(), path: local?.path || inFolder('.claude', 'settings.local.json'), note: jsonValue(want) });
  }
  return out;
}

function voiceRows() {
  const one = aiInfo();
  if (!one) return perTool((x) => (x === AI_TOOLS.claude ? t('~/.claude/rules/내-문체.md') : x.rules));
  if (!claude()) return [{ act: now?.rules ? (now.rules.exists ? 'add' : 'new') : pending(), path: now?.rules?.path || one.rules, note: t("'내 문체' 절") }];
  const c = now?.claude;
  const out = [{ act: c ? (c.voice ? 'change' : 'new') : pending(), path: voicePath(), note: c?.voice ? t('고칠 곳만 보이고 고른 것만') : t('어느 폴더·스타일에서나 같은 노트') }];
  const old = Object.values(c?.styles || {}).find((s) => s.voice);   // 예전 판: 스타일 파일 끝의 내 문체 절
  if (old) out.push({ act: 'move', path: old.path, note: t("끝의 '내 문체' 절을 이 노트로") });
  return out;
}

/** 지금 이 폴더에서 듣는 글쓰기 스타일 (Claude Code — 폴더의 값이 개인 설정보다 앞선다) */
function styleNow() {
  const el = $('#lec-wstyle-now');
  if (!el) return;
  const c = now?.claude;
  if (!claude() || !c) {
    el.textContent = '';
    return;
  }
  const local = now.project?.settings?.local?.value;
  const shared = now.project?.settings?.shared?.value;
  const user = c.settings.user.value;
  const [value, from] = local ? [local, t('이 폴더의 settings.local.json')] : shared ? [shared, t('이 폴더의 .claude/settings.json')] : user ? [user, t('개인 설정')] : [t('Claude Code 기본'), t('정하지 않음')];
  el.textContent = now.project
    ? t('지금 {folder} 폴더에서 듣는 스타일: {value} ({from}) · 모든 폴더의 기본: {user}', { folder: folderName(), value, from, user: user || t('Claude Code 기본') })
    : t('모든 폴더의 기본 스타일: {user}', { user: user || t('Claude Code 기본') });
}

/** 넣을 곳 단추의 이름과 설명 — [이름, 설명]. 폴더 이름이 든 것은 열린 폴더가 없으면 '이 폴더' */
function labels() {
  const name = folderName();
  const only = name ? t('{name} 폴더만', { name }) : t('이 폴더만');
  const all = [t('모든 폴더 (개인)')];
  return {
    guide: {
      all: [all[0], t('개인 폴더에 — 이 PC 의 모든 폴더에서 읽힙니다. 폴더마다 다른 읽는 사람·목적은 넣지 않습니다')],
      folder: [only, t('그 폴더의 지시 파일에 — 그 폴더의 글을 누가 읽고 무엇에 쓰는지와 말투를 적습니다')],
    },
    skills: {
      all: [all[0], t('개인 스킬 폴더에 — 이 PC 의 모든 폴더에서 씁니다')],
      folder: [only, t('그 폴더의 스킬 폴더에 — 그 폴더를 git 으로 함께 쓰는 사람도 씁니다')],
    },
    wstyle: claude() ? {
      folder: [name ? t('{name} 폴더에서 켜기', { name }) : t('이 폴더에서 켜기'), t('보고서를 쓰는 폴더에 — 스타일 파일은 개인 폴더에 두고, 폴더마다 다른 스타일을 켤 수 있습니다')],
      all: [t('모든 폴더에서 켜기'), t('모든 폴더의 기본으로 — 코드를 쓰는 폴더에서도 Claude Code 의 개발 지침이 빠집니다')],
      off: [name ? t('{name} 폴더에서 끄기', { name }) : t('이 폴더에서 끄기'), t('코드를 쓰는 폴더에 — Claude Code 의 기본 스타일로 둡니다')],
    } : {
      folder: [only, t("그 폴더의 AGENTS.md 에 '글쓰기' 절로")],
      all: [all[0], t("개인 지시 파일에 '글쓰기' 절로 — 이 PC 의 모든 폴더에서 읽힙니다")],
    },
  };
}

/** 넣을 곳 단추의 이름·설명과 고른 것, 바뀌는 파일 */
function renderAll() {
  const names = labels();
  for (const item of Object.keys(KEYS)) {
    for (const radio of $$(`#lec-settings input[name="${KEYS[item]}"]`)) {
      const label = radio.closest('label');
      const [name, desc] = names[item][radio.value] || ['', ''];
      label.hidden = !name;
      label.querySelector('.ai-lab').textContent = name;
      label.querySelector('.ai-lab-desc').textContent = desc;
      radio.checked = radio.value === scope(item);
      const folder = radio.value !== 'all';
      radio.disabled = folder && !canFolder();
      label.title = folder && !canFolder() ? (S.tab?.readonly ? t('보기만 하는 폴더입니다 — Lectern 프로그램 폴더 안') : t('열린 폴더가 없습니다')) : '';
    }
  }
  rows('#lec-aiguide-files', guideRows());
  rows('#lec-skills-files', skillRows());
  rows('#lec-wstyle-files', styleRows());
  rows('#lec-voice-files', voiceRows());
  $('#lec-wstyle-warn').hidden = !(claude() && scope('wstyle') === 'all');
  $('#lec-wstyle-chosen').textContent = t('고른 스타일: {name}', { name: claude() && scope('wstyle') === 'off' ? t('Claude Code 기본') : styleName() });
  styleNow();
}

/** 설정 창을 열 때·도구나 탭이 바뀔 때: 지금 상태를 다시 받아 그린다 (받는 동안은 '확인 중…') */
export async function refreshAiSetup() {
  const me = ++asking;
  now = undefined;
  renderAll();
  try {
    const got = await getJSON(`/api/ai-status${S.tab ? `?p=${encodeURIComponent(S.tab.id)}` : ''}`);
    if (me === asking) now = got;
  } catch {
    if (me === asking) now = null;
  }
  if (me === asking) renderAll();
}

/** 다른 창에서 넣을 곳을 바꿨을 때 — 상태는 그대로 두고 다시 그린다 (D159) */
export const redrawAiSetup = () => renderAll();

// ---- 요청 글 ------------------------------------------------------------------------------------------

const LECTERN = () => t('Lectern(Markdown을 중심으로 AI와 함께 작업하는 통합 리서치 작업 환경)');

/** 작성 안내 요약 (D57·D159): 모든 폴더면 개인 규칙 파일 하나(Claude Code)나 개인 지시 파일의 한 절, 이 폴더면 그 폴더의 지시 파일에 읽는 사람·목적 */
export function guidePrompt() {
  const one = aiInfo();
  const guide = S.writingGuide;
  if (scope('guide') === 'all') {
    const target = !one
      ? t('네 개인 지시 파일 (Claude Code 는 ~/.claude/rules/lectern.md 한 파일, Codex 는 ~/.codex/AGENTS.md, Antigravity 는 ~/.gemini/AGENTS.md, OpenCode 는 ~/.config/opencode/AGENTS.md 의 한 절)')
      : claude()
        ? t('내 개인 규칙 파일 {file} (모든 프로젝트에서 읽힌다 — 이 파일 하나에만 쓰고 ~/.claude/CLAUDE.md 는 고치지 마)', { file: one.rules })
        : t('내 개인 지시 파일 {file} 의 Lectern 절 하나 (모든 프로젝트에서 읽힌다 — 그 절 밖은 고치지 마)', { file: one.rules });
    return t("내 문서는 사람이 {lectern}으로 읽고 그 자리에서 고쳐. 먼저 작성 안내 {guide} 를 읽고, 안내 끝의 요약을 {target} 에 넣어 줘. 쓰기 전에 그 파일이 지금 있는지와 Lectern 요약이 이미 들어 있는지 알려 주고, 넣을 글을 보여 준 뒤 물어봐. 프로젝트마다 다른 것(읽는 사람·목적·말투)은 여기에 넣지 마 — 그것은 프로젝트마다 따로 정해.",
      { lectern: LECTERN(), guide, target });
  }
  const where = one
    ? t('이 프로젝트의 {file}', { file: one.file })
    : t('이 프로젝트의 지시 파일 (Claude Code 는 CLAUDE.md, Codex·Antigravity·OpenCode 는 AGENTS.md — 둘 다 쓰는 프로젝트면 AGENTS.md 에 넣고 CLAUDE.md 에는 @AGENTS.md 한 줄만 둬)');
  const rules = now?.rules?.lectern === true
    ? t('형식 규칙은 내 개인 폴더({file})에 이미 있으니 넣지 마.', { file: now.rules.path })
    : now?.rules?.lectern === false
      ? t('안내 끝의 요약도 이 프로젝트에 맞게 다듬어 함께 넣어.')
      : t('내 개인 폴더의 Lectern 요약({file})이 이미 있으면 형식 규칙은 넣지 말고, 없으면 안내 끝의 요약도 이 프로젝트에 맞게 다듬어 함께 넣어.', { file: one?.rules ?? '~/.claude/rules/lectern.md' });
  return t('이 프로젝트의 문서는 사람이 {lectern}으로 읽고 그 자리에서 고쳐. 먼저 작성 안내 {guide} 를 읽어. {where} 에 이 프로젝트의 글을 누가 읽고 무엇에 쓰는지와 말투를 적어 줘 — 모르면 나에게 물어봐. {rules} 넣을 글을 먼저 보여 준 뒤 물어봐. 앞으로 이 프로젝트의 문서는 그 규칙대로 써.',
    { lectern: LECTERN(), guide, where, rules });
}

/** PowerPoint·Word 스킬 (D98·D146·D159): 넣을 곳에 지금 있는지·같은지 알리고 물은 뒤, 없는 것과 다른 것만 복사 */
export function skillsPrompt() {
  const one = aiInfo();
  const all = scope('skills') === 'all';
  const dir = all
    ? (one ? one.skills : t('네 개인 스킬 폴더 (Claude Code 는 ~/.claude/skills, Codex 는 ~/.agents/skills, Antigravity 는 ~/.gemini/config/skills, OpenCode 는 ~/.config/opencode/skills)'))
    : (one ? t('이 프로젝트의 {dir}', { dir: one.projectSkills }) : t('이 프로젝트의 스킬 폴더 (Claude Code 는 .claude/skills, Codex·Antigravity·OpenCode 는 .agents/skills)'));
  const first = !all && claude() ? t(' 개인 스킬 폴더(~/.claude/skills)에 같은 이름이 있으면 그쪽이 먼저 쓰인다는 것도 알려 줘.') : '';
  return t('Lectern 에 {cli} 스킬 세 개가 들어 있어: {src} 의 pptx-to-lectern, lectern-to-pptx, lectern-to-docx. 먼저 그 폴더의 README.md 를 읽고 무엇을 하는지 짧게 알려 줘. 그다음 {dir} 에 지금 그 스킬이 있는지, 있으면 Lectern 의 것과 같은지 확인해 알려 주고 설치할지 나에게 물어봐. 내가 그렇다고 하면 없는 것과 다른 것만 {dir} 에 복사해 — 같은 것은 그대로 두고, 다른 것을 바꾸기 전에는 다시 물어봐.{first}',
    { cli: aiCli(), src: S.skillsDir, dir, first });
}

/** 글쓰기 스타일 (D132·D159): 파일은 늘 개인 폴더에, 켜는 곳은 고른 대로 (Claude Code). 다른 도구는 '글쓰기' 절로 (D138) */
export function writingStylePrompt() {
  const chosen = chosenStyle();
  const file = chosen.path;
  const where = scope('wstyle');
  if (claude()) {
    const check = t('먼저 ~/.claude/settings.json 과 이 프로젝트의 .claude/settings.local.json·.claude/settings.json 의 outputStyle 값을 확인해 알려 줘.');   // 끄기 — 이 글의 첫 할 일
    const also = t('~/.claude/settings.json 과 이 프로젝트의 .claude/settings.local.json·.claude/settings.json 의 outputStyle 값도 확인해 알려 줘.');   // 켜기 — 스타일 파일을 읽은 다음
    if (where === 'off') {
      return t('이 프로젝트에서는 Claude Code 의 기본 출력 스타일을 쓰고 싶어. {check} 그 뒤 이 프로젝트의 .claude/settings.local.json 에 {value} 한 값만 적을지 물어보고 (다른 값은 그대로, 파일이 없으면 만들어), 내가 그렇다고 하면 적어 줘.',
        { check, value: jsonValue('Default') });
    }
    if (chosen.mine) {   // 내 스타일 (D161) — 이미 개인 폴더에 있다. 켜기만
      const set = where === 'all'
        ? t('~/.claude/settings.json 에 {value} 한 값만 적을지 물어봐 (다른 값은 그대로). 이 스타일이 Claude Code 의 개발 지침을 빼는지(맨 앞 설정에 keep-coding-instructions: true 가 없으면 뺀다) 알려 주고, 빼면 코드를 쓰는 프로젝트에서는 그 프로젝트의 .claude/settings.local.json 에 {off} 를 두라고 알려 줘.', { value: jsonValue(styleName()), off: jsonValue('Default') })
        : t('이 프로젝트의 .claude/settings.local.json 에 {value} 한 값만 적을지 물어봐 (다른 값은 그대로, 파일이 없으면 만들어).', { value: jsonValue(styleName()) });
      return t('내 출력 스타일 {name} ({file})을 켜고 싶어. 먼저 그 파일을 읽고 어떤 스타일인지 짧게 알려 줘. {check} 그 뒤 {set} 내가 그렇다고 하면 적어 주고, 스타일 파일을 고친 지 얼마 안 됐으면 Claude Code 를 다시 시작해야 읽는다는 것을 알려 줘.',
        { name: styleName(), file, check: also, set });
    }
    const set = where === 'all'
      ? t('~/.claude/settings.json 에 {value} 한 값만 적기 — 다른 값은 그대로. 이 스타일은 Claude Code 의 개발 지침을 빼니, 코드를 쓰는 프로젝트에서는 그 프로젝트의 .claude/settings.local.json 에 {off} 를 두거나 /output-style 로 기본을 고르라고 알려 줘. 프로젝트에 따로 고른 값이 있으면 그 프로젝트에서는 그것이 이긴다는 것도.', { value: jsonValue(styleName()), off: jsonValue('Default') })
      : t('이 프로젝트의 .claude/settings.local.json 에 {value} 한 값만 적기 — 다른 값은 그대로, 파일이 없으면 만들어.', { value: jsonValue(styleName()) });
    return t("Lectern 에 Claude Code 의 글쓰기용 출력 스타일이 들어 있어: {file}. 먼저 그 파일을 읽고 무엇이 바뀌는지 짧게 알려 줘. 그다음 ~/.claude/output-styles/ 에 같은 이름의 파일이 있는지와 Lectern 의 것과 같은지 알려 줘. {check} 그 뒤 두 가지를 할지 나에게 물어봐. (1) 파일이 없거나 다르면 ~/.claude/output-styles/ 에 같은 파일 이름으로 복사하기 — 바꿀 때 있던 파일 끝에 '## 내 문체'(영어판은 '## My style') 절이 있으면 그 절은 내 개인 규칙 {voice} 로 옮길지 따로 물어봐. (2) {set} 내가 그렇다고 하면 해 주고, 새로 설치한 스타일은 Claude Code 를 다시 시작해야 읽는다는 것을 알려 줘.",
      { file, check: also, voice: voicePath(), set });
  }
  const one = aiInfo();
  if (one) {
    const target = where === 'all' ? t('내 개인 지시 파일 {file}', { file: one.rules }) : t('이 프로젝트의 AGENTS.md');
    return t("Lectern 에 글쓰기 규칙이 들어 있어: {file} (Claude Code 의 출력 스타일 형식으로 쓴 파일이야). 먼저 그 파일을 읽고 무엇이 바뀌는지 짧게 알려 준 뒤, {target} 에 넣을지 나에게 물어봐. 내가 그렇다고 하면 맨 앞 설정(--- 사이)은 빼고 본문을 {target} 의 '글쓰기' 절로 넣어 (본문의 ## 제목은 ### 로 한 단계 내리고, 그 절이 이미 있으면 바꿀지 다시 물어보고, 그 안의 '내 문체' 부분은 그대로 남겨). 그 뒤로 글은 그 규칙대로 써.",
      { file, target });
  }
  const target = where === 'all' ? t('네 개인 지시 파일') : t('이 프로젝트의 AGENTS.md');
  return t("Lectern 에 글쓰기 규칙이 들어 있어: {file} (Claude Code 의 출력 스타일 형식으로 쓴 파일이야). 먼저 그 파일을 읽고 무엇이 바뀌는지 짧게 알려 줘. 네가 Claude Code 면 ~/.claude/output-styles/ 에 같은 파일 이름으로 설치할지 묻고, 켜는 것은 보고서를 쓰는 폴더에서 /output-style 로 고르라고 알려 줘 (코드를 쓰는 폴더에서는 개발 지침이 빠진다). 다른 도구면 {target} 에 넣을지 물어보고, 내가 그렇다고 하면 맨 앞 설정(--- 사이)은 빼고 본문을 '글쓰기' 절로 넣어 (본문의 ## 제목은 ### 로 한 단계 내리고, 그 절이 이미 있으면 바꿀지 다시 물어봐). 어느 쪽이든 있던 것을 바꿀 때 '내 문체' 부분은 그대로 남겨.",
    { file, target });
}

// ---- 고르기 --------------------------------------------------------------------------------------------

export function initAiSetup() {
  for (const key of Object.values(KEYS)) {
    for (const radio of $$(`#lec-settings input[name="${key}"]`)) {
      radio.addEventListener('change', () => {
        if (!radio.checked) return;
        saveConfig({ [key]: radio.value });   // S.config 는 바로 바뀐다 — 저장은 뒤에서
        renderAll();
      });
    }
  }
}
