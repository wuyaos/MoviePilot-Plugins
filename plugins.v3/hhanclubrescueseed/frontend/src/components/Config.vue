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
  enable: false,
  run_once: false,
  history_rescue_enabled: false,
  cron: '*/20 14-15 * * *',
  monitor_cron: '*/30 * * * *',
  downloader: '',
  save_path: '',
  custom_tag: '',
  user_id: '',
  reward_tag: '',
  reward_hours: 18,
  enable_notification: false,
  notify_on_zero_torrents: false,
  force_resume: false,
  auto_delete_enabled: false,
  delete_files: true,
  disk_quota_gb: '',
  stuck_days: 7,
  min_seeders: 1,
  min_downloaders: 1,
  seeding_count: '1-3',
  torrent_size: '',
  max_torrent_size_gb: '',
  download_limit: 5,
  max_downloading: 3,
  max_pages: 5,
  completion_ratio_max: '',
  connect_time_max_hours: '',
  free: false,
}

const form = reactive({ ...defaults, ...props.initialConfig })
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

async function loadConfig() {
  loadingConfig.value = true
  error.value = ''
  try {
    const response = unwrap(await pluginApi.get(`plugin/${props.pluginId}/config`))
    if (!response?.success) throw new Error(response?.message || '获取配置失败')
    const data = response.data || {}
    const serverConfig = data.config || data
    Object.assign(form, defaults, serverConfig)
    if (typeof data.enabled === 'boolean') form.enable = data.enabled
    downloaders.value = data.downloaders || data.all_downloaders || serverConfig.downloaders || []
    savedForm.value = { ...form }
  } catch (err) {
    error.value = err.message || '获取配置失败'
    notify('error', error.value)
  } finally {
    loadingConfig.value = false
  }
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
    // V3 契约：保存由宿主接 save 事件后 PUT /plugin/{id} 完成（对齐 autoptcheckin），不自 POST
    savedForm.value = { ...form }
    emit('save', JSON.parse(JSON.stringify(form)))
    notify('success', '配置已保存')
  } catch (err) {
    error.value = err.message || '保存配置失败'
    notify('error', error.value)
  } finally {
    loading.value = false
  }
}

function resetForm() {
  Object.assign(form, savedForm.value)
  error.value = ''
}

function close() {
  emit('close')
}

onMounted(loadConfig)
</script>

