<script setup>
import { computed, getCurrentInstance, inject, onMounted, ref } from 'vue'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'Hhanclubrescueseed' },
})
const emit = defineEmits(['action', 'switch', 'close'])
const toast = inject('moviepilot:toast', null)
const instance = getCurrentInstance()
const pluginApi = instance?.proxy?.$pluginApi || props.api

const records = ref([])
const autoDeleteEnabled = ref(false)
const loading = ref(false)
const deleting = ref('')
const error = ref('')

const headers = [
  { title: '名称', key: 'title', minWidth: '260px' },
  { title: '体积', key: 'size', width: '120px' },
  { title: '得分', key: 'score', width: '90px' },
  { title: '下载时间', key: 'added_on', width: '170px' },
  { title: '做种时长', key: 'seeding_time', width: '130px' },
  { title: '状态', key: 'status', width: '120px' },
  { title: '进度', key: 'progress', width: '90px' },
  { title: '上传体积', key: 'uploaded', width: '130px' },
  { title: '操作', key: 'actions', sortable: false, align: 'end', width: '90px' },
]

function notify(type, message) {
  if (toast && typeof toast[type] === 'function') toast[type](message)
  else (type === 'error' ? console.error : console.log)(message)
}

function unwrap(response) {
  return response?.data && typeof response.data.success === 'boolean' ? response.data : response
}

function valueOf(record, ...keys) {
  for (const key of keys) if (record?.[key] !== undefined && record?.[key] !== null) return record[key]
  return ''
}

function toGb(value) {
  if (typeof value === 'number') return value
  const text = String(value || '').trim().toUpperCase()
  const amount = Number.parseFloat(text)
  if (!Number.isFinite(amount)) return 0
  if (text.includes('TB')) return amount * 1024
  if (text.includes('MB')) return amount / 1024
  if (text.includes('KB')) return amount / (1024 * 1024)
  return amount
}

function formatSize(value) {
  if (value === '' || value === null || value === undefined) return '-'
  if (typeof value === 'string' && /[A-Za-z]/.test(value)) return value
  return `${toGb(value).toFixed(2)} GB`
}

