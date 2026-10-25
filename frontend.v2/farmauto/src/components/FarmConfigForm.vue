<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue"

const DEFAULT_CONFIG = {
  enabled: false,
  notify: true,
  run_once: false,
  site_ids: [],
  cron_mode: 'cron',
  cron: '5 */4 * * *',
  interval_minutes: 61,
  expire_threshold_minutes: 120,
  min_profit_rate: 0,
  max_profit_rate: 0,
  max_sell_per_run: 50,
  request_interval: 1,
  retry_count: 3,
  use_proxy: false,
  dry_run: false,
  auto_harvest: true,
  auto_plant: true,
  auto_sell: true,
  expiry_sale: true,
  siqi_captcha_ocr: true,
  siqi_auto_buy_slot: false,
  siqi_auto_steal: false,
  siqi_auto_like: false,
  siqi_default_seed_id: 1,
  site_overrides: '{}',
}

const SITE_ITEMS = [
  { title: 'PlayLet', value: 'playlet' },
  { title: 'NovaHD', value: 'novahd' },
  { title: '好学', value: 'haoxue' },
  { title: '包子', value: 'baozi' },
  { title: '拾刻', value: 'skit' },
  { title: '思齐', value: 'siqi' },
]

const NUMERIC_OVERRIDE_FIELDS = [
  'min_profit_rate',
  'max_profit_rate',
  'expire_threshold_minutes',
  'max_sell_per_run',
  'request_interval',
]

const AUTOMATION_FIELDS = [
  'auto_harvest',
  'auto_plant',
  'auto_sell',
  'expiry_sale',
]

const props = defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  api: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['save', 'switch', 'close'])
const activeTab = ref('global')
const config = reactive({ ...DEFAULT_CONFIG })
const sitePolicies = reactive({})
const error = ref('')
const successMessage = ref('')
let successTimer = null
function setSuccess(msg) {
  successMessage.value = msg
  if (successTimer) clearTimeout(successTimer)
  successTimer = setTimeout(() => { successMessage.value = '' }, 3000)
}
onBeforeUnmount(() => { if (successTimer) clearTimeout(successTimer) })

// 思齐种子列表（onMounted 拉取，供默认种子下拉选择）
const siqiSeeds = ref([])
const siqiTotalHarvest = ref(0)
// 可购买种子：unlock_harvest<=0 或已解锁（unlock_harvest<=total_harvest）
const availableSeeds = computed(() =>
  siqiSeeds.value.filter(seed => {
    const unlock = Number(seed.unlock_harvest || 0)
    return unlock <= 0 || unlock <= Number(siqiTotalHarvest.value || 0)
  })
)
function windowToken() {
  if (typeof window === 'undefined') return ''
  return window.__MOVIEPILOT_TOKEN__
    || window.MoviePilot?.token
    || window.localStorage?.getItem('token')
    || ''
}
async function fetchSeeds() {
  const hostApi = props.api?.get ? props.api : (typeof window !== 'undefined' && window.MoviePilotAPI ? window.MoviePilotAPI : null)
  let payload
  try {
    if (hostApi && typeof hostApi.get === 'function') {
      // 宿主 API（axios 实例）返回 .data，联邦 api 返回 {success,data}
      const raw = await hostApi.get('plugin/FarmAuto/siqi/seeds')
      payload = raw?.data ?? raw
    } else {
      const token = windowToken()
      const headers = {}
      if (token) headers.Authorization = `Bearer ${token}`
      const res = await fetch('/api/v1/plugin/FarmAuto/siqi/seeds', { headers })
      payload = await res.json().catch(() => ({}))
    }
  } catch (e) {
    siqiSeeds.value = []
    return
  }
  const data = payload?.data ?? payload ?? {}
  siqiSeeds.value = Array.isArray(data.seeds) ? data.seeds : []
  siqiTotalHarvest.value = Number(data.total_harvest || 0)
}
onMounted(fetchSeeds)
function seedTitle(seed) {
  const emoji = seed.emoji || seed.icon || ''
  const cost = seed.cost != null ? `（成本 ${seed.cost}）` : ''
  return `${emoji} ${seed.name || '未知种子'}${cost}`
}

