<script setup>
import { onMounted } from 'vue'
import FarmWorkbench from './FarmWorkbench.vue'

defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['layout', 'switch', 'close'])

onMounted(() => {
  emit('layout', { maxWidth: '80rem' })
})
</script>

<template>
  <FarmWorkbench
    :api="api"
    plugin-id="FarmAuto"
    initial-tab="config"
    show-close
    show-switch
    compact
    @switch="$emit('switch')"
    @close="$emit('close')"
  />
</template>
