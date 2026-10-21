"""验证器必须从新页面读取按钮与本人行，不以接口成功消息替代。"""
from typing import Protocol
from ..core.models import Evidence

class PageVerifier(Protocol):
    def parse(self, page: str, uid: str, business_date: str) -> Evidence | None: ...
