<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import CropArea from './CropArea.vue'
import PriceTrendChart from './PriceTrendChart.vue'

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
const selectedSiteId = ref('')

const sites = computed(() => Array.isArray(status.value.sites) ? status.value.sites : [])
const selectedSite = computed(() => (
  sites.value.find(site => site.site_id === selectedSiteId.value) || sites.value[0] || {}
))
const balance = computed(() => selectedSite.value.bonus ?? '—')
const currency = computed(() => selectedSite.value.currency || '')
const nextRun = computed(() => status.value.next_run || '未安排')
const dryRun = computed(() => Boolean(status.value.dry_run))
const apiBase = computed(() => `/api/v1/plugin/${props.pluginId}`)
const cropStatus = computed(() => siteDetail.value.crop_status || {})
const crops = computed(() => siteDetail.value.crops || {})
const trends = computed(() => siteDetail.value.trends || {})
const cropKeys = ['crop_1', 'crop_2', 'crop_3', 'crop_4']
const animalKeys = ['animal_1', 'animal_2', 'animal_3', 'animal_4']

function windowToken() {
  if (typeof window === 'undefined') return ''
  return window.__MOVIEPILOT_TOKEN__
    || window.MoviePilot?.token
    || window.localStorage?.getItem('token')
    || ''
}

async function fetchRequest(path, options = {}) {
  const token = props.api?.token || windowToken()
  const headers = { ...(options.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  if (options.body) headers['Content-Type'] = 'application/json'

  const response = await fetch(path, { ...options, headers })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload?.message || `请求失败（${response.status}）`)
  }
  return payload
}

async function request(method, path, body) {
  const apiMethod = props.api?.[method.toLowerCase()]
  if (typeof apiMethod === 'function') {
    return method === 'GET'
      ? apiMethod.call(props.api, path)
      : apiMethod.call(props.api, path, body || {})
  }
  return fetchRequest(path, {
    method,
    body: method === 'GET' ? undefined : JSON.stringify(body || {}),
  })
}

function unwrapResponse(response) {
  const payload = response?.data ?? response
  if (payload?.success === false) {
    throw new Error(payload.message || '请求未成功')
  }
  return payload?.data ?? payload ?? {}
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

async function runNow() {
  running.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const result = unwrapResponse(await request('POST', `${apiBase.value}/run`, {}))
    emit('action', result)
    await loadStatus()
    await loadSiteDetail()
  } catch (requestError) {
    error.value = requestError?.message || '提交立即运行失败'
  } finally {
    running.value = false
  }
}

async function handleManualAction({ action, cropKey }) {
  if (!selectedSiteId.value) return
  actionLoading.value = true
  error.value = ''
  successMessage.value = ''
  try {
    const result = unwrapResponse(await request(
      'POST',
      `${apiBase.value}/site/${encodeURIComponent(selectedSiteId.value)}/action`,
      { action, crop_key: cropKey },
    ))
    successMessage.value = result.message || `${result.target || crops.value[cropKey]?.name || cropKey}操作成功`
    emit('action', result)
    await loadSiteDetail(selectedSiteId.value)
  } catch (requestError) {
    error.value = requestError?.message || '手动操作失败'
  } finally {
    actionLoading.value = false
  }
}

watch(selectedSite, site => {
  successMessage.value = ''
  loadSiteDetail(site?.site_id || '')
})

onMounted(loadStatus)
</script>

<template>
  <v-card flat class="farm-workbench rounded border">
    <v-card-title class="d-flex flex-wrap align-center ga-3 px-4 py-3">
      <div class="d-flex align-center ga-2">
        <v-icon icon="mdi-sprout" color="success" />
        <span>农场工作台</span>
      </div>

      <v-tabs
        v-if="sites.length"
        v-model="selectedSiteId"
        color="success"
        density="compact"
        class="farm-workbench__tabs"
      >
        <v-tab v-for="site in sites" :key="site.site_id" :value="site.site_id">
          {{ site.site_name || site.site_id }}
        </v-tab>
      </v-tabs>

      <v-spacer />

      <div class="text-caption text-medium-emphasis">
        余额 <strong class="text-body-2 text-high-emphasis">{{ balance }} {{ currency }}</strong>
      </div>
      <div class="text-caption text-medium-emphasis">
        下次运行 <strong class="text-body-2 text-high-emphasis">{{ nextRun }}</strong>
      </div>
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
        prepend-icon="mdi-play"
        :loading="running"
        @click="runNow"
      >
        立即运行
      </v-btn>
      <v-btn
        v-if="showSwitch"
        icon="mdi-cog"
        variant="text"
        size="small"
        aria-label="切换到配置"
        @click="emit('switch', 'config')"
      />
      <v-btn
        v-if="showClose"
        icon="mdi-close"
        variant="text"
        size="small"
        aria-label="关闭"
        @click="emit('close')"
      />
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

      <v-row dense>
        <v-col cols="12" md="6">
          <v-card flat class="rounded border">
            <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 bg-blue-lighten-5">
              <v-icon icon="mdi-chart-line" color="blue" size="small" class="mr-2" />
              价格趋势
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
    </v-card-text>
  </v-card>
</template>

<style scoped>
.farm-workbench {
  min-inline-size: 0;
}

.farm-workbench__tabs {
  min-inline-size: 12rem;
  max-inline-size: 36rem;
}

@media (max-width: 959px) {
  .farm-workbench__tabs {
    order: 3;
    inline-size: 100%;
    max-inline-size: none;
  }
}
</style>
