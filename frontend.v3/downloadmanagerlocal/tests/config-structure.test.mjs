import assert from 'node:assert/strict'
import { readFileSync, existsSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { spawnSync } from 'node:child_process'
import { renderToString } from 'vue/server-renderer'
import test from 'node:test'
import { reactive, ref, computed, watch, effectScope, nextTick, defineComponent, h, createSSRApp } from 'vue'
import { loadSfc, mount as renderMount } from './helpers/load-sfc.mjs'

const source = readFileSync(new URL('../src/components/Config.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
const setup = new Function('reactive', 'ref', 'computed', 'watch', 'onMounted', 'defineProps', 'defineEmits', 'getPluginApi', `${script}\nreturn { form, defaults, PANE_RESET_KEYS, OBSERVE_ONLY_KEYS, selectMain, activeSub, currentSubs, askPaneReset, confirmPaneReset, saveConfig, transferTasks, openTransferDialog, transferForm, confirmTransferTask, tagCatPairs, tagTrackerPairs, hrCustomRules };`)
function mount(initialConfig) {
  const scope = effectScope()
  const calls = []
  const props = reactive({ initialConfig, pluginId: 'DownloadManagerLocal', api: { put: async (path, payload) => { calls.push(structuredClone(JSON.parse(JSON.stringify(payload)))); return { success: true } } } })
  const state = scope.run(() => setup(reactive, ref, computed, watch, () => {}, () => props, () => () => {}, () => { throw Error('Unexpected network request') }))
  return { ...state, calls, stop: () => scope.stop() }
}
const observeKeys = ['transfer_observe_only', 'hr_observe_only', 'remover_observe_only', 'failcleanup_observe_only', 'rename_observe_only', 'tag_observe_only', 'upload_limit_observe_only']
const panes = ['transfer', 'hr', 'remover', 'failclean', 'rename', 'tag', 'upload']
const off = Object.fromEntries(observeKeys.map(key => [key, false]))

test('P2-1d: each pane reset enables only its own observation, stays local until save, and resets only owned keys', async () => {
  for (const [index, pane] of panes.entries()) {
    const state = mount({ ...off, compat_future: { keep: [false, 0, ''] }, hr_protection_enabled: false })
    try {
      const owners = Object.values(state.PANE_RESET_KEYS).flat()
      assert.equal(new Set(owners).size, owners.length, 'reset sets must not overlap')
      for (const key of state.PANE_RESET_KEYS[pane]) state.form[key] = typeof state.defaults[key] === 'boolean' ? !state.defaults[key] : 'edited:' + key
      state.form[observeKeys[index]] = false
      const before = JSON.parse(JSON.stringify(state.form))
      assert.deepEqual(new Set(owners), new Set(Object.keys(state.defaults).filter(key => !['enabled', 'migration_observe_only'].includes(key))), 'every module default is registered')
      const prefixes = { hr: 'hr_', remover: 'remover_', failclean: 'failcleanup_', rename: 'rename_', tag: 'tag_', upload: 'upload_limit_' }
      for (const [owner, keys] of Object.entries(state.PANE_RESET_KEYS)) if (prefixes[owner]) assert.ok(keys.every(key => key.startsWith(prefixes[owner])), owner + ' has a foreign reset key')
      const legacyTransferResetKeys = ['transfer_enabled', 'delay_minutes', 'notify', 'transfer_fallback_enabled', 'transfer_fallback_interval_minutes', 'fromdownloader', 'todownloader', 'frompath', 'topath', 'fromtorrentpath', 'nopaths', 'nolabels', 'includelabels', 'includecategory', 'transferemptylabel', 'add_torrent_tags', 'deletesource', 'deleteduplicate', 'remainoldcat', 'remainoldtag', 'transfer_tasks', 'transfer_rename_enabled', 'downloader_ext', 'seed_autostart', 'seed_skipverify', 'seed_check_interval', 'seed_max_wait_minutes', 'scan_limit', 'pause_source', 'transfer_observe_only']
      const newTransferResetKeys = ['transfer_delete_source_default', 'transfer_delete_duplicate_default']
      assert.equal(state.PANE_RESET_KEYS.transfer.length, legacyTransferResetKeys.length + newTransferResetKeys.length)
      assert.deepEqual(legacyTransferResetKeys.filter(key => !state.PANE_RESET_KEYS.transfer.includes(key)), [])
      assert.deepEqual(state.PANE_RESET_KEYS.transfer.filter(key => !legacyTransferResetKeys.includes(key)), newTransferResetKeys)
      assert.deepEqual(newTransferResetKeys.filter(key => !state.PANE_RESET_KEYS.transfer.includes(key)), [])
      state.askPaneReset(pane)
      state.confirmPaneReset()
      await nextTick()
      assert.equal(state.calls.length, 0, 'reset must not write remotely')
      for (const [key, value] of Object.entries(before)) {
        const expected = state.PANE_RESET_KEYS[pane].includes(key) ? (key === observeKeys[index] ? true : state.defaults[key]) : value
        assert.deepEqual(JSON.parse(JSON.stringify(state.form[key])), expected, pane + ':' + key)
      }
      await state.saveConfig()
      assert.equal(state.calls[0][observeKeys[index]], true)
    } finally { state.stop() }
  }
})

test('P2-1d: fresh install observes; explicit false and legacy missing keys survive open, tab changes, save and reopen', async () => {
  for (const config of [{}, { ...off }, { enabled: true }, { migration_observe_only: true }]) {
    const state = mount(config)
    let reopened
    try {
      const expected = observeKeys.map(key => !Object.keys(config).length || (key === 'remover_observe_only' && config.migration_observe_only === true))
      for (const pane of panes) { state.selectMain(pane); await nextTick() }
      await state.saveConfig()
      reopened = mount(state.calls[0])
      assert.deepEqual(observeKeys.map(key => reopened.form[key]), expected)
    } finally { reopened?.stop(); state.stop() }
  }
})

test('P2-1d: unvisited/hidden values and unknown compatibility keys survive save → reopen → save; wire types stay unchanged', async () => {
  const config = { ...off, enabled: false, tag_siteprefix: '', rename_event_debounce_seconds: 0,
    rename_movie_format: '  {{ title }}, {{ original_name }}  ', rename_tv_format: '{{ title }}\n {{ year }} ',
    rename_exclude_dirs: '/keep path/\n/another/', rename_hash_white_list: 'ABCD\nEF01',
    hr_enabled: true, hr_protection_enabled: false, hr_site_config_str: "# preserve raw YAML\n- site_name: 'Legacy'\n  hr_duration: 72\n",
    tag_rename_type: true, tag_all_cat: ['movie'], tag_all_cat_rename: ['影片'], tag_path_rename: '/keep path/#原样\n/z/#第二',
    tag_tracker_mappings_str: 'tracker.test->legacy.test', tag_custom_sites_str: 'legacy.test -> 私有站\nold.test -> 未映射旧值',
    transfer_tasks: JSON.stringify([{ name: 'fixture', from_downloader: 'QB', to_downloader: 'TR', delete_source: false, compat_task: { keep: 1 } }]),
    downloader_ext: JSON.stringify({ QB: { webui_url: '', source_plugin: '', compat_ext: { keep: 0 } } }),
    upload_limit_site_rules: { Legacy: { limit_kib: 0, future_rule: false } }, compat_future: { value: [false, 0, '', { untouched: true }] } }
  const state = mount(config)
  let reopened
  try {
    await state.saveConfig() // No tab has been visited.
    const saved = state.calls[0]
    for (const [key, value] of Object.entries(config)) {
      if (key === 'transfer_tasks' || key === 'downloader_ext') {
        assert.equal(typeof saved[key], 'string', key + ' remains an outer JSON string')
        if (key === 'downloader_ext') assert.deepEqual(JSON.parse(saved[key]), JSON.parse(value))
        else assert.deepEqual(JSON.parse(saved[key])[0].compat_task, { keep: 1 })
      } else assert.deepEqual(saved[key], value, key)
    }
    reopened = mount(saved)
    await reopened.saveConfig()
    assert.deepEqual(reopened.calls[0], saved, 'save → reopen must be value-equivalent')
    reopened.openTransferDialog(0)
    reopened.transferForm.name = 'edited fixture'
    reopened.confirmTransferTask()
    await reopened.saveConfig()
    assert.deepEqual(JSON.parse(reopened.calls[1].transfer_tasks)[0].compat_task, { keep: 1 }, 'editing known fields must retain unknown task keys')
    reopened.tagTrackerPairs.value[0].custom = '编辑标签'
    await reopened.saveConfig()
    assert.match(reopened.calls[2].tag_custom_sites_str, /old\.test -> 未映射旧值/, 'editing a mapped row must not delete unrelated legacy labels')
  } finally { reopened?.stop(); state.stop() }
})

test('P2-1d: legacy subpage destinations land on retained content, and pane reset refreshes mapping/rule editors', async () => {
  const state = mount({ tag_all_cat: ['old'], tag_all_cat_rename: ['旧'], hr_site_config_str: "- site_name: 'Old'\n  hr_duration: 72" })
  try {
    for (const [pane, old, target] of [['transfer', 'seed_basic', 'basic'], ['hr', 'hr_advanced', 'hr_basic'], ['remover', 'remover_conditions', 'remover_basic']]) {
      state.selectMain(pane); state.activeSub.value = old; await nextTick()
      assert.equal(state.activeSub.value, target)
    }
    state.askPaneReset('tag'); state.confirmPaneReset(); await nextTick()
    assert.deepEqual(state.tagCatPairs.value, [])
    state.askPaneReset('hr'); state.confirmPaneReset(); await nextTick()
    assert.deepEqual(state.hrCustomRules.value, [])
  } finally { state.stop() }
})

// Compile the real SFC. Only Vuetify presentation is replaced by editable controls;
// navigation/model handlers and v-show/conditional content are the actual template.
const component = await loadSfc('Config.vue')
const components = Object.fromEntries([...new Set([...source.matchAll(/<(V[A-Z]\w*)\b/g)].map(match => match[1]))].map(name => [name, defineComponent({
  inheritAttrs: false, props: ['modelValue', 'label'], emits: ['update:modelValue'],
  setup(props, { attrs, slots, emit }) { return () => {
    if (name === 'VDialog' && !props.modelValue) return null
    if (['VSwitch', 'VCheckbox', 'VTextField', 'VTextarea', 'VSelect', 'VCombobox', 'VCronField'].includes(name)) return h('input', { ...attrs, 'aria-label': props.label, value: props.modelValue, onChange: value => emit('update:modelValue', value) })
    return h(['VBtn', 'VListItem'].includes(name) ? 'button' : 'div', attrs, slots.default?.())
  } },
})]))
const text = node => (node.type === '#comment' ? '' : node.text) + node.children.map(text).join('')
const visible = node => !node || (node.style.display !== 'none' && visible(node.parent))
async function viewConfig(config) {
  const calls = []
  const view = renderMount(component, { initialConfig: config, api: { get: async path => path.endsWith('/hr_presets') ? { presets: [] } : [], put: async (_path, payload) => { calls.push(JSON.parse(JSON.stringify(payload))); return { success: true } } } }, {}, { components })
  await new Promise(resolve => setImmediate(resolve)); await nextTick()
  const nodes = label => view.findAll(node => node.type === 'input' && node.props['aria-label'] === label && visible(node))
  const field = label => { const matches = nodes(label); assert.equal(matches.length, 1, 'visible field: ' + label); return matches[0] }
  const click = async (label, index = 0) => { const matches = view.findAll(node => node.type === 'button' && text(node).trim() === label && visible(node)); assert.ok(matches[index], 'button: ' + label); assert.notEqual(matches[index].props.disabled, true, label); matches[index].props.onClick({}); await nextTick() }
  const change = async (label, value) => { const node = field(label); assert.notEqual(node.props.disabled, true, label + ' must be editable'); node.props.onChange(value); await nextTick() }
  return { ...view, field, click, change, calls }
}

test('P2-1d: rendered tabs retain seed checks, H&R baseline/more, remover rules and task draft apply/cancel', async () => {
  const view = await viewConfig({ transfer_enabled: true })
  try {
    view.field('检查间隔（秒）')
    await view.click('任务列表'); await view.click('添加任务')
    await view.change('任务名称', 'draft'); await view.change('源下载器', 'QB'); await view.change('目标下载器', 'TR')
    await view.click('应用任务')
    assert.ok(view.findAll(node => node.props['aria-label'] === '编辑任务').length)
    await view.click('保存配置')
    assert.equal(JSON.parse(view.calls[0].transfer_tasks)[0].name, 'draft')
    const edit = view.findAll(node => node.props['aria-label'] === '编辑任务')[0]
    edit.props.onClick({}); await nextTick()
    await view.change('任务名称', 'cancelled draft')
    await view.click('取消', 1) // The footer cancel remains a separate, explicit host action.
    await view.click('保存配置')
    assert.equal(JSON.parse(view.calls[1].transfer_tasks)[0].name, 'draft')
    edit.props.onClick({}); await nextTick()
    await view.change('任务名称', 'applied edit'); await view.click('应用任务')
    assert.equal(view.calls.length, 2, 'apply only edits the form')
    await view.click('保存配置')
    assert.equal(JSON.parse(view.calls[2].transfer_tasks)[0].name, 'applied edit')
    await view.click('H&R 管理'); view.field('检查间隔（分钟）'); view.field('记录保留（天）')
    await view.click('站点规则'); view.field('做种时长（小时）')
    await view.click('自动删种'); view.field('做种时长（小时）'); view.field('错误关键词')
    await view.click('种子重命名'); await view.click('模板与过滤'); view.field('电影模板'); view.field('Hash 白名单')
    await view.click('分类与标签'); await view.click('映射规则'); view.field('分类方式')
    await view.change('分类方式', true); await view.change('路径映射', '/keep path/#分类')
    await view.change('分类方式', false); await view.click('保存配置')
    assert.equal(view.calls.at(-1).tag_path_rename, '/keep path/#分类')
    await view.change('分类方式', true)
    assert.equal(view.field('路径映射').props.value, '/keep path/#分类')
    await view.click('上传限速'); await view.click('限速规则')
    await view.click('基础设置'); await view.click('恢复默认'); await view.click('恢复默认', 1)
    assert.equal(view.field('观察模式').props.value, true)
    assert.equal(view.calls.length, 4, 'reset confirmation must not save')
    await checkNativeFolds()
  } finally { view.unmount() }
})

test('P2-1d: dependent controls disable/re-enable without clearing values; unrelated failure event settings remain editable', async () => {
  const view = await viewConfig({ transfer_fallback_enabled: true, transfer_fallback_interval_minutes: 91, failcleanup_clean_repeat: true, failcleanup_cron: '1 2 * * *', failcleanup_retain_hours: 9, rename_on_download_added: true, rename_event_debounce_seconds: 7, rename_cron_enabled: true, rename_cron: '2 3 * * *', hr_notify: 'always', hr_notify_summary_cron: '4 5 * * *', hr_enable_site_config: true, hr_site_config_str: "- site_name: 'Fixture'\n  hr_duration: 72\n" })
  try {
    for (const [pane, toggle, fields] of [
      [null, '兜底扫描', ['兜底间隔（分钟）']],
      ['失败清理', '清理重复残留', ['巡检计划', '残留保留（小时）']],
      ['种子重命名', '入列触发', ['事件防抖（秒）']],
      [null, '定时补查', ['补查计划']],
    ]) {
      if (pane) await view.click(pane)
      const values = fields.map(label => view.field(label).props.value)
      await view.change(toggle, false)
      for (const [index, label] of fields.entries()) { assert.equal(view.field(label).props.disabled, true, label); assert.equal(view.field(label).props.value, values[index]) }
      if (pane === '失败清理') { assert.notEqual(view.field('发送通知').props.disabled, true); assert.notEqual(view.field('启用').props.disabled, true) }
      await view.change(toggle, true)
      for (const [index, label] of fields.entries()) { assert.notEqual(view.field(label).props.disabled, true); assert.equal(view.field(label).props.value, values[index]) }
      await view.change(toggle, false)
    }
    await view.click('H&R 管理')
    const cron = view.field('汇总计划').props.value
    await view.change('通知模式', 'none'); assert.equal(view.field('汇总计划').props.disabled, true); assert.equal(view.field('汇总计划').props.value, cron)
    await view.change('通知模式', 'always'); assert.notEqual(view.field('汇总计划').props.disabled, true)
    await view.click('站点规则'); await view.click('编辑 YAML')
    const yaml = view.field('站点规则').props.value
    await view.click('基础设置'); await view.change('站点独立规则', false); await view.click('站点规则')
    assert.equal(view.field('站点规则').props.disabled, true); assert.equal(view.field('站点规则').props.value, yaml)
    assert.notEqual(view.field('做种时长（小时）').props.disabled, true, 'global baseline is not disabled by site-specific switch')
    await view.click('基础设置'); await view.change('站点独立规则', true); await view.click('站点规则')
    assert.notEqual(view.field('站点规则').props.disabled, true); assert.equal(view.field('站点规则').props.value, yaml)
    await view.click('保存配置')
    assert.equal(view.calls[0].hr_site_config_str, yaml)
    assert.equal(view.calls[0].hr_notify_summary_cron, cron)
    assert.equal(view.calls[0].failcleanup_cron, '1 2 * * *'); assert.equal(view.calls[0].rename_event_debounce_seconds, 7)
    assert.equal(view.calls[0].transfer_fallback_interval_minutes, 91); assert.equal(view.calls[0].rename_cron, '2 3 * * *')
  } finally { view.unmount() }
})
// Native disclosure behavior is checked in Chrome against the real rendered SFC
// markup, with only Vuetify controls stubbed. This is not MoviePilot host acceptance.
async function checkNativeFolds() {
  const app = createSSRApp(component, { initialConfig: { rename_hash_white_list: 'keep-hash', hr_exclude_tags: ['keep tag'] } })
  for (const [name, stub] of Object.entries(components)) app.component(name, stub)
  const html = await renderToString(app)
  const folds = [...html.matchAll(/<details\b[\s\S]*?<\/details>/g)].map(match => match[0])
  assert.equal(folds.length, 5)
  const chrome = process.env.CHROME_BIN || ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe', '/usr/bin/chromium', '/usr/bin/google-chrome', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'].find(file => existsSync(file))
  assert.ok(chrome, 'Disclosure regression requires Chrome/Chromium; set CHROME_BIN')
  const dir = mkdtempSync(path.join(os.tmpdir(), 'dml-config-folds-'))
  try {
    const file = path.join(dir, 'folds.html')
    writeFileSync(file, '<!doctype html><meta charset="utf-8">' + folds.join('') + '<pre id="result"></pre><script>' + 
      `const result = [...document.querySelectorAll('details')].map(fold => {
        const summary = fold.querySelector('summary'); const fields = [...fold.querySelectorAll('input')];
        const before = fields.map(field => field.value); const closed = !fold.open && fields.every(field => !field.checkVisibility());
        summary.focus(); const focusable = document.activeElement === summary;
        summary.click(); const opened = fold.open && fields.every(field => field.checkVisibility());
        summary.click(); return { title: summary.textContent, closed, focusable, opened, closedAgain: !fold.open, retained: JSON.stringify(before) === JSON.stringify(fields.map(field => field.value)) };
      }); document.getElementById('result').textContent = JSON.stringify(result);` + '</script>')
    const result = spawnSync(chrome, ['--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--user-data-dir=' + path.join(dir, 'profile'), '--dump-dom', pathToFileURL(file).href], { encoding: 'utf8', timeout: 20000, maxBuffer: 1024 * 1024 })
    assert.equal(result.error, undefined, result.error?.message); assert.equal(result.status, 0, result.stderr)
    const match = result.stdout.match(/<pre id="result">([^<]+)<\/pre>/)
    assert.ok(match, 'Browser must return native disclosure observations')
    const observations = JSON.parse(match[1])
    assert.deepEqual(observations.map(item => item.title), ['更多设置', '更多条件与连带处理', '可用变量与示例', '更多过滤', '标签删除权限'])
    for (const item of observations) for (const key of ['closed', 'focusable', 'opened', 'closedAgain', 'retained']) assert.equal(item[key], true, item.title + ':' + key)
    console.log('Config native disclosures:', JSON.stringify(observations))
  } finally { rmSync(dir, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 }) }
}

