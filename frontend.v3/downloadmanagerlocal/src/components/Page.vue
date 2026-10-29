<script setup>
import '../styles/dm-tokens.css'
import TableState from './TableState.vue'
import ModuleTable from './ModuleTable.vue'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { getPluginApi, postPluginApi, postPluginJsonApi } from './api'
import DownloaderBadge from './DownloaderBadge.vue'
import ModuleDetailPanel from './ModuleDetailPanel.vue'
import ModuleHeader from './ModuleHeader.vue'

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
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' },
  { key: 'transfer', title: '转移做种', icon: 'mdi-swap-horizontal' },
  { key: 'history', title: '命名历史', icon: 'mdi-history' },
  { key: 'hr', title: 'H&R 任务', icon: 'mdi-timer-alert-outline' },
  { key: 'autoremove', title: '删种记录', icon: 'mdi-delete-clock-outline' },
  { key: 'failclean', title: '失败清理', icon: 'mdi-broom' },
  { key: 'sitetag', title: '站点标签', icon: 'mdi-tag-multiple' },
  { key: 'upload', title: '上传限速', icon: 'mdi-upload-network-outline' },
  { key: 'diagnostics', title: '运行诊断', icon: 'mdi-stethoscope' },
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
    loading: state.loading && (!hasResult || busyWithResult),
    error: !hasResult ? state.error || false : false,
    refreshFailed: hasResult ? state.error || false : false,
    empty: rows.length ? '' : empty,
  }
}
const total = ref(0)
const archiveTotal = ref(0)
const page = ref(1)
const archivePage = ref(1)
const pageSize = 15
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
    Pending: 'default',
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
const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize)))
const archiveTotalPages = computed(() => Math.max(1, Math.ceil((archiveTotal.value || 0) / pageSize)))

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
    starting: { label: '启动中', color: 'info' },
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
      icon: 'mdi-transfer',
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
      icon: 'mdi-timer-alert-outline',
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
      icon: 'mdi-delete-clock-outline',
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
      icon: 'mdi-broom',
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
      icon: 'mdi-auto-fix',
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
      icon: 'mdi-tag-multiple',
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
      icon: 'mdi-upload-network-outline',
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
const headerMetric = (label, value, tone) => ({ label, value: value ?? '—', tone })
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
  const up = uploadLimit.value
  const headers = {
    transfer: {
      enabled: !!(cards.transfer?.enabled ?? config.transfer_enabled),
      badges: [
        headerMetric('在途', transfer.pending),
        headerMetric('今日成功', transfer.today_success ?? cards.transfer?.today_success),
        headerMetric('累计成功', transfer.success_total ?? cards.transfer?.success_total),
      ],
    },
    rename: {
      enabled: !!(cards.rename?.enabled ?? config.rename_enabled),
      running: !!renameStatus.value.batch_running,
      // The current rename snapshot has per-run, not persisted daily counters.
      badges: [headerMetric('今日成功'), headerMetric('今日失败'),
        headerMetric('待重试', archive.active_failed), headerMetric('失败归档', archive.archived)],
    },
    tag: {
      enabled: !!config.tag_enabled,
      // completed/skipped mix event and complement results, not a full round projection.
      badges: [headerMetric('本轮检查'), headerMetric('成功'), headerMetric('无需更新'), headerMetric('失败')],
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
      // The backend exposes action-specific success counts, but no combined skip count.
      badges: [headerMetric('上轮候选', auto.candidates),
        headerMetric('成功', auto.observe_only ? undefined : (auto.action === 'pause' ? auto.paused : auto.deleted)),
        headerMetric('跳过'), headerMetric('失败', auto.failed)],
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
  if (phase === 'target_added' || phase === 'stopped_after_add') return 'success'
  return 'grey'
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
  if (tag) badges.push({ text: `标签 ${tag}`, color: 'primary' })
  return badges
}

async function loadTransferStatus(request) {
  const recordRequest = beginRecordRequest(['transfer'])
  recordStates.transfer.loading = true
  recordStates.transfer.error = ''
  try {
    const resp = await getApi(`transfer_status?page=${transferPage.value}&page_size=15`, { feedback: 'silent' })
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
    const resp = await getApi(`rename_history?page=${page.value}&page_size=${pageSize}`)
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
    let resp = await getApi(`rename_archive?page=${archivePage.value}&page_size=${pageSize}`)
    if (!isCurrentRecordRequest(request, 'archive')) return
    const lastPage = Math.max(1, Math.ceil((resp?.total || 0) / pageSize))
    if (archivePage.value > lastPage) {
      archivePage.value = lastPage
      resp = await getApi(`rename_archive?page=${archivePage.value}&page_size=${pageSize}`)
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

async function doRecovery(hash) {
  actionMsg.value = ''
  actionOk.value = false
  try {
    const resp = await postApi('recovery_torrent', { hash })
    actionMsg.value = resp?.msg || (resp?.code === 0 ? '恢复成功' : '恢复失败')
    actionOk.value = resp?.code === 0
    if (resp?.code === 0) await reloadRecords()
  } catch (e) {
    actionOk.value = false
    actionMsg.value = e?.message || '恢复失败'
  }
}

async function doDelete(hash) {
  actionMsg.value = ''
  actionOk.value = false
  try {
    const resp = await postApi('delete_rename_history', { hash })
    actionOk.value = resp?.code === 0
    actionMsg.value = resp?.msg || '已删除'
    if (resp?.code === 0) await reloadRecords()
  } catch (e) {
    actionOk.value = false
    actionMsg.value = e?.message || '删除失败'
  }
}

async function doRetryRename(hash) {
  if (!hash || retryingHash.value) return
  actionMsg.value = ''
  actionOk.value = false
  retryingHash.value = hash
  try {
    const resp = await postApi('retry_rename', { hash })
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

async function restoreArchive(hash) {
  actionMsg.value = ''
  actionOk.value = false
  restoringHash.value = hash
  try {
    const resp = await postApi('restore_rename_archive', { hash })
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

async function deleteArchive(hash) {
  actionMsg.value = ''
  actionOk.value = false
  deletingHash.value = hash
  try {
    const resp = await postApi('delete_rename_archive', { hash })
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
    managed: { label: '业务', color: 'success' },
    temporary: { label: '临时', color: 'warning' },
    legacy_temporary: { label: '旧临时', color: 'warning' },
    legacy_candidate: { label: '疑似旧临时', color: 'warning' },
    active_temporary: { label: '使用中', color: 'info' },
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
  try {
    const response = await postJsonApi('tag_cleanup_execute', { removals: cleanupRemovals.value })
    cleanupDialog.value = false
    await scanCleanupTags()
    cleanupStatus.value = response?.code === 0 ? 'success' : (response?.code === 2 ? 'warning' : 'error')
    cleanupMessage.value = response?.msg || '清理完成'
  } catch (error) {
    cleanupStatus.value = 'error'
    cleanupMessage.value = error?.message || '清理失败'
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
      <VBtn size="small" variant="text" prepend-icon="mdi-refresh" class="text-none me-2" @click="refreshActive()" :loading="loading">刷新数据</VBtn>
      <VBtn size="small" variant="text" prepend-icon="mdi-cog-outline" class="text-none" @click="emit('switch')">配置插件</VBtn>
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
          <section v-if="activeTab === 'overview'" class="dm-overview-band">
            <div class="dm-overview-stat-grid">
              <div v-for="card in overviewCoreCards" :key="card.title" class="dm-overview-stat" :class="`dm-overview-stat--${card.color}`">
                <VAvatar :color="card.color" variant="tonal" size="32" rounded="lg"><VIcon :icon="card.icon" size="18" /></VAvatar>
                <div class="dm-overview-stat-content">
                  <div class="dm-overview-stat-label dm-hint">{{ card.title }}</div>
                  <div class="dm-overview-stat-value">{{ card.value }}</div>
                  <div class="dm-overview-stat-desc dm-hint">{{ card.desc }}</div>
                </div>
              </div>
            </div>
            <div class="dm-overview-section mt-3">
              <div class="dm-section-title">运行链路</div>
              <div class="dm-flow">
                <div v-for="flow in runtimeFlows" :key="flow.label" class="dm-flow-block">
                  <div class="dm-flow-label">{{ flow.label }}</div>
                  <div class="dm-flow-row">
                    <template v-for="(step, index) in flow.steps" :key="`${flow.label}-${step}`">
                      <span class="dm-flow-step">{{ step }}</span>
                      <VIcon v-if="index < flow.steps.length - 1" class="dm-flow-arrow" icon="mdi-arrow-right" size="14" />
                    </template>
                  </div>
                </div>
              </div>
            </div>

            <section v-if="overviewAttentionItems.length" class="dm-attention-panel mt-3">
              <div class="dm-section-heading">
                <div>
                  <div class="dm-section-title">需要关注</div>
                  <div class="dm-hint">点击条目可展开对应模块卡并定位。</div>
                </div>
                <VChip color="warning" size="small" variant="tonal">{{ overviewAttentionItems.length }} 项</VChip>
              </div>
              <div class="dm-attention-list">
                <div
                  v-for="item in overviewAttentionItems"
                  :key="`${item.title}-${item.detail}`"
                  class="dm-attention-item"
                  :class="{ 'dm-attention-item--linked': !!item.target }"
                  :role="item.target ? 'button' : null"
                  :tabindex="item.target ? 0 : null"
                  @click="focusModule(item.target)"
                  @keyup.enter="focusModule(item.target)"
                >
                  <VIcon :icon="item.icon" :color="item.color" size="18" />
                  <div class="min-w-0">
                    <strong>{{ item.title }}</strong>
                    <div class="dm-hint dm-break-text">{{ item.detail }}</div>
                  </div>
                </div>
              </div>
            </section>
          </section>

          <section v-if="moduleGridCards.length" class="dm-module-section" :class="activeTab === 'overview' ? 'mt-4' : 'mt-3'">
            <div v-if="activeTab === 'overview'" class="dm-section-heading">
              <div>
                <div class="dm-section-title">功能状态与操作</div>
                <div class="dm-hint">每个模块卡给出状态摘要与手动操作，需要时展开查看运行明细，明细条数可调。</div>
              </div>
              <VSelect density="compact"
                v-model="detailLimit"
                :items="DETAIL_LIMIT_CHOICES"
                label="明细条数"
                variant="outlined"
                hide-details
                class="dm-detail-limit-select"
              />
            </div>
            <div class="dm-module-grid mt-2">
              <article v-for="card in moduleGridCards" :key="card.key" :id="`dm-module-${card.key}`" class="dm-module-card">
                <div v-if="moduleHeaders[card.key]" class="dm-card-heading">
                  <ModuleHeader v-bind="moduleHeaders[card.key]" />
                  <VBtn size="small"
                    v-if="moduleRecordView(card.key)"
                    variant="text"
                    class="text-none dm-card-data-link"
                    prepend-icon="mdi-text-box-search-outline"
                    @click="openModuleRecords(card.key)"
                  >查看数据</VBtn>
                </div>
                <div v-else class="dm-module-head">
                  <VAvatar :color="card.color" variant="tonal" size="30" rounded="lg"><VIcon :icon="card.icon" size="17" /></VAvatar>
                  <div class="min-w-0">
                    <div class="dm-module-title dm-hint">{{ card.title }}</div>
                    <div class="dm-module-value">{{ card.value }}</div>
                  </div>
                </div>
                <div class="dm-hint dm-break-text"><span v-if="moduleHeaders[card.key]">{{ card.value }} · </span>{{ card.desc }}</div>

                <div class="dm-module-actions">
                  <VBtn size="small"
                    v-for="action in card.actions"
                    :key="action.key"
                    variant="tonal"
                    :color="action.color || 'primary'"
                    :prepend-icon="action.icon"
                    class="text-none"
                    :loading="moduleRunning === action.key"
                    :disabled="moduleRunning !== '' && moduleRunning !== action.key"
                    @click="action.run()"
                  >{{ action.label }}</VBtn>
                  <VBtn size="small"
                    v-for="item in moduleCleanupButtons(card.key)"
                    :key="item.key"
                    variant="text"
                    class="text-none"
                    color="warning"
                    prepend-icon="mdi-delete-sweep-outline"
                    :disabled="item.count === 0"
                    @click="openCleanupDialog(item.key)"
                  >{{ item.label }}</VBtn>
                  <VBtn size="small"
                    variant="text"
                    class="text-none ml-auto"
                    :append-icon="expandedModules[card.key] ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                    @click="expandedModules[card.key] = !expandedModules[card.key]"
                  >{{ expandedModules[card.key] ? '收起' : '详情' }}</VBtn>
                </div>

                <VExpandTransition>
                  <div v-show="expandedModules[card.key]" class="dm-module-detail">
                    <template v-if="card.key === 'upload_limit'">
                      <VAlert v-for="runtimeError in uploadLimit.errors || []" :key="runtimeError" type="error" variant="tonal" density="compact" class="mb-2">
                        {{ runtimeError }}
                      </VAlert>
                      <!-- 站点聚合与运行错误已由下方网格和告警展示，本模块不传 items，避免同一数据重复出现 -->
                      <ModuleDetailPanel class="mt-3" title="运行明细" :rows="moduleDetail('upload_limit').rows" :error="moduleDetail('upload_limit').error">
                        <template #appendix>
                          <div class="dm-module-detail-title mt-3">下载器状态</div>
                          <div v-if="uploadLimitDownloaderRows.length" class="dm-upload-status-grid">
                            <div v-for="item in uploadLimitDownloaderRows" :key="item.id" class="dm-upload-status-card">
                              <div class="dm-upload-status-head">
                                <div class="min-w-0">
                                  <strong class="dm-body-text">{{ item.id }}</strong>
                                  <div class="dm-hint">{{ item.type === 'transmission' ? 'Transmission' : 'qBittorrent' }}</div>
                                </div>
                                <VChip size="x-small" :color="item.error ? 'warning' : 'success'" variant="tonal">{{ item.error ? '异常' : '正常' }}</VChip>
                              </div>
                              <div class="dm-upload-values">
                                <span>实时 <strong>{{ formatUploadRate(item.upload_rate_bps) }}</strong></span>
                                <span>{{ item.type === 'transmission' ? 'Session 全局上限' : 'QB 全局上限' }} <strong>{{ item.total_limit_kib }} KiB/s</strong></span>
                                <span>受限任务 <strong>{{ item.managed_torrents || 0 }}</strong></span>
                                <span>宽限任务 <strong>{{ item.grace_torrents || 0 }}</strong></span>
                              </div>
                              <div v-if="item.error" class="dm-hint text-error mt-2 dm-break-text">{{ item.error }}</div>
                            </div>
                          </div>
                          <div v-else class="dm-monitor-empty dm-hint">当前没有启用的限速下载器</div>

                          <div class="dm-module-detail-title mt-3">受限站点</div>
                          <div v-if="uploadLimitSiteRows.length" class="dm-upload-site-status">
                            <div v-for="item in uploadLimitSiteRows" :key="item.key" class="dm-upload-site-status-row">
                              <div class="min-w-0">
                                <strong class="dm-body-text">{{ item.name }}</strong>
                                <div class="dm-hint">{{ item.torrent_count }} 个任务 · {{ item.downloaders?.join('、') }}</div>
                              </div>
                              <span class="dm-hint">实时 <strong>{{ formatUploadRate(item.upload_rate_bps) }}</strong></span>
                              <span class="dm-hint">站点额度 <strong>{{ item.allocated_kib }} KiB/s</strong></span>
                              <span class="dm-hint">站点上限 <strong>{{ item.limit_kib }} KiB/s</strong></span>
                            </div>
                          </div>
                          <div v-else class="dm-monitor-empty dm-hint">当前没有填写正数上限的受限站点</div>
                          <div class="dm-hint mt-2">实时速率是下载器当前实际上传流量；站点额度是插件写入单种限速的合计值，两者不是同一指标。</div>
                        </template>
                      </ModuleDetailPanel>
                    </template>

                    <template v-else>
                      <template v-if="card.detailTitle">
                        <div class="dm-module-detail-title">{{ card.detailTitle }}</div>
                      </template>
                      <div v-if="card.details?.length" class="dm-module-detail-grid">
                        <div v-for="row in card.details" :key="row.label" class="dm-module-detail-row">
                          <span>{{ row.label }}</span><strong>{{ detailValue(row.value) }}</strong>
                        </div>
                      </div>
                      <div v-for="note in card.notes || []" :key="note.text" class="dm-hint mt-2" :class="{ 'dm-risk': note.type === 'warning', 'dm-error': note.type === 'error' }"><VIcon v-if="note.type === 'warning' || note.type === 'error'" :icon="note.type === 'error' ? 'mdi-alert-circle-outline' : 'mdi-alert-outline'" size="16" />{{ note.text }}</div>
                      <template v-if="moduleDetailVisible(card.key)">
                        <ModuleDetailPanel
                          class="mt-3"
                          title="运行明细"
                          :rows="moduleDetail(card.key).rows"
                          :items="moduleDetail(card.key).items"
                          :total="moduleDetail(card.key).total"
                          :limit="moduleDetail(card.key).limit"
                          :truncated="moduleDetail(card.key).truncated"
                          :error="moduleDetail(card.key).error"
                        />
                      </template>
                    </template>
                  </div>
                </VExpandTransition>
              </article>
            </div>
          </section>

          <div v-if="activeTab === 'history'" class="dm-record-block mt-3" data-record-block="rename-history">
            <div class="dm-record-block-head">
              <div>
                <div class="dm-record-block-title">命名历史</div>
                <div class="dm-hint">共 {{ total }} 条，逐条可补刀、恢复原始名称或删除记录。</div>
              </div>
              <VBtn size="small" variant="tonal" prepend-icon="mdi-auto-fix" class="text-none"
                :loading="moduleRunning === 'rename-retry' || renameStatus.batch_running" :disabled="(moduleRunning !== '' && moduleRunning !== 'rename-retry') || renameStatus.batch_running" @click="doRetryRenames">{{ renameStatus.batch_running ? '重试中…' : '重试' }}</VBtn>
              <VBtn size="small" variant="tonal" prepend-icon="mdi-radar" class="text-none ml-2"
                :loading="moduleRunning === 'rename-scan'" :disabled="moduleRunning !== '' && moduleRunning !== 'rename-scan'" @click="doRenameScan">扫描重命名</VBtn>
            </div>
            <div data-record-state="history" :aria-busy="recordStates.history.loading">
              <p v-if="recordStates.history.loading && (recordStates.history.loaded || records.length)" role="status" class="dm-hint">正在刷新记录，保留上次结果</p>
              <div class="dm-table-scroll dm-desktop-table">
                <VTable density="compact" class="dm-table">
                  <thead>
                    <tr>
                      <th class="dm-table-head">时间</th>
                      <th class="dm-table-head">原始名称</th>
                      <th class="dm-table-head">命名后</th>
                      <th class="dm-table-head">状态</th>
                      <th class="dm-table-head">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="!records.length || recordStates.history.error"><td colspan="5"><TableState v-bind="recordTableState('history', records)" @retry="loadHistory(beginRecordRequest(['history']))" /></td></tr>
                    <tr v-for="r in records" :key="r.hash">
                      <td class="dm-body-text text-no-wrap">{{ r.time }}</td>
                      <td class="dm-body-text dm-ellipsis" :title="r.original_name">{{ r.original_name }}</td>
                      <td class="dm-body-text dm-ellipsis" :title="r.after_name">{{ r.after_name }}</td>
                      <td><VChip size="x-small" :color="r.success ? 'success' : 'error'" variant="tonal">{{ r.success ? '成功' : (r.reason || '失败') }}</VChip></td>
                      <td>
                        <div class="d-flex ga-1">
                          <VBtn size="small" variant="tonal" color="primary" @click="doRetryRename(r.hash)" :loading="retryingHash === r.hash">重试</VBtn>
                          <VBtn size="small" v-if="r.success" variant="tonal" color="warning" @click="doRecovery(r.hash)">恢复名称</VBtn>
                          <VBtn size="small" variant="text" color="error" @click="doDelete(r.hash)">删除记录</VBtn>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </VTable>
              </div>
              <div class="dm-mobile-list dm-history-list">
                <TableState v-bind="recordTableState('history', records)" @retry="loadHistory(beginRecordRequest(['history']))" />
                <article v-for="r in records" :key="r.hash" class="dm-record-card dm-history-card">
                  <div class="dm-record-head">
                    <div class="dm-record-title" :title="r.after_name || r.original_name">{{ r.after_name || r.original_name || r.hash }}</div>
                    <VChip class="dm-record-status" size="x-small" :color="r.success ? 'success' : 'error'" variant="tonal">{{ r.success ? '成功' : (r.reason || '失败') }}</VChip>
                  </div>
                  <div class="dm-record-meta">
                    <div class="dm-record-row">
                      <span class="dm-record-label">时间</span>
                      <span class="dm-record-value">{{ r.time || '-' }}</span>
                    </div>
                    <div class="dm-record-row">
                      <span class="dm-record-label">原始</span>
                      <span class="dm-record-value" :title="r.original_name">{{ r.original_name || '-' }}</span>
                    </div>
                    <div class="dm-record-row">
                      <span class="dm-record-label">命名后</span>
                      <span class="dm-record-value" :title="r.after_name">{{ r.after_name || '-' }}</span>
                    </div>
                  </div>
                  <div class="dm-record-actions">
                    <VBtn size="small" variant="tonal" color="primary" prepend-icon="mdi-auto-fix" @click="doRetryRename(r.hash)" :loading="retryingHash === r.hash">重试</VBtn>
                    <VBtn size="small" v-if="r.success" variant="tonal" color="warning" prepend-icon="mdi-undo" @click="doRecovery(r.hash)">恢复名称</VBtn>
                    <VBtn size="small" variant="text" color="error" prepend-icon="mdi-delete-outline" @click="doDelete(r.hash)">删除记录</VBtn>
                  </div>
                </article>
              </div>
            </div>
            <div v-if="records.length && total > pageSize" class="d-flex align-center justify-center pa-3">
              <VBtn size="small" aria-label="上一页" variant="tonal" icon="mdi-chevron-left" :disabled="page <= 1 || paging" @click="prevPage" class="mr-2" />
              <span class="dm-hint mx-1">{{ page }} / {{ totalPages }}（共 {{ total }} 条）</span>
              <VBtn size="small" aria-label="下一页" variant="tonal" icon="mdi-chevron-right" :disabled="page >= totalPages || paging" @click="nextPage" class="ml-2" />
            </div>
          </div>

          <div v-if="activeTab === 'history'" class="dm-record-block mt-3" data-record-block="rename-archive">
            <div class="dm-record-block-head">
              <div>
                <div class="dm-record-block-title">重命名归档</div>
                <div class="dm-hint">共 {{ archiveTotal }} 条连续失败后归档的记录，可补刀、恢复或删除。</div>
              </div>
            </div>
            <div data-record-state="archive" :aria-busy="recordStates.archive.loading">
              <p v-if="recordStates.archive.loading && (recordStates.archive.loaded || archiveRecords.length)" role="status" class="dm-hint">正在刷新记录，保留上次结果</p>
              <div class="dm-table-scroll dm-desktop-table">
                <VTable density="compact" class="dm-table">
                  <thead>
                    <tr>
                      <th class="dm-table-head">归档时间</th>
                      <th class="dm-table-head">名称</th>
                      <th class="dm-table-head">分类</th>
                      <th class="dm-table-head">次数</th>
                      <th class="dm-table-head">原因</th>
                      <th class="dm-table-head">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="!archiveRecords.length || recordStates.archive.error"><td colspan="6"><TableState v-bind="recordTableState('archive', archiveRecords)" @retry="loadArchive(beginRecordRequest(['archive']))" /></td></tr>
                    <tr v-for="r in archiveRecords" :key="r.hash">
                      <td class="dm-body-text text-no-wrap">{{ r.archived_at || r.last_failed_at }}</td>
                      <td class="dm-body-text dm-ellipsis" :title="r.name">{{ r.name || r.hash }}</td>
                      <td><VChip size="x-small" color="warning" variant="tonal">{{ r.category_label || r.category }}</VChip></td>
                      <td class="dm-body-text">{{ r.fail_count }}</td>
                      <td class="dm-body-text dm-ellipsis" :title="r.archive_reason || r.reason">{{ r.archive_reason || r.reason }}</td>
                      <td>
                        <div class="d-flex ga-1">
                          <VBtn size="small" variant="tonal" color="primary" @click="doRetryRename(r.hash)" :loading="retryingHash === r.hash" :disabled="!!retryingHash || restoringHash === r.hash || deletingHash === r.hash">重试</VBtn>
                          <VBtn size="small" variant="tonal" color="primary" @click="restoreArchive(r.hash)" :loading="restoringHash === r.hash" :disabled="retryingHash === r.hash">恢复记录</VBtn>
                          <VBtn size="small" variant="text" color="error" @click="deleteArchive(r.hash)" :loading="deletingHash === r.hash" :disabled="retryingHash === r.hash">删除记录</VBtn>
                        </div>
                      </td>
                    </tr>
                  </tbody>
                </VTable>
              </div>
              <div class="dm-mobile-list dm-archive-list">
                <TableState v-bind="recordTableState('archive', archiveRecords)" @retry="loadArchive(beginRecordRequest(['archive']))" />
                <article v-for="r in archiveRecords" :key="r.hash" class="dm-record-card dm-archive-card">
                  <div class="dm-record-head">
                    <div class="dm-record-title" :title="r.name || r.hash">{{ r.name || r.hash }}</div>
                    <VChip class="dm-record-status" size="x-small" color="warning" variant="tonal">{{ r.category_label || r.category }}</VChip>
                  </div>
                  <div class="dm-record-meta">
                    <div class="dm-record-row">
                      <span class="dm-record-label">归档</span>
                      <span class="dm-record-value">{{ r.archived_at || r.last_failed_at || '-' }}</span>
                    </div>
                    <div class="dm-record-row">
                      <span class="dm-record-label">次数</span>
                      <span class="dm-record-value">{{ r.fail_count }}</span>
                    </div>
                    <div class="dm-record-row">
                      <span class="dm-record-label">原因</span>
                      <span class="dm-record-value">{{ r.archive_reason || r.reason || '-' }}</span>
                    </div>
                  </div>
                  <div class="dm-record-actions">
                    <VBtn size="small" variant="tonal" color="primary" prepend-icon="mdi-auto-fix" @click="doRetryRename(r.hash)" :loading="retryingHash === r.hash" :disabled="!!retryingHash || restoringHash === r.hash || deletingHash === r.hash">重试</VBtn>
                    <VBtn size="small" variant="tonal" color="warning" prepend-icon="mdi-undo" @click="restoreArchive(r.hash)" :loading="restoringHash === r.hash" :disabled="retryingHash === r.hash">恢复记录</VBtn>
                    <VBtn size="small" variant="text" color="error" prepend-icon="mdi-delete-outline" @click="deleteArchive(r.hash)" :loading="deletingHash === r.hash" :disabled="retryingHash === r.hash">删除记录</VBtn>
                  </div>
                </article>
              </div>
            </div>
            <div v-if="archiveRecords.length && archiveTotal > pageSize" class="d-flex align-center justify-center pa-3">
              <VBtn size="small" aria-label="上一页" variant="tonal" icon="mdi-chevron-left" :disabled="archivePage <= 1 || paging" @click="prevArchivePage" class="mr-2" />
              <span class="dm-hint mx-1">{{ archivePage }} / {{ archiveTotalPages }}（共 {{ archiveTotal }} 条）</span>
              <VBtn size="small" aria-label="下一页" variant="tonal" icon="mdi-chevron-right" :disabled="archivePage >= archiveTotalPages || paging" @click="nextArchivePage" class="ml-2" />
            </div>
          </div>

          <div v-if="activeTab === 'autoremove'" class="dm-record-block mt-3" data-record-block="autoremove-preview" data-record-state="autoremove" :aria-busy="recordStates.autoremove.loading">
            <div class="dm-record-block-head">
              <div class="dm-record-block-title"><span class="dm-table-sr">删种预览记录</span></div>
              <div class="dm-hint">自动删种的候选清单；点「预览」重新收集候选，不写下载器。</div>
            </div>
            <p v-if="recordStates.autoremove.loading && (recordStates.autoremove.loaded || autoremoveRows.length)" role="status" class="dm-hint">正在刷新记录，保留上次结果</p>
            <ModuleTable title="删种预览记录" :columns="[
              { key: 'downloader_id', label: '下载器' },
              { key: 'name', label: '名称' },
              { key: 'site', label: '站点' },
              { key: 'size_text', label: '体积', align: 'right' },
              { key: 'ratio', label: '分享率', align: 'right' },
              { key: 'seeding_hours', label: '做种时长', align: 'right' },
              { key: 'reason', label: '原因' },
            ]" :rows="autoremoveRows" :total="autoremoveRows.length" :state="recordTableState('autoremove', autoremoveRows, autoremoveEmptyState, true)" row-key="torrent_hash" @retry="loadAutoremoveStatus(beginPageRequest())">
              <template #toolbar>
                <VChip size="small" variant="tonal" :color="autoremovePreview ? 'primary' : 'default'">
                  {{ autoremovePreview ? `预览命中 ${autoremoveRows.length} 个候选` : `上轮候选 ${autoremoveRows.length} 个` }}
                </VChip>
              </template>
              <template #cell-name="{ row }"><span class="dm-body-text dm-ellipsis" :title="row.name || row.torrent_hash">{{ row.name || row.torrent_hash || '名称未记录' }}</span></template>
              <template #cell-site="{ value }">{{ detailValue(value) }}</template>
              <template #cell-size_text="{ value }">{{ detailValue(value) }}</template>
              <template #cell-ratio="{ value }">{{ detailValue(value) }}</template>
              <template #cell-seeding_hours="{ value }">{{ value == null || value === '' ? '—' : `${value} 小时` }}</template>
              <template #cell-reason="{ value }">{{ detailValue(value) }}</template>
              <template #cell-downloader_id="{ value }">{{ detailValue(value) }}</template>
            </ModuleTable>
            <!-- ModuleTable is the responsive data surface; no second dm-record-card tree. -->
          </div>

          <div v-if="activeTab === 'failclean'" class="dm-record-block mt-3" data-record-state="failclean" :aria-busy="recordStates.failclean.loading">
            <div class="dm-record-block-head">
              <div class="dm-record-block-title"><span class="dm-table-sr">失败清理明细</span></div>
              <div class="dm-hint">来源事件与上轮巡检分开展示；事件计数不并入上轮巡检徽标。</div>
            </div>
            <p v-if="recordStates.failclean.loading && (recordStates.failclean.loaded || failcleanRows.length)" role="status" class="dm-hint">正在刷新记录，保留上次结果</p>
            <ModuleTable title="失败清理明细" :columns="[
              { key: 'source', label: '来源' },
              { key: 'scanned', label: '扫描', align: 'right' },
              { key: 'cleaned', label: '清理', align: 'right' },
              { key: 'failed', label: '失败', align: 'right' },
              { key: 'skipped', label: '跳过', align: 'right' },
            ]" :rows="failcleanRows" :total="failcleanRows.length" :state="recordTableState('failclean', failcleanRows, failcleanEmptyState, true)" row-key="source" @retry="loadFailcleanStatus(beginPageRequest())">
              <template #cell-scanned="{ value }">{{ detailValue(value) }}</template>
              <template #cell-cleaned="{ value }">{{ detailValue(value) }}</template>
              <template #cell-failed="{ value }">{{ detailValue(value) }}</template>
              <template #cell-skipped="{ value }">{{ detailValue(value) }}</template>
            </ModuleTable>
            <!-- ModuleTable is the responsive data surface; no second dm-record-card tree. -->
          </div>

          <div v-if="activeTab === 'hr'" class="dm-record-block mt-3" data-record-block="hr-tasks" data-record-state="hr" :aria-busy="recordStates.hr.loading">
            <div class="dm-record-block-head">
              <div>
                <div class="dm-record-block-title">H&R 任务</div>
                <div class="dm-hint">任务总数 {{ hrSummary.total || 0 }} · 达标 {{ hrSummary.compliant || 0 }} · 超期 {{ hrSummary.overdue || 0 }} · 需做种 {{ hrSummary.needs_seeding || 0 }}</div>
              </div>
              <div class="d-flex flex-wrap ga-2 align-center">
                <VSelect v-model="hrStatusFilter" :items="hrStatusFilterOptions" label="状态筛选" density="compact" variant="outlined" hide-details class="dm-hr-filter" />
                <VBtn size="small" variant="tonal" prepend-icon="mdi-check-decagram-outline" class="text-none" @click="askHrClear('compliant')" :disabled="hrClearing || !(hrSummary.compliant || 0)">清理达标记录</VBtn>
                <VBtn size="small" variant="tonal" prepend-icon="mdi-link-off" class="text-none" @click="askHrClear('missing')" :disabled="hrClearing || !(hrSummary.needs_seeding || 0)">清理失效记录</VBtn>
              </div>
            </div>
            <div class="dm-table-scroll dm-desktop-table mt-2">
              <VTable density="compact" class="dm-table">
                <thead>
                  <tr>
                    <th class="dm-table-head">种子</th>
                    <th class="dm-table-head">状态</th>
                    <th class="dm-table-head">剩余时长</th>
                    <th class="dm-table-head">截止日期</th>
                    <th class="dm-table-head">做种进度</th>
                    <th class="dm-table-head">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-if="!hrTaskRows.length || recordStates.hr.error"><td colspan="6"><TableState v-bind="recordTableState('hr', hrTaskRows, hrStatusFilter !== 'all' ? 'filtered' : 'none')" @retry="loadHrStatus(beginPageRequest())" /></td></tr>
                  <tr v-for="task in hrTaskRows" :key="`${task.downloader_id}-${task.torrent_hash}`">
                    <td class="dm-body-text dm-ellipsis" :title="task.name || task.torrent_hash">{{ hrTaskTitle(task) }}<span v-if="task.site" class="dm-hint"> · {{ task.site }}</span></td>
                    <td><VChip size="x-small" :color="hrStatusColor(task.status)" variant="tonal">{{ task.status_text || task.status }}</VChip></td>
                    <td class="dm-body-text text-no-wrap">{{ formatDuration(task.remain_seconds) }}</td>
                    <td class="dm-body-text text-no-wrap">{{ formatTimestamp(task.deadline) }}</td>
                    <td class="dm-body-text">{{ formatPercent(task.progress) }}</td>
                    <td>
                      <VBtn size="small" variant="text" color="error" :loading="hrClearing && hrClearKey === `${task.downloader_id}-${task.torrent_hash}`" @click="askHrClear('task', task)">清理记录</VBtn>
                    </td>
                  </tr>
                </tbody>
              </VTable>
            </div>
            <div class="dm-mobile-list mt-2">
              <TableState v-if="!hrTaskRows.length || recordStates.hr.error" v-bind="recordTableState('hr', hrTaskRows, hrStatusFilter !== 'all' ? 'filtered' : 'none')" @retry="loadHrStatus(beginPageRequest())" />
              <article v-for="task in hrTaskRows" :key="`${task.downloader_id}-${task.torrent_hash}`" class="dm-record-card">
                <div class="dm-record-head">
                  <div class="dm-record-title" :title="task.name || task.torrent_hash">{{ hrTaskTitle(task) }}<span v-if="task.site" class="dm-hint"> · {{ task.site }}</span></div>
                  <VChip class="dm-record-status" size="x-small" :color="hrStatusColor(task.status)" variant="tonal">{{ task.status_text || task.status }}</VChip>
                </div>
                <div class="dm-record-meta">
                  <div class="dm-record-row"><span class="dm-record-label">剩余</span><span class="dm-record-value">{{ formatDuration(task.remain_seconds) }}</span></div>
                  <div class="dm-record-row"><span class="dm-record-label">截止</span><span class="dm-record-value">{{ formatTimestamp(task.deadline) }}</span></div>
                  <div class="dm-record-row"><span class="dm-record-label">进度</span><span class="dm-record-value">{{ formatPercent(task.progress) }}</span></div>
                </div>
                <div class="dm-record-actions">
                  <VBtn size="small" variant="text" color="error" :loading="hrClearing && hrClearKey === `${task.downloader_id}-${task.torrent_hash}`" @click="askHrClear('task', task)">清理记录</VBtn>
                </div>
              </article>
            </div>
          </div>

          <div v-if="activeTab === 'transfer'" class="dm-record-block mt-3" data-record-block="transfer-tasks">
            <div class="dm-record-block-head">
              <div>
                <div class="dm-record-block-title">任务配置</div>
                <div class="dm-hint">启用任务 {{ transferTasks.length }} 条 · 在途 {{ transferSummary.pending || 0 }} · 已完成 {{ transferSummary.completed || 0 }} · 累计成功 {{ transferSummary.success_total || 0 }}</div>
              </div>
              <div class="d-flex flex-wrap ga-2">
                <VBtn size="small" variant="text" prepend-icon="mdi-refresh" class="text-none" @click="refreshActive">刷新数据</VBtn>
              </div>
            </div>

            <div class="d-flex flex-wrap ga-1 mt-2">
              <VChip size="small" variant="tonal" color="primary">在途 {{ transferSummary.pending || 0 }}</VChip>
              <VChip size="small" variant="tonal" :color="transferSummary.rollback ? 'error' : 'grey'">回滚 {{ transferSummary.rollback || 0 }}</VChip>
              <VChip size="small" variant="tonal" color="success">今日成功 {{ transferSummary.today_success || 0 }}</VChip>
              <VChip size="small" variant="tonal" color="primary">累计成功 {{ transferSummary.success_total || 0 }}</VChip>
              <VChip size="small" variant="tonal" color="warning">兜底成功 {{ transferSummary.fallback_success || 0 }}</VChip>
              <VChip size="small" variant="tonal" color="info">H&R 保护 {{ transferSummary.hr_protected || 0 }}</VChip>
            </div>

            <div class="dm-section-title mt-4">任务配置</div>
            <div v-if="!transferTasks.length" class="dm-state text-center dm-hint">
              <VIcon icon="mdi-swap-horizontal" size="48" color="grey-lighten-1" class="mb-2" />
              <div>暂无启用的转移任务</div>
            </div>
            <div v-else class="dm-table-scroll dm-desktop-table mt-2">
              <VTable density="compact" class="dm-table">
                <thead>
                  <tr>
                    <th class="dm-table-head">名称</th>
                    <th class="dm-table-head">源下载器</th>
                    <th class="dm-table-head">目的下载器</th>
                    <th class="dm-table-head">数据映射</th>
                    <th class="dm-table-head">筛选条件</th>
                    <th class="dm-table-head">设置</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="task in transferTasks" :key="task.name">
                    <td class="dm-body-text dm-ellipsis" :title="task.name">{{ task.name }}</td>
                    <td class="dm-body-text">{{ task.from_downloader }}</td>
                    <td class="dm-body-text">{{ task.to_downloader }}</td>
                    <td class="dm-body-text dm-ellipsis" :title="`${task.from_path} → ${task.to_path}`">{{ task.from_path }} → {{ task.to_path }}</td>
                    <td class="dm-body-text dm-ellipsis" :title="transferFilterText(task)">{{ transferFilterText(task) }}</td>
                    <td>
                      <div v-if="transferSettingBadges(task).length" class="d-flex flex-wrap ga-1">
                        <VChip v-for="badge in transferSettingBadges(task)" :key="badge.text" size="x-small" variant="tonal" :color="badge.color">{{ badge.text }}</VChip>
                      </div>
                      <span v-else class="dm-hint">默认</span>
                    </td>
                  </tr>
                </tbody>
              </VTable>
            </div>

            <div class="dm-section-title mt-4">在途事务</div>
            <div v-if="!transferPending.length" class="dm-state text-center dm-hint">
              <VIcon icon="mdi-check-circle-outline" size="48" color="grey-lighten-1" class="mb-2" />
              <div>暂无在途转移事务</div>
            </div>
            <div v-else class="dm-table-scroll dm-desktop-table mt-2">
              <VTable density="compact" class="dm-table">
                <thead>
                  <tr>
                    <th class="dm-table-head">源 → 目的</th>
                    <th class="dm-table-head">种子</th>
                    <th class="dm-table-head">阶段</th>
                    <th class="dm-table-head">已等待</th>
                    <th class="dm-table-head">选项</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in transferPending" :key="item.key">
                    <td class="dm-body-text">{{ item.source_downloader }} → {{ item.downloader }}</td>
                    <td class="dm-body-text dm-ellipsis" :title="item.source_hash">{{ transferPrimaryText(item) }}<span class="dm-hint"> · {{ transferSecondaryText(item) }}</span></td>
                    <td><VChip size="x-small" variant="tonal" :color="transferPhaseColor(item.phase)">{{ transferPhaseText(item.phase) }}</VChip></td>
                    <td class="dm-body-text text-no-wrap">{{ item.waited_minutes }} 分钟</td>
                    <td>
                      <div class="d-flex flex-wrap ga-1">
                        <VChip v-if="item.fallback" size="x-small" variant="tonal" color="warning">兜底</VChip>
                        <VChip v-if="item.skipverify" size="x-small" variant="tonal" color="info">跳过校验</VChip>
                        <VChip v-if="item.autostart" size="x-small" variant="tonal" color="primary">自动开始</VChip>
                        <VChip v-if="item.delete_source" size="x-small" variant="tonal" color="error">删源种</VChip>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </VTable>
            </div>

            <div class="dm-section-title mt-4">最近记录</div>
            <div data-record-state="transfer" :aria-busy="recordStates.transfer.loading">
              <p v-if="recordStates.transfer.loading && (recordStates.transfer.loaded || transferRecords.length)" role="status" class="dm-hint">正在刷新记录，保留上次结果</p>
              <div class="dm-table-scroll dm-desktop-table mt-2">
                <VTable density="compact" class="dm-table">
                  <thead>
                    <tr>
                      <th class="dm-table-head">源 → 目的</th>
                      <th class="dm-table-head">种子</th>
                      <th class="dm-table-head">状态</th>
                      <th class="dm-table-head">更新时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="!transferRecords.length || recordStates.transfer.error"><td colspan="4"><TableState v-bind="recordTableState('transfer', transferRecords)" @retry="refreshActive()" /></td></tr>
                    <tr v-for="record in transferRecords" :key="`${record.source_downloader}-${record.source_hash}-${record.downloader}`">
                      <td class="dm-body-text">{{ record.source_downloader }} → {{ record.downloader }}</td>
                      <td class="dm-body-text dm-ellipsis" :title="record.source_hash">{{ transferPrimaryText(record) }}<span class="dm-hint"> · {{ transferSecondaryText(record) }}</span></td>
                      <td>
                        <div class="d-flex flex-wrap ga-1 align-center">
                          <VChip size="x-small" variant="tonal" :color="transferPhaseColor(record.phase)">{{ transferPhaseText(record.phase) }}</VChip>
                          <VChip v-if="record.delete_source" size="x-small" variant="tonal" color="error">已删源</VChip>
                          <VChip v-if="record.hr_protected" size="x-small" variant="tonal" color="info">H&R 保护</VChip>
                          <VChip v-if="record.fallback" size="x-small" variant="tonal" color="warning">兜底</VChip>
                        </div>
                      </td>
                      <td class="dm-body-text text-no-wrap">{{ formatTimestamp(record.updated_at) }}</td>
                    </tr>
                  </tbody>
                </VTable>
              </div>
              <div class="dm-mobile-list mt-2">
                <TableState v-bind="recordTableState('transfer', transferRecords)" @retry="refreshActive()" />
                <article v-for="record in transferRecords" :key="`m-${record.source_downloader}-${record.source_hash}-${record.downloader}`" class="dm-record-card">
                  <div class="d-flex align-center justify-space-between ga-2">
                    <strong class="dm-body-text dm-ellipsis">{{ record.source_downloader }} → {{ record.downloader }}</strong>
                    <VChip size="x-small" variant="tonal" :color="transferPhaseColor(record.phase)">{{ transferPhaseText(record.phase) }}</VChip>
                  </div>
                  <div class="dm-hint mt-1">{{ transferPrimaryText(record) }} · {{ transferSecondaryText(record) }} · {{ formatTimestamp(record.updated_at) }}</div>
                </article>
              </div>
            </div>
            <div v-if="transferRecords.length && (transferStatus.total_pages || 1) > 1" class="d-flex align-center justify-center ga-2 mt-2">
              <VBtn size="small" aria-label="上一页" variant="text" icon="mdi-chevron-left" :disabled="transferPage <= 1" @click="changeTransferPage(transferPage - 1)" />
              <span class="dm-hint">{{ transferStatus.page || 1 }} / {{ transferStatus.total_pages || 1 }}</span>
              <VBtn size="small" aria-label="下一页" variant="text" icon="mdi-chevron-right" :disabled="transferPage >= (transferStatus.total_pages || 1)" @click="changeTransferPage(transferPage + 1)" />
            </div>
          </div>

          <div v-if="activeTab === 'sitetag'" class="dm-record-block mt-3" data-record-block="tag-cleanup">
            <div class="dm-record-block-head">
              <div>
                <div class="dm-record-block-title">标签清理</div>
                <div class="dm-hint">扫描所选 qBittorrent 下载器的标签，勾选保留项后清理其余标签。</div>
              </div>
            </div>
            <ModuleDetailPanel v-if="moduleDetailVisible('tagcleanup')" class="mt-3" title="标签清理明细"
              :rows="moduleDetail('tagcleanup').rows" v-bind="moduleDetail('tagcleanup')"
            />
            <div class="dm-cleanup-toolbar mt-2">
              <VSelect density="compact" v-model="cleanupDownloaders" label="下载器" variant="outlined" hide-details
                :items="qbDownloaderItems" multiple chips closable-chips class="dm-cleanup-select" />
              <VBtn size="small" color="primary" variant="tonal" prepend-icon="mdi-radar" :loading="cleanupScanning"
                :disabled="!cleanupDownloaders.length" @click="scanCleanupTags">扫描标签</VBtn>
            </div>

            <VAlert v-if="cleanupMessage" :type="cleanupStatus" variant="tonal" density="compact" closable class="mt-3"
              @click:close="cleanupMessage = ''">{{ cleanupMessage }}</VAlert>

            <div v-if="!cleanupScan && !cleanupMessage" class="dm-state text-center dm-hint">尚未扫描标签，请选择下载器后点击「扫描标签」</div>
            <div v-if="cleanupScan" class="dm-cleanup-results mt-4">
              <div class="dm-cleanup-summary">
                <div>
                  <div class="dm-section-title">扫描结果</div>
                  <div class="dm-hint">
                    {{ cleanupGroups.length }} 个下载器 · 自动清理 {{ cleanupAutoRemovedCount }} 个临时标签
                  </div>
                </div>
                <div class="d-flex ga-1 flex-wrap justify-end">
                  <VBtn size="small" variant="text" prepend-icon="mdi-check-all" @click="setAllCleanupTags(true)">全部保留</VBtn>
                  <VBtn size="small" variant="text" color="warning" prepend-icon="mdi-checkbox-blank-outline"
                    @click="setAllCleanupTags(false)">取消全选</VBtn>
                </div>
              </div>

              <VAlert v-for="item in cleanupScan.errors || []" :key="`${item.downloader}-${item.message}`"
                type="warning" variant="tonal" density="compact" class="mb-2">
                {{ item.downloader }} · {{ item.message }}
              </VAlert>

              <div v-for="group in cleanupGroups" :key="group.name" class="dm-tag-group">
                <div class="dm-tag-group-head">
                  <div class="d-flex align-center ga-2 min-w-0">
                    <VIcon icon="mdi-download-network-outline" size="19" color="primary" />
                    <strong class="dm-body-text">{{ group.name }}</strong>
                  </div>
                  <span class="dm-hint">{{ group.task_count }} 个任务 · {{ group.tags.length }} 个标签</span>
                </div>

                <div v-if="!group.tags.length" class="dm-monitor-empty dm-hint">
                  <VIcon icon="mdi-tag-check-outline" size="28" color="success" />
                  <span>没有待选择标签</span>
                </div>
                <div v-else class="dm-tag-list">
                  <label v-for="item in group.tags" :key="`${group.name}-${item.tag}`" class="dm-tag-row">
                    <VCheckboxBtn v-model="cleanupKeep[tagSelectionKey(group.name, item.tag)]" color="success" />
                    <div class="dm-tag-content">
                      <div class="dm-tag-line">
                        <span class="dm-tag-name" :title="item.tag">{{ item.tag }}</span>
                        <VChip size="x-small" variant="tonal" :color="cleanupKindMeta(item.kind).color">
                          {{ cleanupKindMeta(item.kind).label }}
                        </VChip>
                        <span class="dm-hint">{{ item.count }} 个任务</span>
                      </div>
                      <div class="dm-tag-samples dm-hint" :title="(item.samples || []).join(' · ')">{{ (item.samples || []).join(' · ') }}</div>
                    </div>
                  </label>
                </div>
              </div>

              <div class="dm-cleanup-actions">
                <div class="dm-hint">
                  待清理 {{ cleanupRemovals.length }} 个标签 · {{ cleanupRemovalAssociations }} 条任务关联
                </div>
                <VBtn size="small" color="warning" variant="tonal" prepend-icon="mdi-eye-outline"
                  :disabled="!cleanupRemovals.length" @click="previewCleanupTags">预览标签清理</VBtn>
              </div>
            </div>
          </div>

          <section v-if="activeTab === 'diagnostics'" class="dm-runtime-section mt-4" data-runtime-section="upload-limit">
            <div class="dm-section-heading">
              <div>
                <div class="dm-section-title">运行详情</div>
                <div class="dm-hint">上传限速运行状态；下载器与站点明细见「上传限速」模块卡的展开详情。</div>
              </div>
            </div>
            <div class="dm-runtime-heading mt-2">
              <div>
                <div class="dm-runtime-title">上传限速</div>
                <div class="dm-hint">MP 或插件离线时，下载器继续保留最后一次已写入的限速。</div>
              </div>
              <div class="dm-runtime-actions">
                <VChip size="small" :color="uploadLimitStatus.color" variant="tonal">{{ uploadLimitStatus.label }}</VChip>
                <VBtn size="small" variant="text" class="text-none" @click="selectTab('upload')">查看明细</VBtn>
              </div>
            </div>

            <VAlert v-for="runtimeError in uploadLimit.errors || []" :key="runtimeError" type="error" variant="tonal" density="compact" class="mt-3">
              {{ runtimeError }}
            </VAlert>
            <div class="dm-upload-summary mt-3">
              <div class="dm-monitor-metric"><span>服务</span><strong>{{ uploadLimitStatus.label }}</strong></div>
              <div class="dm-monitor-metric"><span>实时速率</span><strong>{{ formatUploadRate(uploadLimit.upload_rate_bps) }}</strong></div>
              <div class="dm-monitor-metric"><span>受限任务</span><strong>{{ uploadLimit.managed_torrents || 0 }}</strong></div>
              <div class="dm-monitor-metric"><span>宽限任务</span><strong>{{ uploadLimit.grace_torrents || 0 }}</strong></div>
            </div>
            <div class="dm-hint mt-2">实时速率是下载器当前实际上传流量；站点额度是插件写入单种限速的合计值，两者不是同一指标。</div>
          </section>

          <section v-if="activeTab === 'diagnostics'" class="dm-pane mt-4">
            <div class="dm-section-heading">
              <div>
                <div class="dm-section-title">诊断</div>
                <div class="dm-hint">按运行链路顺序检查下载器、路径、转移、命名、标签和归档状态。</div>
              </div>
            </div>
            <div v-if="diagnostics" class="dm-diagnostics mt-2">
              <div class="dm-stat-grid mb-3">
                <div class="dm-stat">
                  <div class="dm-hint">版本</div>
                  <div class="dm-section-title">{{ diagnostics?.plugin?.version }}</div>
                </div>
                <div class="dm-stat">
                  <div class="dm-hint">源下载器</div>
                  <DownloaderBadge class="dm-section-title" :name="diagnostics?.downloaders?.from?.name || '未配置'"
                    :type="diagnostics?.downloaders?.from?.type" />
                  <VChip size="x-small" :color="diagnostics?.downloaders?.from?.available ? 'success' : 'warning'" variant="tonal">{{ diagnostics?.downloaders?.from?.message }}</VChip>
                </div>
                <div class="dm-stat">
                  <div class="dm-hint">目标下载器</div>
                  <DownloaderBadge class="dm-section-title" :name="diagnostics?.downloaders?.to?.name || '未配置'"
                    :type="diagnostics?.downloaders?.to?.type" />
                  <VChip size="x-small" :color="diagnostics?.downloaders?.to?.available ? 'success' : 'warning'" variant="tonal">{{ diagnostics?.downloaders?.to?.message }}</VChip>
                </div>
                <div class="dm-stat">
                  <div class="dm-hint">补刀归档</div>
                  <div class="dm-section-title">{{ diagnostics?.rename_archive?.archived || 0 }} 条</div>
                  <div class="dm-hint">连续失败 {{ diagnostics?.rename_archive?.active_failed || 0 }} · 阈值 {{ diagnostics?.rename_archive?.threshold || 3 }}</div>
                </div>
              </div>

              <div class="dm-diagnostics-panel mb-3">
                <div class="dm-diagnostics-head">
                  <div class="dm-diagnostics-title">
                    <span class="dm-diagnostics-icon"><VIcon icon="mdi-stethoscope" size="20" /></span>
                    <span>运行诊断</span>
                  </div>
                  <div class="dm-diagnostics-score">
                    <strong>{{ diagnosticsOkCount }} / {{ diagnosticsCards.length }}</strong>
                    <span>正常</span>
                    <span v-if="diagnosticsAttentionCount">· {{ diagnosticsAttentionCount }} 项关注</span>
                  </div>
                </div>
                <div class="dm-diagnostics-grid">
                  <div v-for="item in diagnosticsCards" :key="item.label" class="dm-diagnostic-card" :class="`dm-diagnostic-card--${item.status || 'off'}`">
                    <div class="dm-diagnostic-state">
                      <VIcon :icon="item.icon" size="22" />
                    </div>
                    <div class="dm-diagnostic-content">
                      <div class="dm-diagnostic-name">{{ item.label }}</div>
                      <div class="dm-diagnostic-value">{{ item.detail }}</div>
                      <div class="dm-diagnostic-note dm-hint">{{ item.statusText }}</div>
                    </div>
                  </div>
                </div>
                <div class="dm-diagnostics-footer dm-hint">
                  <span>按运行链路顺序检查下载器、路径、转移、命名、标签和归档状态。</span>
                  <span v-if="diagnosticsAttentionCount" class="dm-diagnostics-attention">关注项不阻断运行</span>
                </div>
              </div>

              <div>
                <div class="dm-section-title mb-2">最近失败</div>
                <div v-if="!diagnostics?.rename_history?.recent_failures?.length" class="dm-hint py-2">暂无失败记录</div>
                <div v-else class="dm-table-scroll">
                  <VTable density="compact" class="dm-table">
                    <thead>
                      <tr>
                        <th class="dm-table-head">时间</th>
                        <th class="dm-table-head">名称</th>
                        <th class="dm-table-head">原因</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="item in diagnostics.rename_history.recent_failures" :key="item.hash">
                        <td class="dm-body-text text-no-wrap">{{ item.time }}</td>
                        <td class="dm-body-text dm-ellipsis" :title="item.name">{{ item.name }}</td>
                        <td class="dm-body-text">{{ item.reason }}</td>
                      </tr>
                    </tbody>
                  </VTable>
                </div>
              </div>

              <div class="dm-record-block mt-3" data-record-block="module-data-cleanup">
                <div class="dm-record-block-head">
                  <div>
                    <div class="dm-record-block-title">数据清理</div>
                    <div class="dm-hint">
                      只清理插件自身的历史与统计，不修改下载器任务与文件、H&amp;R 安全状态、活动队列与限速恢复状态。
                    </div>
                  </div>
                </div>
                <div class="dm-cleanup-list mt-2">
                  <div v-for="(target, key) in CLEANUP_TARGETS" :key="key" class="dm-cleanup-row">
                    <div class="dm-cleanup-info">
                      <span class="dm-body-text">{{ target.label }}</span>
                      <span class="dm-hint">{{ target.detail }} · {{ cleanupCounts[key] || 0 }} 条</span>
                    </div>
                    <VBtn size="small" variant="tonal" color="warning" prepend-icon="mdi-delete-sweep-outline"
                      :text="`清理`" :disabled="!(cleanupCounts[key] > 0)" @click="openCleanupDialog(key)" />
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="dm-state text-center dm-hint">
              <VIcon icon="mdi-stethoscope" size="48" color="grey-lighten-1" class="mb-2" />
              <div>点击刷新诊断</div>
            </div>
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
            <VBtn size="small" variant="text" :disabled="moduleRunning === 'transfer-run'" @click="transferRunDialog = false">取消</VBtn>
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
            <VBtn size="small" variant="text" :disabled="cleanupRunning" @click="cleanupConfirmDialog = false">取消</VBtn>
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
            <VBtn size="small" variant="text" :disabled="hrClearing" @click="hrClearDialog = false">取消</VBtn>
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
            <VBtn size="small" variant="text" :disabled="cleanupExecuting" @click="cleanupDialog = false">取消</VBtn>
            <VBtn size="small" color="error" variant="flat" prepend-icon="mdi-tag-remove-outline" :loading="cleanupExecuting"
              @click="executeCleanupTags">删除标签</VBtn>
          </VCardActions>
        </VCard>
      </VDialog>
  </div>
</template>

<style scoped>
.dm-page {
  height: clamp(760px, calc(100dvh - 48px), 860px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.dm-toolbar { position: sticky; top: 0; z-index: 10; background: transparent; }
.dm-layout { flex: 1 1 auto; min-height: 0; display: flex; }
.dm-side { width: 160px; flex: 0 0 160px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), 0.02); }
.dm-side-list { width: 100%; }
.dm-side-item { margin: 2px 8px; }
.dm-main { flex: 1 1 auto; min-width: 0; min-height: 0; padding: 12px; overflow-y: auto; }
.dm-pane { min-width: 0; min-height: 100%; }
.dm-overview-pane { min-height: auto; }
.dm-state { min-height: 240px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.dm-table-scroll { width: 100%; overflow-x: auto; overflow-y: hidden; }
.dm-table { min-width: 720px; }

.dm-ellipsis { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dm-mobile-list { display: none; }
.dm-overview-band { min-width: 0; }
.dm-overview-section { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; padding: 10px 12px; min-width: 0; }
.dm-flow { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; margin-top: 8px; }
.dm-flow-block { min-width: 0; }
.dm-flow-block:first-child { grid-column: 1 / -1; }
.dm-flow-label {margin-bottom: 5px; font-size: var(--dm-text-section-size); font-weight: var(--dm-text-section-weight); line-height: var(--dm-text-section-line-height); color: var(--dm-text-section-color);}
.dm-flow-row {display: flex; flex-wrap: wrap; align-items: center; gap: 5px; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
.dm-flow-step { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 999px; padding: 5px 9px; background: rgba(var(--v-theme-on-surface), 0.02); white-space: nowrap; }
.dm-flow-arrow { flex: 0 0 auto; color: rgba(var(--v-theme-on-surface), 0.44); }
.dm-detail-limit-select { flex: 0 0 auto; width: 132px; }
.dm-overview-stat-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.dm-overview-stat {
  min-width: 0;
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding: 11px 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 9px;
  background: rgba(var(--v-theme-on-surface), 0.018);
}
.dm-overview-stat--warning { border-color: rgba(var(--v-theme-warning), 0.34); background: rgba(var(--v-theme-warning), 0.065); }
.dm-overview-stat--error { border-color: rgba(var(--v-theme-error), 0.4); background: rgba(var(--v-theme-error), 0.075); }
.dm-overview-stat-content { min-width: 0; }
.dm-overview-stat-label { font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-overview-stat-value {margin-top: 2px; overflow-wrap: anywhere; font-size: var(--dm-text-title-size); font-weight: var(--dm-text-title-weight); line-height: var(--dm-text-title-line-height); color: var(--dm-text-title-color);}
.dm-overview-stat-desc {margin-top: 3px; overflow-wrap: anywhere; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; min-width: 0; }
.dm-break-text { overflow-wrap: anywhere; }
.dm-attention-panel {
  padding: 12px;
  border: 1px solid rgba(var(--v-theme-warning), 0.3);
  border-radius: 9px;
  background: rgba(var(--v-theme-warning), 0.045);
}
.dm-attention-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }
.dm-attention-item { min-width: 0; display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 8px; align-items: start; padding: 9px 10px; border-radius: 8px; background: rgba(var(--v-theme-on-surface), 0.025); }
.dm-attention-item strong { font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
.dm-attention-item--linked { cursor: pointer; }
.dm-attention-item--linked:hover { background: rgba(var(--v-theme-warning), 0.14); }
.dm-module-section { min-width: 0; }
.dm-module-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(268px, 1fr)); gap: 8px; align-items: stretch; }
.dm-module-card {
  min-width: 0;
  scroll-margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 11px 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 9px;
  background: rgba(var(--v-theme-on-surface), 0.018);
}
/* Composition only: ModuleHeader owns all title, icon, status and badge styles. */
.dm-card-heading { display: flex; flex-wrap: wrap; align-items: flex-start; gap: 8px; min-width: 0; }
.dm-card-heading > :first-child { flex: 1 1 200px; min-width: 0; max-width: 100%; }
.dm-card-data-link { flex: 0 0 auto; white-space: nowrap; }
.dm-module-head { display: grid; grid-template-columns: 30px minmax(0, 1fr); gap: 9px; align-items: start; min-width: 0; }
.dm-module-title {min-width: 0; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-module-value {margin-top: 1px; overflow-wrap: anywhere; font-size: var(--dm-text-title-size); font-weight: var(--dm-text-title-weight); line-height: var(--dm-text-title-line-height); color: var(--dm-text-title-color);}
.dm-module-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: auto; }
.dm-module-detail { margin-top: 8px; padding-top: 9px; border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.dm-module-detail-title {margin-bottom: 6px; font-size: var(--dm-text-section-size); font-weight: var(--dm-text-section-weight); line-height: var(--dm-text-section-line-height); color: var(--dm-text-section-color);}
.dm-module-detail-grid { display: grid; gap: 5px; }
.dm-module-detail-row {display: grid; grid-template-columns: minmax(72px, auto) minmax(0, 1fr); gap: 8px; align-items: baseline; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
.dm-module-detail-row span { color: rgba(var(--v-theme-on-surface), 0.56); }
.dm-module-detail-row strong {overflow-wrap: anywhere; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
.dm-record-block {
  min-width: 0;
  padding: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 9px;
  background: rgba(var(--v-theme-on-surface), 0.018);
}
.dm-record-block-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; min-width: 0; }
.dm-cleanup-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dm-cleanup-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 4px;
  border-bottom: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity));
}

.dm-cleanup-row:last-child {
  border-bottom: none;
}

.dm-cleanup-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.dm-record-block-title { font-size: var(--dm-text-section-size); font-weight: var(--dm-text-section-weight); line-height: var(--dm-text-section-line-height); color: var(--dm-text-section-color);}
.dm-record-block .dm-state { min-height: 160px; }
.dm-runtime-section {
  padding: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 9px;
  background: rgba(var(--v-theme-on-surface), 0.018);
}
.dm-runtime-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.dm-runtime-title { font-size: var(--dm-text-section-size); font-weight: var(--dm-text-section-weight); line-height: var(--dm-text-section-line-height); color: var(--dm-text-section-color);}
.dm-runtime-actions { display: flex; align-items: center; justify-content: flex-end; gap: 4px; flex: 0 0 auto; }
.dm-upload-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.dm-monitor-metric { min-width: 0; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-monitor-metric span {display: block; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-monitor-metric strong {display: block; margin-top: 3px; overflow-wrap: anywhere; font-size: var(--dm-text-title-size); font-weight: var(--dm-text-title-weight); line-height: var(--dm-text-title-line-height); color: var(--dm-text-title-color);}
.dm-monitor-empty {display: flex; min-height: 64px; align-items: center; justify-content: center; gap: 8px; border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-upload-status-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.dm-upload-status-card { min-width: 0; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-upload-status-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; min-width: 0; }
.dm-upload-values {display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 5px 12px; margin-top: 10px; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
.dm-upload-values span { min-width: 0; overflow-wrap: anywhere; }
.dm-upload-site-status { display: grid; gap: 10px; }
.dm-upload-site-status-row { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(102px, auto) minmax(112px, auto) minmax(124px, auto); gap: 10px; align-items: center; min-width: 0; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-upload-site-status-row > span { min-width: 0; overflow-wrap: anywhere; }
.dm-record-card {
  min-width: 0;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  padding: 10px;
  background: rgba(var(--v-theme-on-surface), 0.02);
}
.dm-record-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}
.dm-record-title {flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
.dm-record-status {
  flex: 0 0 auto;
  max-width: 52%;
  height: auto;
  min-height: 22px;
  align-self: flex-start;
  white-space: normal;
}
.dm-record-status :deep(.v-chip__content) {
  overflow: visible;
  text-overflow: clip;
  white-space: normal;
  line-height: var(--dm-text-badge-line-height);
  word-break: keep-all;
}
.dm-record-meta {
  display: grid;
  gap: 7px;
  margin-top: 10px;
}
.dm-record-row {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
}
.dm-record-label {white-space: nowrap; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-record-value {min-width: 0;
  overflow-wrap: anywhere; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
.dm-record-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.dm-stat-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.dm-stat { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; padding: 10px; min-width: 0; }
.dm-diagnostics-panel {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
  overflow: hidden;
  background: rgba(var(--v-theme-on-surface), 0.02);
}
.dm-diagnostics-head {
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.dm-diagnostics-title {display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0; font-size: var(--dm-text-section-size); font-weight: var(--dm-text-section-weight); line-height: var(--dm-text-section-line-height); color: var(--dm-text-section-color);}
.dm-diagnostics-icon {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: 8px;
  color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), 0.12);
}
.dm-diagnostics-score {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  color: rgba(var(--v-theme-on-surface), 0.68);
  font-size: var(--dm-text-help-size);
  font-weight: var(--dm-text-help-weight);
  line-height: var(--dm-text-help-line-height);
  white-space: nowrap;
}
.dm-diagnostics-score strong { font-size: var(--dm-text-title-size); font-weight: var(--dm-text-title-weight); line-height: var(--dm-text-title-line-height); color: var(--dm-text-title-color);}
.dm-diagnostics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding: 12px;
}
.dm-diagnostic-card {
  min-height: 96px;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.025);
}
.dm-diagnostic-card--ok {
  background: linear-gradient(135deg, rgba(var(--v-theme-success), 0.08), rgba(var(--v-theme-on-surface), 0.025) 54%);
}
.dm-diagnostic-card--warn {
  border-color: rgba(var(--v-theme-warning), 0.28);
  background: linear-gradient(135deg, rgba(var(--v-theme-warning), 0.12), rgba(var(--v-theme-on-surface), 0.025) 54%);
}
.dm-diagnostic-card--error {
  border-color: rgba(var(--v-theme-error), 0.32);
  background: linear-gradient(135deg, rgba(var(--v-theme-error), 0.12), rgba(var(--v-theme-on-surface), 0.025) 54%);
}
.dm-diagnostic-state {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: rgba(var(--v-theme-on-surface), 0.58);
  background: rgba(var(--v-theme-on-surface), 0.055);
}
.dm-diagnostic-card--ok .dm-diagnostic-state {
  color: rgb(var(--v-theme-success));
  background: rgba(var(--v-theme-success), 0.14);
}
.dm-diagnostic-card--warn .dm-diagnostic-state {
  color: rgb(var(--v-theme-warning));
  background: rgba(var(--v-theme-warning), 0.16);
}
.dm-diagnostic-card--error .dm-diagnostic-state {
  color: rgb(var(--v-theme-error));
  background: rgba(var(--v-theme-error), 0.16);
}
.dm-diagnostic-content {
  min-width: 0;
}
.dm-diagnostic-name {overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap; font-size: var(--dm-text-section-size); font-weight: var(--dm-text-section-weight); line-height: var(--dm-text-section-line-height); color: var(--dm-text-section-color);}
.dm-diagnostic-value {margin-top: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
.dm-diagnostic-note {margin-top: 5px; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-diagnostics-footer {min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 12px;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-diagnostics-attention {
  color: rgb(var(--v-theme-warning));
  white-space: nowrap;
}
.dm-cleanup-toolbar { display: flex; align-items: center; gap: 10px; }
.dm-cleanup-select { flex: 1 1 auto; min-width: 0; }
.dm-cleanup-results { display: grid; gap: 10px; }
.dm-cleanup-summary { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.dm-tag-group { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; overflow: hidden; }
.dm-tag-group-head { min-height: 42px; display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 12px; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), 0.02); }
.dm-tag-list { max-height: 280px; overflow-y: auto; }
.dm-tag-row { min-height: 54px; display: flex; align-items: center; gap: 4px; padding: 6px 10px; border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * 0.7)); cursor: pointer; }
.dm-tag-row:last-child { border-bottom: none; }
.dm-tag-row:hover { background: rgba(var(--v-theme-primary), 0.05); }
.dm-tag-content { flex: 1 1 auto; min-width: 0; }
.dm-tag-line { display: flex; align-items: center; gap: 7px; min-width: 0; }
.dm-tag-name {min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
.dm-tag-samples {margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-cleanup-actions { position: sticky; bottom: -18px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 0 0; background: rgb(var(--v-theme-surface)); }
.dm-cleanup-preview-list { max-height: 360px; overflow-y: auto; }
@media (max-width: 1100px) {
  .dm-overview-stat-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .dm-diagnostics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 760px) {
  .dm-page { height: min(860px, calc(100dvh - 16px)); }
  .dm-layout { flex-direction: column; }
  .dm-side {
    width: 100%;
    flex: 0 0 auto;
    border-right: none;
    border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
  }
  .dm-side::-webkit-scrollbar { display: none; }
  .dm-side-list {
    display: flex;
    flex-wrap: nowrap;
    gap: 6px;
    min-width: max-content;
    padding: 8px 12px !important;
  }
  .dm-side-item {
    flex: 0 0 auto;
    min-width: 96px;
    margin: 0;
    padding-inline: 10px;
  }
  .dm-side-item :deep(.v-list-item-title) { white-space: nowrap; }
  .dm-main { padding: 10px; }
  .dm-desktop-table { display: none; }
  .dm-mobile-list { display: grid; gap: 10px; }
  .dm-record-title {white-space: normal;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
  .dm-record-actions :deep(.v-btn) {
    flex: 1 1 72px;
    max-width: 128px;
  }
  .dm-overview-stat-grid { grid-template-columns: 1fr; }
  .dm-module-grid { grid-template-columns: 1fr; }
  .dm-attention-list { grid-template-columns: 1fr; }
  .dm-section-heading { align-items: stretch; flex-direction: column; }
  .dm-record-block-head { align-items: stretch; flex-direction: column; }
  .dm-runtime-heading { align-items: stretch; flex-direction: column; }
  .dm-runtime-actions { justify-content: space-between; }
  .dm-upload-summary, .dm-upload-status-grid, .dm-upload-site-status-row { grid-template-columns: 1fr; }
  .dm-upload-values {grid-template-columns: 1fr; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
  .dm-stat-grid { grid-template-columns: 1fr; }
  .dm-cleanup-toolbar { flex-direction: column; align-items: stretch; }
  .dm-cleanup-summary { flex-direction: column; align-items: flex-start; }
  .dm-diagnostics-head {
    align-items: flex-start;
    flex-direction: column;
  }
  .dm-diagnostics-score {
    white-space: normal;
  }
  .dm-diagnostics-grid {
    grid-template-columns: 1fr;
    gap: 8px;
    padding: 10px;
  }
  .dm-diagnostic-card {
    min-height: 86px;
  }
  .dm-diagnostics-footer {align-items: flex-start;
    flex-direction: column; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
  .dm-diagnostics-attention {
    white-space: normal;
  }
}
@media (max-width: 420px) {
  .dm-overview-stat-grid { gap: 6px; }
  .dm-module-head { grid-template-columns: 26px minmax(0, 1fr); gap: 7px; }
}
</style>
