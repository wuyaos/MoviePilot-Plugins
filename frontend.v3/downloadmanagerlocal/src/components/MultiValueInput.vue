<script setup>
import { computed } from 'vue'
const props = defineProps({ modelValue: { type: [String, Array], default: '' }, label: { type: String, required: true } })
const emit = defineEmits(['update:modelValue'])
// Keep the stored comma-separated string untouched until the user edits it.
const values = computed(() => Array.isArray(props.modelValue) ? props.modelValue : props.modelValue.split(',').map(value => value.trim()).filter(Boolean))
function update(items) { emit('update:modelValue', Array.isArray(props.modelValue) ? items : items.map(String).join(',')) }
function guardComposition(event) {
  if (event.key === 'Enter' && (event.isComposing || event.keyCode === 229)) event.stopImmediatePropagation()
}
</script>

<template>
  <VCombobox :model-value="values" @update:model-value="update" :label="label"
    :delimiters="Array.isArray(modelValue) ? [] : [',']" multiple chips closable-chips :return-object="false" density="compact" variant="outlined"
    class="dm-multi-value-input" @keydown.capture="guardComposition" @keydown.enter.stop :menu-props="{ contentClass: 'dm-select-menu' }">
    <template #chip="{ props: chipProps, item }">
      <VChip v-bind="chipProps" size="small" :title="item.title">{{ item.title }}</VChip>
    </template>
  </VCombobox>
</template>

<style scoped>
.dm-multi-value-input { min-width: 0; max-width: 100%; }
.dm-multi-value-input :deep(.v-field__input) { flex-wrap: wrap; gap: 4px; }
.dm-multi-value-input :deep(.v-combobox__selection) { max-width: 100%; min-width: 0; }
.dm-multi-value-input :deep(.v-chip) { max-width: 100%; }
.dm-multi-value-input :deep(.v-chip__content) { overflow: hidden; text-overflow: ellipsis; display: block; }
.dm-multi-value-input :deep(input) { min-width: min(100%, 80px); }
</style>
