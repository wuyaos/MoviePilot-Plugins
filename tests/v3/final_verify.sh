#!/bin/bash
# PT 签到中心 前端最终验证（在仓库根 D:/work/project/person/MoviePilot-Plugins 执行）
set -e
cd /d/work/project/person/MoviePilot-Plugins
echo "== 1. 离线测试 =="
C:/app/scoop/apps/micromamba/2.9.0-0/base/python.exe -m pytest tests/v3/autoptcheckin -q
echo "== 2. package.v3.json 合法性 =="
micromamba run -n base python -m json.tool package.v3.json >/dev/null && echo "json-ok"
echo "== 3. dist 产物存在 =="
ls plugins.v3/autoptcheckin/dist/assets/remoteEntry.js >/dev/null && echo "dist-ok"
echo "== 4. 宿主装载（需本地实例运行） =="
TOKEN="${MP_LOCAL_API_KEY:-}"
if [ -z "$TOKEN" ]; then echo "SKIP: MP_LOCAL_API_KEY 未设置，跳过宿主安装验证"; exit 0; fi
LOG=/d/test/MoviePilot-v3/config/logs/moviepilot.log
LOG_START=$(wc -l < "$LOG")
for i in 1 2 3; do curl -sS -m 60 "http://127.0.0.1:17430/api/v1/plugin/install/AutoPtCheckin?repo_url=local%3A%2F%2FAutoPtCheckin&force=true" -H "X-API-KEY: $TOKEN" && break || sleep 3; done
sleep 4
grep -a 'AutoPtCheckin 版本' /d/test/MoviePilot-v3/config/logs/moviepilot.log | tail -1
# 只检查本次安装后追加的日志，历史错误不能证明本次装载失败。
if tail -n +$((LOG_START + 1)) "$LOG" | grep -a 'Error adding plugin route'; then
    echo "route-error"
    exit 1
fi
echo "route-ok"
