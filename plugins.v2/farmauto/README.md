# FarmAuto 农场自动化 Pro

MoviePilot V2 多站点农场自动化插件。自动收获、补种、盈利出售与临期出售均可独立控制，支持价格趋势、仓库分页、思齐 OCR 一键收获/偷菜/点赞等能力，并提供 Vue 联邦工作台。

## 功能

- 多站点统一调度（PlayLet / NovaHD / 好学 / 拾刻 / 包子 / 思齐）
- 统一自动运营：按独立开关执行收获、补种、盈利出售和临期出售
- 盈利出售仅在区间 `[min, max]` 内执行，临期出售由独立开关和阈值控制
- 价格趋势滚动记录（每物品最近 20 采样）与图表展示
- 单站策略覆盖（JSON，按站覆盖自动化开关/proxy/利润率/dry_run）
- 拾刻批量出售（batch_sell）降低请求频次
- 思齐原生一键收获（OCR 开启时优先、失败逐格降级）、一键种空地、偷菜/点赞每日限额和扩地
- Vue 联邦工作台：站 Tab、价格趋势图、作物/动物区、仓库表、菜市场表、执行记录、思齐专属区、手动操作

## 自动化开关

| 开关 | 行为 |
|---|---|
| `auto_harvest` | 收获所有成熟作物 |
| `auto_plant` | 仅对明确空位补种/养殖 |
| `auto_sell` | 在盈利区间内出售真实仓库库存 |
| `expiry_sale` | 对达到临期阈值的库存强制出售 |

## Vue 工作台

通过模块联邦暴露 `Page` / `Config` / `AppPage` / `Dashboard` 组件，由 MoviePilot v2.14.6+ 宿主加载。详情弹窗内提供完整工作台。

### 构建

依赖与构建在仓库外执行，避免污染插件目录：

```bash
# 在临时目录构建
BUILD=/tmp/farmauto-build
mkdir -p $BUILD
cp package.json vite.config.js index.html src -t $BUILD/
cd $BUILD
npm install --no-audit --no-fund
npm run build
# 产物复制回插件目录
cp -r dist /path/to/plugins.v2/farmauto/
```

`dist/assets` 由后端 `get_render_mode` 声明加载。

## 参考声明

本插件在实现过程中参考了以下项目：

- **[jxxghp/MoviePilot-Plugins](https://github.com/jxxghp/MoviePilot-Plugins)** `brushflow`：Vue 模块联邦架构、`get_render_mode` 契约、4 组件壳结构、vite 联邦配置与构建产物组织方式。
- **[KoWming/MoviePilot-Plugins](https://github.com/KoWming/MoviePilot-Plugins)** 农场系列（`playletfram` / `novahdfram` / `magicfram` / `skitfarm` / `siqifram`）：站点页面解析、菜市场/仓库/作物状态展示布局、价格波动图表、临期出售、思齐验证码与偷菜点赞交互的 UI 设计。
- **[bfjy2024/MoviePilot-Plugins](https://github.com/bfjy2024/MoviePilot-Plugins)** `farmauto`：原始多站点适配器结构与农场任务调度思路。

感谢上述项目的作者。

## 插件标识

- 目录：`plugins.v2/farmauto/`
- 入口类（MP 插件 ID）：`FarmAuto`
- 配置前缀：`farmauto_`
- 当前版本：`3.0`

## 模块结构

```
plugins.v2/farmauto/
├── __init__.py            # 入口：配置/调度/API/事件/Vue 声明
├── core/
│   ├── models.py          # 数据模型
│   ├── http_client.py     # 统一 HTTP（重试/代理/限速）
│   ├── strategy.py        # 盈利区间/临期决策（纯函数）
│   ├── executor.py        # 单站编排+思齐执行层
│   ├── trend.py           # 价格趋势存储
│   ├── captcha.py         # OCR 识别器
│   └── reporting.py       # 通知/面板 VNode（后备）
├── sites/                 # 站点适配（base + 6 站）
├── src/                   # Vue 联邦源码
│   └── components/
│       ├── FarmWorkbench.vue      # 工作台主体
│       ├── PriceTrendChart.vue    # echarts 趋势图
│       ├── CropArea.vue           # 作物/动物区
│       ├── WarehouseTable.vue     # 仓库表
│       ├── MarketTable.vue        # 菜市场表
│       ├── HistoryTable.vue       # 执行记录
│       ├── SiqiPanel.vue          # 思齐专属区
│       └── (AppPage/Page/Config/Dashboard.vue 联邦壳)
├── dist/assets/           # 构建产物（联邦 remoteEntry）
└── tests/                 # 离线 mock 测试
```

## 站点清单

| 站点 | ID | 能力 |
|---|---|---|
| PlayLet | `playlet` | 一键收获、临期出售、仓库分页 |
| NovaHD | `novahd` | 一键收获、临期出售、仓库分页 |
| 好学 | `haoxue` | 一键收获、临期出售、仓库分页 |
| 拾刻 | `skit` | 一键收获、临期出售、仓库分页、批量出售 |
| 包子 | `baozi` | 一键收获 |
| 思齐 | `siqi` | 原生一键收获（OCR）/逐格降级/一键种空地/偷菜/点赞/扩地 |

## 安全

- Cookie 仅从 MoviePilot 站点管理读取，不写入日志/API/通知
- 思齐高风险行为（偷菜/点赞/扩地/验证码自动提交）默认全部关闭
- 手动操作 API 受 `dry_run` 开关保护

## 校验

```bash
find plugins.v2/farmauto -name '*.py' -print0 | xargs -0 -n1 python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())'
cd plugins.v2/farmauto && python3 -m pytest tests/ -q
python3 -m json.tool package.v2.json >/dev/null
```
