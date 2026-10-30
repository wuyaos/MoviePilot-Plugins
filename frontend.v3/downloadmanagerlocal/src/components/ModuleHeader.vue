<script setup>
import '../styles/dm-tokens.css'

defineProps({
  title: { type: String, required: true },
  icon: { type: String, default: 'mdi-view-module-outline' },
  showStatus: { type: Boolean, default: true },
  enabled: { type: Boolean, default: false },
  observing: { type: Boolean, default: false },
  running: { type: Boolean, default: false },
  fault: { type: [Boolean, String], default: false },
  badges: { type: Array, default: () => [] },
})
const tones = ['primary', 'secondary', 'success', 'warning', 'error']
</script>

<template>
  <header class="dm-module-header">
    <div class="dm-module-header-line">
      <VAvatar :color="fault ? 'error' : observing ? 'warning' : (enabled || running) ? 'primary' : undefined" variant="tonal" size="30" rounded="lg" class="dm-module-icon" :class="{ 'dm-module-icon--enabled': enabled }">
        <VIcon :icon="icon" size="17" aria-hidden="true" />
      </VAvatar>
      <h2 class="dm-module-title">{{ title }}</h2>
      <VChip v-if="showStatus" size="x-small" variant="tonal" :color="enabled ? 'success' : undefined" class="dm-module-status">{{ enabled ? '已启用' : '已禁用' }}</VChip>
      <VChip v-if="observing" size="x-small" variant="tonal" color="warning" class="dm-module-status">观察模式</VChip>
      <VChip v-if="running" size="x-small" variant="tonal" color="primary" class="dm-module-status" role="status">执行中</VChip>
      <VChip v-if="fault" size="x-small" variant="tonal" color="error" class="dm-module-status" role="status">故障{{ typeof fault === 'string' ? '：' + fault : '' }}</VChip>
    </div>
    <ul v-if="badges.length" class="dm-module-badges" aria-label="模块统计">
      <li v-for="(badge, index) in badges" :key="index" class="dm-module-stat"
        :class="tones.includes(badge.tone) ? 'dm-tone-' + badge.tone : ''">
        <span>{{ badge.label }}</span><span>{{ badge.value }}</span>
      </li>
    </ul>
  </header>
</template>

<style scoped>
.dm-module-header { min-width: 0; color: var(--dm-text-body-color); }
.dm-module-header-line { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.dm-module-icon { flex: none; }
.dm-module-title { margin: 0; overflow-wrap: anywhere; font-size: var(--dm-text-title-size); font-weight: var(--dm-text-title-weight); line-height: var(--dm-text-title-line-height); color: var(--dm-text-title-color); }
.dm-module-status, .dm-module-stat { font-size: var(--dm-text-badge-size); font-weight: var(--dm-text-badge-weight); line-height: var(--dm-text-badge-line-height); }
.dm-module-badges { display: flex; flex-wrap: wrap; gap: 8px; min-width: 0; margin: 8px 0 0; padding: 0; list-style: none; }
.dm-module-stat { display: inline-flex; flex: none; align-items: center; gap: 6px; min-width: 0; max-width: 100%; box-sizing: border-box; padding: 2px 0; background: transparent; }
.dm-module-stat > span { min-width: 0; overflow-wrap: anywhere; }
.dm-tone-primary { color: rgb(var(--v-theme-primary)); }
.dm-tone-secondary { color: var(--dm-color-secondary); }
.dm-tone-success { color: rgb(var(--v-theme-success)); }
.dm-tone-warning { color: var(--dm-color-warning); }
.dm-tone-error { color: var(--dm-color-error); }
</style>
