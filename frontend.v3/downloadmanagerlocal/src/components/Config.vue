<script setup>
import '../styles/dm-tokens.css'
import { reactive, ref, computed, watch, onMounted } from 'vue'
import { getPluginApi } from './api'
import DownloaderBadge from './DownloaderBadge.vue'

const props = defineProps({
  api: { type: [Object, Function], default: null },
  initialConfig: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'DownloadManagerLocal' },
  sourcePluginId: { type: String, default: 'DownloadManagerLocal' },
})
const emit = defineEmits(['save', 'close', 'switch'])
const getApi = (path, options = {}) => getPluginApi(props.api, props.pluginId, path, options)
const form = reactive({})
const saveMessage = ref('')
const saveError = ref(false)
const savePending = ref(false)
const activeMain = ref('transfer')
const activeSub = ref('basic')
const downloaderItems = ref([])
const transferTasks = ref([])
const transferExt = ref({})
const transferDialog = ref(false)
const transferEditing = ref(-1)
const transferForm = reactive({})
const transferError = ref('')
const transferDeleteDialog = ref(false)
const transferDeleteIndex = ref(-1)
const siteItems = ref([])
const hrPresets = ref([])
const hrPresetsLoading = ref(false)
const hrPresetsLoaded = ref(false)
const hrPresetsMessage = ref('')
const hrCustomRules = ref([])
const hrExpandedSites = ref([])
const hrShowInherited = ref(false)
const hrRawOpen = ref(false)
const hrRawError = ref('')
const hrAddDialog = ref(false)
const hrNewSiteName = ref('')
const hrAddError = ref('')
let hrSyncedSiteConfigText = ''

onMounted(async () => {
  try {
    const [dlResp, siteResp] = await Promise.all([
      getApi('downloaders', { feedback: 'silent' }),
      getApi('sites', { feedback: 'silent' }),
      loadHrPresets(),
    ])
    if (dlResp) {
      downloaderItems.value = dlResp
    }
    if (siteResp) {
      siteItems.value = siteResp
    }
  } catch (e) {
    console.error('获取列表失败:', e)
  }
})

const defaults = {
  hr_enabled: false, hr_protection_enabled: true, hr_auto_discover: false,
  hr_enable_site_config: false, hr_downloader: [], hr_sites: [],
  hr_notify: 'always', hr_check_period: 10, hr_hit_and_run_tag: 'H&R',
  hr_auto_cleanup_days: 15, hr_notify_summary_cron: '0 8 * * *',
  hr_exclude_tags: [], hr_exclude_categories: [],
  hr_duration: 48, hr_deadline_days: 14, hr_additional_seed_time: 24,
  hr_ratio: null, hr_upload_multiplier: null, hr_upload_gte_download: null,
  hr_active: false, hr_brush_plugin: 'BrushFlow', hr_site_config_str: '',
  remover_enabled: false, remover_notify: false,
  remover_action: 'pause', remover_downloaders: [], remover_cron: '0 */12 * * *',
  remover_samedata: false, remover_mponly: false, remover_size: '', remover_ratio: '',
  remover_time: '', remover_upspeed: '', remover_labels: '', remover_pathkeywords: '',
  remover_trackerkeywords: '', remover_errorkeywords: '', remover_torrentstates: '',
  remover_torrentcategorys: '',
  migration_observe_only: true,
  failcleanup_enabled: false, failcleanup_notify: true, failcleanup_cron: '0 */2 * * *',
  failcleanup_clean_repeat: true, failcleanup_retain_hours: 6,
  rename_notify: false, rename_cron_enabled: false, rename_on_download_added: true,
  rename_downloaders: [], rename_hash_white_list: '', rename_exclude_tags: '已重命名',
  rename_include_tags: '', rename_cron: '', rename_event_debounce_seconds: 3,
  tag_interval_cron: '5 4 * * *', tag_enable_media_tag: false, tag_enable_tag: true,
  tag_enable_category: false, tag_enable_del_tags: false, tag_downloaders: [],
  tag_all_cat: [], tag_all_cat_rename: [], tag_rename_type: false, tag_path_rename: '',
  tag_catprefix: '',
  enabled: false, transfer_enabled: true, delay_minutes: 25, notify: false,
  transfer_fallback_enabled: true, transfer_fallback_interval_minutes: 60,
  fromdownloader: '', todownloader: '', frompath: '', topath: '',
  fromtorrentpath: '', nopaths: '', nolabels: '', includelabels: '', includecategory: '',
  transferemptylabel: false, add_torrent_tags: '⏩转种',
  deletesource: false, deleteduplicate: false,
  remainoldcat: false, remainoldtag: false,
  transfer_tasks: '[]', transfer_rename_enabled: false, downloader_ext: '{}',
  rename_enabled: true,
  rename_movie_format: '[ {{ title }}{% if year %} ({{ year }}){% endif %} ] - {{original_name}}',
  rename_tv_format: '[ {{ title }}{% if year %} ({{ year }}){% endif %}{% if season_episode %} - {{season_episode}}{% endif %} ] - {{original_name}}',
  rename_exclude_dirs: '',
  tag_enabled: true, tag_siteprefix: '🏠', tag_tracker_mappings_str: '',
  tag_custom_sites_str: '',
  seed_autostart: true, seed_skipverify: false,
  seed_check_interval: 60, seed_max_wait_minutes: 120,
  scan_limit: 500, pause_source: true,
  upload_limit_enabled: false, upload_limit_downloaders: [],
  upload_limit_downloader_limits_kib: {}, upload_limit_site_rules: {},
  upload_limit_grace_minutes: 30,
  // 观察模式（阶段三）：只预览候选、不执行写操作。老配置默认关闭（升级保持升级前行为），
  // 全新安装时由下方 fresh install 补丁打开；按模块前缀自动归入对应页签的「恢复默认」键集。
  transfer_observe_only: false, rename_observe_only: false, tag_observe_only: false,
  hr_observe_only: false, remover_observe_only: false, failcleanup_observe_only: false,
  upload_limit_observe_only: false,
}

// 各设置页签的「恢复默认」键集：transfer 为显式列表（含无前缀共享键），其余按模块前缀从 defaults 提取
const PANE_RESET_KEYS = {
  transfer: ['transfer_enabled', 'delay_minutes', 'notify',
    'transfer_fallback_enabled', 'transfer_fallback_interval_minutes',
    'fromdownloader', 'todownloader', 'frompath', 'topath', 'fromtorrentpath',
    'nopaths', 'nolabels', 'includelabels', 'includecategory', 'transferemptylabel',
    'add_torrent_tags', 'deletesource', 'deleteduplicate', 'remainoldcat', 'remainoldtag',
    'transfer_tasks', 'transfer_rename_enabled', 'downloader_ext',
    'seed_autostart', 'seed_skipverify', 'seed_check_interval', 'seed_max_wait_minutes',
    'scan_limit', 'pause_source', 'transfer_observe_only'],
  hr: Object.keys(defaults).filter(k => k.startsWith('hr_')),
  // remover 观察开关已迁移为 remover_observe_only（带前缀），旧 migration_observe_only 键保留在 defaults 供迁移回填
  remover: Object.keys(defaults).filter(k => k.startsWith('remover_')),
  failclean: Object.keys(defaults).filter(k => k.startsWith('failcleanup_')),
  rename: Object.keys(defaults).filter(k => k.startsWith('rename_')),
  tag: Object.keys(defaults).filter(k => k.startsWith('tag_')),
  upload: Object.keys(defaults).filter(k => k.startsWith('upload_limit_')),
}

// 观察模式键（阶段三）：与后端 utils/config.py 的 OBSERVE_ONLY_KEYS 一一对应；
// 全新安装默认开启，老配置升级保持升级前行为（见下方 watch 中的补丁）。
const OBSERVE_ONLY_KEYS = [
  'transfer_observe_only', 'rename_observe_only', 'tag_observe_only', 'hr_observe_only',
  'remover_observe_only', 'failcleanup_observe_only', 'upload_limit_observe_only',
]
const paneResetDialog = ref(false)
const paneResetTarget = ref('')
const paneResetCount = computed(() => (PANE_RESET_KEYS[paneResetTarget.value] || []).length)
const paneResetTitle = computed(() => mainTabs.find(i => i.key === paneResetTarget.value)?.title || '')

function askPaneReset(key) {
  paneResetTarget.value = key
  paneResetDialog.value = true
}

function confirmPaneReset() {
  for (const k of PANE_RESET_KEYS[paneResetTarget.value] || []) {
    form[k] = JSON.parse(JSON.stringify(defaults[k]))
  }
  if (paneResetTarget.value === 'transfer') {
    transferTasks.value = parseTransferTasks(form.transfer_tasks)
    transferExt.value = parseDownloaderExt(form.downloader_ext)
  }
  paneResetDialog.value = false
}

const mainTabs = [
  { key: 'transfer', title: '转移做种', icon: 'mdi-transfer', desc: '监听下载完成事件，延迟后自动转移做种到目标下载器。' },
  { key: 'hr', title: 'H&R 管理', icon: 'mdi-timer-alert-outline', desc: '按站点规则跟踪 H&R 做种状态，为破坏性操作提供统一保护。' },
  { key: 'remover', title: '自动删种', icon: 'mdi-delete-clock-outline', desc: '按时间、分享率、体积等条件自动暂停或删除种子。' },
  { key: 'failclean', title: '失败清理', icon: 'mdi-broom', desc: '整理失败时立即清理源文件与下载历史，并定时清理重复残留。' },
  { key: 'rename', title: '种子重命名', icon: 'mdi-rename-box', desc: '转移后自动根据 TMDB 信息命名种子，失败记录进定时补查，也可手动补刀。' },
  { key: 'tag', title: '站点标签', icon: 'mdi-tag-multiple', desc: '转移后自动根据 tracker 域名打站点标签。' },
  { key: 'upload', title: '上传限速', icon: 'mdi-upload-network-outline', desc: '设置下载器全局上传上限，并按需限制指定站点的合计上传速度。' },
]

