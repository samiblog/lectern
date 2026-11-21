// md 문서 점검 (D190): 상태줄의 '점검 N곳'과 그 목록 — 고르면 그 줄로, 확실한 것은 '고치기'(lineedit.js 의 'lint-fix' — 저장, Ctrl+Z 한 걸음),
// 목록을 터미널에 붙여 넣기(Enter 없이 — D51). 목차에는 점검할 곳이 든 절에 표시한다.
// 계산은 doclint.js (DOM 없음 — 문구는 code 로 받아 여기서 옮긴다). 문서 속 그림 파일이 없는 것은 여기서 서버에 묻는다 (프로그램 자신의 서버 — 바깥 요청이 아니다).
// Lectern 슬라이드는 슬라이드 점검(slidetools.js)이 따로 있어 보지 않는다. 설정 doc_check(기본 켬)·doc_check_style(글버릇 — 기본 끔).
// 파일은 바꾸지 않는다 — 고치기는 사람이 누를 때 그 문서 하나만 (원칙 1).

import { S, on, emit } from './store.js';
import { $, $$, copyText, toast } from './util.js';
import { showMenu } from './ui.js';
import { followLine } from './spotlight.js';
import { blockOfLine } from './lineunits.js';
import { unfoldTo } from './fold.js';
import { lintDoc } from './doclint.js';
import { slugify } from './markdown.js';
import { plainText } from './terminal.js';
import { t } from './i18n.js';

/** 목록에 한 묶음씩 보일 수 — 넘으면 '그 밖에 N곳' (터미널로 보내는 목록에는 모두) */
const SHOW = 40;

const GROUPS = { A: () => t('깨진 틀'), B: () => t('보고서의 틀'), C: () => t('글버릇') };
const KIND = (k) => (k === 'table' ? t('표') : t('그림'));

/** 점검 한 곳의 한 줄 설명 */
function message(it) {
  const a = it.args;
  switch (it.code) {
    case 'front-open': return t('머리 설정의 닫는 --- 가 없어 머리 설정이 본문으로 보입니다');
    case 'fence-open': return t('닫지 않은 코드 블록 — 뒤의 글이 모두 코드로 보입니다');
    case 'math-open': return t('닫지 않은 수식 블록 — 뒤의 글이 모두 수식으로 읽힙니다');
    case 'table-sep': return t('머리행과 구분 줄의 칸 수가 달라({m}·{n}) 표가 되지 않습니다', a);
    case 'table-cells': return t('이 행은 칸이 {n}개 — 머리행은 {m}개입니다', a);
    case 'indent-code': return t('4칸 넘게 들여 써 코드 블록으로 보입니다');
    case 'list-glued': return t('번호가 {n}. 으로 시작해 목록이 되지 않고 윗줄의 글로 붙습니다', a);
    case 'bullet-mixed': return t('글머리표가 앞 항목({a})과 달라({b}) 목록이 둘로 갈립니다', a);
    case 'setext': return t('글 바로 아래의 --- 가 가로줄이 아니라 제목으로 보입니다');
    case 'callout-kind': return t('강조글 종류 [!{kind}] 를 몰라 일반 인용으로 보입니다', a);
    case 'note-missing': return t('주 [^{id}] 의 내용이 없어 글자로 남습니다', a);
    case 'note-unused': return t('주 [^{id}] 의 내용을 본문에서 쓰지 않아 보이지 않습니다', a);
    case 'link-anchor': return t('링크 #{id} 가 가리키는 제목·캡션이 없습니다', a);
    case 'image-missing': return t('그림 파일이 없습니다: {src}', a);
    case 'head-skip': return t('제목 수준을 건너뜁니다 — {a} 다음 {b}', a);
    case 'head-title': return t('제목 1 이 둘 이상입니다 — 문서 제목은 하나로 둡니다');
    case 'head-empty': return t('글이 없는 절입니다');
    case 'head-same': return t('같은 제목이 {line}행에도 있습니다 — 그 절로 가는 링크는 앞 절로 갑니다', a);
    case 'head-number': return t('제목 번호가 차례와 다릅니다');
    case 'caption-order': return a.a ? t('{word} 번호가 차례대로가 아닙니다 — {a} 다음 {b}', a) : t('{word} 번호가 1 로 시작하지 않습니다 ({b})', a);
    case 'caption-missing': return t('이 {kind}에는 캡션이 없습니다 — 이 문서의 다른 {kind}에는 있습니다', { kind: KIND(a.kind) });
    case 'source-missing': return t("이 {kind}에는 '자료:' 줄이 없습니다 — 이 문서의 다른 표·그림에는 있습니다", { kind: KIND(a.kind) });
    case 'list-loose-mixed': return t('목록의 몇 곳만 빈 줄로 띄워 목록 전체가 띄운 목록으로 보입니다');
    case 'long-para': return t('문단이 {n}자입니다 — 나눠 보세요', a);
    case 'long-sentence': return t('문장이 {n}자입니다 — 나눠 보세요', a);
    case 'long-cell': return t('표의 칸 글이 {n}자입니다 — 긴 설명은 표 밖으로', a);
    case 'hard-break': return t('줄 끝의 공백 두 칸이 보이지 않는 줄바꿈입니다');
    case 'tab-indent': return t('탭으로 들여 썼습니다 — 칸으로 바꿉니다');
    case 'head-punct': return t('제목 끝에 {c} 가 있습니다', a);
    default: return it.code;
  }
}

