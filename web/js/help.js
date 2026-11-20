// 사용설명서(F1)와 단축키 표(툴바 '?' 버튼, Ctrl+/) — D45.
// 설명서는 web/help/manual/ 의 문서들(트리 — D182)을 처음 열 때 받아 문서처럼 그린다 (지금 문서 스타일·글자 크기). 터미널 모음처럼 사이드바와
// 문서 화면 위를 덮고, 왼쪽에 문서 트리와 지금 문서의 절, Ctrl+F 는 지금 문서 안에서 찾는다. 다른 화면으로 가면(문서 열기·프로젝트 탭·터미널) 닫힌다.
// 단축키 표와 설명서의 '단축키' 문서(10.1)는 같은 SHORTCUTS 로 만든다 — 단축키를 더하면 여기에 넣는다.
// 사용설명서 창 (D181): 머리줄('사용설명서')·문서 트리를 우클릭해 '새 창에서 열기'(설명서를 보는 중의 Ctrl+Shift+N 도) — 문서의 새 창과 같은 독립창(D95)이
// 폴더 개요 위에 설명서를 덮고 연다 (읽던 곳에서). 그 창에서 F1·Esc·✕ 는 창을 닫는다. 예제 링크는 메인 창에 맡긴다 (예제 프로젝트는 메인 창의 탭).

import { S, on, emit } from './store.js';
import { renderMarkdown } from './markdown.js';
import { decorateBlocks } from './doc.js';
import { setFindTarget, findText } from './find.js';
import { renderMermaid } from './mermaid.js';
import { esc, html, raw, setHtml } from './html.js';
import { $, $$, findAnchor, toast } from './util.js';
import { LANG, t } from './i18n.js';
import { native, postJSON } from './api.js';
import { solo, soloQuery } from './solo.js';
import { showMenu } from './ui.js';

/** 이 창이 사용설명서 창인지 (D181) */
export const helpWindow = !!solo?.help;

/**
 * 사용설명서·예제 가이드를 따로 창에서 여는지 (D181 — 기본). 설정 ref_windows: auto(앱 창에서는 따로 창, 브라우저 개발 모드에서는 덮는 보기 —
 * 팝업을 막는 브라우저가 있고 점검이 덮는 보기를 본다)·on·off
 */
export function refWindows() {
  const v = S.config?.ref_windows;
  return v === 'on' || (v !== 'off' && native.has('open_window'));
}

