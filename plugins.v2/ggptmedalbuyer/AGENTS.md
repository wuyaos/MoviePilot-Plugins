# GGPTMedalBuyer

GGPT 疯狂星期四勋章自动续购插件。

## 来源

- 移植自 [`jiangbkvir/MoviePilot-Plugins`](https://github.com/jiangbkvir/MoviePilot-Plugins) 的 `plugins.v2/ggptmedalbuyer`
- 原作者：`jiangbkvir`
- 当前维护：`wuyaos`

## 版本

- `v1.0.0`：原版功能（自动购买、预计下次购买时间、购买记录、通知提醒）
- `v1.0.1`：修复到期时间解析缺陷（详见下方「修复说明」）

## 修复说明（v1.0.1）

原版存在两个关联 bug，导致「可以买勋章但没买」：

### Bug 1：勋章页 `__parse_owned_expire_time` 误匹配

原实现用 `medal_id` 在**全页文本**中 `find` 搜索：

```python
keywords = [medal_name, DEFAULT_MEDAL_NAME, self._medal_id]  # ["疯狂星期四", "疯狂星期四", "35"]
for keyword in keywords:
    idx = plain.find(str(keyword))   # plain.find("35")
```

页面里 `分享率: 3.935` 含「35」，`find("35")` 命中的是**这里**（而非勋章 ID=35 的行）。该位置附近恰好有其他勋章的「有效期」字样与日期，于是返回 `2025-10-15`（中秋节勋章结束日期）污染 `page_expire_at`，并直接 return 跳过个人中心解析。

### Bug 2：个人中心 `__parse_userdetails_expire_time` 碰运气

原实现取所有「过期时间」标签里**最早的未来时间**：

```python
return min(future_times)  # 不匹配勋章名
```

当用户持有多个到期时间不同的勋章时，可能返回**别的勋章**的时间。

### 修复方案

1. `__medal_html_context`：用购买按钮 `<input data-id="35">` 锚定位置，向前取最近的 `<tr>`，向后取最近的 `<tr>` 或 `</table>` 作为行边界，提取**单行** HTML（兼容 NexusPHP 省略 `</tr>` 的写法）。修复前 context 为 16274 字符（整表），修复后 574 字符（单行）。
2. `__parse_owned_expire_time`：只在单行内查找日期。疯狂星期四行是 `不限 ~ 不限`，行内无日期 → 返回 `None` → 上层走个人中心分支读取真实到期时间。
3. `__parse_userdetails_expire_time`：用 `<img title="疯狂星期四">` 锚定，取其后最近的 `过期时间` span，精确匹配到当前勋章。
4. `logger.warn` 全部改为 `logger.warning`（Python 3.12+ 已弃用 `warn`）。

## 验证

用真实页面数据（gamegamept.com 勋章页 + 个人中心）验证：

| 测试项 | 修复前 | 修复后 |
|--------|--------|--------|
| `__medal_html_context` 行长度 | 16274 | 574 |
| `__parse_owned_expire_time` (ID=35) | `2025-10-15` ❌ | `None` ✅ |
| `__parse_userdetails_expire_time` (疯狂星期四) | 碰运气 | `2026-07-29 21:18` ✅ |
| 交叉验证：明末：渊虚之羽 | 可能错 | `2026-09-02 23:16` ✅ |
| 交叉验证：火伞高张（永久有效） | 返回日期 | `None` ✅ |
| 边界：ID=51（有日期范围） | — | `2025-10-15` ✅ |

## 结构

```
ggptmedalbuyer/
├── __init__.py      # 插件主入口（GGPTMedalBuyer 类）
├── README.md        # 用户文档（含来源声明）
└── AGENTS.md        # 本文件
```

## 关键常量

- `SITE_DOMAIN = "gamegamept.com"`
- `DEFAULT_MEDAL_ID = "35"`（疯狂星期四）
- `DEFAULT_MEDAL_NAME = "疯狂星期四"`
- `DEFAULT_VALID_DAYS = 7`
- 购买接口：`POST /ajax.php`，body `action=buyMedal&params[medal_id]=35`
- 勋章页：`GET /medal.php`
- 个人中心：`GET /userdetails.php?id=<uid>`（uid 从 `c_secure_pass` cookie base64 解码 JSON 取 `user_id`）

## 依赖

- MoviePilot 站点管理中需配置 GGPT 站点（domain=gamegamept.com），Cookie 保持有效
- 图标使用仓库 `icons/medal.png`（与其他勋章插件统一）