const subTabs = {
  upload: [
    { key: 'upload_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'upload_rules', title: '限速规则', icon: 'mdi-speedometer' },
  ],
  transfer: [
    { key: 'basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'tasks', title: '任务列表', icon: 'mdi-playlist-check' },
    { key: 'seed_basic', title: '做种校验', icon: 'mdi-check-circle-outline' },
  ],
  hr: [
    { key: 'hr_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'hr_sites', title: '站点规则', icon: 'mdi-home-outline' },
    { key: 'hr_advanced', title: '高级设置', icon: 'mdi-shield-check-outline' },
  ],
  remover: [
    { key: 'remover_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'remover_conditions', title: '删除条件', icon: 'mdi-filter-variant' },
  ],
  failclean: [{ key: 'failclean_basic', title: '基础设置', icon: 'mdi-tune-variant' }],
  rename: [
    { key: 'rename_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'rename_format', title: '模板与过滤', icon: 'mdi-format-text' },
  ],
  tag: [
    { key: 'tag_basic', title: '基础设置', icon: 'mdi-tune-variant' },
    { key: 'mapping', title: '映射规则', icon: 'mdi-link-variant' },
  ],
}

const currentMain = computed(() => mainTabs.find(i => i.key === activeMain.value) || mainTabs[0])
const currentSubs = computed(() => subTabs[activeMain.value] || [])
/** 下载器下拉统一展示「名称 (类型)」；value 仍是下载器名，后端只认名字。 */
const downloaderSelectItems = computed(() => downloaderItems.value.map(item => ({
  ...item,
  title: `${item.title} (${item.type})`,
})))
const qbDownloaderItems = computed(() => downloaderItems.value.filter(item => item.type === 'qbittorrent'))
const uploadDownloaderItems = computed(() => downloaderItems.value.filter(item => ['qbittorrent', 'transmission'].includes(item.type)))
const uploadSelectedDownloaders = computed(() => {
  const selected = new Set(form.upload_limit_downloaders || [])
  return uploadDownloaderItems.value.filter(item => selected.has(item.value))
})
const uploadMissingLimits = computed(() => uploadSelectedDownloaders.value.filter(
  item => !uploadDownloaderLimit(item.value),
))
const uploadSiteRuleRows = computed(() => Object.entries(form.upload_limit_site_rules || {})
  .map(([name, rule]) => ({ name, limit_kib: Number(rule?.limit_kib || 0) || null }))
  .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN')))
const hrBrushPluginItems = ['BrushFlow', '不启用']
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
const tagCatPairs = ref([])
const tagTrackerPairs = ref([])

function parseCatPairs(cats, renames) {
  const catsList = Array.isArray(cats) ? cats : []
  const renamesList = Array.isArray(renames) ? renames : []
  const rows = []
  for (let i = 0; i < Math.max(catsList.length, renamesList.length); i++) {
    rows.push({ from: catsList[i] || '', to: renamesList[i] || '' })
  }
  return rows
}

function parseTrackerPairs(text) {
  return String(text || '').split('\n').map(line => {
    const [from, ...rest] = line.split('->')
    return { tracker: (from || '').trim(), site: rest.join('->').trim() }
  }).filter(p => p.tracker || p.site)
}

function serializeCatPairs(pairs) {
  return {
    tag_all_cat: pairs.map(p => (p.from || '').trim()).filter(Boolean),
    tag_all_cat_rename: pairs.map(p => (p.to || '').trim()),
  }
}

function serializeTrackerPairs(pairs) {
  return pairs
    .map(p => `${(p.tracker || '').trim()} -> ${(p.site || '').trim()}`)
    .filter(line => !line.startsWith(' -> '))
    .join('\n')
}

function parseCustomSiteLabels(text) {
  const out = {}
  String(text || '').split('\n').forEach(line => {
    const [from, ...rest] = line.split('->')
    const domain = (from || '').trim().toLowerCase()
    const label = rest.join('->').trim()
    if (domain && label) out[domain] = label
  })
  return out
}

function serializeCustomSiteLabels(pairs) {
  return pairs
    .filter(p => !siteNameByDomain(p.site || p.tracker) && String(p.custom || '').trim())
    .map(p => `${(p.site || p.tracker || '').trim().toLowerCase()} -> ${String(p.custom).trim()}`)
    .join('\n')
}

function siteNameByDomain(domain) {
  const clean = String(domain || '').trim().toLowerCase()
  if (!clean) return ''
  const hit = (siteItems.value || []).find(s => String(s.domain || '').toLowerCase() === clean)
  return hit?.title || ''
}

function addCatPair() {
  tagCatPairs.value.push({ from: '', to: '' })
}

function addTrackerPair() {
  tagTrackerPairs.value.push({ tracker: '', site: '' })
}

// ═══ 转移做种 · 多任务引擎（transfer_tasks / downloader_ext）═══

/** 任务字段与后端 service/transfer_tasks.py::_TASK_DEFAULTS 一致。 */
const transferTaskDefaults = {
  name: '', enabled: true, from_downloader: '', to_downloader: '',
  include_category: '', include_labels: '', exclude_labels: '', empty_label_ok: true,
  no_paths: '', from_path: '', to_path: '',
  delete_source: false, delete_duplicate: true, keep_category: true, keep_tag: true,
  transfer_tag: '已转移',
}

/** 对话框草稿；ext_* 只用于 downloader_ext，不进入任务对象。 */
function blankTransferForm() {
  return { ...transferTaskDefaults, ext_webui_url: '', ext_source_plugin: '' }
}

function parseTransferTasks(raw) {
  let parsed
  try {
    parsed = JSON.parse(String(raw || '[]'))
  } catch (error) {
    console.error('transfer_tasks 解析失败:', error)
    return []
  }
  if (!Array.isArray(parsed)) return []
  return parsed
    .filter(item => item && typeof item === 'object')
    .map(item => ({ ...transferTaskDefaults, ...item, enabled: item.enabled !== false }))
}

function parseDownloaderExt(raw) {
  let parsed
  try {
    parsed = JSON.parse(String(raw || '{}'))
  } catch (error) {
    console.error('downloader_ext 解析失败:', error)
    return {}
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
  return Object.fromEntries(Object.entries(parsed).map(([name, value]) => [name, {
    webui_url: String(value?.webui_url || ''),
    source_plugin: String(value?.source_plugin || ''),
  }]))
}


function downloaderTypeOf(name) {
  return downloaderItems.value.find(item => item.value === name)?.type || ''
}

function downloaderTitle(name) {
  const hit = downloaderItems.value.find(item => item.value === name)
  return hit ? hit.title : (name || '—')
}

/** 筛选条件摘要：只列实际生效的条件，无条件时明确显示「不限分类」。 */
function taskFilterChips(task) {
  const chips = []
  const category = String(task.include_category || '').trim()
  chips.push(category ? `分类 ${category}` : '不限分类')
  const labels = String(task.include_labels || '').trim()
  if (labels) chips.push(`标签 ${labels}`)
  const excludeLabels = String(task.exclude_labels || '').trim()
  if (excludeLabels) chips.push(`排除 ${excludeLabels}`)
  if (task.empty_label_ok) chips.push('允许无标签')
  if (task.no_paths) chips.push('不限路径')
  return chips
}

/** 设置列徽标：显示该任务启用了哪些高级设置，未启用任何项时前端显示「默认」。 */
function taskSettingBadges(task) {
  const badges = []
  if (task.delete_source) badges.push({ text: '删源种', color: 'error' })
  if (task.delete_duplicate) badges.push({ text: '去重', color: 'warning' })
  if (!task.keep_category) badges.push({ text: '不保留分类', color: 'secondary' })
  if (!task.keep_tag) badges.push({ text: '不保留标签', color: 'secondary' })
  const transferTag = String(task.transfer_tag || '').trim()
  if (transferTag) badges.push({ text: `标签 ${transferTag}`, color: 'primary' })
  const ext = transferExt.value[task.name] || {}
  if (ext.webui_url) badges.push({ text: 'WebUI 覆盖', color: 'info' })
  if (ext.source_plugin) badges.push({ text: 'source 插件', color: 'info' })
  return badges
}

const transferDialogSourceType = computed(() => (
  downloaderItems.value.find(item => item.value === transferForm.from_downloader)?.type || ''
))

const transferDeleteName = computed(() => transferTasks.value[transferDeleteIndex.value]?.name || '')

function loadTransferTaskExt(name) {
  const entry = transferExt.value[name] || {}
  transferForm.ext_webui_url = entry.webui_url || ''
  transferForm.ext_source_plugin = entry.source_plugin || ''
}

// 对话框内改源下载器时同步该下载器的 downloader_ext 草稿
watch(() => transferForm.from_downloader, name => loadTransferTaskExt(name))

function openTransferDialog(index = -1) {
  transferError.value = ''
  transferEditing.value = index
  const task = index >= 0 ? transferTasks.value[index] : null
  Object.keys(transferForm).forEach(key => delete transferForm[key])
  Object.assign(transferForm, blankTransferForm(), task || {})
  loadTransferTaskExt(transferForm.from_downloader)
  transferDialog.value = true
}

function confirmTransferTask() {
  transferError.value = ''
  const from = String(transferForm.from_downloader || '')
  const to = String(transferForm.to_downloader || '')
  const fromPath = String(transferForm.from_path || '').trim()
  const toPath = String(transferForm.to_path || '').trim()
  if (!from || !to) {
    transferError.value = '请选择源下载器与目的下载器'
    return
  }
  if (from === to) {
    transferError.value = '源下载器与目的下载器不能相同'
    return
  }
  // 路径映射是可选能力：两者都空 = 不做映射（后端 convert_save_path 契约 C1 同样原样返回）。
  // 只有「只填了一个」才是配置错误——那会让映射方向不明。
  if (Boolean(fromPath) !== Boolean(toPath)) {
    transferError.value = '源数据路径与目的数据路径需同时填写或同时留空（都留空＝不做路径映射）'
    return
  }
  const index = transferEditing.value
  const task = {
    ...transferTaskDefaults,
    name: String(transferForm.name || '').trim() || `任务${index >= 0 ? index + 1 : transferTasks.value.length + 1}`,
    enabled: transferForm.enabled !== false,
    from_downloader: from,
    to_downloader: to,
    include_category: String(transferForm.include_category || '').trim(),
    include_labels: String(transferForm.include_labels || '').trim(),
    exclude_labels: String(transferForm.exclude_labels || '').trim(),
    empty_label_ok: transferForm.empty_label_ok !== false,
    no_paths: String(transferForm.no_paths || ''),
    from_path: fromPath,
    to_path: toPath,
    delete_source: !!transferForm.delete_source,
    delete_duplicate: transferForm.delete_duplicate !== false,
    keep_category: transferForm.keep_category !== false,
    keep_tag: transferForm.keep_tag !== false,
    transfer_tag: String(transferForm.transfer_tag ?? '').trim(),
  }
  transferTasks.value = index >= 0
    ? transferTasks.value.map((item, position) => (position === index ? task : item))
    : [...transferTasks.value, task]
  if (transferDialogSourceType.value === 'rtorrent') {
    transferExt.value = {
      ...transferExt.value,
      [from]: {
        webui_url: String(transferForm.ext_webui_url || '').trim(),
        source_plugin: String(transferForm.ext_source_plugin || '').trim(),
      },
    }
  }
  transferDialog.value = false
}

function askTransferDelete(index) {
  transferDeleteIndex.value = index
  transferDeleteDialog.value = true
}

function confirmTransferDelete() {
  transferTasks.value = transferTasks.value.filter((_, position) => position !== transferDeleteIndex.value)
  transferDeleteDialog.value = false
}
// H&R 规则键；initialConfig 的 immediate watcher 放在 setup 末尾，
// 确保 YAML 分档解析依赖的 hrTierFields 等声明也已初始化。
const hrSiteRuleKeys = ['hr_duration', 'additional_seed_time', 'hr_deadline_days', 'hr_ratio', 'hr_upload_multiplier', 'hr_upload_gte_download', 'hr_active']
const hrListRuleKeys = ['trackers']
const hrTierValueKeys = ['hr_duration', 'hr_deadline_days']


function switchToData() {
  emit('switch')
}
function buildSavePayload() {
  return {
    ...form,
    transfer_tasks: JSON.stringify(transferTasks.value),
    downloader_ext: JSON.stringify(transferExt.value),
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
    tag_downloaders: [...(form.tag_downloaders || [])],
    ...serializeCatPairs(tagCatPairs.value),
    tag_tracker_mappings_str: serializeTrackerPairs(tagTrackerPairs.value),
    tag_custom_sites_str: serializeCustomSiteLabels(tagTrackerPairs.value),
  }
}

async function saveConfig() {
  const payload = buildSavePayload()
  saveMessage.value = ''
  saveError.value = false
  savePending.value = true
  try {
    if (!props.api?.put) throw new Error('MoviePilot 插件 API 未就绪')
    // 不得改回 emit('save')：宿主 closeOn 含 save，会立即关闭配置窗口（P3 自保存方案的前提）
    const response = await props.api.put(`plugin/${props.pluginId}`, payload)
    if (response?.success === false || response?.data?.success === false) {
      throw new Error(response.message || response.data?.message || '保存配置失败')
    }
    saveMessage.value = '配置已保存，窗口保持打开；如需同步插件列表/侧边导航，请刷新页面。'
  } catch (error) {
    saveError.value = true
    saveMessage.value = error?.response?.data?.message || error?.data?.message || error?.message || '保存配置失败'
  } finally {
    savePending.value = false
  }
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

function setUploadSiteRule(siteName, value) {
  const rules = Object.fromEntries(Object.entries(form.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }]))
  const current = rules[siteName] || { limit_kib: 0 }
  const limit = Number(value)
  current.limit_kib = Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : 0
  rules[siteName] = current
  form.upload_limit_site_rules = rules
}

function removeUploadSiteRule(siteName) {
  const rules = Object.fromEntries(Object.entries(form.upload_limit_site_rules || {}).map(([name, rule]) => [name, { ...rule }]))
  delete rules[siteName]
  form.upload_limit_site_rules = rules
}

// ═══ H&R 站点规则：内置预设 + 自定义 YAML 双层合并视图（v3.6.0）═══

/** 站点规则可编辑字段，键名与后端 HrSiteRule 一致。 */
const hrNumberFields = [
  { key: 'hr_duration', label: '做种时长（小时）' },
  { key: 'additional_seed_time', label: '额外做种时间（小时）' },
  { key: 'hr_deadline_days', label: '考核期（天）' },
  { key: 'hr_ratio', label: '分享率' },
  { key: 'hr_upload_multiplier', label: '上传倍数' },
]
const hrFlagFields = [
  { key: 'hr_upload_gte_download', label: '上传量≥下载量' },
  { key: 'hr_active', label: '强制纳管' },
]
const hrTierFields = [
  { key: 'max_size_gib', label: '上限（GiB）' },
  { key: 'hr_duration', label: '做种时长（小时）' },
  { key: 'hr_deadline_days', label: '考核期（天）' },
]
/** 生效值摘要列；布尔与分档字段单独格式化。 */
const hrSummaryFields = [
  { key: 'hr_duration', label: '做种时长', unit: ' 小时' },
  { key: 'additional_seed_time', label: '额外做种', unit: ' 小时' },
  { key: 'hr_deadline_days', label: '考核期', unit: ' 天' },
  { key: 'hr_ratio', label: '分享率', unit: '' },
  { key: 'hr_upload_multiplier', label: '上传倍数', unit: '' },
  { key: 'hr_upload_gte_download', label: '上传≥下载', unit: '', boolean: true },
  { key: 'hr_active', label: '强制纳管', unit: '', boolean: true },
  { key: 'hr_size_tiers', label: '体积分档', unit: '', tiers: true },
]
const hrTriStateItems = [
  { title: '继承全局', value: 'inherit' },
  { title: '是', value: 'true' },
  { title: '否', value: 'false' },
]

/** 全局规则当前值（config 表单的 hr_* 全局字段），供「继承」显示与 tooltip 使用。 */
const hrGlobalRule = computed(() => ({
  hr_duration: form.hr_duration,
  additional_seed_time: form.hr_additional_seed_time,
  hr_deadline_days: form.hr_deadline_days,
  hr_ratio: form.hr_ratio,
  hr_upload_multiplier: form.hr_upload_multiplier,
  hr_upload_gte_download: form.hr_upload_gte_download,
  hr_active: form.hr_active,
  hr_size_tiers: form.hr_size_tiers,
}))

function hrIsYamlFalse(value) {
  if (value === false) return true
  if (typeof value !== 'string') return false
  return ['false', '0', 'no', 'off'].includes(value.trim().toLowerCase())
}

function hrIsYamlTrue(value) {
  if (value === true) return true
  if (typeof value !== 'string') return false
  return ['true', '1', 'yes', 'on'].includes(value.trim().toLowerCase())
}

function hrFormatSummary(field, value) {
  if (field.tiers) return Array.isArray(value) ? `${value.length} 档` : '已配置'
  if (field.boolean) return hrIsYamlTrue(value) ? '是' : '否'
  const numeric = Number(value)
  return `${Number.isFinite(numeric) ? String(numeric) : String(value)}${field.unit || ''}`
}

function hrGlobalText(key) {
  const field = hrSummaryFields.find(item => item.key === key) || { key }
  const value = hrGlobalRule.value[key]
  if (value === undefined || value === null || value === '') return '未设置'
  return hrFormatSummary(field, value)
}

function hrHasRuleValues(rule) {
  if (!rule) return false
  if (Array.isArray(rule.hr_size_tiers)) return true
  if (Array.isArray(rule.trackers) && rule.trackers.length) return true
  return hrSiteRuleKeys.some(key => rule[key] !== undefined && rule[key] !== null)
}

function hrPresetRules() {
  const map = new Map()
  for (const preset of hrPresets.value) {
    const name = String(preset?.site_name || '').trim()
    if (name) map.set(name, preset?.rule || {})
  }
  return map
}

const hrSiteRows = computed(() => {
  const presets = hrPresetRules()
  const customMap = new Map()
  for (const rule of hrCustomRules.value) customMap.set(rule.site_name, rule)
  const extraNames = [...customMap.keys()].filter(name => !presets.has(name)).sort((left, right) => left.localeCompare(right, 'zh-CN'))
  const names = [...presets.keys(), ...extraNames]
  return names.map(name => {
    const preset = presets.get(name) || null
    const entry = customMap.get(name) || null
    const blocked = !!entry && hrIsYamlFalse(entry.enabled)
    // enabled 的自定义条目整条覆写预设；内置站的纯影子条目（仅 enabled:false）仍按内置行展示
    const customRow = !!entry && (!preset || !(blocked && !hrHasRuleValues(entry)))
    const sourceRule = blocked ? null : (customRow ? entry : preset)
    const sourceLabel = customRow ? (preset ? '自定义·覆写' : '自定义') : '内置'
    const sourceColor = sourceLabel === '内置' ? 'default' : (sourceLabel === '自定义·覆写' ? 'primary' : 'info')
    const cells = hrSummaryFields.map(field => {
      const value = sourceRule ? sourceRule[field.key] : undefined
      const inherited = value === undefined || value === null || value === ''
      return {
        key: field.key,
        label: field.label,
        inherited,
        text: inherited ? `继承 · ${hrGlobalText(field.key)}` : hrFormatSummary(field, value),
        tooltip: inherited
          ? `${field.label}：站点未设置，继承全局（${hrGlobalText(field.key)}）`
          : `${field.label}：${hrFormatSummary(field, value)}（${sourceLabel}）`,
      }
    })
    const visibleCells = hrShowInherited.value ? cells : cells.filter(cell => !cell.inherited)
    return {
      name,
      entry,
      preset: !!preset,
      enabled: !blocked,
      blocked,
      custom: customRow,
      expanded: hrExpandedSites.value.includes(name),
      cells,
      visibleCells,
      inheritedCount: cells.length - visibleCells.length,
      sourceLabel,
      sourceColor,
    }
  })
})

function hrFindCustomRule(name) {
  return hrCustomRules.value.find(rule => rule.site_name === name) || null
}

function hrReplaceCustomRule(name, rule) {
  hrCommitCustomRules(hrCustomRules.value.map(item => (item.site_name === name ? rule : item)))
}

function hrCommitCustomRules(rules) {
  hrCustomRules.value = rules
  const text = serializeHrSiteConfigYaml(rules)
  hrSyncedSiteConfigText = text
  hrRawError.value = ''
  form.hr_site_config_str = text
}

function hrSetSiteEnabled(name, enabled) {
  const entry = hrFindCustomRule(name)
  const nextEnabled = enabled !== false
  if (!entry) {
    if (!nextEnabled) hrCommitCustomRules([...hrCustomRules.value, { site_name: name, enabled: false }])
    return
  }
  // 内置站的纯影子条目：开启开关即删除条目，该站回到内置预设
  if (nextEnabled && hrIsYamlFalse(entry.enabled) && !hrHasRuleValues(entry) && hrPresetRules().has(name)) {
    hrRemoveCustomSite(name)
    return
  }
  hrReplaceCustomRule(name, { ...entry, enabled: nextEnabled })
}

function hrRemoveCustomSite(name) {
  hrCommitCustomRules(hrCustomRules.value.filter(rule => rule.site_name !== name))
}

function hrCopyPresetToCustom(name) {
  const preset = hrPresetRules().get(name) || {}
  const entry = hrFindCustomRule(name)
  const rule = { site_name: name, enabled: entry ? !hrIsYamlFalse(entry.enabled) : true }
  for (const field of [...hrNumberFields, ...hrFlagFields]) {
    const value = preset[field.key]
    if (value !== undefined && value !== null) rule[field.key] = value
  }
  if (Array.isArray(preset.hr_size_tiers)) rule.hr_size_tiers = preset.hr_size_tiers.map(tier => ({ ...tier }))
  hrCommitCustomRules([...hrCustomRules.value.filter(item => item.site_name !== name), rule])
  if (!hrExpandedSites.value.includes(name)) hrExpandedSites.value = [...hrExpandedSites.value, name]
}

function hrToggleExpanded(name) {
  hrExpandedSites.value = hrExpandedSites.value.includes(name)
    ? hrExpandedSites.value.filter(item => item !== name)
    : [...hrExpandedSites.value, name]
}

function hrRuleNumber(rule, key) {
  const value = rule?.[key]
  return value === undefined || value === null ? '' : value
}

function hrRuleFlag(rule, key) {
  const value = rule?.[key]
  if (value === undefined || value === null) return 'inherit'
  return hrIsYamlTrue(value) ? 'true' : 'false'
}

function hrRuleTrackers(rule) {
  return Array.isArray(rule?.trackers) ? [...rule.trackers] : []
}

function hrNormalizeTrackers(value) {
  const items = Array.isArray(value) ? value : [value]
  const result = []
  for (const item of items) {
    const text = String(item ?? '').trim()
    if (text && !result.includes(text)) result.push(text)
  }
  return result
}

function hrSetRuleTrackers(name, value) {
  const entry = hrFindCustomRule(name)
  if (!entry) return
  const next = { ...entry }
  const trackers = hrNormalizeTrackers(value)
  if (trackers.length) next.trackers = trackers
  else delete next.trackers
  hrReplaceCustomRule(name, next)
}

function hrTierNumber(tier, key) {
  const value = tier?.[key]
  return value === undefined || value === null ? 0 : value
}

function hrSetRuleNumber(name, key, value) {
  const entry = hrFindCustomRule(name)
  if (!entry) return
  const next = { ...entry }
  const text = String(value ?? '').trim()
  if (!text) {
    delete next[key]
  } else {
    const numeric = Number(text)
    if (!Number.isFinite(numeric)) return
    next[key] = numeric
  }
  hrReplaceCustomRule(name, next)
}

function hrSetRuleFlag(name, key, value) {
  const entry = hrFindCustomRule(name)
  if (!entry) return
  const next = { ...entry }
  if (value === 'inherit') delete next[key]
  else next[key] = value === 'true'
  hrReplaceCustomRule(name, next)
}

function hrAddTier(name) {
  const entry = hrFindCustomRule(name)
  if (!entry) return
  const tiers = (entry.hr_size_tiers || []).map(tier => ({ ...tier }))
  tiers.push({ max_size_gib: 0, hr_duration: 0, hr_deadline_days: 0 })
  hrReplaceCustomRule(name, { ...entry, hr_size_tiers: tiers })
}

function hrRemoveTier(name, index) {
  const entry = hrFindCustomRule(name)
  if (!entry) return
  const tiers = (entry.hr_size_tiers || []).filter((_, position) => position !== index)
  const next = { ...entry }
  if (tiers.length) next.hr_size_tiers = tiers
  else delete next.hr_size_tiers
  hrReplaceCustomRule(name, next)
}

function hrSetTierNumber(name, index, key, value) {
  const entry = hrFindCustomRule(name)
  if (!entry) return
  const tiers = (entry.hr_size_tiers || []).map(tier => ({ ...tier }))
  if (!tiers[index]) return
  const text = String(value ?? '').trim()
  const numeric = text ? Number(text) : 0
  tiers[index] = { ...tiers[index], [key]: Number.isFinite(numeric) ? numeric : 0 }
  hrReplaceCustomRule(name, { ...entry, hr_size_tiers: tiers })
}

function hrOpenAddDialog() {
  hrNewSiteName.value = ''
  hrAddError.value = ''
  hrAddDialog.value = true
}

function hrConfirmAddSite() {
  hrAddError.value = ''
  const name = hrNewSiteName.value.trim()
  if (!name) {
    hrAddError.value = '请输入站点名'
    return
  }
  if (hrPresetRules().has(name)) {
    hrAddError.value = '该站点是内置预设，请用「复制为自定义」创建覆写'
    return
  }
  if (hrCustomRules.value.some(rule => rule.site_name === name)) {
    hrAddError.value = '该站点已存在自定义条目'
    return
  }
  hrCommitCustomRules([...hrCustomRules.value, { site_name: name, enabled: true }])
  hrExpandedSites.value = [...hrExpandedSites.value, name]
  hrAddDialog.value = false
}

async function loadHrPresets(force = false) {
  if (hrPresetsLoading.value || (hrPresetsLoaded.value && !force)) return
  hrPresetsLoading.value = true
  hrPresetsMessage.value = ''
  try {
    const response = await getApi('hr_presets', { feedback: 'silent' })
    const presets = Array.isArray(response?.presets) ? response.presets : []
    hrPresets.value = presets.filter(preset => String(preset?.site_name || '').trim())
    hrPresetsLoaded.value = true
    if (!hrPresets.value.length) hrPresetsMessage.value = '未返回内置预设，可继续使用自定义站点规则'
  } catch (error) {
    hrPresetsMessage.value = error?.message || '内置预设获取失败'
  } finally {
    hrPresetsLoading.value = false
  }
}

function hrApplySiteConfigText(text) {
  const parsed = parseHrSiteConfigYaml(text)
  if (parsed.error) {
    hrRawError.value = `站点规则 YAML 解析失败：${parsed.error}`
    hrRawOpen.value = true
    return
  }
  hrRawError.value = ''
  hrCustomRules.value = parsed.rules
}

function syncHrSiteRulesFromForm() {
  const text = String(form.hr_site_config_str ?? '')
  hrSyncedSiteConfigText = text
  hrApplySiteConfigText(text)
}

watch(() => form.hr_site_config_str, raw => {
  const text = String(raw ?? '')
  if (text === hrSyncedSiteConfigText) return
  hrSyncedSiteConfigText = text
  hrApplySiteConfigText(text)
})

// ── hr_site_config_str 的最小 YAML 列表读写（只覆盖后端接受的字段结构）──

function hrStripComment(line) {
  let quote = ''
  for (let index = 0; index < line.length; index++) {
    const char = line.charAt(index)
    if (quote) {
      if (char === quote) quote = ''
      continue
    }
    if (char === '"' || char === "'") {
      quote = char
      continue
    }
    if (char === '#') {
      const previous = index === 0 ? '' : line.charAt(index - 1)
      if (index === 0 || previous === ' ' || previous === '\t') return line.slice(0, index)
    }
  }
  return line
}

function hrSplitKeyValue(text) {
  let quote = ''
  for (let index = 0; index < text.length; index++) {
    const char = text.charAt(index)
    if (quote) {
      if (char === quote) quote = ''
      continue
    }
    if (char === '"' || char === "'") {
      quote = char
      continue
    }
    if (char === ':') {
      const next = index + 1 < text.length ? text.charAt(index + 1) : ''
      if (!next || next === ' ' || next === '\t') {
        const key = text.slice(0, index).trim()
        return key ? { key, valueText: text.slice(index + 1).trim() } : null
      }
    }
  }
  return null
}

function hrParseScalar(text) {
  const trimmed = String(text ?? '').trim()
  if (!trimmed) return { value: null }
  const lower = trimmed.toLowerCase()
  if (trimmed === '~' || lower === 'null') return { value: null }
  if (['true', 'yes', 'on'].includes(lower)) return { value: true }
  if (['false', 'no', 'off'].includes(lower)) return { value: false }
  if (trimmed === '[]') return { value: [] }
  if (trimmed.startsWith('[') || trimmed.startsWith('{')) return { error: `${trimmed} 为行内列表/映射，暂不支持` }
  if (trimmed === '|' || trimmed === '>') return { error: '暂不支持块标量文本' }
  if (trimmed.length > 1 && trimmed.startsWith("'") && trimmed.endsWith("'")) return { value: trimmed.slice(1, -1).replaceAll("''", "'") }
  if (trimmed.length > 1 && trimmed.startsWith('"') && trimmed.endsWith('"')) return { value: trimmed.slice(1, -1).replaceAll('\\"', '"') }
  if (/^[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?$/.test(trimmed)) return { value: Number(trimmed) }
  return { value: trimmed }
}

function hrSplitFlowItems(text) {
  const items = []
  let buffer = ''
  let quote = ''
  for (let index = 0; index < text.length; index++) {
    const char = text.charAt(index)
    if (quote) {
      buffer += char
      if (char === quote) quote = ''
      continue
    }
    if (char === '"' || char === "'") {
      quote = char
      buffer += char
      continue
    }
    if (char === ',') {
      items.push(buffer.trim())
      buffer = ''
      continue
    }
    buffer += char
  }
  items.push(buffer.trim())
  return items.filter(item => item !== '')
}

function hrParseFlowList(valueText) {
  const text = String(valueText ?? '').trim()
  if (!text.endsWith(']')) return { error: `${text} 行内列表未闭合` }
  const inner = text.slice(1, -1).trim()
  if (!inner) return { value: [] }
  const values = []
  for (const item of hrSplitFlowItems(inner)) {
    const parsed = hrParseScalar(item)
    if (parsed.error) return { error: parsed.error }
    if (Array.isArray(parsed.value)) return { error: `列表项 ${item} 不是标量` }
    if (parsed.value === null || parsed.value === '') continue
    values.push(typeof parsed.value === 'string' ? parsed.value : String(parsed.value))
  }
  return { value: values }
}

function hrAssignScalar(target, key, valueText) {
  const text = String(valueText ?? '').trim()
  if (hrListRuleKeys.includes(key) && text.startsWith('[')) {
    const parsedList = hrParseFlowList(text)
    if (parsedList.error) return `字段 ${key}：${parsedList.error}`
    target[key] = parsedList.value
    return ''
  }
  const parsed = hrParseScalar(valueText)
  if (parsed.error) return `字段 ${key}：${parsed.error}`
  if (Array.isArray(parsed.value)) {
    if (key !== 'hr_size_tiers') return `字段 ${key} 不接受列表值`
    target.hr_size_tiers = []
    return ''
  }
  target[key] = parsed.value
  return ''
}

function parseHrSiteConfigYaml(raw) {
  const lines = String(raw ?? '').replace(/\r\n?/g, '\n').split('\n')
  const items = []
  let entry = null
  let tier = null
  let itemIndent = null
  let entryIndent = null
  let tiersIndent = null
  let tierIndent = null
  let inTiers = false
  let inTrackers = false
  let trackersIndent = null
  for (let index = 0; index < lines.length; index++) {
    const content = hrStripComment(lines[index])
    const body = content.trim()
    if (!body || body === '---' || body === '...') continue
    const indent = content.length - content.trimStart().length
    const second = body.charAt(1)
    const isItem = body.startsWith('-') && (body.length === 1 || second === ' ' || second === '\t')
    const rest = body.length === 1 ? '' : body.slice(2).trim()
    if (isItem) {
      if (inTiers && (tierIndent === null || indent >= tierIndent)) {
        if (tierIndent === null) tierIndent = indent
        tier = {}
        if (!Array.isArray(entry.hr_size_tiers)) entry.hr_size_tiers = []
        entry.hr_size_tiers.push(tier)
        if (rest) {
          const pair = hrSplitKeyValue(rest)
          if (!pair) return { error: `第 ${index + 1} 行无法解析「${rest}」` }
          const failure = hrAssignScalar(tier, pair.key, pair.valueText)
          if (failure) return { error: `第 ${index + 1} 行 ${failure}` }
        }
        continue
      }
      if (inTrackers && (trackersIndent === null || indent >= trackersIndent)) {
        if (trackersIndent === null) trackersIndent = indent
        if (!Array.isArray(entry.trackers)) entry.trackers = []
        const scalar = hrParseScalar(rest)
        if (scalar.error) return { error: `第 ${index + 1} 行 ${scalar.error}` }
        if (!Array.isArray(scalar.value) && scalar.value !== null && scalar.value !== '') {
          entry.trackers.push(String(scalar.value))
        }
        continue
      }
      inTiers = false
      inTrackers = false
      tier = null
      if (itemIndent === null) itemIndent = indent
      if (indent !== itemIndent) return { error: `第 ${index + 1} 行列表项缩进与首项不一致` }
      entry = {}
      entryIndent = null
      tiersIndent = null
      tierIndent = null
      trackersIndent = null
      items.push(entry)
      if (rest) {
        const pair = hrSplitKeyValue(rest)
        if (!pair) return { error: `第 ${index + 1} 行无法解析「${rest}」` }
        const failure = hrAssignScalar(entry, pair.key, pair.valueText)
        if (failure) return { error: `第 ${index + 1} 行 ${failure}` }
      }
      continue
    }
    const pair = hrSplitKeyValue(body)
    if (!pair) return { error: `第 ${index + 1} 行无法解析「${body}」` }
    if (inTiers && tiersIndent !== null && indent <= tiersIndent) {
      inTiers = false
      tier = null
    }
    if (inTrackers && trackersIndent !== null && indent <= trackersIndent) inTrackers = false
    if (inTrackers) return { error: `第 ${index + 1} 行 ${pair.key} 不是列表项（trackers 只接受「- 值」形式）` }
    if (inTiers) {
      if (!tier) return { error: `第 ${index + 1} 行分档字段缺少所属分档项` }
      const failure = hrAssignScalar(tier, pair.key, pair.valueText)
      if (failure) return { error: `第 ${index + 1} 行 ${failure}` }
      continue
    }
    if (!entry) return { error: `第 ${index + 1} 行：顶层必须是列表，每项以「- site_name: 站点名」开头` }
    if (entryIndent === null) entryIndent = indent
    else if (indent !== entryIndent) return { error: `第 ${index + 1} 行缩进与首字段不一致` }
    if (!pair.valueText) {
      if (pair.key === 'hr_size_tiers') {
        inTiers = true
        tiersIndent = indent
        tierIndent = null
        tier = null
        entry.hr_size_tiers = []
        continue
      }
      if (hrListRuleKeys.includes(pair.key)) {
        inTrackers = true
        trackersIndent = indent
        entry[pair.key] = []
        continue
      }
      return { error: `第 ${index + 1} 行 ${pair.key} 缺少值（仅 hr_size_tiers 与 trackers 支持列表）` }
    }
    const failure = hrAssignScalar(entry, pair.key, pair.valueText)
    if (failure) return { error: `第 ${index + 1} 行 ${failure}` }
  }
  const merged = []
  const positionByName = new Map()
  for (const item of items) {
    const name = String(item.site_name ?? '').trim()
    if (!name) return { error: '存在缺少 site_name 的站点条目' }
    const rule = { site_name: name }
    const extra = {}
    for (const [key, value] of Object.entries(item)) {
      if (key === 'site_name' || key === 'hr_size_tiers') continue
      if (key === 'enabled') {
        rule.enabled = !hrIsYamlFalse(value)
        continue
      }
      if (hrSiteRuleKeys.includes(key)) rule[key] = value
      else if (hrListRuleKeys.includes(key)) rule[key] = hrNormalizeTrackers(Array.isArray(value) ? value : [value])
      else extra[key] = value
    }
    if (Object.keys(extra).length) rule._extra = extra
    if (rule.enabled === undefined) rule.enabled = true
    if (Array.isArray(item.hr_size_tiers)) {
      rule.hr_size_tiers = item.hr_size_tiers.map(item => {
        const values = {}
        for (const field of hrTierFields) {
          const numeric = Number(item?.[field.key])
          if (Number.isFinite(numeric)) values[field.key] = numeric
        }
        return values
      })
    }
    // 与后端一致：同名后项覆盖前项
    const existing = positionByName.get(name)
    if (existing === undefined) {
      positionByName.set(name, merged.length)
      merged.push(rule)
    } else {
      merged[existing] = rule
    }
  }
  return { rules: merged }
}

function hrQuoteYaml(value) {
  return `'${String(value).replaceAll("'", "''")}'`
}

function hrYamlScalar(value) {
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  if (value === null || value === undefined) return 'null'
  if (Array.isArray(value)) return '[]'
  if (typeof value === 'object') return hrQuoteYaml(JSON.stringify(value))
  return hrQuoteYaml(value)
}

function serializeHrSiteConfigYaml(rules) {
  const blocks = []
  for (const rule of rules || []) {
    const name = String(rule?.site_name || '').trim()
    if (!name) continue
    const lines = [`- site_name: ${hrQuoteYaml(name)}`]
    for (const key of hrSiteRuleKeys) {
      const value = rule[key]
      if (value === undefined || value === null) continue
      lines.push(`  ${key}: ${hrYamlScalar(value)}`)
    }
    if (Array.isArray(rule.trackers) && rule.trackers.length) {
      lines.push('  trackers:')
      for (const tracker of rule.trackers) {
        const text = String(tracker ?? '').trim()
        if (text) lines.push(`    - ${hrQuoteYaml(text)}`)
      }
    }
    if (Array.isArray(rule.hr_size_tiers)) {
      if (!rule.hr_size_tiers.length) {
        lines.push('  hr_size_tiers: []')
      } else {
        lines.push('  hr_size_tiers:')
        for (const tier of rule.hr_size_tiers) {
          const limit = Number(tier?.max_size_gib)
          lines.push(`    - max_size_gib: ${Number.isFinite(limit) ? limit : 0}`)
          for (const key of hrTierValueKeys) {
            const numeric = Number(tier?.[key])
            if (Number.isFinite(numeric)) lines.push(`      ${key}: ${numeric}`)
          }
        }
      }
    }
    for (const [key, value] of Object.entries(rule._extra || {})) {
      lines.push(`  ${key}: ${hrYamlScalar(value)}`)
    }
    lines.push(`  enabled: ${rule.enabled === false ? 'false' : 'true'}`)
    blocks.push(lines.join('\n'))
  }
  return blocks.join('\n\n')
}

watch(() => props.initialConfig, v => {
Object.keys(form).forEach(k => delete form[k])
  Object.assign(form, defaults, v || {})
  // 决策 A：全新安装（后端没有已保存配置）时观察模式默认开启；老配置升级保持升级前行为。
  if (!v || !Object.keys(v).length) {
    for (const key of OBSERVE_ONLY_KEYS) form[key] = true
  }
  // 决策 A：自动删种继承旧「仅观察不执行」开关（仅在旧键存在且未保存过新键时生效）
  if (v?.migration_observe_only !== undefined && v?.remover_observe_only === undefined) {
    form.remover_observe_only = !!v.migration_observe_only
  }
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
  form.tag_all_cat = [...(v?.tag_all_cat || [])]
  form.tag_all_cat_rename = [...(v?.tag_all_cat_rename || [])]
  tagCatPairs.value = parseCatPairs(form.tag_all_cat, form.tag_all_cat_rename)
  const customLabels = parseCustomSiteLabels(form.tag_custom_sites_str)
  tagTrackerPairs.value = parseTrackerPairs(form.tag_tracker_mappings_str).map(p => ({
    ...p,
    custom: customLabels[String(p.site || p.tracker || '').trim().toLowerCase()] || '',
  }))
  syncHrSiteRulesFromForm()
  transferTasks.value = parseTransferTasks(form.transfer_tasks)
  transferExt.value = parseDownloaderExt(form.downloader_ext)
}, { immediate: true, deep: true })
</script>
<template>
  <div class="dm-config">
    <VCard flat class="dm-card">
      <VCardItem class="dm-header">
        <template #prepend>
          <VAvatar color="primary" variant="tonal" size="44" rounded="lg">
            <VIcon icon="mdi-download" size="24" />
          </VAvatar>
        </template>
        <VCardTitle class="dm-title">下载中心</VCardTitle>
        <VCardSubtitle class="dm-hint">{{ currentMain.desc }}</VCardSubtitle>
        <template #append>
          <VSwitch density="compact" v-model="form.enabled" color="primary" hide-details inset :label="form.enabled ? '已启用' : '已停用'" />
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
            <VBtn size="small" v-if="PANE_RESET_KEYS[activeMain]" variant="text" color="warning"
              prepend-icon="mdi-restore" class="ml-auto" @click="askPaneReset(activeMain)">
              恢复默认
            </VBtn>
          </div>
          <VDivider />
          <div class="dm-window">
            <!-- ═══ 上传限速 · 基础设置 ═══ -->
            <div v-show="activeSub === 'upload_basic'" class="dm-pane">
              <div class="dm-section-title">基础设置</div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.upload_limit_enabled" color="primary" inset hide-details label="启用" />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.upload_limit_observe_only" color="warning" inset hide-details label="观察模式" />
                  <div v-if="form.upload_limit_observe_only" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" /> 观察模式：不调整任何上传限速，已有额度保持原样，也不执行恢复；诊断页可看预览统计</div>
                </div>
                <div class="dm-field">
                  <VSelect density="compact" v-model="form.upload_limit_downloaders" :error-messages="form.upload_limit_enabled && !uploadSelectedDownloaders.length ? '请至少选择一个下载器' : ''" label="下载器" variant="outlined"
                    :items="uploadDownloaderItems" multiple chips closable-chips clearable
                    hint="只扫描和修改这里选中的 qBittorrent / Transmission 实例" persistent-hint />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--number">
                  <VTextField density="compact" class="dm-number-input" v-model.number="form.upload_limit_grace_minutes" label="新种宽限（分钟）" type="number" min="0" max="1440" variant="outlined" hint="默认 30；填 0 表示完成后立即纳入分配" persistent-hint />
                </div>
              </div>
              <div  class="dm-hint mt-4">
                单位为 KiB/s（1 Mbps ≈ 122 KiB/s）。宽限期间不做站点和单种分配，但仍受对应下载器总上传上限。
              </div>
            </div>

            <!-- ═══ 上传限速 · 限速规则 ═══ -->
            <div v-show="activeSub === 'upload_rules'" class="dm-pane">
              <div class="dm-section-title">下载器总上限</div>
              <div v-if="uploadSelectedDownloaders.length" class="dm-upload-downloader-list">
                <div v-for="item in uploadSelectedDownloaders" :key="item.value" class="dm-upload-config-row">
                  <div class="dm-upload-config-name">
                    <VIcon :icon="item.type === 'transmission' ? 'mdi-transmission-tower' : 'mdi-download-network-outline'" size="19" color="primary" />
                    <div class="min-w-0">
                      <strong>{{ item.title }}</strong>
                      <div class="dm-hint">
                        {{ item.type === 'transmission' ? 'Transmission Session 上传上限' : 'qB 普通与备用上传上限' }}
                      </div>
                    </div>
                  </div>
                  <VTextField density="compact" class="dm-number-input" :model-value="uploadDownloaderLimit(item.value)"
                    @update:model-value="setUploadDownloaderLimit(item.value, $event)"
                     :error-messages="form.upload_limit_enabled && uploadMissingLimits.some(missing => missing.value === item.value) ? '请设置正整数总上限' : ''" label="总上限（KiB/s）" type="number" min="1" step="1" variant="outlined"
                    hint="必须大于 0；以插件配置为准" persistent-hint />
                </div>
              </div>
              <div v-else class="dm-monitor-empty dm-hint">尚未选择限速下载器</div>

              <div class="dm-section-title mt-4">站点限速表</div>
              <div  class="dm-hint mt-3">
                仅识别唯一有效的「{{ form.tag_siteprefix || '🏠' }}站点名」标签。上限留空或填 0 时不写单种限速，该站点仍受下载器全局上限约束。
              </div>
              <div v-if="uploadSiteRuleRows.length" class="dm-upload-site-list mt-4">
                <div v-for="row in uploadSiteRuleRows" :key="row.name" class="dm-upload-site-row">
                  <div class="dm-upload-site-name">
                    <VIcon icon="mdi-home-outline" size="19" color="primary" />
                    <div class="min-w-0">
                      <strong class="dm-body-text">{{ row.name }}</strong>
                      <div class="dm-hint">{{ form.tag_siteprefix || '🏠' }}{{ row.name }}</div>
                    </div>
                  </div>
                  <VTextField density="compact" class="dm-number-input" :model-value="row.limit_kib" @update:model-value="setUploadSiteRule(row.name, $event)"
                    label="合计上限（KiB/s）" type="number" min="0" step="1" clearable variant="outlined"
                    hint="留空或 0 表示该站点不限速；正数为跨下载器共享的站点合计上限" persistent-hint />
                  <VBtn size="small" aria-label="删除站点" icon="mdi-delete-outline" color="primary" variant="text" title="删除站点"
                    @click="removeUploadSiteRule(row.name)" />
                </div>
              </div>
              <div v-else class="dm-monitor-empty mt-3 dm-hint">尚未配置站点上限；没有站点上限时只应用下载器全局上限</div>
              <div  class="dm-hint mt-4">
                正数上限限制该站点全部任务的合计上传速度；多个受限站点在下载器全局额度内按实际需求共享可用带宽。
              </div>
            </div>

            <!-- ═══ 转移做种 · 基础设置 ═══ -->
            <div v-show="activeSub === 'basic'" class="dm-pane">
              <div class="dm-section-title">基础设置</div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.transfer_enabled" color="primary" inset hide-details label="启用" />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.transfer_observe_only" color="warning" inset hide-details label="观察模式" />
                  <div v-if="form.transfer_observe_only" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" /> 观察模式：转移任务只统计（诊断页可见），不向目标下载器添加种子、不删除源种子</div>
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.notify" color="primary" inset hide-details label="发送通知" />
                </div>
              </div>
              <div class="dm-section-title mt-4">触发与执行</div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--number">
                  <VTextField density="compact" class="dm-number-input" v-model.number="form.delay_minutes" label="延迟时间（分钟）" type="number" variant="outlined"
                    hint="下载完成后延迟 N 分钟再转移" persistent-hint />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--number">
                  <VTextField density="compact" class="dm-number-input" v-model.number="form.transfer_fallback_interval_minutes" label="兜底间隔（分钟）" type="number" min="1" variant="outlined"
                    :disabled="!form.transfer_fallback_enabled" hint="事件漏触发时按此间隔扫描，默认60分钟" persistent-hint />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.transfer_fallback_enabled" color="primary" inset hide-details label="兜底扫描" />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--number">
                  <VTextField density="compact" class="dm-number-input" v-model.number="form.scan_limit" label="源端扫描上限（个）" type="number" min="1" variant="outlined"
                    hint="每轮最多检查的源种子数量，默认 500" persistent-hint />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.pause_source" color="primary" inset hide-details label="暂停源任务" />
                </div>
              </div>
              <div class="dm-section-title mt-4">转移后重命名</div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.transfer_rename_enabled" color="primary" inset hide-details label="转移后重命名" />
                  <div class="dm-hint">仅 qB 目的端生效：修改显示名，不动磁盘文件；Transmission 目的端自动跳过</div>
                </div>
              </div>
            </div>

            <!-- ═══ 转移做种 · 任务列表 ═══ -->
            <div v-show="activeSub === 'tasks'" class="dm-pane">
              <div class="dm-task-toolbar">
                <div class="min-w-0">
                  <div class="dm-section-title mb-1">任务列表</div>
                  <div class="dm-hint">每个任务独立配置源/目的下载器、数据可见性映射、筛选条件与高级选项，保存后写回 transfer_tasks。</div>
                </div>
                <VBtn size="small" color="primary" variant="tonal" prepend-icon="mdi-plus" @click="openTransferDialog()">添加任务</VBtn>
              </div>
              <div class="dm-task-table mt-3">
                <div class="dm-task-row dm-task-row--head">
                  <span>名称</span>
                  <span>状态</span>
                  <span>下载器</span>
                  <span>数据映射</span>
                  <span>筛选条件</span>
                  <span>设置</span>
                  <span class="dm-task-actions">操作</span>
                </div>
                <div v-for="(task, idx) in transferTasks" :key="`transfer-task-${idx}`" class="dm-task-row">
                  <div class="dm-task-name">
                    <strong class="dm-break-text">{{ task.name }}</strong>
                    <span class="dm-hint">转移标签：{{ task.transfer_tag || '不打标签' }}</span>
                  </div>
                  <div class="dm-task-state">
                    <VSwitch density="compact" v-model="task.enabled" inset hide-details />
                    <span class="dm-hint">{{ task.enabled ? '启用' : '停用' }}</span>
                  </div>
                  <div class="dm-task-route">
                    <span class="dm-route-item">
                      <DownloaderBadge :name="downloaderTitle(task.from_downloader)"
                        :type="downloaderTypeOf(task.from_downloader)" :size="16" />
                    </span>
                    <VIcon icon="mdi-arrow-right" size="15" class="dm-map-arrow" />
                    <span class="dm-route-item">
                      <DownloaderBadge :name="downloaderTitle(task.to_downloader)"
                        :type="downloaderTypeOf(task.to_downloader)" :size="16" />
                    </span>
                  </div>
                  <div class="dm-task-paths">
                    <span class="dm-hint dm-break-text">{{ task.from_path || '—' }}</span>
                    <div class="dm-hint dm-map-arrow">→ {{ task.to_path || '—' }}</div>
                  </div>
                  <div class="dm-task-filters">
                    <VChip v-for="chip in taskFilterChips(task)" :key="chip" size="x-small" variant="tonal"
                      color="secondary">{{ chip }}</VChip>
                  </div>
                  <div class="dm-task-settings">
                    <VChip v-for="badge in taskSettingBadges(task)" :key="badge.text" size="x-small" variant="flat"
                      :color="badge.color">{{ badge.text }}</VChip>
                    <span v-if="!taskSettingBadges(task).length" class="dm-hint">默认</span>
                  </div>
                  <div class="dm-task-actions">
                    <VBtn size="small" aria-label="编辑任务" icon="mdi-pencil-outline" variant="text" title="编辑任务"
                      @click="openTransferDialog(idx)" />
                    <VBtn size="small" aria-label="删除任务" icon="mdi-delete-outline" variant="text" color="primary" title="删除任务"
                      @click="askTransferDelete(idx)" />
                  </div>
                </div>
                <div v-if="!transferTasks.length" class="dm-map-empty dm-hint">暂无转移任务，点击右上角「添加任务」创建。</div>
              </div>
            </div>

            <!-- ═══ H&R · 基础设置 ═══ -->
            <div v-show="activeSub === 'hr_basic'" class="dm-pane">
              <div class="dm-section-title">基础设置</div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.hr_enabled" color="primary" inset hide-details label="启用" />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.hr_observe_only" color="warning" inset hide-details label="观察模式" />
                  <div v-if="form.hr_observe_only" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" /> 观察模式：检查与统计照常，但不给种子打 H&R 标签、不移除标签</div>
                </div>
                <div class="dm-field">
                  <VSelect density="compact" v-model="form.hr_notify" label="通知模式" variant="outlined"
                    :items="hrNotifyModeItems" hint="不发送 / 仅异常 / 全部" persistent-hint />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.hr_auto_discover" color="primary" inset hide-details label="自动发现" />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.hr_enable_site_config" color="primary" inset hide-details label="站点独立规则" />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field">
                  <VSelect density="compact" v-model="form.hr_downloader" label="下载器" variant="outlined"
                    :items="downloaderItems" multiple chips closable-chips clearable hint="选择需要跟踪 H&R 的下载器" persistent-hint />
                </div>
                <div class="dm-field">
                  <VSelect density="compact" v-model="form.hr_sites" label="站点白名单" variant="outlined"
                    :items="siteItems" item-title="title" item-value="title" multiple chips closable-chips clearable
                    hint="只跟踪这些站点的种子（按站点名）；留空表示全部站点" persistent-hint />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.hr_hit_and_run_tag" label="H&R 标签" variant="outlined"
                    hint="未达标任务打上的标签，默认 H&R" persistent-hint />
                </div>
                <div class="dm-field">
                  <VSelect density="compact" v-model="form.hr_brush_plugin" label="刷流插件" variant="outlined"
                    :items="hrBrushPluginItems" hint="仅支持 BrushFlow；选择「不启用」表示不使用刷流任务跟踪" persistent-hint />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field">
                  <VCombobox density="compact" v-model="form.hr_exclude_tags" label="排除标签" variant="outlined"
                    multiple chips closable-chips hint="输入后按回车添加；带这些标签的任务不纳入 H&R" persistent-hint />
                </div>
                <div class="dm-field">
                  <VCombobox density="compact" v-model="form.hr_exclude_categories" label="排除分类" variant="outlined"
                    multiple chips closable-chips hint="输入后按回车添加；这些分类的任务不纳入 H&R" persistent-hint />
                </div>
              </div>

              <div class="dm-section-title mt-4">考核规则</div>
              <div class="dm-hr-global-card mt-1">
                <div class="dm-hr-global-head">
                  <span class="dm-section-title mb-0">全局规则基准</span>
                  <span class="dm-hint">站点规则未设置的字段回退到这里；站点规则表中灰字即为此处的值</span>
                </div>
                <div class="dm-field-row">
                  <div class="dm-field dm-field--number">
                    <VTextField density="compact" class="dm-number-input" v-model.number="form.hr_duration" label="做种时长（小时）" type="number" variant="outlined" hint="默认 48" persistent-hint />
                  </div>
                  <div class="dm-field dm-field--number">
                    <VTextField density="compact" class="dm-number-input" v-model.number="form.hr_deadline_days" label="考核期（天）" type="number" variant="outlined" hint="默认 14" persistent-hint />
                  </div>
                  <div class="dm-field dm-field--number">
                    <VTextField density="compact" class="dm-number-input" v-model.number="form.hr_additional_seed_time" label="额外做种（小时）" type="number" variant="outlined" hint="默认 24" persistent-hint />
                  </div>
                </div>
                <div class="dm-field-row">
                  <div class="dm-field dm-field--number">
                    <VTextField density="compact" class="dm-number-input" v-model.number="form.hr_ratio" label="分享率" type="number" variant="outlined" hint="留空表示不校验分享率" persistent-hint />
                  </div>
                  <div class="dm-field dm-field--number">
                    <VTextField density="compact" class="dm-number-input" v-model.number="form.hr_upload_multiplier" label="上传倍数" type="number" variant="outlined" hint="留空表示不校验上传倍数" persistent-hint />
                  </div>
                </div>
                <div class="dm-field-row">
                  <div class="dm-field dm-field--toggle">
                    <VSwitch density="compact" v-model="form.hr_upload_gte_download" color="primary" inset hide-details label="上传量≥下载量" />
                  </div>
                  <div class="dm-field dm-field--toggle">
                    <VSwitch density="compact" v-model="form.hr_active" color="primary" inset hide-details label="强制纳管" />
                    <div class="dm-hint">将适用范围内任务按本规则强制纳管。</div>
                  </div>
                </div>
              </div>

              <div class="dm-section-title mt-4">运行调度</div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--number">
                  <VTextField density="compact" class="dm-number-input" v-model.number="form.hr_check_period" label="检查间隔（分钟）" type="number" variant="outlined"
                    hint="默认 10 分钟" persistent-hint />
                </div>
                <div class="dm-field">
                  <VCronField density="compact" v-model="form.hr_notify_summary_cron" label="汇总计划" variant="outlined" hide-details />
                </div>
              </div>
            </div>

            <!-- ═══ H&R · 站点规则 ═══ -->
            <div v-show="activeSub === 'hr_sites'" class="dm-pane">
              <div class="dm-section-title">站点规则</div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--full">
                  <div class="dm-hr-toolbar">
                    <div>
                      <div class="dm-section-title mb-1">站点规则</div>
                      <div class="dm-hint">
                        内置预设为底，自定义站点同名整条覆写；关闭站点开关会写入 enabled: false 影子条目，该站回退全局规则。
                        <span class="dm-hr-legend">
                          <span class="dm-hr-chip dm-hr-chip--mini"><span class="dm-hr-chip-value">站点显式设置</span></span>
                          <span class="dm-hr-chip dm-hr-chip--mini dm-hr-chip--inherit"><span class="dm-hr-chip-value">灰字 = 继承全局</span></span>
                        </span>
                      </div>
                    </div>
                    <div class="d-flex align-center ga-2 flex-wrap">
                      <VSwitch density="compact" v-model="hrShowInherited" color="primary" inset hide-details
                        label="显示继承字段" />
                      <VBtn size="small" variant="text" prepend-icon="mdi-refresh" :loading="hrPresetsLoading"
                        @click="loadHrPresets(true)">重载预设</VBtn>
                      <VBtn size="small" color="primary" variant="tonal" prepend-icon="mdi-home-plus-outline"
                        @click="hrOpenAddDialog">添加站点</VBtn>
                    </div>
                  </div>
                  <div v-if="!form.hr_enable_site_config" class="dm-hint mt-3">
                    「站点独立规则」当前关闭：内置预设与自定义规则都不生效，全部站点回退全局规则。
                  </div>
                  <VAlert v-if="hrPresetsMessage" type="warning" variant="tonal" density="compact" closable class="mt-3"
                    @click:close="hrPresetsMessage = ''">{{ hrPresetsMessage }}</VAlert>

                  <div class="dm-hr-table mt-3">
                    <div class="dm-hr-row dm-hr-row--head">
                      <span>站点</span>
                      <span>生效值</span>
                      <span>来源</span>
                      <span>启用</span>
                      <span>操作</span>
                    </div>
                    <template v-for="row in hrSiteRows" :key="row.name">
                      <div class="dm-hr-row" :class="{ 'dm-hr-row--blocked': row.blocked }">
                        <div class="dm-hr-site">
                          <strong class="dm-body-text dm-break-text">{{ row.name }}</strong>
                          <div v-if="row.blocked" class="dm-hint">已屏蔽，回退全局</div>
                        </div>
                        <div class="dm-hr-values">
                          <template v-if="row.visibleCells.length">
                            <span v-for="cell in row.visibleCells" :key="cell.key" class="dm-hr-chip"
                              :class="{ 'dm-hr-chip--inherit': cell.inherited }" :title="cell.tooltip">
                              <span class="dm-hr-chip-label dm-hint">{{ cell.label }}</span>
                              <span class="dm-hr-chip-value">{{ cell.text }}</span>
                            </span>
                          </template>
                          <span v-else class="dm-hr-values-empty dm-hint">全部字段继承全局规则</span>
                          <span v-if="row.inheritedCount > 0 && !hrShowInherited" class="dm-hr-chip dm-hr-chip--more"
                            :title="`还有 ${row.inheritedCount} 项继承全局，打开右上角「显示继承字段」查看`">
                            +{{ row.inheritedCount }} 项继承
                          </span>
                        </div>
                        <div>
                          <VChip size="x-small" variant="tonal" :color="row.sourceColor">{{ row.sourceLabel }}</VChip>
                        </div>
                        <div>
                          <VSwitch density="compact" :model-value="row.enabled" color="primary" inset hide-details
                            :title="row.blocked ? '已停用：该站规则不生效，回退全局规则' : '启用中；关闭会写入影子条目，该站回退全局规则'"
                            @update:model-value="hrSetSiteEnabled(row.name, $event)" />
                          </div>
                        <div class="dm-hr-actions">
                          <template v-if="row.custom">
                            <VBtn size="small" variant="text" :prepend-icon="row.expanded ? 'mdi-chevron-up' : 'mdi-chevron-down'"
                              @click="hrToggleExpanded(row.name)">{{ row.expanded ? '收起' : '编辑' }}</VBtn>
                            <VBtn size="small" variant="text" color="primary" prepend-icon="mdi-delete-outline"
                              :title="row.preset ? '删除自定义条目后该站回退内置预设' : '删除该自定义站点'"
                              @click="hrRemoveCustomSite(row.name)">删除站点</VBtn>
                          </template>
                          <VBtn size="small" v-else variant="text" prepend-icon="mdi-content-copy"
                            title="把内置预设值复制为自定义条目后逐字段调整" @click="hrCopyPresetToCustom(row.name)">复制规则</VBtn>
                        </div>
                      </div>
                      <div v-if="row.custom && row.expanded" class="dm-hr-editor">
                        <div class="dm-hr-editor-grid">
                          <VTextField density="compact" class="dm-number-input" v-for="field in hrNumberFields" :key="field.key" :model-value="hrRuleNumber(row.entry, field.key)"
                            @update:model-value="hrSetRuleNumber(row.name, field.key, $event)" :label="field.label" type="number" variant="outlined" :hint="`留空表示继承全局（${hrGlobalText(field.key)}）`"
                            persistent-hint />
                          <VSelect density="compact" v-for="field in hrFlagFields" :key="field.key" :model-value="hrRuleFlag(row.entry, field.key)"
                            @update:model-value="hrSetRuleFlag(row.name, field.key, $event)" :items="hrTriStateItems" :label="field.label" variant="outlined" hide-details />
                        </div>
                        <div class="dm-hr-trackers">
                          <VCombobox density="compact" :model-value="hrRuleTrackers(row.entry)" @update:model-value="hrSetRuleTrackers(row.name, $event)"
                            label="Tracker 域名" variant="outlined" multiple chips
                            closable-chips clearable placeholder="完整 URL 或裸域名，如 https://tracker.example.com/announce"
                            hint="MP 站点库识别不出站点时，按这里的域名兜底匹配该自定义站点" persistent-hint />
                        </div>
                        <div class="dm-hr-tiers">
                          <div class="dm-hr-tiers-head">
                            <span>体积分档</span><span class="dm-hint">按种子 GiB 匹配；上限为 0 表示不限，需置于末位。</span>
                            <VBtn size="small" variant="text" prepend-icon="mdi-plus" @click="hrAddTier(row.name)">添加分档</VBtn>
                          </div>
                          <div v-for="(tier, tierIndex) in row.entry.hr_size_tiers || []" :key="`${row.name}-${tierIndex}`"
                            class="dm-hr-tier-row">
                            <VTextField density="compact" class="dm-number-input" v-for="field in hrTierFields" :key="field.key" :model-value="hrTierNumber(tier, field.key)"
                              @update:model-value="hrSetTierNumber(row.name, tierIndex, field.key, $event)" :label="field.label"
                              type="number" variant="outlined" hide-details />
                            <VBtn size="small" aria-label="删除该分档" icon="mdi-delete-outline" variant="text" color="primary" title="删除该分档"
                              @click="hrRemoveTier(row.name, tierIndex)" />
                          </div>
                          <div v-if="!(row.entry.hr_size_tiers || []).length" class="dm-hint">
                            未设置分档：命中分档时以分档的做种时长/考核期为准，未命中时用站点值。
                          </div>
                        </div>
                      </div>
                    </template>
                    <div v-if="!hrSiteRows.length" class="dm-monitor-empty dm-hint">没有可显示的站点规则；可重载预设或新增自定义站点。</div>
                  </div>

                  <div class="mt-3">
                    <VBtn size="small" variant="text" :prepend-icon="hrRawOpen ? 'mdi-chevron-up' : 'mdi-code-json'"
                      @click="hrRawOpen = !hrRawOpen">{{ hrRawOpen ? '收起 YAML' : '编辑 YAML' }}</VBtn>
                    <template v-if="hrRawOpen">
                      <VTextarea density="compact" v-model="form.hr_site_config_str" :error-messages="hrRawError" label="站点规则" variant="outlined" rows="8" class="mt-1" hint="YAML 格式；解析失败时合并视图保留上一次可解析的规则" persistent-hint />
                      <div class="dm-hint">
                        顶层为列表，每项含 site_name 与 hr_duration / additional_seed_time / hr_deadline_days / hr_ratio / hr_upload_multiplier / hr_upload_gte_download / hr_active / hr_size_tiers / enabled；未设置字段回退全局规则，enabled: false 为影子条目。
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>

            <!-- ═══ H&R · 高级设置 ═══ -->
            <div v-show="activeSub === 'hr_advanced'" class="dm-pane">
              <div class="dm-section-title">高级设置</div>
              <div  class="dm-hint mb-3">
                H&R 纳管且未达标的任务，会在自动删种、整理失败删源、转移源端删除三条破坏性路径上被统一跳过。
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.hr_protection_enabled" color="primary" inset hide-details label="删除保护" />
              <div v-if="!form.hr_protection_enabled" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" />关闭删除保护后，未达标 H&R 任务可能被删除。</div>
                </div>
                <div class="dm-field dm-field--number">
                  <VTextField density="compact" class="dm-number-input" v-model.number="form.hr_auto_cleanup_days" label="记录保留（天）" type="number" variant="outlined"
                    hint="达标/失效记录保留天数，默认 15" persistent-hint />
                </div>
              </div>
            </div>

            <!-- ═══ 自动删种 · 基础设置 ═══ -->
            <div v-show="activeSub === 'remover_basic'" class="dm-pane">
              <div v-if="form.remover_action === 'deletefile'" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" />执行时将删除任务及文件。</div>
              <div class="dm-section-title">基础设置</div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.remover_enabled" color="primary" inset hide-details label="启用" />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.remover_observe_only" color="warning" inset hide-details label="观察模式" />
                  <div v-if="form.remover_observe_only" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" /> 观察模式：只列出候选并发通知，不暂停、不删除种子；原「仅观察不执行」开关已迁移到此处</div>
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.remover_notify" color="primary" inset hide-details label="发送通知" />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.remover_mponly" color="primary" inset hide-details label="仅 MoviePilot 任务" />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.remover_samedata" color="error" inset hide-details label="连带同名同大小任务" />
              <div v-if="form.remover_samedata" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" />命中规则时也处理同名同大小任务；删除动作可能影响文件。</div>
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field">
                  <VSelect density="compact" v-model="form.remover_action" label="动作" variant="outlined"
                    :items="removerActionItems" hint="暂停 / 删除任务 / 删除任务及文件" persistent-hint />
                </div>
                <div class="dm-field">
                  <VSelect density="compact" v-model="form.remover_downloaders" label="下载器" variant="outlined"
                    :items="downloaderItems" multiple chips closable-chips clearable hint="只处理这里选中的下载器" persistent-hint />
                </div>
                <div class="dm-field">
                  <VCronField density="compact" v-model="form.remover_cron" label="执行计划" variant="outlined" hide-details />
                </div>
              </div>
            </div>

            <!-- ═══ 自动删种 · 删除条件 ═══ -->
            <div v-show="activeSub === 'remover_conditions'" class="dm-pane">
              <div class="dm-section-title">删除条件</div>
              <div class="dm-field-row">
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.remover_time" label="做种时长（小时）" variant="outlined" hint="多个以逗号分隔" persistent-hint />
                </div>
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.remover_ratio" label="分享率" variant="outlined" hint="低于此分享率时命中；多个以逗号分隔" persistent-hint />
                </div>
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.remover_size" label="体积（GB）" variant="outlined" hint="多个以逗号分隔" persistent-hint />
                </div>
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.remover_upspeed" label="平均上传速度（KB/s）" variant="outlined" hint="多个以逗号分隔" persistent-hint />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.remover_labels" label="限定标签" variant="outlined" hint="多个以逗号分隔" persistent-hint />
                </div>
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.remover_torrentcategorys" label="限定分类" variant="outlined" hint="多个以逗号分隔" persistent-hint />
                </div>
                <div class="dm-field dm-field--full">
                  <VTextField density="compact" v-model="form.remover_pathkeywords" label="路径关键词" variant="outlined" hint="多个以逗号分隔" persistent-hint />
                </div>
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.remover_trackerkeywords" label="tracker 关键词" variant="outlined" hint="多个以逗号分隔" persistent-hint />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.remover_errorkeywords" label="错误关键词" variant="outlined" hint="多个以逗号分隔" persistent-hint />
                </div>
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.remover_torrentstates" label="任务状态" variant="outlined" hint="多个以逗号分隔" persistent-hint />
                </div>
              </div>
            </div>

            <!-- ═══ 失败清理 · 基础设置 ═══ -->
            <div v-show="activeSub === 'failclean_basic'" class="dm-pane">
              <div v-if="form.failcleanup_enabled && !form.failcleanup_observe_only" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" />真实模式可能删除源文件及下载历史。</div>
              <div class="dm-section-title">基础设置</div>
              <div  class="dm-hint mb-3">
                整理失败事件与重复残留巡检共用本模块设置。
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.failcleanup_enabled" color="primary" inset hide-details label="启用" />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.failcleanup_observe_only" color="warning" inset hide-details label="观察模式" />
                  <div v-if="form.failcleanup_observe_only" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" /> 观察模式：只统计将清理的失败文件，不删除文件、不删下载历史</div>
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.failcleanup_clean_repeat" color="primary" inset hide-details label="清理重复残留" />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.failcleanup_notify" color="primary" inset hide-details label="发送通知" />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field">
                  <VCronField density="compact" v-model="form.failcleanup_cron" label="巡检计划" variant="outlined" hide-details />
                </div>
                <div class="dm-field dm-field--number">
                  <VTextField density="compact" class="dm-number-input" v-model.number="form.failcleanup_retain_hours" label="残留保留（小时）" type="number" variant="outlined"
                    hint="仅清理早于该时长的重复残留路径，默认 6" persistent-hint />
                </div>
              </div>
            </div>

            <!-- ═══ 种子重命名 · 基础设置 ═══ -->
            <div v-show="activeSub === 'rename_basic'" class="dm-pane">
              <div class="dm-section-title">基础设置</div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.rename_enabled" inset hide-details label="启用" />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.rename_observe_only" color="warning" inset hide-details label="观察模式" />
                  <div v-if="form.rename_observe_only" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" /> 只预览，不执行写操作。</div>
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.rename_on_download_added" inset hide-details label="入列触发" />
                </div>
                <div class="dm-field dm-field--number">
                  <VTextField density="compact" class="dm-number-input" v-model.number="form.rename_event_debounce_seconds" label="事件防抖（秒）" type="number" min="1" variant="outlined"
                    :disabled="!form.rename_on_download_added" hint="默认 3 秒" persistent-hint />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.rename_notify" inset hide-details label="发送通知" />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.rename_cron_enabled" inset hide-details label="定时补查" />
                </div>
                <div class="dm-field">
                  <VCronField density="compact" v-model="form.rename_cron" label="补查计划" variant="outlined" hide-details :disabled="!form.rename_cron_enabled" />
                </div>
                <div class="dm-field">
                  <VSelect density="compact" v-model="form.rename_downloaders" label="下载器" variant="outlined"
                    :items="qbDownloaderItems" multiple chips closable-chips clearable hint="仅 qBittorrent 支持重命名" persistent-hint />
                </div>
              </div>
            </div>

            <!-- ═══ 种子重命名 · 模板与过滤 ═══ -->
            <div v-show="activeSub === 'rename_format'" class="dm-pane">
              <div class="dm-section-title">模板与过滤</div>
              <div class="dm-field-row">
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.rename_include_tags" label="包含标签" variant="outlined" hint="多个以逗号分隔；留空表示不限制" persistent-hint />
                </div>
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.rename_exclude_tags" label="排除标签" variant="outlined" hint="多个以逗号分隔；默认排除已重命名" persistent-hint />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--full">
                  <VTextarea density="compact" v-model="form.rename_movie_format" label="电影模板" variant="outlined" rows="2" hint="Jinja2 模板" persistent-hint />
                  <div class="dm-hint">可用变量: {{ title }}, {{ year }}, {{ original_name }}</div>
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--full">
                  <VTextarea density="compact" v-model="form.rename_tv_format" label="电视剧模板" variant="outlined" rows="2" hint="Jinja2 模板" persistent-hint />
                  <div class="dm-hint">可用变量: {{ title }}, {{ year }}, {{ season_episode }}, {{ original_name }}</div>
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--full">
                  <VTextarea density="compact" v-model="form.rename_exclude_dirs" label="排除目录" variant="outlined" rows="2" hint="每行一个目录" persistent-hint />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--full">
                  <VTextarea density="compact" v-model="form.rename_hash_white_list" label="Hash 白名单" variant="outlined" rows="2" hint="每行一个种子 Hash" persistent-hint />
                </div>
              </div>
            </div>

            <!-- ═══ 站点标签 · 基础设置 ═══ -->
            <div v-show="activeSub === 'tag_basic'" class="dm-pane">
              <div class="dm-section-title">基础设置</div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.tag_enabled" color="primary" inset hide-details label="启用" />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.tag_observe_only" color="warning" inset hide-details label="观察模式" />
                  <div v-if="form.tag_observe_only" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" /> 观察模式：只统计将写入的标签/分类，不修改下载器标签</div>
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.tag_enable_tag" color="primary" inset hide-details label="站点名标签" />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.tag_enable_media_tag" color="primary" inset hide-details label="剧名标签" />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.tag_enable_category" color="primary" inset hide-details label="TMDB 二级分类" />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.tag_enable_del_tags" color="error" inset hide-details label="允许删除标签" />
              <div v-if="form.tag_enable_del_tags" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" />允许在标签补全时删除下载器标签。</div>
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.tag_rename_type" color="primary" inset hide-details label="分类方式" />
                  <div class="dm-hint">开启：路径关键词；关闭：TMDB 识别。对应规则在映射规则中配置。</div>
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.tag_siteprefix" label="站点标签前缀" variant="outlined" hide-details />
                </div>
                <div class="dm-field">
                  <VSelect density="compact" v-model="form.tag_downloaders" label="下载器" variant="outlined"
                    :items="downloaderItems" multiple chips closable-chips clearable hint="留空表示全部下载器" persistent-hint />
                </div>
                <div class="dm-field">
                  <VCronField density="compact" v-model="form.tag_interval_cron" label="补全计划" variant="outlined" hide-details />
                </div>
              </div>
            </div>

            <!-- ═══ 站点标签 · 映射规则 ═══ -->
            <div v-show="activeSub === 'mapping'" class="dm-pane">
              <div class="dm-section-title">映射规则</div>
              <div class="dm-field-row">
                <div class="dm-field">
                  <VTextField density="compact" v-model="form.tag_catprefix" label="分类前缀" variant="outlined" hint="写入分类名前的前缀，留空不加" persistent-hint />
                </div>
              </div>

              <!-- ═══ 分类规则 ═══ -->
              <div class="dm-section-title mt-2">分类规则</div>
              <!-- 分类映射（TMDB 模式）：一行一条 载入分类 -> 写入分类 -->
              <template v-if="!form.tag_rename_type">
                <div class="dm-hr-table mt-3">
                  <div class="dm-cat-row dm-cat-row--head">
                    <span>载入分类（TMDB / 站点分类）</span>
                    <span />
                    <span>写入分类</span>
                    <span />
                  </div>
                  <div v-for="(pair, idx) in tagCatPairs" :key="`cat-${idx}`" class="dm-cat-row">
                    <VTextField density="compact" v-model="pair.from" label="载入分类" variant="outlined" hide-details />
                    <span class="dm-map-arrow">→</span>
                    <VTextField density="compact" v-model="pair.to" label="写入分类" variant="outlined" hide-details />
                    <VBtn size="small" aria-label="移除映射" icon="mdi-close" variant="text" color="primary" @click="tagCatPairs.splice(idx, 1)" />
                  </div>
                  <div v-if="!tagCatPairs.length" class="dm-map-empty dm-hint">暂无映射，点击下方按钮添加</div>
                </div>
                <div class="d-flex justify-end mt-2">
                  <VBtn size="small" variant="tonal" prepend-icon="mdi-plus" @click="addCatPair">添加映射</VBtn>
                </div>
                <div class="dm-hint mt-2">
                  当前模式：按 TMDB 识别结果设置分类，每行「载入分类 → 写入分类」一一对应；改为路径判断后此表不生效。
                </div>
              </template>

              <!-- 路径映射（路径模式） -->
              <template v-if="form.tag_rename_type">
                <div class="dm-field-row">
                  <div class="dm-field dm-field--full">
                    <VTextarea density="compact" v-model="form.tag_path_rename" label="路径映射" variant="outlined" rows="3" hint="每行一条：关键词#分类" persistent-hint />
                  </div>
                </div>
                <div class="dm-hint">
                  当前模式：按下载保存路径包含的关键词判断分类（如 /anime/#动漫），一行不命中则不设分类；关闭上方开关则改按 TMDB 识别设置分类。
                </div>
              </template>

              <!-- ═══ 站点规则 ═══ -->
              <div class="dm-section-title mt-4">站点规则</div>
              <!-- Tracker 映射（恒显示）：一行一条 tracker域名 -> 站点库域名，并反查站点名 -->
              <div class="dm-hr-table mt-2">
                <div class="dm-map-row dm-map-row--head">
                  <span>Tracker 域名</span>
                  <span />
                  <span>站点库域名</span>
                  <span>匹配站点</span>
                  <span>标签</span>
                  <span>自定义标签</span>
                  <span />
                </div>
                <div v-for="(pair, idx) in tagTrackerPairs" :key="`tracker-${idx}`" class="dm-map-row">
                  <VTextField density="compact" v-model="pair.tracker" label="Tracker 域名" variant="outlined" hide-details />
                  <span class="dm-map-arrow">→</span>
                  <VTextField density="compact" v-model="pair.site" label="站点库域名" variant="outlined" hide-details />
                  <div class="dm-map-site">
                    <VChip v-if="siteNameByDomain(pair.site) || siteNameByDomain(pair.tracker)" size="x-small" label color="primary">
                      {{ siteNameByDomain(pair.site) || siteNameByDomain(pair.tracker) }}
                    </VChip>
                    <VChip v-else-if="pair.site" size="x-small" label color="warning">未收录</VChip>
                  </div>
                  <div class="dm-map-site">
                    <VChip v-if="siteNameByDomain(pair.site) || siteNameByDomain(pair.tracker)" size="x-small" label variant="tonal">
                      {{ form.tag_siteprefix || '' }}{{ siteNameByDomain(pair.site) || siteNameByDomain(pair.tracker) }}
                    </VChip>
                    <VChip v-else-if="String(pair.custom || '').trim()" size="x-small" label variant="tonal" color="primary">
                      {{ form.tag_siteprefix || '' }}{{ String(pair.custom).trim() }}
                    </VChip>
                    <span v-else class="dm-map-empty-cell">—</span>
                  </div>
                  <div class="dm-map-site">
                    <VChip v-if="siteNameByDomain(pair.site) || siteNameByDomain(pair.tracker)" size="x-small" label variant="tonal" color="success">已收录</VChip>
                    <VTextField density="compact" v-else v-model="pair.custom" label="标签名" variant="outlined" hide-details  />
                  </div>
                  <div class="d-flex justify-end">
                    <VBtn size="small" aria-label="移除映射" icon="mdi-close" variant="text" color="primary" @click="tagTrackerPairs.splice(idx, 1)" />
                  </div>
                </div>
                <div v-if="!tagTrackerPairs.length" class="dm-map-empty dm-hint">暂无映射，点击下方按钮添加</div>
              </div>
              <div class="d-flex justify-end mt-2">
                <VBtn size="small" variant="tonal" prepend-icon="mdi-plus" @click="addTrackerPair">添加映射</VBtn>
              </div>
              <div class="dm-hint mt-2">
                种子 Tracker 域名按行换算成站点库域名后匹配站点打「站点前缀 + 站点名」标签；站点库未收录的行可填「自定义标签」，按「站点前缀 + 自定义标签」打标，留空则跳过。
              </div>
            </div>

            <!-- ═══ 做种校验 v3.0.15 · 基础设置 ═══ -->
            <div v-show="activeSub === 'seed_basic'" class="dm-pane">
              <div class="dm-section-title">基础设置</div>
              <div  class="dm-hint mb-4">做种校验采用按需触发：仅在转移做种或手动补刀添加种子后启动。队列为空后自动停止。</div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.seed_autostart" color="primary" inset hide-details label="自动开始做种" />
                </div>
                <div class="dm-field dm-field--toggle">
                  <VSwitch density="compact" v-model="form.seed_skipverify" color="primary" inset hide-details label="跳过校验" />
                </div>
              </div>
              <div class="dm-field-row">
                <div class="dm-field dm-field--number">
                  <VTextField density="compact" class="dm-number-input" v-model.number="form.seed_check_interval" label="检查间隔（秒）" type="number" variant="outlined" hint="建议 60 秒" persistent-hint />
                </div>
                <div class="dm-field dm-field--number">
                  <VTextField density="compact" class="dm-number-input" v-model.number="form.seed_max_wait_minutes" label="最长等待（分钟）" type="number" variant="outlined" hint="超时后移出队列" persistent-hint />
                </div>
              </div>
            </div>

          </div>
        </section>
      </div>
      <VDivider />
      <VCardActions class="dm-actions">
        <VBtn size="small" variant="text" prepend-icon="mdi-table-eye" @click="switchToData">查看数据</VBtn>
        <span v-if="saveMessage" class="dm-hint" :class="{ 'text-error': saveError }" role="status" aria-live="polite">{{ saveMessage }}</span>
        <VSpacer />
        <VBtn size="small" variant="text" @click="emit('close')">取消</VBtn>
        <VBtn size="small" color="primary" variant="flat" prepend-icon="mdi-content-save-outline" :loading="savePending" :disabled="savePending" @click="saveConfig">保存配置</VBtn>
      </VCardActions>
    </VCard>

    <VDialog content-class="dm-config" v-model="hrAddDialog" max-width="520">
      <VCard class="dm-form-dialog">
        <VCardItem>
          <template #prepend>
            <VAvatar color="primary" variant="tonal" size="40" rounded="lg"><VIcon icon="mdi-home-plus-outline" /></VAvatar>
          </template>
          <VCardTitle class="dm-title">新增自定义站点</VCardTitle>
          <VCardSubtitle class="dm-hint">站点名需与站点标签识别出的站点名一致</VCardSubtitle>
        </VCardItem>
        <VDivider />
        <VCardText>
          <VTextField density="compact" v-model="hrNewSiteName" :error-messages="hrAddError" label="站点名" variant="outlined"
            hint="先写入 site_name，字段留空表示继承全局规则" persistent-hint @keyup.enter="hrConfirmAddSite" />
        </VCardText>
        <VDivider />
        <VCardActions>
          <VSpacer />
          <VBtn size="small" variant="text" @click="hrAddDialog = false">取消</VBtn>
          <VBtn size="small" color="primary" variant="flat" prepend-icon="mdi-plus" @click="hrConfirmAddSite">添加站点</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog content-class="dm-config" v-model="transferDialog" max-width="780" scrollable>
      <VCard class="dm-form-dialog">
        <VCardItem>
          <template #prepend>
            <VAvatar color="primary" variant="tonal" size="40" rounded="lg"><VIcon icon="mdi-transfer" /></VAvatar>
          </template>
          <VCardTitle class="dm-title">{{ transferEditing >= 0 ? '编辑转移任务' : '添加转移任务' }}</VCardTitle>
          <VCardSubtitle class="dm-hint">源/目的下载器必填且不能相同；数据映射可选（两个都空 = 不映射，只填一个才报错）</VCardSubtitle>
        </VCardItem>
        <VDivider />
        <VCardText>
          <div class="dm-field-row">
            <div class="dm-field">
              <VTextField density="compact" v-model="transferForm.name" label="任务名称" variant="outlined"
                hint="留空自动命名为「任务N」" persistent-hint />
            </div>
            <div class="dm-field dm-field--toggle">
              <VSwitch density="compact" v-model="transferForm.enabled" color="primary" inset hide-details label="启用" />
            </div>
          </div>
          <div class="dm-field-row">
            <div class="dm-field">
              <VSelect density="compact" v-model="transferForm.from_downloader" :error-messages="transferError && (!transferForm.from_downloader || !transferForm.to_downloader || transferForm.from_downloader === transferForm.to_downloader) ? transferError : ''" :items="downloaderSelectItems" label="源下载器" variant="outlined"
                hint="从该下载器复制种子" persistent-hint />
            </div>
            <div class="dm-field">
              <VSelect density="compact" v-model="transferForm.to_downloader" :error-messages="transferError && (!transferForm.from_downloader || !transferForm.to_downloader || transferForm.from_downloader === transferForm.to_downloader) ? transferError : ''" :items="downloaderSelectItems" label="目标下载器" variant="outlined"
                hint="转移目标下载器" persistent-hint />
            </div>
          </div>
          <div class="dm-field-row">
            <div class="dm-field dm-field--full">
              <VTextField density="compact" v-model="transferForm.from_path" :error-messages="transferError && (!!transferForm.from_path !== !!transferForm.to_path) ? transferError : ''" label="源数据路径" variant="outlined"
                hint="数据可见性映射（可选）：两个都留空 = 不做映射；只填一个视为配置错误" persistent-hint />
            </div>
            <div class="dm-field dm-field--full">
              <VTextField density="compact" v-model="transferForm.to_path" :error-messages="transferError && (!!transferForm.from_path !== !!transferForm.to_path) ? transferError : ''" label="目标数据路径" variant="outlined"
                hint="数据可见性映射（可选）：两个都留空 = 不做映射；只填一个视为配置错误" persistent-hint />
            </div>
          </div>
          <div class="dm-section-title mt-4">筛选条件</div>
          <div class="dm-field-row">
            <div class="dm-field">
              <VTextField density="compact" v-model="transferForm.include_category" label="包含分类" variant="outlined" hint="多个以逗号分隔；仅转移这些分类的种子，留空不限制" persistent-hint />
            </div>
            <div class="dm-field">
              <VTextField density="compact" v-model="transferForm.include_labels" label="包含标签" variant="outlined" hint="多个以逗号分隔；仅转移包含这些标签的种子，留空不限制" persistent-hint />
            </div>
          </div>
          <div class="dm-field-row">
            <div class="dm-field">
              <VTextField density="compact" v-model="transferForm.exclude_labels" label="排除标签" variant="outlined" hint="多个以逗号分隔；包含这些标签的种子跳过" persistent-hint />
            </div>
            <div class="dm-field dm-field--toggle">
              <VCheckbox density="compact" v-model="transferForm.empty_label_ok" color="info" hide-details label="允许无标签种子" />
            </div>
          </div>
          <div class="dm-field-row">
            <div class="dm-field dm-field--full">
              <VTextarea density="compact" v-model="transferForm.no_paths" label="排除路径" variant="outlined" rows="3" hint="每行一个路径" persistent-hint />
            </div>
          </div>
          <div class="dm-section-title mt-4">高级设置</div>
          <div v-if="transferForm.delete_source" class="dm-hint dm-risk mb-2"><VIcon icon="mdi-alert-outline" size="16" />
            「删除源任务」受 H&R 保护约束：源种若已纳入 H&amp;R 管理且未达标，源任务会被保留，并计入数据页「转移做种」卡的「H&amp;R 保护」跳过数。放行办法有三种——等它达标（自动放行）、让种子在进入下载器前就带 H&amp;R 排除标签、或关闭 H&amp;R 保护总开关。注意：<strong>已纳管的种子事后补排除标签无效</strong>（排除只在首次纳管时判定）。
          </div>
          <div class="dm-field-row">
            <div class="dm-field dm-field--toggle">
              <VSwitch density="compact" v-model="transferForm.delete_source" color="error" inset hide-details label="删除源任务" />
              <div v-if="transferForm.delete_source" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" />转移后删除源任务，仍受 H&R 保护约束。</div>
            </div>
            <div class="dm-field dm-field--toggle">
              <VSwitch density="compact" v-model="transferForm.delete_duplicate" color="error" inset hide-details label="删除重复任务" />
              <div v-if="transferForm.delete_duplicate" class="dm-hint dm-risk"><VIcon icon="mdi-alert-outline" size="16" />转移时删除重复任务，仍受 H&R 保护约束。</div>
            </div>
          </div>
          <div class="dm-field-row">
            <div class="dm-field dm-field--toggle">
              <VSwitch density="compact" v-model="transferForm.keep_category" color="primary" inset hide-details label="保留原分类" />
            </div>
            <div class="dm-field dm-field--toggle">
              <VSwitch density="compact" v-model="transferForm.keep_tag" color="primary" inset hide-details label="保留原标签" />
            </div>
          </div>
          <div class="dm-field-row">
            <div class="dm-field">
              <VTextField density="compact" v-model="transferForm.transfer_tag" label="目标标签" variant="outlined"
                hint="默认「已转移」；留空表示不打标签" persistent-hint />
            </div>
          </div>
          <template v-if="transferDialogSourceType === 'rtorrent'">
            <div class="dm-section-title mt-4">ruTorrent 网络导出</div>
            <div class="dm-hint mb-2">源端为 rtorrent 时，必须填写 ruTorrent WebUI 地址与 source 插件路径，否则无法导出种子数据。</div>
            <div class="dm-field-row">
              <div class="dm-field dm-field--full">
                <VTextField density="compact" v-model="transferForm.ext_webui_url" label="ruTorrent WebUI 地址" variant="outlined"
                  hint="如 http://127.0.0.1:8080/rutorrent，不含末尾斜杠" persistent-hint />
              </div>
              <div class="dm-field dm-field--full">
                <VTextField density="compact" v-model="transferForm.ext_source_plugin" label="source 插件路径" variant="outlined"
                  hint="相对 WebUI 地址的 source 插件路径，如 plugins/source/action.php" persistent-hint />
              </div>
            </div>
          </template>
        </VCardText>
        <VDivider />
        <VCardActions>
          <VSpacer />
          <VBtn size="small" variant="text" @click="transferDialog = false">取消</VBtn>
          <VBtn size="small" color="primary" variant="flat" prepend-icon="mdi-check" @click="confirmTransferTask">应用任务</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog content-class="dm-config" v-model="transferDeleteDialog" max-width="480">
      <VCard class="dm-form-dialog">
        <VCardItem>
          <template #prepend>
            <VAvatar color="error" variant="tonal" size="40" rounded="lg"><VIcon icon="mdi-delete-outline" /></VAvatar>
          </template>
          <VCardTitle class="dm-title">删除转移任务</VCardTitle>
          <VCardSubtitle class="dm-hint">{{ transferDeleteName || '未命名任务' }}</VCardSubtitle>
        </VCardItem>
        <VDivider />
        <VCardText class="dm-body-text">
          删除后该任务不再参与转移做种；已转移的种子不受影响。改动先作用于表单，点击下方「保存」后才会真正生效。
        </VCardText>
        <VDivider />
        <VCardActions>
          <VSpacer />
          <VBtn size="small" variant="text" @click="transferDeleteDialog = false">取消</VBtn>
          <VBtn size="small" color="error" variant="flat" prepend-icon="mdi-delete-outline" @click="confirmTransferDelete">删除任务</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>

    <VDialog content-class="dm-config" v-model="paneResetDialog" max-width="560">
      <VCard class="dm-form-dialog">
        <VCardItem>
          <template #prepend>
            <VAvatar color="warning" variant="tonal" size="40" rounded="lg"><VIcon icon="mdi-restore" /></VAvatar>
          </template>
          <VCardTitle class="dm-title">恢复「{{ paneResetTitle }}」默认设置</VCardTitle>
          <VCardSubtitle class="dm-hint">仅重置本页签的 {{ paneResetCount }} 项，不影响其他页签</VCardSubtitle>
        </VCardItem>
        <VDivider />
        <VCardText class="dm-body-text">
          将把本页签全部设置恢复为插件默认值。改动先作用于表单，点击下方「保存」后才会真正生效。<template v-if="paneResetTarget === 'hr'">H&R 站点独立规则也会一并清空回全局基准。</template>
        </VCardText>
        <VDivider />
        <VCardActions>
          <VSpacer />
          <VBtn size="small" variant="text" @click="paneResetDialog = false">取消</VBtn>
          <VBtn size="small" color="warning" variant="flat" prepend-icon="mdi-restore" @click="confirmPaneReset">恢复默认</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </div>
</template>
<style scoped>
.dm-config {
  width: 100%;
  max-width: 100%;
}
.dm-card {
  width: 100%;
  max-height: min(860px, calc(100dvh - 48px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.dm-header { padding: 14px 18px; }
.dm-header :deep(.v-card-subtitle) {
  max-width: min(560px, 52vw);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dm-body { flex: 1 1 auto; min-height: 0; display: flex; }
.dm-nav { overflow-y: auto; width: 160px; flex: 0 0 160px; border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), 0.02); }
.dm-nav-list { width: 100%; }
.dm-nav-item { margin: 2px 8px; }
.dm-content { flex: 1 1 auto; min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.dm-subtabs { flex: 0 0 auto; display: flex; flex-wrap: wrap; gap: 4px; padding: 8px 12px; }
.dm-subtab { display: inline-flex; align-items: center; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500; color: rgba(var(--v-theme-on-surface), 0.7); background: transparent; border: none; cursor: pointer; transition: background 0.15s, color 0.15s; white-space: nowrap; }
.dm-subtab:hover { background: rgba(var(--v-theme-primary), 0.08); color: rgb(var(--v-theme-primary)); }
.dm-subtab--active { background: rgba(var(--v-theme-primary), 0.14); color: rgb(var(--v-theme-primary)); font-weight: 600; }
.dm-window { flex: 1 1 auto; min-height: 0; overflow: auto; }
.dm-pane { padding: 16px 20px; }
/* Field + its help share one layout item; no breakpoint-sized switch columns. */
.dm-field-row { display: flex; flex-wrap: wrap; align-items: flex-start; gap: var(--dm-field-gap); }
.dm-field-row + .dm-field-row { margin-top: var(--dm-field-gap); }
.dm-field { flex: 1 1 calc(50% - var(--dm-field-gap) / 2); min-width: min(100%, var(--dm-field-min-width)); max-width: calc(50% - var(--dm-field-gap) / 2); }
.dm-field--full { flex-basis: 100%; min-width: 0; max-width: 100%; }
.dm-field--number { flex: 0 1 var(--dm-number-width); min-width: 0; max-width: 100%; }
.dm-field--toggle { flex: 0 1 auto; min-width: 0; max-width: 100%; width: fit-content; }
.dm-field--toggle > .dm-hint { max-width: 28ch; overflow-wrap: anywhere; }
.dm-field--toggle :deep(.v-selection-control) { flex: 0 1 auto; justify-content: space-between; gap: var(--dm-field-gap); }
.dm-field--toggle :deep(.v-label) { flex: 0 1 auto; white-space: normal; }
:is(.dm-config, .dm-form-dialog) :deep(.v-switch .v-selection-control) { flex-direction: row-reverse; }
.dm-number-input { width: var(--dm-number-width); max-width: 100%; flex: 0 1 var(--dm-number-width); }
.dm-pane > .dm-section-title { margin-bottom: var(--dm-field-gap); }
.dm-pane > .dm-section-title:not(:first-child) { margin-top: var(--dm-section-gap); }
.dm-card > .dm-header, .dm-card > :deep(.v-divider), .dm-actions { flex: 0 0 auto; }
:is(.dm-config, .dm-form-dialog) :deep(.v-text-field:not(.v-textarea) .v-field) { --v-input-control-height: var(--dm-control-height); border-radius: var(--dm-panel-radius); }
:is(.dm-config, .dm-form-dialog) :deep(.v-btn) { height: var(--dm-button-height); }
:is(.dm-config, .dm-form-dialog) :deep(.v-btn--icon) { width: var(--dm-button-height); min-width: var(--dm-button-height); }
:is(.dm-config, .dm-form-dialog) :deep(.v-input__details), :is(.dm-config, .dm-form-dialog) :deep(.v-messages), .dm-card .dm-hint, .dm-form-dialog .dm-hint {
  font-size: var(--dm-text-help-size);
  font-weight: var(--dm-text-help-weight);
  line-height: var(--dm-text-help-line-height);
}
@container dm-form (max-width: 520px) {
  .dm-field:not(.dm-field--toggle):not(.dm-field--number) { flex-basis: 100%; max-width: 100%; }
}
.dm-window, :is(.dm-config, .dm-form-dialog) :deep(.v-card-text) { container-type: inline-size; container-name: dm-form; }
:is(.dm-config, .dm-form-dialog) :deep(.v-field__input), :is(.dm-config, .dm-form-dialog) :deep(.v-input__control) { min-width: 0; }
.dm-break-text { overflow-wrap: anywhere; }
.dm-monitor-summary, .dm-upload-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.dm-monitor-metric { min-width: 0; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-monitor-metric span {display: block; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-monitor-metric strong {display: block; margin-top: 3px; overflow-wrap: anywhere; font-size: var(--dm-text-title-size); font-weight: var(--dm-text-title-weight); line-height: var(--dm-text-title-line-height); color: var(--dm-text-title-color);}
.dm-monitor-empty {display: flex; min-height: 64px; align-items: center; justify-content: center; border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-upload-downloader-list, .dm-upload-site-list, .dm-upload-site-status { display: grid; gap: var(--dm-field-gap); }
.dm-upload-config-row { display: flex; flex-wrap: wrap; gap: var(--dm-field-gap); align-items: flex-start; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: var(--dm-panel-radius); }
.dm-upload-config-name, .dm-upload-site-name { display: flex; align-items: center; gap: 9px; min-width: 0; overflow-wrap: anywhere; }
.dm-upload-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.dm-upload-site-row { display: flex; flex-wrap: wrap; gap: var(--dm-field-gap); align-items: flex-start; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: var(--dm-panel-radius); }
.dm-upload-site-row :deep(.v-btn) { margin-top: 0; }
.dm-upload-status-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.dm-upload-status-card { min-width: 0; padding: 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-upload-status-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; min-width: 0; }
.dm-upload-values {display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 5px 12px; margin-top: 10px; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
.dm-upload-values span { min-width: 0; overflow-wrap: anywhere; }
.dm-upload-site-status-row { display: grid; grid-template-columns: minmax(180px, 1fr) minmax(102px, auto) minmax(112px, auto) minmax(124px, auto); gap: 10px; align-items: center; min-width: 0; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.dm-upload-site-status-row > span { min-width: 0; overflow-wrap: anywhere; }
.dm-cleanup-toolbar { display: flex; align-items: center; gap: 10px; }
.dm-cleanup-select { flex: 1 1 auto; min-width: 0; }
.dm-cleanup-results { display: grid; gap: 10px; }
.dm-cleanup-summary { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.dm-tag-group { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; overflow: hidden; }
.dm-map-row { display: grid; grid-template-columns: minmax(140px, 1fr) 22px minmax(140px, 1fr) minmax(88px, .5fr) minmax(96px, .55fr) 48px; gap: var(--dm-field-gap); align-items: center; padding: 8px 12px; border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * 0.7)); }
.dm-cat-row { display: grid; grid-template-columns: minmax(160px, 1fr) 22px minmax(160px, 1fr) 48px; gap: var(--dm-field-gap); align-items: center; padding: 8px 12px; border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * 0.7)); }
.dm-cat-row:last-child { border-bottom: none; }
.dm-cat-row--head {background: rgba(var(--v-theme-on-surface), 0.03); font-size: var(--dm-text-table-head-size); font-weight: var(--dm-text-table-head-weight); line-height: var(--dm-text-table-head-line-height); color: var(--dm-text-table-head-color);}
.dm-map-site { display: flex; align-items: center; justify-content: flex-start; min-width: 0; overflow: hidden; }
.dm-map-empty-cell { color: rgba(var(--v-theme-on-surface), 0.4); }
.dm-map-row:last-child { border-bottom: none; }
.dm-map-row--head {background: rgba(var(--v-theme-on-surface), 0.03); font-size: var(--dm-text-table-head-size); font-weight: var(--dm-text-table-head-weight); line-height: var(--dm-text-table-head-line-height); color: var(--dm-text-table-head-color);}
.dm-map-arrow { text-align: center; color: rgba(var(--v-theme-on-surface), 0.45); }
.dm-map-empty {padding: 14px 12px; text-align: center; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-tag-group-head { min-height: 42px; display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 12px; border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); background: rgba(var(--v-theme-on-surface), 0.02); }
.dm-tag-list { max-height: 280px; overflow-y: auto; }
.dm-tag-row { min-height: 54px; display: flex; align-items: center; gap: 4px; padding: 6px 10px; border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * 0.7)); cursor: pointer; }
.dm-tag-row:last-child { border-bottom: none; }
.dm-tag-row:hover { background: rgba(var(--v-theme-primary), 0.05); }
.dm-tag-content { flex: 1 1 auto; min-width: 0; }
.dm-tag-line { display: flex; align-items: center; gap: 7px; min-width: 0; }
.dm-tag-name {min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
.dm-tag-samples {margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-cleanup-empty {min-height: 82px; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-cleanup-actions { position: sticky; bottom: -18px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 0 0; background: rgb(var(--v-theme-surface)); }
.dm-cleanup-preview-list { max-height: 360px; overflow-y: auto; }
.dm-actions { padding: 10px 18px; }
@media (max-width: 760px) {
  .dm-card { max-height: min(860px, calc(100dvh - 48px)); }
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
  .dm-hr-row { grid-template-columns: 1fr; }
  .dm-task-row { grid-template-columns: 1fr; }
  .dm-task-toolbar { align-items: stretch; flex-direction: column; }
  .dm-task-toolbar :deep(.v-btn) { width: 100%; }
  .dm-hr-tier-row { grid-template-columns: 1fr 40px; }
  .dm-hr-toolbar { align-items: stretch; }
  .dm-monitor-summary, .dm-upload-summary { grid-template-columns: 1fr; }
  .dm-upload-config-row, .dm-upload-site-row, .dm-upload-status-grid, .dm-upload-site-status-row { grid-template-columns: 1fr; }
  .dm-upload-config-name, .dm-upload-site-name { padding-top: 0; }
  .dm-upload-toolbar { align-items: stretch; flex-direction: column; }
  .dm-upload-toolbar :deep(.v-btn) { width: 100%; }
  .dm-upload-site-row :deep(.v-btn) { justify-self: end; margin-top: 0; }
  .dm-cleanup-toolbar, .dm-cleanup-summary, .dm-cleanup-actions, .dm-tag-group-head { align-items: stretch; flex-direction: column; }
  .dm-cleanup-toolbar :deep(.v-btn), .dm-cleanup-actions :deep(.v-btn) { width: 100%; }
  .dm-tag-line { flex-wrap: wrap; }
  .dm-tag-name {width: 100%; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color);}
}
@media (min-width: 761px) and (max-width: 960px) {
  .dm-monitor-summary, .dm-upload-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dm-upload-site-row { grid-template-columns: minmax(180px, .7fr) minmax(220px, 1fr) auto; }
  .dm-upload-status-grid { grid-template-columns: 1fr; }
  .dm-upload-site-status-row { grid-template-columns: minmax(170px, 1fr) repeat(3, minmax(96px, auto)); }
}
.dm-task-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.dm-task-table { display: flex; flex-direction: column; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; overflow-x: auto; }
.dm-task-row { display: grid; grid-template-columns: minmax(150px, 1.1fr) 72px minmax(180px, 1.1fr) minmax(150px, 1fr) minmax(160px, 1fr) minmax(150px, 1fr) 76px; gap: 10px; align-items: center; padding: 8px 12px; min-width: 1020px; border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * 0.7)); }
.dm-task-row:last-child { border-bottom: none; }
.dm-task-row--head { font-size: var(--dm-text-table-head-size); font-weight: var(--dm-text-table-head-weight); line-height: var(--dm-text-table-head-line-height); color: var(--dm-text-table-head-color); background: rgba(var(--v-theme-on-surface), 0.03); }
.dm-task-name { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.dm-task-name > strong { font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); color: var(--dm-text-body-color); }
.dm-task-route { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; min-width: 0; }
.dm-task-paths { min-width: 0; }
.dm-task-state { display: flex; flex-direction: column; align-items: center; gap: 0; }
.dm-route-item { display: inline-flex; align-items: center; gap: 4px; min-width: 0; }
.dm-task-filters, .dm-task-settings { display: flex; flex-wrap: wrap; gap: 4px; min-width: 0; align-content: center; }
.dm-task-actions { display: flex; align-items: center; justify-content: flex-end; }
.dm-hr-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.dm-hr-table { display: flex; flex-direction: column; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; overflow-x: auto; }
.dm-hr-row { display: grid; grid-template-columns: minmax(130px, .7fr) minmax(280px, 2.2fr) minmax(92px, .5fr) 64px minmax(196px, auto); gap: 10px; align-items: center; padding: 8px 12px; border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * 0.7)); }
.dm-hr-row:last-child { border-bottom: none; }
.dm-hr-row--head {background: rgba(var(--v-theme-on-surface), 0.03); font-size: var(--dm-text-table-head-size); font-weight: var(--dm-text-table-head-weight); line-height: var(--dm-text-table-head-line-height); color: var(--dm-text-table-head-color);}
.dm-hr-row--blocked { background: rgba(var(--v-theme-on-surface), 0.02); }
.dm-hr-site { min-width: 0; }
.dm-hr-values { display: flex; flex-wrap: wrap; gap: 4px 6px; min-width: 0; align-items: center; }
.dm-hr-chip {display: inline-flex; flex-direction: column; gap: 0; padding: 2px 8px 3px; border-radius: 6px; background: rgba(var(--v-theme-on-surface), 0.05);  white-space: nowrap; font-size: var(--dm-text-badge-size); font-weight: var(--dm-text-badge-weight); line-height: var(--dm-text-badge-line-height); color: var(--dm-text-badge-color);}
.dm-hr-chip-label { font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-hr-chip-value {font-variant-numeric: tabular-nums; font-size: var(--dm-text-badge-size); font-weight: var(--dm-text-badge-weight); line-height: var(--dm-text-badge-line-height); color: var(--dm-text-badge-color);}
.dm-hr-chip--inherit { background: transparent; border: 1px dashed rgba(var(--v-theme-on-surface), 0.18); }
.dm-hr-chip--inherit .dm-hr-chip-value { color: var(--dm-color-secondary); font-style: italic; font-weight: var(--dm-text-help-weight); }
.dm-hr-chip--more {justify-content: center; background: transparent; border: 1px dashed rgba(var(--v-theme-on-surface), 0.18);   padding: 4px 8px; cursor: default; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-hr-chip--mini { flex-direction: row; align-items: center; padding: 0 6px; background: rgba(var(--v-theme-on-surface), 0.05); }
.dm-hr-chip--mini .dm-hr-chip-value { font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-hr-values-empty {font-style: italic; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); color: var(--dm-text-help-color);}
.dm-hr-legend { display: inline-flex; gap: 6px; margin-left: 8px; vertical-align: middle; }
.dm-hr-global-card { padding: 0; }
.dm-hr-global-head { display: flex; align-items: baseline; gap: var(--dm-field-gap); margin-bottom: var(--dm-field-gap); flex-wrap: wrap; }
.dm-hr-actions { display: flex; align-items: center; gap: 2px; flex-wrap: wrap; }
.dm-hr-editor { padding: 12px; border-bottom: 1px solid rgba(var(--v-border-color), calc(var(--v-border-opacity) * 0.7)); background: rgba(var(--v-theme-on-surface), 0.03); }
.dm-hr-editor-grid { max-width: min(100%, calc(var(--dm-number-width) * 3 + var(--dm-field-gap) * 2)); display: flex; align-items: flex-start; flex-wrap: wrap; gap: var(--dm-field-gap); }
.dm-hr-editor-grid > :deep(.v-select) { flex: 0 1 var(--dm-number-width); width: var(--dm-number-width); max-width: 100%; }
.dm-hr-trackers { margin-top: var(--dm-field-gap); }
.dm-hr-tiers { margin-top: var(--dm-section-gap); }
.dm-hr-tiers-head {display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 6px; font-size: var(--dm-text-section-size); font-weight: var(--dm-text-section-weight); line-height: var(--dm-text-section-line-height); color: var(--dm-text-section-color);}
.dm-hr-tier-row { display: flex; flex-wrap: wrap; gap: var(--dm-field-gap); align-items: flex-start; margin-bottom: var(--dm-field-gap); }
.dm-upload-config-name, .dm-upload-site-name { flex: 1 1 var(--dm-field-min-width); }
:is(.dm-config, .dm-form-dialog) :deep(.v-input__details) { padding-inline: 0; }
</style>
