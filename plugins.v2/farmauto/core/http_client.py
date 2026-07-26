import logging
import time
from typing import Any, Dict, Optional

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger(__name__)


class AuthError(requests.HTTPError):
    """站点认证失效。"""


class FarmHttpClient:
    def __init__(
        self,
        timeout: int = 15,
        retry_count: int = 3,
        retry_interval: float = 3.0,
        use_proxy: bool = False,
        proxy_url: Optional[str] = None,
        min_interval: float = 0.3,
    ):
        self.timeout = timeout
        self.retry_count = max(0, retry_count)
        self.retry_interval = retry_interval
        self.min_interval = max(0.0, min_interval)
        self._last_request_at = 0.0
        self.session = requests.Session()
        self.session.headers.update({
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
        })
        self.proxy_url = proxy_url or (self._moviepilot_proxy() if use_proxy else None)

    @staticmethod
    def _moviepilot_proxy() -> Optional[str]:
        try:
            from app.config import get_config

            return get_config().get("app", {}).get("proxy")
        except Exception:
            return None

    def get(self, url: str, cookies: dict, allow_redirects: bool = True) -> requests.Response:
        return self._request("GET", url, cookies=cookies, allow_redirects=allow_redirects)

    def post(
        self,
        url: str,
        cookies: dict,
        data: Any = None,
        json: Any = None,
        allow_redirects: bool = True,
    ) -> requests.Response:
        return self._request(
            "POST",
            url,
            cookies=cookies,
            data=data,
            json=json,
            allow_redirects=allow_redirects,
        )

    def _rate_limit(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_request_at)
        if wait > 0:
            time.sleep(wait)

    def _request(self, method: str, url: str, cookies: Dict[str, str], **kwargs: Any) -> requests.Response:
        last_error: Optional[BaseException] = None
        for attempt in range(self.retry_count + 1):
            self._rate_limit()
            proxies = {"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None
            try:
                response = self._send(method, url, cookies, proxies, **kwargs)
            except (requests.Timeout, requests.ConnectionError) as error:
                last_error = error
                if proxies:
                    logger.warning("农场请求代理连接失败，回退直连")
                    try:
                        response = self._send(method, url, cookies, None, **kwargs)
                    except (requests.Timeout, requests.ConnectionError) as direct_error:
                        last_error = direct_error
                    else:
                        self._check_auth(response)
                        if response.status_code < 500:
                            return response
                        last_error = requests.HTTPError(
                            f"HTTP {response.status_code}", response=response
                        )
                if attempt < self.retry_count:
                    time.sleep(min(self.retry_interval * (2 ** attempt), 30.0))
                continue
            self._check_auth(response)
            if response.status_code < 500:
                return response
            last_error = requests.HTTPError(
                f"HTTP {response.status_code}", response=response
            )
            if attempt < self.retry_count:
                time.sleep(min(self.retry_interval * (2 ** attempt), 30.0))
        if last_error:
            raise last_error
        raise requests.RequestException("农场请求失败")

    def _send(
        self,
        method: str,
        url: str,
        cookies: Dict[str, str],
        proxies: Optional[Dict[str, str]],
        **kwargs: Any,
    ) -> requests.Response:
        try:
            return self.session.request(
                method,
                url,
                cookies=cookies,
                proxies=proxies,
                timeout=self.timeout,
                verify=False,
                **kwargs,
            )
        finally:
            self._last_request_at = time.monotonic()

    @staticmethod
    def _check_auth(response: requests.Response) -> requests.Response:
        if response.status_code in (401, 403):
            raise AuthError(f"HTTP {response.status_code}", response=response)
        return response
