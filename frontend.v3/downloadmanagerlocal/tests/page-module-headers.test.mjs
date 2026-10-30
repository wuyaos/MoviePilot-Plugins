import { MODULE_ICONS } from '../src/components/module-icons.js'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { compileScript, compileTemplate, parse } from '@vue/compiler-sfc'
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { loadSfc, render } from './helpers/load-sfc.mjs'

const source = fs.readFileSync(new URL('../src/components/Page.vue', import.meta.url), 'utf8')
const { descriptor, errors } = parse(source, { filename: 'Page.vue' })
assert.deepEqual(errors, [])
const compiled = compileScript(descriptor, { id: 'dml-page-header', inlineTemplate: true })
assert.ok(compiled.bindings.ModuleHeader)
assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: 'Page.vue', id: 'dml-page-header' }).errors, [])
const Header = await loadSfc('ModuleHeader.vue')
const setup = new Function('reactive', 'ref', 'computed', 'watch', 'nextTick', 'onMounted', 'onBeforeUnmount',
  'defineProps', 'defineEmits', 'getPluginApi', 'postPluginApi', 'postPluginJsonApi',
  `${descriptor.scriptSetup.content.replace(/^import .*$/gm, '').replace(/^/, `const MODULE_ICONS = ${JSON.stringify(MODULE_ICONS)};\n`)}\nreturn { overview, diagnostics, transferStatus, hrTasks, autoremoveStatus, failcleanStatus, siteTagStatus, renameStatus, moduleRunning, moduleHeaders, moduleCards, moduleGridCards, activeTab };`)
function page(watcher = watch) {
  const noRequest = () => { throw new Error('Header projection must not request API') }
  return setup(reactive, ref, computed, watcher, nextTick, () => {}, () => {},
    () => ({ api: null, pluginId: 'DownloadManagerLocal' }), () => () => {}, noRequest, noRequest, noRequest)
}
const values = header => Object.fromEntries(header.badges.map(({ label, value }) => [label, value]))
function elements(node, found = []) {
  if (node.type === 1) found.push(node)
  for (const child of node.children || []) elements(child, found)
  return found
}
const attribute = (node, name) => node.props.find(prop => prop.type === 6 && prop.name === name)?.value?.content
const directive = (node, name, arg) => node.props.find(prop => prop.type === 7 && prop.name === name && (!arg || prop.arg?.content === arg))?.exp?.content

test('Page 接入七模块公共头部，seed 不再独立显示，总览只导航不执行业务', () => {
  const p = page()
  assert.deepEqual(Object.keys(p.moduleHeaders.value), ['transfer', 'hr', 'autoremove', 'failclean', 'rename', 'tag', 'upload_limit'])
  const nodes = elements(parse(source).descriptor.template.ast)
  const overview = nodes.find(node => attribute(node, 'class') === 'dm-overview-card')
  assert.equal(directive(overview, 'for'), 'card in sevenCards')
  assert.equal(overview.children.filter(node => node.tag === 'ModuleHeader').length, 1)
  const link = overview.children.find(node => node.tag === 'VBtn')
  assert.equal(directive(link, 'on', 'click'), 'openModuleRecords(card.key)')
  assert.ok(!elements(overview).some(node => directive(node, 'on', 'click') === 'action.run()'))
})

test('业务专页仅一处公共头部及动作，转移与命名保留分区标题', async () => {
  const p = page(() => {})
  const nodes = elements(parse(source).descriptor.template.ast)
  const section = nodes.find(node => directive(node, 'if') === 'currentHeader')
  assert.equal(elements(section).filter(node => node.tag === 'ModuleHeader').length, 1)
  const action = elements(section).find(node => directive(node, 'for') === 'action in moduleActions')
  assert.equal(directive(action, 'on', 'click'), 'action.run()')
  for (const [key, title] of [['transfer', '转移做种'], ['rename', '种子重命名']]) {
    const html = await render(Header, p.moduleHeaders.value[key])
    assert.ok(html.includes('<h2 class="dm-module-title">' + title + '</h2>'))
  }
  for (const title of ['任务配置', '在途事务', '最近记录', '执行记录', '失败归档']) assert.ok(nodes.some(node => node.tag === 'ModuleTable' && attribute(node, 'title') === title))
})

