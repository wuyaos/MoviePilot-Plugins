import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { reactive, ref, computed, watch, effectScope, nextTick } from 'vue'

// Execute the entire setup in source order, not extracted parser functions:
// immediate watchers must see every dependency initialized on first mount.
const source = readFileSync(new URL('../src/components/Config.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
const setup = new Function('reactive', 'ref', 'computed', 'watch', 'onMounted', 'defineProps', 'defineEmits', 'getPluginApi',
  `${script}\nreturn { form, transferTasks, hrCustomRules, hrRawError, saveConfig, switchToData };`)

function mount(initialConfig) {
  const scope = effectScope()
  const emitted = []
  const calls = []
  const props = reactive({
    initialConfig,
    pluginId: 'DownloadManagerLocal',
    api: { put: async (path, payload) => { calls.push([path, payload]); return { success: true } } },
  })
  try {
    const state = scope.run(() => setup(reactive, ref, computed, watch, () => {}, () => props,
      () => (...args) => emitted.push(args), () => { throw new Error('Unexpected network request') }))
    return { ...state, props, emitted, calls, stop: () => scope.stop() }
  } catch (error) {
    scope.stop()
    throw error
  }
}

const tasks = [{ name: 'seed-test', enabled: true, from_downloader: 'QB-test', to_downloader: 'TR-test' }]
const tierYaml = "- site_name: 'TestSite'\n  hr_duration: 48\n  hr_size_tiers:\n    - max_size_gib: 100\n      hr_duration: 72\n      hr_deadline_days: 30\n"
const configs = [
  ['empty', {}],
  ['plain H&R rules', { hr_site_config_str: "- site_name: 'TestSite'\n  hr_duration: 48\n" }],
  ['tiered H&R rules', { hr_site_config_str: tierYaml }],
  ['invalid H&R YAML', { hr_site_config_str: 'not a site rule' }],
]
for (const [name, config] of configs) {
  test(`initial setup and save preserve transfer tasks with ${name}`, async () => {
    const state = mount({ ...config, transfer_tasks: JSON.stringify(tasks) })
    try {
      assert.equal(state.transferTasks.value.length, 1)
      assert.equal(state.transferTasks.value[0].name, 'seed-test')
      if (name === 'tiered H&R rules') assert.equal(state.hrCustomRules.value[0].hr_size_tiers[0].hr_duration, 72)
      if (name === 'invalid H&R YAML') assert.match(state.hrRawError.value, /YAML/)
      await state.saveConfig()
      const saved = state.calls[0][1]
      assert.equal(state.emitted.some(([event]) => event === 'save'), false)
      assert.equal(JSON.parse(saved.transfer_tasks)[0].name, 'seed-test')
      assert.equal(saved.hr_site_config_str, config.hr_site_config_str ?? '')
    } finally { state.stop() }
  })
}

test('async config delivery also initializes tiered rules and transfer tasks', async () => {
  const state = mount({})
  try {
    state.props.initialConfig = { transfer_tasks: JSON.stringify(tasks), hr_site_config_str: tierYaml }
    await nextTick()
    assert.equal(state.transferTasks.value.length, 1)
    assert.equal(state.hrCustomRules.value[0].hr_size_tiers[0].hr_duration, 72)
  } finally { state.stop() }
})

test('observe-only switches follow decision A defaults and legacy migration', async () => {
  // 全新安装：七个观察开关默认开启
  const fresh = mount({})
  try {
    await nextTick()
    assert.equal(fresh.form.transfer_observe_only, true)
    assert.equal(fresh.form.remover_observe_only, true)
    assert.equal(fresh.form.upload_limit_observe_only, true)
  } finally { fresh.stop() }

  // 老配置升级：保持升级前行为（关闭）
  const legacy = mount({ transfer_tasks: JSON.stringify(tasks) })
  try {
    await nextTick()
    assert.equal(legacy.form.transfer_observe_only, false)
    assert.equal(legacy.form.remover_observe_only, false)
  } finally { legacy.stop() }

  // 自动删种继承旧「仅观察不执行」开关
  const migrated = mount({ migration_observe_only: true })
  try {
    await nextTick()
    assert.equal(migrated.form.remover_observe_only, true)
  } finally { migrated.stop() }

  // 已保存过新键时旧键不再覆盖
  const upgraded = mount({ migration_observe_only: true, remover_observe_only: false })
  try {
    await nextTick()
    assert.equal(upgraded.form.remover_observe_only, false)
  } finally { upgraded.stop() }
})
