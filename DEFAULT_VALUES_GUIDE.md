# 默认值显示补充指南

## 问题概述

### 当前状态
- **总字段数**: 33 个
- **有默认值**: 23 个（70%）
- **缺失默认值**: 10 个（30%）❌
- **hint 中提示默认值**: 7 个（仅 21%）❌
- **显示方式一致性**: 低

### 主要问题
1. **10 个字段缺失默认值定义**（都是可选路径/URL 字段）
2. **默认值展示方式不统一**（有的用 placeholder，有的在 hint，有的不显示）
3. **可选字段的空值行为不明确**（用户不知道留空会怎样）

---

## 问题详解

### 缺失默认值的 10 个字段

这些字段在 `get_form()` 返回的 dict 中**没有定义默认值**：

| 字段名 | 所在Tab | 字段类型 | 当前缺陷 | 应补充的默认值 |
|--------|--------|---------|--------|------------|
| `zh_font_path_local` | 封面风格 | VTextField | 返回 None | `""` |
| `en_font_path_local` | 封面风格 | VTextField | 返回 None | `""` |
| `covers_input` | 高级设置 | VTextField | 返回 None | `""` |
| `covers_output` | 高级设置 | VTextField | 返回 None | `""` |
| `zh_font_url` | 字体设置 | VTextField | 返回 None | `""` |
| `en_font_url` | 字体设置 | VTextField | 返回 None | `""` |
| `zh_font_path_multi_1_local` | 字体设置 | VTextField | 返回 None | `""` |
| `en_font_path_multi_1_local` | 字体设置 | VTextField | 返回 None | `""` |
| `zh_font_url_multi_1` | 字体设置 | VTextField | 返回 None | `""` |
| `en_font_url_multi_1` | 字体设置 | VTextField | 返回 None | `""` |

**风险**: 这些字段首次加载时值为 `None`，在 `init_plugin()` 中被赋值，但缺少 fallback 默认值（如 `config.get("field", "")`），可能导致字符串操作时报错。

### 默认值显示方式不一致

| 情况 | 字段举例 | 当前做法 | 问题 |
|------|--------|--------|------|
| 数值型 | `delay`, `blur_size` | `placeholder='60'` ✅ | 清晰明确 |
| 路径型 | `covers_output` | 无 placeholder | ❌ 用户不知道默认位置 |
| URL型 | `zh_font_url` | 无 placeholder | ❌ 用户不知道可否留空 |
| 可选字段 | `blur_size_multi_1` | hint="启用模糊时有效" | ❌ 没说默认值是多少 |

---

## 上游插件的最佳实践

### 核心原则（5 条）

1. **placeholder = 默认值**
   ```python
   'placeholder': '60'  # 默认值展示在此
   ```

2. **hint = 语义说明**
   ```python
   'hint': '等待媒体服务器扫描完成后再更新封面'  # 不包含数值
   ```

3. **persistentHint = True**
   ```python
   'persistentHint': True  # hint 常驻显示
   ```

4. **variant = 'outlined'**
   ```python
   'variant': 'outlined'  # 统一样式
   ```

5. **无"默认值："文字**
   ```python
   # ❌ 不这样写:
   'hint': '默认值：60'

   # ✅ 这样写:
   'placeholder': '60'
   'hint': '等待媒体服务器扫描完成后再更新封面'
   ```

### 不同字段类型的示例

#### 示例 1：数值字段
```python
{
    'component': 'VTextField',
    'props': {
        'model': 'delay',
        'label': '入库延迟（秒）',
        'placeholder': '60',              # ← 默认值在此
        'type': 'number',
        'hint': '等待媒体服务器扫描完成后再更新',  # ← hint 只说功能
        'persistentHint': True,
        'variant': 'outlined'
    }
}
```

#### 示例 2：可选路径字段
```python
{
    'component': 'VTextField',
    'props': {
        'model': 'covers_output',
        'label': '历史封面保存目录（可选）',
        'placeholder': '默认为插件数据目录',    # ← 默认值说明在此
        'prependInnerIcon': 'mdi-folder',
        'hint': '留空则保存在数据目录，否则保存到指定目录',  # ← 空值行为
        'persistentHint': True,
        'variant': 'outlined'
    }
}
```

