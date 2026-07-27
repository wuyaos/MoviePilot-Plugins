<script setup>
import { computed } from 'vue'

const props = defineProps({
  history: { type: Array, default: () => [] },
  currency: { type: String, default: '' },
})

// KoWming logMeta 对齐: action -> [中文, class]
const actionMap = {
  harvest: ['收获', 'harvest'],
  harvest_all: ['一键收获', 'harvest'],
  plant: ['种植', 'plant'],
  breed: ['养殖', 'plant'],
  sell: ['售出', 'sell'],
  steal: ['偷菜', 'steal'],
  like: ['点赞', 'like'],
  buy_slot: ['购买坑位', 'plant'],
  buy_decor: ['购买装饰', 'plant'],
  visit: ['参观', 'like'],
}

function logMeta(item) {
  const action = String(item?.action || '').trim()
  const mapped = actionMap[action] || [action || '未知', '']
  const parts = []
  // 种子图标(兼容 user_logs.seed_icon / recent_actions.crop_icon)
  const icon = item?.seed_icon || item?.crop_icon || ''
  const name = item?.seed_name || item?.crop_name || item?.target || ''
  if (icon) parts.push({ icon, name })
  else if (name) parts.push({ name })
  // 地块信息
  const plotIdx = item?.plot_index
  const hasPlotIndex = plotIdx !== undefined && plotIdx !== null && !Number.isNaN(Number(plotIdx))
  if (item?.land_name) parts.push(`(${item.land_name}${hasPlotIndex ? `-${Number(plotIdx) + 1}号地` : ''})`)
  // 数量(仅 >1 显示)
  const qty = Number(item?.quantity || 0)
  if (qty > 1) parts.push(`数量：${qty}`)
  // 失败消息
  if (item?.success === false && item?.message) parts.push(item.message)

  const unit = item?.value_unit || (action === 'harvest' ? '收获值' : '魔力值')
  // 兼容 user_logs.value / recent_actions.profit
  const value = Number(item?.value ?? item?.profit ?? 0)
  // 魔力列优先显示本次变动值；无变动时回退余额 balance_after，保证每行都有值
  const balance = Number(item?.balance_after ?? '')
  const hasChange = value !== 0
  const magicText = hasChange
    ? `${value > 0 ? '+' : ''}${value} ${unit}`
    : (Number.isFinite(balance) ? `${balance} ${unit}` : '')
  return {
    actionText: mapped[0],
    actionClass: mapped[1] ? `history-action--${mapped[1]}` : '',
    detailText: parts.map(p => typeof p === 'string' ? p : (p.name || '')).filter(Boolean).join(' '),
    hasIcon: !!parts.find(p => typeof p === 'object' && p.icon),
    iconSrc: (parts.find(p => typeof p === 'object' && p.icon) || {}).icon,
    valueText: magicText,
    valueClass: value > 0 ? 'history-value--plus' : (value < 0 ? 'history-value--minus' : ''),
  }
}

const rows = computed(() => (Array.isArray(props.history) ? props.history : []).slice(-20).reverse())

function formatTime(value) {
  if (value == null || value === '') return '—'
  if (typeof value === 'string' && /^\d{1,2}:\d{2}(?::\d{2})?$/.test(value)) {
    return value.slice(0, 5)
  }
  const numericValue = Number(value)
  // 数字时间戳：秒(<1e12) 或 毫秒(>=1e12)
  if (Number.isFinite(numericValue) && /^\d+(\.\d+)?$/.test(String(value).trim())) {
    const ms = numericValue < 1e12 ? numericValue * 1000 : numericValue
    const date = new Date(ms)
    if (!Number.isNaN(date.getTime())) {
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
    }
  }
  // 字符串日期（如思齐 user_logs.created_at '2026-07-27 01:45:07'）
  const date = new Date(String(value).replace(' ', 'T'))
  if (!Number.isNaN(date.getTime())) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  }
  return '—'
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
          <th class="text-end">魔力</th>
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
            <span class="history-action" :class="logMeta(item).actionClass">{{ logMeta(item).actionText }}</span>
            <span class="history-detail">
              <v-img
                v-if="logMeta(item).hasIcon"
                :src="logMeta(item).iconSrc"
                width="20"
                height="20"
                contain
                class="d-inline-block mr-1"
                style="vertical-align: middle"
              />
              {{ logMeta(item).detailText }}
            </span>
          </td>
          <td class="text-end text-no-wrap profit" :class="logMeta(item).valueClass">
            {{ logMeta(item).valueText }}
          </td>
        </tr>
      </tbody>
    </v-table>
    <v-card-text v-else class="text-center text-medium-emphasis py-6">暂无记录</v-card-text>
  </v-card>
</template>

<style scoped>
.failed-row td,
.failed-row .profit {
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)) !important;
}

.history-action {
  font-weight: 700;
  margin-right: 6px;
}
.history-action--plant { color: rgb(var(--v-theme-success)); }
.history-action--harvest { color: rgb(var(--v-theme-warning)); }
.history-action--sell { color: rgb(var(--v-theme-info)); }
.history-action--steal { color: rgb(var(--v-theme-error)); }
.history-action--like { color: rgb(var(--v-theme-secondary)); }

.history-detail {
  font-size: 0.8rem;
  color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity));
}

.history-value--plus { color: rgb(var(--v-theme-success)); }
.history-value--minus { color: rgb(var(--v-theme-error)); }
</style>
