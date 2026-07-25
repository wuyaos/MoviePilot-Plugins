"""可组合的站点能力模块。

站点 Handler 按需多继承这些能力，新增能力只需新增一个类，不修改 ISiteHandler。
"""
from lxml import etree
from ..base.site_handler import ISiteHandler
from ..utils.request import parse_json_response


class NexusPHPChatMixin:
    """NexusPHP 喊话区能力。"""
    def send_messagebox(self, message: str, callback=None):
        if callback is None:
            callback = lambda response: " ".join(etree.HTML(response.text).xpath("//tr[1]/td//text()"))
        params = {"shbox_text": message, "shout": "我喊", "sent": "yes", "type": "shoutbox"}
        result = self._send_get_request(self.site_url + "/shoutbox.php", params=params, rt_method=callback)
        if result is None:
            return False, "发送消息失败"
        self._last_message_result = result
        return True, result

    def get_messagebox(self, rt_method=None):
        if rt_method is None:
            rt_method = lambda response: ["".join(x.xpath(".//text()")) for x in etree.HTML(response.text).xpath("//tr/td")]
        return self._send_get_request(self.site_url + "/shoutbox.php", rt_method=rt_method)


class NexusPHPAccountMixin:
    """签到、邮件和用户信息相关能力。"""
    def attendance(self):
        callback = lambda response: "".join(etree.HTML(response.text).xpath("//td/table//tr/td/p//text()"))
        return self._send_get_request(self.site_url + "/attendance.php", rt_method=callback) or "签到失败"

    def get_message_list(self, rt_method=None):
        if rt_method is None:
            rt_method = lambda response: [
                {"status": "".join(x.xpath("./td[1]/img/@title")),
                 "topic": "".join(x.xpath("./td[2]//text()")),
                 "from": "".join(x.xpath("./td[3]/text()")),
                 "time": "".join(x.xpath("./td[4]//text()")),
                 "id": "".join(x.xpath("./td[5]/input/@value"))}
                for x in etree.HTML(response.text).xpath("//form/table//tr")]
        return self._send_get_request(self.site_url + "/messages.php", rt_method=rt_method)

    def set_message_read(self, message_id: str):
        data = {"action": "moveordel", "messages[]": message_id, "markread": "设为已读", "box": "1"}
        return self._send_post_request(self.site_url + "/messages.php", data=data)


class NexusPHPTaskClaimMixin:
    """NexusPHP 任务申领能力。"""
    def claim_task(self, task_id: str, callback=None):
        def parse_claim(response):
            result = parse_json_response(response, "申领失败")
            return result.get("msg") or result.get("message") or "申领失败"

        result = self._send_post_request(
            self.site_url + "/ajax.php",
            data={"action": "claimTask", "params[exam_id]": task_id},
            rt_method=callback or parse_claim,
        )
        if result:
            return result
        error = getattr(self, "_last_request_error", "")
        return f"申领失败：{error}" if error else "申领失败"


class FeedbackMixin:
    """反馈能力默认实现。站点可重写 get_feedback。"""
    def get_feedback(self, message=None):
        if not self._last_message_result:
            return None
        return {"site": self.site_name, "message": message, "rewards": [{
            "type": "raw_feedback", "description": self._last_message_result,
            "amount": "", "unit": "", "is_negative": False,
        }]}


class CapabilityHandler(NexusPHPChatMixin, NexusPHPAccountMixin,
                        NexusPHPTaskClaimMixin, FeedbackMixin, ISiteHandler):
    """通用能力组合基类；站点 Handler 可继承它，也可只选部分 Mixin。"""
    pass
