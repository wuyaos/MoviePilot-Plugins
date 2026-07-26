# AI识别增强

复用 MoviePilot 当前 LLM 配置，在原生识别失败后做本地结构化识别兜底，并把结果交回原生链路继续二次识别。

## Input / Output / Pos
- Input: `ChainEventType.NameRecognize` 事件、标题/路径元信息和 MoviePilot 系统 LLM 配置。
- Input: 插件自定义 OpenAI 兼容 Base URL、API Key、模型名、超时和重试配置。
- Input: 失败样本保存、置信度阈值、TMDB 校验和自定义识别词建议开关。
- Output: 结构化识别猜测、事件链注入结果、失败样本 JSONL 和 LLM 错误记录。
- Output: CustomIdentifiers 建议、详情页列表、清理 API 和诊断信息。
- Pos: MoviePilot 原生识别链路的兜底增强层。
- Pos: 只在原生识别未完成且满足守门条件时介入，避免覆盖原生或其他插件结果。

## Files
- `__init__.py`: 插件入口、事件注册、LLM chain 构建、识别缓存、失败样本记录、API 和详情页。

## Key Constraints
- `plugin_version` 必须与 `package.v2.json` 中 `LLMRecognizer.version` 同步。
- 默认复用系统 LLM；只有 Base URL、API Key、模型名三项齐全时才创建独立 ChatOpenAI 实例。
- 仅填模型名时只能尝试 bind，不保证所有 provider 生效，需保留 warning/hint。
- 识别结果只缓存 `success=True` 的结果，失败不入缓存以允许后续重试。
- 同一 `(title, path)` 正在处理时用 in-flight 集合去重，避免并发重复打 LLM。
- 事件已有 `source_plugin` 或原生结果已填充时跳过，避免覆盖其他插件或原生链路结果。
- JSONL 读写、识别 chain、识别词 chain 和缓存均需使用对应锁保护线程安全。
- 默认不调用 TMDB 校验，避免宿主接口 500 噪音；相关开关必须显式启用。
- Pydantic 输出 schema 字段名要保持稳定，防止 LLM 结构化解析失败。
- API 端点应包裹异常并返回可读错误，不让详情页静默崩溃。
