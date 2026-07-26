<script setup>
import FarmWorkbench from './FarmWorkbench.vue'

defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'FarmAuto' },
})

defineEmits(['action'])
</script>

<template>
  <FarmWorkbench :api="api" :plugin-id="pluginId" @action="$emit('action', $event)" />
</template>
