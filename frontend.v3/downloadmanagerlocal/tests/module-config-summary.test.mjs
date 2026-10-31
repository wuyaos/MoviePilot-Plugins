import { MODULE_ICONS } from '../src/components/module-icons.js'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { computed, reactive, ref, watch, nextTick } from 'vue'

// Page.vue 切页签会读 document.visibilityState 并调 window.setInterval；只给最小桩。
globalThis.document = globalThis.document || { visibilityState: 'hidden', addEventListener() {}, removeEventListener() {} }
globalThis.window = globalThis.window || { setInterval: () => 0, clearInterval() {} }

const source = readFileSync(new URL('../src/components/Page.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1]
  .replace(/^import .*$/gm, '')
  .replace(/^/, `const MODULE_ICONS = ${JSON.stringify(MODULE_ICONS)};\n`)

function setup() {
  return new Function(
    'reactive', 'ref', 'computed', 'watch', 'nextTick', 'onMounted', 'onBeforeUnmount',
    'defineProps', 'defineEmits', 'getPluginApi', 'postPluginApi', 'postPluginJsonApi',
    `${script}\nreturn { summaryValue, summaryFields, moduleConfigSummary, activeTab, currentModule };`)
}

function mount() {
  const props = reactive({ api: null, pluginId: 'DownloadManagerLocal', sourcePluginId: 'DownloadManagerLocal' })
  const fail = () => { throw new Error('展示函数不应发起请求') }
  return setup()(reactive, ref, computed, watch, nextTick, () => {}, () => {},
    () => props, () => () => {}, fail, fail, fail)
}

test('摘要占位从 module_config_summary 投影取值，未加载时保持未提供', () => {
  const page = mount()
  page.activeTab.value = 'hr'
  assert.equal(page.currentModule.value, 'hr')
  assert.equal(page.summaryValue('downloaders'), null, '投影未加载时返回 null')

  page.moduleConfigSummary.value = {
    modules: {
      hr: {
        fields: [
          { key: 'downloaders', label: '下载器范围', value: 'QB1, QB2', category: 'config_value', source: '配置键 hr_downloader' },
          { key: 'rules', label: '规则来源', value: '站点规则（内置预设 + 自定义）', category: 'config_value', source: '...' },
        ],
      },
    },
  }
  assert.equal(page.summaryValue('downloaders'), 'QB1, QB2')
  assert.equal(page.summaryValue('rules'), '站点规则（内置预设 + 自定义）')
  assert.equal(page.summaryValue('missing'), null)
})

test('摘要字段表逐字段接入投影，不再留 null 占位', () => {
  const page = mount()
  page.activeTab.value = 'hr'
  page.moduleConfigSummary.value = {
    modules: {
      hr: {
        fields: [
          { key: 'downloaders', label: '下载器范围', value: 'QB1', category: 'config_value', source: '配置键 hr_downloader' },
          { key: 'sites', label: '站点范围', value: 'GGPT, 52pt', category: 'config_value', source: '配置键 hr_sites' },
          { key: 'rules', label: '规则来源', value: '全局默认', category: 'config_value', source: '...' },
          { key: 'interval', label: '检查周期', value: '10 分钟', category: 'config_value', source: '配置键 hr_check_period' },
        ],
      },
    },
  }
  const fields = page.summaryFields.value
  const byKey = Object.fromEntries(fields.map(f => [f.key, f]))
  assert.equal(byKey.downloaders.value, 'QB1')
  assert.equal(byKey.sites.value, 'GGPT, 52pt')
  assert.equal(byKey.rules.value, '全局默认')
  assert.equal(byKey.interval.value, '10 分钟')
  // 保护字段仍沿用既有 H&R 汇总口径，不来自摘要投影
  assert.equal(byKey.guard.value, null)
})

test('前端源码只接摘要投影，不重做布局、不新增交互控件', () => {
  assert.match(source, /getApi\('module_config_summary'/)
  assert.match(source, /loadModuleConfigSummary/)
  assert.match(source, /const summaryValue = key =>/)
  // 仅替换 null 占位；ConfigSummary 仍是唯一摘要渲染入口
  assert.equal((source.match(/<ConfigSummary\b/g) || []).length, 1)
})
