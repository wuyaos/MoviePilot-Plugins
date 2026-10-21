from ..core.credentials import CredentialSpec
from ..verifiers.ssdforum import SSDForumVerifier

class SSDForum:
    credential_spec = CredentialSpec()
    login_capable = False
    base = "https://ssdforum.org"
    page_path = "/dsu_paulsign-sign.html?mobile=no"
    verifier = SSDForumVerifier()

    def __init__(self, client):
        self.client = client

    def fetch_page(self):
        return self.client.request("GET", self.page_path).text

    def submit(self, page):
        return self.client.request("POST", "/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1",
            data={"formhash": self.verifier.token(page), "qdxq": "kx", "qdmode": "1",
                  "todaysay": "愿今天也是充实而愉快的一天。", "fastreply": "0"})
