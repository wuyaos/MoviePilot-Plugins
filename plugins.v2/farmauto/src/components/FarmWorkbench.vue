<script setup>
import { computed, onMounted, ref } from 'vue'

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
const running = ref(false)
const error = ref('')
const status = ref({ sites: [] })
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

async function runNow() {
  running.value = true
  error.value = ''
  try {
    const result = unwrapResponse(await request('POST', `${apiBase.value}/run`, {}))
    emit('action', result)
    await loadStatus()
  } catch (requestError) {
    error.value = requestError?.message || '提交立即运行失败'
  } finally {
    running.value = false
  }
}

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

    <v-progress-linear v-if="loading" indeterminate color="success" height="2" />

    <v-card-text :class="compact ? 'pa-3' : 'pa-4'">
      <v-alert v-if="error" type="error" variant="tonal" closable class="mb-3" @click:close="error = ''">
        {{ error }}
      </v-alert>
      <v-alert type="info" variant="tonal">
        工作台内容加载中（Phase 3 实现）
      </v-alert>
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
