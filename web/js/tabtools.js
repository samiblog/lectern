// 탭 막대의 단추들 (D193): [개요 · 바뀜 N · 업무 카드] │ [넣기 · 편집 · 목차 · 스타일 · 내보내기] │ [AI 요청 · 메모 · 터미널].
// 열한 개라 이름은 적지 않고 아이콘만 — 마우스를 올리면(키보드로 가면) 바로 아래에 이름과 설명이 뜬다 (설명 풍선, 아래 '설명 풍선').
// 앞의 셋은 고른 프로젝트의 것 — 프로젝트 탭의 우클릭·'또 누르기'·사이드바 '최근 변경'에 숨어 있던 길을 한 번 누르기로.
// - 개요: 프로젝트 개요 (맨 위 폴더의 폴더 개요). 보는 동안 눌린 모양.
// - 바뀜 N: 밖에서(Claude 등) 고쳐졌는데 아직 열어 보지 않은 문서의 수 (tab.changed — 탭 이름 옆의 점·사이드바 '최근 변경'의 수와 같다).
//   누르면 ① 지금 문서의 바뀐 곳을 다 보지 않았으면 다음 곳(F7 과 같다), ② 아니면 가장 최근에 바뀐 안 본 문서를 연다, ③ 그것도 없으면 바뀐 곳을 처음부터.
// - 업무 카드: 이 프로젝트 맨 위의 WORK.md 를 연다. 없으면 흐리고, 누르면 '업무 카드 만들기' 창 (work.js — 만드는 것은 그 창에서 사용자가 누를 때).
// - 스타일: md 문서 스타일 창 (mdstyle.js — 상태줄의 'md 문서 스타일'과 같다).
// - 내보내기: 지금 문서를 밖으로 내는 길을 한 메뉴로 — 인쇄, PDF·html·Word 로 저장(내보내기 창, printdoc.js), Lectern 슬라이드는 pptx·html 로 전환
//   (탭 막대에 따로 있던 [인쇄] — D135 — 는 이 메뉴의 '인쇄…' 가 되었다)
//   (상태줄의 그 단추와 같다). 새로 파일을 쓰는 길은 없다 — 모두 있던 창을 연다.
// - AI 요청: 지금 문서에 쓸 수 있는 요청 글을 한 메뉴로 — 고르면 터미널에 넣는다, Enter 는 사용자가 (D51 — 'term-paste' 그 길).
//   문서 우클릭·상태줄에 흩어져 있던 것이고 새 요청 글은 '@경로' 하나뿐이다. Lectern 이 AI 도구를 실행하지 않는 것은 그대로.
// 독립창에는 프로젝트의 셋이 없다 (app.css 의 .lec-solo — 프로젝트의 것은 메인 창에). AI 요청은 있다 — 붙여 넣기는 메인 창의 터미널이 받는다 (D95).

import { S, on, emit } from './store.js';
import { showMenu } from './ui.js';
import { $, $$, toast, isMd } from './util.js';
import { t } from './i18n.js';
import { stepChange } from './diffmark.js';
import { gatherOn, leaveGather } from './gather.js';
import { openPrint, printDoc, canSavePdf, canExportHtml } from './printdoc.js';
import { aiName, reviewPrompt, voicePrompt, memoPrompt } from './aitool.js';
import { solo } from './solo.js';

const CARD = 'WORK.md';
const shown = (id) => !$(id).hidden;

/** 터미널 모음이 덮고 있으면 걷고 이 프로젝트로 */
async function uncover() {
  if (gatherOn()) await leaveGather({ tab: S.tab });
}

/** 단추 아래에 메뉴 */
function menuUnder(id, items) {
  const r = $(id).getBoundingClientRect();
  showMenu(r.left, r.bottom + 4, items);
}

// ---- 개요 ------------------------------------------------------------------------

async function openOverview() {
  if (!S.tab) return;
  await uncover();
  if (S.view?.type !== 'overview' || S.view.path) emit('open', { type: 'overview', path: '' });
}

// ---- 바뀜 ------------------------------------------------------------------------

/** 아직 열어 보지 않은 바뀐 문서 — 가장 최근에 바뀐 것부터 */
function unseen(tab = S.tab) {
  if (!tab) return [];
  return [...tab.changed].filter((p) => tab.fileMap.has(p))
    .sort((a, b) => (tab.fileMap.get(b).mtime || 0) - (tab.fileMap.get(a).mtime || 0));
}

