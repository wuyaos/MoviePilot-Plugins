<script setup>
import { computed } from 'vue'
const props = defineProps({ record: { type: Object, required: true } })
const labels = {
  hash: 'Hash', torrent_hash: 'Hash', source_hash: '源 Hash', target_hash: '目的 Hash',
  name: '完整名称', source_name: '源种子名称', original_name: '原始名称', after_name: '命名后',
  reason: '原因', error: '异常', message: '说明', archive_reason: '归档原因',
  from_path: '源数据路径', to_path: '目的数据路径', torrent_path: '种子文件目录',
  source_downloader: '源下载器', target_downloader: '目的下载器', downloader_id: '下载器', downloader: '下载器',
  site: '站点', status_text: '考核状态', phase: '阶段', deleted: '下载器中缺失',
  required_hours: '要求做种时长', seeding_time: '当前做种时长', ratio: '分享率',
  rule_source: '规则来源', missing_reason: '缺失原因', created_at: '创建时间', updated_at: '更新时间',
  source: '来源', scanned: '扫描', cleaned: '清理', failed: '失败', skipped: '跳过',
  frompath: '源数据路径', topath: '目的数据路径', fromtorrentpath: '种子文件目录', fromtorrentpath_exists: '种子目录存在',
  archived_at: '归档时间', last_failed_at: '最近失败时间', fail_count: '失败次数', category: '分类', category_label: '分类名称',
}
const fields = computed(() => Object.entries(labels).filter(([key]) => props.record[key] != null)
  .map(([key, label]) => ({ key, label, value: typeof props.record[key] === 'boolean' ? (props.record[key] ? '是' : '否') : props.record[key] })))
</script>
<template>
  <dl class="dm-record-details">
    <template v-for="field in fields" :key="field.key"><dt>{{ field.label }}</dt><dd>{{ field.value }}</dd></template>
  </dl>
</template>
<style scoped>
.dm-record-details { display: grid; grid-template-columns: minmax(80px, auto) minmax(0, 1fr); gap: 6px 12px; margin: 4px 0; }
.dm-record-details dt { color: var(--dm-text-help-color); }
.dm-record-details dd { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