/** [묶음, [[키, 하는 일]], 탭]. 키: 'Ctrl+Shift+F' 처럼 + 로 잇고, 같은 일을 하는 다른 키는 ' / ' 로 나눈다. 탭은 KEY_TABS 의 id (D157) */
export const SHORTCUTS = [
  [t('열기·찾기'), [
    ['Ctrl+P', t('문서·코드 빠르게 열기 (이름·제목·경로로)')],
    ['Ctrl+Shift+P', t('명령 찾기 — 이름을 쳐서 고르고 옆에 단축키 (빠른 열기에서 > 로 시작해도). 키가 없는 인쇄·모두 펼치기 등도')],
    ['Ctrl+F', t('지금 화면에서 찾기 — 문서·코드·사용설명서 (폴더 개요에서는 트리 거르기)')],
    ['Ctrl+O', t('폴더 열기 — 새 탭으로')],
    ['Ctrl+N', t('새 문서 만들기 — 경로를 정하면 바로 만들어 새 문서 탭에서 편집')],
    ['Ctrl+G', t('줄로 가기 — 문서·코드 화면과 편집 모드')],
  ], 'open'],
  [t('프로젝트 탭'), [
    ['Ctrl+1~8', t('그 순번의 탭')],
    ['Ctrl+9', t('마지막 탭')],
    ['Alt+PageDown / Alt+PageUp', t('다음 / 이전 프로젝트 탭')],
    ['Ctrl+Shift+W', t('프로젝트 탭 닫기 (탭을 마우스 가운데 버튼으로 눌러도)')],
  ], 'open'],
  [t('문서 탭'), [
    [t('누르기'), t('사이드바 목록의 문서를 새 문서 탭에서 열기 — 이미 열려 있으면 그 탭으로')],
    [t('Ctrl+누르기 / 가운데 버튼'), t('보던 문서를 두고 뒤에서 새 문서 탭 — 트리·목록·링크·검색·모아 보기')],
    [t('Alt+누르기'), t('사이드바 목록의 문서를 지금 탭에서 열기')],
    ['Ctrl+T', t('새 문서 탭에 문서 열기')],
    ['Ctrl+Shift+T', t('닫은 문서 탭 다시 열기')],
    ['Ctrl+Shift+N', t('지금 문서를 새 창으로 옮기기')],
    ['Ctrl+Tab / Ctrl+Shift+Tab', t('다음 / 이전 문서 탭 (Ctrl+PageDown / Ctrl+PageUp 도 됨)')],
    ['Alt+1~8', t('그 순번의 문서 탭')],
    ['Alt+9', t('마지막 문서 탭')],
    ['Ctrl+W', t('문서 탭 닫기 (Ctrl+F4, 탭을 마우스 가운데 버튼으로 눌러도)')],
  ], 'open'],
  [t('화면'), [
    ['Alt+← / Alt+→', t('뒤로 / 앞으로 — 같은 문서 안에서 뛴 자리도 (마우스의 뒤로·앞으로 버튼도)')],
    ['F6 / Shift+F6', t('초점을 문서 → 터미널 1·2·3… → 사이드바 차례로 옮기기 / 거꾸로 (터미널 안에서도, 닫혀 있으면 열면서 1번으로)')],
    ['F7 / Shift+F7', t('다음 / 이전 바뀐 곳 — 밖에서 고쳐져 자동으로 다시 그려진 블록 (상태줄의 \'바뀐 곳 N곳\'과 같음, 현재 줄도 그리로)')],
    ['Alt+O', t('목차 보이기·숨기기 (탭 막대의 [목차])')],
    ['Alt+L', t('Markdown 문서의 줄 번호 보이기·감추기')],
    ['Alt+H', t('장 하이라이트 켜기·끄기 — 고른 줄이 있으면 그 줄의 하이라이트, 장이 없는 문서·코드 화면에서는 Ctrl+Enter 와 같음')],
    ['Ctrl+Shift+[ / Ctrl+Shift+]', t('현재 줄이 든 절 접기 / 펴기 (md 문서 — 제목 왼쪽의 화살표를 눌러도)')],
    ['Ctrl+Alt+[ / Ctrl+Alt+]', t('모두 접기 / 모두 펴기 (md 문서 — 여백 우클릭 메뉴와 같음, 현재 줄은 그 절의 제목으로)')],
    ['Alt+M', t('이 프로젝트의 메모 열기·닫기')],
    ['Alt+W', t('업무 현황 — 공통 폴더의 개요 맨 위 (WORK.md 가 있는 폴더들의 상태·마감·할 일·일정)')],
    ['Alt+S', t('일정 더하기 — 고른 WORK.md 의 일정 절 끝에 한 줄')],
    [t('달력 (날짜 칸·Ctrl+;)'), t('←→ 하루, ↑↓ 한 주, PageUp·PageDown 한 달, Home·End 그 주의 처음·끝, T 오늘, Enter 고르기, Esc 그만두기')],
    ['Ctrl+= / Ctrl+- / Ctrl+0', t('문서 글자 키우기 / 줄이기 / 100%')],
    ['F5', t('다시 불러오기 (지금 탭의 트리와 화면)')],
    [t('Ctrl+휠'), t('앱 화면 전체 확대·축소 (문서 글자만은 툴바의 − +)')],
    ['Shift+F10', t('초점이 있는 곳이나 현재 줄의 우클릭 메뉴')],
    ['Esc', t('팝업·메뉴·찾기·사용설명서 닫기, 그다음 하이라이트 끄기, 고른 줄 풀기')],
  ], 'open'],
  [t('찾기 막대'), [
    ['Enter / Shift+Enter', t('다음 / 이전 결과')],
    ['F3 / Shift+F3', t('다음 / 이전 찾은 곳 — 찾기 막대를 닫은 뒤에도 (문서에서)')],
    ['Esc', t('찾기 닫기')],
  ], 'open'],
  [t('사이드바'), [
    ['Ctrl+B', t('사이드바 보이기·숨기기 (사용설명서에서는 차례)')],
    ['Ctrl+Shift+E', t('사이드바 \'파일\' 탭의 펼친 묶음으로 — 그 안에서 다시 누르면 다음 묶음 (문서 → 코드 → 자료 → 폴더)')],
    ['Ctrl+Shift+F', t('모든 문서·코드에서 찾기 (사이드바 \'검색\')')],
    ['↑ / ↓', t('위 / 아래 항목 — 문서·코드·자료·폴더 목록')],
    ['Home / End', t('첫 / 마지막 항목')],
    ['→ / ←', t('폴더 펼치기 / 접기 — 펼친 폴더에서 → 는 첫 항목, 접힌 것에서 ← 는 위 폴더')],
    ['Enter', t('열기 — 문서는 뷰어, 코드는 읽기 화면, 자료는 기본 앱 (\'문서\' 목록의 폴더는 폴더 개요)')],
    [t('글자'), t('그 글자로 시작하는 항목으로 (같은 글자를 거듭 치면 다음 항목)')],
    ['F2', t('사이드바에서 고른 파일의 이름 바꾸기 (같은 폴더 안에서)')],
  ], 'open'],
  [t('도움말·설정'), [
    ['F1', t('사용설명서 — 따로 창에서 (그 창에서 F1 은 닫기)')],
    ['Shift+F1', t('예제 가이드 — 사용법(guide)과 Lectern 슬라이드 예제를 따로 창에서')],
    ['Ctrl+/', t('단축키 표 열기·닫기')],
    ['Ctrl+,', t('설정 창')],
  ], 'open'],
  [t('현재 줄·고르기·복사'), [
    ['↑ / ↓', t('현재 줄을 위 / 아래 줄로 — 화면이 따라감, 마지막 줄에서 멈춤 (새 줄은 Shift+Enter. 장 하이라이트 중에는 앞 장 / 다음 장)')],
    ['Home / End', t('현재 줄을 문서의 첫 줄 / 끝 줄로 (Ctrl+Home / Ctrl+End 도) — 고른 낱말이 있으면 그 줄의 첫 / 마지막 낱말')],
    ['PageUp / PageDown', t('한 화면 위 / 아래 — 현재 줄은 화면에서 같은 높이 (Shift+Space / Space 도. 장 하이라이트 중에는 앞 장 / 다음 장)')],
    ['Ctrl+↑ / Ctrl+↓', t('앞 / 뒤 제목으로 — 절 단위로 훑기')],
    ['Enter', t('현재 줄을 한 줄 편집 — F2 와 같다 (칸에서 Enter 는 저장하고 닫고 다음 줄로)')],
    ['Alt+Enter', t('제목 줄이면 그 절 접기·펴기, 링크가 있는 줄이면 그 링크 열기 (여럿이면 고르는 메뉴) — Tab 으로 간 링크·단추도')],
    ['Tab / Shift+Tab', t('현재 줄 뒤 / 앞의 링크로 — Alt+Enter 로 연다, 끝에서는 처음으로 돌고 문서 밖으로 나가지 않음 (여러 줄을 골랐으면 레벨, 문서를 떠나는 것은 F6)')],
    ['Shift+↑ / Shift+↓', t('현재 줄부터 여러 줄 고르기 — 끝 줄을 옮겨 넓히거나 줄이기 (한 줄로 줄면 현재 줄)')],
    [t('Shift+누르기 / Shift+끌기'), t('현재 줄부터 그 줄까지 고르기 — 고른 줄이 있으면 거기까지 넓히기')],
    ['Shift+Home / Shift+End', t('현재 줄부터 문서 처음 / 끝까지 고르기')],
    ['Shift+PageUp / Shift+PageDown', t('한 화면만큼 고르기')],
    ['Ctrl+Shift+↑ / Ctrl+Shift+↓', t('절 제목 / 절 끝까지 고르기 — 거듭 누르면 앞 / 뒤 절까지')],
    ['Ctrl+A', t('문서의 모든 줄 고르기 (화면은 그대로)')],
    ['Ctrl+Enter', t('줄 선택 — 하이라이트 켜기·끄기, 현재 줄이나 고른 줄만 또렷하게 (켠 동안에도 고른 줄의 키가 들음)')],
    [t('두 번 누르기'), t('그 낱말을 고르기 — 한 줄 편집 칸은 열지 않음 (편집은 F2)')],
    ['→ / ←', t('현재 줄의 첫 / 마지막 낱말 고르기 — 고른 채면 오른쪽 / 왼쪽 낱말로')],
    [t('Shift+→ / Shift+← (고른 채)'), t('낱말 단위로 넓히고 줄이기 — 고르지 않았으면 터미널로 보내기 / 위치 복사')],
    ['F8 / Shift+F8', t('다음 / 이전 형광펜으로 — 그 칠한 글을 고른다')],
    [t('B / I / S / M / F (고른 채)'), t('고른 글이나 고른 줄(줄의 글 통째)에 굵게 / 기울임 / 취소선 / 형광펜 / 글자색 — 다시 누르면 풀고, 형광펜·글자색은 거듭 누르면 다음 색. 고른 줄·고른 글에서만 (현재 줄에서는 듣지 않음)')],
    ['Ctrl+B / Ctrl+I / Ctrl+Shift+X / Ctrl+Shift+H / Ctrl+Shift+C', t('고른 글·고른 줄에 같은 서식 — 굵게 / 기울임 / 취소선 / 형광펜 / 글자색 (고른 것이 없으면 Ctrl+B 는 사이드바)')],
    ['Shift+←', t('고른 줄의 위치(@경로 a~b행) 복사')],
    ['Ctrl+C', t('고른 줄의 원문 복사 (고른 글이 없을 때)')],
  ], 'lines'],
  [t('쓰기·넣기·바꾸기 (md 문서)'), [
    ['Ctrl+H', t('찾아 바꾸기 (md 문서)')],
    ['Enter / F2', t('현재 줄을 한 줄 편집 (여러 줄을 골랐으면 Esc 로 풀고)')],
    ['Shift+Enter / Ctrl+Shift+Enter', t('현재 줄의 아래 / 위에 새 줄 — 칸 안과 같은 키')],
    ['Ctrl+Shift+;', t('현재 줄 끝에 특수 문자 — 문장 부호·화살표·단위·원 숫자 (md 문서)')],
    ['/', t('현재 줄 아래에 넣기 창 — 표·강조글·그림 같은 구성 요소 (md 문서. vi 키를 켰으면 Ctrl+Shift+/)')],
    ['.', t('현재 줄·고른 줄의 바꾸기 창 — 제목·목록·강조글로, 목록 전체를, 표·코드로 (md 문서)')],
    [t('아래의 바꾸는 키'), t('여러 줄을 골랐으면 한 번에, 현재 줄 하나면 두 번 — 처음은 그 줄을 잡기만 하고 한 번 더 누르면 바꿈 (Esc 로 그만두기)')],
    ['Alt+↑ / Alt+↓', t('고른 줄을 위 / 아래로 옮기기 — 목록은 하위 항목과 함께')],
    ['1~6 / 0 · P', t('고른 줄을 제목 1~6 / 문단으로 — 같은 키를 다시 누르면 문단 (한글 입력 상태에서도. vi 키를 켜면 고른 줄의 숫자는 횟수 — H 나 Ctrl+Alt+1~6)')],
    ['Ctrl+Alt+1~6 / Ctrl+Alt+0', t('고른 줄을 제목 1~6 / 문단으로 — 같은 수준이면 문단으로')],
    ['H', t('고른 줄의 제목 수준을 차례로 — 제목 2 → 3 → 1 → 문단')],
    ['L · - / N / T / Q', t('고른 줄을 목록 / 번호 목록 / 할 일 / 인용으로 — 다시 누르면 문단 (할 일은 목록)')],
    ['C', t('고른 줄을 강조글로 — 강조글이면 다음 종류 (참고 → 팁 → 중요 → 경고 → 주의)')],
    ['Alt+Shift+← / Alt+Shift+→', t('고른 줄의 레벨 — 제목은 하위 절까지, 목록은 하위 항목까지')],
    ['Tab / Shift+Tab', t('고른 줄의 레벨 — 목록 항목을 한 단계 안 / 밖으로 (제목은 바꾸지 않음. 현재 줄 하나면 Alt+Shift+←·→ 를 두 번)')],
    ['Delete', t('고른 줄 지우기')],
    ['Ctrl+X', t('고른 줄의 원문을 복사하고 지우기 (고른 글이 없을 때)')],
    ['Ctrl+Z', t('한 줄 편집으로 저장한 줄을 고치기 전으로 (거듭 누르면 그 앞 것도)')],
    ['Ctrl+Y', t('되돌린 것을 다시 (거듭 누르면 그 뒤 것도)')],
  ], 'change'],
  [t('한 줄 편집 (F2)'), [
    ['Enter', t('저장하고 닫기 — 원문 파일에 바로, 현재 줄은 다음 줄로 (열지는 않음, 마지막 줄이면 그대로 — 새 줄도)')],
    ['Ctrl+S', t('저장하고 닫기 — 현재 줄은 그 줄')],
    ['Shift+Enter', t('저장하고 아래에 새 줄 — 이어 쓰기, 글 가운데서는 그 자리에서 두 줄로 나눔 (읽는 화면과 같은 키)')],
    ['Esc', t('그만두기')],
    ['↑ / ↓', t('저장하고 위 / 아래 줄을 이어서 편집 (표는 같은 칸) — 글이 화면에서 꺾이면 맨 윗줄·맨 아랫줄에서, 마지막 줄에서는 멈춤 (새 줄은 Shift+Enter)')],
    ['Ctrl+Enter', t('저장하고 그 줄 선택 (하이라이트) — 읽는 화면의 Ctrl+Enter 와 같음')],
    ['Ctrl+Shift+Enter', t('위에 새 줄')],
    ['Backspace', t('줄 맨 앞에서: 같은 종류의 윗줄과 합침')],
    ['Tab / Shift+Tab', t('목록 항목을 한 단계 안 / 밖으로, 표는 옆 / 앞 칸')],
    ['Alt+↑ / Alt+↓', t('이 줄을 위 / 아래로 옮기기 — 목록은 하위 항목과 함께')],
    ['Ctrl+Shift+K', t('이 줄 지우기')],
    ['Ctrl+Shift+D', t('이 줄 복제')],
    ['/', t('빈 줄에서 넣기 창 — 제목·표·강조글·그림·주')],
    ['Ctrl+Shift+/', t('글이 있는 줄에서 넣기 창')],
    ['Ctrl+Alt+1~6 / Ctrl+Alt+0', t('이 줄을 제목 / 문단으로 — 같은 수준이면 문단으로')],
    ['Alt+Shift+← / Alt+Shift+→', t('제목·목록의 레벨 — 제목은 하위 절까지')],
    ['Ctrl+B / Ctrl+I / Ctrl+`', t('고른 글을 굵게 / 기울임 / 코드로 — 다시 누르면 풀기')],
    ['Ctrl+Shift+X', t('고른 글에 취소선 — 다시 누르면 풀기')],
    ['Ctrl+Shift+H / Ctrl+Shift+C', t('고른 글에 형광펜 / 글자색 — 거듭 누르면 다음 색, 마지막에 풀림')],
    [t('칸 안에서 우클릭'), t('서식의 선택 상자 — 서식과 색, 링크·주, 서식 풀기 (고른 글이 없으면 그 줄 통째에)')],
    ['Ctrl+K', t('링크 넣기 — 파일을 고르거나 주소를 쓴다')],
    ['Ctrl+Alt+F', t('주 달기 — 주 표시 위면 그 주를 고친다')],
    ['Ctrl+;', t('날짜 넣기 — 달력에서 고른 날을 커서 자리에 (YYYY-MM-DD)')],
    ['Ctrl+Shift+;', t('특수 문자 넣기 — 문장 부호·화살표·단위·원 숫자 같은 문자를 커서 자리에')],
    [t('앱 키'), t('F1 · Ctrl+/ · Ctrl+W · Ctrl+Tab · Alt+1~9 · Ctrl+P 같은 앱 키는 칸을 저장하고 닫은 뒤 그 일을 한다')],
  ], 'cell'],
  [t('터미널'), [
    ['Ctrl+`', t('오른쪽 터미널 열기·닫기 (` 는 숫자 1 왼쪽 키, 닫아도 셸은 계속 돎)')],
    ['Ctrl+Shift+`', t('터미널 모음 열기·닫기 (모음 안에서 Ctrl+Tab 은 다음 칸)')],
    ['Ctrl+C', t('고른 글 복사 (고른 글이 없으면 실행 중인 명령 멈춤)')],
    ['Ctrl+V', t('붙여 넣기')],
  ], 'term'],
  [t('터미널로 보내기'), [
    ['Shift+→', t('고른 줄(없으면 현재 줄)을 맨 앞 터미널(Claude Code 같은 AI 도구)에 \'@경로 a~b행\' 으로, 초점도 터미널로 (Enter 는 누르지 않음)')],
    ['Ctrl+Shift+→', t('위치를 맨 앞 터미널에 넣고 초점은 문서에 둠 (여러 곳을 이어서 넣을 때 — 낱말을 고른 채여도 보냄)')],
    ['Shift+1~5 / Ctrl+Shift+1~5', t('그 번호의 터미널에 넣기 — 초점은 터미널로 / 문서에 (터미널이 여럿일 때)')],
  ], 'term'],
  [t('편집 모드'), [
    ['Ctrl+E', t('보고 있는 문서·코드를 편집 모드로 열기·닫기')],
    ['Ctrl+S', t('저장 (편집 모드 안)')],
    ['Ctrl+F / Ctrl+H', t('찾기 / 바꾸기 (편집 모드 안)')],
    ['F3 / Shift+F3', t('다음 / 이전 찾기 (편집 모드 안)')],
    ['Ctrl+;', t('날짜 넣기 — 달력에서 고른 날을 커서 자리에 (편집 모드 안)')],
    ['Ctrl+Shift+;', t('특수 문자 넣기 — 커서 자리에 (편집 모드 안 — 칸 안과 같음)')],
    ['Ctrl+Shift+K / Ctrl+Shift+D', t('줄 지우기 / 줄 복제 (편집 모드 안 — 칸 안과 같음)')],
    ['Esc', t('편집 닫기 (저장하지 않은 것이 있으면 물음)')],
    [':w / :q / :wq', t('vi 방식일 때: 저장 / 닫기 / 저장하고 닫기 — 설정의 전체 편집 방식, Esc 는 Normal 모드로')],
  ], 'more'],
  [t('Lectern 슬라이드 (marp: true)'), [
    ['Ctrl+Shift+> / Ctrl+Shift+<', t('이 구성 요소의 글자 크기 키우기·줄이기 (슬라이드)')],
    ['Ctrl+M', t('템플릿을 골라 이 장 뒤에 새 장 (Lectern 슬라이드)')],
    ['Ctrl+D', t('이 장 복제 (슬라이드)')],
    ['Ctrl+Shift+PageUp / Ctrl+Shift+PageDown', t('이 장을 앞·뒤로 옮기기 (슬라이드)')],
    ['Shift+F5', t('발표 — 지금 보는 슬라이드부터 창 전체에 한 장씩')],
    ['→ / ←', t('다음 / 이전 슬라이드 (Space·PageDown·↓ / PageUp·↑ 도, 발표 중)')],
    ['Home / End', t('첫 / 마지막 슬라이드 (발표 중)')],
    ['N', t('발표자 노트 보이기·감추기 (발표 중)')],
    ['F', t('전체 화면 켜기·끄기 (발표 중)')],
    ['Esc', t('발표 끝내기')],
  ], 'more'],
  [t('vi 키 (설정에서 켤 때)'), [
    ['j / k', t('아래 / 위 줄 (앞에 숫자를 치면 그만큼 — 3j)')],
    ['gg / G', t('첫 줄 / 끝 줄 (숫자 다음 G 는 그 줄)')],
    ['[[ / ]]', t('앞 / 뒤 제목')],
    ['zc / zo / za', t('현재 줄이 든 절 접기 / 펴기 / 바꾸기')],
    ['zM / zR', t('모두 접기 / 모두 펴기')],
    ['zz', t('현재 줄을 화면 가운데로')],
    ['/', t('문서에서 찾기')],
    ['n / N', t('다음 / 이전 찾은 곳')],
    [':', t('줄로 가기')],
    ['i / a', t('칸 열기 — 줄 처음 / 줄 끝에 커서')],
    ['o / O', t('아래 / 위에 새 줄')],
    ['V', t('현재 줄 고르기 (다시 누르면 풀기) — 고른 뒤 j·k 넓히기, d 지우기, y 복사, > · < 레벨, J 합치기')],
    ['dd / yy', t('줄 지우기 / 원문 복사 — 담은 줄은 p · P 로 아래 / 위에 넣기 (Y 는 yy 와 같음 — Yp 로 복제)')],
    ['>> / <<', t('줄 레벨 안으로 / 밖으로 — 제목은 그 줄만 (하위 절까지는 Alt+Shift+←·→)')],
    ['u', t('되돌리기 (다시 하기는 Ctrl+Y)')],
    ['Esc', t('칸에서: 저장하고 나오기')],
  ], 'vi'],
];

