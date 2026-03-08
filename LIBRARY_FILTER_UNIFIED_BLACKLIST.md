# 库过滤完全统一黑名单方案

## 目标

将所有库过滤字段统一为 **黑名单模式（排除列表）**：
- ✅ `exclude_libraries` - 排除库
- ✅ `exclude_boxsets` - 排除合集来源库
- ✅ `exclude_users` - 排除用户（改为客户端过滤）

---

## 当前与改后对比

### 字段改动表

| 原字段 | 原模式 | 新字段 | 新模式 | 说明 |
|--------|--------|--------|--------|------|
| `include_libraries` | 白名单 | **删除** | - | 与 selected_libraries 重复 |
| `selected_libraries` | 白名单 | `exclude_libraries` | 黑名单 | 改为排除模式 |
| `exclude_libraries` | 黑名单 | `exclude_libraries` | 黑名单 | 合并上面，保持 |
| `exclude_boxsets` | 黑名单 | `exclude_boxsets` | 黑名单 | 保持不变 |
| `selected_users` | 白名单 | `exclude_users` | 黑名单 | **改为客户端过滤** |

---

## 核心修改：`exclude_users` 实现

### 1. 问题分析

**当前逻辑**（白名单）：
```python
# 第3313-3324行
if self._selected_users:
    user_ids = [user_map.get(user_name) for user_name in self._selected_users]
    boxsets = self.__get_items_batch(service, parent_id, user_ids=user_ids)
    # API 返回："仅这些用户可见的项目"
```

**改为黑名单需要**：
```python
if self._exclude_users:
    # 1. 获取所有用户的项目（不限制用户）
    boxsets = self.__get_items_batch(service, parent_id, user_ids=None)

    # 2. 获取要排除的用户ID列表
    exclude_user_ids = [user_map.get(user_name) for user_name in self._exclude_users]

    # 3. 在客户端过滤掉这些用户的项目
    filtered_boxsets = [b for b in boxsets if b.get('UserData', {}).get('UserId') not in exclude_user_ids]
    boxsets = filtered_boxsets
```

### 2. 实现细节

**问题1**：项目中如何识别用户？
- Emby/Jellyfin API 返回的项目包含 `UserData` 字段
- `UserData.UserId` 表示最后观看该项目的用户

**问题2**：如果一个项目多个用户都看过？
- API 只返回最后观看的用户ID（`UserData.UserId`）
- 无法获取"所有看过的用户"

**问题3**：如何处理"只有被排除用户看过"的项目？
- **选项A**：不显示（严格过滤）← 推荐
- **选项B**：显示（包含）← 容易出错

---

## 代码修改清单

### Phase 1：字段改名与删除

#### 1.1 删除 `_include_libraries`

```python
# 第84行，删除：
# _include_libraries = []

# 第170行，init_plugin() 中删除：
# self._include_libraries = config.get("include_libraries")

# 第425行，get_config() 中删除：
# "include_libraries": self._include_libraries,

# 第2147行，get_form() 默认值中删除：
# "include_libraries": [],
```

#### 1.2 改名：`_selected_libraries` → `_exclude_libraries`

**属性定义**（第128行）：
```python
# 改前
_selected_libraries = []

# 改后
_exclude_libraries = []
```

**init_plugin()** 中（第194行）：
```python
# 改前
self._selected_libraries = config.get("selected_libraries", [])

# 改后
self._exclude_libraries = config.get("exclude_libraries", [])
```

**get_config()** 返回（第461行）：
```python
# 改前
"selected_libraries": self._selected_libraries,

# 改后
"exclude_libraries": self._exclude_libraries,
```

**__update_library()** 检查（第2908-2918行）：
```python
# 改前
if self._selected_libraries:
    if lib_id:
        lib_key = f"{service.name}-{lib_id}"
        if lib_key not in self._selected_libraries:  # 白名单逻辑
            logger.info(f"库 {library.get('Name')} 不在白名单中，跳过")
            return False

# 改后
if self._exclude_libraries:
    if lib_id:
        lib_key = f"{service.name}-{lib_id}"
        if lib_key in self._exclude_libraries:  # 黑名单逻辑
            logger.info(f"库 {library.get('Name')} 在排除列表中，跳过")
            return False
```

#### 1.3 改名：`_selected_users` → `_exclude_users`

**属性定义**（第130行）：
```python
# 改前
_selected_users = []

# 改后
_exclude_users = []
```

**init_plugin()** 中（第196行）：
```python
# 改前
self._selected_users = config.get("selected_users", [])

# 改后
self._exclude_users = config.get("exclude_users", [])
```

**get_config()** 返回（第463行）：
```python
# 改前
"selected_users": self._selected_users,

# 改后
"exclude_users": self._exclude_users,
```

### Phase 2：修改库过滤逻辑

#### 2.1 更新 `__get_event_transfer()` 中的库过滤

