<script setup>
import { computed, ref } from 'vue'
import HistoryTable from './HistoryTable.vue'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'FarmAuto' },
  farm: { type: Object, default: () => ({}) },
  history: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  showSwitch: { type: Boolean, default: false },
  showClose: { type: Boolean, default: false },
})

const emit = defineEmits(['action', 'switch', 'close', 'refresh'])

const actionLoading = ref(false)
const error = ref('')
const success = ref('')
const selectedSeedId = ref('')
const stealDialog = ref(false)
const likeDialog = ref(false)
const visitDialog = ref(false)
const sellAllDialog = ref(false)
const stealTargets = ref([])
const likeUsernames = ref('')
const visitUsername = ref('')
const visitResult = ref(null)

const f = computed(() => props.farm || {})
const bonus = computed(() => f.value.user_bonus ?? '—')
const totalHarvest = computed(() => f.value.user_stats?.total_harvest ?? '—')
const totalSteal = computed(() => f.value.user_steal_gain ?? f.value.user_stats?.total_steal_gain ?? '—')
const farmLike = computed(() => f.value.user_farm_like_total ?? f.value.farm_like_total ?? '—')
const seeds = computed(() => f.value.seeds || [])
const lands = computed(() => f.value.user_lands || [])
const landsGrouped = computed(() => {
  const grouped = new Map()
  for (const plot of lands.value) {
    const key = String(plot.land_id)
    const current = grouped.get(key)
    if (!current) {
      grouped.set(key, {
        land_id: plot.land_id,
        name: plot.name,
        effective_plot_count: plot.effective_plot_count,
        plot_count: plot.plot_count,
      })
      continue
    }
    current.name ||= plot.name
    current.effective_plot_count = Math.max(
      Number(current.effective_plot_count || 0),
      Number(plot.effective_plot_count || 0),
    )
    current.plot_count = Math.max(Number(current.plot_count || 0), Number(plot.plot_count || 0))
  }
  return [...grouped.values()]
})
const inventory = computed(() => f.value.inventory || [])
const likeMax = computed(() => f.value.like_max ?? 0)
const likeRemaining = computed(() => f.value.like_remaining ?? 0)
const canSteal = computed(() => !f.value.steal_done_today)
const plotSlot = computed(() => f.value.plot_slot || {})
const buySlotAvailable = computed(() => plotSlot.value.available === true)
const failedStageIcons = ref(new Set())
const inventoryTotalValue = computed(() => inventory.value.reduce(
  (total, item) => total + Number(item.quantity || 0) * Number(item.unit_reward || 0),
  0,
))

function seedEmoji(name) {
  const emojiByName = {
    萝卜: '🥕',
    西红柿: '🍅',
    玉米: '🌽',
    茄子: '🍆',
    蘑菇: '🍄',
    樱桃: '🍒',
    小麦: '🌾',
    花生: '🥜',
    土豆: '🥔',
    鸡: '🐔',
    猪: '🐷',
    牛: '🐂',
    羊: '🐑',
  }
  return emojiByName[name] || '🌱'
}

function seedNameById(seedId) {
  return seeds.value.find(seed => String(seed.seed_id ?? seed.id) === String(seedId))?.name
}

function apiBase() { return `plugin/${props.pluginId}` }

async function request(method, path, body) {
  const m = props.api?.[method.toLowerCase()]
  if (typeof m === 'function') {
    return method === 'GET' ? m.call(props.api, path) : m.call(props.api, path, body || {})
  }
  throw new Error('宿主 API 不可用')
}

function unwrap(r) {
  const p = r && Object.prototype.hasOwnProperty.call(r, 'success') ? r : (r?.data ?? r)
  if (p?.success === false) throw new Error(p.message || '请求未成功')
  if (p && Object.prototype.hasOwnProperty.call(p, 'success')) return p.data ?? {}
  return p ?? {}
}

