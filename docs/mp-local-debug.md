# MP 本地调试环境调用规范

本地 MoviePilot V3 调试实例的调用方式。只记录环境事实与命令；通用调试流程见 `.pi/skills/moviepilot-debug/SKILL.md`。

## 实例概览

| 项 | 值 |
|---|---|
| 实例根 | `D:\test\MoviePilot-v3`（V3 源码 checkout + `moviepilot` bash CLI） |
| 后端 API | `http://127.0.0.1:17430`（`config/app.env` 的 `PORT`） |
| 前端 | `http://127.0.0.1:17431`（`config/app.env` 的 `NGINX_PORT`） |
| API Key | 文件 `D:/tmp/.mp_local_key`（与 `app.env` 的 `API_TOKEN` 同值；**调用时从文件读，不硬编码**） |
| 插件仓库联动 | `app.env` 的 `PLUGIN_LOCAL_REPO_PATHS=D:\work\project\person\MoviePilot-Plugins`（实例直接感知本仓库） |

## 启动 / 停止

```bash
cd /d/test/MoviePilot-v3 && moviepilot start     # 启动（前台）
moviepilot stop                                   # 停止
```

会话内验证用后台运行（pi `bg_task`，勿用前台阻塞）：

```bash
export MOVIEPILOT_DISABLE_CONSOLE_LOG=1 MOVIEPILOT_STDIO_LOG_BACKUP_COUNT=10 \
       "MOVIEPILOT_STDIO_LOG_FILE=D:\test\MoviePilot-v3\config\logs\moviepilot.stdout.log"
moviepilot start
```

stdio 日志落文件而非终端，避免后台任务日志膨胀；运行日志在 `config/logs/`。

## 探活与鉴权

```bash
# 探活（/docs 返回 404 属正常——文档路由未开，TCP 连通即实例在跑）
curl -s -o /dev/null -w '%{http_code}' --connect-timeout 3 http://127.0.0.1:17430/docs

# 带 key 调用（key 从文件读）
curl -sS "http://127.0.0.1:17430/api/v1/plugin/AutoPtCheckin/config" \
  -H "X-API-KEY: $(cat /d/tmp/.mp_local_key)"
```

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

改 `frontend/src` 后先 `npm run build`（产物在插件目录 `dist/`）再部署；只改后端 `.py` 可直接部署。

## 红线

- API Key、CookieCloud 凭据等敏感值只从文件/环境读，不写入文档、日志、提交或子代理提示。
- reload、`run_once`、调度触发、配置写入均为副作用操作，需用户授权后执行；GET 配置/状态可直接做。
- 不要直接操作 `user.db`；配置走 API，日志看 `config/logs/`。
- 实例 `app.env` 归实例所有，调整端口/路径先问用户。
