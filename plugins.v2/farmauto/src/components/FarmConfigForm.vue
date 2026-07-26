<script setup>
import { reactive, ref, watch } from 'vue'

const DEFAULT_CONFIG = {
  enabled: false,
  notify: true,
  run_once: false,
  mode: 'smart',
  site_ids: [],
  interval_minutes: 61,
  harvest_interval_minutes: 61,
  expire_threshold_minutes: 120,
  min_profit_rate: 0,
  max_profit_rate: 0,
  max_sell_per_run: 50,
  request_interval: 1,
  retry_count: 3,
  use_proxy: false,
  dry_run: false,
  siqi_auto_captcha_harvest: false,
  siqi_captcha_ocr: true,
  siqi_auto_buy_slot: false,
  siqi_auto_steal: false,
  siqi_auto_like: false,
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

const MODE_ITEMS = [
  { title: '智能交易', value: 'smart' },
  { title: '自动收获', value: 'harvest' },
]

const SITE_MODE_ITEMS = [
  { title: '继承全局', value: 'inherit' },
  ...MODE_ITEMS,
]

const BOOLEAN_OVERRIDE_ITEMS = [
  { title: '继承全局', value: 'inherit' },
  { title: '启用', value: true },
  { title: '禁用', value: false },
]

const NUMERIC_OVERRIDE_FIELDS = [
  'min_profit_rate',
  'max_profit_rate',
  'expire_threshold_minutes',
  'max_sell_per_run',
  'request_interval',
]

const props = defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['save', 'switch', 'close'])
const activeTab = ref('global')
const config = reactive({ ...DEFAULT_CONFIG })
const sitePolicies = reactive({})
const advancedJson = ref('{}')
const error = ref('')

