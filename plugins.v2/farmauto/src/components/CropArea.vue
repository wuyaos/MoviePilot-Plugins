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
    <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2" :class="animal ? 'bg-brown-lighten-5' : 'bg-green-lighten-5'">
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

    <v-card-text class="px-3 py-2">
      <v-row dense>
        <v-col v-for="item in areaItems" :key="item.cropKey" cols="12" sm="6">
          <v-card
            variant="outlined"
            :color="stateColor(item.state)"
            class="horizontal-card crop-area__item"
          >
            <div class="d-flex">
              <div class="crop-area__media flex-shrink-0 pa-2">
                <v-img
                  v-if="hasUsableImage(item)"
                  :src="item.image"
                  width="40"
                  height="40"
                  contain
                  class="mx-auto"
                  @error="markImageError(item)"
                />
                <v-icon
                  v-else
                  :icon="cropIcon(item.cropKey, item.name)"
                  :color="animal ? 'brown' : 'green'"
                  size="40"
                  class="d-block mx-auto"
                />
                <div v-if="item.growTime" class="crop-area__time text-center text-caption text-grey mt-1">
                  成长时间: {{ item.growTime }}
                </div>
                <div v-if="item.state === 'growing' && item.remainingMinutes !== null && item.remainingMinutes !== undefined" class="crop-area__time text-center text-caption text-grey">
                  剩余 {{ formatRemainingMinutes(item.remainingMinutes) }}
                </div>
              </div>

              <div class="crop-area__details flex-grow-1 pa-2">
                <div class="d-flex align-center ga-2 mb-1">
                  <div class="text-body-2 font-weight-bold text-truncate" :title="item.name">
                    {{ item.name }}
                  </div>
                  <v-chip size="x-small" :color="stateColor(item.state)">
                    {{ stateText(item.state) }}
                  </v-chip>
                  <v-spacer />
                  <v-btn
                    v-if="item.state === 'empty'"
                    color="success"
                    size="x-small"
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
                    size="x-small"
                    variant="flat"
                    prepend-icon="mdi-basket"
                    :disabled="loading"
                    @click="emitCropAction('harvest', item)"
                  >
                    收获
                  </v-btn>
                </div>
                <div class="text-caption text-grey-darken-1">
                  价格: {{ displayValue(item.price) }}（成本 {{ displayValue(item.cost) }}）
                </div>
              </div>
            </div>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.bg-green-lighten-5 {
  background-color: rgba(76, 175, 80, 0.1) !important;
}

.bg-brown-lighten-5 {
  background-color: rgba(121, 85, 72, 0.1) !important;
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

@media (prefers-color-scheme: dark) {
  .bg-green-lighten-5 {
    background-color: rgba(76, 175, 80, 0.2) !important;
  }

  .bg-brown-lighten-5 {
    background-color: rgba(121, 85, 72, 0.2) !important;
  }
}
</style>
