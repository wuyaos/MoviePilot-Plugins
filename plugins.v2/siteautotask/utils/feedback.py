"""反馈奖励解析工具（迁移自 groupchatzone 的 NotificationIcons + 奖励类型识别）。"""

from typing import Dict, List


class NotificationIcons:
    """通知图标常量。"""

    UPLOAD = "⬆️"
    DOWNLOAD = "⬇️"
    BONUS = "✨"
    WORK = "🔧"
    POWER = "⚡"
    VICOMO = "🐘"
    FROG = "🐸"
    VIP = "👑"
    RAINBOW = "🌈"
    SPARK = "🔥"
    BEER = "🍺"
    FEEDBACK = "📝"
    DEFAULT = "📌"

    _icon_map = {
        "上传量": UPLOAD,
        "下载量": DOWNLOAD,
        "魔力值": BONUS,
        "工分": WORK,
        "电力": POWER,
        "象草": VICOMO,
        "青蛙": FROG,
        "VIP": VIP,
        "彩虹ID": RAINBOW,
        "火花": SPARK,
        "啤酒瓶": BEER,
        "raw_feedback": FEEDBACK,
    }

    @classmethod
    def get(cls, reward_type: str) -> str:
        return cls._icon_map.get(reward_type, cls.DEFAULT)


# 奖励类型识别关键词（按优先级，来自 groupchatzone NexusPHPHandler.get_feedback）
_REWARD_KEYWORDS = [
    ("上传量", ["上传"]),
    ("下载量", ["下载"]),
    ("魔力值", ["魔力"]),
    ("工分", ["工分"]),
    ("VIP", ["vip"]),
    ("彩虹ID", ["彩虹id"]),
]


def detect_reward_type(feedback_text: str) -> str:
    """根据反馈文本关键词识别奖励类型。"""
    if not feedback_text:
        return "raw_feedback"
    lower = feedback_text.lower()
    for reward_type, keywords in _REWARD_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return reward_type
    return "raw_feedback"


def build_feedback(site: str, message: str, description: str,
                   reward_type: str = None, amount: str = "",
                   unit: str = "", is_negative: bool = False) -> Dict:
    """构造标准反馈字典。"""
    if reward_type is None:
        reward_type = detect_reward_type(description)
    return {
        "site": site,
        "message": message,
        "rewards": [{
            "type": reward_type,
            "description": description,
            "amount": amount,
            "unit": unit,
            "is_negative": is_negative,
        }],
    }


def merge_feedbacks(feedbacks: List[Dict]) -> Dict:
    """合并多个反馈字典（同站点）。"""
    if not feedbacks:
        return {}
    merged = {"site": feedbacks[0].get("site", ""), "message": "", "rewards": []}
    for fb in feedbacks:
        if fb.get("message") and not merged["message"]:
            merged["message"] = fb["message"]
        merged["rewards"].extend(fb.get("rewards", []))
    return merged
