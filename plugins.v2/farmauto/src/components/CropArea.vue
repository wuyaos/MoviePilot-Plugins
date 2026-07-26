<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  items: { type: Array, default: () => [] },
  cropStatus: { type: Object, default: () => ({}) },
  crops: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  animal: { type: Boolean, default: false },
})

const emit = defineEmits(['action'])

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
    canHarvest,
    isGrowing,
    remainingMinutes,
  }
}))

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
    </v-card-title>

    <v-card-text class="px-3 py-2">
      <v-row dense>
        <v-col v-for="item in areaItems" :key="item.cropKey" cols="12" sm="6">
          <v-card variant="outlined" class="crop-area__item pa-3">
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
                color="orange"
                size="x-small"
                variant="flat"
                :disabled="loading"
                @click="emit('action', { action: 'harvest', cropKey: item.cropKey })"
              >
                收获
              </v-btn>
              <v-btn
                v-else-if="!item.isGrowing"
                :color="animal ? 'brown' : 'green'"
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

@media (prefers-color-scheme: dark) {
  .bg-green-lighten-5 {
    background-color: rgba(76, 175, 80, 0.2) !important;
  }

  .bg-brown-lighten-5 {
    background-color: rgba(121, 85, 72, 0.2) !important;
  }
}
</style>