function formatAddedOn(record) {
  const value = valueOf(record, 'added_on', 'download_time')
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function formatSeedingTime(value) {
  if (value === '' || value === null || value === undefined) return '-'
  if (typeof value === 'string' && /天\s*\d+小时/.test(value)) return value
  let hours = Number(value)
  if (!Number.isFinite(hours)) {
    const text = String(value)
    const dayMatch = text.match(/([\d.]+)\s*天/)
    const hourMatch = text.match(/([\d.]+)\s*小时/)
    if (dayMatch) hours = Number(dayMatch[1]) * 24 + (hourMatch ? Number(hourMatch[1]) : 0)
    else hours = Number.parseFloat(text)
    if (!Number.isFinite(hours)) return text
  }
  const days = Math.floor(hours / 24)
  const remainHours = Math.floor(hours % 24)
  if (!days) return `${remainHours}小时`
  return `${days}天${remainHours}小时`
}

function statusText(value) {
  const status = String(value || '').toLowerCase()
  if (status.includes('deleted') || status.includes('删除')) return '已删除'
  if (status.includes('paused') || status.includes('pause') || status.includes('暂停')) return '已暂停'
  if (status.includes('queued') || status.includes('pending') || status.includes('排队')) return '排队'
  if (status.includes('complete') || status.includes('达标')) return '已达标'
  if (status.includes('download') || status.includes('下载')) return '下载中'
  return '做种中'
}

function statusColor(value) {
  return { 做种中: 'success', 下载中: 'info', 排队: 'secondary', 已达标: 'primary', 已暂停: 'warning', 已删除: 'grey' }[statusText(value)]
}

const totalSize = computed(() => `${records.value.reduce((total, record) => total + toGb(record.size), 0).toFixed(2)} GB`)
const totalUploaded = computed(() => `${records.value.reduce((total, record) => total + toGb(record.uploaded), 0).toFixed(2)} GB`)
const qualifiedCount = computed(() => records.value.filter(record => statusText(record.status) === '已达标').length)

async function refreshData() {
  loading.value = true
  error.value = ''
  try {
    const response = unwrap(await pluginApi.get(`plugin/Hhanclubrescueseed/download_records`))
    if (!response?.success) throw new Error(response?.message || '获取下载记录失败')
    const data = response.data || {}
    records.value = Array.isArray(data.records) ? data.records : []
    autoDeleteEnabled.value = Boolean(data.auto_delete_enabled)
    emit('action')
  } catch (err) {
    error.value = err.message || '获取下载记录失败'
    records.value = []
    notify('error', error.value)
  } finally {
    loading.value = false
  }
}

async function deleteRecord(record) {
  const title = String(record?.title || '')
  if (!title) return
  deleting.value = title
  try {
    const response = unwrap(await pluginApi.post(`plugin/Hhanclubrescueseed/delete_download_records`, [title]))
    records.value = records.value.filter(item => item.title !== title)
    notify('success', '记录已删除')
    emit('action')
  } catch (err) {
    notify('error', err.message || '删除记录失败')
  } finally {
    deleting.value = ''
  }
}

const adopting = ref(false)

async function adoptTorrents() {
  adopting.value = true
  try {
    const response = unwrap(await pluginApi.post(`plugin/Hhanclubrescueseed/adopt_torrents`))
    if (!response?.success) throw new Error(response?.message || '接管失败')
    const { adopted, total } = response.data || {}
    notify('success', adopted ? `已接管 ${adopted} 个历史种子，共 ${total} 条记录` : `没有需要接管的历史种子（共 ${total} 条记录）`)
    await refreshData()
  } catch (err) {
    notify('error', err.message || '接管失败')
  } finally {
    adopting.value = false
  }
}

const cleaning = ref(false)

async function cleanupStale() {
  cleaning.value = true
  try {
    const response = unwrap(await pluginApi.post(`plugin/Hhanclubrescueseed/cleanup_records`))
    if (!response?.success) throw new Error(response?.message || '清理失败')
    const { removed, total } = response.data || {}
    notify('success', `已清理 ${removed} 条失效记录，剩余 ${total} 条`)
    emit('action')
    await refreshData()
  } catch (err) {
    notify('error', err.message || '清理失败')
  } finally {
    cleaning.value = false
  }
}

function close() {
  emit('close')
}

onMounted(refreshData)
</script>

<template>
  <v-card class="plugin-page">
    <v-card-item>
      <template #prepend><v-icon color="primary">mdi-chart-box-outline</v-icon></template>
      <v-card-title>憨憨保种区</v-card-title>
      <v-card-subtitle>本地下载记录与下载器实时状态</v-card-subtitle>
      <template #append>
        <div class="d-flex align-center ga-1">
          <v-btn icon="mdi-cog-outline" variant="text" aria-label="配置插件" title="配置插件" @click="emit('switch')" />
      <v-btn icon="mdi-tag-plus-outline" variant="text" aria-label="刷新接管" title="刷新接管：把下载器中带标签但无记录的种子入库" :loading="adopting" @click="adoptTorrents" />
      <v-btn icon="mdi-broom" variant="text" aria-label="清理失效记录" title="清理失效记录（下载器中已不存在的）" :loading="cleaning" @click="cleanupStale" />
          <v-btn icon="mdi-refresh" variant="text" aria-label="刷新" title="刷新" @click="refreshData" />
          <v-btn icon="mdi-close" variant="text" aria-label="关闭" @click="close" />
        </div>
      </template>
    </v-card-item>

    <v-card-text>
      <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
      <v-alert v-if="!autoDeleteEnabled" type="info" variant="tonal" class="mb-4">自动清理未启用：磁盘配额清理与卡死清理均不会执行</v-alert>

      <v-row class="stats-row mb-2">
        <v-col cols="12" sm="6" md="3"><v-card class="stat-card" variant="tonal"><div class="stat-label">保种总体积</div><div class="stat-value">{{ totalSize }}</div><div class="stat-meta">当前记录汇总</div></v-card></v-col>
        <v-col cols="12" sm="6" md="3"><v-card class="stat-card" variant="tonal"><div class="stat-label">累计上传量</div><div class="stat-value">{{ totalUploaded }}</div><div class="stat-meta">按下载记录汇总</div></v-card></v-col>
        <v-col cols="12" sm="6" md="3"><v-card class="stat-card" variant="tonal"><div class="stat-label">已达标数</div><div class="stat-value">{{ qualifiedCount }}<small> 条</small></div><div class="stat-meta">达标标签已写入下载器</div></v-card></v-col>
        <v-col cols="12" sm="6" md="3"><v-card class="stat-card" variant="tonal"><div class="stat-label">下载记录数</div><div class="stat-value">{{ records.length }}<small> 条</small></div><div class="stat-meta">本地保存的记录</div></v-card></v-col>
      </v-row>

      <div class="table-heading"><div><h2>下载记录</h2><p>名称、体积和下载时间来自本地记录，状态数据按记录字段展示。得分为推送评分（体积50+需求40+稀缺10，人数热度 20 封顶），旧记录无得分显示 —；下载器中带标签但无本地记录的历史种子会以「发现」合入展示（无删除按钮）。</p></div></div>
      <v-data-table v-if="records.length" height="520" :headers="headers" :items="records" item-value="title" class="records-table" :items-per-page="10">
        <template #item.title="{ item }"><div class="title-cell"><strong>{{ item.title || '-' }}</strong><span v-if="item.zh_title">{{ item.zh_title }}</span></div></template>
        <template #item.size="{ item }">{{ formatSize(item.size) }}</template>
        <template #item.score="{ item }">{{ typeof item.score === 'number' && Number.isFinite(item.score) ? item.score.toFixed(1) : '—' }}</template>
        <template #item.added_on="{ item }">{{ formatAddedOn(item) }}</template>
        <template #item.seeding_time="{ item }">{{ formatSeedingTime(valueOf(item, 'seeding_time', 'seeding_time_hours')) }}</template>
        <template #item.status="{ item }"><v-chip size="small" :color="statusColor(item.status)" label>{{ statusText(item.status) }}</v-chip></template>
        <template #item.progress="{ item }">{{ typeof item.progress === 'number' && Number.isFinite(item.progress) ? `${(item.progress * 100).toFixed(1)}%` : '—' }}</template>
        <template #item.uploaded="{ item }">{{ formatSize(item.uploaded) }}</template>
        <template #item.actions="{ item }"><v-btn v-if="!item.discovered" icon="mdi-delete-outline" size="small" variant="text" color="error" :loading="deleting === item.title" :aria-label="`删除 ${item.title}`" @click="deleteRecord(item)" /></template>
      </v-data-table>
      <v-alert v-else type="info" variant="tonal">暂无下载记录</v-alert>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.plugin-page { max-width: 1280px; margin: 0 auto; }
.stats-row { margin-inline: -6px; }
.stat-card { height: 100%; padding: 16px; border-radius: 10px; }
.stat-label { color: rgba(var(--v-theme-on-surface), .62); font-size: .85rem; }
.stat-value { margin-top: 6px; color: rgb(var(--v-theme-primary)); font-size: 1.35rem; font-weight: 700; }
.stat-value small { font-size: .75rem; font-weight: 500; }
.stat-meta { margin-top: 4px; color: rgba(var(--v-theme-on-surface), .5); font-size: .78rem; }
.table-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 22px 0 12px; }
.table-heading h2 { margin: 0; font-size: 1.2rem; }
.table-heading p { margin: 4px 0 0; color: rgba(var(--v-theme-on-surface), .58); font-size: .86rem; }
.title-cell { display: grid; gap: 3px; max-width: 420px; white-space: normal; }
.title-cell span { color: rgba(var(--v-theme-on-surface), .58); font-size: .8rem; }
.records-table { border: 1px solid rgba(var(--v-theme-on-surface), .12); border-radius: 8px; }
@media (max-width: 600px) { .table-heading { align-items: flex-start; flex-direction: column; } }
</style>
