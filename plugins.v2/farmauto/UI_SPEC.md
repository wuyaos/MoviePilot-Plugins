# FarmAuto Vue UI 布局规范

> 本文件为 `plugins.v2/farmauto/` 前端实现规范，开发过程中实时查询对齐。

---

## 一、整体架构

### 文件结构
```
src/components/
├── FarmWorkbench.vue       # 通用站主组件（入口）
├── SiqiWorkbench.vue       # 思齐站专用组件
├── PriceTrendChart.vue     # echarts 价格趋势图
├── CropArea.vue            # 作物/动物区
├── WarehouseTable.vue      # 仓库表（含一键出售确认弹窗）
├── MarketTable.vue         # 菜市场表（含波动幅度）
├── HistoryTable.vue       # 执行记录表
├── AppPage.vue             # 联邦壳（侧栏入口）
├── Page.vue                # 联邦壳（详情弹窗）
├── Config.vue              # 联邦壳（配置弹窗）
├── Dashboard.vue           # 联邦壳（仪表板）
└── FarmConfigForm.vue      # 配置表单
```

### 渲染分发
```vue
<!-- FarmWorkbench.vue -->
<SiqiWorkbench v-if="selectedSiteId === 'siqi'" ... />
<!-- 否则渲染通用站布局 -->
```

### 联邦契约
```python
@staticmethod
def get_render_mode() -> Tuple[str, str]:
    return "vue", "dist/assets"
```
- Page/Config 均**不 emit layout**，用 MoviePilot 默认弹窗尺寸（约 80rem）
- 构建产物在 `dist/assets/`，仓库外构建后复制回仓库

---

## 二、通用站布局（4 行）

```
┌─ 第1行 ──────────────────────────────────────────┐
│ [魔力值]  [收获]  [操作数]                         │  3卡均分 md=4
├─ 第2行 ──────────────────────────────────────────┤
│ [菜市场价格波动 echarts]  [菜市场表]               │  2列 md=6
├─ 第3行 ──────────────────────────────────────────┤
│ [农作物种植区]  [动物养殖区]                       │  2列 md=6
├─ 第4行 ──────────────────────────────────────────┤
│ [仓库]  [执行记录]                                 │  2列 md=6
└───────────────────────────────────────────────────┘
```

### 组件挂载
```vue
<!-- 第1行 -->
<v-row dense class="mb-3">
  <v-col cols="12" md="4"> 统计卡: 魔力值 </v-col>
  <v-col cols="12" md="4"> 统计卡: 收获 </v-col>
  <v-col cols="12" md="4"> 统计卡: 操作数 </v-col>
</v-row>

<!-- 第2行 -->
<v-row dense class="mb-3">
  <v-col cols="12" md="6"> <PriceTrendChart /> </v-col>
  <v-col cols="12" md="6"> <MarketTable /> </v-col>
</v-row>

<!-- 第3行 -->
<v-row dense class="mb-3">
  <v-col cols="12" md="6"> <CropArea title="农作物种植区" /> </v-col>
  <v-col cols="12" md="6"> <CropArea title="动物养殖区" /> </v-col>
</v-row>

<!-- 第4行 -->
<v-row dense>
  <v-col cols="12" md="6"> <WarehouseTable /> </v-col>
  <v-col cols="12" md="6"> <HistoryTable /> </v-col>
</v-row>
```

---

## 三、思齐站布局（4 行）

```
┌─ 第1行 ──────────────────────────────────────────┐
│ [魔力值] [收获] [总偷菜收获] [农场被点赞]         │  4卡均分 md=3
├─ 第2行 ──────────────────────────────────────────┤
│ [种子商店]  [农场互动]                             │  2列 md=6
├─ 第3行 ──────────────────────────────────────────┤
│ [菜地]                                            │  整行 cols=12
├─ 第4行 ──────────────────────────────────────────┤
│ [背包]  [执行记录]                                 │  2列 md=6
└───────────────────────────────────────────────────┘
```

