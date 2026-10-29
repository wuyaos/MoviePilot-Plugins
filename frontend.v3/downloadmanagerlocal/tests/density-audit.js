// Run with agent-browser-cli exec --tab <TAB> --file <absolute path>.
// Visible DOM only; legacyFields follows dom-audit.js role precedence (including internals).
(() => {
  const root = document.querySelector('#app .dm-config') || document.querySelector('.dm-config');
  if (!root) throw new Error('Missing Config root');
  const visible = el => !!(el.getBoundingClientRect().width || el.getBoundingClientRect().height) && !!el.getClientRects().length;
  const all = [...root.querySelectorAll('*')].filter(visible);
  const rect = el => { const r = el.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }; };
  const histogram = values => values.reduce((out, value) => { out[value] = (out[value] || 0) + 1; return out; }, {});
  const unique = values => [...new Set(values)].sort((a, b) => a - b);
  const isLegacyField = el => {
    const c = typeof el.className === 'string' ? el.className : '';
    if (el.tagName === 'LABEL' || /v-label|\blabel\b|dm-field-label|dm-help|dm-hint|dm-note|text-caption|v-messages|dm-empty|v-btn|v-chip|dm-badge|v-switch|v-checkbox|v-radio|v-tab\b|dm-side-item/.test(c)) return false;
    return /v-field|v-input|v-text-field|v-select|v-textarea|v-combobox/.test(c);
  };
  const fields = all.filter(isLegacyField);
  const labels = all.filter(el => el.matches('label, .v-label, .dm-field-label'));
  const pane = [...root.querySelectorAll('.dm-pane')].find(visible);
  const inputFields = all.filter(el => el.matches('.v-text-field .v-field'));
  const numberFields = inputFields.filter(el => el.querySelector('input[type="number"]'));
  const titles = pane ? [...pane.querySelectorAll(':scope > .dm-section-title')].filter(visible) : [];
  const groups = pane ? [...pane.querySelectorAll(':scope > .dm-field-row, :scope > .v-row')].filter(visible) : [];
  const lastControl = pane ? [...pane.querySelectorAll('.v-input')].filter(visible).at(-1) : null;
  const card = root.querySelector('.dm-card');
  const footer = root.querySelector('.dm-actions');
  const scroll = root.querySelector('.dm-window');
  const help = all.filter(el => el.matches('.dm-hint, .v-input__details, .v-messages, .v-messages__message'));
  const signature = el => { const s = getComputedStyle(el); return [s.fontSize, s.fontWeight, s.lineHeight].join('/'); };
  return JSON.stringify({
    capturedAt: new Date().toISOString(), fixture: document.querySelector('#result')?.textContent,
    viewport: { w: innerWidth, h: innerHeight }, host: rect(root), card: card && rect(card),
    legacyFields: { widths: histogram(fields.map(el => rect(el).w)), x: unique(fields.map(el => rect(el).x)), count: fields.length },
    labels: { heights: histogram(labels.map(el => rect(el).h)), byState: Object.fromEntries(['floating', 'resting', 'selection'].map(state => [state, histogram(labels.filter(el => state === 'floating' ? el.classList.contains('v-field-label--floating') : state === 'resting' ? el.classList.contains('v-field-label') && !el.classList.contains('v-field-label--floating') : !el.classList.contains('v-field-label')).map(el => rect(el).h))])) },
    inputFields: inputFields.map(el => ({ ...rect(el), label: el.querySelector('label')?.textContent, numeric: !!el.querySelector('input[type="number"]') })),
    numberWidths: histogram(numberFields.map(el => rect(el).w)),
    inputHeights: histogram(inputFields.map(el => rect(el).h)),
    buttonHeights: histogram(all.filter(el => el.matches('.v-btn')).map(el => rect(el).h)),
    helpSignatures: histogram(help.map(signature)),
    sectionGaps: titles.slice(1).map(el => ({ title: el.textContent.trim(), gap: Math.round(el.getBoundingClientRect().top - el.previousElementSibling.getBoundingClientRect().bottom) })),
    fieldGroups: groups.map(el => { const s = getComputedStyle(el); return { ...rect(el), rowGap: s.rowGap, columnGap: s.columnGap, marginTop: s.marginTop }; }),
    lastFieldToCardBottom: lastControl && card ? Math.round(card.getBoundingClientRect().bottom - lastControl.getBoundingClientRect().bottom) : null,
    lastFieldGroupToCardBottom: lastControl && card ? Math.round(card.getBoundingClientRect().bottom - lastControl.closest('.dm-field, .v-col-12').getBoundingClientRect().bottom) : null,
    numericX: unique(numberFields.map(el => rect(el).x)),
    switchOrder: all.filter(el => el.matches('.v-switch .v-selection-control') && el.querySelector('label')).map(el => ({ label: el.querySelector('label').textContent, labelX: rect(el.querySelector('label')).x, switchX: rect(el.querySelector('.v-selection-control__wrapper')).x })),
    sanity: window.dmlDensitySanity,
    footer: footer && rect(footer), scroll: scroll && { ...rect(scroll), clientWidth: scroll.clientWidth, scrollWidth: scroll.scrollWidth, clientHeight: scroll.clientHeight, scrollHeight: scroll.scrollHeight },
    pageOverflowX: document.documentElement.scrollWidth > innerWidth,
    // Explicitly scroll to the last input, ensuring fixed footer does not cover it.
    errors: window.dmlRegression?.errors || [],
  });
})()
