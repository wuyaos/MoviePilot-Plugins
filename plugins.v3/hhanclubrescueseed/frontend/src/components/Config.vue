<script setup>
import { getCurrentInstance, inject, onMounted, reactive, ref } from 'vue'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'Hhanclubrescueseed' },
  initialConfig: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['save', 'close'])
const toast = inject('moviepilot:toast', null)
const instance = getCurrentInstance()
const pluginApi = instance?.proxy?.$pluginApi || props.api

const defaults = {
  enable: false, run_once: false, history_rescue_enabled: false,
  cron: '*/20 14-15 * * *', monitor_cron: '*/10 * * * *',
  downloader: null, save_path: null, custom_tag: '憨憨保种', reward_tag: null,
  reward_hours: 18, enable_notification: false, notify_on_zero_torrents: false,
  force_resume: false, auto_delete_enabled: false, delete_files: true,
  disk_quota_gb: null, stuck_days: 7, seeding_count: '1-3', torrent_size: null,
  download_limit: 5, max_downloading: 3, max_pages: 5, min_downloaders: 1,
  completion_ratio_max: 20, connect_time_max_hours: null, free: false,
}
const CONFIG_KEYS = Object.keys(defaults)
function projectInitialConfig(source) {
  return CONFIG_KEYS.reduce((result, key) => {
    if (Object.prototype.hasOwnProperty.call(source || {}, key) && source[key] != null) result[key] = source[key]
    return result
  }, {})
}
const form = reactive({ ...defaults, ...projectInitialConfig(props.initialConfig) })
const savedForm = ref({ ...form })
const downloaders = ref([])
const loading = ref(false)
const loadingConfig = ref(false)
const error = ref('')

function notify(type, message) {
  if (toast && typeof toast[type] === 'function') toast[type](message)
  else (type === 'error' ? console.error : console.log)(message)
}
function unwrap(response) {
  return response?.data && typeof response.data.success === 'boolean' ? response.data : response
}
function projectConfig() {
  return CONFIG_KEYS.reduce((payload, key) => {
    payload[key] = form[key]
    return payload
  }, {})
}
async function loadConfig() {
  loadingConfig.value = true
  error.value = ''
  try {
    const response = unwrap(await pluginApi.get(`plugin/Hhanclubrescueseed/config`))
    if (!response?.success) throw new Error(response?.message || '获取配置失败')
    const data = response.data || {}
    const serverConfig = data.config || data
    Object.assign(form, defaults, projectServerConfig(serverConfig))
    if (typeof data.enabled === 'boolean') form.enable = data.enabled
    downloaders.value = data.downloaders || data.all_downloaders || serverConfig.downloaders || []
    savedForm.value = { ...form }
  } catch (err) {
    error.value = err.message || '获取配置失败'
    Object.assign(form, defaults)
    downloaders.value = []
    savedForm.value = { ...form }
    notify('error', error.value)
  } finally {
    loadingConfig.value = false
  }
}
function projectServerConfig(source) {
  return CONFIG_KEYS.reduce((result, key) => {
    if (Object.prototype.hasOwnProperty.call(source || {}, key) && source[key] != null) result[key] = source[key]
    return result
  }, {})
}
async function saveConfig() {
  if (!String(form.downloader || '').trim()) {
    error.value = '请选择下载器'
    notify('warning', error.value)
    return
  }
  loading.value = true
  error.value = ''
  try {
    const payload = projectConfig()
    savedForm.value = { ...form }
    emit('save', JSON.parse(JSON.stringify(payload)))
    notify('success', '配置已保存')
  } catch (err) {
    error.value = err.message || '保存配置失败'
    notify('error', error.value)
  } finally {
    loading.value = false
  }
}
function resetForm() { Object.assign(form, savedForm.value); error.value = '' }
function close() { emit('close') }
onMounted(loadConfig)
</script>