### 组件挂载
```vue
<!-- 第1行 -->
<v-row dense class="mb-3">
  <v-col cols="6" md="3"> 统计卡: 魔力值 </v-col>
  <v-col cols="6" md="3"> 统计卡: 收获 </v-col>
  <v-col cols="6" md="3"> 统计卡: 总偷菜收获 </v-col>
  <v-col cols="6" md="3"> 统计卡: 农场被点赞 </v-col>
</v-row>

<!-- 第2行 -->
<v-row dense class="mb-3">
  <v-col cols="12" md="6"> 种子商店 </v-col>
  <v-col cols="12" md="6"> 农场互动 </v-col>
</v-row>

<!-- 第3行 -->
<v-row dense class="mb-3">
  <v-col cols="12"> 菜地 </v-col>
</v-row>

<!-- 第4行 -->
<v-row dense>
  <v-col cols="12" md="6"> 背包 </v-col>
  <v-col cols="12" md="6"> 执行记录 </v-col>
</v-row>
```

---

## 四、第1行 / 第4行格式一致性

### 第1行统计卡（两站共用样式）
```vue
<div class="stat-card">
  <div class="stat-icon ${color}"> ${emoji} </div>
  <div class="stat-content">
    <div class="stat-title"> ${标题} </div>
    <div class="stat-value"> ${数值} <small>${单位}</small> </div>
  </div>
</div>
```

### 统计卡配色
| 卡片 | emoji | icon-bg color | 适用 |
|---|---|---|---|
| 魔力值 | 💰 | orange | 通用 + 思齐 |
| 收获 | 🌾 | green | 通用 + 思齐 |
| 操作数 | 🔄 | amber | 通用 |
| 总偷菜收获 | 🥷 | red | 思齐 |
| 农场被点赞 | 👍 | blue | 思齐 |

### 第4行格式（两站一致）
- 左右等宽 `md=6`
- 左侧为仓库/背包（含一键出售按钮 + 确认弹窗）
- 右侧为执行记录表

---

## 五、统计卡 CSS（KoWming 风格）

```css
.stat-card {
  display: flex; align-items: center; gap: 12px;
  border-radius: 14px; padding: 12px 14px;
  border: 0.5px solid rgba(var(--v-theme-on-surface), 0.08);
  background: rgba(var(--v-theme-on-surface), 0.03);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.2), 0 2px 12px rgba(var(--v-theme-on-surface), 0.08);
}
.stat-icon {
  width: 38px; height: 38px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(var(--v-theme-surface), 0.72);
  color: rgba(var(--v-theme-on-surface), 0.68);
  flex: 0 0 38px;
}
.stat-title { font-size: 11px; color: rgba(var(--v-theme-on-surface), 0.55); font-weight: 600; }
.stat-value { font-size: 20px; font-weight: 800; letter-spacing: -0.5px; }
.stat-value small { font-size: 11px; opacity: 0.5; font-weight: 400; }
```

### 统计卡配色类
```css
.stat-icon.orange { background: rgba(245,158,11,0.12); color: #f59e0b; }
.stat-icon.green  { background: rgba(34,197,94,0.12); color: #22c55e; }
.stat-icon.red    { background: rgba(239,68,68,0.12); color: #ef4444; }
.stat-icon.blue   { background: rgba(59,130,246,0.12); color: #3b82f6; }
.stat-icon.amber  { background: rgba(217,119,6,0.12); color: #d97706; }
```

---

## 六、区块卡片样式

### 卡片结构
```vue
<v-card flat class="rounded border">
  <v-card-title class="text-subtitle-2 d-flex align-center px-3 py-2 bg-${color}-lighten-5">
    <v-icon icon="${mdi}" color="${color}" size="small" class="mr-2" />
    ${标题}
    <span style="margin-left:auto"> ${操作按钮} </span>
  </v-card-title>
  <v-card-text class="pa-3"> ${内容} </v-card-text>
</v-card>
```