/**
 * 단축키 표의 첫 탭 — 처음 익힐 스무 가지 (D157). 예제 가이드 15 의 '먼저 익힐 스무 가지'와 같은 키다 (설명은 짧게).
 * 키는 모두 SHORTCUTS 에도 있다 — 여기는 고른 것의 요약이다
 */
export const FIRST_KEYS = [
  [t('읽고 고르기'), [
    ['Ctrl+P', t('문서 열기 — 이름·제목·경로로')],
    ['Ctrl+Tab / Ctrl+W', t('다음 문서 탭 / 문서 탭 닫기')],
    ['Alt+← / Alt+→', t('뒤로 / 앞으로')],
    ['↑ / ↓', t('현재 줄을 위 / 아래로')],
    ['Ctrl+F / Ctrl+G', t('찾기 / 줄로 가기')],
    ['Shift+↑ / Shift+↓', t('여러 줄 고르기')],
    ['Ctrl+Enter', t('줄 선택 — 현재 줄이나 고른 줄만 또렷하게')],
    ['Shift+→', t('위치를 터미널의 AI 도구로 — @경로 a~b행')],
    ['Shift+← / Ctrl+C', t('위치 복사 / 원문 복사')],
    ['Ctrl+` / F6', t('터미널 열기·닫기 / 문서 → 터미널 → 사이드바 차례로 옮기기')],
  ]],
  [t('쓰고 고치기'), [
    ['Enter / F2', t('한 줄 편집 — 칸에서 Enter 는 저장하고 다음 줄로, Esc 는 그만두기')],
    ['Shift+Enter / Ctrl+Shift+Enter', t('아래 / 위에 새 줄')],
    ['/', t('넣기 창 — 표·강조글·그림 같은 구성 요소')],
    ['.', t('바꾸기 창 — 제목·목록·표·코드로')],
    ['Alt+↑ / Alt+↓', t('줄 옮기기 — 현재 줄이면 두 번')],
    ['Delete', t('줄 지우기 — 현재 줄이면 두 번')],
    ['Ctrl+Z / Ctrl+Y', t('되돌리기 / 다시')],
    ['B / M', t('굵게 / 형광펜 — 글이나 줄을 고른 채')],
    ['Esc', t('닫기 · 풀기 · 그만두기')],
    ['Ctrl+/ / F1', t('단축키 표 / 사용설명서')],
  ]],
];

