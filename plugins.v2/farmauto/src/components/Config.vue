<script setup>
import FarmConfigForm from './FarmConfigForm.vue'

const props = defineProps({
  initialConfig: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['save', 'switch', 'close'])
</script>

<template>
  <FarmConfigForm
    :initial-config="props.initialConfig"
    @save="emit('save', $event)"
    @switch="emit('switch')"
    @close="emit('close')"
  />
</template>