### 区块配色
| 区块 | 标题背景 | 图标颜色 | 图标 |
|---|---|---|---|
| 菜市场价格波动 | bg-blue-lighten-5 | blue | mdi-chart-line |
| 菜市场 | bg-blue-lighten-5 | blue | mdi-cash |
| 农作物种植区 | bg-green-lighten-5 | green | mdi-seed |
| 动物养殖区 | bg-brown-lighten-5 | brown | mdi-cow |
| 仓库 / 背包 | bg-amber-lighten-5 | amber | mdi-package-variant |
| 执行记录 | bg-grey-lighten-5 | grey | mdi-history |
| 种子商店 | bg-green-lighten-5 | green | mdi-seed |
| 农场互动 | bg-purple-lighten-5 | purple | mdi-home-group |
| 菜地 | bg-blue-lighten-5 | blue | mdi-farm |

### 行间距
- 行间 `mb-3`，行内无额外间距
- 统计卡之间 `ga-2`

---

## 七、顶栏规范

### 结构
```vue
<v-card-title class="bg-gradient-farm text-white d-flex align-center ga-2 px-3 py-2">
  <v-icon icon="mdi-sprout" color="white" size="small" />
  <span class="text-white text-subtitle-1">农场工作台 / 思齐农场</span>
  <span class="text-caption text-white opacity-70">副标题</span>
  <v-spacer />
  <!-- 状态 chip -->
  <v-chip size="small" variant="flat" color="success" prepend-icon="mdi-play-circle-outline">已启用</v-chip>
  <v-chip size="small" variant="flat" color="teal" prepend-icon="mdi-earth">直连</v-chip>
  <v-chip size="small" variant="flat" color="indigo" prepend-icon="mdi-clock-outline">下次 ${nextRun}</v-chip>
  <v-chip size="small" variant="flat" color="success" prepend-icon="mdi-shield-check-outline">实盘模式</v-chip>
  <!-- 操作按钮 -->
  <v-btn size="small" variant="outlined" color="white" prepend-icon="mdi-play" :loading="running" @click="runNow">立即运行</v-btn>
  <v-btn size="small" variant="outlined" color="white" prepend-icon="mdi-refresh" :loading="loading" @click="refreshData">刷新</v-btn>
  <v-btn v-if="showSwitch" size="small" variant="outlined" color="white" prepend-icon="mdi-cog" @click="emit('switch')">设置</v-btn>
  <v-btn v-if="showClose" size="small" variant="outlined" color="white" prepend-icon="mdi-close" @click="emit('close')">关闭</v-btn>
</v-card-title>
```

### 状态 chip 配色
| chip | 颜色 | 图标 |
|---|---|---|
| 已启用 | success | mdi-play-circle-outline |
| 已禁用 | grey-darken-1 | mdi-pause-circle-outline |
| 代理 | info | mdi-earth |
| 直连 | teal | mdi-earth |
| 下次运行 | indigo | mdi-clock-outline |
| 模拟模式 | warning | mdi-flask-outline |
| 实盘模式 | success | mdi-shield-check-outline |

---

## 八、按钮规范

### 通用原则
- 所有操作按钮统一带 `prepend-icon`（图标+文字）
- 顶栏按钮 `variant="outlined" color="white"`
- 内容区按钮 `variant="flat"`
- 弹窗确认按钮 `variant="elevated"`
- 弹窗取消按钮 `variant="text"`

### 语义颜色
| 操作 | color | 图标 |
|---|---|---|
| 收获/种植/立即运行/确认 | success | mdi-basket / mdi-seed / mdi-play / mdi-check |
| 出售 | orange | mdi-cash |
| 偷菜 | red | mdi-incognito |
| 点赞 | pink | mdi-thumb-up |
| 参观 | blue | mdi-map-marker |
| 扩地 | deep-purple | mdi-home-plus |
| 刷新 | white(顶栏) | mdi-refresh |
| 取消/关闭 | text/grey | mdi-close |

### 按钮不修改规则
- 不改已统一按钮的 variant/color/icon（除非用户明确要求）
- 子区按钮（一键收获/一键出售/单项收获/种植/出售）保持 `variant="flat"`

