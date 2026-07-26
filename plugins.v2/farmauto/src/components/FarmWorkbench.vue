<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import CropArea from './CropArea.vue'
import HistoryTable from './HistoryTable.vue'
import MarketTable from './MarketTable.vue'
import PriceTrendChart from './PriceTrendChart.vue'
import SiqiWorkbench from './SiqiWorkbench.vue'
import WarehouseTable from './WarehouseTable.vue'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'FarmAuto' },
  showClose: { type: Boolean, default: false },
  showSwitch: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['action', 'switch', 'close'])

const loading = ref(false)
const detailLoading = ref(false)
const refreshing = ref(false)
const balanceChanged = ref(false)
const running = ref(false)
const actionLoading = ref(false)
const error = ref('')
const successMessage = ref('')
let successTimer = null
let balanceTimer = null
const status = ref({ sites: [], selected_site_ids: [] })
const siteDetail = ref({})
const selectedSiteId = ref('')

const sites = computed(() => Array.isArray(status.value.sites) ? status.value.sites : [])
const selectedSiteIds = computed(() => (
  Array.isArray(status.value.selected_site_ids) ? status.value.selected_site_ids : []
))
const selectedSite = computed(() => (
  sites.value.find(site => site.site_id === selectedSiteId.value) || sites.value[0] || {}
))
const selectedSiteName = computed(() => selectedSite.value.site_name || '')
const balance = computed(() => siteDetail.value.bonus ?? selectedSite.value.bonus ?? '—')
const currency = computed(() => siteDetail.value.currency || selectedSite.value.currency || '')
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
const siqiFarm = computed(() => siteDetail.value.siqi_farm || {})
const siteActions = computed(() => (
  Array.isArray(siteDetail.value.recent_actions) ? siteDetail.value.recent_actions : []
))
const harvestCount = computed(() => siteActions.value
  .filter(action => action.action === 'harvest' || action.action === 'harvest_all').length)
const cropKeys = computed(() => Object.entries(crops.value)
  .filter(([, definition]) => definition?.type === 'crop')
  .map(([cropKey]) => cropKey))
const animalKeys = computed(() => Object.entries(crops.value)
  .filter(([, definition]) => definition?.type === 'animal')
  .map(([cropKey]) => cropKey))

