---
name: JyingCheckin 落盘静默失败与 onlyonce 语义
timestamp: 2026-11-08
tags: [moviepilot, v3-plugin, super-init, persistence]
status: open
---

## 事件

JyingCheckin 手动 checkin 返回成功（already），但 plugindata 无 session/history 行、
plugininstance onlyonce 未回写、KPI 永远「未登录」。两通道同时静默失败。

## 根因链

1. 插件 `__init__` 未调 `super().__init__()` → 基类端口（`self.plugindata` /
   `self._plugininstance` / `self.systemmessage` 等，base.py:50-66）全部缺失。
2. `save_data` → `self.plugindata.save(...)` 抛 AttributeError。
3. 插件的 `_data_set`/`_data_get` 用裸 `except Exception: pass/return None` 吞掉异常 →
   签到流程继续「成功」，落盘从未发生。
4. `update_config`（走 `self._plugininstance`）同样炸，被 `_consume_onlyonce` 的 except 吞掉。

## 修复

- `__init__` 首行 `super().__init__()`（plugins.v3/jyingcheckin/__init__.py）。
- `_data_set` 异常分支加 `logger.debug` 留痕（类名），不再纯 `pass`。

## 教训

- MP V3 插件类必须 `super().__init__()`：宿主端口在基类构造器绑定，缺了就是全线静默失败。
- 离线测试 mock 了 `_store`/`_notify`，暴露不了端口缺失；运行时验收必须查库（plugindata 行）
  而不是只看 API 返回 success。
- V3 DB 写（`_stage_create/_stage_update`）有 flush 延迟，验证落盘别在写后立即查库。

## 关联事实

- onlyonce 语义：宿主保存配置不会自动复位 `onlyonce`。插件在 `run_once` 开跑即
  `_consume_onlyonce()` 回写 false（self.update_config）。
- 单次任务注册用 `DateTrigger(run_date=now+5s)`：date=now 会被
  `misfire_grace_time`/重载竞争吃掉（18:09 那次到点未跑，原因未完全查清，
  cron 链路已用手动 runscheduler 验证可用）。
- 手动触发验证：`GET /api/v1/system/runscheduler?jobid=<PluginId>_<ServiceId>`。
- 插件 REST API 鉴权用 `X-API-KEY` 头（`Authorization: Bearer` 对 superuser 接口 401）。
