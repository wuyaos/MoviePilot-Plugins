# Yuc 季度订阅 CLI

独立 Python 3.10+ 脚本，不是 MoviePilot 插件。沿用现有 `scripts/` 目录，不修改插件、前端或数据库。

## 运行

在自己的 Python 环境安装三个依赖：

```sh
python -m pip install -r scripts/requirements-season-subscribe.txt
python scripts/season_subscribe.py --year 2026 --month 10 \
  --mp-url http://127.0.0.1:17430 --mp-api-key-file /private/mp-key.txt \
  --proxy http://127.0.0.1:7890
```

如果已填写配置文件，可直接使用：

```sh
micromamba run -n season-subscribe python scripts/season_subscribe.py \
  --config scripts/season_subscribe.config.example.json
```

配置文件支持 `mp_url`、`mp_api_key`、`proxy`、`year`、`month`、`yuc_url`、`apply`；命令行参数优先。建议复制为本地文件后再填写密钥，并保持 `apply: false` 进行首次 dry-run。

本仓库 Windows 环境使用 `micromamba run -n base python` 代替 `python`。也可以用 `--yuc-url https://yuc.wiki/202610/`，URL 优先。API Key 文件只含密钥，UTF-8 编码，不要加入 Git；不提供文件时读取 `MP_API_KEY`。不支持命令行直接传密钥，避免 shell 历史泄漏。

- 默认 dry-run，也可显式加 `--dry-run`。**只有 `--apply` 加交互再次确认，才会 POST 创建订阅。**
- dry-run 仍联网抓页面、检索 Bangumi/AniList、读取 MP；不是离线模式。
- 代理只用于 Yuc、Bangumi、AniList；默认读取 `HTTPS_PROXY`，未配置则直连。需要直连时先取消该环境变量。MP 使用独立客户端直连，不携带代理环境配置，API Key 不会发给公开服务。
- MP URL 是根地址，不含 `/api/v1`；支持反向代理前缀。优先 HTTPS，HTTP 仅用于可信本地网络；不跟随 MP 重定向，避免凭据跨站转发。
- 逐部自动检索：Bangumi/AniList 用 Yuc 中文名+原名双查询，按 名称(4) > 年份(2) > 类型(1) 加检索排名打分；唯一明显领先才自动选中并显示匹配分。名称弱匹配（如罗马音对片假名）时拉 Bangumi 详情用别名复核。同名续作/重制分差不足时仍列候选人工核对，不自动猜续作。
- 主标题优先 Bangumi `name_cn` → AniList `title.native` → Yuc → 原名。AniList native 可能是日文，不等于中文译名；Yuc 标题另行显示。简介优先 Bangumi，缺失才用 AniList（可能为英文，不做机器翻译）。
- MP 用补充后的主标题自动识别，结果需单独确认；年份与季度相差大会警告续作/重制。列出所有返回的季、首播日期及订阅记录。输入 `2,3`、`S02,S03`、`all`；`0`/回车跳过，特别篇单独选 `S00`。
- 所选季在本部作品内统一确认，逐季提交前重新查询订阅；已订阅跳过。任一提示输入 `q` 可退出。提交失败不自动重试；网络超时也可能已创建，请先去 MP 核查。已提交内容不会回滚。
- 本工具只订阅 MP 识别为电视剧的作品；电影展示匹配结果后跳过。

## Yuc 结构假设

依据实际抓取的 `https://yuc.wiki/202610/` Hexo HTML：

1. `.intro` 内含“本期 … 共收录 N 部新番动画”，作为主列表起点，不用 meta description。
2. 其后的前 N 个 `title_main*` 作品单元分别位于详细表格中，内含 `title_cn*`、`title_jp*`；类型取 `type_a*`，补充首播取 `broadcast*`。后缀颜色差异不影响解析。检查全部详细单元数量及去重后数量，不一致必须确认才继续。
3. 起点之前 `.date2` 划分周一至周日和“网络放送 & 其他”；`date_title*` 所在浮动卡片提供日期、时间及 `.area` 地区。按规范化标题精确关联，不擅自合并同名多卡片。
4. `<br>` 按空格连接；缺中文标题用原名，完全缺失保留占位条目以便手动检索；相同规范化原名（缺原名用标题）去重并报警。规范化不删除季号或数字。
5. 不按开播月份、长短篇、年番、周放送/网络放送过滤。因此 9 月底提前播出及主列表内人工补录仍保留。N 之后的未来推荐不进入清单；若人工修改导致 N 过期，警告后需人工核对页面。

Yuc 改版可能破坏这些边界；找不到声明时停止，不猜测列表。放送时间保留原站 `25:30` 等格式，不转换时区。

## MP API 源码证据

适配本机 `D:/test/MoviePilot-v3`，不是猜测 V2 接口：

| 功能 | 请求 | 源码证据（相对上述根目录） |
|---|---|---|
| 路由前缀 | `/api/v1/media`、`/api/v1/subscribe` | `app/api/routers.py` 的 RouterSpec；`app/runtime/config.py:188` |
| 认证 | Header `X-API-KEY: <API_TOKEN>` | `app/adapters/web/security/access.py:48-51,307-341`；`app/api/dependencies/auth.py:90-141` |
| 媒体识别 | GET `/api/v1/media/recognize?title=...` | `app/api/endpoints/media.py:269-296`，返回 Context 的 `media_info` |
| 全部季 | GET `/api/v1/media/seasons?media_source=...&media_id=...` | `app/api/endpoints/media.py:663-729`，`season_number/name/air_date` |
| 订阅列表 | GET `/api/v1/subscribe/` | `app/api/endpoints/subscribe.py:200-222`；不传 page/count 保留全量，见 `app/api/response.py:95-105` |
| 创建 | POST `/api/v1/subscribe/` | `app/api/endpoints/subscribe.py:249-306`；`app/schemas/subscribe.py:207-219` |

创建 JSON 仅含 `name/year/type="电视剧"/media_source/media_id/season`。按来源、来源 ID、季号三元组查重。统一响应由 `app/api/response.py` 包装为 `success/message/data`；失败不当成功。旧版缺身份对时拒绝创建，不把 TMDB ID 硬猜成其他来源。不保证其他 MP 版本兼容。

## 离线验证

```sh
python -m unittest discover -s tests -p test_season_subscribe.py -v
```

HTML fixture 是手写结构缩减样例，不请求外网。API 使用 `httpx.MockTransport`，覆盖默认 dry-run、apply 二次确认、订阅身份、交互多季选择和已有订阅跳过。测试中的 POST 只发给 MockTransport，不联网。

开发验证未安装依赖：本机 base 缺三依赖，使用既有 mp3 环境的 httpx/bs4 及 base pip vendored rich，通过单次进程 `sys.path` 验证，不修改环境。这不等同于验证全新环境安装。实际 Bangumi/AniList 查询和 MP 真实实例联调、真实订阅未执行。
