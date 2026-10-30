<script setup>
import { computed } from 'vue'
const props = defineProps({ modelValue: { type: [String, Array], default: '' } })
const emit = defineEmits(['update:modelValue'])
// Render lists as lines without normalizing the stored value until an edit occurs.
const text = computed(() => Array.isArray(props.modelValue) ? props.modelValue.join('\n') : props.modelValue)
function update(value) {
  const edited = String(value ?? '')
  emit('update:modelValue', Array.isArray(props.modelValue)
    ? edited.split(/\r?\n/).map(line => line.trim()).filter(Boolean) : edited)
}
</script>

<template>
  <VTextarea :model-value="text" @update:model-value="update" density="compact" variant="outlined"
    rows="3" auto-grow class="dm-multi-line-input" @keydown.enter.stop />
</template>

<style scoped>
.dm-multi-line-input { min-width: 0; width: 100%; max-width: 100%; }
</style>
