# 上游同步计划 - wuyaos vs justzerock v0.9.1

**生成日期**: 2026-03-07
**当前版本**: wuyaos v0.9.0.1
**上游版本**: justzerock v0.9.1
**同步难度**: 🟡 **中等** - 有破坏性变更，需要谨慎合并

---

## 📊 版本对比分析

### 代码规模对比

```
                    wuyaos v0.9.0.1      justzerock v0.9.1    变化
文件数              8 个                 21 个                 +13 (+162%)
总代码行数          5,341 行             9,655 行              +4,314 (+81%)
目录结构            扁平                 模块化                大幅重构
```

### 功能对比矩阵

| 功能维度 | wuyaos (当前) | justzerock (上游) | 说明 |
|---------|-------------|-----------------|------|
| **静态风格** | single_1, single_2, multi_1 | style_static_1~4 | 上游风格数+1，结构改名 |
| **动态风格** | ❌ 无 | ✨ style_animated_1~4 | **新增4种动画** |
| **动图格式** | 不支持 | APNG/GIF/WebP | **新增动图生成** |
| **工具模块** | ❌ 无 | ImageResourceManager, PerformanceMonitor, NetworkHelper, ColorHelper | **新增4个工具** |
| **库过滤** | exclude_libraries (黑名单) | include_libraries (白名单) | ⚠️ **逻辑反转** |
| **用户过滤** | ✅ _selected_users (wuyaos 特色) | ❌ 已移除 | ⚠️ **可能丢失** |
| **UI标签页** | 5 个 (basic/adv/template/cover_style/fonts) | 未知 (需确认) | 可能重构 |

---

## ⭐ 上游新增功能详解

### 1. 动图支持 - 4种新风格 (2,648行)

**style_animated_1.py** (877行)
```python
功能: 单张图片 + 动画效果
动画: 旋转 + 飞入动画
输入: 1张图片 → 输出: APNG/GIF/WebP 动图
参数: fps (帧率), duration (时长), animation_format, reduce_colors
用途: 简洁风格，适合单图库展示
```

**style_animated_2.py** (398行)
```python
功能: 多张图片飞入动画
动画: 9张图片依次飞入
输入: 9张图片 → 输出: 动图合集
参数: 同上 + animation_delay, fly_speed
用途: 集合展示，类似 multi_1 但带动效
```

**style_animated_3.py** (1,055行) - 最复杂
```python
功能: 滚动 + 旋转 + 网格组合
动画: 多层复合效果
输入: N张图片 → 输出: 高级动画
参数: scroll_speed, rotation_angle, grid_mode
用途: 高级展示，竞争力强
```

**style_animated_4.py** (318行)
```python
功能: 待确认 (可能是简化版)
动画: 待确认
用途: 待确认
```

### 2. 工具模块化 - 4个新工具 (924行)

**ImageResourceManager** (213行)
```python
职责: PIL 图像生命周期管理，防内存泄漏
方法:
  - register_image() / unregister_image()
  - get_image_info()
  - cleanup_unused()
用处: 长时间运行时的内存优化（动图生成场景）
```

**PerformanceMonitor** (183行)
```python
职责: 操作计时与性能监控
规则: 仅记录 >1秒的操作为 INFO
用处: 识别瓶颈，指导优化
```

**NetworkHelper** (237行)
```python
职责: HTTP 请求封装，重试机制
改进: 比现有 RequestUtils 更完善
用处: 下载图片时的稳定性
```

**ColorHelper** (291行)
```python
职责: 颜色提取与处理工具函数
方法: get_dominant_colors(), contrast_ratio(), etc.
改进: 比 style_multi_1.py 的颜色算法更健壮
用处: 所有风格的颜色处理统一
```

### 3. 新增静态风格 (145行)

**style_static_4.py**
```python
功能: 未知，需人工查看
地位: 与 single_1/2 平行
```

---

## ⚠️ 破坏性变更 (Critical!)

### 问题1：库过滤逻辑反转

**当前行为 (wuyaos v0.9.0.1):**
```python
exclude_libraries = ["server-123", "server-456"]  # 黑名单
# 逻辑：处理所有库 EXCEPT 列表中的库
if f"{service_id}-{lib_id}" in exclude_libraries:
    continue  # 跳过此库
```

