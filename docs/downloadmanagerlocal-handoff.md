# DML 换模型交接

## 从哪里继续

唯一实施规格：[最终实施规格](downloadmanagerlocal-final-implementation-spec.md)。旧方案只作历史，不合并其旧指令。当前只完成方案定稿与代码检查点，新方案 P0-P8 尚未实施；先做 P0 的契约、兼容矩阵和宿主验证，不把已有测试通过视为新方案完成。

## 已提交的代码基线

- commit：`51b759e3dea1c1d12e3523006c44cf29d7270eb3`
- 前置 commit：`09f882b5b4e34b6aea8f633410e24ea72907dbc3`（已用 `git rev-parse 51b759e3^` 核验）。
- 范围：DML v3.9.14 既有前后端、构建资源、回归测试；不是最终重构实现。
- 验证：后端295通过（6.10s），前端39通过，Vite构建通过（1.35s）；34个变更/新增Python文件AST通过；JSON、版本与顶部history一致。
- CRLF-aware差异校验通过：`git -c core.whitespace=cr-at-eol diff --check`。默认检查会将现有CRLF报作尾随空白；本轮未为此批量改行尾。
- 未验：本轮未重跑本地MP浏览器及测试下载器场景，更未在QNAP验收。

## 约束与下一步

1. 用户先换模型，当前停在提交后；没有继续开发、推送或部署。
2. 开发前基线已落地；后续每工作包验证后本地提交，P2逐模块提交。同一文件一个写入者，不全量暂存，不推送。
3. 模型分工按规格第12节：复杂前端Sol骨架，Luna细节，DeepSeek/GLM机械项；后端DeepSeek/GLM，同一阻塞两次定向失败升级Sol后交回。精确模型ID按运行时确认。
4. HTML存档任务暂停，原导出失败布局不能当合格样式对照；保留原视觉风格与Tab，按已批准token统一级内文字/尺寸/风险语义。
5. 本地MP真实验收通过后才申请QNAP完整包部署，保持现有QNAP不变。
6. 旧文档全文在 `docs/history/downloadmanagerlocal/pre-final-v2/`，入口改为转向。不要用历史执行脚本替代新规格。
7. 已验证的门禁命令见最终规格第13.1节；本机必须用已验证的micromamba base绝对解释器，不能用误指向hermes环境的命令。

任务进度以最终规格与本地todo为准，历史Ralph完成勾选不代表新方案实施完成。