const OVERRIDE_UNITS = {
  min_profit_rate: '',
  max_profit_rate: '',
  expire_threshold_minutes: '分钟',
  max_sell_per_run: '',
  request_interval: '秒',
}

function inheritPlaceholder(field) {
  return `继承全局（${config[field]}${OVERRIDE_UNITS[field] || ''}）`
}

function booleanOverrideItems(field) {
  return [
    { title: `继承全局（${config[field] ? '启用' : '禁用'}）`, value: 'inherit' },
    { title: '启用', value: true },
    { title: '禁用', value: false },
  ]
}

function automationItems(field) {
  return [
    { title: `继承全局（${config[field] ? '开启' : '关闭'}）`, value: 'inherit' },
    { title: '开启', value: true },
    { title: '关闭', value: false },
  ]
}

function emptySitePolicy(enabled = false) {
  return {
    enabled,
    min_profit_rate: null,
    max_profit_rate: null,
    expire_threshold_minutes: null,
    max_sell_per_run: null,
    request_interval: null,
    use_proxy: 'inherit',
    dry_run: 'inherit',
    auto_harvest: 'inherit',
    auto_plant: 'inherit',
    auto_sell: 'inherit',
    expiry_sale: 'inherit',
  }
}

function parseInitialOverrides(value) {
  try {
    const parsed = typeof value === 'string' ? JSON.parse(value || '{}') : value
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      throw new Error('顶层必须是 JSON 对象')
    }
    return parsed
  } catch (parseError) {
    error.value = `初始单站覆盖 JSON 格式错误，已忽略：${parseError?.message || '无法解析'}`
    return {}
  }
}

function policyFromOverride(siteId, overrides, selectedSiteIds) {
  const override = overrides[siteId]
  const source = override && !Array.isArray(override) && typeof override === 'object'
    ? override
    : {}
  const policy = emptySitePolicy(selectedSiteIds.includes(siteId) || source.enabled === true)

  for (const field of NUMERIC_OVERRIDE_FIELDS) {
    if (typeof source[field] === 'number' && Number.isFinite(source[field])) {
      policy[field] = source[field]
    }
  }
  if (typeof source.use_proxy === 'boolean') policy.use_proxy = source.use_proxy
  if (typeof source.dry_run === 'boolean') policy.dry_run = source.dry_run
  for (const field of AUTOMATION_FIELDS) {
    if (typeof source[field] === 'boolean') policy[field] = source[field]
  }
  return policy
}

function buildOverrides() {
  const overrides = {}
  for (const site of SITE_ITEMS) {
    const policy = sitePolicies[site.value]
    if (!policy) continue

    const override = {}
    for (const field of NUMERIC_OVERRIDE_FIELDS) {
      if (typeof policy[field] === 'number' && Number.isFinite(policy[field])) {
        override[field] = policy[field]
      }
    }
    if (typeof policy.use_proxy === 'boolean') override.use_proxy = policy.use_proxy
    if (typeof policy.dry_run === 'boolean') override.dry_run = policy.dry_run
    for (const field of AUTOMATION_FIELDS) {
      if (typeof policy[field] === 'boolean') override[field] = policy[field]
    }
    if (Object.keys(override).length) overrides[site.value] = override
  }
  return overrides
}

function initialize(initialConfig) {
  Object.assign(config, DEFAULT_CONFIG, initialConfig || {})
  error.value = ''
  const selectedSiteIds = Array.isArray(config.site_ids) ? config.site_ids : []
  const overrides = parseInitialOverrides(config.site_overrides)
  for (const site of SITE_ITEMS) {
    sitePolicies[site.value] = policyFromOverride(site.value, overrides, selectedSiteIds)
  }
}

watch(
  () => props.initialConfig,
  initialConfig => initialize(initialConfig),
  { deep: true, immediate: true },
)


function effectiveSiteValue(siteId, field) {
  const value = sitePolicies[siteId]?.[field]
  return value === null || value === undefined || value === '' || value === 'inherit'
    ? config[field]
    : value
}

function profitSummary(siteId) {
  const minimum = effectiveSiteValue(siteId, 'min_profit_rate')
  const maximum = effectiveSiteValue(siteId, 'max_profit_rate')
  return `${minimum ?? 0} ~ ${maximum ? maximum : '不限'}`
}

