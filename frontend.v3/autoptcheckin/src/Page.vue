<script setup>
import { ref, computed, inject, onMounted, onBeforeUnmount } from 'vue'
import { watchHostTheme } from './theme.js'
const props = defineProps({ api: Object, pluginId: {type:String,default:'AutoPtCheckin'}, show_switch: {type:Boolean,default:true} })
const brokenIcons = ref({})
// 规范 5.8：复用宿主统一 Toast；注入不存在时静默降级，保留页面内状态提示。
const toast = inject('moviepilot:toast', null)
const emit = defineEmits(['close','switch','layout','action'])
const stats = ref(null), history = ref({total:0,items:[]}), error = ref('')
const showAllSites = ref(false), dayOverrides = ref({})
const siteFilter = ref('')
function toggleSiteFilter(key) { siteFilter.value = siteFilter.value === key ? '' : key; showAllSites.value = false }
const siteLimit = 8
// 统一结果值（signed/login_ok/failed/pending/skipped/cancelled）+ reason 精确值；
// 旧记录/旧载荷无 reason 字段，按旧原始 status 兼容推导，不重写。
const LEGACY_REASONS = {unconfirmed: 'result_unknown', network_error: 'network_error',
  maintenance: 'maintenance', protocol_pending: 'protocol_pending', auth_failed: 'auth_failed'}
const legacyReason = status => LEGACY_REASONS[status] || ''
const trackReason = (site, kind) => site[kind + '_reason'] || legacyReason(site[kind + '_status'])
const trackPriority = site => Number(site.sign_state === 'failed' || site.login_state === 'failed' ||
  (site.sign_state === 'pending' && trackReason(site, 'sign') === 'result_unknown') ||
  (site.login_state === 'pending' && trackReason(site, 'login') === 'result_unknown'))
