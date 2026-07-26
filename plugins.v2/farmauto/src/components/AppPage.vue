<script setup>
import FarmWorkbench from './FarmWorkbench.vue'

defineProps({
  api: { type: Object, default: () => ({}) },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'FarmAuto' },
})

defineEmits(['action'])
</script>

<template>
  <FarmWorkbench :api="api" :plugin-id="pluginId" @action="$emit('action', $event)" />
</template>
