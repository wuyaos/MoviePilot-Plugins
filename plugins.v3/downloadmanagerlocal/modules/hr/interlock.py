"""授权解除与删除结果账。只操作 H&R 标签，实际删除由调用方负责。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.sdk.logging import logger

from ...utils.config import observe_only
from .constants import HR_LOG_PREFIX
from .guard import get_guard
from .scanner import downloader_services, remove_hr_tag, set_hr_tag

if TYPE_CHECKING:
    from .service import HrService

WRITE_SOURCES = frozenset(("transfer_source", "error_torrent_delete"))
SOURCE_MODULES = {"transfer_source": "transfer", "error_torrent_delete": "autoremove"}


class HrInterlock:
    """使用 HrService 的任务账及 guard；不创建服务，不扫描、不自动重试。"""

    def __init__(self, service: HrService):
        self.service = service

    @staticmethod
    def _identity(downloader_id: str, torrent_hash: str) -> None:
        if not str(downloader_id or "").strip() or not str(torrent_hash or "").strip():
            raise ValueError("downloader instance and hash are required")

    def query(self, downloader_id: str, torrent_hash: str) -> dict:
        self._identity(downloader_id, torrent_hash)
        task = self.service.get_task(downloader_id, torrent_hash)
        guard = get_guard()
        return {
            "protected": guard.is_protected(downloader_id, torrent_hash),
            "unconfirmed": guard.unconfirmed,
            "operation_id": task.interlock_id if task else "",
            "state": task.interlock_state if task else "",
            "error": task.interlock_error if task else "",
        }

    def _check_write(self, source: str, authorized: bool) -> None:
        if source not in WRITE_SOURCES or authorized is not True:
            raise PermissionError("H&R release source/authorization denied")
        config = self.service.config
        if not config.enabled or not config.protection_enabled or self.service.stopped:
            raise PermissionError("H&R disabled")
        if any(observe_only(self.service.plugin, module) for module in ("hr", SOURCE_MODULES[source])):
            raise PermissionError("observation forbids H&R writes")
        if get_guard().unconfirmed:
            raise PermissionError("H&R snapshot unconfirmed")

    def _tag_io(self, downloader_id: str, torrent_hash: str, *, restore: bool) -> None:
        services = downloader_services([downloader_id])
        service = services.get(downloader_id)
        if service is None:
            raise RuntimeError("downloader instance unavailable")
        tag = self.service.config.hit_and_run_tag
        if tag:
            (set_hr_tag if restore else remove_hr_tag)(service, torrent_hash, tag, strict=True)

    @staticmethod
    def _matches(task, source: str, operation_id: str) -> None:
        if not operation_id or task.interlock_id != operation_id or task.interlock_source != source:
            raise PermissionError("H&R operation identity mismatch")

    def release(self, downloader_id: str, torrent_hash: str, *, source: str,
                operation_id: str, authorized: bool, target_verified: bool = False,
                error_confirmed: bool = False) -> dict:
        """预约并解除标签；transfer 必须有真实校验证据，错误删除必须再次确认。"""
        self._identity(downloader_id, torrent_hash)
        self._check_write(source, authorized)
        if not operation_id:
            raise ValueError("operation_id required")
        if source == "transfer_source" and target_verified is not True:
            raise PermissionError("real target verification required")
        if source == "error_torrent_delete" and error_confirmed is not True:
            raise PermissionError("error deletion reconfirmation required")
        logger.info(f"{HR_LOG_PREFIX}请求 source={source} instance={downloader_id} hash={torrent_hash} op={operation_id}")
        with self.service.edit_interlock_task(downloader_id, torrent_hash) as task:
            if task.interlock_state:
                self._matches(task, source, operation_id)
                if task.interlock_state not in ("released", "deleting", "deleted"):
                    raise PermissionError("H&R operation requires inspection")
                return self.query(downloader_id, torrent_hash)
            if not get_guard().is_protected(downloader_id, torrent_hash):
                raise PermissionError("H&R task is not protected")
            task.interlock_id = operation_id
            task.interlock_source = source
            task.interlock_state = "pending"
            task.interlock_error = ""
        try:
            self._tag_io(downloader_id, torrent_hash, restore=False)
        except Exception as error:
            self._restore(downloader_id, torrent_hash, str(error))
            return self.query(downloader_id, torrent_hash)
        with self.service.edit_interlock_task(downloader_id, torrent_hash) as task:
            # stop/reload can occur during IO; never grant a stale deletion permit.
            try:
                self._check_write(source, authorized)
                if task.interlock_state != "pending":
                    raise PermissionError("H&R reservation interrupted")
            except PermissionError as error:
                task.interlock_state = "interrupted"
                task.interlock_error = str(error)
            else:
                task.interlock_state = "released"
        logger.info(f"{HR_LOG_PREFIX}解除 instance={downloader_id} hash={torrent_hash} op={operation_id} state={task.interlock_state}")
        return self.query(downloader_id, torrent_hash)

    def begin_delete(self, downloader_id: str, torrent_hash: str, *, source: str,
                     operation_id: str, authorized: bool) -> dict:
        """调用方真实删除之前预约；返回 deleting 才允许执行删除。"""
        self._identity(downloader_id, torrent_hash)
        self._check_write(source, authorized)
        with self.service.edit_interlock_task(downloader_id, torrent_hash) as task:
            self._matches(task, source, operation_id)
            if task.interlock_state != "released":
                raise PermissionError("H&R deletion not released")
            task.interlock_state = "deleting"
        logger.info(f"{HR_LOG_PREFIX}删除 请求 instance={downloader_id} hash={torrent_hash} op={operation_id}")
        return self.query(downloader_id, torrent_hash)

    def finish_delete(self, downloader_id: str, torrent_hash: str, *, source: str,
                      operation_id: str, authorized: bool, success: bool) -> dict:
        """调用方报告真实删除结果；失败先恢复本地保护，再尝试标签恢复。"""
        self._identity(downloader_id, torrent_hash)
        # Failure accounting must remain available after stop/observe/snapshot failure.
        if source not in WRITE_SOURCES or authorized is not True:
            raise PermissionError("H&R result source/authorization denied")
        with self.service.edit_interlock_task(downloader_id, torrent_hash) as task:
            self._matches(task, source, operation_id)
            if task.interlock_state in ("deleted", "restored"):
                return self.query(downloader_id, torrent_hash)
            if task.interlock_state != "deleting":
                raise PermissionError("H&R deletion not started")
            task.interlock_state = "deleted" if success is True else "restoring"
        logger.info(f"{HR_LOG_PREFIX}删除 结果 instance={downloader_id} hash={torrent_hash} success={success}")
        if success is not True:
            self._restore(downloader_id, torrent_hash, "delete failed")
        return self.query(downloader_id, torrent_hash)

    def _restore(self, downloader_id: str, torrent_hash: str, reason: str) -> None:
        with self.service.edit_interlock_task(downloader_id, torrent_hash) as task:
            task.interlock_state = "restoring"
            task.interlock_error = reason
        try:
            self._check_write(self.service.get_task(downloader_id, torrent_hash).interlock_source, True)
            self._tag_io(downloader_id, torrent_hash, restore=True)
        except Exception as error:
            reason += f"; tag restore failed: {error}"
        with self.service.edit_interlock_task(downloader_id, torrent_hash) as task:
            task.interlock_state = "restored"
            task.interlock_error = reason
        logger.warning(f"{HR_LOG_PREFIX}恢复 instance={downloader_id} hash={torrent_hash}: {reason}")