/** 단축키 표의 탭 (D157) — 첫 탭은 FIRST_KEYS, 나머지는 SHORTCUTS 의 묶음을 탭 id 로 모은다 */
const KEY_TABS = [
  ['first', t('자주 쓰는 것')],
  ['open', t('열기·화면')],
  ['lines', t('고르기·복사')],
  ['change', t('쓰기·바꾸기')],
  ['cell', t('한 줄 편집')],
  ['term', t('터미널')],
  ['more', t('편집 모드·슬라이드')],
  ['vi', t('vi 키')],
];

// 백틱은 문자 참조로 — 설명서(Markdown) 표 안에서 코드 표시로 읽히지 않게
const cap = (k) => `<kbd>${esc(k).replace(/`/g, '&#96;')}</kbd>`;
/** 'Ctrl+Tab / Ctrl+Shift+Tab' → <kbd>Ctrl</kbd>+<kbd>Tab</kbd> / … (조합마다 줄바꿈하지 않는 묶음) */
const keysHtml = (keys) => keys.split(' / ').map((combo) => `<span class="combo">${combo.split('+').map(cap).join('+')}</span>`).join(' / ');

/** 설명서의 '단축키' 장에 넣을 Markdown (묶음마다 표 하나) */
function shortcutsMarkdown() {
  const first = FIRST_KEYS.map(([group, rows]) => [`${t('자주 쓰는 것')} — ${group}`, rows]);   // 처음 익힐 스무 가지부터 (D157)
  return [...first, ...SHORTCUTS].map(([group, rows]) => `### ${group}\n\n| ${t('키')} | ${t('하는 일')} |\n|---|---|\n`
    + rows.map(([keys, what]) => `| ${keysHtml(keys)} | ${esc(what).replace(/`/g, '&#96;')} |`).join('\n')).join('\n\n');   // 백틱은 Markdown 이 코드로 읽지 않게
}

// ---- 단축키 표 ------------------------------------------------------------------

const keysBox = () => $('#lec-keys');

/**
 * 설명서 속 예제 링크의 예제 안 경로 — 저장소 기준 상대경로('../../samples/guide/08-….md', GitHub 에서도 맞다)에서 'guide/08-….md'.
 * 예제 링크가 아니면 null
 */
function samplePath(href) {
  let path;
  try {
    path = decodeURIComponent(href || '');
  } catch {
    return null;
  }
  path = path.replace(/^(?:\.\.?\/)+/, '');
  return path.startsWith('samples/') && path.length > 'samples/'.length ? path.slice('samples/'.length).split('#')[0] : null;
}

let keyTab = 'first';   // 단축키 표의 지금 탭 (D157) — 열 때마다 첫 탭

export function openShortcuts() {
  $('#lec-keys-samples').hidden = !S.samples;
  keyTab = 'first';
  $('#lec-keys-find').value = '';
  drawKeys();
  keysBox().hidden = false;
  $('#lec-keys-find').focus();
}

export function closeShortcuts() {
  if (keysBox().hidden) return false;
  keysBox().hidden = true;
  return true;
}

export const toggleShortcuts = () => (closeShortcuts() || openShortcuts());

const groupHtml = (group, rows, tab) => html`<section class="keys-group" data-tab="${tab}"><h3>${group}</h3>
    <table>${rows.map(([keys, what]) => html`<tr data-find="${`${keys} ${what}`.toLowerCase()}"><th scope="row">${raw(keysHtml(keys))}</th><td>${what}</td></tr>`)}</table></section>`;

/** 탭 단추와 모든 묶음을 한 번 그린다 — 보이는 것은 drawKeys 가 고른다 (탭·찾기) */
function renderShortcuts() {
  setHtml($('#lec-keys-tabs'), KEY_TABS.map(([id, name]) => html`<button type="button" role="tab" data-tab="${id}">${name}</button>`));
  setHtml($('#lec-keys-list'), [...FIRST_KEYS.map(([group, rows]) => groupHtml(group, rows, 'first')), ...SHORTCUTS.map(([group, rows, tab]) => groupHtml(group, rows, tab)),
    html`<p class="keys-none" hidden>${t('맞는 단축키가 없습니다 — 다른 말로 찾거나 F1 사용설명서의 \'단축키\' 장을 보세요')}</p>`]);
}

/**
 * 지금 탭의 묶음만 보인다 (D157). 찾기 칸에 글이 있으면 탭과 관계없이 모든 묶음에서 그 글이 든 줄만 — 첫 탭의 요약은 겹치므로 뺀다
 */
function drawKeys() {
  const q = $('#lec-keys-find').value.trim().toLowerCase();
  for (const b of $$('#lec-keys-tabs button')) {
    const on = !q && b.dataset.tab === keyTab;
    b.classList.toggle('on', on);
    b.setAttribute('aria-selected', String(on));
    b.tabIndex = on || (q && b.dataset.tab === 'first') ? 0 : -1;
  }
  let shown = 0;
  for (const sec of $$('#lec-keys-list .keys-group')) {
    let rows = 0;
    for (const tr of sec.querySelectorAll('tr')) {
      tr.hidden = !!q && !tr.dataset.find.includes(q);
      if (!tr.hidden) rows += 1;
    }
    sec.hidden = q ? sec.dataset.tab === 'first' || !rows : sec.dataset.tab !== keyTab;
    if (!sec.hidden) shown += 1;
  }
  $('#lec-keys-list .keys-none').hidden = shown > 0;
  $('.keys-scroll').scrollTop = 0;
}

/** 탭을 고른다 — dir 이 있으면 옆 탭으로 (←→·Ctrl+Tab) */
function keysTab(id, dir = 0) {
  const ids = KEY_TABS.map(([x]) => x);
  keyTab = dir ? ids[(ids.indexOf(keyTab) + dir + ids.length) % ids.length] : id;
  $('#lec-keys-find').value = '';
  drawKeys();
}

// ---- 사용설명서 -----------------------------------------------------------------
// 여러 문서의 트리 (web/help/manual/ — index.json 이 차례, 파일 이름 앞의 번호가 트리: '2.3-문서-탭.md' 는 '2 화면' 아래).
// 문서마다 '# 제목' 과 '> 요약' 한 줄. 왼쪽은 문서 트리와 지금 문서의 절, 본문 위는 경로, 아래는 이전·다음. 흐름도(mermaid)를 그린다.
// 차례가 없으면(영어판 — 옮기기 전) 한 파일을 문서 하나짜리 트리로 보인다. 왼쪽 위 찾기 칸은 모든 문서의 제목·글에서 거른다.

const helpBox = () => $('#lec-help');
const scroller = () => $('#lec-help-scroll');
const view = () => $('#lec-help-view');
const MANUAL_DIR = '/static/help/manual/';
let loaded = null;    // 설명서를 받는 중·받은 것 (Promise) — 처음 열 때 한 번
let docs = [];        // [{file, num, depth, parent, title, summary, text}] — 차례대로
let cur = null;       // 지금 문서
let heads = [];       // 지금 문서의 절 (h2)
let query = '';       // 찾기 칸 (작은 글자)

export const manualOpen = () => !helpBox().hidden;

/** 사용설명서 왼쪽의 차례 보이기·감추기 (Ctrl+B — 설명서를 연 동안은 앱의 사이드바 대신). 감추는데 초점이 차례에 있었으면 본문으로 */
export function toggleManualNav(show = helpBox().classList.contains('nav-off')) {
  const box = helpBox();
  const inNav = box.querySelector('.help-nav').contains(document.activeElement);
  box.classList.toggle('nav-off', !show);
  $('#lec-help-navon').hidden = show;
  if (!show && inNav) $('#lec-help-scroll').focus({ preventScroll: true });
}

/** 파일 이름의 번호로 트리의 자리를 정한다 — '4.1-고치는-길-고르기.md' 는 번호 4.1, 깊이 1, 위는 4 */
function docOf(file, title, text) {
  const num = /^(\d+(?:\.\d+)*)-/.exec(file)?.[1] || '';
  return {
    file, num, title, text,
    depth: num ? num.split('.').length - 1 : 0,
    parent: num.includes('.') ? num.slice(0, num.lastIndexOf('.')) : '',
    summary: text ? (/^>\s*(.+)$/m.exec(text)?.[1] || '') : '',
  };
}

/** 차례(index.json)의 문서를 모두 받는다 — 영어판은 같은 폴더의 index.en.json 과 '….en.md' (D182). 없는 문서는 text null */
async function loadDocs() {
  const r = await fetch(`${MANUAL_DIR}${LANG === 'en' ? 'index.en.json' : 'index.json'}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const index = await r.json();
  return Promise.all(index.docs.map(async ({ file, title }) => {
    const res = await fetch(MANUAL_DIR + encodeURIComponent(file)).catch(() => null);
    return docOf(file, title, res?.ok ? await res.text() : null);
  }));
}

