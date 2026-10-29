# DownloadManagerLocal V3 前端

## 入口与验证
- 权威规格：`../../docs/downloadmanagerlocal-final-implementation-spec.md`；公共组件只展示，不计算统计、不筛选业务、不判定 H&R、不请求 API。
- `src/components/Config.vue` / `Page.vue` 是联邦入口；`api.js` 保留宿主请求契约；`DownloaderBadge.vue` 表示下载器身份，业务页应通过单元格 slot 复用。
- `src/components/ModuleHeader.vue` / `ModuleTable.vue` / `TableState.vue` 为待接线的公共展示骨架；`src/styles/dm-tokens.css` 由组件 import，不在 JS 中注入样式字符串。
- 在本目录执行 `node --test tests/*.test.mjs` 和 `npm run build`，不得新增依赖。
- `vite.config.js` 将联邦产物写到 `../../plugins.v3/downloadmanagerlocal/dist/`；不要把开发 harness 暴露为宿主组件。
- 公共组件在 Page 接线前不会进入联邦产物，标准 build 不能单独作为新组件的验收门禁：必须跑真实 SFC 编译/渲染测试，并通过系统临时目录的消费入口构建（真实引用三个组件、产出 JS/CSS，outDir 不得指向插件 dist）。

## 测试 harness
- 沿用 `node:test`，不依赖 bundler 或真实 DOM；`tests/config-browser.html` 是人工浏览器 harness，不作为自动验收结果。
- `tests/helpers/load-sfc.mjs` 以现有传递依赖 `@vue/compiler-sfc` 编译真实 SFC/template，递归编译子 SFC，以 `vue/server-renderer` 检查真实 HTML；无 DOM 交互用 Vue `createRenderer` 的内存 host 验证事件与响应式展开。
- Node harness 仅剥离 CSS import，并独立编译 scoped style；临时模块位于本地 node_modules 下（保证裸模块解析），加载后清理。CSS/token 结构断言不是浏览器 computed style 验证。
- 接线后另验宿主联邦加载、窄屏滚动、键盘焦点与深浅主题；不要用 SSR/构建冒充这些验收。

## 组件契约
| 组件 | Props | Events | Slots |
| --- | --- | --- | --- |
| ModuleHeader | `title: string` 必填；`icon: string` 为现有 mdi 类名；`enabled/observing/running: boolean` 默认 false；`fault: boolean / string` 默认 false；`badges: {label,value,tone?}[]` 默认 [] | 无 | 无 |
| TableState | `loading: boolean`；`error/refreshFailed: boolean / string`；`empty` 为 `'' / none / filtered / not-scanned / no-candidates / disabled` | `retry`、`reset-filters`，无 payload | 无 |
| ModuleTable | `title: string` 必填；`columns: {key,label,align?,width?}[]`；`rows: object[]`；`rowKey: string / ((row)=>string或number)` 默认 `'id'`；`total: number` 默认 0；`page: number` 默认 1；`pageSize: 20 / 50 / 100` 默认 20；`state` 同 TableState props；`cleanupLabel: string` 默认空 | `update:page(number)`、`update:pageSize(number)`、`retry`、`reset-filters`、`cleanup` | `toolbar({cleanupDisabled})`、`rowActions({row})`、`expand({row})`、`cell-{key}({row,value})` |

- `badges.tone` 仅支持 primary/secondary/success/warning/error；未知 tone 使用中性色。启停、观察、执行、故障均有文字，不只依赖颜色。
- TableState 优先级为 loading → error → refreshFailed → empty；首次状态/空态区最小高度 140px，刷新失败为紧凑提示条。五种空态分别显示暂无记录、筛选无结果、尚未扫描、扫描无候选、模块已关闭。
- ModuleTable 收到非空 rows 时始终保留旧数据（即使 disabled/loading/error）；error 视为刷新失败提示。没有 rows 时默认 empty=none。调用方负责区分“首次”与“已有空结果刷新”。
- rows 已由后端先筛选后分页；组件不二次 slice。total 是当前查询总数；rowKey 必须存在且在结果中唯一、跨刷新稳定，不得用数组下标。
- align 接受 CSS left/center/right；缺省时 JS number 列自动右对齐，格式化数值字符串及空表数字列须显式 `align: 'right'`。width 为 px 数字或合法 CSS 宽度字符串。
- 页码受控：调用方绑定 page/pageSize 并据事件请求后端；改每页条数先发 update:pageSize，再发 update:page(1)。非法 pageSize 验证警告并按 20 展示；UI 只允许 20/50/100。
- 重置筛选先发 update:page(1)，再发 reset-filters；调用方在一次请求中应用新筛选与分页，避免各监听器重复发请求。
- 没有 rowActions/expand slot 时不渲染对应列；expand slot 由可键盘操作按钮开关，替换 rows 会丢弃不再存在的展开键。
- 清理入口默认不渲染；仅在实际业务支持并接入 `@cleanup` 确认流程后传 cleanupLabel（如“清理记录”，不可泛化为“清理”）。total=0 或 loading 时禁用；不在组件内做删除/确认/API 调用。
- 自定义 toolbar 清理按钮必须绑定 slot 的 cleanupDisabled；业务确认范围/数量不能用当前页 rows.length 冒充后端总数。

## 样式与宿主边界
- token 仅挂在 `.dm-config` / `.dm-page` 及三个公共组件根类，子组件样式必须 scoped 且使用 dm- 前缀；禁止全局通配字号规则或修改宿主/Tab 样式。
- 文字使用规格第 2 节对应角色的 size/weight/line-height/color token；次要、禁用、warning/error 共用语义 token，颜色只引用 Vuetify 主题变量。
- 窄屏仍是同一张表横向滚动，不另建业务卡片；外层细边框不再套一层 v-table 边框。
- 标准 save 事件必然关闭宿主配置弹窗；公共骨架不处理保存/关闭，不新增保存 API 或模拟不关窗。
