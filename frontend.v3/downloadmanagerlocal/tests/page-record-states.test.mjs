import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { defineComponent, h, nextTick } from 'vue'
import { loadSfc, mount } from './helpers/load-sfc.mjs'

globalThis.document = { visibilityState: 'hidden', addEventListener() {}, removeEventListener() {} }
globalThis.window = { setInterval: () => 0, clearInterval() {} }
const Page = await loadSfc('Page.vue')
const source = readFileSync(new URL('../src/components/Page.vue', import.meta.url), 'utf8')
const components = Object.fromEntries([...new Set([...source.matchAll(/<(V[A-Z]\w*)\b/g)].map(match => match[1]))].map(name => [name, defineComponent({
  inheritAttrs: false, props: ['modelValue', 'text'],
  setup(props, { attrs, slots }) { return () => {
    if (name === 'VDialog' && !props.modelValue) return null
    return h(name === 'VTable' ? 'table' : ['VBtn', 'VListItem'].includes(name) ? 'button' : 'div', attrs, props.text || slots.default?.())
  } },
})]))
const text = node => (node.type === '#comment' ? '' : node.text) + node.children.map(text).join('')
const walk = (root, predicate) => {
  const found = []
  function visit(node) { if (predicate(node)) found.push(node); node.children.forEach(visit) }
  visit(root); return found
}
const hasClass = (node, name) => String(node.props.class || '').split(/\s+/).includes(name)
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
const pending = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
async function viewPage() {
  const handlers = {}, calls = []
  const api = { get: async path => {
    calls.push(path)
    const key = path.split('/').at(-1).split('?')[0]
    if (handlers[key]) return handlers[key](path)
    if (key === 'downloaders') return []
    return { code: 0 }
  }, post: async () => { throw Error('rendering must not write') } }
  const view = mount(Page, { api }, {}, { components })
  await flush()
  const click = async label => {
    const button = view.findAll(node => node.type === 'button' && text(node).trim() === label)[0]
    assert.ok(button, 'button ' + label); assert.notEqual(button.props.disabled, true)
    button.props.onClick({}); await nextTick()
  }
  const block = key => { const node = view.findAll(node => node.props['data-record-state'] === key)[0]; assert.ok(node, key); return node }
  const surfaces = key => {
    const root = block(key)
    const nodes = walk(root, node => hasClass(node, 'dm-table-scroll')); assert.equal(nodes.length, 1); return [root]
  }
  return { ...view, handlers, calls, click, block, surfaces }
}
const fixtures = [
  { key: 'history', api: 'rename_history', tab: '命名历史', row: { hash: 'history-hash', original_name: '原名.mkv', after_name: '历史样本.mkv', success: true }, title: '历史样本.mkv', response: items => ({ items, total: items.length ? 43 : 0 }) },
  { key: 'archive', api: 'rename_archive', tab: '命名历史', row: { hash: 'archive-hash', name: '归档样本.mkv', fail_count: 3 }, title: '归档样本.mkv', response: items => ({ items, total: items.length ? 27 : 0 }) },
  { key: 'transfer', api: 'transfer_status', tab: '转移做种', row: { source_downloader: 'QB', downloader: 'TR', source_hash: 'abcdefgh0123456789', source_name: '转移样本.mkv', phase: 'completed' }, title: '转移样本.mkv', response: records => ({ status: { enabled: false, records, page: 1, total: records.length ? 151 : 0, total_pages: records.length ? 8 : 1 } }) },
]
for (const f of fixtures) {
  test(`${f.key}: real Page renders first-load skeleton on both surfaces, retains headers, and retries only its block after first failure`, async () => {
    const view = await viewPage()
    try {
      const request = pending(); view.handlers[f.api] = () => request.promise
      await view.click(f.tab)
      for (const surface of view.surfaces(f.key)) {
        assert.equal(walk(surface, node => hasClass(node, 'dm-table-skeleton')).length, 3)
        assert.equal(walk(surface, node => node.props['aria-busy'] === 'true').length, 1)
        assert.ok(!text(surface).includes('暂无记录'))
      }
      assert.ok(walk(view.surfaces(f.key)[0], node => node.type === 'th').length > 0)
      request.reject(Error(f.key + ' offline')); await flush()
      for (const surface of view.surfaces(f.key)) {
        assert.ok(text(surface).includes(f.key + ' offline'))
        assert.equal(walk(surface, node => node.props.role === 'alert').length, 1)
      }
      if (f.key !== 'transfer') {
        const other = view.block(f.key === 'history' ? 'archive' : 'history')
        assert.ok(!text(other).includes('offline'), 'errors cannot leak into the other block')
      }
      view.handlers[f.api] = () => f.response([f.row])
      const before = view.calls.filter(path => path.includes('rename_')).length
      walk(view.surfaces(f.key)[0], node => node.type === 'button' && text(node) === '重试')[0].props.onClick()
      await flush()
      for (const surface of view.surfaces(f.key)) { assert.ok(text(surface).includes(f.title)); assert.ok(!text(surface).includes('offline')) }
      if (f.key !== 'transfer') assert.equal(view.calls.filter(path => path.includes('rename_')).length, before + 1)
    } finally { view.unmount() }
  })
  test(`${f.key}: refreshing keeps old rows, exposes busy status, refresh failure preserves rows, empty success hides pagination`, async () => {
    const view = await viewPage()
    try {
      view.handlers[f.api] = () => f.response([f.row]); await view.click(f.tab); await flush()
      assert.ok(view.findAll(node => node.props['aria-label'] === '下一页').length > 0, 'server pagination is used even with only one rendered row')
      for (const surface of view.surfaces(f.key)) assert.ok(text(surface).includes(f.title), 'disabled module still exposes historical records')
      const refresh = pending(); view.handlers[f.api] = () => refresh.promise
      await view.click('刷新数据')
      assert.equal(view.block(f.key).props['aria-busy'], true)
      assert.ok(text(view.block(f.key)).includes('正在刷新记录，保留上次结果'))
      for (const surface of view.surfaces(f.key)) { assert.ok(text(surface).includes(f.title)); assert.equal(walk(surface, node => hasClass(node, 'dm-table-skeleton')).length, 0) }
      refresh.reject(Error('refresh offline')); await flush()
      for (const surface of view.surfaces(f.key)) {
        assert.ok(text(surface).includes(f.title)); assert.ok(text(surface).includes('刷新失败，保留上次结果'), text(surface))
        assert.equal(walk(surface, node => hasClass(node, 'dm-table-state--refresh')).length, 1)
        assert.equal(walk(surface, node => node.props.role === 'alert').length, 0)
      }
      view.handlers[f.api] = () => f.response([]); await view.click('刷新数据'); await flush()
      for (const surface of view.surfaces(f.key)) {
        assert.ok(text(surface).includes('暂无记录'))
        assert.ok(!text(surface).includes('筛选无结果'))
        assert.equal(walk(surface, node => node.type === 'button' && text(node) === '重置筛选').length, 0)
      }
      assert.equal(view.findAll(node => node.props['aria-label'] === '下一页').length, 0)
      const emptyRefresh = pending(); view.handlers[f.api] = () => emptyRefresh.promise
      await view.click('刷新数据'); emptyRefresh.reject(Error('empty refresh failed')); await flush()
      for (const surface of view.surfaces(f.key)) assert.ok(text(surface).includes('刷新失败，保留上次结果'), 'a previously loaded empty result is still a result')
    } finally { view.unmount() }
  })
}

