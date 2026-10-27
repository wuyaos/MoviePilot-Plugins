# MP 本地调试环境调用规范

本地 MoviePilot V3 调试实例的调用方式。只记录环境事实与命令；通用调试流程见 `.pi/skills/moviepilot-debug/SKILL.md`。

## 实例概览

| 项 | 值 |
|---|---|
| 实例根 | `D:\test\MoviePilot-v3`（V3 源码 checkout） |
| 后端 API | `http://127.0.0.1:17430`（`config/app.env` 的 `PORT`） |
| 前端 | `http://127.0.0.1:17431`（`config/app.env` 的 `NGINX_PORT`） |
| API Key | 文件 `D:/tmp/.mp_local_key`（与 `app.env` 的 `API_TOKEN` 同值；**调用时从文件读，不硬编码**） |
| 站点认证 | `AUTH_SITE=audiences` + `AUDIENCES_UID/PASSKEY`（在 `app.env`，**认证失败=插件系统整体不装载**，登录报「登录失败，请检查网络连接」同因） |
| 插件仓库联动 | `app.env` 的 `PLUGIN_LOCAL_REPO_PATHS=D:\work\project\person\MoviePilot-Plugins`（实例直接感知本仓库） |

## 启动 / 停止

**首选 `mp.ps1`**（实例根下，实测可用）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File D:\test\MoviePilot-v3\mp.ps1 start    # 加载 app.env 后最小化窗口启动
powershell -NoProfile -ExecutionPolicy Bypass -File D:\test\MoviePilot-v3\mp.ps1 stop     # 按 17430 端口找 pid 强杀
powershell -NoProfile -ExecutionPolicy Bypass -File D:\test\MoviePilot-v3\mp.ps1 restart
powershell -NoProfile -ExecutionPolicy Bypass -File D:\test\MoviePilot-v3\mp.ps1 status
```

要点：

- `python app/main.py` **直启不读 `app.env`**（读 env 是 CLI 的职责），mp.ps1 已内置解析（剥单引号）。手工 bash 启动必须 `set -a && source config/app.env && set +a`，否则认证/插件全挂。
- `mp.ps1` 已加 UTF-8 BOM——PowerShell 5.1 读无 BOM 的中文脚本会乱码破坏语法。
- 启动后插件异步装载，被 GitHub 索引请求超时拖慢，**约 1-2 分钟后插件才可用**；验证装载看 `GET /api/v1/plugin/remotes?token=moviepilot`。
- 弃用 `moviepilot` CLI：依赖工程 `.venv`（未建），且残留前端进程时端口检测误判报「前端正在运行」。
- mp3 editable 环境：`micromamba run -n mp3 python app/main.py`；运行日志 `config/logs/`。
## 探活与鉴权

```bash
# 探活（/docs 返回 404 属正常——文档路由未开，TCP 连通即实例在跑）
curl -s -o /dev/null -w '%{http_code}' --connect-timeout 3 http://127.0.0.1:17430/docs

# 带 key 调用（key 从文件读；key 无效时返回 404 而非 401，别按「路由不存在」处理）
curl -sS "http://127.0.0.1:17430/api/v1/plugin/form/AutoPtCheckin" \
  -H "X-API-KEY: $(cat /d/tmp/.mp_local_key)"
```

### 宿主插件端点（本地 17430 实测，2026-10-28）

| 用途 | 方法与路径 | 说明 |
|---|---|---|
| 读配置 | `GET  /api/v1/plugin/<Id>` | 返回 `data` = 完整配置 dict |
| 写配置 | `PUT  /api/v1/plugin/<Id>` | body 必须是**完整**配置 dict |
| 前端表单 | `GET  /api/v1/plugin/form/<Id>` | 返回 `render_mode/conf/model` |
| 重载插件 | `POST /api/v1/plugin/reload/<Id>` | GET 会 405 |
| 插件业务 | `POST /api/v1/plugin/<Id>/<action>` | 插件注册的 action 路由 |
| 运行数据 | `GET  /api/v1/plugin/runtime/<Id>/data/summary` | |

反例：`/api/v1/plugin/config/<Id>`（把 `config` 插在 id 前）与 `/api/v1/plugin/<Id>/config` 在本实例**都是 404**。别再凭印象拼路径，先用上表核对一次。

## 插件部署与重载

实例内插件有两份位置，**只有 `app/plugins/<lower(id)>` 在 V3 加载路径上**：

- `app/plugins/autoptcheckin` —— 生效代码，部署目标
- `config/plugins/AutoPtCheckin` —— V2 风格中心副本，不直接生效

部署本仓库最新代码到本地实例后重载：

```bash
# 1. 覆盖生效目录（整目录替换，勿散拷）
rm -rf /d/test/MoviePilot-v3/app/plugins/autoptcheckin
mkdir -p /d/test/MoviePilot-v3/app/plugins/autoptcheckin
cp -r plugins.v3/autoptcheckin/{__init__.py,core,sites,helper,integrations,dist,*.json} \
      /d/test/MoviePilot-v3/app/plugins/autoptcheckin/

