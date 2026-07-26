<script setup>
import { computed } from 'vue'

const props = defineProps({
  market_prices: { type: Object, default: () => ({}) },
  crops: { type: Object, default: () => ({}) },
  trends: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
})

function priceChange(cropKey) {
  const samples = props.trends?.[cropKey]
  if (!Array.isArray(samples) || samples.length < 2) return null

  const previousSample = samples[samples.length - 2]
  const currentSample = samples[samples.length - 1]
  if (!Array.isArray(previousSample) || !Array.isArray(currentSample)) return null

  const previousPrice = Number(previousSample[1])
  const currentPrice = Number(currentSample[1])
  if (!Number.isFinite(previousPrice) || !Number.isFinite(currentPrice) || previousPrice === 0) return null
  return ((currentPrice - previousPrice) / previousPrice) * 100
}

const rows = computed(() => Object.entries(props.market_prices || {}).map(([cropKey, rawPrice]) => {
  const crop = props.crops?.[cropKey] || {}
  const price = Number(rawPrice)
  const cost = Number(crop.cost)
  const profitRate = Number.isFinite(price) && Number.isFinite(cost) && cost !== 0
    ? ((price - cost) / cost) * 100
    : null
  return {
    cropKey,
    name: crop.name || cropKey,
    price: Number.isFinite(price) ? price : rawPrice,
    cost: Number.isFinite(cost) ? cost : '—',
    profitRate,
    priceChange: priceChange(cropKey),
  }
}))

function formatRate(rate) {
  if (rate === null) return '—'
  return `${rate > 0 ? '+' : ''}${rate.toFixed(2)}%`
}
</script>

<template>
  <v-card flat class="rounded border">
    <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 section-title-bg">
      <v-icon icon="mdi-cash" color="blue" size="small" class="mr-2" />
      <span>菜市场</span>
      <v-spacer />
      <v-progress-circular v-if="loading" indeterminate size="18" width="2" color="success" />
    </v-card-title>

    <v-table v-if="rows.length" density="compact">
      <thead>
        <tr>
          <th>名称</th>
          <th class="text-center">市场价</th>
          <th class="text-center">成本</th>
          <th class="text-center">盈利率</th>
          <th class="text-center">波动幅度</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.cropKey">
          <td>{{ row.name }}</td>
          <td class="text-center font-weight-medium">{{ row.price }}</td>
          <td class="text-center">{{ row.cost }}</td>
          <td
            class="text-center font-weight-medium"
            :class="row.profitRate === null ? 'text-medium-emphasis' : row.profitRate >= 0 ? 'text-success' : 'text-error'"
          >
            {{ formatRate(row.profitRate) }}
          </td>
          <td
            class="text-center font-weight-medium"
            :class="row.priceChange === null ? 'text-medium-emphasis' : row.priceChange > 0 ? 'text-error' : row.priceChange < 0 ? 'text-success' : 'text-medium-emphasis'"
          >
            {{ formatRate(row.priceChange) }}
          </td>
        </tr>
      </tbody>
    </v-table>
    <v-card-text v-else class="text-center text-medium-emphasis py-6">暂无市场价格</v-card-text>
  </v-card>
</template>

<style scoped>
</style>