#### 示例 3：条件禁用字段
```python
{
    'component': 'VTextField',
    'props': {
        'model': 'blur_size_multi_1',
        'label': '背景模糊程度',
        'placeholder': '50',              # ← 默认值
        'type': 'number',
        'hint': '启用多图模糊时有效；禁用时忽略此值',  # ← 条件+行为
        'persistentHint': True,
        'variant': 'outlined',
        'disabled': '{{ !multi_1_blur }}'
    }
}
```

#### 示例 4：开关字段
```python
{
    'component': 'VSwitch',
    'props': {
        'model': 'single_use_primary',
        'label': '优先使用海报图',
        'hint': '关闭则优先使用背景图',  # ← hint 说反义行为（默认为 False）
        'persistentHint': True
    }
}
```

---

## 修复方案

### 方案 A：补齐所有缺失的默认值（推荐）

**位置**: `get_form()` 返回的第二个元素（defaults dict）

**修改**:
```python
return [
    # ... form definition ...
], {
    # ... 现有默认值 ...

    # 新增缺失的 10 个字段默认值
    "zh_font_path_local": "",
    "en_font_path_local": "",
    "covers_input": "",
    "covers_output": "",
    "zh_font_url": "",
    "en_font_url": "",
    "zh_font_path_multi_1_local": "",
    "en_font_path_multi_1_local": "",
    "zh_font_url_multi_1": "",
    "en_font_url_multi_1": "",
}
```

### 方案 B：更新 init_plugin() 中的 fallback

**位置**: `init_plugin()` 方法中的 `config.get()` 调用

**修改前**:
```python
self._zh_font_url = config.get("zh_font_url")  # 可能返回 None
```

**修改后**:
```python
self._zh_font_url = config.get("zh_font_url", "")  # 默认返回空字符串
```

**需要修改的 10 处**（搜索这些字段名）:
```bash
grep -n "config.get.*zh_font_url\|config.get.*en_font_url\|config.get.*covers_" \
  plugins.v2/mediacovergeneratorcustom/__init__.py
```

### 方案 C：统一所有字段的默认值显示方式

#### 数值字段（数值类）
统一加 `placeholder` 和改进 `hint`:

**改前**:
```python
{
    'component': 'VTextField',
    'props': {
        'model': 'blur_size_multi_1',
        'label': '背景模糊程度',
        'hint': '启用模糊时有效'
    }
}
```

**改后**:
```python
{
    'component': 'VTextField',
    'props': {
        'model': 'blur_size_multi_1',
        'label': '背景模糊程度',
        'type': 'number',
        'placeholder': '50',              # ← 加 placeholder
        'hint': '默认 50；启用多图模糊时有效',  # ← 补充默认值说明
        'persistentHint': True,
        'variant': 'outlined'
    }
}
```

#### 路径/URL 字段
统一加 `placeholder` 说明默认行为：

**改前**:
```python
{
    'component': 'VTextField',
    'props': {
        'model': 'covers_output',
        'label': '历史封面保存目录（可选）',
        'hint': '生成的封面默认保存在本插件数据目录下'
    }
}
```

**改后**:
```python
{
    'component': 'VTextField',
    'props': {
        'model': 'covers_output',
        'label': '历史封面保存目录（可选）',
        'placeholder': '默认为插件数据目录',        # ← 加 placeholder
        'hint': '留空则保存在数据目录；否则保存到指定路径',  # ← 改为说空值行为
        'persistentHint': True,
        'variant': 'outlined',
        'prependInnerIcon': 'mdi-folder'
    }
}
```

---

## 实施清单

### 优先级排序

**P0 关键**（必须做）:
- [ ] 补齐 10 个字段在 `get_form()` 返回 dict 中的默认值定义
- [ ] 更新 `init_plugin()` 中所有 `config.get()` 的 fallback 默认值

**P1 改进**（应该做）:
- [ ] 为所有路径/URL 字段加 `placeholder` 说明默认行为
- [ ] 为所有数值字段的 hint 补充默认值说明
- [ ] 为所有可选字段的 hint 说明"留空时的行为"

