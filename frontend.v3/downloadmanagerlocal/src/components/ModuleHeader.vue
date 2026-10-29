<script setup>
import '../styles/dm-tokens.css'

defineProps({
  title: { type: String, required: true },
  icon: { type: String, default: 'mdi-view-module-outline' },
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
      <span class="mdi dm-module-icon" :class="[icon, { 'dm-module-icon--enabled': enabled }]" aria-hidden="true" />
      <h2 class="dm-module-title">{{ title }}</h2>
      <span class="dm-module-status">{{ enabled ? '已启用' : '已禁用' }}</span>
      <span v-if="observing" class="dm-module-status dm-tone-warning">观察模式</span>
      <span v-if="running" class="dm-module-status dm-tone-primary" role="status">执行中</span>
      <span v-if="fault" class="dm-module-status dm-tone-error" role="status">故障{{ typeof fault === 'string' ? '：' + fault : '' }}</span>
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
.dm-module-icon { color: var(--dm-color-disabled); font-size: 20px; line-height: 24px; }
.dm-module-icon--enabled { color: rgb(var(--v-theme-primary)); }
.dm-module-title { margin: 0; overflow-wrap: anywhere; font-size: var(--dm-text-title-size); font-weight: var(--dm-text-title-weight); line-height: var(--dm-text-title-line-height); color: var(--dm-text-title-color); }
.dm-module-status, .dm-module-stat { font-size: var(--dm-text-badge-size); font-weight: var(--dm-text-badge-weight); line-height: var(--dm-text-badge-line-height); }
.dm-module-status { color: var(--dm-color-secondary); }
.dm-module-badges { display: flex; flex-wrap: wrap; gap: 8px; min-width: 0; margin: 8px 0 0; padding: 0; list-style: none; }
.dm-module-stat { display: inline-flex; flex: none; align-items: center; gap: 6px; min-width: 0; max-width: 100%; box-sizing: border-box; padding: 2px 8px; border-radius: 4px; background: rgba(var(--v-theme-on-surface), var(--v-hover-opacity)); }
.dm-module-stat > span { min-width: 0; overflow-wrap: anywhere; }
.dm-tone-primary { color: rgb(var(--v-theme-primary)); }
.dm-tone-secondary { color: var(--dm-color-secondary); }
.dm-tone-success { color: rgb(var(--v-theme-success)); }
.dm-tone-warning { color: var(--dm-color-warning); }
.dm-tone-error { color: var(--dm-color-error); }
</style>
