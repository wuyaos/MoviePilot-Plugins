<script setup>
import ModuleTable from './ModuleTable.vue'
defineProps({ fields: { type: Array, default: () => [] } })
const emit = defineEmits(['settings'])
</script>

<template>
  <ModuleTable title="配置摘要" :columns="fields.map(field => ({ key: field.key, label: field.label }))"
    :rows="[{ id: 'current' }]" :pagination="false">
    <template #toolbar><VBtn size="small" variant="text" prepend-icon="mdi-cog-outline" @click="emit('settings')">前往设置</VBtn></template>
    <template v-for="field in fields" :key="field.key" #[`cell-${field.key}`]>
      <VChip v-if="field.badge && field.value != null" size="x-small" variant="tonal" :color="field.color || 'default'">{{ field.value }}</VChip>
      <details v-else-if="field.long && field.value != null" class="dm-summary-long">
        <summary :title="String(field.value)">{{ field.value }}</summary><p>{{ field.value }}</p>
      </details>
      <span v-else :title="field.value == null ? '当前接口未提供' : String(field.value)">{{ field.value ?? '当前接口未提供' }}</span>
    </template>
  </ModuleTable>
</template>

<style scoped>
.dm-summary-long { max-width: 260px; }
.dm-summary-long summary { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer; }
.dm-summary-long p { margin: 6px 0 0; overflow-wrap: anywhere; white-space: pre-wrap; }
</style>
