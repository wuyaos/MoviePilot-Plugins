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

本机 `moviepilot` CLI 依赖工程 `.venv`（未建，报「未找到项目虚拟环境」），实际用 mp3 editable 环境直连：

```bash
cd /d/test/MoviePilot-v3
export CONFIG_DIR='D:\test\MoviePilot-v3\config'
alias mp3cli="micromamba run -n mp3 python -m app.cli"

mp3cli start     # 后台启动（daemon 化：CLI 拉起前后端子进程后即返回）
mp3cli status    # 状态（running + PID）
mp3cli stop      # 停止
mp3cli restart   # 重启
```

**注意：`start` 是后台守护化启动，CLI wrapper 退出 ≠ 实例停止**——pi `bg_task` 里跑它，「任务 finished」是正常现象，服务存活以 `status` 或探活为准。stdio 日志由 `MOVIEPILOT_STDIO_LOG_*` 系列环境变量控制落文件（见下），运行日志在 `config/logs/`：

```bash
export MOVIEPILOT_DISABLE_CONSOLE_LOG=1 MOVIEPILOT_STDIO_LOG_BACKUP_COUNT=10 \
       "MOVIEPILOT_STDIO_LOG_FILE=D:\test\MoviePilot-v3\config\logs\moviepilot.stdout.log"
```

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


## 排障备忘

- `/api/v1/plugin/file/<plugin_id>/<path>` 用登录后的**资源 Cookie** 鉴权（`resource_token_cookie`），不带 `X-API-KEY`；curl 带 API key 得 401 属正常，不代表文件缺失。文件服务从 `app/plugins/<lower(id)>/` 直读，验证存在性直接 `ls` 即可。
- 本地 repo 首装新插件出现过「插件加载失败，请查看插件日志」但插件日志为空：安装流程 reload 时启用位/身份行尚未对装载判据生效，直接重试一次安装即成功（日志出现「加载插件：X 版本：Y」）。装载成功判据看 `moviepilot.log` 的这行 INFO，不要只看 install 接口返回。
- 插件装载全程无 `config/logs/plugins/<id>.log` 不代表失败：该日志由插件业务代码写出，未启用的插件没有内容。
## 红线

- API Key、CookieCloud 凭据等敏感值只从文件/环境读，不写入文档、日志、提交或子代理提示。
- reload、`run_once`、调度触发、配置写入均为副作用操作，需用户授权后执行；GET 配置/状态可直接做。
- 不要直接操作 `user.db`；配置走 API，日志看 `config/logs/`。
- 实例 `app.env` 归实例所有，调整端口/路径先问用户。