<template>
  <v-card class="plugin-config" :loading="loadingConfig">
    <v-card-item>
      <template #prepend><v-icon color="primary">mdi-shield-check-outline</v-icon></template>
      <v-card-title>憨憨保种区配置</v-card-title>
      <v-card-subtitle>按列表页粗筛、详情页精筛和下载器并发控制保种任务</v-card-subtitle>
      <template #append><v-btn icon="mdi-close" variant="text" aria-label="关闭" @click="close" /></template>
    </v-card-item>
    <v-card-text>
      <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
      <v-form @submit.prevent="saveConfig">
        <section class="config-section">
          <div class="section-heading"><v-icon color="primary">mdi-power</v-icon><div><h3>运行开关</h3><p>控制插件运行，以及是否立即执行一次任务。</p></div></div>
          <v-row dense>
            <v-col cols="12" md="4"><v-switch v-model="form.enable" color="primary" label="启用插件" hint="按获取任务调度自动获取保种种子" persistent-hint /></v-col>
            <v-col cols="12" md="4"><v-switch v-model="form.run_once" color="primary" label="立即运行普通保种" hint="保存后执行一次普通保种任务" persistent-hint /></v-col>
            <v-col cols="12" md="4"><v-switch v-model="form.history_rescue_enabled" color="primary" label="立即运行历史保种" hint="保存后执行一次历史保种任务，UID由站点自动解析" persistent-hint /></v-col>
          </v-row>
        </section>

        <section class="config-section">
          <div class="section-heading"><v-icon color="primary">mdi-tune</v-icon><div><h3>基础配置</h3><p>定义下载器、路径、标签和通知策略。</p></div></div>
          <v-row dense>
            <v-col cols="12" md="4"><v-switch v-model="form.force_resume" color="primary" label="qb 强制作种" hint="仅 qBittorrent 支持" persistent-hint /></v-col>
            <v-col cols="12" md="4"><v-switch v-model="form.enable_notification" color="primary" label="发送通知" hide-details /></v-col>
            <v-col cols="12" md="4"><v-switch v-model="form.notify_on_zero_torrents" color="primary" label="无新种子时也通知" hide-details /></v-col>
          </v-row>
          <v-row dense>
            <v-col cols="12" md="4"><v-select v-model="form.downloader" :items="downloaders" item-title="title" item-value="value" label="全局下载器" placeholder="请选择下载器" :rules="[value => !!value || '请选择下载器']" variant="outlined" density="comfortable" /></v-col>
            <v-col cols="12" md="4"><v-text-field v-model="form.save_path" label="保存路径" placeholder="留空使用下载器默认" variant="outlined" density="comfortable" /></v-col>
            <v-col cols="12" md="4"><v-text-field v-model="form.custom_tag" label="下载标签" hint="本插件管理标签，可用逗号分隔多个标签" persistent-hint variant="outlined" density="comfortable" /></v-col>
          </v-row>
        </section>

        <section class="config-section">
          <div class="section-heading"><v-icon color="primary">mdi-download-box-outline</v-icon><div><h3>获取规则</h3><p>先用列表页粗筛，再按需读取详情页下载者精筛。</p></div></div>
          <v-row dense>
            <v-col cols="12" md="3"><VCronField v-model="form.cron" label="获取任务调度" hint="保种区每天 14:00 更新种子" persistent-hint /></v-col>
            <v-col cols="12" sm="6" md="3"><v-text-field v-model.number="form.max_pages" label="翻页数" type="number" variant="outlined" density="comfortable" /></v-col>
            <v-col cols="12" sm="6" md="3"><v-text-field v-model.number="form.download_limit" label="本轮下载配额" hint="0 = 不限" persistent-hint type="number" variant="outlined" density="comfortable" /></v-col>
            <v-col cols="12" sm="6" md="3"><v-text-field v-model.number="form.max_downloading" label="最大同时下载数" hint="下载器并发上限" persistent-hint type="number" variant="outlined" density="comfortable" /></v-col>
          </v-row>
          <div class="filter-block">
            <div class="filter-label">列表页粗筛</div>
            <v-row dense>
              <v-col cols="12" md="3"><v-text-field v-model="form.seeding_count" label="做种数区间/多档" hint="支持单值、a-b 或逗号分隔多档，如 1-3,5,8-10" persistent-hint variant="outlined" density="comfortable" /></v-col>
              <v-col cols="12" md="3"><v-text-field v-model.number="form.min_downloaders" label="最小下载数" hint="列表页下载数不足时跳过" type="number" variant="outlined" density="comfortable" /></v-col>
              <v-col cols="12" md="3"><v-text-field v-model="form.torrent_size" label="体积区间（GB）" hint="如 1-100，留空不限" variant="outlined" density="comfortable" /></v-col>
              <v-col cols="12" md="3"><v-switch v-model="form.free" color="primary" label="仅下载免费种子" hint="免费属于列表页粗筛条件" persistent-hint /></v-col>
            </v-row>
          </div>
          <div class="filter-block">
            <div class="filter-label">详情页精筛</div>
            <v-row dense>
              <v-col cols="12" md="6"><v-text-field v-model="form.completion_ratio_max" label="详情页下载者完成率上限（%）" placeholder="留空不启用精筛" type="number" hint="留空不启用精筛；每轮详情请求 ≤15 个" persistent-hint variant="outlined" density="comfortable" /></v-col>
              <v-col cols="12" md="6"><v-text-field v-model="form.connect_time_max_hours" label="详情页下载者连接时间上限（小时）" placeholder="留空不启用精筛" type="number" hint="留空不启用精筛；每轮详情请求 ≤15 个" persistent-hint variant="outlined" density="comfortable" /></v-col>
            </v-row>
          </div>
        </section>

        <section class="config-section">
          <div class="section-heading monitor-heading"><v-icon color="primary">mdi-radar</v-icon><div><h3>监控与清理</h3><p>达标打标、体积配额清理和卡死清理。</p></div><span class="section-note">默认关闭，只触碰本插件标签</span></div>
          <v-row dense class="monitor-row">
            <v-col cols="12" md="4"><VCronField v-model="form.monitor_cron" label="监控任务调度" hint="留空禁用监控任务；启用自动删除后建议保持足够监控频率（如 */10）以便及时清理" persistent-hint /></v-col>
            <v-col cols="12" md="4"><v-text-field v-model="form.reward_tag" label="达标标签" hint="达标后添加，需与下载标签不同" persistent-hint variant="outlined" density="comfortable" /></v-col>
            <v-col cols="12" md="4"><v-text-field v-model.number="form.reward_hours" label="达标做种时长（小时）" hint="已完成且做种满时长后达标" persistent-hint type="number" variant="outlined" density="comfortable" /></v-col>
          </v-row>
          <div class="danger-block">
            <div class="danger-title"><v-icon color="error">mdi-alert-circle-outline</v-icon><strong>危险操作</strong></div>
            <v-row dense><v-col cols="12" md="6"><v-switch v-model="form.auto_delete_enabled" color="error" label="自动删除种子" hint="总开关：关闭时仅监控和打标" persistent-hint /></v-col><v-col cols="12" md="6"><v-switch v-model="form.delete_files" color="error" label="删种时同时删除文件" hint="关闭则保留磁盘文件" persistent-hint /></v-col></v-row>
            <v-row dense><v-col cols="12" md="6"><v-text-field v-model.number="form.disk_quota_gb" label="保种体积配额（GB）" placeholder="留空 = 不限" hint="留空禁用体积清理" persistent-hint type="number" variant="outlined" density="comfortable" /></v-col><v-col cols="12" md="6"><v-text-field v-model.number="form.stuck_days" label="卡死清理（天）" hint="未完成超 N 天清理；0 = 禁用" persistent-hint type="number" variant="outlined" density="comfortable" /></v-col></v-row>
          </div>
        </section>

        <section class="logic-notes">
          <div><strong>两阶段获取</strong><span>列表页只做免费、做种数、下载数和体积粗筛；命中完成率或连接时间任一详情条件时，再请求 viewpeerlist.php 读取详情页下载者，每轮最多15次。</span></div>
          <div><strong>下载者口径</strong><span>完成率和连接时间均针对详情页下载者，所有启用条件必须严格低于上限；请求失败、坏行或表结构变化按未知处理，不放行下载。</span></div>
          <div><strong>历史任务</strong><span>历史保种任务使用站点自动解析的当前 UID，保持独立历史页流程，不纳入普通任务的详情页精筛。</span></div>
        </section>
        <div class="actions"><v-btn variant="text" @click="resetForm">重置</v-btn><v-btn color="primary" type="submit" :loading="loading">保存配置</v-btn></div>
      </v-form>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.plugin-config { max-width: 1100px; margin: 0 auto; }
