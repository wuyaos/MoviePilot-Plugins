<script setup>
import { reactive, ref, computed, watch, inject, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { sourceBadge, credentialBadge } from './badges.js'
import { pinyin } from 'pinyin-pro'
import defaults from '../../../plugins.v3/autoptcheckin/config_defaults.json'
import { watchHostTheme } from './theme.js'
const props = defineProps({ initialConfig: Object, api: Object, pluginId: {type:String,default:'AutoPtCheckin'} })
const brokenIcons = ref({})
const emit = defineEmits(['save', 'switch', 'close', 'layout'])
// 规范 5.8：复用宿主统一 Toast；注入不存在时静默降级，保留页面内状态提示。
const toast = inject('moviepilot:toast', null)
const model = reactive({ ...structuredClone(defaults), ...JSON.parse(JSON.stringify(props.initialConfig || {})) })
// API 与历史配置中的自定义 ID 可能是数字；表单内统一使用字符串关联站点。
// site_proxy/site_emulate 是 {id:bool} 覆盖表：只规范化已有键，不为缺键站点物化 false。
function normalizeSiteIds() {
  for (const key of ['enabled_sites', 'paused_sites', 'sign_sites', 'login_sites', 'site_cloudsign']) {
    if (Array.isArray(model[key])) model[key] = model[key].map(String)
  }
  for (const key of ['site_proxy', 'site_emulate']) {
    if (model[key] && typeof model[key] === 'object' && !Array.isArray(model[key])) {
      model[key] = Object.fromEntries(Object.entries(model[key]).map(([k, v]) => [String(k), !!v]))
    } else model[key] = {}
  }
  if (Array.isArray(model.custom_sites_data)) model.custom_sites_data = model.custom_sites_data.map(site => ({...site, id: String(site.id)}))
  delete model.site_browserless // 旧运行时绑定键不得进入初始状态与保存 payload
}
normalizeSiteIds()
watch(() => props.initialConfig, value => {
  Object.assign(model, structuredClone(defaults), JSON.parse(JSON.stringify(value || {})))
  normalizeSiteIds()
  customOverlay.value = []
  loadSites()
})
const tab = ref('settings'), search = ref(''), error = ref(''), registrySites = ref([]), customOverlay = ref([])
const timeWindow = ref(`${model.begin_hour}-${model.end_hour}`)
function applyTimeWindow() {
  const match = /^(\d{1,2})\s*-\s*(\d{1,2})$/.exec(String(timeWindow.value).trim())
  if (!match) { timeWindow.value = `${model.begin_hour}-${model.end_hour}`; return }
  const begin = Number(match[1]); const end = Number(match[2])
  if (begin < 0 || end <= begin || end > 24) { timeWindow.value = `${model.begin_hour}-${model.end_hour}`; return }
  model.begin_hour = begin; model.end_hour = end
}
watch(() => [model.begin_hour, model.end_hour], ([b, e]) => { timeWindow.value = `${b}-${e}` })

const showPlain = reactive({})
const credentialFields = {rousi:[{key:'rousi_username',label:'肉丝账号',type:'text'},{key:'rousi_password',label:'肉丝密码',type:'password'}], sunnypt:[{key:'sunnypt_username',label:'SunnyPT 账号',type:'text'},{key:'sunnypt_password',label:'SunnyPT 密码',type:'password'}],yzyy:[{key:'yzyy_username',label:'yzyy 账号',type:'text'},{key:'yzyy_password',label:'yzyy 密码',type:'password'}],ourbits:[{key:'ourbits_username',label:'我堡账号',type:'text'},{key:'ourbits_password',label:'我堡密码',type:'password'},{key:'ourbits_totp',label:'我堡 TOTP 密钥（可选）',type:'password'}],mteam:[{key:'mteam_username',label:'M-Team 账号',type:'text'},{key:'mteam_password',label:'M-Team 密码',type:'password'},{key:'mteam_totp',label:'M-Team TOTP 密钥（可选）',type:'password'}]}
// 有效值：覆盖表键存在即生效（显式 false 终结继承），缺键继承 /sites 服务端有效字段。
const overrideOf = (mapName, site, fallback) => {
  const map = model[mapName] || (model[mapName] = {})
  const key = String(site.id)
  return key in map ? !!map[key] : !!fallback
}
const siteEmulated = site => overrideOf('site_emulate', site, site.emulate)
const siteProxied = site => overrideOf('site_proxy', site, site.proxy)
// 仅用户触碰的开关才写入覆盖表，缺键继续继承，不批量固化 false。
function setSiteOverride(mapName, site, value) {
  const map = model[mapName] || (model[mapName] = {})
  map[String(site.id)] = !!value
}
// 与后端 cloudsign.configured 同口径：有 token 或非默认自建地址即视为已配置，自建服务允许免 Token。
const DEFAULT_BROWSERLESS_URL = 'https://production-sfo.browserless.io'
const cloudsignConfigured = computed(() => !!String(model.browserless_token || '').trim() ||
  (!!String(model.browserless_url || '').trim() && String(model.browserless_url).trim() !== DEFAULT_BROWSERLESS_URL))
const canSign = site => site.source === '自定义站点'
  ? model.sign_sites.includes(String(site.id))
  : site.signin_capable === true
const canLogin = site => site.login_capable !== false
// 仅凭据算额外配置允许展开；云签提示移入收起行徽标，纯展示信息不展开。
const hasExtraSettings = site => (site.fields || []).length > 0
const hasCloudsign = site => site.cloudsign_capable === true
const hasEmulate = site => site.emulate_capable === true
// 云签按草稿选择显示；关闭时回退有效仿真徽标。仅签到通道，登录仍走本地仿真。
const cloudsignSelected = site => hasCloudsign(site) && model.site_cloudsign.includes(String(site.id))
async function togglePaused(site) {
  const id = String(site.id)
  try {
    const response = await props.api.get(`plugin/${props.pluginId}/config`)
    if (response?.success === false) throw new Error(response.message)
    const config = response?.data ?? response
    const paused = new Set((config.paused_sites || []).map(String))
    paused.has(id) ? paused.delete(id) : paused.add(id)
    const next = [...paused]
    const saved = await props.api.put(`plugin/${props.pluginId}/config`, {...config, paused_sites: next})
    if (saved?.success === false) throw new Error(saved.message)
    model.paused_sites = next
  } catch (e) { error.value = e.message || '暂停状态保存失败'; toast?.error(error.value) }
}
function toggleCloudsign(site, checked) {
  const key = String(site.id)
  model.site_cloudsign = checked ? [...new Set([...model.site_cloudsign, key])]
    : model.site_cloudsign.filter(v => v !== key) // 不自动启用站点或勾选动作
}
const selectedSearch = ref('')
const filteredSelected = computed(() => selected.value.filter(site => (site.name+site.id).toLowerCase().includes(selectedSearch.value.trim().toLowerCase())))
const openSites = ref([])
function toggleSite(id) { openSites.value = openSites.value.includes(id) ? openSites.value.filter(key => key !== id) : [...openSites.value, id] }
function expandSites() { openSites.value = selected.value.filter(hasExtraSettings).map(site => site.id) }
function collapseSites() { openSites.value = [] }
const pickerOpen = ref(false), pendingSites = ref([])
// 自定义站点弹窗的全部编辑（含签到勾选/删除）都停留在草稿，取消不落任何主模型。
// 自定义站点弹窗编辑全落草稿：draftSign 记录「显式切换增量」（Map id→bool），
// 未切换行沿用主模型现状；visible 过滤删除行。取消弹窗不落任何主模型。
const draftSign = ref(new Map())
const visibleCustomDraft = computed(() => customDraft.value.filter(site => !site.deleted))
const pickerAnchor = ref(null), pickerPopup = ref(null), pickerStyle = ref({})
function positionPicker() {
  if (!pickerOpen.value || !pickerAnchor.value) return
  const rect = pickerAnchor.value.getBoundingClientRect()
  const width = Math.min(rect.width, window.innerWidth - 16)
  const below = Math.max(0, window.innerHeight - rect.bottom - 12)
  const above = Math.max(0, rect.top - 12)
  const desired = Math.min(400, window.innerHeight * .6)
  const upwards = below < desired && above > below
  const height = Math.min(desired, upwards ? above : below)
  pickerStyle.value = {width:width+'px', left:Math.max(8, Math.min(rect.left, window.innerWidth-width-8))+'px', maxHeight:height+'px', top:upwards ? 'auto' : rect.bottom+4+'px', bottom:upwards ? window.innerHeight-rect.top+4+'px' : 'auto'}
}
watch(pickerOpen, async open => {
  await nextTick()
  if (open) { positionPicker(); pickerPopup.value?.showPopover() }
  else pickerPopup.value?.hidePopover()
})
function togglePicker() {
  if (!pickerOpen.value) pendingSites.value = [...model.enabled_sites]
  pickerOpen.value = !pickerOpen.value
}
function confirmSites() {
  model.enabled_sites = [...pendingSites.value]
  pickerOpen.value = false
}
const customDialog = ref(null), customDraft = ref([])
function editCustomSites() {
  pickerOpen.value = false
  error.value = ''
  customDraft.value = JSON.parse(JSON.stringify(model.custom_sites_data))
  draftSign.value = new Map()
  customDialog.value?.showModal()
}
function toggleCustomSignin(site, checked) {
  draftSign.value = new Map(draftSign.value).set(String(site.id), !!checked)
}
function addCustomSite() {
  const id = 'custom-' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
  customDraft.value.push({id, name:'', url:'', emulate:false, source:'自定义站点', login_capable:true, credential:'cookie', fields:[]})
}
function removeCustomDraft(id) {
  const site = customDraft.value.find(item => String(item.id) === String(id))
  if (site) site.deleted = true
}
function saveCustomDraft() {
  const kept = customDraft.value.filter(site => !site.deleted)
  for (const site of kept) {
    const id = String(site.id)
    if (!site.name.trim() || !site.url) { error.value = '请填写名称及 HTTP(S) 地址'; return }
    let url; try { url = new URL(site.url) } catch { error.value = '请填写有效的 HTTP(S) 地址'; return }
    if (!['http:', 'https:'].includes(url.protocol)) { error.value = '请填写名称及 HTTP(S) 地址'; return }
    Object.assign(site, {id, name:site.name.trim(), url:url.href, source:'自定义站点'})
    // 仿真开关与主卡同源（siteEmulated/setSiteOverride 直写覆盖表），保存时不再二次同步；
    // 签到状态：显式切换过的行以草稿为准，未切换的行沿用主模型现状（重命名/改址不丢勾选）。
    const toggled = draftSign.value.get(id)
    const signOn = toggled !== undefined ? toggled : model.sign_sites.includes(id)
    if (signOn) {
      if (!model.sign_sites.includes(id)) model.sign_sites.push(id)
      if (!model.enabled_sites.includes(id)) model.enabled_sites.push(id)
    } else {
      model.sign_sites = model.sign_sites.filter(item => item !== id)
    }
  }
  model.custom_sites_data = kept.map(site => ({...site}))
  // overlay 重建保留 deleted 占位（含本轮草稿删除项）：sites 合并时靠它压制 registry 同 id 行。
  const draftDeleted = customDraft.value.filter(site => site.deleted).map(site => ({id: String(site.id), deleted: true}))
  customOverlay.value = [
    ...customOverlay.value.filter(site => site.deleted),
    ...draftDeleted,
    ...model.custom_sites_data.map(site => ({...site}))
  ]
  customDialog.value?.close()
}
const pendingRemove = ref(null)
function confirmRemove(id) { remove(id); pendingRemove.value = null }
const sites = computed(() => {
  const rows = new Map(registrySites.value.map(site => [site.id, site]))
  for (const site of customOverlay.value) {
    if (site.deleted) rows.delete(site.id)
    else rows.set(site.id, {...rows.get(site.id), ...site})
  }
  return [...rows.values()]
})
const selected = computed(() => sites.value.filter(s => model.enabled_sites.includes(s.id)))
const pickerSelected = computed(() => sites.value.filter(site => (pickerOpen.value ? pendingSites.value : model.enabled_sites).includes(site.id)))
function removePickerSite(id) {
  if (pickerOpen.value) pendingSites.value = pendingSites.value.filter(key => key !== id)
  else remove(id)
}
const pinyinIndex = computed(() => new Map(sites.value.map(site => { const parts = pinyin(site.name || '', { toneType:'none', type:'array' }); return [site.id, { full:parts.join('').toLowerCase(), initials:pinyin(site.name || '', { toneType:'none', type:'array', pattern:'first' }).join('').toLowerCase() }] })))
const filtered = computed(() => { const q = search.value.trim().toLowerCase(); return sites.value.filter(site => { const py = pinyinIndex.value.get(site.id) || {}; let host = ''; try { host = new URL(site.url).host.toLowerCase() } catch {} return !q || (site.name || '').toLowerCase().includes(q) || (site.id || '').toLowerCase().includes(q) || host.includes(q) || py.full.includes(q) || py.initials.includes(q) }) })
const allFilteredSelected = computed(() => filtered.value.length > 0 && filtered.value.every(site => pendingSites.value.includes(site.id)))
function toggleFilteredSelection() {
  const ids = filtered.value.map(site => site.id)
  pendingSites.value = allFilteredSelected.value ? pendingSites.value.filter(id => !ids.includes(id)) : [...new Set([...pendingSites.value, ...ids])]
}
function remove(id) { model.enabled_sites = model.enabled_sites.filter(s => s !== id); openSites.value = openSites.value.filter(s => s !== id) }
function save() { emit('save', JSON.parse(JSON.stringify(model))) }
async function loadSites() { try { const response = await props.api?.get(`plugin/${props.pluginId || 'AutoPtCheckin'}/sites`); registrySites.value = (response?.data?.sites || response?.sites || []).map(site => ({...site, id: String(site.id), source: site.source, fields: credentialFields[site.id] || [], credential: site.credential && site.credential.kind ? site.credential.kind : 'cookie'})) } catch { registrySites.value = []; toast?.error('站点清单加载失败') } }
let stopTheme
onMounted(() => { stopTheme = watchHostTheme(); loadSites(); window.addEventListener('resize', positionPicker); window.addEventListener('scroll', positionPicker, true) })
onBeforeUnmount(() => { stopTheme?.(); window.removeEventListener('resize', positionPicker); window.removeEventListener('scroll', positionPicker, true) })
emit('layout', { maxWidth: '1000px' })
</script>
<template>
<div class="pt-center"><section class="card embedded-card" aria-label="插件配置">
<div class="card-head"><h2>PT 签到中心</h2><button class="btn ghost" @click="emit('close')">关闭</button></div>
<div class="tabs" role="tablist"><button v-for="(label, key) in {settings:'设置',sites:'站点'}" :key="key" class="tab" role="tab" :aria-selected="tab === key" @click="tab = key">{{ label }}</button></div>
<section v-show="tab === 'settings'" class="win">
<div class="group"><h3>基础设置</h3><div class="grid fields-grid"><label class="switch mini-switch"><input type="checkbox" role="switch" v-model="model.enabled">启用插件</label><label class="switch mini-switch"><input type="checkbox" role="switch" v-model="model.notify">发送通知</label></div></div>
<div class="group"><h3>执行调度</h3><div class="grid fields-grid"><label class="field"><span>调度模式</span><select class="input" v-model="model.cron_mode"><option value="interval">间隔模式</option><option value="cron">Cron 模式</option></select></label><label class="field" v-if="model.cron_mode === 'interval'"><span>执行间隔</span><input class="input" type="number" min="1" v-model.number="model.interval_hours" placeholder="间隔(h)"></label><label class="field"><span>时间窗口</span><input class="input" v-model="timeWindow" placeholder="8-24（开始时间也计入）" @change="applyTimeWindow"></label><label class="field" v-if="model.cron_mode === 'cron'"><span>Cron 表达式</span><input class="input" v-model="model.cron" placeholder="分 时 日 月 周"></label></div><div class="grid fields-grid" style="margin-top:16px"><label class="field"><span>并发数</span><input class="input" type="number" min="1" v-model.number="model.queue_cnt"></label><label class="field"><span>当场重试次数</span><input class="input" type="number" min="0" v-model.number="model.retry_count"></label></div></div>

<div class="group"><h3>Browserless</h3><div class="grid fields-grid"><label class="field"><span>Browserless 服务地址</span><input class="input" v-model="model.browserless_url" placeholder="https://production-sfo.browserless.io"></label><label class="field"><span>Browserless Token</span><span class="input-wrap"><input class="input" :type="showPlain['global.browserless_token'] ? 'text' : 'password'" v-model="model.browserless_token" autocomplete="off"><button type="button" class="eye-btn" :aria-label="(showPlain['global.browserless_token'] ? '隐藏' : '显示')+'Browserless Token'" @click="showPlain['global.browserless_token'] = !showPlain['global.browserless_token']"><svg v-if="showPlain['global.browserless_token']" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg><svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button></span></label></div><p class="hint" style="margin:-6px 0 0">用于 CF 盾站点云签（云端浏览器签到），仅对声明 shield=cloud 的站点生效。</p></div>
</section>
<section v-show="tab === 'sites'" class="win">
<div class="topline"><h3>启用站点</h3><div class="row"><span class="chip blue">已启用 {{ selected.length }} 个站点</span><button class="btn ghost mini" @click="editCustomSites">编辑自定义站点</button></div></div><details class="picker" :open="pickerOpen"><summary ref="pickerAnchor" @click.prevent="togglePicker"><span class="picker-selection"><button v-for="site in pickerSelected" :key="site.id" type="button" class="chip" :class="sourceBadge(site.source)" :aria-label="'移除选择 '+site.name" @click.stop.prevent="removePickerSite(site.id)">{{ site.name }} ×</button><span v-if="!pickerSelected.length">选择启用的站点 · 支持名称筛选</span></span><span>⌄</span></summary><div ref="pickerPopup" popover="manual" class="picker-popup" :style="pickerStyle"><label class="field"><span>筛选站点</span><input v-model="search" class="input" type="search" placeholder="搜索站点名称"></label><button type="button" class="btn ghost mini" :disabled="!filtered.length" @click="toggleFilteredSelection">{{ allFilteredSelected ? '全不选' : '全选' }}</button><div class="choices"><label v-for="site in filtered" :key="site.id" class="choice"><span><input v-model="pendingSites" type="checkbox" :value="site.id">{{ site.name }}</span><span class="chip" :class="sourceBadge(site.source)">{{ site.source }}</span></label><p v-if="!filtered.length" class="hint">没有匹配的站点</p></div><div class="row picker-actions"><button class="btn confirm" @click="confirmSites">确认选择</button><button class="btn subtle" @click="pickerOpen = false">取消</button></div></div></details>

<div v-if="selected.length" class="site-management"><label class="field"><span>筛选已启用站点</span><input v-model="selectedSearch" type="search" class="input" placeholder="搜索已启用站点"></label><div class="row management-actions"><button class="btn ghost mini" @click="expandSites">全部展开</button><button class="btn ghost mini" @click="collapseSites">全部收起</button></div><div class="enabled-site-list"><details v-for="site in filteredSelected" :key="site.id" class="site-card config-site" :open="hasExtraSettings(site) && openSites.includes(site.id)"><summary @click.prevent><span class="row-left"><button v-if="pendingRemove !== site.id" type="button" class="remove-icon" :aria-label="'移出启用 '+site.name" @click="pendingRemove = site.id">×</button><template v-else><button type="button" class="btn danger mini" @click="confirmRemove(site.id)">确认移除</button><button type="button" class="btn subtle mini" @click="pendingRemove = null">取消</button></template><span class="site-name site-label"><img v-if="site.icon && !brokenIcons[site.id]" class="site-icon" :src="site.icon" alt="" @error="brokenIcons[site.id] = true"><span v-else class="site-icon site-initial" aria-hidden="true">{{ site.name?.slice(0,1) }}</span>{{ site.name }}</span><button type="button" class="pwr" :class="model.paused_sites.includes(String(site.id)) ? 'paused' : 'active'" :title="model.paused_sites.includes(String(site.id)) ? '恢复执行' : '暂停执行'" :aria-label="model.paused_sites.includes(String(site.id)) ? '恢复执行' : '暂停执行'" @click.stop="togglePaused(site)">⏻</button><span class="badges"><span class="chip" :class="sourceBadge(site.source)">{{ site.source }}</span><span class="chip" :class="credentialBadge(site.credential)">{{ (site.credential && site.credential.kind) ? site.credential.kind : (site.credential || 'cookie') }}</span><span v-if="site.cf === true" class="chip cf-yes">CF 盾</span><span v-if="cloudsignSelected(site)" class="chip shield-cloud">云签</span><span v-else-if="siteEmulated(site)" class="chip emulate">仿真</span><span v-if="hasCloudsign(site) && cloudsignSelected(site) && !cloudsignConfigured" class="chip badge-unknown" title="未配置 Browserless Token 或自建服务地址，云签不会生效">云签未配置</span><span v-if="site.notice" class="chip badge-unknown" :title="site.notice">⚠</span></span></span><span class="row-right"><span class="switch-group switch-group-left"><label class="switch mini-switch switch-col" :title="site.name+' 代理'" @click.stop><input type="checkbox" role="switch" :checked="siteProxied(site)" :aria-label="site.name+' 代理'" @change="setSiteOverride('site_proxy', site, $event.target.checked)"><span>代理</span></label><label class="switch mini-switch switch-col emulate-switch" :class="{adapt: hasEmulate(site)}" :title="site.name+(hasEmulate(site) ? ' 仿真（有适配）' : ' 仿真')" @click.stop><input type="checkbox" role="switch" :checked="siteEmulated(site)" :aria-label="site.name+' 仿真'" @change="setSiteOverride('site_emulate', site, $event.target.checked)"><span>仿真</span></label><label v-if="hasCloudsign(site)" class="switch mini-switch switch-col" :title="site.name+' 云签'" @click.stop><input type="checkbox" role="switch" :checked="cloudsignSelected(site)" :aria-label="site.name+' 云签'" @change="toggleCloudsign(site, $event.target.checked)"><span>云签</span></label><span v-else class="switch-col switch-placeholder" aria-hidden="true"></span></span><span class="switch-group switch-group-right"><label v-if="canSign(site)" class="switch mini-switch switch-col" :title="site.name+' 签到'" @click.stop><input v-model="model.sign_sites" type="checkbox" role="switch" :value="site.id" :aria-label="site.name+' 签到'"><span>签到</span></label><span v-else class="switch-col switch-placeholder" aria-hidden="true"></span><label class="switch mini-switch switch-col" :title="site.name+' 登录'" @click.stop><input v-model="model.login_sites" type="checkbox" role="switch" :value="site.id" :aria-label="site.name+' 登录'"><span>登录</span></label></span></span><button v-if="hasExtraSettings(site)" type="button" class="btn ghost mini expand-icon" :aria-expanded="openSites.includes(site.id)" :aria-label="(openSites.includes(site.id) ? '收起配置 ' : '展开配置 ')+site.name" @click.prevent="toggleSite(site.id)">{{ openSites.includes(site.id) ? '▾' : '▸' }}</button><span v-else class="expand-placeholder" aria-hidden="true"></span></summary><div class="site-detail"><div v-if="(site.fields || []).length && (model.sign_sites.includes(site.id) || model.login_sites.includes(site.id))" class="credentials"><div class="grid fields-grid"><label v-for="field in (site.fields || [])" :key="field.key" class="field"><span>{{ field.label }}</span><input v-model="model[field.key]" class="input" :type="field.type === 'password' && showPlain[site.id + '.' + field.key] ? 'text' : field.type" autocomplete="off"><button v-if="field.type === 'password'" type="button" class="btn ghost mini eye-btn" :aria-label="(showPlain[site.id + '.' + field.key] ? '隐藏' : '显示')+field.label" @click="showPlain[site.id + '.' + field.key] = !showPlain[site.id + '.' + field.key]">{{ showPlain[site.id + '.' + field.key] ? '隐藏' : '显示' }}</button></label></div></div></div></details><div v-if="!filteredSelected.length" class="empty">没有匹配的已启用站点</div></div></div>
<div v-if="!selected.length" class="empty">尚未启用站点。请从上方下拉清单选择。</div><dialog ref="customDialog" class="custom-dialog" aria-labelledby="custom-dialog-title"><div class="card-head"><h3 id="custom-dialog-title">编辑自定义站点</h3><button type="button" class="btn ghost" @click="customDialog.close()">关闭</button></div><div class="custom-list"><div class="custom-table-head" role="row"><span></span><span>站点名称</span><span>站点地址</span><span>仿真</span><span>签到</span></div><div v-for="site in visibleCustomDraft" :key="site.id" class="custom-row custom-columns"><button type="button" class="remove-icon" aria-label="删除自定义站点" @click="removeCustomDraft(site.id)">×</button><label class="field" aria-label="站点名称"><input class="input" v-model="site.name" required></label><label class="field" aria-label="站点地址"><input class="input" type="url" v-model="site.url" required></label><label class="switch mini-switch"><input type="checkbox" role="switch" :checked="siteEmulated(site)" @change="setSiteOverride('site_emulate', site, $event.target.checked)">仿真</label><label class="switch mini-switch"><input type="checkbox" role="switch" :checked="draftSign.has(String(site.id))" @change="toggleCustomSignin(site, $event.target.checked)">签到</label></div><p v-if="!visibleCustomDraft.length" class="hint">暂无自定义站点</p><span role="alert">{{ error }}</span></div><div class="footer custom-footer"><button type="button" class="btn ghost" @click="addCustomSite">+ 新增站点</button><div class="row"><button type="button" class="btn subtle" @click="customDialog.close()">取消</button><button type="button" class="btn" @click="saveCustomDraft">保存</button></div></div></dialog>
</section><div class="footer"><button class="btn ghost" @click="emit('switch')">查看数据</button><button class="btn" @click="save">保存配置</button></div>
</section></div>
</template>
<style scoped src="./preview.css"></style>
