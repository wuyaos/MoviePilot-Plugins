<script setup>
import { computed, onMounted, ref } from 'vue'
import { errorText, getPluginApi, postPluginJsonApi } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'MediaServerEnhance' },
  sourcePluginId: { type: String, default: 'MediaServerEnhance' },
})

const emit = defineEmits(['close', 'switch'])

const tabs = [
  { key: 'overview', title: '总览' },
  { key: 'refresh', title: '服务器与刷新' },
  { key: 'audit', title: '媒体库体检' },
  { key: 'covers', title: '封面工坊' },
  { key: 'capabilities', title: '服务端能力' },
  { key: 'diagnostics', title: '诊断' },
]

const MODULE_LABELS = {
  refresh: '服务器与刷新',
  audit: '媒体库体检',
  covers: '封面工坊',
  capabilities: '服务端能力',
}

const AUDIT_LABELS = {
  missing_episode: '缺集',
  duplicate: '重复',
  empty_dir: '空目录',
  orphan_meta: '孤立旁车',
  missing_image: '缺封面',
  invalid_path: '路径失效',
}

const activeTab = ref('overview')
const overview = ref(null)
const overviewLoading = ref(false)
const jobs = ref([])
const jobsLoading = ref(false)
const auditReport = ref(null)
const auditLoading = ref(false)
const coverItems = ref([])
const coverMessage = ref('')
const coverLoading = ref(false)
const coverStyle = ref('poster')
const coverLimit = ref(6)
const capabilities = ref(null)
const capabilityLoading = ref(false)
const diagnostics = ref(null)
const diagnosticsLoading = ref(false)
const busy = ref('')
const notice = ref({ show: false, text: '', color: 'success' })

const getApi = (path, options = {}) => getPluginApi(props.api, props.pluginId, path, options)
const postApi = (path, payload = {}, options = {}) => postPluginJsonApi(props.api, props.pluginId, path, payload, options)

function toast(text, color = 'success') {
  notice.value = { show: true, text: String(text || ''), color }
}

function errorToast(error) {
  toast(errorText(error), 'error')
}

const serverRows = computed(() => (overview.value?.servers || []))
const hasPlexServer = computed(() => serverRows.value.some((row) => String(row.type || '').toLowerCase() === 'plex'))
const moduleStates = computed(() => (overview.value?.module_states || {}))
const auditCounts = computed(() => {
  const counts = auditReport.value?.counts || {}
  return Object.keys(AUDIT_LABELS)
    .filter((key) => Number(counts[key] || 0) > 0)
    .map((key) => ({ key, title: AUDIT_LABELS[key], value: Number(counts[key] || 0) }))
})

const serverHeaders = [
  { title: '服务器', key: 'name' },
  { title: '类型', key: 'type', width: 100 },
  { title: '状态', key: 'online', width: 90 },
  { title: '媒体库', key: 'library_count', width: 90 },
  { title: '条目', key: 'item_count', width: 100 },
  { title: '插件', key: 'plugin_count', width: 90 },
]

const jobHeaders = [
  { title: '时间', key: 'started_at', width: 170 },
  { title: '模块', key: 'module', width: 130 },
  { title: '触发器', key: 'trigger', width: 130 },
  { title: '状态', key: 'status', width: 100 },
  { title: '成功/失败/跳过', key: 'counts', width: 140 },
  { title: '说明', key: 'message' },
]

const auditHeaders = [
  { title: '问题', key: 'issue_type', width: 120 },
  { title: '服务器', key: 'server', width: 120 },
  { title: '媒体库', key: 'library_name', width: 140 },
  { title: '标题', key: 'title' },
  { title: '详情', key: 'detail' },
]

const pluginHeaders = [
  { title: '服务端插件', key: 'name' },
  { title: '版本', key: 'version', width: 120 },
  { title: '状态', key: 'status', width: 120 },
]

function moduleLabel(value) {
  return MODULE_LABELS[value] || value || '未知'
}

function statusColor(value) {
  if (value === 'success' || value === 'generated' || value === 'online') return 'success'
  if (value === 'partial' || value === 'running') return 'warning'
  if (value === 'failed' || value === 'error') return 'error'
  return 'grey'
}

