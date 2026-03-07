# 库白名单 + 合集黑名单实施指南

**目标**: 实现库白名单 + 合集黑名单两层过滤
**文件**: 仅修改 `__init__.py`
**改动量**: 4 处，约 20 行代码
**难度**: 🟢 低

---

## 📋 完整改动清单

### 改动1: 添加类属性

**位置**: `__init__.py` 第 77-78 行（在 `_exclude_libraries` 之后）

```python
    _exclude_libraries = []
    _selected_libraries = []     # 新增：库白名单
    _exclude_boxsets = []        # 新增：合集黑名单
```

### 改动2: 在 init_plugin() 中读取配置

**位置**: 第 133-134 行（在 `_exclude_libraries` 读取之后）

```python
            self._exclude_libraries = config.get("exclude_libraries")
            self._selected_libraries = config.get("selected_libraries", [])  # 新增
            self._exclude_boxsets = config.get("exclude_boxsets", [])        # 新增
```

### 改动3: 在 __update_config() 中保存配置

**位置**: 第 220-221 行（在 `exclude_libraries` 之后）

```python
            "exclude_libraries": self._exclude_libraries,
            "selected_libraries": self._selected_libraries,  # 新增
            "exclude_boxsets": self._exclude_boxsets,        # 新增
```

### 改动4: 在 __update_library() 中应用库白名单

**位置**: `__update_library()` 方法开头（查找该方法定义）

```python
def __update_library(self, service, library):
    library_name = library['Name']
    logger.info(f"媒体库 {service.name}：{library_name} 开始准备更新封面")

    # 新增：检查库白名单
    if self._selected_libraries:
        lib_key = f"{service.id}-{library.get('Id', '')}"
        if lib_key not in self._selected_libraries:
            logger.info(f"库 {library_name} 不在白名单中，跳过")
            return False

    # 原有逻辑继续...
    # 自定义图像路径
    image_path = self.__check_custom_image(library_name)
    # ... 后续代码 ...
```

### 改动5: 在 __handle_boxset_library() 中应用合集黑名单

**位置**: `__handle_boxset_library()` 方法内部，处理合集项目的循环中

搜索类似这样的代码结构：
```python
def __handle_boxset_library(self, service, library):
    # ... 获取合集列表的代码 ...

    for boxset in boxsets:  # ← 在这个循环中添加
        # 新增：检查合集来源库是否在黑名单中
        source_library_id = boxset.get('SeriesId')  # 合集的来源库ID
        if source_library_id:
            boxset_key = f"{service.id}-{source_library_id}"
            if boxset_key in self._exclude_boxsets:
                logger.info(f"合集 {boxset.get('Name')} 来自黑名单库，跳过")
                continue

        # 原有的处理逻辑（生成合集封面）
        # self.__update_library(service, boxset)
        # ... 后续代码 ...
```

---

## ✅ 实施步骤

| 步骤 | 任务 | 时间 |
|------|------|------|
| 1 | 添加类属性（改动1） | 1分钟 |
| 2 | 配置读取（改动2） | 1分钟 |
| 3 | 配置保存（改动3） | 1分钟 |
| 4 | 库白名单（改动4） | 3分钟 |
| 5 | 合集黑名单（改动5） | 3分钟 |
| 6 | 代码检查 | 2分钟 |
| 7 | 本地测试 | 30分钟 |

**总计**: 约 40 分钟

---

## 🧪 测试验证

### 编译检查
```bash
python -m py_compile plugins.v2/mediacovergenerator/__init__.py
```

### 场景1: 库白名单为空（向后兼容）
```
预期行为：处理所有库（与原有行为相同）
验证：生成所有库的封面
```

### 场景2: 库白名单只包含"电影库"
```
配置：selected_libraries = ["server-电影库"]

预期行为：
  ├─ 电影库 → 生成封面 ✅
  ├─ 电视剧库 → 跳过 ❌
  └─ 合集库 → 生成封面 ✅

验证：日志中显示跳过的库
```