const label = (d) => (d.num ? `${d.num} ${d.title}` : d.title);
const docAt = (file) => docs.find((d) => d.file === file) || null;

/** 하위 문서 표 (자리 표시 '<!-- 하위 문서 -->' 에) — 번호·제목·요약 */
function childrenMarkdown(d) {
  const kids = d.num ? docs.filter((x) => x.parent === d.num) : [];
  if (!kids.length) return '';
  const cell = (s) => String(s).replace(/\|/g, '\\|');
  return `| ${t('문서')} | ${t('무엇')} |\n|---|---|\n${kids.map((k) => `| [${cell(label(k))}](${encodeURI(k.file)}) | ${cell(k.summary || '—')} |`).join('\n')}`;
}

/** 맨 위 경로 — 사용설명서 › 4 쓰기 › 4.1 고치는 길 고르기 */
function pathHtml(d) {
  if (!d.num) return '';
  const chain = [];
  for (let n = d.parent; n; n = n.includes('.') ? n.slice(0, n.lastIndexOf('.')) : '') {
    const p = docs.find((x) => x.num === n);
    if (p) chain.unshift(p);
  }
  return html`<nav class="help-path" aria-label="${t('경로')}"><span>${t('사용설명서')}</span>${chain.map((p) => html` › <a href="#" data-doc="${p.file}">${label(p)}</a>`)} › <span class="here">${label(d)}</span></nav>`;
}

