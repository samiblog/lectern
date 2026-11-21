// Lectern 의 데이터 모양. 개발할 때 tsc 만 읽고 앱에는 들어가지 않는다 (D89).
// tests/test_rules.py 의 test_types 가 돌린다. web/js 의 JSDoc 이 이 이름들을 쓴다.

export {};

declare global {
  // 앱이 부르는 vendor 전역과 pywebview. 이름을 틀리면 잡히도록 하나씩 적는다
  interface Window {
    pywebview: any;
    DOMPurify: any;
    hljs: any;
    katex: any;
    markdownit: any;
    markdownItAnchor: any;
    markdownitFootnote: any;
    markdownitTaskLists: any;
    mermaid: any;
    CodeMirror: any;
    Terminal: any;
    FitAddon: any;
    Unicode11Addon: any;
    vega: any;
    vegaLite: any;
    echarts: any;
    Plotly: any;
    Viz: any;
  }

  // DOM 은 엄하게 보지 않는다. 이 점검이 잡으려는 것은 앱의 데이터 모양이고,
  // querySelector 와 이벤트 대상마다 형을 밝히면 주석만 늘어난다
  interface Element {
    dataset: DOMStringMap;
    content: any;
    contentDocument: Document | null;
    focus(options?: FocusOptions): void;
  }
  interface EventTarget {
    classList: DOMTokenList;
    closest(selector: string): any;
    hasAttribute(name: string): boolean;
    textContent: string | null;
  }

  /** 칸의 화면 (nav.js). 선택된 칸이면 S.view 와 같다 */
  interface PaneView {
    type: string;
    path: string;
    hash?: string;
    line?: number;
    sheet?: number;
  }

  /** 화면을 그릴 때 받는 값 (showDoc·showCode 등). scrollTop 은 바꿔 끼우기 직전에 읽을 함수일 수 있다 */
  interface ShowOptions {
    hash?: string;
    line?: number;
    sheet?: number;
    scrollTop?: number | (() => number);
  }

  /** 문서 칸 (panes.js 의 makePane). 뒤쪽은 다른 모듈이 나중에 붙이는 것 */
  interface Pane {
    /** 펼친 블록 (lineblock.js, D112) */
    unfold?: { path: string; line?: number; a?: number; b?: number; front?: boolean; raw?: boolean; values?: boolean; focus?: { r: number; c: number }; panel?: HTMLElement | null; refocus?: () => void } | null;
    el: HTMLElement;
    tab: Tab | null;
    scroller: HTMLElement;
    view: any;
    current: PaneView | null;
    history: any[];
    hIndex: number;
    wanted: any;
    scrollPos: Map<string, number>;
    pending: number;
    missedRefresh: boolean;
    dragMissed: boolean;
    redrawing: number;
    drawing: Promise<unknown> | null;
    stale: boolean;
    renderId: number;
    tocRoot: HTMLElement | null;
    status: { path?: string; info?: string };
    source: { path: string; lines: string[] } | null;
    marks: { all: any[]; sigs: string[]; idx: number[]; count: number; list: any[]; at: number; pos: number };

    coming?: any;
    codeStamp?: any;
    deferred?: any;
    editor?: any;
    here?: any;
    lineEdit?: any;
    lineEditHold?: any;
    lineEditMissed?: any;
    opening?: any;
    tocLimit?: any;
    tocOutline?: any;
    used?: any;
    /** md 문서 점검의 결과 (doccheck.js — D190) */
    lint?: { path: string; issues: LintIssue[] } | null;
    lintGen?: number;
  }

  /** 프로젝트 탭 (tabs.js 의 makeTab). 뒤쪽은 다른 모듈이 나중에 붙이는 것 */
  interface Tab {
    id: string;
    root: string;
    name: string;
    watch: string;
    seq: number;
    readonly: boolean;
    position: any;
    tree: any[];
    files: any[];
    fileMap: Map<string, any>;
    dirs: Set<string>;
    changed: Set<string>;
    open: Set<string>;
    lastSync: any;
    treeLoaded: boolean;
    /** 트리를 받은 횟수 — 뒤에서 받는 제목 있는 트리가 그사이의 새 트리를 덮지 않게 (project.js, D140) */
    treeGen?: number;
    /** 문서 속 형광펜·할 일 (GET /api/marks — tree.js, D143) */
    marks?: { data: Map<string, any> | null; loading: Promise<any> | null; stale: boolean; error?: string | null };
    loaded: boolean;
    loading: Promise<any> | null;
    side: any;
    recent: any;
    others: any;
    pane: Pane;
    panes: Pane[];

    basket?: any;
    behindLast?: Pane;
    behindOf?: Pane;
    closedDocs?: any[];
    notes?: any;
    closing?: any;
    partsCache?: any;
    restoring?: any;
    term?: any;
    terms?: any[];
    /** 쌓은 터미널 칸의 무게 (번호 → 높이 비율 — D137, 메모리에만. null 이면 균등) */
    termWeights?: Map<number, number> | null;
  }

  /** 앱 상태 (store.js). root 부터는 선택된 탭의 값을 그대로 읽고 쓴다 */
  interface AppState {
    mode: string;
    sep: string;
    config: Record<string, any>;
    tabs: Tab[];
    tab: Tab | null;
    panes: Pane[];
    pane: Pane | null;
    view: PaneView | null;
    samples: string | null;
    writingGuide: string;
  slidesGuide: string;
  skillsDir: string;
  writingStyle: string;
  /** Lectern 에 든 글쓰기 스타일 넷 (D161) */
  writingStyles: { id: string; file: string; path: string; name: string; description: string }[];
  /** 새 글쓰기 스타일 만들기 안내의 경로 (D161) */
  styleGuide: string;
  reviewGuide: string;
  voiceGuide: string;

    root: string | null;
    name: string;
    watch: string;
    tree: any[];
    files: any[];
    fileMap: Map<string, any>;
    dirs: Set<string>;
    changed: Set<string>;
    open: Set<string>;
    seq: number;
    lastSync: any;
  }

  /** 화면에 넣을 HTML (html.js) — html`` 의 결과와 그 배열. 없을 때는 빈 글 */
  type Markup = import('../../web/js/html.js').Safe | '' | Markup[];

  /** 우클릭 메뉴의 한 줄 (ui.js 의 showMenu). '-' 는 구분선 */
  type MenuItem = '-' | { header: string } | {
    label: string;
    action: () => any;
    hint?: string;
    tip?: string;
    term?: string;
    icon?: Markup;
    current?: boolean;
    /** 항목 오른쪽의 곁단추 (문서 점검의 '고치기' — D190) */
    side?: { label: string; tip?: string; action: () => any };
  };

  /** md 문서 점검의 한 곳 (doclint.js — D190). 문구는 화면(doccheck.js)이 code 로 옮긴다 */
  interface LintIssue {
    line: number;
    group: 'A' | 'B' | 'C';
    code: string;
    args: Record<string, any>;
    fix?: { kind: string; apply: (lines: string[]) => string[] | null };
  }

  /** 표 영역 (tabledata.js 의 findRegions) */
  interface TableRegion {
    r0: number;
    c0: number;
    headers: string[];
    rows: string[][];
    titles: string[];
    [key: string]: any;
  }

  /** 데이터 보기의 표 상태 (csvview.js 의 view.csv) */
  interface CsvState {
    grid: { rows: string[][]; lines: number[][]; merges: number[][] };
    key: string;
    root: any;
    mem: any;
    stats: boolean;
    header: boolean;
    rows: string[][];
    lines: number[][];
    cols: any[];
    baseLetter: any;
    baseTitle: any;
    letter: any;
    titleOf: any;
    calcs: any[];
    calcBlocked: boolean;
    regions: TableRegion[];
    region: TableRegion | null;
    pick: any;
    time: any;
    width: number;
    plain?: boolean;
    [key: string]: any;
  }
}