**第2802行**：
```python
# 改前
if self._include_libraries and f"{server}-{library_id}" not in self._include_libraries:
    logger.info(f"{server}：{library['Name']} 不在列表中，跳过更新封面")
    return

# 改后
if self._exclude_libraries and f"{server}-{library_id}" in self._exclude_libraries:
    logger.info(f"{server}：{library['Name']} 在排除列表中，跳过更新封面")
    return
```

#### 2.2 更新 `__handle_boxset_library()` 中的用户过滤

**第3304-3324行**，完全重写用户过滤逻辑：

```python
# 改前
# 排除来源库：按当前合集库本身进行过滤（与 UI 的库选择器 value 对齐）
if self._exclude_boxsets:
    current_library_key = f"{service.name}-{library_id}"
    if current_library_key in self._exclude_boxsets:
        logger.info(f"合集来源库 {library.get('Name')} 在排除列表中，跳过")
        return False

# 获取选中用户的 ID
selected_user_ids = None
if self._selected_users:
    try:
        user_map = service.instance.get_users() if hasattr(service.instance, 'get_users') else {}
        selected_user_ids = [user_map.get(user_name) for user_name in self._selected_users if user_map.get(user_name)]
        if selected_user_ids:
            logger.debug(f"合集库用户筛选: {selected_user_ids}")
    except Exception as e:
        logger.warning(f"获取用户 ID 失败: {e}")

boxsets = self.__get_items_batch(service, parent_id,
                              include_types=include_types,
                              user_ids=selected_user_ids)

# 改后
# 排除来源库：按当前合集库本身进行过滤（与 UI 的库选择器 value 对齐）
if self._exclude_boxsets:
    current_library_key = f"{service.name}-{library_id}"
    if current_library_key in self._exclude_boxsets:
        logger.info(f"合集来源库 {library.get('Name')} 在排除列表中，跳过")
        return False

# 获取所有合集（不限制用户）
boxsets = self.__get_items_batch(service, parent_id,
                              include_types=include_types,
                              user_ids=None)

# 客户端过滤：排除指定用户的项目
if self._exclude_users and boxsets:
    try:
        user_map = service.instance.get_users() if hasattr(service.instance, 'get_users') else {}
        exclude_user_ids = [user_map.get(user_name) for user_name in self._exclude_users if user_map.get(user_name)]

        if exclude_user_ids:
            logger.debug(f"合集库排除用户: {exclude_user_ids}")
            # 过滤掉这些用户看过的项目
            filtered_boxsets = []
            for boxset in boxsets:
                user_data = boxset.get('UserData', {})
                boxset_user_id = user_data.get('UserId')
                if boxset_user_id not in exclude_user_ids:
                    filtered_boxsets.append(boxset)
            boxsets = filtered_boxsets
            logger.debug(f"用户过滤后剩余 {len(boxsets)} 个合集")
    except Exception as e:
        logger.warning(f"获取用户 ID 失败: {e}")
```

#### 2.3 同样修改 `__handle_boxset_library()` 中的电影获取

**第3345-3348行**：
```python
# 改前
movies = self.__get_items_batch(service,
                             parent_id=boxset['Id'],
                             include_types=include_types,
                             user_ids=selected_user_ids)

# 改后
movies = self.__get_items_batch(service,
                             parent_id=boxset['Id'],
                             include_types=include_types,
                             user_ids=None)

# 也需要对 movies 进行相同的用户过滤（复用逻辑）
if self._exclude_users and movies:
    exclude_user_ids = [user_map.get(user_name) for user_name in self._exclude_users if user_map.get(user_name)]
    if exclude_user_ids:
        filtered_movies = [m for m in movies if m.get('UserData', {}).get('UserId') not in exclude_user_ids]
        movies = filtered_movies
```

### Phase 3：UI 改动

#### 3.1 更新 get_form() 的库过滤区域

**重构"库过滤与合集配置"区域**：

```python
{
    "component": "VRow",
    "content": [
        {
            "component": "VCol",
            "props": {"cols": 12},
            "content": [
                {
                    "component": "VSubheader",
                    "props": {"class": "pl-0 py-2 mt-2"},
                    "text": "库过滤与合集配置"
                }
            ]
        }
    ]
},
# ───────── 库过滤（黑名单模式） ─────────
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
                        "text": "库过滤说明：所有过滤均为排除列表（黑名单）模式。选中的项将被跳过，留空表示处理所有项",
                        "class": "mb-2"
                    }
                }
            ]
        },
        {
            "component": "VCol",
            "props": {"cols": 12},
            "content": [
                {
                    "component": "VSelect",
                    "props": {
                        "multiple": True,
                        "chips": True,
                        "clearable": True,
                        "model": "exclude_libraries",
                        "label": "排除库",
                        "items": library_items,
                        "hint": "选中的库不会被更新封面；留空表示更新所有库",
                        "persistentHint": True,
                        "prependInnerIcon": "mdi-folder-off-outline"
                    }
                }
            ]
        }
    ]
},
# ───────── 合集配置 ─────────
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
                    "text": "合集专用配置（黑名单模式）"
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
                        "hint": "选中的库不参与合集素材采集；留空表示使用所有库",
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
                        "model": "exclude_users",
                        "label": "排除用户",
                        "items": self._all_users,
                        "hint": "选中用户观看过的项目将不参与合集素材；留空表示不限制用户",
                        "persistentHint": True,
                        "prependInnerIcon": "mdi-account-remove"
                    }
                }
            ]
        }
    ]
}
```

