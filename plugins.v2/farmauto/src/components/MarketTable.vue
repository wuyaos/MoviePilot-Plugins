<script setup>
import { computed } from 'vue'

const props = defineProps({
  market_prices: { type: Object, default: () => ({}) },
  crops: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
})

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
  }
}))

function formatRate(rate) {
  if (rate === null) return '—'
  return `${rate > 0 ? '+' : ''}${rate.toFixed(2)}%`
}
</script>

<template>
  <v-card flat class="rounded border">
    <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 bg-light-green-lighten-5">
      <span>💰 菜市场</span>
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
          <th class="text-center">波动</th>
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
          <td class="text-center text-medium-emphasis">—</td>
        </tr>
      </tbody>
    </v-table>
    <v-card-text v-else class="text-center text-medium-emphasis py-6">暂无市场价格</v-card-text>
  </v-card>
</template>