---

## 九、作物卡片样式（CropArea.vue）

### 结构
```vue
<div class="crop-card">
  <div class="crop-emoji">${emoji}</div>
  <div class="crop-name">${名称}</div>
  <div class="crop-status ${status}">${状态文字}</div>
  <div class="crop-meta">成本 ${cost} · 成长 ${grow_time}</div>
  <v-btn size="x-small" color="${action_color}" variant="flat">${action_label}</v-btn>
</div>
```

### 状态配色
| 状态 | class | 文字颜色 | 说明 |
|---|---|---|---|
| 可收获 | `.ready` | orange (#fb923c) | 显示收获按钮 |
| 成长中 | `.growing` | grey (opacity 0.4) | 显示剩余时间 |
| 空地 | `.empty` | grey (opacity 0.3) | 显示种植/养殖按钮 |

### 作物 emoji 映射
```
小麦🌾 玉米🌽 花生🥜 土豆🥔 鸡🐔 猪🐷 羊🐑 牛🐂
```

### 动物区差异
- `crop-card.animal` 边框色改为棕色系
- 按钮文字「养殖」而非「种植」

---

## 十、仓库表样式（WarehouseTable.vue）

### 列定义
| 列 | 说明 |
|---|---|
| 名称 | 含 emoji |
| 数量 | 数字 |
| 过期 | 带颜色标记 |
| 操作 | 出售按钮 |

### 过期颜色规则
| 剩余时间 | class | 样式 |
|---|---|---|
| > 3 天 | `.expire-normal` | 灰色 (opacity 0.5) |
| 1-3 天 | `.expire-warning` | 黄色 (#fbbf24) |
| < 1 天 | `.expire-danger` | 红色加粗 (#ef4444) ⚠ |
| 已过期 | `.expire-expired` | 灰色删除线 |

### 一键出售确认弹窗
```vue
<v-dialog v-model="sellAllDialog" max-width="440">
  <v-card>
    <v-card-title>确认出售</v-card-title>
    <v-card-text>
      确定一键出售仓库中的所有物品吗？<br>
      预计总价值：${totalValue}
    </v-card-text>
    <v-card-actions>
      <v-btn variant="text" @click="sellAllDialog = false">取消</v-btn>
      <v-btn color="orange" variant="flat" :loading="loading" @click="confirmSellAll">确认出售</v-btn>
    </v-card-actions>
  </v-card>
</v-dialog>
```

---

## 十一、菜市场表样式（MarketTable.vue）

### 列定义
| 列 | 说明 |
|---|---|
| 名称 | 含 emoji |
| 市场价 | 数字 |
| 成本 | 数字 |
| 盈利率 | 标签：正绿负红 |
| 波动幅度 | ↑X% 红色 / ↓X% 绿色 / — 灰色 |

### 盈利率标签
```css
.tag.green { background: rgba(34,197,94,0.15); color: #4ade80; }  /* 盈利 */
.tag.red   { background: rgba(239,68,68,0.15); color: #ef4444; }   /* 亏损 */
```

### 波动幅度
- 数据来源：`trends` prop，取最后两次采样计算变化率
- `(current - previous) / previous * 100%`
- 上涨红色 ↑、下跌绿色 ↓、无数据 —

---

## 十二、执行记录表样式（HistoryTable.vue）

### 数据来源
- `siteDetail.recent_actions`（每步操作记录）
- 每项含 `{action, target, profit, success, message, time, site}`

### action 中文映射
| action | 图标 | 中文 |
|---|---|---|
| harvest | 🌾 | 收获 |
| plant | 🌱 | 种植 |
| sell | 💰 | 出售 |
| harvest_all | 🧺 | 一键收获 |
| steal | 🥷 | 偷菜 |
| like | 👍 | 点赞 |
| buy_slot | 🏗 | 扩地 |

### 列定义
| 列 | 说明 |
|---|---|
| 时间 | HH:mm 格式 |
| 操作 | 图标 + 中文动作 + 目标 |
| 利润 | >0 绿色 `+{profit} {currency}`，=0 灰色 — |

### 失败行
- 整行灰色，显示 message

---

## 十三、思齐菜地样式（SiqiWorkbench.vue）

### Plot 结构（原生 button，不用 v-card）
```vue
<button class="plot ${stateClass}" @click="...">
  <img v-if="stageImg" :src="stageImg" class="stage-img" />
  <span v-else class="plot-emoji">${emoji}</span>
  <small>${作物名}</small>
  <small class="${statusColor}">${状态文字}</small>
</button>
```

### Plot 状态配色
| 状态 | class | 背景 | 边框 | 说明 |
|---|---|---|---|---|
| 成熟 | `.ready` | rgba(255,152,0,0.12) | rgba(255,152,0,0.3) | 可点击收获 |
| 种植中 | `.planted` | rgba(76,175,80,0.10) | rgba(76,175,80,0.2) | 显示剩余时间 |
| 空地 | (默认) | rgba(121,85,72,0.1) | rgba(255,255,255,0.06) | 可点击种植 |
| 可购买 | `.buyable` | rgba(59,130,246,0.08) | rgba(59,130,246,0.25) | 显示购买价格 |
| 锁定 | `.locked` | rgba(100,116,139,0.06) | rgba(100,116,139,0.12) | **灰色 opacity:0.6 cursor:not-allowed** |

### Plot 网格
```css
.plot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(82px, 1fr));
  gap: 8px;
}
.plot {
  min-height: 78px; border-radius: 10px;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 2px; padding: 6px; font-size: 11px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
```

### Land 分区
```vue
<div class="land-section ${locked ? 'land-section--locked' : ''}">
  <div class="land-title">
    ${农场名}<span class="land-plot-count">（坑位：${effective}/${max}）</span>
    <span v-if="locked" class="unlock-hint">🔒 解锁需总收获 ${unlock_harvest}</span>
    <span v-else style="color: green;">✓ 已解锁</span>
  </div>
  <div class="plot-grid"> ${plots} </div>
</div>
```

### 移动端响应（锁定农场折叠）
```css
@media (max-width: 600px) {
  .land-section--locked .plot-grid { display: none; }
  .land-section--locked .land-locked-hint { display: block; }
}
```

---

## 十四、数据刷新动画（KoWming 风格）

### 动画清单
| 动画 | 触发 | 效果 | CSS |
|---|---|---|---|
| 刷新按钮 loading | 点刷新 | 按钮转圈 + 半透明 | `.btn-loading` + `@keyframes spin` |
| 统计卡脉冲 | 刷新中 | 卡片背景闪绿光 | `.stat-card.refreshing` + `@keyframes stat-pulse` |
| 数值淡出 | 刷新中 | 数值 opacity 0.3 | `.stat-value.refreshing` |
| 数值变化高亮 | 刷新完成 | 新值绿色闪烁 | `.value-changed` + `@keyframes value-flash` |
| 区块卡半透明 | 刷新中 | 卡片 opacity 0.5 | `.card.refreshing` |
| 表格行淡入 | 数据加载后 | 逐行从上滑入 | `@keyframes row-fade-in` + nth-child 延迟 |
| 块位弹出 | 菜地加载后 | 逐个 scale 弹出 | `@keyframes plot-pop-in` + nth-child 延迟 |
| 消息提示 slide-fade | 操作完成 | 从上滑入，2.5s 后滑出 | `transition name="slide-fade"` |

### CSS 定义
```css
/* 按钮 loading */
.btn-loading { pointer-events: none; opacity: 0.7; }
.btn-loading .btn-icon { animation: spin 0.8s linear infinite; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 统计卡脉冲 */
.stat-card.refreshing { animation: stat-pulse 0.6s ease; }
@keyframes stat-pulse {
  0% { background: rgba(255,255,255,0.03); }
  50% { background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.2); }
  100% { background: rgba(255,255,255,0.03); }
}

/* 数值变化高亮 */
.value-changed { animation: value-flash 0.8s ease; }
@keyframes value-flash {
  0% { color: inherit; }
  30% { color: #4ade80; text-shadow: 0 0 8px rgba(74,222,128,0.4); }
  100% { color: inherit; text-shadow: none; }
}

/* 表格行淡入 */
.mini-table tbody tr { animation: row-fade-in 0.3s ease forwards; opacity: 0; }
.mini-table tbody tr:nth-child(1) { animation-delay: 0.05s; }
.mini-table tbody tr:nth-child(2) { animation-delay: 0.10s; }
.mini-table tbody tr:nth-child(3) { animation-delay: 0.15s; }
@keyframes row-fade-in {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 块位弹出 */
.plot { animation: plot-pop-in 0.3s ease backwards; }
.plot:nth-child(1) { animation-delay: 0.03s; }
.plot:nth-child(2) { animation-delay: 0.06s; }
@keyframes plot-pop-in {
  from { opacity: 0; transform: scale(0.9); }
  to { opacity: 1; transform: scale(1); }
}

/* 消息提示 slide-fade（KoWming 同名） */
.slide-fade-enter-active, .slide-fade-leave-active { transition: all 0.3s ease; }
.slide-fade-enter-from, .slide-fade-leave-to { transform: translateY(-20px); opacity: 0; }
```

### 刷新流程（KoWming 同款）
```javascript
async function refreshData() {
  loading.value = true;           // 按钮转圈
  // 统计卡脉冲 + 区块半透明
  refreshing.value = true;
  try {
    const detail = await request('GET', `${apiBase}/site/${siteId}`);
    // 更新数据
    siteDetail.value = detail;
    // 数值变化高亮
    changedKeys.value = ['bonus', 'harvest', 'ops'];
    // slide-fade 消息提示
    successMessage.value = '✅ 数据刷新成功';
  } catch (e) {
    errorMessage.value = '刷新失败: ' + e.message;
  } finally {
    loading.value = false;
    refreshing.value = false;
    setTimeout(() => changedKeys.value = [], 800);  // 清除高亮
  }
}
```

---

## 十五、暗色主题兼容

- 所有颜色使用 `rgba(var(--v-theme-on-surface), opacity)` 或 `rgba(var(--v-theme-surface), opacity)`
- 不使用硬编码 `#fff` / `#000`
- `border-color` 用 `rgba(var(--v-theme-on-surface), 0.07)`
- Vuetify 内置色（success/blue/orange 等）自动适配暗色

---

## 十六、构建与部署

### 仓库外构建（避免 node_modules 污染）
```bash
BUILD=/tmp/farmauto-build
rm -rf "$BUILD/src"; cp -r plugins.v2/farmauto/src "$BUILD/src"
cp plugins.v2/farmauto/{package.json,vite.config.js,index.html} "$BUILD/"
cd "$BUILD" && npm install && npm run build
rm -rf plugins.v2/farmauto/dist && cp -r dist plugins.v2/farmauto/dist
```

### dist 提交
- `dist/` 被 `.gitignore` 忽略，需 `git add -f plugins.v2/farmauto/dist`
- MP 加载需 dist 存在

### 依赖版本
```json
{
  "dependencies": {
    "vue": "^3.5.13",
    "vuetify": "3.7.3",
    "echarts": "^5.6.0"
  },
  "devDependencies": {
    "@originjs/vite-plugin-federation": "^1.4.1",
    "@vitejs/plugin-vue": "^5.0.4",
    "vite": "^5.4.11"
  }
}
```

---

## 十六、参考来源

- **brushflow** (jxxghp)：Vue 联邦架构、get_render_mode、4组件壳、vite 配置
- **KoWming 农场系列**：UI 布局、统计卡样式、菜地 plot 样式、刷新动画 slide-fade、magic-pulse
- **bfjy2024 farmauto**：原始站点适配器结构与调度

---

## 变更记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-07-26 | v1 | 初始规范：4行布局、统计卡、区块卡、按钮、作物卡、仓库、菜市场、执行记录、思齐菜地、刷新动画 |
