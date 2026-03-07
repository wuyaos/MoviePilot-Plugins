# 标题配置升级 - 支持背景色 + 可视化UI

**目标**: 升级标题配置支持背景色，改为可视化表格配置而非JSON文本框
**涉及文件**: `__init__.py`
**改动量**: 中等（约 80 行代码）
**难度**: 🟡 中等

---

## 📋 改动清单

### 改动1: 修改配置数据结构

**位置**: `__init__.py` 第 96 行左右（`_title_config` 属性）

```python
# 原有
_title_config = ''

# 改为
_title_config = {}  # 改为字典而非字符串
_title_colors = {}  # 新增：存储标题背景色
```

或者保持为单个字典存储：

```python
# 替代方案：用单个字典存储所有标题配置
_title_configs = {}  # {"电影库": {"zh": "电影", "en": "Movies", "color": "#FF5722"}}
```

### 改动2: init_plugin() 中读取配置

**位置**: 第 137 行左右

```python
# 原有
self._title_config = config.get("title_config")

# 改为
title_config_data = config.get("title_config", {})
if isinstance(title_config_data, str):
    # 兼容旧版本 JSON 字符串
    try:
        self._title_config = json.loads(title_config_data) if title_config_data else {}
    except:
        self._title_config = {}
else:
    # 新版本直接是字典
    self._title_config = title_config_data if title_config_data else {}
```

### 改动3: __update_config() 中保存配置

**位置**: 第 225 行左右

```python
# 原有
"title_config": self._title_config,

# 改为（保持一致）
"title_config": self._title_config,
```

### 改动4: 修改 __get_library_title_from_config() 方法

**位置**: 搜索该方法（通常在类的中部）

```python
# 原有逻辑（需要修改以支持背景色）
def __get_library_title_from_config(self, library_name):
    """从配置获取标题"""
    if not self._title_config:
        return None

    # 原有：直接返回列表
    config = self._title_config.get(library_name)
    if config:
        return (config[0], config[1]) if len(config) >= 2 else None

# 改为
def __get_library_title_from_config(self, library_name):
    """从配置获取标题和背景色"""
    if not self._title_config:
        return None

    config = self._title_config.get(library_name)
    if not config:
        return None

    # 支持新格式：[中文, 英文, 背景色]
    if isinstance(config, dict):
        # 新格式：字典
        return (
            config.get('zh', ''),
            config.get('en', ''),
            config.get('color', None)
        )
    elif isinstance(config, (list, tuple)):
        # 兼容旧格式：列表 [中文, 英文, 背景色(可选)]
        zh = config[0] if len(config) > 0 else ''
        en = config[1] if len(config) > 1 else ''
        color = config[2] if len(config) > 2 else None
        return (zh, en, color)

    return None
```

### 改动5: 修改调用处理背景色

**位置**: `__generate_image_from_path()` 或 `__update_single_image()` 中

```python
# 原有
title = self.__get_library_title_from_config(library_name)
if title:
    zh_title, en_title = title
else:
    zh_title, en_title = library_name, library_name

# 改为
title_data = self.__get_library_title_from_config(library_name)
if title_data:
    zh_title, en_title, bg_color = title_data
    # 可选：将 bg_color 传递给图像生成函数
    image_data = create_style_xxx(..., bg_color=bg_color)
else:
    zh_title, en_title, bg_color = library_name, library_name, None
```

### 改动6: get_form() 中添加可视化表格配置

**位置**: `get_form()` 方法中，用表格替换原有的 JSON 文本框