/** 지금 문서에 남은 바뀐 곳 [모두, 아직 안 간 것] */
function placesHere() {
  if (S.view?.type !== 'doc' && S.view?.type !== 'code') return [0, 0];
  const m = S.pane?.marks;
  const n = m ? m.all.filter((el) => el.isConnected).length : 0;
  return [n, n ? n - 1 - Math.max(m.at, -1) : 0];
}

async function nextChanged() {
  if (!S.tab) return;
  await uncover();
  const [here, left] = placesHere();
  if (left > 0) {   // 이 문서의 바뀐 곳부터 끝까지
    stepChange(1);
    return;
  }
  const [path] = unseen();
  if (path) {
    emit('open', { type: 'doc', path, newTab: true });
    return;
  }
  if (here) {   // 다 보았다 — 처음 곳으로 돈다 (F7 과 같다)
    stepChange(1);
    return;
  }
  toast(t('바뀐 문서가 없습니다 — 밖에서(Claude 등) 문서가 고쳐지면 여기에 수가 뜹니다'));
}

// ---- 업무 카드 -------------------------------------------------------------------

async function openCard() {
  if (!S.tab) return;
  await uncover();
  emit('work-card', { tab: S.tab });
}

// ---- 스타일 ----------------------------------------------------------------------

function openStyle() {
  if (shown('#lec-st-mdstyle')) emit('md-style');   // 상태줄의 그 단추가 보일 때가 고를 수 있는 때 (mdstyle.js)
  else toast(t('md 문서 스타일은 md 문서에서 고릅니다 — 왼쪽에서 md 문서를 여세요'));
}

// ---- 내보내기 --------------------------------------------------------------------

/** 지금 화면에서 내보낼 수 있는 길 (없으면 빈 배열) */
function exportItems() {
  const cur = S.pane?.current;
  if (cur?.type !== 'doc') return [];
  /** @type {MenuItem[]} */
  const items = [];
  if (canSavePdf()) {
    const deck = S.pane.view.classList.contains('lec-deck');
    items.push({ label: t('PDF로 저장…'),
      tip: deck ? t('미리 보고 저장합니다 — 슬라이드 한 장이 한 쪽, 브라우저가 붙이는 날짜·주소는 없습니다')
        : t('글꼴·여백·쪽 머리를 고르고 미리 본 뒤 A4 PDF 로 저장합니다 — 브라우저가 붙이는 날짜·주소는 없습니다'),
      action: () => openPrint('pdf') },
    { label: t('인쇄…'), tip: deck ? t('미리 보고 인쇄합니다 — 슬라이드 한 장이 한 쪽') : t('글꼴·여백·쪽 머리를 고르고 미리 본 그대로 인쇄합니다 — 프린터·매수는 인쇄 창에서'),
      action: () => openPrint('print') });
  } else {
    items.push({ label: t('인쇄 / PDF로 저장…'), tip: t("프린터에서 'Microsoft Print to PDF'를 고르면 PDF로 저장"), action: printDoc });
  }
  if (canExportHtml()) {
    items.push({ label: t('html로 저장…'), tip: t('지금 화면 스타일 그대로 html 파일 하나로 — 그림·차트·수식이 파일 안에 들어갑니다'), action: () => openPrint('html') },
      { label: t('Word로 저장…'), tip: t('Word 에서 고쳐 쓸 docx 로 — 회사 Word 양식을 고를 수 있습니다'), action: () => openPrint('docx') });
  }
  // Lectern 슬라이드: 상태줄의 전환 단추와 같은 창 (pptxdialog.js·impressexport.js — 보일 때만 있다)
  if (shown('#lec-st-pptx')) items.push({ label: t('pptx 로 전환…'), tip: t('pptx 스타일을 골라 pptx 파일을 만듭니다'), action: () => $('#lec-st-pptx').click() });
  if (shown('#lec-st-html')) items.push({ label: t('html 로 전환…'), tip: t('impress.js 발표 html 파일을 만듭니다 — 브라우저로 엽니다'), action: () => $('#lec-st-html').click() });
  return items;
}

function exportMenu() {
  const items = exportItems();
  if (!items.length) {
    toast(t('문서를 볼 때 내보낼 수 있습니다 — 왼쪽에서 문서를 여세요'));
    return;
  }
  menuUnder('#lec-btn-export', items);
}

// ---- AI 요청 ---------------------------------------------------------------------

