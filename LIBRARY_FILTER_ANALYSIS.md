# MediaCoverGeneratorCustom 库过滤逻辑分析与优化方案

## 问题概述

当前存在 **5 个库过滤相关字段**，分别应用于不同场景，导致：
- ❌ 字段重复、概念重叠
- ❌ 优先级逻辑不清
- ❌ UI 组织散乱
- ❌ 用户容易混淆

---

## 当前的 5 个库过滤字段

### 1️⃣ `include_libraries`
**位置**: `__get_event_transfer()` (第 2802 行)
**作用**: 转入库过滤
**逻辑**:
```python
if self._include_libraries and f"{server}-{library_id}" not in self._include_libraries:
    return  # 跳过不在列表中的库
```
**触发时机**: 监控转入时
**UI**: 无（隐藏字段）

### 2️⃣ `selected_libraries`
**位置**: `__update_library()` (第 2908 行)
**作用**: 库白名单（仅更新勾选的库）
**逻辑**:
```python
if self._selected_libraries:
    if lib_key not in self._selected_libraries:
        return False  # 不在白名单中就跳过
```
**触发时机**: 更新库封面时
**UI**: ✅ 出现在"库过滤与合集"区域 (第 503 行)

### 3️⃣ `exclude_libraries`
**位置**: `__update_library()` (第 2921 行)
**作用**: 库黑名单（排除指定库）
**逻辑**:
```python
if self._exclude_libraries:
    if lib_key in self._exclude_libraries:
        return False  # 在黑名单中就跳过
```
**触发时机**: 更新库封面时
**UI**: ✅ 出现在"库过滤与合集"区域 (第 523 行)

### 4️⃣ `exclude_boxsets`
**位置**: `__handle_boxset_library()` (第 3305 行)
**作用**: 合集来源库排除
**逻辑**:
```python
if self._exclude_boxsets:
    current_library_key = f"{service.name}-{library_id}"
    if current_library_key in self._exclude_boxsets:
        return False  # 不为合集生成素材
```
**触发时机**: 处理合集库时
**UI**: ✅ 出现在"库过滤与合集"区域 (第 564 行)

### 5️⃣ `selected_users`
**位置**: `__handle_boxset_library()` (第 3313 行)
**作用**: 合集用户筛选
**逻辑**:
```python
if self._selected_users:
    selected_user_ids = [user_map.get(user_name) for user_name in self._selected_users if user_map.get(user_name)]
    # 用 user_ids 参数调用 __get_items_batch()
```
**触发时机**: 获取合集项目时
**UI**: ✅ 出现在"库过滤与合集"区域 (第 584 行)

---

## 问题分析

### 问题 1：字段重复（`include_libraries` vs `selected_libraries`）

| 字段 | 作用 | 检查时机 | UI显示 |
|------|------|--------|-------|
| `include_libraries` | 转入库过滤 | 转入事件 | ❌ 无 |
| `selected_libraries` | 库白名单 | 更新库时 | ✅ 有 |

**冲突**：两个都是白名单概念，但应用于不同场景
- **方案 A**: 合并为一个字段，应用于所有场景
- **方案 B**: 保持分离，但明确在UI中区分用途

### 问题 2：白名单与黑名单并存时的优先级不清

当同时设置 `selected_libraries`（白名单）和 `exclude_libraries`（黑名单）：
```python
# 当前逻辑：白名单优先检查
if self._selected_libraries:  # 先检查白名单
    if lib_key not in self._selected_libraries:
        return False

if self._exclude_libraries:   # 再检查黑名单
    if lib_key in self._exclude_libraries:
        return False
```

**问题**：如果一个库既在白名单又在黑名单中，会被跳过（符合逻辑）
**但UI提示不清**：没有明确说"黑名单优先"还是"白名单优先"

### 问题 3：合集相关的两个字段组织不当

`exclude_boxsets` 和 `selected_users` 属于合集专用配置，应该组织到一起：
- ❌ 目前与库过滤字段混在同一行
- ✅ 应该单独为合集配置分组

---

## 优化方案

### 方案概览

```
基础设置标签
 ├─ 基础功能行 (启用、立即更新、入库监控)
 └─ 库过滤配置 (合并到一个清晰的区域)
     ├─ [库白名单] - 仅更新勾选库
     ├─ [库黑名单] - 排除指定库
     ├─ ─────────────────────── (分隔线)
     └─ [合集配置] (新分组)
         ├─ [排除来源库] - 不为这些库生成素材
         └─ [用户筛选] - 仅合集适用
```

### 具体修改

#### 修改 1：统一库过滤逻辑

**目标**：使用统一的字段 `_selected_libraries` 作为全局库白名单

```python
# init_plugin() 中
self._selected_libraries = config.get("selected_libraries", [])

# __get_event_transfer() 中改为：
if self._selected_libraries and f"{server}-{library_id}" not in self._selected_libraries:
    return  # 改用 selected_libraries，删除 include_libraries

# __update_library() 中保持不变
```

**删除**：`_include_libraries` 字段（设为空数组）

#### 修改 2：在UI中清晰分组

**获取库列表的变量**：
```python
library_items = [{"title": lib['name'], "value": lib['value']} for lib in self._all_libraries]
```

**改动后的 get_form()** (在"库过滤与合集"区域)：

