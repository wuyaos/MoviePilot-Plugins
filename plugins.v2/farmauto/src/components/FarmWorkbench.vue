<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import CropArea from './CropArea.vue'
import HistoryTable from './HistoryTable.vue'
import MarketTable from './MarketTable.vue'
import PriceTrendChart from './PriceTrendChart.vue'
import SiqiPanel from './SiqiPanel.vue'
import WarehouseTable from './WarehouseTable.vue'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'FarmAuto' },
  initialTab: { type: String, default: 'main' },
  showClose: { type: Boolean, default: false },
  showSwitch: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['action', 'switch', 'close'])

const loading = ref(false)
const detailLoading = ref(false)
const running = ref(false)
const actionLoading = ref(false)
const error = ref('')
const successMessage = ref('')
const status = ref({ sites: [] })
const siteDetail = ref({})
const history = ref([])
const selectedSiteId = ref('')

const sites = computed(() => Array.isArray(status.value.sites) ? status.value.sites : [])
const selectedSite = computed(() => (
  sites.value.find(site => site.site_id === selectedSiteId.value) || sites.value[0] || {}
))
const balance = computed(() => selectedSite.value.bonus ?? '—')
const currency = computed(() => selectedSite.value.currency || '')
const enabled = computed(() => Boolean(status.value.enabled))
const useProxy = computed(() => Boolean(status.value.use_proxy))
const nextRun = computed(() => status.value.next_run || '未安排')
const dryRun = computed(() => Boolean(status.value.dry_run))
// 宿主 api 会自动拼接 /api/v1/ 前缀并附带 bearer 认证。
const apiBase = computed(() => `plugin/${props.pluginId || 'FarmAuto'}`)
const cropStatus = computed(() => siteDetail.value.crop_status || {})
const crops = computed(() => siteDetail.value.crops || {})
const trends = computed(() => siteDetail.value.trends || {})
const warehouse = computed(() => Array.isArray(siteDetail.value.warehouse) ? siteDetail.value.warehouse : [])
const marketPrices = computed(() => siteDetail.value.market_prices || {})
const siqiExtra = computed(() => siteDetail.value.siqi_extra || null)
const cropKeys = computed(() => Object.entries(crops.value)
  .filter(([, definition]) => definition?.type === 'crop')
  .map(([cropKey]) => cropKey))
const animalKeys = computed(() => Object.entries(crops.value)
  .filter(([, definition]) => definition?.type === 'animal')
  .map(([cropKey]) => cropKey))

function windowToken() {
  if (typeof window === 'undefined') return ''
  return window.__MOVIEPILOT_TOKEN__
    || window.MoviePilot?.token
    || window.localStorage?.getItem('token')
    || ''
}

async function fetchRequest(path, options = {}) {
  const token = windowToken()
  const headers = { ...(options.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  if (options.body) headers['Content-Type'] = 'application/json'

  const response = await fetch(path, { ...options, headers })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload?.message || payload?.detail || `请求失败（${response.status}）`)
  }
  return payload
}

async function request(method, path, body) {
  const hasHostApi = typeof props.api?.get === 'function' || typeof props.api?.post === 'function'
  if (hasHostApi) {
    if (method === 'GET' && typeof props.api.get === 'function') {
      return props.api.get(path)
    }
    if (method === 'POST' && typeof props.api.post === 'function') {
      return props.api.post(path, body || {})
    }
    throw new Error(`宿主 API 不支持 ${method} 请求`)
  }

  // 仅在宿主未注入 api 时兜底；相对插件路径需补全为后端绝对路径。
  const url = path.startsWith('http') || path.startsWith('/api')
    ? path
    : `/api/v1/${path}`
  return fetchRequest(url, {
    method,
    body: method === 'GET' ? undefined : JSON.stringify(body || {}),
  })
}

function unwrapResponse(response) {
  const payload = response
    && Object.prototype.hasOwnProperty.call(response, 'success')
    ? response
    : response?.data ?? response
  if (payload?.success === false) {
    throw new Error(payload.message || '请求未成功')
  }
  if (payload && Object.prototype.hasOwnProperty.call(payload, 'success')) {
    return Object.prototype.hasOwnProperty.call(payload, 'data')
      ? payload.data ?? {}
      : payload
  }
  return payload ?? {}
}