/** 지금 화면에서 쓸 수 있는 요청 — 모두 터미널에 넣기만 한다 (Enter 는 사용자가) */
function aiItems() {
  const cur = S.pane?.current;
  const path = cur?.type === 'doc' || cur?.type === 'code' ? cur.path : '';
  const ai = aiName();
  /** @type {MenuItem[]} */
  const items = [{ header: t('{ai} 에 요청 — 터미널에 넣습니다 (Enter 는 누르지 않음)', { ai }) }];
  if (path) {
    const ref = `@${path}`;
    items.push({ label: t('이 문서 가리키기 ({ref})', { ref }), tip: t('문서의 위치를 터미널에 넣습니다 — 이어서 할 말을 적으세요'), action: () => emit('term-paste', `${ref} `) });
    if (cur.type === 'doc' && isMd(path)) {
      const deck = ['lec-marp', 'lec-deck'].some((c) => S.pane.view.classList.contains(c));
      items.push({ label: t('다듬기 점검 요청'), tip: t('{ai} 에게 틀린 말과 읽기 어려운 곳을 표로 먼저 찾아 달라는 요청 — 터미널에 (Enter 는 누르지 않음)', { ai }),
        action: () => emit('term-paste', reviewPrompt(ref)) });
      if (!deck) {
        items.push({ label: t('내 문체 견본으로 보내기'), tip: t('내가 직접 쓴 글이면 — 내 문체 노트를 만들거나 보태 달라는 요청을 터미널에 (Enter 는 누르지 않음)'),
          action: () => emit('term-paste', voicePrompt(ref)) });
      }
      if (/(^|\/)work\.md$/i.test(path)) {
        items.push({ label: t('기획 메모 반영 요청'), tip: t('{ai} 에게 이 업무 카드의 기획 메모를 할 일·일정·결정에 옮겨 달라는 요청 — 터미널에 (Enter 는 누르지 않음)', { ai }),
          action: () => emit('term-paste', memoPrompt(ref)) });
      }
    }
    // 점검 목록 (상태줄의 '점검 N곳' — 그 목록에 '목록을 터미널에 붙여 넣기'가 있다)
    if (shown('#lec-st-lint')) items.push({ label: t('문서 점검 목록…'), tip: t('문서의 틀에서 고칠 곳 — 목록을 터미널에 넣을 수 있습니다'), action: () => $('#lec-st-lint').click() });
    if (shown('#lec-st-check')) items.push({ label: t('슬라이드 점검 목록…'), tip: t('넘치거나 잘못 쓴 곳 — 목록을 터미널에 넣을 수 있습니다'), action: () => $('#lec-st-check').click() });
  } else {
    items.push({ header: t('문서를 열면 그 문서에 쓸 요청이 나옵니다') });
  }
  if (!solo) items.push('-', { label: t('AI 도구 설정…'),   // 설정은 메인 창에 (D95)
    tip: t('쓰는 AI 도구, 작성 안내·글쓰기 스타일·스킬 알려 주기'), action: () => emit('open-settings', 'ai') });
  return items;
}

const aiMenu = () => menuUnder('#lec-btn-ai', aiItems());

// ---- 설명 풍선 -------------------------------------------------------------------
// 단추의 이름은 화면에 적지 않는다 — 마우스를 올리면 바로(브라우저의 title 은 1초쯤 걸린다) 단추 아래에 '이름 / 설명'.
// 글은 index.html 의 title 에서 온다 (translatePage 가 옮긴 뒤): 처음에 data-tip·aria-label 로 옮기고 title 은 뗀다 (두 번 뜨지 않게).
// 글의 ' — ' 앞이 이름 줄, 뒤가 설명 줄.

const TIP_DELAY = 120;
let tipTimer = 0;
let tipFor = null;

/** 단추의 설명을 바꾼다 (title 대신 — 설명 풍선과 읽어 주기가 같이 쓴다) */
function setTip(btn, text) {
  btn.dataset.tip = text;
  btn.setAttribute('aria-label', text);
  btn.removeAttribute('title');
  if (tipFor === btn) showTip(btn);
}

function tipBox() {
  let box = $('#lec-tabtip');
  if (!box) {
    box = document.createElement('div');
    box.id = 'lec-tabtip';
    box.setAttribute('role', 'tooltip');
    box.hidden = true;
    box.append(document.createElement('b'), document.createElement('span'));
    document.body.append(box);
  }
  return box;
}

