# frontend.v3

MoviePilot V3 插件前端源码目录。与本层 `plugins.v3/` 按插件名一一映射。

## Input / Output / Pos
- Input: 插件后端提供的 REST API 与配置数据。
- Output: Vite + Vue3 前端源码工程；构建产物直接输出到 `plugins.v3/<插件>/dist/`，迁移前旧产物可保留在 `distbak/`。
- Pos: 仅存放前端源码；不存放 Python 后端代码。`node_modules/` 仅作本地构建缓存，不入库。

## 约定
- 目录名与 `plugins.v3/` 中对应插件目录一致（小写）。
- 每个插件一个独立 Vite 工程：`package.json`、`vite.config.js`、`src/`，使用 `@originjs/vite-plugin-federation` 暴露 `Page`/`Config`/`Dashboard` 组件，vue/vuetify 设为 singleton 共享、不打包。
- 构建产物必须包含 `dist/assets/remoteEntry.js`，并直接作为后端插件运行产物打包。
- 仍使用 JSON 表单的插件不在本目录创建空工程；同一插件只保留一份前端源码，不在 `frontend.v3` 与插件目录重复维护。
