import { MODULE_ICONS } from '../src/components/module-icons.js'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { computed, nextTick, reactive, ref, watch } from 'vue'

// Page.vue 切页签会读 document.visibilityState 并调 window.setInterval；
// 只给最小桩，且 setInterval 不真正排程，避免测试进程被定时器挂住。
globalThis.document = globalThis.document || { visibilityState: 'hidden', addEventListener() {}, removeEventListener() {} }
globalThis.window = globalThis.window || { setInterval: () => 0, clearInterval() {} }
// 沿用 config-setup.test.mjs 的执行方式：整份 <script setup> 按源码顺序执行，
// 只替换 API 与生命周期边界（页面只读展示函数不触发请求），不引入 DOM 依赖。
const source = readFileSync(new URL('../src/components/Page.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace(/^/, `const MODULE_ICONS = ${JSON.stringify(MODULE_ICONS)};\n`)
const setup = new Function(
  'reactive', 'ref', 'computed', 'watch', 'nextTick', 'onMounted', 'onBeforeUnmount',
  'defineProps', 'defineEmits', 'getPluginApi', 'postPluginApi', 'postPluginJsonApi',
  `${script}\nreturn { transferSourceName, transferPrimaryText, transferSecondaryText, hrTaskTitle, detailLimit, DETAIL_LIMIT_CHOICES, diagnostics, moduleDetail, loadDiagnostics, loadOverviewTab, refreshActive, selectTab, activeTab, tabs, page, archivePage, cleanupCounts, cleanupTargetKey, cleanupConfirmDialog, cleanupRunning, CLEANUP_TARGETS, confirmCleanupData, openCleanupDialog, autoremovePreview, MODULE_RECORD_VIEWS, MODULE_CLEANUP_KEYS, moduleRecordView, moduleCleanupButtons, openModuleRecords };`)

function mount() {
  const props = reactive({ api: null, pluginId: 'DownloadManagerLocal', sourcePluginId: 'DownloadManagerLocal' })
  const fail = () => { throw new Error('展示函数不应发起请求') }
  return setup(reactive, ref, computed, watch, nextTick, () => {}, () => {},
    () => props, () => () => {}, fail, fail, fail)
}

const page = mount()
const template = source.slice(source.indexOf('</script>'))
const HASH40 = 'A'.repeat(40)

test('源种子名缺失或空白时回退「名称未记录」，短 hash 仅作辅助', () => {
  const records = [
    { source_hash: HASH40 },
    { source_hash: HASH40, source_name: '' },
    { source_hash: HASH40, source_name: '   ' },
    { source_hash: HASH40, source_name: null },
  ]
  for (const record of records) {
    assert.equal(page.transferPrimaryText(record), '名称未记录')
    assert.equal(page.transferSecondaryText(record), 'AAAAAAAA')
  }
  assert.equal(page.transferPrimaryText({}), '名称未记录')
  assert.equal(page.transferSecondaryText({}), '—')
})

test('中文与长名称原样返回：不截断、不做 HTML 处理，转义交给 Vue 文本插值', () => {
  const longName = '某站点 [ASW] 2024 年度合集 第一季 第01-12话 1080p BDRip HEVC 简繁外挂字幕'
  assert.equal(page.transferSourceName({ source_name: `  ${longName}  ` }), longName)
  assert.equal(page.transferPrimaryText({ source_name: longName, source_hash: HASH40 }), longName)
  assert.equal(
    page.transferSourceName({ source_name: '<b>标签</b> & 引号" 结束' }),
    '<b>标签</b> & 引号" 结束',
    '含尖括号/和号的名称原样返回，由模板插值转义，不做二次编码')
})

test('H&R 任务标题种子名优先，缺失时「名称未记录 + 短 hash」', () => {
  assert.equal(page.hrTaskTitle({ name: '在保任务.mkv', site: '站点A', torrent_hash: HASH40 }), '在保任务.mkv')
  assert.equal(page.hrTaskTitle({ name: '  ', site: '站点A', torrent_hash: HASH40 }), '名称未记录 · AAAAAAAA')
  assert.equal(page.hrTaskTitle({ torrent_hash: HASH40 }), '名称未记录 · AAAAAAAA')
  assert.equal(page.hrTaskTitle({}), '名称未记录')
  assert.equal(page.hrTaskTitle(null), '名称未记录')
})

test('模板使用文本插值渲染名称：无 v-html，三处转移列表 + 两处 H&R 标题，且不再裸渲染 hash', () => {
  assert.ok(!/v-html/.test(source), 'Page.vue 不允许用 v-html 渲染名称')
  assert.equal((template.match(/transferPrimaryText\(/g) || []).length, 2, '在途事务与最近记录各复用单表')
  assert.equal((template.match(/transferSecondaryText\(/g) || []).length, 2)
  assert.equal((template.match(/hrTaskTitle\(/g) || []).length, 2, 'H&R 单表的名称与操作菜单各引用一次')
  assert.ok(!/transferShortHash\(/.test(template), '列表不再直接渲染裸 hash，改由辅助文案函数提供')
})

// —— 步骤6：首次总览/页签刷新/条数选择 的请求行为（记录型 harness）——
function deferred() {
  let settle
  const promise = new Promise(resolve => { settle = resolve })
  return { promise, resolve: settle }
}

function mountRecording(handlers = {}) {
  const calls = []
  const props = reactive({ api: {}, pluginId: 'DownloadManagerLocal', sourcePluginId: 'DownloadManagerLocal' })
  const unmounts = []
  const getPluginApi = (api, pluginId, path, options) => {
    calls.push({ kind: 'get', path, options })
    const handler = handlers[path.split('?')[0]]
    return Promise.resolve(typeof handler === 'function' ? handler(path) : { code: 0 })
  }
  const record = (kind) => (api, pluginId, path, payload) => {
    calls.push({ kind, path, payload })
    return Promise.resolve({ code: 0, msg: '' })
  }
  const page = setup(reactive, ref, computed, watch, nextTick, () => {}, unmount => { unmounts.push(unmount) },
    () => props, () => () => {}, getPluginApi, record('post'), record('postJson'))
  return { page, calls, unmount: () => unmounts.forEach(unmount => unmount()) }
}

test('进入总览即读取诊断明细，一轮刷新只取一次且带上限参数', async () => {
  const { page: instance, calls } = mountRecording()
  await instance.loadOverviewTab()
  const diagnosticsCalls = calls.filter(call => call.path.startsWith('diagnostics'))
  assert.equal(diagnosticsCalls.length, 1, '总览刷新只取一次诊断')
  assert.equal(diagnosticsCalls[0].path, 'diagnostics?detail_limit=20')
  assert.ok(calls.some(call => call.path === 'overview'), '总览数据照常读取')
})

test('切模块页签与诊断页签都读取诊断，诊断页不重复请求', async () => {
  const { page: instance, calls } = mountRecording()
  await instance.selectTab('hr')
  assert.equal(calls.filter(call => call.path.startsWith('diagnostics')).length, 1)
  assert.ok(calls.some(call => call.path === 'hr/tasks'))
  calls.length = 0
  await instance.selectTab('diagnostics')
  assert.equal(calls.filter(call => call.path.startsWith('diagnostics')).length, 1, '诊断页不重复取诊断')
  assert.ok(calls.some(call => call.path === 'upload_limit_status'))
})

test('改明细条数只刷新诊断：不重载业务数据、不写配置', async () => {
  const { page: instance, calls } = mountRecording()
  await instance.loadOverviewTab()
  calls.length = 0
  instance.detailLimit.value = 200
  await nextTick()
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(calls.map(call => call.path), ['diagnostics?detail_limit=200'])
  assert.equal(calls.filter(call => call.kind !== 'get').length, 0, '条数选择不落盘、不改配置')
})

test('明细请求乱序返回：旧请求的响应不覆盖新响应', async () => {
  const queue = []
  const { page: instance } = mountRecording({
    diagnostics: () => {
      const pending = deferred()
      queue.push(pending)
      return pending.promise
    },
  })
  const request = { revision: 0, pluginId: 'DownloadManagerLocal', tab: 'overview' }
  const older = instance.loadDiagnostics(request)
  const newer = instance.loadDiagnostics(request)
  queue[1].resolve({ code: 0, marker: 'newer', module_details: {} })
  await newer
  queue[0].resolve({ code: 0, marker: 'older', module_details: {} })
  await older
  assert.equal(instance.diagnostics.value.marker, 'newer', '先发后到的响应被丢弃')
})

test('页面销毁后返回的响应不再写入状态', async () => {
  const queue = []
  const { page: instance, unmount } = mountRecording({
    diagnostics: () => {
      const pending = deferred()
      queue.push(pending)
      return pending.promise
    },
  })
  const request = { revision: 0, pluginId: 'DownloadManagerLocal', tab: 'overview' }
  const pending = instance.loadDiagnostics(request)
  unmount()
  queue[0].resolve({ code: 0, marker: 'late', module_details: {} })
  await pending
  assert.ok(!instance.diagnostics.value, '销毁后不写状态')
})

test('moduleDetail 带出 total/limit/truncated 并兼容旧响应', () => {
  const rows = [{ label: '失败记录', value: '34' }]
  const items = [{ title: '某种子.mkv', meta: '失败' }]
  page.diagnostics.value = { module_details: { rename: { rows, items } } }
  assert.deepEqual(page.moduleDetail('rename'), { rows, items, error: '', total: 1, limit: 20, truncated: false })
  page.diagnostics.value = { module_details: { rename: { rows, items, error: '读取失败', total: 34, limit: 20, truncated: true } } }
  assert.deepEqual(page.moduleDetail('rename'), { rows, items, error: '读取失败', total: 34, limit: 20, truncated: true })
  page.diagnostics.value = null
  assert.deepEqual(page.moduleDetail('rename'), { rows: [], items: [], error: '', total: 0, limit: 20, truncated: false })
})

test('条数白名单与后端一致，模板提供选择器与截断提示', () => {
  assert.deepEqual(page.DETAIL_LIMIT_CHOICES, [20, 50, 100, 200], '须与后端 MODULE_DETAIL_LIMIT_CHOICES 一致')
  assert.match(template, /:truncated="moduleDetail\('tagcleanup'\)\.truncated"/)
  assert.match(template, /:truncated="moduleDetail\('autoremove'\)\.truncated"/)
  assert.ok(!/moduleDetail\(card\.key\)\.items/.test(template), '总览卡不再展示运行明细')
  assert.ok(!/共 20 条/.test(template), '不得硬编码条数')
})

// —— 步骤12：查看记录 / 清理记录 入口 ——

const TAB_KEYS = ['overview', 'transfer', 'history', 'hr', 'autoremove', 'failclean', 'sitetag', 'upload', 'diagnostics']
const MODULE_KEYS = ['transfer', 'seed', 'hr', 'autoremove', 'failclean', 'tag', 'rename', 'upload_limit']

test('查看记录映射覆盖有记录的七个模块，页签与锚点都必须真实存在', () => {
  assert.deepEqual(Object.keys(page.MODULE_RECORD_VIEWS).sort(),
    ['autoremove', 'failclean', 'hr', 'rename', 'tag', 'transfer', 'upload_limit'])
  for (const [key, view] of Object.entries(page.MODULE_RECORD_VIEWS)) {
    assert.ok(TAB_KEYS.includes(view.tab), `${key} 的页签 ${view.tab} 不存在`)
    if (view.anchor) {
      const attribute = view.anchor.replace(/^\[|\]$/g, '')
      assert.ok(template.includes(attribute), `${key} 锚点 ${attribute} 未出现在模板中`)
    }
  }
  // seed 只保留现有说明，不造第八套记录
  assert.equal(page.moduleRecordView('seed'), null)
  for (const key of MODULE_KEYS.filter(item => item !== 'seed')) assert.ok(page.moduleRecordView(key), `${key} 缺少查看记录`)
})

test('模块卡清理按钮严格映射后端白名单，无记录模块不给清理入口', () => {
  const items = Object.values(page.MODULE_CLEANUP_KEYS).flat()
  assert.deepEqual([...new Set(items.map(item => item.key))].sort(),
    ['autoremove_state', 'failclean_state', 'rename_archive', 'rename_history'])
  for (const item of items) assert.ok(page.CLEANUP_TARGETS[item.key], `${item.key} 不在 CLEANUP_TARGETS 内`)
  assert.deepEqual(page.moduleCleanupButtons('rename').map(item => item.label), ['清理历史', '清理归档'], '重命名历史与归档是两个独立按钮')
  for (const key of ['transfer', 'hr', 'tag', 'upload_limit', 'seed']) {
    assert.deepEqual(page.moduleCleanupButtons(key), [], `${key} 不应有清理按钮`)
  }
  for (const item of items) assert.ok(!/全部/.test(item.label), '不得提供「全部清理」按钮')
})

test('清理按钮 0 条禁用，数量取自诊断 cleanup_data', () => {
  page.diagnostics.value = { cleanup_data: { rename_history: 34, rename_archive: 31, autoremove_state: 1, failclean_state: 0 } }
  assert.deepEqual(page.moduleCleanupButtons('rename').map(item => item.count), [34, 31])
  assert.equal(page.moduleCleanupButtons('autoremove')[0].count, 1)
  assert.equal(page.moduleCleanupButtons('failclean')[0].count, 0, '0 条时按钮禁用')
  page.diagnostics.value = null
  assert.deepEqual(page.moduleCleanupButtons('rename').map(item => item.count), [0, 0], '诊断缺失时按 0 处理，不误报有记录')
  assert.match(template, /:cleanup-blocked="!cleanupCounts\.rename_history"/)
  assert.match(template, /:cleanup-blocked="!cleanupCounts\.rename_archive"/)
  assert.match(template, /@cleanup="openCleanupDialog\('rename_history'\)"/)
  assert.match(template, /@cleanup="openCleanupDialog\('rename_archive'\)"/)
})

test('查看记录只切页签 + 定位：全过程零写请求', async () => {
  const previousDocument = globalThis.document
  const scrolled = []
  globalThis.document = {
    visibilityState: 'hidden',
    addEventListener() {},
    removeEventListener() {},
    querySelector(selector) {
      scrolled.push(selector)
      return { scrollIntoView: options => scrolled.push(options?.block) }
    },
  }
  try {
    for (const [key, view] of Object.entries(page.MODULE_RECORD_VIEWS)) {
      const { page: instance, calls } = mountRecording()
      await instance.openModuleRecords(key)
      assert.equal(instance.activeTab.value, view.tab, `${key} 切到 ${view.tab}`)
      assert.equal(calls.filter(call => call.kind !== 'get').length, 0, `${key} 查看记录不得触发写操作`)
      for (const call of calls) assert.ok(call.path.startsWith('diagnostics') || !/_run|_execute|_scan|_preview|_complement|_reallocate|_check/.test(call.path), `${key} 不应触发 ${call.path}`)
      if (view.anchor) {
        assert.ok(scrolled.includes(view.anchor), `${key} 必须定位到 ${view.anchor}`)
        assert.ok(scrolled.includes('start'), '定位使用块首对齐')
      }
    }
  } finally {
    globalThis.document = previousDocument
  }
})

test('无 DOM 时查看记录不抛错（document 桩没有 querySelector）', async () => {
  const { page: instance } = mountRecording()
  await instance.openModuleRecords('transfer')
  assert.equal(instance.activeTab.value, 'transfer')
})

test('清理成功后：重命名分页回第一页、自动删种清掉旧预览，且只刷新对应模块', async () => {
  const { page: instance, calls } = mountRecording()
  instance.cleanupTargetKey.value = 'rename_history'
  instance.page.value = 3
  instance.archivePage.value = 4
  await instance.confirmCleanupData()
  assert.equal(instance.page.value, 1, '历史分页回第一页')
  assert.equal(instance.archivePage.value, 1, '归档分页回第一页')
  assert.deepEqual(calls.filter(call => call.kind === 'postJson').map(call => call.path), ['cleanup_module_data'])
  assert.deepEqual(calls.filter(call => call.kind === 'postJson')[0].payload, { module: 'rename_history' })
  assert.ok(calls.some(call => call.path.startsWith('rename_history?page=1')), '刷新回第一页数据')

  const second = mountRecording()
  second.page.cleanupTargetKey.value = 'autoremove_state'
  second.page.autoremovePreview.value = { candidate_list: [{ hash: 'A'.repeat(40) }] }
  await second.page.confirmCleanupData()
  assert.equal(second.page.autoremovePreview.value, null, '记录已清理，旧预览不得残留')
  assert.deepEqual(second.calls.filter(call => call.kind === 'postJson').map(call => call.path), ['cleanup_module_data'])
  assert.ok(second.calls.some(call => call.path === 'autoremove_status'))
})

test('确认框口径：失败清理说明保留累计统计，通用提示不含下载器数据', () => {
  assert.ok(/累计/.test(page.CLEANUP_TARGETS.failclean_state.consequence), '失败清理必须说明累计统计保留')
  assert.ok(/只清最近一次执行结果/.test(page.CLEANUP_TARGETS.failclean_state.consequence))
  assert.ok(/可重新识别与补刀/.test(page.CLEANUP_TARGETS.rename_archive.consequence), '归档清理须写明后果（决策 C）')
  assert.ok(/无法再按记录恢复原名或补刀/.test(page.CLEANUP_TARGETS.rename_history.consequence))
  assert.ok(/不修改下载器任务与文件/.test(template), '确认框须写明不动下载器数据')
})
