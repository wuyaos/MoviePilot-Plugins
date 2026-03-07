# R18 内容过滤 - 合集封面实施指南

**目标**: 在生成合集封面时，排除 R18 内容的图片
**涉及文件**: 仅 `__init__.py`
**改动量**: 极小（≈60 行）
**难度**: 🟢 低

---

## 📋 完整改动清单

### 改动1: 添加 R18 评级常量 (在文件顶部导入后)

**位置**: `__init__.py` 第 40 行左右（在 class 定义前）

```python
# 在 "from app.plugins.mediacovergenerator.static.multi_1 import multi_1" 之后添加

# R18 内容判断常量
R18_RATINGS = {'UNRATED', 'NC-17', 'X', 'XXX', 'Explicit', '18+', 'R18', 'R18+', 'R-18'}
R18_GENRES = {'Adult', 'Hentai', 'XXX'}
R18_TAG_KEYWORDS = ['R18', 'R-18', 'r18', '成人', 'adult', 'nsfw', 'NSFW']
```

### 改动2: 添加类属性 (在 `_font_download` 属性后)

**位置**: `__init__.py` 第 113 行左右

```python
    _font_download = True  # 新增：字体下载开关
    # 添加以下两行
    _exclude_r18 = False  # 新增：R18 过滤开关
    _r18_custom_tags = ""  # 新增：自定义 R18 标签
```

### 改动3: 在 init_plugin 中读取配置 (在 `_font_download` 读取后)

**位置**: `__init__.py` 第 165 行左右

```python
            self._selected_users = config.get("selected_users", [])  # 新增：获取用户筛选配置
            self._font_download = config.get("font_download", True)  # 新增：获取字体下载配置
            # 添加以下两行
            self._exclude_r18 = config.get("exclude_r18", False)
            self._r18_custom_tags = config.get("r18_custom_tags", "")
```

### 改动4: 在 __update_config 中保存配置 (在 `font_download` 后)

**位置**: `__init__.py` 第 253 行左右

```python
            "selected_users": self._selected_users,  # 新增：保存用户筛选配置
            "font_download": self._font_download  # 新增：保存字体下载配置
            # 添加以下两行
            "exclude_r18": self._exclude_r18,
            "r18_custom_tags": self._r18_custom_tags,
```

### 改动5: API 参数添加 Fields (在 `__get_items_batch()` 方法中)

**位置**: 查找 `def __get_items_batch` 方法，找到构建 URL 的地方

```python
# 搜索类似这样的代码：
# url += f"&SortBy={sort_by}&Limit={limit}&StartIndex={offset}&IncludeItemTypes={include_str}..."

# 找到这一行（通常在 URL 构建的最后添加）：
url += f"&Recursive=true&SortOrder=Descending"

# 改为：
url += f"&Recursive=true&SortOrder=Descending&Fields=OfficialRating,Tags,Genres"
```

### 改动6: 新增 R18 检测方法 (在类的末尾添加)

**位置**: `__init__.py` 最后一个方法之后

```python
    def __is_r18_item(self, item: dict) -> bool:
        """
        判断是否为 R18 内容

        检查三个字段：
        1. OfficialRating (分级标记)
        2. Genres (内容类型)
        3. Tags (用户标签)
        """
        if not item:
            return False

        # 检查1: OfficialRating
        rating = item.get('OfficialRating', '').upper()
        if rating and rating in R18_RATINGS:
            logger.info(f"[R18过滤] 检测到评级: {rating}")
            return True

        # 检查2: Genres
        genres = item.get('Genres', [])
        if genres:
            for genre in genres:
                if genre.upper() in R18_GENRES:
                    logger.info(f"[R18过滤] 检测到类型: {genre}")
                    return True

        # 检查3: Tags (包括自定义标签)
        tags = item.get('Tags', [])
        custom_tags = [t.strip().lower() for t in self._r18_custom_tags.split(',') if t.strip()]

        if tags:
            for tag in tags:
                tag_lower = tag.lower()
                # 检查内置关键词
                if any(keyword.lower() in tag_lower for keyword in R18_TAG_KEYWORDS):
                    logger.info(f"[R18过滤] 检测到标签: {tag}")
                    return True
                # 检查用户自定义标签
                if tag_lower in custom_tags:
                    logger.info(f"[R18过滤] 检测到自定义标签: {tag}")
                    return True

        return False
```

### 改动7: 在 `__filter_valid_items()` 中添加过滤逻辑

**位置**: 查找 `def __filter_valid_items` 方法

```python
def __filter_valid_items(self, items, parent_id=None):
    """
    筛选有效项目
    """
    valid_items = []
    seen_tags = set()

    # 在现有循环中添加 R18 过滤
    for item in items:
        # 新增：R18 过滤
        if self._exclude_r18 and self.__is_r18_item(item):
            continue

        # 以下是原有的逻辑，保持不变
        tag = item.get('Name', '')
        if tag and tag not in seen_tags:
            seen_tags.add(tag)
            valid_items.append(item)

    return valid_items
```

### 改动8: 在 get_form() 中添加 UI 配置

**位置**: 查找 `def get_form(self)` 方法，在适当位置（如 advanced_tab 末尾）添加

