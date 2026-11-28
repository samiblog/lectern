// 터미널에서 쓰는 AI 도구 (D138): 화면의 이름과 요청 글이 따르는 표. 설정 ai_tool (설정 창의 '쓰는 AI 도구') —
// claude(Claude Code, 기본) | codex(Codex CLI) | antigravity(Antigravity CLI) | opencode(OpenCode) | any(여럿 — 이름을 정하지 않고 'AI').
// Lectern 은 이 도구들을 실행하지 않는다 — 사용자가 터미널에서 띄운다. 여기는 이름·지시 파일·스킬 폴더·이어 가기 명령뿐이고,
// 터미널에 무엇이 도는지 찾지도 않는다 (D69). 붙여 넣기가 네 도구에서 같은 까닭은 terminal.js 의 pasteText.

import { S } from './store.js';
import { t } from './i18n.js';

/**
 * name: 짧은 이름('Codex로 보내기'), cli: 프로그램 이름, file: 프로젝트 지시 파일, skills: 개인 스킬 폴더, projectSkills: 프로젝트 스킬 폴더,
 * rules: Lectern 작성 안내 요약을 넣는 개인 파일 (D159 — Claude Code 는 개인 규칙 폴더의 한 파일, 다른 도구는 개인 지시 파일의 한 절),
 * resume: 하던 대화를 잇는 명령. 경로는 각 도구의 공식 문서로 확인했다 (2026-11-17 — 서버 aistatus.py 의 TOOLS 와 같게, 시험이 견준다)
 */
export const AI_TOOLS = {
  claude: { name: 'Claude', cli: 'Claude Code', file: 'CLAUDE.md', skills: '~/.claude/skills', projectSkills: '.claude/skills', rules: '~/.claude/rules/lectern.md', resume: 'claude --continue' },
  // Codex 의 개인 스킬은 ~/.agents/skills (~/.codex/skills 는 옛 자리), 개인 지시 파일은 ~/.codex/AGENTS.md (AGENTS.override.md 가 있으면 그것만 읽힌다)
  codex: { name: 'Codex', cli: 'Codex', file: 'AGENTS.md', skills: '~/.agents/skills', projectSkills: '.agents/skills', rules: '~/.codex/AGENTS.md', resume: 'codex resume --last' },
  antigravity: { name: 'Antigravity', cli: 'Antigravity', file: 'AGENTS.md', skills: '~/.gemini/config/skills', projectSkills: '.agents/skills', rules: '~/.gemini/AGENTS.md', resume: 'agy --continue' },
  opencode: { name: 'OpenCode', cli: 'OpenCode', file: 'AGENTS.md', skills: '~/.config/opencode/skills', projectSkills: '.agents/skills', rules: '~/.config/opencode/AGENTS.md', resume: 'opencode --continue' },   // ~/.claude/skills 도 읽는다
};

/** 고른 도구: 'claude'·'codex'·'antigravity'·'opencode'·'any' */
export const aiTool = () => (S.config?.ai_tool === 'any' || S.config?.ai_tool in AI_TOOLS ? S.config.ai_tool : 'claude');

/** 고른 도구의 표 — 여럿(any)이면 null */
export const aiInfo = () => AI_TOOLS[aiTool()] ?? null;

/** 짧은 이름: 'Claude'·'Codex'·'Antigravity'·'OpenCode', 여럿이면 'AI' */
export const aiName = () => aiInfo()?.name ?? 'AI';

/** 프로그램 이름: 'Claude Code'·'Codex'·'Antigravity'·'OpenCode', 여럿이면 'AI 도구' */
export const aiCli = () => aiInfo()?.cli ?? t('AI 도구', { alt: true });   // 영어는 문장 속 꼴 'your AI tool' — 설정 창 분류 이름은 보통 꼴 'AI tool'

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

