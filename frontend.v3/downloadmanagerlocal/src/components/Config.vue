<script setup>
import { reactive, ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { getPluginApi, postPluginJsonApi } from './api'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'DownloadManagerLocal' },
  sourcePluginId: { type: String, default: 'DownloadManagerLocal' },
})
const emit = defineEmits(['save', 'close', 'switch'])
const getApi = (path, options = {}) => getPluginApi(props.api, props.pluginId, path, options)
const postJsonApi = (path, payload = {}, options = {}) => postPluginJsonApi(props.api, props.pluginId, path, payload, options)

const form = reactive({})
const activeMain = ref('overview')
const activeSub = ref('overview')
const downloaderItems = ref([])
const siteItems = ref([])
const hrSkipStats = ref({})
const overview = ref(null)
const cleanupDownloaders = ref([])
const cleanupScan = ref(null)
const cleanupKeep = reactive({})
const cleanupScanning = ref(false)
const cleanupExecuting = ref(false)
const cleanupDialog = ref(false)
const cleanupMessage = ref('')
const cleanupStatus = ref('info')
const uploadSiteItems = ref([])
const uploadScanningSites = ref(false)
const uploadActionRunning = ref('')
const uploadMessage = ref('')
const uploadMessageStatus = ref('info')
const uploadRestoreDialog = ref(false)
const UPLOAD_STATUS_REFRESH_INTERVAL_MS = 30_000
let uploadStatusRefreshTimer = null
let uploadStatusRefreshPending = false
let uploadSiteRulesSaveTail = Promise.resolve()
let uploadSiteRulesRevision = 0
let uploadSiteScanTail = Promise.resolve()
let configDraftRevision = 0
let configDisposed = false

async function refreshOverview() {
  const response = await getApi('overview')
  if (response?.code === 0 || response?.cards) overview.value = response
}

onMounted(async () => {
  try {
    const [dlResp, siteResp, overviewResp] = await Promise.all([
      getApi('downloaders', { feedback: 'silent' }),
      getApi('sites', { feedback: 'silent' }),
      getApi('overview', { feedback: 'silent' }),
    ])
    if (dlResp) {
      downloaderItems.value = dlResp
    }
    if (siteResp) {
      siteItems.value = siteResp
    }
    if (overviewResp?.code === 0 || overviewResp?.cards) overview.value = overviewResp
    try {
      const hrSkipResp = await getApi('hr/skip_stats', { feedback: 'silent' })
      if (hrSkipResp?.skip_stats) hrSkipStats.value = hrSkipResp.skip_stats
    } catch (e) {
      console.error('获取 H&R 跳过计数失败:', e)
    }
  } catch (e) {
    console.error('获取列表失败:', e)
  }
})

const defaults = {
  hr_enabled: false, hr_protection_enabled: true, hr_auto_discover: false,
  hr_enable_site_config: false, hr_onlyonce: false, hr_downloader: [], hr_sites: [],
  hr_notify: 'always', hr_check_period: 10, hr_hit_and_run_tag: 'H&R',
  hr_auto_cleanup_days: 15, hr_notify_summary_cron: '0 8 * * *',
  hr_exclude_tags: [], hr_exclude_categories: [],
  hr_duration: 48, hr_deadline_days: 14, hr_additional_seed_time: 24,
  hr_ratio: null, hr_upload_multiplier: null, hr_upload_gte_download: null,
  hr_active: false, hr_brush_plugin: 'BrushFlow', hr_site_config_str: '',
  remover_enabled: false, remover_notify: false, remover_onlyonce: false,
  remover_action: 'pause', remover_downloaders: [], remover_cron: '0 */12 * * *',
  remover_samedata: false, remover_mponly: false, remover_size: '', remover_ratio: '',
  remover_time: '', remover_upspeed: '', remover_labels: '', remover_pathkeywords: '',
  remover_trackerkeywords: '', remover_errorkeywords: '', remover_torrentstates: '',
  remover_torrentcategorys: '',
  failcleanup_enabled: false, failcleanup_notify: true, failcleanup_cron: '0 */2 * * *',
  failcleanup_clean_repeat: true, failcleanup_retain_hours: 6,
  rename_notify: false, rename_cron_enabled: false, rename_on_download_added: true,
  rename_downloaders: [], rename_hash_white_list: '', rename_exclude_tags: '已重命名',
  rename_include_tags: '', rename_cron: '', rename_event_debounce_seconds: 3,
  tag_interval_cron: '5 4 * * *', tag_enable_media_tag: false, tag_enable_tag: true,
  tag_enable_category: false, tag_enable_del_tags: false, tag_downloaders: [],
  tag_all_cat: [], tag_all_cat_rename: [], tag_rename_type: false, tag_path_rename: '',
  tag_catprefix: '',
  enabled: false, transfer_enabled: true, delay_minutes: 25, onlyonce: false, notify: false,
  transfer_fallback_enabled: true, transfer_fallback_interval_minutes: 60,
  fromdownloader: '', todownloader: '', frompath: '', topath: '',
  fromtorrentpath: '', nopaths: '', nolabels: '', includelabels: '', includecategory: '',
  transferemptylabel: false, add_torrent_tags: '⏩转种',
  deletesource: false, deleteduplicate: false,
  remainoldcat: false, remainoldtag: false,
  rename_enabled: true,
  rename_movie_format: '[ {{ title }}{% if year %} ({{ year }}){% endif %} ] - {{original_name}}',
  rename_tv_format: '[ {{ title }}{% if year %} ({{ year }}){% endif %}{% if season_episode %} - {{season_episode}}{% endif %} ] - {{original_name}}',
  rename_exclude_dirs: '',
  tag_enabled: true, tag_siteprefix: '🏠', tag_tracker_mappings_str: '',
  seed_autostart: true, seed_skipverify: false,
  seed_check_interval: 60, seed_max_wait_minutes: 120,
  upload_limit_enabled: false, upload_limit_downloaders: [],
  upload_limit_downloader_limits_kib: {}, upload_limit_site_rules: {},
  upload_limit_grace_minutes: 30,
}

