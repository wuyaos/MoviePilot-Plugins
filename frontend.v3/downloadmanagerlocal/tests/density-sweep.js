// Development harness only. Read-only navigation/scroll; never saves real configuration.
(async () => {
  const root = document.querySelector('#app .dm-config');
  if (!root || !window.dmlRegression) throw new Error('Open tests/config-browser.html first');
  const settle = () => window.dmlRegression.nextTick();
  const visible = el => !!el.getBoundingClientRect().width && !!el.getBoundingClientRect().height;
  const rect = el => { const r = el.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }; };
  const rows = [];
  for (const main of root.querySelectorAll('.dm-nav-item')) {
    main.click(); await settle();
    for (const tab of root.querySelectorAll('.dm-subtab')) {
      tab.click(); await settle();
      const pane = [...root.querySelectorAll('.dm-pane')].find(visible);
      if (tab.textContent.trim() === '站点规则') {
        const edit = [...pane.querySelectorAll('button')].find(el => el.textContent.trim() === '编辑')
        edit?.click(); await settle()
        const yaml = [...pane.querySelectorAll('button')].find(el => el.textContent.trim() === '编辑 YAML')
        yaml?.click(); await settle()
      }
      const scroll = root.querySelector('.dm-window');
      scroll.scrollTop = scroll.scrollHeight; await settle();
      const footer = root.querySelector('.dm-actions');
      const fields = [...pane.querySelectorAll('.v-field')].filter(visible);
      const inputs = fields.filter(el => !el.closest('.v-textarea') && !el.closest('.v-select--multiple, .v-combobox--multiple'));
      const last = [...pane.querySelectorAll('.v-input')].filter(visible).at(-1);
      const numeric = fields.filter(el => el.querySelector('input[type="number"]'));
      const help = [...pane.querySelectorAll('.dm-hint, .v-input__details, .v-messages, .v-messages__message')].filter(visible);
      rows.push({ main: main.textContent.trim(), tab: tab.textContent.trim(), host: rect(root),
        numberWidths: numeric.map(el => rect(el).w), inputHeights: inputs.map(el => rect(el).h),
        helpSignatures: [...new Set(help.map(el => { const s = getComputedStyle(el); return `${s.fontSize}/${s.fontWeight}/${s.lineHeight}`; }))],
        scrollWidth: scroll.scrollWidth, clientWidth: scroll.clientWidth,
        footer: rect(footer), scrollBottom: Math.round(scroll.getBoundingClientRect().bottom),
        lastFieldBottom: last ? Math.round(last.getBoundingClientRect().bottom) : null,
        pageOverflowX: document.documentElement.scrollWidth > innerWidth,
        unresolvedCron: pane.querySelectorAll('vcronfield').length,
      });
    }
  }
  root.querySelector('.dm-nav-item').click(); await settle();
  root.querySelector('.dm-window').scrollTop = 0;
  return JSON.stringify({ viewport: { w: innerWidth, h: innerHeight }, rows, errors: window.dmlRegression.errors });
})()
