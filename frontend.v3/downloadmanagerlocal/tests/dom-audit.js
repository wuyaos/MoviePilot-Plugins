// DML 样式审计：dump 活页面里插件 UI 的 DOM + computed style + 几何异常。
// 用法（在浏览器页内执行，返回 JSON 字符串）：
//   agent-browser-cli exec --tab <TAB> --file frontend.v3/downloadmanagerlocal/tests/dom-audit.js
// 根选择器按优先级取第一个存在的：.dm-config（配置弹窗）/ .dm-card（数据页）。
(async () => {
  const ROOTS = ['.dm-config', '.dm-page', '.dm-card'];
  const MAX_NODES = 1500;
  const root = ROOTS.map(s => document.querySelector(s)).find(Boolean);
  if (!root) {
    return JSON.stringify({ ok: false, reason: 'plugin-root-not-found', tried: ROOTS, overlays: document.querySelectorAll('.v-overlay--active').length });
  }
  const context = root.classList.contains('dm-config') ? 'config' : 'page';

  const px = v => (v === undefined || v === null ? '' : String(v));
  const styleKeys = ['fontSize', 'fontWeight', 'lineHeight', 'color', 'backgroundColor', 'paddingTop', 'paddingLeft', 'marginTop', 'marginBottom', 'borderRadius', 'borderTopWidth', 'height', 'letterSpacing'];

  function classify(el) {
    const tag = el.tagName.toLowerCase();
    const cls = typeof el.className === 'string' ? el.className : '';
    const c = ' ' + cls + ' ';
    if (/^h[1-6]$/.test(tag)) return 'title';
    if (/\b(dm-card-title|dm-title|dm-header-title|v-card-title|v-toolbar-title)\b/.test(c)) return 'title';
    if (/\b(dm-section-title|dm-block-title|dm-panel-title|dm-group-title)\b/.test(c)) return 'section';
    if (tag === 'th') return 'table-head';
    if (tag === 'td') return 'table-cell';
    if (/v-label|\blabel\b|dm-field-label/.test(c) || tag === 'label') return 'label';
    if (/dm-help|dm-hint|dm-note|text-caption|v-messages|dm-empty/.test(c)) return 'help';
    if (/v-btn/.test(c)) return 'button';
    if (/v-chip|dm-badge/.test(c)) return 'badge';
    if (/v-switch|v-checkbox|v-radio/.test(c)) return 'switch';
    if (/v-tab\b|dm-side-item/.test(c)) return 'tab';
    if (/v-field|v-input|v-text-field|v-select|v-textarea|v-combobox/.test(c)) return 'field';
    if (/v-table|v-data-table|dm-table/.test(c)) return 'table';
    if (/dm-module-card|dm-stat|dm-card\b/.test(c)) return 'card';
    return 'other';
  }

  function classSig(el) {
    const cls = typeof el.className === 'string' ? el.className : '';
    return cls.split(/\s+/).filter(Boolean).sort().slice(0, 6).join('.');
  }

  const nodes = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
  let el = root;
  while (el && nodes.length < MAX_NODES) {
    const rect = el.getBoundingClientRect();
    if (rect.width > 0 || rect.height > 0) {
      const cs = getComputedStyle(el);
      const styles = {};
      for (const k of styleKeys) styles[k] = px(cs[k]);
      const ownText = Array.from(el.childNodes)
        .filter(n => n.nodeType === 3)
        .map(n => n.textContent.trim())
        .join(' ')
        .replace(/\s+/g, ' ')
        .slice(0, 80);
      const issues = [];
      if (el.scrollWidth - el.clientWidth > 2 && cs.overflowX !== 'visible' && cs.overflowX !== 'auto' && cs.overflowX !== 'scroll') issues.push('content-clipped-x');
      if (el.scrollHeight - el.clientHeight > 2 && cs.overflowY === 'hidden') issues.push('content-clipped-y');
      if (rect.right > window.innerWidth + 1) issues.push('overflows-viewport');
      if (tagNeedsText(el) && ownText && el.scrollWidth > el.clientWidth + 2) issues.push('text-truncated');
      nodes.push({
        role: classify(el),
        tag: el.tagName.toLowerCase(),
        sig: classSig(el),
        text: ownText,
        rect: { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) },
        styles,
        issues,
      });
    }
    el = walker.nextNode();
  }

  function tagNeedsText(node) {
    const t = node.tagName.toLowerCase();
    return t === 'span' || t === 'div' || t === 'p' || t === 'label' || t === 'td';
  }

  function count(sel) {
    try {
      return root.querySelectorAll(sel).length;
    } catch (e) {
      return -1;
    }
  }

  return JSON.stringify({
    ok: true,
    capturedAt: new Date().toISOString(),
    context,
    root: root.className,
    pagePresent: !!document.querySelector('.dm-page'),
    configPresent: !!document.querySelector('.dm-config'),
    version: (document.querySelector('script[src*="remoteEntry.js"]') || {}).src || '',
    viewport: { w: window.innerWidth, h: window.innerHeight },
    counts: {
      nodes: nodes.length,
      buttons: count('.v-btn'),
      fields: count('.v-field'),
      switches: count('.v-switch'),
      tables: count('table'),
      cards: count('.dm-module-card'),
      tabs: count('.v-tab, .dm-side-item'),
    },
    nodes,
  });
})()
