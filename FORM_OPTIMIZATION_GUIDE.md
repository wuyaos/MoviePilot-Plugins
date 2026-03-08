# MediaCoverGeneratorCustom 表单优化与逻辑重组指南

## 目录
1. [执行概览](#执行概览)
2. [P0 高优修复](#p0-高优修复)
3. [P1 中优改进](#p1-中优改进)
4. [P2 低优优化](#p2-低优优化)
5. [验证清单](#验证清单)
6. [风险评估](#风险评估)

---

## 执行概览

### 当前状态
- **get_form() 总行数**: 1572 行（包含 520 行死代码）
- **活跃 Tab**: 4 个（basic、style、library、advanced）
- **死代码 Tab**: 1 个（font_tab，从未挂载）
- **重复渲染字段**: 10 个
- **逻辑 Bug**: 1 个（selected_users 未传递）

### 优化目标
- **删减代码**: 1572 → ~1132 行（减少 28%）
- **消除死代码**: 520 行 → 0 行
- **修复 BUG**: 1 个
- **提升可维护性**: 消除字段重复、统一命名规则

### 预期影响
- ✅ 配置逻辑更清晰
- ✅ 用户筛选功能完整可用
- ✅ 代码冗余度降低
- ⚠️ 需要完整测试验证

---

## P0 高优修复

### P0.1 删除 font_tab 死代码

**影响范围**: 第 1149-1670 行（520 行）

**步骤**:

1. **定位代码块**
```
第 1149 行: # 字体设置标签
第 1670 行: ]  # font_tab 结束
```

2. **精确删除范围**
```python
# 删除以下完整代码块：
        # 字体设置标签
        single_tab = [
            # ... 520 行字体配置代码 ...
        ]
```

**检查清单**:
- [ ] 确认删除前备份原文件
- [ ] 确认删除的是 `single_tab = [` 到对应 `]`
- [ ] 保留 `# 更多参数标签` 注释（第 1671 行）
- [ ] 保留 `single_tab = [` 的定义（第 1671 行起，多图设置）

3. **验证删除正确性**
```bash
# 删除后，应该在第 1149 行附近看到：
# 更多参数标签  # (原第 1671 行，现第 1149 行)
single_tab = [
    {
        'component': 'VRow',
        ...
    }
]
```

---

### P0.2 修复 selected_users BUG

**症状**: 用户筛选字段在 UI 上有，但过滤逻辑不生效

**根本原因**:
```python
# 第 2081-2088 行（__generate_from_server 方法）
selected_user_ids = self.__get_selected_user_ids(...)  # ✅ 获取了
# ... 处理代码 ...
batch_items = self.__get_items_batch(
    service, parent_id,
    offset=offset, limit=batch_size,
    include_types=include_types
    # ❌ 缺少: user_ids=selected_user_ids
)
```

**修复步骤**:

1. **定位方法**
```python
# 文件: plugins.v2/mediacovergeneratorcustom/__init__.py
# 行号: 第 2081-2088 行
# 方法: def __generate_from_server(self, service, library, ...)
```

2. **修改代码**
```python
# 改前（第 2084-2088 行）:
batch_items = self.__get_items_batch(service, parent_id,
                                  offset=offset, limit=batch_size,
                                  include_types=include_types)

# 改后:
batch_items = self.__get_items_batch(service, parent_id,
                                  offset=offset, limit=batch_size,
                                  include_types=include_types,
                                  user_ids=selected_user_ids)
```

3. **验证其他调用点**
检查 `__get_items_batch()` 方法的其他 2 个调用点是否也需要修复：
- [ ] 搜索其他 `__get_items_batch` 调用
- [ ] 确认是否都需要传递 `user_ids`
- [ ] 检查 `__get_items_batch()` 的方法签名是否支持 `user_ids` 参数

---

### P0.3 恢复缺失的字体 URL 字段到 style_tab

**缺失字段** (原在 font_tab，需恢复到 style_tab):
- `zh_font_url`
- `en_font_url`
- `zh_font_url_multi_1`
- `en_font_url_multi_1`
- `zh_font_path_multi_1_local`
- `en_font_path_multi_1_local`
- `zh_font_size_multi_1`
- `en_font_size_multi_1`

**恢复步骤**:

1. **在 style_tab 中定位字体设置区域**
```python
# 第 800-968 行存在"字体设置"部分
# 在该区域的末尾添加缺失的多图字体大小字段
```

2. **添加多图字体 URL 字段**
```python
# 在 style_tab 的适当位置（字体设置末尾）添加：
{
    'component': 'VRow',
    'props': {'dense': True, 'class': 'mt-3'},
    'content': [
        {
            'component': 'VCol',
            'props': {'cols': 12, 'md': 6},
            'content': [
                {
                    'component': 'VTextField',
                    'props': {
                        'model': 'zh_font_url_multi_1',
                        'label': '多图中文字体URL',
                        'prependInnerIcon': 'mdi-link',
                        'hint': '多图模式下使用的中文字体在线URL',
                        'persistentHint': True
                    }
                }
            ]
        },
        {
            'component': 'VCol',
            'props': {'cols': 12, 'md': 6},
            'content': [
                {
                    'component': 'VTextField',
                    'props': {
                        'model': 'en_font_url_multi_1',
                        'label': '多图英文字体URL',
                        'prependInnerIcon': 'mdi-link',
                        'hint': '多图模式下使用的英文字体在线URL',
                        'persistentHint': True
                    }
                }
            ]
        }
    ]
}
```

3. **添加多图本地字体路径字段**
```python
{
    'component': 'VRow',
    'props': {'dense': True, 'class': 'mt-3'},
    'content': [
        {
            'component': 'VCol',
            'props': {'cols': 12, 'md': 6},
            'content': [
                {
                    'component': 'VTextField',
                    'props': {
                        'model': 'zh_font_path_multi_1_local',
                        'label': '多图中文字体本地路径',
                        'prependInnerIcon': 'mdi-file-document',
                        'hint': '多图模式下使用的本地中文字体路径',
                        'persistentHint': True
                    }
                }
            ]
        },
        {
            'component': 'VCol',
            'props': {'cols': 12, 'md': 6},
            'content': [
                {
                    'component': 'VTextField',
                    'props': {
                        'model': 'en_font_path_multi_1_local',
                        'label': '多图英文字体本地路径',
                        'prependInnerIcon': 'mdi-file-document',
                        'hint': '多图模式下使用的本地英文字体路径',
                        'persistentHint': True
                    }
                }
            ]
        }
    ]
}
```

4. **添加多图字体大小字段**
```python
{
    'component': 'VRow',
    'props': {'dense': True, 'class': 'mt-3'},
    'content': [
        {
            'component': 'VCol',
            'props': {'cols': 12, 'md': 6},
            'content': [
                {
                    'component': 'VTextField',
                    'props': {
                        'model': 'zh_font_size_multi_1',
                        'label': '多图中文字体大小',
                        'prependInnerIcon': 'mdi-format-size',
                        'hint': '多图模式下中文字体相对大小（倍数）',
                        'persistentHint': True
                    }
                }
            ]
        },
        {
            'component': 'VCol',
            'props': {'cols': 12, 'md': 6},
            'content': [
                {
                    'component': 'VTextField',
                    'props': {
                        'model': 'en_font_size_multi_1',
                        'label': '多图英文字体大小',
                        'prependInnerIcon': 'mdi-format-size',
                        'hint': '多图模式下英文字体相对大小（倍数）',
                        'persistentHint': True
                    }
                }
            ]
        }
    ]
}
```

5. **在 get_form() 返回字典中确保这些字段有默认值**
```python
# 检查 return [{...}, {...}] 的第二个元素（defaults dict）
# 确保包含：
"zh_font_url_multi_1": "",
"en_font_url_multi_1": "",
"zh_font_path_multi_1_local": "",
"en_font_path_multi_1_local": "",
"zh_font_size_multi_1": 1,
"en_font_size_multi_1": 1,
```

---

## P1 中优改进

### P1.1 提取重复的用户筛选逻辑

**现象**: `__get_selected_user_ids()` 逻辑被重复调用 3 次

**步骤**:

1. **搜索重复位置**
```bash
grep -n "__get_selected_user_ids\|selected_user_ids = " plugins.v2/mediacovergeneratorcustom/__init__.py
```

2. **标准化提取方式**
确保所有调用都使用同一个 helper 方法：
```python
def __get_selected_user_ids(self, service):
    """获取选中的用户 ID 列表"""
    if not self._selected_users:
        return None

    user_map = service.instance.get_users() if hasattr(service.instance, 'get_users') else {}
    return [user_map.get(user_name) for user_name in self._selected_users if user_map.get(user_name)]
```

3. **统一所有调用点**
```python
# 改前（分散的 7 行逻辑）:
selected_user_ids = None
if self._selected_users:
    user_map = service.instance.get_users() if hasattr(...) else {}
    selected_user_ids = [user_map.get(u) for u in self._selected_users if user_map.get(u)]

# 改后（统一调用）:
selected_user_ids = self.__get_selected_user_ids(service)
```

---

## P2 低优优化

### P2.1 统一 hint 属性的拼写

**现象**: 部分字段用 `persistentHint`，部分用 `persistent-hint`

**步骤**:
```bash
# 搜索不一致的拼写
grep -n "persistent-hint\|persistentHint" plugins.v2/mediacovergeneratorcustom/__init__.py | head -20

# 确保全部使用 'persistentHint'（camelCase）
```

### P2.2 统一字段命名规则

**规则**:
- 单图相关字段后缀: `_single`
- 多图相关字段后缀: `_multi_1` (或 `_multi`)
- 位置: 后缀统一放在末尾

**例子**:
```python
# 改前（不一致）:
zh_font_path_multi_1_local  # multi_1 在中间
blur_size_multi_1           # multi_1 在末尾

# 改后（统一）:
zh_font_path_local_multi_1
blur_size_multi_1
```

---

## 验证清单

在完成所有修改后，按以下顺序验证：

### 语法验证
```bash
cd /path/to/MoviePilot-Plugins
python3 -m py_compile plugins.v2/mediacovergeneratorcustom/__init__.py
# 应输出: 无错误
```

### 代码行数验证
```bash
# 数 get_form() 的行数
grep -n "def get_form\|return \[" plugins.v2/mediacovergeneratorcustom/__init__.py | head -2
# 应该看到: 开始行 ~ 结束行，总数约 1132 行（比原 1572 行少 440 行）
```

### 字段可达性验证
```bash
# 确保所有 8 个缺失字段在返回的 defaults dict 中
grep -E "zh_font_url_multi_1|en_font_url_multi_1|zh_font_path_multi_1_local" plugins.v2/mediacovergeneratorcustom/__init__.py
# 应该在 get_form() 返回的 dict 中各出现 1 次
```

### 用户筛选 BUG 验证
```bash
# 确保 user_ids 参数已添加
grep -A3 "__get_items_batch" plugins.v2/mediacovergeneratorcustom/__init__.py | grep -c "user_ids"
# 应该至少出现 1 次
```

### 功能测试
- [ ] 启用插件并进入配置页
- [ ] 验证字体设置部分是否完整显示（包含新添加的多图字体字段）
- [ ] 验证用户筛选功能是否可用（选择用户后生成封面，检查是否过滤）
- [ ] 验证基础功能是否正常（仍能生成封面）

---

## 风险评估

### 高风险项
| 项 | 风险 | 缓解措施 |
|---|------|--------|
| 删除 font_tab | 误删其他代码块 | 删除前多次确认范围、备份原文件 |
| 修改 user_ids 参数 | 参数类型错误 | 检查 `__get_items_batch()` 方法签名 |

### 中风险项
| 项 | 风险 | 缓解措施 |
|---|------|--------|
| 添加多图字体字段 | 字段位置错误 | 在 style_tab 的明确位置添加 |
| 命名规则统一 | 改名导致配置不兼容 | 仅改字段名，数据库 key 保持不变 |

### 低风险项
| 项 | 风险 | 缓解措施 |
|---|------|--------|
| 提取重复逻辑 | 逻辑改变 | 提取前后对比测试 |
| 统一拼写 | 无 | 直接替换即可 |

### 回滚计划
```bash
# 如果出现问题，回滚到之前的版本：
git checkout HEAD -- plugins.v2/mediacovergeneratorcustom/__init__.py
```

---

## 后续维护

修改完成后的建议：
1. **提交 commit**: 包含详细的修改说明
2. **创建新版本**: 更新 package.v2.json 中的版本号
3. **更新 CHANGELOG**: 记录这次优化的详细内容
4. **用户沟通**: 如果有breaking change，通知用户

---

## 问题排查

### 修改后启动失败
```bash
# 查看错误日志
tail -100 /path/to/moviepilot/logs/*.log | grep -i "mediacovergenerator"

# 常见问题：
# 1. 语法错误 → 检查删除的代码块范围
# 2. 缺失字段 → 检查 defaults dict 是否包含所有新字段
# 3. BUG 修复失败 → 检查参数类型是否匹配
```

### 配置加载失败
```python
# 确保 init_plugin() 中有对应的字段读取
config.get('zh_font_url_multi_1', '')
config.get('en_font_url_multi_1', '')
...
```

---

**文档版本**: v1.0
**最后更新**: 2026-03-08
**维护者**: Claude Code
