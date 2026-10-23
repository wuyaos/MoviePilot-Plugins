> 历史记录：以下内容记载旧桥清理前的状态，不代表当前代码。旧桥、PILOTS 门控与 sites 顶层副本已移除；现状以插件主 AGENTS.md 和当前测试为准。

# D8 三态夹具盘点（3.15.0）

口径：按当前 registry 的站点 ID 统计离线合成输入覆盖，不等于生产页面校准。三态指正向、明确未签/可提交、未知输入；没有可靠 unsigned 判据的站点，未签输入允许仍为 unconfirmed，不为了凑三种输出伪造失败。success/already/unconfirmed 流程夹具也单独注明。通用基类测试不计为每个声明站的逐站夹具。

## 已覆盖

- D1 下沉20站：`test_generic_behavior_d1.py` 参数化覆盖12个 CAPTCHA 站（success/already/unconfirmed）、6个 GET 站与2个静态 POST 站（三种回读输入）；原 C1/C2/C34 保留异常、取消和单次动作验证。
- 专属站：`test_native_batch1*.py`、`test_native_sites.py`、`test_get_signin_c2.py`、`test_post_api_signin_c34.py`、`test_tjupt_login_only_c56.py`、`test_bakatest_yzyy_c7.py` 覆盖 agsvpt/chdbits/dstudio/haitang/hdbao/hdchina/hdsky/lajidui/luckpt/muxuege/opencd/pterclub/ptzone/retrotoon/siqi/tjupt/ttg/u2/yema/yzyy/zhuque 的状态输入或 success/already/unconfirmed 流程。
- BTSchool 三种输入均不能证明签到；海胆/HDUpt/TJUPT/U2 等缺少可靠未签判据时保持 unconfirmed，不能将其当作缺少 failed 断言的测试错误。

## 缺少逐站三态夹具

- 专属站：`gtk`、`lpbits`。
- 通用站（61个）：`13city`、`1ptba`、`52movie`、`audiences`、`bilibili`、`cangbao`、`carpt`、`cc_mypt`、`crabpt`、`cspt`、`cyanbug`、`discfan`、`dragonhd`、`dubhe`、`duckboobee`、`et8`、`gamegamept`、`hddolby`、`hdfans`、`hdhome`、`hdkyl`、`hdtime`、`hdvideo`、`hitpt`、`hxpt`、`kufei`、`lemonhd`、`longpt`、`momentpt`、`mua_xloli`、`musopia`、`nanyangpt`、`nicept`、`njtupt`、`okpt`、`pandapt`、`pt_0ff`、`pt_aling`、`pt_daxiangjiao`、`pt_eastgame`、`pt_hdclone`、`pt_itzmx`、`pt_keepfrds`、`pt_sjtu_edu`、`pt_tey`、`pt_xingyungept`、`pt_ying_us`、`ptcafe`、`ptfans`、`pthome`、`ptlgs`、`ptskit`、`sbpt`、`sewerpt`、`tangpt`、`ubits`、`xdypt`、`xingtan`、`xingwan`、`zmpt`、`hdwing`。
- generic 中另有与专属模块同 ID 的 `ptzone` 声明；registry 最终使用专属模块，B1-7 已按该站 ID 覆盖。其被覆盖的 generic 类本身没有独立三态测试，不将同一站点重复统计。

## 不适用及迁移残留

- `52pt` 已是未实现滑块流程且 signin_capable=False；无有效签到三态夹具，不再沿用 bakatest 测试。删除 B1 测试里未使用的 Pt52/import_module 导入；CHDBits 的 bakatest 三态保留。
- `darkland`、`digitalcore`、`mteam` 不适用签到三态，已有 skipped/无签到请求验证；不算遗漏站。
- `hares` 已移除 native 声明，无 native 测试 import 残留；旧副本和元数据仍保留，不能把已关闭站点补成有效签到夹具。
- 全量测试收集检查没有已删除专属模块的失效 import。新增 D7 回归检查原生 ID 的 sign/verify/login 分流不构造旧桥，并检查旧副本状态；该分流 mock 不是三态行为覆盖。

## 执行边界风险

旧 `PilotBridge` 仅实现 hdsky/haitang；该实现与旧适配器元数据现已删除。历史问题描述已失效，仅作为当时审计记录保留。27域排除清单没有 native 声明，不代表这些域名具有签到实现。