async function loadStatus() {
  loading.value = true
  error.value = ''
  try {
    status.value = unwrapResponse(await request('GET', `${apiBase.value}/status`))
    const hasSelection = sites.value.some(site => site.site_id === selectedSiteId.value)
    if (!hasSelection) selectedSiteId.value = sites.value[0]?.site_id || ''
  } catch (requestError) {
    error.value = requestError?.message || '加载农场状态失败'
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  try {
    const payload = unwrapResponse(await request('GET', `${apiBase.value}/stats`))
    history.value = Array.isArray(payload?.stats?.history) ? payload.stats.history : []
  } catch (requestError) {
    history.value = []
    error.value = requestError?.message || '加载执行记录失败'
  }
}

async function loadSiteDetail(siteId = selectedSiteId.value) {
  if (!siteId) {
    siteDetail.value = {}
    return
  }
  detailLoading.value = true
  error.value = ''
  try {
    const detail = unwrapResponse(await request('GET', `${apiBase.value}/site/${encodeURIComponent(siteId)}`))
    if (siteId === selectedSiteId.value) siteDetail.value = detail
  } catch (requestError) {
    if (siteId === selectedSiteId.value) {
      siteDetail.value = {}
      error.value = requestError?.message || '加载站点农场详情失败'
    }
  } finally {
    if (siteId === selectedSiteId.value) detailLoading.value = false
  }
}

async function refreshData() {
  await loadStatus()
  await Promise.all([loadSiteDetail(), loadHistory()])
}

async function runNow() {
  running.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const result = unwrapResponse(await request('POST', `${apiBase.value}/run`, {}))
    emit('action', result)
    await loadStatus()
    await Promise.all([loadSiteDetail(), loadHistory()])
  } catch (requestError) {
    error.value = requestError?.message || '提交立即运行失败'
  } finally {
    running.value = false
  }
}

async function postSiteAction(action, cropKey) {
  const body = cropKey ? { action, crop_key: cropKey } : { action }
  return unwrapResponse(await request(
    'POST',
    `${apiBase.value}/site/${encodeURIComponent(selectedSiteId.value)}/action`,
    body,
  ))
}

async function handleManualAction({ action, cropKey }) {
  if (!selectedSiteId.value) return
  actionLoading.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const result = await postSiteAction(action, cropKey)
    successMessage.value = result.message || `${result.target || crops.value[cropKey]?.name || cropKey || action}操作成功`
    emit('action', result)
    await loadSiteDetail(selectedSiteId.value)
  } catch (requestError) {
    error.value = requestError?.message || '手动操作失败'
  } finally {
    actionLoading.value = false
  }
}

async function sellWarehouseItem(cropKey) {
  await handleManualAction({ action: 'sell', cropKey })
}

async function sellAllWarehouseItems() {
  if (!selectedSiteId.value || !warehouse.value.length) return
  const cropKeys = warehouse.value.map(item => item.crop_key).filter(Boolean)
  if (!cropKeys.length) {
    error.value = '仓库物品缺少可出售标识'
    return
  }

  actionLoading.value = true
  error.value = ''
  successMessage.value = ''
  const failures = []
  let successCount = 0
  try {
    for (const cropKey of cropKeys) {
      try {
        const result = await postSiteAction('sell', cropKey)
        successCount += 1
        emit('action', result)
      } catch (requestError) {
        failures.push(`${crops.value[cropKey]?.name || cropKey}：${requestError?.message || '出售失败'}`)
      }
    }
    if (failures.length) error.value = failures.join('；')
    if (successCount) successMessage.value = `已出售 ${successCount} 类仓库物品`
    await loadSiteDetail(selectedSiteId.value)
  } finally {
    actionLoading.value = false
  }
}

async function handleSiqiAction({ action }) {
  await handleManualAction({ action })
}

watch(selectedSiteId, siteId => {
  successMessage.value = ''
  loadSiteDetail(siteId)
})

onMounted(() => Promise.all([loadStatus(), loadHistory()]))
</script>