async function doAction(action, params = {}) {
  actionLoading.value = true
  error.value = ''
  success.value = ''
  try {
    const r = unwrap(await request('POST', `${apiBase()}/site/siqi/action`, { action, ...params }))
    success.value = r.message || `${action} 操作成功`
    emit('action', { action, result: r })
    return r
  } catch (e) {
    error.value = e?.message || `${action} 失败`
  } finally {
    actionLoading.value = false
  }
  return null
}

function selectSeed(seed) { selectedSeedId.value = seed.seed_id ?? seed.id }
function plantFill() {
  if (!selectedSeedId.value) { error.value = '请先选择种子'; return }
  doAction('plant', { seed_id: selectedSeedId.value })
}
async function openStealDialog() {
  stealDialog.value = true
  const result = await doAction('get_steal_targets')
  stealTargets.value = Array.isArray(result?.targets) ? result.targets : []
}
async function steal(target, plot) {
  const result = await doAction('steal', {
    target_id: target.target_id ?? target.victim_id ?? target.id,
    land_id: plot.land_id,
    plot_index: plot.plot_index,
  })
  if (result?.success) {
    stealDialog.value = false
    emit('refresh')
  }
}
async function openLikeDialog() {
  likeDialog.value = true
  if (!likeUsernames.value.trim()) await loadLikeTargets()
}
async function loadLikeTargets() {
  const result = await doAction('get_like_targets')
  const names = Array.isArray(result?.targets) ? result.targets : []
  likeUsernames.value = names.map(item => (
    typeof item === 'string' ? item : item.username ?? item.name ?? item.target_id ?? ''
  )).filter(Boolean).join(', ')
}
async function like() {
  const usernames = likeUsernames.value.split(/[，,\n]+/).map(item => item.trim()).filter(Boolean)
  if (!usernames.length) { error.value = '请输入至少一个用户名'; return }
  const result = await doAction('like', { usernames: usernames.join('\n') })
  if (result?.success) {
    likeDialog.value = false
    emit('refresh')
  }
}
async function visit() {
  const username = visitUsername.value.trim()
  if (!username) { error.value = '请输入用户名'; return }
  const result = await doAction('visit', { username })
  if (result?.success) visitResult.value = result
}
function harvestPlot(plot) { doAction('harvest', { land_id: plot.land_id, plot_index: plot.plot_index }) }
function harvestAll() { doAction('harvest_all') }
function plant(plot) {
  if (!selectedSeedId.value) { error.value = '请先选择种子'; return }
  doAction('plant', {
    land_id: plot.land_id,
    plot_index: plot.plot_index,
    seed_id: selectedSeedId.value,
  })
}
function buyPlotSlot(landId) { doAction('buy_plot_slot', { land_id: landId }) }
function sell(item) { doAction('sell', { seed_id: item.seed_id, quantity: item.quantity }) }
async function sellAll() {
  if (!inventory.value.length) { error.value = '背包为空'; return }
  sellAllDialog.value = false
  for (const item of inventory.value) {
    await doAction('sell', { seed_id: item.seed_id, quantity: item.quantity })
  }
  emit('refresh')
}
function buySlot() {
  const nextSlotCosts = plotSlot.value.next_slot_cost_by_land || {}
  const landId = Object.keys(nextSlotCosts).find(key => nextSlotCosts[key] != null)
  if (landId != null) buyPlotSlot(landId)
}
function refresh() { emit('refresh') }

function nowSec() {
  return Date.now() / 1000
}

function valueForLand(values, landId) {
  return values?.[landId] ?? values?.[String(landId)]
}

function effectivePlotCount(land) {
  const configured = valueForLand(plotSlot.value.effective_plot_counts, land.land_id)
  return Number(configured ?? land.effective_plot_count ?? land.plot_count ?? 0)
}

function maxPlotCount(land) {
  const maxPerLand = Number(plotSlot.value.max_per_land || 0)
  return maxPerLand > 0 ? maxPerLand : Number(land.plot_count ?? 0)
}

function landPlotCountLabel(land) {
  return `${effectivePlotCount(land)}/${maxPlotCount(land)}`
}

