<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { errorText, getPluginApi } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'MediaServerEnhance' },
  sourcePluginId: { type: String, default: 'MediaServerEnhance' },
})

const emit = defineEmits(['close', 'switch'])

const DEFAULTS = {
  enabled: false,
  notify: false,
  history_limit: 300,
  request_timeout: 30,
  refresh_enabled: false,
  refresh_servers: [],
  refresh_libraries: [],
  refresh_on_transfer: true,
  refresh_debounce_seconds: 30,
  refresh_delay_seconds: 0,
  refresh_recent_enabled: false,
  refresh_recent_count: 20,
  refresh_cron: '',
  audit_enabled: false,
  audit_servers: [],
  audit_libraries: [],
  audit_checks: ['missing_episode', 'duplicate', 'empty_dir', 'orphan_meta', 'missing_image', 'invalid_path'],
  audit_max_items: 20000,
  audit_cron: '',
  covers_enabled: false,
  covers_servers: [],
  covers_libraries: [],
  covers_style: 'poster',
  covers_limit: 20,
  covers_upload: false,
  covers_font: '',
  covers_output_dir: '',
  covers_cron: '',
  capabilities_enabled: false,
  capabilities_servers: [],
  capabilities_watch: ['StrmAssistant', '神医'],
  capabilities_cron: '',
}

const AUDIT_CHECK_ITEMS = [
  { title: '缺集 / 断季', value: 'missing_episode' },
  { title: '重复媒体 / 多版本', value: 'duplicate' },
  { title: '空壳目录', value: 'empty_dir' },
  { title: '孤立旁车文件', value: 'orphan_meta' },
  { title: '缺少封面图', value: 'missing_image' },
  { title: '失效路径', value: 'invalid_path' },
]

const COVER_STYLES = [
  { title: '底部渐变', value: 'poster' },
  { title: '底部色条', value: 'clean' },
  { title: '侧栏竖条', value: 'gradient' },
]

const CRON_HINTS = {
  '': '留空表示不启用定时任务（仍可用页面按钮或远程命令手动触发）',
}

const tabs = [
  { key: 'general', title: '通用' },
  { key: 'refresh', title: '服务器与刷新' },
  { key: 'audit', title: '媒体库体检' },
  { key: 'covers', title: '封面工坊' },
  { key: 'capabilities', title: '服务端能力' },
]

const form = reactive({ ...DEFAULTS })
const activeTab = ref('general')
const serverItems = ref([])
const librariesByServer = ref({})
const serverLoading = ref(false)
const saveMessage = ref('')
const saveError = ref(false)
const savePending = ref(false)

const getApi = (path, options = {}) => getPluginApi(props.api, props.pluginId, path, options)

function listValue(value) {
  if (Array.isArray(value)) return value.filter((item) => item !== null && item !== undefined && item !== '')
  if (value === null || value === undefined || value === '') return []
  return String(value).split(',').map((item) => item.trim()).filter(Boolean)
}

function assignConfig(config) {
  const source = config && typeof config === 'object' ? config : {}
  Object.keys(DEFAULTS).forEach((key) => {
    const fallback = DEFAULTS[key]
    const raw = source[key]
    if (Array.isArray(fallback)) {
      form[key] = listValue(raw === undefined || raw === null ? fallback : raw)
    } else if (typeof fallback === 'boolean') {
      form[key] = raw === undefined || raw === null ? fallback : raw === true || raw === 'true'
    } else if (typeof fallback === 'number') {
      const parsed = Number(raw)
      form[key] = Number.isFinite(parsed) ? parsed : fallback
    } else {
      form[key] = raw === undefined || raw === null ? fallback : String(raw)
    }
  })
}

watch(() => props.initialConfig, (value) => assignConfig(value), { immediate: true, deep: true })

const serverOptions = computed(() => serverItems.value.map((item) => ({
  title: `${item.name}（${item.type || '未知'}）`,
  value: item.name,
})))

