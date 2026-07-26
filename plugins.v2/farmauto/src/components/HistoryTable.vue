<script setup>
import { computed } from 'vue'

const props = defineProps({
  history: { type: Array, default: () => [] },
})

const rows = computed(() => (Array.isArray(props.history) ? props.history : []).slice(-20).reverse())
const statusMeta = {
  completed: { text: '已完成', color: 'success' },
  partial: { text: '部分完成', color: 'warning' },
  failed: { text: '失败', color: 'error' },
}

function getStatus(status) {
  return statusMeta[status] || { text: status || '—', color: 'grey' }
}
</script>

<template>
  <v-card flat class="rounded border h-100">
    <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 bg-grey-lighten-5">
      <v-icon icon="mdi-history" color="grey" size="small" class="mr-2" />
      执行记录
    </v-card-title>

    <v-table v-if="rows.length" density="compact">
      <thead>
        <tr>
          <th>时间</th>
          <th>站点</th>
          <th>操作</th>
          <th class="text-center">利润</th>
          <th class="text-center">状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(item, index) in rows" :key="`${item.time}-${item.site}-${index}`">
          <td class="text-no-wrap">{{ item.time || '—' }}</td>
          <td>{{ item.site || '—' }}</td>
          <td>{{ item.action || '—' }}</td>
          <td class="text-center">{{ item.profit ?? 0 }}</td>
          <td class="text-center">
            <v-chip :color="getStatus(item.status).color" size="x-small" variant="tonal">
              {{ getStatus(item.status).text }}
            </v-chip>
          </td>
        </tr>
      </tbody>
    </v-table>
    <v-card-text v-else class="text-center text-medium-emphasis py-6">暂无记录</v-card-text>
  </v-card>
</template>

<style scoped>
.bg-grey-lighten-5 {
  background-color: rgba(158, 158, 158, 0.1) !important;
}

.text-subtitle-2 {
  font-size: 0.9rem !important;
  font-weight: 500 !important;
}

@media (prefers-color-scheme: dark) {
  .bg-grey-lighten-5 {
    background-color: rgba(158, 158, 158, 0.16) !important;
  }
}
</style>
