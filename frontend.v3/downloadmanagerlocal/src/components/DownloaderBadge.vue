<script setup>
import { computed } from 'vue'

/**
 * 下载器品牌徽标：品牌色圆标 + 实例名（如 QB1）。
 * Config.vue（转移任务列表）与 Page.vue（诊断/总览）复用同一组件；
 * 未知类型用通用图标；纯本地样式，不联网加载、不引入图标框架。
 */
const props = defineProps({
  name: { type: String, default: '' },
  type: { type: String, default: '' },
  size: { type: [Number, String], default: 20 },
})

const BRANDS = {
  qbittorrent: { text: 'Q', color: '#2f7ac0', label: 'qBittorrent' },
  transmission: { text: 'T', color: '#b52025', label: 'Transmission' },
  rtorrent: { text: 'R', color: '#5f7a8a', label: 'rTorrent' },
}

const brand = computed(() => BRANDS[String(props.type || '').toLowerCase()] || null)
const displayName = computed(() => props.name || '—')
const title = computed(() => `${displayName.value}${brand.value ? ` · ${brand.value.label}` : ''}`)
const markSize = computed(() => `${Number(props.size) || 20}px`)
</script>

<template>
  <span class="dm-downloader-badge" :title="title">
    <span
      v-if="brand"
      class="dm-downloader-badge-mark"
      :style="{ background: brand.color, width: markSize, height: markSize, fontSize: `calc(${markSize} * 0.6)` }"
    >{{ brand.text }}</span>
    <VIcon
      v-else
      icon="mdi-download-outline"
      class="dm-downloader-badge-mark dm-downloader-badge-mark--unknown"
      :style="{ width: markSize, height: markSize, fontSize: markSize }"
    />
    <span class="dm-downloader-badge-name">{{ displayName }}</span>
  </span>
</template>

<style scoped>
.dm-downloader-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.dm-downloader-badge-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  border-radius: 26%;
  color: #fff;
  font-weight: 700;
  line-height: 1;
}

.dm-downloader-badge-mark--unknown {
  color: var(--dm-color-secondary);
  background: rgba(var(--v-theme-on-surface), 0.08);
}

.dm-downloader-badge-name {
  font-size: var(--dm-text-badge-size);
  font-weight: var(--dm-text-badge-weight);
  line-height: var(--dm-text-badge-line-height);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