function plotsForLand(land) {
  const effective = effectivePlotCount(land)
  const configuredMax = Number(plotSlot.value.max_per_land || 0)
  const max = configuredMax > 0 ? configuredMax : effective
  const nextSlotCost = valueForLand(plotSlot.value.next_slot_cost_by_land, land.land_id)
  const plots = []

  for (let plotIndex = 0; plotIndex < max; plotIndex += 1) {
    if (plotIndex < effective) {
      const source = lands.value.find(plot => (
        String(plot.land_id) === String(land.land_id)
        && Number(plot.plot_index) === plotIndex
      ))
      const plot = source || { land_id: land.land_id, plot_index: plotIndex }
      const hasSeed = plot.seed_id != null && Number(plot.seed_id) !== 0
      const seed = hasSeed
        ? (plot.seed || seeds.value.find(item => String(item.seed_id ?? item.id) === String(plot.seed_id)))
        : null
      plots.push({ ...plot, seed, state: hasSeed ? 'planted' : 'empty' })
    } else if (nextSlotCost != null) {
      plots.push({
        land_id: land.land_id,
        plot_index: plotIndex,
        state: 'buyable',
        cost: nextSlotCost,
      })
    } else {
      plots.push({ land_id: land.land_id, plot_index: plotIndex, state: 'locked' })
    }
  }
  return plots
}

function isPlotReady(plot) {
  const harvestAt = Number(plot?.harvest_time)
  return plot?.is_ready === true || (harvestAt > 0 && harvestAt <= nowSec())
}

function formatRemain(plot) {
  if (isPlotReady(plot) || !plot?.harvest_time) return ''
  const diff = Math.max(0, Number(plot.harvest_time) - nowSec())
  const days = Math.floor(diff / 86400)
  const hours = Math.floor((diff % 86400) / 3600)
  const minutes = Math.floor((diff % 3600) / 60)
  if (days > 0) return `${days}天${hours}时${minutes}分`
  return hours > 0 ? `${hours}时${minutes}分` : `${minutes}分`
}

function growSeconds(growTime) {
  if (typeof growTime === 'number') return growTime
  const text = String(growTime || '')
  const days = Number(text.match(/([\d.]+)\s*天/)?.[1] || 0)
  const hours = Number(text.match(/([\d.]+)\s*(?:小时|时)/)?.[1] || 0)
  const minutes = Number(text.match(/([\d.]+)\s*分/)?.[1] || 0)
  const seconds = Number(text.match(/([\d.]+)\s*秒/)?.[1] || 0)
  return days * 86400 + hours * 3600 + minutes * 60 + seconds
}

function plotProgress(plot) {
  if (isPlotReady(plot)) return 100
  const plantedAt = Number(plot?.plant_time)
  const duration = growSeconds(plot?.seed?.grow_time)
  if (!plantedAt || !duration) return null
  const elapsed = nowSec() - plantedAt
  return Math.max(0, Math.min(100, (elapsed / duration) * 100))
}

function plotStageIcon(plot) {
  const icons = plot?.seed?.stage_icons
  if (!icons || typeof icons !== 'object') return ''
  const progress = plotProgress(plot) ?? 0
  const phase = isPlotReady(plot) ? 'mature' : (progress < 50 ? 'seedling' : 'growth')
  return icons[phase] || ''
}

function plotKey(plot) {
  return `${plot.land_id}-${plot.plot_index}-${plotStageIcon(plot)}`
}

function hasFailedStageIcon(plot) {
  return failedStageIcons.value.has(plotKey(plot))
}

function markStageIconFailed(plot) {
  failedStageIcons.value = new Set([...failedStageIcons.value, plotKey(plot)])
}

function assetUrl(path) {
  if (!path) return ''
  if (/^(?:https?:|data:)/.test(path)) return path
  const baseUrl = String(f.value.base_url || 'https://si-qi.xyz').replace(/\/$/, '')
  return `${baseUrl}/${String(path).replace(/^\//, '')}`
}

