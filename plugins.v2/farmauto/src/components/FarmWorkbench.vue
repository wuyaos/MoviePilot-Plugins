<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import CropArea from './CropArea.vue'
import HistoryTable from './HistoryTable.vue'
import MarketTable from './MarketTable.vue'
import PriceTrendChart from './PriceTrendChart.vue'
import SiqiPanel from './SiqiPanel.vue'
import SiqiWorkbench from './SiqiWorkbench.vue'
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
const status = ref({ sites: [], selected_site_ids: [] })
const siteDetail = ref({})
const history = ref([])
const selectedSiteId = ref('')

const sites = computed(() => Array.isArray(status.value.sites) ? status.value.sites : [])
const selectedSiteIds = computed(() => (
  Array.isArray(status.value.selected_site_ids) ? status.value.selected_site_ids : []
))
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
const siqiFarm = computed(() => siteDetail.value.siqi_farm || {})
const filteredHistory = computed(() => {
  if (!selectedSiteId.value) return history.value
  const siteName = selectedSite.value.site_name
  return history.value.filter(record => (
    record.site === siteName || record.site_id === selectedSiteId.value
  ))
})
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

async function loadStatus(manageLoading = true) {
  if (manageLoading) loading.value = true
  error.value = ''
  try {
    status.value = unwrapResponse(await request('GET', `${apiBase.value}/status`))
    const hasSelection = sites.value.some(site => site.site_id === selectedSiteId.value)
    if (!hasSelection) selectedSiteId.value = sites.value[0]?.site_id || ''
  } catch (requestError) {
    error.value = requestError?.message || '加载农场状态失败'
  } finally {
    if (manageLoading) loading.value = false
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
  loading.value = true
  error.value = ''
  successMessage.value = ''
  try {
    await loadStatus(false)
    if (error.value) throw new Error(error.value)
    await Promise.all([loadSiteDetail(), loadHistory()])
    if (error.value) throw new Error(error.value)
    successMessage.value = '数据已刷新'
  } catch (requestError) {
    error.value = `刷新数据失败：${requestError?.message || '未知错误'}`
  } finally {
    loading.value = false
  }
}

async function runNow() {
  error.value = ''
  successMessage.value = ''
  if (!selectedSiteIds.value.length) {
    error.value = '请先在配置页选择至少一个站点'
    return
  }

  running.value = true
  try {
    const result = unwrapResponse(await request('POST', `${apiBase.value}/run`, {}))
    successMessage.value = result.message || '任务已在后台启动'
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

async function harvestAllCurrent() {
  if (!selectedSiteId.value) {
    error.value = '请先选择站点'
    return
  }

  actionLoading.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const result = await postSiteAction('harvest_all')
    successMessage.value = result.message || (dryRun.value ? 'dry-run：已生成一键收获计划' : '一键收获成功')
    emit('action', result)
    await loadSiteDetail(selectedSiteId.value)
  } catch (requestError) {
    error.value = requestError?.message || '一键收获失败'
  } finally {
    actionLoading.value = false
  }
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
  if (!selectedSiteId.value) {
    error.value = '请先选择站点'
    return
  }
  if (!warehouse.value.length) {
    error.value = '仓库为空，无可出售物品'
    return
  }
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

async function handleSiqiAction({ action, result }) {
  if (!result) {
    await handleManualAction({ action })
    return
  }
  emit('action', result)
  await loadSiteDetail(selectedSiteId.value)
}

watch(selectedSiteId, siteId => {
  successMessage.value = ''
  loadSiteDetail(siteId)
})

onMounted(() => Promise.all([loadStatus(), loadHistory()]))
</script>

<template>
  <v-card flat class="farm-workbench rounded border text-body-2">
    <v-card-title class="bg-gradient-farm text-white d-flex align-center ga-2 px-3 py-2">
      <v-icon icon="mdi-sprout" color="white" size="small" />
      <span class="text-subtitle-1 text-white">农场工作台</span>
      <v-spacer />

      <div class="d-flex flex-wrap align-center ga-2 farm-header-status">
        <v-chip
          size="small"
          variant="flat"
          :color="enabled ? 'success' : 'grey-darken-1'"
          :prepend-icon="enabled ? 'mdi-play-circle-outline' : 'mdi-pause-circle-outline'"
        >
          {{ enabled ? '已启用' : '已禁用' }}
        </v-chip>
        <v-chip
          size="small"
          variant="flat"
          :color="useProxy ? 'info' : 'blue-grey'"
          prepend-icon="mdi-earth"
        >
          {{ useProxy ? '代理' : '直连' }}
        </v-chip>
        <v-chip size="small" variant="flat" color="blue-grey" prepend-icon="mdi-clock-outline">
          {{ nextRun === '未安排' ? '未安排' : `下次 ${nextRun}` }}
        </v-chip>
        <v-chip
          size="small"
          variant="flat"
          :color="dryRun ? 'warning' : 'success'"
          :prepend-icon="dryRun ? 'mdi-flask-outline' : 'mdi-shield-check-outline'"
        >
          {{ dryRun ? '模拟模式' : '实盘模式' }}
        </v-chip>
      </div>

      <div class="d-flex flex-wrap align-center ga-2 farm-header-actions">
        <v-btn
          size="small"
          variant="outlined"
          color="white"
          prepend-icon="mdi-play"
          :loading="running"
          @click="runNow"
        >
          立即运行
        </v-btn>
        <v-btn
          size="small"
          variant="outlined"
          color="white"
          prepend-icon="mdi-refresh"
          :loading="loading || detailLoading"
          @click="refreshData"
        >
          刷新
        </v-btn>
        <v-btn
          v-if="showSwitch"
          size="small"
          variant="outlined"
          color="white"
          prepend-icon="mdi-cog"
          @click="emit('switch', 'config')"
        >
          设置
        </v-btn>
        <v-btn
          v-if="showClose"
          size="small"
          variant="outlined"
          color="white"
          prepend-icon="mdi-close"
          @click="emit('close')"
        >
          关闭
        </v-btn>
      </div>
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

      <SiqiWorkbench
        v-if="selectedSiteId === 'siqi' && siqiFarm"
        :api="api"
        :plugin-id="pluginId"
        :farm="siqiFarm"
        :history="filteredHistory"
        :loading="detailLoading"
        :show-switch="showSwitch"
        :show-close="showClose"
        @action="handleSiqiAction"
        @switch="emit('switch')"
        @close="emit('close')"
        @refresh="refreshData"
      />

      <template v-else>
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
            @harvest-all="harvestAllCurrent"
          />
          <CropArea
            title="动物养殖区"
            :items="animalKeys"
            :crop-status="cropStatus"
            :crops="crops"
            :loading="actionLoading"
            animal
            @action="handleManualAction"
            @harvest-all="harvestAllCurrent"
          />
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

      <v-row dense class="mt-1">
        <v-col cols="12">
          <WarehouseTable
            :warehouse="warehouse"
            :crops="crops"
            :currency="currency"
            :loading="actionLoading || detailLoading"
            @sell="sellWarehouseItem"
            @sell-all="sellAllWarehouseItems"
          />
        </v-col>
      </v-row>

      <v-row dense class="mt-1">
        <v-col cols="12">
          <MarketTable
            :market_prices="marketPrices"
            :crops="crops"
            :loading="detailLoading"
          />
        </v-col>
      </v-row>

      <v-row dense class="mt-1">
        <v-col cols="12">
          <HistoryTable :history="filteredHistory" />
        </v-col>
      </v-row>
      </template>
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
