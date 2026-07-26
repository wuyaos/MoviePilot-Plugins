<script setup>
import FarmWorkbench from './FarmWorkbench.vue'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['action', 'switch', 'close'])
</script>

<template>
  <FarmWorkbench
    :api="props.api"
    plugin-id="FarmAuto"
    show-close
    show-switch
    compact
    @action="emit('action', $event)"
    @switch="emit('switch')"
    @close="emit('close')"
  />
</template>