```python
# 原有（JSON文本框）
{
    'component': 'VTextarea',
    'props': {
        'model-value': 'title_config',
        'label': '标题配置',
        'hint': '{"电影库": ["电影", "Movies"]}'
    }
}

# 改为（可视化表格）
{
    'component': 'VRow',
    'props': {'dense': True},
    'content': [
        {
            'component': 'VCol',
            'props': {'cols': 12},
            'content': [
                {
                    'component': 'VAlert',
                    'props': {
                        'type': 'info',
                        'variant': 'tonal',
                        'text': '【标题配置】为每个媒体库设置中英文标题和背景颜色',
                        'class': 'mb-2'
                    }
                }
            ]
        }
    ]
},
# 表格显示现有配置
{
    'component': 'VTable',
    'props': {
        'dense': True,
        'hover': True,
        'headers': [
            {'title': '库名', 'value': 'library'},
            {'title': '中文标题', 'value': 'zh'},
            {'title': '英文标题', 'value': 'en'},
            {'title': '背景色', 'value': 'color'},
            {'title': '操作', 'value': 'actions'}
        ],
        'items': self.__get_title_config_items()  # 需要新增此方法
    }
},
# 添加新配置的表单
{
    'component': 'VRow',
    'props': {'dense': True, 'class': 'mt-2'},
    'content': [
        {
            'component': 'VCol',
            'props': {'cols': 4},
            'content': [
                {
                    'component': 'VTextField',
                    'props': {
                        'model-value': 'new_lib_name',
                        'label': '库名',
                        'placeholder': '电影库'
                    }
                }
            ]
        },
        {
            'component': 'VCol',
            'props': {'cols': 2},
            'content': [
                {
                    'component': 'VTextField',
                    'props': {
                        'model-value': 'new_title_zh',
                        'label': '中文标题',
                        'placeholder': '电影'
                    }
                }
            ]
        },
        {
            'component': 'VCol',
            'props': {'cols': 2},
            'content': [
                {
                    'component': 'VTextField',
                    'props': {
                        'model-value': 'new_title_en',
                        'label': '英文标题',
                        'placeholder': 'Movies'
                    }
                }
            ]
        },
        {
            'component': 'VCol',
            'props': {'cols': 2},
            'content': [
                {
                    'component': 'VColorPicker',
                    'props': {
                        'model-value': 'new_title_color',
                        'label': '背景色',
                        'mode': 'hex'
                    }
                }
            ]
        },
        {
            'component': 'VCol',
            'props': {'cols': 2},
            'content': [
                {
                    'component': 'VBtn',
                    'props': {
                        'text': '添加',
                        'color': 'primary',
                        'size': 'small'
                    }
                }
            ]
        }
    ]
}
```

### 改动7: 新增辅助方法

**位置**: 类的末尾

```python
def __get_title_config_items(self):
    """获取标题配置用于表格显示"""
    items = []
    for lib_name, config in self._title_config.items():
        if isinstance(config, dict):
            items.append({
                'library': lib_name,
                'zh': config.get('zh', ''),
                'en': config.get('en', ''),
                'color': config.get('color', '#000000')
            })
        elif isinstance(config, (list, tuple)):
            items.append({
                'library': lib_name,
                'zh': config[0] if len(config) > 0 else '',
                'en': config[1] if len(config) > 1 else '',
                'color': config[2] if len(config) > 2 else '#000000'
            })
    return items

def __add_title_config(self, lib_name, zh_title, en_title, color):
    """添加标题配置"""
    if not lib_name:
        return False

    self._title_config[lib_name] = {
        'zh': zh_title,
        'en': en_title,
        'color': color
    }
    self.__update_config()
    return True

def __remove_title_config(self, lib_name):
    """删除标题配置"""
    if lib_name in self._title_config:
        del self._title_config[lib_name]
        self.__update_config()
        return True
    return False
```

---

## ⚠️ 复杂性说明

这个改动涉及：

1. **配置格式变更**（向后兼容旧格式）
2. **UI 从文本框改为可视化表格**
3. **新增背景色支持**
4. **数据验证和错误处理**

**工作量**: 3-4 小时开发 + 2 小时测试

---

## 📊 新旧格式对比

### 旧格式（JSON 文本框）
```json
{
  "电影库": ["电影", "Movies"],
  "合集库": ["合集", "Collections"]
}
```

用户需要手写 JSON，容易出错。

### 新格式（可视化表格）

| 库名 | 中文标题 | 英文标题 | 背景色 | 操作 |
|------|---------|---------|--------|------|
| 电影库 | 电影 | Movies | #FF5722 | 编辑/删除 |
| 合集库 | 合集 | Collections | #2196F3 | 编辑/删除 |

用户通过表单填充，直观易用。

---

## ❓ 实施难度评估

| 层面 | 难度 | 说明 |
|------|------|------|
| 配置读写 | 🟢 低 | 增加向后兼容逻辑 |
| 标题处理 | 🟡 中 | 支持字典和列表两种格式 |
| UI 表格 | 🔴 高 | VTable + VColorPicker 需要熟悉 Vue 组件 |
| 表单提交 | 🔴 高 | 需要处理表格的增删改 |

---

## 🔄 替代方案（更简单）

如果可视化表格太复杂，可以采用**混合方案**：

```
保留 JSON 文本框，但格式从：
  ["电影", "Movies"]
改为：
  ["电影", "Movies", "#FF5722"]

优点：
  ✅ 代码改动少（仅改数据结构）
  ✅ 用户可手工编辑
  ✅ 支持背景色

缺点：
  ❌ UI 仍是文本框，不够可视化
  ❌ 用户需要手写 JSON
```

---

## 💡 建议

### 如果你有时间，建议完整实施
- 表格 UI 更友好
- 用户体验更好
- 与上游保持一致方向

### 如果时间紧张，建议先采用混合方案
- 快速支持背景色
- 后续再优化 UI

---

**你想要哪个方案？**

A. 完整方案（可视化表格，3-4小时）
B. 混合方案（JSON 支持背景色，1小时）
C. 先完成库白名单+合集黑名单，标题配置后续再说

