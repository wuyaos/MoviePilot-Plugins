<script setup>
defineProps({
  siqi_extra: { type: Object, default: null },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['action'])

function run(action) {
  emit('action', { action })
}
</script>

<template>
  <v-card v-if="siqi_extra" flat class="rounded border">
    <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 bg-purple-lighten-5">
      <v-icon icon="mdi-snake" color="purple" size="small" class="mr-2" />
      思齐专属
    </v-card-title>
    <v-card-text class="pa-3">
      <v-list density="compact" class="pa-0">
        <v-list-item title="验证码状态">
          <template #append>
            <v-chip :color="siqi_extra.captcha_ready ? 'success' : 'grey'" size="small" variant="tonal">
              {{ siqi_extra.captcha_ready ? '有成熟作物' : '暂无成熟作物' }}
            </v-chip>
            <v-btn
              color="success"
              size="small"
              variant="text"
              class="ml-2"
              :loading="loading"
              :disabled="loading || !siqi_extra.captcha_ready"
              @click="run('harvest_captcha')"
            >
              验证码收获
            </v-btn>
          </template>
        </v-list-item>

        <v-divider />
        <v-list-item title="偷菜今日额度">
          <template #append>
            <v-chip :color="siqi_extra.steal_done_today ? 'success' : 'warning'" size="small" variant="tonal">
              {{ siqi_extra.steal_done_today ? '已完成 ✓' : '未完成' }}
            </v-chip>
            <v-btn
              v-if="!siqi_extra.steal_done_today"
              color="warning"
              size="small"
              variant="text"
              class="ml-2"
              :loading="loading"
              :disabled="loading"
              @click="run('steal')"
            >
              去偷菜
            </v-btn>
          </template>
        </v-list-item>

        <v-divider />
        <v-list-item title="点赞额度">
          <template #append>
            <v-chip :color="siqi_extra.like_done_today ? 'success' : 'warning'" size="small" variant="tonal">
              {{ siqi_extra.like_done_today ? '已完成 ✓' : '未完成' }}
            </v-chip>
            <v-btn
              v-if="!siqi_extra.like_done_today"
              color="pink"
              size="small"
              variant="text"
              class="ml-2"
              :loading="loading"
              :disabled="loading"
              @click="run('like')"
            >
              去点赞
            </v-btn>
          </template>
        </v-list-item>

        <v-divider />
        <v-list-item title="扩地可购数">
          <template #append>
            <v-chip color="info" size="small" variant="tonal">{{ siqi_extra.buy_slot_available ?? 0 }}</v-chip>
            <v-btn
              color="info"
              size="small"
              variant="text"
              class="ml-2"
              :loading="loading"
              :disabled="loading || Number(siqi_extra.buy_slot_available || 0) <= 0"
              @click="run('buy_slot')"
            >
              购买扩地
            </v-btn>
          </template>
        </v-list-item>
      </v-list>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.bg-purple-lighten-5 {
  background-color: rgba(156, 39, 176, 0.1) !important;
}

.text-subtitle-2 {
  font-size: 0.9rem !important;
  font-weight: 500 !important;
}

@media (prefers-color-scheme: dark) {
  .bg-purple-lighten-5 {
    background-color: rgba(156, 39, 176, 0.2) !important;
  }
}
</style>