const mainTabs = [
  { key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline', desc: '查看下载中心各模块的完整运行链路。' },
  { key: 'transfer', title: '转移做种', icon: 'mdi-transfer', desc: '监听下载完成事件，延迟后自动转移做种到目标下载器。' },
  { key: 'hr', title: 'H&R', icon: 'mdi-timer-alert-outline', desc: '按站点规则跟踪 H&R 做种状态，为破坏性操作提供统一保护。' },
  { key: 'remover', title: '自动删种', icon: 'mdi-delete-clock-outline', desc: '按时间、分享率、体积等条件自动暂停或删除任务。' },
  { key: 'failclean', title: '失败清理', icon: 'mdi-broom', desc: '整理失败时立即清理源文件与下载历史，并定时清理重复残留。' },
  { key: 'rename', title: '命名补刀', icon: 'mdi-rename-box', desc: '转移后自动根据 TMDB 信息命名种子，并支持失败补刀。' },
  { key: 'tag', title: '站点标签', icon: 'mdi-tag-multiple', desc: '转移后自动根据 tracker 域名打站点标签。' },
  { key: 'upload', title: '上传限速', icon: 'mdi-upload-network-outline', desc: '设置下载器全局上传上限，并按需限制指定站点的合计上传速度。' },
]

const subTabs = {
  overview: [{ key: 'overview', title: '运行总览', icon: 'mdi-view-dashboard-outline' }],
  upload: [
    { key: 'upload_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'upload_sites', title: '站点策略', icon: 'mdi-home-outline' },
    { key: 'upload_status', title: '运行状态', icon: 'mdi-pulse' },
  ],
  transfer: [
    { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'filter', title: '筛选条件', icon: 'mdi-filter-variant' },
    { key: 'advanced', title: '高级选项', icon: 'mdi-tune' },
    { key: 'seed_basic', title: '做种校验', icon: 'mdi-check-circle-outline' },
  ],
  hr: [
    { key: 'hr_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'hr_sites', title: '站点规则', icon: 'mdi-home-outline' },
    { key: 'hr_protection', title: '保护开关', icon: 'mdi-shield-check-outline' },
  ],
  remover: [{ key: 'remover_basic', title: '基础设置', icon: 'mdi-tune-variant' }],
  failclean: [{ key: 'failclean_basic', title: '基础设置', icon: 'mdi-tune-variant' }],
  rename: [{ key: 'format', title: '命名格式', icon: 'mdi-format-text' }],
  tag: [
    { key: 'mapping', title: 'Tracker 映射', icon: 'mdi-link-variant' },
    { key: 'tag_cleanup', title: '标签清理', icon: 'mdi-tag-remove-outline' },
  ],
}

const currentMain = computed(() => mainTabs.find(i => i.key === activeMain.value) || mainTabs[0])
const currentSubs = computed(() => subTabs[activeMain.value] || [])
const selectedToDownloaderType = computed(() => {
  const selected = downloaderItems.value.find(item => item.value === form.todownloader)
  return selected?.type || ''
})
const qbDownloaderItems = computed(() => downloaderItems.value.filter(item => item.type === 'qbittorrent'))
const uploadDownloaderItems = computed(() => downloaderItems.value.filter(item => ['qbittorrent', 'transmission'].includes(item.type)))
const uploadSelectedDownloaders = computed(() => {
  const selected = new Set(form.upload_limit_downloaders || [])
  return uploadDownloaderItems.value.filter(item => selected.has(item.value))
})
const uploadMissingLimits = computed(() => uploadSelectedDownloaders.value.filter(
  item => !uploadDownloaderLimit(item.value),
))
const uploadLimit = computed(() => overview.value?.upload_limit || {})
const uploadLimitDownloaderRows = computed(() => uploadLimit.value.downloaders || [])
const uploadLimitSiteRows = computed(() => uploadLimit.value.sites || [])
const uploadSiteRuleRows = computed(() => Object.entries(form.upload_limit_site_rules || {})
  .map(([name, rule]) => ({ name, limit_kib: Number(rule?.limit_kib || 0) || null }))
  .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN')))
const uploadLimitStatus = computed(() => {
  const status = uploadLimit.value.service_status
  return {
    disabled: { label: '未启用', color: 'default' },
    starting: { label: '启动中', color: 'info' },
    running: { label: '分配中', color: 'success' },
    degraded: { label: '部分异常', color: 'warning' },
    error: { label: '状态异常', color: 'error' },
  }[status] || { label: '未启用', color: 'default' }
})
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
const cleanupRemovalAssociations = computed(() => cleanupRemovals.value.reduce((total, item) => total + item.hashes.length, 0))
const hrNotifyModeItems = [
  { title: '不发送', value: 'none' },
  { title: '仅异常', value: 'on_error' },
  { title: '全部', value: 'always' },
]
const removerActionItems = [
  { title: '暂停任务', value: 'pause' },
  { title: '删除任务', value: 'delete' },
  { title: '删除任务及文件', value: 'deletefile' },
]
const hrSkipStatRows = computed(() => [
  { label: '转移源端', value: Number(hrSkipStats.value.transfer_source || 0) },
  { label: '自动删种', value: Number(hrSkipStats.value.auto_remove || 0) },
  { label: '整理失败', value: Number(hrSkipStats.value.transfer_failure || 0) },
])
const runtimeFlows = [
  {
    label: '转移做种',
    steps: ['下载完成', '延迟等待', '目标转移', '公共链路'],
  },
  {
    label: '公共链路',
    steps: ['命名处理', '站点标签', '做种校验'],
  },
  {
    label: '上传限速',
    steps: ['全局限速', '站点识别', '按需设限', '合计限速', '动态调速', '停用恢复'],
  },
  {
    label: '兜底补刀',
    steps: ['异常命名', '兜底补刀', '失败计数', '归档恢复'],
  },
]

watch(() => props.initialConfig, v => {
  configDraftRevision++
  uploadSiteRulesRevision++
  Object.keys(form).forEach(k => delete form[k])
  Object.assign(form, defaults, v || {})
  form.upload_limit_downloaders = [...(v?.upload_limit_downloaders || [])]
  form.upload_limit_downloader_limits_kib = { ...(v?.upload_limit_downloader_limits_kib || {}) }
  form.upload_limit_site_rules = Object.fromEntries(Object.entries(v?.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }]))
  form.hr_downloader = [...(v?.hr_downloader || [])]
  form.hr_sites = [...(v?.hr_sites || [])]
  form.hr_exclude_tags = [...(v?.hr_exclude_tags || [])]
  form.hr_exclude_categories = [...(v?.hr_exclude_categories || [])]
  form.remover_downloaders = [...(v?.remover_downloaders || [])]
  form.rename_downloaders = [...(v?.rename_downloaders || [])]
  form.tag_downloaders = [...(v?.tag_downloaders || [])]
  form.tag_all_cat = [...(v?.tag_all_cat || [])]
  form.tag_all_cat_rename = [...(v?.tag_all_cat_rename || [])]
}, { immediate: true, deep: true })
watch(() => props.pluginId, () => {
  configDraftRevision++
  uploadSiteRulesRevision++
})

function saveConfig() {
  emit('save', {
    ...form,
    upload_limit_downloaders: [...(form.upload_limit_downloaders || [])],
    upload_limit_downloader_limits_kib: { ...(form.upload_limit_downloader_limits_kib || {}) },
    upload_limit_site_rules: Object.fromEntries(Object.entries(form.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }])),
    hr_downloader: [...(form.hr_downloader || [])],
    hr_sites: [...(form.hr_sites || [])],
    hr_exclude_tags: [...(form.hr_exclude_tags || [])],
    hr_exclude_categories: [...(form.hr_exclude_categories || [])],
    remover_downloaders: [...(form.remover_downloaders || [])],
    rename_downloaders: [...(form.rename_downloaders || [])],
    tag_downloaders: [...(form.tag_downloaders || [])],
    tag_all_cat: [...(form.tag_all_cat || [])],
    tag_all_cat_rename: [...(form.tag_all_cat_rename || [])],
  })
}
function selectMain(key) {
  if (activeMain.value === key) return
  activeMain.value = key
  activeSub.value = subTabs[key]?.[0]?.key || ''
}

function uploadDownloaderLimit(downloaderId) {
  const value = Number(form.upload_limit_downloader_limits_kib?.[downloaderId] || 0)
  return value > 0 ? value : null
}

function setUploadDownloaderLimit(downloaderId, value) {
  const mapping = { ...(form.upload_limit_downloader_limits_kib || {}) }
  const normalized = Number(value)
  if (Number.isFinite(normalized) && normalized > 0) mapping[downloaderId] = Math.floor(normalized)
  else delete mapping[downloaderId]
  form.upload_limit_downloader_limits_kib = mapping
}

function formatUploadRate(value) {
  const speed = Number(value || 0)
  if (speed >= 1024 * 1024) return `${(speed / 1024 / 1024).toFixed(2)} MiB/s`
  return `${(speed / 1024).toFixed(1)} KiB/s`
}

function cloneUploadSiteRules(rules = form.upload_limit_site_rules) {
  return Object.fromEntries(Object.entries(rules || {}).map(([name, rule]) => [name, { ...rule }]))
}

function queueUploadSiteRulesSave(rules) {
  const snapshot = cloneUploadSiteRules(rules)
  const revision = ++uploadSiteRulesRevision
  const draftRevision = configDraftRevision
  const pluginId = props.pluginId
  const api = props.api
  const ownsDraft = () => !configDisposed && draftRevision === configDraftRevision && pluginId === props.pluginId
  uploadSiteRulesSaveTail = uploadSiteRulesSaveTail.catch(() => undefined).then(async () => {
    if (!ownsDraft()) return null
    const response = await postPluginJsonApi(api, pluginId, 'upload_limit_site_rules_update', { rules: snapshot })
    if (!ownsDraft()) return null
    if (response?.code !== 0) throw new Error(response?.msg || '站点策略保存失败')
    if (revision === uploadSiteRulesRevision) {
      form.upload_limit_site_rules = cloneUploadSiteRules(response?.rules || snapshot)
      uploadMessageStatus.value = 'success'
      uploadMessage.value = response?.msg || '站点策略已立即生效'
    }
    return response
  }).catch(error => {
    if (!ownsDraft()) return null
    if (revision === uploadSiteRulesRevision) {
      uploadMessageStatus.value = 'error'
      uploadMessage.value = error?.message || '站点策略保存失败'
    }
    throw error
  })
  void uploadSiteRulesSaveTail.catch(() => undefined)
  return uploadSiteRulesSaveTail
}

async function flushUploadSiteRulesSave() {
  await uploadSiteRulesSaveTail
}

function setUploadSiteRule(siteName, value) {
  const rules = Object.fromEntries(Object.entries(form.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }]))
  const current = rules[siteName] || { limit_kib: 0 }
  const limit = Number(value)
  current.limit_kib = Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : 0
  rules[siteName] = current
  form.upload_limit_site_rules = rules
  queueUploadSiteRulesSave(rules)
}

