<script setup>
import '../styles/dm-tokens.css'
import TableState from './TableState.vue'
import ModuleTable from './ModuleTable.vue'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { getPluginApi, postPluginApi, postPluginJsonApi } from './api'
import DownloaderBadge from './DownloaderBadge.vue'
import ModuleDetailPanel from './ModuleDetailPanel.vue'
import ModuleHeader from './ModuleHeader.vue'
import ConfigSummary from './ConfigSummary.vue'
import RecordDetails from './RecordDetails.vue'
import CompactSelect from './CompactSelect.vue'
import RowActionMenu from './RowActionMenu.vue'
import { MODULE_ICONS } from './module-icons.js'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  pluginId: { type: String, default: 'DownloadManagerLocal' },
  sourcePluginId: { type: String, default: 'DownloadManagerLocal' },
})
const emit = defineEmits(['close', 'switch'])
const getApi = (path, options = {}) => getPluginApi(props.api, props.pluginId, path, options)
const postApi = (path, payload = {}, options = {}) => postPluginApi(props.api, props.pluginId, path, payload, options)
const postJsonApi = (path, payload = {}, options = {}) => postPluginJsonApi(props.api, props.pluginId, path, payload, options)

const activeTab = ref('overview')
const DETAIL_LIMIT_CHOICES = [20, 50, 100, 200]
const detailLimit = ref(20)
const tabs = [
  { key: 'overview', title: '运行总览', icon: MODULE_ICONS.overview },
  { key: 'transfer', title: '转移做种', icon: MODULE_ICONS.transfer },
  { key: 'history', title: '命名历史', icon: MODULE_ICONS.rename },
  { key: 'hr', title: 'H&R 任务', icon: MODULE_ICONS.hr },
  { key: 'autoremove', title: '删种记录', icon: MODULE_ICONS.autoremove },
  { key: 'failclean', title: '失败清理', icon: MODULE_ICONS.failclean },
  { key: 'sitetag', title: '站点标签', icon: MODULE_ICONS.tag },
  { key: 'upload', title: '上传限速', icon: MODULE_ICONS.upload_limit },
  { key: 'diagnostics', title: '运行诊断', icon: MODULE_ICONS.diagnostics },
]
const tabModuleKeys = {
  transfer: 'transfer',
  history: 'rename',
  hr: 'hr',
  autoremove: 'autoremove',
  failclean: 'failclean',
  sitetag: 'tag',
  upload: 'upload_limit',
}
const runtimeFlows = [
  { label: '转移做种', steps: ['下载完成', '延迟等待', '目标转移', '公共链路'] },
  { label: '公共链路', steps: ['命名处理', '站点标签', '做种校验'] },
  { label: '上传限速', steps: ['全局限速', '站点识别', '按需设限', '合计限速', '动态调速', '停用恢复'] },
  { label: '兜底补刀', steps: ['异常命名', '定时补查', '失败计数', '归档恢复'] },
]

const overview = ref(null)
const diagnostics = ref(null)
const downloaderItems = ref([])
const records = ref([])
const archiveRecords = ref([])
// Each block owns its result/error; the existing request revision also guards block retries.
const recordStates = reactive({
  history: { loading: false, loaded: false, error: '', revision: 0 },
  archive: { loading: false, loaded: false, error: '', revision: 0 },
  transfer: { loading: false, loaded: false, error: '', revision: 0 },
  hr: { loading: false, loaded: false, error: '', revision: 0 },
  autoremove: { loading: false, loaded: false, error: '', revision: 0 },
  failclean: { loading: false, loaded: false, error: '', revision: 0 },
})
function recordTableState(key, rows, empty = 'none', busyWithResult = false) {
  const state = recordStates[key]
  const hasResult = state.loaded || rows.length > 0
  return {
    loading: state.loading,
    error: !hasResult ? state.error || false : false,
    refreshFailed: hasResult ? state.error || false : false,
    empty: rows.length ? '' : empty,
  }
}
const total = ref(0)
const archiveTotal = ref(0)
const page = ref(1)
const archivePage = ref(1)
const pageSize = ref(20)
const archivePageSize = ref(20)
const transferPageSize = ref(20)
const historyResultFilter = ref('all')
const transferResultFilter = ref('all')
const loading = ref(false)
const paging = ref(false)
const error = ref('')
const actionMsg = ref('')
const actionOk = ref(false)

const moduleRunning = ref('')
const expandedModules = reactive({})

const hrTasks = ref({ tasks: [], summary: {} })
const hrSkipStats = ref({})
const autoremoveStatus = ref({})
const failcleanStatus = ref({})
const siteTagStatus = ref({})
const transferStatus = ref({})
const transferPage = ref(1)
const renameStatus = ref({})
const autoremovePreview = ref(null)
const moduleConfigSummary = ref(null)

const retryingHash = ref('')
const restoringHash = ref('')
const deletingHash = ref('')

const hrClearing = ref(false)
const hrClearKey = ref('')
const hrClearDialog = ref(false)
const hrClearKind = ref('')
const hrClearTarget = ref(null)
const hrClearDialogDescription = computed(() => ({
  task: '只清除这一条 H&R 记录，不操作下载器任务',
  compliant: '清除所有已满足的 H&R 记录',
  missing: '清除种子已不在下载器的 H&R 记录',
}[hrClearKind.value] || '清除 H&R 记录，不操作下载器任务'))

const transferRunDialog = ref(false)

const cleanupDownloaders = ref([])
const cleanupScan = ref(null)
const cleanupKeep = reactive({})
const cleanupScanning = ref(false)
const cleanupExecuting = ref(false)
const cleanupDialog = ref(false)
const cleanupMessage = ref('')
const cleanupStatus = ref('info')

const OVERVIEW_REFRESH_INTERVAL_MS = 30_000
let overviewRefreshTimer = null
let overviewRefreshPending = false
let pageRequestRevision = 0
let recordRequestRevision = 0
let diagnosticsRequestRevision = 0
let pageDisposed = false

function beginPageRequest() {
  return { revision: ++pageRequestRevision, pluginId: props.pluginId, tab: activeTab.value }
}
function isCurrentPageRequest(request) {
  return !pageDisposed && request.revision === pageRequestRevision
    && request.pluginId === props.pluginId && request.tab === activeTab.value
}
function beginRecordRequest(blocks = ['history', 'archive']) {
  const request = { revision: ++recordRequestRevision, pluginId: props.pluginId, tab: activeTab.value }
  for (const key of blocks) recordStates[key].revision = request.revision
  return request
}
function isCurrentRecordRequest(request, key) {
  return !pageDisposed && request.revision === (key ? recordStates[key].revision : recordRequestRevision)
    && request.pluginId === props.pluginId && request.tab === activeTab.value
}
function beginDiagnosticsRequest() {
  return { revision: ++diagnosticsRequestRevision }
}
function isCurrentDiagnosticsRequest(request) {
  return !pageDisposed && request.revision === diagnosticsRequestRevision
}
function reportLoadError(request, e, fallback, { silent = false } = {}) {
  if (!isCurrentPageRequest(request)) return
  if (silent) {
    console.error(fallback, e)
    return
  }
  error.value = e?.message || fallback
}
function reportRecordLoadError(request, e, fallback, key) {
  if (!isCurrentRecordRequest(request, key)) return
  recordStates[key].error = e?.message || fallback
}

function formatDuration(seconds) {
  const total = Number(seconds || 0)
  if (total <= 0) return '—'
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  if (days > 0) return `${days} 天 ${hours} 小时`
  if (hours > 0) return `${hours} 小时 ${minutes} 分`
  return `${minutes} 分`
}