test('history and archive concurrent retries cannot cancel each other; late older response cannot replace newer history', async () => {
  const view = await viewPage()
  try {
    view.handlers.rename_history = () => Promise.reject(Error('history failed'))
    view.handlers.rename_archive = () => Promise.reject(Error('archive failed'))
    await view.click('命名历史'); await flush()
    const history = pending(), archive = pending()
    view.handlers.rename_history = () => history.promise
    view.handlers.rename_archive = () => archive.promise
    for (const key of ['history', 'archive']) walk(view.surfaces(key)[0], node => node.type === 'button' && text(node) === '重试')[0].props.onClick()
    archive.resolve(fixtures[1].response([fixtures[1].row])); history.resolve(fixtures[0].response([fixtures[0].row])); await flush()
    assert.ok(text(view.block('history')).includes(fixtures[0].title)); assert.ok(text(view.block('archive')).includes(fixtures[1].title))
    const older = pending(); view.handlers.rename_history = () => older.promise
    await view.click('刷新数据')
    view.handlers.rename_history = () => fixtures[0].response([{ ...fixtures[0].row, after_name: '较新的记录.mkv' }])
    await view.click('刷新数据'); await flush()
    older.resolve(fixtures[0].response([{ ...fixtures[0].row, after_name: '过期记录.mkv' }])); await flush()
    assert.ok(text(view.block('history')).includes('较新的记录.mkv')); assert.ok(!text(view.block('history')).includes('过期记录.mkv'))
  } finally { view.unmount() }
})

