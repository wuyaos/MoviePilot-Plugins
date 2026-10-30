import { MODULE_ICONS } from '../src/components/module-icons.js'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { reactive, ref, computed, watch, effectScope, nextTick } from 'vue'

// Execute the entire setup in source order, not extracted parser functions:
// immediate watchers must see every dependency initialized on first mount.
const source = readFileSync(new URL('../src/components/Config.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace(/^/, `const MODULE_ICONS = ${JSON.stringify(MODULE_ICONS)};\n`)
const setup = new Function('reactive', 'ref', 'computed', 'watch', 'onMounted', 'defineProps', 'defineEmits', 'getPluginApi',
  `${script}\nreturn { form, transferTasks, hrCustomRules, hrRawError, saveConfig, switchToData, tagCatPairs, tagCategoryRows, tagCategoryNames, tagCategoriesError, tagCategoriesLoaded, loadTagCategories, setTagCategoryTarget, uploadNewSiteName, uploadAddError, addUploadSiteRule, setUploadSiteRule };`)

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

test('自定义站点限速和可编辑分类来源保留原配置结构，不要求站点库候选', async () => {
  const state = mount({ tag_all_cat: ['电影'], tag_all_cat_rename: ['Movies'], upload_limit_site_rules: {} })
  try {
    state.uploadNewSiteName.value = 'CustomFixture'
    state.addUploadSiteRule()
    state.setUploadSiteRule('CustomFixture', 1024)
    state.uploadNewSiteName.value = 'customfixture'
    state.addUploadSiteRule()
    assert.match(state.uploadAddError.value, /已存在/)
    assert.equal(Object.keys(state.form.upload_limit_site_rules).length, 1)
    state.tagCatPairs.value[0].from = '自定义来源'
    await state.saveConfig()
    const saved = state.calls[0][1]
    assert.deepEqual(saved.upload_limit_site_rules, { CustomFixture: { limit_kib: 1024 } })
    assert.deepEqual(saved.tag_all_cat, ['自定义来源'])
    assert.deepEqual(saved.tag_all_cat_rename, ['Movies'])
  } finally { state.stop() }
})

test('MP 分类加载去重且不修改已保存映射；编辑目标才创建新映射', async () => {
  const state = mount({ tag_all_cat: ['电影', '旧分类'], tag_all_cat_rename: ['Movies', 'Legacy'] })
  try {
    const requests = []
    state.props.api.get = async path => { requests.push(path); return { success: true, message: '', data: { 电影: ['电影', '动画'], 电视剧: ['动画', '剧集'] } } }
    await state.loadTagCategories()
    assert.deepEqual(requests, ['media/category'])
    assert.equal(state.tagCategoriesLoaded.value, true)
    assert.deepEqual(state.tagCategoryRows.value.map(row => [row.from, row.to, row.legacy]), [
      ['电影', 'Movies', false], ['动画', '动画', false], ['剧集', '剧集', false], ['旧分类', 'Legacy', true],
    ])
    assert.equal(state.tagCatPairs.value.length, 2)
    await state.saveConfig()
    assert.deepEqual(state.calls[0][1].tag_all_cat, ['电影', '旧分类'])
    state.setTagCategoryTarget('动画', 'Anime')
    state.setTagCategoryTarget('电影', 'Films')
    await state.saveConfig()
    assert.deepEqual(state.calls[1][1].tag_all_cat, ['电影', '旧分类', '动画'])
    assert.deepEqual(state.calls[1][1].tag_all_cat_rename, ['Films', 'Legacy', 'Anime'])
    state.props.api.get = async () => ({ 电视剧: ['剧集'] })
    await state.loadTagCategories()
    assert.equal(state.tagCategoryRows.value.find(row => row.from === '动画').to, 'Anime')
    assert.equal(state.tagCategoryRows.value.find(row => row.from === '动画').legacy, true)
  } finally { state.stop() }
})

test('MP 分类失败或无分类时不回填固定默认、不清空旧映射', async () => {
  const state = mount({ tag_all_cat: ['保留来源'], tag_all_cat_rename: ['保留目标'] })
  try {
    for (const result of [{ success: false, message: '接口失败', data: null }, { success: true, data: [] }, { 电影: [1] }]) {
      state.props.api.get = async () => result
      await state.loadTagCategories()
      assert.ok(state.tagCategoriesError.value)
      assert.deepEqual(state.tagCategoryRows.value.map(row => row.from), ['保留来源'])
    }
    state.props.api.get = async () => { throw new Error('Network failed') }
    await state.loadTagCategories()
    assert.equal(state.tagCategoriesError.value, 'Network failed')
    state.props.api.get = async () => ({ success: true, message: '', data: { 电影: [], 电视剧: [] } })
    await state.loadTagCategories()
    assert.equal(state.tagCategoriesError.value, '')
    assert.deepEqual(state.tagCategoryNames.value, [])
    await state.saveConfig()
    assert.deepEqual(state.calls[0][1].tag_all_cat, ['保留来源'])
    assert.deepEqual(state.calls[0][1].tag_all_cat_rename, ['保留目标'])
  } finally { state.stop() }
})
