<script setup>
import { reactive, ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { sourceBadge, credentialBadge } from './badges.js'
import defaults from '../../config_defaults.json'
import { watchHostTheme } from './theme.js'
const props = defineProps({ initialConfig: Object, api: Object, pluginId: { type: String, default: 'ForumSignin' } })
const emit = defineEmits(['save','switch','close','layout'])
const model = reactive({ ...structuredClone(defaults), ...(props.initialConfig || {}) })
const tab = ref('settings'), openSites = ref([]), sites = ref([]), error = ref('')
const fields = { fengchao: [{ key:'fengchao_api_key', label:'蜂巢 API Key', type:'password' }], yaowan:[{ key:'yaowan_cookie', label:'药丸 Cookie', type:'password' }], ssdforum:[{ key:'ssdforum_cookie', label:'SSDForum Cookie', type:'password' }] }
const selected = computed(() => sites.value.filter(site => model.enabled_sites.includes(site.id)))
function toggle(id) { openSites.value = openSites.value.includes(id) ? openSites.value.filter(x => x !== id) : [...openSites.value, id] }
function save() { emit('save', JSON.parse(JSON.stringify(model))) }
async function loadSites() {
  try { const response = await props.api?.get(`plugin/${props.pluginId}/sites`); const data = response?.data || response; sites.value = (data?.sites || []).map(site => ({ ...site, fields: fields[site.id] || [], source: site.source || '插件适配', credentialText: [site.credential?.kind, site.credential?.refresh].filter(Boolean).join(' / ') })) }
  catch { sites.value = ['fengchao','yaowan','ssdforum'].map(id => ({ id, name:{fengchao:'蜂巢',yaowan:'药丸',ssdforum:'SSDForum'}[id], source:'插件适配', credential:{kind:id === 'fengchao' ? 'api' : 'cookie'}, fields:fields[id], login_capable:false })) }
}
function syncStatus(site) { return site.id === 'fengchao' ? (model.fengchao_sync_status || {}) : null }
let stopTheme
onMounted(() => { stopTheme = watchHostTheme(); loadSites(); emit('layout', { maxWidth:'1000px' }) })
onBeforeUnmount(() => stopTheme?.())
</script>
<template>
<div class="pt-center"><section class="card embedded-card" aria-label="论坛签到配置"><div class="card-head"><h2>论坛签到</h2><button class="btn ghost" @click="emit('close')">关闭</button></div>
<div class="tabs" role="tablist"><button v-for="(label,key) in {settings:'设置',sites:'站点'}" :key="key" class="tab" role="tab" :aria-selected="tab===key" @click="tab=key">{{ label }}</button></div>
<section v-show="tab==='settings'" class="win"><div class="group"><h3>基础设置</h3><div class="grid"><label class="switch"><input v-model="model.enabled" type="checkbox" role="switch">启用插件</label><label class="switch"><input v-model="model.notify" type="checkbox" role="switch">发送通知</label></div></div>
<div class="group"><h3>蜂巢同步</h3><div class="grid"><label class="switch"><input v-model="model.timed_update_enabled" type="checkbox" role="switch">启用蜂巢同步</label><label class="field"><span>同步 Cron</span><input v-model="model.timed_update_cron" class="input"></label></div></div>
<div class="group"><h3>凭证</h3><div class="grid"><label class="field"><span>蜂巢 API Key</span><input v-model="model.fengchao_api_key" type="password" autocomplete="off" class="input"></label><label class="field"><span>药丸 Cookie</span><input v-model="model.yaowan_cookie" type="password" autocomplete="off" class="input"></label><label class="field"><span>SSDForum Cookie</span><input v-model="model.ssdforum_cookie" type="password" autocomplete="off" class="input"></label></div></div></section>
<section v-show="tab==='sites'" class="win"><div class="topline"><h3>论坛站点</h3><span class="chip blue">已启用 {{ selected.length }} 个站点</span></div><div class="enabled-site-list"><details v-for="site in sites" :key="site.id" class="site-card config-site" :open="openSites.includes(site.id)"><summary @click.prevent><strong class="site-name site-label"><span class="site-icon site-initial" aria-hidden="true">{{ site.name?.slice(0,1) }}</span>{{ site.name }}</strong><span class="chip" :class="sourceBadge(site.source)">{{ site.source || '插件适配' }}</span><label class="check" @click.stop><input v-model="model.enabled_sites" type="checkbox" :value="site.id">启用</label><button type="button" class="btn ghost mini expand-site" :aria-expanded="openSites.includes(site.id)" @click.stop="toggle(site.id)">{{ openSites.includes(site.id) ? '收起配置' : '展开配置' }}</button></summary><div class="site-detail"><p class="site-metadata hint">来源：{{ site.source || '插件适配' }} · 凭证：{{ site.credentialText || site.credential?.kind || '未配置' }} · 能力：{{ site.login_capable ? '签到/模拟登录' : '签到' }}</p><div v-if="site.id==='fengchao'" class="sync-box"><h3>蜂巢同步状态</h3><p class="hint">上次同步：{{ model.fengchao_user_info_updated_at || '暂无' }} · 未读数：{{ model.fengchao_user_info?.unread_count ?? '暂无' }}</p><label class="switch"><input v-model="model.timed_update_enabled" type="checkbox" role="switch">同步开关</label></div><div v-if="(fields[site.id] || []).length" class="credentials"><div class="grid"><label v-for="field in fields[site.id]" :key="field.key" class="field"><span>{{ field.label }}</span><input v-model="model[field.key]" :type="field.type" autocomplete="off" class="input"></label></div></div></div></details></div></section>
<div v-if="error" role="alert" class="alert">{{ error }}</div><div class="footer"><button class="btn ghost" @click="emit('switch')">查看数据</button><button class="btn" @click="save">保存配置</button></div></section></div>
</template>
<style scoped src="./preview.css"></style>
