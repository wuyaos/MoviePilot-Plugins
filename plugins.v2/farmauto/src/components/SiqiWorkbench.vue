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

const f = computed(() => props.farm || {})
const bonus = computed(() => f.value.user_bonus ?? '—')
const totalHarvest = computed(() => f.value.user_stats?.total_harvest ?? '—')
const totalSteal = computed(() => f.value.user_steal_gain ?? f.value.user_stats?.total_steal_gain ?? '—')
const farmLike = computed(() => f.value.user_farm_like_total ?? f.value.farm_like_total ?? '—')
const seeds = computed(() => f.value.seeds || [])
const lands = computed(() => f.value.user_lands || [])
const inventory = computed(() => f.value.inventory || [])
const likeMax = computed(() => f.value.like_max ?? 0)
const likeRemaining = computed(() => f.value.like_remaining ?? 0)
const canSteal = computed(() => !f.value.steal_done_today)
const plotSlot = computed(() => f.value.plot_slot || {})
const buySlotAvailable = computed(() => plotSlot.value.available ?? 0)

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
  } catch (e) {
    error.value = e?.message || `${action} 失败`
  } finally {
    actionLoading.value = false
  }
}

function selectSeed(seed) { selectedSeedId.value = seed.seed_id ?? seed.id }
function plantFill() {
  if (!selectedSeedId.value) { error.value = '请先选择种子'; return }
  doAction('plant', { seed_id: selectedSeedId.value })
}
function steal() { doAction('steal') }
function like() { doAction('like') }
function harvestPlot(land) { doAction('harvest', { land_id: land.land_id, plot_index: land.plot_index }) }
function harvestAll() { doAction('harvest_all') }
function sell(item) { doAction('sell', { seed_id: item.seed_id, quantity: item.quantity }) }
function sellAll() {
  if (!inventory.value.length) { error.value = '背包为空'; return }
  for (const item of inventory.value) doAction('sell', { seed_id: item.seed_id, quantity: item.quantity })
}
function buySlot() { doAction('buy_plot_slot') }
function refresh() { emit('refresh') }
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
              <v-btn color="green" size="small" variant="flat" :disabled="!selectedSeedId" @click="plantFill">一键种植</v-btn>
            </v-card-title>
            <v-card-text class="pa-3">
              <v-row dense>
                <v-col v-for="seed in seeds" :key="seed.seed_id ?? seed.id" cols="6" sm="4">
                  <v-card flat variant="outlined" :class="{ 'border-success': selectedSeedId === (seed.seed_id ?? seed.id) }" class="pa-2 cursor-pointer" @click="selectSeed(seed)">
                    <div class="text-body-2 font-weight-bold">{{ seed.name }}</div>
                    <div class="text-caption text-grey">成本 {{ seed.cost }} → 收益 {{ seed.base_reward }}</div>
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
                    <v-btn :color="canSteal ? 'red' : 'grey'" size="small" variant="flat" :disabled="!canSteal" @click="steal">{{ canSteal ? '去偷菜' : '今日已偷' }}</v-btn>
                  </div>
                </v-col>
                <v-col cols="12">
                  <div class="d-flex align-center ga-2 pa-2 rounded border">
                    <v-icon icon="mdi-thumb-up" color="pink" />
                    <div class="flex-grow-1">
                      <div class="text-body-2 font-weight-bold">点赞</div>
                      <div class="text-caption text-grey">剩余 {{ likeRemaining }}/{{ likeMax }}</div>
                    </div>
                    <v-btn color="pink" size="small" variant="flat" :disabled="likeRemaining <= 0" @click="like">去点赞</v-btn>
                  </div>
                </v-col>
                <v-col cols="12">
                  <div class="d-flex align-center ga-2 pa-2 rounded border">
                    <v-icon icon="mdi-map-marker" color="deep-purple" />
                    <div class="flex-grow-1">
                      <div class="text-body-2 font-weight-bold">扩地</div>
                      <div class="text-caption text-grey">可购买 {{ buySlotAvailable }} 个坑位</div>
                    </div>
                    <v-btn color="deep-purple" size="small" variant="flat" :disabled="buySlotAvailable <= 0" @click="buySlot">购买</v-btn>
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
          <v-btn color="orange" size="small" variant="flat" prepend-icon="mdi-basket" @click="harvestAll">一键收获</v-btn>
        </v-card-title>
        <v-card-text class="pa-3">
          <div v-for="land in lands" :key="land.land_id" class="mb-3">
            <div class="text-body-2 font-weight-bold mb-1">
              {{ land.name || `地块 ${land.land_id}` }}
              <span class="text-caption text-grey">（坑位：{{ land.effective_plot_count ?? land.plot_count ?? 0 }}）</span>
            </div>
            <v-row dense>
              <v-col cols="6" sm="4" md="3">
                <v-card flat variant="outlined" :color="land.is_ready ? 'orange' : 'grey'" class="pa-2 text-center cursor-pointer" @click="harvestPlot(land)">
                  <div class="text-caption">{{ land.seed_name || land.seed_id || '空地' }}</div>
                  <div class="text-caption" :class="land.is_ready ? 'text-orange' : 'text-grey'">
                    {{ land.is_ready ? '可收获' : (land.harvest_time ? `剩余 ${land.harvest_time}` : '空地') }}
                  </div>
                  <v-btn v-if="land.is_ready" size="x-small" color="orange" variant="flat" class="mt-1">收获</v-btn>
                </v-card>
              </v-col>
            </v-row>
          </div>
          <div v-if="!lands.length" class="text-center text-grey pa-4">暂无菜地数据</div>
        </v-card-text>
      </v-card>

      <!-- 背包 -->
      <v-card flat class="rounded border mb-3">
        <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 bg-amber-lighten-5">
          <v-icon icon="mdi-bag-personal" color="amber" size="small" class="mr-2" />收获背包
          <v-spacer />
          <v-btn color="orange" size="small" variant="flat" prepend-icon="mdi-cash" :disabled="!inventory.length" @click="sellAll">一键出售</v-btn>
        </v-card-title>
        <v-card-text class="pa-3">
          <v-table v-if="inventory.length" density="compact">
            <thead>
              <tr><th>物品</th><th>数量</th><th>单价</th><th>总价</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="item in inventory" :key="item.seed_id">
                <td>{{ item.name || `作物 ${item.seed_id}` }}</td>
                <td>{{ item.quantity }}</td>
                <td>{{ item.unit_reward }}</td>
                <td>{{ (Number(item.quantity || 0) * Number(item.unit_reward || 0)) }}</td>
                <td><v-btn size="x-small" color="orange" variant="flat" @click="sell(item)">出售</v-btn></td>
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
    </v-card-text>
  </v-card>
</template>

<style scoped>
.cursor-pointer { cursor: pointer; }
.h-100 { height: 100%; }
</style>
