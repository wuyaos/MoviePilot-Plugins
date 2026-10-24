"""Bounded transport, no redirects and no automatic submission retries."""
import re


def response_text(response):
    """Decode response bytes using the page-declared charset before fallback text."""
    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        head = content[:8192].decode("latin-1", errors="ignore")
        match = re.search(r"<meta[^>]+charset\s*=\s*[\"']?\s*([\w.-]+)", head, re.I)
        if not match:
            match = re.search(r"<meta[^>]+content\s*=\s*[\"'][^\"']*charset\s*=\s*([\w.-]+)", head, re.I)
        charset = match.group(1) if match else "utf-8"
        try:
            return content.decode(charset, errors="replace")
        except LookupError:
            pass
    return getattr(response, "text", "") or ""


class HttpClient:
    def __init__(self, base, credential, instance_id="", version=""):
        self.base = base
        self.credential = credential
        self.instance_id = instance_id
        self.session = None

    def request(self, method, path, **kwargs):
        if self.session is None:
            from curl_cffi.requests import Session
            self.session = Session(impersonate="chrome")
        headers = {"User-Agent": self.credential.ua or "MoviePilot-ForumSignin/3.0.0"}
        if self.credential.source == "local_api":
            headers.update({"Authorization": f"Bearer {self.credential.value}",
                            "X-MoviePilot-Instance-Id": self.instance_id,
                            "X-MoviePilot-Plugin-Version": self.version or "3.0.0"})
            if self.version:
                headers["X-MoviePilot-Version"] = self.version
        else:
            headers["Cookie"] = self.credential.value
        headers.update(kwargs.pop("headers", {}))
        proxies = None
        if self.credential.proxy:
            from app.sdk.config import settings
            proxies = settings.PROXY
        response = self.session.request(method, self.base + path, headers=headers,
                                        timeout=30, allow_redirects=False, proxies=proxies, **kwargs)
        if response is None:
            raise RuntimeError("no_response")
        if response.status_code != 200:
            detail = ""
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = str(payload.get("message") or "")[:200]
            except Exception:
                detail = ""
            raise RuntimeError(f"HTTP {response.status_code}" + (f": {detail}" if detail else ""))
        return response

    def text(self, response):
        return response_text(response)

    def close(self):
        if self.session is not None:
            self.session.close()
