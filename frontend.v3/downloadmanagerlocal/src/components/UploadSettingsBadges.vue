<script setup>
import { computed } from 'vue'
const props = defineProps({ value: { default: null } })
const tooltip = computed(() => props.value == null ? '未记录' : typeof props.value === 'object' ? JSON.stringify(props.value) : String(props.value))
function setting(label, bps, enabled) {
  const speed = bps == null ? '额度未知' : Number(bps) === 0 ? '不限速' : `${Number((Number(bps) / 1024 / 1024).toFixed(2))} MB/s`
  return { label: `${label} ${enabled === false ? '未启用' : speed}${enabled == null ? ' · 状态未知' : ''}`, color: enabled === false ? 'default' : 'primary' }
}
const badges = computed(() => {
  const value = props.value
  if (value == null) return []
  if (typeof value !== 'object') return [{ label: String(value), color: 'default' }]
  const result = []
  if ('upload_limit_bps' in value || 'upload_enabled' in value) result.push(setting('普通', value.upload_limit_bps, value.upload_enabled))
  if (value.alternate_upload_limit_bps != null || value.alternate_upload_enabled != null) result.push(setting('备用', value.alternate_upload_limit_bps, value.alternate_upload_enabled))
  if ('limit_bps' in value || 'enabled' in value) result.push(setting('单种', value.limit_bps, value.enabled))
  return result.length ? result : [{ label: '已记录', color: 'default' }]
})
</script>
<template>
  <span class="dm-upload-settings-badges" :title="tooltip" tabindex="0" :aria-label="tooltip">
    <VChip v-for="badge in badges" :key="badge.label" size="x-small" variant="tonal" :color="badge.color">{{ badge.label }}</VChip>
    <span v-if="!badges.length">—</span>
  </span>
</template>
<style scoped>
.dm-upload-settings-badges { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
.dm-upload-settings-badges:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 2px; }
</style>