function jobCountsText(row) {
  const parts = []
  if (row.success) parts.push(`成功 ${row.success}`)
  if (row.failed) parts.push(`失败 ${row.failed}`)
  if (row.skipped) parts.push(`跳过 ${row.skipped}`)
  return parts.join(' / ') || '-'
}

async function loadOverview() {
  overviewLoading.value = true
  try {
    overview.value = await getApi('overview', { feedback: 'silent' })
  } catch (error) {
    errorToast(error)
  } finally {
    overviewLoading.value = false
  }
}

async function loadJobs(module = '') {
  jobsLoading.value = true
  try {
    const query = module ? `?module=${encodeURIComponent(module)}` : ''
    const result = await getApi(`jobs/1/30${query}`, { feedback: 'silent' })
    jobs.value = Array.isArray(result?.items) ? result.items : []
  } catch (error) {
    jobs.value = []
    errorToast(error)
  } finally {
    jobsLoading.value = false
  }
}

async function loadAudit() {
  auditLoading.value = true
  try {
    auditReport.value = await getApi('audit', { feedback: 'silent' })
  } catch (error) {
    errorToast(error)
  } finally {
    auditLoading.value = false
  }
}

async function loadCapabilities() {
  capabilityLoading.value = true
  try {
    capabilities.value = await getApi('capabilities', { feedback: 'silent' })
  } catch (error) {
    errorToast(error)
  } finally {
    capabilityLoading.value = false
  }
}

async function loadDiagnostics() {
  diagnosticsLoading.value = true
  try {
    diagnostics.value = await getApi('diagnostics', { feedback: 'silent' })
  } catch (error) {
    errorToast(error)
  } finally {
    diagnosticsLoading.value = false
  }
}

async function runRefresh(mode = 'library') {
  busy.value = 'refresh'
  try {
    const result = await postApi('refresh', { mode, recent_count: 20 })
    toast(result?.message || '刷新任务已提交', result?.ok ? 'success' : 'warning')
    await Promise.all([loadOverview(), loadJobs('refresh')])
  } catch (error) {
    errorToast(error)
  } finally {
    busy.value = ''
  }
}

async function flushPending() {
  busy.value = 'pending'
  try {
    const result = await postApi('refresh_pending', {})
    toast(result?.message || '已提交待刷新条目', result?.ok ? 'success' : 'warning')
    await Promise.all([loadOverview(), loadJobs('refresh')])
  } catch (error) {
    errorToast(error)
  } finally {
    busy.value = ''
  }
}

async function runAudit() {
  busy.value = 'audit'
  auditLoading.value = true
  try {
    const result = await postApi('audit_run', {})
    await loadAudit()
    toast(result?.message || '体检已完成', result?.ok ? 'success' : 'warning')
    await Promise.all([loadOverview(), loadJobs('audit')])
  } catch (error) {
    errorToast(error)
  } finally {
    busy.value = ''
    auditLoading.value = false
  }
}

async function previewCovers() {
  coverLoading.value = true
  coverMessage.value = ''
  try {
    const result = await postApi('cover_preview', { style: coverStyle.value, limit: coverLimit.value })
    coverItems.value = Array.isArray(result?.items) ? result.items : []
    coverMessage.value = result?.message || `已生成 ${result?.generated || 0} 张封面（未上传）`
    if (!coverItems.value.length) toast(coverMessage.value, 'warning')
  } catch (error) {
    coverItems.value = []
    errorToast(error)
  } finally {
    coverLoading.value = false
  }
}

async function runCovers() {
  busy.value = 'covers'
  try {
    const result = await postApi('cover_run', { style: coverStyle.value, limit: coverLimit.value, upload: true })
    toast(result?.message || '封面任务已提交', result?.ok ? 'success' : 'warning')
    await Promise.all([loadOverview(), loadJobs('covers')])
  } catch (error) {
    errorToast(error)
  } finally {
    busy.value = ''
  }
}

