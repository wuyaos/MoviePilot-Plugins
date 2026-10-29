import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import test from 'node:test'
import { parse, compileStyle, compileTemplate } from '@vue/compiler-sfc'
import postcss from 'postcss'

const source = fs.readFileSync(new URL('../src/components/Config.vue', import.meta.url), 'utf8')
const normalized = source.replace(/\r\n/g, '\n')
const fixture = JSON.parse(fs.readFileSync(new URL('./fixtures/config-density-contract.json', import.meta.url), 'utf8'))
const { descriptor, errors } = parse(source)
const nodes = []
const parents = new Map()
function walk(node, parent) {
  if (node.type === 1) { nodes.push(node); parents.set(node, parent); parent = node }
  for (const child of node.children || []) walk(child, parent)
}
walk(descriptor.template.ast)
const attr = (node, name) => node.props.find(prop => prop.type === 6 && prop.name === name)?.value?.content
const has = (node, name) => node.props.some(prop => prop.type === 6 && prop.name === name)
const classes = node => (attr(node, 'class') || '').split(/\s+/)
const ancestor = (node, cls) => { for (let n = parents.get(node); n; n = parents.get(n)) if (classes(n).includes(cls)) return n }
const css = descriptor.styles[0].content
const ast = postcss.parse(css)
const rule = selector => ast.nodes.find(node => node.type === 'rule' && node.selector === selector)
const declaration = (selector, prop) => rule(selector)?.nodes.find(node => node.prop === prop)?.value