function setSuccess(message = '') {
  successMessage.value = message
  if (successTimer) clearTimeout(successTimer)
  successTimer = message
    ? setTimeout(() => {
      successMessage.value = ''
      successTimer = null
    }, 3000)
    : null
}

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
  const previousBalance = balance.value
  loading.value = true
  refreshing.value = true
  error.value = ''
  setSuccess('')
  try {
    await loadStatus(false)
    if (error.value) throw new Error(error.value)
    await loadSiteDetail()
    if (error.value) throw new Error(error.value)
    if (balance.value !== previousBalance) {
      balanceChanged.value = true
      if (balanceTimer) clearTimeout(balanceTimer)
      balanceTimer = setTimeout(() => {
        balanceChanged.value = false
        balanceTimer = null
      }, 800)
    }
    setSuccess('数据已刷新')
  } catch (requestError) {
    error.value = `刷新数据失败：${requestError?.message || '未知错误'}`
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function runNow() {
  error.value = ''
  setSuccess('')
  if (!selectedSiteIds.value.length) {
    error.value = '请先在配置页选择至少一个站点'
    return
  }

  running.value = true
  try {
    const result = unwrapResponse(await request('POST', `${apiBase.value}/run`, {}))
    setSuccess(result.message || '任务已在后台启动')
    emit('action', result)
    await loadStatus()
    await loadSiteDetail()
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
  setSuccess('')
  try {
    const result = await postSiteAction('harvest_all')
    setSuccess(result.message || (dryRun.value ? 'dry-run：已生成一键收获计划' : '一键收获成功'))
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
  setSuccess('')
  try {
    const result = await postSiteAction(action, cropKey)
    setSuccess(result.message || `${result.target || crops.value[cropKey]?.name || cropKey || action}操作成功`)
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
  setSuccess('')
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
    if (successCount) setSuccess(`已出售 ${successCount} 类仓库物品`)
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
  setSuccess('')
  siteDetail.value = {}
  loadSiteDetail(siteId)
})

onMounted(() => loadStatus())
onBeforeUnmount(() => {
  if (successTimer) clearTimeout(successTimer)
  if (balanceTimer) clearTimeout(balanceTimer)
})
</script>

<template>
  <v-card flat class="farm-workbench rounded-lg border text-body-2">
    <div class="farm-header bg-gradient-farm text-white">
      <div class="farm-header-row d-flex align-center ga-2 px-3 py-2">
        <div class="d-flex align-center ga-2 farm-header-left">
          <v-icon icon="mdi-sprout" color="white" size="small" />
          <span class="text-subtitle-1 text-white font-weight-bold">农场工作台</span>
          <span v-if="selectedSiteName" class="text-caption text-white opacity-70 ml-1">· {{ selectedSiteName }}</span>
        </div>
        <div class="d-flex flex-wrap align-center justify-center ga-1 farm-header-status farm-header-center">
          <v-chip
            size="x-small"
            variant="flat"
            class="farm-status-chip"
            :prepend-icon="enabled ? 'mdi-play-circle-outline' : 'mdi-pause-circle-outline'"
          >
            <span class="farm-status-dot" :class="enabled ? 'dot-success' : 'dot-grey'"></span>
            {{ enabled ? '已启用' : '已禁用' }}
          </v-chip>
          <v-chip
            size="x-small"
            variant="flat"
            class="farm-status-chip"
            prepend-icon="mdi-earth"
          >
            <span class="farm-status-dot" :class="useProxy ? 'dot-info' : 'dot-teal'"></span>
            {{ useProxy ? '代理' : '直连' }}
          </v-chip>
          <v-chip size="x-small" variant="flat" class="farm-status-chip" prepend-icon="mdi-clock-outline">
            {{ nextRun === '未安排' ? '未安排' : `下次 ${nextRun}` }}
          </v-chip>
          <v-chip
            size="x-small"
            variant="flat"
            class="farm-status-chip"
            :prepend-icon="dryRun ? 'mdi-flask-outline' : 'mdi-shield-check-outline'"
          >
            <span class="farm-status-dot" :class="dryRun ? 'dot-warning' : 'dot-success'"></span>
            {{ dryRun ? '模拟模式' : '实盘模式' }}
          </v-chip>
        </div>
        <div class="d-flex flex-wrap align-center justify-end ga-3 farm-header-right">
          <v-btn
            icon="mdi-play"
            size="default"
            variant="outlined"
            color="white"
            border="white"
            :loading="running"
            @click="runNow"
          />
          <v-btn
            icon="mdi-refresh"
            size="default"
            variant="outlined"
            color="white"
            border="white"
            :loading="loading || detailLoading"
            @click="refreshData"
          />
          <v-btn
            v-if="showSwitch"
            icon="mdi-cog"
            size="default"
            variant="outlined"
            color="white"
            border="white"
            @click="emit('switch', 'config')"
          />
          <v-btn
            v-if="showClose"
            icon="mdi-close"
            size="default"
            variant="outlined"
            color="white"
            border="white"
            @click="emit('close')"
          />
        </div>
      </div>
    </div>

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
        <v-tab v-for="site in sites" :key="site.site_id" :value="site.site_id" :prepend-icon="site.site_id === 'siqi' ? 'mdi-snake' : 'mdi-web'">
          {{ site.site_name || site.site_id }}
          <span class="tab-status-dot" :class="selectedSiteIds.includes(site.site_id) ? 'on' : 'off'"></span>
        </v-tab>
      </v-tabs>

      <SiqiWorkbench
        v-if="selectedSiteId === 'siqi' && siqiFarm"
        :api="api"
        :plugin-id="pluginId"
        :farm="siqiFarm"
        :history="siteActions"
        :currency="currency"
        :loading="detailLoading"
        :show-switch="showSwitch"
        :show-close="showClose"
        @action="handleSiqiAction"
        @switch="emit('switch')"
        @close="emit('close')"
        @refresh="refreshData"
      />

      <template v-else>
        <v-row dense class="mb-3">
          <v-col cols="12" md="4">
            <div class="stat-card" :class="{ refreshing }">
              <div class="stat-icon orange"><v-icon icon="mdi-auto-fix" /></div>
              <div class="stat-content">
                <div class="stat-title">魔力值</div>
                <div
                  class="stat-value"
                  :class="{ refreshing, 'value-changed': balanceChanged }"
                >
                  {{ balance }} <small v-if="currency">{{ currency }}</small>
                </div>
              </div>
            </div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="stat-card" :class="{ refreshing }">
              <div class="stat-icon green"><v-icon icon="mdi-sprout" /></div>
              <div class="stat-content">
                <div class="stat-title">收获</div>
                <div class="stat-value" :class="{ refreshing }">
                  {{ harvestCount }} <small>次</small>
                </div>
              </div>
            </div>
          </v-col>
          <v-col cols="12" md="4">
            <div class="stat-card" :class="{ refreshing }">
              <div class="stat-icon amber"><v-icon icon="mdi-sync" /></div>
              <div class="stat-content">
                <div class="stat-title">操作数</div>
                <div class="stat-value" :class="{ refreshing }">
                  {{ siteActions.length }} <small>次</small>
                </div>
              </div>
            </div>
          </v-col>
        </v-row>

        <v-row dense class="mb-3">
          <v-col cols="12" md="6">
            <v-card flat class="rounded border">
              <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 section-title-bg">
                <v-icon icon="mdi-chart-line" color="blue" size="small" class="mr-2" />
                菜市场价格波动
                <span class="text-caption text-medium-emphasis ml-2">价格随运行更新 · 波动±20%</span>
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
          <v-col cols="12" md="6">
            <MarketTable
              :market_prices="marketPrices"
              :crops="crops"
              :trends="trends"
              :loading="detailLoading"
            />
          </v-col>
        </v-row>

        <v-row dense class="mb-3">
          <v-col cols="12" md="6">
            <CropArea
              title="农作物种植区"
              :items="cropKeys"
              :crop-status="cropStatus"
              :crops="crops"
              :loading="actionLoading"
              @action="handleManualAction"
              @harvest-all="harvestAllCurrent"
            />
          </v-col>
          <v-col cols="12" md="6">
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

        <v-row dense>
          <v-col cols="12" md="6">
            <WarehouseTable
              :warehouse="warehouse"
              :crops="crops"
              :currency="currency"
              :loading="actionLoading || detailLoading"
              @sell="sellWarehouseItem"
              @sell-all="sellAllWarehouseItems"
            />
          </v-col>
          <v-col cols="12" md="6">
            <HistoryTable :history="siteActions" :currency="currency" />
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
  max-width: 1100px;
  margin-inline: auto;
}

.farm-header {
  border-radius: inherit;
}
.farm-header-row { position: relative; }
.farm-header-left { flex: 0 0 auto; }
.farm-header-center { flex: 1 1 auto; }
.farm-header-right { flex: 0 0 auto; }

.farm-workbench :deep(.v-card) {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.farm-workbench :deep(.v-card:hover) {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.value-changed { animation: value-flash 0.8s ease; }
@keyframes value-flash { 0% { color: inherit; } 30% { color: #4ade80; text-shadow: 0 0 8px rgba(74,222,128,0.4); } 100% { color: inherit; text-shadow: none; } }

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
</style>

<style>
/**
 * FarmAuto 共享主题样式
 * 解决 Vuetify 联邦构建下 scoped :deep 失效与多组件重复定义问题
 */

/* 区块标题背景：深浅色自适应，替代 bg-*-lighten-5 */
.section-title-bg {
  background-color: rgba(var(--v-theme-on-surface), 0.06) !important;
}

/* 顶栏渐变背景（主题色感知） */
.bg-gradient-farm {
  background: rgba(var(--v-theme-on-surface), 0.06) !important;
  backdrop-filter: blur(16px) saturate(0.9);
  -webkit-backdrop-filter: blur(16px) saturate(0.9);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.farm-status-chip {
  background: rgba(255, 255, 255, 0.15) !important;
  color: rgba(255, 255, 255, 0.92) !important;
  border: 1px solid rgba(255, 255, 255, 0.25) !important;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}
.farm-status-chip :deep(.v-chip__content) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.farm-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 2px;
}
.farm-status-dot.dot-success { background: #4ade80; box-shadow: 0 0 4px rgba(74, 222, 128, 0.6); }
.farm-status-dot.dot-info { background: #60a5fa; box-shadow: 0 0 4px rgba(96, 165, 250, 0.6); }
.farm-status-dot.dot-teal { background: #2dd4bf; box-shadow: 0 0 4px rgba(45, 212, 191, 0.6); }
.farm-status-dot.dot-warning { background: #fbbf24; box-shadow: 0 0 4px rgba(251, 191, 36, 0.6); }
.farm-status-dot.dot-grey { background: #9ca3af; }

/* 统计卡（KoWming 风格） */
.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  border-radius: 14px;
  padding: 12px 14px;
  border: 0.5px solid rgba(var(--v-theme-on-surface), 0.08);
  background: rgba(var(--v-theme-on-surface), 0.03);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2),
    0 2px 12px rgba(var(--v-theme-on-surface), 0.08);
  transition: all 0.3s ease;
}
.stat-card.refreshing {
  animation: stat-pulse 0.6s ease;
}
@keyframes stat-pulse {
  0% { background: rgba(var(--v-theme-on-surface), 0.03); }
  50% {
    background: rgba(34, 197, 94, 0.08);
    border-color: rgba(34, 197, 94, 0.2);
  }
  100% { background: rgba(var(--v-theme-on-surface), 0.03); }
}
.stat-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 38px;
}
.stat-icon.orange { background: rgba(245, 158, 11, 0.14); color: rgb(var(--v-theme-warning)); }
.stat-icon.green { background: rgba(34, 197, 94, 0.14); color: rgb(var(--v-theme-success)); }
.stat-icon.red { background: rgba(239, 68, 68, 0.14); color: rgb(var(--v-theme-error)); }
.stat-icon.blue { background: rgba(59, 130, 246, 0.14); color: rgb(var(--v-theme-info)); }
.stat-icon.amber { background: rgba(217, 119, 6, 0.14); color: rgb(var(--v-theme-warning)); }
.stat-content { min-width: 0; flex: 1; }
.stat-title {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.55);
  font-weight: 600;
}
.stat-value {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -0.5px;
}
.stat-value small { font-size: 11px; opacity: 0.5; font-weight: 400; }
.stat-value.refreshing { opacity: 0.3; }

.tab-status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-left: 6px;
  vertical-align: middle;
}
.tab-status-dot.on { background: #4ade80; box-shadow: 0 0 4px rgba(74, 222, 128, 0.6); }
.tab-status-dot.off { background: rgba(var(--v-theme-on-surface), 0.25); }
</style>
