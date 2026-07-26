<script setup>
import { computed } from 'vue'

const props = defineProps({
  history: { type: Array, default: () => [] },
  currency: { type: String, default: '' },
})

const actionMeta = {
  harvest: { icon: '🌾', text: '收获' },
  plant: { icon: '🌱', text: '种植' },
  sell: { icon: '💰', text: '出售' },
  harvest_all: { icon: '🧺', text: '一键收获' },
  steal: { icon: '🥷', text: '偷菜' },
  like: { icon: '👍', text: '点赞' },
  buy_slot: { icon: '🏗', text: '扩地' },
}

const rows = computed(() => (Array.isArray(props.history) ? props.history : []).slice(-20).reverse())

function getActionMeta(action) {
  return actionMeta[action] || { icon: '📋', text: action || '操作' }
}

function formatTime(value) {
  if (value == null || value === '') return '—'
  if (typeof value === 'string' && /^\d{1,2}:\d{2}(?::\d{2})?$/.test(value)) {
    return value.slice(0, 5)
  }

  const numericValue = Number(value)
  const date = Number.isFinite(numericValue)
    ? new Date(numericValue < 1e12 ? numericValue * 1000 : numericValue)
    : new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function profitValue(profit) {
  const value = Number(profit)
  return Number.isFinite(value) ? value : 0
}

function formatProfit(profit) {
  const value = profitValue(profit)
  if (!value) return ''
  const sign = value > 0 ? '+' : ''
  const unit = props.currency || '魔力'
  return `${unit} ${sign}${value}`
}
</script>

<template>
  <v-card flat class="rounded border h-100">
    <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 section-title-bg">
      <v-icon icon="mdi-history" color="grey" size="small" class="mr-2" />
      执行记录
    </v-card-title>

    <v-table v-if="rows.length" density="compact">
      <thead>
        <tr>
          <th>时间</th>
          <th>操作</th>
          <th class="text-end">费用</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(item, index) in rows"
          :key="`${item.time}-${item.action}-${item.target}-${index}`"
          :class="{ 'failed-row': item.success === false }"
        >
          <td class="text-no-wrap">{{ formatTime(item.time) }}</td>
          <td>
            <span class="mr-1" aria-hidden="true">{{ getActionMeta(item.action).icon }}</span>
            <span>{{ getActionMeta(item.action).text }}</span>
            <span v-if="item.target"> {{ item.target }}</span>
            <span v-if="item.success === false && item.message" class="failure-message"> — {{ item.message }}</span>
          </td>
          <td
            class="text-end text-no-wrap profit"
            :class="profitValue(item.profit) > 0 ? 'text-success' : 'text-error'"
          >
            {{ formatProfit(item.profit) }}
          </td>
        </tr>
      </tbody>
    </v-table>
    <v-card-text v-else class="text-center text-medium-emphasis py-6">暂无记录</v-card-text>
  </v-card>
</template>

<style scoped>
.section-title-bg {
  background-color: rgba(var(--v-theme-on-surface), 0.06) !important;
}

.text-subtitle-2 {
  font-size: 0.9rem !important;
  font-weight: 500 !important;
}

.failed-row td,
.failed-row .profit {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)) !important;
}

.failure-message {
  font-size: 0.75rem;
}

@media (prefers-color-scheme: dark) {
  .section-title-bg {
    background-color: rgba(var(--v-theme-on-surface), 0.06) !important;
  }
}
</style>
