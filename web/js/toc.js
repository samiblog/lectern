// 오른쪽 목차와 '지금 읽는 위치' 표시. 선택된 탭의 문서를 따른다 (목차는 칸마다 남겨 두고 탭을 고르면 그 칸의 것을 보인다)

import { S, on } from './store.js';
import { unfoldTo } from './fold.js';
import { $, $$, esc, screenRect } from './util.js';

let heads = [];
let links = [];
let active = -1;
let raf = 0;

export function updateTocVisibility() {
  const show = S.config.toc_visible !== false && heads.length > 0;
  document.documentElement.classList.toggle('toc-off', !show);
  $('#lec-btn-toc').classList.toggle('on', S.config.toc_visible !== false);
}

export function clearToc() {
  heads = [];
  links = [];
  active = -1;
  $('#lec-toc').innerHTML = '';
  updateTocVisibility();
}

/** 칸(pane)의 목차를 정한다 (root: 제목을 찾을 곳, 없으면 null). 선택된 칸이면 바로 다시 그린다 */
export function setToc(pane, root) {
  pane.tocRoot = root;
  if (pane === S.pane) showPaneToc(pane);
}

const showPaneToc = (pane) => (pane.tocRoot ? buildToc(pane.tocRoot) : clearToc());

function buildToc(view) {
  const all = $$('h1[id], h2[id], h3[id], h4[id]', view).filter((h) => !h.closest('.front-matter, .footnotes'));
  const h1s = all.filter((h) => h.tagName === 'H1');
  heads = h1s.length === 1 ? all.filter((h) => h.tagName !== 'H1') : all;   // 문서 제목(H1 하나)은 빼고
  const box = $('#lec-toc');
  if (heads.length < 2) {
    clearToc();
    return;
  }
  const top = Math.min(...heads.map((h) => +h.tagName[1]));
  box.innerHTML = `<p class="toc-head">목차</p><ul class="toc-list">${heads.map((h, i) => (
    `<li class="lv${+h.tagName[1] - top}"><a href="#${esc(h.id)}" data-i="${i}">${esc(h.textContent.trim())}</a></li>`
  )).join('')}</ul>`;
  links = $$('a', box);
  active = -1;
  spy();
  updateTocVisibility();
}

function spy() {
  raf = 0;
  if (!heads.length) return;
  const content = $('#lec-content');
  const limit = content.getBoundingClientRect().top + 96;
  let idx = 0;
  const shown = (h) => !h.classList.contains('lec-fold-hidden');   // 접힌 절 안의 제목은 위치가 0이다
  for (let i = 0; i < heads.length; i++) {
    if (!shown(heads[i])) continue;
    if (screenRect(heads[i]).top <= limit) idx = i;   // html 문서(iframe) 안의 제목도 화면 좌표로
    else break;
  }
  // 문서 끝까지 내려오면 마지막 절들은 위로 올라갈 수 없으므로, 화면에 보이는 마지막 제목을 현재 위치로 본다
  if (content.scrollTop + content.clientHeight >= content.scrollHeight - 4) {
    const bottom = content.getBoundingClientRect().bottom;
    for (let i = heads.length - 1; i > idx; i--) {
      if (shown(heads[i]) && screenRect(heads[i]).top < bottom) { idx = i; break; }
    }
  }
  if (idx === active) return;
  links[active]?.classList.remove('active');
  links[idx]?.classList.add('active');
  active = idx;
  links[idx]?.scrollIntoView({ block: 'nearest' });
}

export function initToc() {
  // 스크롤은 거품처럼 올라오지 않으므로 잡기 단계에서 듣는다. 선택된 칸(#lec-content)의 스크롤만
  document.addEventListener('scroll', (e) => {
    if (e.target === S.pane?.scroller && !raf) raf = requestAnimationFrame(spy);
  }, { capture: true, passive: true });
  on('pane', showPaneToc);
  $('#lec-toc').addEventListener('click', (e) => {
    const a = e.target.closest('a[data-i]');
    if (!a) return;
    e.preventDefault();
    const h = heads[+a.dataset.i];
    if (!h) return;
    unfoldTo(h);
    h.scrollIntoView({ block: 'start' });
  });
}