test('完整脚本 SHA-256 与全部模板业务 directives 精确匹配批准后的 fixture', () => {
  const script = normalized.match(/<script setup>([\s\S]*?)<\/script>/)[1]
  assert.equal(createHash('sha256').update(script).digest('hex'), fixture.scriptSha256)
  const directives = [...descriptor.template.content.matchAll(/(?:v-[\w.-]+|[:@][\w:-]+)="[^"]*"/g)].map(match => match[0]).sort()
  assert.deepEqual(directives, fixture.directives)
  assert.doesNotMatch(normalized, /emit\(['"]layout/)
})

test('真实模板/scoped 样式编译，Config 保持纯 CRLF', () => {
  assert.deepEqual(errors, [])
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'Config.vue', id: 'density' }).errors, [])
  assert.deepEqual(compileStyle({ source: css, filename: 'Config.vue', id: 'density', scoped: true }).errors, [])
  assert.equal(source.replace(/\r\n/g, '').includes('\n'), false)
})

test('几何 token 符合 §2.4，公共 token 表不修改文字 token', () => {
  const tokens = postcss.parse(fs.readFileSync(new URL('../src/styles/dm-tokens.css', import.meta.url), 'utf8'))
  const values = {}
  tokens.walkDecls(decl => { if (decl.prop.startsWith('--dm-')) values[decl.prop] = decl.value })
  for (const [key, value] of Object.entries({ 'control-height': '40px', 'button-height': '32px', 'number-width': '144px', 'field-gap': '12px', 'section-gap': '16px', 'panel-radius': '8px' })) assert.equal(values[`--dm-${key}`], value)
  assert.equal(declaration('.dm-field-row', 'gap'), 'var(--dm-field-gap)')
  assert.equal(declaration('.dm-pane > .dm-section-title:not(:first-child)', 'margin-top'), 'var(--dm-section-gap)')
})

test('所有短数值控件显式 144px；普通字段最多两列，长模板/路径/文本域整行', () => {
  const numbers = nodes.filter(node => node.tag === 'VTextField' && attr(node, 'type') === 'number')
  assert.equal(numbers.length, 19)
  for (const node of numbers) assert.ok(classes(node).includes('dm-number-input'), node.loc.source)
  assert.equal(declaration('.dm-number-input', 'width'), 'var(--dm-number-width)')
  assert.match(declaration('.dm-field', 'max-width'), /50%/)
  assert.equal(declaration('.dm-field--full', 'flex-basis'), '100%')
  for (const node of nodes.filter(node => node.tag === 'VTextarea' || (node.tag === 'VTextField' && /路径|模板|WebUI 地址/.test(attr(node, 'label') || '')))) {
    assert.ok(ancestor(node, 'dm-field--full'), node.loc.source)
  }
  assert.doesNotMatch(source, /<\/?V(?:Row|Col)\b/)
})

test('所有简单开关通过 flex 左标签右开关；不依赖无效 reverse 属性或等宽栅格', () => {
  const switches = nodes.filter(node => node.tag === 'VSwitch')
  assert.equal(switches.length, 47)
  for (const node of switches) assert.equal(has(node, 'reverse'), false, node.loc.source)
  assert.equal(declaration(':is(.dm-config, .dm-form-dialog) :deep(.v-switch .v-selection-control)', 'flex-direction'), 'row-reverse')
  assert.equal(declaration('.dm-field--toggle', 'width'), 'fit-content')
  for (const row of nodes.filter(node => classes(node).includes('dm-field-row'))) {
    const fields = row.children.filter(node => node.type === 1)
    const short = fields.filter(node => classes(node).includes('dm-field--number') || classes(node).includes('dm-field--toggle'))
    assert.ok(short.length <= 3, `short row at ${row.loc.start.line}`)
  }
})

test('页脚为滚动区外的卡片直属子节点；无最小760px或填满面板，支持低高度收缩', () => {
  const footer = nodes.find(node => classes(node).includes('dm-actions'))
  assert.ok(classes(parents.get(footer)).includes('dm-card'))
  assert.equal(ancestor(footer, 'dm-window'), undefined)
  assert.equal(declaration('.dm-window', 'min-height'), '0')
  assert.equal(declaration('.dm-body', 'min-height'), '0')
  assert.equal(declaration('.dm-card', 'height'), undefined)
  assert.match(declaration('.dm-card', 'max-height'), /100dvh - 48px/)
  assert.equal(declaration('.dm-pane', 'min-height'), undefined)
  assert.match(css, /@container dm-form \(max-width: 520px\)/)
})

test('help 继承层使用唯一 token，浮动标签变换不覆盖，不新增 !important 修补', () => {
  const help = rule(':is(.dm-config, .dm-form-dialog) :deep(.v-input__details), :is(.dm-config, .dm-form-dialog) :deep(.v-messages), .dm-card .dm-hint, .dm-form-dialog .dm-hint')
  assert.ok(help)
  for (const [prop, token] of [['font-size', 'size'], ['font-weight', 'weight'], ['line-height', 'line-height']]) assert.equal(help.nodes.find(d => d.prop === prop).value, `var(--dm-text-help-${token})`)
  ast.walkDecls(decl => {
    if (decl.important) assert.match(decl.parent.selector, /dm-nav-list/)
    if (/transform|--v-field-label-scale/.test(decl.prop)) assert.match(decl.parent.selector, /dm-subtab/)
  })
  assert.equal(declaration('.dm-hr-global-card', 'border'), undefined)
  const dialogs = nodes.filter(node => node.tag === 'VDialog')
  assert.equal(dialogs.length, 4)
  for (const dialog of dialogs) assert.ok(classes(dialog.children.find(node => node.type === 1 && node.tag === 'VCard')).includes('dm-form-dialog'))
  assert.equal(declaration('.dm-hr-editor-grid', 'align-items'), 'flex-start')
})

// Replay captured real harness measurements; this is not a new browser/host run.
for (const name of ['wide', 'low', 'narrow']) {
  test(`浏览器采集回放 ${name}：15 子页无横溢出、40px/144px、help 唯一、低窗页脚不遮挡`, () => {
    const data = JSON.parse(fs.readFileSync(new URL(`./evidence/density-${name}-sweep.json`, import.meta.url)))
    assert.equal(data.rows.length, 15)
    assert.deepEqual(data.errors, [])
    let numericCount = 0
    for (const row of data.rows) {
      assert.equal(row.pageOverflowX, false, row.main + row.tab)
      assert.equal(row.scrollWidth, row.clientWidth, row.main + row.tab)
      assert.ok(row.footer.y + row.footer.h <= data.viewport.h)
      assert.ok(row.scrollBottom <= row.footer.y + 1)
      if (row.lastFieldBottom !== null) assert.ok(row.lastFieldBottom <= row.footer.y)
      for (const height of row.inputHeights) assert.equal(height, 40, row.main + row.tab)
      for (const width of row.numberWidths) { assert.equal(width, 144, row.main + row.tab); numericCount++ }
      assert.deepEqual(row.helpSignatures, ['12px/400/18px'])
    }
    assert.ok(numericCount >= 23, 'Includes expanded H&R editor and non-empty upload limit rows')
  })
}
