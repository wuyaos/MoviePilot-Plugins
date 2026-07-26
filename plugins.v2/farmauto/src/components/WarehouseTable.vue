<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  warehouse: { type: Array, default: () => [] },
  crops: { type: Object, default: () => ({}) },
  currency: { type: String, default: '' },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['sell', 'sell-all'])
const sellAllDialog = ref(false)
const items = computed(() => Array.isArray(props.warehouse) ? props.warehouse : [])
const estimatedTotal = computed(() => items.value.reduce((total, item) => {
  const unitPrice = numericValue(item.unit_price)
  const quantity = numericValue(item.quantity)
  return unitPrice !== null && quantity !== null
    ? total + unitPrice * quantity
    : total
}, 0))

function itemName(item) {
  return item.name || props.crops[item.crop_key]?.name || item.crop_key || '未知物品'
}

function expiryState(item) {
  const minutes = Number(item.expire_minutes)
  if (!Number.isFinite(minutes)) return 'normal'
  if (minutes <= 0) return 'expired'
  return minutes <= 120 ? 'expiring' : 'normal'
}

function expiryText(item) {
  if (expiryState(item) === 'expired') return item.expire_raw || item.expire || '已过期'
  return item.expire_raw || item.expire || (Number.isFinite(Number(item.expire_minutes)) ? `${item.expire_minutes} 分钟` : '—')
}

function numericValue(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function formatPrice(value) {
  return numericValue(value) ?? '—'
}

function itemTotal(item) {
  const totalPrice = numericValue(item.total_price)
  if (totalPrice !== null) return totalPrice
  const unitPrice = numericValue(item.unit_price)
  const quantity = numericValue(item.quantity)
  return unitPrice !== null && quantity !== null ? unitPrice * quantity : null
}

function confirmSellAll() {
  sellAllDialog.value = false
  emit('sell-all')
}
</script>

<template>
  <v-card flat class="rounded border">
    <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 bg-amber-lighten-5">
      <v-icon icon="mdi-package-variant" color="amber" size="small" class="mr-2" />
      <span>仓库</span>
      <span v-if="currency" class="text-caption text-medium-emphasis ml-2">{{ currency }}</span>
      <v-spacer />
      <v-btn
        color="orange"
        size="small"
        variant="flat"
        prepend-icon="mdi-cash"
        :loading="loading"
        :disabled="loading || !items.length"
        @click="sellAllDialog = true"
      >
        一键出售
      </v-btn>
    </v-card-title>

    <v-table v-if="items.length" density="compact">
      <thead>
        <tr>
          <th>名称</th>
          <th class="text-center">数量</th>
          <th class="text-center">过期</th>
          <th class="text-center">单价</th>
          <th class="text-center">总价</th>
          <th class="text-center">出售</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(item, index) in items" :key="item.sell_key || `${item.crop_key}-${index}`">
          <td>{{ itemName(item) }}</td>
          <td class="text-center">{{ item.quantity ?? 0 }}</td>
          <td class="text-center">
            <span :class="{ 'text-error font-weight-medium': expiryState(item) === 'expiring', 'text-medium-emphasis': expiryState(item) === 'expired' }">
              {{ expiryText(item) }}
              <v-chip v-if="expiryState(item) === 'expiring'" color="error" size="x-small" class="ml-1">临期</v-chip>
            </span>
          </td>
          <td class="text-center">{{ formatPrice(item.unit_price) }}</td>
          <td class="text-center font-weight-medium">{{ formatPrice(itemTotal(item)) }}</td>
          <td class="text-center">
            <v-btn
              color="orange"
              size="x-small"
              variant="flat"
              prepend-icon="mdi-cash"
              :loading="loading"
              :disabled="loading || !item.crop_key"
              @click="emit('sell', item.crop_key)"
            >
              出售
            </v-btn>
          </td>
        </tr>
      </tbody>
    </v-table>
    <v-card-text v-else class="text-center text-medium-emphasis py-6">暂无物品</v-card-text>

    <v-dialog v-model="sellAllDialog" max-width="440">
      <v-card>
        <v-card-title>确认出售</v-card-title>
        <v-card-text>
          确定一键出售仓库 {{ items.length }} 个物品？预计总价值 {{ estimatedTotal }}<span v-if="currency"> {{ currency }}</span>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="grey" variant="text" prepend-icon="mdi-close" :disabled="loading" @click="sellAllDialog = false">取消</v-btn>
          <v-btn color="orange" variant="flat" prepend-icon="mdi-check" :loading="loading" :disabled="loading || !items.length" @click="confirmSellAll">
            确认
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<style scoped>
.bg-amber-lighten-5 {
  background-color: rgba(255, 193, 7, 0.1) !important;
}

.text-subtitle-2 {
  font-size: 0.9rem !important;
  font-weight: 500 !important;
}

.text-caption {
  font-size: 0.75rem !important;
}

@media (prefers-color-scheme: dark) {
  .bg-amber-lighten-5 {
    background-color: rgba(255, 193, 7, 0.2) !important;
  }
}
</style>
