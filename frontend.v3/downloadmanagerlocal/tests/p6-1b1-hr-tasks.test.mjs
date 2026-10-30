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
const bounded = (promise, label = 'bounded wait') => new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error(label + ' timed out')), 2000)
  promise.then(value => { clearTimeout(timer); resolve(value) }, error => { clearTimeout(timer); reject(error) })
})
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }

async function viewPage(initialHandlers = {}) {
  const handlers = {}
  Object.assign(handlers, initialHandlers)
  const api = {
    get: async path => {
      const key = path.split('/').at(-1).split('?')[0]
      if (handlers[key]) return handlers[key](path)
      if (key === 'downloaders') return []
      return { code: 0 }
    },
    post: async () => { throw Error('H&R state test must not write') },
  }
  const view = mount(Page, { api }, {}, { components })
  await bounded(flush(), 'mount flush')
  const button = label => view.findAll(node => node.type === 'button' && text(node).trim() === label)[0]
  const block = () => view.findAll(node => node.props['data-record-block'] === 'hr-tasks')[0]
  return { ...view, handlers, button, block }
}

test('P6-1b-1: H&R 首次加载保留表头并显示骨架，失败后仅本块重试', async () => {
  const tasks = deferred()
  const view = await viewPage({ tasks: () => tasks.promise })
  try {
    view.button('H&R 任务').props.onClick({})
    await bounded(flush(), 'loading flush')
    const loading = view.block()
    assert.equal(loading.props['aria-busy'], true)
    assert.equal(walk(loading, node => node.type === 'th').length, 10)
    assert.equal(walk(loading, node => node.props.class?.includes('dm-table-skeleton')).length, 3)
    tasks.reject(Error('hr offline'))
    await bounded(flush(), 'error flush')
    assert.match(text(view.block()), /hr offline/)
    assert.equal(walk(view.block(), node => node.props.role === 'alert').length, 1)
    view.handlers.tasks = () => ({ tasks: [{ downloader_id: 'QB', torrent_hash: 'abcdef0123456789', name: 'H&R 样本', status: 'Pending' }], summary: { total: 1, compliant: 0, needs_seeding: 1 } })
    const retry = walk(view.block(), node => node.type === 'button' && text(node) === '重试')[0]
    assert.ok(retry)
    retry.props.onClick()
    await bounded(flush(), 'retry flush')
    assert.match(text(view.block()), /H&R 样本/)
  } finally { view.unmount() }
})

test('P6-1b-1: H&R 正常行、筛选空态、清理按钮禁用与刷新失败保留旧行', async () => {
  const view = await viewPage()
  try {
    view.handlers.tasks = () => ({ tasks: [{ downloader_id: 'QB', torrent_hash: 'abcdef0123456789', name: '达标样本', status: 'Compliant' }], summary: { total: 1, compliant: 0, needs_seeding: 0 } })
    view.button('H&R 任务').props.onClick(); await bounded(flush(), 'normal flush')
    assert.match(text(view.block()), /达标样本/)
    const clearButtons = view.findAll(node => node.type === 'button' && /清理(达标|缺失)记录/.test(text(node)))
    assert.equal(clearButtons.length, 2)
    assert.ok(clearButtons.every(node => node.props.disabled === true))
    const refresh = deferred()
    view.handlers.tasks = () => refresh.promise
    const refreshButton = view.button('刷新数据')
    assert.ok(refreshButton)
    refreshButton.props.onClick(); await bounded(nextTick(), 'refresh tick')
    assert.match(text(view.block()), /达标样本/)
    refresh.reject(Error('hr refresh offline')); await bounded(flush(), 'refresh error flush')
    assert.match(text(view.block()), /达标样本/)
    assert.match(text(view.block()), /刷新失败，保留上次结果/)
  } finally { view.unmount() }
})

test('P6-1b-1: H&R 状态筛选无结果显示筛选空态且仍保留表头', async () => {
  const view = await viewPage()
  try {
    view.handlers.tasks = () => ({ tasks: [{ downloader_id: 'QB', torrent_hash: 'abcdef0123456789', name: '待处理样本', status: 'Pending' }], summary: { total: 1, compliant: 0, needs_seeding: 0 } })
    view.button('H&R 任务').props.onClick(); await bounded(flush(), 'filter flush')
    const select = view.findAll(node => node.props['aria-label'] === '考核状态')[0]
    assert.ok(select)
    assert.equal(typeof select.props['onUpdate:modelValue'], 'function')
    select.props['onUpdate:modelValue']('Compliant')
    await bounded(nextTick(), 'filter tick')
    assert.match(text(view.block()), /筛选无结果/)
    assert.equal(walk(view.block(), node => node.type === 'th').length, 10)
    assert.doesNotMatch(text(view.block()), /待处理样本/)
  } finally { view.unmount() }
})
