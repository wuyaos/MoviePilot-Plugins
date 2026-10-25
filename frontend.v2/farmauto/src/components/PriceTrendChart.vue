<script setup>
import * as echarts from 'echarts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  trends: { type: Object, default: () => ({}) },
  crops: { type: Object, default: () => ({}) },
})

const CHART_COLORS = [
  '#F44336', '#E91E63', '#9C27B0', '#673AB7', '#3F51B5',
  '#2196F3', '#03A9F4', '#00BCD4', '#009688', '#4CAF50',
  '#8BC34A', '#CDDC39', '#FFEB3B', '#FFC107', '#FF9800',
  '#FF5722', '#795548', '#9E9E9E', '#607D8B',
]

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
    const idx = trendEntries.value.findIndex(([k]) => k === cropKey)
    return {
      name: props.crops?.[cropKey]?.name || cropKey,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      showSymbol: true,
      connectNulls: true,
      data: labels.map(label => pricesByTime.get(label) ?? null),
      lineStyle: { width: 3 },
      itemStyle: { color: CHART_COLORS[idx % CHART_COLORS.length] },
    }
  })

  const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
    || window.matchMedia('(prefers-color-scheme: dark)').matches
  const labelColor = isDark ? '#ccc' : '#333'
  const axisLineColor = isDark ? '#555' : '#e0e0e0'
  const axisLabelColor = isDark ? '#aaa' : '#999'
  const splitColor = isDark ? '#444' : '#eee'

  chart.setOption({
    animationDuration: 300,
    color: CHART_COLORS,
    tooltip: {
      trigger: 'axis',
      appendToBody: true,
      padding: 10,
      backgroundColor: isDark ? 'rgba(30,30,30,0.95)' : 'rgba(255,255,255,0.9)',
      borderColor: isDark ? '#555' : '#ccc',
      textStyle: { color: isDark ? '#eee' : '#333' },
      extraCssText: 'box-shadow: 0 0 10px rgba(0, 0, 0, 0.1); border-radius: 4px;',
      formatter: (params) => {
        if (!params || !params.length) return ''
        let res = `<div style="font-weight:600;margin-bottom:6px">${params[0].name}</div>`
        params.forEach(param => {
          const val = param.value
          if (val == null) return
          const cropName = param.seriesName
          const color = param.color
          const cropEntry = Object.entries(props.crops || {}).find(([, c]) => (c?.name) === cropName)
          const cost = cropEntry ? Number(cropEntry[1]?.cost) : 0
          let fluctuationStr = ''
          if (cost > 0) {
            const pct = ((val - cost) / cost) * 100
            const sign = pct > 0 ? '+' : ''
            const colorClass = pct > 0 ? '#F44336' : (pct < 0 ? '#4CAF50' : '#999')
            fluctuationStr = ` <span style="color:${colorClass}; font-size:0.9em;">(${sign}${pct.toFixed(2)}%)</span>`
          }
          res += `<div style="display:flex; align-items:center; justify-content:space-between; margin:2px 0;">
            <div><span style="display:inline-block;margin-right:5px;border-radius:10px;width:10px;height:10px;background-color:${color};"></span><span>${cropName}</span></div>
            <span style="margin-left:10px; font-weight:bold;">${val}${fluctuationStr}</span>
          </div>`
        })
        return res
      },
    },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '10%', containLabel: true },
    legend: {
      data: series.map(s => s.name),
      type: 'scroll',
      bottom: 0,
      icon: 'roundRect',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { fontSize: 11, color: labelColor },
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: labels,
      axisLine: { lineStyle: { color: axisLineColor } },
      axisLabel: { color: axisLabelColor, fontSize: 10, hideOverlap: true },
    },
    yAxis: {
      type: 'value',
      name: '价格',
      scale: true,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { type: 'dashed', color: splitColor } },
      axisLabel: { color: axisLabelColor, fontSize: 10 },
      nameTextStyle: { color: axisLabelColor },
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
