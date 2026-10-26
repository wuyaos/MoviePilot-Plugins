"""Config.vue 新配置契约的真实渲染验证（compileScript + compiler-ssr + server-renderer）。

离线、无宿主、无网络：/sites 由 mock api 提供；每次渲染新建 app 并共享捕获的 setup 绑定状态。
"""
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "frontend.v3/autoptcheckin"
PLUGIN = ROOT / "plugins.v3/autoptcheckin"

DEFAULT_URL = "https://production-sfo.browserless.io"

HARNESS = r"""
import * as Vue from 'vue'
import * as VSR from 'vue/server-renderer'
import { renderToString } from 'vue/server-renderer'
import { compile } from '@vue/compiler-ssr'
import { parse, compileScript } from '@vue/compiler-sfc'
import { readFileSync } from 'node:fs'
import assert from 'node:assert/strict'
import { sourceBadge, credentialBadge } from './src/badges.js'

const src = readFileSync(new URL('./src/Config.vue', import.meta.url), 'utf8')
const { descriptor, errors } = parse(src, { filename: 'Config.vue' })
if (errors.length) throw new Error(errors.map(e => e.message).join('; '))
const compiled = compileScript(descriptor, { id: 'cfg' })
let js = compiled.content.replace(/^import [^\n]*$/gm, '')
js = js.replace('const __returned__ = {', 'const __returned__ = globalThis.__returned__ = {')
js = js.replace('export default {', 'globalThis.__component = {')
const templateSrc = src.slice(src.indexOf('<template>') + 10, src.lastIndexOf('</template>'))
let ssrCode = compile(templateSrc, { filename: 'Config.vue', id: 'cfg', bindingMetadata: compiled.bindings }).code
ssrCode = ssrCode.replaceAll('require("vue/server-renderer")', '__vsr').replaceAll('require("vue")', '__vue')
const ssrRender = new Function('__vsr', '__vue', ssrCode + '\n')(VSR, Vue)

const watchHostTheme = () => () => {}
const { reactive, ref, computed, watch, inject, nextTick, onMounted, onBeforeUnmount, createSSRApp, h } = Vue
const defaults = DEFAULTS_JSON
eval(js)

const rows = [
  { id: 'loginonly', name: 'LoginOnly', signin_applicable: false, login_capable: true, emulate: false, cloudsign_capable: false, source: 'MP 站点', credential: { kind: 'cookie' }, cf: 'unknown' },
  { id: 'audiences', name: 'Audiences', signin_applicable: true, login_capable: true, emulate: true, cloudsign_capable: true, source: 'MP 站点', credential: { kind: 'cookie' }, cf: true },
  { id: 'plain', name: 'Plain', signin_applicable: true, login_capable: false, emulate: false, cloudsign_capable: false, source: 'MP 站点', credential: { kind: 'cookie' }, cf: 'unknown' },
]
const input = reactive({ initialConfig: {
  enabled_sites: ['loginonly', 'audiences', 'plain'],
  site_emulate: { audiences: false },
}, api: { get: async () => ({ data: { sites: rows } }) } })
__component.ssrRender = ssrRender
const props = { get initialConfig() { return input.initialConfig }, api: input.api, pluginId: 'AutoPtCheckin' }
const boot = createSSRApp({ setup: () => () => h(__component, props) })
await renderToString(boot)
const ret = globalThis.__returned__
await ret.loadSites()
// 同一 app 二次 renderToString 返回旧树；用捕获的绑定状态重建 app 渲染当前状态。
const render = async () => renderToString(createSSRApp({ setup: () => globalThis.__returned__, ssrRender }))
let html = await render()

// 能力门控：仅登录站无签到框；无登录能力站无登录框；无云签能力站无云签框。
assert(html.includes('aria-label="LoginOnly 登录"'), 'login switch for login-only site')
assert(!html.includes('aria-label="LoginOnly 签到"'), 'no sign switch for login-only site')
assert(html.includes('aria-label="Plain 签到"'), 'sign switch for capable site')
assert(!html.includes('aria-label="Plain 登录"'), 'no login switch when login_capable=false')
assert(html.includes('aria-label="Audiences 云签"'), 'cloudsign switch when capable')
assert(!html.includes('aria-label="Plain 云签"') && !html.includes('aria-label="LoginOnly 云签"'), 'no cloudsign switch without capability')
// 显式 false 压声明 true：audiences 声明 emulate=true 但覆盖 false，无仿真徽标。
assert(!html.includes('class="chip emulate">仿真'), 'explicit false suppresses emulate badge')
assert(!html.includes('class="chip shield-cloud">云签'), 'cloudsign off -> no cloud badge')
assert(!html.includes('云签不会生效'), 'no credentials hint when cloudsign off')
// 开启云签：徽标变云签、缺凭据短提示；不自动启用站点或勾选动作。
ret.toggleCloudsign({ id: 'audiences' }, true)
html = await render()
assert(html.includes('class="chip shield-cloud">云签'), 'cloudsign selected -> cloud badge')
assert(!html.includes('class="chip emulate">仿真'), 'cloud badge replaces emulate badge')
assert(html.includes('云签不会生效'), 'missing credentials hint')
assert(input.initialConfig.enabled_sites.includes('audiences'), 'cloudsign toggle must not touch enabled_sites')
assert(!(input.initialConfig.sign_sites || []).includes('audiences'), 'cloudsign toggle must not touch sign_sites')
// 自建地址免 Token：提示消失。
ret.model.browserless_url = 'http://127.0.0.1:3000'
html = await render()
assert(!html.includes('云签不会生效'), 'self-hosted URL without token counts as configured')
ret.model.browserless_url = DEFAULT_URL
ret.model.browserless_token = 'tok'
assert(ret.cloudsignConfigured, 'token with default URL counts as configured')
ret.model.browserless_token = ''
// 关闭云签：显式仿真覆盖恢复后回到有效仿真徽标。
ret.toggleCloudsign({ id: 'audiences' }, false)
ret.setSiteOverride('site_emulate', { id: 'audiences' }, true)
html = await render()
assert(html.includes('class="chip emulate">仿真'), 'emulate badge returns when cloudsign off')
assert(!html.includes('class="chip shield-cloud">云签'), 'no cloud badge after cloudsign off')
console.log('Config SSR siteconf contract: passed')
"""


def test_config_ssr_siteconf_contract():
    defaults = json.loads((PLUGIN / "config_defaults.json").read_text(encoding="utf-8"))
    harness = HARNESS.replace("DEFAULTS_JSON", json.dumps(defaults)).replace(
        "DEFAULT_URL", json.dumps(DEFAULT_URL))
    handle = tempfile.NamedTemporaryFile(dir=FRONTEND, prefix=".ssr_harness_", suffix=".mjs", delete=False)
    try:
        handle.write(harness.encode("utf-8"))
        handle.close()
        result = subprocess.run(["node", handle.name], cwd=FRONTEND,
                                capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        Path(handle.name).unlink(missing_ok=True)


def test_page_run_once_is_direct_post():
    """「立即运行」必须走 POST /run_once 直接线程路径，不得借配置 onlyonce 保存触发。"""
    page = (FRONTEND / "src/Page.vue").read_text(encoding="utf8")
    assert "execute('run_once')" in page
    assert "props.api.post" in page
    assert "onlyonce" not in page
    config = (FRONTEND / "src/Config.vue").read_text(encoding="utf8")
    config = (FRONTEND / "src/Config.vue").read_text(encoding="utf8")
    assert config.count("site_browserless") == 1 and "delete model.site_browserless" in config, "旧 site_browserless 仅允许出现在规范化删除处"
