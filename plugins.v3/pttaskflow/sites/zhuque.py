"""朱雀：技能释放与一键升级。"""
from datetime import datetime
import re

from ..core.models import Control, ControlKind, TaskResult
from ..core.site import Site
from ..core.task import ActionTask, TaskType
from ..actions.site_actions import ZhuqueSkillAction, ZhuqueLevelUpAction


class ZhuqueLevelUpTask(ActionTask):
    """带目标等级选择的一键升级任务。"""

    def __init__(self):
        super().__init__("level_up", ZhuqueLevelUpAction(), "一键升级", TaskType.GENERIC)

    def controls(self, site):
        controls = super().controls(site)
        controls.append(Control(
            ControlKind.SELECT_ONE,
            self.key(site) + "_target",
            "朱雀目标等级",
            hint="升级会消耗灵石，请确认余额和目标等级",
            options=[{"id": str(level), "label": f"等级 {level}"} for level in range(1, 80)],
            placeholder="默认等级 79",
        ))
        return controls

    def expand(self, site, config):
        target = str(config.get(self.key(site) + "_target") or "79")
        return [self._unit(site, target)]

    def _unit(self, site, target):
        from ..core.models import Unit
        return Unit(self, site, self.execution_key(site, target), self.label(site), target)

    def run(self, site, unit):
        return self.action.execute(site, int(unit.argument or 79))


class Zhuque(Site):
    site_name = "朱雀"
    domain = "zhuque.in"
    shoutbox = None
    tasks = [
        ActionTask("skill_release", ZhuqueSkillAction(), "技能释放"),
        ZhuqueLevelUpTask(),
    ]

    def _csrf_headers(self):
        response = self.get("/index")
        if not response:
            return None
        matches = re.findall(r'<meta\s+name=["\']x-csrf-token["\']\s+content=["\']([^"\']+)', response.text or "", re.I)
        if len(matches) != 1 or not matches[0]:
            self.request_error = "朱雀首页未获取到 x-csrf-token"
            return None
        return {"x-csrf-token": matches[0]}

    def _json_request(self, method, path, headers=None, **kwargs):
        response = self.request(method, path, headers=headers, **kwargs)
        if not response:
            return None
        try:
            payload = response.json()
        except (TypeError, ValueError):
            self.request_error = f"朱雀接口返回非 JSON（HTTP {response.status_code}）"
            return None
        if response.status_code in (401, 403):
            self.request_error = "朱雀 Cookie 已失效"
            return None
        if response.status_code != 200:
            self.request_error = f"朱雀接口请求失败（HTTP {response.status_code}）"
            return None
        return payload

    def skill_is_due(self, payload):
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        characters = data.get("characters", []) if isinstance(data, dict) else []
        now = datetime.now().timestamp()
        future = []
        for item in characters:
            info = item.get("info", {}) if isinstance(item, dict) else {}
            try:
                value = float(info.get("next_time"))
            except (TypeError, ValueError):
                continue
            if value > now:
                future.append(value)
        return not future

    def get_user_info(self, headers):
        return self._json_request("GET", "/api/gaming/listGenshinCharacter", headers=headers)

    def get_skill_next_time(self):
        headers = self._csrf_headers()
        if not headers:
            return None
        payload = self.get_user_info(headers)
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        characters = data.get("characters", []) if isinstance(data, dict) else []
        now = datetime.now().timestamp()
        values = [float(item.get("info", {}).get("next_time")) for item in characters
                  if isinstance(item, dict) and str(item.get("info", {}).get("next_time", "")).replace(".", "", 1).isdigit()
                  and float(item.get("info", {}).get("next_time")) > now]
        return min(values) if values else None
