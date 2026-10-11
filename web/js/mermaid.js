// Mermaid 다이어그램: 필요할 때만 라이브러리를 불러오고, 오류가 나면 원문을 보여 준다.

import { esc } from './util.js';
import { mermaidTheme } from './theme.js';
import { openLightbox } from './ui.js';

let loading = null;

// 라이브러리를 불러오기 전에는 문서 속 id="mermaid" 요소(예: '## Mermaid' 제목)가 window.mermaid 로 잡힌다.
// 그래서 전역이 있는지가 아니라 진짜 라이브러리인지를 본다.
const loaded = () => (typeof window.mermaid?.run === 'function' ? window.mermaid : null);

function ensureMermaid() {
  if (loaded()) return Promise.resolve(loaded());
  if (!loading) {
    loading = new Promise((resolve, reject) => {
      const fail = () => { loading = null; reject(new Error('mermaid 로드 실패')); };
      const s = document.createElement('script');
      s.src = '/static/vendor/mermaid/mermaid.min.js';
      s.onload = () => (loaded() ? resolve(loaded()) : fail());
      s.onerror = fail;
      document.head.append(s);
    });
  }
  return loading;
}

function showSource(node, message) {
  const box = document.createElement('div');
  box.className = 'mermaid-error';
  box.innerHTML = `<p>${esc(message)}</p><pre><code>${esc(node.dataset.source ?? node.textContent)}</code></pre>`;
  node.replaceWith(box);
}

/** root 안의 pre.mermaid 를 SVG로 바꾼다. root는 화면(문서 트리)에 붙어 있어야 크기 계산이 된다. */
export async function renderMermaid(root) {
  const nodes = [...root.querySelectorAll('pre.mermaid')];
  if (!nodes.length) return;
  for (const n of nodes) n.dataset.source = n.textContent;

  let mermaid;
  try {
    mermaid = await ensureMermaid();
  } catch {
    nodes.forEach((n) => showSource(n, '다이어그램 라이브러리를 불러오지 못해 원문을 표시합니다'));
    return;
  }

  mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: mermaidTheme(),
    suppressErrorRendering: true,
    fontFamily: '"Segoe UI", "Malgun Gothic", "Noto Sans KR", sans-serif',
  });
  try {
    await mermaid.run({ nodes, suppressErrors: true });
  } catch (e) {
    console.warn('mermaid', e);
  }

  for (const n of nodes) {
    const svg = n.querySelector('svg');
    if (!svg) {
      showSource(n, 'Mermaid 문법 오류가 있어 원문을 표시합니다');
      continue;
    }
    n.classList.add('mermaid-ok');
    n.title = '클릭하면 크게 봅니다';
    n.addEventListener('click', () => openLightbox(svg.cloneNode(true)));
  }
}
