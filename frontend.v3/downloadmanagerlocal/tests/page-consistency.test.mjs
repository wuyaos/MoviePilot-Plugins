import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'

const read = name => readFileSync(new URL('../src/components/' + name, import.meta.url), 'utf8')
const source = read('Page.vue')
function elements(node) {
  return [...(node.type === 1 ? [node] : []), ...(node.children || []).flatMap(elements)]
}
const nodes = elements(parse(source).descriptor.template.ast)
const attr = (node, name) => node.props.find(p => p.type === 6 && p.name === name)?.value?.content
const directive = (node, name, arg) => node.props.find(p => p.type === 7 && p.name === name && (!arg || p.arg?.content === arg))?.exp?.content

test('业务页唯一公共页头与摘要；总览仅七卡，seed 归转移而非独立卡', () => {
  const section = nodes.find(n => directive(n, 'if') === 'currentHeader')
  assert.equal(elements(section).filter(n => n.tag === 'ModuleHeader').length, 1)
  assert.equal(elements(section).filter(n => n.tag === 'ConfigSummary').length, 1)
  assert.match(source, /moduleCards\.value\.filter\(card => card\.key !== 'seed'\)/)
  assert.doesNotMatch(source, /dm-desktop-table|dm-mobile-list/)
})

test('实际业务表均复用 ModuleTable；保留表头、状态、分页、展开和清理事件', () => {
  const blocks = nodes.filter(n => attr(n, 'data-record-block') && n.tag === 'ModuleTable')
  assert.deepEqual(blocks.map(n => attr(n, 'data-record-block')).sort(), [
    'transfer-tasks', 'transfer-records', 'rename-history', 'rename-archive', 'hr-tasks', 'autoremove-preview', 'tag-cleanup',
  ].sort())
  const table = read('ModuleTable.vue')
  assert.equal((table.match(/<VTable\b/g) || []).length, 1)
  assert.match(table, /<TableState/)
  assert.match(table, /overflow-x: auto/)
  assert.match(table, /emit\('cleanup'\)/)
  assert.match(table, /<slot name="expand"/)
  assert.doesNotMatch(table, /getPluginApi|postPluginApi/)
})

test('五个执行历史表绑定真实历史流，保留独立分页和重试', () => {
  const tables = nodes.filter(n => n.tag === 'ModuleTable' && attr(n, 'data-execution-stream'))
  assert.deepEqual(tables.map(n => attr(n, 'data-execution-stream')), ['autoremove', 'tag', 'tag_cleanup', 'upload_limit'])
  for (const table of tables) {
    assert.equal(attr(table, 'row-key'), 'record_id')
    assert.ok(directive(table, 'bind')?.startsWith('executionTableProps('))
    assert.ok(directive(table, 'on', 'retry')?.startsWith('loadExecutionHistory('))
  }
  assert.doesNotMatch(source, /unavailableHistory/)
})

test('上传按下载器折叠分组，共用站点表；跨下载器汇总明确独立，不按下载器复制', () => {
  assert.match(source, /v-for="group in uploadGroups"/)
  assert.match(source, /:rows="group\.rows"/)
  assert.match(source, /跨下载器站点汇总（当前接口未拆分）/)
  assert.match(source, /owners\.length === 1/)
  assert.doesNotMatch(source, /<VTable|dm-upload-status-grid|dm-upload-site-status-row/)
})

test('上传限速站点表展示单种/合计分配徽标与三态状态，不残留宽限控件', () => {
  assert.match(source, /allocation_badge/)
  assert.match(source, /cell-allocation_badge/)
  assert.match(source, /uploadLimitStateChip\(row\)/)
  assert.match(source, /formatAllocationMb\(row\.desired_allocated_kib \?\? row\.torrent_limit_kib\)/)
  assert.doesNotMatch(source, /宽限|grace_torrents|grace_minutes/)
})