test('tagcleanup diagnostics render in tag cleanup block; missing detail values become — while zero/false remain real values; zero cleanup buttons disable', async () => {
  const view = await viewPage()
  try {
    view.handlers.diagnostics = () => ({ code: 0, module_details: { tagcleanup: { rows: [
      { label: '空串', value: '' }, { label: '空值', value: null }, { label: '缺失' }, { label: '真实零', value: 0 }, { label: '真实否', value: false },
    ], items: [{ title: '标签清理快照', meta: '下载器 A' }], total: 91, limit: 20, truncated: true } }, cleanup_data: { rename_history: 0, rename_archive: 0 } })
    await view.click('站点标签'); await flush()
    const block = view.findAll(node => node.props['data-record-block'] === 'tag-cleanup-snapshot')[0]
    assert.ok(text(block).includes('标签清理快照')); assert.ok(text(block).includes('共 91 条'))
    const values = walk(block, node => hasClass(node, 'dm-detail-row')).map(node => text(node))
    assert.deepEqual(values, ['空串—', '空值—', '缺失—', '真实零0', '真实否false'])
    await view.click('命名历史'); await flush()
    const cleanup = view.findAll(node => node.type === 'button' && ['清历史', '清归档'].some(label => text(node).startsWith(label)))
    assert.equal(cleanup.length, 2); assert.ok(cleanup.every(node => node.props.disabled === true))
  } finally { view.unmount() }
})

test('transfer legacy record keeps short hash and explicit missing-name label on both surfaces', async () => {
  const view = await viewPage()
  try {
    view.handlers.transfer_status = () => fixtures[2].response([{ ...fixtures[2].row, source_name: '' }])
    await view.click('转移做种'); await flush()
    for (const surface of view.surfaces('transfer')) { assert.ok(text(surface).includes('名称未记录')); assert.ok(text(surface).includes('abcdefgh')); assert.ok(!text(surface).includes('abcdefgh0123456789')) }
  } finally { view.unmount() }
})

const executionCases = [
  ['autoremove', '删种记录'], ['tag', '站点标签'],
  ['tag_cleanup', '站点标签'], ['upload_limit', '上传限速'],
]
const historyRow = (stream, name = '真实执行样本') => ({ record_id: stream + '-1', occurred_at: 1700000000,
  downloader_id: 'QB1', name, site: 'site-a', trigger: 'manual', action: '调整', result: 'success', reason: '实际操作成功', before: 0, after: false })
const historyResult = (items, page = 1, total = items.length) => ({ items, page, page_size: 20, total,
  total_pages: Math.max(1, Math.ceil(total / 20)), initialized: !!items.length })