function formatTimestamp(value) {
  const seconds = Number(value || 0)
  if (!seconds) return '—'
  const date = new Date(seconds * 1000)
  const pad = part => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`
}

function formatUploadRate(value) {
  const rate = Number(value || 0)
  if (rate >= 1024 * 1024) return `${(rate / 1024 / 1024).toFixed(2)} MiB/s`
  return `${(rate / 1024).toFixed(1)} KiB/s`
}

function hrStatusColor(status) {
  return {
    Pending: 'warning',
    'In Progress': 'primary',
    Compliant: 'success',
    'Needs Seeding': 'warning',
    Overdue: 'error',
  }[status] || 'default'
}

const hrStatusFilter = ref('all')
const hrStatusFilterOptions = [
  { title: '全部状态', value: 'all' },
  { title: '待处理', value: 'Pending' },
  { title: '做种中', value: 'In Progress' },
  { title: '已达标', value: 'Compliant' },
  { title: '需做种', value: 'Needs Seeding' },
  { title: '已超期', value: 'Overdue' },
]
const hrSummary = computed(() => hrTasks.value.summary || {})
const hrTaskRows = computed(() => {
  const rows = hrTasks.value.tasks || []
  if (hrStatusFilter.value === 'all') return rows
  return rows.filter(task => task.status === hrStatusFilter.value)
})
const hrSkipRowLabels = {
  transfer_source: '转移源端',
  auto_remove: '自动删种',
  transfer_failure: '整理失败',
  sync_delete: '同步删除',
}
const hrSkipRows = computed(() => Object.entries(hrSkipStats.value || {})
  .map(([key, value]) => ({ label: hrSkipRowLabels[key] || key, value: Number(value || 0) })))
const hrSkipTotal = computed(() => hrSkipRows.value.reduce((sum, row) => sum + row.value, 0))

const autoremoveCandidates = computed(() => autoremoveStatus.value.candidate_list || [])
const autoremoveRows = computed(() => (
  Array.isArray(autoremovePreview.value?.candidate_list)
    ? autoremovePreview.value.candidate_list
    : autoremoveCandidates.value
))
const autoremoveHasRun = computed(() => Number(autoremoveStatus.value.last_run_at || 0) > 0)
const autoremoveEmptyState = computed(() => {
  if (autoremoveRows.value.length) return ''
  if (autoremoveHasRun.value) return 'no-candidates'
  if (recordStates.autoremove.loaded && autoremoveStatus.value.enabled === false) return 'disabled'
  return 'not-scanned'
})
function failcleanMetric(value) {
  return value == null || value === '' ? null : value
}
function hasFailcleanActivity(source, keys) {
  return keys.some(key => Number(source?.[key] || 0) > 0)
}
const failcleanRows = computed(() => {
  const status = failcleanStatus.value || {}
  const rows = []
  if (hasFailcleanActivity(status.event, ['deleted', 'failed', 'skipped'])) {
    rows.push({ source: '来源事件', scanned: null, cleaned: failcleanMetric(status.event.deleted), failed: failcleanMetric(status.event.failed), skipped: failcleanMetric(status.event.skipped) })
  }
  if (hasFailcleanActivity(status.scan, ['scanned', 'cleaned', 'failed', 'skipped'])) {
    rows.push({ source: '上轮巡检', scanned: failcleanMetric(status.scan.scanned), cleaned: failcleanMetric(status.scan.cleaned), failed: failcleanMetric(status.scan.failed), skipped: failcleanMetric(status.scan.skipped) })
  }
  if (hasFailcleanActivity(status.total, ['cleaned', 'failed', 'skipped'])) {
    rows.push({ source: '累计', scanned: null, cleaned: failcleanMetric(status.total.cleaned), failed: failcleanMetric(status.total.failed), skipped: failcleanMetric(status.total.skipped) })
  }
  return rows
})
const failcleanHasRun = computed(() => Number(failcleanStatus.value.last_scan_time || 0) > 0)
const failcleanHasResult = computed(() => failcleanHasRun.value || failcleanRows.value.length > 0)
const failcleanEmptyState = computed(() => {
  if (failcleanRows.value.length) return ''
  if (failcleanHasResult.value) return 'no-candidates'
  if (recordStates.failclean.loaded && failcleanStatus.value.enabled === false) return 'disabled'
  return 'not-scanned'
})
const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize.value)))
const archiveTotalPages = computed(() => Math.max(1, Math.ceil((archiveTotal.value || 0) / archivePageSize.value)))

const diagnosticsCards = computed(() => {
  const items = Array.isArray(diagnostics.value?.checks) ? diagnostics.value.checks : []
  return items.map(item => ({
    ...item,
    statusText: item.status === 'ok' ? '正常' : item.status === 'error' ? '故障' : item.status === 'warn' ? '关注' : '未启用',
    icon: item.status === 'ok'
      ? 'mdi-check-circle-outline'
      : item.status === 'error'
        ? 'mdi-alert-octagon-outline'
        : item.status === 'warn'
          ? 'mdi-alert-circle-outline'
          : 'mdi-minus-circle-outline',
  }))
})
const diagnosticsOkCount = computed(() => diagnosticsCards.value.filter(item => item.status === 'ok').length)
const diagnosticsAttentionCount = computed(() => diagnosticsCards.value.length - diagnosticsOkCount.value)

const uploadLimit = computed(() => overview.value?.upload_limit || {})
const uploadLimitDownloaderRows = computed(() => uploadLimit.value.downloaders || [])
const uploadLimitSiteRows = computed(() => uploadLimit.value.sites || [])
const uploadLimitStatus = computed(() => {
  const status = uploadLimit.value.service_status
  return {
    disabled: { label: '未启用', color: 'default' },
    starting: { label: '启动中', color: 'primary' },
    running: { label: '分配中', color: 'primary' },
    degraded: { label: '部分异常', color: 'warning' },
    error: { label: '状态异常', color: 'error' },
    observe_only: { label: '观察模式', color: 'warning' },
  }[status] || { label: '未启用', color: 'default' }
})

const overviewAttentionCount = computed(() => {
  const uploadErrors = Array.isArray(uploadLimit.value.errors) ? uploadLimit.value.errors.length : 0
  const downloaderErrors = uploadLimitDownloaderRows.value.filter(item => item.error).length
  const uploadStatusErrors = ['degraded', 'error'].includes(uploadLimit.value.service_status) && uploadErrors + downloaderErrors === 0 ? 1 : 0
  return uploadErrors + downloaderErrors + uploadStatusErrors
})
const overviewPendingCount = computed(() => {
  const archive = overview.value?.archive || {}
  return Number(archive.active_failed || 0) + Number(archive.near_archive || 0)
})
const moduleFaultLabels = {
  transfer: '转移做种',
  rename: '种子重命名',
  tag: '站点标签与分类',
  hr: 'H&R 管理',
  autoremove: '自动删种',
  failclean: '失败清理',
  upload_limit: '上传限速',
}
/** 模块运行异常项：模块关闭时后端不产生故障记录，只有启用后运行出错才会出现。 */
const moduleFaultItems = computed(() => {
  const faults = diagnostics.value?.module_faults
  if (!faults || typeof faults !== 'object') return []
  return Object.entries(faults)
    .filter(([module]) => moduleFaultLabels[module])
    .map(([module, reason]) => ({
      icon: 'mdi-alert-octagon-outline',
      color: 'error',
      title: `${moduleFaultLabels[module]}运行异常`,
      detail: String(reason || '未知原因'),
      target: module,
    }))
})
const overviewAttentionItems = computed(() => {
  const archive = overview.value?.archive || {}
  const items = []
  if (archive.active_failed) {
    items.push({ icon: 'mdi-auto-fix', color: 'warning', title: '命名失败待处理', detail: `${archive.active_failed} 条记录连续失败`, target: 'rename' })
  }
  if (archive.near_archive) {
    items.push({ icon: 'mdi-archive-alert-outline', color: 'warning', title: '接近归档阈值', detail: `${archive.near_archive} 条记录需要关注`, target: 'rename' })
  }
  for (const runtimeError of uploadLimit.value.errors || []) {
    items.push({ icon: 'mdi-upload-network-outline', color: 'error', title: '上传限速异常', detail: runtimeError, target: 'upload_limit' })
  }
  for (const downloader of uploadLimitDownloaderRows.value.filter(item => item.error)) {
    items.push({ icon: 'mdi-download-network-outline', color: 'warning', title: `${downloader.id} 状态异常`, detail: downloader.error, target: 'upload_limit' })
  }
  if (['degraded', 'error'].includes(uploadLimit.value.service_status) && !uploadLimit.value.errors?.length && !uploadLimitDownloaderRows.value.some(item => item.error)) {
    items.push({ icon: 'mdi-upload-network-outline', color: 'error', title: '上传限速异常', detail: '服务返回异常状态，请展开上传限速卡详情查看运行数据', target: 'upload_limit' })
  }
  items.push(...moduleFaultItems.value)
  return items
})
const overviewCoreCards = computed(() => {
  const archive = overview.value?.archive || {}
  const uploadErrors = Array.isArray(uploadLimit.value.errors) ? uploadLimit.value.errors.length : 0
  const downloaderErrors = uploadLimitDownloaderRows.value.filter(item => item.error).length
  const uploadStatusErrors = ['degraded', 'error'].includes(uploadLimit.value.service_status) && uploadErrors + downloaderErrors === 0 ? 1 : 0
  return [
    {
      title: '上传限速',
      icon: 'mdi-upload-network-outline',
      color: uploadLimitStatus.value.color,
      value: uploadLimitStatus.value.label,
      desc: `受限 ${uploadLimit.value.managed_torrents || 0} · 宽限 ${uploadLimit.value.grace_torrents || 0}`,
    },
    {
      title: '待关注',
      icon: 'mdi-bell-alert-outline',
      color: overviewPendingCount.value ? 'warning' : 'success',
      value: overviewPendingCount.value,
      desc: `命名 ${Number(archive.active_failed || 0) + Number(archive.near_archive || 0)}`,
    },
    {
      title: '异常数量',
      icon: 'mdi-alert-outline',
      color: overviewAttentionCount.value ? 'error' : 'success',
      value: overviewAttentionCount.value,
      desc: overviewAttentionCount.value
        ? `限速异常 ${uploadErrors + downloaderErrors + uploadStatusErrors}`
        : '当前无服务异常',
    },
  ]
})

const moduleCards = computed(() => {
  const cards = overview.value?.cards || {}
  const archive = overview.value?.archive || {}
  const transfer = cards.transfer || {}
  const seed = cards.seed || {}
  const hr = hrSummary.value
  const auto = autoremoveStatus.value
  const fail = failcleanStatus.value
  const tag = siteTagStatus.value
  const rename = renameStatus.value
  const up = uploadLimit.value
  return [
    {
      key: 'transfer',
      title: '转移做种',
      icon: MODULE_ICONS.transfer,
      color: transfer.active ? 'primary' : (transfer.enabled ? 'warning' : 'default'),
      value: transfer.active ? '运行中' : (transfer.enabled ? '未就绪' : '未启用'),
      desc: `今日成功 ${transfer.today_success || 0} · 今日兜底 ${transfer.today_fallback || 0}`,
      details: [
        { label: '累计成功', value: transfer.success_total || 0 },
        { label: '兜底累计', value: transfer.fallback_success || 0 },
        { label: '兜底扫描', value: transfer.fallback_enabled ? '已启用' : '未启用' },
      ],
      actions: [
        { key: 'transfer-run', label: '执行转移', icon: 'mdi-play-circle-outline', color: 'primary', run: () => { transferRunDialog.value = true } },
      ],
    },
    {
      key: 'seed',
      title: '做种校验',
      icon: 'mdi-check-circle-outline',
      color: seed.autostart ? 'primary' : 'default',
      value: seed.autostart ? '自动开始' : '仅校验',
      desc: seed.skipverify ? '跳过校验' : '按需校验',
      details: [
        { label: '自动开始做种', value: seed.autostart ? '已启用' : '未启用' },
        { label: '跳过校验', value: seed.skipverify ? '已启用' : '未启用' },
      ],
      notes: [{ type: 'info', text: '做种校验按需触发：仅在转移做种或手动补刀添加种子后启动，队列为空后自动停止。' }],
      actions: [],
    },
    {
      key: 'hr',
      title: 'H&R',
      icon: MODULE_ICONS.hr,
      color: hr.overdue ? 'warning' : (hr.enabled ? 'primary' : 'default'),
      value: `${hr.total || 0} 条任务`,
      desc: `达标 ${hr.compliant || 0} · 超期 ${hr.overdue || 0} · 需做种 ${hr.needs_seeding || 0}`,
      detailTitle: '保护跳过计数',
      details: hrSkipRows.value,
      actions: [
        { key: 'hr-check', label: '检查 H&R', icon: 'mdi-clipboard-check-outline', color: 'primary', run: doHrCheck },
        { key: 'hr-scan', label: '发现任务', icon: 'mdi-radar', color: 'primary', run: doHrScan },
      ],
    },
    {
      key: 'autoremove',
      title: '自动删种',
      icon: MODULE_ICONS.autoremove,
      color: auto.enabled ? 'primary' : 'default',
      value: `${auto.deleted || 0} 个已删除`,
      desc: `候选 ${auto.candidates || 0} · 跳过保护 ${auto.skipped_protected || 0} · 失败 ${auto.failed || 0}`,
      details: [
        { label: '执行动作', value: auto.action === 'deletefile' ? '删除任务及文件' : (auto.action === 'delete' ? '删除任务' : '暂停任务') },
        { label: '运行中', value: auto.running ? '是' : '否' },
        { label: '保护闸门', value: auto.guard_unconfirmed ? '无法确认（已保守跳过）' : (auto.guard_enabled ? '已启用' : '未启用') },
      ],
      notes: auto.observe_only
        ? [{ type: 'warning', text: '迁移观察期：仅列出候选，不执行下载器写操作。' }]
        : (auto.config_error ? [{ type: 'error', text: auto.config_error }] : []),
      actions: [
        { key: 'autoremove-preview', label: '预览候选', icon: 'mdi-eye-outline', color: 'primary', run: doAutoremovePreview },
        { key: 'autoremove-run', label: auto.action === 'deletefile' ? '删除任务及文件' : (auto.action === 'delete' ? '删除任务' : '暂停任务'), icon: 'mdi-delete-clock-outline', color: auto.observe_only ? 'warning' : (auto.action === 'delete' || auto.action === 'deletefile' ? 'error' : 'primary'), run: doAutoremoveRun },
      ],
    },
    {
      key: 'failclean',
      title: '失败清理',
      icon: MODULE_ICONS.failclean,
      color: fail.enabled ? 'primary' : 'default',
      value: `巡检清理 ${fail.scan?.cleaned || 0}`,
      desc: `整理失败删源 ${fail.event?.deleted || 0} · 跳过 ${(fail.scan?.skipped || 0) + (fail.event?.skipped || 0)}`,
      details: [
        { label: '即时删源', value: fail.event?.deleted || 0 },
        { label: '巡检清理', value: fail.scan?.cleaned || 0 },
        { label: '失败合计', value: (fail.scan?.failed || 0) + (fail.event?.failed || 0) },
        { label: '累计清理', value: fail.total?.cleaned || 0 },
      ],
      actions: [
        { key: 'failclean-scan', label: '扫描残留', icon: 'mdi-radar', color: 'primary', run: doFailcleanScan },
      ],
    },
    {
      key: 'rename',
      title: '种子重命名',
      icon: MODULE_ICONS.rename,
      color: archive.archived ? 'warning' : 'primary',
      value: `${archive.active_failed || 0} / ${archive.archived || 0}`,
      desc: `待处理 / 已归档 · 阈值 ${archive.threshold || 3} 次`,
      details: [
        { label: '事件改名', value: rename.event?.renamed || 0 },
        { label: '定时补查', value: rename.cron?.renamed || 0 },
        { label: '本次失败', value: rename.failed || 0 },
        { label: '本次跳过', value: rename.skipped || 0 },
      ],
      actions: [
        { key: 'rename-retry', label: '重试', icon: 'mdi-auto-fix', color: 'primary', run: doRetryRenames },
      ],
    },
    {
      key: 'tag',
      title: '站点标签',
      icon: MODULE_ICONS.tag,
      color: tag.completed ? 'primary' : 'default',
      value: `${tag.completed || 0} 个补全`,
      desc: `补全成功 · 跳过 ${tag.skipped || 0}`,
      details: Object.entries(tag.matched || {}).map(([name, value]) => ({ label: name, value })),
      notes: Object.keys(tag.matched || {}).length ? [] : [{ type: 'info', text: '暂无本轮站点标签匹配统计；标签清理工具见下方「标签清理」区块。' }],
      actions: [
        { key: 'tag-complement', label: '补全分类标签', icon: 'mdi-tag-plus-outline', color: 'primary', run: doTagComplement },
      ],
    },
    {
      key: 'upload_limit',
      title: '上传限速',
      icon: MODULE_ICONS.upload_limit,
      color: uploadLimitStatus.value.color,
      value: uploadLimitStatus.value.label,
      desc: `受限 ${up.managed_torrents || 0} · 宽限 ${up.grace_torrents || 0}`,
      actions: [
        { key: 'upload-reallocate', label: '重新分配', icon: 'mdi-call-split', color: 'primary', run: doUploadReallocate },
        { key: 'upload-scan-sites', label: '扫描站点', icon: 'mdi-radar', color: 'primary', run: doUploadScanSites },
        { key: 'upload-clear-rules', label: '清空策略', icon: 'mdi-delete-sweep-outline', color: 'error', run: doUploadClearRules },
      ],
    },
  ]
})

// Header projections only consume existing snapshots; missing counters are not inferred from rows.
const headerMetric = (label, value, tone) => ({
  label, value: value ?? '—',
  tone: value == null ? 'secondary' : tone || (
    ['今日失败', '失败', '失败归档'].includes(label) ? (Number(value) > 0 ? 'error' : 'secondary') :
    ['待重试', '待做种', '跳过'].includes(label) ? (Number(value) > 0 ? 'warning' : 'secondary') :
    ['今日成功', '累计成功', '成功', '清理', '已达标'].includes(label) ? 'success' :
    ['在途', '做种中', '上传中', '当前上传'].includes(label) ? 'primary' : 'secondary')
})
const moduleHeaders = computed(() => {
  const cards = overview.value?.cards || {}
  const config = diagnostics.value?.config || overview.value?.config || {}
  const observing = diagnostics.value?.module_observe_only || {}
  const faults = diagnostics.value?.module_faults || {}
  const transfer = transferStatus.value.summary || {}
  const archive = overview.value?.archive || {}
  const hr = hrSummary.value
  const auto = autoremoveStatus.value
  const fail = failcleanStatus.value
  const rename = renameStatus.value
  const tag = siteTagStatus.value
  const up = uploadLimit.value
  const headers = {
    transfer: {
      enabled: !!(cards.transfer?.enabled ?? config.transfer_enabled),
      badges: [
        headerMetric('在途', transfer.pending),
        headerMetric('今日成功', transfer.today_success ?? cards.transfer?.today_success),
        headerMetric('今日失败', transfer.today_failed),
        headerMetric('累计成功', transfer.success_total ?? cards.transfer?.success_total),
      ],
    },
    rename: {
      enabled: !!(cards.rename?.enabled ?? config.rename_enabled),
      running: !!renameStatus.value.batch_running,
      // today_success/today_failed 由后端 rename_status 直接提供（modules/rename/archive.py::today_stats）。
      badges: [headerMetric('今日成功', rename.today_success), headerMetric('今日失败', rename.today_failed),
        headerMetric('待重试', archive.active_failed), headerMetric('失败归档', archive.archived)],
    },
    tag: {
      enabled: !!config.tag_enabled,
      // round 为本轮补全投影；缺失时不回退到累计 completed/skipped。
      badges: [headerMetric('本轮检查', tag.round?.checked), headerMetric('成功', tag.round?.success),
        headerMetric('无需更新', tag.round?.no_update), headerMetric('失败', tag.round?.failed)],
    },
    hr: {
      enabled: !!hr.enabled,
      badges: [headerMetric('总数', hr.total), headerMetric('待做种', hr.needs_seeding),
        headerMetric('做种中', hr.in_progress), headerMetric('已达标', hr.compliant)],
    },
    autoremove: {
      enabled: !!auto.enabled,
      observing: !!auto.observe_only,
      running: !!auto.running,
      fault: !!auto.config_error,
      // skipped 为后端汇总的保护跳过 + 已消失跳过（modules/autoremove/service.py::get_module_status）。
      badges: [headerMetric('上轮候选', auto.candidates),
        headerMetric('成功', auto.observe_only ? undefined : (auto.action === 'pause' ? auto.paused : auto.deleted)),
        headerMetric('跳过', auto.skipped), headerMetric('失败', auto.failed)],
    },
    failclean: {
      enabled: !!fail.enabled,
      badges: [headerMetric('上轮扫描', fail.scan?.scanned), headerMetric('清理', fail.scan?.cleaned),
        headerMetric('跳过', fail.scan?.skipped), headerMetric('失败', fail.scan?.failed)],
    },
    upload_limit: {
      enabled: !!up.enabled,
      observing: up.service_status === 'observe_only',
      fault: ['degraded', 'error'].includes(up.service_status) || !!up.errors?.length || !!up.state_error,
      badges: [headerMetric('受管种子', up.managed_torrents), headerMetric('上传中', up.uploading_torrents),
        headerMetric('当前上传', up.upload_rate_bps == null ? undefined : formatUploadRate(up.upload_rate_bps)),
        headerMetric('已分配额度', up.allocated_kib == null ? undefined : `${up.allocated_kib} KiB/s`)],
    },
  }
  return Object.fromEntries(moduleCards.value.filter(card => headers[card.key]).map(card => {
    const header = headers[card.key]
    return [card.key, {
      ...header,
      title: card.key === 'hr' ? 'H&R 管理' : card.title,
      icon: card.icon,
      observing: !!(observing[card.key] || header.observing),
      running: !!(header.running || card.actions.some(action => action.key === moduleRunning.value)),
      fault: !!(faults[card.key] || header.fault),
    }]
  }))
})

const moduleGridCards = computed(() => {
  if (activeTab.value === 'overview') return moduleCards.value
  const key = tabModuleKeys[activeTab.value]
  return key ? moduleCards.value.filter(card => card.key === key) : []
})

function focusModule(key) {
  if (!key) return
  expandedModules[key] = true
  void nextTick(() => {
    const element = document.getElementById(`dm-module-${key}`)
    if (element) element.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

async function loadOverview(request, { silent = false } = {}) {
  try {
    const requestOptions = { feedback: 'silent' }
    const [overviewResp, uploadResp] = await Promise.all([
      getApi('overview', requestOptions),
      getApi('upload_limit_status', requestOptions).catch(err => {
        console.error('上传限速状态刷新失败，保留总览快照:', err)
        return null
      }),
    ])
    if (!isCurrentPageRequest(request)) return
    if (overviewResp?.code && overviewResp.code !== 0 && !overviewResp.cards) {
      throw new Error(overviewResp?.msg || '总览加载失败')
    }
    const uploadStatus = uploadResp?.code === 0 || uploadResp?.service_status
      ? uploadResp
      : overviewResp?.upload_limit
    overview.value = { ...(overviewResp || {}), upload_limit: uploadStatus || {} }
  } catch (e) {
    reportLoadError(request, e, '总览加载失败', { silent })
  }
}

async function loadRenameStatus(request) {
  const resp = await getApi('rename_status', { feedback: 'silent' }).catch(() => null)
  if (!isCurrentPageRequest(request) || !resp?.status) return
  renameStatus.value = resp.status
}

async function loadHrStatus(request) {
  if (isCurrentPageRequest(request)) {
    recordStates.hr.loading = true
    recordStates.hr.error = ''
  }
  const [tasksResp, skipResp] = await Promise.all([
    getApi('hr/tasks', { feedback: 'silent' }).catch(error => ({ __error: error })),
    getApi('hr/skip_stats', { feedback: 'silent' }).catch(() => null),
  ])
  if (!isCurrentPageRequest(request)) return
  recordStates.hr.loading = false
  if (!tasksResp || tasksResp.__error) {
    recordStates.hr.error = tasksResp?.__error?.message || 'H&R 任务加载失败'
    return
  }
  recordStates.hr.loaded = true
  recordStates.hr.error = ''
  hrTasks.value = { tasks: tasksResp.tasks || [], summary: tasksResp.summary || {} }
  if (skipResp?.skip_stats) hrSkipStats.value = skipResp.skip_stats
}

async function loadAutoremoveStatus(request) {
  const recordRequest = beginRecordRequest(['autoremove'])
  recordStates.autoremove.loading = true
  recordStates.autoremove.error = ''
  try {
    const resp = await getApi('autoremove_status', { feedback: 'silent' })
    if (!isCurrentPageRequest(request) || !isCurrentRecordRequest(recordRequest, 'autoremove')) return
    if (!resp?.status) throw new Error(resp?.msg || '自动删种记录加载失败')
    autoremoveStatus.value = resp.status
    recordStates.autoremove.loaded = true
  } catch (e) {
    reportRecordLoadError(recordRequest, e, '自动删种记录加载失败', 'autoremove')
  } finally {
    if (isCurrentRecordRequest(recordRequest, 'autoremove')) recordStates.autoremove.loading = false
  }
}

async function loadFailcleanStatus(request) {
  const recordRequest = beginRecordRequest(['failclean'])
  recordStates.failclean.loading = true
  recordStates.failclean.error = ''
  try {
    const resp = await getApi('failclean_status', { feedback: 'silent' })
    if (!isCurrentPageRequest(request) || !isCurrentRecordRequest(recordRequest, 'failclean')) return
    if (!resp?.status) throw new Error(resp?.msg || '失败清理明细加载失败')
    failcleanStatus.value = resp.status
    recordStates.failclean.loaded = true
  } catch (e) {
    reportRecordLoadError(recordRequest, e, '失败清理明细加载失败', 'failclean')
  } finally {
    if (isCurrentRecordRequest(recordRequest, 'failclean')) recordStates.failclean.loading = false
  }
}

async function loadSiteTagStatus(request) {
  const resp = await getApi('tag_status', { feedback: 'silent' }).catch(() => null)
  if (!isCurrentPageRequest(request) || !resp?.status) return
  siteTagStatus.value = resp.status
}

const TRANSFER_PHASE_LABELS = {
  source_pausing: '暂停源种',
  adding: '添加目标',
  target_added: '已添加目标',
  // 旧版本写过的历史状态：后端仅作为「视同完成」读取（modules/transfer/service.py:419），
  // 当前 pipeline 不再产出，但 qnap 的历史记录里可能存在，缺映射会让界面漏出原始英文。
  stopped_after_add: '已添加目标（旧记录）',
  verifying: '做种校验',
  target_ready: '待确认做种',
  completed: '已完成',
  rollback: '回滚中',
  rolled_back: '已回滚',
  failed: '已放弃（超重试上限）',
}
const transferSummary = computed(() => transferStatus.value.summary || {})
const transferTasks = computed(() => transferStatus.value.tasks || [])
const transferPending = computed(() => transferStatus.value.pending || [])
const transferRecords = computed(() => transferStatus.value.records || [])

function transferPhaseText(phase) {
  return TRANSFER_PHASE_LABELS[phase] || phase || '—'
}

function transferPhaseColor(phase) {
  if (phase === 'completed') return 'success'
  if (phase === 'rollback' || phase === 'rolled_back' || phase === 'failed') return 'error'
  if (phase === 'verifying' || phase === 'target_ready') return 'primary'
  if (phase === 'source_pausing') return 'warning'
  if (phase === 'target_added') return 'primary'
  if (phase === 'stopped_after_add') return 'warning'
  return 'default'
}

function transferShortHash(hash) {
  const text = String(hash || '')
  return text ? text.slice(0, 8) : '—'
}


/** 源种子名：转移记录写入端自 3.9.13 起落 `source_name`，旧记录为空串（名称未记录）。 */
function transferSourceName(record) {
  return String((record && record.source_name) || '').trim()
}

/** 转移列表主文案：有名字用名字，没有则明确写「名称未记录」，不拿 hash 冒充名称。 */
function transferPrimaryText(record) {
  return transferSourceName(record) || '名称未记录'
}

/** 转移列表次要文案：短 hash 作辅助；无 hash 时为占位符，完整 hash 仍在 title 提示里。 */
function transferSecondaryText(record) {
  return transferShortHash(record && record.source_hash)
}

/** H&R 任务主标题：种子名优先，缺失时「名称未记录 + 短 hash」，站点另作次级信息。 */
function hrTaskTitle(task) {
  const name = String((task && task.name) || '').trim()
  if (name) return name
  const short = transferShortHash(task && task.torrent_hash)
  return short === '—' ? '名称未记录' : `名称未记录 · ${short}`
}

/** 筛选条件摘要：与配置页任务列表口径一致，无条件时明确显示「不限分类」。 */
function transferFilterText(task) {
  const parts = []
  const category = String(task.include_category || '').trim()
  parts.push(category ? `分类 ${category}` : '不限分类')
  const labels = String(task.include_labels || '').trim()
  if (labels) parts.push(`标签 ${labels}`)
  const excluded = String(task.exclude_labels || '').trim()
  if (excluded) parts.push(`排除 ${excluded}`)
  return parts.join(' · ')
}

/** 设置徽标：只列已启用的高级设置，未启用时前端显示「默认」。 */
function transferSettingBadges(task) {
  const badges = []
  if (task.delete_source) badges.push({ text: '删源种', color: 'error' })
  if (task.delete_duplicate) badges.push({ text: '去重', color: 'warning' })
  if (!task.keep_category) badges.push({ text: '不保留分类', color: 'secondary' })
  if (!task.keep_tag) badges.push({ text: '不保留标签', color: 'secondary' })
  const tag = String(task.transfer_tag || '').trim()
  if (tag) badges.push({ text: `标签 ${tag}`, color: 'default' })
  return badges
}

async function loadTransferStatus(request) {
  const recordRequest = beginRecordRequest(['transfer'])
  recordStates.transfer.loading = true
  recordStates.transfer.error = ''
  try {
    const resp = await getApi(`transfer_status?page=${transferPage.value}&page_size=${transferPageSize.value}&result_filter=${transferResultFilter.value}`, { feedback: 'silent' })
    if (!isCurrentPageRequest(request) || !isCurrentRecordRequest(recordRequest, 'transfer')) return
    if (!resp?.status) throw new Error(resp?.msg || '转移记录加载失败')
    transferStatus.value = resp.status
    transferPage.value = resp.status.page || transferPage.value
    recordStates.transfer.loaded = true
  } catch (e) {
    reportRecordLoadError(recordRequest, e, '转移记录加载失败', 'transfer')
  } finally {
    if (isCurrentRecordRequest(recordRequest, 'transfer')) recordStates.transfer.loading = false
  }
}

function changeTransferPage(page) {
  const total = transferStatus.value.total_pages || 1
  transferPage.value = Math.min(Math.max(1, page), total)
  void refreshActive()
}

async function loadDownloaders(request) {
  const resp = await getApi('downloaders', { feedback: 'silent' }).catch(() => null)
  if (!isCurrentPageRequest(request) || !Array.isArray(resp)) return
  downloaderItems.value = resp
}

async function loadModuleConfigSummary(request) {
  const resp = await getApi('module_config_summary', { feedback: 'silent' }).catch(() => null)
  if (!isCurrentPageRequest(request) || !resp) return
  moduleConfigSummary.value = resp
}

async function loadUploadLimitStatus(request) {
  const resp = await getApi('upload_limit_status', { feedback: 'silent' }).catch(error => {
    console.error('上传限速状态刷新失败，保留总览快照:', error)
    return null
  })
  if (!isCurrentPageRequest(request) || !resp) return
  if (resp?.code === 0 || resp?.service_status) {
    overview.value = { ...(overview.value || {}), upload_limit: resp }
  }
}

async function loadModuleStatuses(request) {
  await Promise.all([
    loadModuleConfigSummary(request),
    loadRenameStatus(request),
    loadHrStatus(request),
    loadAutoremoveStatus(request),
    loadFailcleanStatus(request),
    loadSiteTagStatus(request),
    loadDownloaders(request),
  ])
}

async function loadHistory(request) {
  recordStates.history.loading = true
  recordStates.history.error = ''
  try {
    const resp = await getApi(`rename_history?page=${page.value}&page_size=${pageSize.value}&result_filter=${historyResultFilter.value}`)
    if (!isCurrentRecordRequest(request, 'history')) return
    records.value = Array.isArray(resp?.items) ? resp.items : []
    total.value = resp?.total || 0
    recordStates.history.loaded = true
  } catch (e) {
    reportRecordLoadError(request, e, '命名历史加载失败', 'history')
  } finally {
    if (isCurrentRecordRequest(request, 'history')) { paging.value = false; recordStates.history.loading = false }
  }
}

async function loadArchive(request) {
  recordStates.archive.loading = true
  recordStates.archive.error = ''
  try {
    let resp = await getApi(`rename_archive?page=${archivePage.value}&page_size=${archivePageSize.value}`)
    if (!isCurrentRecordRequest(request, 'archive')) return
    const lastPage = Math.max(1, Math.ceil((resp?.total || 0) / archivePageSize.value))
    if (archivePage.value > lastPage) {
      archivePage.value = lastPage
      resp = await getApi(`rename_archive?page=${archivePage.value}&page_size=${archivePageSize.value}`)
    }
    if (!isCurrentRecordRequest(request, 'archive')) return
    archiveRecords.value = Array.isArray(resp?.items) ? resp.items : []
    archiveTotal.value = resp?.total || 0
    recordStates.archive.loaded = true
  } catch (e) {
    reportRecordLoadError(request, e, '归档加载失败', 'archive')
  } finally {
    if (isCurrentRecordRequest(request, 'archive')) { paging.value = false; recordStates.archive.loading = false }
  }
}

async function loadDiagnostics(request) {
  const diagnosticsRequest = beginDiagnosticsRequest()
  try {
    const resp = await getApi(`diagnostics?detail_limit=${detailLimit.value}`)
    if (!isCurrentPageRequest(request) || !isCurrentDiagnosticsRequest(diagnosticsRequest)) return
    if (resp?.code && resp.code !== 0) {
      error.value = resp?.msg || '诊断失败'
      return
    }
    diagnostics.value = resp
  } catch (e) {
    if (!isCurrentDiagnosticsRequest(diagnosticsRequest)) return
    reportLoadError(request, e, '诊断失败')
  }
}

// 明细条数只影响诊断读取：变化时只刷新诊断，不重载业务状态、不写配置。
watch(detailLimit, () => {
  const request = { revision: pageRequestRevision, pluginId: props.pluginId, tab: activeTab.value }
  void loadDiagnostics(request)
})

/** 数据清理白名单口径与后端 _cleanup_actions 一致；只清插件自身历史/统计。 */
const CLEANUP_TARGETS = {
  rename_archive: {
    label: '重命名归档',
    detail: '连续失败后归档的补刀记录',
    consequence: '归档状态一并删除，对应种子可重新识别与补刀。',
  },
  rename_history: {
    label: '重命名历史',
    detail: '已记录的成功与失败命名记录',
    consequence: '清理后无法再按记录恢复原名或补刀。',
  },
  transfer_stats: {
    label: '转移统计',
    detail: '转移成功计数与跳过计数',
    consequence: '运行总览的转移统计归零，不影响下载器任务。',
  },
  autoremove_state: {
    label: '删种执行记录',
    detail: '自动删种最近一次执行结果',
    consequence: '只清插件记录，下载器中的种子保持不变。',
  },
  failclean_state: {
    label: '失败清理记录',
    detail: '失败清理最近一次执行结果',
    consequence: '只清最近一次执行结果，累计清理统计保留；实际文件与种子保持不变。',
  },
}
const cleanupTargetKey = ref('')
const cleanupConfirmDialog = ref(false)
const cleanupRunning = ref(false)
const cleanupCounts = computed(() => diagnostics.value?.cleanup_data || {})
const cleanupTarget = computed(() => CLEANUP_TARGETS[cleanupTargetKey.value] || null)
const cleanupTargetCount = computed(() => cleanupCounts.value[cleanupTargetKey.value] || 0)


const moduleDetails = computed(() => diagnostics.value?.module_details || {})

function detailValue(value) {
  return value == null || value === '' ? '—' : value
}
function moduleDetail(key) {
  const detail = moduleDetails.value[key]
  const rows = Array.isArray(detail?.rows) ? detail.rows : []
  const items = Array.isArray(detail?.items) ? detail.items : []
  const totalValue = Number(detail?.total)
  const limitValue = Number(detail?.limit)
  const total = Number.isFinite(totalValue) && totalValue >= 0 ? totalValue : items.length
  return {
    rows: rows.map(row => ({ ...row, value: detailValue(row.value) })),
    items,
    error: detail?.error || '',
    total,
    limit: Number.isFinite(limitValue) && limitValue > 0 ? limitValue : detailLimit.value,
    // 旧响应没有 total/truncated：按当前条目数处理，不虚构被截断
    truncated: typeof detail?.truncated === 'boolean' ? detail.truncated : total > items.length,
  }
}

function moduleDetailVisible(key) {
  const detail = moduleDetail(key)
  return Boolean(detail.rows.length || detail.items.length || detail.error)
}
function openCleanupDialog(key) {
  if (!CLEANUP_TARGETS[key]) return
  cleanupTargetKey.value = key
  cleanupConfirmDialog.value = true
}

/**
 * 总览卡「查看记录」落点：只切页签 + 各页签原有的 GET 刷新 + 展开 + 滚动定位，
 * 不触发扫描 / 预览 / 补全 / 重新分配等写操作。
 */
const MODULE_RECORD_VIEWS = {
  transfer: { tab: 'transfer', anchor: '[data-record-block="transfer-tasks"]' },
  rename: { tab: 'history', anchor: '[data-record-block="rename-history"]' },
  hr: { tab: 'hr', anchor: '[data-record-block="hr-tasks"]' },
  autoremove: { tab: 'autoremove', anchor: '[data-record-block="autoremove-preview"]' },
  // 失败清理没有逐条记录，只切页签看最近一次执行结果
  failclean: { tab: 'failclean', anchor: '' },
  tag: { tab: 'sitetag', anchor: '[data-record-block="tag-cleanup"]' },
  upload_limit: { tab: 'upload', anchor: '[data-runtime-section="upload-limit"]' },
}

/** 模块卡上的清理按钮：严格对应后端白名单对象，未列出的模块不显示清理入口。 */
const MODULE_CLEANUP_KEYS = {
  // 重命名历史与归档是两个独立对象，不做「全部清理」
  rename: [
    { key: 'rename_history', label: '清理历史' },
    { key: 'rename_archive', label: '清理归档' },
  ],
  autoremove: [{ key: 'autoremove_state', label: '清理记录' }],
  failclean: [{ key: 'failclean_state', label: '清理记录' }],
}

function moduleRecordView(key) {
  return MODULE_RECORD_VIEWS[key] || null
}

function moduleCleanupButtons(key) {
  return (MODULE_CLEANUP_KEYS[key] || []).map(item => ({ ...item, count: cleanupCounts.value[item.key] || 0 }))
}

function scrollToModuleAnchor(anchor) {
  // 测试 harness 的 document 桩没有 querySelector：没有真实 DOM 时直接跳过定位
  if (!anchor || typeof document === 'undefined' || typeof document.querySelector !== 'function') return
  const node = document.querySelector(anchor)
  if (!node || typeof node.scrollIntoView !== 'function') return
  node.scrollIntoView({ block: 'start', behavior: 'smooth' })
}

async function openModuleRecords(key) {
  const view = moduleRecordView(key)
  if (!view || typeof view.tab !== 'string' || !view.tab) return
  await selectTab(view.tab)
  // 页签切换后目标块才挂载，必须等一次渲染再定位
  await nextTick()
  scrollToModuleAnchor(view.anchor)
}

async function confirmCleanupData() {
  const key = cleanupTargetKey.value
  if (!CLEANUP_TARGETS[key] || cleanupRunning.value) return
  cleanupRunning.value = true
  try {
    const resp = await postJsonApi('cleanup_module_data', { module: key })
    actionOk.value = !!resp && resp.code !== 1
    actionMsg.value = resp?.msg || (actionOk.value ? '清理完成' : '清理失败')
    cleanupConfirmDialog.value = false
    const request = beginPageRequest()
    await loadDiagnostics(request)
    if (key === 'rename_archive' || key === 'rename_history') {
      // 记录变少后可能停在已不存在的空页：先回第一页再刷新
      page.value = 1
      archivePage.value = 1
      const recordRequest = beginRecordRequest()
      await Promise.all([loadHistory(recordRequest), loadArchive(recordRequest)])
    } else if (key === 'transfer_stats') {
      await loadOverview(request, { silent: true })
    } else if (key === 'autoremove_state') {
      // 记录已清空：同步清掉旧预览，避免「上轮候选」残留
      autoremovePreview.value = null
      await loadAutoremoveStatus(request)
    } else if (key === 'failclean_state') {
      await loadFailcleanStatus(request)
    }
  } catch (e) {
    actionOk.value = false
    actionMsg.value = e?.message || '清理失败'
  } finally {
    cleanupRunning.value = false
  }
}

async function loadOverviewTab({ silent = false } = {}) {
  const request = beginPageRequest()
  if (!silent) {
    loading.value = true
    error.value = ''
  }
  try {
    await Promise.all([
      loadOverview(request, { silent }),
      loadModuleStatuses(request),
      // 模块卡「运行明细」依赖诊断数据：首次进入总览就取一次，不必先打开诊断页
      loadDiagnostics(request),
    ])
  } finally {
    if (isCurrentPageRequest(request)) loading.value = false
  }
}

async function loadHistoryTab(request) {
  const recordRequest = beginRecordRequest()
  await Promise.all([
    loadHistory(recordRequest),
    loadArchive(recordRequest),
    loadRenameStatus(request),
  ])
}

async function refreshActive() {
  if (activeTab.value === 'overview') return loadOverviewTab()
  const request = beginPageRequest()
  loading.value = true
  error.value = ''
  try {
    const tasks = []
    if (activeTab.value === 'history') {
      tasks.push(loadHistoryTab(request))
    } else if (activeTab.value === 'hr') {
      tasks.push(loadHrStatus(request))
    } else if (activeTab.value === 'autoremove') {
      tasks.push(loadAutoremoveStatus(request))
    } else if (activeTab.value === 'failclean') {
      tasks.push(loadFailcleanStatus(request))
    } else if (activeTab.value === 'transfer') {
      tasks.push(loadTransferStatus(request))
    } else if (activeTab.value === 'sitetag') {
      tasks.push(loadSiteTagStatus(request), loadDownloaders(request))
    } else if (activeTab.value === 'upload' || activeTab.value === 'diagnostics') {
      tasks.push(loadUploadLimitStatus(request))
    }
    // 模块页签同样展示模块卡与运行明细：每轮刷新固定取一次诊断
    tasks.push(loadModuleConfigSummary(request))
    tasks.push(loadDiagnostics(request))
    await Promise.all(tasks)
  } finally {
    if (isCurrentPageRequest(request)) loading.value = false
  }
}

async function selectTab(key) {
  stopOverviewAutoRefresh()
  activeTab.value = key
  if (tabModuleKeys[key]) expandedModules[tabModuleKeys[key]] = true
  await refreshActive()
  syncOverviewAutoRefresh()
}

async function refreshLive() {
  if (!isOverviewVisible() || overviewRefreshPending || loading.value) return
  overviewRefreshPending = true
  try {
    await loadOverviewTab({ silent: true })
  } finally {
    overviewRefreshPending = false
  }
}

function isOverviewVisible() {
  return activeTab.value === 'overview' && document.visibilityState === 'visible'
}

function stopOverviewAutoRefresh() {
  if (!overviewRefreshTimer) return
  window.clearInterval(overviewRefreshTimer)
  overviewRefreshTimer = null
}

function syncOverviewAutoRefresh({ refresh = false } = {}) {
  stopOverviewAutoRefresh()
  if (!isOverviewVisible()) return
  if (refresh) void refreshLive()
  overviewRefreshTimer = window.setInterval(() => { void refreshLive() }, OVERVIEW_REFRESH_INTERVAL_MS)
}

function handleVisibilityChange() {
  syncOverviewAutoRefresh({ refresh: true })
}

async function runModuleAction(key, handler, fallback) {
  actionMsg.value = ''
  actionOk.value = false
  moduleRunning.value = key
  try {
    const resp = await handler()
    actionOk.value = !!resp && resp.code !== 1
    actionMsg.value = resp?.msg || (actionOk.value ? fallback : `${fallback.replace(/完成$|已触发$/, '')}失败`)
    return resp
  } catch (e) {
    actionOk.value = false
    actionMsg.value = e?.message || `${fallback.replace(/完成$|已触发$/, '')}失败`
    return null
  } finally {
    moduleRunning.value = ''
  }
}

async function doTransferRun() {
  const resp = await runModuleAction('transfer-run', () => postApi('transfer_run', {}), '转移做种已触发')
  if (resp?.code !== 1) await refreshActive()
}

function confirmTransferRun() {
  transferRunDialog.value = false
  void doTransferRun()
}

async function doHrScan() {
  const resp = await runModuleAction('hr-scan', () => postApi('hr_scan', {}), 'H&R 发现完成')
  if (resp?.code !== 1) await refreshActive()
}

async function doHrCheck() {
  const resp = await runModuleAction('hr-check', () => postApi('hr_check', {}), 'H&R 检查完成')
  if (resp?.code !== 1) await refreshActive()
}

function askHrClear(kind, task = null) {
  hrClearTarget.value = task
  hrClearKind.value = kind
  hrClearDialog.value = true
}

async function confirmHrClear() {
  const kind = hrClearKind.value
  const target = hrClearTarget.value
  hrClearDialog.value = false
  if (!kind) return
  actionMsg.value = ''
  actionOk.value = false
  hrClearing.value = true
  hrClearKey.value = target ? `${target.downloader_id}-${target.torrent_hash}` : ''
  try {
    const payload = kind === 'task'
      ? { downloader_id: target?.downloader_id || '', torrent_hash: target?.torrent_hash || '' }
      : {}
    const resp = await postApi(`hr_clear_${kind}`, payload)
    actionOk.value = resp?.code === 0
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '清除完成' : '清除失败')
    if (resp?.code !== 1) await refreshActive()
  } catch (e) {
    actionOk.value = false
    actionMsg.value = e?.message || '清除失败'
  } finally {
    hrClearing.value = false
    hrClearKey.value = ''
    hrClearTarget.value = null
  }
}

async function doAutoremoveRun() {
  const resp = await runModuleAction('autoremove-run', () => postApi('autoremove_run', {}), '自动删种执行完成')
  if (resp?.code !== 1) await refreshActive()
}

async function doAutoremovePreview() {
  const resp = await runModuleAction('autoremove-preview', async () => {
    const previewResp = await postApi('autoremove_preview', {})
    autoremovePreview.value = previewResp?.result || null
    if (previewResp?.code !== 1) {
      const hits = Array.isArray(previewResp?.result?.candidate_list) ? previewResp.result.candidate_list.length : 0
      return { ...previewResp, msg: `预览命中 ${hits} 个候选，未执行任何下载器写操作` }
    }
    return previewResp
  }, '候选预览完成')
  if (resp?.code !== 1) await refreshActive()
}

async function doFailcleanScan() {
  const resp = await runModuleAction('failclean-scan', () => postApi('failclean_scan', {}), '残留巡检完成')
  if (resp?.code !== 1) await refreshActive()
}

async function doRetryRenames() {
  const resp = await runModuleAction('rename-retry', () => postApi('retry_renames', {}), '补刀已在后台开始')
  if (resp?.code !== 1) await refreshActive()
}

async function doRenameScan() {
  const resp = await runModuleAction('rename-scan', () => postApi('rename_scan', {}), '扫描已在后台开始')
  if (resp?.code !== 1) await refreshActive()
}

async function doTagComplement() {
  const resp = await runModuleAction('tag-complement', () => postApi('tag_complement', {}), '站点标签补全完成')
  if (resp?.code !== 1) await refreshActive()
}

async function doUploadReallocate() {
  const resp = await runModuleAction('upload-reallocate', () => postJsonApi('upload_limit_reallocate', {}), '上传额度已重新分配')
  if (resp?.code !== 1) await refreshActive()
}

async function doUploadScanSites() {
  // 只发下载器列表：后端以已持久化站点策略为基底补充扫描到的站点名（见 handlers.api_upload_limit_site_tags）
  const downloaders = [...(uploadLimit.value.selected_downloaders || [])]
  const resp = await runModuleAction('upload-scan-sites', () => postJsonApi('upload_limit_site_tags', { downloaders }), '站点标签扫描完成')
  if (resp?.code !== 1) await refreshActive()
}

async function doUploadClearRules() {
  const resp = await runModuleAction('upload-clear-rules', () => postJsonApi('upload_limit_site_rules_update', { rules: {} }), '站点策略已清空')
  if (resp?.code !== 1) await refreshActive()
}

async function doRecovery(hash, downloader = '') {
  actionMsg.value = ''
  actionOk.value = false
  try {
    const resp = await postApi('recovery_torrent', { hash, downloader })
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '恢复成功' : '恢复失败')
    actionOk.value = resp?.code === 0
    if (resp?.code === 0) await reloadRecords()
  } catch (e) {
    actionOk.value = false
    actionMsg.value = e?.message || '恢复失败'
  }
}

async function doDelete(hash, downloader = '') {
  actionMsg.value = ''
  actionOk.value = false
  try {
    const resp = await postApi('delete_rename_history', { hash, downloader })
    actionOk.value = resp?.code === 0
    actionMsg.value = resp?.msg || '已删除'
    if (resp?.code === 0) await reloadRecords()
  } catch (e) {
    actionOk.value = false
    actionMsg.value = e?.message || '删除失败'
  }
}

async function doRetryRename(hash, downloader = '') {
  if (!hash || retryingHash.value) return
  actionMsg.value = ''
  actionOk.value = false
  retryingHash.value = hash
  try {
    const resp = await postApi('retry_rename', { hash, downloader })
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '补刀完成' : '补刀失败')
    actionOk.value = resp?.code === 0
  } catch (e) {
    actionOk.value = false
    actionMsg.value = e?.message || '补刀失败'
  } finally {
    await reloadRecords()
    retryingHash.value = ''
  }
}

async function restoreArchive(hash, downloader = '') {
  actionMsg.value = ''
  actionOk.value = false
  restoringHash.value = hash
  try {
    const resp = await postApi('restore_rename_archive', { hash, downloader })
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '已恢复' : '恢复失败')
    actionOk.value = resp?.code === 0
    if (resp?.code === 0) await reloadRecords()
  } catch (e) {
    actionOk.value = false
    actionMsg.value = e?.message || '恢复失败'
  } finally {
    restoringHash.value = ''
  }
}

function handleHistoryAction(action, row) {
  if (action === 'retry') return doRetryRename(row.hash, row.downloader)
  if (action === 'recover') return doRecovery(row.hash, row.downloader)
  if (action === 'delete') return doDelete(row.hash, row.downloader)
}
function handleArchiveAction(action, row) {
  if (action === 'retry') return doRetryRename(row.hash, row.downloader)
  if (action === 'restore') return restoreArchive(row.hash, row.downloader)
  if (action === 'delete' && window.confirm('确认删除“' + (row.name || row.hash) + '”的失败归档记录？仅清理记录，不删除种子或数据。')) return deleteArchive(row.hash, row.downloader)
}
async function deleteArchive(hash, downloader = '') {
  actionMsg.value = ''
  actionOk.value = false
  deletingHash.value = hash
  try {
    const resp = await postApi('delete_rename_archive', { hash, downloader })
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '已删除' : '删除失败')
    actionOk.value = resp?.code === 0
    if (resp?.code === 0) await reloadRecords()
  } catch (e) {
    actionOk.value = false
    actionMsg.value = e?.message || '删除失败'
  } finally {
    deletingHash.value = ''
  }
}

async function reloadRecords() {
  const request = beginRecordRequest()
  await Promise.all([loadHistory(request), loadArchive(request)])
}

function prevPage() {
  if (page.value <= 1 || paging.value) return
  paging.value = true
  page.value--
  void loadHistory(beginRecordRequest(['history']))
}
function nextPage() {
  if (page.value >= totalPages.value || paging.value) return
  paging.value = true
  page.value++
  void loadHistory(beginRecordRequest(['history']))
}
function prevArchivePage() {
  if (archivePage.value <= 1 || paging.value) return
  paging.value = true
  archivePage.value--
  void loadArchive(beginRecordRequest(['archive']))
}
function nextArchivePage() {
  if (archivePage.value >= archiveTotalPages.value || paging.value) return
  paging.value = true
  archivePage.value++
  void loadArchive(beginRecordRequest(['archive']))
}

const qbDownloaderItems = computed(() => downloaderItems.value.filter(item => item.type === 'qbittorrent'))
const cleanupGroups = computed(() => cleanupScan.value?.downloaders || [])
const cleanupAutoRemovedCount = computed(() => cleanupScan.value?.auto_removed?.length || 0)
const cleanupRemovals = computed(() => {
  const removals = []
  for (const group of cleanupGroups.value) {
    for (const item of group.tags || []) {
      if (!cleanupKeep[tagSelectionKey(group.name, item.tag)]) {
        removals.push({ downloader: group.name, tag: item.tag, hashes: [...(item.hashes || [])] })
      }
    }
  }
  return removals
})
const cleanupRemovalAssociations = computed(() => cleanupRemovals.value.reduce((sum, item) => sum + item.hashes.length, 0))

function tagSelectionKey(downloader, tag) {
  return `${downloader}\u0000${tag}`
}

function resetCleanupKeep(groups) {
  Object.keys(cleanupKeep).forEach(key => delete cleanupKeep[key])
  for (const group of groups || []) {
    for (const item of group.tags || []) {
      cleanupKeep[tagSelectionKey(group.name, item.tag)] = item.kind !== 'legacy_candidate'
    }
  }
}

function setAllCleanupTags(keep) {
  for (const group of cleanupGroups.value) {
    for (const item of group.tags || []) cleanupKeep[tagSelectionKey(group.name, item.tag)] = keep
  }
}

function cleanupKindMeta(kind) {
  return {
    site: { label: '站点', color: 'primary' },
    managed: { label: '业务', color: 'default' },
    temporary: { label: '临时', color: 'warning' },
    legacy_temporary: { label: '旧临时', color: 'warning' },
    legacy_candidate: { label: '疑似旧临时', color: 'warning' },
    active_temporary: { label: '使用中', color: 'primary' },
    other: { label: '其他', color: 'default' },
  }[kind] || { label: '其他', color: 'default' }
}

async function scanCleanupTags() {
  cleanupMessage.value = ''
  if (!cleanupDownloaders.value.length) {
    cleanupStatus.value = 'warning'
    cleanupMessage.value = '请先选择下载器'
    return
  }
  cleanupScanning.value = true
  try {
    const response = await postJsonApi('tag_cleanup_scan', { downloaders: cleanupDownloaders.value })
    cleanupScan.value = response || null
    resetCleanupKeep(response?.downloaders || [])
    const errorCount = response?.errors?.length || 0
    cleanupStatus.value = response?.code === 0 ? (errorCount ? 'warning' : 'success') : 'error'
    cleanupMessage.value = response?.code === 0
      ? `扫描完成 · 自动清理 ${response?.auto_removed?.length || 0} 个临时标签`
      : (response?.msg || '扫描失败')
  } catch (error) {
    cleanupStatus.value = 'error'
    cleanupMessage.value = error?.message || '扫描失败'
  } finally {
    cleanupScanning.value = false
  }
}

function previewCleanupTags() {
  if (!cleanupRemovals.value.length) {
    cleanupStatus.value = 'warning'
    cleanupMessage.value = '没有需要清理的标签'
    return
  }
  cleanupDialog.value = true
}

async function executeCleanupTags() {
  cleanupExecuting.value = true
  let response = null
  try {
    response = await postJsonApi('tag_cleanup_execute', { removals: cleanupRemovals.value })
  } catch (error) {
    if (error?.code === 2) {
      // 部分失败（success=false 抛错）：按 warning 收尾，弹窗照常关闭并刷新列表
      response = { code: 2, msg: error.message }
    } else {
      cleanupStatus.value = 'error'
      cleanupMessage.value = error?.message || '清理失败'
      cleanupExecuting.value = false
      return
    }
  }
  try {
    cleanupDialog.value = false
    await scanCleanupTags()
    cleanupStatus.value = response?.code === 0 ? 'success' : (response?.code === 2 ? 'warning' : 'error')
    cleanupMessage.value = response?.msg || '清理完成'
  } finally {
    cleanupExecuting.value = false
  }
}

watch(
  () => `${uploadLimit.value.service_status || ''}|${(uploadLimit.value.errors || []).join('|')}|${uploadLimitDownloaderRows.value.filter(item => item.error).map(item => item.id).join('|')}`,
  value => {
    if (value.startsWith('degraded|') || value.startsWith('error|')) expandedModules.upload_limit = true
  },
)

// Page owns projections, filters and paging; shared components stay presentation-only.
const localPages = reactive({ hr: 1, pending: 1, candidates: 1, attention: 1, diagnostics: 1 })
const localSizes = reactive({ hr: 20, pending: 20, candidates: 20, attention: 20, diagnostics: 20 })
function visibleRows(key, rows) {
  const last = Math.max(1, Math.ceil(rows.length / localSizes[key]))
  const current = Math.min(localPages[key], last)
  return rows.slice((current - 1) * localSizes[key], current * localSizes[key])
}
function setLocalSize(key, size) { localSizes[key] = size; localPages[key] = 1 }
const autoRunConfirm = ref(false)
async function runDiagnostics() {
  const request = beginPageRequest()
  loading.value = true
  error.value = ''
  try {
    const result = await getApi(`diagnostics?detail_limit=${detailLimit.value}&run=true`)
    if (!isCurrentPageRequest(request)) return
    if (result?.code && result.code !== 0) throw new Error(result.msg || '诊断失败')
    diagnostics.value = result
  } catch (e) { reportLoadError(request, e, '诊断失败') }
  finally { if (isCurrentPageRequest(request)) loading.value = false }
}
const presenceFilter = ref('all')
const visibleHrRows = computed(() => hrTaskRows.value.filter(task => presenceFilter.value === 'all'
  || (typeof task.deleted === 'boolean' && (presenceFilter.value === 'missing' ? task.deleted : !task.deleted))))
watch([hrStatusFilter, presenceFilter], () => { localPages.hr = 1 })
const rowIdentity = row => `${row.downloader_id || row.source_downloader || ''}:${row.torrent_hash || row.source_hash || row.hash || row.name || row.id}`
const columnsOf = labels => labels.map(([key, label]) => ({ key, label, ...(['name', 'original_name', 'after_name', 'reason', 'detail', 'message'].includes(key) ? { lines: 2 } : {}) }))
const recordColumns = {
  tasks: columnsOf([['name', '名称'], ['from_downloader', '源下载器'], ['to_downloader', '目的下载器'], ['mapping', '数据映射'], ['filters', '筛选条件'], ['settings', '设置']]),
  pending: columnsOf([['name', '种子'], ['route', '源 → 目的'], ['phase', '阶段'], ['wait', '已等待'], ['options', '选项']]),
  transfer: columnsOf([['name', '种子'], ['route', '源 → 目的'], ['phase', '结果'], ['updated', '更新时间']]),
  history: columnsOf([['time', '时间'], ['downloader', '下载器'], ['original_name', '原始名称'], ['after_name', '命名后'], ['success', '结果']]),
  archive: columnsOf([['archived_at', '归档时间'], ['downloader', '下载器'], ['name', '名称'], ['category', '分类'], ['fail_count', '失败次数'], ['reason', '原因']]),
  hr: columnsOf([['name', '种子'], ['downloader_id', '下载器'], ['site', '站点'], ['status', '考核状态'], ['deleted', '存在状态'], ['remain_seconds', '剩余时长'], ['deadline', '截止日期'], ['progress', '做种进度']]),
  candidates: columnsOf([['downloader_id', '下载器'], ['name', '名称'], ['site', '站点'], ['size_text', '体积'], ['ratio', '分享率'], ['seeding_hours', '做种时长'], ['reason', '命中原因']]),
  autoHistory: columnsOf([['time', '执行时间'], ['downloader', '下载器'], ['name', '名称'], ['action', '执行动作'], ['result', '结果'], ['reason', '原因']]),
  failHistory: columnsOf([['time', '时间'], ['downloader', '下载器'], ['name', '名称'], ['type', '清理类型'], ['source', '触发来源'], ['action', '动作'], ['result', '结果']]),
  tagHistory: columnsOf([['time', '时间'], ['downloader', '下载器'], ['name', '种子名称'], ['site', '站点'], ['tags', '标签变更'], ['category', '分类变更'], ['result', '结果']]),
  cleanupHistory: columnsOf([['time', '时间'], ['scope', '清理范围'], ['tags', '清理标签数'], ['success', '成功'], ['failed', '失败'], ['result', '结果']]),
  uploadHistory: columnsOf([['time', '时间'], ['downloader', '下载器'], ['target', '作用对象'], ['action', '动作'], ['before', '调整前'], ['after', '调整后'], ['result', '结果']]),
  sites: columnsOf([['name', '站点'], ['torrent_count', '受管种子'], ['uploading_torrents', '上传中'], ['upload_rate_bps', '当前上传'], ['allocated_kib', '已分配额度'], ['state', '状态']]),
  diagnostics: columnsOf([['name', '检查项'], ['module', '所属模块'], ['stateLabel', '状态'], ['message', '检查结果']]),
  attention: columnsOf([['level', '级别'], ['module', '模块'], ['detail', '问题']]),
}
const unavailableHistory = '当前接口未提供逐条执行历史；此处不以候选、汇总或实时快照代替。'
const currentModule = computed(() => tabModuleKeys[activeTab.value])
const currentHeader = computed(() => moduleHeaders.value[currentModule.value])
const settings = () => emit('switch')
const moduleActions = computed(() => {
  const card = moduleCards.value.find(item => item.key === currentModule.value)
  if (!card) return []
  if (card.key === 'rename') return [{ key: 'rename-scan', label: '扫描重命名', run: doRenameScan }]
  if (card.key === 'autoremove') return card.actions.filter(action => action.key === 'autoremove-preview')
  if (card.key === 'upload_limit') return card.actions.filter(action => action.key === 'upload-reallocate')
  return card.actions
})
const enabledValue = value => typeof value === 'boolean' ? (value ? '开启' : '关闭') : null
const configField = (key, label, value, options = {}) => ({ key, label, value, ...options,
  color: options.color || (['观察模式', '跳过校验'].includes(value) || (['verify', 'guard'].includes(key) && value === '开启') ? 'warning' :
    value === '开启' || value === '正常执行' ? 'primary' : 'default'),
})
const summaryValue = key => {
  const fields = moduleConfigSummary.value?.modules?.[currentModule.value]?.fields
  if (!Array.isArray(fields)) return null
  const item = fields.find(f => f.key === key)
  return item ? item.value : null
}
const summaryFields = computed(() => {
  const config = diagnostics.value?.config || overview.value?.config || {}
  const mode = currentHeader.value?.observing ? '观察模式' : (currentHeader.value?.enabled ? '正常执行' : null)
  const field = configField
  switch (currentModule.value) {
    case 'transfer': return [field('event', '入列触发', summaryValue('event')), field('fallback', '定时兜底', enabledValue(config.transfer_fallback_enabled), { badge: true }), field('start', '自动开始', enabledValue(config.seed_autostart), { badge: true }), field('verify', '跳过校验', enabledValue(config.seed_skipverify), { badge: true }), field('interval', '检查间隔', summaryValue('interval'))]
    case 'rename': return [field('event', '入列触发', summaryValue('event')), field('cron', '定时补查及周期', summaryValue('cron')), field('movie', '电影模板', summaryValue('movie'), { long: true }), field('tv', '剧集模板', summaryValue('tv'), { long: true })]
    case 'hr': return [field('downloaders', '下载器范围', summaryValue('downloaders')), field('sites', '站点范围', summaryValue('sites')), field('rules', '规则来源', summaryValue('rules')), field('interval', '检查周期', summaryValue('interval')), field('guard', '删除保护', enabledValue(hrSummary.value.protection_enabled), { badge: true })]
    case 'autoremove': return [field('mode', '运行模式', mode, { badge: true }), field('action', '执行动作', ({ pause: '暂停任务', delete: '删除任务', deletefile: '删除任务及文件' })[autoremoveStatus.value.action]), field('downloaders', '下载器范围', summaryValue('downloaders')), field('rules', '命中规则', summaryValue('rules')), field('cron', '执行周期', summaryValue('cron')), field('guard', 'H&R保护', enabledValue(autoremoveStatus.value.guard_enabled), { badge: true })]
    case 'failclean': return [field('scope', '清理范围', summaryValue('scope')), field('event', '事件触发', '整理失败事件（固有行为）'), field('cron', '定时巡检及周期', summaryValue('cron')), field('action', '清理动作', summaryValue('action'))]
    case 'tag': return [field('mode', '运行模式', mode, { badge: true }), field('downloaders', '下载器范围', summaryValue('downloaders')), field('site', '站点标签', summaryValue('site')), field('media', '媒体标签', summaryValue('media')), field('category', '下载分类', summaryValue('category')), field('cron', '执行周期', summaryValue('cron'))]
    case 'upload_limit': return [field('mode', '运行模式', uploadLimitStatus.value.label, { badge: true, color: uploadLimitStatus.value.color }), field('downloaders', '下载器范围', summaryValue('downloaders')), field('global', '全局限速', summaryValue('global')), field('sites', '站点限速', summaryValue('sites')), field('dynamic', '动态调速', summaryValue('dynamic')), field('interval', '调整周期', summaryValue('interval'))]
    default: return []
  }
})
const sevenCards = computed(() => moduleCards.value.filter(card => card.key !== 'seed'))
const overviewStats = computed(() => {
  if (!overview.value) return ['已启用模块', '正在执行', '观察模式', '异常模块'].map(label => headerMetric(label))
  const headers = Object.values(moduleHeaders.value)
  return [headerMetric('已启用模块', headers.filter(item => item.enabled).length), headerMetric('正在执行', headers.filter(item => item.running).length), headerMetric('观察模式', headers.filter(item => item.observing).length), headerMetric('异常模块', headers.filter(item => item.fault).length)]
})
const attentionModuleFilter = ref('all')
const attentionRows = computed(() => overviewAttentionItems.value.map((item, index) => ({ ...item, id: index,
  level: item.color === 'error' ? '异常' : '关注', module: moduleHeaders.value[item.target]?.title || item.target || '插件',
})).filter(item => attentionModuleFilter.value === 'all' || item.target === attentionModuleFilter.value))
const moduleFilterItems = computed(() => [{ title: '全部模块', value: 'all' }, ...sevenCards.value.map(card => ({ title: moduleHeaders.value[card.key].title, value: card.key }))])
const diagnosticModuleFilter = ref('all')
const diagnosticStateFilter = ref('all')
const selectedDiagnostic = ref(null)
const diagnosticModule = name => {
  if (/源下载器|目标下载器|种子文件|转移/.test(name)) return 'transfer'
  if (/重命名|补刀|命名/.test(name)) return 'rename'
  if (/H&R/.test(name)) return 'hr'
  if (/自动删种/.test(name)) return 'autoremove'
  if (/失败|同步删除/.test(name)) return 'failclean'
  if (/标签|分类/.test(name)) return 'tag'
  if (/上传|限速/.test(name)) return 'upload_limit'
  return 'plugin'
}
const diagnosticRows = computed(() => (diagnostics.value?.checks || []).map((item, index) => {
  const name = item.label || item.name || '未命名检查'
  const moduleKey = item.target || item.module || diagnosticModule(name)
  const state = item.status === 'off' ? 'off' : (item.state || ({ ok: 'normal', warn: 'attention', error: 'error' })[item.status] || 'pending')
  return { ...item, name, message: item.detail || item.message || '—', id: `${index}:${name}`, moduleKey, module: moduleHeaders.value[moduleKey]?.title || '插件', state,
    stateLabel: ({ normal: '正常', ok: '正常', attention: '需关注', warn: '需关注', error: '异常', pending: '未检查', unchecked: '未检查', off: '不适用' })[state] || '未检查' }
}))
const filteredDiagnosticRows = computed(() => diagnosticRows.value.filter(item => (diagnosticModuleFilter.value === 'all' || item.moduleKey === diagnosticModuleFilter.value)
  && (diagnosticStateFilter.value === 'all' || item.stateLabel === diagnosticStateFilter.value)))
const diagnosticStats = computed(() => ['正常', '需关注', '异常', '未检查'].map(label => headerMetric(label === '正常' ? '正常项' : label === '异常' ? '异常项' : label,
  diagnostics.value?.checked === false ? (label === '未检查' ? '尚未执行诊断' : '—') : diagnosticRows.value.filter(item => item.stateLabel === label).length)))
watch([diagnosticModuleFilter, diagnosticStateFilter], () => { localPages.diagnostics = 1 })
watch(diagnostics, () => { selectedDiagnostic.value = null })
watch(attentionModuleFilter, () => { localPages.attention = 1 })
const uploadDownloaderFilter = ref('all')
const uploadSiteFilter = ref('')
const closedUploadGroups = reactive({})
const uploadGroups = computed(() => {
  const groups = uploadLimitDownloaderRows.value.filter(item => uploadDownloaderFilter.value === 'all' || String(item.id) === uploadDownloaderFilter.value)
    .map(item => ({ ...item, key: String(item.id), title: item.name || item.id, rows: [] }))
  const shared = []
  for (const site of uploadLimitSiteRows.value) {
    if (uploadSiteFilter.value && !String(site.name || '').toLowerCase().includes(uploadSiteFilter.value.toLowerCase())) continue
    const owners = site.downloaders || []
    const group = owners.length === 1 ? groups.find(item => item.key === String(owners[0])) : null
    if (group) group.rows.push(site)
    else if (owners.length !== 1 && (uploadDownloaderFilter.value === 'all' || owners.map(String).includes(uploadDownloaderFilter.value))) shared.push(site)
  }
  if (shared.length) groups.push({ key: 'shared', title: '跨下载器站点汇总（当前接口未拆分）', rows: shared, aggregate: true })
  return groups
})
const cleanupPanel = ref(false)
const cleanupSearch = ref('')
const cleanupTagMatrix = computed(() => {
  const merged = new Map()
  for (const group of cleanupGroups.value) for (const item of group.tags || []) {
    if (!merged.has(item.tag)) merged.set(item.tag, { tag: item.tag, owners: [], keep: true })
    const tag = merged.get(item.tag)
    tag.owners.push(group.name)
    tag.keep = tag.keep && !!cleanupKeep[tagSelectionKey(group.name, item.tag)]
  }
  return [...merged.values()].sort((a, b) => a.tag.localeCompare(b.tag))
})
const filteredCleanupTags = computed(() => cleanupTagMatrix.value.filter(item => item.tag.toLowerCase().includes(cleanupSearch.value.toLowerCase())))
function setMergedTag(tag, keep) { for (const group of cleanupGroups.value) if ((group.tags || []).some(item => item.tag === tag)) cleanupKeep[tagSelectionKey(group.name, tag)] = keep }
async function openTagCleanup() {
  cleanupPanel.value = true
  const request = { revision: pageRequestRevision, pluginId: props.pluginId, tab: activeTab.value }
  await loadDownloaders(request)
  if (isCurrentPageRequest(request)) cleanupDownloaders.value = qbDownloaderItems.value.map(item => item.name)
}
function pageRecordChange(kind, value) {
  if (kind === 'history') { page.value = value; void loadHistory(beginRecordRequest(['history'])) }
  if (kind === 'archive') { archivePage.value = value; void loadArchive(beginRecordRequest(['archive'])) }
  if (kind === 'transfer') { transferPage.value = value; void loadTransferStatus(beginPageRequest()) }
}
function sizeRecordChange(kind, value) {
  if (kind === 'history') pageSize.value = value
  if (kind === 'archive') archivePageSize.value = value
  if (kind === 'transfer') transferPageSize.value = value
  // ModuleTable emits update:page(1) after size changes, issuing one request.
}
function resetHistoryFilter() { historyResultFilter.value = 'all'; pageRecordChange('history', 1) }
function resetTransferFilter() { transferResultFilter.value = 'all'; pageRecordChange('transfer', 1) }
function routeText(row) { return `${row.source_downloader || row.from_downloader || '—'} → ${row.target_downloader || row.to_downloader || '—'}` }
function presentValue(value) { return value == null || value === '' ? '—' : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value) }
onMounted(() => {
  document.addEventListener('visibilitychange', handleVisibilityChange)
  void refreshActive()
  syncOverviewAutoRefresh()
})
onBeforeUnmount(() => {
  pageDisposed = true
  pageRequestRevision++
  stopOverviewAutoRefresh()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<template>
  <div class="dm-page">
    <VToolbar density="comfortable" class="dm-toolbar">
      <VIcon icon="mdi-download" class="ms-3 me-2" color="primary" />
      <div class="dm-title">下载中心</div>
      <VSpacer />
      <VBtn color="primary" size="small" variant="tonal" prepend-icon="mdi-refresh" class="text-none me-2" @click="refreshActive()" :loading="loading">刷新数据</VBtn>
      <VBtn color="primary" size="small" variant="tonal" prepend-icon="mdi-cog-outline" class="text-none" @click="emit('switch')">配置插件</VBtn>
      <VBtn size="small" aria-label="关闭窗口" icon="mdi-close" variant="text" @click="emit('close')" />
    </VToolbar>
    <VDivider />

    <div class="dm-layout">
      <nav class="dm-side">
        <VList density="compact" nav class="dm-side-list py-2">
          <VListItem v-for="tab in tabs" :key="tab.key" :active="activeTab === tab.key" color="primary" rounded="lg" class="dm-side-item" @click="selectTab(tab.key)">
            <template #prepend><VIcon :icon="tab.icon" /></template>
            <VListItemTitle>{{ tab.title }}</VListItemTitle>
          </VListItem>
        </VList>
      </nav>

      <main class="dm-main">
        <VAlert v-if="actionMsg" :type="actionOk ? 'success' : 'error'" variant="tonal" class="mb-3" closable density="compact">{{ actionMsg }}</VAlert>
        <VAlert v-if="error" type="error" variant="tonal" class="mb-3" density="compact">{{ error }}</VAlert>
        <div v-if="loading && !['history', 'transfer', 'hr', 'autoremove', 'failclean'].includes(activeTab)" class="dm-state">
          <VProgressCircular indeterminate color="primary" />
        </div>

        <template v-else>
          <section v-if="activeTab === 'overview'" class="dm-page-stack" data-page="overview">
            <div class="dm-page-heading"><ModuleHeader title="运行总览" :icon="MODULE_ICONS.overview" :show-status="false" enabled /></div>
            <div class="dm-four-stats"><div v-for="stat in overviewStats" :key="stat.label"><span>{{ stat.label }}</span><strong>{{ stat.value }}</strong></div></div>
            <div class="dm-overview-cards">
              <article v-for="card in sevenCards" :key="card.key" class="dm-overview-card">
                <ModuleHeader v-bind="moduleHeaders[card.key]" :badges="moduleHeaders[card.key].badges.slice(0, 2)" />
                <VBtn size="small" variant="text" :aria-label="'打开' + moduleHeaders[card.key].title" icon="mdi-arrow-top-right" @click="openModuleRecords(card.key)" />
                <p class="dm-hint">最近时间：{{ moduleDetail(card.key).time || '当前接口未提供' }}</p>
              </article>
            </div>
            <ModuleTable title="待处理事项" :columns="recordColumns.attention" :rows="visibleRows('attention', attentionRows)" :total="attentionRows.length" :page="localPages.attention" :page-size="localSizes.attention"
              :state="{ empty: attentionModuleFilter === 'all' ? 'none' : 'filtered' }" @update:page="localPages.attention = $event" @update:page-size="setLocalSize('attention', $event)" @reset-filters="attentionModuleFilter = 'all'">
              <template #filters><CompactSelect v-model="attentionModuleFilter" :items="moduleFilterItems" label="模块" class="dm-filter" /></template>
              <template #rowActions="{ row }"><RowActionMenu :label="row.name || row.title || '待处理项'" :actions="[{key:'view',label:'查看',icon:'mdi-open-in-new'}]" @select="openModuleRecords(row.target)" /></template>
            </ModuleTable>
          </section>

          <section v-if="currentHeader" class="dm-page-stack" :data-page="currentModule">
            <div class="dm-page-heading">
              <ModuleHeader v-bind="currentHeader" />
              <div class="dm-page-actions">
                <VBtn v-for="action in moduleActions" :key="action.key" size="small" variant="tonal" :color="action.color || 'primary'" :loading="moduleRunning === action.key" :disabled="moduleRunning !== '' || (action.key === 'rename-scan' && renameStatus.batch_running)" @click="action.run()">{{ action.label }}</VBtn>
                <VBtn color="primary" v-if="currentModule === 'tag'" size="small" variant="tonal" @click="openTagCleanup">标签清理</VBtn>
              </div>
            </div>
            <ConfigSummary :fields="summaryFields" @settings="settings" />

            <template v-if="activeTab === 'transfer'">
              <ModuleTable title="任务配置" data-record-block="transfer-tasks" :columns="recordColumns.tasks" :rows="transferTasks" row-key="name" :pagination="false" :state="recordTableState('transfer', transferTasks)" @retry="refreshActive">
                <template #cell-from_downloader="{ value }"><DownloaderBadge :name="value" /></template>
                <template #cell-to_downloader="{ value }"><DownloaderBadge :name="value" /></template>
                <template #cell-mapping="{ row }"><span>{{ row.from_path || '—' }} → {{ row.to_path || '—' }}</span></template>
                <template #cell-filters="{ row }">{{ transferFilterText(row) }}</template>
                <template #cell-settings="{ row }"><VChip v-for="badge in transferSettingBadges(row)" :key="badge.text" :color="badge.color" size="x-small" variant="tonal">{{ badge.text }}</VChip><span v-if="!transferSettingBadges(row).length">默认</span></template>
                <template #rowActions><RowActionMenu label="转移任务" :actions="[{key:'settings',label:'设置',icon:'mdi-cog-outline'}]" @select="settings" /></template>
              </ModuleTable>
              <ModuleTable title="在途事务" :columns="recordColumns.pending" :rows="visibleRows('pending', transferPending)" :total="transferPending.length" :row-key="rowIdentity" :page="localPages.pending" :page-size="localSizes.pending" :state="recordTableState('transfer', transferPending)" @update:page="localPages.pending = $event" @update:page-size="setLocalSize('pending', $event)" @retry="refreshActive">
                <template #cell-name="{ row }"><span :title="transferSourceName(row)">{{ transferPrimaryText(row) }}</span><div class="dm-hint">{{ transferSecondaryText(row) }}</div></template>
                <template #cell-route="{ row }">{{ routeText(row) }}</template>
                <template #cell-phase="{ row }"><VChip size="x-small" :color="transferPhaseColor(row.phase)" variant="tonal">{{ transferPhaseText(row.phase) }}</VChip></template>
                <template #cell-wait="{ row }">{{ row.waited_minutes != null ? formatDuration(Number(row.waited_minutes) * 60) : '当前接口未提供' }}</template>
                <template #cell-options="{ row }">{{ row.delete_source === true ? '含删源' : row.delete_source === false ? '保留源' : '见详情' }}</template>
                <template #expand="{ row }"><RecordDetails :record="row" /></template>
              </ModuleTable>
              <ModuleTable title="最近记录" data-record-block="transfer-records" data-record-state="transfer" :columns="recordColumns.transfer" :rows="transferRecords" :total="transferStatus.total || 0" :row-key="rowIdentity" :page="transferPage" :page-size="transferPageSize" :state="recordTableState('transfer', transferRecords, transferResultFilter === 'all' ? 'none' : 'filtered')" @retry="refreshActive" @reset-filters="resetTransferFilter" @update:page="pageRecordChange('transfer', $event)" @update:page-size="sizeRecordChange('transfer', $event)">
                <template #filters><CompactSelect v-model="transferResultFilter" :items="[{title:'全部结果',value:'all'},{title:'成功',value:'success'},{title:'失败',value:'failed'},{title:'源端待处理',value:'source_pending'},{title:'回滚',value:'rollback'}]" label="结果" class="dm-filter" @update:model-value="pageRecordChange('transfer', 1)" /></template>
                <template #cell-name="{ row }"><span :title="transferSourceName(row)">{{ transferPrimaryText(row) }}</span><div class="dm-hint">{{ transferSecondaryText(row) }}</div></template>
                <template #cell-route="{ row }">{{ routeText(row) }}</template>
                <template #cell-phase="{ row }"><VChip size="x-small" :color="transferPhaseColor(row.phase)" variant="tonal">{{ transferPhaseText(row.phase) }}</VChip></template>
                <template #cell-updated="{ row }">{{ formatTimestamp(row.updated_at || row.timestamp || row.created_at) }}</template>
                <template #expand="{ row }"><RecordDetails :record="row" /></template>
              </ModuleTable>
            </template>

            <template v-if="activeTab === 'history'">
              <ModuleTable title="执行记录" data-record-block="rename-history" data-record-state="history" :columns="recordColumns.history" :rows="records" :total="total" row-key="hash" :page="page" :page-size="pageSize" :state="recordTableState('history', records, historyResultFilter === 'all' ? 'none' : 'filtered')" :cleanup-blocked="!cleanupCounts.rename_history" cleanup-label="清历史" @cleanup="openCleanupDialog('rename_history')" @retry="loadHistory(beginRecordRequest(['history']))" @reset-filters="resetHistoryFilter" @update:page="pageRecordChange('history', $event)" @update:page-size="sizeRecordChange('history', $event)">
                <template #filters><CompactSelect v-model="historyResultFilter" :items="[{title:'全部结果',value:'all'},{title:'成功',value:'success'},{title:'失败',value:'failed'}]" label="结果" class="dm-filter" @update:model-value="pageRecordChange('history', 1)" /></template>
                <template #toolbar>
                  <VBtn color="primary" size="small" variant="tonal" :loading="renameStatus.batch_running || moduleRunning === 'rename-retry'" :disabled="!!moduleRunning || renameStatus.batch_running" @click="doRetryRenames">重试失败项</VBtn>
                </template>
                <template #cell-downloader="{ row }"><DownloaderBadge :name="row.downloader || row.downloader_id || '未记录'" /></template>
                <template #cell-success="{ row }"><VChip size="x-small" :color="row.success ? 'success' : 'error'" variant="tonal">{{ row.success ? '成功' : '失败' }}</VChip></template>
                <template #rowActions="{ row }"><RowActionMenu :label="row.name || row.hash" :busy="retryingHash === row.hash"
                  :actions="[
                    {key:'retry',label:'重试',icon:'mdi-refresh',disabled:!!retryingHash || !!moduleRunning},
                    ...(row.success ? [{key:'recover',label:'恢复原名',icon:'mdi-undo',color:'warning'}] : []),
                    {key:'delete',label:'删除记录',icon:'mdi-delete-outline',color:'error'},
                  ]" @select="handleHistoryAction($event, row)" /></template>
                <template #expand="{ row }"><RecordDetails :record="row" /></template>
              </ModuleTable>
              <ModuleTable title="失败归档" data-record-block="rename-archive" data-record-state="archive" :columns="recordColumns.archive" :rows="archiveRecords" :total="archiveTotal" row-key="hash" :page="archivePage" :page-size="archivePageSize" :state="recordTableState('archive', archiveRecords)" :cleanup-blocked="!cleanupCounts.rename_archive" cleanup-label="清归档" @cleanup="openCleanupDialog('rename_archive')" @retry="loadArchive(beginRecordRequest(['archive']))" @update:page="pageRecordChange('archive', $event)" @update:page-size="sizeRecordChange('archive', $event)">
                <template #cell-archived_at="{ row }">{{ row.archived_at || row.last_failed_at || '—' }}</template>
                <template #cell-downloader="{ row }"><DownloaderBadge :name="row.downloader || row.downloader_id || '未记录'" /></template>
                <template #cell-category="{ row }">{{ row.category_label || row.category || '—' }}</template>
                <template #cell-reason="{ row }"><span :title="row.archive_reason || row.reason">{{ row.archive_reason || row.reason || '—' }}</span></template>
                <template #rowActions="{ row }">
                  <RowActionMenu :label="row.name || row.hash" :busy="retryingHash === row.hash || restoringHash === row.hash || deletingHash === row.hash"
                    :actions="[
                      { key: 'retry', label: '重试', icon: 'mdi-refresh', disabled: !!retryingHash || restoringHash === row.hash || deletingHash === row.hash },
                      { key: 'restore', label: '恢复记录', icon: 'mdi-archive-arrow-up-outline', disabled: retryingHash === row.hash },
                      { key: 'delete', label: '删除记录', icon: 'mdi-delete-outline', color: 'error', disabled: retryingHash === row.hash },
                    ]" @select="handleArchiveAction($event, row)" />
                </template>
                <template #expand="{ row }"><RecordDetails :record="row" /></template>
              </ModuleTable>
            </template>

            <template v-if="activeTab === 'hr'">
              <ModuleTable title="H&R 任务" data-record-block="hr-tasks" data-record-state="hr" :columns="recordColumns.hr" :rows="visibleRows('hr', visibleHrRows)" :total="visibleHrRows.length" :row-key="rowIdentity" :page="localPages.hr" :page-size="localSizes.hr" :state="recordTableState('hr', visibleHrRows, hrStatusFilter === 'all' && presenceFilter === 'all' ? 'none' : 'filtered')" @retry="refreshActive" @reset-filters="hrStatusFilter = 'all'; presenceFilter = 'all'" @update:page="localPages.hr = $event" @update:page-size="setLocalSize('hr', $event)">
                <template #filters>
                  <CompactSelect v-model="hrStatusFilter" :items="hrStatusFilterOptions" label="考核状态" class="dm-filter" />
                  <CompactSelect v-model="presenceFilter" :items="[{title:'全部',value:'all'},{title:'存在',value:'present'},{title:'缺失',value:'missing'}]" label="存在状态" class="dm-filter" />
                </template>
                <template #toolbar>
                  <VBtn color="primary" size="small" variant="tonal" :disabled="hrClearing || !hrSummary.compliant" @click="askHrClear('compliant')">清理达标记录</VBtn>
                  <VBtn color="primary" size="small" variant="tonal" :disabled="hrClearing || !hrSummary.deleted" @click="askHrClear('missing')">清理缺失记录</VBtn>
                </template>
                <template #cell-name="{ row }"><span :title="row.name || row.torrent_hash">{{ hrTaskTitle(row) }}</span></template>
                <template #cell-downloader_id="{ value }"><DownloaderBadge :name="value || '未记录'" /></template>
                <template #cell-status="{ row }"><VChip size="x-small" :color="hrStatusColor(row.status)" variant="tonal">{{ row.status_text || row.status }}</VChip></template>
                <template #cell-deleted="{ value }"><VChip size="x-small" :color="value === true ? 'warning' : 'default'" variant="tonal">{{ value === true ? '缺失' : value === false ? '存在' : '未知' }}</VChip></template>
                <template #cell-remain_seconds="{ value }">{{ value == null ? '—' : formatDuration(value) }}</template>
                <template #cell-deadline="{ value }">{{ formatTimestamp(value) }}</template>
                <template #cell-progress="{ value }">{{ value == null ? '—' : formatPercent(value) }}</template>
                <template #rowActions="{ row }"><RowActionMenu :label="hrTaskTitle(row)" :busy="hrClearing" :actions="[{key:'clear',label:'清理记录',icon:'mdi-delete-outline',color:'error',disabled:hrClearing}]" @select="askHrClear('task', row)" /></template>
                <template #expand="{ row }"><RecordDetails :record="row" /></template>
              </ModuleTable>
              <details class="dm-runtime-details"><summary>保护跳过统计</summary><dl><template v-for="row in hrSkipRows" :key="row.label"><dt>{{ row.label }}</dt><dd>{{ row.value }}</dd></template></dl></details>
            </template>

            <template v-if="activeTab === 'autoremove'">
              <ModuleTable title="候选清单" data-record-block="autoremove-preview" data-record-state="autoremove" :columns="recordColumns.candidates" :rows="visibleRows('candidates', autoremoveRows)" :total="autoremoveRows.length" :row-key="rowIdentity" :page="localPages.candidates" :page-size="localSizes.candidates" :state="recordTableState('autoremove', autoremoveRows, autoremoveEmptyState, true)" @retry="refreshActive" @update:page="localPages.candidates = $event" @update:page-size="setLocalSize('candidates', $event)">
                <template #toolbar><VChip size="small" variant="tonal">{{ autoremovePreview ? '本次预览' : '上轮候选' }}</VChip><VBtn size="small" :color="autoremoveStatus.observe_only ? 'warning' : autoremoveStatus.action === 'pause' ? 'primary' : 'error'" variant="tonal" :disabled="!!moduleRunning" @click="autoRunConfirm = true">按当前配置执行</VBtn></template>
                <template #cell-name="{ row }">{{ row.name || '名称未记录' }}</template>
                <template #cell-downloader_id="{ value }"><DownloaderBadge :name="value || '未记录'" /></template>
                <template #expand="{ row }"><RecordDetails :record="row" /></template>
              </ModuleTable>
              <p class="dm-hint">预览不锁定执行清单；执行时后端会按当前配置重新判断。</p>
              <ModuleTable title="执行记录" :columns="recordColumns.autoHistory" :unavailable="unavailableHistory" />
              <details class="dm-runtime-details"><summary>最近运行详情</summary>
                <VBtn color="primary" size="small" variant="tonal" :disabled="!cleanupCounts.autoremove_state" @click="openCleanupDialog('autoremove_state')">清最近运行记录</VBtn>
                <ModuleDetailPanel :rows="moduleDetail('autoremove').rows" :items="moduleDetail('autoremove').items" :total="moduleDetail('autoremove').total" :limit="moduleDetail('autoremove').limit" :truncated="moduleDetail('autoremove').truncated" :error="moduleDetail('autoremove').error" />
              </details>
            </template>

            <template v-if="activeTab === 'failclean'">
              <ModuleTable title="执行记录" :columns="recordColumns.failHistory" :unavailable="unavailableHistory" />
              <details class="dm-runtime-details" data-record-state="failclean" :aria-busy="recordStates.failclean.loading"><summary>事件与最近巡检详情</summary>
                <VBtn color="primary" size="small" variant="tonal" :disabled="!cleanupCounts.failclean_state" @click="openCleanupDialog('failclean_state')">清最近运行记录</VBtn>
                <TableState v-if="!failcleanRows.length || recordStates.failclean.error" v-bind="recordTableState('failclean', failcleanRows, failcleanEmptyState)" @retry="refreshActive" />
                <RecordDetails v-for="row in failcleanRows" :key="row.source" :record="{ source: row.source, scanned: row.scanned, cleaned: row.cleaned, failed: row.failed, skipped: row.skipped }" />
              </details>
            </template>

            <template v-if="activeTab === 'sitetag'">
              <ModuleTable title="补全执行记录" :columns="recordColumns.tagHistory" :unavailable="unavailableHistory" />
              <ModuleTable title="标签清理记录" data-record-block="tag-cleanup" :columns="recordColumns.cleanupHistory" :unavailable="unavailableHistory" />
              <details class="dm-runtime-details" data-record-block="tag-cleanup-snapshot"><summary>最近标签清理快照（非逐条历史）</summary>
                <ModuleDetailPanel :rows="moduleDetail('tagcleanup').rows" :items="moduleDetail('tagcleanup').items" :total="moduleDetail('tagcleanup').total" :limit="moduleDetail('tagcleanup').limit" :truncated="moduleDetail('tagcleanup').truncated" :error="moduleDetail('tagcleanup').error" />
              </details>
            </template>

            <template v-if="activeTab === 'upload'">
              <section class="dm-page-stack" data-record-block="upload-status" data-runtime-section="upload-limit">
                <div class="dm-page-heading"><h3>实时监控</h3><div class="dm-page-actions">
                  <CompactSelect v-model="uploadDownloaderFilter" :items="[{title:'全部下载器',value:'all'}, ...uploadLimitDownloaderRows.map(item => ({title:item.name || item.id,value:String(item.id)}))]" label="下载器" class="dm-filter" />
                  <VTextField v-model="uploadSiteFilter" label="搜索站点" density="compact" variant="outlined" hide-details class="dm-filter" />
                </div></div>
                <p v-if="!uploadGroups.length" class="dm-hint">{{ uploadDownloaderFilter !== 'all' || uploadSiteFilter ? '筛选无结果' : '当前快照没有下载器状态' }}</p>
                <section v-for="group in uploadGroups" :key="group.key" class="dm-upload-group">
                  <button type="button" class="dm-group-heading" :aria-expanded="!closedUploadGroups[group.key]" @click="closedUploadGroups[group.key] = !closedUploadGroups[group.key]">
                    <span>{{ closedUploadGroups[group.key] ? '▸' : '▾' }} {{ group.title }}</span>
                    <template v-if="!group.aggregate"><span>{{ group.error ? '异常：' + group.error : group.connected === false ? '未连接' : '状态：' + (group.status || '当前接口未提供') }}</span><span>当前上传 {{ group.upload_rate_bps == null ? '—' : formatUploadRate(group.upload_rate_bps) }}</span><span>全局限速 {{ group.global_limit_kib == null ? '—' : group.global_limit_kib + ' KiB/s' }}</span><span>受管 {{ group.managed_torrents ?? '—' }}</span><span>更新时间 {{ group.updated_at || '当前接口未提供' }}</span></template>
                  </button>
                  <ModuleTable v-if="!closedUploadGroups[group.key]" :title="group.title + ' · 站点额度'" :columns="recordColumns.sites" :rows="group.rows" row-key="key" :pagination="false">
                    <template #cell-upload_rate_bps="{ value }">{{ value == null ? '—' : formatUploadRate(value) }}</template>
                    <template #cell-allocated_kib="{ value }">{{ value == null ? '—' : value + ' KiB/s' }}</template>
                    <template #cell-uploading_torrents="{ value }">{{ value ?? '当前接口未提供' }}</template>
                    <template #cell-state="{ row }">{{ row.state || '当前接口未提供' }}</template>
                    <template #expand="{ row }"><p class="dm-hint">关联下载器：{{ row.downloaders?.join('、') || '当前接口未提供' }}；种子级明细当前接口未提供。</p></template>
                  </ModuleTable>
                </section>
              </section>
              <ModuleTable title="执行记录" :columns="recordColumns.uploadHistory" :unavailable="unavailableHistory" />
              <p class="dm-hint">实际上传与分配额度是不同指标；MP 或插件离线后，下载器可能保留最后写入的限速。</p>
              <details class="dm-runtime-details"><summary>站点识别与策略操作</summary><VBtn color="primary" size="small" variant="tonal" :disabled="!!moduleRunning" @click="doUploadScanSites">扫描站点</VBtn><VBtn size="small" variant="tonal" color="error" :disabled="!!moduleRunning" @click="doUploadClearRules">清空策略</VBtn></details>
            </template>
          </section>

          <section v-if="activeTab === 'diagnostics'" class="dm-page-stack" data-page="diagnostics">
            <div class="dm-page-heading"><ModuleHeader title="运行诊断" :icon="MODULE_ICONS.diagnostics" :show-status="false" enabled /><VBtn color="primary" size="small" variant="tonal" :loading="loading" @click="runDiagnostics">刷新诊断</VBtn></div>
            <div class="dm-four-stats"><div v-for="stat in diagnosticStats" :key="stat.label"><span>{{ stat.label }}</span><strong>{{ stat.value }}</strong></div></div>
            <p class="dm-hint">最近检查：{{ diagnostics?.time || '未检查' }} · 当前显示最近快照，刷新诊断会进行只读检查（可能访问下载器）。</p>
            <ModuleTable title="检查结果" :columns="recordColumns.diagnostics" :rows="visibleRows('diagnostics', filteredDiagnosticRows)" :total="filteredDiagnosticRows.length" :page="localPages.diagnostics" :page-size="localSizes.diagnostics" :state="{ empty: diagnosticModuleFilter === 'all' && diagnosticStateFilter === 'all' ? 'none' : 'filtered' }" @update:page="localPages.diagnostics = $event" @update:page-size="setLocalSize('diagnostics', $event)" @reset-filters="diagnosticModuleFilter = 'all'; diagnosticStateFilter = 'all'">
              <template #filters>
                <CompactSelect v-model="diagnosticModuleFilter" :items="[...moduleFilterItems, {title:'插件',value:'plugin'}]" label="模块" class="dm-filter" />
                <CompactSelect v-model="diagnosticStateFilter" :items="['all','正常','需关注','异常','未检查','不适用']" label="状态" class="dm-filter" />
              </template>
              <template #rowActions="{ row }"><RowActionMenu :label="row.name || row.title || '诊断项'" :actions="[{key:'detail',label:'详情',icon:'mdi-text-box-search-outline'}]" @select="selectedDiagnostic = row" /></template>
            </ModuleTable>
            <section v-if="selectedDiagnostic" class="dm-runtime-details"><h3>{{ selectedDiagnostic.name }}</h3><dl>
              <dt>问题</dt><dd>{{ selectedDiagnostic.reason || selectedDiagnostic.message || '—' }}</dd>
              <dt>影响范围</dt><dd>{{ selectedDiagnostic.target || selectedDiagnostic.module }}</dd>
              <dt>建议</dt><dd>{{ selectedDiagnostic.suggestion || '当前检查项未提供建议' }}</dd>
              <dt>检查时间 / 来源</dt><dd>{{ diagnostics?.time || '未检查' }} / 最近诊断快照</dd>
            </dl></section>
            <details class="dm-runtime-details"><summary>环境信息</summary><p>插件版本：{{ diagnostics?.plugin?.version || '—' }}</p><RecordDetails :record="diagnostics?.paths || {}" /></details>
          </section>
        </template>
      </main>
    </div>

      <VDialog content-class="dm-page" v-model="transferRunDialog" max-width="520">
        <VCard>
          <VCardItem>
            <template #prepend>
              <VAvatar color="primary" variant="tonal" size="40" rounded="lg"><VIcon icon="mdi-transfer" /></VAvatar>
            </template>
            <VCardTitle class="dm-title">确认立即运行转移做种</VCardTitle>
            <VCardSubtitle class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" />按当前配置扫描源下载器并转移种子；若配置了删源，转移完成后会删除源任务。</VCardSubtitle>
          </VCardItem>
          <VDivider />
          <VCardActions>
            <VSpacer />
            <VBtn color="primary" size="small" variant="tonal" :disabled="moduleRunning === 'transfer-run'" @click="transferRunDialog = false">取消</VBtn>
            <VBtn size="small" color="primary" variant="flat" prepend-icon="mdi-play-circle-outline" :loading="moduleRunning === 'transfer-run'" @click="confirmTransferRun">运行转移</VBtn>
          </VCardActions>
        </VCard>
      </VDialog>

      <VDialog content-class="dm-page" v-model="cleanupConfirmDialog" max-width="520">
        <VCard>
          <VCardItem>
            <template #prepend>
              <VAvatar color="warning" variant="tonal" size="40" rounded="lg"><VIcon icon="mdi-delete-sweep-outline" /></VAvatar>
            </template>
            <VCardTitle class="dm-title">确认清理{{ cleanupTarget?.label }}</VCardTitle>
            <VCardSubtitle class="dm-hint">将删除 {{ cleanupTargetCount }} 条{{ cleanupTarget?.detail }}</VCardSubtitle>
          </VCardItem>
          <VDivider />
          <VCardText class="dm-body-text">
            <div>{{ cleanupTarget?.consequence }}</div>
            <div class="dm-hint mt-2">
              不修改下载器任务与文件，不影响 H&amp;R 安全状态、活动队列与限速恢复状态。
            </div>
          </VCardText>
          <VCardActions>
            <VSpacer />
            <VBtn color="primary" size="small" variant="tonal" :disabled="cleanupRunning" @click="cleanupConfirmDialog = false">取消</VBtn>
            <VBtn size="small" color="error" variant="flat" prepend-icon="mdi-delete-sweep-outline" :loading="cleanupRunning"
              :disabled="cleanupTargetCount === 0" @click="confirmCleanupData">清理记录</VBtn>
          </VCardActions>
        </VCard>
      </VDialog>

      <VDialog content-class="dm-page" v-model="hrClearDialog" max-width="520">
        <VCard>
          <VCardItem>
            <template #prepend>
              <VAvatar color="error" variant="tonal" size="40" rounded="lg"><VIcon icon="mdi-delete-outline" /></VAvatar>
            </template>
            <VCardTitle class="dm-title">确认清除 H&R 记录</VCardTitle>
            <VCardSubtitle class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" />{{ hrClearDialogDescription }}</VCardSubtitle>
          </VCardItem>
          <VDivider />
          <VCardText v-if="hrClearKind === 'task'" class="dm-body-text">
            {{ hrClearTarget?.site || hrClearTarget?.name || hrClearTarget?.torrent_hash }}
          </VCardText>
          <VCardActions>
            <VSpacer />
            <VBtn color="primary" size="small" variant="tonal" :disabled="hrClearing" @click="hrClearDialog = false">取消</VBtn>
            <VBtn size="small" color="error" variant="flat" prepend-icon="mdi-delete-outline" :loading="hrClearing" @click="confirmHrClear">清理记录</VBtn>
          </VCardActions>
        </VCard>
      </VDialog>

      <VDialog content-class="dm-page" v-model="cleanupDialog" max-width="620">
        <VCard>
          <VCardItem>
            <template #prepend>
              <VAvatar color="warning" variant="tonal" size="40" rounded="lg"><VIcon icon="mdi-tag-remove-outline" /></VAvatar>
            </template>
            <VCardTitle class="dm-title">确认标签清理</VCardTitle>
            <VCardSubtitle class="dm-hint">{{ cleanupRemovals.length }} 个标签 · {{ cleanupRemovalAssociations }} 条任务关联</VCardSubtitle>
          </VCardItem>
          <VDivider />
          <VList density="compact" class="dm-cleanup-preview-list">
            <VListItem v-for="item in cleanupRemovals" :key="`${item.downloader}-${item.tag}`">
              <template #prepend><VIcon icon="mdi-tag-outline" size="18" /></template>
              <VListItemTitle>{{ item.tag }}</VListItemTitle>
              <VListItemSubtitle>{{ item.downloader }} · {{ item.hashes.length }} 个任务</VListItemSubtitle>
            </VListItem>
          </VList>
          <VDivider />
          <VCardActions>
            <VSpacer />
            <VBtn color="primary" size="small" variant="tonal" :disabled="cleanupExecuting" @click="cleanupDialog = false">取消</VBtn>
            <VBtn size="small" color="error" variant="flat" prepend-icon="mdi-tag-remove-outline" :loading="cleanupExecuting"
              @click="executeCleanupTags">删除标签</VBtn>
          </VCardActions>
        </VCard>
      </VDialog>
  </div>
</template>

<style scoped>
.dm-page { height: clamp(640px, calc(100dvh - 48px), 900px); display: flex; flex-direction: column; overflow: hidden; }
.dm-layout { flex: 1 1 auto; min-height: 0; display: flex; }
.dm-side { width: 160px; flex: 0 0 160px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow-y: auto; }
.dm-side-item { margin: 2px 8px; }
.dm-main { flex: 1 1 auto; min-width: 0; min-height: 0; padding: 16px; overflow-y: auto; }
.dm-page-stack { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.dm-page-heading { display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: 12px; min-width: 0; }
.dm-page-heading > :first-child { flex: 1 1 280px; min-width: 0; }
.dm-page :deep(.v-btn .v-icon) { width: 16px; height: 16px; font-size: var(--dm-text-title-size); }
.dm-page-heading h2 { margin: 0; font-size: var(--dm-text-title-size); font-weight: var(--dm-text-title-weight); line-height: var(--dm-text-title-line-height); }
.dm-page-heading h3 { margin: 0; font-size: var(--dm-text-section-size); font-weight: var(--dm-text-section-weight); line-height: var(--dm-text-section-line-height); }
.dm-page-actions, .dm-row-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; align-items: center; gap: 8px; }
.dm-page-stack :deep(.dm-module-badges) { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.dm-page-stack :deep(.dm-module-stat) { flex-direction: column; align-items: flex-start; gap: 4px; padding: 8px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 6px; }
.dm-page-stack :deep(.dm-module-stat > span:first-child) { color: var(--dm-text-help-color); font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); }
.dm-page-stack :deep(.dm-module-stat > span:last-child) { font-size: var(--dm-text-metric-size); font-weight: var(--dm-text-metric-weight); line-height: var(--dm-text-metric-line-height); font-variant-numeric: tabular-nums; }
.dm-filter { min-width: 140px; max-width: 200px; flex: 1 1 140px; }
.dm-four-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.dm-four-stats > div { min-width: 0; display: flex; flex-direction: column; gap: 4px; padding: 8px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 6px; }
.dm-four-stats span, .dm-hint { color: var(--dm-text-help-color); font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); }
.dm-four-stats strong { overflow-wrap: anywhere; font-size: var(--dm-text-metric-size); font-weight: var(--dm-text-metric-weight); line-height: var(--dm-text-metric-line-height); color: rgb(var(--v-theme-primary)); font-variant-numeric: tabular-nums; }
.dm-overview-cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.dm-overview-card { min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 6px; }
.dm-overview-card p { grid-column: 1 / -1; margin: 0; }
.dm-overview-card :deep(.dm-module-badges) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.dm-overview-card :deep(.dm-module-stat) { border: 0; padding: 4px 0; }
.dm-runtime-details { padding: 8px 0; min-width: 0; }
.dm-runtime-details summary { cursor: pointer; font-size: var(--dm-text-section-size); color: var(--dm-text-section-color); }
.dm-runtime-details dl { display: grid; grid-template-columns: minmax(80px, auto) minmax(0, 1fr); gap: 8px 16px; }
.dm-runtime-details dd { margin: 0; overflow-wrap: anywhere; }
.dm-group-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 20px; width: 100%; padding: 8px 0; text-align: left; border: 0; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: transparent; color: var(--dm-text-body-color); cursor: pointer; font: inherit; }
.dm-group-heading:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); }
.dm-group-heading > :first-child { font-weight: var(--dm-text-section-weight); }
.dm-tag-matrix { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 4px 12px; margin-top: 8px; }
.dm-tag-matrix label { display: flex; align-items: flex-start; gap: 8px; min-width: 0; padding: 6px 0; overflow-wrap: anywhere; }
.dm-tag-matrix input { margin-top: 4px; flex: none; }
.dm-state { display: flex; justify-content: center; padding: 36px; }
.dm-risk { white-space: normal; overflow-wrap: anywhere; color: rgb(var(--v-theme-warning)); }
.dm-title { font-size: var(--dm-text-title-size); font-weight: var(--dm-text-title-weight); }
@media (min-width: 1400px) { .dm-overview-cards { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 760px) {
  .dm-layout { flex-direction: column; }
  .dm-side { width: auto; flex: none; border-right: 0; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
  .dm-side-list { display: flex; overflow-x: auto; }
  .dm-side-item { flex: 0 0 auto; margin: 0 2px; }
  .dm-main { padding: 12px; }
  .dm-overview-cards { grid-template-columns: minmax(0, 1fr); }
  .dm-four-stats, .dm-page-stack :deep(.dm-module-badges) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dm-tag-matrix { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dm-page-actions { width: 100%; }
}
@media (max-width: 400px) { .dm-tag-matrix { grid-template-columns: minmax(0, 1fr); } }
</style>
