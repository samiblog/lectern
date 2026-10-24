// 화면 문구의 언어 (D46). 서버가 설정 language(auto 면 Windows 표시 언어)로 정해 index.html 의 <html lang> 에 넣는다.
// 언어를 바꾸면 페이지를 다시 불러오므로 한 페이지 안에서는 그대로다 — 그래서 모듈 맨 위의 상수에도 t() 를 써도 된다.
//
// 문구는 한국어 문장을 그대로 열쇠로 쓴다: t('문서 열기') → 영어면 사전(lang/en.js)의 말, 한국어면 그대로.
// 값을 끼울 자리는 {이름}: t('문서 {n}개', { n }). 사전의 값이 [하나, 여럿] 이면 n 이 1 이 아닐 때 뒤의 것 (영어 복수형 — n 이 없으면 앞의 것).
// 새 문구는 t() 로 감싸고 lang/en.js 에 영어를 넣는다 — tests/test_i18n.py 가 감싸지 않은 한국어·빠진 영어·안 쓰는 영어를 잡는다.

import EN from './lang/en.js';

export const LANG = document.documentElement.lang === 'en' ? 'en' : 'ko';
const dict = LANG === 'en' ? EN : null;
const HANGUL = /[가-힣]/;
const SLOT = /\{(\w+)\}/g;

export function t(ko, values) {
  let text = dict?.[ko] ?? ko;
  // 값 n 이 없으면 하나. n 은 '1,234' 처럼 자리 쉼표를 넣은 글이어도 된다
  if (Array.isArray(text)) text = values && 'n' in values && Number(String(values.n).replace(/,/g, '')) !== 1 ? text[1] : text[0];
  return values ? text.replace(SLOT, (m, k) => (k in values ? String(values[k]) : m)) : text;
}

const ATTRS = ['title', 'placeholder', 'aria-label'];

/** index.html 에 적힌 화면 글자(글자 마디와 title·placeholder·aria-label)를 지금 언어로. translate="no" 안은 그대로 (언어 이름) */
export function translatePage(root = document.body) {
  if (!dict) return;
  const skip = (el) => el.closest('[translate="no"], script, style');
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const key = node.nodeValue.trim();
    if (HANGUL.test(key) && !skip(node.parentElement)) node.nodeValue = node.nodeValue.replace(key, t(key));
  }
  for (const el of root.querySelectorAll(ATTRS.map((a) => `[${a}]`).join(','))) {
    if (skip(el)) continue;
    for (const a of ATTRS) {
      const v = el.getAttribute(a);
      if (v && HANGUL.test(v)) el.setAttribute(a, t(v));
    }
  }
}
