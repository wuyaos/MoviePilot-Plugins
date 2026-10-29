import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { defineComponent, h, nextTick } from 'vue'
import { loadSfc, mount } from './helpers/load-sfc.mjs'

const source = readFileSync(new URL('../src/components/Config.vue', import.meta.url), 'utf8')
const component = await loadSfc('Config.vue')

// Stub only the Vuetify presentation boundary. Config's setup, template, handlers,
// reactivity and local JS/SFC dependencies are compiled and executed unchanged.
// The host is the existing Vue in-memory renderer, not a browser/Vuetify test.
const components = Object.fromEntries([...new Set([...source.matchAll(/<(V[A-Z]\w*)\b/g)].map(match => match[1]))].map(name => [name, defineComponent({
  name: name + 'TestBoundary',
  inheritAttrs: false,
  props: ['modelValue', 'label'],
  emits: ['update:modelValue'],
  setup(props, { attrs, slots, emit }) {
    return () => {
      if (name === 'VDialog' && !props.modelValue) return null
      if (name === 'VTextField' || name === 'VTextarea') {
        return h('input', { ...attrs, 'aria-label': props.label, value: props.modelValue,
          onInput: event => emit('update:modelValue', event.target.value) })
      }
      return h(name === 'VBtn' || name === 'VListItem' ? 'button' : 'div', attrs, slots.default?.())
    }
  },
})]))
const text = node => (node.type.startsWith('#') ? (node.type === '#text' ? node.text : '') : node.text) + node.children.map(text).join('')
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
async function mountConfig(initialConfig = {}, put = async () => ({ success: true }), target = component) {
  const calls = []
  const events = []
  const props = {
    initialConfig, pluginId: 'DownloadManagerLocal',
    api: {
      get: async path => path.endsWith('/hr_presets') ? { presets: [] } : [],
      put: (path, payload) => { calls.push([path, payload]); return put(path, payload) },
    },
    onSwitch: (...args) => events.push(['switch', ...args]),
    onSave: (...args) => events.push(['save', ...args]),
    onClose: (...args) => events.push(['close', ...args]),
  }
  const view = mount(target, props, {}, { components })
  await flush()
  const button = label => {
    const matches = view.findAll(node => node.type === 'button' && text(node).trim() === label)
    assert.equal(matches.length, 1, 'Expected one rendered button: ' + label)
    return matches[0]
  }
  const click = async label => {
    const node = button(label)
    assert.equal(typeof node.props.onClick, 'function', label + ' must have a template click binding')
    node.props.onClick({ type: 'click' })
    await nextTick()
  }
  const status = () => view.findAll(node => node.props.role === 'status')
  return { ...view, calls, events, button, click, status }
}

test('点击「查看数据」只触发 switch，不触发 save 或 PUT', async () => {
  const view = await mountConfig()
  try {
    await view.click('查看数据')
    assert.deepEqual(view.events, [['switch']])
    assert.deepEqual(view.calls, [])
    assert.deepEqual(view.status(), [])
  } finally { view.unmount() }
})

test('点击「保存配置」经 plugin PUT 自保存，提示成功并复位 pending，不触发 save', async () => {
  const request = deferred()
  const initialConfig = { rename_exclude_tags: 'keep-me', transfer_tasks: '[]', hr_site_config_str: '', custom_config: 'preserved' }
  const view = await mountConfig(initialConfig, () => request.promise)
  try {
    assert.equal(view.button('保存配置').props.disabled, false)
    await view.click('保存配置')
    assert.equal(view.calls.length, 1)
    assert.equal(view.calls[0][0], 'plugin/DownloadManagerLocal')
    for (const [key, value] of Object.entries(initialConfig)) assert.deepEqual(view.calls[0][1][key], value, 'PUT payload: ' + key)
    assert.equal(view.button('保存配置').props.loading, true)
    assert.equal(view.button('保存配置').props.disabled, true)
    assert.deepEqual(view.events, [])
    request.resolve({ success: true, message: 'ok' })
    await flush()
    const [status] = view.status()
    assert.equal(view.status().length, 1)
    assert.equal(text(status), '配置已保存，窗口保持打开；如需同步插件列表/侧边导航，请刷新页面。')
    assert.equal(status.props['aria-live'], 'polite')
    assert.doesNotMatch(status.props.class || '', /text-error/)
    assert.equal(view.button('保存配置').props.loading, false)
    assert.equal(view.button('保存配置').props.disabled, false)
    assert.deepEqual(view.events, [])
  } finally { request.resolve({ success: true }); view.unmount() }
})

test('点击保存失败展示 response.data.message/error 样式，保留已编辑表单并复位 pending', async () => {
  const request = deferred()
  const view = await mountConfig({ rename_exclude_tags: 'initial-value' }, () => request.promise)
  try {
    const field = () => view.findAll(node => node.type === 'input' && node.props['aria-label'] === '排除标签')[0]
    assert.equal(field().props.value, 'initial-value')
    field().props.onInput({ target: { value: 'edited-keep-me' } })
    await nextTick()
    await view.click('保存配置')
    assert.equal(view.calls.length, 1)
    assert.equal(view.calls[0][0], 'plugin/DownloadManagerLocal')
    assert.equal(view.calls[0][1].rename_exclude_tags, 'edited-keep-me')
    assert.equal(view.button('保存配置').props.disabled, true)
    request.reject({ message: 'must not use outer message', response: { data: { message: '后端拒绝保存' } } })
    await flush()
    const [status] = view.status()
    assert.equal(view.status().length, 1)
    assert.equal(text(status), '后端拒绝保存')
    assert.match(status.props.class, /text-error/)
    assert.equal(status.props['aria-live'], 'polite')
    assert.equal(field().props.value, 'edited-keep-me')
    assert.equal(view.button('保存配置').props.loading, false)
    assert.equal(view.button('保存配置').props.disabled, false)
    assert.deepEqual(view.events, [])
  } finally { request.resolve({ success: true }); view.unmount() }
})

test('断链对照：仅在内存移除两个 @click 后，渲染按钮不再派发事件/PUT', async () => {
  const disconnected = await loadSfc('Config.vue', { transformSource: (value, filename) => {
    if (!filename.endsWith('Config.vue')) return value
    for (const binding of ['@click="switchToData"', '@click="saveConfig"']) {
      assert.ok(value.includes(binding), 'Mutation target must exist: ' + binding)
      value = value.replace(binding, '')
    }
    return value
  } })
  const view = await mountConfig({}, undefined, disconnected)
  try {
    for (const label of ['查看数据', '保存配置']) {
      const button = view.button(label)
      assert.equal(button.props.onClick, undefined)
      button.props.onClick?.({ type: 'click' })
      await nextTick()
    }
    assert.deepEqual(view.events, [])
    assert.deepEqual(view.calls, [])
    assert.deepEqual(view.status(), [])
  } finally { view.unmount() }
})
