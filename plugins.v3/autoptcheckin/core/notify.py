from .models import SignResult

def format_notification(site: str, result: SignResult) -> str:
    reward = result.reward.reported if result.reward else "未知"
    return f"{site}：{result.status.value}，{result.message}，奖励：{reward}"