<template>
  <v-card flat class="farm-workbench rounded border text-body-2">
    <v-card-title class="text-subtitle-1 d-flex align-center px-3 py-2 bg-gradient-farm">
      <v-icon icon="mdi-sprout" color="white" size="small" class="mr-2" />
      <span class="text-white">农场工作台</span>
      <v-spacer />
      <v-btn-group variant="outlined" density="compact" class="farm-header-actions">
        <v-btn
          icon="mdi-refresh"
          color="white"
          size="small"
          aria-label="刷新农场数据"
          :loading="loading || detailLoading"
          @click="refreshData"
        />
        <v-btn
          v-if="showSwitch"
          icon="mdi-cog"
          color="white"
          size="small"
          aria-label="切换到配置"
          @click="emit('switch', 'config')"
        />
        <v-btn
          v-if="showClose"
          icon="mdi-close"
          color="white"
          size="small"
          aria-label="关闭"
          @click="emit('close')"
        />
      </v-btn-group>
    </v-card-title>

    <v-progress-linear v-if="loading || detailLoading || actionLoading" indeterminate color="success" height="2" />

    <v-card-text :class="compact ? 'pa-3' : 'pa-4'">
      <v-alert v-if="error" type="error" variant="tonal" closable class="mb-3" @click:close="error = ''">
        {{ error }}
      </v-alert>
      <v-alert
        v-if="successMessage"
        type="success"
        variant="tonal"
        closable
        class="mb-3"
        @click:close="successMessage = ''"
      >
        {{ successMessage }}
      </v-alert>

      <v-card flat class="rounded border mb-3">
        <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 bg-purple-lighten-5">
          <v-icon icon="mdi-information" color="purple" size="small" class="mr-2" />
          插件运行状态
        </v-card-title>
        <v-card-text class="px-3 py-2">
          <v-row dense align="center">
            <v-col cols="3">
              <div class="text-caption text-medium-emphasis text-center">插件状态</div>
              <div class="d-flex align-center justify-center mt-1">
                <v-icon
                  icon="mdi-play-circle-outline"
                  :color="enabled ? 'success' : 'grey'"
                  size="small"
                  class="mr-1"
                />
                <span :class="enabled ? 'text-success' : 'text-medium-emphasis'">
                  {{ enabled ? '已启用' : '已禁用' }}
                </span>
              </div>
            </v-col>
            <v-col cols="3">
              <div class="text-caption text-medium-emphasis text-center">代理状态</div>
              <div class="d-flex align-center justify-center mt-1">
                <v-icon
                  icon="mdi-earth"
                  :color="useProxy ? 'info' : 'grey'"
                  size="small"
                  class="mr-1"
                />
                <span :class="useProxy ? 'text-info' : 'text-medium-emphasis'">
                  {{ useProxy ? '已启用' : '未启用' }}
                </span>
              </div>
            </v-col>
            <v-col cols="3">
              <div class="text-caption text-medium-emphasis text-center">下次执行时间</div>
              <div class="d-flex align-center justify-center mt-1">
                <v-icon icon="mdi-clock-outline" color="grey" size="small" class="mr-1" />
                <span class="text-body-2 text-truncate" :title="nextRun">{{ nextRun }}</span>
              </div>
            </v-col>
            <v-col cols="3">
              <div class="text-caption text-medium-emphasis text-center">运行操作</div>
              <div class="d-flex align-center justify-center flex-wrap ga-2 mt-1">
                <v-switch
                  :model-value="dryRun"
                  label="Dry Run"
                  color="warning"
                  density="compact"
                  hide-details
                  readonly
                />
                <v-btn
                  color="success"
                  variant="elevated"
                  size="small"
                  prepend-icon="mdi-play"
                  :loading="running"
                  @click="runNow"
                >
                  立即运行
                </v-btn>
              </div>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <v-tabs
        v-if="sites.length"
        v-model="selectedSiteId"
        color="success"
        density="compact"
        class="mb-3"
      >
        <v-tab v-for="site in sites" :key="site.site_id" :value="site.site_id">
          {{ site.site_name || site.site_id }}
        </v-tab>
      </v-tabs>

      <v-row dense>
        <v-col cols="12" md="6">
          <v-card flat class="rounded border">
            <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 bg-blue-lighten-5">
              <v-icon icon="mdi-chart-line" color="blue" size="small" class="mr-2" />
              菜市场价格波动
              <v-spacer />
              <v-chip color="blue-grey-lighten-4" size="small" variant="flat" class="magic-anim">
                <v-icon icon="mdi-auto-fix" color="purple" size="small" class="mr-1" />
                <span class="font-weight-bold">{{ balance }} {{ currency }}</span>
              </v-chip>
            </v-card-title>
            <v-card-text class="pa-3">
              <PriceTrendChart :trends="trends" :crops="crops" />
            </v-card-text>
          </v-card>
        </v-col>

        <v-col cols="12" md="6" class="d-flex flex-column ga-3">
          <CropArea
            title="农作物种植区"
            :items="cropKeys"
            :crop-status="cropStatus"
            :crops="crops"
            :loading="actionLoading"
            @action="handleManualAction"
          />
          <CropArea
            title="动物养殖区"
            :items="animalKeys"
            :crop-status="cropStatus"
            :crops="crops"
            :loading="actionLoading"
            animal
            @action="handleManualAction"
          />
        </v-col>
      </v-row>

      <v-row dense class="mt-1">
        <v-col cols="12" md="6" class="d-flex flex-column ga-3">
          <WarehouseTable
            :warehouse="warehouse"
            :crops="crops"
            :currency="currency"
            :loading="actionLoading || detailLoading"
            @sell="sellWarehouseItem"
            @sell_all="sellAllWarehouseItems"
          />
          <MarketTable
            :market_prices="marketPrices"
            :crops="crops"
            :loading="detailLoading"
          />
        </v-col>
        <v-col cols="12" md="6">
          <HistoryTable :history="history" />
        </v-col>
      </v-row>

      <v-row v-if="siqiExtra" dense class="mt-1">
        <v-col cols="12">
          <SiqiPanel
            :siqi_extra="siqiExtra"
            :loading="actionLoading"
            @action="handleSiqiAction"
          />
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.farm-workbench {
  min-inline-size: 0;
  padding: 0.5rem;
}