# 2. 重载插件（有副作用，需用户授权）
curl -sS -X POST "http://127.0.0.1:17430/api/v1/plugin/reload/AutoPtCheckin" \
  -H "X-API-KEY: $(cat /d/tmp/.mp_local_key)"
```

改 `frontend.v2/<插件>/src` 或 `frontend.v3/<插件>/src` 后，在对应前端目录执行 `npm run build`，产物会直接写入 `plugins.vX/<插件>/dist/`；只改后端 `.py` 可直接部署 `__init__.py`。

**部署形态必须真目录，禁止 junction**：曾用 junction 指回本仓库，MP 恢复同步的 `.resolve()` 解引用后判「非法插件ID」，**junction 时代表例 `hhanclubrescueseed`/`autoptcheckin`/`ForumSignin` 全部装载失败**（日志：`sync.py - 创建插件安装快照失败：非法插件ID`）。统一真目录复制：

```bash
# hhanclubrescueseed 部署（本仓库 → 实例，运行产物仅 3 项）
J=/d/test/MoviePilot-v3/app/plugins/hhanclubrescueseed
S=/d/work/project/person/MoviePilot-Plugins/plugins.v3/hhanclubrescueseed
rm -rf $J && mkdir -p $J/dist
cp $S/__init__.py $S/AGENTS.md $J/
cp -r $S/dist/assets $J/dist/
```


## 排障备忘

- `/api/v1/plugin/file/<plugin_id>/<path>` 用登录后的**资源 Cookie** 鉴权（`resource_token_cookie`），不带 `X-API-KEY`；curl 带 API key 得 401 属正常，不代表文件缺失。文件服务从 `app/plugins/<lower(id)>/` 直读，验证存在性直接 `ls` 即可。
- 本地 repo 首装新插件出现过「插件加载失败，请查看插件日志」但插件日志为空：安装流程 reload 时启用位/身份行尚未对装载判据生效，直接重试一次安装即成功（日志出现「加载插件：X 版本：Y」）。装载成功判据看 `moviepilot.log` 的这行 INFO，不要只看 install 接口返回。
- 插件装载全程无 `config/logs/plugins/<id>.log` 不代表失败：该日志由插件业务代码写出，未启用的插件没有内容。
- 启动日志反复刷 `raw.githubusercontent.com ... ReadTimeout` 后插件迟迟不可用：无代理环境下 GitHub 索引请求每次 15 秒超时阻塞装载线程，属慢而非死；`app.env` 配 `GITHUB_TOKEN` 后缓解。判定装载完成以 remotes API 为准，不看启动日志时间戳。
- `AUDIENCES_UID/PASSKEY` 报「未设置」= env 没进进程（直启没 source），不是文件里没写。
- **前端是独立 Node 服务**（`public/service.js`，静态 `public/` + 反代 API，监听 NGINX_PORT 17431）。它启动时探测后端 `/health/ready`，后端未就绪达 `MOVIEPILOT_FRONTEND_MAX_FAILURES`（默认 4 次×15s）即退出并记 `Backend is unavailable, skip starting frontend service`——后端冷启动慢会连锁导致前端不启，表现「登录失败，请检查网络连接」。mp.ps1 已把该值调到 40（10 分钟容忍窗口）。前端日志 `config/logs/moviepilot.frontend.log`。
- 删 junction 必须用 `python -c "os.rmdir(...)"` 或资源管理器；**bash 里内嵌 PowerShell 转义会静默失败**（`\\'$p'` 类转义错后 2>/dev/null 吞错），导致「删了其实没删」，后续 cp 还会写穿 junction 污染源目录。删后务必用 resolve() 相对性校验（见「部署形态」）。
- qnap 生产实例的 `app.env` 可作本地合并基线（2025-10 已合并：GITHUB_TOKEN、PLUGIN_MARKET、LLM、DOH 等），但本地运行时键（PORT/NGINX_PORT/HOST/SUPERUSER/API_TOKEN）保留本地值；qnap 的 compose 级 env（AUTH_SITE/AUDIENCES_*、**PROXY_HOST**）不在其 app.env 里，需单独补——PROXY_HOST 漏配实证：GITHUB_TOKEN 在手仍全部「策略：直连 ConnectTimeout」，插件市场永远加载中，补 `PROXY_HOST='http://127.0.0.1:7890'` 后即愈。

## 红线

- API Key、CookieCloud 凭据等敏感值只从文件/环境读，不写入文档、日志、提交或子代理提示。
- reload、`run_once`、调度触发、配置写入均为副作用操作，需用户授权后执行；GET 配置/状态可直接做。
- 不要直接操作 `user.db`；配置走 API，日志看 `config/logs/`。
- 实例 `app.env` 归实例所有，调整端口/路径先问用户。
