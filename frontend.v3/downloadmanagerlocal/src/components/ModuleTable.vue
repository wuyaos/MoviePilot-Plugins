<script setup>
import { computed, ref, watch } from 'vue'
import TableState from './TableState.vue'
import '../styles/dm-tokens.css'

const props = defineProps({
  title: { type: String, required: true },
  columns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  rowKey: { type: [String, Function], default: 'id' },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20, validator: value => [20, 50, 100].includes(value) },
  state: { type: Object, default: () => ({}) },
  // Opt-in presentation action only; the consumer owns confirmation and IO.
  cleanupLabel: { type: String, default: '' },
})
const emit = defineEmits(['update:page', 'update:pageSize', 'retry', 'reset-filters', 'cleanup'])
const pageSizes = [20, 50, 100]
const effectivePageSize = computed(() => pageSizes.includes(props.pageSize) ? props.pageSize : 20)
const pageCount = computed(() => Math.max(1, Math.ceil(props.total / effectivePageSize.value)))
const currentPage = computed(() => Math.min(Math.max(1, props.page), pageCount.value))
const cleanupDisabled = computed(() => props.total === 0 || !!props.state.loading)
const expanded = ref(new Set())
const keyOf = row => typeof props.rowKey === 'function' ? props.rowKey(row) : row[props.rowKey]
watch(() => props.rows, rows => {
  const keys = new Set(rows.map(keyOf))
  expanded.value = new Set([...expanded.value].filter(key => keys.has(key)))
})
function toggleRow(row) {
  const key = keyOf(row)
  const next = new Set(expanded.value)
  next.has(key) ? next.delete(key) : next.add(key)
  expanded.value = next
}
function changePageSize(event) {
  const size = Number(event.target.value)
  if (!pageSizes.includes(size)) return
  emit('update:pageSize', size)
  emit('update:page', 1)
}
// Only presentation types are inspected; no business keys, sorting or slicing.
function alignment(column) {
  return column.align || (props.rows.some(row => typeof row[column.key] === 'number') ? 'right' : 'left')
}
const tableState = computed(() => props.rows.length
  ? { refreshFailed: props.state.refreshFailed || props.state.error }
  : { ...props.state, empty: props.state.empty || 'none' })
const resetFilters = () => { emit('update:page', 1); emit('reset-filters') }
</script>

<template>
  <section class="dm-module-table" :aria-label="title" :aria-busy="!!state.loading">
    <div class="dm-module-table-header">
      <h3 class="dm-module-table-title">{{ title }}</h3>
      <div v-if="$slots.toolbar || cleanupLabel" class="dm-module-table-toolbar">
        <slot name="toolbar" :cleanup-disabled="cleanupDisabled" />
        <button v-if="cleanupLabel" type="button" class="dm-table-button dm-table-cleanup"
          :disabled="cleanupDisabled" @click="emit('cleanup')">{{ cleanupLabel }}</button>
      </div>
    </div>
    <TableState v-if="rows.length && tableState.refreshFailed" v-bind="tableState" @retry="emit('retry')" />
    <div class="dm-table-scroll" role="region" :aria-label="title + '，可横向滚动'" tabindex="0">
      <table class="dm-table">
        <caption class="dm-table-sr">{{ title }}</caption>
        <thead>
          <tr>
            <th v-if="$slots.expand" scope="col" class="dm-table-control"><span class="dm-table-sr">详情</span></th>
            <th v-for="column in columns" :key="column.key" scope="col" :style="{ textAlign: alignment(column), width: typeof column.width === 'number' ? column.width + 'px' : column.width }">{{ column.label }}</th>
            <th v-if="$slots.rowActions" scope="col" class="dm-table-control">操作</th>
          </tr>
        </thead>
        <tbody v-if="rows.length">
          <template v-for="row in rows" :key="keyOf(row)">
            <tr>
              <td v-if="$slots.expand" class="dm-table-control">
                <button type="button" class="dm-table-button" :aria-expanded="expanded.has(keyOf(row))"
                  :aria-label="(expanded.has(keyOf(row)) ? '收起' : '展开') + '记录详情'" @click="toggleRow(row)">
                  <span class="mdi" :class="expanded.has(keyOf(row)) ? 'mdi-chevron-up' : 'mdi-chevron-down'" aria-hidden="true" />
                </button>
              </td>
              <td v-for="column in columns" :key="column.key" :style="{ textAlign: alignment(column) }">
                <slot :name="'cell-' + column.key" :row="row" :value="row[column.key]">{{ row[column.key] }}</slot>
              </td>
              <td v-if="$slots.rowActions" class="dm-table-control"><slot name="rowActions" :row="row" /></td>
            </tr>
            <tr v-if="$slots.expand && expanded.has(keyOf(row))" class="dm-table-expanded">
              <td :colspan="columns.length + 1 + ($slots.rowActions ? 1 : 0)"><slot name="expand" :row="row" /></td>
            </tr>
          </template>
        </tbody>
        <tbody v-else>
          <tr><td class="dm-table-state-cell" :colspan="Math.max(1, columns.length + ($slots.expand ? 1 : 0) + ($slots.rowActions ? 1 : 0))">
            <TableState v-bind="tableState" @retry="emit('retry')" @reset-filters="resetFilters" />
          </td></tr>
        </tbody>
      </table>
    </div>
    <footer class="dm-module-table-footer">
      <span>共 {{ total }} 条</span>
      <div v-if="total > 0" class="dm-table-pagination" role="navigation" :aria-label="title + '分页'">
        <label class="dm-table-page-size">每页
          <select :value="effectivePageSize" :disabled="!!state.loading" aria-label="每页条数" @change="changePageSize">
            <option v-for="size in pageSizes" :key="size" :value="size">{{ size }}</option>
          </select>条
        </label>
        <button type="button" class="dm-table-button" :disabled="currentPage <= 1 || !!state.loading" aria-label="上一页" @click="emit('update:page', currentPage - 1)">上一页</button>
        <span aria-live="polite">第 {{ currentPage }} / {{ pageCount }} 页</span>
        <button type="button" class="dm-table-button" :disabled="currentPage >= pageCount || !!state.loading" aria-label="下一页" @click="emit('update:page', currentPage + 1)">下一页</button>
      </div>
    </footer>
  </section>
