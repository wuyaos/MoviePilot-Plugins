"""抓取器共享的同源请求与结果构造。"""
from __future__ import annotations

from urllib.parse import urljoin

import requests

from ..models import SourceFetchResult, SourceSpec
from ..url_utils import same_origin

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def get_same_origin(
    url: str, *, origin_url: str, headers: dict,
    proxies: dict | None, timeout: int, context: str,
):
    current = url
    for _ in range(4):
        response = requests.get(
            current, headers=headers, proxies=proxies,
            timeout=(5, timeout), allow_redirects=False,
        )
        if response.status_code not in _REDIRECT_STATUSES:
            return response
        target = urljoin(current, response.headers.get("Location", ""))
        if not target or not same_origin(origin_url, target):
            raise PermissionError(f"{context}重定向到非同源地址")
        current = target
    raise ValueError(f"{context}重定向次数过多")


def fetch_result(source: SourceSpec, success: bool, **kwargs) -> SourceFetchResult:
    return SourceFetchResult(
        source_id=source.source_id,
        source_title=source.title,
        success=success,
        **kwargs,
    )