function removeUploadSiteRule(siteName) {
  const rules = Object.fromEntries(Object.entries(form.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }]))
  delete rules[siteName]
  form.upload_limit_site_rules = rules
  queueUploadSiteRulesSave(rules)
}

async function clearUploadSiteRules() {
  uploadActionRunning.value = 'site-rules'
  uploadMessage.value = ''
  const previousRules = Object.fromEntries(Object.entries(form.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }]))
  form.upload_limit_site_rules = {}
  try {
    const response = await queueUploadSiteRulesSave({})
    form.upload_limit_site_rules = {}
    uploadMessageStatus.value = 'success'
    uploadMessage.value = '站点策略已清空并立即生效；所有任务仅受下载器全局上限约束'
  } catch (error) {
    form.upload_limit_site_rules = previousRules
    uploadMessageStatus.value = 'error'
    uploadMessage.value = error?.message || '站点策略清空失败'
  } finally {
    uploadActionRunning.value = ''
  }
}

function applyUploadStatus(response) {
  if (!response || (response.code !== 0 && !response.service_status)) return
  overview.value = { ...(overview.value || {}), upload_limit: response }
}

async function refreshUploadLimitStatus({ silent = false } = {}) {
  if (!silent) {
    uploadActionRunning.value = 'refresh'
    uploadMessage.value = ''
  }
  try {
    const response = await getApi(
      'upload_limit_status',
      silent ? { feedback: 'silent' } : {},
    )
    applyUploadStatus(response)
  } catch (error) {
    if (silent) console.error('上传限速状态自动刷新失败:', error)
    else {
      uploadMessageStatus.value = 'error'
      uploadMessage.value = error?.message || '状态刷新失败'
    }
  } finally {
    if (!silent) uploadActionRunning.value = ''
  }
}

function isUploadStatusVisible() {
  return activeMain.value === 'upload'
    && activeSub.value === 'upload_status'
    && document.visibilityState === 'visible'
}

async function refreshVisibleUploadLimitStatus() {
  if (!isUploadStatusVisible() || uploadStatusRefreshPending || uploadActionRunning.value) return
  uploadStatusRefreshPending = true
  try {
    await refreshUploadLimitStatus({ silent: true })
  } finally {
    uploadStatusRefreshPending = false
  }
}

function stopUploadStatusAutoRefresh() {
  if (!uploadStatusRefreshTimer) return
  window.clearInterval(uploadStatusRefreshTimer)
  uploadStatusRefreshTimer = null
}

function syncUploadStatusAutoRefresh() {
  stopUploadStatusAutoRefresh()
  if (!isUploadStatusVisible()) return
  void refreshVisibleUploadLimitStatus()
  uploadStatusRefreshTimer = window.setInterval(refreshVisibleUploadLimitStatus, UPLOAD_STATUS_REFRESH_INTERVAL_MS)
}

watch([activeMain, activeSub], syncUploadStatusAutoRefresh, { flush: 'post' })

onMounted(() => {
  document.addEventListener('visibilitychange', syncUploadStatusAutoRefresh)
  syncUploadStatusAutoRefresh()
})

onBeforeUnmount(stopUploadStatusAutoRefresh)
onBeforeUnmount(() => {
  configDisposed = true
  configDraftRevision++
  document.removeEventListener('visibilitychange', syncUploadStatusAutoRefresh)
})

async function scanUploadSites() {
  uploadMessage.value = ''
  if (!form.upload_limit_downloaders?.length) {
    uploadMessageStatus.value = 'warning'
    uploadMessage.value = '请先选择限速下载器'
    return
  }
  uploadScanningSites.value = true
  const scanOperation = (async () => {
    await flushUploadSiteRulesSave()
    return postJsonApi('upload_limit_site_tags', {
      downloaders: form.upload_limit_downloaders,
      rules: cloneUploadSiteRules(),
    })
  })()
  uploadSiteScanTail = scanOperation
  try {
    const response = await scanOperation
    uploadSiteItems.value = response?.items || []
    form.upload_limit_site_rules = response?.rules || form.upload_limit_site_rules || {}
    uploadMessageStatus.value = response?.code === 0 ? 'success' : (response?.code === 2 ? 'warning' : 'error')
    uploadMessage.value = response?.msg || `扫描到 ${uploadSiteItems.value.length} 个站点标签，策略已立即生效`
  } catch (error) {
    uploadMessageStatus.value = 'error'
    uploadMessage.value = error?.message || '站点扫描失败'
  } finally {
    if (uploadSiteScanTail === scanOperation) uploadSiteScanTail = Promise.resolve()
    uploadScanningSites.value = false
  }
}

async function reallocateUploadLimits() {
  uploadActionRunning.value = 'reallocate'
  uploadMessage.value = ''
  try {
    await uploadSiteScanTail
    await flushUploadSiteRulesSave()
    const response = await postJsonApi('upload_limit_reallocate', {})
    applyUploadStatus(response)
    uploadMessageStatus.value = response?.code === 0 ? 'success' : (response?.code === 2 ? 'warning' : 'error')
    uploadMessage.value = response?.msg || '上传额度已重新分配'
  } catch (error) {
    uploadMessageStatus.value = 'error'
    uploadMessage.value = error?.message || '重新分配失败'
  } finally {
    uploadActionRunning.value = ''
  }
}

