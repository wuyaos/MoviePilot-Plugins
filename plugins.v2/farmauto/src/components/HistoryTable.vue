<script setup>
import { computed } from 'vue'

const props = defineProps({
  history: { type: Array, default: () => [] },
  currency: { type: String, default: '' },
})

// KoWming logMeta 对齐: action -> [中文, class, emoji]
const actionMap = {
  harvest: ['收获', 'harvest', '🌾'],
  harvest_all: ['一键收获', 'harvest', '🌾'],
  plant: ['种植', 'plant', '🌱'],
  breed: ['养殖', 'plant', '🐣'],
  sell: ['售出', 'sell', '💰'],
  steal: ['偷菜', 'steal', '🥷'],
  like: ['点赞', 'like', '👍'],
  buy_slot: ['购买坑位', 'plant', '🏗'],
  buy_decor: ['购买装饰', 'plant', '🏗'],
  visit: ['参观', 'like', '🚜'],
}

// 作物 emoji 回退映射（crop_icon 为 data URI 图片时不用，用名称匹配 emoji）
const CROP_EMOJI_FALLBACK = {
  萝卜: '🥕', 西红柿: '🍅', 玉米: '🌽', 茄子: '🍆', 蘑菇: '🍄', 樱桃: '🍒',
  小麦: '🌾', 花生: '🥜', 土豆: '🥔', 南瓜: '🎃', 白菜: '🥬', 辣椒: '🌶',
  鸡: '🐔', 猪: '🐷', 牛: '🐂', 羊: '🐑', 鱼: '🐟', 鸭: '🦆',
}
function cropEmoji(name) {
  if (!name) return ''
  return CROP_EMOJI_FALLBACK[String(name).trim()] || '🌱'
}

function logMeta(item) {
  const action = String(item?.action || '').trim()
  const mapped = actionMap[action] || [action || '未知', '', '']
  const actionEmoji = mapped[2] || ''
  const parts = []
  // 作物 emoji（统一用 emoji，不用 data URI 图片）
  const name = item?.seed_name || item?.crop_name || item?.target || ''
  if (name && name !== 'all' && !/收获/.test(name)) {
    parts.push({ emoji: cropEmoji(name), name })
  }
  // 地块信息
  const plotIdx = item?.plot_index
  const hasPlotIndex = plotIdx !== undefined && plotIdx !== null && !Number.isNaN(Number(plotIdx))
  if (item?.land_name) parts.push(`(${item.land_name}${hasPlotIndex ? `-${Number(plotIdx) + 1}号地` : ''})`)
  // 数量(仅 >1 显示)
  const qty = Number(item?.quantity || 0)
  if (qty > 1) parts.push(`数量：${qty}`)
  // 失败消息
  if (item?.success === false && item?.message) parts.push(item.message)

  const unit = '魔力值'
  // 兼容 user_logs.value / recent_actions.profit
  const value = Number(item?.value ?? item?.profit ?? 0)
  // 魔力列：有变动显示±value，无变动回退余额 balance_after；保证每行都有值
  const balance = Number(item?.balance_after ?? '')
  const hasChange = value !== 0
  const displayValue = hasChange ? value : (Number.isFinite(balance) ? balance : 0)
  const magicText = `${displayValue > 0 ? '+' : ''}${displayValue} ${unit}`
  return {
    actionText: mapped[0],
    actionClass: mapped[1] ? `history-action--${mapped[1]}` : '',
    actionEmoji,
    detailText: parts.map(p => typeof p === 'string' ? p : (p.name || '')).filter(Boolean).join(' '),
    cropEmoji: parts.find(p => typeof p === 'object' && p.emoji)?.emoji || '',
    hasIcon: false,
    iconSrc: '',
    valueText: magicText,
    valueClass: displayValue > 0 ? 'history-value--plus' : (displayValue < 0 ? 'history-value--minus' : ''),
  }
}

const rows = computed(() => (Array.isArray(props.history) ? props.history : []).slice(0, 50))

const CHINA_TIME_OPTIONS = {
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: 'Asia/Shanghai',
}

function formatTime(value) {
  if (value == null || value === '') return '—'
  const text = String(value).trim()
  if (/^\d{1,2}:\d{2}(?::\d{2})?$/.test(text)) return text.slice(0, 5)

  const numericValue = Number(value)
  // ActionResult 使用 Unix 秒时间戳；固定按站点所在的中国时区显示，不依赖浏览器时区。
  if (Number.isFinite(numericValue) && /^\d+(\.\d+)?$/.test(text)) {
    const ms = numericValue < 1e12 ? numericValue * 1000 : numericValue
    const date = new Date(ms)
    if (!Number.isNaN(date.getTime())) return date.toLocaleTimeString('zh-CN', CHINA_TIME_OPTIONS)
  }

  // 思齐 created_at 是不带时区的中国本地时间，直接保留原始时分，避免二次时区换算。
  const localDateTime = text.match(/^\d{4}-\d{2}-\d{2}[ T](\d{2}):(\d{2})(?::\d{2})?$/)
  if (localDateTime) return `${localDateTime[1]}:${localDateTime[2]}`

  const date = new Date(text)
  if (!Number.isNaN(date.getTime())) return date.toLocaleTimeString('zh-CN', CHINA_TIME_OPTIONS)
  return '—'
}
</script>

<template>
  <v-card flat class="rounded border h-100">
    <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 section-title-bg">
      <v-icon icon="mdi-history" color="grey" size="small" class="mr-2" />
      执行记录
    </v-card-title>

    <div v-if="rows.length" class="history-scroll">
    <v-table density="compact">
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
          :key="`${item.time ?? item.created_at}-${item.action}-${item.target}-${index}`"
          :class="{ 'failed-row': item.success === false }"
        >
          <td class="text-no-wrap">{{ formatTime(item.time ?? item.created_at) }}</td>
          <td>
            <span class="history-action" :class="logMeta(item).actionClass">
              <span v-if="logMeta(item).actionEmoji" class="action-emoji">{{ logMeta(item).actionEmoji }}</span>
              {{ logMeta(item).actionText }}
            </span>
            <span class="history-detail">
              <span v-if="logMeta(item).cropEmoji" class="crop-emoji-inline">{{ logMeta(item).cropEmoji }}</span>
              {{ logMeta(item).detailText }}
            </span>
          </td>
          <td class="text-end text-no-wrap profit" :class="logMeta(item).valueClass">
            {{ logMeta(item).valueText }}
          </td>
        </tr>
      </tbody>
    </v-table>
    </div>
    <v-card-text v-else class="text-center text-medium-emphasis py-6">暂无记录</v-card-text>
  </v-card>
</template>

<style scoped>
.history-scroll {
  max-height: 360px;
  overflow-y: auto;
}
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
.action-emoji { margin-right: 4px; }
.crop-emoji-inline { margin-right: 2px; }

.history-value--plus { color: rgb(var(--v-theme-success)); }
.history-value--minus { color: rgb(var(--v-theme-error)); }
</style>
