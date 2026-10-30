import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { h } from 'vue'
import { loadSfc, render } from './helpers/load-sfc.mjs'

const read = name => fs.readFileSync(new URL('../src/components/' + name + '.vue', import.meta.url), 'utf8')

test('archive menu preserves action dispatch and cancelling deletion never calls its action', async () => {
  const source = read('Page')
  const body = source.slice(source.indexOf('function handleArchiveAction('), source.indexOf('async function deleteArchive('))
  const calls = [], confirmations = []
  let approve = false
  const handle = new Function('doRetryRename', 'restoreArchive', 'deleteArchive', 'window', body + '; return handleArchiveAction')(
    hash => calls.push(['retry', hash]), hash => calls.push(['restore', hash]), hash => calls.push(['delete', hash]),
    { confirm: message => { confirmations.push(message); return approve } })
  const row = { hash: 'fixture-hash', name: '<完整名称>.mkv' }
  handle('retry', row)
  handle('restore', row)
  handle('delete', row)
  assert.deepEqual(calls, [['retry', row.hash], ['restore', row.hash]])
  assert.match(confirmations[0], /<完整名称>\.mkv/)
  assert.match(confirmations[0], /不删除种子或数据/)
  approve = true
  handle('delete', row)
  assert.deepEqual(calls.at(-1), ['delete', row.hash])
  handle('unknown', row)
  assert.equal(calls.length, 3)
})

test('full names/reasons remain escaped in cells and expandable details; count and grouped tools render once', async () => {
  const Table = await loadSfc('ModuleTable.vue')
  const Details = await loadSfc('RecordDetails.vue')
  const name = '<script>不可执行</script>' + '长名称'.repeat(100)
  const reason = '完整失败原因'.repeat(100)
  const html = await render(Table, {
    title: '失败归档', columns: [{key:'name', label:'名称', lines:2}, {key:'reason', label:'原因', lines:2}],
    rows:[{id:'a',name,reason}], total:1, pagination:false,
  }, { filters: () => h('span', '筛选组'), toolbar: () => h('button', '清归档') })
  assert.ok(html.includes('长名称'.repeat(100)))
  assert.ok(html.includes(reason))
  assert.ok(!html.includes('<script>'))
  assert.match(html, /-webkit-line-clamp:2/)
  const empty = await render(Table, {title:'失败归档', columns:[], rows:[], total:0})
  assert.equal((empty.match(/共 0 条/g) || []).length, 1)
  assert.match(html, /dm-module-table-filters/)
  assert.match(html, /dm-module-table-actions/)
  const details = await render(Details, {record:{name, archive_reason:reason}})
  assert.ok(details.includes(reason))
  assert.match(details, /&lt;script&gt;/)
  const page = read('Page')
  assert.ok(page.includes("import CompactSelect from './CompactSelect.vue'"))
  assert.ok(read('ModuleTable').includes("import CompactSelect from './CompactSelect.vue'"))
  assert.doesNotMatch(read('ModuleTable'), /<select\b/)
})

test('all existing row action columns share the same menu without changing business handlers', () => {
  const page = read('Page')
  const columns = [...page.matchAll(/<template #rowActions\b[^>]*>([\s\S]*?)<\/template>/g)]
  assert.equal(columns.length, 6)
  for (const [, content] of columns) {
    assert.match(content, /<RowActionMenu\b/)
    assert.doesNotMatch(content, /<VBtn\b|<button\b/)
  }
  assert.doesNotMatch(read('ModuleTable'), /<button\b/)
  assert.match(read('ModuleTable'), /<VTable\b/)
  assert.doesNotMatch(read('TableState'), /<button\b/)
})
