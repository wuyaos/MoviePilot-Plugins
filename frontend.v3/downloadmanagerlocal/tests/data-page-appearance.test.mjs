import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import postcss from 'postcss'

const component = name => fs.readFileSync(new URL(`../src/components/${name}.vue`, import.meta.url), 'utf8')
const css = fs.readFileSync(new URL('../src/styles/dm-tokens.css', import.meta.url), 'utf8')
const page = component('Page')
const styles = name => postcss.parse(component(name).split('<style scoped>')[1].split('</style>')[0])
const declaration = (ast, selector, property) => ast.nodes.find(node => node.selector === selector)?.nodes.find(node => node.prop === property)?.value

test('tables, cards and badges retain light borders without redundant nested frames', () => {
  const border = '1px solid rgba(var(--v-border-color), var(--v-border-opacity))'
  assert.equal(declaration(styles('ModuleTable'), '.dm-module-table', 'border'), border)
  for (const selector of ['.dm-four-stats > div', '.dm-overview-card', '.dm-page-stack :deep(.dm-module-stat)']) {
    assert.equal(declaration(styles('Page'), selector, 'border'), border)
  }
  assert.equal(declaration(styles('Page'), '.dm-overview-card :deep(.dm-module-stat)', 'border'), '0')
  for (const selector of ['.dm-runtime-details', '.dm-tag-matrix']) {
    assert.equal(declaration(styles('Page'), selector, 'border'), undefined)
  }
  assert.match(component('ModuleHeader'), /<VChip[^>]*variant="tonal"/)
  assert.equal(declaration(postcss.parse(css), ':where(.dm-page) .v-chip', 'border'), undefined)
})

test('data-page density and badges are scoped and configuration keeps its existing sizes', () => {
  const ast = postcss.parse(css)
  assert.equal(declaration(ast, ':where(.dm-page, .dm-page .dm-module-header, .dm-page .dm-module-table, .dm-page .dm-table-state)', '--dm-button-height'), '28px')
  assert.equal(declaration(ast, ':where(.dm-page) .v-chip', 'height'), undefined)
  assert.equal(declaration(ast, ':where(.dm-page) .v-chip', 'border-radius'), undefined)
  assert.equal(declaration(ast, ':where(.dm-page, .dm-page .dm-module-header, .dm-page .dm-module-table, .dm-page .dm-table-state)', '--dm-text-title-size'), '16px')
  assert.equal(declaration(ast, ':where(.dm-page, .dm-page .dm-module-header, .dm-page .dm-module-table, .dm-page .dm-table-state)', '--dm-text-body-size'), '13px')
  assert.match(css, /@media \(pointer: coarse\)/)
})

test('header metrics use result semantics, with unknown and zero failures neutral', () => {
  const source = page.slice(page.indexOf('const headerMetric ='), page.indexOf('const moduleHeaders ='))
  const metric = new Function(`${source}; return headerMetric`)()
  assert.equal(metric('今日成功', 5).tone, 'success')
  assert.equal(metric('今日失败', 2).tone, 'error')
  assert.equal(metric('今日失败', 0).tone, 'secondary')
  assert.equal(metric('待重试', 2).tone, 'warning')
  assert.equal(metric('做种中', 3).tone, 'primary')
  assert.equal(metric('今日失败', undefined).tone, 'secondary')
  assert.equal(metric('今日失败', undefined).value, '—')
})

test('H&R pending and transfer intermediate phases do not claim success', () => {
  const source = page.slice(page.indexOf('function transferPhaseColor('), page.indexOf('function transferShortHash('))
  const color = new Function(`${source}; return transferPhaseColor`)()
  assert.equal(color('completed'), 'success')
  assert.equal(color('target_added'), 'primary')
  assert.equal(color('stopped_after_add'), 'warning')
  assert.equal(color('failed'), 'error')
  assert.equal(color('unknown'), 'default')
  assert.match(page, /Pending: 'warning'/)
})

test('module icons use VIcon and keep fault/observing/enabled/off colour precedence', () => {
  const source = component('ModuleHeader')
  assert.match(source, /<VIcon :icon="icon"/)
  assert.doesNotMatch(source, /<span class="mdi /)
  const expression = source.match(/<VAvatar :color="([^"]+)"/)[1]
  const color = new Function('fault', 'observing', 'enabled', 'running', `return ${expression}`)
  assert.equal(color(true, true, true, true), 'error')
  assert.equal(color(false, true, true, true), 'warning')
  assert.equal(color(false, false, true, false), 'primary')
  assert.equal(color(false, false, false, true), 'primary')
  assert.equal(color(false, false, false, false), undefined)
})

test('page controls share compact heights and filters do not use floating form labels', () => {
  const ast = styles('Page')
  assert.equal(declaration(ast, '.dm-page :deep(.v-btn.v-btn--size-small)', 'height'), undefined)
  assert.equal(declaration(styles('CompactSelect'), '.dm-compact-select :deep(.v-field__input)', 'min-height'), 'var(--dm-button-height)')
  assert.equal(declaration(ast, '.dm-page-heading h3', 'font-size'), 'var(--dm-text-section-size)')
  const select = component('CompactSelect')
  assert.match(select, /single-line/)
  assert.match(select, /:list-props="\{ density: 'compact' \}"/)
  assert.ok([...page.matchAll(/<CompactSelect\b/g)].length >= 7)
  assert.doesNotMatch(page, /<VSelect\b/)
})