### 场景3: 合集库中应用合集黑名单
```
配置：
  selected_libraries = ["server-合集库"]
  exclude_boxsets = ["server-R18库"]

合集库中的合集：
  ├─ 合集A (来自"电影库") → 生成 ✅
  ├─ 合集B (来自"R18库")  → 跳过 ❌
  └─ 合集C (来自"动漫库")  → 生成 ✅

验证：合集B 的日志显示被跳过
```

---

## 📊 UI 配置

改动完成后，UI 会自动出现两个新配置字段：

```
【库白名单配置】
  输入框：选择要处理的库
  示例：["server-电影库", "server-合集库"]
  说明：为空时处理所有库

【合集黑名单配置】
  输入框：选择要排除的源库
  示例：["server-R18库", "server-成人库"]
  说明：合集库中的合集如果来自这些库将被排除
```

---

## 🔍 关键代码位置参考

### 找到 __update_library 方法
```python
# 搜索这一行
def __update_library(self, service, library):
    library_name = library['Name']
    logger.info(f"媒体库 {service.name}：{library_name} 开始准备更新封面")
```

### 找到 __handle_boxset_library 方法
```python
# 搜索这一行
def __handle_boxset_library(self, service, library):
    # 这个方法专门处理合集库
```

---

## ⚠️ 注意事项

1. **库ID格式**
   - 库ID = `{service.id}-{library.get('Id', '')}`
   - 例如：`emby-123` 或 `jellyfin-456`

2. **合集来源库字段**
   - 使用 `boxset.get('SeriesId')` 获取来源库ID
   - 不同 Emby/Jellyfin 版本可能略有差异

3. **配置为空的含义**
   - `_selected_libraries` 为空 = 处理所有库（向后兼容）
   - `_exclude_boxsets` 为空 = 处理所有合集（无排除）

4. **日志输出**
   - 添加了 logger.info() 便于调试
   - 检查日志可以看到是否正确应用了过滤

---

## 💡 调试技巧

如果不确定某个库的ID，可以：

1. 启用调试日志：在 `__update_all_libraries()` 中添加
   ```python
   for library in libraries:
       lib_key = f"{service.id}-{library.get('Id', '')}"
       logger.info(f"处理库: {library.get('Name')} (ID: {lib_key})")
   ```

2. 根据输出的 ID，配置白名单和黑名单

---

## 📝 改动完整代码片段

### 类属性部分
```python
# 第 77-79 行
    _exclude_libraries = []
    _selected_libraries = []     # 新增
    _exclude_boxsets = []        # 新增
```

### init_plugin 部分
```python
# 第 133-135 行
            self._exclude_libraries = config.get("exclude_libraries")
            self._selected_libraries = config.get("selected_libraries", [])
            self._exclude_boxsets = config.get("exclude_boxsets", [])
```

### __update_config 部分
```python
# 第 220-222 行
            "exclude_libraries": self._exclude_libraries,
            "selected_libraries": self._selected_libraries,
            "exclude_boxsets": self._exclude_boxsets,
```

### __update_library 部分
```python
def __update_library(self, service, library):
    library_name = library['Name']
    logger.info(f"媒体库 {service.name}：{library_name} 开始准备更新封面")

    # 新增：库白名单检查
    if self._selected_libraries:
        lib_key = f"{service.id}-{library.get('Id', '')}"
        if lib_key not in self._selected_libraries:
            logger.info(f"库 {library_name} 不在白名单中，跳过")
            return False

    # 原有逻辑...
```

### __handle_boxset_library 部分
```python
# 在处理合集的循环中添加
for boxset in boxsets:
    # 新增：合集黑名单检查
    source_id = boxset.get('SeriesId')
    if source_id:
        boxset_key = f"{service.id}-{source_id}"
        if boxset_key in self._exclude_boxsets:
            logger.info(f"合集 {boxset.get('Name')} 来自黑名单库，跳过")
            continue

    # 原有逻辑...
```

---

## ✅ 完成标志

改动完成后，你应该能看到：

```
✅ 类中有 _selected_libraries 和 _exclude_boxsets 属性
✅ init_plugin() 中读取两个配置
✅ __update_config() 中保存两个配置
✅ __update_library() 开头有库白名单检查
✅ __handle_boxset_library() 循环中有合集黑名单检查
✅ 代码编译无错误
✅ 本地测试通过
```

现在可以开始改代码了！有问题随时问。