<template>
  <v-card class="plugin-config" :loading="loadingConfig">
    <v-card-item>
      <template #prepend><v-icon color="primary">mdi-shield-check-outline</v-icon></template>
      <v-card-title>憨憨保种区配置</v-card-title>
      <v-card-subtitle>按列表页预筛和下载器并发控制保种任务</v-card-subtitle>
      <template #append><v-btn icon="mdi-close" variant="text" aria-label="关闭" @click="close" /></template>
    </v-card-item>

    <v-card-text>
      <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
      <v-form @submit.prevent="saveConfig">
        <section class="config-section">
          <div class="section-heading"><v-icon color="primary">mdi-power</v-icon><div><h3>运行开关</h3><p>控制插件是否运行，以及是否立即执行一次任务。</p></div></div>
          <v-row dense>
            <v-col cols="12" md="4"><v-switch v-model="form.enable" color="primary" label="启用插件" hint="按获取任务调度自动获取保种种子" persistent-hint /></v-col>
            <v-col cols="12" md="4"><v-switch v-model="form.run_once" color="primary" label="立即运行普通保种" hint="保存后执行一次普通保种任务" persistent-hint /></v-col>
            <v-col cols="12" md="4"><v-switch v-model="form.history_rescue_enabled" color="primary" label="立即运行历史保种" hint="保存后执行一次下载历史保种任务" persistent-hint /></v-col>
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
            <v-col cols="12" md="4"><v-text-field v-model="form.custom_tag" label="下载标签" hint="本插件管理池标记" persistent-hint variant="outlined" density="comfortable" /></v-col>
            <v-col cols="12" md="4"><v-text-field v-model="form.user_id" label="憨憨站用户 ID" hint="数字 ID，历史保种任务必需" persistent-hint variant="outlined" density="comfortable" /></v-col>
          </v-row>
        </section>

        <section class="config-section">
          <div class="section-heading"><v-icon color="primary">mdi-download-box-outline</v-icon><div><h3>获取规则</h3><p>列表页预筛 → 推送下载器。</p></div></div>
          <v-row dense>
            <v-col cols="12" md="4"><VCronField v-model="form.cron" label="获取任务调度" hint="保种区每天 14:00 更新种子" persistent-hint /></v-col>
            <v-col cols="6" md="2"><v-text-field v-model.number="form.max_pages" label="翻页数" type="number" variant="outlined" density="comfortable" /></v-col>
            <v-col cols="6" md="3"><v-text-field v-model.number="form.download_limit" label="本轮下载配额" hint="0 = 不限" persistent-hint type="number" variant="outlined" density="comfortable" /></v-col>
            <v-col cols="6" md="3"><v-text-field v-model.number="form.max_downloading" label="最大同时下载数" hint="下载器并发上限" persistent-hint type="number" variant="outlined" density="comfortable" /></v-col>
          </v-row>
          <div class="filter-block"><div class="filter-label">列表页粗筛</div><v-row dense>
            <v-col cols="6" md="3"><v-text-field v-model.number="form.min_seeders" label="最小做种数" type="number" variant="outlined" density="comfortable" /></v-col>
            <v-col cols="6" md="3"><v-text-field v-model.number="form.min_downloaders" label="最小下载数" type="number" variant="outlined" density="comfortable" /></v-col>
            <v-col cols="6" md="3"><v-text-field v-model="form.max_torrent_size_gb" label="最大种子体积（GB）" type="number" variant="outlined" density="comfortable" /></v-col>
            <v-col cols="6" md="3"><v-text-field v-model="form.seeding_count" label="做种数区间" hint="如 1-3，逗号分隔多档" persistent-hint variant="outlined" density="comfortable" /></v-col>
            <v-col cols="6" md="3"><v-text-field v-model="form.torrent_size" label="体积区间（GB）" hint="如 1-100，留空不限" persistent-hint variant="outlined" density="comfortable" /></v-col>
          </v-row></div>
          <div class="filter-block"><div class="filter-label">列表页预筛</div><v-row dense>
            <v-col cols="12" md="4"><v-text-field v-model="form.completion_ratio_max" label="完成率上限（%）" placeholder="留空不筛" type="number" variant="outlined" density="comfortable" /></v-col>
            <v-col cols="12" md="4"><v-text-field v-model="form.connect_time_max_hours" label="连接时间上限（小时）" placeholder="留空不筛" type="number" variant="outlined" density="comfortable" /></v-col>
            <v-col cols="12" md="4"><v-text-field v-model="form.free" label="免费种子" hint="当前站点规则：免费种子自动纳入候选" persistent-hint readonly variant="outlined" density="comfortable" /></v-col>
          </v-row></div>
        </section>

        <section class="config-section">
          <div class="section-heading"><v-icon color="primary">mdi-radar</v-icon><div><h3>监控与清理</h3><p>达标打标、体积配额清理和卡死清理。</p></div></div>
          <v-row dense><v-col cols="12" md="6"><VCronField v-model="form.monitor_cron" label="监控任务调度" hint="留空禁用监控任务" persistent-hint /></v-col></v-row>
          <v-row dense>
            <v-col cols="12" md="4"><v-text-field v-model="form.reward_tag" label="达标标签" hint="达标后添加，需与下载标签不同" persistent-hint variant="outlined" density="comfortable" /></v-col>
            <v-col cols="12" md="4"><v-text-field v-model.number="form.reward_hours" label="达标做种时长（小时）" hint="满时长且完成后达标" persistent-hint type="number" variant="outlined" density="comfortable" /></v-col>
            <v-col cols="12" md="4"><v-text-field v-model.number="form.disk_quota_gb" label="保种体积配额（GB）" placeholder="留空 = 不限" hint="留空禁用体积清理" persistent-hint type="number" variant="outlined" density="comfortable" /></v-col>
            <v-col cols="12" md="4"><v-text-field v-model.number="form.stuck_days" label="卡死清理（天）" hint="未完成超 N 天清理；0 = 禁用" persistent-hint type="number" variant="outlined" density="comfortable" /></v-col>
          </v-row>
          <div class="danger-block">
            <div class="danger-title"><v-icon color="error">mdi-alert-circle-outline</v-icon><strong>危险操作</strong><span>默认关闭，只触碰本插件标签</span></div>
            <v-row dense><v-col cols="12" md="6"><v-switch v-model="form.auto_delete_enabled" color="error" label="自动删除种子" hint="总开关：关闭时仅打标" persistent-hint /></v-col><v-col cols="12" md="6"><v-switch v-model="form.delete_files" color="error" label="删种时同时删除文件" hint="关闭则保留磁盘文件" persistent-hint /></v-col></v-row>
          </div>
        </section>

        <section class="logic-notes">
          <div><strong>获取链路</strong><span>按列表顺序抓保种区，依次经过免费、做种数、下载数、完成率、发布时间、体积预筛，通过后推送下载器并打下载标签。</span></div>
          <div><strong>监控链路</strong><span>按调度遍历带下载标签的种子，做种满达标时长且已完成后添加奖励标签；自动删除关闭时仅监控和打标。</span></div>
          <div><strong>删除链路</strong><span>开启自动清理后，按无奖励标签优先、上传量低优先、做种时间短优先清理超出配额的任务，并处理卡死任务。</span></div>
        </section>

        <div class="actions"><v-btn variant="text" @click="resetForm">重置</v-btn><v-btn color="primary" type="submit" :loading="loading">保存配置</v-btn></div>
      </v-form>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.plugin-config { max-width: 1100px; margin: 0 auto; }
.config-section { padding: 18px 0 10px; border-bottom: 1px solid rgba(var(--v-theme-on-surface), .12); }
.section-heading { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 14px; }
.section-heading h3 { margin: 0; font-size: 1.05rem; }
.section-heading p { margin: 3px 0 0; color: rgba(var(--v-theme-on-surface), .6); font-size: .88rem; }
.filter-block { padding: 12px 14px 2px; margin: 10px 0; border: 1px solid rgba(var(--v-theme-on-surface), .12); border-radius: 8px; background: rgba(var(--v-theme-primary), .05); }
.filter-label { margin-bottom: 10px; color: rgb(var(--v-theme-primary)); font-weight: 600; }
.danger-block { padding: 12px 14px 2px; border: 1px solid rgba(var(--v-theme-error), .35); border-radius: 8px; background: rgba(var(--v-theme-error), .06); }
.danger-title { display: flex; gap: 8px; align-items: center; color: rgb(var(--v-theme-error)); }
.danger-title span { font-size: .85rem; font-weight: 400; }
.logic-notes { display: grid; gap: 10px; margin-top: 18px; padding: 14px; border-radius: 8px; background: rgba(var(--v-theme-on-surface), .04); color: rgba(var(--v-theme-on-surface), .72); font-size: .9rem; line-height: 1.65; }
.logic-notes div { display: grid; grid-template-columns: 72px 1fr; gap: 8px; }
.logic-notes strong { color: rgb(var(--v-theme-primary)); }
.actions { display: flex; justify-content: flex-end; gap: 10px; padding-top: 20px; }
</style>
