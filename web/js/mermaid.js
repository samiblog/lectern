// Mermaid 다이어그램: 필요할 때만 라이브러리를 불러오고, 오류가 나면 원문을 보여 준다.

import { html, setHtml } from './html.js';
import { styleOf, colorsOf, mermaidConfig, mermaidSource, decorateMermaid } from './diagramstyles.js';
import { openLightbox } from './ui.js';
import { t } from './i18n.js';

let loading = null;

// 라이브러리를 불러오기 전에는 문서 속 id="mermaid" 요소(예: '## Mermaid' 제목)가 window.mermaid 로 잡힌다.
// 그래서 전역이 있는지가 아니라 진짜 라이브러리인지를 본다.
const loaded = () => (typeof window.mermaid?.run === 'function' ? window.mermaid : null);

function ensureMermaid() {
  if (loaded()) return Promise.resolve(loaded());
  if (!loading) {
    loading = new Promise((resolve, reject) => {
      const fail = () => { loading = null; reject(new Error(t('mermaid 로드 실패'))); };
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
  box.className = 'diagram-error';
  if (node.dataset.lines) box.dataset.lines = node.dataset.lines;   // 본문 우클릭 메뉴의 원문 복사용
  setHtml(box, html`<p>${message}</p><pre><code>${node.dataset.source ?? node.textContent}</code></pre>`);
  node.replaceWith(box);
}

let drawing = Promise.resolve();   // 그리기 줄 (renderMermaid)

/** 도해 스타일 번호별로 묶어 그린다 — 원문에 강조 표시의 classDef 를 붙이고, 그린 뒤 다듬는다 (diagramstyles.js) */
async function drawGroups(mermaid, nodes, marks) {
  const groups = new Map();   // '모양|색' → 그 그림들
  for (const n of nodes) {
    const style = styleOf(n.dataset.source, 'mermaid', marks);
    const colors = colorsOf(n.dataset.source, 'mermaid', marks);
    n.textContent = mermaidSource(n.dataset.source, style, colors);   // 강조 표시의 classDef 를 붙인 것 — 원문 파일은 그대로
    const key = `${style}|${colors}`;
    if (!groups.has(key)) groups.set(key, { style, colors, nodes: [] });
    groups.get(key).nodes.push(n);
  }
  for (const { style, colors, nodes: group } of groups.values()) {
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      ...mermaidConfig(style, colors),   // theme, themeVariables (문서 스타일의 색 + 색 조합) + 그 번호의 look·flowchart·themeCSS
      suppressErrorRendering: true,
      fontFamily: '"Segoe UI", "Malgun Gothic", "Noto Sans KR", sans-serif',
    });
    try {
      await mermaid.run({ nodes: group, suppressErrors: true });
    } catch (e) {
      console.warn('mermaid', e);
    }
    for (const n of group) {
      const svg = n.querySelector('svg');
      if (!svg) continue;
      n.dataset.diagramStyle = String(style);
      n.dataset.diagramColors = String(colors);
      try {
        decorateMermaid(svg, style, colors);
      } catch (e) {
        console.warn('diagram style', e);
      }
    }
  }
}

/**
 * root 안의 pre.mermaid 를 SVG로 바꾼다. root는 화면(문서 트리)에 붙어 있어야 크기 계산이 된다.
 * marks: 문서의 기본 도해 스타일·색 조합 {style, colors} (D213 — '<!-- 도해: 스타일 8 · 색 2 -->', 0 이면 설정)
 */
export async function renderMermaid(root, marks = null) {
  const nodes = [...root.querySelectorAll('pre.mermaid')];
  if (!nodes.length) return;
  for (const n of nodes) n.dataset.source = n.textContent;

  let mermaid;
  try {
    mermaid = await ensureMermaid();
  } catch {
    nodes.forEach((n) => showSource(n, t('다이어그램 라이브러리를 불러오지 못해 원문을 표시합니다')));
    return;
  }

  // 도해 스타일(D212)마다 따로 그린다 — 번호마다 initialize (그때마다 기본 설정에서 다시 시작한다).
  // initialize 는 전역이므로 다른 칸·설정 창의 미리보기와 섞이지 않게 차례로 (drawing)
  const job = drawing.then(() => drawGroups(mermaid, nodes, marks));
  drawing = job.catch(() => {});
  await job;

  for (const n of nodes) {
    const svg = n.querySelector('svg');
    if (!svg) {
      showSource(n, t('Mermaid 문법 오류가 있어 원문을 표시합니다'));
      continue;
    }
    n.classList.add('mermaid-ok');
    n.title = t('누르면 크게 봅니다');
    n.addEventListener('click', () => openLightbox(svg.cloneNode(true)));
  }
}
