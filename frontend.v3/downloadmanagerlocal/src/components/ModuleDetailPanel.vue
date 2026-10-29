<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  rows: { type: Array, default: () => [] },
  items: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  limit: { type: Number, default: 0 },
  truncated: { type: Boolean, default: false },
  error: { type: String, default: '' },
  emptyText: { type: String, default: '' },
})

const shownCount = computed(() => (props.items.length ? props.items.length : props.rows.length))
</script>

<template>
  <div class="dm-detail-panel">
    <div v-if="title" class="dm-detail-title">{{ title }}</div>
    <div v-if="subtitle" class="text-caption text-medium-emphasis dm-detail-break">{{ subtitle }}</div>
    <div v-if="error" class="text-caption text-error dm-detail-break">{{ error }}</div>
    <slot name="actions" />
    <slot>
      <div v-if="rows.length" class="dm-detail-grid">
        <div v-for="row in rows" :key="`row-${row.label}`" class="dm-detail-row">
          <span>{{ row.label }}</span><strong>{{ row.value }}</strong>
        </div>
      </div>
      <div v-if="items.length" class="dm-detail-items">
        <div v-for="(item, index) in items" :key="`item-${index}`" class="dm-detail-item">
          <div class="dm-detail-item-title dm-detail-break">{{ item.title }}</div>
          <div v-if="item.meta" class="text-caption text-medium-emphasis dm-detail-break">{{ item.meta }}</div>
        </div>
      </div>
      <div v-if="emptyText && !rows.length && !items.length" class="dm-detail-empty">{{ emptyText }}</div>
      <div v-if="truncated" class="text-caption text-medium-emphasis dm-detail-truncated">
        仅显示前 {{ shownCount }} 条，共 {{ total }} 条（上限 {{ limit }} 条）；可在「总览」页调整明细条数。
      </div>
    </slot>
    <slot name="appendix" />
  </div>
</template>

<style scoped>
.dm-detail-panel { min-width: 0; }
.dm-detail-title { margin-bottom: 6px; color: rgba(var(--v-theme-on-surface), 0.78); font-size: 12px; font-weight: 700; }
.dm-detail-break { overflow-wrap: anywhere; }
.dm-detail-grid { display: grid; gap: 5px; }
.dm-detail-row { display: grid; grid-template-columns: minmax(72px, auto) minmax(0, 1fr); gap: 8px; align-items: baseline; font-size: 12px; }
.dm-detail-row span { color: rgba(var(--v-theme-on-surface), 0.56); }
.dm-detail-row strong { overflow-wrap: anywhere; font-weight: 650; }
.dm-detail-items { display: grid; gap: 6px; margin-top: 8px; }
.dm-detail-item { min-width: 0; padding: 6px 8px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 7px; background: rgba(var(--v-theme-on-surface), 0.02); }
.dm-detail-item-title { font-size: 12px; font-weight: 650; }
.dm-detail-empty { display: flex; min-height: 64px; align-items: center; justify-content: center; border: 1px dashed rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; color: rgba(var(--v-theme-on-surface), 0.6); font-size: 13px; }
.dm-detail-truncated { margin-top: 8px; }
</style>
