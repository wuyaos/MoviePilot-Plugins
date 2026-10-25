# Hhanclubrescueseed（憨憨保种区）

MoviePilot V3 插件，站点强耦合 hhanclub.net 憨憨 BT。

## 结构与运行

- `__init__.py`：插件入口；`init_plugin()` 与 `load_config()` 统一规范化 26 个配置键。
- 普通获取 `_check_seeding()`：抓取 `rescue.php?page=N`，先做列表页粗筛，再按完成率/连接时间条件读取详情下载者，最后按下载预算和实时槽位下载。
- 详情精筛使用 `GET viewpeerlist.php?id={torrent_id}&json=1`，一轮共享最多 15 次请求；失败、坏行和结构变化 fail-closed，并合并通知。`leechers.data` 少于 `count` 时记录 partial debug，但按已返回行判定。
- 历史任务 `_check_history_seeding()` 使用站点自动解析的当前 UID，保持独立历史页流程，不纳入普通获取的详情精筛。
- `_maintenance()` 仅处理应用层复核后确实带本插件标签的种子；qb/tr 标签写入统一使用 `set_torrent_tag`，删除还要求 hash 精确匹配。
- 治理常数集中在类顶部：`DISK_QUOTA_TARGET_RATIO=0.9`、`NO_UPLOAD_AVG_SPEED=1024`、`MAX_REMOVE_PER_RUN=5`。

## 26 个配置键

`enable` / `run_once` / `history_rescue_enabled` / `cron` / `monitor_cron` / `downloader` / `save_path` / `custom_tag` / `reward_tag` / `reward_hours` / `enable_notification` / `notify_on_zero_torrents` / `force_resume` / `auto_delete_enabled` / `delete_files` / `disk_quota_gb` / `stuck_days` / `seeding_count` / `torrent_size` / `download_limit` / `max_downloading` / `max_pages` / `min_downloaders` / `completion_ratio_max` / `connect_time_max_hours` / `free`。

`user_id` 为内部运行态，不是可写配置；`min_seeders`、`max_torrent_size_gb` 已删除；`all_downloaders` 仅为 API 辅助数据，不是配置键。默认 `custom_tag` 为「憨憨保种」，`monitor_cron` 为 `*/10 * * * *`，缺省 `completion_ratio_max` 为 20，显式清空两个详情阈值表示不启用精筛。

## 前端构建

- 从 `frontend.v3/hhanclubrescueseed/` 源码构建，禁止手工编辑 `plugins.v3/hhanclubrescueseed/dist/`。
- 构建依赖可使用源码目录下被 `.gitignore` 忽略的 `node_modules/`，不入库。
- 构建直接输出到 `plugins.v3/hhanclubrescueseed/dist/`；`distbak/` 保留迁移前备份，必须使用同一次构建生成的完整产物，不要混入开发壳文件。
