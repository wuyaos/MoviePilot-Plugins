import { MODULE_ICONS } from '../src/components/module-icons.js'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { reactive, ref, computed, watch, effectScope, nextTick, defineComponent, h } from 'vue'
import { loadSfc, mount as renderMount } from './helpers/load-sfc.mjs'

const source = readFileSync(new URL('../src/components/Config.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace(/^/, `const MODULE_ICONS = ${JSON.stringify(MODULE_ICONS)};\n`)
const setup = new Function('reactive', 'ref', 'computed', 'watch', 'onMounted', 'defineProps', 'defineEmits', 'getPluginApi', `${script}\nreturn { form, transferTasks, transferForm, transferStatusTasks, openTransferDialog, confirmTransferTask, transferDeleteMeta, transferDeleteItems, saveConfig };`)

function mountSetup(initialConfig = {}) {
  const scope = effectScope()
  const calls = []
  const props = reactive({
    initialConfig,
    pluginId: 'DownloadManagerLocal',
    api: { put: async (_path, payload) => { calls.push(JSON.parse(JSON.stringify(payload))); return { success: true } } },
  })
  const state = scope.run(() => setup(
    reactive, ref, computed, watch, () => {}, () => props,
    () => () => {}, () => { throw new Error('Unexpected network request') },
  ))
  return { ...state, calls, stop: () => scope.stop() }
}

test('隐藏默认设置仍保留已存值，新任务用默认开关状态提示且不固化继承', async () => {
  const state = mountSetup({ transfer_delete_source_default: true, transfer_delete_duplicate_default: false })
  try {
    assert.deepEqual(state.transferDeleteItems(state.form.transfer_delete_source_default)[0], { title: '默认（开启）', value: 'inherit' })
    assert.deepEqual(state.transferDeleteItems(state.form.transfer_delete_duplicate_default)[0], { title: '默认（关闭）', value: 'inherit' })
    state.openTransferDialog()
    assert.deepEqual([state.transferForm.delete_source, state.transferForm.delete_duplicate], ['inherit', 'inherit'])
    await state.saveConfig()
    assert.equal(state.calls.at(-1).transfer_delete_source_default, true)
    assert.equal(state.calls.at(-1).transfer_delete_duplicate_default, false)
  } finally { state.stop() }
})
test('删源/删重复三态经过应用与保存 payload 原样保留', async () => {
  const state = mountSetup({
    transfer_tasks: JSON.stringify([
      { name: 'true-task', from_downloader: 'QB', to_downloader: 'TR', delete_source: true, delete_duplicate: false },
      { name: 'inherit-task', from_downloader: 'QB', to_downloader: 'TR', delete_source: 'inherit', delete_duplicate: 'inherit' },
      { name: 'missing-task', from_downloader: 'QB', to_downloader: 'TR' },
    ]),
  })
  try {
    assert.deepEqual(state.transferTasks.value.map(task => [task.delete_source, task.delete_duplicate]), [
      [true, false], ['inherit', 'inherit'], [false, true],
    ])

    await state.saveConfig()
    const saved = JSON.parse(state.calls.at(-1).transfer_tasks)
    assert.deepEqual(saved.map(task => [task.delete_source, task.delete_duplicate]), [
      [true, false], ['inherit', 'inherit'], [false, true],
    ])
    assert.equal(state.calls.at(-1).transfer_tasks.includes('"inherit":true'), false)

    state.openTransferDialog()
    assert.deepEqual([state.transferForm.delete_source, state.transferForm.delete_duplicate], ['inherit', 'inherit'])
    state.transferForm.from_downloader = 'QB'
    state.transferForm.to_downloader = 'TR'
    state.transferForm.delete_source = false
    state.transferForm.delete_duplicate = 'inherit'
    state.confirmTransferTask()
    assert.deepEqual(
      [state.transferTasks.value.at(-1).delete_source, state.transferTasks.value.at(-1).delete_duplicate],
      [false, 'inherit'],
    )
  } finally {
    state.stop()
  }
})

test('来源映射逐项使用 transfer_status 投影，缺失不回退表单值', () => {
  const state = mountSetup({
    transfer_tasks: JSON.stringify([{ name: 'status-task', delete_source: false, delete_duplicate: 'inherit' }]),
  })
  try {
    const task = state.transferTasks.value[0]
    state.transferStatusTasks.value = [{
      name: 'status-task',
      delete_source_origin: 'task',
      delete_source_effective: true,
      delete_duplicate_origin: 'global',
      delete_duplicate_effective: false,
    }]
    assert.deepEqual(state.transferDeleteMeta(task, 'delete_source'), { origin: '任务覆盖', effective: '开启' })
    assert.deepEqual(state.transferDeleteMeta(task, 'delete_duplicate'), { origin: '继承全局', effective: '关闭' })

    state.transferStatusTasks.value = [{ name: 'status-task', delete_source_origin: 'legacy-default', delete_source_effective: false }]
    assert.deepEqual(state.transferDeleteMeta(task, 'delete_source'), { origin: '升级前默认', effective: '关闭' })
    assert.deepEqual(state.transferDeleteMeta(task, 'delete_duplicate'), { origin: '—', effective: '—' })
    state.transferStatusTasks.value = []
    assert.deepEqual(state.transferDeleteMeta(task, 'delete_source'), { origin: '—', effective: '—' })
  } finally {
    state.stop()
  }
})

const component = await loadSfc('Config.vue')
const components = Object.fromEntries([...new Set([...source.matchAll(/<(V[A-Z]\w*)\b/g)].map(match => match[1]))].map(name => [name, defineComponent({
  inheritAttrs: false,
  props: ['modelValue', 'label'],
  emits: ['update:modelValue'],
  setup(props, { attrs, slots, emit }) {
    return () => {
      if (name === 'VDialog' && !props.modelValue) return null
      if (['VSwitch', 'VCheckbox', 'VTextField', 'VTextarea', 'VSelect', 'VCombobox', 'VCronField'].includes(name)) {
        return h('input', { ...attrs, 'aria-label': props.label, value: props.modelValue, onChange: value => emit('update:modelValue', value) })
      }
      return h(['VBtn', 'VListItem'].includes(name) ? 'button' : 'div', attrs, slots.default?.())
    }
  },
})]))

function treeText(node) {
  return (node.type === '#comment' ? '' : node.text) + node.children.map(treeText).join('')
}

function visible(node) {
  return !node || (node.style.display !== 'none' && visible(node.parent))
}

test('任务列表渲染来源与生效值文本，并对缺失投影显示破折号', async () => {
  const statusTasks = [{
    name: 'render-task',
    delete_source_origin: 'task',
    delete_source_effective: true,
    delete_duplicate_origin: 'global',
    delete_duplicate_effective: false,
  }]
  const view = renderMount(component, {
    initialConfig: { transfer_tasks: JSON.stringify([{ name: 'render-task', from_downloader: 'QB', to_downloader: 'TR', delete_source: 'inherit', delete_duplicate: true }]) },
    api: {
      get: async path => path.includes('transfer_status') ? { tasks: statusTasks } : (path.endsWith('/hr_presets') ? { presets: [] } : []),
      put: async () => ({ success: true }),
    },
  }, {}, { components })
  try {
    await new Promise(resolve => setImmediate(resolve))
    await nextTick()
    const taskTab = view.findAll(node => node.type === 'button' && treeText(node).trim() === '任务列表' && visible(node))[0]
    taskTab.props.onClick({})
    await nextTick()
    const text = treeText(view.root)
    assert.match(text, /删源：来源 任务覆盖，生效 开启/)
    assert.match(text, /删重复：来源 继承全局，生效 关闭/)

    const missingView = renderMount(component, {
      initialConfig: { transfer_tasks: JSON.stringify([{ name: 'missing-render', from_downloader: 'QB', to_downloader: 'TR', delete_source: true, delete_duplicate: false }]) },
      api: { get: async path => path.includes('transfer_status') ? { tasks: [] } : (path.endsWith('/hr_presets') ? { presets: [] } : []), put: async () => ({ success: true }) },
    }, {}, { components })
    try {
      await new Promise(resolve => setImmediate(resolve)); await nextTick()
      const missingTab = missingView.findAll(node => node.type === 'button' && treeText(node).trim() === '任务列表' && visible(node))[0]
      missingTab.props.onClick({}); await nextTick()
      const missingText = treeText(missingView.root)
      assert.match(missingText, /删源：来源 —，生效 —/)
      assert.match(missingText, /删重复：来源 —，生效 —/)
    } finally {
      missingView.unmount()
    }
  } finally {
    view.unmount()
  }
})
