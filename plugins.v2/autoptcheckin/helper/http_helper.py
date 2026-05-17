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

    def get(self, url: str, timeout: int = 60) -> tuple[int, str]:
        """GET 请求，返回 (status_code, text)"""
        try:
            kwargs = {"timeout": timeout}
            if self._proxy:
                kwargs["proxies"] = {"https": self._proxy, "http": self._proxy}
            resp = self._session.get(url, **kwargs)
            return resp.status_code, resp.text
        except Exception as e:
            logger.error(f"curl-cffi GET 失败: {url} - {e}")
            return 0, ""

    def post(
        self, url: str, data: dict = None, multipart: dict = None, timeout: int = 60
    ) -> tuple[int, str]:
        """POST 请求，支持 multipart dict → CurlMime"""
        try:
            kwargs = {"timeout": timeout}
            if self._proxy:
                kwargs["proxies"] = {"https": self._proxy, "http": self._proxy}
            if multipart:
                mp = CurlMime()
                for k, v in multipart.items():
                    mp.addpart(name=k, data=str(v))
                kwargs["multipart"] = mp
            elif data:
                kwargs["data"] = data
            resp = self._session.post(url, **kwargs)
            return resp.status_code, resp.text
        except Exception as e:
            logger.error(f"curl-cffi POST 失败: {url} - {e}")
            return 0, ""

    def get_bytes(self, url: str, timeout: int = 60) -> bytes | None:
        """GET 返回二进制内容（验证码图片）"""
        try:
            kwargs = {"timeout": timeout}
            if self._proxy:
                kwargs["proxies"] = {"https": self._proxy, "http": self._proxy}
            resp = self._session.get(url, **kwargs)
            if resp.status_code == 200:
                return resp.content
        except Exception as e:
            logger.error(f"curl-cffi 下载失败: {url} - {e}")
        return None
