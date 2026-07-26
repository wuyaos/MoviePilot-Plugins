<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  items: { type: Array, default: () => [] },
  cropStatus: { type: Object, default: () => ({}) },
  crops: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  animal: { type: Boolean, default: false },
  showHarvestAll: { type: Boolean, default: true },
})

const emit = defineEmits(['action', 'harvest-all'])
const imageErrors = ref(new Set())

const areaItems = computed(() => props.items.map(cropKey => {
  const definition = props.crops?.[cropKey] || {}
  const status = props.cropStatus?.[cropKey] || {}
  const remainingMinutes = status.remaining_minutes
  let state = status.state
  if (!['empty', 'ripe', 'growing'].includes(state)) {
    state = status.can_harvest
      ? 'ripe'
      : Number(remainingMinutes) > 0 ? 'growing' : 'empty'
  }
  return {
    cropKey,
    name: definition.name || cropKey,
    cost: definition.cost,
    image: definition.image || '',
    state,
    price: status.price,
    growTime: status.grow_time,
    remainingMinutes,
  }
}))

function cropIcon(cropKey, name) {
  const iconsByKey = {
    crop_1: 'mdi-grain',
    crop_2: 'mdi-corn',
    crop_3: 'mdi-peanut-outline',
    crop_4: 'mdi-carrot',
    animal_1: 'mdi-bird',
    animal_2: 'mdi-pig',
    animal_3: 'mdi-sheep',
    animal_4: 'mdi-cow',
  }
  if (iconsByKey[cropKey]) return iconsByKey[cropKey]

  const cropName = String(name || '').toLowerCase()
  if (cropName.includes('小麦') || cropName.includes('wheat')) return 'mdi-grain'
  if (cropName.includes('玉米') || cropName.includes('corn')) return 'mdi-corn'
  if (cropName.includes('花生') || cropName.includes('peanut')) return 'mdi-peanut-outline'
  if (cropName.includes('土豆') || cropName.includes('马铃薯') || cropName.includes('potato')) return 'mdi-carrot'
  if (cropName.includes('鸡') || cropName.includes('chicken')) return 'mdi-bird'
  if (cropName.includes('猪') || cropName.includes('pig')) return 'mdi-pig'
  if (cropName.includes('羊') || cropName.includes('sheep')) return 'mdi-sheep'
  if (cropName.includes('牛') || cropName.includes('cow')) return 'mdi-cow'
  return props.animal ? 'mdi-cow' : 'mdi-seed'
}

function imageErrorKey(item) {
  return `${item.cropKey}:${item.image}`
}

function hasUsableImage(item) {
  return Boolean(item.image) && !imageErrors.value.has(imageErrorKey(item))
}

function markImageError(item) {
  const errors = new Set(imageErrors.value)
  errors.add(imageErrorKey(item))
  imageErrors.value = errors
}

function stateColor(state) {
  return {
    empty: 'green',
    ripe: 'orange',
    growing: 'blue',
  }[state] || 'grey'
}

function stateText(state) {
  return {
    empty: '空闲',
    ripe: '已成熟',
    growing: '生长中',
  }[state] || '未知'
}

function formatRemainingMinutes(value) {
  const totalMinutes = Math.max(0, Math.floor(Number(value)))
  if (!Number.isFinite(totalMinutes)) return '—'

  const days = Math.floor(totalMinutes / 1440)
  const hours = Math.floor((totalMinutes % 1440) / 60)
  const minutes = totalMinutes % 60
  return `${days ? `${days}天` : ''}${days || hours ? `${hours}小时` : ''}${minutes}分`
}

function displayValue(value) {
  return value === null || value === undefined || value === '' ? '—' : value
}

function emitCropAction(action, item) {
  emit('action', {
    action,
    crop_key: item.cropKey,
    cropKey: item.cropKey,
  })
}
</script>

