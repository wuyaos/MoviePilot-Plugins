import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { MODULE_ICONS } from '../src/components/module-icons.js'
import { loadSfc, render } from './helpers/load-sfc.mjs'

const source = name => fs.readFileSync(new URL(`../src/components/${name}.vue`, import.meta.url), 'utf8')
function projection(name, returns) {
  const script = parse(source(name)).descriptor.scriptSetup.content.replace(/^import .*$/gm, '')
  const setup = new Function('MODULE_ICONS', 'reactive', 'ref', 'computed', 'watch', 'nextTick', 'onMounted', 'onBeforeUnmount', 'defineProps', 'defineEmits', 'getPluginApi', 'postPluginApi', 'postPluginJsonApi', `${script}\nreturn { ${returns} };`)
  const noRequest = () => { throw Error('Icon projection must not request API') }
  return setup(MODULE_ICONS, reactive, ref, computed, watch, nextTick, () => {}, () => {}, () => ({ api: null, pluginId: 'DownloadManagerLocal', initialConfig: {} }), () => () => {}, noRequest, noRequest, noRequest)
}

test('navigation, overview cards, module titles and configuration share module identity icons', () => {
  const scope = effectScope()
  try {
    scope.run(() => {
      const page = projection('Page', 'tabs, tabModuleKeys, moduleHeaders')
      const config = projection('Config', 'mainTabs')
      for (const tab of page.tabs) {
        const key = page.tabModuleKeys[tab.key] || tab.key
        assert.equal(tab.icon, MODULE_ICONS[key], tab.key)
        if (page.moduleHeaders.value[key]) assert.equal(page.moduleHeaders.value[key].icon, tab.icon, key)
      }
      const aliases = { remover: 'autoremove', upload: 'upload_limit' }
      for (const tab of config.mainTabs) assert.equal(tab.icon, MODULE_ICONS[aliases[tab.key] || tab.key], tab.key)
    })
  } finally { scope.stop() }
})

test('overview and diagnostics render shared title icons without misleading enabled/disabled chips', async () => {
  const Header = await loadSfc('ModuleHeader.vue')
  const template = parse(source('Page')).descriptor.template.content
  for (const [key, title] of [['overview', '运行总览'], ['diagnostics', '运行诊断']]) {
    assert.ok(template.includes(`<ModuleHeader title="${title}" :icon="MODULE_ICONS.${key}" :show-status="false" enabled />`))
    const html = await render(Header, { title, icon: MODULE_ICONS[key], showStatus: false, enabled: true })
    assert.ok(html.includes(title))
    assert.ok(html.includes(MODULE_ICONS[key]))
    assert.doesNotMatch(html, /已启用|已禁用/)
  }
  const normal = await render(Header, { title: '转移做种', icon: MODULE_ICONS.transfer, enabled: false })
  assert.match(normal, /已禁用/)
})