/** 맨 아래 이전·다음 */
function footHtml(d) {
  const i = docs.indexOf(d);
  const prev = docs[i - 1];
  const next = docs[i + 1];
  if (!prev && !next) return '';
  return html`<nav class="help-foot" aria-label="${t('이전·다음 문서')}">${prev ? html`<a href="#" data-doc="${prev.file}" class="prev">← ${label(prev)}</a>` : html`<span></span>`}${next ? html`<a href="#" data-doc="${next.file}" class="next">${label(next)} →</a>` : ''}</nav>`;
}

/** 문서 하나를 그린다. anchor: 그 절로 (없으면 맨 위) */
async function showDoc(d, { anchor = '' } = {}) {
  cur = d;
  const body = (d.text ?? `# ${d.title}\n\n> ${t('이 문서는 아직 쓰는 중입니다.')}\n`)
    .replace('<!-- 단축키 표 -->', shortcutsMarkdown())   // i18n-ok (두 설명서에 같은 자리 표시)
    .replace('<!-- 하위 문서 -->', childrenMarkdown(d));   // i18n-ok (자리 표시)
  const { html: markup } = renderMarkdown(body, { math: false });
  setHtml(view(), [pathHtml(d), raw(window.DOMPurify.sanitize(markup)), footHtml(d)]);
  for (const a of $$('a[href]', view())) {   // 예제로 가는 링크 (예제 프로젝트의 그 문서를 연다)
    if (!samplePath(a.getAttribute('href'))) continue;
    a.classList.add('sample-link');
    a.title = t('예제 프로젝트에서 엽니다 (Shift+F1 은 예제의 첫 문서)');
  }
  decorateBlocks(view());
  heads = $$('h2', view());   // 차례에는 지금 문서의 절(h2)만
  drawToc();
  const at = anchor && findAnchor(view(), anchor);
  if (at) scrollToHead(at);
  else scroller().scrollTop = 0;
  markCurrent();
  await renderMermaid(view());   // 흐름도 — 그린 뒤 높이가 바뀌니 절로 다시
  if (at && cur === d) scrollToHead(at);
}