function showTip(btn) {
  const text = btn.dataset.tip || '';
  if (!text || !btn.isConnected || !$('#lec-menu').hidden) return;
  const cut = text.indexOf(' — ');
  const box = tipBox();
  box.firstElementChild.textContent = cut < 0 ? text : text.slice(0, cut);
  box.lastElementChild.textContent = cut < 0 ? '' : text.slice(cut + 3);
  box.lastElementChild.hidden = cut < 0;
  box.hidden = false;
  const r = btn.getBoundingClientRect();
  const w = box.offsetWidth;
  box.style.left = `${Math.max(8, Math.min(r.left + r.width / 2 - w / 2, innerWidth - w - 8))}px`;
  box.style.top = `${r.bottom + 6}px`;
  tipFor = btn;
}

function hideTip() {
  clearTimeout(tipTimer);
  tipFor = null;
  const box = $('#lec-tabtip');
  if (box) box.hidden = true;
}

function bindTips() {
  const bar = $('#lec-tabbar');
  for (const btn of $$('.tabbar-btn', bar)) if (btn.title) setTip(btn, btn.title);
  bar.addEventListener('pointerover', (e) => {
    const btn = e.target.closest?.('.tabbar-btn');
    if (!btn || btn === tipFor) return;
    clearTimeout(tipTimer);
    if (tipFor) showTip(btn);   // 옆 단추로 옮기면 기다리지 않는다
    else tipTimer = setTimeout(() => showTip(btn), TIP_DELAY);
  });
  bar.addEventListener('pointerout', (e) => {
    const btn = e.target.closest?.('.tabbar-btn');
    if (btn && !btn.contains(e.relatedTarget)) hideTip();
  });
  bar.addEventListener('pointerdown', hideTip, true);   // 누르면 걷는다 — 메뉴·창을 가리지 않게
  bar.addEventListener('focusin', (e) => {   // 키보드로 왔을 때도 (마우스로 누른 초점은 아니다)
    const btn = e.target.closest?.('.tabbar-btn');
    if (btn?.matches(':focus-visible')) showTip(btn);
  });
  bar.addEventListener('focusout', hideTip);
  addEventListener('keydown', (e) => { if (e.key === 'Escape') hideTip(); }, true);
  addEventListener('blur', hideTip);
  addEventListener('resize', hideTip);
}

// ---- 모양 ------------------------------------------------------------------------

function render() {
  const tab = S.tab;
  const view = S.view;
  const over = $('#lec-btn-overview');
  const on1 = !!tab && view?.type === 'overview' && !view.path;
  over.classList.toggle('on', on1);
  over.setAttribute('aria-pressed', String(on1));
  over.disabled = !tab;

  const n = unseen(tab).length;
  const chg = $('#lec-btn-changed');
  const num = $('#lec-btn-changed-n');
  num.textContent = String(n);
  num.hidden = !n;
  chg.classList.toggle('none', !n);
  chg.disabled = !tab;
  setTip(chg, n ? t('바뀐 문서 {n}개 — 누르면 다음 바뀐 곳으로, 이 문서를 다 보았으면 다음 바뀐 문서를 엽니다', { n })
    : t('바뀜 — 밖에서 고쳐진 문서가 있으면 수가 뜹니다. 누르면 이 문서의 다음 바뀐 곳으로 (F7)'));

  const card = $('#lec-btn-card');
  const has = !!tab?.fileMap.has(CARD);
  const on2 = has && view?.type === 'doc' && view.path === CARD;
  card.classList.toggle('none', !has);
  card.classList.toggle('on', on2);
  card.setAttribute('aria-pressed', String(on2));
  card.disabled = !tab;
  setTip(card, has ? t('업무 카드 열기 — 이 프로젝트 맨 위의 WORK.md') : t('업무 카드 만들기… — 이 프로젝트 맨 위에 WORK.md 가 아직 없습니다'));
}

export function initTabTools() {
  bindTips();
  $('#lec-btn-overview').addEventListener('click', openOverview);
  $('#lec-btn-changed').addEventListener('click', nextChanged);
  $('#lec-btn-card').addEventListener('click', openCard);
  $('#lec-btn-style').addEventListener('click', openStyle);
  $('#lec-btn-export').addEventListener('click', exportMenu);
  $('#lec-btn-ai').addEventListener('click', aiMenu);
  for (const ev of ['tab', 'view', 'changed', 'tree']) on(ev, render);
  render();
}