/**
 * 기획 메모 반영 요청 (D150): ref 는 WORK.md 의 '@경로'. 옮길 곳·겹치는 줄·날짜·메모를 건드리지 않음·기록 한 줄은
 * 작성 안내(web/help/writing.md 의 '업무 카드' 절)가 정한다. 문서 우클릭(docmenu.js)이 터미널에 Enter 없이 넣는다 (D51)
 */
/**
 * 원문의 색 빼기 요청 (0.113.2): 원문이 정한 색·모양은 사람이 고른 색 조합·도해 스타일(D212·D213)보다 먼저라 그대로 남는다.
 * ref 는 '@경로 12~20행'(그림 하나 — 고르기 창) 이나 '@경로'(문서 전체 — AI 요청 메뉴). 나누는 법은 작성 안내 4장의 '색 없이 나누는 법'
 */
export const uncolorPrompt = (ref, key = 'colors') => (key === 'style'
  ? t("Lectern 작성 안내({guide}) 4장을 읽고, {ref} 그림에 원문이 정한 모양·색(classDef·style·%%{init}%%·fillcolor 같은 것)을 빼 줘 — 내가 Lectern 에서 도해 스타일을 골라도 그것이 남는다. 강조는 :::key·:::warn·:::muted(Graphviz 는 class=\"key\")로 바꾸고, 블록 안의 표시 줄(스타일·색 번호)과 글은 그대로 둬. 고친 뒤 무엇을 바꿨는지 한두 줄로 알려 줘.", { guide: S.writingGuide, ref })
  : t("Lectern 작성 안내({guide}) 4장의 '색 없이 나누는 법'을 읽고, {ref} 의 그림·차트에 원문이 정한 색을 빼 줘 — 내가 Lectern 에서 색 조합을 골라도 그 색이 남는다. 색으로 나누던 것은 그 표대로(계열은 데이터의 열이나 층마다 datum, 강조는 투명도, 전망은 점선, 도해의 강조는 :::key·:::warn·:::muted) 바꾸고, 블록 안의 표시 줄(스타일·색 번호)과 데이터는 그대로 둬. 색 자체에 뜻이 있는 것(증가 빨강·감소 파랑 같은)은 빼기 전에 물어봐. 고친 뒤 무엇을 바꿨는지 한두 줄로 알려 줘.", { guide: S.writingGuide, ref }));

export const memoPrompt = (ref) => t("Lectern 작성 안내({guide})의 '업무 카드' 절을 읽고, {ref} 의 '기획 메모' 절을 이 업무 카드의 할 일·일정·결정·현재 상태에 반영해 줘. 메모 글은 그대로 두고, 날짜가 분명하지 않으면 묻고, 반영한 것은 기록 절에 한 줄 남겨 줘.", { guide: S.writingGuide, ref });

/**
 * 바꿔 쓰기 요청 (D155): ref 는 '@경로 12~18행'. 글을 다시 써야 하는 바꾸기(문단 셋을 표로, 표를 글로 풀어)는 규칙으로 할 수 없어 AI 에게 맡긴다 —
 * 바꿀 모양은 사람이 이어서 적고 Enter 를 누른다 (요청 글은 Enter 없이 — D51). 바꾸기 창의 '이 줄에 맞는 것'
 */
export const rewritePrompt = (ref) => t('Lectern 작성 안내({guide})를 따라 {ref} 를 다른 구성 요소로 바꿔 써 줘. 내용과 숫자는 그대로 두고 모양만 바꾸고, 고치기 전에 바꾼 모양을 먼저 보여 줘. 바꿀 모양: ', { guide: S.writingGuide, ref });

/** 하던 대화를 잇는 법 — 멈춘 프로그램을 다시 시작한 뒤의 안내 (terminal.js) */
export function aiResume() {
  const one = aiInfo();
  const say = (x) => t('{cli} 는 {command} 로 이어 갑니다', { cli: x.cli, command: x.resume });
  return one ? say(one) : Object.values(AI_TOOLS).map(say).join(', ');
}
