// 터미널에서 쓰는 AI 도구 (D138): 화면의 이름과 요청 글이 따르는 표. 설정 ai_tool (설정 창의 '쓰는 AI 도구') —
// claude(Claude Code, 기본) | codex(Codex CLI) | antigravity(Antigravity CLI) | opencode(OpenCode) | any(여럿 — 이름을 정하지 않고 'AI').
// Lectern 은 이 도구들을 실행하지 않는다 — 사용자가 터미널에서 띄운다. 여기는 이름·지시 파일·스킬 폴더·이어 가기 명령뿐이고,
// 터미널에 무엇이 도는지 찾지도 않는다 (D69). 붙여 넣기가 네 도구에서 같은 까닭은 terminal.js 의 pasteText.

import { S } from './store.js';
import { t } from './i18n.js';

/** name: 짧은 이름('Codex로 보내기'), cli: 프로그램 이름, file: 프로젝트 지시 파일, skills: 개인 스킬 폴더, resume: 하던 대화를 잇는 명령 */
export const AI_TOOLS = {
  claude: { name: 'Claude', cli: 'Claude Code', file: 'CLAUDE.md', skills: '~/.claude/skills', resume: 'claude --continue' },
  codex: { name: 'Codex', cli: 'Codex', file: 'AGENTS.md', skills: '~/.codex/skills', resume: 'codex resume --last' },
  antigravity: { name: 'Antigravity', cli: 'Antigravity', file: 'AGENTS.md', skills: '~/.gemini/config/skills', resume: 'agy --continue' },
  opencode: { name: 'OpenCode', cli: 'OpenCode', file: 'AGENTS.md', skills: '~/.config/opencode/skills', resume: 'opencode --continue' },   // ~/.claude/skills 도 읽는다
};

/** 고른 도구: 'claude'·'codex'·'antigravity'·'opencode'·'any' */
export const aiTool = () => (S.config?.ai_tool === 'any' || S.config?.ai_tool in AI_TOOLS ? S.config.ai_tool : 'claude');

/** 고른 도구의 표 — 여럿(any)이면 null */
export const aiInfo = () => AI_TOOLS[aiTool()] ?? null;

/** 짧은 이름: 'Claude'·'Codex'·'Antigravity'·'OpenCode', 여럿이면 'AI' */
export const aiName = () => aiInfo()?.name ?? 'AI';

/** 프로그램 이름: 'Claude Code'·'Codex'·'Antigravity'·'OpenCode', 여럿이면 'AI 도구' */
export const aiCli = () => aiInfo()?.cli ?? t('AI 도구');

/**
 * 다듬기 점검 요청 (D148): ref 는 '@경로' 또는 '@경로 12~30행'. 순서·등급·건드리지 않을 것은 안내(web/help/review.md)가 정한다 —
 * 표를 먼저 보이고, 고치는 것은 사람이 고른 뒤. 문서 우클릭(docmenu.js)이 터미널에 Enter 없이 넣는다 (D51)
 */
export const reviewPrompt = (ref) => t('Lectern 의 다듬기 점검 안내({guide})를 읽고, 내가 쓴 {ref} 를 점검해 줘. 고치기 전에 표로 먼저 보여 줘.', { guide: S.reviewGuide, ref });

/**
 * 내 문체 노트 요청 (D148): refs 는 견본의 '@경로'. 비었으면 사람이 견본을 이어서 적는다 (설정 창).
 * 세 칸(지킬 것·참고할 것·따라 하지 않을 것)과 저장할 곳은 안내(web/help/voice.md)가 정한다 — 저장하기 전에 보이고 묻는다
 */
export const voicePrompt = (refs = '') => (refs
  ? t('Lectern 의 내 문체 안내({guide})를 읽고, 내가 직접 쓴 {refs} 를 견본으로 내 문체 노트를 만들거나 보태 줘. 저장하기 전에 무엇을 찾았는지 먼저 보여 줘.', { guide: S.voiceGuide, refs })
  : t('Lectern 의 내 문체 안내({guide})를 읽고, 내가 직접 쓴 글을 견본으로 내 문체 노트를 만들어 줘. 저장하기 전에 무엇을 찾았는지 먼저 보여 줘. 견본: ', { guide: S.voiceGuide }));

/** 하던 대화를 잇는 법 — 멈춘 프로그램을 다시 시작한 뒤의 안내 (terminal.js) */
export function aiResume() {
  const one = aiInfo();
  const say = (x) => t('{cli} 는 {command} 로 이어 갑니다', { cli: x.cli, command: x.resume });
  return one ? say(one) : Object.values(AI_TOOLS).map(say).join(', ');
}
