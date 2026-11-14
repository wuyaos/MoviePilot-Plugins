import { MODULE_ICONS } from '../src/components/module-icons.js'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { reactive, ref, computed, watch, effectScope, nextTick, defineComponent, h } from 'vue'
import { loadSfc, mount as renderMount } from './helpers/load-sfc.mjs'

const source = readFileSync(new URL('../src/components/Config.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace(/^/, `const MODULE_ICONS = ${JSON.stringify(MODULE_ICONS)};\n`)
const setup = new Function('reactive', 'ref', 'computed', 'watch', 'onMounted', 'defineProps', 'defineEmits', 'getPluginApi', `${script}\nreturn { form, transferTasks, transferForm, openTransferDialog, confirmTransferTask, transferDeleteMeta, transferDeleteItems, saveConfig, taskFilterChips };`)

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


test('旧无标签字段被丢弃，标签摘要与保存遵守包含标签硬条件', async () => {
  const state = mountSetup({ transfer_tasks: JSON.stringify([
    { name: 'strict', from_downloader: 'TR', to_downloader: 'QB', include_labels: '已转移', empty_label_ok: true },
    { name: 'unrestricted', from_downloader: 'TR', to_downloader: 'QB', include_labels: '', empty_label_ok: false },
  ]) })
  try {
    assert.deepEqual(state.taskFilterChips(state.transferTasks.value[0]), ['不限分类', '标签 已转移'])
    assert.deepEqual(state.taskFilterChips(state.transferTasks.value[1]), ['不限分类'])
    assert.doesNotMatch(source, /v-model="transferForm.empty_label_ok"/)
    assert.match(source, /hint="必须包含全部指定标签；无标签种子跳过。留空不限制标签"/)
    await state.saveConfig()
    const saved = JSON.parse(state.calls.at(-1).transfer_tasks)
    assert.deepEqual(saved.map(task => task.include_labels), ['已转移', ''])
    assert.ok(saved.every(task => !Object.hasOwn(task, 'empty_label_ok')))
  } finally { state.stop() }
})
test('全局删除设置仍保留已存值，新任务用默认开关状态提示且不固化继承', async () => {
  const state = mountSetup({ transfer_delete_source_default: true, transfer_delete_duplicate_default: false })
  try {
    assert.deepEqual(state.transferDeleteItems(state.form.transfer_delete_source_default)[0], { title: '继承全局（当前：开启）', value: 'inherit' })
    assert.deepEqual(state.transferDeleteItems(state.form.transfer_delete_duplicate_default)[0], { title: '继承全局（当前：关闭）', value: 'inherit' })
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

test('删除策略按当前配置展示，不依赖首次运行，关闭规则仍有来源和生效值', () => {
  const state = mountSetup({
    enabled: false, transfer_delete_source_default: true, transfer_delete_duplicate_default: true,
    transfer_tasks: JSON.stringify([{ name: 'not-run', enabled: false, delete_source: 'inherit', delete_duplicate: 'inherit' }]),
  })
  try {
    const task = state.transferTasks.value[0]
    assert.deepEqual(state.transferDeleteMeta(task, 'delete_source'), { origin: '继承全局', effective: '开启' })
    assert.deepEqual(state.transferDeleteMeta(task, 'delete_duplicate'), { origin: '继承全局', effective: '开启' })
    state.form.transfer_delete_source_default = false
    assert.deepEqual(state.transferDeleteMeta(task, 'delete_source'), { origin: '继承全局', effective: '关闭' })
    task.delete_source = true
    assert.deepEqual(state.transferDeleteMeta(task, 'delete_source'), { origin: '任务覆盖', effective: '开启' })
    task.delete_duplicate = false
    assert.deepEqual(state.transferDeleteMeta(task, 'delete_duplicate'), { origin: '任务覆盖', effective: '关闭' })
    assert.deepEqual(state.transferDeleteMeta({}, 'delete_source'), { origin: '升级前默认', effective: '关闭' })
    assert.deepEqual(state.transferDeleteMeta({}, 'delete_duplicate'), { origin: '升级前默认', effective: '开启' })
  } finally { state.stop() }
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

test('真实任务列表按表单配置渲染删除策略，不受旧状态或缺失状态影响', async () => {
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
    assert.match(text, /删源：来源 继承全局，生效 关闭/)
    assert.match(text, /删重复：来源 任务覆盖，生效 开启/)

    const missingView = renderMount(component, {
      initialConfig: { transfer_tasks: JSON.stringify([{ name: 'missing-render', from_downloader: 'QB', to_downloader: 'TR', delete_source: true, delete_duplicate: false }]) },
      api: { get: async path => path.includes('transfer_status') ? { tasks: [] } : (path.endsWith('/hr_presets') ? { presets: [] } : []), put: async () => ({ success: true }) },
    }, {}, { components })
    try {
      await new Promise(resolve => setImmediate(resolve)); await nextTick()
      const missingTab = missingView.findAll(node => node.type === 'button' && treeText(node).trim() === '任务列表' && visible(node))[0]
      missingTab.props.onClick({}); await nextTick()
      const missingText = treeText(missingView.root)
      assert.match(missingText, /删源：来源 任务覆盖，生效 开启/)
      assert.match(missingText, /删重复：来源 任务覆盖，生效 关闭/)
    } finally {
      missingView.unmount()
    }
  } finally {
    view.unmount()
  }
})


test("旧单链路缺任务键时迁移，显式空列表与迁移标记不复活旧任务", async () => {
  const legacy = { fromdownloader: "QB", todownloader: "TR", deletesource: false, deleteduplicate: true, frompath: "/old", topath: "/new" }
  for (const [extra, count] of [[{}, 1], [{ transfer_tasks: "[]" }, 0], [{ transfer_tasks_migrated: true }, 0]]) {
    const state = mountSetup({ ...legacy, ...extra })
    try {
      assert.equal(state.transferTasks.value.length, count)
      await state.saveConfig()
      const saved = JSON.parse(state.calls.at(-1).transfer_tasks)
      assert.equal(saved.length, count)
      if (count) {
        assert.equal(saved[0].from_downloader, "QB")
        assert.equal(saved[0].to_downloader, "TR")
        assert.equal(saved[0].delete_source, false)
        assert.equal(saved[0].delete_duplicate, true)
        assert.equal(saved[0].from_path, "/old")
      }
    } finally { state.stop() }
  }
})
