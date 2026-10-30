import assert from 'node:assert/strict'
import test from 'node:test'
import fs from 'node:fs'
import { defineComponent, h } from 'vue'
import { loadSfc, render, mount } from './helpers/load-sfc.mjs'

const ConfigSummary = await loadSfc('ConfigSummary.vue')
const RecordDetails = await loadSfc('RecordDetails.vue')
const ModuleTable = await loadSfc('ModuleTable.vue')
const source = fs.readFileSync(new URL('../src/components/Page.vue', import.meta.url), 'utf8')

test('统一摘要保持单行、无分页，未知配置不冒充关闭', async () => {
  const html = await render(ConfigSummary, { fields: [
    { key: 'known', label: '已知值', value: '关闭', badge: true },
    { key: 'missing', label: '未知值', value: null, badge: true },
  ] })
  assert.match(html, /配置摘要/)
  assert.match(html, /当前接口未提供/)
  assert.equal((html.match(/<tbody/g) || []).length, 1)
  assert.doesNotMatch(html, /dm-module-table-footer|每页条数/)
})

test('统一摘要前往设置发出导航事件，不执行IO', () => {
  let switched = 0
  const VBtn = defineComponent({ setup(_, { attrs, slots }) { return () => h('button', attrs, slots.default?.()) } })
  const view = mount(ConfigSummary, { fields: [], onSettings: () => switched++ }, {}, { components: { VBtn } })
  try {
    const button = view.findAll(node => node.type === 'button')[0]
    button.props.onClick()
    assert.equal(switched, 1)
  } finally { view.unmount() }
})

test('长模板可展开且文本转义，不注入HTML', async () => {
  const html = await render(ConfigSummary, { fields: [{ key: 'template', label: '模板', value: '<script>unsafe</script>', long: true }] })
  assert.match(html, /<details/)
  assert.match(html, /&lt;script&gt;/)
  assert.doesNotMatch(html, /<script>/)
})

test('行详情保留真实0和false，只展示已声明字段，不泄露其他配置', async () => {
  const html = await render(RecordDetails, { record: { source: '上轮巡检', scanned: 0, skipped: 0, deleted: false, reason: null, secret: 'do-not-render', name: '<img src=x>' } })
  assert.match(html, /上轮巡检/)
  assert.match(html, /<dd>0<\/dd>/)
  assert.match(html, /<dd>否<\/dd>/)
  assert.match(html, /&lt;img src=x&gt;/)
  assert.doesNotMatch(html, /do-not-render|<dt>原因/)
})

test('共享清历史按钮可由真实可清计数额外禁用', async () => {
  const html = await render(ModuleTable, { title: '记录', rows: [{ id: 'r1' }], total: 1, cleanupLabel: '清历史', cleanupBlocked: true })
  assert.match(html, /disabled[^>]*>清历史/)
})

test('九页共用单表，不再维护移动卡片副本；七业务模块用同一配置摘要', () => {
  assert.equal((source.match(/<ConfigSummary\b/g) || []).length, 1)
  assert.equal((source.match(/data-page="diagnostics"/g) || []).length, 1)
  assert.doesNotMatch(source, /class="dm-mobile-records|class="dm-record-card/)
  assert.match(source, /moduleCards\.value\.filter\(card => card\.key !== 'seed'\)/)
  assert.match(source, /当前接口未提供逐条执行历史/)
  for (const key of ['autoHistory', 'failHistory', 'tagHistory', 'cleanupHistory', 'uploadHistory']) {
    assert.match(source, new RegExp(':columns="recordColumns\\.' + key + '" :unavailable="unavailableHistory"'))
  }
})
