# input: URL, cookie, UA
# output: HTTP 响应 (status, text, bytes)
# pos: helper 层，curl-cffi Chrome 指纹 HTTP 客户端，CF 保护站点使用

from app.log import logger

try:
    from curl_cffi import requests as cffi_requests, CurlMime
    _CFFI_AVAILABLE = True
except ImportError:
    _CFFI_AVAILABLE = False
    logger.warning("curl-cffi 未安装，CF 保护站点可能无法访问")


class CffiClient:
    """curl-cffi Chrome 指纹 HTTP 客户端"""

    # 容器缺 CA 证书时 curl 报 (60) SSL certificate problem；命中即回退跳过校验
    _SSL_ERROR_MARKERS = ("certificate", "ssl", "curl: (60)")

    def __init__(self, cookie: str = "", ua: str = None, proxy: str = None, referer: str = None):
        if not _CFFI_AVAILABLE:
            raise ImportError("curl-cffi 未安装")
        self._session = cffi_requests.Session(impersonate="chrome")
        if cookie:
            self._session.headers["Cookie"] = cookie
        if ua:
            self._session.headers["User-Agent"] = ua
        if referer:
            self._session.headers["Referer"] = referer
        self._proxy = proxy

    def _proxies(self) -> dict:
        return {"https": self._proxy, "http": self._proxy} if self._proxy else None

    @staticmethod
    def _is_ssl_error(err: Exception) -> bool:
        msg = str(err).lower()
        return any(m in msg for m in CffiClient._SSL_ERROR_MARKERS)

    def _request(self, method: str, url: str, timeout: int = 60, **kwargs):
        """执行请求；仅 SSL 证书异常时以 verify=False 重试一次。"""
        kwargs["timeout"] = timeout
        if self._proxy:
            kwargs["proxies"] = self._proxies()
        request = getattr(self._session, method)
        try:
            return request(url, **kwargs)
        except Exception as err:
            if not self._is_ssl_error(err):
                logger.error(f"curl-cffi {method.upper()} 失败: {url} - {err}")
                return None
            logger.warning(f"curl-cffi SSL 证书校验失败，回退跳过校验重试: {url} - {err}")
            try:
                return request(url, verify=False, **kwargs)
            except Exception as retry_err:
                logger.error(f"curl-cffi {method.upper()} 回退失败: {url} - {retry_err}")
                return None

    def get(self, url: str, timeout: int = 60) -> tuple[int, str]:
        """GET 请求，返回 (status_code, text)。"""
        resp = self._request("get", url, timeout)
        return (resp.status_code, resp.text) if resp is not None else (0, "")

    def post(
        self, url: str, data: dict = None, multipart: dict = None, timeout: int = 60
    ) -> tuple[int, str]:
        """POST 请求，支持 multipart dict → CurlMime。"""
        kwargs = {}
        if multipart:
            mime = CurlMime()
            for key, value in multipart.items():
                mime.addpart(name=key, data=str(value))
            kwargs["multipart"] = mime
        elif data:
            kwargs["data"] = data
        resp = self._request("post", url, timeout, **kwargs)
        return (resp.status_code, resp.text) if resp is not None else (0, "")

    def get_bytes(self, url: str, timeout: int = 60) -> bytes | None:
        """GET 返回二进制内容，仅在 HTTP 200 时返回。"""
        resp = self._request("get", url, timeout)
        return resp.content if resp is not None and resp.status_code == 200 else None