.bg-gradient-primary,
.bg-gradient-farm {
  background: linear-gradient(135deg, #43a047, #66bb6a) !important;
  box-shadow: 0 2px 8px rgba(67, 160, 71, 0.3);
}

.bg-purple-lighten-5 {
  background-color: rgba(156, 39, 176, 0.1) !important;
}

.bg-blue-lighten-5 {
  background-color: rgba(33, 150, 243, 0.1) !important;
}

.bg-green-lighten-5 {
  background-color: rgba(76, 175, 80, 0.1) !important;
}

.bg-brown-lighten-5 {
  background-color: rgba(121, 85, 72, 0.1) !important;
}

.bg-amber-lighten-5 {
  background-color: rgba(255, 193, 7, 0.1) !important;
}

.bg-grey-lighten-5 {
  background-color: rgba(158, 158, 158, 0.1) !important;
}

.text-subtitle-1 {
  font-size: 1.1rem !important;
  font-weight: 500 !important;
}

.text-subtitle-2 {
  font-size: 0.9rem !important;
  font-weight: 500 !important;
}

.text-caption {
  font-size: 0.75rem !important;
}

.text-body-2 {
  font-size: 0.875rem !important;
}

.farm-header-actions :deep(.v-btn) {
  color: white !important;
}

.farm-workbench :deep(.v-card) {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.farm-workbench :deep(.v-card:hover) {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.magic-anim {
  animation: magic-pulse 2s infinite ease-in-out;
}

@keyframes magic-pulse {
  0%, 100% {
    transform: scale(1) rotate(0deg);
    filter: drop-shadow(0 0 2px rgba(156, 39, 176, 0.4));
  }
  50% {
    transform: scale(1.04) rotate(1deg);
    filter: drop-shadow(0 0 5px rgba(156, 39, 176, 0.8));
  }
}

@media (prefers-color-scheme: dark) {
  .bg-purple-lighten-5 { background-color: rgba(156, 39, 176, 0.2) !important; }
  .bg-blue-lighten-5 { background-color: rgba(33, 150, 243, 0.2) !important; }
  .bg-green-lighten-5 { background-color: rgba(76, 175, 80, 0.2) !important; }
  .bg-brown-lighten-5 { background-color: rgba(121, 85, 72, 0.2) !important; }
  .bg-amber-lighten-5 { background-color: rgba(255, 193, 7, 0.2) !important; }
  .bg-grey-lighten-5 { background-color: rgba(158, 158, 158, 0.16) !important; }
}
</style>
