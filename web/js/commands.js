// 명령 찾기 (D170 — Ctrl+Shift+P, 빠른 열기에서 > 로 시작): 이름을 쳐서 고르는 명령 목록과 그 단축키.
// 키가 없는 동작(인쇄·모두 펼치기·열린 문서 모두 닫기·설정 원문 보기 등)도 이름으로 찾고, 키가 있는 것은 옆에 키를 보여 쓰다 보면 익게 한다.
// 여러 모듈의 동작을 모으므로 main.js 만 이 모듈을 부른다 (다른 모듈이 부르면 import 순환이 생긴다). main.js 안의 동작은 initCommands 로 받는다.
// 키 글자는 help.js 의 SHORTCUTS 와 같게 적는다 (단축키 표가 기준).

import { S } from './store.js';
import { setCommands, openPalette } from './palette.js';
import { openFind, openReplace } from './find.js';
import { openSearch } from './search.js';
import { focusFilter } from './tree.js';
import { chooseAndOpen, closeCurrentTab, openSamples } from './tabs.js';
import { reopenDocTab, moveToWindow, closeDocTabKey, closeAllDocs, canCloseAll } from './doctabs.js';
import { askNewDocument } from './newdialog.js';
import { stepChange } from './diffmark.js';
import { foldAllHere } from './fold.js';
import { toggleLineNumbers } from './linenums.js';
import { spotButton, putKey } from './spotlight.js';
import { toggleSpread } from './spread.js';
import { step as stepText, resetText } from './textsize.js';
import { toggleNotes } from './notes.js';
import { openBoard, openEventDialog } from './work.js';
import { toggleTerminal, reattachTerminal } from './terminal.js';
import { toggleGather } from './gather.js';
import { toggleEditor } from './editor.js';
import { printButton } from './printdoc.js';
import { startPresent } from './present.js';
import { toggleManual, toggleShortcuts } from './help.js';
import { openSettings } from './settings.js';
import { openRaw } from './rawview.js';
import { solo } from './solo.js';
import { toast } from './util.js';
import { t } from './i18n.js';

const docOrCode = () => S.view?.type === 'doc' || S.view?.type === 'code';
/** 할 수 없는 곳이면(false 를 돌려주면) 까닭을 알린다 */
const or = (run, why) => () => { if (run() === false) toast(why); };

/**
 * 명령 목록 — [묶음, [[이름, 키, 할 일, 메인 창에만?]]]. local: main.js 안의 동작 {toggleSidebar, toggleToc, refresh, focusFiles}
 * @returns {{group: string, name: string, keys: string, run: () => void}[]}
 */
