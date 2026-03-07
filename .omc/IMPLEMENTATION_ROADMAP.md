# 完整实施路线图

**总体目标**: Phase 1 核心功能 + Phase 2 可视化配置
**总工作量**: 3-4 周
**最终版本**: v0.9.1 或 v0.10.0

---

## 📅 实施时间表

### Phase 1: 库白名单 + 合集黑名单（第1-2周）

**目标**: 实现核心过滤功能

```
Week 1:
  Day 1-2: 代码开发（4处改动，约20行）
  Day 3: 本地测试（库白名单、合集黑名单）
  Day 4-5: 修复bug、验证兼容性

Week 2:
  Day 1-2: 集成测试（Emby/Jellyfin 真实环境）
  Day 3: 文档更新 + CHANGELOG
  Day 4-5: 准备发布
```

**参考文档**: `.omc/WHITELIST_BLACKLIST_IMPLEMENTATION.md`

**改动内容**:
```
✅ 库白名单 (_selected_libraries)
✅ 合集黑名单 (_exclude_boxsets)
✅ 配置读写
✅ 逻辑集成
```

**预期成果**: v0.9.1（或v0.10.0）- 包含库白名单 + 合集黑名单

---

### Phase 2: 表格可视化标题配置（第3-4周）

**目标**: 升级标题配置为可视化表格 + 支持背景色

```
Week 3:
  Day 1-2: 标题配置升级（数据结构改造）
  Day 3: UI 表格组件实现（VTable + VColorPicker）
  Day 4-5: 表格操作（增删改）

Week 4:
  Day 1-2: 集成测试
  Day 3: 向后兼容性验证（旧配置迁移）
  Day 4-5: 发布准备
```

**参考文档**: `.omc/TITLE_CONFIG_UPGRADE.md`

**改动内容**:
```
✅ 标题配置支持背景色 ["电影", "Movies", "#FF5722"]
✅ 数据结构从 JSON 字符串 → 字典
✅ UI 从文本框 → VTable 可视化表格
✅ VColorPicker 颜色选择
✅ 增删改表格行
✅ 向后兼容性（旧格式自动迁移）
```

**预期成果**: v0.10.0 - 包含库白名单 + 合集黑名单 + 可视化标题配置

---

## 🎯 Phase 1 快速指南

### 改动位置
```
1. 类属性 (L77-78)
   + _selected_libraries = []
   + _exclude_boxsets = []

2. init_plugin() (L133-134)
   + self._selected_libraries = config.get(...)
   + self._exclude_boxsets = config.get(...)

3. __update_config() (L220-221)
   + "selected_libraries": ...
   + "exclude_boxsets": ...

4. __update_library() (开头)
   + if self._selected_libraries: check...

5. __handle_boxset_library() (循环内)
   + if boxset in self._exclude_boxsets: skip...
```

### 验证清单
```
✅ 代码编译无错
✅ 启用库白名单，仅处理指定库
✅ 启用合集黑名单，排除指定来源库的合集
✅ 旧配置升级兼容
✅ Emby/Jellyfin 真实环境测试
```

---

## 🎯 Phase 2 快速指南

### 改动位置
```
1. 数据结构 (L96)
   - _title_config = ''  →  _title_config = {}

2. 标题读取 (init_plugin)
   - 支持新格式 ["电影", "Movies", "#FF5722"]
   - 向后兼容旧格式

3. 标题使用 (__get_library_title_from_config)
   - 返回 (zh, en, color) 三元组

4. get_form() UI
   - 移除 VTextarea (JSON文本框)
   - 添加 VTable (可视化表格)
   - 添加 VColorPicker (颜色选择)

5. 新增方法
   - __get_title_config_items() (表格数据)
   - __add_title_config() (新增行)
   - __remove_title_config() (删除行)
```

### 验证清单
```
✅ 代码编译无错
✅ 旧格式配置自动迁移
✅ 表格显示所有配置
✅ 颜色选择器工作正常
✅ 新增/删除/编辑配置行
✅ 配置保存生效
```

---

## 📚 参考文档

| 文档 | 位置 | 用途 |
|------|------|------|
| **库白名单实施** | `.omc/WHITELIST_BLACKLIST_IMPLEMENTATION.md` | Phase 1 完整改动指南 |
| **标题配置升级** | `.omc/TITLE_CONFIG_UPGRADE.md` | Phase 2 完整改动指南 |
| **官方开发规范** | https://github.com/jxxghp/MoviePilot-Plugins | Vuetify 组件使用 |

---

## 🚀 立即开始

### 现在就可以开始 Phase 1：

1. **打开** `.omc/WHITELIST_BLACKLIST_IMPLEMENTATION.md`
2. **按步骤** 修改 `__init__.py`（5处改动，20行代码）
3. **测试** 库白名单和合集黑名单功能
4. **提交** Phase 1 版本

### Phase 1 完成后，再启动 Phase 2：

1. **打开** `.omc/TITLE_CONFIG_UPGRADE.md`
2. **升级** 标题配置数据结构
3. **实现** VTable 可视化表格
4. **测试** 向后兼容性
5. **提交** Phase 2 版本

---

## 📊 工作量估算

| 阶段 | 开发 | 测试 | 文档 | 总计 |
|------|------|------|------|------|
| Phase 1 | 30分钟 | 2小时 | 30分钟 | **3小时** |
| Phase 2 | 2小时 | 1.5小时 | 30分钟 | **4小时** |
| **总计** | **2.5小时** | **3.5小时** | **1小时** | **7小时** |

**分布**: 约 3-4 个工作周（取决于测试时间）

---

## ✅ 最终产物

### v0.9.1（Phase 1 完成）
```
新增功能：
  ✅ 库白名单（_selected_libraries）
  ✅ 合集黑名单（_exclude_boxsets）

保留功能：
  ✅ 多_1合集风格
  ✅ 用户过滤
  ✅ 字体下载
  ✅ 播放列表支持
```

### v0.10.0（Phase 2 完成）
```
新增功能：
  ✅ 库白名单 + 合集黑名单
  ✅ 可视化标题表格
  ✅ 背景色支持

改进功能：
  ✅ 标题配置更友好
  ✅ 颜色选择器
```

---

## 🎬 现在就开始吧！

**第一步**: 打开 `.omc/WHITELIST_BLACKLIST_IMPLEMENTATION.md`

**预计完成**: 明天或后天推出 Phase 1 版本

准备好开始写代码了吗？有任何疑问随时问我！

