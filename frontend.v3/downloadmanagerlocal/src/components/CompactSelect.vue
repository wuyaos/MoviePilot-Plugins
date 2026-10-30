<script setup>
defineProps({
  modelValue: { type: [String, Number], default: '' },
  items: { type: Array, default: () => [] },
  label: { type: String, required: true },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <VSelect class="dm-compact-select" :model-value="modelValue" :items="items" :aria-label="label"
    :disabled="disabled" density="compact" single-line hide-details variant="outlined"
    :menu-props="{ contentClass: 'dm-select-menu' }" :list-props="{ density: 'compact' }" @update:model-value="emit('update:modelValue', $event)" />
</template>

<style scoped>
.dm-compact-select { min-width: 0; font-family: var(--dm-font-family); font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); letter-spacing: normal; }
.dm-compact-select :deep(.v-select__selection-text), .dm-compact-select :deep(input) { font-family: inherit; font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); letter-spacing: normal; }
.dm-compact-select :deep(.v-field) { --v-input-control-height: var(--dm-button-height); --v-field-padding-top: 0px; --v-field-padding-bottom: 0px; --v-field-padding-start: 8px; --v-field-padding-end: 8px; border-radius: 4px; }
.dm-compact-select :deep(.v-field__input) { min-height: var(--dm-button-height); padding-block: 0; font-size: var(--dm-text-body-size); line-height: var(--dm-text-body-line-height); }
.dm-compact-select :deep(.v-select__selection) { margin-block: 0; }
.dm-compact-select :deep(.v-field__append-inner) { padding-block: 0; align-items: center; }
</style>
