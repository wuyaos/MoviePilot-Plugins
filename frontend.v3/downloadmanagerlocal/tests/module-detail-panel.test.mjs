import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import { compileScript, parse } from '@vue/compiler-sfc'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'

const here = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(here, '..')
const componentPath = path.join(projectRoot, 'src', 'components', 'ModuleDetailPanel.vue')
const source = fs.readFileSync(componentPath, 'utf8')

/**
 * 用项目已有的 @vue/compiler-sfc 把 <script setup> + template 编译成真实组件对象：
 * 产物写进 node_modules 下的临时目录，裸模块名 `vue` 才能按 Node 规则解析到本项目依赖。
 * 这样断言的是组件真实模板的渲染结果，而不是在测试里复刻一份渲染逻辑。
 */
async function loadComponent() {
  const { descriptor, errors } = parse(source, { filename: componentPath })
  assert.deepEqual(errors, [], '组件源码必须能通过 SFC 解析')
  assert.ok(descriptor.template, '组件必须有 <template>')
  const compiled = compileScript(descriptor, { id: 'dml-module-detail-panel', inlineTemplate: true })
  const dir = path.join(projectRoot, 'node_modules', '.dml-module-detail-panel')
  fs.mkdirSync(dir, { recursive: true })
  const file = path.join(dir, 'ModuleDetailPanel.mjs')
  fs.writeFileSync(file, compiled.content, 'utf8')
  const module = await import(pathToFileURL(file).href)
  return module.default
}

const component = await loadComponent()

function render(props = {}, slots = {}) {
  return renderToString(createSSRApp({ render: () => h(component, props, slots) }))
}

test('空态：无 rows/items 时渲染 emptyText 并使用统一空态样式', async () => {
  const html = await render({ emptyText: '暂无转移记录' })
  assert.match(html, /暂无转移记录/)
  assert.match(html, /dm-detail-empty/)
})

test('有 rows 但没有 items 时不显示误导性的空态文案', async () => {
  const html = await render({ rows: [{ label: '失败归档', value: '34' }], emptyText: '暂无记录' })
  assert.match(html, /失败归档/)
  assert.match(html, /34/)
  assert.doesNotMatch(html, /暂无记录/)
})

test('error 与 rows 同时存在时两者都渲染', async () => {
  const html = await render({ rows: [{ label: '历史记录', value: '37' }], error: '读取归档失败' })
  assert.match(html, /读取归档失败/)
  assert.match(html, /历史记录/)
})

test('截断提示按传入数字生成，不硬编码 20', async () => {
  const html = await render({
    items: [{ title: 'a' }, { title: 'b' }, { title: 'c' }],
    total: 34,
    limit: 50,
    truncated: true,
  })
  assert.match(html, /仅显示前 3 条/)
  assert.match(html, /共 34 条/)
  assert.match(html, /上限 50 条/)
  const other = await render({ items: [{ title: 'a' }], total: 5, limit: 200, truncated: true })
  assert.match(other, /上限 200 条/)
  const notTruncated = await render({ items: [{ title: 'a' }], total: 1, limit: 20 })
  assert.doesNotMatch(notTruncated, /仅显示前/)
})

test('默认 slot 提供专用内容时不再渲染 rows/items', async () => {
  const html = await render(
    { rows: [{ label: '不该出现', value: '1' }], items: [{ title: '也不该出现' }] },
    { default: () => h('div', { class: 'custom-block' }, '专用内容') },
  )
  assert.match(html, /专用内容/)
  assert.match(html, /custom-block/)
  assert.doesNotMatch(html, /不该出现/)
  assert.doesNotMatch(html, /也不该出现/)
})

test('appendix slot 在内置明细之后追加渲染，不替换 rows（上传限速网格走此通道）', async () => {
  const html = await render(
    { title: '运行明细', rows: [{ label: '管理种子', value: '12' }] },
    { appendix: () => h('div', { class: 'upload-grid' }, '下载器状态') },
  )
  assert.match(html, /管理种子/)
  assert.match(html, /12/)
  assert.match(html, /下载器状态/)
  assert.match(html, /upload-grid/)
  assert.ok(html.indexOf('管理种子') < html.indexOf('下载器状态'), 'appendix 必须排在内置明细之后')
})

test('默认 slot 覆盖内置明细时 appendix 仍然渲染', async () => {
  const html = await render(
    { rows: [{ label: '不该出现', value: '1' }] },
    { default: () => h('div', null, '专用内容'), appendix: () => h('div', null, '附加内容') },
  )
  assert.doesNotMatch(html, /不该出现/)
  assert.match(html, /专用内容/)
  assert.match(html, /附加内容/)
})

test('actions slot 与外层 title/subtitle 一起渲染', async () => {
  const html = await render(
    { title: '运行明细', subtitle: '只统计已完成的记录' },
    { actions: () => h('button', { class: 'custom-action' }, '查看执行记录') },
  )
  assert.match(html, /运行明细/)
  assert.match(html, /只统计已完成的记录/)
  assert.match(html, /查看执行记录/)
  assert.match(html, /custom-action/)
})

test('长文本原样渲染且带换行保护类', async () => {
  const long = `很长的种子名${'x'.repeat(200)}`
  const html = await render({ items: [{ title: long, meta: 'meta' }] })
  assert.ok(html.includes(long), '长文本不得被截断或改写')
  assert.match(html, /dm-detail-break/)
})

test('组件不依赖插件 API 与业务配置', () => {
  assert.match(source, /from 'vue'/)
  assert.doesNotMatch(source, /from '\.\.?\//, '不得引入同项目其他模块')
  assert.doesNotMatch(source, /getPluginApi|postPluginApi|pluginId/, '纯展示组件，不碰插件 API')
})