/** 왼쪽 차례 — 문서 트리, 지금 문서 아래에 그 절. 찾는 중이면 맞는 문서만 */
function drawToc() {
  const terms = query.split(/\s+/).filter(Boolean);
  const hit = (d) => terms.every((w) => `${label(d)}\n${d.text || ''}`.toLowerCase().includes(w));
  const shown = terms.length ? docs.filter(hit) : docs;
  const items = [];
  for (const d of shown) {
    items.push(html`<li class="doc d${terms.length ? 0 : d.depth}${d.text == null ? ' todo' : ''}${d === cur ? ' current' : ''}"><a href="#" data-doc="${d.file}">${label(d)}</a></li>`);
    if (d !== cur || terms.length) continue;
    heads.forEach((h, i) => items.push(html`<li class="sec d${d.depth}${h.tagName === 'H3' ? ' sub' : ''}"><a href="#" data-doc="${d.file}" data-h="${i}">${h.textContent}</a></li>`));
  }
  if (!shown.length) items.push(html`<li class="none">${t('맞는 문서가 없습니다')}</li>`);
  setHtml($('#lec-help-toc'), items);
}

/** 제목으로 (위에 조금 띄워서) */
function scrollToHead(h) {
  const box = scroller();
  box.scrollTop += h.getBoundingClientRect().top - box.getBoundingClientRect().top - 16;
}

/** 지금 읽는 절의 차례 (0부터, 없으면 -1) */
function currentHead() {
  const top = scroller().getBoundingClientRect().top + 80;
  let at = -1;
  heads.forEach((h, i) => { if (h.getBoundingClientRect().top <= top) at = i; });
  return at;
}

/** 차례에 지금 읽는 절 표시 */
function markCurrent() {
  const at = currentHead();
  for (const a of $$('#lec-help-toc a[data-h]')) {
    const on = Number(a.dataset.h) === at;
    a.classList.toggle('active', on);
    if (on) a.scrollIntoView({ block: 'nearest' });
  }
}