function emptySitePolicy(enabled = false) {
  return {
    enabled,
    mode: 'inherit',
    min_profit_rate: null,
    max_profit_rate: null,
    expire_threshold_minutes: null,
    max_sell_per_run: null,
    request_interval: null,
    use_proxy: 'inherit',
    dry_run: 'inherit',
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

  if (source.mode === 'smart' || source.mode === 'harvest') policy.mode = source.mode
  for (const field of NUMERIC_OVERRIDE_FIELDS) {
    if (typeof source[field] === 'number' && Number.isFinite(source[field])) {
      policy[field] = source[field]
    }
  }
  if (typeof source.use_proxy === 'boolean') policy.use_proxy = source.use_proxy
  if (typeof source.dry_run === 'boolean') policy.dry_run = source.dry_run
  return policy
}

function buildOverrides() {
  const overrides = {}
  for (const site of SITE_ITEMS) {
    const policy = sitePolicies[site.value]
    if (!policy) continue

    const override = {}
    if (policy.mode === 'smart' || policy.mode === 'harvest') override.mode = policy.mode
    for (const field of NUMERIC_OVERRIDE_FIELDS) {
      if (typeof policy[field] === 'number' && Number.isFinite(policy[field])) {
        override[field] = policy[field]
      }
    }
    if (typeof policy.use_proxy === 'boolean') override.use_proxy = policy.use_proxy
    if (typeof policy.dry_run === 'boolean') override.dry_run = policy.dry_run
    if (Object.keys(override).length) overrides[site.value] = override
  }
  return overrides
}

function syncAdvancedJson() {
  const formatted = JSON.stringify(buildOverrides(), null, 2)
  advancedJson.value = formatted
  config.site_overrides = formatted
}

function initialize(initialConfig) {
  Object.assign(config, DEFAULT_CONFIG, initialConfig || {})
  error.value = ''
  const selectedSiteIds = Array.isArray(config.site_ids) ? config.site_ids : []
  const overrides = parseInitialOverrides(config.site_overrides)
  for (const site of SITE_ITEMS) {
    sitePolicies[site.value] = policyFromOverride(site.value, overrides, selectedSiteIds)
  }
  syncAdvancedJson()
}

watch(
  () => props.initialConfig,
  initialConfig => initialize(initialConfig),
  { deep: true, immediate: true },
)

watch(sitePolicies, syncAdvancedJson, { deep: true })

function applyAdvancedJson() {
  error.value = ''
  let overrides
  try {
    overrides = JSON.parse(advancedJson.value || '{}')
    if (!overrides || Array.isArray(overrides) || typeof overrides !== 'object') {
      throw new Error('顶层必须是 JSON 对象')
    }
    for (const [siteId, override] of Object.entries(overrides)) {
      if (!SITE_ITEMS.some(site => site.value === siteId)) {
        throw new Error(`不支持站点 ${siteId}`)
      }
      if (!override || Array.isArray(override) || typeof override !== 'object') {
        throw new Error(`${siteId} 的配置必须是对象`)
      }
    }
  } catch (parseError) {
    error.value = `单站覆盖 JSON 格式错误：${parseError?.message || '无法解析'}`
    return
  }

  for (const site of SITE_ITEMS) {
    const currentEnabled = sitePolicies[site.value]?.enabled ?? false
    const override = overrides[site.value]
    const source = override && !Array.isArray(override) && typeof override === 'object'
      ? override
      : {}
    const selectedSiteIds = source.enabled === true
      ? [site.value]
      : (source.enabled === false ? [] : (currentEnabled ? [site.value] : []))
    sitePolicies[site.value] = policyFromOverride(site.value, overrides, selectedSiteIds)
  }
  syncAdvancedJson()
}

function inheritedValue(siteId, field) {
  const value = sitePolicies[siteId]?.[field]
  return value === null || value === undefined || value === '' || value === 'inherit'
    ? config[field]
    : value
}

function modeLabel(siteId) {
  return inheritedValue(siteId, 'mode') === 'harvest' ? '自动收获' : '智能交易'
}

function profitSummary(siteId) {
  const minimum = inheritedValue(siteId, 'min_profit_rate')
  const maximum = inheritedValue(siteId, 'max_profit_rate')
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
}
</script>

<template>
  <v-form class="farm-config-form text-body-2" @submit.prevent="saveConfig">
    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      closable
      class="mb-3 text-caption"
      @click:close="error = ''"
    >
      {{ error }}
    </v-alert>

    <v-card flat class="rounded border mb-3 config-tabs-card">
      <v-tabs
        v-model="activeTab"
        color="primary"
        density="compact"
        show-arrows
        class="config-tabs"
      >
        <v-tab value="global" prepend-icon="mdi-tune-variant">全局设置</v-tab>
        <v-tab
          v-for="site in SITE_ITEMS"
          :key="site.value"
          :value="site.value"
          prepend-icon="mdi-web"
        >
          {{ site.title }}
        </v-tab>
        <v-tab value="advanced" prepend-icon="mdi-code-json">高级设置</v-tab>
      </v-tabs>

      <v-window v-model="activeTab">
        <v-window-item value="global">
          <div class="pa-3">
            <v-card flat class="config-section rounded border mb-3">
              <v-card-title class="config-section-title text-subtitle-2 d-flex align-center px-3 py-2 bg-blue-lighten-5">
                <v-icon icon="mdi-cog-outline" color="purple" size="small" class="mr-2" />
                基础设置
              </v-card-title>
              <v-card-text class="pa-3">
                <v-row dense>
                  <v-col cols="12" sm="4">
                    <v-switch v-model="config.enabled" label="启用插件" color="primary" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-switch v-model="config.notify" label="发送通知" color="primary" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="4">
                    <v-switch v-model="config.run_once" label="立即运行一次" color="primary" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" md="4">
                    <v-select
                      v-model="config.mode"
                      :items="MODE_ITEMS"
                      label="运行模式"
                      density="compact"
                      variant="outlined"
                      hide-details
                    />
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>

            <v-card flat class="config-section rounded border">
              <v-card-title class="config-section-title text-subtitle-2 d-flex align-center px-3 py-2 bg-green-lighten-5">
                <v-icon icon="mdi-chart-timeline-variant" color="green" size="small" class="mr-2" />
                调度与策略
              </v-card-title>
              <v-card-text class="pa-3">
                <v-row dense>
                  <v-col cols="12" md="4">
                    <v-text-field v-model.number="config.interval_minutes" label="智能交易间隔（分钟）" type="number" min="1" density="compact" variant="outlined" />
                  </v-col>
                  <v-col cols="12" md="4">
                    <v-text-field v-model.number="config.harvest_interval_minutes" label="自动收获间隔（分钟）" type="number" min="5" density="compact" variant="outlined" />
                  </v-col>
                  <v-col cols="12" md="4">
                    <v-text-field v-model.number="config.expire_threshold_minutes" label="临期阈值（分钟）" type="number" min="10" density="compact" variant="outlined" />
                  </v-col>
                  <v-col cols="12" sm="6" md="3">
                    <v-text-field v-model.number="config.min_profit_rate" label="最低利润率" type="number" min="0" step="0.01" density="compact" variant="outlined" hint="0.1 表示 10%" persistent-hint />
                  </v-col>
                  <v-col cols="12" sm="6" md="3">
                    <v-text-field v-model.number="config.max_profit_rate" label="最高利润率" type="number" min="0" step="0.01" density="compact" variant="outlined" hint="0 表示无上限" persistent-hint />
                  </v-col>
                  <v-col cols="12" sm="6" md="3">
                    <v-text-field v-model.number="config.max_sell_per_run" label="单轮单站最大出售数" type="number" min="1" density="compact" variant="outlined" />
                  </v-col>
                  <v-col cols="12" sm="6" md="3">
                    <v-text-field v-model.number="config.request_interval" label="请求间隔（秒）" type="number" min="0" step="0.1" density="compact" variant="outlined" />
                  </v-col>
                  <v-col cols="12" md="4">
                    <v-text-field v-model.number="config.retry_count" label="重试次数" type="number" min="0" density="compact" variant="outlined" hide-details />
                  </v-col>
                  <v-col cols="12" sm="6" md="4">
                    <v-switch v-model="config.use_proxy" label="使用 MP 系统代理" color="info" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="6" md="4">
                    <v-switch v-model="config.dry_run" label="仅模拟（不发送操作请求）" color="warning" density="compact" hide-details />
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
          <div class="pa-3">
            <v-card flat class="config-section rounded border mb-3">
              <v-card-title class="config-section-title d-flex flex-wrap align-center ga-2 px-3 py-2 bg-green-lighten-5">
                <v-icon icon="mdi-web" color="green" size="small" />
                <span class="text-subtitle-2">{{ site.title }} 策略</span>
                <v-spacer />
                <v-switch
                  v-model="sitePolicies[site.value].enabled"
                  label="启用该站点"
                  color="success"
                  density="compact"
                  hide-details
                />
              </v-card-title>
              <v-card-text class="pa-3">
                <v-alert type="info" variant="tonal" density="compact" class="mb-3 text-caption">
                  未填写的覆盖项会自动继承全局设置；禁用站点只会将其从 site_ids 中移除。
                </v-alert>

                <v-row dense>
                  <v-col cols="12" sm="6" md="3">
                    <v-select
                      v-model="sitePolicies[site.value].mode"
                      :items="SITE_MODE_ITEMS"
                      label="运行模式"
                      density="compact"
                      variant="outlined"
                    />
                  </v-col>
                  <v-col cols="12" sm="6" md="3">
                    <v-text-field
                      v-model.number="sitePolicies[site.value].min_profit_rate"
                      label="最低利润率"
                      type="number"
                      min="0"
                      step="0.01"
                      clearable
                      density="compact"
                      variant="outlined"
                      @click:clear="sitePolicies[site.value].min_profit_rate = null"
                    />
                  </v-col>
                  <v-col cols="12" sm="6" md="3">
                    <v-text-field
                      v-model.number="sitePolicies[site.value].max_profit_rate"
                      label="最高利润率"
                      type="number"
                      min="0"
                      step="0.01"
                      clearable
                      density="compact"
                      variant="outlined"
                      @click:clear="sitePolicies[site.value].max_profit_rate = null"
                    />
                  </v-col>
                  <v-col cols="12" sm="6" md="3">
                    <v-text-field
                      v-model.number="sitePolicies[site.value].expire_threshold_minutes"
                      label="临期阈值（分钟）"
                      type="number"
                      min="10"
                      clearable
                      density="compact"
                      variant="outlined"
                      @click:clear="sitePolicies[site.value].expire_threshold_minutes = null"
                    />
                  </v-col>
                  <v-col cols="12" sm="6" md="3">
                    <v-text-field
                      v-model.number="sitePolicies[site.value].max_sell_per_run"
                      label="单轮最大出售数"
                      type="number"
                      min="1"
                      clearable
                      density="compact"
                      variant="outlined"
                      @click:clear="sitePolicies[site.value].max_sell_per_run = null"
                    />
                  </v-col>
                  <v-col cols="12" sm="6" md="3">
                    <v-text-field
                      v-model.number="sitePolicies[site.value].request_interval"
                      label="请求间隔（秒）"
                      type="number"
                      min="0"
                      step="0.1"
                      clearable
                      density="compact"
                      variant="outlined"
                      @click:clear="sitePolicies[site.value].request_interval = null"
                    />
                  </v-col>
                  <v-col cols="12" sm="6" md="3">
                    <v-select
                      v-model="sitePolicies[site.value].use_proxy"
                      :items="BOOLEAN_OVERRIDE_ITEMS"
                      label="代理设置"
                      density="compact"
                      variant="outlined"
                    />
                  </v-col>
                  <v-col cols="12" sm="6" md="3">
                    <v-select
                      v-model="sitePolicies[site.value].dry_run"
                      :items="BOOLEAN_OVERRIDE_ITEMS"
                      label="模拟模式"
                      density="compact"
                      variant="outlined"
                    />
                  </v-col>
                </v-row>

                <div class="d-flex flex-wrap align-center ga-2 mt-1">
                  <span class="text-caption text-medium-emphasis">生效摘要</span>
                  <v-chip size="small" variant="tonal" color="primary">模式：{{ modeLabel(site.value) }}</v-chip>
                  <v-chip size="small" variant="tonal" color="success">利润：{{ profitSummary(site.value) }}</v-chip>
                  <v-chip size="small" variant="tonal" color="blue">最大出售：{{ inheritedValue(site.value, 'max_sell_per_run') }}</v-chip>
                  <v-chip size="small" variant="tonal" color="info">代理：{{ inheritedValue(site.value, 'use_proxy') ? '启用' : '禁用' }}</v-chip>
                  <v-chip size="small" variant="tonal" :color="inheritedValue(site.value, 'dry_run') ? 'warning' : 'success'">
                    Dry Run：{{ inheritedValue(site.value, 'dry_run') ? '启用' : '禁用' }}
                  </v-chip>
                </div>
              </v-card-text>
            </v-card>

            <v-card v-if="site.value === 'siqi'" flat class="config-section rounded border">
              <v-card-title class="config-section-title text-subtitle-2 d-flex align-center px-3 py-2 bg-amber-lighten-5">
                <v-icon icon="mdi-shield-alert-outline" color="amber-darken-3" size="small" class="mr-2" />
                思齐专属功能
              </v-card-title>
              <v-card-text class="pa-3">
                <v-alert type="warning" variant="tonal" density="compact" class="mb-3 text-caption">
                  验证码收获、偷菜、点赞和扩地属于高风险行为；除 OCR 外默认关闭，开启即表示自行承担账号风控风险。
                </v-alert>
                <v-row dense>
                  <v-col cols="12" sm="6" md="4">
                    <v-switch v-model="config.siqi_auto_captcha_harvest" label="验证码收获" color="warning" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="6" md="4">
                    <v-switch v-model="config.siqi_captcha_ocr" label="OCR 优先" color="warning" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="6" md="4">
                    <v-switch v-model="config.siqi_auto_buy_slot" label="自动扩地" color="warning" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-switch v-model="config.siqi_auto_steal" label="每日偷菜" color="warning" density="compact" hide-details />
                  </v-col>
                  <v-col cols="12" sm="6">
                    <v-switch v-model="config.siqi_auto_like" label="每日点赞" color="warning" density="compact" hide-details />
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>
          </div>
        </v-window-item>

        <v-window-item value="advanced">
          <div class="pa-3">
            <v-card flat class="config-section rounded border">
              <v-card-title class="config-section-title text-subtitle-2 d-flex align-center px-3 py-2 bg-grey-lighten-5">
                <v-icon icon="mdi-code-json" color="blue-grey" size="small" class="mr-2" />
                自动生成的单站覆盖 JSON
              </v-card-title>
              <v-card-text class="pa-3">
                <v-alert type="info" variant="tonal" density="compact" class="mb-3 text-caption">
                  可视化设置会自动更新此 JSON。手动修改后请点击“应用 JSON”，再保存配置。
                </v-alert>
                <v-textarea
                  v-model="advancedJson"
                  label="site_overrides"
                  rows="14"
                  density="compact"
                  variant="outlined"
                  spellcheck="false"
                  hide-details
                />
                <div class="d-flex justify-end mt-3">
                  <v-btn variant="outlined" color="primary" prepend-icon="mdi-check" @click="applyAdvancedJson">
                    应用 JSON
                  </v-btn>
                </div>
              </v-card-text>
            </v-card>
          </div>
        </v-window-item>
      </v-window>
    </v-card>

    <div class="d-flex flex-wrap justify-end ga-2">
      <v-btn variant="text" prepend-icon="mdi-close" @click="emit('close')">关闭</v-btn>
      <v-btn variant="outlined" color="primary" prepend-icon="mdi-view-dashboard-outline" @click="emit('switch')">
        切换到详情
      </v-btn>
      <v-btn type="submit" color="primary" prepend-icon="mdi-content-save" :loading="loading">
        保存配置
      </v-btn>
    </div>
  </v-form>
</template>

<style scoped>
.farm-config-form {
  min-inline-size: 0;
  padding: 0.5rem;
}

.config-tabs-card,
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

.bg-blue-lighten-5 { background-color: rgba(33, 150, 243, 0.1) !important; }
.bg-green-lighten-5 { background-color: rgba(76, 175, 80, 0.1) !important; }
.bg-amber-lighten-5 { background-color: rgba(255, 193, 7, 0.12) !important; }
.bg-grey-lighten-5 { background-color: rgba(158, 158, 158, 0.1) !important; }

@media (prefers-color-scheme: dark) {
  .bg-blue-lighten-5 { background-color: rgba(33, 150, 243, 0.2) !important; }
  .bg-green-lighten-5 { background-color: rgba(76, 175, 80, 0.2) !important; }
  .bg-amber-lighten-5 { background-color: rgba(255, 193, 7, 0.2) !important; }
  .bg-grey-lighten-5 { background-color: rgba(158, 158, 158, 0.16) !important; }
}
</style>