test('七模块缺失徽标均为 —；真实零保留，不从列表或本次重命名结果伪造今日统计', () => {
  const p = page()
  for (const header of Object.values(p.moduleHeaders.value)) {
    assert.ok(header.badges.every(badge => badge.value === '—'))
  }
  p.renameStatus.value = { renamed: 32, failed: 7 }
  p.siteTagStatus.value = { completed: 91, skipped: 6 }
  p.transferStatus.value = { pending: [{ id: 1 }], records: [{ phase: 'completed' }] }
  assert.equal(values(p.moduleHeaders.value.transfer)['在途'], '—')
  assert.equal(values(p.moduleHeaders.value.rename)['今日成功'], '—')
  assert.equal(values(p.moduleHeaders.value.rename)['今日失败'], '—')
  assert.ok(p.moduleHeaders.value.tag.badges.every(badge => badge.value === '—'))
  p.overview.value = { cards: { transfer: { today_success: 0, success_total: 20 } }, archive: { active_failed: 0, archived: 2 } }
  p.transferStatus.value = { summary: { pending: 0 } }
  assert.deepEqual(values(p.moduleHeaders.value.transfer), { 在途: 0, 今日成功: 0, 今日失败: '—', 累计成功: 20 })
  assert.deepEqual(values(p.moduleHeaders.value.rename), { 今日成功: '—', 今日失败: '—', 待重试: 0, 失败归档: 2 })
})

test('启停取配置而非活跃/历史计数；观察/故障/执行中独立，真实头部渲染有文字', async () => {
  const p = page()
  p.overview.value = { cards: { transfer: { enabled: true, active: false }, rename: { enabled: false } } }
  p.diagnostics.value = { config: { tag_enabled: false }, module_observe_only: { transfer: true }, module_faults: { transfer: '连接失败' } }
  p.siteTagStatus.value = { completed: 900 }
  p.moduleRunning.value = 'transfer-run'
  assert.equal(p.moduleHeaders.value.transfer.enabled, true)
  assert.equal(p.moduleHeaders.value.tag.enabled, false)
  const html = await render(Header, p.moduleHeaders.value.transfer)
  for (const text of ['已启用', '观察模式', '执行中', '故障']) assert.ok(html.includes(text), text)
  assert.match(html, /dm-module-icon--enabled/)
  const disabled = await render(Header, p.moduleHeaders.value.rename)
  assert.ok(disabled.includes('已禁用'))
  assert.doesNotMatch(disabled, /dm-module-icon--enabled/)
})

test('H&R 和失败清理徽标直读汇总；事件计数不混入上轮巡检', () => {
  const p = page()
  p.hrTasks.value = { summary: { enabled: true, total: 8, needs_seeding: 2, pending: 99, in_progress: 3, compliant: 1 } }
  assert.deepEqual(values(p.moduleHeaders.value.hr), { 总数: 8, 待做种: 2, 做种中: 3, 已达标: 1 })
  p.failcleanStatus.value = { enabled: true, scan: { scanned: 15, cleaned: 2, skipped: 3, failed: 4 }, event: { deleted: 1000, skipped: 2000, failed: 3000 } }
  assert.deepEqual(values(p.moduleHeaders.value.failclean), { 上轮扫描: 15, 清理: 2, 跳过: 3, 失败: 4 })
})

test('自动删种不以预览冒充成功，不以单项保护跳过冒充跳过总数；原动作按钮全保留', () => {
  const p = page()
  for (const action of ['pause', 'delete', 'deletefile']) {
    p.autoremoveStatus.value = { enabled: true, action, candidates: 12, paused: 2, deleted: 3, deleted_files: 3, skipped_protected: 5, failed: 1 }
    assert.deepEqual(values(p.moduleHeaders.value.autoremove), { 上轮候选: 12, 成功: action === 'pause' ? 2 : 3, 跳过: '—', 失败: 1 })
  }
  p.autoremoveStatus.value = { action: 'delete', observe_only: true, deleted: 0 }
  assert.equal(values(p.moduleHeaders.value.autoremove)['成功'], '—')
  assert.deepEqual(Object.fromEntries(p.moduleCards.value.map(card => [card.key, card.actions.map(action => action.key)])), {
    transfer: ['transfer-run'], seed: [], hr: ['hr-check', 'hr-scan'], autoremove: ['autoremove-preview', 'autoremove-run'],
    failclean: ['failclean-scan'], rename: ['rename-retry'], tag: ['tag-complement'],
    upload_limit: ['upload-reallocate', 'upload-scan-sites', 'upload-clear-rules'],
  })
})

test('上传限速格式化真实汇总数值，缺速率/额度不显示假零，常驻 running 状态不冒充正在执行', async () => {
  const p = page()
  p.overview.value = { upload_limit: { enabled: true, service_status: 'running', managed_torrents: 0, uploading_torrents: 2, upload_rate_bps: 2048, allocated_kib: 100 } }
  const header = p.moduleHeaders.value.upload_limit
  assert.deepEqual(values(header), { 受管种子: 0, 上传中: 2, 当前上传: '2.0 KiB/s', 已分配额度: '100 KiB/s' })
  assert.equal(header.running, false)
  const html = await render(Header, header)
  for (const text of ['受管种子', '上传中', '当前上传', '已分配额度']) assert.ok(html.includes(text))
  p.overview.value = { upload_limit: { enabled: true } }
  assert.ok(p.moduleHeaders.value.upload_limit.badges.every(badge => badge.value === '—'))
})
