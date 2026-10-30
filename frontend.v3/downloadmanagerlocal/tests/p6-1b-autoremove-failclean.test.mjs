import assert from 'node:assert/strict'
import test from 'node:test'
import { defineComponent, h, nextTick } from 'vue'
import { loadSfc, mount } from './helpers/load-sfc.mjs'

globalThis.document ||= { visibilityState: 'hidden', addEventListener() {}, removeEventListener() {} }
globalThis.window ||= { setInterval: () => 0, clearInterval() {} }

const Page = await loadSfc('Page.vue')
const source = await import('node:fs').then(({ readFileSync }) => readFileSync(new URL('../src/components/Page.vue', import.meta.url), 'utf8'))
const components = Object.fromEntries([...new Set([...source.matchAll(/<(V[A-Z]\w*)\b/g)].map(match => match[1]))].map(name => [name, defineComponent({
  inheritAttrs: false,
  props: ['modelValue', 'text'],
  setup(props, { attrs, slots }) {
    return () => h(name === 'VTable' ? 'table' : ['VBtn', 'VListItem'].includes(name) ? 'button' : 'div', attrs, props.text || slots.default?.())
  },
})]))
const text = node => (node.type === '#comment' ? '' : node.text) + node.children.map(text).join('')
const walk = (root, predicate) => {
  const found = []
  const visited = new WeakSet()
  function visit(node) {
    if (!node || visited.has(node)) return
    visited.add(node)
    if (predicate(node)) found.push(node)
    node.children.forEach(visit)
  }
  visit(root)
  return found
}
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
const bounded = (promise, label) => new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error(label + ' timed out')), 2000)
  promise.then(value => { clearTimeout(timer); resolve(value) }, error => { clearTimeout(timer); reject(error) })
})
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const status = {
  autoremove: { enabled: true, last_run_at: 0, candidate_list: [] },
  failclean: { enabled: true, last_scan_time: 0, scan: { scanned: 0, cleaned: 0, failed: 0, skipped: 0 }, event: { deleted: 0, failed: 0, skipped: 0 }, total: { cleaned: 0, failed: 0, skipped: 0 } },
}

async function viewPage(handlers = {}) {
  const api = {
    get: async path => {
      const key = path.split('/').at(-1).split('?')[0]
      if (handlers[key]) return handlers[key](path)
      if (key === 'downloaders') return []
      if (key === 'autoremove_status') return { code: 0, status: status.autoremove }
      if (key === 'failclean_status') return { code: 0, status: status.failclean }
      if (key === 'diagnostics') return { code: 0, module_details: {} }
      if (key === 'overview') return { code: 0, cards: {} }
      if (key === 'hr') return { code: 0, tasks: [], summary: {} }
      return { code: 0 }
    },
    post: async () => { throw Error('P6-1b record state test must not write') },
  }
  const view = mount(Page, { api }, {}, { components })
  await bounded(flush(), 'mount flush')
  const button = label => view.findAll(node => node.type === 'button' && text(node).trim() === label)[0]
  const block = key => view.findAll(node => node.props['data-record-state'] === key)[0]
  return { ...view, handlers, button, block }
}

const candidate = { downloader_id: 'QB', torrent_hash: 'A'.repeat(40), name: '候选样本', site: '站点A', size_text: '1 GiB', ratio: 0.1, seeding_hours: 12, reason: '分享率不足' }

test('P6-1b 自动删种预览：首次骨架、错误重试、刷新失败保留旧候选', async () => {
  const view = await viewPage()
  try {
    const pending = deferred()
    view.handlers.autoremove_status = () => pending.promise
    view.button('删种记录').props.onClick({})
    await bounded(flush(), 'autoremove loading flush')
    const loading = view.block('autoremove')
    assert.equal(loading.props['aria-busy'], true)
    assert.equal(walk(loading, node => node.type === 'th').length, 8)
    assert.equal(walk(loading, node => node.props.class?.includes('dm-table-skeleton')).length, 3)

    pending.reject(Error('autoremove offline'))
    await bounded(flush(), 'autoremove error flush')
    assert.match(text(view.block('autoremove')), /autoremove offline/)
    const retry = walk(view.block('autoremove'), node => node.type === 'button' && text(node).trim() === '重试')[0]
    assert.ok(retry)

    view.handlers.autoremove_status = () => ({ code: 0, status: { enabled: true, last_run_at: 1710000000, candidate_list: [candidate] } })
    retry.props.onClick({})
    await bounded(flush(), 'autoremove retry flush')
    assert.match(text(view.block('autoremove')), /候选样本/)

    const refresh = deferred()
    view.handlers.autoremove_status = () => refresh.promise
    view.button('刷新数据').props.onClick({})
    await bounded(nextTick(), 'autoremove refresh tick')
    assert.match(text(view.block('autoremove')), /候选样本/)
    refresh.reject(Error('autoremove refresh offline'))
    await bounded(flush(), 'autoremove refresh error flush')
    assert.match(text(view.block('autoremove')), /候选样本/)
    assert.match(text(view.block('autoremove')), /刷新失败，保留上次结果/)
  } finally { view.unmount() }
})

test('P6-1b 自动删种与失败清理区分尚未扫描、扫描无候选和来源明细', async () => {
  const view = await viewPage()
  try {
    view.handlers.autoremove_status = () => ({ code: 0, status: { enabled: true, last_run_at: 1710000000, candidate_list: [] } })
    view.handlers.failclean_status = () => ({ code: 0, status: { enabled: true, last_scan_time: 1710000000, scan: { scanned: 0, cleaned: 0, failed: 0, skipped: 0 }, event: { deleted: 0, failed: 0, skipped: 0 }, total: { cleaned: 0, failed: 0, skipped: 0 } } })
    view.button('删种记录').props.onClick({}); await bounded(flush(), 'autoremove empty flush')
    assert.match(text(view.block('autoremove')), /扫描无候选/)
    view.button('失败清理').props.onClick({}); await bounded(flush(), 'failclean empty flush')
    assert.match(text(view.block('failclean')), /扫描无候选/)

    view.handlers.failclean_status = () => ({ code: 0, status: {
      enabled: true,
      last_scan_time: 1710000000,
      scan: { scanned: 4, cleaned: 2, failed: 1, skipped: 1 },
      event: { deleted: 3, failed: 0, skipped: 2 },
      total: { cleaned: 5, failed: 1, skipped: 3 },
    } })
    view.button('刷新数据').props.onClick({}); await bounded(flush(), 'failclean detail flush')
    const block = view.block('failclean')
    assert.match(text(block), /来源事件/)
    assert.match(text(block), /上轮巡检/)
    assert.match(text(block), /累计/)
    assert.match(text(block), /来源事件[\s\S]*3/)
    assert.match(text(block), /上轮巡检[\s\S]*4/)
  } finally { view.unmount() }
})