function list(local) {
  const groups = [
    [t('열기·탭'), [
      [t('문서·코드 열기 — 이름·제목·경로로'), 'Ctrl+P', () => openPalette()],
      [t('폴더 열기 — 새 프로젝트 탭으로'), 'Ctrl+O', chooseAndOpen, true],
      [t('새 문서 만들기…'), 'Ctrl+N', () => askNewDocument()],
      [t('새 코드 파일 만들기…'), '', () => askNewDocument(null, { kind: 'code' })],   // 만들기 창의 종류만 바꿔 연다 (D177)
      [t('새 자료 파일 만들기…'), '', () => askNewDocument(null, { kind: 'data' })],
      [t('새 폴더 만들기…'), '', () => askNewDocument(null, { kind: 'folder' })],
      [t('닫은 문서 탭 다시 열기'), 'Ctrl+Shift+T', reopenDocTab],
      [t('지금 문서를 새 창으로 옮기기'), 'Ctrl+Shift+N', () => moveToWindow()],
      [t('문서 탭 닫기'), 'Ctrl+W', closeDocTabKey],
      [t('열린 문서 모두 닫기'), '', or(() => (canCloseAll(S.tab) ? closeAllDocs() : false), t('닫을 문서 탭이 없습니다')), true],
      [t('프로젝트 탭 닫기'), 'Ctrl+Shift+W', closeCurrentTab, true],
      [t('예제 프로젝트 열기'), 'Shift+F1', () => openSamples(), true],
    ]],
    [t('찾기·옮기기'), [
      [t('지금 화면에서 찾기'), 'Ctrl+F', () => (docOrCode() ? openFind() : focusFilter())],
      [t('찾아 바꾸기 (md 문서)'), 'Ctrl+H', or(() => openReplace(), t('찾아 바꾸기는 고칠 수 있는 md 문서에서 씁니다'))],
      [t('모든 문서·코드에서 찾기'), 'Ctrl+Shift+F', openSearch],
      [t('줄로 가기'), 'Ctrl+G', or(() => (docOrCode() ? openPalette({ query: ':' }) : false), t('줄로 가기는 문서·코드 화면에서 씁니다'))],
      [t('다음 바뀐 곳'), 'F7', or(() => stepChange(1), t('바뀐 곳은 문서·코드 화면에서 봅니다'))],
      [t('이전 바뀐 곳'), 'Shift+F7', or(() => stepChange(-1), t('바뀐 곳은 문서·코드 화면에서 봅니다'))],
    ]],
    [t('보기'), [
      [t('사이드바 보이기·숨기기'), 'Ctrl+B', local.toggleSidebar],
      [t("사이드바 '파일' 탭의 목록으로"), 'Ctrl+Shift+E', local.focusFiles],
      [t('목차 보이기·숨기기'), 'Alt+O', local.toggleToc],
      [t('모두 접기'), 'Ctrl+Alt+[', or(() => foldAllHere(true), t('접을 수 있는 제목이 있는 md 문서에서 씁니다'))],
      [t('모두 펴기'), 'Ctrl+Alt+]', or(() => foldAllHere(false), t('접을 수 있는 제목이 있는 md 문서에서 씁니다'))],
      [t('줄 번호 보이기·감추기'), 'Alt+L', or(toggleLineNumbers, t('줄 번호는 Markdown 문서에서 봅니다'))],
      [t('장 하이라이트 켜기·끄기'), 'Alt+H', or(spotButton, t('장 하이라이트는 문서를 볼 때 씁니다'))],
      [t('모두 펼치기 — 열린 문서 탭들과 터미널을 창 전체에'), '', toggleSpread, true],
      [t('문서 글자 키우기'), 'Ctrl+=', () => stepText(1)],
      [t('문서 글자 줄이기'), 'Ctrl+-', () => stepText(-1)],
      [t('문서 글자 100%'), 'Ctrl+0', resetText],
      [t('다시 불러오기'), 'F5', local.refresh],
    ]],
    [t('쓰기·내보내기'), [
      [t('편집 모드 열기·닫기'), 'Ctrl+E', toggleEditor],
      [t('넣기 — 현재 줄 아래에 표·그림·강조글 같은 구성 요소'), '/', or(putKey, t('넣기는 md 문서에서 씁니다 — 문서를 열고 넣을 자리의 줄을 누른 뒤 [넣기]나 / 를 누릅니다'))],
      [t('인쇄·PDF'), '', printButton],
      [t('발표 — 지금 보는 슬라이드부터'), 'Shift+F5', or(() => (S.pane?.view.classList.contains('lec-deck') ? startPresent() : false), t('발표는 Lectern 슬라이드를 볼 때 씁니다'))],
    ]],
    [t('메모·업무·터미널'), [
      [t('메모 열기·닫기'), 'Alt+M', toggleNotes, true],
      [t('업무 현황'), 'Alt+W', openBoard, true],
      [t('일정 더하기'), 'Alt+S', () => openEventDialog(), true],
      [t('터미널 열기·닫기'), 'Ctrl+`', () => toggleTerminal(), true],
      [t('터미널 모음 열기·닫기'), 'Ctrl+Shift+`', toggleGather, true],
      [t('터미널 화면 다시 붙기 — 셸과 그 안의 프로그램은 그대로'), '', or(() => (S.tab?.term?.alive ? reattachTerminal() : false), t('다시 붙을 터미널이 없습니다 — 먼저 터미널을 여세요')), true],
    ]],
    [t('도움말·설정'), [
      [t('사용설명서'), 'F1', toggleManual],
      [t('단축키 표'), 'Ctrl+/', toggleShortcuts],
      [t('설정'), 'Ctrl+,', () => openSettings(), true],
      [t('설정 원문 보기'), '', () => openRaw(), true],
    ]],
  ];
  /** @type {{group: string, name: string, keys: string, run: () => void}[]} */
  const out = [];
  for (const [group, rows] of groups) {
    for (const [name, keys, run, mainOnly] of rows) if (!(solo && mainOnly)) out.push({ group, name, keys, run });
  }
  return out;
}

/** local: main.js 안의 동작 {toggleSidebar, toggleToc, refresh, focusFiles} */
export function initCommands(local) {
  setCommands(() => list(local));
}
