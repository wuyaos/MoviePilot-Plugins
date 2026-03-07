# 上游同步 - 快速决策指南

**对比**: wuyaos v0.9.0.1 vs justzerock v0.9.1

---

## 🎯 核心发现（3句话总结）

1. **上游有重大更新** ✨
   - 新增 **4种动图风格** (APNG/GIF/WebP动画)
   - 新增 **4个工具模块** (内存/性能/网络/颜色优化)
   - 代码量翻倍：5,341行 → 9,655行

2. **有2个破坏性变更** ⚠️
   - 库过滤逻辑反转：`exclude_libraries` → `include_libraries`
   - 用户过滤被移除：`_selected_users` 消失

3. **合并策略** ✅
   - **不要直接 merge**（会破坏现有配置）
   - **推荐 cherry-pick**（精细控制，保留你的特色）
   - **保留3个功能**：multi_1合集、用户过滤、exclude_libraries黑名单

---

## 📊 新功能对标

### 新增的4种动图风格

| 风格 | 特点 | 输入 | 输出 | 用途 |
|------|------|------|------|------|
| **animated_1** | 单图旋转飞入 | 1张图 | 动图 | 简洁展示 |
| **animated_2** | 多图飞入 | 9张图 | 动图 | 类似你的multi_1但有动效 |
| **animated_3** | 滚动+旋转+网格 | N张图 | 动图 | 最炫酷 |
| **animated_4** | 待探索 | ? | 动图 | 待探索 |

**你的 multi_1 还在吗？** ✅ 是的，完全保留。动画是额外选择。

---

## ⚠️ 破坏性变更 - 必须处理

### 问题1：库过滤逻辑反转

```python
# 现在 (你的版本)
exclude_libraries = ["emby-123", "jellyfin-456"]
# 含义：处理所有库，EXCEPT 这些

# 上游
include_libraries = ["emby-123", "jellyfin-456"]
# 含义：仅处理这些库

# 🔴 冲突：完全相反！
```

**影响**: 升级后，用户被排除的库会被重新处理 → 配置失效 → 用户愤怒

**缓解**: 合并时保留两套逻辑，黑名单优先

### 问题2：用户过滤功能消失

```python
# 你有这个 (_selected_users，68处引用)
_selected_users: List[str]  # 按用户ID过滤，多用户家庭必需

# 上游版本：没有！
# 上游可能不需要，或用其他方式实现
```

**影响**: 多用户家庭无法为特定用户生成封面

**缓解**: 合并时保留 `_selected_users` 代码

---

## 🎬 建议的合并流程

### 选项A：保守方案（推荐）⭐

```
步骤1: 创建分支
  git checkout -b feature/upstream-sync-v0.10

步骤2: 只 cherry-pick 新文件（不改现有代码）
  ✅ style_animated_1.py
  ✅ style_animated_2.py
  ✅ style_animated_3.py
  ✅ style_animated_4.py
  ✅ utils/ (4个工具模块)

步骤3: 手工集成（在你的 __init__.py 中添加）
  ✅ 导入新风格
  ✅ 添加 animated_1/2/3/4 到样式选择
  ✅ 在路由逻辑中处理新风格
  ❌ 不删除用户过滤代码
  ❌ 不改库过滤逻辑

步骤4: 测试
  ✅ multi_1 仍可用
  ✅ 用户过滤仍可用
  ✅ 动画风格可生成
  ✅ 旧配置可加载

步骤5: 发布
  v0.9.0.1 → v0.10.0
```

**优点**:
- 保留所有现有功能
- 获得新的动图能力
- 用户配置无破坏

**缺点**:
- 手工工作量多（≈200行代码改动）
- 需要充分测试

**工作量**: 7-10个工作日

---

### 选项B：激进方案（不推荐）

```
直接 merge upstream
```

**优点**: 快速，代码冲突自动解决

**缺点**:
- 🔴 用户配置破坏（库过滤反转）
- 🔴 用户功能丢失（用户过滤消失）
- 🔴 升级后投诉满天飞
- 需要回滚或发紧急补丁

**风险**: 极高

---

### 选项C：延期方案

```
暂时不合并，继续维护 v0.9.0.1
等上游稳定后再考虑
```

**优点**:
- 无风险
- 继续维护现有功能稳定

**缺点**:
- 无法获得动图新功能
- 长期可能与上游逐渐分化

---

## 💡 我的建议

### 如果你有时间 + 想要新功能
➜ **选择选项A**（保守合并）
- 动图风格会大大提升用户体验
- 保留你的特色（multi_1、用户过滤）
- 代码工作量可控

### 如果你时间紧张
➜ **选择选项C**（延期）
- 继续稳定运营现有版本
- 积累用户和反馈
- 等上游发展更稳定了再合并

### 如果用户有强烈需求（动图）
➜ **立即启动选项A**
- 用户会因为新功能升级版本
- 竞争力提升

---

## 📋 下一步具体行动