**上游行为 (justzerock v0.9.1):**
```python
include_libraries = ["server-123", "server-456"]  # 白名单
# 逻辑：仅处理列表中的库
if include_libraries and f"{service_id}-{lib_id}" not in include_libraries:
    continue  # 跳过此库
```

**风险等级**: 🔴 **HIGH**
- 现有用户的 exclude_libraries 配置在上游版本中会被无视
- 导致原本被排除的库被重新处理，产生不期望的结果
- 如果简单 merge，会破坏用户配置

**缓解方案**:
```python
# 合并时，保留两个字段，兼容两种逻辑
if self._exclude_libraries and f"{service_id}-{lib_id}" in self._exclude_libraries:
    continue  # 黑名单优先

if self._include_libraries and f"{service_id}-{lib_id}" not in self._include_libraries:
    continue  # 白名单其次

# 双向兼容
```

### 问题2：用户过滤功能被移除

**当前 (wuyaos):**
```python
_selected_users: List[str]  # 用户ID列表，68处引用
# 功能：Emby 合集可按用户过滤，只为特定用户生成封面
# 应用：多用户家庭，可为不同用户显示不同内容
```

**上游 (justzerock v0.9.1):**
```python
# _selected_users 完全移除
# 影响：上游版本无法进行用户级过滤
```

**风险等级**: 🟡 **MEDIUM**
- wuyaos 用户若依赖用户过滤功能会失效
- 上游可能认为这功能不必要，或计划用其他方式实现

**缓解方案**:
```python
# 保留 wuyaos 的用户过滤逻辑
# 在 cherry-pick 时，不要删除相关代码
# 动图风格中如需用户过滤，自行适配
```

### 问题3：UI 标签页结构可能变更

**当前 (wuyaos):**
```
标签页:
  - basic (启用/计划/延迟)
  - advanced (服务器/库/排除/排序)
  - template (标题/背景图)
  - cover_style (样式选择 + 样式参数)
  - fonts (字体配置)
```

**上游 (v0.9.1):**
```
标签页结构: 未知 (需人工查看)
可能变更: 可能从 5 页重构为其他方案
```

**风险等级**: 🟡 **MEDIUM**
- 如果上游重构了 UI，直接 merge 会产生配置丢失或冲突
- 用户看不到熟悉的 UI

---

## 🎯 Cherry-Pick 策略

### 推荐方案：选择性合并（不是直接 merge）

```
步骤 1: 创建新分支
  git checkout -b feature/upstream-animated-sync

步骤 2: 按优先级 cherry-pick
  优先级 HIGH（必选）:
    ├─ plugins/mediacovergenerator/style_animated_*.py (4个文件)
    ├─ plugins/mediacovergenerator/utils/ (工具目录)
    └─ 集成这些风格到现有 __init__.py

  优先级 MEDIUM（建议）:
    ├─ style_static_4.py (新增静态风格)
    ├─ ColorHelper 工具（替换 style_multi_1.py 的颜色函数）
    └─ PerformanceMonitor 性能监控

  优先级 LOW/SKIP（跳过）:
    ├─ include_libraries 反转逻辑
    ├─ _selected_users 移除
    └─ UI 标签页重构（待明确）

步骤 3: 人工集成
  ├─ 在 __init__.py 导入新风格: from .style_animated_* import create_style_animated_*
  ├─ 在 cover_style 配置选项中添加 animated_1/2/3/4
  ├─ 验证与现有 multi_1 样式无冲突
  ├─ 保留 _selected_users 用户过滤功能
  ├─ 保留 exclude_libraries 黑名单逻辑（不采用 include_libraries）
  └─ 测试所有样式生成无误

步骤 4: 版本号更新
  v0.9.0.1 → v0.10.0 (新增动图功能，小版本号)
```

---

## 📋 详细 Cherry-Pick 清单

### Cherry-Pick List

