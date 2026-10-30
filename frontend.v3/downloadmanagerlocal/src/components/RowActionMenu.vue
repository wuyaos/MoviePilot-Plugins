<script setup>
defineProps({
  label: { type: String, required: true },
  actions: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['select'])
</script>

<template>
  <span class="dm-row-menu">
    <VMenu location="bottom end" content-class="dm-action-menu">
      <template #activator="{ props: activatorProps }">
        <VBtn v-bind="activatorProps" size="small" variant="text" icon="mdi-dots-vertical"
          :aria-label="'更多操作：' + label" :loading="busy" :disabled="busy" />
      </template>
      <VList density="compact" :aria-label="label + '的操作'">
        <VListItem v-for="action in actions" :key="action.key" :disabled="action.disabled"
          :base-color="action.color" @click="!action.disabled && emit('select', action.key)">
          <template #prepend><VIcon :icon="action.icon" size="18" /></template>
          <VListItemTitle>{{ action.label }}</VListItemTitle>
        </VListItem>
      </VList>
    </VMenu>
  </span>
</template>

<style scoped>
.dm-row-menu { display: inline-flex; align-items: center; white-space: nowrap; }
</style>
