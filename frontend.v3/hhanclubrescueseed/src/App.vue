<template>
  <div class="app-container">
    <v-app>
      <v-app-bar color="primary" app>
        <v-app-bar-title>憨憨保种区 组件开发预览</v-app-bar-title>
      </v-app-bar>

      <v-main>
        <v-container>
          <v-tabs v-model="activeTab" bg-color="primary">
            <v-tab value="page">详情页面</v-tab>
            <v-tab value="config">配置页面</v-tab>
          </v-tabs>

          <v-window v-model="activeTab" class="mt-4">
            <v-window-item value="page">
              <h2 class="text-h5 mb-4">Page组件</h2>
              <div class="component-preview">
                <PageComponent :api="mockApi" @action="handleAction"></PageComponent>
              </div>
            </v-window-item>

            <v-window-item value="config">
              <h2 class="text-h5 mb-4">Config组件</h2>
              <div class="component-preview">
                <ConfigComponent :api="mockApi" :initial-config="initialConfig" @save="handleConfigSave" @close="handleClose"></ConfigComponent>
              </div>
            </v-window-item>
          </v-window>
        </v-container>
      </v-main>

      <v-footer app color="primary" class="text-center d-flex justify-center">
        <span class="text-white">MoviePilot 模块联邦开发壳 ©{{ new Date().getFullYear() }}</span>
      </v-footer>
    </v-app>

    <!-- 通知弹窗 -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="snackbar.timeout">
      {{ snackbar.text }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar.show = false"> 关闭 </v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import PageComponent from './components/Page.vue'
import ConfigComponent from './components/Config.vue'

// 活动标签页
const activeTab = ref('page')

// 配置初始值（与插件 defaultConfig 对齐）
const initialConfig = {
  id: 'Hhanclubrescueseed',
  name: '憨憨保种区',
  enable: false,
  cron: '',
  downloader: '',
  seeding_count: '1-3',
  torrent_size: '',
  download_limit: 5,
  all_downloaders: [
    { title: 'qbittorrent', value: 'qbittorrent' },
    { title: 'transmission', value: 'transmission' },
  ],
  save_path: '',
  run_once: false,
  custom_tag: '',
  enable_notification: true,
  notify_on_zero_torrents: true,
  history_rescue_enabled: false,
  user_id: '',
  force_resume: false,
  max_pages: 5,
}

// 开发用 api mock：不请求后端，直接返回空数据
const mockApi = {
  get: async () => ({ success: true, data: [] }),
  post: async () => ({ success: true, data: null }),
}

// 通知状态
const snackbar = reactive({
  show: false,
  text: '',
  color: 'success',
  timeout: 3000,
})

// 显示通知
function showNotification(text, color = 'success') {
  snackbar.text = text
  snackbar.color = color
  snackbar.show = true
}

// 处理详情页面操作
function handleAction() {
  showNotification('Page组件触发了action事件')
}

// 处理配置保存
function handleConfigSave(config) {
  console.log('配置已保存:', config)
  showNotification('配置已保存')
}

// 处理关闭
function handleClose() {
  showNotification('收到close事件')
}
</script>

<style scoped>
/* 为了使测试应用更美观 */
.app-container {
  block-size: 100vh;
  inline-size: 100vw;
}

.component-preview {
  overflow: hidden;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
}
</style>
