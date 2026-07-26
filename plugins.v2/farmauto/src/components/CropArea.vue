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
  const status = props.cropStatus?.[cropKey]
  const canHarvest = Boolean(status?.can_harvest)
  const remainingMinutes = status?.remaining_minutes
  const isGrowing = !canHarvest && remainingMinutes !== null && remainingMinutes !== undefined
  return {
    cropKey,
    name: definition.name || cropKey,
    cost: definition.cost,
    image: definition.image || '',
    canHarvest,
    isGrowing,
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

function statusText(item) {
  if (item.canHarvest) return '可收获'
  if (item.isGrowing) return `生长中，剩余 ${item.remainingMinutes} 分钟`
  return '空地'
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
          <v-card variant="outlined" class="crop-area__item pa-3">
            <div class="d-flex align-center">
              <div class="crop-area__media d-flex align-center justify-center flex-shrink-0">
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
                />
              </div>

              <div class="crop-area__details flex-grow-1 min-width-0">
                <div class="d-flex align-center ga-2">
                  <div class="text-body-2 font-weight-bold text-truncate" :title="item.name">
                    {{ item.name }}
                  </div>
                  <v-chip
                    size="x-small"
                    :color="item.canHarvest ? 'orange' : item.isGrowing ? 'info' : 'green'"
                    variant="tonal"
                  >
                    {{ item.canHarvest ? '可收获' : item.isGrowing ? '生长中' : '空地' }}
                  </v-chip>
                  <v-spacer />
                  <v-btn
                    v-if="item.canHarvest"
                    color="success"
                    size="x-small"
                    variant="flat"
                    :disabled="loading"
                    @click="emit('action', { action: 'harvest', cropKey: item.cropKey })"
                  >
                    收获
                  </v-btn>
                  <v-btn
                    v-else-if="!item.isGrowing"
                    color="success"
                    size="x-small"
                    variant="flat"
                    :disabled="loading"
                    @click="emit('action', { action: 'plant', cropKey: item.cropKey })"
                  >
                    {{ animal ? '养殖' : '种植' }}
                  </v-btn>
                </div>
                <div class="text-caption text-medium-emphasis mt-2">
                  {{ statusText(item) }}
                  <span v-if="item.cost !== null && item.cost !== undefined"> · 成本 {{ item.cost }}</span>
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

.crop-area__item {
  min-block-size: 76px;
}

.crop-area__media {
  inline-size: 70px;
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
