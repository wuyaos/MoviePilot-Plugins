<script setup>
import FarmConfigForm from './FarmConfigForm.vue'

const props = defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['save', 'switch', 'close'])
</script>

<template>
  <FarmConfigForm
    :initial-config="props.initialConfig"
    :api="props.api"
    @save="emit('save', $event)"
    @switch="emit('switch')"
    @close="emit('close')"
  />
</template>
