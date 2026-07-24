# siteautotask

合并 `ptautotask` 与 `groupchatzone` 的站点自动任务插件。

## 模块职责

- `__init__.py`：MoviePilot V2 生命周期入口，仅做模块委托
- `base/`：任务元数据、统一结果、最小站点处理器抽象
- `core/`：配置、执行引擎、历史、调度、通知
- `sites/`：每个站点一个模块；按需组合 `capabilities.py` 中的能力
- `ui/`：配置表单与运行数据页
- `utils/`：请求、反馈解析、HTML 工具
- `tests/`：无真实网络副作用的 mock 测试

## 新增站点

1. 在 `sites/` 新增一个小模块。
2. 定义 `Handler`，继承 `CapabilityHandler` 或按需组合能力，实施 `match()`。
3. 定义 `Tasks(BaseTask)`，每个任务使用 `@task_info(..., task_type=...)`。
4. 任务返回 `TaskResult`；旧站点返回字符串/元组也可由引擎兼容。
5. 补充 mock 测试后再接入真实站点。

## 校验

```bash
python3 -m unittest discover -s plugins.v2/siteautotask/tests -v
find plugins.v2/siteautotask -name '*.py' -print0 | xargs -0 -n1 python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())'
```

真实购买、喊话、抽奖测试必须明确确认，默认只使用 mock 或只读请求。