/** 고치기 단추의 설명 */
function fixTip(it) {
  switch (it.fix?.kind) {
    case 'close-front': return t('키 줄 뒤에 닫는 --- 를 넣습니다');
    case 'close-fence': return t('다음 제목 앞(없으면 문서 끝)에 닫는 줄을 넣습니다');
    case 'renumber': return t('1 부터 번호를 매깁니다');
    case 'blank-before': return t('위에 빈 줄을 넣습니다');
    case 'same-marker': return t('앞 항목의 글머리표로 맞춥니다');
    case 'callout': return t('[!{to}] 로 바꿉니다', it.args);
    case 'heading-numbers': return t('번호가 있는 제목의 번호를 차례대로 — 번호 없는 제목은 그대로');
    case 'caption-numbers': return t('캡션 번호를 차례대로 — 참조 링크도');
    case 'caption': return t('빈 캡션 줄을 넣고 번호를 차례대로 맞춥니다');
    case 'source': return t("아래에 빈 '자료:' 줄을 넣습니다");
    case 'trim': return t('걷어 냅니다');
    case 'spaces': return t('탭을 같은 폭의 칸으로 바꿉니다');
    default: return '';
  }
}

/** 지금 화면이 점검하는 md 문서인지 — 코드 화면·Lectern 슬라이드(문서로 보기도)·보기만 하는 화면 아님 */
const docView = (pane) => {
  const v = pane?.view;
  return !!v && v.classList.contains('md-body') && !v.classList.contains('code-view') && !v.classList.contains('lec-marp') && !!v.dataset.docPath && !!pane.source?.lines;
};

/** 문서 속 그림 파일이 있는지 — 그릴 때마다 묻는다 (그림을 나중에 넣어도 알게). 한 문서 안의 같은 주소는 한 번 */
async function missingImages(view) {
  const out = [];
  const seen = new Map();
  for (const img of $$('img', view)) {
    const src = img.getAttribute('src') || '';
    if (!src.startsWith('/doc/') && !src.startsWith(`${location.origin}/doc/`)) continue;
    const key = src.replace(/\?v=\d+$/, '');
    if (!seen.has(key)) seen.set(key, fetch(src, { method: 'HEAD' }).then((r) => r.ok, () => true));
    if (await seen.get(key)) continue;
    const line = Number(/^\d+/.exec(img.closest('[data-lines]')?.dataset.lines || '')?.[0]);
    if (!line) continue;
    let name = key.split('/').pop() || '';
    try {
      name = decodeURIComponent(name);
    } catch { /* 그대로 */ }
    out.push({ line, group: 'A', code: 'image-missing', args: { src: name } });
  }
  return out;
}

/** 화면(pane)을 점검한다 — 그린 뒤에, 그리는 일을 막지 않게. 그사이 다시 그렸으면 앞의 것은 버린다 (칸마다) */
function check(pane) {
  const mine = (pane.lintGen = (pane.lintGen || 0) + 1);
  const gen = () => pane.lintGen;
  setTimeout(async () => {
    if (mine !== gen()) return;
    if (!docView(pane) || S.config?.doc_check === false) {
      pane.lint = null;
      if (pane === S.pane) show();
      return;
    }
    const path = pane.view.dataset.docPath;
    const issues = lintDoc(pane.source.lines, { slug: slugify, style: S.config?.doc_check_style === true, emptyOk: /(^|\/)WORK\.md$/i.test(path) });
    pane.lint = { path, issues };
    if (pane === S.pane) show();
    const images = await missingImages(pane.view);
    if (mine !== gen() || !images.length || pane.lint?.path !== path) return;
    pane.lint = { path, issues: [...issues, ...images].sort((x, y) => x.line - y.line) };
    if (pane === S.pane) show();
  });
}