</template>

<style scoped>
.dm-module-table { min-width: 0; max-width: 100%; overflow: hidden; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; color: var(--dm-text-body-color); font-size: var(--dm-text-body-size); font-weight: var(--dm-text-body-weight); line-height: var(--dm-text-body-line-height); }
.dm-module-table-header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 12px; }
.dm-module-table-title { margin: 0; overflow-wrap: anywhere; color: var(--dm-text-section-color); font-size: var(--dm-text-section-size); font-weight: var(--dm-text-section-weight); line-height: var(--dm-text-section-line-height); }
.dm-module-table-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.dm-table-scroll { max-width: 100%; overflow-x: auto; }
.dm-table { width: 100%; border-collapse: collapse; }
.dm-table th { padding: 6px 12px; white-space: nowrap; background: rgba(var(--v-theme-on-surface), var(--v-hover-opacity)); color: var(--dm-text-table-head-color); font-size: var(--dm-text-table-head-size); font-weight: var(--dm-text-table-head-weight); line-height: var(--dm-text-table-head-line-height); }
.dm-table td { padding: 6px 12px; min-width: 100px; max-width: 480px; overflow-wrap: anywhere; border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.dm-table .dm-table-control { width: 1%; min-width: 48px; white-space: nowrap; }
.dm-table .dm-table-state-cell { padding: 0; }
.dm-module-table-footer, .dm-table-pagination, .dm-table-page-size { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.dm-module-table-footer { justify-content: space-between; padding: 8px 12px; color: var(--dm-text-help-color); font-size: var(--dm-text-help-size); font-weight: var(--dm-text-help-weight); line-height: var(--dm-text-help-line-height); }
.dm-table-button, .dm-table-page-size select { min-height: 32px; padding: 4px 8px; border: 0; border-radius: 4px; color: rgb(var(--v-theme-primary)); background: transparent; font-family: inherit; font-size: var(--dm-text-button-size); font-weight: var(--dm-text-button-weight); line-height: var(--dm-text-button-line-height); cursor: pointer; }
.dm-table-page-size select { appearance: auto; background: rgb(var(--v-theme-surface)); color: var(--dm-text-body-color); }
.dm-table-button:disabled, .dm-table-page-size select:disabled { color: var(--dm-color-disabled); cursor: default; }
.dm-table-button:focus-visible, .dm-table-page-size select:focus-visible, .dm-table-scroll:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: -2px; }
.dm-table-sr { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
</style>