async function probeCapabilities() {
  capabilityLoading.value = true
  try {
    capabilities.value = await postApi('capabilities_probe', {})
    toast('服务端能力探测已完成')
    await Promise.all([loadOverview(), loadJobs('capabilities')])
  } catch (error) {
    errorToast(error)
  } finally {
    capabilityLoading.value = false
  }
}

async function clearHistory(target, module = '') {
  busy.value = `clear-${target}`
  try {
    const result = await postApi('history_clear', { target, module })
    toast(result?.message || '已清理')
    if (target === 'jobs') await loadJobs('')
    if (target === 'audit') auditReport.value = null
    if (target === 'covers') coverItems.value = []
    if (target === 'capabilities') capabilities.value = null
  } catch (error) {
    errorToast(error)
  } finally {
    busy.value = ''
  }
}

function onTabChange(key) {
  if (key === 'overview') loadOverview()
  if (key === 'refresh') loadJobs('refresh')
  if (key === 'audit' && !auditReport.value) loadAudit()
  if (key === 'capabilities' && !capabilities.value) loadCapabilities()
  if (key === 'diagnostics' && !diagnostics.value) loadDiagnostics()
}

onMounted(() => {
  loadOverview()
  loadJobs('')
})
</script>

<template>
  <v-card rounded="lg" variant="flat">
    <v-card-title class="d-flex align-center ga-2 py-3">
      <span class="text-subtitle-1 font-weight-medium">媒体服务器增强</span>
      <v-chip size="small" variant="tonal" :color="overview?.enabled ? 'success' : 'grey'">
        {{ overview?.enabled ? '运行中' : '已停用' }}
      </v-chip>
      <v-spacer />
      <v-btn size="small" variant="text" :loading="overviewLoading" prepend-icon="mdi-refresh"
        @click="loadOverview">刷新数据</v-btn>
      <v-btn size="small" variant="text" @click="emit('switch')">配置</v-btn>
      <v-btn size="small" variant="text" @click="emit('close')">关闭</v-btn>
    </v-card-title>
    <v-tabs v-model="activeTab" density="compact" color="primary" show-arrows @update:model-value="onTabChange">
      <v-tab v-for="tab in tabs" :key="tab.key" :value="tab.key">{{ tab.title }}</v-tab>
    </v-tabs>
    <v-divider />
    <v-card-text class="pt-4" style="max-height: 62vh; overflow-y: auto;">
      <v-window v-model="activeTab">
        <!-- 总览 -->
        <v-window-item value="overview">
          <v-row dense>
            <v-col cols="6" md="3">
              <v-card variant="tonal" class="pa-3">
                <div class="text-caption">服务器在线</div>
                <div class="text-h5">{{ overview?.online_count || 0 }} / {{ overview?.server_count || 0 }}</div>
              </v-card>
            </v-col>
            <v-col cols="6" md="3">
              <v-card variant="tonal" class="pa-3">
                <div class="text-caption">媒体库</div>
                <div class="text-h5">{{ overview?.library_count || 0 }}</div>
              </v-card>
            </v-col>
            <v-col cols="6" md="3">
              <v-card variant="tonal" class="pa-3">
                <div class="text-caption">今日任务 / 失败</div>
                <div class="text-h5">{{ overview?.today_jobs || 0 }} / {{ overview?.failed_jobs || 0 }}</div>
              </v-card>
            </v-col>
            <v-col cols="6" md="3">
              <v-card variant="tonal" class="pa-3">
                <div class="text-caption">体检问题 / 封面</div>
                <div class="text-h5">{{ overview?.audit_issue_count || 0 }} / {{ overview?.cover_total || 0 }}</div>
              </v-card>
            </v-col>
          </v-row>

          <div class="d-flex flex-wrap ga-2 my-4">
            <v-chip v-for="(enabled, key) in moduleStates" :key="key" size="small" variant="tonal"
              :color="enabled ? 'success' : 'grey'">
              {{ moduleLabel(key) }}{{ enabled ? ' 已启用' : ' 未启用' }}
            </v-chip>
          </div>

          <div class="d-flex flex-wrap ga-2 mb-3">
            <v-btn size="small" color="primary" :loading="busy === 'refresh'" @click="runRefresh('library')">
              立即刷新
            </v-btn>
            <v-btn size="small" variant="tonal" :loading="busy === 'pending'" @click="flushPending">
              提交待刷新
            </v-btn>
            <v-btn size="small" variant="tonal" :loading="busy === 'audit'" @click="runAudit">
              立即体检
            </v-btn>
            <v-btn size="small" variant="tonal" :loading="capabilityLoading" @click="probeCapabilities">
              探测服务端能力
            </v-btn>
          </div>

          <v-table density="compact" hover>
            <thead>
              <tr>
                <th v-for="head in serverHeaders" :key="head.key" :style="{ width: head.width ? `${head.width}px` : undefined }">
                  {{ head.title }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in serverRows" :key="row.name">
                <td>{{ row.name }}</td>
                <td>{{ row.type || '-' }}</td>
                <td>
                  <v-chip size="x-small" variant="tonal" :color="row.online ? 'success' : 'error'">
                    {{ row.online ? '在线' : '离线' }}
                  </v-chip>
                </td>
                <td>{{ row.library_count }}</td>
                <td>{{ row.item_count }}</td>
                <td>{{ row.plugins_supported ? row.plugin_count : '-' }}</td>
              </tr>
              <tr v-if="!serverRows.length">
                <td colspan="6" class="text-center text-medium-emphasis py-4">未发现已配置的媒体服务器</td>
              </tr>
            </tbody>
          </v-table>

          <v-expansion-panels v-if="serverRows.some((row) => row.error)" variant="accordion" class="mt-3">
            <v-expansion-panel title="连接异常详情">
              <v-expansion-panel-text>
                <div v-for="row in serverRows.filter((item) => item.error)" :key="row.name" class="text-body-2 mb-1">
                  <strong>{{ row.name }}</strong>：{{ row.error }}
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-window-item>

        <!-- 服务器与刷新 -->
        <v-window-item value="refresh">
          <div class="d-flex flex-wrap align-center ga-2 mb-3">
            <v-btn size="small" color="primary" :loading="busy === 'refresh'" @click="runRefresh('library')">
              整库刷新
            </v-btn>
            <v-btn size="small" variant="tonal" :loading="busy === 'refresh'" @click="runRefresh('recent')">
              刷新最近条目
            </v-btn>
            <v-btn size="small" variant="tonal" :loading="busy === 'pending'" @click="flushPending">
              提交待刷新
            </v-btn>
            <v-spacer />
            <span class="text-caption text-medium-emphasis">最近刷新：{{ overview?.last_refresh || '暂无' }}</span>
          </div>
          <v-table density="compact" hover>
            <thead>
              <tr>
                <th v-for="head in jobHeaders" :key="head.key" :style="{ width: head.width ? `${head.width}px` : undefined }">
                  {{ head.title }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in jobs" :key="row.job_id">
                <td>{{ row.started_at }}</td>
                <td>{{ moduleLabel(row.module) }}</td>
                <td>{{ row.trigger }}</td>
                <td>
                  <v-chip size="x-small" variant="tonal" :color="statusColor(row.status)">{{ row.status }}</v-chip>
                </td>
                <td>{{ jobCountsText(row) }}</td>
                <td>{{ row.message || '-' }}</td>
              </tr>
              <tr v-if="!jobs.length">
                <td colspan="6" class="text-center text-medium-emphasis py-4">
                  {{ jobsLoading ? '加载中…' : '暂无刷新任务记录' }}
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-window-item>

        <!-- 媒体库体检 -->
        <v-window-item value="audit">
          <div class="d-flex flex-wrap align-center ga-2 mb-3">
            <v-btn size="small" color="primary" :loading="busy === 'audit'" @click="runAudit">运行体检</v-btn>
            <v-btn size="small" variant="tonal" :loading="auditLoading" @click="loadAudit">读取上次报告</v-btn>
            <v-btn size="small" variant="text" :loading="busy === 'clear-audit'" @click="clearHistory('audit')">
              清空报告
            </v-btn>
            <v-spacer />
            <span v-if="auditReport?.time" class="text-caption text-medium-emphasis">
              {{ auditReport.time }} · 扫描 {{ auditReport.scanned_items }} 条目 / {{ auditReport.scanned_libraries }} 库
            </span>
          </div>
          <v-alert v-if="auditReport?.truncated" density="compact" type="warning" variant="tonal" class="mb-3">
            条目数超过单次扫描上限，结果已截断。可提高上限或缩小媒体库范围后重跑。
          </v-alert>
          <div class="d-flex flex-wrap ga-2 mb-3">
            <v-chip v-for="item in auditCounts" :key="item.key" size="small" variant="tonal" color="warning">
              {{ item.title }} {{ item.value }}
            </v-chip>
            <v-chip v-if="auditReport && !auditCounts.length" size="small" variant="tonal" color="success">
              未发现问题
            </v-chip>
          </div>
          <v-table density="compact" hover>
            <thead>
              <tr>
                <th v-for="head in auditHeaders" :key="head.key" :style="{ width: head.width ? `${head.width}px` : undefined }">
                  {{ head.title }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in (auditReport?.issues || [])" :key="`${row.server}-${row.item_id}-${index}`">
                <td>{{ AUDIT_LABELS[row.issue_type] || row.issue_type }}</td>
                <td>{{ row.server }}</td>
                <td>{{ row.library_name || row.library }}</td>
                <td>{{ row.title }}{{ row.year ? ` (${row.year})` : '' }}</td>
                <td class="text-body-2">{{ row.detail }}</td>
              </tr>
              <tr v-if="!(auditReport?.issues || []).length">
                <td colspan="5" class="text-center text-medium-emphasis py-4">
                  {{ auditLoading ? '加载中…' : '暂无体检数据' }}
                </td>
              </tr>
            </tbody>
          </v-table>
          <v-expansion-panels v-if="(auditReport?.errors || []).length" variant="accordion" class="mt-3">
            <v-expansion-panel :title="`扫描错误 ${auditReport.errors.length} 条`">
              <v-expansion-panel-text>
                <div v-for="(item, index) in auditReport.errors" :key="index" class="text-body-2">{{ item }}</div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-window-item>

        <!-- 封面工坊 -->
        <v-window-item value="covers">
          <div class="d-flex flex-wrap align-center ga-2 mb-3">
            <v-select v-model="coverStyle" :items="[
              { title: '底部渐变', value: 'poster' },
              { title: '底部色条', value: 'clean' },
              { title: '侧栏竖条', value: 'gradient' },
            ]" density="compact" variant="outlined" label="风格" hide-details style="max-width: 180px;" />
            <v-text-field v-model.number="coverLimit" type="number" min="1" max="50" density="compact"
              variant="outlined" label="数量" hide-details style="max-width: 120px;" />
            <v-btn size="small" color="primary" :loading="coverLoading" @click="previewCovers">生成预览</v-btn>
            <v-btn size="small" variant="tonal" :loading="busy === 'covers'" @click="runCovers">生成并上传</v-btn>
            <span v-if="hasPlexServer" class="text-caption text-orange-darken-2 mr-2">
              含 Plex 实例：封面上传暂不支持 Plex，会自动跳过
            </span>
            <v-spacer />
            <span v-if="coverMessage" class="text-caption text-medium-emphasis">{{ coverMessage }}</span>
          </div>
          <div v-if="coverItems.length" class="mse-cover-grid">
            <v-card v-for="(item, index) in coverItems" :key="`${item.item_id}-${index}`" variant="outlined" class="pa-2">
              <v-img v-if="item.preview" :src="item.preview" height="180" cover class="rounded" />
              <div v-else class="text-caption text-medium-emphasis d-flex align-center justify-center"
                style="height: 180px;">无预览图</div>
              <div class="text-body-2 mt-2 text-truncate">{{ item.title || item.item_id }}</div>
              <div class="text-caption text-medium-emphasis text-truncate">{{ item.server }} · {{ item.status }}</div>
            </v-card>
          </div>
          <div v-else class="text-center text-medium-emphasis py-8">
            还没有预览。选择风格与数量后点击「生成预览」，预览不会上传到服务器。
          </div>
        </v-window-item>

        <!-- 服务端能力 -->
        <v-window-item value="capabilities">
          <div class="d-flex flex-wrap align-center ga-2 mb-3">
            <v-btn size="small" color="primary" :loading="capabilityLoading" @click="probeCapabilities">
              立即探测
            </v-btn>
            <v-btn size="small" variant="tonal" :loading="capabilityLoading" @click="loadCapabilities">
              读取快照
            </v-btn>
            <v-btn size="small" variant="text" @click="clearHistory('capabilities')">清空快照</v-btn>
            <span v-if="hasPlexServer" class="text-caption text-orange-darken-2 mr-2">
              含 Plex 实例：插件探测仅支持 Emby / Jellyfin
            </span>
            <v-spacer />
            <span class="text-caption text-medium-emphasis">快照时间：{{ capabilities?.time || '暂无' }}</span>
          </div>
          <div v-if="(capabilities?.servers || []).length" class="d-flex flex-column ga-3">
            <v-card v-for="row in capabilities.servers" :key="row.server" variant="outlined" class="pa-3">
              <div class="d-flex align-center ga-2 mb-2">
                <span class="text-body-1 font-weight-medium">{{ row.server }}</span>
                <v-chip size="x-small" variant="tonal" color="grey">{{ row.type || '未知' }}</v-chip>
                <v-chip size="x-small" variant="tonal" :color="row.supported ? 'success' : 'warning'">
                  {{ row.supported ? '支持插件查询' : '不支持' }}
                </v-chip>
                <v-spacer />
                <span class="text-caption text-medium-emphasis">{{ row.checked_at }}</span>
              </div>
              <v-alert v-if="row.error" density="compact" type="error" variant="tonal" class="mb-2">
                {{ row.error }}
              </v-alert>
              <div v-if="(row.watched || []).length" class="d-flex flex-wrap ga-2 mb-2">
                <v-chip v-for="hit in row.watched" :key="hit.name || hit.keyword" size="small" variant="tonal"
                  :color="hit.found ? 'success' : 'grey'">
                  {{ hit.title || hit.name || hit.keyword }}{{ hit.found ? ' 已就绪' : ' 未发现' }}
                </v-chip>
              </div>
              <v-table v-if="(row.plugins || []).length" density="compact">
                <thead>
                  <tr>
                    <th v-for="head in pluginHeaders" :key="head.key" :style="{ width: head.width ? `${head.width}px` : undefined }">
                      {{ head.title }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="plugin in row.plugins" :key="plugin.name">
                    <td>{{ plugin.name }}</td>
                    <td>{{ plugin.version || '-' }}</td>
                    <td>{{ plugin.status || '-' }}</td>
                  </tr>
                </tbody>
              </v-table>
              <div v-else class="text-caption text-medium-emphasis">未读取到服务端插件列表</div>
            </v-card>
          </div>
          <div v-else class="text-center text-medium-emphasis py-8">
            {{ capabilityLoading ? '探测中…' : '还没有服务端能力快照，点击「立即探测」获取。' }}
          </div>
        </v-window-item>

        <!-- 诊断 -->
        <v-window-item value="diagnostics">
          <div class="d-flex flex-wrap align-center ga-2 mb-3">
            <v-btn size="small" color="primary" :loading="diagnosticsLoading" @click="loadDiagnostics">
              重新诊断
            </v-btn>
            <v-btn size="small" variant="text" :loading="busy === 'clear-jobs'" @click="clearHistory('jobs')">
              清空任务历史
            </v-btn>
            <v-btn size="small" variant="text" @click="clearHistory('covers')">清空封面历史</v-btn>
            <v-spacer />
            <span class="text-caption text-medium-emphasis">{{ diagnostics?.time || '' }}</span>
          </div>
          <v-alert v-if="diagnostics && diagnostics.checked === false" density="compact" type="error" variant="tonal"
            class="mb-3">
            诊断执行失败
          </v-alert>
          <v-alert v-for="(item, index) in (diagnostics?.warnings || [])" :key="index" density="compact"
            type="warning" variant="tonal" class="mb-2">
            {{ item }}
          </v-alert>
          <v-alert v-if="diagnostics?.observe_only" density="compact" type="info" variant="tonal" class="mb-2">
            当前处于观察模式：体检等只读检查照常运行，刷新与封面上传被跳过。
          </v-alert>
          <v-row dense>
            <v-col cols="12" md="6">
              <v-card variant="outlined" class="pa-3">
                <div class="text-subtitle-2 mb-2">插件</div>
                <div v-for="(value, key) in (diagnostics?.plugin || {})" :key="key" class="text-body-2 d-flex">
                  <span class="text-medium-emphasis" style="min-width: 120px;">{{ key }}</span>
                  <span>{{ value }}</span>
                </div>
              </v-card>
            </v-col>
            <v-col cols="12" md="6">
              <v-card variant="outlined" class="pa-3">
                <div class="text-subtitle-2 mb-2">配置</div>
                <div v-for="(value, key) in (diagnostics?.config || {})" :key="key" class="text-body-2 d-flex">
                  <span class="text-medium-emphasis" style="min-width: 120px;">{{ key }}</span>
                  <span>{{ value }}</span>
                </div>
              </v-card>
            </v-col>
            <v-col cols="12" md="6">
              <v-card variant="outlined" class="pa-3">
                <div class="text-subtitle-2 mb-2">历史</div>
                <div v-for="(value, key) in (diagnostics?.history || {})" :key="key" class="text-body-2 d-flex">
                  <span class="text-medium-emphasis" style="min-width: 120px;">{{ key }}</span>
                  <span>{{ value }}</span>
                </div>
              </v-card>
            </v-col>
            <v-col cols="12" md="6">
              <v-card variant="outlined" class="pa-3">
                <div class="text-subtitle-2 mb-2">服务器</div>
                <div v-for="(row, index) in (diagnostics?.servers || [])" :key="index" class="text-body-2 mb-2">
                  <div class="font-weight-medium">{{ row.name }}</div>
                  <div v-for="(value, key) in row" :key="key" class="d-flex">
                    <span class="text-medium-emphasis" style="min-width: 96px;">{{ key }}</span>
                    <span class="text-truncate">{{ value }}</span>
                  </div>
                </div>
                <div v-if="!(diagnostics?.servers || []).length" class="text-caption text-medium-emphasis">
                  暂无服务器诊断信息
                </div>
              </v-card>
            </v-col>
            <v-col cols="12" md="6">
              <v-card variant="outlined" class="pa-3">
                <div class="text-subtitle-2 mb-2">功能重叠插件</div>
                <div v-for="(row, index) in (diagnostics?.overlap || [])" :key="index"
                  class="text-body-2 d-flex mb-1">
                  <span style="min-width: 160px;">{{ row.plugin }}</span>
                  <span class="text-medium-emphasis">{{ row.capability }}</span>
                </div>
                <div v-if="!(diagnostics?.overlap || []).length" class="text-caption text-medium-emphasis">
                  没有检测到功能重叠的插件
                </div>
              </v-card>
            </v-col>
            <v-col cols="12" md="6">
              <v-card variant="outlined" class="pa-3">
                <div class="text-subtitle-2 mb-2">最近 Webhook 事件（只记录）</div>
                <div v-for="(row, index) in (diagnostics?.webhooks || []).slice(0, 8)" :key="index"
                  class="text-body-2 mb-1">
                  <span class="text-medium-emphasis mr-2">{{ row.time }}</span>
                  <span class="font-weight-medium">{{ row.channel }}</span>
                  <span class="ml-2">{{ row.event }}</span>
                  <span v-if="row.summary" class="text-truncate text-medium-emphasis ml-2">{{ row.summary }}</span>
                </div>
                <div v-if="!(diagnostics?.webhooks || []).length" class="text-caption text-medium-emphasis">
                  尚未收到媒体服务器 webhook；收到播放/入库事件后会在这里登记
                </div>
              </v-card>
            </v-col>
          </v-row>
        </v-window-item>
      </v-window>
    </v-card-text>
    <v-snackbar v-model="notice.show" :color="notice.color" timeout="4000" location="bottom">
      {{ notice.text }}
    </v-snackbar>
  </v-card>
</template>

<style scoped>
.mse-cover-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
</style>