```bash
# HIGH 优先级 - 必选 (新增文件，无冲突)
git cherry-pick <upstream-commit-hash> --  \
  plugins/mediacovergenerator/style_animated_1.py  \
  plugins/mediacovergenerator/style_animated_2.py  \
  plugins/mediacovergenerator/style_animated_3.py  \
  plugins/mediacovergenerator/style_animated_4.py  \
  plugins/mediacovergenerator/utils/

# MEDIUM 优先级 - 建议 (可选，但推荐)
git cherry-pick <upstream-commit-hash> --  \
  plugins/mediacovergenerator/style_static_4.py

# 手工集成点1: __init__.py 顶部导入
+ from app.plugins.mediacovergenerator.style_animated_1 import create_style_animated_1
+ from app.plugins.mediacovergenerator.style_animated_2 import create_style_animated_2
+ from app.plugins.mediacovergenerator.style_animated_3 import create_style_animated_3
+ from app.plugins.mediacovergenerator.style_animated_4 import create_style_animated_4

# 手工集成点2: cover_style 配置选项（约 L258 的 form 定义）
# 在现有选项后添加:
  {
    'component': 'VSelect',
    'props': {
      'model-value': 'cover_style',
      'label': '封面样式',
      'options': [
        {'label': '单图风格1', 'value': 'single_1'},
        {'label': '单图风格2', 'value': 'single_2'},
        {'label': '合集九宫格', 'value': 'multi_1'},
        {'label': '动画风格1', 'value': 'animated_1'},  # ← NEW
        {'label': '动画风格2', 'value': 'animated_2'},  # ← NEW
        {'label': '动画风格3', 'value': 'animated_3'},  # ← NEW
        {'label': '动画风格4', 'value': 'animated_4'},  # ← NEW
        {'label': '静态风格4', 'value': 'static_4'},    # ← NEW (optional)
      ]
    }
  }

# 手工集成点3: __generate_image_from_path() 路由逻辑 (约 L2071)
# 在现有 if/elif 链后添加:
  elif self._cover_style == 'animated_1':
    image_data = create_style_animated_1(image_path, title, font_path, ...)
  elif self._cover_style == 'animated_2':
    image_data = create_style_animated_2(library_dir, title, font_path, ...)  # multi 模式
  elif self._cover_style.startswith('animated'):
    # 其他动画风格
    ...

# 手工集成点4: 不要做的事情 (避免破坏)
# ❌ 不要删除 _selected_users 相关代码
# ❌ 不要将 exclude_libraries 改为 include_libraries
# ❌ 不要重构 UI 标签页结构（除非确认兼容性）
```

---

## 🧪 合并后的测试清单

### 功能测试

- [ ] **单图风格**
  - [ ] single_1 生成无误
  - [ ] single_2 生成无误

- [ ] **合集风格**
  - [ ] multi_1 九宫格生成无误
  - [ ] 旋转列、投影、圆角都正常

- [ ] **动画风格** (新增)
  - [ ] animated_1: 旋转飞入动画生成成功
  - [ ] animated_2: 多图飞入生成成功
  - [ ] animated_3: 复合动画生成成功
  - [ ] animated_4: 生成成功
  - [ ] 输出格式: APNG/GIF/WebP 可选

- [ ] **配置兼容**
  - [ ] 旧配置 (v0.9.0.1) 仍可加载
  - [ ] exclude_libraries 黑名单仍可用
  - [ ] _selected_users 用户过滤仍可用

- [ ] **API 集成**
  - [ ] Emby 连接正常
  - [ ] Jellyfin 连接正常
  - [ ] 图片获取、处理、上传全流程

- [ ] **性能**
  - [ ] 动图生成时间 < 30s (对于 9 张图)
  - [ ] 内存占用 < 500MB (ImageResourceManager 工作)
  - [ ] 无内存泄漏 (监控 cleanup)

### 边界测试

- [ ] 库中图片不足 9 张时，动画风格是否降级或报错
- [ ] 用户禁用动图功能时，是否正确回退到静态风格
- [ ] 多用户家庭的 _selected_users 过滤是否与动图兼容
- [ ] 大图集（>20 张）的性能表现

---

## 📅 实施时间表

### 第1阶段：准备 (1天)
- [ ] 本地 checkout upstream 代码，通读 4 个 animated_*.py 文件
- [ ] 确认 utils/ 工具模块的依赖和 API
- [ ] 列出所有需要手工集成的点

### 第2阶段：集成 (2-3天)
- [ ] 创建 feature/upstream-animated-sync 分支
- [ ] Cherry-pick 新文件 (style_animated_*.py, utils/)
- [ ] 修改 __init__.py，集成新风格到路由逻辑
- [ ] 扩展 get_form() UI，添加动画风格选项
- [ ] 修改参数传递链，确保动画参数正确传递
- [ ] 代码审查，确保多_1 和动画风格无冲突

