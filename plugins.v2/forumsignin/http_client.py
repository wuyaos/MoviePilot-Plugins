import traceback
from typing import Optional

from app.log import logger
from curl_cffi import requests as cffi_requests


class ForumSigninHttpClient:
    """curl-cffi Chrome 指纹 HTTP 客户端，论坛签到唯一网络出口。"""

    _SSL_ERROR_MARKERS = ("certificate", "ssl", "curl: (60)")

    def __init__(
        self,
        headers: Optional[dict] = None,
        cookies=None,
        proxy_url: Optional[str] = None,
        proxy_enabled: bool = False,
        timeout: int = 30,
    ):
        self._session = cffi_requests.Session(impersonate="chrome", trust_env=False)
        if headers:
            self._session.headers.update(headers)
        if cookies:
            if isinstance(cookies, str):
                self._session.headers["Cookie"] = cookies
            else:
                self._session.cookies.update(cookies)
        self._proxy_url = proxy_url if proxy_enabled else None
        self._proxy_enabled = proxy_enabled
        self._timeout = timeout

    def _proxies(self):
        return {"https": self._proxy_url, "http": self._proxy_url} if self._proxy_url else None

    @staticmethod
    def _is_ssl_error(err: Exception) -> bool:
        msg = str(err).lower()
        return any(marker in msg for marker in ForumSigninHttpClient._SSL_ERROR_MARKERS)

    def _kwargs(self, **kwargs):
        request_kwargs = {"timeout": self._timeout, **kwargs}
        proxies = self._proxies()
        if proxies:
            request_kwargs["proxies"] = proxies
        return request_kwargs

    def _log_error(self, method: str, url: str, exc: Exception):
        logger.error(
            f"HTTP {method.upper()} 失败 url={url} proxy_enabled={self._proxy_enabled} "
            f"proxy_url={self._proxy_url} trust_env=False exc_type={type(exc).__name__} exc={exc}\n"
            f"{traceback.format_exc()}"
        )

    def get_res(self, url: str, raise_exception: bool = False, **kwargs):
        request_kwargs = self._kwargs(**kwargs)
        try:
            return self._session.get(url, **request_kwargs)
        except Exception as e:
            if self._is_ssl_error(e):
                try:
                    return self._session.get(url, verify=False, **request_kwargs)
                except Exception as retry_e:
                    self._log_error("GET", url, retry_e)
                    if raise_exception:
                        raise
                    return None
            self._log_error("GET", url, e)
            if raise_exception:
                raise
            return None

    def post_res(self, url: str, raise_exception: bool = False, **kwargs):
        request_kwargs = self._kwargs(**kwargs)
        try:
            return self._session.post(url, **request_kwargs)
        except Exception as e:
            if self._is_ssl_error(e):
                try:
                    return self._session.post(url, verify=False, **request_kwargs)
                except Exception as retry_e:
                    self._log_error("POST", url, retry_e)
                    if raise_exception:
                        raise
                    return None
            self._log_error("POST", url, e)
            if raise_exception:
                raise
            return None
