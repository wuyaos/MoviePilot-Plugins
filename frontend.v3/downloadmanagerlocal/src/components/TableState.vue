<script setup>
import { computed } from 'vue'
import '../styles/dm-tokens.css'

const props = defineProps({
  loading: { type: Boolean, default: false },
  error: { type: [Boolean, String], default: false },
  refreshFailed: { type: [Boolean, String], default: false },
  empty: { type: String, default: '', validator: value => ['', 'none', 'filtered', 'not-scanned', 'no-candidates', 'disabled'].includes(value) },
})
const emit = defineEmits(['retry', 'reset-filters'])
const emptyStates = {
  none: { icon: 'mdi-inbox-outline', title: '暂无记录', help: '' },
  filtered: { icon: 'mdi-filter-outline', title: '筛选无结果', help: '可重置筛选后查看全部记录。' },
  'not-scanned': { icon: 'mdi-magnify', title: '尚未扫描', help: '运行扫描后查看结果。' },
  'no-candidates': { icon: 'mdi-check-circle-outline', title: '扫描无候选', help: '本次扫描未发现候选项。' },
  disabled: { icon: 'mdi-pause-circle-outline', title: '模块已关闭', help: '启用模块后可生成新记录。' },
}
const emptyState = computed(() => emptyStates[props.empty])
</script>

<template>
  <div v-if="loading" class="dm-table-state dm-table-state--loading" role="status" aria-label="正在加载记录" aria-busy="true">
    <span class="dm-table-state-sr">正在加载记录</span>
    <span v-for="row in 3" :key="row" class="dm-table-skeleton" aria-hidden="true" />
  </div>
  <div v-else-if="error" class="dm-table-state" role="alert">
    <span class="mdi mdi-alert-circle-outline dm-table-state-icon dm-table-state-error" aria-hidden="true" />
    <p class="dm-table-state-title">记录加载失败</p>
    <p v-if="typeof error === 'string'" class="dm-table-state-help dm-table-state-error">{{ error }}</p>
    <button type="button" class="dm-table-state-button" @click="emit('retry')">重试</button>
  </div>
  <div v-else-if="refreshFailed" class="dm-table-state dm-table-state--refresh" role="status">
    <span class="mdi mdi-alert-outline dm-table-state-icon" aria-hidden="true" />
    <p class="dm-table-state-help">刷新失败，保留上次结果{{ typeof refreshFailed === 'string' ? '：' + refreshFailed : '' }}</p>
    <button type="button" class="dm-table-state-button" @click="emit('retry')">重试</button>
  </div>
  <div v-else-if="emptyState" class="dm-table-state" role="status">
    <span class="mdi dm-table-state-icon" :class="emptyState.icon" aria-hidden="true" />
    <p class="dm-table-state-title">{{ emptyState.title }}</p>
    <p v-if="emptyState.help" class="dm-table-state-help">{{ emptyState.help }}</p>
    <button v-if="empty === 'filtered'" type="button" class="dm-table-state-button" @click="emit('reset-filters')">重置筛选</button>
  </div>
</template>

<style scoped>
.dm-table-state { box-sizing: border-box; min-height: 140px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; padding: 12px; text-align: center; color: var(--dm-color-secondary); }
.dm-table-state-title { margin: 0; color: var(--dm-text-body-color); font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); }
.dm-table-state-help { margin: 0; overflow-wrap: anywhere; font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); }
.dm-table-state-icon { font-size: 20px; line-height: 24px; }
.dm-table-state-error { color: var(--dm-color-error); }
.dm-table-state--refresh { min-height: 0; flex-direction: row; flex-wrap: wrap; color: var(--dm-color-warning); }
.dm-table-state-button { min-height: 32px; padding: 4px 12px; border: 0; border-radius: 4px; color: rgb(var(--v-theme-primary)); background: transparent; cursor: pointer; font-family: inherit; font-size: var(--dm-text-button-size); font-weight: var(--dm-text-button-weight); line-height: var(--dm-text-button-line-height); }
.dm-table-state-button:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 2px; }
.dm-table-skeleton { display: block; width: 100%; height: 24px; border-radius: 4px; background: rgba(var(--v-theme-on-surface), var(--v-hover-opacity)); }
.dm-table-state-sr { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
</style>
