import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { pathToFileURL } from 'node:url'
import test from 'node:test'
import { compileStyle, parse } from '@vue/compiler-sfc'
import postcss from 'postcss'
import { loadSfc, render } from './helpers/load-sfc.mjs'

// Run the rendered SFC and its real CSS in a layout engine, not a CSS-string assertion.
const Header = await loadSfc('ModuleHeader.vue')
const read = file => fs.readFileSync(new URL(file, import.meta.url), 'utf8')
const header = parse(read('../src/components/ModuleHeader.vue')).descriptor
const headerCss = compileStyle({ source: header.styles[0].content, filename: 'ModuleHeader.vue', id: 'layout' })
assert.deepEqual(headerCss.errors, [])
const page = parse(read('../src/components/Page.vue')).descriptor
const gridSelectors = ['.dm-overview-cards', '.dm-overview-card']
const gridCss = postcss.parse(page.styles.map(style => style.content).join('\n')).nodes
  .filter(node => node.type === 'rule' && gridSelectors.includes(node.selector))
  .map(node => node.toString()).join('\n')
const chrome = process.env.CHROME_BIN || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome',
].find(file => fs.existsSync(file))

test('真实浏览器布局：206px 徽标行换行，超量/超长徽标不裁切且同排卡等高', async () => {
  assert.ok(chrome, 'Layout regression requires Chrome/Chromium; set CHROME_BIN to its executable')
  const badges = [
    { label: '受管种子', value: 0 }, { label: '上传中', value: 0 },
    { label: '当前上传', value: '0.0 KiB/s' }, { label: '已分配额度', value: '0 KiB/s' },
    { label: '累计成功', value: '1234567890'.repeat(8) },
  ]
  const many = await render(Header, { title: '上传限速', enabled: true, badges })
  const few = await render(Header, { title: '转移做种', badges: [{ label: '在途', value: '—' }] })
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'dml-header-layout-'))
  try {
    const fixture = path.join(dir, 'layout.html')
    fs.writeFileSync(fixture, `<!doctype html><meta charset="utf-8"><style>
${read('../src/styles/dm-tokens.css')}\n${headerCss.code}\n${gridCss}
.dm-page { --v-border-color: 0, 0, 0; --v-border-opacity: 0.12; }
.dm-overview-cards { grid-template-columns: repeat(2, 240px); }
.dm-module-header { width: 206px; max-width: 100%; }
</style><div class="dm-page"><div class="dm-overview-cards"><article class="dm-overview-card">${many}</article><article class="dm-overview-card">${few}</article></div></div>
<pre id="result"></pre><script>
const cards = [...document.querySelectorAll('.dm-overview-card')];
const row = cards[0].querySelector('.dm-module-badges');
const badges = [...row.children];
const rect = cards[0].getBoundingClientRect();
document.getElementById('result').textContent = JSON.stringify({
  wrap: getComputedStyle(row).flexWrap,
  titleSize: getComputedStyle(cards[0].querySelector('.dm-module-title')).fontSize,
  rowClientWidth: row.clientWidth, rowScrollWidth: row.scrollWidth,
  badgeCount: badges.length, lineCount: new Set(badges.map(b => b.offsetTop)).size,
  overflowRight: badges.map(b => b.getBoundingClientRect().right - rect.right),
  badgeContentOverflow: badges.map(b => b.scrollWidth - b.clientWidth),
  text: badges.map(b => b.textContent), heights: cards.map(c => c.getBoundingClientRect().height)
});
</script>`)
    const result = spawnSync(chrome, ['--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
      `--user-data-dir=${path.join(dir, 'profile')}`, '--dump-dom', pathToFileURL(fixture).href],
    { encoding: 'utf8', timeout: 20000, maxBuffer: 1024 * 1024 })
    assert.equal(result.error, undefined, result.error?.message)
    assert.equal(result.status, 0, result.stderr)
    const match = result.stdout.match(/<pre id="result">([^<]+)<\/pre>/)
    assert.ok(match, 'Browser must return measurements from the rendered fixture: ' + result.stderr)
    const measured = JSON.parse(match[1])
    assert.equal(measured.rowClientWidth, 206, JSON.stringify(measured))
    assert.equal(measured.wrap, 'wrap')
    assert.equal(measured.titleSize, '16px')
    assert.ok(measured.lineCount > 1, JSON.stringify(measured))
    assert.equal(measured.badgeCount, badges.length)
    assert.ok(measured.rowScrollWidth <= measured.rowClientWidth, JSON.stringify(measured))
    assert.ok(measured.overflowRight.every(value => value <= 0), JSON.stringify(measured))
    assert.ok(measured.badgeContentOverflow.every(value => value <= 0), JSON.stringify(measured))
    assert.deepEqual(measured.text, badges.map(badge => badge.label + badge.value))
    assert.equal(measured.heights[0], measured.heights[1], JSON.stringify(measured))
    console.log('ModuleHeader layout measurements:', JSON.stringify(measured))
  } finally {
    fs.rmSync(dir, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 })
  }
})
