"""本地 S5 安装验证：凭据只从本机配置读取，不输出。"""
from pathlib import Path
import json
import urllib.request

values = {}
for line in Path('D:/test/MoviePilot-v3/config/app.env').read_text(encoding='utf8').splitlines():
    key, sep, value = line.partition('=')
    if sep:
        values[key.strip()] = value.strip().strip('\"\'')
token = values.get('API_TOKEN') or values.get('API_KEY')
if not token:
    raise RuntimeError('No local API token configured')
request = urllib.request.Request('http://127.0.0.1:17430/api/v1/plugin/install/AutoPtCheckin?repo_url=local%3A%2F%2FAutoPtCheckin&force=true', headers={'X-API-KEY':token})
with urllib.request.urlopen(request, timeout=180) as response:
    result = json.load(response)
    print(json.dumps({'success':result.get('success'), 'message':result.get('message')},ensure_ascii=False))
