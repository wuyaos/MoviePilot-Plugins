# ui/ Vuetify 表单与页面

## 一句话职责
构建 `get_form()` 与 `get_page()` 返回的 Vuetify JSON 树，替代原插件 1262 行 `get_form` 与 357 行 `get_page` 巨方法。

## Input / Output / Pos
- **Input**：PluginConfig 字段、媒体库/用户/字体预设列表
- **Output**：`(components, defaults)` 元组（form）或 `List[dict]` 组件树（page）
- **Pos**：`plugins.v2/covergen/ui/`，被 `__init__.py` 的 `get_form()` `get_page()` 调用

## Files
- `form_utils.py` — Vuetify 组件工厂（`v_row` `v_col` `v_select` `v_switch` `v_text` `v_alert` `v_tabs` `v_window` `v_card` `v_cron` `v_btn` `v_textarea`）
- `form.py` — `build_form()` + 6 个 `_build_*_tab` 函数（基础/标题/风格/字体/过滤/其他，含历史保留配置默认值）
- `page.py` — `build_page()` + 详情页区块（生成、历史首行展示/更多折叠、最近执行按运行汇总列表）

## 更新条件
新增配置字段、调整表单分 tab 结构、变更页面布局时同步更新本目录文件与文件头注释。