const issuesNow = () => (docView(S.pane) && S.pane.lint?.path === S.pane.view.dataset.docPath ? S.pane.lint.issues : []);

/** 상태줄과 목차의 표시를 지금 화면에 맞춘다 */
function show() {
  const issues = issuesNow();
  const btn = $('#lec-st-lint');
  btn.hidden = !issues.length;
  btn.querySelector('span').textContent = t('점검 {n}곳', { n: issues.length });
  markToc(issues);
}

/** 목차: 점검할 곳이 든 절의 제목에 표시 (슬라이드 목차의 '●'와 같게) */
function markToc(issues) {
  if (!docView(S.pane)) return;   // 슬라이드 목차의 표시(slides.js 의 점검)는 그대로
  const view = S.pane?.view;
  const links = $$('#lec-toc .toc-list a[data-i]');
  const starts = links.map((a) => {
    let id = (a.getAttribute('href') || '').slice(1);
    try {
      id = decodeURIComponent(id);
    } catch { /* 그대로 */ }
    const head = id && view ? view.querySelector(`#${CSS.escape(id)}`) : null;
    return Number(/^\d+/.exec(head?.dataset.lines || '')?.[0]) || 0;
  });
  links.forEach((a, i) => {
    const from = starts[i];
    const to = starts.slice(i + 1).find((n) => n > from) ?? Infinity;
    a.parentElement.classList.toggle('warn', !!from && issues.some((it) => it.line >= from && it.line < to));
  });
}

/** 터미널에 넣을 한 줄 */
function listText(path, issues) {
  const rows = issues.map((it) => t('{line}행 {text}', { line: it.line, text: plainText(message(it)).replace(/\s+/g, ' ') }));
  const ask = t('@{path} 문서 점검 결과입니다. 고쳐 주세요: {rows}', { path, rows: rows.join(' / ') });
  return S.writingGuide ? `${ask} ${t('문서는 Lectern 작성 안내({path})를 따라 주세요.', { path: S.writingGuide })}` : ask;
}

/** 그 줄로 — 접힌 절·머리 설정 안이면 편다 */
function goLine(pane, line) {
  const el = blockOfLine(pane.view, line);
  emit('jump');
  if (el) unfoldTo(el);
  followLine(line);
}

/** 점검 목록 — 상태줄의 '점검 N곳', 명령 찾기의 '문서 점검' */
export function openDocCheck() {
  const pane = S.pane;
  const issues = issuesNow();
  if (!issues.length) {
    toast(docView(pane) ? t('이 문서에는 점검할 곳이 없습니다') : t('문서 점검은 md 문서에서 합니다 (Lectern 슬라이드는 상태줄의 점검)'));
    return;
  }
  /** @type {MenuItem[]} */
  const items = [];
  for (const g of ['A', 'B', 'C']) {
    const part = issues.filter((it) => it.group === g);
    if (!part.length) continue;
    if (items.length) items.push('-');
    items.push({ header: GROUPS[g]() });
    for (const it of part.slice(0, SHOW)) {
      items.push({
        label: t('{line}행 — {text}', { line: it.line, text: message(it) }),
        action: () => goLine(pane, it.line),
        ...(it.fix ? { side: { label: t('고치기'), tip: fixTip(it), action: () => emit('lint-fix', { pane, line: it.line, fix: it.fix.apply }) } } : {}),
      });
    }
    if (part.length > SHOW) items.push({ header: t('그 밖에 {n}곳 — 터미널로 보내는 목록에는 모두', { n: part.length - SHOW }) });
  }
  const text = listText(pane.view.dataset.docPath, issues);
  items.push('-',
    { label: t('목록을 터미널에 붙여 넣기'), tip: t('터미널에 (Enter 는 누르지 않음)'), action: () => emit('term-paste', text) },
    { label: t('목록 복사'), action: () => copyText(text).then(() => toast(t('복사했습니다'))) });
  const r = $('#lec-st-lint').getBoundingClientRect();
  showMenu(r.left, r.top, items);
}

export function initDocCheck() {
  $('#lec-st-lint').addEventListener('click', openDocCheck);
  on('rendered', (pane) => check(pane));
  on('pane', () => {
    if (S.pane && docView(S.pane) && S.pane.lint?.path !== S.pane.view.dataset.docPath) check(S.pane);
    else show();
  });
  on('toc-built', () => markToc(issuesNow()));
  on('doc-check', () => {   // 설정 창 (doc_check·doc_check_style)
    for (const pane of S.panes) check(pane);
  });
}