/** '#파일.md#절' · '#절' → {file, anchor} — 사용설명서 창에 넘기는 읽을 곳 */
function parseHash(hash) {
  const s = String(hash || '').replace(/^#/, '');
  const m = /^([^#]*\.md)(?:#(.*))?$/.exec(s);
  return m ? { file: m[1], anchor: m[2] ? `#${m[2]}` : '' } : { file: '', anchor: s ? `#${s}` : '' };
}

/** hash: 읽을 곳 ('#파일.md#절' — 사용설명서 창이 읽던 곳에서 연다. 창 폭이 달라 스크롤 위치로는 같은 곳이 아니다) */
export async function openManual({ hash = '' } = {}) {
  $('#lec-help-samples').hidden = !S.samples;
  closeShortcuts();
  helpBox().hidden = false;
  setFindTarget({ root: view(), scroller: scroller() });   // Ctrl+F 는 설명서 안에서
  scroller().focus({ preventScroll: true });               // 화살표·PageDown 으로 설명서를 넘기게
  loaded ??= loadDocs().then((list) => { docs = list; }).catch((e) => {
    loaded = null;   // 다음에 다시 시도
    setHtml(view(), html`<p>${t('사용설명서를 읽지 못했습니다 ({error}). Lectern 을 다시 설치하면 고쳐집니다.', { error: e.message })}</p>`);
  });
  await loaded;
  if (docs.length) {
    const { file, anchor } = parseHash(hash);
    const d = (file && docAt(file)) || cur || docs[0];
    if (d !== cur || anchor || !view().childElementCount) await showDoc(d, { anchor });
  }
  if (helpWindow) native.setTitle(`${t('사용설명서')} - Lectern`);
}

/** user: 사용자가 닫았다 (F1·Esc·✕) — 사용설명서 창이면 창을 닫는다. 다른 화면으로 가서 걷히는 것은 user 가 아니다 */
export function closeManual(opts = null) {
  if (!manualOpen()) return false;
  if (helpWindow && opts?.user === true) {   // 이벤트로 불릴 때는 그 값이 들어온다 (on('view', closeManual)) — user 일 때만 창을 닫는다
    native.closeWindow();
    return true;
  }
  helpBox().hidden = true;
  setFindTarget(null);   // 찾기 막대를 문서 화면으로 되돌린다
  $('#lec-content')?.focus({ preventScroll: true });
  return true;
}

export const toggleManual = () => (closeManual({ user: true }) || showManual());

/** 사용설명서를 보인다 (F1·명령 찾기·단축키 표의 설명서) — 따로 창이 기본 (D181). 프로젝트가 없거나(창은 프로젝트에 속한다) 창을 열지 못하면 이 창에 덮어서 */
export async function showManual() {
  if (!helpWindow && refWindows() && S.tab && await manualToWindow(null, { quiet: true })) return true;
  await openManual();
  return true;
}

/**
 * 사용설명서를 새 창에서 연다 (D181) — 문서의 새 창과 같은 독립창이라 지금 프로젝트에 속한다.
 * at: {file, anchor} — 열 곳 (없으면 지금 읽는 문서와 절). 열리면 이 창의 설명서는 걷는다
 */
export async function manualToWindow(at = null, { quiet = false } = {}) {
  if (helpWindow) return false;   // 이미 사용설명서 창
  if (!S.tab) {
    if (!quiet) toast(t('새 창은 프로젝트에 속합니다 — 먼저 폴더를 여세요'));
    return false;
  }
  const where = at || (manualOpen() && cur ? { file: cur.file, anchor: heads[currentHead()]?.id ? `#${heads[currentHead()].id}` : '' } : null);
  const hash = where ? `#${where.file}${where.anchor || ''}` : '';
  const done = await native.openWindow(soloQuery(S.tab.id, { type: 'doc', path: '', help: true, ...(hash && hash !== '#' ? { hash } : {}) }));
  if (!done) {
    if (!quiet) toast(t('새 창을 열지 못했습니다. 안 쓰는 창을 닫고 다시 하세요'), 'error');
    return false;
  }
  closeManual();
  return true;
}

/** 머리줄·차례의 우클릭 메뉴 — at: 그 문서·절에서 열 때 */
function helpMenu(e, at = null) {
  e.preventDefault();
  showMenu(e.clientX, e.clientY, helpWindow
    ? [{ label: t('사용설명서 창 닫기'), hint: 'F1', action: () => closeManual({ user: true }) }]
    : [{ label: t('새 창에서 열기'), hint: 'Ctrl+Shift+N', tip: t('설명서를 옆에 두고 문서를 봅니다'), action: () => manualToWindow(at) },
      { label: t('사용설명서 닫기'), hint: 'F1', action: () => closeManual({ user: true }) }]);
}

/** 차례·경로·이전·다음의 문서 링크 (data-doc), 본문의 다른 설명서 문서 링크 ('2.3-문서-탭.md#절') */
function goDoc(file, anchor = '') {
  const d = docAt(file);
  if (!d) return false;
  showDoc(d, { anchor }).then(() => { if (query) findText(query, { scroll: true }); });   // 찾는 중이면 그 말을 문서에서 짚는다
  return true;
}

/** 예제로 가는 길 — 사용설명서 창이면 메인 창에 맡긴다 (예제 프로젝트는 메인 창의 탭이다) */
async function toSample(path) {
  if (!helpWindow) {
    closeManual();
    closeShortcuts();
    emit('open-sample', path);   // tabs.js — 예제 프로젝트를 열고 그 문서로
    return;
  }
  try {
    await postJSON('/api/window-send', { to: '', type: 'sample', path: path || '' });
    toast(t('메인 창에서 예제를 엽니다'));
  } catch (e) {
    toast(t('메인 창으로 보내지 못했습니다: {error}', { error: e.message }), 'error');
  }
}

export function initHelp() {
  renderShortcuts();
  if (helpWindow) {   // 사용설명서 창 (D181): 첫 화면을 그린 뒤 설명서를 연다 — 화면이 바뀌면 설명서가 걷히니(main.js) 그 뒤에
    document.documentElement.classList.add('lec-help-window');
    let first = true;
    on('help-jump', (hash) => openManual({ hash }));   // 떠 있는 사용설명서 창에서 또 열면 그 장으로 (windows.py)
    on('view', () => {
      if (!first || S.view?.type !== 'overview') return;   // 탭을 고를 때의 빈 화면이 아니라 첫 화면(폴더 개요)이 그려진 뒤
      first = false;
      setTimeout(() => openManual({ hash: solo.start.hash || '' }), 0);
    });
  }
  $('#lec-help-ver').textContent = document.querySelector('meta[name="lec-version"]')?.content || '';
  $('#lec-btn-help').addEventListener('click', toggleShortcuts);
  $('#lec-keys-close').addEventListener('click', closeShortcuts);
  $('#lec-keys-tabs').addEventListener('click', (e) => {   // 단축키 표의 탭 (D157)
    const b = e.target.closest('button[data-tab]');
    if (b) keysTab(b.dataset.tab);
  });
  $('#lec-keys-find').addEventListener('input', drawKeys);
  keysBox().addEventListener('keydown', (e) => {   // ←→ 는 탭 단추에서, Ctrl+Tab·Ctrl+PageDown 은 어디서나 옆 탭으로
    const onTab = !!e.target.closest?.('#lec-keys-tabs');
    const mod = e.ctrlKey || e.metaKey;
    let dir = 0;
    if (onTab && !mod && (e.key === 'ArrowRight' || e.key === 'ArrowLeft')) dir = e.key === 'ArrowRight' ? 1 : -1;
    else if (mod && !e.altKey && (e.key === 'Tab' || e.key === 'PageDown' || e.key === 'PageUp')) dir = e.key === 'PageUp' || (e.key === 'Tab' && e.shiftKey) ? -1 : 1;
    if (!dir) return;
    e.preventDefault();
    e.stopPropagation();
    keysTab('', dir);
    if (onTab) $(`#lec-keys-tabs button[data-tab="${keyTab}"]`)?.focus();
  });
  $('#lec-keys-manual').addEventListener('click', () => {   // 단축키 표의 '사용설명서' — F1 과 같이 (따로 창이 기본)
    closeShortcuts();
    showManual();
  });
  keysBox().addEventListener('click', (e) => { if (e.target === keysBox()) closeShortcuts(); });   // 바깥을 누르면 닫기
  $('#lec-help-close').addEventListener('click', () => closeManual({ user: true }));
  $('#lec-help-navoff').addEventListener('click', () => toggleManualNav(false));
  $('#lec-help-navon').addEventListener('click', () => toggleManualNav(true));
  $('#lec-help .help-title').addEventListener('contextmenu', (e) => helpMenu(e));   // 설명서의 '탭' — 새 창에서 열기 (D181)
  $('#lec-help-toc').addEventListener('contextmenu', (e) => {   // 문서·절을 우클릭하면 그곳에서
    const a = e.target.closest('a[data-doc]');
    const h = a?.dataset.h != null ? heads[Number(a.dataset.h)] : null;
    helpMenu(e, a ? { file: a.dataset.doc, anchor: h?.id ? `#${h.id}` : '' } : null);
  });
  $('#lec-help-keys').addEventListener('click', openShortcuts);
  $('#lec-help-toc').addEventListener('click', (e) => {
    const a = e.target.closest('a[data-doc]');
    if (!a) return;
    e.preventDefault();
    if (a.dataset.h != null && cur?.file === a.dataset.doc) scrollToHead(heads[Number(a.dataset.h)]);
    else goDoc(a.dataset.doc);
  });
  $('#lec-help-find').addEventListener('input', (e) => {   // 모든 문서에서 거르기 — 제목과 글
    query = e.target.value.trim().toLowerCase();
    drawToc();
  });
  $('#lec-help-find').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.isComposing) {   // 맞는 첫 문서를 열고 그 말을 짚는다
      e.preventDefault();
      const first = $('#lec-help-toc a[data-doc]');
      if (first) goDoc(first.dataset.doc);
    } else if (e.key === 'Escape' && e.target.value) {
      e.preventDefault();
      e.stopPropagation();
      e.target.value = '';
      query = '';
      drawToc();
    }
  });
  // 설명서 속 링크: 설명서 문서(경로·이전·다음·'2.3-문서-탭.md#절'), 안의 제목(#…)과 예제 문서(../../samples/…)만 — 다른 주소로 가면 앱 창이 떠난다
  view().addEventListener('click', (e) => {
    const a = e.target.closest('a[data-doc], a[href]');
    if (!a) return;
    e.preventDefault();
    if (a.dataset.doc != null) {
      goDoc(a.dataset.doc);
      return;
    }
    const href = a.getAttribute('href');
    const sample = samplePath(href);
    if (sample) {
      toSample(sample);
      return;
    }
    let path = href;
    try {
      path = decodeURIComponent(href);
    } catch { /* 그대로 */ }
    const doc = /^(?:\.\/)?([^/#]+\.md)(#.*)?$/.exec(path);
    if (doc && goDoc(doc[1], doc[2] || '')) return;
    const target = href.startsWith('#') && findAnchor(view(), href);
    if (target) scrollToHead(target);
  });
  const toSamples = () => toSample(null);
  $('#lec-help-samples').addEventListener('click', toSamples);
  $('#lec-keys-samples').addEventListener('click', toSamples);
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