假设你选择**选项A（保守合并）**，具体步骤：

### 第一周：调研 (2-3天)
1. **在本地clone上游代码**
   ```bash
   git clone https://github.com/justzerock/MoviePilot-Plugins.git upstream
   cd upstream
   ```

2. **仔细阅读这些文件**
   ```
   plugins.v2/mediacovergenerator/style_animated_1.py  (877行)
   plugins.v2/mediacovergenerator/style_animated_2.py  (398行)
   plugins.v2/mediacovergenerator/style_animated_3.py  (1055行)
   plugins.v2/mediacovergenerator/utils/ImageResourceManager.py
   plugins.v2/mediacovergenerator/utils/ColorHelper.py
   ```

3. **理解关键点**
   - animated_2 的输入格式（是否需要9张图像？）
   - 动图输出参数（fps、duration、format 可配置吗？）
   - 工具模块是否有额外依赖

### 第二周：集成 (3-4天)
4. **创建分支**
   ```bash
   git checkout -b feature/upstream-animated-v0.10
   ```

5. **复制新文件**
   - `cp upstream/plugins.v2/mediacovergenerator/style_animated_*.py yours/`
   - `cp -r upstream/plugins.v2/mediacovergenerator/utils/ yours/`

6. **修改 `__init__.py`**（约200行改动）
   - 在顶部导入 4个 animated 风格
   - 在 `get_form()` 添加样式选择 UI
   - 在 `__generate_image_from_path()` 添加路由逻辑
   - **关键**: 保留所有用户过滤代码，不删除

7. **自我代码审查**
   ```
   ✅ multi_1 代码未动
   ✅ _selected_users 完整保留
   ✅ exclude_libraries 逻辑未改
   ✅ 新导入的模块无冲突
   ✅ 参数传递链完整
   ```

### 第三周：测试 (3-4天)
8. **在你的 Emby/Jellyfin 上测试**
   - 选择 animated_1 风格，生成一个库的封面
   - 检查动图文件是否生成
   - 用播放器查看动画效果
   - 重复测试其他风格

9. **兼容性测试**
   - 升级旧版本配置，检查是否加载正确
   - 用户过滤是否有效
   - 库排除是否有效

### 第四周：发布 (1-2天)
10. **更新版本号和文档**
    - `package.v2.json`: v0.9.0.1 → v0.10.0
    - 添加 CHANGELOG 条目
    - 创建 Release 标签

11. **发布**
    - Push 到 GitHub
    - 发送更新通知

---

## 📚 相关文档

我已为你生成了两份详细文档，保存在项目目录：

1. **`.omc/UPSTREAM_SYNC_PLAN.md`**
   - 完整的合并计划
   - 所有破坏性变更分析
   - cherry-pick 详细清单
   - 测试场景和时间表

2. **`.omc/RESEARCH_SUMMARY.md`**
   - 5阶段研究完整报告
   - Fork关系分析
   - multi_1 功能评估
   - R18过滤设计方案

---

## ❓ 快速FAQ

**Q: 动图会不会很慢？**
A: 预期慢 2-3倍（静态5s → 动画15s），但有优化工具。用户可选择。

**Q: 多_1合集会保留吗？**
A: 100% 保留。动画只是新增选项，不替代multi_1。

**Q: 上游还在继续更新吗？**
A: 是的，最新一次是2026年3月（支持动图）。建议定期监控。

**Q: 如果出现问题怎么回滚？**
A: 用 git revert，或直接回到 v0.9.0.1 tag。很安全。

**Q: 要改 requirements.txt 吗？**
A: 可能要，需要检查 animated_*.py 的依赖。合并时确认。

---

## 📊 合并后的产物对比

```
现在 (v0.9.0.1):
  ├─ 封面样式: single_1, single_2, multi_1
  ├─ 输出格式: JPEG/PNG
  ├─ 特色功能: 用户过滤, 字体下载, 播放列表
  └─ 总代码: 5,341行

之后 (v0.10.0):
  ├─ 封面样式: single_1, single_2, multi_1, animated_1/2/3/4 ✨
  ├─ 输出格式: JPEG/PNG, APNG/GIF/WebP ✨
  ├─ 特色功能: 同上 (全部保留)
  ├─ 新工具: 内存管理, 性能监控, 颜色提取优化 ✨
  └─ 总代码: 9,500+行
```

---

## 🎬 最后决定

现在请告诉我：

**你想选择哪个方案？**

- [ ] **A. 立即启动保守合并** (获得动图功能，保留所有特色)
- [ ] **B. 继续调研** (再看看其他细节)
- [ ] **C. 暂时延期** (稳定现有版本，以后再说)
- [ ] **D. 有其他问题** (继续讨论)

选好后，我可以：
- **A选**: 立即提供详细的代码改动指南和集成步骤
- **B选**: 帮你深入分析任何疑问
- **C选**: 转向其他需求（比如实现R18过滤）
- **D选**: 耐心解答

