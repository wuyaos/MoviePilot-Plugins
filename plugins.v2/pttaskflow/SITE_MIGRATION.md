# PtTaskFlow 站点迁移矩阵

> 目标：替代 `SiteAutoTask`。SiteAutoTask 保持原提交状态，不与本插件共享运行配置或执行锁。

## 站点覆盖

| 站点 | 域名 | 任务 | 特殊能力 | 状态 |
|---|---|---|---|---|
| Azusa | azusa.wiki | CLAIM | task.php CSRF | 已迁移，WAF 需 render 环境验证 |
| 藏宝阁 | cangbao.ge | CHECKIN/CLAIM/CHAT | 60s、系统反馈 | 已迁移 |
| CARPT | carpt.net | CHECKIN/CLAIM | 标准 JSON claim | 已迁移 |
| 13City | 13city.org | CHECKIN/CLAIM/CHAT/勋章检查 | 喊话前诸神赐福 | 已迁移，勋章需无副作用 mock 验证 |
| 蟹黄堡 | crabpt.vip | CHECKIN/CLAIM | 标准 JSON claim | 已迁移 |
| 财神 | cspt.top | CHECKIN/CLAIM | 标准 JSON claim | 已迁移 |
| 大青虫 | cyanbug.net | CHECKIN/CHAT | 60s | 已迁移 |
| 天枢 | dubhe.to | CHECKIN/CHAT | 随机反馈 | 已迁移 |
| 自由农场 | 0ff.cc | CHECKIN/CLAIM | 标准 JSON claim | 已迁移 |
| GGPT | gamegamept.com | CHECKIN/MEDAL | 固定勋章 35 | 已迁移，购买需授权验证 |
| 好学 | haoxue.net | CHECKIN/CHAT/CLAIM | AJAX 快照、no-retry | 已迁移，发送接口需真实站点验证 |
| 垃圾堆 | lajidui.top | CHECKIN/CLAIM | 标准 JSON claim | 已迁移 |
| LongPT | longpt.org | CHECKIN/CLAIM/CHAT/LOTTERY | 单选 API 喊话、抽奖 | 已迁移，API 需 mock 验证 |
| LuckPT | luckpt.de | CHECKIN/CHAT | wish-bubble 外部反馈 | 已迁移 |
| Moment | m-team.io | CHECKIN/CHAT | 双向反馈、120s | 已迁移 |
| myPT | mypt.cc | CHECKIN/MEDAL | 多选勋章 | 已迁移，购买需授权验证 |
| NovaHD | novahd.top | CHECKIN/CLAIM | 标准 JSON claim | 已迁移 |
| PTLGS | ptlgs.org | CHECKIN/CHAT | 时间前缀、负面损失 | 已迁移 |
| PTSKit | ptskit.org | CHECKIN/CLAIM/CHAT | 顶部外部奖励 | 已迁移 |
| 青蛙 | qingwapt.com | CHECKIN/CHAT/EXCHANGE | li 行、动态商品 | 已迁移，兑换需 mock 验证 |
| RailgunPT | bilibili.download | CHECKIN/CHAT | 标准 Profile | 已迁移 |
| 躺平 | tangpt.top | CHECKIN/CLAIM | 标准 JSON claim | 已迁移 |
| Vc-Lib | vclib.online | CHECKIN/CLAIM/复合任务 | 每周上传兑换 | 已迁移；MP 站点优先本地 Cookie，内置站点 CookieCloud 缓存/单次刷新已 mock 验证；真实兑换需授权 |
| 织梦 | zmpt.cc | CHECKIN/CHAT | 60s、邮件时间、24h date | 已迁移，date 续排需验证 |

共 **24 个站点**。任务名称固定为 `daily_checkin`、`daily_shotbox`、`claim`、`buy_medal`、`daily_lottery`、`daily_exchange` 或站点原有复合任务名，配置键由 `task_{site_id}_{task_name}` 生成。

## 运行边界

- 禁止与 SiteAutoTask 同时对同一站点启用相同副作用任务。
- 默认不进行真实签到、喊话、勋章购买、兑换；真实验证需用户逐项授权。
- Azusa WAF、LongPT API、13City 勋章、Vc-Lib 真实兑换、织梦 date 续排必须在授权条件下单独验收。
- Cookie 生命周期已通过 mock 验证：MP 站点失效不切换 CookieCloud；内置站点缓存 CookieCloud Cookie，失效仅刷新一次，失败返回明确错误。

## 外部可重跑验证命令

工作目录：`/mnt/d/work/project/person/MoviePilot-Plugins`

```bash
cd /mnt/d/work/project/person/MoviePilot-Plugins
python3 -m unittest discover -s plugins.v2/pttaskflow/tests -p 'test_*.py'
python3 -m unittest discover -s plugins.v2/siteautotask/tests -p 'test_*.py'
python3 -c "import ast,pathlib;[ast.parse(p.read_text()) for p in pathlib.Path('plugins.v2/pttaskflow').rglob('*.py')];print('AST OK')"
pyflakes $(find plugins.v2/pttaskflow -name '*.py')
python3 -m json.tool package.v2.json >/dev/null
python3 - <<'PY'
from PIL import Image
im=Image.open('icons/pttaskflow.png')
assert im.size == (200, 200) and im.mode == 'RGBA'
print('ICON OK')
PY
find plugins.v2/pttaskflow -type d -name __pycache__ -prune -exec rm -rf {} +
git diff --check
test -z "$(git status --short plugins.v2/siteautotask/)"
```

运行态（本地 MP，API token 不写入仓库）：

```bash
curl -sS http://127.0.0.1:7300/api/v1/plugin/reload/PtTaskFlow \
  -H 'X-API-KEY: <LOCAL_API_TOKEN>'
curl -sS http://127.0.0.1:7300/api/v1/plugin/form/PtTaskFlow \
  -H 'X-API-KEY: <LOCAL_API_TOKEN>'
curl -sS http://127.0.0.1:7300/api/v1/plugin/page/PtTaskFlow \
  -H 'X-API-KEY: <LOCAL_API_TOKEN>'
```