#### 3.2 更新默认值

**第2190-2193行**，改动：
```python
# 改前
"selected_libraries": [],
"exclude_libraries": [],
"exclude_boxsets": [],
"selected_users": [],

# 改后
"exclude_libraries": [],
"exclude_boxsets": [],
"exclude_users": [],
```

---

## 向后兼容处理

在 `init_plugin()` 中添加迁移逻辑：

```python
def init_plugin(self, config: dict = None):
    if config:
        # ━━━ 迁移旧配置 ━━━

        # 1. include_libraries → exclude_libraries（需要取反逻辑）
        if "include_libraries" in config and config.get("include_libraries"):
            logger.warning("检测到旧版库白名单 include_libraries，请在设置中更新为新的排除列表格式")
            # 无法自动迁移（白→黑需要反转所有库列表）

        # 2. selected_libraries → exclude_libraries（需要取反逻辑）
        if "selected_libraries" in config and config.get("selected_libraries"):
            logger.warning("检测到旧版库白名单 selected_libraries，请在设置中更新为新的排除列表格式")
            # 无法自动迁移

        # 3. selected_users → exclude_users（可以自动迁移）
        if "selected_users" in config and config.get("selected_users"):
            logger.info("自动迁移：selected_users → exclude_users")
            config["exclude_users"] = config.get("selected_users", [])

        # 加载新字段
        self._exclude_libraries = config.get("exclude_libraries", [])
        self._exclude_boxsets = config.get("exclude_boxsets", [])
        self._exclude_users = config.get("exclude_users", [])
```

---

## 修改清单（快速查询）

### 删除
- [ ] 属性：`_include_libraries` (第84行)
- [ ] init_plugin()：include_libraries 加载 (第170行)
- [ ] get_config()：include_libraries 返回 (第425行)
- [ ] get_form() 默认值：include_libraries (第2147行)

### 改名
- [ ] `_selected_libraries` → `_exclude_libraries`
  - [ ] 属性定义 (第128行)
  - [ ] init_plugin() (第194行)
  - [ ] get_config() (第461行)
  - [ ] __update_library() (第2908-2918行)

- [ ] `_selected_users` → `_exclude_users`
  - [ ] 属性定义 (第130行)
  - [ ] init_plugin() (第196行)
  - [ ] get_config() (第463行)

### 逻辑修改
- [ ] __get_event_transfer() 库过滤 (第2802行)
- [ ] __update_library() 库过滤逻辑 (第2908-2931行)
- [ ] __handle_boxset_library() 用户过滤 (第3304-3324行)
- [ ] __handle_boxset_library() 电影获取 (第3345-3348行)
- [ ] get_form() 库过滤UI区域 (大幅改动)
- [ ] get_form() 默认值 (第2190-2193行)

---

## 预期效果

```
改前：
├─ include_libraries (白名单) → 隐藏
├─ selected_libraries (白名单) → UI 显示
├─ exclude_libraries (黑名单) → UI 显示
├─ exclude_boxsets (黑名单) → UI 显示
└─ selected_users (白名单) → UI 显示

↓ 改后

统一黑名单：
├─ exclude_libraries (黑名单，合并前两个) → UI 显示
├─ exclude_boxsets (黑名单) → UI 显示
└─ exclude_users (黑名单，客户端过滤) → UI 显示
```

---

## 性能影响分析

| 场景 | 改前 | 改后 | 影响 |
|------|------|------|------|
| 合集处理（无用户过滤） | API 限制用户 | 获取全部后过滤 | ⚠️ 稍微增加API返回量 |
| 合集处理（有用户排除） | 无此功能 | 客户端过滤 | ✅ 功能增强，性能可接受 |
| 库过滤 | 白名单逻辑 | 黑名单逻辑 | ✅ 性能无差异 |

**总体**：性能影响极小（客户端过滤几百个项目很快）

---

## 测试验证清单

- [ ] 库排除功能正常工作
- [ ] 合集来源库排除正常工作
- [ ] 合集用户排除正常工作（客户端过滤）
- [ ] 转入事件库过滤生效
- [ ] 旧配置迁移提示正确
- [ ] 多个排除项同时生效无冲突

