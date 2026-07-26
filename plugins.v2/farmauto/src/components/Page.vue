<script setup>
import FarmWorkbench from './FarmWorkbench.vue'

defineProps({
  api: { type: Object, default: () => ({}) },
})

defineEmits(['action', 'switch', 'close'])
</script>

<template>
  <FarmWorkbench
    :api="api"
    plugin-id="FarmAuto"
    show-close
    show-switch
    compact
    @action="$emit('action')"
    @switch="$emit('switch')"
    @close="$emit('close')"
  />
</template>
