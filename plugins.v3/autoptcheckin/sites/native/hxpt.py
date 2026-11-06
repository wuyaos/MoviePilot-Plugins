"""好学（hxpt）FluxTorrent API：JSON 回读 + checkin 提交 + 提交后再回读。

generic 的 api 协议只支持 GET 动作与 HTML/单字段回读；本站动作是 POST
`/api/v1/attendance/checkin`、回读是 `{code, data:{checked_today}}` 信封，
故收敛为独立模块（同 52pt/yema/hdwing 先例）。
结论一律来自回读证据：pre-read checked_today=True 为 ALREADY；
提交后回读 checked_today=True 才转 SUCCESS；提交回执只作消息补充，不单独定成功。
"""
import json

from ...core.models import SignStatus
from ...core.sitemodel import RecordSpec, SiteModule

_STATUS_PATH = "api/v1/attendance"
_CHECKIN_PATH = "api/v1/attendance/checkin"


def _payload(page):
    """Envelope dict or None (non-200/empty/malformed is never guessed)."""
    if page is None or page.status_code != 200 or not (page.text or "").strip():
        return None
    try:
        payload = json.loads(page.text)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _data(payload):
    return payload.get("data") if isinstance(payload.get("data"), dict) else {}


class Hxpt(SiteModule):
    id = "hxpt"
    name = "好学"
    url = "https://www.hxpt.org/"
    record_spec = RecordSpec("", {})  # 结论在 signin 内产出；此字段仅满足声明契约。

    def _read_status(self, ctx):
        """(payload, data)；异常/不可读时返回 (None, None)，401 另见 page。"""
        try:
            page = ctx.http.get(self.url + _STATUS_PATH)
        except Exception:
            return None, None
        payload = _payload(page)
        if payload is None:
            return None, None
        return payload, _data(payload)

    def signin(self, ctx):
        if ctx.cancel.is_set():
            return ctx.result(status=SignStatus.CANCELLED)
        try:
            pre_page = ctx.http.get(self.url + _STATUS_PATH)
        except Exception as exc:
            return ctx.result(status=SignStatus.NETWORK_ERROR,
                              message=f"签到状态不可达：{type(exc).__name__}")
        if pre_page is not None and pre_page.status_code == 401:
            return ctx.result(status=SignStatus.AUTH_FAILED, message="回读未登录（HTTP 401）")
        pre = _payload(pre_page)
        if pre is None:
            status = pre_page.status_code if pre_page is not None else 0
            return ctx.result(status=SignStatus.NETWORK_ERROR,
                              message=f"签到状态不可读：HTTP {status} 或非 JSON 响应")
        pre_data = _data(pre)
        if pre_data.get("checked_today") is True:
            return ctx.result(status=SignStatus.ALREADY, message="今日已签到")
        if pre.get("code") != 0:
            return ctx.result(status=SignStatus.UNCONFIRMED,
                              message=(f"签到状态未确认：code={pre.get('code')}"
                                       f" {pre.get('message') or ''}").strip())

        if ctx.cancel.is_set():
            return ctx.result(status=SignStatus.CANCELLED)
        receipt = None
        try:
            receipt = _payload(ctx.http.post(self.url + _CHECKIN_PATH, json={}))
        except Exception:
            receipt = None
        finally:
            after_payload, after_data = self._read_status(ctx)
        if after_payload is None:
            return ctx.result(status=SignStatus.UNCONFIRMED,
                              message="已提交签到，但回读未确认（状态接口不可读）")
        if after_data.get("checked_today") is True:
            parts = []
            receipt_data = _data(receipt) if isinstance(receipt, dict) else {}
            if receipt_data.get("reward") is not None:
                parts.append(f"+{receipt_data['reward']} 魔力")
            if receipt_data.get("streak") is not None:
                parts.append(f"连续 {receipt_data['streak']} 天")
            return ctx.result(status=SignStatus.SUCCESS,
                              message="签到成功" + ("（" + "，".join(parts) + "）" if parts else ""))
        return ctx.result(status=SignStatus.UNCONFIRMED,
                          message="已提交签到，但回读仍为未签到")
