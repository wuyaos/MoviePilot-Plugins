<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { watchHostTheme } from './theme.js'
const props = defineProps({ api: Object, pluginId: {type:String,default:'AutoPtCheckin'}, show_switch: {type:Boolean,default:true} })
const brokenIcons = ref({})
const emit = defineEmits(['close','switch','layout'])
const stats = ref(null), history = ref({total:0,items:[]}), expanded = ref([]), error = ref('')
const showAllSites = ref(false), dayOverrides = ref({})
const siteFilter = ref('')
function toggleSiteFilter(key) { siteFilter.value = siteFilter.value === key ? '' : key; showAllSites.value = false }
const siteLimit = 8
const sortedSites = computed(() => [...(stats.value?.sites || [])].sort((a, b) =>
  Number(['failed','unconfirmed','auth_failed'].includes(b.status)) - Number(['failed','unconfirmed','auth_failed'].includes(a.status))))
function trackMatches(site, filter) {
  const sb = site.sign_status, lb = site.login_status
  return ({sign_success: sb === 'success' || sb === 'signed',
           sign_failed: sb === 'failed' || sb === 'auth_failed',
           sign_unconfirmed: sb === 'unconfirmed',
           login_success: lb === 'success' || lb === 'signed' || lb === 'login_ok',
           login_failed: lb === 'failed' || lb === 'auth_failed',
           protocol_pending: sb === 'protocol_pending' || lb === 'protocol_pending',
           network_error: sb === 'network_error' || lb === 'network_error',
           maintenance: sb === 'maintenance' || lb === 'maintenance',
           off: (sb === 'off' || !sb) && (lb === 'off' || !lb)})[filter]
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
function toggleDay(day) { dayOverrides.value[day] = !dayIsOpen(day) }
const trackStates = {
  sign_success: ['签到成功', 'success'],
  sign_failed: ['签到失败', 'failure'],
  sign_unconfirmed: ['签到未确认', 'unknown'],
  login_success: ['登录成功', 'signed'],
  login_failed: ['登录失败', 'failure'],
  protocol_pending: ['协议待适配', 'off'],
  network_error: ['站点不可达', 'off'],
  maintenance: ['维护中/已关闭', 'off'],
  off: ['停用/未尝试', 'off'],
}
const legacyStates = {success:['成功','success'],signed:['已签','signed'],failed:['失败','failure'],unconfirmed:['未确认','unknown'],maintenance:['维护中/已关闭','off'],network_error:['站点不可达','off'],protocol_pending:['协议待适配','off'],disabled:['停用','off']}
const status = key => key === 'login_ok' ? ['登录成功','signed'] : key === 'auth_failed' ? ['认证失败','failure'] : key === 'cancelled' ? ['已取消','off'] : key === 'already' ? states.signed : key === 'skipped' ? ['已跳过','off'] : states[key] || states.unconfirmed
const evidence = {button_text:'回读按钮文本',uid:'本人 UID',date:'记录日期',record_status:'记录状态'}
function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = number => String(number).padStart(2, '0')
  return `${date.getFullYear()}/${pad(date.getMonth()+1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
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
    expanded.value = []
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
function toggle(id) { expanded.value = expanded.value.includes(id) ? expanded.value.filter(x=>x!==id) : [...expanded.value,id] }
let stopTheme
onMounted(() => { stopTheme = watchHostTheme(); load() })
onBeforeUnmount(() => stopTheme?.())
emit('layout',{maxWidth:'1000px'})
</script>
<template><div class="pt-center"><section class="card embedded-card" aria-label="运行数据页"><div class="card-head"><h2>PT 签到中心</h2><div class="row"><button v-if="show_switch" class="btn ghost" @click="emit('switch')">配置</button><button class="btn ghost" @click="emit('close')">关闭</button></div></div>
<div v-if="error" class="win" role="alert">{{ error }} <button class="btn ghost" @click="load">重试</button></div>
<template v-else-if="stats"><div class="win"><div class="topline"><div><h3 style="margin:0">站点状态总览</h3><p class="hint">下次调度：<b>{{ stats.next_schedule || '暂无调度' }}</b> · {{ stats.schedule.mode === 'cron' ? 'Cron：' + (stats.schedule.cron || '未配置') : '间隔：' + stats.schedule.interval_hours + ' 小时 · ' + stats.schedule.begin_hour + '–' + stats.schedule.end_hour + ' 时' }}</p></div><div class="row" style="gap:8px"><button class="btn" :disabled="busy" @click="execute('manual_signin')">{{ busy ? '执行中…' : '立即签到' }}</button><button class="btn ghost" :disabled="busy" @click="verifyAll">只读核验</button><button class="btn ghost" :disabled="busy" @click="execute('run_once')">立即运行一次</button><button class="btn ghost" :disabled="busy" @click="execute('clean_today')">清理本日缓存</button></div></div>
<div class="stats-group"><h4 class="stats-title">签到</h4><div class="stats"><div v-for="key in ['success','failed','unconfirmed']" :key="'s-'+key" class="stat" :class="status(key)[1]"><strong>{{ (stats.latest.sign || {})[key] || 0 }}</strong><span>{{ key === 'success' ? '成功' : status(key)[0] }}</span></div></div></div><div class="stats-group"><h4 class="stats-title">模拟登录</h4><div class="stats"><div v-for="key in ['success','failed','unconfirmed']" :key="'l-'+key" class="stat" :class="status(key)[1]"><strong>{{ (stats.latest.login || {})[key] || 0 }}</strong><span>{{ key === 'success' ? '成功' : status(key)[0] }}</span></div></div></div><div class="site-filters" aria-label="筛选站点状态"><button v-for="(value,key) in trackStates" :key="key" type="button" class="chip" :class="value[1]" :aria-pressed="siteFilter === key" @click="toggleSiteFilter(key)">{{ value[0] }}</button></div><div class="data-grid"><article v-for="site in visibleSites" :key="site.id" class="site-card" :class="'is-'+status(site.status)[1]"><div class="site-head"><strong class="site-label"><img v-if="site.icon && !brokenIcons[site.id]" class="site-icon" :src="site.icon" alt="" @error="brokenIcons[site.id] = true"><span v-else class="site-icon site-initial" aria-hidden="true">{{ site.name?.slice(0,1) }}</span>{{ site.name }}</strong><span class="chip" :class="status(site.sign_status)[1]" :title="`签到：${site.sign_message || status(site.sign_status)[0]}`">签{{ status(site.sign_status)[0] }}</span><span v-if="site.login_status && site.login_status !== 'off'" class="chip" :class="status(site.login_status)[1]" :title="`登录：${site.login_message || status(site.login_status)[0]}`">登{{ status(site.login_status)[0] }}</span></div><div class="row"><button v-if="site.sign_selected" class="btn ghost mini" :disabled="busy || !site.can_signin" @click="execute('signin_by_domain',site.id)">单站签到</button><button v-if="site.login_selected" class="btn ghost mini" :disabled="busy || !site.can_login" @click="execute('login_by_domain',site.id)">模拟登录</button><button class="btn ghost mini" :disabled="busy || !site.can_verify" @click="execute('verify_site',site.id)">只读核验</button></div></article></div><button v-if="filteredSites.length > siteLimit" class="btn ghost sites-toggle" :aria-expanded="showAllSites" @click="showAllSites = !showAllSites">{{ showAllSites ? '收起其余站点' : `展开其余 ${filteredSites.length - siteLimit} 个站点` }}</button><div v-if="!stats.sites.length" class="empty">暂无站点结果</div><div v-else-if="!filteredSites.length" class="empty">该状态暂无站点</div><h3 style="margin:28px 0 0">历史记录</h3></div>
<div class="table-wrap"><table><caption class="hint" style="text-align:left;padding:0 24px 12px">{{ history.total || 0 }} 条记录</caption><thead><tr><th v-for="label in ['时间','站点','状态','最近消息','证据']" :key="label">{{ label }}</th></tr></thead><tbody><template v-for="group in historyDays" :key="group.day"><tr class="history-day"><th colspan="5"><button class="btn ghost mini" :aria-expanded="dayIsOpen(group.day)" @click="toggleDay(group.day)">{{ dayIsOpen(group.day) ? '▾' : '▸' }} {{ group.day }} · {{ group.records.length }} 条记录</button></th></tr><template v-if="dayIsOpen(group.day)"><template v-for="{item,index} in group.records" :key="index"><tr><td>{{ formatTime(item.time) }}</td><td>{{ siteName(item.site) }}</td><td><span class="chip" :class="status(item.status)[1]">{{ status(item.status)[0] }}</span></td><td>{{ resultMessage(item) }}</td><td><button class="btn ghost mini" :aria-expanded="expanded.includes(index)" @click="toggle(index)">{{ expanded.includes(index) ? '收起证据' : '展开证据' }}</button></td></tr><tr v-if="expanded.includes(index)" class="evidence"><td colspan="5"><div class="evidence-grid"><div v-for="(label,key) in evidence" :key="key"><span>{{ label }}</span>{{ item.evidence?.[key] || '' }}</div></div></td></tr></template></template></template><tr v-if="!history.items.length"><td colspan="5" class="muted">暂无历史记录</td></tr></tbody></table></div><div class="footer"><div class="legend"><span v-for="(value,key) in states" :key="key" class="chip" :class="value[1]">{{ value[0] }}</span></div></div></template><div v-else class="win">加载中…</div></section></div></template>
<style scoped src="./preview.css"></style>
