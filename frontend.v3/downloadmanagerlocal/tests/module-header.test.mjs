import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import postcss from 'postcss'
import { loadSfc, render } from './helpers/load-sfc.mjs'

const component = await loadSfc('ModuleHeader.vue')
test('ModuleHeader 统计徽标渲染零值及语义色，不计算或丢弃数据', async () => {
  const html = await render(component, { title: '转移做种', enabled: true, badges: [{ label: '在途', value: 0 }, { label: '今日失败', value: 3, tone: 'error' }] })
  assert.match(html, /转移做种/)
  assert.match(html, /aria-label="模块统计"/)
  assert.ok(html.includes('在途</span><span>0'))
  assert.ok(html.includes('今日失败</span><span>3'))
  assert.match(html, /dm-tone-error/)
  assert.match(html, /dm-module-icon--enabled/)
})
test('ModuleHeader 启停/观察/执行/故障均有文字，不仅靠颜色', async () => {
  const active = await render(component, { title: '测试模块', enabled: true, observing: true, running: true, fault: '连接失败' })
  for (const text of ['已启用', '观察模式', '执行中', '故障：连接失败']) assert.ok(active.includes(text))
  const disabled = await render(component, { title: '测试模块' })
  assert.match(disabled, /已禁用/)
  assert.doesNotMatch(disabled, /dm-module-icon--enabled|观察模式|执行中|故障|模块统计/)
})
test('ModuleHeader 文本转义，未知徽标 tone 不注入 class', async () => {
  const html = await render(component, { title: '<标题>', badges: [{ label: '<统计>', value: '<1>', tone: 'arbitrary' }] })
  assert.match(html, /&lt;标题&gt;/)
  assert.match(html, /&lt;统计&gt;/)
  assert.match(html, /&lt;1&gt;/)
  assert.doesNotMatch(html, /dm-tone-arbitrary/)
})
const pluginRoots = ['.dm-config', '.dm-page', '.dm-module-header', '.dm-module-table', '.dm-table-state']
const tokenRoot = ':where(.dm-config, .dm-page, .dm-module-header, .dm-module-table, .dm-table-state)'
function isPluginScopedSelector(selector) {
  const match = selector.match(/^:where\(([^)]+)\)(?:\s+[^,]+)?$/)
  return Boolean(match && !selector.includes('*') && match[1].split(',').every(root => pluginRoots.includes(root.trim())))
}

test('CSS 作用域门禁接受插件共享类，拒绝裸类与非插件根', () => {
  for (const selector of [
    ':where(.dm-config, .dm-page) .dm-section-title',
    ':where(.dm-config, .dm-page) .dm-hint',
    ':where(.dm-config, .dm-page) .v-messages__message',
  ]) assert.equal(isPluginScopedSelector(selector), true, selector)
  for (const selector of ['.dm-section-title', ':where(.foo) .dm-hint', ':where(.dm-config) .dm-hint, .outside']) {
    assert.equal(isPluginScopedSelector(selector), false, selector)
  }
})
test('CSS 静态门禁：token 与规格一致，主题颜色，无全局通配字号规则', () => {
  const css = fs.readFileSync(new URL('../src/styles/dm-tokens.css', import.meta.url), 'utf8')
  const ast = postcss.parse(css)
  const tokens = {}
  ast.walkRules(rule => {
    assert.ok(!rule.selector.includes('*'))
    if (rule.nodes.some(node => node.type === 'decl' && node.prop.startsWith('--'))) {
      assert.match(rule.selector, /^:where\(\.dm-config, \.dm-page, \.dm-module-header, \.dm-module-table, \.dm-table-state\)$/)
    } else {
      assert.ok(isPluginScopedSelector(rule.selector), '共享规则必须限定在插件根内：' + rule.selector)
    }
  })
  assert.equal(ast.nodes.filter(node => node.type === 'rule' && node.selector === tokenRoot).length, 1)
  for (const [selector, role, margin] of [
    [':where(.dm-config, .dm-page) .dm-section-title', 'section', ['margin-bottom', '8px']],
    [':where(.dm-config, .dm-page) .dm-hint', 'help', ['margin-top', '2px']],
    [':where(.dm-config, .dm-page) .v-messages__message', 'help', null],
  ]) {
    const rules = ast.nodes.filter(node => node.type === 'rule' && node.selector === selector)
    assert.equal(rules.length, 1, selector)
    const declarations = Object.fromEntries(rules[0].nodes.filter(node => node.type === 'decl').map(node => [node.prop, node.value]))
    for (const [property, suffix] of [['font-size', 'size'], ['font-weight', 'weight'], ['line-height', 'line-height'], ['color', 'color']]) {
      assert.equal(declarations[property], `var(--dm-text-${role}-${suffix})`, selector + ' ' + property)
    }
    if (margin) assert.equal(declarations[margin[0]], margin[1], selector)
  }
  ast.walkDecls(decl => { tokens[decl.prop] = decl.value })
  const roles = { title: [16, 600, 24], section: [14, 600, 20], label: [14, 400, 20], body: [14, 400, 20], 'table-head': [12, 600, 18], button: [13, 500, 20], badge: [12, 500, 18], help: [12, 400, 18] }
  for (const [role, [size, weight, line]] of Object.entries(roles)) {
    assert.equal(tokens['--dm-text-' + role + '-size'], size + 'px')
    assert.equal(tokens['--dm-text-' + role + '-weight'], String(weight))
    assert.equal(tokens['--dm-text-' + role + '-line-height'], line + 'px')
  }
  assert.match(tokens['--dm-color-secondary'], /--v-theme-on-surface/)
  assert.match(tokens['--dm-color-disabled'], /--v-disabled-opacity/)
  assert.match(tokens['--dm-color-warning'], /--v-theme-warning/)
  assert.match(tokens['--dm-color-error'], /--v-theme-error/)
  for (const name of ['ModuleHeader', 'ModuleTable', 'TableState']) {
    const source = fs.readFileSync(new URL('../src/components/' + name + '.vue', import.meta.url), 'utf8')
    const styles = source.match(/<style scoped>([\s\S]*?)<\/style>/)[1]
    postcss.parse(styles).walkRules(rule => {
      assert.ok(!rule.selector.includes('*'), '不得以通配规则改全局字号')
      assert.ok(rule.selector.split(',').every(selector => selector.trim().startsWith('.dm-')))
    })
    assert.doesNotMatch(styles, /#[0-9a-fA-F]{3,8}\b/)
  }
})