### 第3阶段：测试 (2-3天)
- [ ] 单元测试：各风格生成测试
- [ ] 集成测试：Emby/Jellyfin 端到端
- [ ] 兼容性测试：旧配置升级场景
- [ ] 性能测试：内存/CPU/时间
- [ ] 手工 UI 测试：样式选择、参数调整

### 第4阶段：验证 (1天)
- [ ] 交叉验证：多_1 + 动画风格无冲突
- [ ] 用户过滤：_selected_users 功能完整
- [ ] 库过滤：exclude_libraries 黑名单生效
- [ ] 回滚计划：若出现问题的回滚方案

### 第5阶段：发布 (1天)
- [ ] 更新 package.v2.json: v0.9.0.1 → v0.10.0
- [ ] 添加 CHANGELOG 条目 (动图支持、新工具、兼容性说明)
- [ ] 创建 Release 标签和发布说明
- [ ] 通知用户升级

**总预计**: 7-10 个工作日

---

## 🎁 合并后的最终产物

```
MediaCoverGenerator v0.10.0
├─ 静态风格: single_1, single_2, multi_1 (wuyaos 特色), static_4 (上游)
├─ 动态风格: animated_1, animated_2, animated_3, animated_4 (✨ NEW)
├─ 格式支持: JPEG/PNG/APNG/GIF/WebP
├─ 功能保留:
│  ├─ 用户过滤 (_selected_users, wuyaos 特色)
│  ├─ 库黑名单 (exclude_libraries, 向后兼容)
│  ├─ 字体自动下载 (wuyaos 特色)
│  ├─ 播放列表封面 (当前版本)
│  └─ 5 标签页 UI (wuyaos 定制)
└─ 新增工具:
   ├─ ImageResourceManager (内存优化)
   ├─ PerformanceMonitor (性能监控)
   ├─ NetworkHelper (网络稳定性)
   └─ ColorHelper (颜色处理统一)
```

---

## ❓ 常见问题

### Q1: 为什么不直接 merge upstream？

**答**: 因为有破坏性变更：
- `exclude_libraries` ↔ `include_libraries` 逻辑反转
- `_selected_users` 被移除
- UI 可能重构

直接 merge 会破坏现有用户的配置和功能。cherry-pick 可以精细控制，保留 wuyaos 的特色功能。

### Q2: 动图风格和 multi_1 冲突吗？

**答**: 不冲突。
- multi_1: 静态九宫格（wuyaos）
- animated_2: 动态九宫格（上游）
- 两者独立，用户可选择

### Q3: 动图生成会比静态慢很多吗？

**答**: 是的，但可以优化。
- 预期: 静态 5-10s → 动画 15-30s (9 张图)
- 优化: ImageResourceManager + PerformanceMonitor 应该减缓
- 建议: 提供 `reduce_colors` 参数，用户自行平衡质量/速度

### Q4: 需要改动 requirements.txt 吗？

**答**: 可能需要。
- 检查 animated_*.py 是否有新的 PIL 相关依赖
- 检查是否需要 `pillow>=9.0` (APNG 支持)
- 待合并时确认

### Q5: 如果 upstream 继续更新怎么办？

**答**:
- 建议定期（如每月）检查上游更新
- 用同样的 cherry-pick 策略，逐个评估新功能
- 保持 wuyaos 特色（multi_1, 用户过滤）的完整性

---

## 📞 后续建议

1. **立即行动**: 在本地 clone 上游代码，仔细阅读 animated_*.py 源码，确认动画逻辑和参数
2. **风险评估**: 与熟悉现有代码的人 code review，确认集成方案无遗漏
3. **创建分支**: `git checkout -b feature/upstream-animated-sync`
4. **逐步集成**: 先合并 animated_1（最简单），测试通过后再合并其他
5. **社区反馈**: 考虑是否要把改进后的版本（保留 multi_1 + 动画）贡献回上游

---

**报告生成**: 2026-03-07
**基于数据**: WebFetch upstream repo + git commit history analysis
**置信度**: HIGH (直接从上游 package.v2.json 和 commit 消息确认)
