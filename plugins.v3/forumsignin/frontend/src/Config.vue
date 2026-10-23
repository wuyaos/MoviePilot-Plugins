<script setup>
import { reactive, ref, computed, onMounted, onBeforeUnmount } from 'vue'
import defaults from '../../config_defaults.json'
import { sourceBadge } from './badges.js'
import { watchHostTheme } from './theme.js'
const props = defineProps({ initialConfig:Object, api:Object, pluginId:{type:String,default:'ForumSignin'} })
const emit = defineEmits(['save','switch','close','layout'])
const model=reactive({...structuredClone(defaults),...(props.initialConfig||{})}), sites=ref([]), expanded=ref([]), error=ref('')
const enabledCount=computed(()=>model.enabled_sites.length)
function toggle(id){expanded.value=expanded.value.includes(id)?expanded.value.filter(x=>x!==id):[...expanded.value,id]}
function save(){emit('save',JSON.parse(JSON.stringify(model)))}
async function load(){try{const r=await props.api.get(`plugin/${props.pluginId}/stats`);const d=r?.data??r;sites.value=(d.sites||[])}catch(e){error.value=e.message||'站点列表加载失败'}}
function remove(id){model.enabled_sites=model.enabled_sites.filter(value=>value!==id); expanded.value=expanded.value.filter(value=>value!==id)}
const fieldsFor=site=>site.credential?.fields||[]
let stopTheme
onMounted(()=>{stopTheme=watchHostTheme();load();emit('layout',{maxWidth:'1000px'})})
onBeforeUnmount(()=>stopTheme?.())
</script>
<template><div class="pt-center"><section class="card embedded-card" aria-label="论坛签到配置"><div class="card-head"><h2>论坛签到</h2><button class="btn ghost" @click="emit('close')">关闭</button></div>

<section class="win"><div class="group"><h3>基础设置</h3><div class="grid"><label class="switch"><input v-model="model.enabled" type="checkbox" role="switch">启用插件</label><label class="switch"><input v-model="model.notify" type="checkbox" role="switch">发送通知</label><label class="field"><span>调度模式</span><select v-model="model.onlyonce" class="input"><option :value="false">定时签到</option><option :value="true">启动后运行一次</option></select></label><label class="field"><span>签到 Cron</span><input v-model="model.cron" class="input"></label><label class="field"><span>失败重试次数</span><input v-model.number="model.retry_count" type="number" min="0" class="input"></label><label class="field"><span>重试间隔（分钟）</span><input v-model.number="model.retry_interval" type="number" min="1" class="input"></label></div></div>
<div class="group"><h3>执行调度</h3><div class="row"><label class="switch"><input v-model="model.timed_update_enabled" type="checkbox" role="switch">蜂巢信息定时同步</label><label class="field"><span>同步 Cron</span><input v-model="model.timed_update_cron" class="input"></label></div></div></section>
<section class="win" style="margin-top:16px"><div class="topline"><h3>论坛站点</h3><span class="chip blue">已启用 {{enabledCount}} 个站点</span></div><div class="enabled-site-list"><details v-for="site in sites" :key="site.id" class="site-card config-site" :open="expanded.includes(site.id)"><summary @click.prevent><button class="remove-icon" :aria-label="`移除${site.name}`" @click.stop="remove(site.id)">×</button><strong class="site-name site-label"><span class="site-icon site-initial">{{site.name?.slice(0,1)}}</span>{{site.name}}</strong><span class="chip" :class="sourceBadge(site.source)">{{site.source||'插件适配'}}</span><label class="switch compact-switch" @click.stop><input v-model="model.enabled_sites" type="checkbox" :value="site.id" role="switch">签到</label><button class="btn ghost mini expand-site" @click.stop="toggle(site.id)">{{expanded.includes(site.id)?'收起':'展开配置'}}</button></summary><div class="site-detail"><div class="credentials"><div class="grid"><label v-for="field in fieldsFor(site)" :key="field.key" class="field"><span>{{field.label}}</span><input v-model="model[field.key]" :type="field.type||'text'" autocomplete="off" class="input"></label></div></div><p class="hint">{{site.domain}}</p></div></details></div></section>
<div v-if="error" role="alert" class="alert">{{error}}</div><div class="footer"><button class="btn ghost" @click="emit('switch')">查看数据</button><button class="btn" @click="save">保存配置</button></div></section></div></template>
<style scoped src="./preview.css"></style>