function saveConfig() {
  error.value = ''
  const overrides = buildOverrides()
  const payload = {
    ...JSON.parse(JSON.stringify(config)),
    site_ids: SITE_ITEMS
      .filter(site => sitePolicies[site.value]?.enabled)
      .map(site => site.value),
    site_overrides: JSON.stringify(overrides),
  }
  emit('save', payload)
  setSuccess('配置已保存')
}
</script>

<template>
  <v-form class="farm-config-form text-body-2" @submit.prevent="saveConfig">
  <v-card flat class="rounded-lg border">
    <div class="farm-header bg-gradient-farm text-white">
      <div class="farm-header-row d-flex align-center ga-2 px-3 py-2">
        <div class="d-flex align-center ga-2 farm-header-left">
          <v-icon icon="mdi-sprout" color="white" size="small" />
          <span class="text-subtitle-1 text-white font-weight-bold">农场配置</span>
        </div>
        <v-spacer />
        <div class="d-flex flex-wrap align-center justify-end ga-2 farm-header-right">
          <v-btn
            icon="mdi-content-save"
            size="small"
            variant="outlined"
            color="white"
            border="white"
            :loading="loading"
            @click="saveConfig"
          />
          <v-btn
            icon="mdi-view-dashboard-outline"
            size="small"
            variant="outlined"
            color="white"
            border="white"
            @click="emit('switch')"
          />
          <v-btn
            icon="mdi-close"
            size="small"
            variant="outlined"
            color="white"
            border="white"
            @click="emit('close')"
          />
        </div>
      </div>
    </div>

    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      closable
      class="mb-4 text-body-2"
      @click:close="error = ''"
    >
      {{ error }}
    </v-alert>
    <v-alert
      v-if="successMessage"
      type="success"
      variant="tonal"
      closable
      class="mb-4 text-body-2"
      @click:close="successMessage = ''"
    >
      {{ successMessage }}
    </v-alert>

    <v-tabs
      v-model="activeTab"
      color="primary"
      density="default"
      show-arrows
      class="config-tabs mb-3"
    >
        <v-tab value="global" prepend-icon="mdi-tune-variant">全局设置<span class="tab-status-dot" :class="config.enabled ? 'on' : 'off'"></span></v-tab>
        <v-tab
          v-for="site in SITE_ITEMS"
          :key="site.value"
          :value="site.value"
          prepend-icon="mdi-web"
        >
          {{ site.title }}<span class="tab-status-dot" :class="sitePolicies[site.value]?.enabled ? 'on' : 'off'"></span>
        </v-tab>
      </v-tabs>

      <v-window v-model="activeTab">
        <v-window-item value="global">
          <div class="pa-4">
            <v-card flat class="config-section rounded border mb-4">
              <v-card-title class="config-section-title section-title-bg text-subtitle-1 d-flex align-center px-4 py-3">
                <v-icon icon="mdi-cog-outline" color="primary" size="small" class="mr-2" />
                基础设置
              </v-card-title>
              <v-card-text class="pa-4">
                <v-row>
                  <v-col cols="12" sm="4">
                    <v-switch v-model="config.enabled" label="启用插件" color="primary" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-switch v-model="config.notify" label="发送通知" color="primary" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-switch v-model="config.run_once" label="立即运行一次" color="primary" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-switch v-model="config.use_proxy" label="使用 MP 系统代理" color="info" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-switch v-model="config.dry_run" label="仅模拟（不发送操作请求）" color="warning" density="compact" hide-details />
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>

            <v-card flat class="config-section rounded border mb-4">
              <v-card-title class="config-section-title section-title-bg text-subtitle-1 d-flex align-center px-4 py-3">
                <v-icon icon="mdi-robot-outline" color="success" size="small" class="mr-2" />
                自动化功能
              </v-card-title>
              <v-card-text class="pa-4">
                <v-row>
                  <v-col cols="12" sm="4">
                    <v-switch v-model="config.auto_harvest" label="自动收获" hint="成熟作物自动收获" persistent-hint color="primary" density="compact" />
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-switch v-model="config.auto_plant" label="自动种植/养殖" hint="空地自动补种" persistent-hint color="primary" density="compact" />
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-switch v-model="config.auto_sell" label="自动出售" hint="盈利区间内自动出售" persistent-hint color="primary" density="compact" />
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-switch v-model="config.expiry_sale" label="临期自动出售" hint="剩余时间低于阈值强制出售" persistent-hint color="primary" density="compact" />
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-text-field v-model.number="config.expire_threshold_minutes" label="临期阈值（分钟）" type="number" min="10" density="compact" variant="outlined" hint="剩余时间低于此值强制出售（分钟）" persistent-hint />
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>

            <v-card flat class="config-section rounded border mb-4">
              <v-card-title class="config-section-title section-title-bg text-subtitle-1 d-flex align-center px-4 py-3">
                <v-icon icon="mdi-timer-sand" color="info" size="small" class="mr-2" />
                调度与网络
              </v-card-title>
              <v-card-text class="pa-4">
                <v-row>
                  <v-col cols="12" sm="6" md="3">
                    <v-select v-model="config.cron_mode" label="调度模式" :items="[{title:'Cron 表达式',value:'cron'},{title:'固定间隔',value:'interval'}]" density="compact" variant="outlined" />
                  </v-col>
                  <v-col v-if="config.cron_mode === 'cron'" cols="12" sm="6" md="9">
                    <v-text-field v-model="config.cron" label="Cron 表达式（5位）" placeholder="5 */4 * * *" hint="如 5 */4 * * *（每4小时第5分钟）" persistent-hint density="compact" variant="outlined" />
                  </v-col>
                  <v-col v-if="config.cron_mode !== 'cron'" cols="12" sm="6" md="3">
                    <v-text-field v-model.number="config.interval_minutes" label="运行间隔（分钟）" type="number" min="1" density="compact" variant="outlined" />
                  </v-col>
                  <v-col v-if="config.cron_mode !== 'cron'" cols="12" sm="6" md="3">
                    <v-text-field v-model.number="config.request_interval" label="请求间隔（秒）" type="number" min="0" step="0.1" density="compact" variant="outlined" />
                  </v-col>
                  <v-col v-if="config.cron_mode !== 'cron'" cols="12" sm="6" md="3">
                    <v-text-field v-model.number="config.retry_count" label="重试次数" type="number" min="0" density="compact" variant="outlined" hide-details />
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>

            <v-card flat class="config-section rounded border">
              <v-card-title class="config-section-title section-title-bg text-subtitle-1 d-flex align-center px-4 py-3">
                <v-icon icon="mdi-chart-line" color="warning" size="small" class="mr-2" />
                交易策略
              </v-card-title>
              <v-card-text class="pa-4">
                <v-row>
                  <v-col cols="12" sm="4">
                    <v-text-field v-model.number="config.min_profit_rate" label="最低利润率" type="number" min="0" step="0.01" density="compact" variant="outlined" hint="0.1 表示 10%" persistent-hint />
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-text-field v-model.number="config.max_profit_rate" label="最高利润率" type="number" min="0" step="0.01" density="compact" variant="outlined" hint="0 表示无上限" persistent-hint />
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-text-field v-model.number="config.max_sell_per_run" label="单轮单站最大出售数" type="number" min="1" density="compact" variant="outlined" />
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>
          </div>
        </v-window-item>

        <v-window-item
          v-for="site in SITE_ITEMS"
          :key="site.value"
          :value="site.value"
        >
          <div class="pa-4">
            <v-card flat class="config-section rounded border mb-4">
              <v-card-title class="config-section-title section-title-bg d-flex flex-wrap align-center ga-2 px-4 py-3">
                <v-icon icon="mdi-web" color="warning" size="small" />
                <span class="text-subtitle-1">{{ site.title }} 策略</span>
                <v-spacer />
                <v-switch
                  v-model="sitePolicies[site.value].enabled"
                  label="启用该站点"
                  color="success"
                  density="compact"
                  hide-details
                />
              </v-card-title>
              <v-card-text class="pa-4">
                <v-alert type="info" variant="tonal" class="mb-4 pa-3 text-body-2">
                  未填写的覆盖项会自动继承全局设置；禁用站点只会将其从 site_ids 中移除。
                </v-alert>

                <v-row>
                  <v-col cols="12" md="6">
                    <v-text-field
                      v-model.number="sitePolicies[site.value].min_profit_rate"
                      label="最低利润率"
                      type="number"
                      min="0"
                      step="0.01"
                      clearable
                      density="compact"
                      variant="outlined"
                      :placeholder="inheritPlaceholder('min_profit_rate')"
                      @click:clear="sitePolicies[site.value].min_profit_rate = null"
                    />
                  </v-col>
                  <v-col cols="12" md="6">
                    <v-text-field
                      v-model.number="sitePolicies[site.value].max_profit_rate"
                      label="最高利润率"
                      type="number"
                      min="0"
                      step="0.01"
                      clearable
                      density="compact"
                      variant="outlined"
                      :placeholder="inheritPlaceholder('max_profit_rate')"
                      @click:clear="sitePolicies[site.value].max_profit_rate = null"
                    />
                  </v-col>
                  <v-col cols="12" md="6">
                    <v-text-field
                      v-model.number="sitePolicies[site.value].expire_threshold_minutes"
                      label="临期阈值（分钟）"
                      type="number"
                      min="10"
                      clearable
                      density="compact"
                      variant="outlined"
                      :placeholder="inheritPlaceholder('expire_threshold_minutes')"
                      @click:clear="sitePolicies[site.value].expire_threshold_minutes = null"
                    />
                  </v-col>
                  <v-col cols="12" md="6">
                    <v-text-field
                      v-model.number="sitePolicies[site.value].max_sell_per_run"
                      label="单轮最大出售数"
                      type="number"
                      min="1"
                      clearable
                      density="compact"
                      variant="outlined"
                      :placeholder="inheritPlaceholder('max_sell_per_run')"
                      @click:clear="sitePolicies[site.value].max_sell_per_run = null"
                    />
                  </v-col>
                  <v-col cols="12" md="6">
                    <v-text-field
                      v-model.number="sitePolicies[site.value].request_interval"
                      label="请求间隔（秒）"
                      type="number"
                      min="0"
                      step="0.1"
                      clearable
                      density="compact"
                      variant="outlined"
                      :placeholder="inheritPlaceholder('request_interval')"
                      @click:clear="sitePolicies[site.value].request_interval = null"
                    />
                  </v-col>
                  <v-col cols="12" md="6">
                    <v-select
                      v-model="sitePolicies[site.value].use_proxy"
                      :items="booleanOverrideItems('use_proxy')"
                      label="代理设置"
                      density="compact"
                      variant="outlined"
                    />
                  </v-col>
                  <v-col cols="12" md="6">
                    <v-select
                      v-model="sitePolicies[site.value].dry_run"
                      :items="booleanOverrideItems('dry_run')"
                      label="模拟模式"
                      density="compact"
                      variant="outlined"
                    />
                  </v-col>
                  <v-col cols="12" md="6">
                    <v-select
                      v-model="sitePolicies[site.value].auto_harvest"
                      :items="automationItems('auto_harvest')"
                      label="自动收获"
                      density="compact"
                      variant="outlined"
                    />
                  </v-col>
                  <v-col cols="12" md="6">
                    <v-select
                      v-model="sitePolicies[site.value].auto_plant"
                      :items="automationItems('auto_plant')"
                      label="自动种植/养殖"
                      density="compact"
                      variant="outlined"
                    />
                  </v-col>
                  <v-col cols="12" md="6">
                    <v-select
                      v-model="sitePolicies[site.value].auto_sell"
                      :items="automationItems('auto_sell')"
                      label="自动出售"
                      density="compact"
                      variant="outlined"
                    />
                  </v-col>
                  <v-col cols="12" md="6">
                    <v-select
                      v-model="sitePolicies[site.value].expiry_sale"
                      :items="automationItems('expiry_sale')"
                      label="临期自动出售"
                      density="compact"
                      variant="outlined"
                    />
                  </v-col>
                </v-row>

                <div class="d-flex flex-wrap align-center ga-2 mt-2">
                  <span class="text-body-2 text-medium-emphasis">生效摘要</span>
                  <v-chip-group column class="ga-2">
                    <v-chip size="small" variant="tonal" color="success">利润：{{ profitSummary(site.value) }}</v-chip>
                    <v-chip size="small" variant="tonal" color="blue">最大出售：{{ effectiveSiteValue(site.value, 'max_sell_per_run') }}</v-chip>
                    <v-chip size="small" variant="tonal" color="info">代理：{{ effectiveSiteValue(site.value, 'use_proxy') ? '启用' : '禁用' }}</v-chip>
                    <v-chip size="small" variant="tonal" :color="effectiveSiteValue(site.value, 'dry_run') ? 'warning' : 'success'">
                      Dry Run：{{ effectiveSiteValue(site.value, 'dry_run') ? '启用' : '禁用' }}
                    </v-chip>
                    <v-chip size="small" variant="tonal" color="success">收获:{{ effectiveSiteValue(site.value, 'auto_harvest') ? '开' : '关' }}</v-chip>
                    <v-chip size="small" variant="tonal" color="success">补种:{{ effectiveSiteValue(site.value, 'auto_plant') ? '开' : '关' }}</v-chip>
                    <v-chip size="small" variant="tonal" color="success">出售:{{ effectiveSiteValue(site.value, 'auto_sell') ? '开' : '关' }}</v-chip>
                    <v-chip size="small" variant="tonal" color="success">临期:{{ effectiveSiteValue(site.value, 'expiry_sale') ? '开' : '关' }}</v-chip>
                  </v-chip-group>
                </div>
              </v-card-text>
            </v-card>

            <v-card v-if="site.value === 'siqi'" flat class="config-section rounded border">
              <v-card-title class="config-section-title section-title-bg text-subtitle-1 d-flex align-center px-4 py-3">
                <v-icon icon="mdi-shield-alert-outline" color="warning" size="small" class="mr-2" />
                思齐专属功能
              </v-card-title>
              <v-card-text class="pa-4">
                <v-alert type="warning" variant="tonal" class="mb-4 pa-3 text-body-2">
                  自动收获开启时，OCR 将优先调用站点原生一键收获；识别失败自动逐格收获。偷菜、点赞和扩地属于高风险行为。
                </v-alert>
                <v-row>
                  <v-col cols="12" sm="6" md="4">
                    <v-switch v-model="config.siqi_captcha_ocr" label="OCR 一键收获" color="primary" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="6" md="4">
                    <v-switch v-model="config.siqi_auto_buy_slot" label="自动扩地" color="primary" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="6" md="4">
                    <v-switch v-model="config.siqi_auto_steal" label="每日偷菜" color="primary" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="6" md="4">
                    <v-switch v-model="config.siqi_auto_like" label="每日点赞" color="primary" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" md="4">
                    <v-select
                      v-if="availableSeeds.length"
                      v-model="config.siqi_default_seed_id"
                      :items="availableSeeds"
                      item-title="name"
                      item-value="seed_id"
                      label="默认种植种子"
                      density="compact"
                      variant="outlined"
                      hide-details
                    >
                      <template #item="{ props, item }">
                        <v-list-item v-bind="props" :title="seedTitle(item.raw)" />
                      </template>
                      <template #selection="{ item }">
                        <span>{{ seedTitle(item.raw) }}</span>
                      </template>
                    </v-select>
                    <v-text-field
                      v-else
                      v-model.number="config.siqi_default_seed_id"
                      type="number"
                      label="默认种植种子 ID"
                      hint="无 Cookie 无法拉取种子列表，请手动输入 ID（萝卜=1）"
                      persistent-hint
                      density="compact"
                      hide-details
                    />
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>
          </div>
        </v-window-item>

      </v-window>

  </v-card>
  </v-form>
</template>

<style scoped>
.farm-config-form {
  min-inline-size: 0;
  padding: 0.5rem;
  margin-inline: auto;
}

.farm-config-form .farm-header :deep(.v-btn) {
  color: white !important;
  border-width: 1px !important;
  border-color: rgba(255, 255, 255, 0.6) !important;
}
.farm-config-form .farm-header :deep(.v-btn:hover) {
  border-color: rgba(255, 255, 255, 1) !important;
  background: rgba(255, 255, 255, 0.12) !important;
}

.config-section {
  overflow: hidden;
}

.config-tabs {
  border-block-end: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.config-section {
  background: rgba(var(--v-theme-surface), 0.96);
  box-shadow: 0 2px 10px rgba(28, 40, 52, 0.06);
}

.config-section-title {
  border-block-end: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

:deep(.v-field-label),
:deep(.v-label) {
  font-size: 0.875rem;
}

:deep(.v-field__input) {
  font-size: 1rem;
}

</style>