const capabilityWatchText = computed({
  get: () => (form.capabilities_watch || []).join(', '),
  set: (value) => {
    form.capabilities_watch = listValue(value)
  },
})
function libraryOptions(servers) {
  const options = []
  ;(servers || []).forEach((server) => {
    const rows = librariesByServer.value[server] || []
    rows.forEach((row) => {
      options.push({
        title: `${server} / ${row.name || row.id}`,
        value: `${server}|${row.id}`,
      })
    })
  })
  return options
}

async function loadServers() {
  serverLoading.value = true
  try {
    const rows = await getApi('servers', { feedback: 'silent' })
    serverItems.value = Array.isArray(rows) ? rows : []
  } catch (error) {
    serverItems.value = []
    saveError.value = true
    saveMessage.value = `读取媒体服务器列表失败：${errorText(error)}`
  } finally {
    serverLoading.value = false
  }
}

async function loadLibraries(servers) {
  const targets = (servers || []).filter((server) => !librariesByServer.value[server])
  if (!targets.length) return
  await Promise.all(targets.map(async (server) => {
    try {
      const rows = await getApi(`libraries/${encodeURIComponent(server)}`, { feedback: 'silent' })
      librariesByServer.value = { ...librariesByServer.value, [server]: Array.isArray(rows) ? rows : [] }
    } catch (error) {
      librariesByServer.value = { ...librariesByServer.value, [server]: [] }
    }
  }))
}

function refreshLibraries(servers) {
  loadLibraries(servers)
}

onMounted(() => {
  loadServers()
})

async function saveConfig() {
  savePending.value = true
  saveError.value = false
  saveMessage.value = ''
  const payload = { ...form }
  Object.keys(payload).forEach((key) => {
    if (Array.isArray(DEFAULTS[key])) payload[key] = listValue(payload[key])
  })
  try {
    const response = await props.api.put(`plugin/${props.pluginId}`, payload)
    if (response?.success === false || response?.data?.success === false) {
      throw new Error(response.message || response.data?.message || '保存配置失败')
    }
    saveMessage.value = '配置已保存，窗口保持打开。刷新插件或页面后生效。'
  } catch (error) {
    saveError.value = true
    saveMessage.value = errorText(error)
  } finally {
    savePending.value = false
  }
}

function close() {
  emit('close')
}
</script>

