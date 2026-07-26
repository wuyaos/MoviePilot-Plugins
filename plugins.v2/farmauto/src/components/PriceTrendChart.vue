<script setup>
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  trends: { type: Object, default: () => ({}) },
  crops: { type: Object, default: () => ({}) },
})

const chartElement = ref(null)
let chart
let resizeObserver

const trendEntries = computed(() => Object.entries(props.trends || {})
  .map(([cropKey, samples]) => [cropKey, Array.isArray(samples) ? samples.slice(-20) : []])
  .filter(([, samples]) => samples.length))
const hasData = computed(() => trendEntries.value.length > 0)

function sampleTime(timestamp) {
  const numericTimestamp = Number(timestamp)
  const date = new Date(numericTimestamp < 1e12 ? numericTimestamp * 1000 : numericTimestamp)
  if (Number.isNaN(date.getTime())) return String(timestamp ?? '')
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function renderChart() {
  if (!chartElement.value || !hasData.value) {
    chart?.clear()
    return
  }
  if (!chart) chart = echarts.init(chartElement.value)

  const labels = [...new Set(trendEntries.value.flatMap(([, samples]) => (
    samples.map(sample => sampleTime(sample?.[0]))
  )))]
  const series = trendEntries.value.map(([cropKey, samples]) => {
    const pricesByTime = new Map(samples.map(sample => [sampleTime(sample?.[0]), sample?.[1]]))
    return {
      name: props.crops?.[cropKey]?.name || cropKey,
      type: 'line',
      smooth: true,
      showSymbol: false,
      connectNulls: true,
      data: labels.map(label => pricesByTime.get(label) ?? null),
    }
  })

  chart.setOption({
    animationDuration: 300,
    color: ['#4caf50', '#ff9800', '#2196f3', '#9c27b0', '#795548', '#009688', '#f44336', '#607d8b'],
    tooltip: { trigger: 'axis' },
    legend: { type: 'scroll', bottom: 0 },
    grid: { left: 48, right: 20, top: 24, bottom: 54 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels,
      axisLabel: { hideOverlap: true },
    },
    yAxis: {
      type: 'value',
      name: '价格',
      scale: true,
      splitLine: { lineStyle: { type: 'dashed' } },
    },
    series,
  }, true)
  chart.resize()
}

watch(() => [props.trends, props.crops], async () => {
  await nextTick()
  renderChart()
}, { deep: true })

onMounted(async () => {
  await nextTick()
  renderChart()
  if (typeof ResizeObserver !== 'undefined' && chartElement.value) {
    resizeObserver = new ResizeObserver(() => chart?.resize())
    resizeObserver.observe(chartElement.value)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
  chart = undefined
})
</script>

<template>
  <div class="price-trend-chart">
    <div v-show="hasData" ref="chartElement" class="price-trend-chart__canvas" />
    <div v-if="!hasData" class="price-trend-chart__empty text-medium-emphasis">
      <v-icon icon="mdi-chart-line" size="40" class="mb-2 opacity-50" />
      <div>暂无市场波动数据</div>
    </div>
  </div>
</template>

<style scoped>
.price-trend-chart {
  position: relative;
  block-size: 300px;
  min-block-size: 300px;
  min-inline-size: 0;
}

.price-trend-chart__canvas {
  inline-size: 100%;
  block-size: 100%;
}

.price-trend-chart__empty {
  display: flex;
  block-size: 100%;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  border-radius: 4px;
  background: rgba(var(--v-theme-on-surface), 0.04);
}
</style>
