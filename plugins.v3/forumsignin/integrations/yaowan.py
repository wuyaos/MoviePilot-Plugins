from ..core.credentials import CredentialSpec
from ..verifiers.yaowan import YaowanVerifier

class Yaowan:
    credential_spec = CredentialSpec()
    login_capable = False
    base = "https://invites.fun"
    page_path = "/"
    verifier = YaowanVerifier()

    def __init__(self, client):
        self.client = client

    def fetch_page(self):
        return self.client.request("GET", self.page_path).text

    def submit(self, page):
        token = self.verifier.token(page)
        return self.client.request("POST", "/api/checkin", headers={
            "x-csrf-token": token, "Origin": self.base, "Referer": self.base + "/"})
