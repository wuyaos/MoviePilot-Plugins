# 库过滤优化方案：统一黑名单模式

## 当前问题

1. **字段混乱**：
   - `include_libraries` + `selected_libraries` = 白名单（重复）
   - `exclude_libraries` = 黑名单
   - `selected_users` = 用户白名单（特例，无法改为黑名单）
   - `exclude_boxsets` = 排除来源库黑名单

2. **合集用户筛选逻辑（第3440-3442行）**：
   ```python
   if user_ids:
       for user_id in user_ids:
           url += f'&UserId={user_id}'  # API 参数：仅返回这些用户的项目
   ```
   ➜ 这是 **API 级别的白名单过滤**，无法改为黑名单，因为：
   - API 接口本身就是 `&UserId=` 参数（白名单模式）
   - 如果改为黑名单，需要获取 **所有用户** 的项目，再在客户端过滤（低效）

---

## 统一黑名单方案

### 方案 A：最优方案（推荐）

**原则**：
- 非 API 限制的字段 → 统一改为黑名单（排除列表）
- API 限制的字段 → 保持现状，但改名并明确说明

**具体修改**：

| 原字段 | 新字段 | 模式 | 说明 |
|--------|--------|------|------|
| `include_libraries` | **删除** | - | 与 selected_libraries 重复 |
| `selected_libraries` | `exclude_libraries` | 黑名单 | 改为排除列表 |
| `exclude_libraries` | `exclude_libraries` | 黑名单 | 合并为同一个字段 |
| `exclude_boxsets` | `exclude_boxsets` | 黑名单 | 保持不变 |
| `selected_users` | `exclude_users` | 特例 | ⚠️ **见下方说明** |

### `selected_users` 的困境

**当前逻辑**（第3313-3324行）：
```python
if self._selected_users:
    selected_user_ids = [user_map.get(user_name) for user_name in self._selected_users]
    # API 调用时
    boxsets = self.__get_items_batch(service, parent_id, user_ids=selected_user_ids)
    # ➜ 这会添加 &UserId=xxx&UserId=yyy 参数
    # ➜ API 返回："仅这些用户可见的项目"
```

**改为黑名单的方案**（两个选项）：

#### 选项 1：保持现状，但改名为 `include_users`（保守方案）
- 保持 API 调用不变
- 改名以统一术语：`selected_users` → `include_users`
- 在 UI 中明确说"选中用户：**仅** 这些用户的项目参与合集封面"

#### 选项 2：改为 `exclude_users`（激进方案，需要修改 API 调用）
```python
# 改后逻辑
if self._exclude_users:
    # 这种情况下，不传 user_ids 参数，获取所有用户的项目
    # 然后在客户端过滤掉 exclude_users
    all_boxsets = self.__get_items_batch(service, parent_id, user_ids=None)
    # 过滤
    filtered_boxsets = [b for b in all_boxsets if b.get('UserData', {}).get('UserId') not in exclude_user_ids]
    boxsets = filtered_boxsets
```
**缺点**：API 调用需要获取所有用户的项目，性能下降；需要修改很多代码

---

## 推荐方案（折中）

### 方案总结

采用"**选项 1**" + 统一其他字段为黑名单：

```
原状态：
├─ include_libraries (白名单，与 selected_libraries 重复)
├─ selected_libraries (白名单)
├─ exclude_libraries (黑名单)
├─ exclude_boxsets (黑名单)
└─ selected_users (用户白名单，API 限制无法改)

↓ 改后

优化后：
├─ exclude_libraries (黑名单) ← 合并 include_libraries + selected_libraries
├─ exclude_boxsets (黑名单) ← 保持不变
└─ include_users (用户白名单) ← 仅改名，逻辑不变（API 限制）
```

### 修改清单

#### 1. 代码层面（第一阶段）

**删除**：
- [ ] `_include_libraries` 属性 (第84行)
- [ ] init_plugin() 中的加载 (第170行)
- [ ] get_config() 中的返回 (第425行)
- [ ] get_form() 中的默认值 (第2147行)

**改名**：
- [ ] `_selected_libraries` → `_exclude_libraries` (注意：可能有多个地方)
  - 属性定义 (第128行)
  - init_plugin() 加载 (第194行)
  - get_config() 返回 (第461行)
  - __update_library() 检查 (第2908-2918行)
  - 其他引用处
- [ ] `_selected_users` → `_include_users` (用户相关)
  - 属性定义 (第130行)
  - init_plugin() 加载 (第196行)
  - get_config() 返回 (第463行)
  - __handle_boxset_library() 使用 (第3313-3316行)

**合并逻辑**：
- [ ] 在 __get_event_transfer() 中，改用 exclude_libraries 而不是 include_libraries (第2802行)
  ```python
  # 改前
  if self._include_libraries and f"{server}-{library_id}" not in self._include_libraries:

  # 改后
  if self._exclude_libraries and f"{server}-{library_id}" in self._exclude_libraries:
  ```

#### 2. UI 层面（第二阶段）

**重构 get_form() 库过滤区域**：

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
                        "text": "库过滤说明：排除列表模式 - 选中的库将被跳过，留空表示处理所有库",
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
                        "hint": "选中的库不参与合集素材采集",
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
                        "model": "include_users",  # ← 改名
                        "label": "合集用户限制",
                        "items": self._all_users,
                        "hint": "选中用户：仅这些用户的项目参与合集素材（API限制，无法反向排除）；留空表示不限制",
                        "persistentHint": True,
                        "prependInnerIcon": "mdi-account-multiple-check"
                    }
                }
            ]
        }
    ]
}
```

---

## 修改影响分析

| 方面 | 影响 | 说明 |
|------|------|------|
| **代码行数** | ~50行 | 改名 + 删除 + 逻辑调整 |
| **测试覆盖** | 关键 | 库过滤逻辑需充分测试 |
| **向后兼容** | ⚠️ | 需要数据迁移脚本 |
| **API 改动** | 无 | 只改字段名，逻辑不变 |

### 向后兼容处理

在 init_plugin() 中添加迁移逻辑：

```python
def init_plugin(self, config: dict = None):
    if config:
        # ━━━ 迁移：include_libraries → exclude_libraries ━━━
        if "include_libraries" in config and config.get("include_libraries"):
            # 旧版本：include_libraries（白名单）
            # 新版本：exclude_libraries（黑名单）
            # 默认迁移：保持不动（用户需手动调整）
            logger.warning("检测到旧版库过滤配置 include_libraries，请在设置中更新为新格式")

        # ━━━ 迁移：selected_users → include_users ━━━
        if "selected_users" in config:
            config["include_users"] = config.get("selected_users")  # 自动迁移

        # 加载新字段
        self._exclude_libraries = config.get("exclude_libraries", [])
        self._include_users = config.get("include_users", [])
```

---

## 优势总结

| 维度 | 优势 |
|------|------|
| **统一性** | ✅ 除了 include_users（API限制），所有字段都是黑名单 |
| **易用性** | ✅ 用户只需"选择要排除的项"，不用考虑"包含什么" |
| **可维护性** | ✅ 减少字段数（4 → 3），概念更清晰 |
| **兼容性** | ⚠️ 需要迁移脚本 |
| **性能** | ✅ 无性能变化（逻辑不改） |

---

**预计工作量**：
- Phase 1（代码）：1-2小时
- Phase 2（UI）：1小时
- Phase 3（测试）：2小时
- **总计**：4-5小时

