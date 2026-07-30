"""统一任务日志。

格式固定为：``[PtTaskFlow] [场景] [站点] [单元] 阶段/结果``。
站点与 Action 不得自行拼接任务生命周期日志，只记录底层 HTTP/解析异常；
禁止记录 Cookie、Token、请求头和完整响应体。
"""
from app.log import logger


class TaskLogger:
    PREFIX = "[PtTaskFlow]"

    @classmethod
    def _line(cls, scene: str, site: str = "", unit: str = "", text: str = ""):
        parts = [cls.PREFIX, f"[{scene}]" if scene else ""]
        if site:
            parts.append(f"[{site}]")
        if unit:
            parts.append(f"[{unit}]")
        if text:
            parts.append(text)
        return " ".join(part for part in parts if part)

    @classmethod
    def run_start(cls, scene: str, units: int):
        logger.info(cls._line(scene, text=f"开始 -> 待执行 {units} 个单元"))

    @classmethod
    def unit_start(cls, scene: str, unit):
        logger.info(cls._line(scene, unit.site.site_name, unit.label, "开始"))

    @classmethod
    def unit_result(cls, scene: str, unit, result):
        outcome = "成功" if result.success else "失败"
        log = logger.info if result.success else logger.warning
        log(cls._line(scene, unit.site.site_name, unit.label,
                      f"{outcome} -> {result.message or '无详情'}"))
        for reward in result.rewards or []:
            sign = "损失" if reward.get("is_negative") else "奖励"
            log(cls._line(scene, unit.site.site_name, unit.label,
                          f"{sign} -> {reward.get('type', '未分类')}：{reward.get('description', '')}"))

    @classmethod
    def unit_error(cls, scene: str, unit, error: Exception):
        logger.error(cls._line(scene, unit.site.site_name, unit.label,
                               f"异常 -> {type(error).__name__}: {error}"), exc_info=True)

    @classmethod
    def unit_skip(cls, scene: str, unit, reason: str):
        logger.info(cls._line(scene, unit.site.site_name, unit.label, f"跳过 -> {reason}"))

    @classmethod
    def run_end(cls, scene: str, executed: int, success: int, failed: int, skipped: int):
        logger.info(cls._line(scene, text=(
            f"完成 -> 执行 {executed} / 成功 {success} / 失败 {failed} / 跳过 {skipped}"
        )))