**P2 优化**（可以做）:
- [ ] 统一所有 VTextField 加 `variant='outlined'`
- [ ] 统一所有有 hint 的字段加 `persistentHint=True`

### 验证脚本

```bash
# 1. 检查缺失默认值
grep -A 50 "return \[" plugins.v2/mediacovergeneratorcustom/__init__.py | \
  grep -E "zh_font_url|en_font_url|covers_" | wc -l
# 应输出: 10（表示 10 个字段都有默认值）

# 2. 检查 init_plugin() 的 fallback
grep "config.get.*zh_font_url\|config.get.*covers_" plugins.v2/mediacovergeneratorcustom/__init__.py | \
  grep -v 'config.get.*""' | wc -l
# 应输出: 0（表示所有都有 fallback）

# 3. 检查 placeholder 一致性
grep -c "placeholder'" plugins.v2/mediacovergeneratorcustom/__init__.py
# 应输出: >= 20（表示至少 20 个字段有 placeholder）
```

---

## 示例：完整修改流程

### 步骤 1：补齐返回 dict 中的默认值

```python
# 第 2375-2435 行，get_form() 返回的 defaults dict

return [
    # ... form structure ...
], {
    "enabled": True,
    # ... 其他默认值 ...

    # 新增这 10 行:
    "zh_font_path_local": "",              # P0.1
    "en_font_path_local": "",              # P0.1
    "covers_input": "",                    # P0.1
    "covers_output": "",                   # P0.1
    "zh_font_url": "",                     # P0.1
    "en_font_url": "",                     # P0.1
    "zh_font_path_multi_1_local": "",      # P0.1
    "en_font_path_multi_1_local": "",      # P0.1
    "zh_font_url_multi_1": "",             # P0.1
    "en_font_url_multi_1": "",             # P0.1
}
```

### 步骤 2：更新 init_plugin() 的所有 fallback

```python
# 第 160-195 行，init_plugin() 方法

# 改前:
self._zh_font_url = config.get("zh_font_url")
self._en_font_url = config.get("en_font_url")
self._covers_input = config.get("covers_input")
self._covers_output = config.get("covers_output")
# ... 等等

# 改后:
self._zh_font_url = config.get("zh_font_url", "")
self._en_font_url = config.get("en_font_url", "")
self._covers_input = config.get("covers_input", "")
self._covers_output = config.get("covers_output", "")
# ... 等等
```

### 步骤 3：为路径字段补充 placeholder 和 hint

在 `style_tab` 或对应 Tab 中，找到路径字段并修改：

```python
# 改前:
{
    'component': 'VTextField',
    'props': {
        'model': 'covers_output',
        'label': '历史封面保存目录（可选）',
        'hint': '生成的封面默认保存在本插件数据目录下'
    }
}

# 改后:
{
    'component': 'VTextField',
    'props': {
        'model': 'covers_output',
        'label': '历史封面保存目录（可选）',
        'placeholder': '默认为插件数据目录',
        'hint': '留空则保存在数据目录；否则保存到指定路径',
        'persistentHint': True,
        'variant': 'outlined',
        'prependInnerIcon': 'mdi-folder'
    }
}
```

---

## 测试验证

### 单元测试检查

```python
# 在 init_plugin() 后检查
def test_default_values():
    plugin = MediaCoverGeneratorCustom()
    plugin.init_plugin()

    # 这些字段应该都不是 None
    assert plugin._zh_font_url == "" or isinstance(plugin._zh_font_url, str)
    assert plugin._covers_output == "" or isinstance(plugin._covers_output, str)
    # ... 等等
```

### UI 视觉检查

在 MoviePilot 中，进入插件配置页，逐一检查：
- [ ] 所有数值字段都显示默认值（placeholder）
- [ ] 所有路径字段都明确说明"留空时的行为"
- [ ] 所有可选字段的 hint 清晰明确
- [ ] 所有字段都有 `persistentHint`（hint 常驻显示）

---

## 预期收益

- ✅ 10 个字段的缺失默认值问题解决
- ✅ 用户清楚各字段的默认值和空值行为
- ✅ 减少因 `None` 值导致的运行时错误
- ✅ UI 显示更清晰一致

---

**文档版本**: v1.0
**最后更新**: 2026-03-08
**维护者**: Claude Code
