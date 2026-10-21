"""Bounded transport, no redirects and no automatic submission retries."""
class HttpClient:
    def __init__(self, base, credential, instance_id=""):
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
                            "X-MoviePilot-Plugin-Version": "3.0.0"})
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
            raise RuntimeError(f"status_code={response.status_code}")
        return response

    def close(self):
        if self.session is not None:
            self.session.close()