async function disableAndRestoreUploadLimits() {
  uploadActionRunning.value = 'restore'
  uploadMessage.value = ''
  try {
    const response = await postJsonApi('upload_limit_disable_restore', {})
    form.upload_limit_enabled = false
    uploadRestoreDialog.value = false
    await refreshUploadLimitStatus()
    uploadMessageStatus.value = response?.code === 0 ? 'success' : (response?.code === 2 ? 'warning' : 'error')
    uploadMessage.value = response?.msg || '上传限速已停用并恢复'
  } catch (error) {
    uploadMessageStatus.value = 'error'
    uploadMessage.value = error?.message || '停用恢复失败'
  } finally {
    uploadActionRunning.value = ''
  }
}

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
</script>
<template>
  <div class="dm-config">
    <VCard flat class="dm-card">
      <VCardItem class="dm-header">
        <template #prepend>
          <VAvatar color="success" variant="tonal" size="44" rounded="lg">
            <VIcon icon="mdi-download" size="24" />
          </VAvatar>
        </template>
        <VCardTitle class="text-h6">下载中心</VCardTitle>
        <VCardSubtitle class="text-caption">{{ currentMain.desc }}</VCardSubtitle>
        <template #append>
          <VSwitch v-model="form.enabled" color="success" hide-details inset :label="form.enabled ? '已启用' : '已停用'" />
        </template>
      </VCardItem>
      <VDivider />
      <div class="dm-body">
        <nav class="dm-nav">
          <VList density="comfortable" nav class="dm-nav-list py-2">
            <VListItem v-for="item in mainTabs" :key="item.key" :active="activeMain === item.key"
              color="primary" rounded="lg" class="dm-nav-item" @click="selectMain(item.key)">
              <template #prepend><VIcon :icon="item.icon" /></template>
              <VListItemTitle>{{ item.title }}</VListItemTitle>
            </VListItem>
          </VList>
        </nav>
        <section class="dm-content">
          <div class="dm-subtabs">
            <button v-for="sub in currentSubs" :key="sub.key" type="button"
              class="dm-subtab" :class="{ 'dm-subtab--active': activeSub === sub.key }" @click="activeSub = sub.key">
              <VIcon :icon="sub.icon" size="18" class="mr-1" />{{ sub.title }}
            </button>
          </div>
          <VDivider />
          <div class="dm-window" :class="{ 'dm-window--overview': activeMain === 'overview' }">
            <div v-show="activeSub === 'overview'" class="dm-pane dm-pane--overview">
              <div class="dm-overview-section mb-3">
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

            </div>

            <!-- ═══ 上传限速 · 基础设置 ═══ -->
            <div v-show="activeSub === 'upload_basic'" class="dm-pane">
              <div class="dm-section-title">上传限速设置</div>
              <VRow>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.upload_limit_enabled" color="success" inset hide-details label="启用上传限速" />
                </VCol>
                <VCol cols="12" md="8">
                  <VSelect v-model="form.upload_limit_downloaders" label="限速下载器" density="compact" variant="outlined"
                    :items="uploadDownloaderItems" multiple chips closable-chips clearable
                    hint="只扫描和修改这里选中的 qBittorrent / Transmission 实例" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" sm="6" md="4">
                  <VTextField v-model.number="form.upload_limit_grace_minutes" label="新种宽限（分钟）" type="number" min="0" max="1440"
                    density="compact" variant="outlined" hint="默认 30；填 0 表示完成后立即纳入分配" persistent-hint />
                </VCol>
              </VRow>

              <div class="dm-section-title mt-4">下载器总上限</div>
              <div v-if="uploadSelectedDownloaders.length" class="dm-upload-downloader-list">
                <div v-for="item in uploadSelectedDownloaders" :key="item.value" class="dm-upload-config-row">
                  <div class="dm-upload-config-name">
                    <VIcon :icon="item.type === 'transmission' ? 'mdi-transmission-tower' : 'mdi-download-network-outline'" size="19" color="primary" />
                    <div class="min-w-0">
                      <strong>{{ item.title }}</strong>
                      <div class="text-caption text-medium-emphasis">
                        {{ item.type === 'transmission' ? 'Transmission Session 上传上限' : 'qB 普通与备用上传上限' }}
                      </div>
                    </div>
                  </div>
                  <VTextField :model-value="uploadDownloaderLimit(item.value)"
                    @update:model-value="setUploadDownloaderLimit(item.value, $event)"
                    label="总上限（KiB/s）" type="number" min="1" step="1" density="compact" variant="outlined"
                    hint="必须大于 0；以插件配置为准" persistent-hint />
                </div>
              </div>
              <div v-else class="dm-monitor-empty">尚未选择限速下载器</div>

              <VAlert v-if="form.upload_limit_enabled && !uploadSelectedDownloaders.length" type="warning" variant="tonal" density="compact" class="mt-4">
                请至少选择一个 qBittorrent 或 Transmission 下载器，并设置正整数总上限。
              </VAlert>
              <VAlert v-else-if="form.upload_limit_enabled && uploadMissingLimits.length" type="warning" variant="tonal" density="compact" class="mt-4">
                {{ uploadMissingLimits.map(item => item.title).join('、') }} 尚未设置正整数总上限，保存后上传限速不会启动。
              </VAlert>

              <VAlert type="info" variant="tonal" density="compact" class="mt-4">
                单位为 KiB/s（1 Mbps ≈ 122 KiB/s）。宽限期间不做站点和单种分配，但仍受对应下载器总上传上限。
              </VAlert>
            </div>

            <!-- ═══ 上传限速 · 站点策略 ═══ -->
            <div v-show="activeSub === 'upload_sites'" class="dm-pane">
              <div class="dm-upload-toolbar">
                <div>
                  <div class="dm-section-title mb-1">站点限速</div>
                  <div class="text-caption text-medium-emphasis">扫描只添加站点名称，不预填上限；只有填写正数的站点才会限制合计上传速度。</div>
                </div>
                <div class="d-flex align-center ga-2">
                  <VBtn color="primary" variant="tonal" prepend-icon="mdi-radar" :loading="uploadScanningSites"
                    :disabled="uploadActionRunning === 'site-rules' || uploadActionRunning === 'reallocate'"
                    @click="scanUploadSites">扫描站点</VBtn>
                  <VBtn color="error" variant="text" prepend-icon="mdi-delete-sweep-outline"
                    :disabled="!uploadSiteRuleRows.length || uploadScanningSites || uploadActionRunning === 'reallocate'"
                    :loading="uploadActionRunning === 'site-rules'"
                    @click="clearUploadSiteRules">清空策略</VBtn>
                </div>
              </div>

              <VAlert type="info" variant="tonal" density="compact" class="mt-3">
                仅识别唯一有效的「{{ form.tag_siteprefix || '🏠' }}站点名」标签。上限留空或填 0 时不写单种限速，该站点仍受下载器全局上限约束。
              </VAlert>

              <VAlert v-if="uploadMessage" :type="uploadMessageStatus" variant="tonal" density="compact" closable class="mt-3"
                @click:close="uploadMessage = ''">{{ uploadMessage }}</VAlert>

              <div v-if="uploadSiteRuleRows.length" class="dm-upload-site-list mt-4">
                <div v-for="row in uploadSiteRuleRows" :key="row.name" class="dm-upload-site-row">
                  <div class="dm-upload-site-name">
                    <VIcon icon="mdi-home-outline" size="19" color="primary" />
                    <div class="min-w-0">
                      <strong class="text-body-2">{{ row.name }}</strong>
                      <div class="text-caption text-medium-emphasis">{{ form.tag_siteprefix || '🏠' }}{{ row.name }}</div>
                    </div>
                  </div>
                  <VTextField :model-value="row.limit_kib" @update:model-value="setUploadSiteRule(row.name, $event)"
                    label="合计上限（KiB/s）" type="number" min="0" step="1" clearable density="compact" variant="outlined"
                    :disabled="uploadScanningSites || uploadActionRunning === 'site-rules' || uploadActionRunning === 'reallocate'"
                    hint="留空或 0 表示该站点不限速；正数为跨下载器共享的站点合计上限" persistent-hint />
                  <VBtn icon="mdi-delete-outline" size="small" color="error" variant="text" title="删除站点"
                    :disabled="uploadScanningSites || uploadActionRunning === 'site-rules' || uploadActionRunning === 'reallocate'"
                    @click="removeUploadSiteRule(row.name)" />
                </div>
              </div>
              <div v-else class="dm-monitor-empty mt-3">尚未扫描站点；没有站点上限时只应用下载器全局上限</div>

              <VAlert type="info" variant="tonal" density="compact" class="mt-4">
                正数上限限制该站点全部任务的合计上传速度；多个受限站点在下载器全局额度内按实际需求共享可用带宽。
              </VAlert>
            </div>

            <!-- ═══ 上传限速 · 运行状态 ═══ -->
            <div v-show="activeSub === 'upload_status'" class="dm-pane">
              <div class="dm-upload-toolbar">
                <div>
                  <div class="dm-section-title mb-1">运行状态</div>
                  <div class="text-caption text-medium-emphasis">MP 或插件离线时，下载器继续保留最后一次已写入的限速。</div>
                </div>
                <div class="d-flex ga-2 flex-wrap justify-end">
                  <VBtn size="small" variant="text" prepend-icon="mdi-refresh" :loading="uploadActionRunning === 'refresh'"
                    @click="refreshUploadLimitStatus">刷新</VBtn>
                  <VBtn size="small" color="primary" variant="tonal" prepend-icon="mdi-call-split"
                    :loading="uploadActionRunning === 'reallocate'"
                    :disabled="!uploadLimit.enabled || uploadScanningSites || uploadActionRunning === 'site-rules'"
                    @click="reallocateUploadLimits">立即分配</VBtn>
                  <VBtn size="small" color="warning" variant="tonal" prepend-icon="mdi-backup-restore"
                    :disabled="!uploadLimit.active && !uploadLimit.enabled" @click="uploadRestoreDialog = true">停用并恢复</VBtn>
                </div>
              </div>

              <VAlert v-if="uploadMessage" :type="uploadMessageStatus" variant="tonal" density="compact" closable class="mt-3"
                @click:close="uploadMessage = ''">{{ uploadMessage }}</VAlert>
              <VAlert v-for="error in uploadLimit.errors || []" :key="error" type="warning" variant="tonal" density="compact" class="mt-2">
                {{ error }}
              </VAlert>

              <div class="dm-upload-summary mt-4">
                <div class="dm-monitor-metric"><span>服务</span><strong>{{ uploadLimitStatus.label }}</strong></div>
                <div class="dm-monitor-metric"><span>实时速率</span><strong>{{ formatUploadRate(uploadLimit.upload_rate_bps) }}</strong></div>
                <div class="dm-monitor-metric"><span>受限任务</span><strong>{{ uploadLimit.managed_torrents || 0 }}</strong></div>
                <div class="dm-monitor-metric"><span>宽限任务</span><strong>{{ uploadLimit.grace_torrents || 0 }}</strong></div>
              </div>
              <div class="dm-hint mt-2">实时速率是下载器当前实际上传流量；站点额度是插件写入单种限速的合计值，两者不是同一指标。</div>

              <div class="dm-section-title mt-4">下载器状态</div>
              <div v-if="uploadLimitDownloaderRows.length" class="dm-upload-status-grid">
                <div v-for="item in uploadLimitDownloaderRows" :key="item.id" class="dm-upload-status-card">
                  <div class="dm-upload-status-head">
                    <div class="min-w-0">
                      <strong class="text-body-2">{{ item.id }}</strong>
                      <div class="text-caption text-medium-emphasis">{{ item.type === 'transmission' ? 'Transmission' : 'qBittorrent' }}</div>
                    </div>
                    <VChip size="x-small" :color="item.error ? 'warning' : 'success'" variant="tonal">{{ item.error ? '异常' : '正常' }}</VChip>
                  </div>
                  <div class="dm-upload-values">
                    <span>实时 <strong>{{ formatUploadRate(item.upload_rate_bps) }}</strong></span>
                    <span>{{ item.type === 'transmission' ? 'Session 全局上限' : 'QB 全局上限' }} <strong>{{ item.total_limit_kib }} KiB/s</strong></span>
                    <span>受限任务 <strong>{{ item.managed_torrents || 0 }}</strong></span>
                    <span>宽限任务 <strong>{{ item.grace_torrents || 0 }}</strong></span>
                  </div>
                  <div v-if="item.error" class="text-caption text-warning mt-2 dm-break-text">{{ item.error }}</div>
                </div>
              </div>
              <div v-else class="dm-monitor-empty">当前没有启用的限速下载器</div>

              <div class="dm-section-title mt-4">受限站点</div>
              <div v-if="uploadLimitSiteRows.length" class="dm-upload-site-status">
                <div v-for="item in uploadLimitSiteRows" :key="item.key" class="dm-upload-site-status-row">
                  <div class="min-w-0">
                    <strong class="text-body-2">{{ item.name }}</strong>
                    <div class="text-caption text-medium-emphasis">{{ item.torrent_count }} 个任务 · {{ item.downloaders?.join('、') }}</div>
                  </div>
                  <span class="text-caption">实时 <strong>{{ formatUploadRate(item.upload_rate_bps) }}</strong></span>
                  <span class="text-caption">站点额度 <strong>{{ item.allocated_kib }} KiB/s</strong></span>
                  <span class="text-caption">站点上限 <strong>{{ item.limit_kib }} KiB/s</strong></span>
                </div>
              </div>
              <div v-else class="dm-monitor-empty">当前没有填写正数上限的受限站点</div>
            </div>

            <!-- ═══ 转移做种 · 基础设置 ═══ -->
            <div v-show="activeSub === 'basic'" class="dm-pane">
              <div class="dm-section-title">基础设置</div>
              <VRow>
                <VCol cols="12" md="6">
                  <VSelect v-model="form.fromdownloader" label="源下载器" density="compact" variant="outlined" hide-details
                    :items="downloaderItems" hint="选择源下载器" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VSelect v-model="form.todownloader" label="目的下载器" density="compact" variant="outlined" hide-details
                    :items="downloaderItems" hint="选择目的下载器" persistent-hint />
                </VCol>
              </VRow>
              <VAlert
                v-if="form.todownloader && selectedToDownloaderType === 'transmission'"
                type="warning"
                variant="tonal"
                density="compact"
                class="mt-2"
              >
                Transmission 当前不支持种子重命名，命名补刀与恢复原名不会生效；转移做种和做种校验不受影响。
              </VAlert>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VTextField v-model="form.frompath" label="源数据文件根路径" density="compact" variant="outlined" hide-details
                    hint="源下载器中数据的根路径" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VTextField v-model="form.topath" label="目的数据文件根路径" density="compact" variant="outlined" hide-details
                    hint="目标下载器中数据的根路径" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VTextField v-model="form.fromtorrentpath" label="源种子文件路径" density="compact" variant="outlined" hide-details
                    hint="如 BT_backup，留空自动获取" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VTextField v-model="form.add_torrent_tags" label="添加种子标签" density="compact" variant="outlined" hide-details
                    hint="多个以逗号分隔" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.transfer_enabled" color="success" inset hide-details label="启用转移做种" />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.notify" color="info" inset hide-details label="发送通知" />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.onlyonce" color="warning" inset hide-details label="立即运行一次" />
                </VCol>
                <VCol cols="12" md="3">
                  <VTextField v-model.number="form.delay_minutes" label="延迟时间（分钟）" type="number" density="compact" variant="outlined" hide-details
                    hint="下载完成后延迟 N 分钟再转移" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.transfer_fallback_enabled" color="success" inset hide-details label="转移做种兜底服务" />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model.number="form.transfer_fallback_interval_minutes" label="兜底间隔（分钟）" type="number" min="1" density="compact" variant="outlined" hide-details
                    :disabled="!form.transfer_fallback_enabled" hint="事件漏触发时按此间隔扫描，默认60分钟" persistent-hint />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 转移做种 · 筛选条件 ═══ -->
            <div v-show="activeSub === 'filter'" class="dm-pane">
              <div class="dm-section-title">筛选条件</div>
              <VRow>
                <VCol cols="12" md="6">
                  <VTextField v-model="form.includelabels" label="转移种子标签（逗号分隔）" density="compact" variant="outlined" hide-details
                    hint="仅转移包含这些标签的种子" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VTextField v-model="form.nolabels" label="不转移种子标签（逗号分隔）" density="compact" variant="outlined" hide-details
                    hint="跳过包含这些标签的种子" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VTextField v-model="form.includecategory" label="转移种子分类（逗号分隔）" density="compact" variant="outlined" hide-details
                    hint="仅转移这些分类的种子" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VSwitch v-model="form.transferemptylabel" color="info" inset hide-details label="转移无标签种子" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.nopaths" label="不转移数据文件目录（每行一个）" density="compact" variant="outlined" hide-details rows="3" />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 转移做种 · 高级选项 ═══ -->
            <div v-show="activeSub === 'advanced'" class="dm-pane">
              <div class="dm-section-title">高级选项</div>
              <VRow>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.deletesource" color="warning" inset hide-details label="删除源种子" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.deleteduplicate" color="warning" inset hide-details label="删除重复种子" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.remainoldcat" color="info" inset hide-details label="保留原分类" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.remainoldtag" color="info" inset hide-details label="保留原标签" />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ H&R · 基础设置 ═══ -->
            <div v-show="activeSub === 'hr_basic'" class="dm-pane">
              <div class="dm-section-title">H&R 基础设置</div>
              <VRow>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.hr_enabled" color="success" inset hide-details label="启用 H&R" />
                </VCol>
                <VCol cols="12" md="3">
                  <VSelect v-model="form.hr_notify" label="通知模式" density="compact" variant="outlined" hide-details
                    :items="hrNotifyModeItems" hint="不发送 / 仅异常 / 全部" persistent-hint />
                </VCol>
                <VCol cols="12" md="3">
                  <VTextField v-model.number="form.hr_check_period" label="状态检查周期（分钟）" type="number" density="compact" variant="outlined" hide-details
                    hint="默认 10 分钟" persistent-hint />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.hr_onlyonce" color="warning" inset hide-details label="立即运行一次" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="4">
                  <VSelect v-model="form.hr_downloader" label="纳管下载器" density="compact" variant="outlined" hide-details
                    :items="downloaderItems" multiple chips closable-chips clearable hint="选择需要跟踪 H&R 的下载器" persistent-hint />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model="form.hr_hit_and_run_tag" label="H&R 标签" density="compact" variant="outlined" hide-details
                    hint="未达标任务打上的标签，默认 H&R" persistent-hint />
                </VCol>
                <VCol cols="12" md="4">
                  <VCronField v-model="form.hr_notify_summary_cron" label="每日汇总通知周期" density="compact" variant="outlined" hide-details />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.hr_auto_discover" color="info" inset hide-details label="自动发现新任务" />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.hr_enable_site_config" color="info" inset hide-details label="启用站点独立规则" />
                </VCol>
                <VCol cols="12" md="3">
                  <VTextField v-model.number="form.hr_auto_cleanup_days" label="自动清理记录（天）" type="number" density="compact" variant="outlined" hide-details
                    hint="达标/失效记录保留天数，默认 15" persistent-hint />
                </VCol>
                <VCol cols="12" md="3">
                  <VTextField v-model="form.hr_brush_plugin" label="刷流插件名" density="compact" variant="outlined" hide-details
                    hint="刷流任务来源插件名，默认 BrushFlow" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VCombobox v-model="form.hr_exclude_tags" label="排除标签（回车输入）" density="compact" variant="outlined" hide-details
                    multiple chips closable-chips hint="带这些标签的任务不纳入 H&R" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VCombobox v-model="form.hr_exclude_categories" label="排除分类（回车输入）" density="compact" variant="outlined" hide-details
                    multiple chips closable-chips hint="这些分类的任务不纳入 H&R" persistent-hint />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ H&R · 站点规则 ═══ -->
            <div v-show="activeSub === 'hr_sites'" class="dm-pane">
              <div class="dm-section-title">站点规则</div>
              <VRow>
                <VCol cols="12">
                  <VSelect v-model="form.hr_sites" label="站点白名单" density="compact" variant="outlined" hide-details
                    :items="siteItems" multiple chips closable-chips clearable hint="只跟踪这些站点的种子；留空表示全部站点" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="4">
                  <VTextField v-model.number="form.hr_duration" label="全局做种时长（小时）" type="number" density="compact" variant="outlined" hide-details hint="默认 48" persistent-hint />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model.number="form.hr_deadline_days" label="全局考核期（天）" type="number" density="compact" variant="outlined" hide-details hint="默认 14" persistent-hint />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model.number="form.hr_additional_seed_time" label="额外做种时间（小时）" type="number" density="compact" variant="outlined" hide-details hint="默认 24" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="3">
                  <VTextField v-model.number="form.hr_ratio" label="全局分享率" type="number" density="compact" variant="outlined" hide-details hint="留空表示不校验分享率" persistent-hint />
                </VCol>
                <VCol cols="12" md="3">
                  <VTextField v-model.number="form.hr_upload_multiplier" label="全局上传倍数" type="number" density="compact" variant="outlined" hide-details hint="留空表示不校验上传倍数" persistent-hint />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.hr_upload_gte_download" color="info" inset hide-details label="要求上传量≥下载量" />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.hr_active" color="success" inset hide-details label="启用全局规则" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.hr_site_config_str" label="站点独立规则（YAML）" density="compact" variant="outlined" hide-details rows="10" />
                  <div class="dm-hint">顶层为列表，每项含 site_name 及 hr_duration / hr_deadline_days / hr_ratio / hr_upload_multiplier / hr_upload_gte_download / hr_size_tiers / hr_active；未设置字段回退全局规则。</div>
                </VCol>
              </VRow>
            </div>

            <!-- ═══ H&R · 保护开关 ═══ -->
            <div v-show="activeSub === 'hr_protection'" class="dm-pane">
              <div class="dm-section-title">保护开关</div>
              <VAlert type="info" variant="tonal" density="compact" class="mb-3">
                H&R 纳管且未达标的任务，会在自动删种、整理失败删源、转移源端删除三条破坏性路径上被统一跳过。
              </VAlert>
              <VRow>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.hr_protection_enabled" color="success" inset hide-details label="启用 H&R 保护" />
                </VCol>
              </VRow>
              <div class="dm-section-title mt-4">保护跳过计数</div>
              <div class="dm-monitor-summary">
                <div v-for="item in hrSkipStatRows" :key="item.label" class="dm-monitor-metric">
                  <span>{{ item.label }}</span><strong>{{ item.value }}</strong>
                </div>
              </div>
            </div>

            <!-- ═══ 自动删种 · 基础设置 ═══ -->
            <div v-show="activeSub === 'remover_basic'" class="dm-pane">
              <div class="dm-section-title">自动删种设置</div>
              <VRow>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.remover_enabled" color="success" inset hide-details label="启用自动删种" />
                </VCol>
                <VCol cols="12" md="3">
                  <VSelect v-model="form.remover_action" label="执行动作" density="compact" variant="outlined" hide-details
                    :items="removerActionItems" hint="暂停 / 删除任务 / 删除任务及文件" persistent-hint />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.remover_notify" color="info" inset hide-details label="发送通知" />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.remover_onlyonce" color="warning" inset hide-details label="立即运行一次" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VSelect v-model="form.remover_downloaders" label="目标下载器" density="compact" variant="outlined" hide-details
                    :items="downloaderItems" multiple chips closable-chips clearable hint="只处理这里选中的下载器" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VCronField v-model="form.remover_cron" label="执行周期" density="compact" variant="outlined" hide-details />
                </VCol>
              </VRow>
              <div class="dm-section-title mt-4">删除条件</div>
              <VRow>
                <VCol cols="12" md="3">
                  <VTextField v-model="form.remover_time" label="做种时长（小时）" density="compact" variant="outlined" hide-details hint="多个以逗号分隔" persistent-hint />
                </VCol>
                <VCol cols="12" md="3">
                  <VTextField v-model="form.remover_ratio" label="分享率低于" density="compact" variant="outlined" hide-details hint="多个以逗号分隔" persistent-hint />
                </VCol>
                <VCol cols="12" md="3">
                  <VTextField v-model="form.remover_size" label="体积（GB）" density="compact" variant="outlined" hide-details hint="多个以逗号分隔" persistent-hint />
                </VCol>
                <VCol cols="12" md="3">
                  <VTextField v-model="form.remover_upspeed" label="平均上传速度（KB/s）" density="compact" variant="outlined" hide-details hint="多个以逗号分隔" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="3">
                  <VTextField v-model="form.remover_labels" label="限定标签（逗号分隔）" density="compact" variant="outlined" hide-details />
                </VCol>
                <VCol cols="12" md="3">
                  <VTextField v-model="form.remover_torrentcategorys" label="限定分类（逗号分隔）" density="compact" variant="outlined" hide-details />
                </VCol>
                <VCol cols="12" md="3">
                  <VTextField v-model="form.remover_pathkeywords" label="路径关键词" density="compact" variant="outlined" hide-details hint="多个以逗号分隔" persistent-hint />
                </VCol>
                <VCol cols="12" md="3">
                  <VTextField v-model="form.remover_trackerkeywords" label="tracker 关键词" density="compact" variant="outlined" hide-details hint="多个以逗号分隔" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="3">
                  <VTextField v-model="form.remover_errorkeywords" label="错误关键词" density="compact" variant="outlined" hide-details hint="多个以逗号分隔" persistent-hint />
                </VCol>
                <VCol cols="12" md="3">
                  <VTextField v-model="form.remover_torrentstates" label="任务状态（逗号分隔）" density="compact" variant="outlined" hide-details />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.remover_mponly" color="info" inset hide-details label="仅 MoviePilot 标签任务" />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.remover_samedata" color="warning" inset hide-details label="连带同名同大小任务" />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 失败清理 · 基础设置 ═══ -->
            <div v-show="activeSub === 'failclean_basic'" class="dm-pane">
              <div class="dm-section-title">失败清理设置</div>
              <VAlert type="info" variant="tonal" density="compact" class="mb-3">
                整理失败时立即删除源文件与下载历史；定时巡检按保留时长清理重复下载残留路径。
              </VAlert>
              <VRow>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.failcleanup_enabled" color="success" inset hide-details label="启用失败清理" />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.failcleanup_clean_repeat" color="info" inset hide-details label="清理重复残留" />
                </VCol>
                <VCol cols="12" md="3">
                  <VSwitch v-model="form.failcleanup_notify" color="info" inset hide-details label="发送通知" />
                </VCol>
                <VCol cols="12" md="3">
                  <VCronField v-model="form.failcleanup_cron" label="巡检周期" density="compact" variant="outlined" hide-details />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="4">
                  <VTextField v-model.number="form.failcleanup_retain_hours" label="残留保留时长（小时）" type="number" density="compact" variant="outlined" hide-details
                    hint="仅清理早于该时长的重复残留路径，默认 6" persistent-hint />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 种子重命名 · 命名格式 ═══ -->
            <div v-show="activeSub === 'format'" class="dm-pane">
              <div class="dm-section-title">重命名设置</div>
              <VRow>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.rename_enabled" color="success" inset hide-details label="启用重命名" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.rename_movie_format" label="电影命名格式 (Jinja2)" density="compact" variant="outlined" hide-details rows="2" />
                  <div class="dm-hint">可用变量: {{ title }}, {{ year }}, {{ original_name }}</div>
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.rename_tv_format" label="电视剧命名格式 (Jinja2)" density="compact" variant="outlined" hide-details rows="2" />
                  <div class="dm-hint">可用变量: {{ title }}, {{ year }}, {{ season_episode }}, {{ original_name }}</div>
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.rename_exclude_dirs" label="排除目录（每行一个）" density="compact" variant="outlined" hide-details rows="2" />
                </VCol>
              </VRow>              <VRow class="mt-2">
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.rename_on_download_added" color="success" inset hide-details label="下载入列事件触发重命名" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.rename_cron_enabled" color="info" inset hide-details label="定时重命名" />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model.number="form.rename_event_debounce_seconds" label="事件防抖（秒）" type="number" min="1" density="compact" variant="outlined" hide-details
                    :disabled="!form.rename_on_download_added" hint="默认 3 秒" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VCronField v-model="form.rename_cron" label="定时重命名周期" density="compact" variant="outlined" hide-details :disabled="!form.rename_cron_enabled" />
                </VCol>
                <VCol cols="12" md="6">
                  <VSelect v-model="form.rename_downloaders" label="重命名下载器" density="compact" variant="outlined" hide-details
                    :items="qbDownloaderItems" multiple chips closable-chips clearable hint="仅 qBittorrent 支持重命名" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VTextField v-model="form.rename_include_tags" label="包含标签（逗号分隔）" density="compact" variant="outlined" hide-details hint="留空表示不限制" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VTextField v-model="form.rename_exclude_tags" label="排除标签（逗号分隔）" density="compact" variant="outlined" hide-details hint="默认排除已重命名" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.rename_hash_white_list" label="种子 hash 白名单（每行一个）" density="compact" variant="outlined" hide-details rows="2" />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 站点标签 · Tracker 映射 ═══ -->
            <div v-show="activeSub === 'mapping'" class="dm-pane">
              <div class="dm-section-title">站点标签设置</div>
              <VRow>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.tag_enabled" color="success" inset hide-details label="启用站点标签" />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model="form.tag_siteprefix" label="站点标签前缀" density="compact" variant="outlined" hide-details />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.tag_tracker_mappings_str" label="Tracker 映射（每行: 域名 -> 映射域名）" density="compact" variant="outlined" hide-details rows="4" />
                  <div class="dm-hint">例: tracker.example.com -> example</div>
                </VCol>
              </VRow>              <VRow class="mt-2">
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.tag_enable_tag" color="success" inset hide-details label="站点名标签" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.tag_enable_media_tag" color="info" inset hide-details label="剧名标签" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.tag_enable_category" color="info" inset hide-details label="TMDB 二级分类" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="4">
                  <VCronField v-model="form.tag_interval_cron" label="历史补全周期" density="compact" variant="outlined" hide-details />
                </VCol>
                <VCol cols="12" md="4">
                  <VSelect v-model="form.tag_downloaders" label="标签下载器" density="compact" variant="outlined" hide-details
                    :items="downloaderItems" multiple chips closable-chips clearable hint="留空表示全部下载器" persistent-hint />
                </VCol>
                <VCol cols="12" md="4">
                  <VTextField v-model="form.tag_catprefix" label="分类前缀" density="compact" variant="outlined" hide-details hint="写入分类名前的前缀，留空不加" persistent-hint />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VCombobox v-model="form.tag_all_cat" label="站点分类（回车输入）" density="compact" variant="outlined" hide-details
                    multiple chips closable-chips hint="TMDB 分类名列表" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VCombobox v-model="form.tag_all_cat_rename" label="映射目标分类（回车输入）" density="compact" variant="outlined" hide-details
                    multiple chips closable-chips hint="与左侧按顺序一一对应" persistent-hint />
                </VCol>
              </VRow>
              <div class="dm-hint">两个分类列表按顺序一一对应，数量需保持一致。</div>
              <VRow class="mt-2">
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.tag_enable_del_tags" color="warning" inset hide-details label="允许删除标签" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.tag_rename_type" color="info" inset hide-details label="目录重命名映射" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12">
                  <VTextarea v-model="form.tag_path_rename" label="路径映射规则（每行: 关键词#分类）" density="compact" variant="outlined" hide-details rows="3"
                    :disabled="!form.tag_rename_type" />
                </VCol>
              </VRow>
            </div>

            <!-- ═══ 站点标签 · 标签清理 ═══ -->
            <div v-show="activeSub === 'tag_cleanup'" class="dm-pane">
              <div class="dm-section-title">标签清理</div>
              <div class="dm-cleanup-toolbar">
                <VSelect v-model="cleanupDownloaders" label="下载器" density="compact" variant="outlined" hide-details
                  :items="qbDownloaderItems" multiple chips closable-chips class="dm-cleanup-select" />
                <VBtn color="primary" variant="tonal" prepend-icon="mdi-radar" :loading="cleanupScanning"
                  :disabled="!cleanupDownloaders.length" @click="scanCleanupTags">扫描标签</VBtn>
              </div>

              <VAlert v-if="cleanupMessage" :type="cleanupStatus" variant="tonal" density="compact" closable class="mt-3"
                @click:close="cleanupMessage = ''">{{ cleanupMessage }}</VAlert>

              <div v-if="cleanupScan" class="dm-cleanup-results mt-4">
                <div class="dm-cleanup-summary">
                  <div>
                    <div class="text-subtitle-2">扫描结果</div>
                    <div class="text-caption text-medium-emphasis">
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
                      <strong class="text-body-2">{{ group.name }}</strong>
                    </div>
                    <span class="text-caption text-medium-emphasis">{{ group.task_count }} 个任务 · {{ group.tags.length }} 个标签</span>
                  </div>

                  <div v-if="!group.tags.length" class="dm-cleanup-empty">
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
                          <span class="text-caption text-medium-emphasis">{{ item.count }} 个任务</span>
                        </div>
                        <div class="dm-tag-samples" :title="(item.samples || []).join(' · ')">{{ (item.samples || []).join(' · ') }}</div>
                      </div>
                    </label>
                  </div>
                </div>

                <div class="dm-cleanup-actions">
                  <div class="text-caption text-medium-emphasis">
                    待清理 {{ cleanupRemovals.length }} 个标签 · {{ cleanupRemovalAssociations }} 条任务关联
                  </div>
                  <VBtn color="warning" variant="tonal" prepend-icon="mdi-eye-outline"
                    :disabled="!cleanupRemovals.length" @click="previewCleanupTags">预览清理</VBtn>
                </div>
              </div>
            </div>

            <!-- ═══ 做种校验 v3.0.15 · 基础设置 ═══ -->
            <div v-show="activeSub === 'seed_basic'" class="dm-pane">
              <div class="dm-section-title">做种校验设置</div>
              <VAlert type="info" variant="tonal" density="compact" class="mb-4">做种校验采用按需触发：仅在转移做种或手动补刀添加种子后启动。队列为空后自动停止。</VAlert>
              <VRow>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.seed_autostart" color="success" inset hide-details label="启用自动开始做种" />
                </VCol>
                <VCol cols="12" md="4">
                  <VSwitch v-model="form.seed_skipverify" color="info" inset hide-details label="跳过校验(QB有效)" />
                </VCol>
              </VRow>
              <VRow class="mt-2">
                <VCol cols="12" md="6">
                  <VTextField v-model.number="form.seed_check_interval" label="校验检查间隔（秒）" type="number" density="compact" variant="outlined" hide-details hint="建议 60 秒" persistent-hint />
                </VCol>
                <VCol cols="12" md="6">
                  <VTextField v-model.number="form.seed_max_wait_minutes" label="最大等待时间（分钟）" type="number" density="compact" variant="outlined" hide-details hint="超时后移出队列" persistent-hint />
                </VCol>
              </VRow>
            </div>

          </div>
        </section>
      </div>
      <VDivider />
      <VCardActions class="dm-actions">
        <VSpacer />
        <VBtn variant="text" @click="emit('close')">取消</VBtn>
        <VBtn color="primary" variant="flat" prepend-icon="mdi-content-save-outline" @click="saveConfig">保存配置</VBtn>
      </VCardActions>
    </VCard>

    <VDialog v-model="cleanupDialog" max-width="620">
      <VCard>
        <VCardItem>
          <template #prepend>
            <VAvatar color="warning" variant="tonal" size="40" rounded="lg"><VIcon icon="mdi-tag-remove-outline" /></VAvatar>
          </template>
          <VCardTitle class="text-subtitle-1">确认标签清理</VCardTitle>
          <VCardSubtitle>{{ cleanupRemovals.length }} 个标签 · {{ cleanupRemovalAssociations }} 条任务关联</VCardSubtitle>
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
          <VBtn variant="text" :disabled="cleanupExecuting" @click="cleanupDialog = false">取消</VBtn>
          <VBtn color="error" variant="flat" prepend-icon="mdi-tag-remove-outline" :loading="cleanupExecuting"
            @click="executeCleanupTags">确认清理</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog v-model="uploadRestoreDialog" max-width="560">
      <VCard>
        <VCardItem>
          <template #prepend>
            <VAvatar color="warning" variant="tonal" size="40" rounded="lg"><VIcon icon="mdi-backup-restore" /></VAvatar>
          </template>
          <VCardTitle class="text-subtitle-1">停用并恢复上传限速</VCardTitle>
          <VCardSubtitle>恢复插件接管前的下载器与单种上传设置</VCardSubtitle>
        </VCardItem>
        <VDivider />
        <VCardText class="text-body-2">
          当前值仍等于插件最后写入值时才会恢复；若你后来手工修改过，则保留手工值，不会覆盖。
        </VCardText>
        <VDivider />
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" :disabled="uploadActionRunning === 'restore'" @click="uploadRestoreDialog = false">取消</VBtn>
          <VBtn color="warning" variant="flat" prepend-icon="mdi-backup-restore" :loading="uploadActionRunning === 'restore'"
            @click="disableAndRestoreUploadLimits">确认恢复</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </div>