```python
# 找到现有的标签页定义，在某个标签页（如 advanced_tab）末尾添加：

{
    'component': 'VRow',
    'props': {'dense': True},
    'content': [
        {
            'component': 'VCol',
            'props': {'cols': 12},
            'content': [
                {
                    'component': 'VDivider',
                    'props': {'class': 'my-2'}
                }
            ]
        },
        {
            'component': 'VCol',
            'props': {'cols': 12},
            'content': [
                {
                    'component': 'VAlert',
                    'props': {
                        'type': 'warning',
                        'variant': 'tonal',
                        'text': '【R18 内容过滤】启用后，将在生成合集封面时排除所有标记为 R18 的内容',
                        'class': 'mb-2'
                    }
                }
            ]
        },
        {
            'component': 'VCol',
            'props': {'cols': 12},
            'content': [
                {
                    'component': 'VSwitch',
                    'props': {
                        'model-value': 'exclude_r18',
                        'label': '启用 R18 内容过滤',
                        'hint': '勾选后，合集封面中将不包含成人相关内容'
                    }
                }
            ]
        },
        {
            'component': 'VCol',
            'props': {'cols': 12},
            'content': [
                {
                    'component': 'VTextField',
                    'props': {
                        'model-value': 'r18_custom_tags',
                        'label': '自定义 R18 标签',
                        'hint': '额外要过滤的标签，多个用逗号分隔（如: "成人,18禁"）',
                        'placeholder': '成人, 18禁, hentai'
                    }
                }
            ]
        }
    ]
}
```

### 改动9: 在 get_form() 的默认值中添加配置

**位置**: 查找 `get_form()` 方法末尾的默认值字典

```python
def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
    # ... 上面的 form 定义 ...

    # 找到末尾的默认值字典
    return form, {
        "enabled": False,
        "onlyonce": False,
        # ... 其他配置 ...
        "selected_users": [],
        "font_download": True,
        # 添加以下两行
        "exclude_r18": False,
        "r18_custom_tags": "",
    }
```

---

## ✅ 实施步骤

### Step 1: 添加常量（2分钟）
```
编辑 __init__.py 第 40 行
添加：R18_RATINGS, R18_GENRES, R18_TAG_KEYWORDS
```

### Step 2: 添加类属性（1分钟）
```
编辑 __init__.py 第 113 行
添加：_exclude_r18, _r18_custom_tags
```

### Step 3: 配置读写（2分钟）
```
编辑 init_plugin() 方法 - 读取配置
编辑 __update_config() 方法 - 保存配置
```

### Step 4: API 参数（1分钟）
```
编辑 __get_items_batch() 方法
在 URL 末尾添加 &Fields=OfficialRating,Tags,Genres
```

### Step 5: 新增检测方法（5分钟）
```
编辑类末尾
添加完整的 __is_r18_item() 方法
```

### Step 6: 集成过滤逻辑（2分钟）
```
编辑 __filter_valid_items() 方法
在循环头添加：if self._exclude_r18 and self.__is_r18_item(item): continue
```

### Step 7: UI 配置（5分钟）
```
编辑 get_form() 方法
添加 VSwitch 和 VTextField 组件
更新默认值字典
```

**总计**: 约 20 分钟代码改动

---

## 🧪 测试验证

改动完成后，验证清单：

### 编译/语法检查
```bash
# 检查 Python 语法
python -m py_compile plugins.v2/mediacovergenerator/__init__.py
```

### 插件加载测试
```
重启 MoviePilot
检查日志是否有错误
UI 中是否出现新的 "启用 R18 内容过滤" 开关
```

### 功能测试
```
1. 在合集中添加一些有 R18 标签的内容
2. 禁用过滤，生成封面 (应该包含 R18 内容)
3. 启用过滤，重新生成 (应该排除 R18 内容)
4. 检查日志中的 [R18过滤] 消息
```

### 回归测试
```
确保原有功能仍可用：
  ✅ 单图风格 (single_1/2)
  ✅ 合集风格 (multi_1)
  ✅ 用户过滤 (_selected_users)
  ✅ 库排除 (exclude_libraries)
  ✅ 字体下载
```

---

## 📊 效果示例

### 场景：多用户家庭的合集

**改动前**:
```
合集 "成人内容"
├─ 用户1看到: [成人电影1, 成人电影2, ...]
└─ 用户2(孩子)看到: [成人电影1, 成人电影2, ...]  ❌ 问题！
```

**改动后**:
```
启用 R18 过滤后：

合集 "成人内容"
├─ 用户1看到: 无法生成封面（所有项目都被过滤）
└─ 用户2(孩子)看到: [安全的非R18内容合集]  ✅ 安全
```

---

## 💡 配置建议

### 对于多用户家庭
```
启用: ✅ "启用 R18 内容过滤"
自定义标签: "成人, 18禁, hentai, 伦理"
```

### 对于单用户或不关心的用户
```
启用: ❌ (保持默认关闭)
```

---

## ❓ 常见问题

**Q: 如何知道内容是否被过滤了？**
A: 查看日志，会有 `[R18过滤] 检测到...` 的消息

**Q: 如何添加自定义标签？**
A: 在 "自定义 R18 标签" 文本框中输入，多个用逗号分隔

**Q: 上传到 Emby/Jellyfin 后没有效果？**
A:
1. 确认 Emby/Jellyfin 的内容标注了 OfficialRating 或 Tags
2. 启用过滤后，需要重新生成一次封面
3. 检查日志是否有 [R18过滤] 消息

**Q: 性能影响大吗？**
A: 非常小，仅在过滤时额外检查 3 个字段，可忽略

---

## 🎯 下一步

完成以上改动后：

1. **测试** (1-2 小时)
   - 本地环境验证
   - 在真实的 Emby/Jellyfin 上测试

2. **优化** (可选)
   - 调整 R18_RATINGS/GENRES 集合（根据实际需求）
   - 添加更多自定义标签

3. **发布**
   - 更新 package.v2.json 版本号 (v0.9.0.1 → v0.9.1)
   - 添加 CHANGELOG 条目
   - 推送到 GitHub

---

现在可以开始改代码了！有任何问题尽管问。
