<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { watchHostTheme } from './theme.js'
const props = defineProps({ api: Object, pluginId: {type:String,default:'AutoPtCheckin'}, show_switch: {type:Boolean,default:true} })
const brokenIcons = ref({})
const emit = defineEmits(['close','switch','layout'])
const stats = ref(null), history = ref({total:0,items:[]}), error = ref('')
const showAllSites = ref(false), dayOverrides = ref({})
const siteFilter = ref('')
function toggleSiteFilter(key) { siteFilter.value = siteFilter.value === key ? '' : key; showAllSites.value = false }
const siteLimit = 8
const sortedSites = computed(() => [...(stats.value?.sites || [])].sort((a, b) =>
  Number(b.sign_state === 'failed' || b.login_state === 'failed') - Number(a.sign_state === 'failed' || a.login_state === 'failed')))
function trackMatches(site, filter) {
  const signFailed = site.sign_state === 'failed', loginFailed = site.login_state === 'failed'
  const signOff = site.sign_state === 'pending' || site.sign_state === 'disabled'
  const loginOff = site.login_state === 'pending' || site.login_state === 'disabled'
  return ({sign_success: site.sign_state === 'success',
           sign_failed: signFailed && site.sign_status !== 'unconfirmed',
           sign_unconfirmed: signFailed && site.sign_status === 'unconfirmed',
           login_success: site.login_state === 'success',
           login_failed: loginFailed,
           network_error: (site.sign_state !== 'success' && site.sign_status === 'network_error') ||
             (site.login_state !== 'success' && site.login_status === 'network_error'),
           maintenance: (site.sign_state !== 'success' && site.sign_status === 'maintenance') ||
             (site.login_state !== 'success' && site.login_status === 'maintenance'),
           protocol_pending: (site.sign_state !== 'success' && site.sign_status === 'protocol_pending') ||
             (site.login_state !== 'success' && site.login_status === 'protocol_pending'),
           off: signOff && loginOff})[filter]
}
const filteredSites = computed(() => sortedSites.value.filter(site => !siteFilter.value || trackMatches(site, siteFilter.value)))
const visibleSites = computed(() => showAllSites.value ? filteredSites.value : filteredSites.value.slice(0, siteLimit))
function historyDay(value) {
  if (!value || Number.isNaN(new Date(value).getTime())) return '日期未知'
  return formatTime(value).slice(0, 10).replaceAll('/', '-')
}
const historyDays = computed(() => {
  const groups = new Map()
  history.value.items.forEach((item, index) => {
    const day = historyDay(item.time)
    if (!groups.has(day)) groups.set(day, {day, records: []})
    groups.get(day).records.push({item, index})
  })
  return [...groups.values()].sort((a, b) => b.day.localeCompare(a.day))
})
function dayIsOpen(day) { return dayOverrides.value[day] ?? day === historyDay(new Date()) }
const trackChip = (site, kind) => {
  const state = site[kind + '_state']
  const raw = site[kind + '_status']
  const label = kind === 'login' ? '登录' : '签到'
  if (state !== 'success' && raw === 'network_error') return ['不可达', 'off']
  if (state !== 'success' && raw === 'maintenance') return ['维护', 'off']
  if (state !== 'success' && raw === 'protocol_pending') return ['待适配', 'off']
  if (state === 'success') return [label, 'success']
  if (state === 'failed') return [label, raw === 'unconfirmed' ? 'unknown' : 'failure']
  return [label, 'off']
}
function trackTitle(site, kind) {
  const message = site[kind + '_message']
  if (message) return message
  const state = site[kind + '_state']
  if (state === 'pending' || state === 'disabled') return '未进行'
  return status(site[kind + '_status'])[0]
}
const cardCls = site => {
  const pick = (state, raw) => state === 'success' ? 'success' : state === 'failed' ? (raw === 'unconfirmed' ? 'unknown' : 'failure') : ''
  return pick(site.sign_state, site.sign_status) || pick(site.login_state, site.login_status) || 'off'
}
function toggleDay(day) { dayOverrides.value[day] = !dayIsOpen(day) }
const trackStates = [
  {key: 'sign_success', label: '签到', cls: 'success'},
  {key: 'sign_failed', label: '签到', cls: 'failure'},
  {key: 'sign_unconfirmed', label: '签到', cls: 'unknown'},
  {key: 'login_success', label: '登录', cls: 'success'},
  {key: 'login_failed', label: '登录', cls: 'failure'},
  {key: 'network_error', label: '不可达', cls: 'off'},
  {key: 'maintenance', label: '维护', cls: 'off'},
  {key: 'protocol_pending', label: '待适配', cls: 'off'},
  {key: 'off', label: '未进行', cls: 'off'},
]
const states = {success:['成功','success'],signed:['已签','signed'],failed:['失败','failure'],unconfirmed:['未确认','unknown'],maintenance:['维护中/已关闭','off'],network_error:['站点不可达','off'],protocol_pending:['协议待适配','off'],disabled:['停用','off'],off:['未进行','off']}
const status = key => key === 'login_ok' ? ['登录成功','signed'] : key === 'auth_failed' ? ['认证失败','failure'] : key === 'cancelled' ? ['已取消','off'] : key === 'already' ? states.signed : key === 'skipped' ? ['已跳过','off'] : states[key] || states.unconfirmed
function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = number => String(number).padStart(2, '0')
  return `${date.getFullYear()}/${pad(date.getMonth()+1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
function formatShort(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = number => String(number).padStart(2, '0')
  return `${date.getFullYear()}/${pad(date.getMonth()+1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
const timeWindow = computed(() => { const pad = n => String(n ?? 0).padStart(2, '0'); return `${pad(stats.value?.schedule?.begin_hour)}:00~${pad(stats.value?.schedule?.end_hour)}:00` })
function siteName(id) {
  const s = (stats.value?.sites || []).find(x => x.id === id || String(x.id) === String(id))
  return s ? s.name : id
}
function resultMessage(item) { return [item.message, item.reward].filter(Boolean).join(' ') }
async function get(path) { const response = await props.api.get(`plugin/${props.pluginId}/${path}`); if (response?.success === false) throw new Error(response.message); return response?.data ?? response }
async function loadHistory() {
  const first = await get('history?page=1&size=100')
  const items = [...first.items]
  for (let page = 2; items.length < first.total; page++) {
    const next = await get(`history?page=${page}&size=100`)
    if (!next.items.length) break
    items.push(...next.items)
  }
  return {total: first.total, items}
}
async function load() {
  error.value = ''
  try {
    [stats.value, history.value] = await Promise.all([get('stats'), loadHistory()])
  } catch (e) { error.value = e.message || '加载失败' }
}
const busy = ref(false)
async function execute(action, domain = '') {
  busy.value = true; error.value = ''
  try {
    const response = await props.api.post(`plugin/${props.pluginId}/${action}${domain ? '?domain='+encodeURIComponent(domain) : ''}`)
    if (response?.success === false) throw new Error(response.message)
    await load()
  } catch (e) { error.value = e.message || '执行请求失败' }
  finally { busy.value = false }
}
async function verifyAll() {
  for (const site of stats.value.sites.filter(s => s.can_verify)) await execute('verify_site', site.id)
}
let stopTheme
onMounted(() => { stopTheme = watchHostTheme(); load() })
onBeforeUnmount(() => stopTheme?.())
emit('layout',{maxWidth:'1000px'})
</script>
<template><div class="pt-center"><section class="card embedded-card" aria-label="运行数据页"><div class="card-head"><h2>PT 签到中心</h2><div class="row"><button v-if="show_switch" class="btn ghost" @click="emit('switch')">配置</button><button class="btn ghost" @click="emit('close')">关闭</button></div></div>
<div v-if="error" class="win" role="alert">{{ error }} <button class="btn ghost" @click="load">重试</button></div>
<template v-else-if="stats"><div class="win"><div class="topline"><div><h3 style="margin:0">站点状态总览</h3><p class="hint">下次调度：<b>{{ formatShort(stats.next_schedule) || '暂无调度' }}</b> · {{ stats.schedule.mode === 'cron' ? 'Cron：' + (stats.schedule.cron || '未配置') : '间隔：' + stats.schedule.interval_hours + ' 小时 · ' + timeWindow }}</p></div><div class="row" style="gap:8px"><button class="btn" :disabled="busy" @click="execute('manual_signin')">{{ busy ? '执行中…' : '立即签到' }}</button><button class="btn ghost" :disabled="busy" @click="verifyAll">只读核验</button><button class="btn ghost" :disabled="busy" @click="execute('run_once')">立即运行</button><button class="btn ghost" :disabled="busy" @click="execute('clean_today')">清理缓存</button></div></div>
<div class="stats-row"><div class="stats-group"><h4 class="stats-title">签到统计</h4><div class="stats"><div v-for="key in ['success','failed','unconfirmed']" :key="'s-'+key" class="stat" :class="status(key)[1]"><strong>{{ (stats.latest.sign || {})[key] || 0 }}</strong><span>{{ key === 'success' ? '成功' : status(key)[0] }}</span></div></div></div><div class="stats-group"><h4 class="stats-title">登录统计</h4><div class="stats"><div v-for="key in ['success','failed','unconfirmed']" :key="'l-'+key" class="stat" :class="status(key)[1]"><strong>{{ (stats.latest.login || {})[key] || 0 }}</strong><span>{{ key === 'success' ? '成功' : status(key)[0] }}</span></div></div></div></div><div class="site-filters" aria-label="筛选站点状态"><button v-for="item in trackStates" :key="item.key" type="button" class="chip" :class="item.cls" :aria-pressed="siteFilter === item.key" @click="toggleSiteFilter(item.key)">{{ item.label }}</button></div><div class="data-grid"><article v-for="site in visibleSites" :key="site.id" class="site-card" :class="'is-'+cardCls(site)"><div class="site-head"><strong class="site-label"><img v-if="site.icon && !brokenIcons[site.id]" class="site-icon" :src="site.icon" alt="" @error="brokenIcons[site.id] = true"><span v-else class="site-icon site-initial" aria-hidden="true">{{ site.name?.slice(0,1) }}</span>{{ site.name }}</strong><span class="head-right"><button class="btn ghost pico verify-btn" aria-label="测试连接" title="测试连接" :disabled="busy || !site.can_verify" @click="execute('verify_site',site.id)">⇄</button><span class="chip" :class="trackChip(site,'sign')[1]" :title="`签到：${trackTitle(site,'sign')}`">{{ trackChip(site,'sign')[0] }}</span><span class="chip" :class="trackChip(site,'login')[1]" :title="`登录：${trackTitle(site,'login')}`">{{ trackChip(site,'login')[0] }}</span></span></div><div class="row"><button v-if="site.sign_selected" class="btn ghost pico" :disabled="busy || !site.can_signin" @click="execute('signin_by_domain',site.id)">签到</button><button v-if="site.login_selected" class="btn ghost pico" :disabled="busy || !site.can_login" @click="execute('login_by_domain',site.id)">登录</button></div></article></div><button v-if="filteredSites.length > siteLimit" class="btn ghost sites-toggle" :aria-expanded="showAllSites" @click="showAllSites = !showAllSites">{{ showAllSites ? '收起其余站点' : `展开其余 ${filteredSites.length - siteLimit} 个站点` }}</button><div v-if="!stats.sites.length" class="empty">暂无站点结果</div><div v-else-if="!filteredSites.length" class="empty">该状态暂无站点</div><h3 style="margin:28px 0 0">历史记录</h3></div>
<div class="table-wrap"><table><caption class="hint" style="text-align:left;padding:0 24px 12px">{{ history.total || 0 }} 条记录</caption><thead><tr><th v-for="label in ['时间','站点','状态','最近消息']" :key="label">{{ label }}</th></tr></thead><tbody><template v-for="group in historyDays" :key="group.day"><tr class="history-day"><th colspan="4"><button class="btn ghost mini" :aria-expanded="dayIsOpen(group.day)" @click="toggleDay(group.day)">{{ dayIsOpen(group.day) ? '▾' : '▸' }} {{ group.day }} · {{ group.records.length }} 条记录</button></th></tr><template v-if="dayIsOpen(group.day)"><template v-for="{item,index} in group.records" :key="index"><tr><td>{{ formatTime(item.time) }}</td><td>{{ siteName(item.site) }}</td><td><span class="chip" :class="status(item.status)[1]">{{ status(item.status)[0] }}</span></td><td>{{ resultMessage(item) }}</td></tr></template></template></template><tr v-if="!history.items.length"><td colspan="4" class="muted">暂无历史记录</td></tr></tbody></table></div></template><div v-else class="win">加载中…</div></section></div></template>
<style scoped src="./preview.css"></style>