const sortedSites = computed(() => [...(stats.value?.sites || [])].sort((a, b) => trackPriority(b) - trackPriority(a)))
function trackMatches(site, filter) {
  const track = kind => ({state: site[kind + '_state'], status: site[kind + '_status'], reason: trackReason(site, kind)})
  const s = track('sign'), l = track('login')
  const unknown = t => (t.state === 'failed' && t.status === 'unconfirmed') ||
    (t.state === 'pending' && t.reason === 'result_unknown')
  const failed = t => t.state === 'failed' && t.status !== 'unconfirmed'
  const crossReason = (a, b, r) => (a.state !== 'success' && a.reason === r) || (b.state !== 'success' && b.reason === r)
  const off = t => t.state === 'disabled' || (t.state === 'pending' && !t.reason)
  return ({sign_success: s.state === 'success',
           sign_failed: failed(s),
           sign_unknown: unknown(s),
           login_success: l.state === 'success',
           login_failed: failed(l),
           unreachable: crossReason(s, l, 'network_error'),
           maintenance: crossReason(s, l, 'maintenance'),
           protocol: crossReason(s, l, 'protocol_pending'),
           off: off(s) && off(l)})[filter]
}
const filteredSites = computed(() => sortedSites.value.filter(site => !siteFilter.value || trackMatches(site, siteFilter.value)))
const visibleSites = computed(() => showAllSites.value ? filteredSites.value : filteredSites.value.slice(0, siteLimit))
function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = number => String(number).padStart(2, '0')
  return `${date.getFullYear()}/${pad(date.getMonth()+1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
function historyDay(value) {
  if (!value || Number.isNaN(new Date(value).getTime())) return '日期未知'
  return formatTime(value).slice(0, 10).replaceAll('/', '-')
}
const SUCCESS_STATUSES = new Set(['success', 'signed', 'already', 'login_ok'])
const UNREACHABLE_REASONS = new Set(['network_error', 'maintenance', 'protocol_pending'])
const historyDays = computed(() => {
  const today = historyDay(new Date())
  const groups = new Map()
  history.value.items.forEach((item, index) => {
    const day = historyDay(item.time)
    if (day === today) return
    if (!groups.has(day)) groups.set(day, {day, records: [], success: 0, failed: 0, unconfirmed: 0, unreachable: 0})
    const group = groups.get(day)
    group.records.push({item, index})
    const reason = item.reason || legacyReason(item.status)
    if (SUCCESS_STATUSES.has(item.status)) group.success++
    else if (item.status === 'failed' || item.status === 'auth_failed') group.failed++
    else if (item.status === 'pending' || item.status === 'unconfirmed') {
      if (UNREACHABLE_REASONS.has(reason)) group.unreachable++
      else group.unconfirmed++
    }
  })
  return [...groups.values()].sort((a, b) => b.day.localeCompare(a.day))
})
function dayIsOpen(day) { return !!dayOverrides.value[day] }
function toggleDay(day) { dayOverrides.value[day] = !dayIsOpen(day) }
const REASON_LABELS = {already_signed: '已签', result_unknown: '结果待确认', network_error: '不可达',
  maintenance: '维护中', protocol_pending: '待验证', auth_failed: '认证失败'}
const trackChip = (site, kind) => {
  const state = site[kind + '_state']
  const raw = site[kind + '_status']
  const reason = trackReason(site, kind)
  const label = kind === 'login' ? '登录' : '签到'
  if (state === 'success') return [label, 'success']
  if (state === 'failed') return [label, 'failure']
  if (state === 'pending') {
    if (reason === 'result_unknown') return ['结果待确认', 'unknown']
    if (reason === 'network_error') return ['不可达', 'off']
    if (reason === 'maintenance') return ['维护中', 'off']
    if (reason === 'protocol_pending') return ['待验证', 'off']
    return ['待执行', 'off']
  }
  return [label, 'off']
}
function trackTitle(site, kind) {
  const message = site[kind + '_message']
  if (message) return message
  const state = site[kind + '_state']
  const reason = trackReason(site, kind)
  if (state === 'pending') return REASON_LABELS[reason] || '待执行'
  return '未进行'
}
const cardCls = site => {
  const pick = (state, raw, reason) =>
    state === 'success' ? 'success'
      : state === 'failed' ? ((raw === 'unconfirmed' || reason === 'result_unknown') ? 'unknown' : 'failure')
      : (state === 'pending' && reason === 'result_unknown') ? 'unknown' : ''
  return pick(site.sign_state, site.sign_status, trackReason(site, 'sign')) ||
    pick(site.login_state, site.login_status, trackReason(site, 'login')) || 'off'
}
function cardMessage(site) {
  const pick = (kind) => {
    if (site[kind + '_state'] === 'success') return ''
    const msg = site[kind + '_message']
    return msg ? `${kind === 'login' ? '登录' : '签到'}：${msg}` : ''
  }
  return pick('sign') || pick('login')
}
const trackStates = [
  {key: 'sign_success', label: '签到', cls: 'success'},
  {key: 'sign_failed', label: '签到', cls: 'failure'},
  {key: 'sign_unknown', label: '结果待确认', cls: 'unknown'},
  {key: 'login_success', label: '登录', cls: 'success'},
  {key: 'login_failed', label: '登录', cls: 'failure'},
  {key: 'unreachable', label: '不可达', cls: 'off'},
  {key: 'maintenance', label: '维护中', cls: 'off'},
  {key: 'protocol', label: '待验证', cls: 'off'},
  {key: 'off', label: '待执行', cls: 'off'},
]
const states = {success:['成功','success'],signed:['已签','signed'],login_ok:['登录成功','signed'],failed:['失败','failure'],pending:['待处理','off'],skipped:['已跳过','off'],cancelled:['已取消','off'],unconfirmed:['结果待确认','unknown'],maintenance:['维护中','off'],network_error:['不可达','off'],protocol_pending:['待验证','off'],auth_failed:['认证失败','failure'],disabled:['停用','off'],off:['未进行','off']}
// 历史行徽标：新统一值按 reason 细分，旧原始值经 legacyReason 兼容推导。
function historyBadge(item) {
  const key = item.status, reason = item.reason || legacyReason(key)
  if (key === 'signed') return reason === 'already_signed' ? states.signed : ['成功','success']
  if (key === 'pending') return ({result_unknown: ['结果待确认','unknown'], network_error: ['不可达','off'],
    maintenance: ['维护中','off'], protocol_pending: ['待验证','off']})[reason] || ['待执行','off']
  return states[key] || ['结果待确认','unknown']
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
    emit('action')
  } catch (e) { error.value = e.message || '加载失败'; toast?.error(error.value) }
}
async function toggleTrack(site, kind, on) {
  await execute(`site_track?domain=${encodeURIComponent(site.id)}&track=${kind}&on=${on ? 1 : 0}`)
}
const busy = ref(false)
async function execute(action, domain = '') {
  busy.value = true; error.value = ''
  try {
    const response = await props.api.post(`plugin/${props.pluginId}/${action}${domain ? '?domain='+encodeURIComponent(domain) : ''}`)
    if (response?.success === false) throw new Error(response.message)
    await load()
  } catch (e) { error.value = e.message || '执行请求失败'; toast?.error(error.value) }
  finally { busy.value = false }
}
let stopTheme
onMounted(() => { stopTheme = watchHostTheme(); load() })
onBeforeUnmount(() => stopTheme?.())
emit('layout',{maxWidth:'1000px'})
</script>
<template><div class="pt-center"><section class="card embedded-card" aria-label="运行数据页"><div class="card-head"><h2>PT 签到中心</h2><div class="row"><button v-if="show_switch" class="btn ghost" @click="emit('switch')">配置</button><button class="btn ghost" @click="emit('close')">关闭</button></div></div>
<div v-if="error" class="win" role="alert">{{ error }} <button class="btn ghost" @click="load">重试</button></div>
<template v-else-if="stats"><div class="win"><div class="topline"><div><h3 style="margin:0">站点状态总览</h3><p class="hint">下次调度：<b>{{ formatShort(stats.next_schedule) || '暂无调度' }}</b> · {{ stats.schedule.mode === 'cron' ? 'Cron：' + (stats.schedule.cron || '未配置') : '间隔：' + stats.schedule.interval_hours + ' 小时 · ' + timeWindow }}</p></div><div class="row" style="gap:8px"><button class="btn ghost" :disabled="busy" @click="execute('run_once')">{{ busy ? '执行中…' : '立即运行' }}</button><button class="btn ghost" :disabled="busy" @click="execute('clean_today')">清理缓存</button><button class="btn ghost refresh-btn" aria-label="刷新数据" title="刷新数据" :disabled="busy" @click="load">⟳</button></div></div>
<div class="stats-row"><div class="stat-card" v-for="group in [{key:'sign',label:'签到统计'},{key:'login',label:'登录统计'}]" :key="group.key"><h4 class="stats-title">{{ group.label }}</h4><div class="stats-numbers"><strong class="num-success">{{ (stats.latest[group.key]||{}).success || 0 }}</strong><span class="stats-sep">/</span><strong class="num-failure">{{ (stats.latest[group.key]||{}).failed || 0 }}</strong><span class="stats-sep">/</span><strong class="num-unknown">{{ (stats.latest[group.key]||{}).pending || 0 }}</strong></div><div class="stats-labels"><span class="num-success">成功</span><span class="stats-sep">/</span><span class="num-failure">失败</span><span class="stats-sep">/</span><span class="num-unknown">待处理</span></div></div></div>
<div class="site-filters" aria-label="筛选站点状态"><button v-for="item in trackStates" :key="item.key" type="button" class="chip" :class="item.cls" :aria-pressed="siteFilter === item.key" @click="toggleSiteFilter(item.key)">{{ item.label }}</button></div>
<div class="data-grid"><article v-for="site in visibleSites" :key="site.id" class="site-card" :class="'is-'+cardCls(site)"><div class="site-head"><strong class="site-label"><img v-if="site.icon && !brokenIcons[site.id]" class="site-icon" :src="site.icon" alt="" @error="brokenIcons[site.id] = true"><span v-else class="site-icon site-initial" aria-hidden="true">{{ site.name?.slice(0,1) }}</span><a v-if="site.url" class="site-link" :href="site.url" target="_blank" rel="noopener" @click.stop>{{ site.name }}</a><span v-else>{{ site.name }}</span><button class="verify-btn" aria-label="测试连接" title="测试连接" :disabled="busy || !site.can_verify" @click="execute('verify_site',site.id)">🔗</button></strong><span class="head-right"><span v-if="site.sign_selected && !site.sign_disabled_struct" class="chip" :class="trackChip(site,'sign')[1]" :title="`签到：${trackTitle(site,'sign')}`">{{ trackChip(site,'sign')[0] }}</span><span v-if="site.login_selected && !site.login_disabled_struct" class="chip" :class="trackChip(site,'login')[1]" :title="`登录：${trackTitle(site,'login')}`">{{ trackChip(site,'login')[0] }}</span><span v-if="site.cf === true" class="chip badge-cf-yes">CF 盾</span><span v-if="site.shield === 'cloud'" class="chip badge-shield-cloud">云签</span><span v-else-if="site.emulate === true" class="chip badge-emulate">仿真</span><span v-if="site.notice" class="chip badge-unknown" :title="site.notice">⚠</span></span></div><p v-if="cardMessage(site)" class="site-error-line" :title="cardMessage(site)">{{ cardMessage(site) }}</p><div class="row" v-if="!site.sign_disabled_struct || !site.login_disabled_struct"><button v-if="site.sign_selected && !site.sign_disabled_struct" class="btn ghost pico" :disabled="busy || !site.can_signin" @click="execute('signin_by_domain',site.id)">签到</button><button v-if="site.login_selected && !site.login_disabled_struct" class="btn ghost pico" :disabled="busy || !site.can_login" @click="execute('login_by_domain',site.id)">登录</button><span class="row-toggles"><label v-if="site.sign_track_available" class="mini-switch" :title="(site.sign_selected?'停用':'启用')+'签到轨道'"><input type="checkbox" role="switch" :checked="!!site.sign_selected" :disabled="busy" @change="toggleTrack(site,'sign',$event.target.checked)"><span>签</span></label><label v-if="site.login_track_available" class="mini-switch" :title="(site.login_selected?'停用':'启用')+'登录轨道'"><input type="checkbox" role="switch" :checked="!!site.login_selected" :disabled="busy" @change="toggleTrack(site,'login',$event.target.checked)"><span>登</span></label></span></div></article></div>
<button v-if="filteredSites.length > siteLimit" class="btn ghost sites-toggle" :aria-expanded="showAllSites" @click="showAllSites = !showAllSites">{{ showAllSites ? '收起其余站点' : `展开其余 ${filteredSites.length - siteLimit} 个站点` }}</button><div v-if="!stats.sites.length" class="empty">暂无站点结果</div><div v-else-if="!filteredSites.length" class="empty">该状态暂无站点</div><h3 style="margin:28px 0 0">历史记录</h3></div>
<div class="table-wrap"><table><caption class="hint" style="text-align:left;padding:0 24px 12px">{{ history.total || 0 }} 条记录</caption><thead><tr><th v-for="label in ['时间','站点','状态','最近消息']" :key="label">{{ label }}</th></tr></thead><tbody><template v-for="group in historyDays" :key="group.day"><tr class="history-day"><th colspan="4"><button class="btn ghost mini" :aria-expanded="dayIsOpen(group.day)" @click="toggleDay(group.day)">{{ dayIsOpen(group.day) ? '▾' : '▸' }} {{ group.day }} · {{ group.records.length }} 条 · <span class="num-success">成功 {{ group.success }}</span> / <span class="num-failure">失败 {{ group.failed }}</span> / <span class="num-unknown">未确认 {{ group.unconfirmed }}</span> / <span class="num-off">不可达 {{ group.unreachable }}</span></button></th></tr><template v-if="dayIsOpen(group.day)"><template v-for="{item,index} in group.records" :key="index"><tr><td>{{ formatTime(item.time) }}</td><td>{{ siteName(item.site) }}</td><td><span class="chip" :class="historyBadge(item)[1]">{{ historyBadge(item)[0] }}</span></td><td>{{ resultMessage(item) }}</td></tr></template></template></template><tr v-if="!historyDays.length"><td colspan="4" class="muted">暂无历史记录</td></tr></tbody></table></div></template><div v-else class="win">加载中…</div></section></div></template>
<style scoped src="./preview.css"></style>