```python
{
    "component": "VSubheader",
    "props": {"class": "pl-0 py-2 mt-2"},
    "text": "库过滤与合集配置"
},
# ───────── 库过滤 (两选一或都不选) ─────────
{
    "component": "VRow",
    "content": [
        {
            "component": "VCol",
            "props": {"cols": 12},
            "content": [
                {
                    "component": "VAlert",
                    "props": {
                        "type": "info",
                        "variant": "tonal",
                        "text": "库过滤说明：白名单→仅更新勾选库；黑名单→排除指定库；两者并存时黑名单优先排除",
                        "class": "mb-2"
                    }
                }
            ]
        },
        {
            "component": "VCol",
            "props": {"cols": 12, "md": 6},
            "content": [
                {
                    "component": "VSelect",
                    "props": {
                        "multiple": True,
                        "chips": True,
                        "clearable": True,
                        "model": "selected_libraries",
                        "label": "库白名单",
                        "items": library_items,
                        "hint": "仅更新勾选库；留空表示不过滤",
                        "persistentHint": True,
                        "prependInnerIcon": "mdi-folder-check-outline"
                    }
                }
            ]
        },
        {
            "component": "VCol",
            "props": {"cols": 12, "md": 6},
            "content": [
                {
                    "component": "VSelect",
                    "props": {
                        "multiple": True,
                        "chips": True,
                        "clearable": True,
                        "model": "exclude_libraries",
                        "label": "库黑名单",
                        "items": library_items,
                        "hint": "排除指定库（与白名单并存时优先排除）",
                        "persistentHint": True,
                        "prependInnerIcon": "mdi-folder-off-outline"
                    }
                }
            ]
        }
    ]
},
# ───────── 合集配置 (分隔线) ─────────
{
    "component": "VRow",
    "content": [
        {
            "component": "VCol",
            "props": {"cols": 12},
            "content": [
                {
                    "component": "VSubheader",
                    "props": {"class": "pl-0 py-2 mt-4"},
                    "text": "合集专用配置"
                }
            ]
        }
    ]
},
{
    "component": "VRow",
    "content": [
        {
            "component": "VCol",
            "props": {"cols": 12, "md": 6},
            "content": [
                {
                    "component": "VSelect",
                    "props": {
                        "multiple": True,
                        "chips": True,
                        "clearable": True,
                        "model": "exclude_boxsets",
                        "label": "排除来源库",
                        "items": library_items,
                        "hint": "选中的库不为合集生成素材",
                        "persistentHint": True,
                        "prependInnerIcon": "mdi-folder-remove-outline"
                    }
                }
            ]
        },
        {
            "component": "VCol",
            "props": {"cols": 12, "md": 6},
            "content": [
                {
                    "component": "VSelect",
                    "props": {
                        "multiple": True,
                        "chips": True,
                        "clearable": True,
                        "model": "selected_users",
                        "label": "用户筛选",
                        "items": self._all_users,
                        "hint": "仅合集项目适用；留空表示不过滤",
                        "persistentHint": True,
                        "prependInnerIcon": "mdi-account-filter"
                    }
                }
            ]
        }
    ]
}
```

#### 修改 3：更新默认值和代码逻辑

**删除 `_include_libraries`**：

```python
# 从属性定义中删除
# _include_libraries = []

# 从 init_plugin() 中删除
# self._include_libraries = config.get("include_libraries")

# 从 get_config() 中删除
# "include_libraries": self._include_libraries,

# 从 get_form() 默认值中删除
# "include_libraries": [],
```

**更新 `__get_event_transfer()` 第 2802 行**：

```python
# 改前：
if self._include_libraries and f"{server}-{library_id}" not in self._include_libraries:

# 改后：
if self._selected_libraries and f"{server}-{library_id}" not in self._selected_libraries:
```

---

## 修改清单

### Phase 1：代码层面
- [ ] 删除 `_include_libraries` 属性定义 (第 84 行)
- [ ] 删除 init_plugin() 中的加载逻辑 (第 170 行)
- [ ] 删除 get_config() 中的返回逻辑 (第 425 行)
- [ ] 更新 __get_event_transfer() (第 2802 行)
- [ ] 删除 get_form() 中的默认值 (第 2147 行)

### Phase 2：UI层面
- [ ] 在 get_form() 中重构库过滤区域
- [ ] 添加"库过滤说明" VAlert
- [ ] 将 exclude_boxsets 和 selected_users 独立为"合集配置"分组
- [ ] 更新所有相关的 hint 文本

### Phase 3：测试验证
- [ ] ✅ 库白名单功能正常
- [ ] ✅ 库黑名单功能正常
- [ ] ✅ 转入事件库过滤生效
- [ ] ✅ 合集配置相互独立
- [ ] ✅ 用户筛选生效

---

## 预期效果

| 场景 | 改前 | 改后 |
|------|------|------|
| 仅启用白名单 | include_libraries + selected_libraries 重复 | ✅ 统一用 selected_libraries |
| 启用黑名单 | 优先级不清 | ✅ 清晰说明"优先排除" |
| 合集配置 | 与库过滤混在一起 | ✅ 独立分组"合集专用配置" |
| 用户筛选 | 不知道只对合集有效 | ✅ 分组提示"仅合集适用" |

---

**预计修改行数**: ~40 行代码 + ~60 行UI配置
**影响范围**: 安全（不改逻辑，只改字段和UI）
**向后兼容**: ❌ 需要迁移（`include_libraries` → `selected_libraries`）