</template>
<style scoped>
.dm-config {
  width: min(1120px, calc(100vw - 48px));
  max-width: 100%;
  padding: 8px;
}
.dm-card {
  width: 100%;
  height: clamp(760px, calc(100dvh - 48px), 860px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 14px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}
.dm-header { padding: 14px 18px; }
.dm-header :deep(.v-card-subtitle) {
  max-width: min(560px, 52vw);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dm-body { flex: 1 1 auto; min-height: 0; display: flex; }
.dm-nav { width: 160px; flex: 0 0 160px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), 0.02); }
.dm-nav-list { width: 100%; }
.dm-nav-item { margin: 2px 8px; }
.dm-content { flex: 1 1 auto; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.dm-subtabs { flex: 0 0 auto; display: flex; flex-wrap: wrap; gap: 4px; padding: 8px 12px; }
.dm-subtab { display: inline-flex; align-items: center; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500; color: rgba(var(--v-theme-on-surface), 0.7); background: transparent; border: none; cursor: pointer; transition: background 0.15s, color 0.15s; white-space: nowrap; }
.dm-subtab:hover { background: rgba(var(--v-theme-primary), 0.08); color: rgb(var(--v-theme-primary)); }
.dm-subtab--active { background: rgba(var(--v-theme-primary), 0.14); color: rgb(var(--v-theme-primary)); font-weight: 600; }
.dm-window { flex: 1 1 auto; min-height: 0; overflow-y: auto; }
.dm-window--overview { overflow-y: hidden; }
.dm-pane { min-height: 100%; padding: 18px 20px; }
.dm-pane--overview { min-height: auto; padding: 12px 16px; }
.dm-section-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; color: rgb(var(--v-theme-primary)); }
.dm-hint { font-size: 12px; line-height: 1.5; color: rgba(var(--v-theme-on-surface), 0.6); margin-top: 2px; }
.dm-overview-section { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; padding: 10px 12px; min-width: 0; }
.dm-flow { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; }
.dm-flow-block { min-width: 0; }
.dm-flow-block:first-child { grid-column: 1 / -1; }
.dm-flow-label { font-size: 12px; font-weight: 600; color: rgb(var(--v-theme-primary)); margin-bottom: 5px; }
.dm-flow-row { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.78); }
.dm-flow-step { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 999px; padding: 5px 9px; background: rgba(var(--v-theme-on-surface), 0.02); white-space: nowrap; }
.dm-flow-arrow { flex: 0 0 auto; color: rgba(var(--v-theme-on-surface), 0.44); }
.dm-break-text { overflow-wrap: anywhere; }
.dm-monitor-summary, .dm-upload-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.dm-monitor-metric { min-width: 0; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-monitor-metric span { display: block; color: rgba(var(--v-theme-on-surface), 0.62); font-size: 12px; }
.dm-monitor-metric strong { display: block; margin-top: 3px; overflow-wrap: anywhere; font-size: 15px; }
.dm-monitor-empty { display: flex; min-height: 64px; align-items: center; justify-content: center; border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; color: rgba(var(--v-theme-on-surface), 0.6); font-size: 13px; }
.dm-upload-downloader-list, .dm-upload-site-list, .dm-upload-site-status { display: grid; gap: 10px; }
.dm-upload-config-row { display: grid; grid-template-columns: minmax(220px, .72fr) minmax(260px, 1fr); gap: 16px; align-items: start; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-upload-config-name, .dm-upload-site-name { display: flex; align-items: flex-start; gap: 9px; min-width: 0; padding-top: 8px; overflow-wrap: anywhere; }
.dm-upload-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.dm-upload-site-row { display: grid; grid-template-columns: minmax(180px, .72fr) minmax(250px, 1fr) auto; gap: 12px; align-items: start; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-upload-site-row :deep(.v-btn) { margin-top: 4px; }
.dm-upload-status-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.dm-upload-status-card { min-width: 0; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-upload-status-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; min-width: 0; }
.dm-upload-values { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 5px 12px; margin-top: 10px; font-size: 12px; }
.dm-upload-values span { min-width: 0; overflow-wrap: anywhere; }
.dm-upload-site-status-row { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(102px, auto) minmax(112px, auto) minmax(124px, auto); gap: 10px; align-items: center; min-width: 0; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-upload-site-status-row > span { min-width: 0; overflow-wrap: anywhere; }
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
.dm-tag-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 600; }
.dm-tag-samples { margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: rgba(var(--v-theme-on-surface), 0.55); font-size: 11px; }
.dm-cleanup-empty { min-height: 82px; display: flex; align-items: center; justify-content: center; gap: 8px; color: rgba(var(--v-theme-on-surface), 0.6); font-size: 13px; }
.dm-cleanup-actions { position: sticky; bottom: -18px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 0 0; background: rgb(var(--v-theme-surface)); }
.dm-cleanup-preview-list { max-height: 360px; overflow-y: auto; }
.dm-actions { padding: 10px 18px; }
@media (max-width: 760px) {
  .dm-config { width: min(100%, calc(100vw - 16px)); padding: 4px; }
  .dm-card { height: min(860px, calc(100dvh - 16px)); }
  .dm-header :deep(.v-card-subtitle) { max-width: 100%; }
  .dm-body { flex-direction: column; }
  .dm-nav { width: 100%; flex: 0 0 auto; border-right: none; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); overflow-x: auto; overflow-y: hidden; scrollbar-width: none; }
  .dm-nav::-webkit-scrollbar { display: none; }
  .dm-nav-list { display: flex; flex-wrap: nowrap; gap: 6px; min-width: max-content; padding: 8px 12px !important; }
  .dm-nav-item { flex: 0 0 auto; min-width: 96px; margin: 0; padding-inline: 10px; }
  .dm-nav-item :deep(.v-list-item-title) { white-space: nowrap; }
  .dm-subtabs { flex-wrap: nowrap; overflow-x: auto; overflow-y: hidden; scrollbar-width: none; padding: 6px 12px; }
  .dm-subtabs::-webkit-scrollbar { display: none; }
  .dm-subtab { flex: 0 0 auto; padding: 6px 12px; }
  .dm-flow { grid-template-columns: 1fr; }
  .dm-flow-block:first-child { grid-column: auto; }
  .dm-monitor-summary, .dm-upload-summary { grid-template-columns: 1fr; }
  .dm-upload-config-row, .dm-upload-site-row, .dm-upload-status-grid, .dm-upload-site-status-row { grid-template-columns: 1fr; }
  .dm-upload-config-name, .dm-upload-site-name { padding-top: 0; }
  .dm-upload-toolbar { align-items: stretch; flex-direction: column; }
  .dm-upload-toolbar :deep(.v-btn) { width: 100%; }
  .dm-upload-site-row :deep(.v-btn) { justify-self: end; margin-top: 0; }
  .dm-cleanup-toolbar, .dm-cleanup-summary, .dm-cleanup-actions, .dm-tag-group-head { align-items: stretch; flex-direction: column; }
  .dm-cleanup-toolbar :deep(.v-btn), .dm-cleanup-actions :deep(.v-btn) { width: 100%; }
  .dm-tag-line { flex-wrap: wrap; }
  .dm-tag-name { width: 100%; }
  .dm-window--overview { overflow-y: auto; }
}
@media (min-width: 761px) and (max-width: 960px) {
  .dm-monitor-summary, .dm-upload-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dm-upload-site-row { grid-template-columns: minmax(180px, .7fr) minmax(220px, 1fr) auto; }
  .dm-upload-status-grid { grid-template-columns: 1fr; }
  .dm-upload-site-status-row { grid-template-columns: minmax(170px, 1fr) repeat(3, minmax(96px, auto)); }
  .dm-flow { grid-template-columns: 1fr; }
  .dm-flow-block:first-child { grid-column: auto; }
  .dm-window--overview { overflow-y: auto; }
}
@media (max-height: 760px) {
  .dm-window--overview { overflow-y: auto; }
}
</style>