<template>
  <v-card flat class="rounded border">
    <v-card-title class="section-title-bg text-subtitle-2 d-flex align-center px-3 py-2">
      <v-icon :icon="animal ? 'mdi-cow' : 'mdi-seed'" :color="animal ? 'brown' : 'green'" size="small" class="mr-2" />
      {{ title }}
      <v-spacer />
      <v-tooltip v-if="showHarvestAll" text="一键收获全场" location="top">
        <template #activator="{ props: tooltipProps }">
          <v-btn
            v-bind="tooltipProps"
            prepend-icon="mdi-basket"
            color="success"
            size="small"
            variant="flat"
            :loading="loading"
            @click="emit('harvest-all')"
          >
            一键收获
          </v-btn>
        </template>
      </v-tooltip>
    </v-card-title>

    <v-card-text class="pa-3">
      <div class="crop-grid">
        <div
          v-for="item in areaItems"
          :key="item.cropKey"
          class="crop-card"
          :class="[`state-${item.state}`, { animal }]"
        >
          <div class="crop-icon">
            <v-img
              v-if="hasUsableImage(item)"
              :src="item.image"
              width="40"
              height="40"
              contain
              @error="markImageError(item)"
            />
            <v-icon
              v-else
              :icon="cropIcon(item.cropKey, item.name)"
              :color="animal ? 'brown' : 'green'"
              size="36"
            />
          </div>
          <div class="crop-info">
            <div class="crop-name" :title="item.name">{{ item.name }}</div>
            <div class="crop-meta">
              价格 {{ displayValue(item.price) }} · 成本 {{ displayValue(item.cost) }}
              <span v-if="item.growTime"> · 成长 {{ item.growTime }}</span>
            </div>
            <div class="crop-status">
              <v-chip size="x-small" :color="stateColor(item.state)" variant="flat">
                {{ stateText(item.state) }}
              </v-chip>
              <span
                v-if="item.state === 'growing' && item.remainingMinutes !== null && item.remainingMinutes !== undefined"
                class="crop-remain"
              >
                剩余 {{ formatRemainingMinutes(item.remainingMinutes) }}
              </span>
            </div>
          </div>
          <div class="crop-action">
            <v-btn
              v-if="item.state === 'empty'"
              color="success"
              size="small"
              variant="flat"
              prepend-icon="mdi-seed"
              :disabled="loading"
              @click="emitCropAction('plant', item)"
            >
              种植
            </v-btn>
            <v-btn
              v-else-if="item.state === 'ripe'"
              color="orange"
              size="small"
              variant="flat"
              prepend-icon="mdi-basket"
              :disabled="loading"
              @click="emitCropAction('harvest', item)"
            >
              收获
            </v-btn>
          </div>
        </div>
      </div>
    </v-card-text>
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

.text-caption {
  font-size: 0.75rem !important;
}

.text-body-2 {
  font-size: 0.875rem !important;
}

.horizontal-card {
  min-block-size: 76px;
}

.crop-area__media {
  inline-size: 70px;
}

.crop-area__time {
  font-size: 0.65rem !important;
  line-height: 1.1;
  white-space: nowrap;
}

.crop-area__details {
  min-inline-size: 0;
}

/* CropArea 卡片样式（对齐思齐 seed-card 风格） */
.crop-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 8px;
}
.crop-card {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  gap: 10px;
  align-items: center;
  background: rgba(var(--v-theme-surface), 0.5);
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}
.crop-card:hover {
  border-color: rgba(76, 175, 80, 0.4);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  transform: translateY(-1px);
}
.crop-card.animal:hover {
  border-color: rgba(180, 83, 9, 0.4);
}
.crop-card.state-ripe {
  border-color: rgba(255, 152, 0, 0.35);
  background: rgba(255, 152, 0, 0.05);
}
.crop-card.state-growing {
  border-color: rgba(59, 130, 246, 0.25);
  background: rgba(59, 130, 246, 0.04);
}
.crop-icon {
  width: 48px;
  height: 48px;
  flex: 0 0 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}
.crop-info {
  flex: 1;
  min-width: 0;
}
.crop-name {
  font-weight: 700;
  font-size: 13px;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.crop-meta {
  font-size: 10px;
  color: rgba(var(--v-theme-on-surface), 0.4);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.crop-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}
.crop-remain {
  font-size: 10px;
  color: rgba(var(--v-theme-on-surface), 0.45);
}
.crop-action {
  flex: 0 0 auto;
}
</style>
