# Agent Note: ForumSignin F1/F2 协议与骨架边界

Status: implemented

## Problem
旧论坛插件把提交响应、状态推算和通知混在一起；SSDForum 权威魔改副本还存在整数 HTTP 状态码拼接异常。新入口不能把未确认响应继续记成失败或成功。

## Decision
按本轮 F1/F2 指令建立独立 V3 后端，沿用 PT 签到中心模型与宿主 Vue/API 契约，不导入另一个插件。蜂巢使用任务明确批准的 API 证据例外；药丸与 SSDForum 使用本人当日页面行和按钮证据，未知 DOM 保持 unconfirmed。三站均无提交重试，页面站提交异常仍回读。
仅声明蜂巢只读同步服务；不迁签到调度、消息中心、CookieCloud、登录续期、PT 快照上传。前端/dist 属于下一轮，当前版本是不可直接安装验收 UI 的骨架。
SSDForum 协议来源为 `D:/tmp/ssdforumsigninmod/__init__.py`，SHA256 `d76361577a73e5d266d9d05e56fd032730c37b361c991680a07c4f42dfc2dc84`；保留该权威原件不改写，不下载在线原版替代。

## Alternatives considered
- 原样迁入 V2 重试与状态推算能提高表面成功率，但可能重复提交、把未知当失败，故只提取协议路径及表单。
- 仅凭药丸用户 API 或 SSDForum 通用成功文案确认更容易适配，但违反本轮页面本人记录约束，故保守拒绝未知结构。
- 蜂巢强制 DOM 回读符合旧合并方案，但本轮明确批准 API 响应为证据，采用新指令且保留 source=api，绝不制造页面字段。

## Consequences
离线合成夹具证明状态机、协议参数和异常回读，不证明真实站点 DOM；生产接管须另获授权。history 保持 history.records 键与分页语义，reward 保存完整模型以免丢失余额/累计记录，source 保留 API/页面区别。
当前目录没有既存 notes；按 ForumSignin/论坛检索无命中，无重叠笔记需要合并。测试禁止外部 socket，放行 loopback 仅供 Windows asyncio socketpair。
