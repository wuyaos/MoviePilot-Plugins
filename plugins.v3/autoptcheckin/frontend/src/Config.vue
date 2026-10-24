<script setup>
import { reactive, ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { sourceBadge, credentialBadge } from './badges.js'
import defaults from '../../config_defaults.json'
import { watchHostTheme } from './theme.js'
const props = defineProps({ initialConfig: Object, api: Object, pluginId: {type:String,default:'AutoPtCheckin'} })
const brokenIcons = ref({})
const emit = defineEmits(['save', 'switch', 'close', 'layout'])
const model = reactive({ ...structuredClone(defaults), ...JSON.parse(JSON.stringify(props.initialConfig || {})) })
// API 与历史配置中的自定义 ID 可能是数字；表单内统一使用字符串关联站点。
function normalizeSiteIds() {
  for (const key of ['enabled_sites', 'sign_sites', 'login_sites', 'site_browserless']) {
    if (Array.isArray(model[key])) model[key] = model[key].map(String)
  }
  model.custom_sites_data = model.custom_sites_data.map(site => ({...site, id: String(site.id)}))
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
const credentialFields = {rousi:[{key:'rousi_username',label:'肉丝账号',type:'text'},{key:'rousi_password',label:'肉丝密码',type:'password'}], sunnypt:[{key:'sunnypt_username',label:'SunnyPT 账号',type:'text'},{key:'sunnypt_password',label:'SunnyPT 密码',type:'password'}],yzyy:[{key:'yzyy_username',label:'yzyy 账号',type:'text'},{key:'yzyy_password',label:'yzyy 密码',type:'password'}],mteam:[{key:'mteam_username',label:'M-Team 账号',type:'text'},{key:'mteam_password',label:'M-Team 密码',type:'password'},{key:'mteam_totp',label:'M-Team TOTP 密钥（可选）',type:'password'}]}
const hasExtraSettings = site => (site.fields || []).length > 0 || site.emulate === true
const siteEmulated = site => { const list = model.site_browserless || (model.site_browserless = []); return list.includes(site.id) }
function toggleSiteEmulate(site) { const list = model.site_browserless || (model.site_browserless = []); const i = list.indexOf(site.id); if (i >= 0) list.splice(i, 1); else list.push(site.id) }
const selectedSearch = ref('')
const filteredSelected = computed(() => selected.value.filter(site => (site.name+site.id).toLowerCase().includes(selectedSearch.value.trim().toLowerCase())))
const openSites = ref([])
function toggleSite(id) { openSites.value = openSites.value.includes(id) ? openSites.value.filter(key => key !== id) : [...openSites.value, id] }
function expandSites() {
  openSites.value = selected.value.filter(site => hasExtraSettings(site)).map(site => site.id)
}
function collapseSites() { openSites.value = [] }
const pickerOpen = ref(false), pendingSites = ref([])
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
  customDialog.value.showModal()
}
function toggleCustomSignin(site, checked) {
  const id = String(site.id)
  if (checked) {
    if (!model.sign_sites.includes(id)) model.sign_sites.push(id)
    if (!model.enabled_sites.includes(id)) model.enabled_sites.push(id)
  } else {
    model.sign_sites = model.sign_sites.filter(key => key !== id)
  }
}
function addCustomSite() {
  const id = 'custom-' + crypto.randomUUID()
  customDraft.value.push({id, name:'', url:'', emulate:false, source:'自定义站点', login_capable:true, credential:'cookie', fields:[]})
}
function deleteCustomSite(id) {
  customDraft.value = customDraft.value.filter(site => site.id !== id)
  model.custom_sites_data = model.custom_sites_data.filter(site => site.id !== id)
  customOverlay.value = [...customOverlay.value.filter(site => site.id !== id), {id, deleted:true}]
  remove(id)
  model.sign_sites = model.sign_sites.filter(key => key !== id)
  model.login_sites = model.login_sites.filter(key => key !== id)
}
function saveCustomSite(site) {
  error.value = ''
  let url
  try { url = new URL(site.url) } catch { error.value = '请填写有效的 HTTP(S) 地址'; return }
  if (!site.name.trim() || !['http:', 'https:'].includes(url.protocol)) { error.value = '请填写名称及 HTTP(S) 地址'; return }
  const updated = {...site, name:site.name.trim(), url:url.href, source:'自定义站点'}
  customOverlay.value = [...customOverlay.value.filter(item => item.id !== site.id), updated]
  const index = model.custom_sites_data.findIndex(item => item.id === site.id)
  if (index < 0) model.custom_sites_data.push(updated)
  else model.custom_sites_data[index] = updated
  Object.assign(site, updated)
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
const filtered = computed(() => sites.value.filter(s => (s.name + s.id).toLowerCase().includes(search.value.trim().toLowerCase())))
const allFilteredSelected = computed(() => filtered.value.length > 0 && filtered.value.every(site => pendingSites.value.includes(site.id)))
function toggleFilteredSelection() {
  const ids = filtered.value.map(site => site.id)
  pendingSites.value = allFilteredSelected.value ? pendingSites.value.filter(id => !ids.includes(id)) : [...new Set([...pendingSites.value, ...ids])]
}
function remove(id) { model.enabled_sites = model.enabled_sites.filter(s => s !== id); openSites.value = openSites.value.filter(s => s !== id) }
function save() { emit('save', JSON.parse(JSON.stringify(model))) }
async function loadSites() { try { const response = await props.api?.get(`plugin/${props.pluginId || 'AutoPtCheckin'}/sites`); registrySites.value = (response?.data?.sites || response?.sites || []).map(site => ({...site, id: String(site.id), source: site.source, fields: credentialFields[site.id] || [], credential: site.credential && site.credential.kind ? site.credential.kind : 'cookie'})) } catch { registrySites.value = [] } }
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
<div class="group"><h3>基础设置</h3><div class="grid fields-grid"><label class="switch"><input type="checkbox" role="switch" v-model="model.enabled">启用插件</label><label class="switch"><input type="checkbox" role="switch" v-model="model.notify">发送通知</label><label class="field"><span>通知格式</span><select class="input" v-model="model.notify_format"><option value="plain">纯文本</option><option value="markdown">Markdown</option><option value="html">HTML</option></select></label></div><p class="hint">Markdown/HTML：Telegram、飞书、Discord 支持；钉钉等纯文本渠道按原样显示。</p></div>
<div class="group"><h3>执行调度</h3><div class="grid fields-grid"><label class="field"><span>调度模式</span><select class="input" v-model="model.cron_mode"><option value="interval">间隔模式</option><option value="cron">Cron 模式</option></select></label><label class="field" v-if="model.cron_mode === 'interval'"><span>执行间隔</span><input class="input" type="number" min="1" v-model.number="model.interval_hours" placeholder="间隔(h)"></label><label class="field"><span>时间窗口</span><input class="input" v-model="timeWindow" placeholder="8-24（开始时间也计入）" @change="applyTimeWindow"></label><label class="field" v-if="model.cron_mode === 'cron'"><span>Cron 表达式</span><input class="input" v-model="model.cron" placeholder="分 时 日 月 周"></label></div><div class="grid fields-grid" style="margin-top:16px"><label class="field"><span>并发数</span><input class="input" type="number" min="1" v-model.number="model.queue_cnt"></label><label class="field"><span>当场重试次数</span><input class="input" type="number" min="0" v-model.number="model.retry_count"></label></div></div>

<div class="group"><h3>Browserless</h3><div class="grid fields-grid"><label class="field"><span>Browserless 服务地址</span><input class="input" v-model="model.browserless_url" placeholder="https://production-sfo.browserless.io"></label><label class="field"><span>Browserless Token</span><input class="input" :type="showPlain['global.browserless_token'] ? 'text' : 'password'" v-model="model.browserless_token" autocomplete="off"><button type="button" class="btn ghost mini eye-btn" :aria-label="(showPlain['global.browserless_token'] ? '隐藏' : '显示')+'Browserless Token'" @click="showPlain['global.browserless_token'] = !showPlain['global.browserless_token']">{{ showPlain['global.browserless_token'] ? '隐藏' : '显示' }}</button></label></div><p class="hint" style="margin:-6px 0 0">用于 CF 盾站点云签（云端浏览器签到），仅对声明 shield=cloud 的站点生效。</p></div>
</section>
<section v-show="tab === 'sites'" class="win">
<div class="topline"><h3>启用站点</h3><div class="row"><span class="chip blue">已启用 {{ selected.length }} 个站点</span><button class="btn ghost mini" @click="editCustomSites">编辑自定义站点</button></div></div><details class="picker" :open="pickerOpen"><summary ref="pickerAnchor" @click.prevent="togglePicker"><span class="picker-selection"><button v-for="site in pickerSelected" :key="site.id" type="button" class="chip" :class="sourceBadge(site.source)" :aria-label="'移除选择 '+site.name" @click.stop.prevent="removePickerSite(site.id)">{{ site.name }} ×</button><span v-if="!pickerSelected.length">选择启用的站点 · 支持名称筛选</span></span><span>⌄</span></summary><div ref="pickerPopup" popover="manual" class="picker-popup" :style="pickerStyle"><label class="field"><span>筛选站点</span><input v-model="search" class="input" type="search" placeholder="搜索站点名称"></label><button type="button" class="btn ghost mini" :disabled="!filtered.length" @click="toggleFilteredSelection">{{ allFilteredSelected ? '全不选' : '全选' }}</button><div class="choices"><label v-for="site in filtered" :key="site.id" class="choice"><span><input v-model="pendingSites" type="checkbox" :value="site.id">{{ site.name }}</span><span class="chip" :class="sourceBadge(site.source)">{{ site.source }}</span></label><p v-if="!filtered.length" class="hint">没有匹配的站点</p></div><div class="row picker-actions"><button class="btn confirm" @click="confirmSites">确认选择</button><button class="btn subtle" @click="pickerOpen = false">取消</button></div></div></details>

<div v-if="selected.length" class="site-management"><label class="field"><span>筛选已启用站点</span><input v-model="selectedSearch" type="search" class="input" placeholder="搜索已启用站点"></label><div class="row management-actions"><button class="btn ghost mini" @click="expandSites">全部展开</button><button class="btn ghost mini" @click="collapseSites">全部收起</button></div><div class="enabled-site-list"><details v-for="site in filteredSelected" :key="site.id" class="site-card config-site" :open="openSites.includes(site.id)"><summary @click.prevent><span class="row-left"><button v-if="pendingRemove !== site.id" type="button" class="remove-icon" :aria-label="'移出启用 '+site.name" @click="pendingRemove = site.id">×</button><template v-else><button type="button" class="btn danger mini" @click="confirmRemove(site.id)">确认移除</button><button type="button" class="btn subtle mini" @click="pendingRemove = null">取消</button></template><span class="site-name site-label"><img v-if="site.icon && !brokenIcons[site.id]" class="site-icon" :src="site.icon" alt="" @error="brokenIcons[site.id] = true"><span v-else class="site-icon site-initial" aria-hidden="true">{{ site.name?.slice(0,1) }}</span>{{ site.name }}</span><span class="badges"><span class="chip" :class="sourceBadge(site.source)">{{ site.source }}</span><span class="chip" :class="credentialBadge(site.credential)">{{ (site.credential && site.credential.kind) ? site.credential.kind : (site.credential || 'cookie') }}</span><span v-if="site.cf === true" class="chip cf-yes">CF 盾</span><span v-if="site.shield === 'cloud'" class="chip shield-cloud">云签</span><span v-else-if="site.emulate === true || siteEmulated(site)" class="chip emulate">仿真</span><span v-if="site.notice" class="chip badge-unknown" :title="site.notice">⚠</span></span></span><span class="row-right"><label v-if="site.signin_applicable !== false" class="switch mini-switch sign-switch" :title="site.name+' 签到'" @click.stop><input v-model="model.sign_sites" type="checkbox" role="switch" :value="site.id" :aria-label="site.name+' 签到'"><span>签到</span></label><label class="switch mini-switch login-switch" :title="site.name+' 登录'" @click.stop><input v-model="model.login_sites" type="checkbox" role="switch" :value="site.id" :aria-label="site.name+' 登录'"><span>登录</span></label><button v-if="hasExtraSettings(site)" type="button" class="btn ghost mini expand-icon" :aria-expanded="openSites.includes(site.id)" :aria-label="(openSites.includes(site.id) ? '收起配置 ' : '展开配置 ')+site.name" @click.prevent="toggleSite(site.id)">{{ openSites.includes(site.id) ? '▾' : '▸' }}</button></span></summary><div class="site-detail"><label v-if="site.emulate === true" class="switch" @click.stop><input type="checkbox" role="switch" :checked="siteEmulated(site)" :aria-label="site.name+' 仿真'" @change="toggleSiteEmulate(site)"><span>仿真（无头浏览器渲染）</span></label><div v-if="(site.fields || []).length && (model.sign_sites.includes(site.id) || model.login_sites.includes(site.id))" class="credentials"><div class="grid fields-grid"><label v-for="field in (site.fields || [])" :key="field.key" class="field"><span>{{ field.label }}</span><input v-model="model[field.key]" class="input" :type="field.type === 'password' && showPlain[site.id + '.' + field.key] ? 'text' : field.type" autocomplete="off"><button v-if="field.type === 'password'" type="button" class="btn ghost mini eye-btn" :aria-label="(showPlain[site.id + '.' + field.key] ? '隐藏' : '显示')+field.label" @click="showPlain[site.id + '.' + field.key] = !showPlain[site.id + '.' + field.key]">{{ showPlain[site.id + '.' + field.key] ? '隐藏' : '显示' }}</button></label></div></div></div></details><div v-if="!filteredSelected.length" class="empty">没有匹配的已启用站点</div></div></div>
<div v-if="!selected.length" class="empty">尚未启用站点。请从上方下拉清单选择。</div><dialog ref="customDialog" class="custom-dialog" aria-labelledby="custom-dialog-title"><div class="card-head"><h3 id="custom-dialog-title">编辑自定义站点</h3><button type="button" class="btn ghost" @click="customDialog.close()">关闭</button></div><div class="custom-list"><form v-for="site in customDraft" :key="site.id" class="custom-row custom-columns" @submit.prevent="saveCustomSite(site)"><label class="field"><span>站点名称</span><input class="input" v-model="site.name" required></label><label class="field"><span>站点地址</span><input class="input" type="url" v-model="site.url" required></label><label class="switch"><input type="checkbox" role="switch" v-model="site.emulate">仿真</label><label class="switch"><input type="checkbox" role="switch" :checked="model.sign_sites.includes(String(site.id))" @change="toggleCustomSignin(site, $event.target.checked)">是否签到</label><div class="row"><button type="submit" class="btn confirm mini">保存</button><button type="button" class="btn danger mini" @click="deleteCustomSite(site.id)">删除</button></div></form><p v-if="!customDraft.length" class="hint">暂无自定义站点</p><span role="alert">{{ error }}</span></div><div class="footer"><button type="button" class="btn ghost" @click="addCustomSite">新增站点</button></div></dialog>
</section><div class="footer"><button class="btn ghost" @click="emit('switch')">查看数据</button><button class="btn" @click="save">保存配置</button></div>
</section></div>
</template>
<style scoped src="./preview.css"></style>