<template>
  <v-card rounded="lg" variant="flat">
    <v-card-title class="d-flex align-center ga-2 py-3">
      <span class="text-subtitle-1 font-weight-medium">媒体服务器增强 · 配置</span>
      <v-spacer />
      <v-chip v-if="form.enabled" color="success" size="small" variant="tonal">总开关已开</v-chip>
      <v-chip v-else color="grey" size="small" variant="tonal">总开关已关</v-chip>
    </v-card-title>
    <v-tabs v-model="activeTab" density="compact" color="primary">
      <v-tab v-for="tab in tabs" :key="tab.key" :value="tab.key">{{ tab.title }}</v-tab>
    </v-tabs>
    <v-divider />
    <v-card-text class="pt-4" style="max-height: 58vh; overflow-y: auto;">
      <v-window v-model="activeTab">
        <v-window-item value="general">
          <v-row dense>
            <v-col cols="12" md="6">
              <v-switch v-model="form.enabled" color="primary" density="compact" hide-details
                label="启用插件" />
              <div class="text-caption text-medium-emphasis mb-3">
                关闭后全部模块停止工作，定时任务不再注册，事件也不再响应。
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <v-switch v-model="form.notify" color="primary" density="compact" hide-details
                label="推送运行通知" />
              <div class="text-caption text-medium-emphasis mb-3">
                仅在任务失败或部分失败时推送，成功任务不打扰。
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field v-model.number="form.history_limit" type="number" min="20" max="5000"
                density="compact" variant="outlined" label="任务历史保留条数" hide-details />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field v-model.number="form.request_timeout" type="number" min="5" max="300"
                density="compact" variant="outlined" label="请求超时（秒）" hide-details />
            </v-col>
          </v-row>
          <v-alert class="mt-4" density="compact" type="info" variant="tonal">
            媒体服务器连接统一由 MoviePilot 的「媒体服务器」设置提供，本插件不重复维护实例。
          </v-alert>
        </v-window-item>

        <v-window-item value="refresh">
          <v-switch v-model="form.refresh_enabled" color="primary" density="compact" hide-details
            label="启用服务器与刷新模块" />
          <v-row dense class="mt-2">
            <v-col cols="12" md="6">
              <v-select v-model="form.refresh_servers" :items="serverOptions" :loading="serverLoading"
                multiple chips closable-chips clearable density="compact" variant="outlined"
                label="作用服务器（留空=全部）" hide-details @update:model-value="refreshLibraries" />
            </v-col>
            <v-col cols="12" md="6">
              <v-select v-model="form.refresh_libraries" :items="libraryOptions(form.refresh_servers)"
                multiple chips closable-chips clearable density="compact" variant="outlined"
                label="作用媒体库（留空=全部）" hide-details />
            </v-col>
            <v-col cols="12" md="6">
              <v-switch v-model="form.refresh_on_transfer" color="primary" density="compact" hide-details
                label="整理完成后自动刷新" />
              <div class="text-caption text-medium-emphasis">
                命中媒体库路径的入库条目会在防抖窗口结束后合并成一次刷新。
              </div>
            </v-col>
            <v-col cols="6" md="3">
              <v-text-field v-model.number="form.refresh_debounce_seconds" type="number" min="0" max="3600"
                density="compact" variant="outlined" label="防抖窗口（秒）" hide-details />
            </v-col>
            <v-col cols="6" md="3">
              <v-text-field v-model.number="form.refresh_delay_seconds" type="number" min="0" max="86400"
                density="compact" variant="outlined" label="延迟刷新（秒）" hide-details />
            </v-col>
            <v-col cols="12" md="6">
              <v-switch v-model="form.refresh_recent_enabled" color="primary" density="compact" hide-details
                label="定时任务只刷新最近媒体" />
              <div class="text-caption text-medium-emphasis">
                关闭时定时任务执行整库刷新；开启时只刷新最近条目，压力更小。
              </div>
            </v-col>
            <v-col cols="6" md="3">
              <v-text-field v-model.number="form.refresh_recent_count" type="number" min="1" max="200"
                density="compact" variant="outlined" label="最近条目数量" hide-details />
            </v-col>
            <v-col cols="6" md="3">
              <v-text-field v-model="form.refresh_cron" density="compact" variant="outlined"
                label="定时刷新 Cron" placeholder="0 3 * * *" hide-details />
            </v-col>
          </v-row>
          <div class="text-caption text-medium-emphasis mt-1">{{ CRON_HINTS[''] }}</div>
        </v-window-item>

        <v-window-item value="audit">
          <v-switch v-model="form.audit_enabled" color="primary" density="compact" hide-details
            label="启用媒体库体检模块" />
          <v-row dense class="mt-2">
            <v-col cols="12" md="6">
              <v-select v-model="form.audit_servers" :items="serverOptions" :loading="serverLoading"
                multiple chips closable-chips clearable density="compact" variant="outlined"
                label="作用服务器（留空=全部）" hide-details @update:model-value="refreshLibraries" />
            </v-col>
            <v-col cols="12" md="6">
              <v-select v-model="form.audit_libraries" :items="libraryOptions(form.audit_servers)"
                multiple chips closable-chips clearable density="compact" variant="outlined"
                label="作用媒体库（留空=全部）" hide-details />
            </v-col>
            <v-col cols="12">
              <v-select v-model="form.audit_checks" :items="AUDIT_CHECK_ITEMS" multiple chips
                closable-chips density="compact" variant="outlined" label="检查项" hide-details />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field v-model.number="form.audit_max_items" type="number" min="100" max="200000"
                density="compact" variant="outlined" label="单次扫描条目上限" hide-details />
              <div class="text-caption text-medium-emphasis">
                超出上限时报告会标记「已截断」，可在体检页单独重跑某个媒体库。
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field v-model="form.audit_cron" density="compact" variant="outlined"
                label="定时体检 Cron" placeholder="0 4 * * 1" hide-details />
            </v-col>
          </v-row>
          <v-alert class="mt-3" density="compact" type="warning" variant="tonal">
            体检只读：不删除文件、不改数据库，只读取服务器返回的条目与本地目录状态。
          </v-alert>
        </v-window-item>

        <v-window-item value="covers">
          <v-switch v-model="form.covers_enabled" color="primary" density="compact" hide-details
            label="启用封面工坊模块" />
          <v-row dense class="mt-2">
            <v-col cols="12" md="6">
              <v-select v-model="form.covers_servers" :items="serverOptions" :loading="serverLoading"
                multiple chips closable-chips clearable density="compact" variant="outlined"
                label="作用服务器（留空=全部）" hide-details @update:model-value="refreshLibraries" />
            </v-col>
            <v-col cols="12" md="6">
              <v-select v-model="form.covers_libraries" :items="libraryOptions(form.covers_servers)"
                multiple chips closable-chips clearable density="compact" variant="outlined"
                label="作用媒体库（留空=全部）" hide-details />
            </v-col>
            <v-col cols="6" md="3">
              <v-select v-model="form.covers_style" :items="COVER_STYLES" density="compact"
                variant="outlined" label="封面风格" hide-details />
            </v-col>
            <v-col cols="6" md="3">
              <v-text-field v-model.number="form.covers_limit" type="number" min="1" max="500"
                density="compact" variant="outlined" label="单次生成上限" hide-details />
            </v-col>
            <v-col cols="12" md="6">
              <v-switch v-model="form.covers_upload" color="primary" density="compact" hide-details
                label="生成后上传回服务器" />
              <div class="text-caption text-medium-emphasis">
                关闭时只落地到本地目录，可在运行页预览后再决定是否上传。
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field v-model="form.covers_font" density="compact" variant="outlined"
                label="字体文件路径（可选）" placeholder="C:/Windows/Fonts/msyhbd.ttc" hide-details />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field v-model="form.covers_output_dir" density="compact" variant="outlined"
                label="输出目录（可选）" placeholder="留空使用插件数据目录" hide-details />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field v-model="form.covers_cron" density="compact" variant="outlined"
                label="定时生成 Cron" placeholder="0 5 * * *" hide-details />
            </v-col>
          </v-row>
          <v-alert class="mt-3" density="compact" type="info" variant="tonal">
            封面渲染依赖宿主已安装的 Pillow；缺失时模块会跳过渲染并在运行页提示。
          </v-alert>
        </v-window-item>

        <v-window-item value="capabilities">
          <v-switch v-model="form.capabilities_enabled" color="primary" density="compact" hide-details
            label="启用服务端能力模块" />
          <v-row dense class="mt-2">
            <v-col cols="12" md="6">
              <v-select v-model="form.capabilities_servers" :items="serverOptions" :loading="serverLoading"
                multiple chips closable-chips clearable density="compact" variant="outlined"
                label="作用服务器（留空=全部）" hide-details />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field v-model="capabilityWatchText" density="compact" variant="outlined"
                label="关注的插件关键词（逗号分隔）" hint="命中即视为该能力已就绪" persistent-hint />
            </v-col>
            <v-col cols="12" md="6">
              <v-text-field v-model="form.capabilities_cron" density="compact" variant="outlined"
                label="定时探测 Cron" placeholder="0 6 * * *" hide-details />
            </v-col>
          </v-row>
          <v-alert class="mt-3" density="compact" type="info" variant="tonal">
            本节只识别 Emby/Jellyfin 已安装的服务端插件，不代为安装，也不修改其配置。
          </v-alert>
        </v-window-item>
      </v-window>
    </v-card-text>
    <v-divider />
    <v-card-actions class="px-4 py-3">
      <v-btn color="primary" :loading="savePending" @click="saveConfig">保存配置</v-btn>
      <v-btn variant="text" @click="close">关闭</v-btn>
      <v-spacer />
      <span v-if="saveMessage" class="text-caption" :class="saveError ? 'text-error' : 'text-success'">
        {{ saveMessage }}
      </span>
    </v-card-actions>
  </v-card>
</template>