.config-section { padding: 18px 0 10px; border-bottom: 1px solid rgba(var(--v-theme-on-surface), .12); }
.section-heading { display: flex; gap: 12px; align-items: flex-start; flex-wrap: wrap; margin-bottom: 14px; }
.section-heading h3 { margin: 0; font-size: 1.05rem; }
.section-heading p { margin: 3px 0 0; color: rgba(var(--v-theme-on-surface), .6); font-size: .88rem; }
.section-note { margin-left: auto; color: rgba(var(--v-theme-error), .8); font-size: .85rem; }
.filter-block { padding: 8px 0 0; margin: 14px 0; }
.filter-label { margin-bottom: 10px; color: rgb(var(--v-theme-primary)); font-weight: 600; }
.danger-block { padding: 12px 14px 2px; border: 1px solid rgba(var(--v-theme-error), .35); border-radius: 8px; background: rgba(var(--v-theme-error), .06); }
.danger-title { display: flex; gap: 8px; align-items: center; color: rgb(var(--v-theme-error)); }
.logic-notes { display: grid; gap: 10px; margin-top: 18px; padding: 14px; border-radius: 8px; background: rgba(var(--v-theme-on-surface), .04); color: rgba(var(--v-theme-on-surface), .72); font-size: .9rem; line-height: 1.65; }
.logic-notes div { display: grid; grid-template-columns: 90px 1fr; gap: 8px; }
.logic-notes strong { color: rgb(var(--v-theme-primary)); }
.actions { display: flex; justify-content: flex-end; gap: 10px; padding-top: 20px; }
@media (max-width: 600px) { .section-note { margin-left: 0; } .logic-notes div { grid-template-columns: 1fr; } }
</style>
