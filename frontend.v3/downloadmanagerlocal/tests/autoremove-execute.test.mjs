import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import { defineComponent, h, nextTick } from 'vue'
import { loadSfc, mount } from './helpers/load-sfc.mjs'

globalThis.document = { visibilityState: 'hidden', addEventListener() {}, removeEventListener() {} }
globalThis.window = { setInterval: () => 0, clearInterval() {} }
const Page = await loadSfc('Page.vue')
const source = readFileSync(new URL('../src/components/Page.vue', import.meta.url), 'utf8')
const components = Object.fromEntries([...new Set([...source.matchAll(/<(V[A-Z]\w*)\b/g)].map(m => m[1]))].map(name => [name, defineComponent({
  inheritAttrs: false, props: ['modelValue', 'text'],
  setup(props, { attrs, slots }) {
    return () => h(name === 'VBtn' || name === 'VListItem' ? 'button' : 'div', { ...attrs, 'data-component': name, 'data-open': props.modelValue }, props.text || slots.default?.())
  },
})]))
const text = node => (node.type === '#comment' ? '' : node.text) + node.children.map(text).join('')
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }

for (const observe of [true, false]) test(`auto remove rendered confirmation, cancel, and exactly one request (observe=${observe})`, async () => {
  const calls = []
  let finish
  const api = {
    get: async path => {
      const key = path.split('/').at(-1).split('?')[0]
      if (key === 'downloaders') return []
      if (key === 'autoremove_status') return { code: 0, status: { enabled: true, observe_only: observe, action: 'deletefile', candidate_list: [] } }
      if (key === 'overview') return { code: 0, cards: {} }
      if (key === 'diagnostics') return { code: 0, module_details: {} }
      return { code: 0 }
    },
    post: (...args) => { calls.push(args); return new Promise(resolve => { finish = resolve }) },
  }
  const view = mount(Page, { api }, {}, { components })
  const button = label => {
    const matches = view.findAll(node => node.type === 'button' && text(node).trim() === label)
    const inside = (root, node) => root === node || root.children.some(child => inside(child, node))
    const opened = dialogs()
    return opened.length ? matches.find(node => opened.some(dialog => inside(dialog, node))) : matches[0]
  }
  const dialogs = () => view.findAll(node => node.props['data-component'] === 'VDialog' && node.props['data-open'] === true)
  try {
    await flush()
    button('删种记录').props.onClick({}); await flush()
    button('按当前配置执行').props.onClick({}); await flush()
    assert.equal(calls.length, 0, 'opening confirmation never executes')
    assert.equal(dialogs().length, 1)
    assert.match(text(dialogs()[0]), observe ? /仅扫描候选/ : /文件删除不可撤销/)
    button('取消').props.onClick({}); await flush()
    assert.equal(dialogs().length, 0)
    assert.equal(calls.length, 0)
    button('按当前配置执行').props.onClick({}); await flush()
    const confirm = button('确认执行')
    confirm.props.onClick({}); confirm.props.onClick({}); await flush()
    assert.equal(calls.length, 1, 'double click must not duplicate requests')
    assert.match(calls[0][0], /\/autoremove_run$/)
    assert.equal(dialogs().length, 0)
    finish({ code: 0, msg: 'test success' }); await flush()
  } finally { view.unmount() }
})
