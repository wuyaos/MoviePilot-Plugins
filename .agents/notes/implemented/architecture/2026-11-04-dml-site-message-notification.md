# Agent Note: DML统一站点消息通知

Status: implemented

## Problem

DML各模块原来选择不同消息类型，统一出口还强制`parse_mode="plain"`。用户要求所有DML通知对齐Cloudflare优选插件：使用站点消息且不指定解析模式。Cloudflare源码未说明“查看详情”的生成机制，不能仅据消息分类承诺链接效果。

## Decision

`utils/notify.py::notify_module_result`统一使用宿主`MessageType.SiteMessage`，忽略历史调用点传入的消息分类参数，并不再传`parse_mode`。保留兼容参数以避免各模块调用签名变化；DML所有通知从同一出口获得一致的站点消息分类。

## Alternatives considered

只修改上传限速通知会保留转移、H&R、自动删种和失败清理之间的不一致；保留`Plugin`并在正文拼Markdown链接不能获得宿主`SiteMessage`行为，且纯文本解析模式不会解析链接。

## Consequences

所有DML通知改走站点消息类型，渠道订阅分类可能随之变化；开关、标题、正文与通知异常隔离不变。测试锁定所有模块及旧分类参数最终均发送`SiteMessage`且不传解析模式。是否呈现可点击“查看详情”仍取决于宿主和渠道，尚未实发验证。

失败清理调用方已按用户决定退出，见[退出整理相关文件清理](../../implemented/simplification/2026-11-05-dml-retire-failclean.md)；其他有效模块继续遵守此通知出口约定。