function stealPlots(target) {
  return (target.plots || target.victim_plots || target.user_lands || []).filter(plot => (
    plot?.seed_id && (Number(plot.is_ready) === 1 || Number(plot.harvest_time || 0) <= Date.now() / 1000)
  ))
}

function handlePlotClick(plot) {
  if (plot.state === 'buyable') buyPlotSlot(plot.land_id)
  else if (plot.state === 'empty') plant(plot)
  else if (plot.state === 'planted' && isPlotReady(plot)) harvestPlot(plot)
}
</script>

<template>
  <v-card flat class="siqi-workbench rounded border text-body-2">
    <v-card-title class="text-subtitle-1 d-flex align-center ga-2 px-3 py-2 bg-gradient-farm text-white">
      <v-icon icon="mdi-sprout" color="white" size="small" />
      <span class="text-white">思齐农场</span>
      <span class="text-caption text-white opacity-70">管理菜地、背包、偷菜与农场互动</span>
    </v-card-title>

    <v-progress-linear v-if="actionLoading" indeterminate color="success" height="2" />

    <v-card-text class="pa-4">
      <v-alert v-if="error" type="error" variant="tonal" closable class="mb-3" @click:close="error = ''">{{ error }}</v-alert>
      <v-alert v-if="success" type="success" variant="tonal" closable class="mb-3" @click:close="success = ''">{{ success }}</v-alert>

      <!-- 统计卡 -->
      <v-row dense class="mb-3">
        <v-col cols="6" md="3">
          <v-card flat variant="tonal" color="orange" class="pa-3 text-center">
            <v-icon icon="mdi-auto-fix" color="orange" class="mb-1" />
            <div class="text-caption">魔力值</div>
            <div class="text-h6 font-weight-bold">{{ bonus }}</div>
          </v-card>
        </v-col>
        <v-col cols="6" md="3">
          <v-card flat variant="tonal" color="green" class="pa-3 text-center">
            <v-icon icon="mdi-sprout" color="green" class="mb-1" />
            <div class="text-caption">总种植收获</div>
            <div class="text-h6 font-weight-bold">{{ totalHarvest }}</div>
          </v-card>
        </v-col>
        <v-col cols="6" md="3">
          <v-card flat variant="tonal" color="red" class="pa-3 text-center">
            <v-icon icon="mdi-incognito" color="red" class="mb-1" />
            <div class="text-caption">总偷菜收获</div>
            <div class="text-h6 font-weight-bold">{{ totalSteal }}</div>
          </v-card>
        </v-col>
        <v-col cols="6" md="3">
          <v-card flat variant="tonal" color="blue" class="pa-3 text-center">
            <v-icon icon="mdi-thumb-up" color="blue" class="mb-1" />
            <div class="text-caption">农场被点赞</div>
            <div class="text-h6 font-weight-bold">{{ farmLike }}</div>
          </v-card>
        </v-col>
      </v-row>

      <!-- 种子商店 + 农场互动 -->
      <v-row dense class="mb-3">
        <v-col cols="12" md="6">
          <v-card flat class="rounded border h-100">
            <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 bg-green-lighten-5">
              <v-icon icon="mdi-seed" color="green" size="small" class="mr-2" />种子商店
              <v-spacer />
              <v-btn color="success" size="small" variant="flat" :disabled="!selectedSeedId" @click="plantFill">一键种植</v-btn>
            </v-card-title>
            <v-card-text class="pa-3">
              <v-row dense>
                <v-col v-for="seed in seeds" :key="seed.seed_id ?? seed.id" cols="6" sm="4">
                  <v-card flat variant="outlined" :class="{ 'border-success': selectedSeedId === (seed.seed_id ?? seed.id) }" class="pa-2 cursor-pointer" @click="selectSeed(seed)">
                    <div class="d-flex align-center ga-2">
                      <span class="text-h5" aria-hidden="true">{{ seedEmoji(seed.name) }}</span>
                      <div class="flex-grow-1">
                        <div class="text-body-2 font-weight-bold">{{ seed.name }}</div>
                        <div class="text-caption text-grey">{{ seed.cost }} → {{ seed.base_reward }}</div>
                      </div>
                    </div>
                  </v-card>
                </v-col>
              </v-row>
              <div v-if="!seeds.length" class="text-center text-grey pa-4">暂无种子数据</div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="6">
          <v-card flat class="rounded border h-100">
            <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 bg-purple-lighten-5">
              <v-icon icon="mdi-home-group" color="deep-purple" size="small" class="mr-2" />农场互动
              <span class="text-caption text-grey ml-2">偷菜、点赞与参观</span>
            </v-card-title>
            <v-card-text class="pa-3">
              <v-row dense>
                <v-col cols="12">
                  <div class="d-flex align-center ga-2 pa-2 rounded border">
                    <v-icon icon="mdi-incognito" color="red" />
                    <div class="flex-grow-1">
                      <div class="text-body-2 font-weight-bold">偷菜</div>
                      <div class="text-caption text-grey">每日一次，自动寻找可偷作物</div>
                    </div>
                    <v-btn color="red" size="small" variant="flat" :disabled="!canSteal" @click="openStealDialog">{{ canSteal ? '去偷菜' : '今日已偷' }}</v-btn>
                  </div>
                </v-col>
                <v-col cols="12">
                  <div class="d-flex align-center ga-2 pa-2 rounded border">
                    <v-icon icon="mdi-thumb-up" color="pink" />
                    <div class="flex-grow-1">
                      <div class="text-body-2 font-weight-bold">点赞</div>
                      <div class="text-caption text-grey">剩余 {{ likeRemaining }}/{{ likeMax }}</div>
                    </div>
                    <v-btn color="pink" size="small" variant="flat" :disabled="likeRemaining <= 0" @click="openLikeDialog">去点赞</v-btn>
                  </div>
                </v-col>
                <v-col cols="12">
                  <div class="d-flex align-center ga-2 pa-2 rounded border">
                    <v-icon icon="mdi-account-search" color="blue" />
                    <div class="flex-grow-1">
                      <div class="text-body-2 font-weight-bold">参观农场</div>
                      <div class="text-caption text-grey">按用户名访问好友农场</div>
                    </div>
                    <v-btn color="blue" size="small" variant="flat" @click="visitDialog = true">去参观</v-btn>
                  </div>
                </v-col>
                <v-col cols="12">
                  <div class="d-flex align-center ga-2 pa-2 rounded border">
                    <v-icon icon="mdi-map-marker" color="deep-purple" />
                    <div class="flex-grow-1">
                      <div class="text-body-2 font-weight-bold">扩地</div>
                      <div class="text-caption text-grey">{{ buySlotAvailable ? '可购买坑位' : '暂无可购买坑位' }}</div>
                    </div>
                    <v-btn color="deep-purple" size="small" variant="flat" :disabled="!buySlotAvailable" @click="buySlot">扩地</v-btn>
                  </div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- 菜地 -->
      <v-card flat class="rounded border mb-3">
        <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 bg-blue-lighten-5">
          <v-icon icon="mdi-farm" color="blue" size="small" class="mr-2" />菜地
          <v-spacer />
          <v-btn color="success" size="small" variant="flat" prepend-icon="mdi-basket" @click="harvestAll">一键收获</v-btn>
        </v-card-title>
        <v-card-text class="pa-3">
          <section v-for="land in landsGrouped" :key="land.land_id" class="mb-4">
            <div class="d-flex align-center ga-2 mb-2">
              <div class="text-body-2 font-weight-bold">{{ land.name || `地块 ${land.land_id}` }}</div>
              <v-chip size="x-small" color="green" variant="tonal">
                {{ landPlotCountLabel(land) }} 坑位
              </v-chip>
            </div>
            <div class="plot-grid">
              <v-card
                v-for="plot in plotsForLand(land)"
                :key="`${plot.land_id}-${plot.plot_index}`"
                flat
                variant="outlined"
                class="plot-card pa-3 text-center h-100"
                :class="{ 'cursor-pointer': plot.state !== 'locked' && (plot.state !== 'planted' || isPlotReady(plot)) }"
                :color="isPlotReady(plot) ? 'orange' : (plot.state === 'buyable' ? 'deep-purple' : 'grey')"
                @click="handlePlotClick(plot)"
              >
                <template v-if="plot.state === 'locked'">
                  <div class="text-h5 mb-1" aria-hidden="true">🔒</div>
                  <div class="text-caption text-grey">未解锁</div>
                </template>
                <template v-else-if="plot.state === 'buyable'">
                  <div class="text-h5 mb-1" aria-hidden="true">➕</div>
                  <div class="text-caption font-weight-bold">购买 {{ plot.cost }}</div>
                </template>
                <template v-else-if="plot.seed">
                  <img
                    v-if="plotStageIcon(plot) && !hasFailedStageIcon(plot)"
                    :src="assetUrl(plotStageIcon(plot))"
                    :alt="`${plot.seed.name}阶段图`"
                    class="plot-stage-image mb-1"
                    @error="markStageIconFailed(plot)"
                  >
                  <div v-else class="plot-emoji mb-1" aria-hidden="true">{{ plot.seed.icon || seedEmoji(plot.seed.name) }}</div>
                  <div class="text-caption font-weight-bold">{{ plot.seed.name }}</div>
                  <div class="text-caption" :class="isPlotReady(plot) ? 'text-orange' : 'text-grey'">
                    {{ isPlotReady(plot) ? '可收获' : `成长中 ${formatRemain(plot)}` }}
                  </div>
                  <v-progress-linear
                    v-if="plotProgress(plot) !== null"
                    :model-value="plotProgress(plot)"
                    color="success"
                    height="5"
                    rounded
                    class="mt-2"
                  />
                </template>
                <template v-else>
                  <div class="text-h5 mb-1" aria-hidden="true">🌱</div>
                  <div class="text-caption font-weight-bold">空地</div>
                  <div class="text-caption text-grey">点击种植</div>
                </template>
              </v-card>
            </div>
          </section>
          <div v-if="!landsGrouped.length" class="text-center text-grey pa-4">暂无菜地数据</div>
        </v-card-text>
      </v-card>

      <!-- 背包 -->
      <v-card flat class="rounded border mb-3">
        <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 bg-amber-lighten-5">
          <v-icon icon="mdi-bag-personal" color="amber" size="small" class="mr-2" />收获背包
          <v-spacer />
          <v-btn color="orange" size="small" variant="flat" prepend-icon="mdi-cash" :disabled="!inventory.length" @click="sellAllDialog = true">一键出售</v-btn>
        </v-card-title>
        <v-card-text class="pa-3">
          <v-table v-if="inventory.length" density="compact">
            <thead>
              <tr><th>物品</th><th>数量</th><th>单价</th><th>总价</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="item in inventory" :key="item.seed_id">
                <td><span class="mr-1" aria-hidden="true">{{ seedEmoji(item.name || seedNameById(item.seed_id)) }}</span>{{ item.name || `作物 ${item.seed_id}` }}</td>
                <td>{{ item.quantity }}</td>
                <td>{{ item.unit_reward }}</td>
                <td>{{ (Number(item.quantity || 0) * Number(item.unit_reward || 0)) }}</td>
                <td><v-btn size="small" color="orange" variant="flat" @click="sell(item)">出售</v-btn></td>
              </tr>
            </tbody>
          </v-table>
          <div v-else class="text-center text-grey pa-4">
            <v-icon icon="mdi-bag-personal-outline" size="40" class="mb-2 opacity-50" />
            <div>背包空空如也</div>
          </div>
        </v-card-text>
      </v-card>

      <!-- 执行记录 -->
      <HistoryTable :history="history" />

      <v-dialog v-model="stealDialog" max-width="720">
        <v-card>
          <v-card-title class="d-flex align-center">偷菜目标<v-spacer /><v-btn icon="mdi-close" variant="text" @click="stealDialog = false" /></v-card-title>
          <v-card-text>
            <v-progress-linear v-if="actionLoading" indeterminate color="red" class="mb-3" />
            <v-card v-for="target in stealTargets" :key="target.target_id ?? target.victim_id" variant="outlined" class="mb-3">
              <v-card-title class="text-subtitle-2">{{ target.name || target.victim_name || `农场 ${target.target_id ?? target.victim_id}` }}</v-card-title>
              <v-card-text>
                <div v-if="stealPlots(target).length" class="d-flex flex-wrap ga-2">
                  <v-btn
                    v-for="plot in stealPlots(target)"
                    :key="`${plot.land_id}-${plot.plot_index}`"
                    color="red"
                    variant="tonal"
                    :disabled="actionLoading"
                    @click="steal(target, plot)"
                  >
                    偷取 {{ plot.seed_name || seedNameById(plot.seed_id) || `作物 ${plot.seed_id}` }}（地 {{ plot.land_id }}-{{ Number(plot.plot_index) + 1 }}）
                  </v-btn>
                </div>
                <div v-else class="text-grey">暂无成熟作物</div>
              </v-card-text>
            </v-card>
            <div v-if="!actionLoading && !stealTargets.length" class="text-center text-grey pa-4">暂无可偷菜目标</div>
          </v-card-text>
        </v-card>
      </v-dialog>

      <v-dialog v-model="likeDialog" max-width="560">
        <v-card>
          <v-card-title>批量点赞</v-card-title>
          <v-card-text>
            <div class="text-caption text-grey mb-2">剩余 {{ likeRemaining }}/{{ likeMax }}</div>
            <v-textarea v-model="likeUsernames" label="用户名（逗号或换行分隔）" rows="5" variant="outlined" />
          </v-card-text>
          <v-card-actions>
            <v-btn variant="tonal" :loading="actionLoading" @click="loadLikeTargets">随机填充</v-btn>
            <v-spacer />
            <v-btn variant="text" @click="likeDialog = false">取消</v-btn>
            <v-btn color="pink" variant="flat" :loading="actionLoading" @click="like">一键点赞</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <v-dialog v-model="visitDialog" max-width="640">
        <v-card>
          <v-card-title>参观农场</v-card-title>
          <v-card-text>
            <div class="d-flex ga-2 align-start">
              <v-text-field v-model="visitUsername" label="用户名" variant="outlined" @keyup.enter="visit" />
              <v-btn color="blue" variant="flat" :loading="actionLoading" @click="visit">访问</v-btn>
            </div>
            <v-card v-if="visitResult" variant="tonal" color="green" class="mt-2">
              <v-card-title class="text-subtitle-2">{{ visitResult.target_desc_name || visitResult.target_name || visitResult.request_username || visitUsername }} 的农场</v-card-title>
              <v-card-text>
                <div>{{ visitResult.message || visitResult.msg || '访问成功' }}</div>
                <div v-if="visitResult.user_bonus != null">魔力值：{{ visitResult.user_bonus }}</div>
                <div v-if="Array.isArray(visitResult.user_lands)">菜地坑位：{{ visitResult.user_lands.length }}</div>
              </v-card-text>
            </v-card>
          </v-card-text>
          <v-card-actions><v-spacer /><v-btn variant="text" @click="visitDialog = false">关闭</v-btn></v-card-actions>
        </v-card>
      </v-dialog>

      <v-dialog v-model="sellAllDialog" max-width="440">
        <v-card>
          <v-card-title>确认出售</v-card-title>
          <v-card-text>确定出售背包中的 {{ inventory.length }} 类作物？总价值 {{ inventoryTotalValue }} 魔力。</v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="sellAllDialog = false">取消</v-btn>
            <v-btn color="orange" variant="flat" :loading="actionLoading" @click="sellAll">确认出售</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.cursor-pointer { cursor: pointer; }
.h-100 { height: 100%; }
.plot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
}
.plot-card { min-height: 116px; }
.plot-emoji { font-size: 2rem; line-height: 1.2; }
.plot-stage-image { width: 42px; height: 42px; object-fit: contain; }
</style>