const historyBlock = (view, stream) => view.findAll(n => n.props['data-execution-stream'] === stream)[0]
for (const [stream, tab] of executionCases) {
  test(`${stream}: actual Page requests history, shows errors/retry, true records and empty state without snapshots`, async () => {
    const view = await viewPage()
    try {
      view.handlers.execution_history = path => {
        const key = new URLSearchParams(path.split('?')[1]).get('module')
        if (key === stream) throw Error('history unavailable')
        return historyResult([])
      }
      await view.click(tab); await flush()
      assert.ok(text(historyBlock(view, stream)).includes('history unavailable'))
      view.handlers.execution_history = path => historyResult([historyRow(new URLSearchParams(path.split('?')[1]).get('module'))])
      walk(historyBlock(view, stream), n => n.type === 'button' && text(n) === '重试')[0].props.onClick()
      await flush()
      assert.ok(text(historyBlock(view, stream)).includes('真实执行样本'))
      assert.ok(text(historyBlock(view, stream)).includes('实际操作成功'))
      assert.ok(!text(historyBlock(view, stream)).includes('当前接口未提供'))
      if (stream === 'upload_limit') {
        assert.ok(text(historyBlock(view, stream)).includes('调整前'))
        assert.ok(text(historyBlock(view, stream)).includes('false'))
      }
      view.handlers.execution_history = () => Promise.reject(Error('refresh lost'))
      await view.click('刷新数据'); await flush()
      assert.ok(text(historyBlock(view, stream)).includes('真实执行样本'))
      assert.ok(text(historyBlock(view, stream)).includes('刷新失败，保留上次结果'))
      view.handlers.execution_history = () => historyResult([])
      await view.click('刷新数据'); await flush()
      assert.ok(text(historyBlock(view, stream)).includes('暂无记录'), text(historyBlock(view, stream)))
      assert.ok(!text(historyBlock(view, stream)).includes('真实执行样本'))
      assert.ok(view.calls.some(p => p.includes('execution_history?module=' + stream)))
    } finally { view.unmount() }
  })
}

test('execution history server pagination, page-size reset, late response isolation and tag streams are independent', async () => {
  const view = await viewPage()
  try {
    view.handlers.execution_history = path => {
      const params = new URLSearchParams(path.split('?')[1])
      const stream = params.get('module'), page = Number(params.get('page'))
      return historyResult([historyRow(stream, stream + '-page-' + page)], page, 43)
    }
    await view.click('站点标签'); await flush()
    const tag = () => historyBlock(view, 'tag')
    const cleanup = () => historyBlock(view, 'tag_cleanup')
    const before = view.calls.length
    walk(tag(), n => n.props['aria-label'] === '下一页')[0].props.onClick(); await flush()
    assert.ok(text(tag()).includes('tag-page-2'))
    assert.ok(text(cleanup()).includes('tag_cleanup-page-1'))
    assert.equal(view.calls.length, before + 1)
    const sizeSelect = walk(tag(), n => n.props['onUpdate:modelValue'] && n.props['aria-label'] === '每页条数')[0]
    assert.ok(sizeSelect, 'actual page-size select')
    const priorSizeCalls = view.calls.length
    sizeSelect.props['onUpdate:modelValue']('50'); await flush()
    assert.equal(view.calls.length, priorSizeCalls + 1, 'page-size emits page 1 without duplicate query')
    assert.ok(view.calls.at(-1).includes('page=1&page_size=50'))
    const older = pending()
    view.handlers.execution_history = path => path.includes('module=tag&') ? older.promise : historyResult([])
    await view.click('刷新数据')
    view.handlers.execution_history = path => historyResult([historyRow('tag', '最新执行')])
    await view.click('刷新数据'); await flush()
    older.resolve(historyResult([historyRow('tag', '过期执行')])); await flush()
    assert.ok(text(tag()).includes('最新执行'))
    assert.ok(!text(tag()).includes('过期执行'))
  } finally { view.unmount() }
})
